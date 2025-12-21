"""
Ledger API Routes: Core endpoints for immutable decision management.

These endpoints implement the four critical flows:
1. POST /decisions - Create a new decision
2. PUT /decisions/{id} - Amend (creates new version, never overwrites)
3. POST /decisions/{id}/supersede - Mark as superseded
4. GET /decisions/{id} - Fetch with optional time travel
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..core import OrgContextDep, SessionDep
from ..models import ImpactLevel
from ..models import DecisionStatus
from ..services.ledger_engine import (
    AmendDecisionInput,
    CreateDecisionInput,
    DecisionContentDTO,
    DecisionNotFoundError,
    InvalidOperationError,
    LedgerEngine,
    SupersedeInput,
    VersionNotFoundError,
    ConcurrencyError,
)

router = APIRouter(prefix="/decisions", tags=["ledger"])


# =============================================================================
# REQUEST/RESPONSE SCHEMAS
# =============================================================================


class AlternativeSchema(BaseModel):
    """An alternative that was considered but rejected."""
    name: str = Field(..., min_length=1, max_length=200)
    rejected_reason: str = Field(..., min_length=1)


class DecisionContentSchema(BaseModel):
    """The structured content of a decision."""
    context: str = Field(
        ...,
        min_length=1,
        description="Background and problem statement (Markdown supported)",
    )
    choice: str = Field(
        ...,
        min_length=1,
        description="The decision that was made (Markdown supported)",
    )
    rationale: str = Field(
        ...,
        min_length=1,
        description="Why this choice was made (Markdown supported)",
    )
    alternatives: list[AlternativeSchema] = Field(
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

    def to_dto(self) -> DecisionContentDTO:
        return DecisionContentDTO(
            context=self.context,
            choice=self.choice,
            rationale=self.rationale,
            alternatives=[a.model_dump() for a in self.alternatives],
            consequences=self.consequences,
            review_date=self.review_date,
        )


class CreateDecisionRequest(BaseModel):
    """Request to create a new decision."""
    title: str = Field(..., min_length=1, max_length=500)
    content: DecisionContentSchema
    impact_level: ImpactLevel = ImpactLevel.MEDIUM
    tags: list[str] = Field(default_factory=list, max_length=20)
    owner_team_id: UUID | None = None
    reviewer_ids: list[UUID] = Field(
        default_factory=list,
        description="Users who must approve this decision",
    )


class AmendDecisionRequest(BaseModel):
    """Request to amend a decision (creates a new version)."""
    title: str = Field(..., min_length=1, max_length=500)
    content: DecisionContentSchema
    impact_level: ImpactLevel
    tags: list[str] = Field(default_factory=list, max_length=20)
    change_summary: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="REQUIRED: Describe what changed in this version",
    )
    expected_version: int | None = Field(
        default=None,
        description="For optimistic locking: the version you're editing from",
    )


class SupersedeRequest(BaseModel):
    """Request to supersede this decision with another."""
    new_decision_id: UUID = Field(
        ...,
        description="The ID of the decision that supersedes this one",
    )
    reason: str | None = Field(
        default=None,
        max_length=500,
        description="Why is this decision being superseded?",
    )


class UserRefResponse(BaseModel):
    """User reference in responses."""
    id: UUID
    name: str
    email: str | None = None


class VersionResponse(BaseModel):
    """A decision version response."""
    id: UUID
    version_number: int
    title: str
    impact_level: str
    content: dict
    tags: list[str]
    content_hash: str | None
    created_by: UserRefResponse
    created_at: datetime
    change_summary: str | None
    is_current: bool


class DecisionResponse(BaseModel):
    """Full decision response."""
    id: UUID
    organization_id: UUID
    decision_number: int
    status: str
    created_by: UserRefResponse
    created_at: datetime

    # Current or requested version
    version: VersionResponse
    version_count: int

    # For time travel
    requested_version: int | None = None


class VersionHistoryResponse(BaseModel):
    """Version history item."""
    id: UUID
    version_number: int
    title: str
    impact_level: str
    content_hash: str
    created_by: UserRefResponse
    created_at: datetime
    change_summary: str | None


class SupersedeResponse(BaseModel):
    """Response after superseding a decision."""
    old_decision_id: UUID
    old_decision_number: int
    new_decision_id: UUID
    new_decision_number: int
    relationship_id: UUID
    message: str


class VersionCompareResponse(BaseModel):
    """Response comparing two versions."""
    version_a: dict
    version_b: dict
    changes: dict


class DecisionSummaryResponse(BaseModel):
    """Summary response for decision lists."""
    id: UUID
    organization_id: UUID
    decision_number: int
    status: str
    title: str
    impact_level: str
    tags: list[str]
    created_by: UserRefResponse
    created_at: datetime
    version_count: int


class PaginatedDecisionsResponse(BaseModel):
    """Paginated list of decisions."""
    items: list[DecisionSummaryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# =============================================================================
# DEPENDENCIES
# =============================================================================


def get_ledger_engine(session: SessionDep) -> LedgerEngine:
    return LedgerEngine(session)


LedgerEngineDep = Annotated[LedgerEngine, Depends(get_ledger_engine)]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def build_decision_response(
    result,
    requested_version: int | None = None,
) -> DecisionResponse:
    """Convert LedgerEngine result to API response."""
    decision = result.decision
    version = result.version

    return DecisionResponse(
        id=decision.id,
        organization_id=decision.organization_id,
        decision_number=decision.decision_number,
        status=decision.status.value,
        created_by=UserRefResponse(
            id=decision.creator.id,
            name=decision.creator.name,
            email=decision.creator.email,
        ),
        created_at=decision.created_at,
        version=VersionResponse(
            id=version.id,
            version_number=version.version_number,
            title=version.title,
            impact_level=version.impact_level.value,
            content=version.content,
            tags=version.tags or [],
            content_hash=version.content_hash,
            created_by=UserRefResponse(
                id=version.creator.id,
                name=version.creator.name,
                email=version.creator.email if hasattr(version.creator, 'email') else None,
            ),
            created_at=version.created_at,
            change_summary=version.change_summary,
            is_current=result.is_current,
        ),
        version_count=result.version_count,
        requested_version=requested_version,
    )


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.post(
    "",
    response_model=DecisionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new decision",
    description="""
    Create a new decision with its initial version (v1).

    This creates:
    - A Decision record (the immutable anchor)
    - A DecisionVersion v1 with the provided content
    - An audit log entry

    The decision starts in DRAFT status.
    """,
)
async def create_decision(
    request: CreateDecisionRequest,
    current_user: OrgContextDep,
    engine: LedgerEngineDep,
):
    """Create a new decision."""
    try:
        input_data = CreateDecisionInput(
            title=request.title,
            content=request.content.to_dto(),
            impact_level=request.impact_level,
            tags=request.tags,
            owner_team_id=request.owner_team_id,
            reviewer_ids=request.reviewer_ids,
        )

        result = await engine.create_decision(
            input=input_data,
            organization_id=current_user.organization_id,
            author_id=current_user.id,
        )

        return build_decision_response(result)

    except ConcurrencyError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.get(
    "",
    response_model=PaginatedDecisionsResponse,
    summary="List all decisions",
    description="""
    List all decisions for the current organization with pagination.

    Query parameters:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, max: 100)
    - status: Optional status filter (draft, in_review, approved, deprecated, superseded)
    """,
)
async def list_decisions(
    current_user: OrgContextDep,
    engine: LedgerEngineDep,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    status: str | None = Query(default=None, description="Filter by status"),
):
    """List all decisions with pagination."""
    offset = (page - 1) * page_size

    # Parse status filter if provided
    status_filter = None
    if status:
        try:
            status_filter = DecisionStatus(status)
        except ValueError:
            pass  # Invalid status, ignore filter

    decisions, total = await engine.list_decisions(
        organization_id=current_user.organization_id,
        limit=page_size,
        offset=offset,
        status_filter=status_filter,
    )

    items = [
        DecisionSummaryResponse(
            id=d.decision.id,
            organization_id=d.decision.organization_id,
            decision_number=d.decision.decision_number,
            status=d.decision.status.value,
            title=d.version.title,
            impact_level=d.version.impact_level.value,
            tags=d.version.tags or [],
            created_by=UserRefResponse(
                id=d.decision.creator.id,
                name=d.decision.creator.name,
                email=d.decision.creator.email,
            ),
            created_at=d.decision.created_at,
            version_count=d.version_count,
        )
        for d in decisions
    ]

    total_pages = (total + page_size - 1) // page_size

    return PaginatedDecisionsResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.put(
    "/{decision_id}",
    response_model=DecisionResponse,
    summary="Amend a decision (creates new version)",
    description="""
    Amend a decision by creating a NEW version.

    **CRITICAL: This endpoint NEVER overwrites existing data.**

    What happens:
    1. A new DecisionVersion row is INSERTED (not updated)
    2. The Decision.current_version_id pointer is updated
    3. An audit log entry records the change

    The original version remains immutable and accessible via time travel.

    **Optimistic Locking**: Pass `expected_version` to detect concurrent edits.
    If another user modified the decision, you'll get a 409 Conflict.
    """,
)
async def amend_decision(
    decision_id: UUID,
    request: AmendDecisionRequest,
    current_user: OrgContextDep,
    engine: LedgerEngineDep,
):
    """Amend a decision by creating a new version."""
    try:
        input_data = AmendDecisionInput(
            title=request.title,
            content=request.content.to_dto(),
            impact_level=request.impact_level,
            tags=request.tags,
            change_summary=request.change_summary,
            expected_version=request.expected_version,
        )

        result = await engine.amend_decision(
            decision_id=decision_id,
            input=input_data,
            author_id=current_user.id,
        )

        return build_decision_response(result)

    except DecisionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision {decision_id} not found",
        )
    except InvalidOperationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except ConcurrencyError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.post(
    "/{decision_id}/supersede",
    response_model=SupersedeResponse,
    summary="Supersede this decision with another",
    description="""
    Mark this decision as superseded by a newer decision.

    What happens:
    1. A 'supersedes' relationship is created
    2. This decision's status changes to SUPERSEDED
    3. The superseding decision becomes the "current" version

    Use GET /decisions/{id}/current to follow the supersession chain.
    """,
)
async def supersede_decision(
    decision_id: UUID,
    request: SupersedeRequest,
    current_user: OrgContextDep,
    engine: LedgerEngineDep,
):
    """Mark a decision as superseded by another."""
    try:
        input_data = SupersedeInput(
            new_decision_id=request.new_decision_id,
            reason=request.reason,
        )

        old_decision, new_decision, relationship = await engine.supersede_decision(
            old_decision_id=decision_id,
            input=input_data,
            author_id=current_user.id,
        )

        return SupersedeResponse(
            old_decision_id=old_decision.id,
            old_decision_number=old_decision.decision_number,
            new_decision_id=new_decision.id,
            new_decision_number=new_decision.decision_number,
            relationship_id=relationship.id,
            message=f"Decision #{old_decision.decision_number} is now superseded by #{new_decision.decision_number}",
        )

    except DecisionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except InvalidOperationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/{decision_id}",
    response_model=DecisionResponse,
    summary="Get a decision (with optional time travel)",
    description="""
    Retrieve a decision, optionally at a specific historical version.

    **Default behavior**: Returns the current (latest) version.

    **Time Travel**: Pass `?version=2` to retrieve the decision
    as it existed at version 2.

    The response includes:
    - `is_current`: Whether this is the current version
    - `version_count`: Total number of versions
    - `requested_version`: The version you asked for (if specified)
    """,
)
async def get_decision(
    decision_id: UUID,
    current_user: OrgContextDep,
    engine: LedgerEngineDep,
    version: int | None = Query(
        default=None,
        ge=1,
        description="Specific version number to retrieve (time travel)",
    ),
):
    """Get a decision, optionally at a specific version."""
    try:
        result = await engine.get_decision(
            decision_id=decision_id,
            version=version,
        )

        return build_decision_response(result, requested_version=version)

    except DecisionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision {decision_id} not found",
        )
    except VersionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version} not found for decision {decision_id}",
        )


@router.get(
    "/{decision_id}/versions",
    response_model=list[VersionHistoryResponse],
    summary="Get version history",
    description="Get all versions of a decision, ordered newest first.",
)
async def get_version_history(
    decision_id: UUID,
    current_user: OrgContextDep,
    engine: LedgerEngineDep,
):
    """Get the complete version history of a decision."""
    try:
        # First verify decision exists
        await engine.get_decision(decision_id)

        versions = await engine.get_version_history(decision_id)

        return [
            VersionHistoryResponse(
                id=v.id,
                version_number=v.version_number,
                title=v.title,
                impact_level=v.impact_level.value,
                content_hash=v.content_hash,
                created_by=UserRefResponse(
                    id=v.created_by_id,
                    name=v.created_by_name,
                ),
                created_at=v.created_at,
                change_summary=v.change_summary,
            )
            for v in versions
        ]

    except DecisionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision {decision_id} not found",
        )


@router.get(
    "/{decision_id}/compare",
    response_model=VersionCompareResponse,
    summary="Compare two versions",
    description="Compare two versions of a decision to see what changed.",
)
async def compare_versions(
    decision_id: UUID,
    current_user: OrgContextDep,
    engine: LedgerEngineDep,
    version_a: int = Query(..., ge=1, description="First version to compare"),
    version_b: int = Query(..., ge=1, description="Second version to compare"),
):
    """Compare two versions of a decision."""
    try:
        comparison = await engine.compare_versions(
            decision_id=decision_id,
            version_a=version_a,
            version_b=version_b,
        )

        return VersionCompareResponse(**comparison)

    except DecisionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision {decision_id} not found",
        )
    except VersionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
