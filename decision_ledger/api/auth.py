"""Authentication API routes for Imputable.

This module provides login/token endpoints for development and production use.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core import SessionDep
from ..core.security import create_access_token, verify_password
from ..models import Organization, OrganizationMember, User

router = APIRouter(prefix="/auth", tags=["authentication"])


# =============================================================================
# REQUEST/RESPONSE SCHEMAS
# =============================================================================


class LoginRequest(BaseModel):
    """Login request with email and password."""
    email: EmailStr
    password: str


class DevLoginRequest(BaseModel):
    """Dev login request - just email (no password check)."""
    email: EmailStr
    organization_id: str | None = None


class TokenResponse(BaseModel):
    """Token response after successful login."""
    access_token: str
    token_type: str = "bearer"
    user_id: str
    user_name: str
    user_email: str
    organization_id: str | None = None
    organization_name: str | None = None


class UserInfo(BaseModel):
    """User info for the current session."""
    id: str
    name: str
    email: str
    organizations: list[dict]


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    session: SessionDep,
):
    """Login with email and password."""
    # Find user by email
    result = await session.execute(
        select(User).where(
            User.email == request.email,
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Verify password
    if not user.password_hash or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Get user's first organization
    org_result = await session.execute(
        select(OrganizationMember, Organization)
        .join(Organization, OrganizationMember.organization_id == Organization.id)
        .where(OrganizationMember.user_id == user.id)
        .limit(1)
    )
    org_row = org_result.first()

    org_id = None
    org_name = None
    if org_row:
        membership, org = org_row
        org_id = org.id
        org_name = org.name

    # Create access token
    token = create_access_token(user_id=user.id, organization_id=org_id)

    return TokenResponse(
        access_token=token,
        user_id=str(user.id),
        user_name=user.name,
        user_email=user.email,
        organization_id=str(org_id) if org_id else None,
        organization_name=org_name,
    )


@router.post("/dev-login", response_model=TokenResponse)
async def dev_login(
    request: DevLoginRequest,
    session: SessionDep,
):
    """
    Development login - bypasses password check.

    WARNING: This should only be enabled in development environments.
    In production, this endpoint should be disabled or protected.
    """
    import os

    # Only allow in non-production or if explicitly enabled
    env = os.getenv("ENVIRONMENT", "development")
    if env == "production" and not os.getenv("ALLOW_DEV_LOGIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dev login not available in production",
        )

    # Find user by email
    result = await session.execute(
        select(User).where(
            User.email == request.email,
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with email {request.email} not found",
        )

    # Get organization
    org_id = None
    org_name = None

    if request.organization_id:
        try:
            org_uuid = UUID(request.organization_id)
            org_result = await session.execute(
                select(OrganizationMember, Organization)
                .join(Organization, OrganizationMember.organization_id == Organization.id)
                .where(
                    OrganizationMember.user_id == user.id,
                    OrganizationMember.organization_id == org_uuid,
                )
            )
            org_row = org_result.first()
            if org_row:
                membership, org = org_row
                org_id = org.id
                org_name = org.name
        except ValueError:
            pass

    # If no org specified, get user's first organization
    if not org_id:
        org_result = await session.execute(
            select(OrganizationMember, Organization)
            .join(Organization, OrganizationMember.organization_id == Organization.id)
            .where(OrganizationMember.user_id == user.id)
            .limit(1)
        )
        org_row = org_result.first()
        if org_row:
            membership, org = org_row
            org_id = org.id
            org_name = org.name

    # Create access token
    token = create_access_token(user_id=user.id, organization_id=org_id)

    return TokenResponse(
        access_token=token,
        user_id=str(user.id),
        user_name=user.name,
        user_email=user.email,
        organization_id=str(org_id) if org_id else None,
        organization_name=org_name,
    )


@router.get("/users", response_model=list[dict])
async def list_dev_users(session: SessionDep):
    """
    List available users for dev login.

    WARNING: This should only be enabled in development environments.
    """
    import os

    env = os.getenv("ENVIRONMENT", "development")
    if env == "production" and not os.getenv("ALLOW_DEV_LOGIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not available in production",
        )

    result = await session.execute(
        select(User).where(User.deleted_at.is_(None)).limit(20)
    )
    users = result.scalars().all()

    user_list = []
    for user in users:
        # Get user's organizations
        org_result = await session.execute(
            select(Organization)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .where(OrganizationMember.user_id == user.id)
        )
        orgs = org_result.scalars().all()

        user_list.append({
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
            "organizations": [
                {"id": str(org.id), "name": org.name, "slug": org.slug}
                for org in orgs
            ],
        })

    return user_list
