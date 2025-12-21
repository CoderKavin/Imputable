"""
Risk Dashboard API: Endpoints for management visibility into tech debt.

These endpoints power the executive view for:
1. Overview statistics (expired, at-risk counts)
2. Expiring decisions list with filters
3. Calendar view (Debt Wall)
4. Heatmap data for visualization
5. One-click actions (snooze, request update)
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..core import OrgContextDep, SessionDep
from ..core.billing import RiskDashboardDep
from ..services.expiry_engine import (
    ExpiryConfig,
    ExpiryEngine,
    ExpiryStats,
)


router = APIRouter(prefix="/risk-dashboard", tags=["risk-dashboard"])


# =============================================================================
# REQUEST/RESPONSE SCHEMAS
# =============================================================================


class RiskStatsResponse(BaseModel):
    """Overview statistics for the risk dashboard."""
    total_expired: int = Field(..., description="Number of expired decisions")
    total_at_risk: int = Field(..., description="Number of at-risk decisions")
    expiring_this_week: int = Field(..., description="Decisions expiring within 7 days")
    expiring_this_month: int = Field(..., description="Decisions expiring within 30 days")
    by_team: dict[str, int] = Field(..., description="Count by team name")
    by_impact: dict[str, int] = Field(..., description="Count by impact level")


class ExpiringDecisionResponse(BaseModel):
    """A decision that is expiring or at risk."""
    decision_id: str
    decision_number: int
    title: str
    owner_team_name: str | None
    creator_name: str
    review_by_date: datetime
    days_until_expiry: int
    status: str
    is_temporary: bool
    last_reminder_sent: datetime | None


class ExpiringDecisionsListResponse(BaseModel):
    """List of expiring decisions with pagination info."""
    decisions: list[ExpiringDecisionResponse]
    total_count: int
    has_more: bool


class CalendarDayResponse(BaseModel):
    """Decisions grouped by a single day."""
    date: str  # YYYY-MM-DD
    decisions: list[dict]


class CalendarResponse(BaseModel):
    """Calendar data for the Debt Wall view."""
    start_date: str
    end_date: str
    days: list[CalendarDayResponse]


class HeatmapDataPoint(BaseModel):
    """A single data point for the heatmap."""
    week: str  # YYYY-MM-DD (start of week)
    count: int


class HeatmapResponse(BaseModel):
    """Heatmap data for visualization."""
    data: list[HeatmapDataPoint]
    max_count: int
    total_decisions: int


class SnoozeRequest(BaseModel):
    """Request to snooze a decision."""
    days: int = Field(
        ...,
        ge=1,
        le=90,
        description="Number of days to extend the review date (max 90)",
    )
    reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="REQUIRED: Explanation for why this delay is necessary",
    )


class SnoozeResponse(BaseModel):
    """Response after snoozing a decision."""
    decision_id: str
    old_review_date: datetime
    new_review_date: datetime
    days_extended: int
    message: str


class RequestUpdateRequest(BaseModel):
    """Request for someone to update a decision."""
    message: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional message to the decision owner",
    )
    urgency: str = Field(
        default="normal",
        description="Urgency level: low, normal, high, critical",
    )


class RequestUpdateResponse(BaseModel):
    """Response after requesting an update."""
    request_id: str
    decision_id: str
    message: str


class ResolveRequest(BaseModel):
    """Request to resolve tech debt."""
    resolution_note: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="What was done to resolve the tech debt",
    )
    new_review_date: datetime | None = Field(
        default=None,
        description="Optional new review date for continued monitoring",
    )


class ResolveResponse(BaseModel):
    """Response after resolving tech debt."""
    decision_id: str
    decision_number: int
    new_status: str
    message: str


class UpdateRequestResponse(BaseModel):
    """An update request from stakeholders."""
    id: str
    decision_id: str
    decision_number: int | None
    decision_title: str | None
    requested_by_name: str
    message: str | None
    urgency: str
    created_at: datetime


# =============================================================================
# DEPENDENCIES
# =============================================================================


def get_expiry_engine(session: SessionDep) -> ExpiryEngine:
    return ExpiryEngine(session)


ExpiryEngineDep = Annotated[ExpiryEngine, Depends(get_expiry_engine)]


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.get(
    "/stats",
    response_model=RiskStatsResponse,
    summary="Get risk dashboard statistics",
    description="""
    Get overview statistics for the risk dashboard.

    Returns counts of expired and at-risk decisions,
    broken down by team and impact level.

    **Requires Professional subscription or higher.**
    """,
)
async def get_risk_stats(
    current_user: OrgContextDep,
    engine: ExpiryEngineDep,
    subscription: RiskDashboardDep,  # PAYWALL: Requires Pro tier
):
    """Get aggregated risk statistics."""
    stats = await engine.get_expiry_stats(current_user.organization_id)

    return RiskStatsResponse(
        total_expired=stats.total_expired,
        total_at_risk=stats.total_at_risk,
        expiring_this_week=stats.expiring_this_week,
        expiring_this_month=stats.expiring_this_month,
        by_team=stats.by_team,
        by_impact=stats.by_impact,
    )


@router.get(
    "/expiring",
    response_model=ExpiringDecisionsListResponse,
    summary="Get list of expiring decisions",
    description="""
    Get a list of decisions that are expired or at risk.

    Results are ordered by review date (most urgent first).
    Use filters to narrow down by team, status, or impact level.
    """,
)
async def get_expiring_decisions(
    current_user: OrgContextDep,
    engine: ExpiryEngineDep,
    subscription: RiskDashboardDep,  # PAYWALL: Requires Pro tier
    status_filter: str | None = Query(
        default=None,
        description="Filter by status: expired, at_risk, or all",
    ),
    team_id: UUID | None = Query(
        default=None,
        description="Filter by team ID",
    ),
    impact_level: str | None = Query(
        default=None,
        description="Filter by impact level: low, medium, high, critical",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """Get list of expiring decisions."""
    expiring = await engine.scan_expiring_decisions(current_user.organization_id)

    # Apply filters
    filtered = expiring

    if status_filter:
        if status_filter == "expired":
            filtered = [d for d in filtered if d.status.value == "expired"]
        elif status_filter == "at_risk":
            filtered = [d for d in filtered if d.status.value == "at_risk"]

    if team_id:
        filtered = [d for d in filtered if d.owner_team_id == team_id]

    # Pagination
    total_count = len(filtered)
    paginated = filtered[offset:offset + limit]

    return ExpiringDecisionsListResponse(
        decisions=[
            ExpiringDecisionResponse(
                decision_id=str(d.decision_id),
                decision_number=d.decision_number,
                title=d.title,
                owner_team_name=d.owner_team_name,
                creator_name=d.creator_name,
                review_by_date=d.review_by_date,
                days_until_expiry=d.days_until_expiry,
                status=d.status.value,
                is_temporary=d.is_temporary,
                last_reminder_sent=d.last_reminder_sent,
            )
            for d in paginated
        ],
        total_count=total_count,
        has_more=offset + limit < total_count,
    )


@router.get(
    "/calendar",
    response_model=CalendarResponse,
    summary="Get calendar data for Debt Wall",
    description="""
    Get decisions grouped by review date for the calendar view.

    This powers the "Debt Wall" visualization showing when
    decisions are due for review.
    """,
)
async def get_calendar_data(
    current_user: OrgContextDep,
    engine: ExpiryEngineDep,
    subscription: RiskDashboardDep,  # PAYWALL: Requires Pro tier
    start_date: datetime | None = Query(
        default=None,
        description="Start of date range (default: today)",
    ),
    end_date: datetime | None = Query(
        default=None,
        description="End of date range (default: 3 months from now)",
    ),
):
    """Get calendar data for the Debt Wall."""
    now = datetime.now(timezone.utc)

    if start_date is None:
        start_date = now - timedelta(days=7)  # Include last week

    if end_date is None:
        end_date = now + timedelta(days=90)  # 3 months ahead

    calendar_data = await engine.get_calendar_data(
        organization_id=current_user.organization_id,
        start_date=start_date,
        end_date=end_date,
    )

    return CalendarResponse(
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        days=[
            CalendarDayResponse(
                date=day["date"],
                decisions=day["decisions"],
            )
            for day in calendar_data
        ],
    )


@router.get(
    "/heatmap",
    response_model=HeatmapResponse,
    summary="Get heatmap data",
    description="""
    Get weekly aggregated data for the heatmap visualization.

    Shows the density of expiring decisions across weeks,
    helping identify periods of high tech debt risk.
    """,
)
async def get_heatmap_data(
    current_user: OrgContextDep,
    engine: ExpiryEngineDep,
    subscription: RiskDashboardDep,  # PAYWALL: Requires Pro tier
    months: int = Query(
        default=12,
        ge=1,
        le=24,
        description="Number of months of data to include",
    ),
):
    """Get heatmap data for visualization."""
    heatmap_data = await engine.get_heatmap_data(
        organization_id=current_user.organization_id,
        months=months,
    )

    total = sum(d["count"] for d in heatmap_data)
    max_count = max((d["count"] for d in heatmap_data), default=0)

    return HeatmapResponse(
        data=[
            HeatmapDataPoint(week=d["week"], count=d["count"])
            for d in heatmap_data
        ],
        max_count=max_count,
        total_decisions=total,
    )


class TeamHeatmapItem(BaseModel):
    """Team health data for heatmap."""
    team_name: str
    team_id: str | None
    expired_count: int
    at_risk_count: int
    healthy_count: int
    total_count: int
    health_score: float = Field(..., description="0-100, higher is better")
    color: str = Field(..., description="red, yellow, or green")


class TeamHeatmapResponse(BaseModel):
    """Team-based heatmap response."""
    teams: list[TeamHeatmapItem]


class TagHeatmapItem(BaseModel):
    """Tag health data for heatmap."""
    tag: str
    expired_count: int
    at_risk_count: int
    total_count: int
    health_score: float
    color: str


class TagHeatmapResponse(BaseModel):
    """Tag-based heatmap response."""
    tags: list[TagHeatmapItem]


@router.get(
    "/heatmap/teams",
    response_model=TeamHeatmapResponse,
    summary="Get team-based heatmap",
    description="""
    Get tech debt heatmap grouped by team.

    Shows which teams have the most expired/at-risk decisions.
    Color coding:
    - Red: Teams with expired decisions
    - Yellow: Teams with at-risk decisions only
    - Green: Teams with zero tech debt

    This is the "Accountability" view for executives.
    """,
)
async def get_team_heatmap(
    current_user: OrgContextDep,
    engine: ExpiryEngineDep,
    subscription: RiskDashboardDep,  # PAYWALL: Requires Pro tier
):
    """Get team-based heatmap data."""
    teams_data = await engine.get_team_heatmap_data(
        organization_id=current_user.organization_id,
    )

    return TeamHeatmapResponse(
        teams=[TeamHeatmapItem(**team) for team in teams_data],
    )


@router.get(
    "/heatmap/tags",
    response_model=TagHeatmapResponse,
    summary="Get tag-based heatmap",
    description="""
    Get tech debt heatmap grouped by tag/category.

    Shows which domains (e.g., "security", "performance") have
    the most expired/at-risk decisions.
    """,
)
async def get_tag_heatmap(
    current_user: OrgContextDep,
    engine: ExpiryEngineDep,
    subscription: RiskDashboardDep,  # PAYWALL: Requires Pro tier
):
    """Get tag-based heatmap data."""
    tags_data = await engine.get_tag_heatmap_data(
        organization_id=current_user.organization_id,
    )

    return TagHeatmapResponse(
        tags=[TagHeatmapItem(**tag) for tag in tags_data],
    )


@router.post(
    "/decisions/{decision_id}/snooze",
    response_model=SnoozeResponse,
    summary="Snooze a decision",
    description="""
    Extend the review date for a decision.

    IMPORTANT: A reason is required explaining why the delay is necessary.
    This creates a new version in the decision's history for accountability.

    Maximum snooze is 90 days.
    """,
)
async def snooze_decision(
    decision_id: UUID,
    request: SnoozeRequest,
    current_user: OrgContextDep,
    engine: ExpiryEngineDep,
):
    """Snooze a decision by extending its review date."""
    try:
        result = await engine.snooze_decision(
            decision_id=decision_id,
            days=request.days,
            user_id=current_user.id,
            reason=request.reason,
        )

        return SnoozeResponse(
            decision_id=str(result.decision_id),
            old_review_date=result.old_review_date,
            new_review_date=result.new_review_date,
            days_extended=result.days_extended,
            message=f"Review date extended by {result.days_extended} days",
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/decisions/{decision_id}/request-update",
    response_model=RequestUpdateResponse,
    summary="Request an update from the owner",
    description="""
    Send a request to the decision owner asking them to update it.

    This is the "one-click" action for executives who notice
    a decision needs attention but don't want to edit it themselves.
    """,
)
async def request_update(
    decision_id: UUID,
    request: RequestUpdateRequest,
    current_user: OrgContextDep,
    engine: ExpiryEngineDep,
):
    """Request an update for a decision."""
    try:
        update_request = await engine.request_update(
            decision_id=decision_id,
            requester_id=current_user.id,
            message=request.message,
            urgency=request.urgency,
        )

        return RequestUpdateResponse(
            request_id=str(update_request.id),
            decision_id=str(decision_id),
            message="Update request sent to the decision owner",
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/decisions/{decision_id}/resolve",
    response_model=ResolveResponse,
    summary="Resolve tech debt",
    description="""
    Mark a tech debt decision as resolved.

    This clears the AT_RISK or EXPIRED status and optionally
    sets a new review date for continued monitoring.
    """,
)
async def resolve_tech_debt(
    decision_id: UUID,
    request: ResolveRequest,
    current_user: OrgContextDep,
    engine: ExpiryEngineDep,
):
    """Resolve tech debt for a decision."""
    try:
        decision = await engine.resolve_tech_debt(
            decision_id=decision_id,
            user_id=current_user.id,
            resolution_note=request.resolution_note,
            new_review_date=request.new_review_date,
        )

        return ResolveResponse(
            decision_id=str(decision.id),
            decision_number=decision.decision_number,
            new_status=decision.status.value,
            message="Tech debt resolved successfully",
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/update-requests",
    response_model=list[UpdateRequestResponse],
    summary="Get pending update requests",
    description="""
    Get all pending (unresolved) update requests.

    For decision owners to see what stakeholders have requested.
    """,
)
async def get_update_requests(
    current_user: OrgContextDep,
    engine: ExpiryEngineDep,
    my_decisions_only: bool = Query(
        default=False,
        description="Only show requests for decisions I own",
    ),
):
    """Get pending update requests."""
    owner_id = current_user.id if my_decisions_only else None

    requests = await engine.get_pending_update_requests(
        organization_id=current_user.organization_id,
        owner_user_id=owner_id,
    )

    return [
        UpdateRequestResponse(
            id=str(req.id),
            decision_id=str(req.decision_id),
            decision_number=req.decision.decision_number if req.decision else None,
            decision_title=req.decision.current_version.title if req.decision and req.decision.current_version else None,
            requested_by_name=req.requester.name if req.requester else "Unknown",
            message=req.message,
            urgency=req.urgency,
            created_at=req.created_at,
        )
        for req in requests
    ]


@router.post(
    "/process-expiry",
    summary="Trigger expiry processing (admin only)",
    description="""
    Manually trigger the expiry processing job.

    This is normally run by a daily cron job but can be
    triggered manually for testing or immediate processing.
    """,
)
async def trigger_expiry_processing(
    current_user: OrgContextDep,
    engine: ExpiryEngineDep,
):
    """Manually trigger expiry processing."""
    # In production, add admin-only check here

    expired_count, at_risk_count = await engine.process_expiry_transitions(
        organization_id=current_user.organization_id,
    )

    return {
        "message": "Expiry processing completed",
        "expired_count": expired_count,
        "at_risk_count": at_risk_count,
    }
