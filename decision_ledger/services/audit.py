"""Audit service: logging and compliance reporting."""

from datetime import datetime
from typing import Any, Sequence
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditAction, AuditLog


class AuditService:
    """Service for audit logging and compliance."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def log_event(
        self,
        organization_id: UUID,
        action: AuditAction,
        resource_type: str,
        resource_id: UUID,
        user_id: UUID | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Log an audit event using the database function."""
        # Use the PostgreSQL function for chain integrity
        result = await self.session.execute(
            text("""
                SELECT log_audit_event(
                    :action::audit_action,
                    :resource_type,
                    :resource_id,
                    :details::jsonb
                )
            """),
            {
                "action": action.value,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "details": details or {},
            },
        )
        audit_id = result.scalar_one()

        # Fetch and return the created entry
        query = select(AuditLog).where(AuditLog.id == audit_id)
        result = await self.session.execute(query)
        return result.scalar_one()

    async def log_decision_read(
        self,
        decision_id: UUID,
        version_id: UUID | None = None,
        fields_accessed: list[str] | None = None,
    ) -> None:
        """Log a read access to a decision."""
        await self.session.execute(
            text("""
                SELECT log_decision_read(
                    :decision_id,
                    :version_id,
                    :fields_accessed
                )
            """),
            {
                "decision_id": decision_id,
                "version_id": version_id,
                "fields_accessed": fields_accessed or [],
            },
        )

    async def log_export(
        self,
        decision_ids: list[UUID],
        format: str,
        include_history: bool = False,
    ) -> None:
        """Log an export event for multiple decisions."""
        await self.session.execute(
            text("""
                SELECT log_decision_export(
                    :decision_ids,
                    :format,
                    :include_history
                )
            """),
            {
                "decision_ids": decision_ids,
                "format": format,
                "include_history": include_history,
            },
        )

    async def get_audit_log(
        self,
        organization_id: UUID,
        user_id: UUID | None = None,
        action: AuditAction | None = None,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[AuditLog], int]:
        """Query the audit log with filters."""
        query = select(AuditLog).where(AuditLog.organization_id == organization_id)

        if user_id:
            query = query.where(AuditLog.user_id == user_id)
        if action:
            query = query.where(AuditLog.action == action)
        if resource_type:
            query = query.where(AuditLog.resource_type == resource_type)
        if resource_id:
            query = query.where(AuditLog.resource_id == resource_id)
        if start_date:
            query = query.where(AuditLog.created_at >= start_date)
        if end_date:
            query = query.where(AuditLog.created_at <= end_date)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(count_query)).scalar_one()

        # Get results
        query = query.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(query)

        return result.scalars().all(), total

    async def get_decision_access_report(
        self,
        decision_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Any]:
        """Generate an access report for a specific decision."""
        query = select(AuditLog).where(
            AuditLog.resource_type == "decision",
            AuditLog.resource_id == decision_id,
            AuditLog.action == AuditAction.READ,
        )

        if start_date:
            query = query.where(AuditLog.created_at >= start_date)
        if end_date:
            query = query.where(AuditLog.created_at <= end_date)

        result = await self.session.execute(query.order_by(AuditLog.created_at.desc()))
        entries = result.scalars().all()

        unique_users = set(e.user_id for e in entries if e.user_id)

        return {
            "decision_id": decision_id,
            "total_reads": len(entries),
            "unique_users": len(unique_users),
            "first_access": entries[-1].created_at if entries else None,
            "last_access": entries[0].created_at if entries else None,
            "accesses": entries,
        }

    async def verify_chain_integrity(
        self,
        organization_id: UUID,
    ) -> dict[str, Any]:
        """Verify the cryptographic chain of audit entries."""
        result = await self.session.execute(
            text("SELECT * FROM verify_audit_chain(:org_id)"),
            {"org_id": organization_id},
        )
        row = result.fetchone()

        return {
            "is_valid": row[0],
            "broken_at_id": row[1],
            "expected_hash": row[2],
            "actual_hash": row[3],
            "verified_at": datetime.now(),
        }

    async def get_audit_summary(
        self,
        organization_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """Get a summary of audit activity for a period."""
        # Actions by type
        actions_query = text("""
            SELECT action, resource_type, COUNT(*) as count
            FROM audit_log
            WHERE organization_id = :org_id
              AND created_at BETWEEN :start_date AND :end_date
            GROUP BY action, resource_type
            ORDER BY count DESC
        """)
        actions_result = await self.session.execute(
            actions_query,
            {"org_id": organization_id, "start_date": start_date, "end_date": end_date},
        )

        # Top users
        users_query = text("""
            SELECT user_id, COUNT(*) as count
            FROM audit_log
            WHERE organization_id = :org_id
              AND created_at BETWEEN :start_date AND :end_date
              AND user_id IS NOT NULL
            GROUP BY user_id
            ORDER BY count DESC
            LIMIT 10
        """)
        users_result = await self.session.execute(
            users_query,
            {"org_id": organization_id, "start_date": start_date, "end_date": end_date},
        )

        # Total count
        total_query = select(func.count()).where(
            AuditLog.organization_id == organization_id,
            AuditLog.created_at.between(start_date, end_date),
        )
        total = (await self.session.execute(total_query)).scalar_one()

        return {
            "organization_id": organization_id,
            "period_start": start_date,
            "period_end": end_date,
            "total_events": total,
            "actions_by_type": [
                {"action": r[0], "resource_type": r[1], "count": r[2]}
                for r in actions_result.fetchall()
            ],
            "top_users": [
                {"user_id": r[0], "count": r[1]} for r in users_result.fetchall()
            ],
        }
