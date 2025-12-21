"""API routes for decision management."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..core import OrgContextDep, SessionDep
from ..models import AuditAction
from ..schemas import (
    ApprovalCreate,
    ApprovalResponse,
    ApprovalSummary,
    DecisionCreate,
    DecisionLineage,
    DecisionRef,
    DecisionResponse,
    DecisionSearchParams,
    DecisionSummary,
    DecisionUpdate,
    DecisionVersionResponse,
    DecisionVersionSummary,
    DecisionWithHistory,
    PaginatedResponse,
    RelationshipCreate,
    RelationshipResponse,
    SupersedeRequest,
    TeamRef,
    UserRef,
)
from ..services import AuditService, DecisionService

router = APIRouter(prefix="/decisions", tags=["decisions"])


def get_decision_service(session: SessionDep) -> DecisionService:
    return DecisionService(session)


def get_audit_service(session: SessionDep) -> AuditService:
    return AuditService(session)


DecisionServiceDep = Annotated[DecisionService, Depends(get_decision_service)]
AuditServiceDep = Annotated[AuditService, Depends(get_audit_service)]


# =============================================================================
# HELPERS
# =============================================================================


def decision_to_response(decision) -> DecisionResponse:
    """Convert a Decision model to a response schema."""
    version = decision.current_version
    return DecisionResponse(
        id=decision.id,
        organization_id=decision.organization_id,
        decision_number=decision.decision_number,
        status=decision.status,
        owner_team=TeamRef(
            id=decision.owner_team.id,
            slug=decision.owner_team.slug,
            name=decision.owner_team.name,
        ) if decision.owner_team else None,
        created_by=UserRef(
            id=decision.creator.id,
            name=decision.creator.name,
            email=decision.creator.email,
            avatar_url=decision.creator.avatar_url,
        ),
        created_at=decision.created_at,
        deleted_at=decision.deleted_at,
        current_version=DecisionVersionResponse(
            id=version.id,
            decision_id=version.decision_id,
            version_number=version.version_number,
            title=version.title,
            impact_level=version.impact_level,
            content=version.content,
            tags=version.tags,
            custom_fields=version.custom_fields,
            created_by=UserRef(
                id=version.creator.id,
                name=version.creator.name,
                email=version.creator.email,
                avatar_url=version.creator.avatar_url,
            ),
            created_at=version.created_at,
            change_summary=version.change_summary,
            content_hash=version.content_hash,
        ),
        version_count=len(decision.versions) if hasattr(decision, 'versions') and decision.versions else 1,
        latest_version_at=version.created_at,
    )


def decision_to_summary(decision) -> DecisionSummary:
    """Convert a Decision model to a summary schema."""
    version = decision.current_version
    return DecisionSummary(
        id=decision.id,
        decision_number=decision.decision_number,
        title=version.title,
        status=decision.status,
        impact_level=version.impact_level,
        tags=version.tags,
        owner_team=TeamRef(
            id=decision.owner_team.id,
            slug=decision.owner_team.slug,
            name=decision.owner_team.name,
        ) if decision.owner_team else None,
        created_by=UserRef(
            id=decision.creator.id,
            name=decision.creator.name,
            email=decision.creator.email,
            avatar_url=decision.creator.avatar_url,
        ),
        created_at=decision.created_at,
        version_count=len(decision.versions) if hasattr(decision, 'versions') and decision.versions else 1,
    )


# =============================================================================
# DECISION CRUD
# =============================================================================


@router.post("", response_model=DecisionResponse, status_code=status.HTTP_201_CREATED)
async def create_decision(
    data: DecisionCreate,
    current_user: OrgContextDep,
    service: DecisionServiceDep,
    audit: AuditServiceDep,
):
    """Create a new decision."""
    decision = await service.create_decision(
        data=data,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
    )

    # Log the creation
    await audit.log_event(
        organization_id=current_user.organization_id,
        action=AuditAction.CREATE,
        resource_type="decision",
        resource_id=decision.id,
        user_id=current_user.id,
        details={"title": data.title, "impact_level": data.impact_level.value},
    )

    # Reload with relationships
    decision = await service.get_decision(decision.id)
    return decision_to_response(decision)


@router.get("", response_model=PaginatedResponse)
async def list_decisions(
    current_user: OrgContextDep,
    service: DecisionServiceDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query(None, description="Search query to filter decisions by title, tags, or content"),
):
    """List all current (non-superseded) decisions. Optionally filter by search query."""
    offset = (page - 1) * page_size

    if search and search.strip():
        # Use search functionality
        search_params = DecisionSearchParams(query=search.strip())
        decisions, total = await service.search_decisions(
            organization_id=current_user.organization_id,
            params=search_params,
            limit=page_size,
            offset=offset,
        )
    else:
        # List all current decisions
        decisions, total = await service.list_current_decisions(
            organization_id=current_user.organization_id,
            limit=page_size,
            offset=offset,
        )

    return PaginatedResponse.create(
        items=[decision_to_summary(d) for d in decisions],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/search", response_model=PaginatedResponse)
async def search_decisions(
    params: DecisionSearchParams,
    current_user: OrgContextDep,
    service: DecisionServiceDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Search decisions with filters."""
    offset = (page - 1) * page_size
    decisions, total = await service.search_decisions(
        organization_id=current_user.organization_id,
        params=params,
        limit=page_size,
        offset=offset,
    )

    return PaginatedResponse.create(
        items=[decision_to_summary(d) for d in decisions],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{decision_id}", response_model=DecisionWithHistory)
async def get_decision(
    decision_id: UUID,
    current_user: OrgContextDep,
    service: DecisionServiceDep,
    audit: AuditServiceDep,
):
    """Get a decision by ID with full version history."""
    # SECURITY: Pass org_id to enforce tenant isolation
    decision = await service.get_decision(
        decision_id,
        organization_id=current_user.organization_id,
        include_versions=True,
    )
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    # Log the read
    await audit.log_decision_read(
        decision_id=decision_id,
        version_id=decision.current_version_id,
    )

    response = decision_to_response(decision)
    response.versions = [
        DecisionVersionSummary(
            id=v.id,
            version_number=v.version_number,
            title=v.title,
            impact_level=v.impact_level,
            created_by=UserRef(
                id=v.creator.id,
                name=v.creator.name,
                email=v.creator.email,
            ),
            created_at=v.created_at,
            change_summary=v.change_summary,
        )
        for v in decision.versions
    ]

    return response


@router.get("/number/{decision_number}", response_model=DecisionResponse)
async def get_decision_by_number(
    decision_number: int,
    current_user: OrgContextDep,
    service: DecisionServiceDep,
    audit: AuditServiceDep,
):
    """Get a decision by its organization-scoped number (e.g., DEC-42)."""
    decision = await service.get_decision_by_number(
        organization_id=current_user.organization_id,
        decision_number=decision_number,
    )
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    await audit.log_decision_read(decision_id=decision.id)
    return decision_to_response(decision)


@router.put("/{decision_id}", response_model=DecisionVersionResponse)
async def update_decision(
    decision_id: UUID,
    data: DecisionUpdate,
    current_user: OrgContextDep,
    service: DecisionServiceDep,
    audit: AuditServiceDep,
):
    """Update a decision by creating a new version."""
    try:
        # SECURITY: Pass org_id to enforce tenant isolation
        version = await service.update_decision(
            decision_id=decision_id,
            organization_id=current_user.organization_id,
            data=data,
            user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    await audit.log_event(
        organization_id=current_user.organization_id,
        action=AuditAction.UPDATE,
        resource_type="decision",
        resource_id=decision_id,
        user_id=current_user.id,
        details={
            "version_number": version.version_number,
            "change_summary": data.change_summary,
        },
    )

    return DecisionVersionResponse(
        id=version.id,
        decision_id=version.decision_id,
        version_number=version.version_number,
        title=version.title,
        impact_level=version.impact_level,
        content=version.content,
        tags=version.tags,
        custom_fields=version.custom_fields,
        created_by=UserRef(
            id=version.creator.id,
            name=version.creator.name,
            email=version.creator.email,
        ),
        created_at=version.created_at,
        change_summary=version.change_summary,
        content_hash=version.content_hash,
    )


# =============================================================================
# STATUS TRANSITIONS
# =============================================================================


@router.post("/{decision_id}/submit", response_model=DecisionResponse)
async def submit_for_review(
    decision_id: UUID,
    current_user: OrgContextDep,
    service: DecisionServiceDep,
):
    """Submit a draft decision for review."""
    try:
        # SECURITY: Pass org_id to enforce tenant isolation
        decision = await service.submit_for_review(decision_id, organization_id=current_user.organization_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return decision_to_response(decision)


@router.post("/{decision_id}/deprecate", response_model=DecisionResponse)
async def deprecate_decision(
    decision_id: UUID,
    current_user: OrgContextDep,
    service: DecisionServiceDep,
    audit: AuditServiceDep,
):
    """Deprecate a decision."""
    try:
        # SECURITY: Pass org_id to enforce tenant isolation
        decision = await service.deprecate_decision(decision_id, organization_id=current_user.organization_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await audit.log_event(
        organization_id=current_user.organization_id,
        action=AuditAction.DEPRECATE,
        resource_type="decision",
        resource_id=decision_id,
        user_id=current_user.id,
    )

    return decision_to_response(decision)


# =============================================================================
# RELATIONSHIPS
# =============================================================================


@router.post("/{decision_id}/relationships", response_model=RelationshipResponse)
async def create_relationship(
    decision_id: UUID,
    data: RelationshipCreate,
    current_user: OrgContextDep,
    service: DecisionServiceDep,
):
    """Create a relationship from this decision to another."""
    relationship = await service.create_relationship(
        source_decision_id=decision_id,
        data=data,
        user_id=current_user.id,
    )

    # Fetch source and target for response
    source = await service.get_decision(decision_id)
    target = await service.get_decision(data.target_decision_id)

    return RelationshipResponse(
        id=relationship.id,
        source_decision=DecisionRef(
            id=source.id,
            decision_number=source.decision_number,
            title=source.current_version.title,
            status=source.status,
        ),
        target_decision=DecisionRef(
            id=target.id,
            decision_number=target.decision_number,
            title=target.current_version.title,
            status=target.status,
        ),
        relationship_type=relationship.relationship_type,
        description=relationship.description,
        created_by=UserRef(
            id=current_user.user.id,
            name=current_user.user.name,
            email=current_user.user.email,
        ),
        created_at=relationship.created_at,
    )


@router.post("/{decision_id}/supersede", response_model=RelationshipResponse)
async def supersede_decision(
    decision_id: UUID,
    data: SupersedeRequest,
    current_user: OrgContextDep,
    service: DecisionServiceDep,
    audit: AuditServiceDep,
):
    """Mark this decision as superseding another decision."""
    relationship = await service.supersede_decision(
        new_decision_id=decision_id,
        old_decision_id=data.old_decision_id,
        user_id=current_user.id,
        description=data.description,
    )

    await audit.log_event(
        organization_id=current_user.organization_id,
        action=AuditAction.SUPERSEDE,
        resource_type="decision",
        resource_id=data.old_decision_id,
        user_id=current_user.id,
        details={"superseded_by": str(decision_id)},
    )

    source = await service.get_decision(decision_id)
    target = await service.get_decision(data.old_decision_id)

    return RelationshipResponse(
        id=relationship.id,
        source_decision=DecisionRef(
            id=source.id,
            decision_number=source.decision_number,
            title=source.current_version.title,
            status=source.status,
        ),
        target_decision=DecisionRef(
            id=target.id,
            decision_number=target.decision_number,
            title=target.current_version.title,
            status=target.status,
        ),
        relationship_type=relationship.relationship_type,
        description=relationship.description,
        created_by=UserRef(
            id=current_user.user.id,
            name=current_user.user.name,
            email=current_user.user.email,
        ),
        created_at=relationship.created_at,
    )


@router.get("/{decision_id}/lineage", response_model=DecisionLineage)
async def get_decision_lineage(
    decision_id: UUID,
    current_user: OrgContextDep,
    service: DecisionServiceDep,
):
    """Get the supersession chain for a decision."""
    # SECURITY: Pass org_id to enforce tenant isolation
    decision = await service.get_decision(decision_id, organization_id=current_user.organization_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    predecessors = await service.get_decision_lineage(decision_id)

    return DecisionLineage(
        current_decision=DecisionRef(
            id=decision.id,
            decision_number=decision.decision_number,
            title=decision.current_version.title,
            status=decision.status,
        ),
        predecessors=[
            DecisionRef(
                id=d.id,
                decision_number=d.decision_number,
                title=d.current_version.title,
                status=d.status,
            )
            for d in predecessors
        ],
        successors=[],  # Would need another query for this
    )


@router.get("/{decision_id}/current")
async def get_current_version(
    decision_id: UUID,
    current_user: OrgContextDep,
    service: DecisionServiceDep,
):
    """Get the current (non-superseded) decision in a chain."""
    # SECURITY: First verify the original decision belongs to this org
    original = await service.get_decision(decision_id, organization_id=current_user.organization_id)
    if not original:
        raise HTTPException(status_code=404, detail="Decision not found")

    current_id = await service.get_current_decision(decision_id)
    decision = await service.get_decision(current_id, organization_id=current_user.organization_id)

    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    return decision_to_response(decision)


# =============================================================================
# APPROVALS
# =============================================================================


@router.post("/{decision_id}/versions/{version_id}/approve", response_model=ApprovalResponse)
async def approve_version(
    decision_id: UUID,
    version_id: UUID,
    data: ApprovalCreate,
    current_user: OrgContextDep,
    service: DecisionServiceDep,
    audit: AuditServiceDep,
):
    """Submit an approval for a decision version."""
    approval = await service.add_approval(
        version_id=version_id,
        user_id=current_user.id,
        data=data,
    )

    action = AuditAction.APPROVE if data.status.value == "approved" else AuditAction.REJECT
    await audit.log_event(
        organization_id=current_user.organization_id,
        action=action,
        resource_type="decision_version",
        resource_id=version_id,
        user_id=current_user.id,
        details={"status": data.status.value, "comment": data.comment},
    )

    return ApprovalResponse(
        id=approval.id,
        decision_version_id=approval.decision_version_id,
        user=UserRef(
            id=current_user.user.id,
            name=current_user.user.name,
            email=current_user.user.email,
        ),
        status=approval.status,
        comment=approval.comment,
        created_at=approval.created_at,
    )


@router.get("/pending-approvals", response_model=list[DecisionVersionSummary])
async def get_my_pending_approvals(
    current_user: OrgContextDep,
    service: DecisionServiceDep,
):
    """Get decisions awaiting my approval."""
    versions = await service.get_pending_approvals(
        user_id=current_user.id,
        organization_id=current_user.organization_id,
    )

    return [
        DecisionVersionSummary(
            id=v.id,
            version_number=v.version_number,
            title=v.title,
            impact_level=v.impact_level,
            created_by=UserRef(
                id=v.creator.id,
                name=v.creator.name,
                email=v.creator.email,
            ),
            created_at=v.created_at,
            change_summary=v.change_summary,
        )
        for v in versions
    ]
