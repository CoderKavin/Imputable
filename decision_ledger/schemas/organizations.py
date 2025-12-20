"""Pydantic schemas for Organizations, Teams, and Users."""

from datetime import datetime
from uuid import UUID

from pydantic import EmailStr, Field

from .base import (
    LedgerBaseModel,
    OrgRole,
    TeamRole,
    TimestampMixin,
)


# =============================================================================
# USER SCHEMAS
# =============================================================================


class UserBase(LedgerBaseModel):
    """Base user fields."""

    email: EmailStr
    name: str = Field(..., min_length=1, max_length=255)
    avatar_url: str | None = None


class UserCreate(UserBase):
    """Create a new user (typically from auth provider)."""

    auth_provider: str = "email"
    auth_provider_id: str | None = None


class UserResponse(UserBase):
    """Full user response."""

    id: UUID
    created_at: datetime
    last_login_at: datetime | None = None


class UserProfile(UserResponse):
    """User with their organization memberships."""

    organizations: list["OrganizationMembershipSummary"]


# =============================================================================
# ORGANIZATION SCHEMAS
# =============================================================================


class OrganizationBase(LedgerBaseModel):
    """Base organization fields."""

    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(
        ...,
        min_length=3,
        max_length=63,
        pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$",
        description="URL-safe identifier (lowercase, alphanumeric, hyphens)",
    )


class OrganizationCreate(OrganizationBase):
    """Create a new organization."""

    settings: dict = Field(default_factory=dict)


class OrganizationUpdate(LedgerBaseModel):
    """Update organization settings."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    settings: dict | None = None


class OrganizationResponse(OrganizationBase):
    """Full organization response."""

    id: UUID
    settings: dict
    created_at: datetime
    deleted_at: datetime | None = None


class OrganizationWithStats(OrganizationResponse):
    """Organization with usage statistics."""

    member_count: int
    team_count: int
    decision_count: int
    active_decision_count: int  # Non-superseded/deprecated


# =============================================================================
# ORGANIZATION MEMBERSHIP SCHEMAS
# =============================================================================


class OrganizationMemberCreate(LedgerBaseModel):
    """Add a member to an organization."""

    user_id: UUID
    role: OrgRole = OrgRole.MEMBER


class OrganizationMemberUpdate(LedgerBaseModel):
    """Update a member's role."""

    role: OrgRole


class OrganizationMemberResponse(LedgerBaseModel):
    """Organization membership record."""

    id: UUID
    organization_id: UUID
    user: UserResponse
    role: OrgRole
    created_at: datetime
    invited_by: UserResponse | None = None


class OrganizationMembershipSummary(LedgerBaseModel):
    """Summary of user's membership in an org."""

    organization_id: UUID
    organization_name: str
    organization_slug: str
    role: OrgRole


# =============================================================================
# TEAM SCHEMAS
# =============================================================================


class TeamBase(LedgerBaseModel):
    """Base team fields."""

    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(
        ...,
        min_length=2,
        max_length=63,
        pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$",
    )
    description: str | None = None


class TeamCreate(TeamBase):
    """Create a new team."""

    parent_team_id: UUID | None = None


class TeamUpdate(LedgerBaseModel):
    """Update team details."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    parent_team_id: UUID | None = None


class TeamResponse(TeamBase):
    """Full team response."""

    id: UUID
    organization_id: UUID
    parent_team_id: UUID | None = None
    created_at: datetime
    deleted_at: datetime | None = None


class TeamWithMembers(TeamResponse):
    """Team with member list."""

    members: list["TeamMemberResponse"]
    member_count: int


class TeamHierarchy(TeamResponse):
    """Team with parent/child relationships."""

    parent_team: "TeamResponse | None" = None
    child_teams: list["TeamResponse"]


# =============================================================================
# TEAM MEMBERSHIP SCHEMAS
# =============================================================================


class TeamMemberCreate(LedgerBaseModel):
    """Add a member to a team."""

    user_id: UUID
    role: TeamRole = TeamRole.MEMBER


class TeamMemberUpdate(LedgerBaseModel):
    """Update team member role."""

    role: TeamRole


class TeamMemberResponse(LedgerBaseModel):
    """Team membership record."""

    id: UUID
    team_id: UUID
    user: UserResponse
    role: TeamRole
    created_at: datetime


# =============================================================================
# TAG SCHEMAS
# =============================================================================


class TagBase(LedgerBaseModel):
    """Base tag fields."""

    name: str = Field(..., min_length=1, max_length=100)
    color: str = Field(
        default="#6366f1",
        pattern=r"^#[0-9a-fA-F]{6}$",
        description="Hex color code",
    )
    description: str | None = None


class TagCreate(TagBase):
    """Create a new tag."""

    pass


class TagResponse(TagBase):
    """Full tag response."""

    id: UUID
    organization_id: UUID
    created_at: datetime


class TagWithUsage(TagResponse):
    """Tag with usage count."""

    decision_count: int


# Resolve forward references
UserProfile.model_rebuild()
TeamHierarchy.model_rebuild()
