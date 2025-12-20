"""
Ledger Engine: Core immutable decision management logic.

This module implements the "no overwrite" principle:
- Decisions are NEVER updated in place
- Every change creates a new DecisionVersion
- All operations are fully transactional
- Complete audit trail for every action
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence
from uuid import UUID

from sqlalchemy import func, select, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.security import hash_content
from ..models import (
    Approval,
    ApprovalStatus,
    AuditLog,
    AuditAction,
    Decision,
    DecisionRelationship,
    DecisionStatus,
    DecisionVersion,
    ImpactLevel,
    RelationshipType,
    RequiredReviewer,
    User,
)


# =============================================================================
# EXCEPTIONS
# =============================================================================


class LedgerError(Exception):
    """Base exception for ledger operations."""
    pass


class DecisionNotFoundError(LedgerError):
    """Decision does not exist."""
    pass


class VersionNotFoundError(LedgerError):
    """Specific version does not exist."""
    pass


class InvalidOperationError(LedgerError):
    """Operation not allowed in current state."""
    pass


class ConcurrencyError(LedgerError):
    """Concurrent modification detected."""
    pass


# =============================================================================
# DATA TRANSFER OBJECTS
# =============================================================================


@dataclass
class DecisionContentDTO:
    """Content structure for a decision."""
    context: str
    choice: str
    rationale: str
    alternatives: list[dict]  # [{"name": str, "rejected_reason": str}]
    consequences: str | None = None
    review_date: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "context": self.context,
            "choice": self.choice,
            "rationale": self.rationale,
            "alternatives": self.alternatives,
            "consequences": self.consequences,
            "review_date": self.review_date.isoformat() if self.review_date else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DecisionContentDTO":
        return cls(
            context=data.get("context", ""),
            choice=data.get("choice", ""),
            rationale=data.get("rationale", ""),
            alternatives=data.get("alternatives", []),
            consequences=data.get("consequences"),
            review_date=datetime.fromisoformat(data["review_date"]) if data.get("review_date") else None,
        )


@dataclass
class CreateDecisionInput:
    """Input for creating a new decision."""
    title: str
    content: DecisionContentDTO
    impact_level: ImpactLevel = ImpactLevel.MEDIUM
    tags: list[str] | None = None
    owner_team_id: UUID | None = None
    reviewer_ids: list[UUID] | None = None


@dataclass
class AmendDecisionInput:
    """Input for amending a decision (creating new version)."""
    title: str
    content: DecisionContentDTO
    impact_level: ImpactLevel
    tags: list[str] | None = None
    change_summary: str = ""  # Required: what changed?
    expected_version: int | None = None  # Optimistic locking


@dataclass
class SupersedeInput:
    """Input for superseding a decision."""
    new_decision_id: UUID
    reason: str | None = None


@dataclass
class VersionInfo:
    """Summary of a version for responses."""
    id: UUID
    version_number: int
    title: str
    impact_level: ImpactLevel
    content_hash: str
    created_by_id: UUID
    created_by_name: str
    created_at: datetime
    change_summary: str | None


@dataclass
class DecisionWithVersion:
    """Decision with its current or requested version."""
    decision: Decision
    version: DecisionVersion
    version_count: int
    is_current: bool


# =============================================================================
# LEDGER ENGINE
# =============================================================================


class LedgerEngine:
    """
    Core engine for immutable decision management.

    Guarantees:
    1. DecisionVersions are NEVER updated after creation
    2. All mutations create new versions (append-only)
    3. Operations are atomic (all-or-nothing)
    4. Full audit trail for every action
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    # =========================================================================
    # CREATE DECISION
    # =========================================================================

    async def create_decision(
        self,
        input: CreateDecisionInput,
        organization_id: UUID,
        author_id: UUID,
    ) -> DecisionWithVersion:
        """
        Create a new decision with its first version (v1).

        Flow:
        1. Generate next decision number for org
        2. Create Decision (anchor row)
        3. Create DecisionVersion v1 with content
        4. Link Decision.current_version_id -> v1
        5. Add required reviewers (if any)
        6. Log audit event

        All steps are atomic - failure rolls back everything.
        """
        try:
            # Step 1: Get next decision number (atomic with FOR UPDATE would be ideal)
            next_number = await self._get_next_decision_number(organization_id)

            # Step 2: Create the Decision anchor
            decision = Decision(
                organization_id=organization_id,
                decision_number=next_number,
                status=DecisionStatus.DRAFT,
                owner_team_id=input.owner_team_id,
                created_by=author_id,
            )
            self._session.add(decision)
            await self._session.flush()  # Get the ID

            # Step 3: Create version 1
            version = await self._create_version_internal(
                decision_id=decision.id,
                version_number=1,
                title=input.title,
                impact_level=input.impact_level,
                content=input.content,
                tags=input.tags or [],
                author_id=author_id,
                change_summary="Initial version",
            )

            # Step 4: Point decision to current version
            decision.current_version_id = version.id

            # Step 5: Add reviewers
            if input.reviewer_ids:
                for reviewer_id in input.reviewer_ids:
                    reviewer = RequiredReviewer(
                        decision_version_id=version.id,
                        user_id=reviewer_id,
                        added_by=author_id,
                    )
                    self._session.add(reviewer)

            # Step 6: Audit log
            await self._log_audit(
                organization_id=organization_id,
                user_id=author_id,
                action=AuditAction.CREATE,
                resource_type="decision",
                resource_id=decision.id,
                details={
                    "decision_number": next_number,
                    "title": input.title,
                    "version": 1,
                },
            )

            await self._session.flush()

            return DecisionWithVersion(
                decision=decision,
                version=version,
                version_count=1,
                is_current=True,
            )

        except IntegrityError as e:
            # Handle race condition on decision_number
            raise ConcurrencyError(f"Failed to create decision: {e}")

    # =========================================================================
    # AMEND DECISION (THE "NO OVERWRITE" RULE)
    # =========================================================================

    async def amend_decision(
        self,
        decision_id: UUID,
        input: AmendDecisionInput,
        author_id: UUID,
    ) -> DecisionWithVersion:
        """
        Amend a decision by creating a NEW version.

        CRITICAL: This method NEVER runs UPDATE on content columns.

        Flow:
        1. Fetch decision (verify exists, not deleted)
        2. Verify state allows amendments
        3. Optimistic lock check (if expected_version provided)
        4. Get current max version number
        5. INSERT new DecisionVersion row (v+1)
        6. UPDATE Decision.current_version_id pointer only
        7. Log audit event

        Transactional guarantee: If step 5 or 6 fails, nothing changes.
        """
        # Step 1: Fetch decision
        decision = await self._get_decision_or_raise(decision_id)

        # Step 2: Verify state
        if decision.status == DecisionStatus.SUPERSEDED:
            raise InvalidOperationError(
                "Cannot amend a superseded decision. Create a new decision instead."
            )

        # Step 3: Optimistic locking
        current_version_number = await self._get_current_version_number(decision_id)

        if input.expected_version is not None:
            if current_version_number != input.expected_version:
                raise ConcurrencyError(
                    f"Version mismatch: expected v{input.expected_version}, "
                    f"but current is v{current_version_number}. "
                    "The decision was modified by another user."
                )

        # Step 4: Next version number
        new_version_number = current_version_number + 1

        # Step 5: INSERT new version (NEVER UPDATE existing versions)
        new_version = await self._create_version_internal(
            decision_id=decision_id,
            version_number=new_version_number,
            title=input.title,
            impact_level=input.impact_level,
            content=input.content,
            tags=input.tags or [],
            author_id=author_id,
            change_summary=input.change_summary,
        )

        # Step 6: UPDATE only the pointer (this is the ONLY update allowed)
        decision.current_version_id = new_version.id

        # If the decision was approved and we're amending, it needs re-review
        if decision.status == DecisionStatus.APPROVED:
            decision.status = DecisionStatus.DRAFT

        # Step 7: Audit log
        await self._log_audit(
            organization_id=decision.organization_id,
            user_id=author_id,
            action=AuditAction.UPDATE,
            resource_type="decision",
            resource_id=decision_id,
            details={
                "previous_version": current_version_number,
                "new_version": new_version_number,
                "change_summary": input.change_summary,
            },
        )

        await self._session.flush()

        return DecisionWithVersion(
            decision=decision,
            version=new_version,
            version_count=new_version_number,
            is_current=True,
        )

    # =========================================================================
    # SUPERSEDE DECISION
    # =========================================================================

    async def supersede_decision(
        self,
        old_decision_id: UUID,
        input: SupersedeInput,
        author_id: UUID,
    ) -> tuple[Decision, Decision, DecisionRelationship]:
        """
        Mark a decision as superseded by another.

        Flow:
        1. Verify old decision exists and is not already superseded
        2. Verify new decision exists
        3. Create supersedes relationship
        4. Mark old decision status as SUPERSEDED
        5. Log audit events for both decisions

        Returns: (old_decision, new_decision, relationship)
        """
        # Step 1: Get old decision
        old_decision = await self._get_decision_or_raise(old_decision_id)

        if old_decision.status == DecisionStatus.SUPERSEDED:
            raise InvalidOperationError(
                f"Decision {old_decision.decision_number} is already superseded"
            )

        # Step 2: Get new decision
        new_decision = await self._get_decision_or_raise(input.new_decision_id)

        if new_decision.id == old_decision_id:
            raise InvalidOperationError("A decision cannot supersede itself")

        if new_decision.organization_id != old_decision.organization_id:
            raise InvalidOperationError(
                "Cannot supersede a decision from a different organization"
            )

        # Step 3: Create relationship
        relationship = DecisionRelationship(
            source_decision_id=input.new_decision_id,  # New supersedes Old
            target_decision_id=old_decision_id,
            relationship_type=RelationshipType.SUPERSEDES,
            description=input.reason,
            created_by=author_id,
        )
        self._session.add(relationship)

        # Step 4: Update old decision status
        old_decision.status = DecisionStatus.SUPERSEDED

        # Step 5: Audit logs
        await self._log_audit(
            organization_id=old_decision.organization_id,
            user_id=author_id,
            action=AuditAction.SUPERSEDE,
            resource_type="decision",
            resource_id=old_decision_id,
            details={
                "superseded_by": str(input.new_decision_id),
                "superseded_by_number": new_decision.decision_number,
                "reason": input.reason,
            },
        )

        await self._session.flush()

        return old_decision, new_decision, relationship

    # =========================================================================
    # TIME TRAVEL FETCH
    # =========================================================================

    async def get_decision(
        self,
        decision_id: UUID,
        version: int | None = None,
        include_all_versions: bool = False,
    ) -> DecisionWithVersion:
        """
        Get a decision, optionally at a specific version (time travel).

        Args:
            decision_id: The decision UUID
            version: Specific version number (None = current/latest)
            include_all_versions: Whether to load all versions

        Returns:
            DecisionWithVersion with the requested version
        """
        # Build query
        query = select(Decision).where(
            Decision.id == decision_id,
            Decision.deleted_at.is_(None),
        )

        if include_all_versions:
            query = query.options(
                selectinload(Decision.versions).selectinload(DecisionVersion.creator),
                selectinload(Decision.current_version),
                selectinload(Decision.owner_team),
                selectinload(Decision.creator),
            )
        else:
            query = query.options(
                selectinload(Decision.current_version).selectinload(DecisionVersion.creator),
                selectinload(Decision.owner_team),
                selectinload(Decision.creator),
            )

        result = await self._session.execute(query)
        decision = result.scalar_one_or_none()

        if not decision:
            raise DecisionNotFoundError(f"Decision {decision_id} not found")

        # Get version count
        count_result = await self._session.execute(
            select(func.count()).where(DecisionVersion.decision_id == decision_id)
        )
        version_count = count_result.scalar_one()

        # Determine which version to return
        if version is None:
            # Return current version
            return DecisionWithVersion(
                decision=decision,
                version=decision.current_version,
                version_count=version_count,
                is_current=True,
            )
        else:
            # Time travel: fetch specific version
            version_query = select(DecisionVersion).where(
                DecisionVersion.decision_id == decision_id,
                DecisionVersion.version_number == version,
            ).options(selectinload(DecisionVersion.creator))

            version_result = await self._session.execute(version_query)
            specific_version = version_result.scalar_one_or_none()

            if not specific_version:
                raise VersionNotFoundError(
                    f"Version {version} not found for decision {decision_id}"
                )

            is_current = (decision.current_version_id == specific_version.id)

            return DecisionWithVersion(
                decision=decision,
                version=specific_version,
                version_count=version_count,
                is_current=is_current,
            )

    async def get_version_history(
        self,
        decision_id: UUID,
    ) -> list[VersionInfo]:
        """Get all versions of a decision with metadata."""
        query = (
            select(DecisionVersion, User.name)
            .join(User, DecisionVersion.created_by == User.id)
            .where(DecisionVersion.decision_id == decision_id)
            .order_by(DecisionVersion.version_number.desc())
        )

        result = await self._session.execute(query)
        rows = result.all()

        return [
            VersionInfo(
                id=v.id,
                version_number=v.version_number,
                title=v.title,
                impact_level=v.impact_level,
                content_hash=v.content_hash or "",
                created_by_id=v.created_by,
                created_by_name=name,
                created_at=v.created_at,
                change_summary=v.change_summary,
            )
            for v, name in rows
        ]

    async def compare_versions(
        self,
        decision_id: UUID,
        version_a: int,
        version_b: int,
    ) -> dict:
        """Compare two versions of a decision."""
        v_a = await self._get_version(decision_id, version_a)
        v_b = await self._get_version(decision_id, version_b)

        return {
            "version_a": {
                "number": v_a.version_number,
                "title": v_a.title,
                "content": v_a.content,
                "tags": v_a.tags,
                "created_at": v_a.created_at.isoformat(),
            },
            "version_b": {
                "number": v_b.version_number,
                "title": v_b.title,
                "content": v_b.content,
                "tags": v_b.tags,
                "created_at": v_b.created_at.isoformat(),
            },
            "changes": {
                "title_changed": v_a.title != v_b.title,
                "content_changed": v_a.content != v_b.content,
                "tags_changed": set(v_a.tags or []) != set(v_b.tags or []),
            },
        }

    # =========================================================================
    # INTERNAL HELPERS
    # =========================================================================

    async def _get_next_decision_number(self, organization_id: UUID) -> int:
        """Get the next decision number for an organization."""
        result = await self._session.execute(
            select(func.coalesce(func.max(Decision.decision_number), 0) + 1).where(
                Decision.organization_id == organization_id
            )
        )
        return result.scalar_one()

    async def _get_current_version_number(self, decision_id: UUID) -> int:
        """Get the current (max) version number for a decision."""
        result = await self._session.execute(
            select(func.coalesce(func.max(DecisionVersion.version_number), 0)).where(
                DecisionVersion.decision_id == decision_id
            )
        )
        return result.scalar_one()

    async def _get_decision_or_raise(self, decision_id: UUID) -> Decision:
        """Get a decision or raise DecisionNotFoundError."""
        query = select(Decision).where(
            Decision.id == decision_id,
            Decision.deleted_at.is_(None),
        ).options(
            selectinload(Decision.current_version),
            selectinload(Decision.creator),
        )
        result = await self._session.execute(query)
        decision = result.scalar_one_or_none()

        if not decision:
            raise DecisionNotFoundError(f"Decision {decision_id} not found")

        return decision

    async def _get_version(self, decision_id: UUID, version_number: int) -> DecisionVersion:
        """Get a specific version or raise VersionNotFoundError."""
        query = select(DecisionVersion).where(
            DecisionVersion.decision_id == decision_id,
            DecisionVersion.version_number == version_number,
        )
        result = await self._session.execute(query)
        version = result.scalar_one_or_none()

        if not version:
            raise VersionNotFoundError(
                f"Version {version_number} not found for decision {decision_id}"
            )

        return version

    async def _create_version_internal(
        self,
        decision_id: UUID,
        version_number: int,
        title: str,
        impact_level: ImpactLevel,
        content: DecisionContentDTO,
        tags: list[str],
        author_id: UUID,
        change_summary: str,
    ) -> DecisionVersion:
        """
        Create a new version (internal, called by create and amend).

        This is an INSERT-only operation. No existing rows are modified.
        """
        # Serialize content
        content_dict = content.to_dict()
        content_json = json.dumps(content_dict, sort_keys=True)

        # Calculate content hash for integrity verification
        hash_input = f"{title}|{content_json}|{','.join(sorted(tags))}"
        content_hash = hash_content(hash_input)

        version = DecisionVersion(
            decision_id=decision_id,
            version_number=version_number,
            title=title,
            impact_level=impact_level,
            content=content_dict,
            tags=tags,
            custom_fields={},
            created_by=author_id,
            change_summary=change_summary,
            content_hash=content_hash,
        )
        self._session.add(version)
        await self._session.flush()

        return version

    async def _log_audit(
        self,
        organization_id: UUID,
        user_id: UUID,
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
        # Don't flush here - let it be part of the transaction
