"""SQLAlchemy ORM Models for Decision Ledger.

These models map directly to the PostgreSQL schema defined in db/schema.sql.
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


# =============================================================================
# ENUMS
# =============================================================================


class SubscriptionTier(str, PyEnum):
    """Subscription tiers for billing."""
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class DecisionStatus(str, PyEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"  # Review date passed without action
    AT_RISK = "at_risk"  # Approaching review date (warning state)


class ImpactLevel(str, PyEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RelationshipType(str, PyEnum):
    SUPERSEDES = "supersedes"
    BLOCKED_BY = "blocked_by"
    RELATED_TO = "related_to"
    IMPLEMENTS = "implements"
    CONFLICTS_WITH = "conflicts_with"


class AuditAction(str, PyEnum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    APPROVE = "approve"
    REJECT = "reject"
    SUPERSEDE = "supersede"
    DEPRECATE = "deprecate"
    EXPORT = "export"
    SHARE = "share"
    EXPIRE = "expire"  # Decision expired
    SNOOZE = "snooze"  # Review date extended
    RESOLVE = "resolve"  # Tech debt resolved


class ApprovalStatus(str, PyEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ABSTAINED = "abstained"


# =============================================================================
# ORGANIZATION & USER MODELS
# =============================================================================


class Organization(Base, UUIDMixin, SoftDeleteMixin):
    """Multi-tenant organization."""

    __tablename__ = "organizations"

    slug: Mapped[str] = mapped_column(String(63), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    # Billing fields
    subscription_tier: Mapped[SubscriptionTier] = mapped_column(
        Enum(SubscriptionTier, name="subscription_tier", values_callable=lambda x: [e.value for e in x]),
        default=SubscriptionTier.FREE,
        nullable=False,
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Stripe customer ID for billing"
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Active Stripe subscription ID"
    )

    # Slack Integration (OAuth - SaaS Mode)
    slack_access_token: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Encrypted Slack OAuth access token"
    )
    slack_team_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Slack workspace/team ID"
    )
    slack_team_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Slack workspace name for display"
    )
    slack_channel_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Default Slack channel ID for notifications"
    )
    slack_channel_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Default Slack channel name for display"
    )
    slack_bot_user_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Slack bot user ID"
    )
    slack_installed_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="When Slack integration was installed"
    )

    # Microsoft Teams Integration (Webhook - Enterprise Mode)
    teams_webhook_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Microsoft Teams Incoming Webhook URL"
    )
    teams_channel_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Teams channel name for display"
    )
    teams_installed_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="When Teams integration was configured"
    )

    # Microsoft Teams Bot Framework Integration
    teams_tenant_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Azure AD tenant ID for Teams Bot authentication"
    )
    teams_bot_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Teams Bot registration ID from Azure Bot Service"
    )
    teams_service_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Teams Bot Framework service URL for sending proactive messages"
    )

    # Relationships
    members: Mapped[list["OrganizationMember"]] = relationship(
        back_populates="organization"
    )
    teams: Mapped[list["Team"]] = relationship(back_populates="organization")
    decisions: Mapped[list["Decision"]] = relationship(
        back_populates="organization"
    )
    tags: Mapped[list["Tag"]] = relationship(back_populates="organization")

    __table_args__ = (
        CheckConstraint(
            "slug ~ '^[a-z0-9][a-z0-9-]*[a-z0-9]$'",
            name="slug_format",
        ),
        Index("idx_organizations_slug", "slug", postgresql_where="deleted_at IS NULL"),
    )


class User(Base, UUIDMixin, SoftDeleteMixin):
    """Application user."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    auth_provider: Mapped[str] = mapped_column(String(50), default="email")
    auth_provider_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column()

    # Relationships
    org_memberships: Mapped[list["OrganizationMember"]] = relationship(
        back_populates="user", foreign_keys="OrganizationMember.user_id"
    )
    team_memberships: Mapped[list["TeamMember"]] = relationship(
        back_populates="user"
    )

    __table_args__ = (
        Index("idx_users_email", "email", postgresql_where="deleted_at IS NULL"),
    )


class OrganizationMember(Base, UUIDMixin):
    """Membership linking users to organizations."""

    __tablename__ = "organization_members"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(50), default="member")
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    invited_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(
        back_populates="org_memberships", foreign_keys=[user_id]
    )
    inviter: Mapped["User | None"] = relationship(foreign_keys=[invited_by])

    __table_args__ = (
        UniqueConstraint("organization_id", "user_id"),
        Index("idx_org_members_org", "organization_id"),
        Index("idx_org_members_user", "user_id"),
    )


class Team(Base, UUIDMixin, SoftDeleteMixin):
    """Team within an organization."""

    __tablename__ = "teams"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(63), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    parent_team_id: Mapped[UUID | None] = mapped_column(ForeignKey("teams.id"))
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="teams")
    parent_team: Mapped["Team | None"] = relationship(
        back_populates="child_teams", remote_side="Team.id"
    )
    child_teams: Mapped[list["Team"]] = relationship(back_populates="parent_team")
    members: Mapped[list["TeamMember"]] = relationship(back_populates="team")
    owned_decisions: Mapped[list["Decision"]] = relationship(
        back_populates="owner_team"
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "slug"),
        Index("idx_teams_org", "organization_id", postgresql_where="deleted_at IS NULL"),
    )


class TeamMember(Base, UUIDMixin):
    """Membership linking users to teams."""

    __tablename__ = "team_members"

    team_id: Mapped[UUID] = mapped_column(ForeignKey("teams.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="member")
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    # Relationships
    team: Mapped["Team"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="team_memberships")

    __table_args__ = (
        UniqueConstraint("team_id", "user_id"),
        Index("idx_team_members_team", "team_id"),
    )


# =============================================================================
# DECISION MODELS (Core)
# =============================================================================


class Decision(Base, UUIDMixin, SoftDeleteMixin):
    """The immutable decision header (anchor entity)."""

    __tablename__ = "decisions"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    decision_number: Mapped[int] = mapped_column(Integer, autoincrement=True)
    current_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("decision_versions.id", use_alter=True)
    )
    status: Mapped[DecisionStatus] = mapped_column(
        Enum(DecisionStatus, name="decision_status", values_callable=lambda x: [e.value for e in x]),
        default=DecisionStatus.DRAFT,
    )
    owner_team_id: Mapped[UUID | None] = mapped_column(ForeignKey("teams.id"))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    # Tech Debt Timer fields
    review_by_date: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="Date by which this decision must be reviewed (tech debt timer)"
    )
    last_review_reminder_sent: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="Last time a review reminder was sent"
    )
    is_temporary: Mapped[bool] = mapped_column(
        default=False,
        comment="Flag indicating this is a temporary/expedient decision"
    )

    # Source tracking (for Slack integration)
    source: Mapped[str] = mapped_column(
        String(20),
        default="web",
        comment="Origin of the decision: web, slack"
    )
    slack_channel_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Slack channel ID where decision was created"
    )
    slack_message_ts: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Slack message timestamp for deep linking"
    )
    slack_thread_ts: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Slack thread timestamp if created in a thread"
    )

    # Teams source tracking (for Teams integration)
    teams_message_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Teams message ID for deep linking to source conversation"
    )
    teams_conversation_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Teams conversation/channel ID for deep linking"
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="decisions")
    owner_team: Mapped["Team | None"] = relationship(back_populates="owned_decisions")
    creator: Mapped["User"] = relationship(foreign_keys=[created_by])
    current_version: Mapped["DecisionVersion | None"] = relationship(
        foreign_keys=[current_version_id], post_update=True
    )
    versions: Mapped[list["DecisionVersion"]] = relationship(
        back_populates="decision",
        foreign_keys="DecisionVersion.decision_id",
        order_by="DecisionVersion.version_number",
    )
    outgoing_relationships: Mapped[list["DecisionRelationship"]] = relationship(
        back_populates="source_decision",
        foreign_keys="DecisionRelationship.source_decision_id",
    )
    incoming_relationships: Mapped[list["DecisionRelationship"]] = relationship(
        back_populates="target_decision",
        foreign_keys="DecisionRelationship.target_decision_id",
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "decision_number"),
        Index("idx_decisions_org", "organization_id", postgresql_where="deleted_at IS NULL"),
        Index(
            "idx_decisions_status",
            "organization_id",
            "status",
            postgresql_where="deleted_at IS NULL",
        ),
        Index("idx_decisions_owner_team", "owner_team_id", postgresql_where="deleted_at IS NULL"),
        Index("idx_decisions_created_by", "created_by"),
        # Tech Debt Timer indexes
        Index(
            "idx_decisions_review_by_date",
            "organization_id",
            "review_by_date",
            postgresql_where="deleted_at IS NULL AND review_by_date IS NOT NULL",
        ),
        # Note: Partial index for expiring decisions removed due to PostgreSQL enum casting issues
        # The idx_decisions_review_by_date index above covers the main use case
    )


class DecisionVersion(Base, UUIDMixin):
    """Immutable snapshot of decision content."""

    __tablename__ = "decision_versions"

    decision_id: Mapped[UUID] = mapped_column(
        ForeignKey("decisions.id"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    impact_level: Mapped[ImpactLevel] = mapped_column(
        Enum(ImpactLevel, name="impact_level", values_callable=lambda x: [e.value for e in x]),
        default=ImpactLevel.MEDIUM,
    )
    content: Mapped[dict] = mapped_column(JSONB, default=dict)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    custom_fields: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    change_summary: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(64))

    # Relationships
    decision: Mapped["Decision"] = relationship(
        back_populates="versions", foreign_keys=[decision_id]
    )
    creator: Mapped["User"] = relationship(foreign_keys=[created_by])
    approvals: Mapped[list["Approval"]] = relationship(back_populates="decision_version")
    required_reviewers: Mapped[list["RequiredReviewer"]] = relationship(
        back_populates="decision_version"
    )

    __table_args__ = (
        UniqueConstraint("decision_id", "version_number"),
        Index("idx_decision_versions_decision", "decision_id"),
        Index("idx_decision_versions_created_at", "created_at"),
        Index("idx_decision_versions_tags", "tags", postgresql_using="gin"),
        Index(
            "idx_decision_versions_content",
            "content",
            postgresql_using="gin",
            postgresql_ops={"content": "jsonb_path_ops"},
        ),
    )


class DecisionRelationship(Base, UUIDMixin):
    """Directed relationship between decisions."""

    __tablename__ = "decision_relationships"

    source_decision_id: Mapped[UUID] = mapped_column(
        ForeignKey("decisions.id"), nullable=False
    )
    target_decision_id: Mapped[UUID] = mapped_column(
        ForeignKey("decisions.id"), nullable=False
    )
    relationship_type: Mapped[RelationshipType] = mapped_column(
        Enum(RelationshipType, name="relationship_type", values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    invalidated_at: Mapped[datetime | None] = mapped_column()
    invalidated_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))

    # Relationships
    source_decision: Mapped["Decision"] = relationship(
        back_populates="outgoing_relationships",
        foreign_keys=[source_decision_id],
    )
    target_decision: Mapped["Decision"] = relationship(
        back_populates="incoming_relationships",
        foreign_keys=[target_decision_id],
    )
    creator: Mapped["User"] = relationship(foreign_keys=[created_by])
    invalidator: Mapped["User | None"] = relationship(foreign_keys=[invalidated_by])

    __table_args__ = (
        UniqueConstraint(
            "source_decision_id", "target_decision_id", "relationship_type"
        ),
        CheckConstraint(
            "source_decision_id != target_decision_id", name="no_self_reference"
        ),
        Index(
            "idx_relationships_source",
            "source_decision_id",
            postgresql_where="invalidated_at IS NULL",
        ),
        Index(
            "idx_relationships_target",
            "target_decision_id",
            postgresql_where="invalidated_at IS NULL",
        ),
        Index(
            "idx_relationships_type",
            "relationship_type",
            postgresql_where="invalidated_at IS NULL",
        ),
    )


# =============================================================================
# APPROVAL MODELS
# =============================================================================


class Approval(Base, UUIDMixin):
    """Approval record for a decision version."""

    __tablename__ = "approvals"

    decision_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("decision_versions.id"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus, name="approval_status", values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    # Relationships
    decision_version: Mapped["DecisionVersion"] = relationship(
        back_populates="approvals"
    )
    user: Mapped["User"] = relationship()

    __table_args__ = (
        UniqueConstraint("decision_version_id", "user_id"),
        Index("idx_approvals_version", "decision_version_id"),
        Index("idx_approvals_user", "user_id"),
        Index("idx_approvals_status", "decision_version_id", "status"),
    )


class RequiredReviewer(Base, UUIDMixin):
    """Required approver for a decision version."""

    __tablename__ = "required_reviewers"

    decision_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("decision_versions.id"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    required_role: Mapped[str | None] = mapped_column(String(50))
    added_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    # Relationships
    decision_version: Mapped["DecisionVersion"] = relationship(
        back_populates="required_reviewers"
    )
    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    adder: Mapped["User"] = relationship(foreign_keys=[added_by])

    __table_args__ = (
        UniqueConstraint("decision_version_id", "user_id"),
        Index("idx_required_reviewers_version", "decision_version_id"),
    )


# =============================================================================
# AUDIT MODELS
# =============================================================================


class AuditLog(Base, UUIDMixin):
    """Append-only audit trail."""

    __tablename__ = "audit_log"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, name="audit_action", values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    previous_hash: Mapped[str | None] = mapped_column(String(64))
    entry_hash: Mapped[str | None] = mapped_column(String(64))

    # Relationships
    organization: Mapped["Organization"] = relationship()
    user: Mapped["User | None"] = relationship()

    __table_args__ = (
        Index("idx_audit_log_org_time", "organization_id", "created_at"),
        Index("idx_audit_log_user", "user_id", "created_at"),
        Index("idx_audit_log_resource", "resource_type", "resource_id"),
        Index("idx_audit_log_action", "action", "created_at"),
    )


class Session(Base, UUIDMixin):
    """User session for audit context."""

    __tablename__ = "sessions"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column()

    # Relationships
    user: Mapped["User"] = relationship()

    __table_args__ = (
        Index("idx_sessions_user", "user_id", postgresql_where="revoked_at IS NULL"),
    )


# =============================================================================
# TAG MODEL
# =============================================================================


class Tag(Base, UUIDMixin):
    """Centralized tag management."""

    __tablename__ = "tags"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[str] = mapped_column(String(7), default="#6366f1")
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="tags")

    __table_args__ = (
        UniqueConstraint("organization_id", "name"),
        Index("idx_tags_org", "organization_id"),
    )


# =============================================================================
# NOTIFICATION MODELS (Tech Debt Timer)
# =============================================================================


class NotificationType(str, PyEnum):
    """Types of notifications."""
    REVIEW_REMINDER = "review_reminder"  # Decision needs review soon
    EXPIRED_ALERT = "expired_alert"  # Decision has expired
    UPDATE_REQUEST = "update_request"  # Someone requested an update
    DAILY_DIGEST = "daily_digest"  # Daily summary of expiring decisions


class NotificationStatus(str, PyEnum):
    """Status of notification delivery."""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"  # User opted out


class NotificationLog(Base, UUIDMixin):
    """Log of all notifications sent for audit and deduplication."""

    __tablename__ = "notification_log"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    decision_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("decisions.id"), nullable=True
    )
    recipient_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    notification_type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notification_type", values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus, name="notification_status", values_callable=lambda x: [e.value for e in x]),
        default=NotificationStatus.PENDING,
    )
    channel: Mapped[str] = mapped_column(
        String(50), default="email",
        comment="Delivery channel: email, webhook, slack"
    )
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, default=dict)
    sent_at: Mapped[datetime | None] = mapped_column()
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship()
    decision: Mapped["Decision | None"] = relationship()
    recipient: Mapped["User"] = relationship()

    __table_args__ = (
        Index("idx_notification_log_org", "organization_id", "created_at"),
        Index("idx_notification_log_decision", "decision_id", "created_at"),
        Index("idx_notification_log_recipient", "recipient_id", "created_at"),
        # Note: Partial index for pending status removed due to PostgreSQL enum casting issues
        Index("idx_notification_log_status", "status"),
    )


class UpdateRequest(Base, UUIDMixin):
    """Track requests for decision updates from stakeholders."""

    __tablename__ = "update_requests"

    decision_id: Mapped[UUID] = mapped_column(
        ForeignKey("decisions.id"), nullable=False
    )
    requested_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    message: Mapped[str | None] = mapped_column(Text)
    urgency: Mapped[str] = mapped_column(
        String(20), default="normal",
        comment="Urgency level: low, normal, high, critical"
    )
    resolved_at: Mapped[datetime | None] = mapped_column()
    resolved_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    # Relationships
    decision: Mapped["Decision"] = relationship()
    requester: Mapped["User"] = relationship(foreign_keys=[requested_by])
    resolver: Mapped["User | None"] = relationship(foreign_keys=[resolved_by])

    __table_args__ = (
        Index("idx_update_requests_decision", "decision_id"),
        Index("idx_update_requests_pending", "decision_id", postgresql_where="resolved_at IS NULL"),
    )


# =============================================================================
# CONSENSUS POLLING MODELS
# =============================================================================


class PollVoteType(str, PyEnum):
    """Types of consensus poll votes."""
    AGREE = "agree"
    CONCERN = "concern"
    BLOCK = "block"


class PollVote(Base, UUIDMixin):
    """Consensus poll vote from Slack/Teams.

    Supports both internal Imputable users and external Slack/Teams users.
    Each user (internal or external) can have one vote per decision.
    """

    __tablename__ = "poll_votes"

    decision_id: Mapped[UUID] = mapped_column(
        ForeignKey("decisions.id", ondelete="CASCADE"), nullable=False
    )

    # Voter identification (one of user_id or external_user_id must be set)
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True,
        comment="Internal Imputable user ID"
    )
    external_user_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
        comment="External Slack user ID or Teams user ID"
    )
    external_user_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="Display name for external users"
    )

    # Vote details
    vote_type: Mapped[PollVoteType] = mapped_column(
        Enum(PollVoteType, name="poll_vote_type", values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )
    comment: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Optional comment with vote"
    )

    # Source tracking
    source: Mapped[str] = mapped_column(
        String(20), default="slack",
        comment="Source platform: slack or teams"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    decision: Mapped["Decision"] = relationship()
    user: Mapped["User | None"] = relationship()

    __table_args__ = (
        # One vote per internal user per decision
        UniqueConstraint("decision_id", "user_id", name="uq_poll_votes_internal_user"),
        # One vote per external user per decision per source
        UniqueConstraint("decision_id", "external_user_id", "source", name="uq_poll_votes_external_user"),
        # Ensure at least one identifier is provided
        CheckConstraint(
            "user_id IS NOT NULL OR external_user_id IS NOT NULL",
            name="chk_poll_votes_user_identifier"
        ),
        Index("idx_poll_votes_decision", "decision_id"),
        Index("idx_poll_votes_user", "user_id", postgresql_where="user_id IS NOT NULL"),
        Index("idx_poll_votes_external", "external_user_id", "source", postgresql_where="external_user_id IS NOT NULL"),
    )


class LoggedMessage(Base, UUIDMixin):
    """Track Slack/Teams messages that have been logged as decisions.

    Used for duplicate detection to prevent the same message from being
    logged multiple times.
    """

    __tablename__ = "logged_messages"

    # Source message identifiers
    source: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="Source platform: slack or teams"
    )
    message_id: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="Slack message_ts or Teams message ID"
    )
    channel_id: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="Channel or conversation ID"
    )

    # Link to created decision
    decision_id: Mapped[UUID] = mapped_column(
        ForeignKey("decisions.id", ondelete="CASCADE"), nullable=False
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    # Relationships
    decision: Mapped["Decision"] = relationship()

    __table_args__ = (
        # Prevent duplicate logging of same message
        UniqueConstraint("source", "message_id", "channel_id", name="uq_logged_messages_source_message"),
        Index("idx_logged_messages_lookup", "source", "message_id", "channel_id"),
        Index("idx_logged_messages_decision", "decision_id"),
    )
