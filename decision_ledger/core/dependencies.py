"""FastAPI dependencies for authentication, authorization, and context."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Organization, OrganizationMember, User
from .database import get_session, set_tenant_context
from .security import decode_token

# Security scheme
bearer_scheme = HTTPBearer(auto_error=False)


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

    Validates JWT token and optionally sets organization context.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Decode token
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
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
    org_id: UUID | None = None
    org_role: str | None = None

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
