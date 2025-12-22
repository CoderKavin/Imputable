"""Authentication API routes for Imputable.

This module provides login/token endpoints for development and production use.
"""

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core import SessionDep
from ..core.security import create_access_token, verify_password
from ..core.dependencies import CurrentUserDep
from ..models import Organization, OrganizationMember, User, SubscriptionTier

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


class OrganizationResponse(BaseModel):
    """Organization info."""
    id: str
    name: str
    slug: str
    role: str | None = None


class OrganizationsListResponse(BaseModel):
    """List of organizations."""
    organizations: list[OrganizationResponse]


class CreateOrganizationRequest(BaseModel):
    """Request to create a new organization."""
    name: str
    slug: str


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

    This is enabled for demo purposes. In a real production environment,
    you would disable this and use proper authentication.
    """
    try:
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Login error: {str(e)}",
        )


@router.get("/users", response_model=list[dict])
async def list_dev_users(session: SessionDep):
    """
    List available users for dev login.

    This is enabled for demo purposes.
    """
    try:
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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )


# =============================================================================
# USER ORGANIZATIONS
# =============================================================================


@router.get("/me/organizations", response_model=OrganizationsListResponse)
async def get_my_organizations(
    current_user: CurrentUserDep,
    session: SessionDep,
):
    """Get all organizations the current user belongs to."""
    result = await session.execute(
        select(Organization, OrganizationMember.role)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(
            OrganizationMember.user_id == current_user.id,
            Organization.deleted_at.is_(None),
        )
        .order_by(Organization.name)
    )
    rows = result.all()

    organizations = [
        OrganizationResponse(
            id=str(org.id),
            name=org.name,
            slug=org.slug,
            role=role,
        )
        for org, role in rows
    ]

    return OrganizationsListResponse(organizations=organizations)


@router.post("/organizations", response_model=OrganizationResponse)
async def create_organization(
    request: CreateOrganizationRequest,
    current_user: CurrentUserDep,
    session: SessionDep,
):
    """Create a new organization and add the current user as owner."""
    import re

    # Validate and clean slug
    slug = request.slug.lower().strip()
    slug = re.sub(r'[^a-z0-9-]', '-', slug)
    slug = re.sub(r'-+', '-', slug)  # Remove consecutive hyphens
    slug = slug.strip('-')  # Remove leading/trailing hyphens

    if len(slug) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slug must be at least 3 characters",
        )

    # Check if slug already exists
    existing = await session.execute(
        select(Organization).where(Organization.slug == slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An organization with this slug already exists",
        )

    # Create organization
    org = Organization(
        id=uuid4(),
        name=request.name,
        slug=slug,
        settings={},
        subscription_tier=SubscriptionTier.FREE,
    )
    session.add(org)

    # Add current user as owner
    membership = OrganizationMember(
        id=uuid4(),
        organization_id=org.id,
        user_id=current_user.id,
        role="owner",
    )
    session.add(membership)

    await session.commit()
    await session.refresh(org)

    return OrganizationResponse(
        id=str(org.id),
        name=org.name,
        slug=org.slug,
        role="owner",
    )
