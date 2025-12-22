"""FastAPI dependencies for authentication, authorization, and context."""

import logging
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Organization, OrganizationMember, User, SubscriptionTier
from .config import get_settings
from .database import get_session, set_tenant_context
from .security import decode_token, decode_firebase_token, FirebaseTokenPayload

logger = logging.getLogger(__name__)
settings = get_settings()

# Security scheme
bearer_scheme = HTTPBearer(auto_error=False)


async def get_or_create_firebase_user(
    session: AsyncSession,
    firebase_payload: FirebaseTokenPayload,
) -> User:
    """Get or create a user from Firebase token payload."""
    # Look up user by Firebase UID (auth_provider_id)
    result = await session.execute(
        select(User).where(
            User.auth_provider == "firebase",
            User.auth_provider_id == firebase_payload.uid,
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()

    if user:
        # Update user info if changed
        needs_update = False
        if firebase_payload.email and user.email != firebase_payload.email:
            user.email = firebase_payload.email
            needs_update = True
        if firebase_payload.name and user.name != firebase_payload.name:
            user.name = firebase_payload.name
            needs_update = True
        if firebase_payload.picture and user.avatar_url != firebase_payload.picture:
            user.avatar_url = firebase_payload.picture
            needs_update = True
        if needs_update:
            await session.commit()
        return user

    # Create new user
    user_name = firebase_payload.name or firebase_payload.email or f"User {firebase_payload.uid[-8:]}"
    user_email = firebase_payload.email or f"{firebase_payload.uid}@firebase.local"

    logger.info(f"Creating new Firebase user: email={user_email}, name={user_name}, uid={firebase_payload.uid}")

    user = User(
        id=uuid4(),
        email=user_email,
        name=user_name,
        avatar_url=firebase_payload.picture,
        auth_provider="firebase",
        auth_provider_id=firebase_payload.uid,
    )
    session.add(user)
    try:
        await session.commit()
        await session.refresh(user)
        logger.info(f"Created new user from Firebase: {user.id} ({user.email})")
    except Exception as e:
        logger.error(f"Failed to create Firebase user: {e}")
        await session.rollback()
        raise
    return user


async def get_user_organization(
    session: AsyncSession,
    user: User,
    org_id: str | None = None,
) -> tuple[Organization | None, str | None]:
    """Get user's organization by ID or their first organization."""
    if org_id:
        try:
            org_uuid = UUID(org_id)
            # Verify membership
            result = await session.execute(
                select(OrganizationMember, Organization)
                .join(Organization, OrganizationMember.organization_id == Organization.id)
                .where(
                    OrganizationMember.organization_id == org_uuid,
                    OrganizationMember.user_id == user.id,
                    Organization.deleted_at.is_(None),
                )
            )
            row = result.first()
            if row:
                membership, org = row
                return org, membership.role
        except ValueError:
            logger.warning(f"Invalid organization ID format: {org_id}")
            pass

    # Get user's first organization
    result = await session.execute(
        select(OrganizationMember, Organization)
        .join(Organization, OrganizationMember.organization_id == Organization.id)
        .where(
            OrganizationMember.user_id == user.id,
            Organization.deleted_at.is_(None),
        )
        .limit(1)
    )
    row = result.first()
    if row:
        membership, org = row
        return org, membership.role

    return None, None


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

    Validates JWT token (Firebase or legacy) and optionally sets organization context.
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

    # Try Firebase authentication first if enabled
    if settings.firebase_enabled:
        logger.info(f"Firebase enabled, attempting to decode token (first 50 chars): {token[:50]}...")
        firebase_payload = decode_firebase_token(token)
        if firebase_payload:
            logger.info(f"Firebase token decoded for user: {firebase_payload.uid}, email: {firebase_payload.email}")

            # Get or create user from Firebase
            user = await get_or_create_firebase_user(session, firebase_payload)

            # Handle organization context from header
            if x_organization_id:
                logger.info(f"Using X-Organization-ID header: {x_organization_id}")
                try:
                    org, role = await get_user_organization(session, user, x_organization_id)
                    if org:
                        org_id = org.id
                        org_role = role
                except Exception as e:
                    logger.error(f"Error processing X-Organization-ID '{x_organization_id}': {e}", exc_info=True)
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to process organization: {str(e)}",
                    )
            else:
                # Get user's first organization if no header
                org, role = await get_user_organization(session, user)
                if org:
                    org_id = org.id
                    org_role = role

            # Set RLS context if we have an org
            if org_id:
                await set_tenant_context(session, org_id, user.id)

            return CurrentUser(user=user, organization_id=org_id, org_role=org_role)

    # Fall back to legacy token authentication
    logger.info("Firebase auth failed or not enabled, trying legacy auth")
    payload = decode_token(token)
    if not payload:
        logger.warning(f"Legacy token decode failed for token (first 50 chars): {token[:50]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token - neither Firebase nor legacy auth succeeded",
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
