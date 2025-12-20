"""Pydantic schemas for Audit Log and compliance features."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from .base import (
    AuditAction,
    LedgerBaseModel,
    PaginatedResponse,
    UserRef,
)


# =============================================================================
# AUDIT LOG SCHEMAS
# =============================================================================


class AuditLogEntry(LedgerBaseModel):
    """A single audit log entry."""

    id: UUID
    organization_id: UUID
    user: UserRef | None = None  # None for system actions
    action: AuditAction
    resource_type: str
    resource_id: UUID
    details: dict
    created_at: datetime

    # Chain integrity
    previous_hash: str | None = None
    entry_hash: str | None = None


class AuditLogEntryWithContext(AuditLogEntry):
    """Audit entry with resolved resource information."""

    resource_title: str | None = None
    resource_status: str | None = None


class AuditLogQuery(LedgerBaseModel):
    """Query parameters for audit log searches."""

    user_id: UUID | None = None
    action: list[AuditAction] | None = None
    resource_type: str | None = None
    resource_id: UUID | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None


class AuditLogResponse(PaginatedResponse):
    """Paginated audit log response."""

    items: list[AuditLogEntryWithContext]


# =============================================================================
# AUDIT SUMMARY SCHEMAS
# =============================================================================


class AuditActionSummary(LedgerBaseModel):
    """Summary of actions by type."""

    action: AuditAction
    resource_type: str
    event_count: int
    first_occurrence: datetime
    last_occurrence: datetime


class UserActivitySummary(LedgerBaseModel):
    """Summary of a user's activity."""

    user: UserRef
    action: AuditAction
    action_count: int
    last_activity: datetime


class AuditSummaryResponse(LedgerBaseModel):
    """Overall audit summary for an organization."""

    organization_id: UUID
    period_start: datetime
    period_end: datetime
    total_events: int
    actions_by_type: list[AuditActionSummary]
    top_users: list[UserActivitySummary]


# =============================================================================
# CHAIN VERIFICATION
# =============================================================================


class ChainVerificationResult(LedgerBaseModel):
    """Result of audit chain integrity verification."""

    is_valid: bool
    verified_entries: int
    broken_at_id: UUID | None = None
    expected_hash: str | None = None
    actual_hash: str | None = None
    verification_timestamp: datetime


# =============================================================================
# COMPLIANCE REPORT SCHEMAS
# =============================================================================


class DecisionAccessReport(LedgerBaseModel):
    """Report of who accessed a specific decision."""

    decision_id: UUID
    decision_number: int
    decision_title: str
    accesses: list[AuditLogEntry]
    total_reads: int
    unique_users: int
    first_access: datetime | None = None
    last_access: datetime | None = None


class UserAccessReport(LedgerBaseModel):
    """Report of what a specific user accessed."""

    user: UserRef
    period_start: datetime
    period_end: datetime
    decisions_accessed: list[UUID]
    total_actions: int
    actions_by_type: dict[str, int]


class ComplianceExport(LedgerBaseModel):
    """Compliance data export request."""

    organization_id: UUID
    start_date: datetime
    end_date: datetime
    include_user_details: bool = True
    include_decision_content: bool = False  # Sensitive!
    format: str = Field(
        default="json",
        pattern=r"^(json|csv)$",
    )


class ComplianceExportResponse(LedgerBaseModel):
    """Response for compliance export request."""

    export_id: UUID
    status: str  # "pending", "processing", "completed", "failed"
    download_url: str | None = None
    expires_at: datetime | None = None
    record_count: int | None = None


# =============================================================================
# SESSION SCHEMAS
# =============================================================================


class SessionInfo(LedgerBaseModel):
    """Current session information."""

    id: UUID
    user_id: UUID
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime
    expires_at: datetime


class SessionCreate(LedgerBaseModel):
    """Create a new session (internal use)."""

    user_id: UUID
    ip_address: str | None = None
    user_agent: str | None = None
    expires_in_hours: int = Field(default=24, ge=1, le=720)
