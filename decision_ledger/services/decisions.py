"""Decision service: core business logic for decision management."""

import json
from typing import Sequence
from uuid import UUID

from sqlalchemy import and_, func, not_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.security import hash_content
from ..models import (
    Approval,
    ApprovalStatus,
    Decision,
    DecisionRelationship,
    DecisionStatus,
    DecisionVersion,
    ImpactLevel,
    RelationshipType,
    RequiredReviewer,
    User,
)
from ..schemas import (
    ApprovalCreate,
    DecisionContent,
    DecisionCreate,
    DecisionSearchParams,
    DecisionUpdate,
    RelationshipCreate,
)


class DecisionService:
    """Service for managing decisions and their versions."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # =========================================================================
    # DECISION CRUD
    # =========================================================================

    async def create_decision(
        self,
        data: DecisionCreate,
        organization_id: UUID,
        user_id: UUID,
    ) -> Decision:
        """Create a new decision with its initial version."""
        # Get next decision number for this org
        result = await self.session.execute(
            select(func.coalesce(func.max(Decision.decision_number), 0) + 1).where(
                Decision.organization_id == organization_id
            )
        )
        next_number = result.scalar_one()

        # Create decision
        decision = Decision(
            organization_id=organization_id,
            decision_number=next_number,
            status=DecisionStatus.DRAFT,
            owner_team_id=data.owner_team_id,
            created_by=user_id,
        )
        self.session.add(decision)
        await self.session.flush()  # Get the decision ID

        # Create initial version
        version = await self._create_version(
            decision_id=decision.id,
            title=data.title,
            impact_level=data.impact_level,
            content=data.content,
            tags=data.tags,
            custom_fields=data.custom_fields,
            user_id=user_id,
            version_number=1,
        )

        # Update decision to point to current version
        decision.current_version_id = version.id

        # Add required reviewers
        for reviewer_id in data.reviewer_ids:
            reviewer = RequiredReviewer(
                decision_version_id=version.id,
                user_id=reviewer_id,
                added_by=user_id,
            )
            self.session.add(reviewer)

        await self.session.flush()
        return decision

    async def get_decision(
        self,
        decision_id: UUID,
        organization_id: UUID | None = None,
        include_versions: bool = False,
    ) -> Decision | None:
        """Get a decision by ID.

        SECURITY: If organization_id is provided, enforces tenant isolation.
        Always pass organization_id from authenticated context to prevent data leaks.
        """
        conditions = [
            Decision.id == decision_id,
            Decision.deleted_at.is_(None),
        ]

        # CRITICAL: Enforce tenant isolation when org_id is provided
        if organization_id is not None:
            conditions.append(Decision.organization_id == organization_id)

        query = select(Decision).where(*conditions)

        if include_versions:
            query = query.options(
                selectinload(Decision.versions),
                selectinload(Decision.current_version),
                selectinload(Decision.owner_team),
                selectinload(Decision.creator),
            )
        else:
            query = query.options(
                selectinload(Decision.current_version),
                selectinload(Decision.owner_team),
                selectinload(Decision.creator),
            )

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_decision_by_number(
        self,
        organization_id: UUID,
        decision_number: int,
    ) -> Decision | None:
        """Get a decision by its org-scoped number."""
        query = (
            select(Decision)
            .where(
                Decision.organization_id == organization_id,
                Decision.decision_number == decision_number,
                Decision.deleted_at.is_(None),
            )
            .options(
                selectinload(Decision.current_version),
                selectinload(Decision.owner_team),
                selectinload(Decision.creator),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def update_decision(
        self,
        decision_id: UUID,
        data: DecisionUpdate,
        user_id: UUID,
        organization_id: UUID | None = None,
    ) -> DecisionVersion:
        """Update a decision by creating a new version."""
        # SECURITY: Pass org_id for tenant isolation
        decision = await self.get_decision(decision_id, organization_id=organization_id)
        if not decision:
            raise ValueError("Decision not found")

        # Get next version number
        result = await self.session.execute(
            select(func.max(DecisionVersion.version_number)).where(
                DecisionVersion.decision_id == decision_id
            )
        )
        current_version = result.scalar_one() or 0

        # Create new version
        version = await self._create_version(
            decision_id=decision_id,
            title=data.title,
            impact_level=data.impact_level,
            content=data.content,
            tags=data.tags,
            custom_fields=data.custom_fields,
            user_id=user_id,
            version_number=current_version + 1,
            change_summary=data.change_summary,
        )

        # Update decision pointer
        decision.current_version_id = version.id

        # Add new reviewers if specified
        if data.reviewer_ids is not None:
            for reviewer_id in data.reviewer_ids:
                reviewer = RequiredReviewer(
                    decision_version_id=version.id,
                    user_id=reviewer_id,
                    added_by=user_id,
                )
                self.session.add(reviewer)

        await self.session.flush()
        return version

    async def _create_version(
        self,
        decision_id: UUID,
        title: str,
        impact_level: ImpactLevel,
        content: DecisionContent,
        tags: list[str],
        custom_fields: dict,
        user_id: UUID,
        version_number: int,
        change_summary: str | None = None,
    ) -> DecisionVersion:
        """Create a new decision version (internal helper)."""
        # Serialize content and calculate hash
        content_dict = content.model_dump()
        content_json = json.dumps(content_dict, sort_keys=True)
        content_hash = hash_content(f"{title}{content_json}{','.join(sorted(tags))}")

        version = DecisionVersion(
            decision_id=decision_id,
            version_number=version_number,
            title=title,
            impact_level=impact_level,
            content=content_dict,
            tags=tags,
            custom_fields=custom_fields,
            created_by=user_id,
            change_summary=change_summary,
            content_hash=content_hash,
        )
        self.session.add(version)
        await self.session.flush()
        return version

    async def soft_delete_decision(
        self,
        decision_id: UUID,
    ) -> None:
        """Soft-delete a decision."""
        decision = await self.get_decision(decision_id)
        if decision:
            decision.soft_delete()
            await self.session.flush()

    # =========================================================================
    # DECISION LISTING & SEARCH
    # =========================================================================

    async def list_current_decisions(
        self,
        organization_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[Sequence[Decision], int]:
        """List all current (non-superseded) decisions."""
        # Base query for current decisions
        base_query = (
            select(Decision)
            .where(
                Decision.organization_id == organization_id,
                Decision.deleted_at.is_(None),
                not_(Decision.status.in_([DecisionStatus.SUPERSEDED, DecisionStatus.DEPRECATED])),
            )
            # Exclude decisions that have been superseded
            .where(
                not_(
                    Decision.id.in_(
                        select(DecisionRelationship.target_decision_id).where(
                            DecisionRelationship.relationship_type == RelationshipType.SUPERSEDES,
                            DecisionRelationship.invalidated_at.is_(None),
                        )
                    )
                )
            )
        )

        # Count total
        count_query = select(func.count()).select_from(base_query.subquery())
        total = (await self.session.execute(count_query)).scalar_one()

        # Get paginated results
        query = (
            base_query.options(
                selectinload(Decision.current_version),
                selectinload(Decision.owner_team),
                selectinload(Decision.creator),
            )
            .order_by(Decision.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(query)
        return result.scalars().all(), total

    async def search_decisions(
        self,
        organization_id: UUID,
        params: DecisionSearchParams,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[Sequence[Decision], int]:
        """Search decisions with filters."""
        query = select(Decision).where(
            Decision.organization_id == organization_id,
            Decision.deleted_at.is_(None),
        )

        # Apply filters
        if params.status:
            query = query.where(Decision.status.in_(params.status))
        elif not params.include_superseded:
            query = query.where(Decision.status != DecisionStatus.SUPERSEDED)

        if not params.include_deprecated:
            query = query.where(Decision.status != DecisionStatus.DEPRECATED)

        if params.owner_team_id:
            query = query.where(Decision.owner_team_id == params.owner_team_id)

        if params.created_by_id:
            query = query.where(Decision.created_by == params.created_by_id)

        if params.created_after:
            query = query.where(Decision.created_at >= params.created_after)

        if params.created_before:
            query = query.where(Decision.created_at <= params.created_before)

        # Join with current version for content filters
        query = query.join(
            DecisionVersion,
            Decision.current_version_id == DecisionVersion.id,
        )

        if params.impact_level:
            query = query.where(DecisionVersion.impact_level.in_(params.impact_level))

        if params.tags:
            query = query.where(DecisionVersion.tags.overlap(params.tags))

        if params.query:
            # Full-text search on title and content
            search_vector = func.to_tsvector(
                "english",
                DecisionVersion.title + " " + func.coalesce(
                    DecisionVersion.content["context"].astext, ""
                ),
            )
            search_query = func.plainto_tsquery("english", params.query)
            query = query.where(search_vector.op("@@")(search_query))

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(count_query)).scalar_one()

        # Get results
        query = (
            query.options(
                selectinload(Decision.current_version),
                selectinload(Decision.owner_team),
                selectinload(Decision.creator),
            )
            .order_by(Decision.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(query)
        return result.scalars().all(), total

    # =========================================================================
    # STATUS MANAGEMENT
    # =========================================================================

    async def submit_for_review(self, decision_id: UUID, organization_id: UUID | None = None) -> Decision:
        """Submit a draft decision for review."""
        # SECURITY: Pass org_id for tenant isolation
        decision = await self.get_decision(decision_id, organization_id=organization_id)
        if not decision:
            raise ValueError("Decision not found")

        if decision.status != DecisionStatus.DRAFT:
            raise ValueError("Only draft decisions can be submitted for review")

        decision.status = DecisionStatus.PENDING_REVIEW
        await self.session.flush()
        return decision

    async def deprecate_decision(self, decision_id: UUID, organization_id: UUID | None = None) -> Decision:
        """Deprecate a decision."""
        # SECURITY: Pass org_id for tenant isolation
        decision = await self.get_decision(decision_id, organization_id=organization_id)
        if not decision:
            raise ValueError("Decision not found")

        if decision.status == DecisionStatus.SUPERSEDED:
            raise ValueError("Cannot deprecate a superseded decision")

        decision.status = DecisionStatus.DEPRECATED
        await self.session.flush()
        return decision

    # =========================================================================
    # RELATIONSHIPS
    # =========================================================================

    async def create_relationship(
        self,
        source_decision_id: UUID,
        data: RelationshipCreate,
        user_id: UUID,
    ) -> DecisionRelationship:
        """Create a relationship between two decisions."""
        relationship = DecisionRelationship(
            source_decision_id=source_decision_id,
            target_decision_id=data.target_decision_id,
            relationship_type=data.relationship_type,
            description=data.description,
            created_by=user_id,
        )
        self.session.add(relationship)

        # If this is a supersedes relationship, update the target decision status
        if data.relationship_type == RelationshipType.SUPERSEDES:
            target = await self.get_decision(data.target_decision_id)
            if target:
                target.status = DecisionStatus.SUPERSEDED

        await self.session.flush()
        return relationship

    async def supersede_decision(
        self,
        new_decision_id: UUID,
        old_decision_id: UUID,
        user_id: UUID,
        description: str | None = None,
    ) -> DecisionRelationship:
        """Mark a decision as superseding another."""
        return await self.create_relationship(
            source_decision_id=new_decision_id,
            data=RelationshipCreate(
                target_decision_id=old_decision_id,
                relationship_type=RelationshipType.SUPERSEDES,
                description=description,
            ),
            user_id=user_id,
        )

    async def get_current_decision(self, decision_id: UUID) -> UUID:
        """Get the current (non-superseded) version of a decision chain."""
        # Use the database function for efficiency
        result = await self.session.execute(
            text("SELECT get_current_decision(:decision_id)"),
            {"decision_id": decision_id},
        )
        return result.scalar_one()

    async def get_decision_lineage(
        self,
        decision_id: UUID,
    ) -> list[Decision]:
        """Get the full supersession chain for a decision."""
        # Get predecessors (what this decision superseded)
        predecessors_query = text("""
            WITH RECURSIVE lineage AS (
                SELECT target_decision_id AS id, 1 AS depth
                FROM decision_relationships
                WHERE source_decision_id = :decision_id
                  AND relationship_type = 'supersedes'
                  AND invalidated_at IS NULL

                UNION ALL

                SELECT dr.target_decision_id, l.depth + 1
                FROM lineage l
                JOIN decision_relationships dr ON dr.source_decision_id = l.id
                WHERE dr.relationship_type = 'supersedes'
                  AND dr.invalidated_at IS NULL
                  AND l.depth < 100
            )
            SELECT id FROM lineage ORDER BY depth DESC
        """)

        result = await self.session.execute(
            predecessors_query, {"decision_id": decision_id}
        )
        predecessor_ids = [row[0] for row in result.fetchall()]

        if not predecessor_ids:
            return []

        # Fetch the actual decisions
        query = (
            select(Decision)
            .where(Decision.id.in_(predecessor_ids))
            .options(selectinload(Decision.current_version))
        )
        result = await self.session.execute(query)
        decisions = {d.id: d for d in result.scalars().all()}

        # Return in order
        return [decisions[id] for id in predecessor_ids if id in decisions]

    # =========================================================================
    # APPROVALS
    # =========================================================================

    async def add_approval(
        self,
        version_id: UUID,
        user_id: UUID,
        data: ApprovalCreate,
    ) -> Approval:
        """Add an approval to a decision version."""
        approval = Approval(
            decision_version_id=version_id,
            user_id=user_id,
            status=data.status,
            comment=data.comment,
        )
        self.session.add(approval)
        await self.session.flush()

        # Check if all required approvals are in
        await self._check_approval_complete(version_id)

        return approval

    async def _check_approval_complete(self, version_id: UUID) -> None:
        """Check if a version has all required approvals."""
        # Get version and its decision
        version_query = select(DecisionVersion).where(
            DecisionVersion.id == version_id
        )
        result = await self.session.execute(version_query)
        version = result.scalar_one_or_none()
        if not version:
            return

        # Count required vs actual approvals
        required_count = await self.session.execute(
            select(func.count()).where(
                RequiredReviewer.decision_version_id == version_id
            )
        )
        required = required_count.scalar_one()

        approved_count = await self.session.execute(
            select(func.count()).where(
                Approval.decision_version_id == version_id,
                Approval.status == ApprovalStatus.APPROVED,
            )
        )
        approved = approved_count.scalar_one()

        # If all required reviewers approved, update decision status
        if required > 0 and approved >= required:
            decision_query = select(Decision).where(
                Decision.id == version.decision_id,
                Decision.status == DecisionStatus.PENDING_REVIEW,
            )
            result = await self.session.execute(decision_query)
            decision = result.scalar_one_or_none()
            if decision:
                decision.status = DecisionStatus.APPROVED
                await self.session.flush()

    async def get_pending_approvals(
        self,
        user_id: UUID,
        organization_id: UUID,
    ) -> Sequence[DecisionVersion]:
        """Get versions awaiting approval from a specific user."""
        query = (
            select(DecisionVersion)
            .join(RequiredReviewer)
            .join(Decision, DecisionVersion.decision_id == Decision.id)
            .where(
                RequiredReviewer.user_id == user_id,
                Decision.organization_id == organization_id,
                Decision.status == DecisionStatus.PENDING_REVIEW,
                Decision.deleted_at.is_(None),
            )
            .where(
                not_(
                    DecisionVersion.id.in_(
                        select(Approval.decision_version_id).where(
                            Approval.user_id == user_id
                        )
                    )
                )
            )
            .options(
                selectinload(DecisionVersion.decision),
                selectinload(DecisionVersion.creator),
            )
        )

        result = await self.session.execute(query)
        return result.scalars().all()
