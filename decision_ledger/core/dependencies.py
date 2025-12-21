"""FastAPI dependencies for authentication, authorization, and context."""

import logging
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Organization, OrganizationMember, User
from .config import get_settings
from .database import get_session, set_tenant_context
from .security import decode_token, decode_clerk_token, ClerkTokenPayload

logger = logging.getLogger(__name__)
settings = get_settings()

# Security scheme
bearer_scheme = HTTPBearer(auto_error=False)


async def get_or_create_clerk_user(
    session: AsyncSession,
    clerk_payload: ClerkTokenPayload,
) -> User:
    """Get or create a user from Clerk token payload."""
    # Look up user by Clerk ID (auth_provider_id)
    result = await session.execute(
        select(User).where(
            User.auth_provider == "clerk",
            User.auth_provider_id == clerk_payload.sub,
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()

    if user:
        # Update user info if changed
        needs_update = False
        if clerk_payload.email and user.email != clerk_payload.email:
            user.email = clerk_payload.email
            needs_update = True
        if clerk_payload.full_name and user.name != clerk_payload.full_name:
            user.name = clerk_payload.full_name
            needs_update = True
        if clerk_payload.image_url and user.avatar_url != clerk_payload.image_url:
            user.avatar_url = clerk_payload.image_url
            needs_update = True
        if needs_update:
            await session.commit()
        return user

    # Create new user
    user = User(
        id=uuid4(),
        email=clerk_payload.email or f"{clerk_payload.sub}@clerk.local",
        name=clerk_payload.full_name,
        avatar_url=clerk_payload.image_url,
        auth_provider="clerk",
        auth_provider_id=clerk_payload.sub,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    logger.info(f"Created new user from Clerk: {user.id} ({user.email})")
    return user


async def get_or_create_clerk_organization(
    session: AsyncSession,
    clerk_org_id: str,
    clerk_org_slug: str | None,
    user: User,
    role: str = "member",
) -> tuple[Organization, str]:
    """Get or create an organization from Clerk org ID."""
    # Look up organization by Clerk org ID (stored in settings)
    result = await session.execute(
        select(Organization).where(
            Organization.settings["clerk_org_id"].astext == clerk_org_id,
            Organization.deleted_at.is_(None),
        )
    )
    org = result.scalar_one_or_none()

    if not org:
        # Create new organization
        slug = clerk_org_slug or f"org-{clerk_org_id[-8:]}"
        # Ensure unique slug
        base_slug = slug
        counter = 1
        while True:
            existing = await session.execute(
                select(Organization).where(Organization.slug == slug)
            )
            if not existing.scalar_one_or_none():
                break
            slug = f"{base_slug}-{counter}"
            counter += 1

        org = Organization(
            id=uuid4(),
            slug=slug,
            name=clerk_org_slug or f"Organization {clerk_org_id[-8:]}",
            settings={"clerk_org_id": clerk_org_id},
        )
        session.add(org)
        await session.commit()
        await session.refresh(org)
        logger.info(f"Created new organization from Clerk: {org.id} ({org.slug})")

    # Ensure user is a member of the organization
    result = await session.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org.id,
            OrganizationMember.user_id == user.id,
        )
    )
    membership = result.scalar_one_or_none()

    if not membership:
        # Map Clerk roles to our roles
        mapped_role = "member"
        if role in ("org:admin", "admin"):
            mapped_role = "admin"
        elif role in ("org:owner", "owner"):
            mapped_role = "owner"

        membership = OrganizationMember(
            id=uuid4(),
            organization_id=org.id,
            user_id=user.id,
            role=mapped_role,
        )
        session.add(membership)
        await session.commit()
        logger.info(f"Added user {user.id} to organization {org.id} as {mapped_role}")
        return org, mapped_role

    return org, membership.role


class CurrentUser:
    """Represents the authenticated user context."""

    def __init__(
        self,
        user: User,
        organization_id: UUID | None = None,
        org_role: str | None = None,
    ):
        self.user = user
        self.organization_id = organization_id
        self.org_role = org_role

    @property
    def id(self) -> UUID:
        return self.user.id

    @property
    def is_admin(self) -> bool:
        return self.org_role in ("owner", "admin")

    @property
    def is_owner(self) -> bool:
        return self.org_role == "owner"


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
    x_organization_id: Annotated[str | None, Header()] = None,
) -> CurrentUser:
    """Dependency to get the current authenticated user.

    Validates JWT token (Clerk or legacy) and optionally sets organization context.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    user: User | None = None
    org_id: UUID | None = None
    org_role: str | None = None

    # Try Clerk authentication first if enabled
    if settings.clerk_enabled:
        logger.info(f"Clerk enabled, attempting to decode token (first 50 chars): {token[:50]}...")
        clerk_payload = decode_clerk_token(token)
        if clerk_payload:
            logger.info(f"Clerk token decoded for user: {clerk_payload.sub}, org_id: {clerk_payload.org_id}")

            # Get or create user from Clerk
            user = await get_or_create_clerk_user(session, clerk_payload)

            # Handle organization context from Clerk
            if clerk_payload.org_id:
                # User has an active organization in Clerk
                org, role = await get_or_create_clerk_organization(
                    session,
                    clerk_payload.org_id,
                    clerk_payload.org_slug,
                    user,
                    clerk_payload.org_role or "member",
                )
                org_id = org.id
                org_role = role
            elif x_organization_id:
                # Use header-provided org ID
                try:
                    org_id = UUID(x_organization_id)
                    # Verify membership
                    result = await session.execute(
                        select(OrganizationMember).where(
                            OrganizationMember.organization_id == org_id,
                            OrganizationMember.user_id == user.id,
                        )
                    )
                    membership = result.scalar_one_or_none()
                    if membership:
                        org_role = membership.role
                    else:
                        org_id = None  # Not a member, ignore header
                except ValueError:
                    pass

            # Set RLS context if we have an org
            if org_id:
                await set_tenant_context(session, org_id, user.id)

            return CurrentUser(user=user, organization_id=org_id, org_role=org_role)

    # Fall back to legacy token authentication
    logger.info("Clerk auth failed or not enabled, trying legacy auth")
    payload = decode_token(token)
    if not payload:
        logger.warning(f"Legacy token decode failed for token (first 50 chars): {token[:50]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token - neither Clerk nor legacy auth succeeded",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    # Get user from database
    user_id = UUID(payload.sub)
    result = await session.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Determine organization context
    # Priority: header > token > None
    if x_organization_id:
        try:
            org_id = UUID(x_organization_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid organization ID format",
            )
    elif payload.org:
        org_id = UUID(payload.org)

    # Verify organization membership and get role
    if org_id:
        result = await session.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == user_id,
            )
        )
        membership = result.scalar_one_or_none()

        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of this organization",
            )

        org_role = membership.role

        # Set RLS context
        await set_tenant_context(session, org_id, user_id)

    return CurrentUser(user=user, organization_id=org_id, org_role=org_role)


async def get_current_user_optional(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CurrentUser | None:
    """Optional authentication - returns None if not authenticated."""
    if not credentials:
        return None

    try:
        return await get_current_user(credentials, session)
    except HTTPException:
        return None


def require_org_context(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    """Require that an organization context is set."""
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization context required. Set X-Organization-ID header.",
        )
    return current_user


def require_admin(
    current_user: Annotated[CurrentUser, Depends(require_org_context)],
) -> CurrentUser:
    """Require admin or owner role in the current organization."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


def require_owner(
    current_user: Annotated[CurrentUser, Depends(require_org_context)],
) -> CurrentUser:
    """Require owner role in the current organization."""
    if not current_user.is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner privileges required",
        )
    return current_user


# Type aliases for cleaner dependency injection
CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
OrgContextDep = Annotated[CurrentUser, Depends(require_org_context)]
AdminDep = Annotated[CurrentUser, Depends(require_admin)]
OwnerDep = Annotated[CurrentUser, Depends(require_owner)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
