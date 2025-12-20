#!/usr/bin/env python3
"""
Seed Data Script for Decision Ledger

Creates a realistic "Tech Company" scenario with:
- 3 Users (Alice CTO, Bob Engineering Lead, Charlie Junior Dev)
- 1 Organization (Acme Tech)
- 2 Teams (Platform, Frontend)
- Multiple decisions demonstrating various features:
  - Decision A: Approved migration decision
  - Decision B: EXPIRED tech debt (credentials issue)
  - Decision C: Multiple versions for diff testing
  - Decision D: At-risk decision (expiring soon)
  - Decision E: Superseded decision chain

Run with: python seed_data.py
"""

import asyncio
import hashlib
import json
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# Import models
from decision_ledger.models import (
    Organization,
    User,
    OrganizationMember,
    Team,
    TeamMember,
    Decision,
    DecisionVersion,
    DecisionRelationship,
    Approval,
    AuditLog,
    Tag,
    DecisionStatus,
    ImpactLevel,
    RelationshipType,
    AuditAction,
    ApprovalStatus,
)
from decision_ledger.core.config import get_settings

settings = get_settings()


def compute_content_hash(content: dict) -> str:
    """Compute SHA-256 hash of content for immutability verification."""
    content_str = json.dumps(content, sort_keys=True, default=str)
    return hashlib.sha256(content_str.encode()).hexdigest()


async def seed_database():
    """Main seeding function."""

    # Create engine and session
    engine = create_async_engine(settings.database_url_async, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        print("🌱 Starting database seed...")

        # Check if data already exists
        result = await session.execute(text("SELECT COUNT(*) FROM organizations"))
        count = result.scalar()
        if count and count > 0:
            print("⚠️  Database already has data. Clearing existing data...")
            await clear_database(session)

        # =================================================================
        # CREATE ORGANIZATION
        # =================================================================
        print("\n📦 Creating organization...")

        org = Organization(
            id=uuid4(),
            slug="acme-tech",
            name="Acme Technologies Inc.",
            settings={
                "features": {
                    "tech_debt_timer": True,
                    "audit_export": True,
                    "slack_integration": True,
                },
                "review_reminder_days": [14, 7, 1],
            },
        )
        session.add(org)
        await session.flush()
        print(f"   ✓ Created: {org.name} ({org.slug})")

        # =================================================================
        # CREATE USERS
        # =================================================================
        print("\n👥 Creating users...")

        alice = User(
            id=uuid4(),
            email="alice@acme.tech",
            name="Alice Chen",
            avatar_url="https://api.dicebear.com/7.x/avataaars/svg?seed=alice",
            auth_provider="google",
        )

        bob = User(
            id=uuid4(),
            email="bob@acme.tech",
            name="Bob Martinez",
            avatar_url="https://api.dicebear.com/7.x/avataaars/svg?seed=bob",
            auth_provider="google",
        )

        charlie = User(
            id=uuid4(),
            email="charlie@acme.tech",
            name="Charlie Kim",
            avatar_url="https://api.dicebear.com/7.x/avataaars/svg?seed=charlie",
            auth_provider="google",
        )

        session.add_all([alice, bob, charlie])
        await session.flush()

        print(f"   ✓ Alice Chen (CTO, Admin)")
        print(f"   ✓ Bob Martinez (Engineering Lead)")
        print(f"   ✓ Charlie Kim (Junior Developer)")

        # =================================================================
        # CREATE ORG MEMBERSHIPS
        # =================================================================
        print("\n🔗 Creating organization memberships...")

        alice_member = OrganizationMember(
            id=uuid4(),
            organization_id=org.id,
            user_id=alice.id,
            role="admin",
        )

        bob_member = OrganizationMember(
            id=uuid4(),
            organization_id=org.id,
            user_id=bob.id,
            role="member",
        )

        charlie_member = OrganizationMember(
            id=uuid4(),
            organization_id=org.id,
            user_id=charlie.id,
            role="member",
        )

        session.add_all([alice_member, bob_member, charlie_member])
        await session.flush()
        print(f"   ✓ All users added to {org.name}")

        # =================================================================
        # CREATE TEAMS
        # =================================================================
        print("\n🏢 Creating teams...")

        platform_team = Team(
            id=uuid4(),
            organization_id=org.id,
            slug="platform",
            name="Platform Engineering",
            description="Core infrastructure and backend services",
        )

        frontend_team = Team(
            id=uuid4(),
            organization_id=org.id,
            slug="frontend",
            name="Frontend Team",
            description="User interface and client applications",
        )

        security_team = Team(
            id=uuid4(),
            organization_id=org.id,
            slug="security",
            name="Security & Compliance",
            description="Security practices and compliance",
        )

        session.add_all([platform_team, frontend_team, security_team])
        await session.flush()

        print(f"   ✓ Platform Engineering")
        print(f"   ✓ Frontend Team")
        print(f"   ✓ Security & Compliance")

        # =================================================================
        # CREATE TEAM MEMBERSHIPS
        # =================================================================
        print("\n👤 Assigning team members...")

        team_memberships = [
            TeamMember(id=uuid4(), team_id=platform_team.id, user_id=alice.id, role="lead"),
            TeamMember(id=uuid4(), team_id=platform_team.id, user_id=bob.id, role="member"),
            TeamMember(id=uuid4(), team_id=frontend_team.id, user_id=bob.id, role="lead"),
            TeamMember(id=uuid4(), team_id=frontend_team.id, user_id=charlie.id, role="member"),
            TeamMember(id=uuid4(), team_id=security_team.id, user_id=alice.id, role="lead"),
        ]

        session.add_all(team_memberships)
        await session.flush()
        print(f"   ✓ Team memberships created")

        # =================================================================
        # CREATE TAGS
        # =================================================================
        print("\n🏷️  Creating tags...")

        tags = [
            Tag(id=uuid4(), organization_id=org.id, name="database", color="#3b82f6"),
            Tag(id=uuid4(), organization_id=org.id, name="security", color="#ef4444"),
            Tag(id=uuid4(), organization_id=org.id, name="frontend", color="#10b981"),
            Tag(id=uuid4(), organization_id=org.id, name="infrastructure", color="#8b5cf6"),
            Tag(id=uuid4(), organization_id=org.id, name="tech-debt", color="#f59e0b"),
            Tag(id=uuid4(), organization_id=org.id, name="api", color="#06b6d4"),
        ]

        session.add_all(tags)
        await session.flush()
        print(f"   ✓ Created {len(tags)} tags")

        # =================================================================
        # DECISION A: Approved Migration (Clean Example)
        # =================================================================
        print("\n📋 Creating Decision A: PostgreSQL Migration...")

        decision_a = Decision(
            id=uuid4(),
            organization_id=org.id,
            decision_number=1,
            status=DecisionStatus.APPROVED,
            owner_team_id=platform_team.id,
            created_by=alice.id,
            created_at=datetime.utcnow() - timedelta(days=45),
            review_by_date=datetime.utcnow() + timedelta(days=180),  # 6 months from now
            is_temporary=False,
        )
        session.add(decision_a)
        await session.flush()

        content_a = {
            "context": """Our current MySQL 5.7 database is reaching its limits. We're experiencing:
- Slow complex queries on analytics workloads
- Lack of native JSON support causing application complexity
- Upcoming MySQL 5.7 end-of-life in October 2024
- Growing need for advanced features like full-text search and geospatial queries

The platform team has been evaluating alternatives for the past quarter.""",
            "choice": """We will migrate our primary database from MySQL 5.7 to PostgreSQL 15.

The migration will be phased:
1. Phase 1 (Q1): Set up PostgreSQL infrastructure, create migration scripts
2. Phase 2 (Q2): Dual-write period with data validation
3. Phase 3 (Q3): Full cutover with MySQL as hot standby
4. Phase 4 (Q4): Decommission MySQL""",
            "rationale": """PostgreSQL was chosen over other alternatives because:

1. **Feature Set**: Native JSON/JSONB support, excellent full-text search, PostGIS for geospatial
2. **Performance**: Better query optimizer, parallel query execution, advanced indexing
3. **Team Expertise**: 3 of 5 platform engineers have production PostgreSQL experience
4. **Ecosystem**: Strong support in our stack (SQLAlchemy, Django, etc.)
5. **Cost**: Open source with no licensing fees, unlike Oracle or SQL Server""",
            "alternatives": [
                {
                    "name": "MySQL 8.0 Upgrade",
                    "rejected_reason": "While simpler, MySQL 8.0 still lacks the JSON performance and advanced features we need. Would be another migration in 2-3 years."
                },
                {
                    "name": "Amazon Aurora",
                    "rejected_reason": "Vendor lock-in concerns and significantly higher cost (~3x our current spend). Team prefers self-managed for better control."
                },
                {
                    "name": "CockroachDB",
                    "rejected_reason": "Excellent distributed database but overkill for our current scale. Higher operational complexity without clear benefits yet."
                }
            ],
            "consequences": """Positive:
- 40% improvement in analytics query performance (based on POC)
- Native JSON support reduces application code complexity
- Future-proof for next 5+ years

Negative:
- 3-month migration effort requiring dedicated engineering time
- Temporary increase in infrastructure costs during dual-write phase
- Learning curve for MySQL-experienced team members

Risks:
- Data migration bugs could cause data loss (mitigated by extensive testing)
- Application compatibility issues (mitigated by comprehensive test suite)""",
        }

        version_a = DecisionVersion(
            id=uuid4(),
            decision_id=decision_a.id,
            version_number=1,
            title="Migrate Primary Database to PostgreSQL 15",
            impact_level=ImpactLevel.HIGH,
            content=content_a,
            tags=["database", "infrastructure"],
            created_by=alice.id,
            created_at=datetime.utcnow() - timedelta(days=45),
            change_summary="Initial decision document",
            content_hash=compute_content_hash(content_a),
        )
        session.add(version_a)
        await session.flush()

        decision_a.current_version_id = version_a.id

        # Add approval
        approval_a = Approval(
            id=uuid4(),
            decision_version_id=version_a.id,
            user_id=bob.id,
            status=ApprovalStatus.APPROVED,
            comment="LGTM! The phased approach is smart. Let's make sure we have rollback procedures documented.",
            created_at=datetime.utcnow() - timedelta(days=44),
        )
        session.add(approval_a)

        print(f"   ✓ DEC-1: Migrate Primary Database to PostgreSQL 15 [APPROVED]")

        # =================================================================
        # DECISION B: EXPIRED Tech Debt (Security Risk)
        # =================================================================
        print("\n📋 Creating Decision B: Temporary Admin Credentials (EXPIRED)...")

        decision_b = Decision(
            id=uuid4(),
            organization_id=org.id,
            decision_number=2,
            status=DecisionStatus.EXPIRED,  # Set to EXPIRED
            owner_team_id=security_team.id,
            created_by=charlie.id,
            created_at=datetime.utcnow() - timedelta(days=90),
            review_by_date=datetime.utcnow() - timedelta(days=1),  # YESTERDAY - triggers RED on dashboard
            is_temporary=True,  # Marked as temporary decision
        )
        session.add(decision_b)
        await session.flush()

        content_b = {
            "context": """During the Q3 sprint crunch, we needed to quickly set up internal admin tools for the ops team.
The proper authentication system (SSO integration) was not ready yet.

This is a TEMPORARY solution that MUST be replaced before production launch.""",
            "choice": """Use hardcoded credentials (admin/admin) for the internal admin dashboard.

Scope:
- Only accessible from internal VPN
- Only used by 3 ops team members
- Dashboard has read-only access to non-sensitive data

This decision MUST be revisited within 30 days.""",
            "rationale": """We chose this expedient approach because:
1. SSO integration requires 2 weeks of engineering work we don't have
2. The ops team is blocked without any admin access
3. Risk is limited due to VPN-only access and read-only permissions

This is explicitly acknowledged as tech debt that must be addressed.""",
            "alternatives": [
                {
                    "name": "Wait for SSO",
                    "rejected_reason": "Would block ops team for 2+ weeks, impacting customer support capabilities"
                },
                {
                    "name": "Individual passwords",
                    "rejected_reason": "Similar security risk but with added complexity of password management"
                }
            ],
            "consequences": """CRITICAL RISKS:
- Security vulnerability if VPN is compromised
- Compliance risk for SOC2 audit
- Must be addressed before Q4 launch

Mitigation:
- Set 30-day review deadline (NON-NEGOTIABLE)
- Add audit logging for all admin actions
- Document all users with access""",
        }

        version_b = DecisionVersion(
            id=uuid4(),
            decision_id=decision_b.id,
            version_number=1,
            title="Temporary Admin Credentials for Internal Tools",
            impact_level=ImpactLevel.CRITICAL,
            content=content_b,
            tags=["security", "tech-debt"],
            created_by=charlie.id,
            created_at=datetime.utcnow() - timedelta(days=90),
            change_summary="Initial temporary decision - MUST BE REVIEWED",
            content_hash=compute_content_hash(content_b),
        )
        session.add(version_b)
        await session.flush()

        decision_b.current_version_id = version_b.id

        print(f"   ✓ DEC-2: Temporary Admin Credentials [EXPIRED - Shows RED on dashboard]")

        # =================================================================
        # DECISION C: Multiple Versions (For Diff Testing)
        # =================================================================
        print("\n📋 Creating Decision C: Frontend Framework (3 versions for diff testing)...")

        decision_c = Decision(
            id=uuid4(),
            organization_id=org.id,
            decision_number=3,
            status=DecisionStatus.APPROVED,
            owner_team_id=frontend_team.id,
            created_by=charlie.id,
            created_at=datetime.utcnow() - timedelta(days=30),
            review_by_date=datetime.utcnow() + timedelta(days=365),
            is_temporary=False,
        )
        session.add(decision_c)
        await session.flush()

        # VERSION 1: Angular (1 month ago, by Charlie)
        content_c1 = {
            "context": """We need to rebuild our customer portal. The current jQuery-based UI is unmaintainable and doesn't meet modern UX standards.

Requirements:
- Component-based architecture
- Strong TypeScript support
- Good ecosystem for enterprise features""",
            "choice": """Use Angular 17 for the new customer portal.

Angular provides:
- Full framework with batteries included
- Strong TypeScript integration
- Excellent tooling (CLI, DevTools)""",
            "rationale": """Angular was chosen because:
1. Enterprise-grade framework with long-term support
2. Built-in solutions for routing, forms, HTTP
3. Team has some Angular experience from previous project""",
            "alternatives": [
                {
                    "name": "React",
                    "rejected_reason": "Requires too many decisions about state management, routing, etc."
                },
                {
                    "name": "Vue.js",
                    "rejected_reason": "Smaller ecosystem, fewer enterprise examples"
                }
            ],
            "consequences": """Learning curve for team members new to Angular. Larger bundle size compared to lighter alternatives.""",
        }

        version_c1 = DecisionVersion(
            id=uuid4(),
            decision_id=decision_c.id,
            version_number=1,
            title="Use Angular for Customer Portal",
            impact_level=ImpactLevel.MEDIUM,
            content=content_c1,
            tags=["frontend"],
            created_by=charlie.id,
            created_at=datetime.utcnow() - timedelta(days=30),
            change_summary="Initial framework decision",
            content_hash=compute_content_hash(content_c1),
        )
        session.add(version_c1)

        # VERSION 2: React (2 weeks ago, by Bob)
        content_c2 = {
            "context": """We need to rebuild our customer portal. The current jQuery-based UI is unmaintainable and doesn't meet modern UX standards.

Requirements:
- Component-based architecture
- Strong TypeScript support
- Good ecosystem for enterprise features
- **UPDATE**: After 2 weeks of Angular POC, team velocity was lower than expected""",
            "choice": """Use React 18 with TypeScript for the new customer portal.

React provides:
- Flexible component model
- Huge ecosystem and community
- Better developer experience based on POC feedback""",
            "rationale": """Switching to React because:
1. Angular POC showed steeper learning curve than anticipated
2. More team members have React experience (3 vs 1)
3. Faster iteration speed in POC comparisons
4. Better component library options (shadcn/ui, Radix)""",
            "alternatives": [
                {
                    "name": "Continue with Angular",
                    "rejected_reason": "POC showed 40% slower development velocity vs React prototype"
                },
                {
                    "name": "Vue.js",
                    "rejected_reason": "Still concerned about enterprise adoption and long-term support"
                }
            ],
            "consequences": """Need to restart the 2-week POC work. However, long-term velocity improvement justifies the reset.""",
        }

        version_c2 = DecisionVersion(
            id=uuid4(),
            decision_id=decision_c.id,
            version_number=2,
            title="Use React for Customer Portal",
            impact_level=ImpactLevel.MEDIUM,
            content=content_c2,
            tags=["frontend"],
            created_by=bob.id,
            created_at=datetime.utcnow() - timedelta(days=14),
            change_summary="Switched from Angular to React based on POC learnings",
            content_hash=compute_content_hash(content_c2),
        )
        session.add(version_c2)

        # VERSION 3: Next.js (Today, by Alice)
        content_c3 = {
            "context": """We need to rebuild our customer portal. The current jQuery-based UI is unmaintainable and doesn't meet modern UX standards.

Requirements:
- Component-based architecture
- Strong TypeScript support
- Good ecosystem for enterprise features
- **UPDATE**: SEO requirements from marketing team require server-side rendering
- **UPDATE**: Performance budget requires optimized loading strategy""",
            "choice": """Use Next.js 14 (App Router) with React for the new customer portal.

Next.js provides:
- Built on React (preserves team's React work)
- Server-side rendering for SEO
- Automatic code splitting and optimization
- API routes for BFF pattern""",
            "rationale": """Adding Next.js on top of React because:
1. Marketing team requires SEO optimization for public pages
2. Built-in performance optimizations (Image, Font, Script)
3. API routes enable Backend-for-Frontend pattern
4. Streaming and Suspense support for better UX
5. Strong Vercel backing and active development""",
            "alternatives": [
                {
                    "name": "Plain React with SSR library",
                    "rejected_reason": "Would require significant custom setup. Next.js provides this out of the box."
                },
                {
                    "name": "Remix",
                    "rejected_reason": "Excellent framework but smaller community. Next.js has more resources and examples."
                },
                {
                    "name": "Astro",
                    "rejected_reason": "Great for content sites but our portal is highly interactive. React/Next.js is better fit."
                }
            ],
            "consequences": """Positive:
- SEO requirements met
- Performance budget achievable with built-in optimizations
- Team can leverage existing React knowledge

Considerations:
- Need to learn App Router patterns (different from Pages Router)
- Deployment requires Node.js server (not pure static)
- Some additional complexity vs plain React""",
        }

        version_c3 = DecisionVersion(
            id=uuid4(),
            decision_id=decision_c.id,
            version_number=3,
            title="Use Next.js 14 for Customer Portal",
            impact_level=ImpactLevel.MEDIUM,
            content=content_c3,
            tags=["frontend", "infrastructure"],
            created_by=alice.id,
            created_at=datetime.utcnow(),  # Today
            change_summary="Upgraded to Next.js for SSR and SEO requirements",
            content_hash=compute_content_hash(content_c3),
        )
        session.add(version_c3)
        await session.flush()

        decision_c.current_version_id = version_c3.id

        # Add approvals for version 3
        approval_c = Approval(
            id=uuid4(),
            decision_version_id=version_c3.id,
            user_id=bob.id,
            status=ApprovalStatus.APPROVED,
            comment="Makes sense given the SEO requirements. Let's do it!",
            created_at=datetime.utcnow(),
        )
        session.add(approval_c)

        print(f"   ✓ DEC-3: Frontend Framework [3 VERSIONS - Angular → React → Next.js]")

        # =================================================================
        # DECISION D: At-Risk (Expiring Soon)
        # =================================================================
        print("\n📋 Creating Decision D: API Rate Limiting (AT RISK - expires in 5 days)...")

        decision_d = Decision(
            id=uuid4(),
            organization_id=org.id,
            decision_number=4,
            status=DecisionStatus.AT_RISK,  # Shows YELLOW on dashboard
            owner_team_id=platform_team.id,
            created_by=bob.id,
            created_at=datetime.utcnow() - timedelta(days=60),
            review_by_date=datetime.utcnow() + timedelta(days=5),  # 5 days from now - AT RISK
            is_temporary=True,
        )
        session.add(decision_d)
        await session.flush()

        content_d = {
            "context": """Our public API is experiencing abuse from scrapers and poorly implemented client integrations.
We need rate limiting but our API gateway doesn't support it natively.

This is a temporary solution until we migrate to the new API gateway (planned Q1).""",
            "choice": """Implement application-level rate limiting using Redis.

Configuration:
- 100 requests per minute per API key
- 1000 requests per hour per API key
- Sliding window algorithm""",
            "rationale": """Redis-based solution chosen because:
1. We already run Redis for caching
2. Can implement quickly with existing libraries
3. Flexible enough to customize per endpoint later""",
            "alternatives": [
                {
                    "name": "Wait for new API gateway",
                    "rejected_reason": "Can't wait 3 months while abuse continues"
                },
                {
                    "name": "Cloudflare rate limiting",
                    "rejected_reason": "Per-request pricing too expensive at our scale"
                }
            ],
            "consequences": """This is tech debt. The application-level solution:
- Adds latency to every request
- Doesn't protect against DDoS (need infrastructure-level solution)
- Must be removed when new gateway is live""",
        }

        version_d = DecisionVersion(
            id=uuid4(),
            decision_id=decision_d.id,
            version_number=1,
            title="Temporary API Rate Limiting with Redis",
            impact_level=ImpactLevel.MEDIUM,
            content=content_d,
            tags=["api", "infrastructure", "tech-debt"],
            created_by=bob.id,
            created_at=datetime.utcnow() - timedelta(days=60),
            change_summary="Temporary rate limiting solution",
            content_hash=compute_content_hash(content_d),
        )
        session.add(version_d)
        await session.flush()

        decision_d.current_version_id = version_d.id

        print(f"   ✓ DEC-4: Temporary API Rate Limiting [AT RISK - expires in 5 days]")

        # =================================================================
        # DECISION E: Superseded Decision Chain
        # =================================================================
        print("\n📋 Creating Decision E: Auth Strategy (Superseded chain)...")

        # Original decision (superseded)
        decision_e1 = Decision(
            id=uuid4(),
            organization_id=org.id,
            decision_number=5,
            status=DecisionStatus.SUPERSEDED,
            owner_team_id=security_team.id,
            created_by=alice.id,
            created_at=datetime.utcnow() - timedelta(days=120),
            is_temporary=False,
        )
        session.add(decision_e1)
        await session.flush()

        content_e1 = {
            "context": "Need to implement user authentication for the platform.",
            "choice": "Use session-based authentication with server-side sessions stored in PostgreSQL.",
            "rationale": "Simple to implement, well-understood security model.",
            "alternatives": [{"name": "JWT", "rejected_reason": "Added complexity not needed for MVP"}],
            "consequences": "Works well for single-server deployment.",
        }

        version_e1 = DecisionVersion(
            id=uuid4(),
            decision_id=decision_e1.id,
            version_number=1,
            title="Session-Based Authentication",
            impact_level=ImpactLevel.HIGH,
            content=content_e1,
            tags=["security", "api"],
            created_by=alice.id,
            created_at=datetime.utcnow() - timedelta(days=120),
            change_summary="Initial auth strategy",
            content_hash=compute_content_hash(content_e1),
        )
        session.add(version_e1)
        await session.flush()
        decision_e1.current_version_id = version_e1.id

        # New decision (supersedes the old one)
        decision_e2 = Decision(
            id=uuid4(),
            organization_id=org.id,
            decision_number=6,
            status=DecisionStatus.APPROVED,
            owner_team_id=security_team.id,
            created_by=alice.id,
            created_at=datetime.utcnow() - timedelta(days=30),
            review_by_date=datetime.utcnow() + timedelta(days=365),
            is_temporary=False,
        )
        session.add(decision_e2)
        await session.flush()

        content_e2 = {
            "context": """Our platform has grown to require multiple services and mobile apps.
Session-based auth (DEC-5) doesn't scale well for this architecture.

We need stateless authentication that works across services.""",
            "choice": """Migrate to JWT-based authentication with refresh tokens.

Implementation:
- Short-lived access tokens (15 minutes)
- Long-lived refresh tokens (7 days)
- Tokens stored in httpOnly cookies for web
- Token rotation on refresh""",
            "rationale": """JWT chosen because:
1. Stateless - works across microservices without shared session store
2. Mobile-friendly - works well with native apps
3. Standard format - easy integration with third-party services
4. Supports our planned SSO integration""",
            "alternatives": [
                {"name": "Keep sessions with Redis", "rejected_reason": "Added infrastructure complexity, doesn't help with mobile"},
                {"name": "OAuth2 only", "rejected_reason": "Need internal auth too, not just third-party"},
            ],
            "consequences": """This supersedes DEC-5 (Session-Based Authentication).

Migration plan:
1. Implement JWT alongside sessions
2. Migrate endpoints one by one
3. Support both during transition
4. Deprecate sessions after 60 days""",
        }

        version_e2 = DecisionVersion(
            id=uuid4(),
            decision_id=decision_e2.id,
            version_number=1,
            title="JWT-Based Authentication with Refresh Tokens",
            impact_level=ImpactLevel.HIGH,
            content=content_e2,
            tags=["security", "api", "infrastructure"],
            created_by=alice.id,
            created_at=datetime.utcnow() - timedelta(days=30),
            change_summary="New auth strategy replacing session-based approach",
            content_hash=compute_content_hash(content_e2),
        )
        session.add(version_e2)
        await session.flush()
        decision_e2.current_version_id = version_e2.id

        # Create supersedes relationship
        relationship = DecisionRelationship(
            id=uuid4(),
            source_decision_id=decision_e2.id,
            target_decision_id=decision_e1.id,
            relationship_type=RelationshipType.SUPERSEDES,
            description="JWT auth replaces session-based auth for multi-service architecture",
            created_by=alice.id,
            created_at=datetime.utcnow() - timedelta(days=30),
        )
        session.add(relationship)

        print(f"   ✓ DEC-5: Session-Based Auth [SUPERSEDED]")
        print(f"   ✓ DEC-6: JWT-Based Auth [APPROVED, supersedes DEC-5]")

        # =================================================================
        # CREATE AUDIT LOG ENTRIES
        # =================================================================
        print("\n📝 Creating audit log entries...")

        audit_entries = [
            AuditLog(
                id=uuid4(),
                organization_id=org.id,
                user_id=alice.id,
                action=AuditAction.CREATE,
                resource_type="decision",
                resource_id=decision_a.id,
                details={"decision_number": 1, "title": version_a.title},
                created_at=datetime.utcnow() - timedelta(days=45),
            ),
            AuditLog(
                id=uuid4(),
                organization_id=org.id,
                user_id=bob.id,
                action=AuditAction.APPROVE,
                resource_type="decision",
                resource_id=decision_a.id,
                details={"decision_number": 1, "version": 1},
                created_at=datetime.utcnow() - timedelta(days=44),
            ),
            AuditLog(
                id=uuid4(),
                organization_id=org.id,
                user_id=charlie.id,
                action=AuditAction.CREATE,
                resource_type="decision",
                resource_id=decision_c.id,
                details={"decision_number": 3, "title": "Use Angular for Customer Portal"},
                created_at=datetime.utcnow() - timedelta(days=30),
            ),
            AuditLog(
                id=uuid4(),
                organization_id=org.id,
                user_id=bob.id,
                action=AuditAction.UPDATE,
                resource_type="decision",
                resource_id=decision_c.id,
                details={"decision_number": 3, "version": 2, "change": "Switched to React"},
                created_at=datetime.utcnow() - timedelta(days=14),
            ),
            AuditLog(
                id=uuid4(),
                organization_id=org.id,
                user_id=alice.id,
                action=AuditAction.UPDATE,
                resource_type="decision",
                resource_id=decision_c.id,
                details={"decision_number": 3, "version": 3, "change": "Upgraded to Next.js"},
                created_at=datetime.utcnow(),
            ),
        ]

        session.add_all(audit_entries)
        print(f"   ✓ Created {len(audit_entries)} audit log entries")

        # =================================================================
        # COMMIT ALL CHANGES
        # =================================================================
        await session.commit()

        print("\n" + "=" * 60)
        print("✅ DATABASE SEEDED SUCCESSFULLY!")
        print("=" * 60)
        print(f"""
📊 Summary:
   • 1 Organization: {org.name}
   • 3 Users: Alice (CTO), Bob (Lead), Charlie (Dev)
   • 3 Teams: Platform, Frontend, Security
   • 6 Decisions:
     - DEC-1: PostgreSQL Migration [APPROVED]
     - DEC-2: Temp Admin Credentials [EXPIRED - RED] 🔴
     - DEC-3: Frontend Framework [3 versions - for diff testing]
     - DEC-4: API Rate Limiting [AT RISK - YELLOW] 🟡
     - DEC-5: Session Auth [SUPERSEDED]
     - DEC-6: JWT Auth [APPROVED, supersedes DEC-5]

🧪 What you can test:
   1. Risk Dashboard: See DEC-2 (red/expired) and DEC-4 (yellow/at-risk)
   2. Diff View: Open DEC-3 and compare versions (Angular→React→Next.js)
   3. Supersession: See DEC-6 supersedes DEC-5 in the lineage
   4. Audit Export: Generate a compliance report with all decisions
   5. Snooze: Try snoozing DEC-2 or DEC-4

🌐 Access the app at: http://localhost:3000
""")


async def clear_database(session: AsyncSession):
    """Clear all data from the database (in correct order for FK constraints)."""
    tables = [
        "audit_log",
        "notification_log",
        "update_requests",
        "approvals",
        "required_reviewers",
        "decision_relationships",
        "decision_versions",
        "decisions",
        "tags",
        "team_members",
        "teams",
        "organization_members",
        "users",
        "organizations",
    ]

    for table in tables:
        try:
            await session.execute(text(f"DELETE FROM {table}"))
        except Exception as e:
            print(f"   Warning: Could not clear {table}: {e}")

    await session.commit()
    print("   ✓ Cleared existing data")


if __name__ == "__main__":
    asyncio.run(seed_database())
