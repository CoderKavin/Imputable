"""
Audit Export API - Enterprise Compliance Report Generation

Provides endpoints for generating SOC2/ISO/HIPAA compliant audit reports.
"""

from datetime import datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_session
from ..core.dependencies import CurrentUser, require_org_context
from ..models import Organization
from ..services.audit_export import AuditExportService

router = APIRouter(prefix="/audit-export", tags=["Audit Export"])


# =============================================================================
# REQUEST/RESPONSE SCHEMAS
# =============================================================================


class AuditExportRequest(BaseModel):
    """Request schema for generating an audit export."""

    start_date: datetime = Field(
        ...,
        description="Start date for the audit period (inclusive)",
    )
    end_date: datetime = Field(
        ...,
        description="End date for the audit period (inclusive)",
    )
    team_ids: list[UUID] | None = Field(
        default=None,
        description="Filter by specific team IDs (optional)",
    )
    tags: list[str] | None = Field(
        default=None,
        description="Filter by specific tags (optional)",
    )
    status_filter: list[str] | None = Field(
        default=None,
        description="Filter by decision status (optional)",
    )


class AuditExportPreviewResponse(BaseModel):
    """Preview response showing what will be included in the export."""

    decision_count: int
    date_range: str
    filters_applied: dict
    estimated_pages: int
    decisions_preview: list[dict]


class AuditExportMetadata(BaseModel):
    """Metadata about a generated export."""

    report_id: str
    generated_at: datetime
    generated_by: str
    decision_count: int
    verification_hash: str
    date_range: str


class QuarterPreset(BaseModel):
    """Preset for quarterly date ranges."""

    label: str
    start_date: datetime
    end_date: datetime


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.get("/presets", response_model=list[QuarterPreset])
async def get_date_presets() -> list[QuarterPreset]:
    """
    Get preset date ranges for common audit periods.

    Returns quarterly presets for the current and previous year.
    """
    now = datetime.utcnow()
    current_year = now.year
    presets = []

    # Current and previous year quarters
    for year in [current_year, current_year - 1]:
        quarters = [
            ("Q1", datetime(year, 1, 1), datetime(year, 3, 31, 23, 59, 59)),
            ("Q2", datetime(year, 4, 1), datetime(year, 6, 30, 23, 59, 59)),
            ("Q3", datetime(year, 7, 1), datetime(year, 9, 30, 23, 59, 59)),
            ("Q4", datetime(year, 10, 1), datetime(year, 12, 31, 23, 59, 59)),
        ]

        for quarter_name, start, end in quarters:
            # Only include past or current quarters
            if start <= now:
                presets.append(
                    QuarterPreset(
                        label=f"{quarter_name} {year}",
                        start_date=start,
                        end_date=min(end, now),
                    )
                )

    # Add "Last 30 days" and "Last 90 days" presets
    presets.insert(0, QuarterPreset(
        label="Last 30 Days",
        start_date=now - timedelta(days=30),
        end_date=now,
    ))
    presets.insert(1, QuarterPreset(
        label="Last 90 Days",
        start_date=now - timedelta(days=90),
        end_date=now,
    ))

    # Add "Year to Date"
    presets.insert(2, QuarterPreset(
        label=f"Year to Date ({current_year})",
        start_date=datetime(current_year, 1, 1),
        end_date=now,
    ))

    return presets


@router.post("/preview", response_model=AuditExportPreviewResponse)
async def preview_audit_export(
    request: AuditExportRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[CurrentUser, Depends(require_org_context)],
) -> AuditExportPreviewResponse:
    """
    Preview what will be included in the audit export.

    Use this endpoint to show users what decisions will be included
    before generating the full PDF report.
    """
    export_service = AuditExportService(session)

    decisions = await export_service.get_decisions_for_export(
        organization_id=current_user.organization_id,
        start_date=request.start_date,
        end_date=request.end_date,
        team_ids=request.team_ids,
        tags=request.tags,
        status_filter=request.status_filter,
    )

    # Build preview
    decisions_preview = []
    for decision in decisions[:20]:  # Limit preview to 20 decisions
        current_version = decision.current_version or (
            decision.versions[-1] if decision.versions else None
        )
        decisions_preview.append({
            "decision_number": decision.decision_number,
            "title": current_version.title if current_version else "Untitled",
            "status": decision.status.value,
            "created_at": decision.created_at.isoformat(),
            "version_count": len(decision.versions),
        })

    # Estimate pages (rough: 1 decision per 1-2 pages)
    estimated_pages = max(5, len(decisions) * 1.5)

    date_range = (
        f"{request.start_date.strftime('%b %d, %Y')} — "
        f"{request.end_date.strftime('%b %d, %Y')}"
    )

    return AuditExportPreviewResponse(
        decision_count=len(decisions),
        date_range=date_range,
        filters_applied={
            "teams": len(request.team_ids) if request.team_ids else 0,
            "tags": request.tags or [],
            "status": request.status_filter or [],
        },
        estimated_pages=int(estimated_pages),
        decisions_preview=decisions_preview,
    )


@router.post("/generate")
async def generate_audit_export(
    request: AuditExportRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[CurrentUser, Depends(require_org_context)],
) -> StreamingResponse:
    """
    Generate the official audit export PDF.

    This endpoint generates a professional PDF report suitable for
    SOC2, ISO 27001, and HIPAA compliance audits.

    The response includes:
    - Cover page with organization details
    - Table of contents
    - Executive summary with statistics
    - Detailed decision documentation with audit trails
    - Cryptographic verification hash for tamper detection
    """
    export_service = AuditExportService(session)

    try:
        pdf_bytes, verification_hash = await export_service.generate_report(
            organization_id=current_user.organization_id,
            start_date=request.start_date,
            end_date=request.end_date,
            generated_by_id=current_user.user.id,
            team_ids=request.team_ids,
            tags=request.tags,
            status_filter=request.status_filter,
        )

        await session.commit()

    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate audit report: {str(e)}",
        )

    # Generate filename
    date_str = datetime.utcnow().strftime("%Y%m%d")
    start_str = request.start_date.strftime("%Y%m%d")
    end_str = request.end_date.strftime("%Y%m%d")
    org_slug = str(current_user.organization_id)[:8]  # Use partial UUID as slug
    filename = f"audit_report_{org_slug}_{start_str}_{end_str}_{date_str}.pdf"

    # Stream the PDF response
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Verification-Hash": verification_hash,
            "X-Report-Generated": datetime.utcnow().isoformat(),
        },
    )


@router.get("/history", response_model=list[AuditExportMetadata])
async def get_export_history(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[CurrentUser, Depends(require_org_context)],
    limit: int = Query(default=20, le=100),
) -> list[AuditExportMetadata]:
    """
    Get history of previously generated audit exports.

    Useful for tracking when reports were generated and by whom.
    """
    from sqlalchemy import select
    from ..models import AuditAction, AuditLog

    query = (
        select(AuditLog)
        .where(
            AuditLog.organization_id == current_user.organization_id,
            AuditLog.action == AuditAction.EXPORT,
            AuditLog.resource_type == "audit_report",
        )
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )

    result = await session.execute(query)
    exports = result.scalars().all()

    history = []
    for export in exports:
        details = export.details or {}
        history.append(
            AuditExportMetadata(
                report_id=str(export.id),
                generated_at=export.created_at,
                generated_by=current_user.user.name,
                decision_count=details.get("decision_count", 0),
                verification_hash=details.get("content_hash", ""),
                date_range=f"{details.get('start_date', 'N/A')} — {details.get('end_date', 'N/A')}",
            )
        )

    return history


@router.get("/verify/{verification_hash}")
async def verify_report_hash(
    verification_hash: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[CurrentUser, Depends(require_org_context)],
) -> dict:
    """
    Verify if a report hash matches a previously generated report.

    This endpoint allows auditors to verify that a report
    has not been tampered with since generation.
    """
    from sqlalchemy import select
    from ..models import AuditAction, AuditLog

    query = select(AuditLog).where(
        AuditLog.organization_id == current_user.organization_id,
        AuditLog.action == AuditAction.EXPORT,
        AuditLog.resource_type == "audit_report",
        AuditLog.details["content_hash"].astext == verification_hash,
    )

    result = await session.execute(query)
    export_log = result.scalar_one_or_none()

    if export_log:
        return {
            "verified": True,
            "message": "Report hash matches a previously generated report.",
            "generated_at": export_log.created_at.isoformat(),
            "report_id": str(export_log.id),
        }
    else:
        return {
            "verified": False,
            "message": "Report hash does not match any known reports. The report may have been modified.",
        }
