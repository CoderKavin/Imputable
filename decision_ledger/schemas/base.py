"""Base schemas and common types for Decision Ledger API."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# =============================================================================
# ENUMS (Mirror database enums)
# =============================================================================


class DecisionStatus(str, Enum):
    """Status of a decision in its lifecycle."""

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"


class ImpactLevel(str, Enum):
    """Impact level classification for decisions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RelationshipType(str, Enum):
    """Types of relationships between decisions."""

    SUPERSEDES = "supersedes"
    BLOCKED_BY = "blocked_by"
    RELATED_TO = "related_to"
    IMPLEMENTS = "implements"
    CONFLICTS_WITH = "conflicts_with"


class ApprovalStatus(str, Enum):
    """Status of an approval."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ABSTAINED = "abstained"


class AuditAction(str, Enum):
    """Types of auditable actions."""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    APPROVE = "approve"
    REJECT = "reject"
    SUPERSEDE = "supersede"
    DEPRECATE = "deprecate"
    EXPORT = "export"
    SHARE = "share"


class OrgRole(str, Enum):
    """Organization membership roles."""

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class TeamRole(str, Enum):
    """Team membership roles."""

    LEAD = "lead"
    MEMBER = "member"


# =============================================================================
# BASE SCHEMAS
# =============================================================================


class LedgerBaseModel(BaseModel):
    """Base model with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,  # Enable ORM mode
        populate_by_name=True,
        use_enum_values=True,
        json_schema_extra={"example": {}},
    )


class TimestampMixin(BaseModel):
    """Mixin for created/updated timestamps."""

    created_at: datetime
    updated_at: datetime | None = None


class SoftDeleteMixin(BaseModel):
    """Mixin for soft-deletable entities."""

    deleted_at: datetime | None = None


# =============================================================================
# PAGINATION
# =============================================================================


class PaginationParams(BaseModel):
    """Query parameters for pagination."""

    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(
        default=20, ge=1, le=100, description="Items per page"
    )

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class PaginatedResponse(LedgerBaseModel):
    """Wrapper for paginated responses."""

    items: list[Any]
    total: int
    page: int
    page_size: int
    total_pages: int

    @classmethod
    def create(
        cls,
        items: list[Any],
        total: int,
        page: int,
        page_size: int,
    ) -> "PaginatedResponse":
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size,
        )


# =============================================================================
# ERROR RESPONSES
# =============================================================================


class ErrorDetail(LedgerBaseModel):
    """Detailed error information."""

    field: str | None = None
    message: str
    code: str


class ErrorResponse(LedgerBaseModel):
    """Standard error response format."""

    error: str
    message: str
    details: list[ErrorDetail] = []
    request_id: str | None = None


# =============================================================================
# COMMON REFERENCE SCHEMAS
# =============================================================================


class UserRef(LedgerBaseModel):
    """Minimal user reference for embedding in responses."""

    id: UUID
    name: str
    email: EmailStr
    avatar_url: str | None = None


class TeamRef(LedgerBaseModel):
    """Minimal team reference for embedding in responses."""

    id: UUID
    slug: str
    name: str


class OrganizationRef(LedgerBaseModel):
    """Minimal organization reference."""

    id: UUID
    slug: str
    name: str


class DecisionRef(LedgerBaseModel):
    """Minimal decision reference for relationships."""

    id: UUID
    decision_number: int
    title: str
    status: DecisionStatus
