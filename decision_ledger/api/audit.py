"""API routes for audit and compliance."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from ..core import AdminDep, SessionDep
from ..schemas import (
    AuditLogEntryWithContext,
    AuditLogQuery,
    AuditLogResponse,
    AuditSummaryResponse,
    ChainVerificationResult,
    DecisionAccessReport,
    PaginatedResponse,
    UserRef,
)
from ..services import AuditService

router = APIRouter(prefix="/audit", tags=["audit"])


def get_audit_service(session: SessionDep) -> AuditService:
    return AuditService(session)


AuditServiceDep = Annotated[AuditService, Depends(get_audit_service)]


@router.get("/log", response_model=AuditLogResponse)
async def get_audit_log(
    current_user: AdminDep,  # Only admins can view audit logs
    service: AuditServiceDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user_id: UUID | None = None,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
):
    """Query the audit log with filters. Requires admin privileges."""
    offset = (page - 1) * page_size

    entries, total = await service.get_audit_log(
        organization_id=current_user.organization_id,
        user_id=user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        start_date=start_date,
        end_date=end_date,
        limit=page_size,
        offset=offset,
    )

    return AuditLogResponse(
        items=[
            AuditLogEntryWithContext(
                id=e.id,
                organization_id=e.organization_id,
                user=UserRef(
                    id=e.user.id,
                    name=e.user.name,
                    email=e.user.email,
                ) if e.user else None,
                action=e.action,
                resource_type=e.resource_type,
                resource_id=e.resource_id,
                details=e.details,
                created_at=e.created_at,
                previous_hash=e.previous_hash,
                entry_hash=e.entry_hash,
            )
            for e in entries
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/decision/{decision_id}/access-report", response_model=DecisionAccessReport)
async def get_decision_access_report(
    decision_id: UUID,
    current_user: AdminDep,
    service: AuditServiceDep,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
):
    """Get a report of who accessed a specific decision."""
    report = await service.get_decision_access_report(
        decision_id=decision_id,
        start_date=start_date,
        end_date=end_date,
    )

    return DecisionAccessReport(
        decision_id=report["decision_id"],
        decision_number=0,  # Would need to fetch this
        decision_title="",  # Would need to fetch this
        accesses=report["accesses"],
        total_reads=report["total_reads"],
        unique_users=report["unique_users"],
        first_access=report["first_access"],
        last_access=report["last_access"],
    )


@router.get("/summary", response_model=AuditSummaryResponse)
async def get_audit_summary(
    current_user: AdminDep,
    service: AuditServiceDep,
    start_date: datetime = Query(...),
    end_date: datetime = Query(...),
):
    """Get a summary of audit activity for a time period."""
    summary = await service.get_audit_summary(
        organization_id=current_user.organization_id,
        start_date=start_date,
        end_date=end_date,
    )

    return AuditSummaryResponse(
        organization_id=summary["organization_id"],
        period_start=summary["period_start"],
        period_end=summary["period_end"],
        total_events=summary["total_events"],
        actions_by_type=summary["actions_by_type"],
        top_users=summary["top_users"],
    )


@router.post("/verify-chain", response_model=ChainVerificationResult)
async def verify_audit_chain(
    current_user: AdminDep,
    service: AuditServiceDep,
):
    """Verify the cryptographic integrity of the audit chain.

    This checks that no audit entries have been tampered with.
    """
    result = await service.verify_chain_integrity(
        organization_id=current_user.organization_id,
    )

    return ChainVerificationResult(
        is_valid=result["is_valid"],
        verified_entries=0,  # Would need to count
        broken_at_id=result["broken_at_id"],
        expected_hash=result["expected_hash"],
        actual_hash=result["actual_hash"],
        verification_timestamp=result["verified_at"],
    )
