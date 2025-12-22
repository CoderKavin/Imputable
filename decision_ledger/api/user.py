"""User API routes for Imputable.

This module provides user-related endpoints like organization management.
"""

from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from ..core import SessionDep
from ..core.dependencies import CurrentUserDep
from ..models import Organization, OrganizationMember, SubscriptionTier

router = APIRouter(prefix="/me", tags=["user"])


# =============================================================================
# SCHEMAS
# =============================================================================


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


@router.get("/organizations", response_model=OrganizationsListResponse)
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


@router.get("/profile")
async def get_my_profile(current_user: CurrentUserDep):
    """Get the current user's profile."""
    return {
        "id": str(current_user.id),
        "email": current_user.user.email,
        "name": current_user.user.name,
        "avatar_url": current_user.user.avatar_url,
        "current_organization_id": str(current_user.organization_id) if current_user.organization_id else None,
        "org_role": current_user.org_role,
    }
