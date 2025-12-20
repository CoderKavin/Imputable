"""Pydantic schemas for Decision and DecisionVersion entities."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from .base import (
    ApprovalStatus,
    DecisionRef,
    DecisionStatus,
    ImpactLevel,
    LedgerBaseModel,
    RelationshipType,
    TeamRef,
    UserRef,
)


# =============================================================================
# DECISION CONTENT (JSONB Structure)
# =============================================================================


class Alternative(LedgerBaseModel):
    """An alternative that was considered but rejected."""

    name: str = Field(..., min_length=1, max_length=200)
    rejected_reason: str = Field(..., min_length=1)


class DecisionContent(LedgerBaseModel):
    """Structured content of a decision (maps to JSONB)."""

    context: str = Field(
        ...,
        min_length=1,
        description="Background and problem statement (Markdown)",
    )
    choice: str = Field(
        ...,
        min_length=1,
        description="The decision that was made (Markdown)",
    )
    rationale: str = Field(
        ...,
        min_length=1,
        description="Why this choice was made (Markdown)",
    )
    alternatives: list[Alternative] = Field(
        default_factory=list,
        description="Alternatives that were rejected",
    )
    consequences: str | None = Field(
        default=None,
        description="Expected outcomes and implications",
    )
    review_date: datetime | None = Field(
        default=None,
        description="Scheduled date to review this decision",
    )


# =============================================================================
# DECISION VERSION SCHEMAS
# =============================================================================


class DecisionVersionBase(LedgerBaseModel):
    """Base fields for decision version."""

    title: str = Field(..., min_length=1, max_length=500)
    impact_level: ImpactLevel = ImpactLevel.MEDIUM
    content: DecisionContent
    tags: list[str] = Field(default_factory=list, max_length=20)
    custom_fields: dict = Field(default_factory=dict)


class DecisionVersionCreate(DecisionVersionBase):
    """Schema for creating a new decision version."""

    change_summary: str | None = Field(
        default=None,
        max_length=500,
        description="Brief description of changes from previous version",
    )

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        # Normalize tags: lowercase, strip whitespace
        return [tag.lower().strip() for tag in v if tag.strip()]


class DecisionVersionResponse(DecisionVersionBase):
    """Full decision version response."""

    id: UUID
    decision_id: UUID
    version_number: int
    created_by: UserRef
    created_at: datetime
    change_summary: str | None = None
    content_hash: str | None = None


class DecisionVersionSummary(LedgerBaseModel):
    """Abbreviated version info for lists."""

    id: UUID
    version_number: int
    title: str
    impact_level: ImpactLevel
    created_by: UserRef
    created_at: datetime
    change_summary: str | None = None


# =============================================================================
# DECISION SCHEMAS
# =============================================================================


class DecisionCreate(LedgerBaseModel):
    """Schema for creating a new decision."""

    title: str = Field(..., min_length=1, max_length=500)
    impact_level: ImpactLevel = ImpactLevel.MEDIUM
    content: DecisionContent
    tags: list[str] = Field(default_factory=list, max_length=20)
    custom_fields: dict = Field(default_factory=dict)
    owner_team_id: UUID | None = None
    reviewer_ids: list[UUID] = Field(
        default_factory=list,
        description="Users who must approve this decision",
    )


class DecisionUpdate(LedgerBaseModel):
    """Schema for updating a decision (creates new version)."""

    title: str = Field(..., min_length=1, max_length=500)
    impact_level: ImpactLevel
    content: DecisionContent
    tags: list[str] = Field(default_factory=list, max_length=20)
    custom_fields: dict = Field(default_factory=dict)
    change_summary: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Required: describe what changed",
    )
    reviewer_ids: list[UUID] | None = Field(
        default=None,
        description="New reviewers for this version (None = keep existing)",
    )


class DecisionResponse(LedgerBaseModel):
    """Full decision response with current version."""

    id: UUID
    organization_id: UUID
    decision_number: int
    status: DecisionStatus
    owner_team: TeamRef | None = None
    created_by: UserRef
    created_at: datetime
    deleted_at: datetime | None = None

    # Current version (expanded)
    current_version: DecisionVersionResponse

    # Version history summary
    version_count: int
    latest_version_at: datetime


class DecisionSummary(LedgerBaseModel):
    """Abbreviated decision for lists and search results."""

    id: UUID
    decision_number: int
    title: str
    status: DecisionStatus
    impact_level: ImpactLevel
    tags: list[str]
    owner_team: TeamRef | None = None
    created_by: UserRef
    created_at: datetime
    version_count: int


class DecisionWithHistory(DecisionResponse):
    """Decision with full version history."""

    versions: list[DecisionVersionSummary]


# =============================================================================
# RELATIONSHIP SCHEMAS
# =============================================================================


class RelationshipCreate(LedgerBaseModel):
    """Create a relationship between two decisions."""

    target_decision_id: UUID
    relationship_type: RelationshipType
    description: str | None = Field(default=None, max_length=500)


class RelationshipResponse(LedgerBaseModel):
    """A relationship between decisions."""

    id: UUID
    source_decision: DecisionRef
    target_decision: DecisionRef
    relationship_type: RelationshipType
    description: str | None = None
    created_by: UserRef
    created_at: datetime
    invalidated_at: datetime | None = None


class SupersedeRequest(LedgerBaseModel):
    """Request to supersede an old decision with a new one."""

    old_decision_id: UUID
    description: str | None = Field(
        default=None,
        max_length=500,
        description="Why is this decision being superseded?",
    )


# =============================================================================
# APPROVAL SCHEMAS
# =============================================================================


class ApprovalCreate(LedgerBaseModel):
    """Submit an approval for a decision version."""

    status: ApprovalStatus = Field(
        ...,
        description="Approval verdict",
    )
    comment: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional comment explaining the decision",
    )

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: ApprovalStatus) -> ApprovalStatus:
        if v == ApprovalStatus.PENDING:
            raise ValueError("Cannot explicitly set status to 'pending'")
        return v


class ApprovalResponse(LedgerBaseModel):
    """An approval record."""

    id: UUID
    decision_version_id: UUID
    user: UserRef
    status: ApprovalStatus
    comment: str | None = None
    created_at: datetime


class ApprovalSummary(LedgerBaseModel):
    """Summary of approval status for a version."""

    version_id: UUID
    required_approvals: int
    received_approvals: int
    approved_count: int
    rejected_count: int
    pending_count: int
    is_fully_approved: bool
    approvals: list[ApprovalResponse]


# =============================================================================
# DECISION GRAPH SCHEMAS
# =============================================================================


class DecisionLineage(LedgerBaseModel):
    """The supersession chain for a decision."""

    current_decision: DecisionRef
    predecessors: list[DecisionRef]  # Oldest first
    successors: list[DecisionRef]  # Most recent last


class DecisionGraphNode(LedgerBaseModel):
    """A node in the decision graph for visualization."""

    id: UUID
    decision_number: int
    title: str
    status: DecisionStatus
    impact_level: ImpactLevel
    distance: int  # Distance from focal node


class DecisionGraphEdge(LedgerBaseModel):
    """An edge in the decision graph."""

    id: UUID
    source_id: UUID
    target_id: UUID
    relationship_type: RelationshipType


class DecisionGraph(LedgerBaseModel):
    """Complete decision graph for visualization."""

    focal_decision_id: UUID
    nodes: list[DecisionGraphNode]
    edges: list[DecisionGraphEdge]


# =============================================================================
# SEARCH AND FILTER SCHEMAS
# =============================================================================


class DecisionSearchParams(BaseModel):
    """Search and filter parameters for decisions."""

    query: str | None = Field(default=None, description="Full-text search")
    status: list[DecisionStatus] | None = None
    impact_level: list[ImpactLevel] | None = None
    tags: list[str] | None = None
    owner_team_id: UUID | None = None
    created_by_id: UUID | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    include_superseded: bool = Field(
        default=False,
        description="Include superseded decisions in results",
    )
    include_deprecated: bool = Field(
        default=False,
        description="Include deprecated decisions in results",
    )


class DecisionSearchResult(DecisionSummary):
    """Search result with relevance score."""

    relevance_score: float | None = None
    context_preview: str | None = None  # Snippet from matching content
