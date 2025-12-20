"""
Tests for the Ledger Engine - Verifying Immutability Guarantees.

These tests verify:
1. CREATE: New decisions get v1
2. AMEND: Creates new version, never updates existing
3. SUPERSEDE: Marks old decision, creates relationship
4. TIME TRAVEL: Can fetch any historical version
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from decision_ledger.models import (
    Decision,
    DecisionVersion,
    DecisionRelationship,
    DecisionStatus,
    ImpactLevel,
    Organization,
    User,
)
from decision_ledger.services.ledger_engine import (
    LedgerEngine,
    CreateDecisionInput,
    AmendDecisionInput,
    SupersedeInput,
    DecisionContentDTO,
    DecisionNotFoundError,
    VersionNotFoundError,
    InvalidOperationError,
    ConcurrencyError,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_content() -> DecisionContentDTO:
    """Create sample decision content."""
    return DecisionContentDTO(
        context="We need to choose a database for the new service.",
        choice="We will use PostgreSQL.",
        rationale="PostgreSQL offers strong ACID compliance and JSONB support.",
        alternatives=[
            {"name": "MySQL", "rejected_reason": "Less robust JSON support"},
            {"name": "MongoDB", "rejected_reason": "Need ACID transactions"},
        ],
        consequences="Team needs PostgreSQL training.",
    )


@pytest.fixture
def updated_content() -> DecisionContentDTO:
    """Create updated decision content."""
    return DecisionContentDTO(
        context="We need to choose a database for the new service.",
        choice="We will use PostgreSQL with read replicas.",
        rationale="PostgreSQL offers strong ACID compliance. Read replicas improve performance.",
        alternatives=[
            {"name": "MySQL", "rejected_reason": "Less robust JSON support"},
            {"name": "MongoDB", "rejected_reason": "Need ACID transactions"},
            {"name": "CockroachDB", "rejected_reason": "Operational complexity"},
        ],
        consequences="Team needs PostgreSQL training. DevOps to set up replication.",
    )


# =============================================================================
# TEST: CREATE DECISION
# =============================================================================


class TestCreateDecision:
    """Tests for POST /decisions - Create Logic."""

    async def test_create_decision_creates_v1(
        self,
        session: AsyncSession,
        org_id: uuid4,
        user_id: uuid4,
        sample_content: DecisionContentDTO,
    ):
        """Creating a decision should create version 1."""
        engine = LedgerEngine(session)

        input_data = CreateDecisionInput(
            title="Database Selection",
            content=sample_content,
            impact_level=ImpactLevel.HIGH,
            tags=["infrastructure", "database"],
        )

        result = await engine.create_decision(
            input=input_data,
            organization_id=org_id,
            author_id=user_id,
        )

        # Verify decision was created
        assert result.decision is not None
        assert result.decision.status == DecisionStatus.DRAFT

        # Verify version 1 was created
        assert result.version is not None
        assert result.version.version_number == 1
        assert result.version.title == "Database Selection"
        assert result.version_count == 1
        assert result.is_current is True

    async def test_create_decision_generates_decision_number(
        self,
        session: AsyncSession,
        org_id: uuid4,
        user_id: uuid4,
        sample_content: DecisionContentDTO,
    ):
        """Each decision should get a sequential number within the org."""
        engine = LedgerEngine(session)

        # Create first decision
        result1 = await engine.create_decision(
            input=CreateDecisionInput(title="Decision 1", content=sample_content),
            organization_id=org_id,
            author_id=user_id,
        )

        # Create second decision
        result2 = await engine.create_decision(
            input=CreateDecisionInput(title="Decision 2", content=sample_content),
            organization_id=org_id,
            author_id=user_id,
        )

        assert result1.decision.decision_number == 1
        assert result2.decision.decision_number == 2

    async def test_create_decision_calculates_content_hash(
        self,
        session: AsyncSession,
        org_id: uuid4,
        user_id: uuid4,
        sample_content: DecisionContentDTO,
    ):
        """Content hash should be calculated for integrity verification."""
        engine = LedgerEngine(session)

        result = await engine.create_decision(
            input=CreateDecisionInput(title="Test", content=sample_content),
            organization_id=org_id,
            author_id=user_id,
        )

        assert result.version.content_hash is not None
        assert len(result.version.content_hash) == 64  # SHA-256 hex


# =============================================================================
# TEST: AMEND DECISION (THE "NO OVERWRITE" RULE)
# =============================================================================


class TestAmendDecision:
    """Tests for PUT /decisions/{id} - Amend Logic."""

    async def test_amend_creates_new_version(
        self,
        session: AsyncSession,
        org_id: uuid4,
        user_id: uuid4,
        sample_content: DecisionContentDTO,
        updated_content: DecisionContentDTO,
    ):
        """Amending should INSERT a new version, not UPDATE."""
        engine = LedgerEngine(session)

        # Create initial decision
        create_result = await engine.create_decision(
            input=CreateDecisionInput(title="Original Title", content=sample_content),
            organization_id=org_id,
            author_id=user_id,
        )
        decision_id = create_result.decision.id
        v1_id = create_result.version.id

        # Amend the decision
        amend_result = await engine.amend_decision(
            decision_id=decision_id,
            input=AmendDecisionInput(
                title="Updated Title",
                content=updated_content,
                impact_level=ImpactLevel.HIGH,
                change_summary="Added read replicas to the decision",
            ),
            author_id=user_id,
        )

        # Verify new version was created
        assert amend_result.version.version_number == 2
        assert amend_result.version.id != v1_id
        assert amend_result.version.title == "Updated Title"
        assert amend_result.version_count == 2

    async def test_amend_preserves_old_version(
        self,
        session: AsyncSession,
        org_id: uuid4,
        user_id: uuid4,
        sample_content: DecisionContentDTO,
        updated_content: DecisionContentDTO,
    ):
        """Old version should remain unchanged after amend."""
        engine = LedgerEngine(session)

        # Create and amend
        create_result = await engine.create_decision(
            input=CreateDecisionInput(title="Original", content=sample_content),
            organization_id=org_id,
            author_id=user_id,
        )
        decision_id = create_result.decision.id
        original_content_hash = create_result.version.content_hash

        await engine.amend_decision(
            decision_id=decision_id,
            input=AmendDecisionInput(
                title="Changed",
                content=updated_content,
                impact_level=ImpactLevel.HIGH,
                change_summary="Major update",
            ),
            author_id=user_id,
        )

        # Fetch v1 via time travel
        v1_result = await engine.get_decision(decision_id, version=1)

        # V1 should be unchanged
        assert v1_result.version.title == "Original"
        assert v1_result.version.content_hash == original_content_hash
        assert v1_result.is_current is False

    async def test_amend_updates_current_pointer(
        self,
        session: AsyncSession,
        org_id: uuid4,
        user_id: uuid4,
        sample_content: DecisionContentDTO,
        updated_content: DecisionContentDTO,
    ):
        """Decision.current_version_id should point to the new version."""
        engine = LedgerEngine(session)

        create_result = await engine.create_decision(
            input=CreateDecisionInput(title="Test", content=sample_content),
            organization_id=org_id,
            author_id=user_id,
        )
        decision_id = create_result.decision.id

        amend_result = await engine.amend_decision(
            decision_id=decision_id,
            input=AmendDecisionInput(
                title="Updated",
                content=updated_content,
                impact_level=ImpactLevel.MEDIUM,
                change_summary="Update",
            ),
            author_id=user_id,
        )

        # Verify the decision points to v2
        assert amend_result.decision.current_version_id == amend_result.version.id
        assert amend_result.is_current is True

    async def test_amend_with_optimistic_locking_success(
        self,
        session: AsyncSession,
        org_id: uuid4,
        user_id: uuid4,
        sample_content: DecisionContentDTO,
        updated_content: DecisionContentDTO,
    ):
        """Amend with correct expected_version should succeed."""
        engine = LedgerEngine(session)

        create_result = await engine.create_decision(
            input=CreateDecisionInput(title="Test", content=sample_content),
            organization_id=org_id,
            author_id=user_id,
        )

        # Amend with expected_version=1
        amend_result = await engine.amend_decision(
            decision_id=create_result.decision.id,
            input=AmendDecisionInput(
                title="Updated",
                content=updated_content,
                impact_level=ImpactLevel.MEDIUM,
                change_summary="Safe update",
                expected_version=1,  # We expect v1
            ),
            author_id=user_id,
        )

        assert amend_result.version.version_number == 2

    async def test_amend_with_optimistic_locking_conflict(
        self,
        session: AsyncSession,
        org_id: uuid4,
        user_id: uuid4,
        sample_content: DecisionContentDTO,
        updated_content: DecisionContentDTO,
    ):
        """Amend with wrong expected_version should raise ConcurrencyError."""
        engine = LedgerEngine(session)

        create_result = await engine.create_decision(
            input=CreateDecisionInput(title="Test", content=sample_content),
            organization_id=org_id,
            author_id=user_id,
        )

        # First amend succeeds
        await engine.amend_decision(
            decision_id=create_result.decision.id,
            input=AmendDecisionInput(
                title="V2",
                content=updated_content,
                impact_level=ImpactLevel.MEDIUM,
                change_summary="First update",
            ),
            author_id=user_id,
        )

        # Second amend with stale expected_version should fail
        with pytest.raises(ConcurrencyError) as exc_info:
            await engine.amend_decision(
                decision_id=create_result.decision.id,
                input=AmendDecisionInput(
                    title="V3 Conflict",
                    content=updated_content,
                    impact_level=ImpactLevel.MEDIUM,
                    change_summary="Stale update",
                    expected_version=1,  # Stale! Current is v2
                ),
                author_id=user_id,
            )

        assert "Version mismatch" in str(exc_info.value)

    async def test_cannot_amend_superseded_decision(
        self,
        session: AsyncSession,
        org_id: uuid4,
        user_id: uuid4,
        sample_content: DecisionContentDTO,
        updated_content: DecisionContentDTO,
    ):
        """Superseded decisions cannot be amended."""
        engine = LedgerEngine(session)

        # Create two decisions
        old_result = await engine.create_decision(
            input=CreateDecisionInput(title="Old", content=sample_content),
            organization_id=org_id,
            author_id=user_id,
        )
        new_result = await engine.create_decision(
            input=CreateDecisionInput(title="New", content=sample_content),
            organization_id=org_id,
            author_id=user_id,
        )

        # Supersede old with new
        await engine.supersede_decision(
            old_decision_id=old_result.decision.id,
            input=SupersedeInput(new_decision_id=new_result.decision.id),
            author_id=user_id,
        )

        # Try to amend the superseded decision
        with pytest.raises(InvalidOperationError) as exc_info:
            await engine.amend_decision(
                decision_id=old_result.decision.id,
                input=AmendDecisionInput(
                    title="Should Fail",
                    content=updated_content,
                    impact_level=ImpactLevel.MEDIUM,
                    change_summary="This should fail",
                ),
                author_id=user_id,
            )

        assert "superseded" in str(exc_info.value).lower()


# =============================================================================
# TEST: SUPERSEDE DECISION
# =============================================================================


class TestSupersedeDecision:
    """Tests for POST /decisions/{id}/supersede."""

    async def test_supersede_marks_old_as_superseded(
        self,
        session: AsyncSession,
        org_id: uuid4,
        user_id: uuid4,
        sample_content: DecisionContentDTO,
    ):
        """Superseding should mark the old decision's status."""
        engine = LedgerEngine(session)

        # Create two decisions
        old_result = await engine.create_decision(
            input=CreateDecisionInput(title="Old Decision", content=sample_content),
            organization_id=org_id,
            author_id=user_id,
        )
        new_result = await engine.create_decision(
            input=CreateDecisionInput(title="New Decision", content=sample_content),
            organization_id=org_id,
            author_id=user_id,
        )

        # Supersede
        old, new, relationship = await engine.supersede_decision(
            old_decision_id=old_result.decision.id,
            input=SupersedeInput(
                new_decision_id=new_result.decision.id,
                reason="Technology has evolved",
            ),
            author_id=user_id,
        )

        assert old.status == DecisionStatus.SUPERSEDED
        assert new.status == DecisionStatus.DRAFT  # New decision unchanged

    async def test_supersede_creates_relationship(
        self,
        session: AsyncSession,
        org_id: uuid4,
        user_id: uuid4,
        sample_content: DecisionContentDTO,
    ):
        """Superseding should create a relationship link."""
        engine = LedgerEngine(session)

        old_result = await engine.create_decision(
            input=CreateDecisionInput(title="Old", content=sample_content),
            organization_id=org_id,
            author_id=user_id,
        )
        new_result = await engine.create_decision(
            input=CreateDecisionInput(title="New", content=sample_content),
            organization_id=org_id,
            author_id=user_id,
        )

        old, new, relationship = await engine.supersede_decision(
            old_decision_id=old_result.decision.id,
            input=SupersedeInput(new_decision_id=new_result.decision.id),
            author_id=user_id,
        )

        assert relationship is not None
        assert relationship.source_decision_id == new.id
        assert relationship.target_decision_id == old.id
        assert relationship.relationship_type.value == "supersedes"

    async def test_cannot_supersede_already_superseded(
        self,
        session: AsyncSession,
        org_id: uuid4,
        user_id: uuid4,
        sample_content: DecisionContentDTO,
    ):
        """Cannot supersede a decision that's already superseded."""
        engine = LedgerEngine(session)

        # Create chain: A <- B <- C
        a = await engine.create_decision(
            input=CreateDecisionInput(title="A", content=sample_content),
            organization_id=org_id,
            author_id=user_id,
        )
        b = await engine.create_decision(
            input=CreateDecisionInput(title="B", content=sample_content),
            organization_id=org_id,
            author_id=user_id,
        )
        c = await engine.create_decision(
            input=CreateDecisionInput(title="C", content=sample_content),
            organization_id=org_id,
            author_id=user_id,
        )

        # B supersedes A
        await engine.supersede_decision(
            old_decision_id=a.decision.id,
            input=SupersedeInput(new_decision_id=b.decision.id),
            author_id=user_id,
        )

        # Try to have C also supersede A (already superseded)
        with pytest.raises(InvalidOperationError):
            await engine.supersede_decision(
                old_decision_id=a.decision.id,
                input=SupersedeInput(new_decision_id=c.decision.id),
                author_id=user_id,
            )

    async def test_cannot_supersede_self(
        self,
        session: AsyncSession,
        org_id: uuid4,
        user_id: uuid4,
        sample_content: DecisionContentDTO,
    ):
        """A decision cannot supersede itself."""
        engine = LedgerEngine(session)

        result = await engine.create_decision(
            input=CreateDecisionInput(title="Test", content=sample_content),
            organization_id=org_id,
            author_id=user_id,
        )

        with pytest.raises(InvalidOperationError):
            await engine.supersede_decision(
                old_decision_id=result.decision.id,
                input=SupersedeInput(new_decision_id=result.decision.id),
                author_id=user_id,
            )


# =============================================================================
# TEST: TIME TRAVEL FETCH
# =============================================================================


class TestTimeTravelFetch:
    """Tests for GET /decisions/{id}?version=N."""

    async def test_get_returns_current_by_default(
        self,
        session: AsyncSession,
        org_id: uuid4,
        user_id: uuid4,
        sample_content: DecisionContentDTO,
        updated_content: DecisionContentDTO,
    ):
        """Without version param, should return current version."""
        engine = LedgerEngine(session)

        create_result = await engine.create_decision(
            input=CreateDecisionInput(title="V1", content=sample_content),
            organization_id=org_id,
            author_id=user_id,
        )

        await engine.amend_decision(
            decision_id=create_result.decision.id,
            input=AmendDecisionInput(
                title="V2",
                content=updated_content,
                impact_level=ImpactLevel.MEDIUM,
                change_summary="Update",
            ),
            author_id=user_id,
        )

        # Get without version
        result = await engine.get_decision(create_result.decision.id)

        assert result.version.version_number == 2
        assert result.version.title == "V2"
        assert result.is_current is True

    async def test_get_specific_version(
        self,
        session: AsyncSession,
        org_id: uuid4,
        user_id: uuid4,
        sample_content: DecisionContentDTO,
        updated_content: DecisionContentDTO,
    ):
        """Can retrieve any historical version."""
        engine = LedgerEngine(session)

        create_result = await engine.create_decision(
            input=CreateDecisionInput(title="V1 Title", content=sample_content),
            organization_id=org_id,
            author_id=user_id,
        )

        await engine.amend_decision(
            decision_id=create_result.decision.id,
            input=AmendDecisionInput(
                title="V2 Title",
                content=updated_content,
                impact_level=ImpactLevel.MEDIUM,
                change_summary="Update",
            ),
            author_id=user_id,
        )

        # Time travel to v1
        v1_result = await engine.get_decision(
            create_result.decision.id,
            version=1,
        )

        assert v1_result.version.version_number == 1
        assert v1_result.version.title == "V1 Title"
        assert v1_result.is_current is False

        # Also verify v2 is still there
        v2_result = await engine.get_decision(
            create_result.decision.id,
            version=2,
        )
        assert v2_result.version.version_number == 2
        assert v2_result.is_current is True

    async def test_get_nonexistent_version_raises(
        self,
        session: AsyncSession,
        org_id: uuid4,
        user_id: uuid4,
        sample_content: DecisionContentDTO,
    ):
        """Requesting a non-existent version should raise."""
        engine = LedgerEngine(session)

        create_result = await engine.create_decision(
            input=CreateDecisionInput(title="Test", content=sample_content),
            organization_id=org_id,
            author_id=user_id,
        )

        with pytest.raises(VersionNotFoundError):
            await engine.get_decision(create_result.decision.id, version=999)

    async def test_get_nonexistent_decision_raises(
        self,
        session: AsyncSession,
    ):
        """Requesting a non-existent decision should raise."""
        engine = LedgerEngine(session)

        with pytest.raises(DecisionNotFoundError):
            await engine.get_decision(uuid4())

    async def test_version_history(
        self,
        session: AsyncSession,
        org_id: uuid4,
        user_id: uuid4,
        sample_content: DecisionContentDTO,
        updated_content: DecisionContentDTO,
    ):
        """Can get complete version history."""
        engine = LedgerEngine(session)

        create_result = await engine.create_decision(
            input=CreateDecisionInput(title="V1", content=sample_content),
            organization_id=org_id,
            author_id=user_id,
        )

        await engine.amend_decision(
            decision_id=create_result.decision.id,
            input=AmendDecisionInput(
                title="V2",
                content=updated_content,
                impact_level=ImpactLevel.MEDIUM,
                change_summary="First update",
            ),
            author_id=user_id,
        )

        await engine.amend_decision(
            decision_id=create_result.decision.id,
            input=AmendDecisionInput(
                title="V3",
                content=updated_content,
                impact_level=ImpactLevel.HIGH,
                change_summary="Second update",
            ),
            author_id=user_id,
        )

        history = await engine.get_version_history(create_result.decision.id)

        assert len(history) == 3
        # Newest first
        assert history[0].version_number == 3
        assert history[1].version_number == 2
        assert history[2].version_number == 1

    async def test_compare_versions(
        self,
        session: AsyncSession,
        org_id: uuid4,
        user_id: uuid4,
        sample_content: DecisionContentDTO,
        updated_content: DecisionContentDTO,
    ):
        """Can compare two versions."""
        engine = LedgerEngine(session)

        create_result = await engine.create_decision(
            input=CreateDecisionInput(
                title="Original",
                content=sample_content,
                tags=["a", "b"],
            ),
            organization_id=org_id,
            author_id=user_id,
        )

        await engine.amend_decision(
            decision_id=create_result.decision.id,
            input=AmendDecisionInput(
                title="Changed",
                content=updated_content,
                impact_level=ImpactLevel.HIGH,
                tags=["a", "c"],  # Changed tags
                change_summary="Major update",
            ),
            author_id=user_id,
        )

        comparison = await engine.compare_versions(
            create_result.decision.id,
            version_a=1,
            version_b=2,
        )

        assert comparison["changes"]["title_changed"] is True
        assert comparison["changes"]["content_changed"] is True
        assert comparison["changes"]["tags_changed"] is True
