"""
Expiry Engine: Tech Debt Timer and Risk Management.

This module handles the automatic status transitions and notifications
for decisions approaching or past their review dates.

Key responsibilities:
1. Scan for decisions requiring review (AT_RISK window)
2. Flag expired decisions (past review_by_date)
3. Generate notifications for decision owners
4. Support snooze/resolve operations
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Sequence
from uuid import UUID

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import (
    AuditAction,
    AuditLog,
    Decision,
    DecisionStatus,
    DecisionVersion,
    NotificationLog,
    NotificationStatus,
    NotificationType,
    Team,
    TeamMember,
    UpdateRequest,
    User,
)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class ExpiryConfig:
    """Configuration for expiry engine behavior."""

    # Days before review_by_date to mark as AT_RISK
    at_risk_threshold_days: int = 14

    # Days before review_by_date for first reminder
    first_reminder_days: int = 14

    # Days before review_by_date for second reminder
    second_reminder_days: int = 7

    # Days before review_by_date for urgent reminder
    urgent_reminder_days: int = 1

    # Minimum hours between reminder emails for same decision
    reminder_cooldown_hours: int = 24

    # Maximum snooze duration in days
    max_snooze_days: int = 90


DEFAULT_CONFIG = ExpiryConfig()


# =============================================================================
# DATA TRANSFER OBJECTS
# =============================================================================


@dataclass
class ExpiringDecision:
    """A decision that is expiring or at risk."""
    decision_id: UUID
    decision_number: int
    title: str
    organization_id: UUID
    owner_team_id: UUID | None
    owner_team_name: str | None
    created_by: UUID
    creator_name: str
    review_by_date: datetime
    days_until_expiry: int
    status: DecisionStatus
    is_temporary: bool
    last_reminder_sent: datetime | None


@dataclass
class ExpiryStats:
    """Statistics about expiring decisions."""
    total_expired: int
    total_at_risk: int
    expiring_this_week: int
    expiring_this_month: int
    by_team: dict[str, int]  # team_name -> count
    by_impact: dict[str, int]  # impact_level -> count


@dataclass
class SnoozeResult:
    """Result of a snooze operation."""
    decision_id: UUID
    old_review_date: datetime
    new_review_date: datetime
    snoozed_by: UUID
    days_extended: int


@dataclass
class NotificationBatch:
    """A batch of notifications to send."""
    notifications: list[NotificationLog]
    decisions_processed: int
    errors: list[str]


# =============================================================================
# EXPIRY ENGINE
# =============================================================================


class ExpiryEngine:
    """
    Engine for managing decision expiry and tech debt timers.

    This engine runs as part of the daily cron job and handles:
    1. Status transitions (APPROVED -> AT_RISK -> EXPIRED)
    2. Notification generation for stakeholders
    3. Snooze and resolve operations
    """

    def __init__(
        self,
        session: AsyncSession,
        config: ExpiryConfig = DEFAULT_CONFIG,
    ):
        self._session = session
        self._config = config

    # =========================================================================
    # EXPIRY SCANNING
    # =========================================================================

    async def scan_expiring_decisions(
        self,
        organization_id: UUID | None = None,
    ) -> list[ExpiringDecision]:
        """
        Scan for all decisions that are expired or at risk.

        Returns decisions where:
        - review_by_date is set
        - Status is not already SUPERSEDED, DEPRECATED
        - Either past review date (EXPIRED) or within at_risk window
        """
        now = datetime.now(timezone.utc)
        at_risk_threshold = now + timedelta(days=self._config.at_risk_threshold_days)

        query = (
            select(
                Decision,
                DecisionVersion.title,
                User.name.label("creator_name"),
                Team.name.label("team_name"),
            )
            .join(DecisionVersion, Decision.current_version_id == DecisionVersion.id)
            .join(User, Decision.created_by == User.id)
            .outerjoin(Team, Decision.owner_team_id == Team.id)
            .where(
                Decision.deleted_at.is_(None),
                Decision.review_by_date.isnot(None),
                Decision.status.notin_([
                    DecisionStatus.SUPERSEDED,
                    DecisionStatus.DEPRECATED,
                ]),
                Decision.review_by_date <= at_risk_threshold,
            )
            .order_by(Decision.review_by_date.asc())
        )

        if organization_id:
            query = query.where(Decision.organization_id == organization_id)

        result = await self._session.execute(query)
        rows = result.all()

        expiring = []
        for decision, title, creator_name, team_name in rows:
            days_until = (decision.review_by_date.replace(tzinfo=timezone.utc) - now).days

            expiring.append(ExpiringDecision(
                decision_id=decision.id,
                decision_number=decision.decision_number,
                title=title,
                organization_id=decision.organization_id,
                owner_team_id=decision.owner_team_id,
                owner_team_name=team_name,
                created_by=decision.created_by,
                creator_name=creator_name,
                review_by_date=decision.review_by_date,
                days_until_expiry=days_until,
                status=decision.status,
                is_temporary=decision.is_temporary,
                last_reminder_sent=decision.last_review_reminder_sent,
            ))

        return expiring

    async def get_expiry_stats(
        self,
        organization_id: UUID,
    ) -> ExpiryStats:
        """Get aggregated statistics about expiring decisions."""
        now = datetime.now(timezone.utc)
        week_from_now = now + timedelta(days=7)
        month_from_now = now + timedelta(days=30)

        # Base filter
        base_filter = and_(
            Decision.organization_id == organization_id,
            Decision.deleted_at.is_(None),
            Decision.review_by_date.isnot(None),
            Decision.status.notin_([
                DecisionStatus.SUPERSEDED,
                DecisionStatus.DEPRECATED,
            ]),
        )

        # Count expired
        expired_result = await self._session.execute(
            select(func.count()).select_from(Decision).where(
                base_filter,
                Decision.status == DecisionStatus.EXPIRED,
            )
        )
        total_expired = expired_result.scalar_one()

        # Count at risk
        at_risk_result = await self._session.execute(
            select(func.count()).select_from(Decision).where(
                base_filter,
                Decision.status == DecisionStatus.AT_RISK,
            )
        )
        total_at_risk = at_risk_result.scalar_one()

        # Expiring this week
        week_result = await self._session.execute(
            select(func.count()).select_from(Decision).where(
                base_filter,
                Decision.review_by_date <= week_from_now,
                Decision.review_by_date > now,
            )
        )
        expiring_this_week = week_result.scalar_one()

        # Expiring this month
        month_result = await self._session.execute(
            select(func.count()).select_from(Decision).where(
                base_filter,
                Decision.review_by_date <= month_from_now,
                Decision.review_by_date > now,
            )
        )
        expiring_this_month = month_result.scalar_one()

        # By team
        team_result = await self._session.execute(
            select(
                func.coalesce(Team.name, "Unassigned").label("team_name"),
                func.count().label("count"),
            )
            .select_from(Decision)
            .outerjoin(Team, Decision.owner_team_id == Team.id)
            .where(
                base_filter,
                or_(
                    Decision.status == DecisionStatus.EXPIRED,
                    Decision.status == DecisionStatus.AT_RISK,
                ),
            )
            .group_by(Team.name)
        )
        by_team = {row.team_name: row.count for row in team_result.all()}

        # By impact level
        impact_result = await self._session.execute(
            select(
                DecisionVersion.impact_level,
                func.count().label("count"),
            )
            .select_from(Decision)
            .join(DecisionVersion, Decision.current_version_id == DecisionVersion.id)
            .where(
                base_filter,
                or_(
                    Decision.status == DecisionStatus.EXPIRED,
                    Decision.status == DecisionStatus.AT_RISK,
                ),
            )
            .group_by(DecisionVersion.impact_level)
        )
        by_impact = {str(row.impact_level.value): row.count for row in impact_result.all()}

        return ExpiryStats(
            total_expired=total_expired,
            total_at_risk=total_at_risk,
            expiring_this_week=expiring_this_week,
            expiring_this_month=expiring_this_month,
            by_team=by_team,
            by_impact=by_impact,
        )

    # =========================================================================
    # STATUS TRANSITIONS
    # =========================================================================

    async def process_expiry_transitions(
        self,
        organization_id: UUID | None = None,
    ) -> tuple[int, int]:
        """
        Process all pending expiry transitions.

        This is the main method called by the daily cron job.

        Returns: (expired_count, at_risk_count)
        """
        now = datetime.now(timezone.utc)
        at_risk_threshold = now + timedelta(days=self._config.at_risk_threshold_days)

        expired_count = 0
        at_risk_count = 0

        # Base filters
        base_filter = and_(
            Decision.deleted_at.is_(None),
            Decision.review_by_date.isnot(None),
        )

        if organization_id:
            base_filter = and_(base_filter, Decision.organization_id == organization_id)

        # 1. Find and mark EXPIRED decisions
        # These are decisions past their review date that aren't already expired
        expired_query = (
            select(Decision)
            .where(
                base_filter,
                Decision.review_by_date < now,
                Decision.status.notin_([
                    DecisionStatus.EXPIRED,
                    DecisionStatus.SUPERSEDED,
                    DecisionStatus.DEPRECATED,
                ]),
            )
        )

        expired_result = await self._session.execute(expired_query)
        expired_decisions = expired_result.scalars().all()

        for decision in expired_decisions:
            old_status = decision.status
            decision.status = DecisionStatus.EXPIRED

            # Log the transition
            await self._log_audit(
                organization_id=decision.organization_id,
                user_id=None,  # System action
                action=AuditAction.EXPIRE,
                resource_type="decision",
                resource_id=decision.id,
                details={
                    "old_status": old_status.value,
                    "review_by_date": decision.review_by_date.isoformat(),
                    "auto_expired": True,
                },
            )
            expired_count += 1

        # 2. Find and mark AT_RISK decisions
        # These are decisions within the threshold that aren't already at risk or expired
        at_risk_query = (
            select(Decision)
            .where(
                base_filter,
                Decision.review_by_date >= now,
                Decision.review_by_date <= at_risk_threshold,
                Decision.status.notin_([
                    DecisionStatus.AT_RISK,
                    DecisionStatus.EXPIRED,
                    DecisionStatus.SUPERSEDED,
                    DecisionStatus.DEPRECATED,
                ]),
            )
        )

        at_risk_result = await self._session.execute(at_risk_query)
        at_risk_decisions = at_risk_result.scalars().all()

        for decision in at_risk_decisions:
            old_status = decision.status
            decision.status = DecisionStatus.AT_RISK

            # Log the transition
            await self._log_audit(
                organization_id=decision.organization_id,
                user_id=None,  # System action
                action=AuditAction.EXPIRE,  # Using EXPIRE for both transitions
                resource_type="decision",
                resource_id=decision.id,
                details={
                    "old_status": old_status.value,
                    "new_status": DecisionStatus.AT_RISK.value,
                    "review_by_date": decision.review_by_date.isoformat(),
                    "days_until_expiry": (decision.review_by_date.replace(tzinfo=timezone.utc) - now).days,
                },
            )
            at_risk_count += 1

        await self._session.flush()

        return expired_count, at_risk_count

    # =========================================================================
    # SNOOZE OPERATIONS
    # =========================================================================

    async def snooze_decision(
        self,
        decision_id: UUID,
        days: int,
        user_id: UUID,
        reason: str,
    ) -> SnoozeResult:
        """
        Extend the review date for a decision (snooze).

        IMPORTANT: Creates a new DecisionVersion to record the snooze
        in the immutable history, maintaining the ledger pattern.

        Args:
            decision_id: The decision to snooze
            days: Number of days to extend (max from config)
            user_id: Who is snoozing
            reason: REQUIRED explanation for why the delay is necessary

        Returns:
            SnoozeResult with old and new dates
        """
        if days > self._config.max_snooze_days:
            raise ValueError(
                f"Cannot snooze for more than {self._config.max_snooze_days} days"
            )

        if days < 1:
            raise ValueError("Snooze duration must be at least 1 day")

        if not reason or len(reason.strip()) < 10:
            raise ValueError("A reason for snoozing is required (minimum 10 characters)")

        # Fetch decision with current version
        query = (
            select(Decision)
            .where(
                Decision.id == decision_id,
                Decision.deleted_at.is_(None),
            )
            .options(selectinload(Decision.current_version))
        )
        result = await self._session.execute(query)
        decision = result.scalar_one_or_none()

        if not decision:
            raise ValueError(f"Decision {decision_id} not found")

        if decision.review_by_date is None:
            raise ValueError("Cannot snooze a decision without a review date")

        old_review_date = decision.review_by_date
        new_review_date = datetime.now(timezone.utc) + timedelta(days=days)

        # Get current max version number
        version_count_result = await self._session.execute(
            select(func.coalesce(func.max(DecisionVersion.version_number), 0)).where(
                DecisionVersion.decision_id == decision_id
            )
        )
        current_version_number = version_count_result.scalar_one()
        new_version_number = current_version_number + 1

        # Create a new DecisionVersion to record the snooze in history
        # This maintains the immutable ledger pattern
        current_version = decision.current_version
        new_version = DecisionVersion(
            decision_id=decision_id,
            version_number=new_version_number,
            title=current_version.title,
            impact_level=current_version.impact_level,
            content=current_version.content,
            tags=current_version.tags,
            custom_fields=current_version.custom_fields,
            created_by=user_id,
            change_summary=f"[SNOOZE] Review date extended by {days} days. Reason: {reason}",
            content_hash=current_version.content_hash,
        )
        self._session.add(new_version)
        await self._session.flush()  # Get the new version ID

        # Update the decision pointer and dates
        decision.current_version_id = new_version.id
        decision.review_by_date = new_review_date
        decision.last_review_reminder_sent = None  # Reset reminder tracking

        # If it was expired or at risk, move back to approved
        if decision.status in (DecisionStatus.EXPIRED, DecisionStatus.AT_RISK):
            decision.status = DecisionStatus.APPROVED

        # Log the snooze in audit trail
        await self._log_audit(
            organization_id=decision.organization_id,
            user_id=user_id,
            action=AuditAction.SNOOZE,
            resource_type="decision",
            resource_id=decision_id,
            details={
                "old_review_date": old_review_date.isoformat(),
                "new_review_date": new_review_date.isoformat(),
                "days_extended": days,
                "reason": reason,
                "new_version": new_version_number,
            },
        )

        await self._session.flush()

        return SnoozeResult(
            decision_id=decision_id,
            old_review_date=old_review_date,
            new_review_date=new_review_date,
            snoozed_by=user_id,
            days_extended=days,
        )

    async def resolve_tech_debt(
        self,
        decision_id: UUID,
        user_id: UUID,
        resolution_note: str,
        new_review_date: datetime | None = None,
    ) -> Decision:
        """
        Mark a tech debt decision as resolved.

        This removes the review_by_date or sets a new one,
        and transitions the status back to APPROVED.

        Args:
            decision_id: The decision to resolve
            user_id: Who is resolving
            resolution_note: What was done to resolve it
            new_review_date: Optional new review date for ongoing review

        Returns:
            The updated Decision
        """
        query = select(Decision).where(
            Decision.id == decision_id,
            Decision.deleted_at.is_(None),
        )
        result = await self._session.execute(query)
        decision = result.scalar_one_or_none()

        if not decision:
            raise ValueError(f"Decision {decision_id} not found")

        old_status = decision.status
        old_review_date = decision.review_by_date

        # Update decision
        decision.status = DecisionStatus.APPROVED
        decision.review_by_date = new_review_date
        decision.is_temporary = False if new_review_date is None else decision.is_temporary
        decision.last_review_reminder_sent = None

        # Log the resolution
        await self._log_audit(
            organization_id=decision.organization_id,
            user_id=user_id,
            action=AuditAction.RESOLVE,
            resource_type="decision",
            resource_id=decision_id,
            details={
                "old_status": old_status.value,
                "old_review_date": old_review_date.isoformat() if old_review_date else None,
                "new_review_date": new_review_date.isoformat() if new_review_date else None,
                "resolution_note": resolution_note,
            },
        )

        # Resolve any open update requests
        update_requests_query = select(UpdateRequest).where(
            UpdateRequest.decision_id == decision_id,
            UpdateRequest.resolved_at.is_(None),
        )
        update_requests_result = await self._session.execute(update_requests_query)
        for req in update_requests_result.scalars().all():
            req.resolved_at = datetime.now(timezone.utc)
            req.resolved_by = user_id

        await self._session.flush()

        return decision

    # =========================================================================
    # UPDATE REQUESTS
    # =========================================================================

    async def request_update(
        self,
        decision_id: UUID,
        requester_id: UUID,
        message: str | None = None,
        urgency: str = "normal",
    ) -> UpdateRequest:
        """
        Create a request for someone to update a decision.

        This is the "one-click request update" feature for executives.
        """
        # Validate urgency
        if urgency not in ("low", "normal", "high", "critical"):
            urgency = "normal"

        # Check decision exists
        decision_query = select(Decision).where(
            Decision.id == decision_id,
            Decision.deleted_at.is_(None),
        )
        decision_result = await self._session.execute(decision_query)
        decision = decision_result.scalar_one_or_none()

        if not decision:
            raise ValueError(f"Decision {decision_id} not found")

        # Create update request
        update_request = UpdateRequest(
            decision_id=decision_id,
            requested_by=requester_id,
            message=message,
            urgency=urgency,
        )
        self._session.add(update_request)

        # Log it
        await self._log_audit(
            organization_id=decision.organization_id,
            user_id=requester_id,
            action=AuditAction.UPDATE,
            resource_type="update_request",
            resource_id=decision_id,
            details={
                "message": message,
                "urgency": urgency,
            },
        )

        await self._session.flush()

        return update_request

    async def get_pending_update_requests(
        self,
        organization_id: UUID | None = None,
        decision_id: UUID | None = None,
        owner_user_id: UUID | None = None,
    ) -> list[UpdateRequest]:
        """Get all pending (unresolved) update requests."""
        query = (
            select(UpdateRequest)
            .join(Decision, UpdateRequest.decision_id == Decision.id)
            .where(UpdateRequest.resolved_at.is_(None))
            .order_by(
                # Urgency order: critical, high, normal, low
                func.case(
                    (UpdateRequest.urgency == "critical", 1),
                    (UpdateRequest.urgency == "high", 2),
                    (UpdateRequest.urgency == "normal", 3),
                    else_=4,
                ),
                UpdateRequest.created_at.asc(),
            )
        )

        if organization_id:
            query = query.where(Decision.organization_id == organization_id)

        if decision_id:
            query = query.where(UpdateRequest.decision_id == decision_id)

        if owner_user_id:
            query = query.where(Decision.created_by == owner_user_id)

        result = await self._session.execute(query)
        return list(result.scalars().all())

    # =========================================================================
    # NOTIFICATION GENERATION
    # =========================================================================

    async def generate_reminder_notifications(
        self,
        organization_id: UUID | None = None,
    ) -> NotificationBatch:
        """
        Generate reminder notifications for expiring decisions.

        This creates NotificationLog entries that should be processed
        by the notification delivery system.

        Returns:
            NotificationBatch with created notifications
        """
        now = datetime.now(timezone.utc)
        notifications = []
        errors = []
        decisions_processed = 0

        # Get expiring decisions
        expiring = await self.scan_expiring_decisions(organization_id)

        for decision in expiring:
            try:
                # Check cooldown
                if decision.last_reminder_sent:
                    hours_since_last = (now - decision.last_reminder_sent.replace(tzinfo=timezone.utc)).total_seconds() / 3600
                    if hours_since_last < self._config.reminder_cooldown_hours:
                        continue

                # Determine notification type
                if decision.status == DecisionStatus.EXPIRED:
                    notif_type = NotificationType.EXPIRED_ALERT
                    subject = f"[EXPIRED] Decision #{decision.decision_number} requires immediate attention"
                else:
                    notif_type = NotificationType.REVIEW_REMINDER
                    if decision.days_until_expiry <= 1:
                        subject = f"[URGENT] Decision #{decision.decision_number} expires tomorrow"
                    elif decision.days_until_expiry <= 7:
                        subject = f"Decision #{decision.decision_number} expires in {decision.days_until_expiry} days"
                    else:
                        subject = f"Reminder: Decision #{decision.decision_number} review due in {decision.days_until_expiry} days"

                # Get recipients - decision creator and team members
                recipient_ids = await self._get_notification_recipients(decision)

                for recipient_id in recipient_ids:
                    notification = NotificationLog(
                        organization_id=decision.organization_id,
                        decision_id=decision.decision_id,
                        recipient_id=recipient_id,
                        notification_type=notif_type,
                        status=NotificationStatus.PENDING,
                        channel="email",
                        subject=subject,
                        content={
                            "decision_id": str(decision.decision_id),
                            "decision_number": decision.decision_number,
                            "title": decision.title,
                            "review_by_date": decision.review_by_date.isoformat(),
                            "days_until_expiry": decision.days_until_expiry,
                            "is_temporary": decision.is_temporary,
                            "team_name": decision.owner_team_name,
                        },
                    )
                    self._session.add(notification)
                    notifications.append(notification)

                # Update last reminder sent
                decision_update = await self._session.execute(
                    select(Decision).where(Decision.id == decision.decision_id)
                )
                dec = decision_update.scalar_one()
                dec.last_review_reminder_sent = now

                decisions_processed += 1

            except Exception as e:
                errors.append(f"Failed to process decision {decision.decision_id}: {str(e)}")

        await self._session.flush()

        return NotificationBatch(
            notifications=notifications,
            decisions_processed=decisions_processed,
            errors=errors,
        )

    async def _get_notification_recipients(
        self,
        decision: ExpiringDecision,
    ) -> list[UUID]:
        """Get all users who should be notified about a decision."""
        recipients = {decision.created_by}  # Always include creator

        # Add team members if there's an owner team
        if decision.owner_team_id:
            team_members_query = select(TeamMember.user_id).where(
                TeamMember.team_id == decision.owner_team_id
            )
            result = await self._session.execute(team_members_query)
            for row in result.all():
                recipients.add(row.user_id)

        return list(recipients)

    # =========================================================================
    # CALENDAR VIEW DATA
    # =========================================================================

    async def get_calendar_data(
        self,
        organization_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict]:
        """
        Get decisions grouped by review date for calendar view.

        Returns a list of date-grouped decisions for the Debt Wall calendar.
        """
        query = (
            select(
                Decision,
                DecisionVersion.title,
                DecisionVersion.impact_level,
                Team.name.label("team_name"),
            )
            .join(DecisionVersion, Decision.current_version_id == DecisionVersion.id)
            .outerjoin(Team, Decision.owner_team_id == Team.id)
            .where(
                Decision.organization_id == organization_id,
                Decision.deleted_at.is_(None),
                Decision.review_by_date.isnot(None),
                Decision.review_by_date >= start_date,
                Decision.review_by_date <= end_date,
                Decision.status.notin_([
                    DecisionStatus.SUPERSEDED,
                    DecisionStatus.DEPRECATED,
                ]),
            )
            .order_by(Decision.review_by_date.asc())
        )

        result = await self._session.execute(query)
        rows = result.all()

        # Group by date
        calendar_data = {}
        for decision, title, impact_level, team_name in rows:
            date_key = decision.review_by_date.strftime("%Y-%m-%d")

            if date_key not in calendar_data:
                calendar_data[date_key] = {
                    "date": date_key,
                    "decisions": [],
                }

            calendar_data[date_key]["decisions"].append({
                "id": str(decision.id),
                "decision_number": decision.decision_number,
                "title": title,
                "status": decision.status.value,
                "impact_level": impact_level.value,
                "team_name": team_name,
                "is_temporary": decision.is_temporary,
            })

        return list(calendar_data.values())

    async def get_heatmap_data(
        self,
        organization_id: UUID,
        months: int = 12,
    ) -> list[dict]:
        """
        Get weekly aggregated data for the heatmap visualization.

        Returns weekly counts of expiring decisions for the past N months.
        """
        now = datetime.now(timezone.utc)
        start_date = now - timedelta(days=months * 30)
        end_date = now + timedelta(days=months * 30)

        query = (
            select(
                func.date_trunc("week", Decision.review_by_date).label("week"),
                func.count().label("count"),
            )
            .where(
                Decision.organization_id == organization_id,
                Decision.deleted_at.is_(None),
                Decision.review_by_date.isnot(None),
                Decision.review_by_date >= start_date,
                Decision.review_by_date <= end_date,
            )
            .group_by(func.date_trunc("week", Decision.review_by_date))
            .order_by("week")
        )

        result = await self._session.execute(query)

        return [
            {
                "week": row.week.strftime("%Y-%m-%d"),
                "count": row.count,
            }
            for row in result.all()
        ]

    async def get_team_heatmap_data(
        self,
        organization_id: UUID,
    ) -> list[dict]:
        """
        Get team-based heatmap data showing tech debt by team.

        Returns teams with their expired/at-risk decision counts.
        Color coding:
        - Red: Teams with many expired/overdue decisions
        - Yellow: Teams with some at-risk decisions
        - Green: Teams with zero debt

        This is the "Accountability" view for executives.
        """
        # Get all teams in the org with their decision counts
        query = (
            select(
                func.coalesce(Team.name, "Unassigned").label("team_name"),
                Team.id.label("team_id"),
                func.count(Decision.id).filter(
                    Decision.status == DecisionStatus.EXPIRED
                ).label("expired_count"),
                func.count(Decision.id).filter(
                    Decision.status == DecisionStatus.AT_RISK
                ).label("at_risk_count"),
                func.count(Decision.id).filter(
                    Decision.status.in_([
                        DecisionStatus.APPROVED,
                        DecisionStatus.DRAFT,
                        DecisionStatus.PENDING_REVIEW,
                    ])
                ).label("healthy_count"),
                func.count(Decision.id).label("total_count"),
            )
            .select_from(Decision)
            .outerjoin(Team, Decision.owner_team_id == Team.id)
            .where(
                Decision.organization_id == organization_id,
                Decision.deleted_at.is_(None),
                Decision.review_by_date.isnot(None),
                Decision.status.notin_([
                    DecisionStatus.SUPERSEDED,
                    DecisionStatus.DEPRECATED,
                ]),
            )
            .group_by(Team.id, Team.name)
            .order_by(
                # Sort by expired count descending (worst teams first)
                func.count(Decision.id).filter(
                    Decision.status == DecisionStatus.EXPIRED
                ).desc(),
                func.count(Decision.id).filter(
                    Decision.status == DecisionStatus.AT_RISK
                ).desc(),
            )
        )

        result = await self._session.execute(query)
        rows = result.all()

        teams = []
        for row in rows:
            # Calculate health score (0-100, higher is better)
            total = row.total_count or 1
            expired_weight = row.expired_count * 3  # Expired counts more
            at_risk_weight = row.at_risk_count * 1
            health_score = max(0, 100 - ((expired_weight + at_risk_weight) / total * 100))

            # Determine color category
            if row.expired_count > 0:
                color = "red"
            elif row.at_risk_count > 0:
                color = "yellow"
            else:
                color = "green"

            teams.append({
                "team_name": row.team_name,
                "team_id": str(row.team_id) if row.team_id else None,
                "expired_count": row.expired_count,
                "at_risk_count": row.at_risk_count,
                "healthy_count": row.healthy_count,
                "total_count": row.total_count,
                "health_score": round(health_score, 1),
                "color": color,
            })

        return teams

    async def get_tag_heatmap_data(
        self,
        organization_id: UUID,
    ) -> list[dict]:
        """
        Get tag-based heatmap data showing tech debt by tag/category.

        Groups decisions by their tags and shows expired/at-risk counts.
        Useful for identifying problem areas by domain (e.g., "security", "performance").
        """
        # This requires aggregating by tags (which is an array field)
        # We'll use unnest to expand the tags array
        query = (
            select(
                func.unnest(DecisionVersion.tags).label("tag"),
                func.count(Decision.id).filter(
                    Decision.status == DecisionStatus.EXPIRED
                ).label("expired_count"),
                func.count(Decision.id).filter(
                    Decision.status == DecisionStatus.AT_RISK
                ).label("at_risk_count"),
                func.count(Decision.id).label("total_count"),
            )
            .select_from(Decision)
            .join(DecisionVersion, Decision.current_version_id == DecisionVersion.id)
            .where(
                Decision.organization_id == organization_id,
                Decision.deleted_at.is_(None),
                Decision.review_by_date.isnot(None),
                Decision.status.notin_([
                    DecisionStatus.SUPERSEDED,
                    DecisionStatus.DEPRECATED,
                ]),
            )
            .group_by(func.unnest(DecisionVersion.tags))
            .order_by(
                func.count(Decision.id).filter(
                    Decision.status == DecisionStatus.EXPIRED
                ).desc(),
            )
        )

        result = await self._session.execute(query)
        rows = result.all()

        tags = []
        for row in rows:
            total = row.total_count or 1
            expired_weight = row.expired_count * 3
            at_risk_weight = row.at_risk_count * 1
            health_score = max(0, 100 - ((expired_weight + at_risk_weight) / total * 100))

            if row.expired_count > 0:
                color = "red"
            elif row.at_risk_count > 0:
                color = "yellow"
            else:
                color = "green"

            tags.append({
                "tag": row.tag,
                "expired_count": row.expired_count,
                "at_risk_count": row.at_risk_count,
                "total_count": row.total_count,
                "health_score": round(health_score, 1),
                "color": color,
            })

        return tags

    # =========================================================================
    # INTERNAL HELPERS
    # =========================================================================

    async def _log_audit(
        self,
        organization_id: UUID,
        user_id: UUID | None,
        action: AuditAction,
        resource_type: str,
        resource_id: UUID,
        details: dict,
    ) -> None:
        """Log an audit event."""
        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
        )
        self._session.add(audit)
