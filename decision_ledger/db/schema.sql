-- Decision Ledger: PostgreSQL Schema
-- Immutable decision tracking with full audit compliance
-- Author: Decision Ledger System

-- =============================================================================
-- EXTENSIONS
-- =============================================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- ENUMS (Type Safety at DB Level)
-- =============================================================================

CREATE TYPE decision_status AS ENUM (
    'draft',
    'pending_review',
    'approved',
    'deprecated',
    'superseded'
);

CREATE TYPE impact_level AS ENUM (
    'low',
    'medium',
    'high',
    'critical'
);

CREATE TYPE relationship_type AS ENUM (
    'supersedes',      -- This decision replaces another
    'blocked_by',      -- This decision depends on another
    'related_to',      -- Informational link
    'implements',      -- This decision implements a higher-level decision
    'conflicts_with'   -- Explicit conflict marker
);

CREATE TYPE audit_action AS ENUM (
    'create',
    'read',
    'update',
    'approve',
    'reject',
    'supersede',
    'deprecate',
    'export',
    'share'
);

CREATE TYPE approval_status AS ENUM (
    'pending',
    'approved',
    'rejected',
    'abstained'
);

-- =============================================================================
-- ORGANIZATIONS (Multi-Tenancy Root)
-- =============================================================================

CREATE TABLE organizations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    slug            VARCHAR(63) NOT NULL UNIQUE,  -- URL-safe identifier
    name            VARCHAR(255) NOT NULL,
    settings        JSONB DEFAULT '{}',           -- Flexible org settings
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Soft delete for compliance (never hard delete)
    deleted_at      TIMESTAMPTZ DEFAULT NULL,

    CONSTRAINT slug_format CHECK (slug ~ '^[a-z0-9][a-z0-9-]*[a-z0-9]$')
);

CREATE INDEX idx_organizations_slug ON organizations(slug) WHERE deleted_at IS NULL;

-- =============================================================================
-- USERS
-- =============================================================================

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    name            VARCHAR(255) NOT NULL,
    avatar_url      VARCHAR(500),
    auth_provider   VARCHAR(50) NOT NULL DEFAULT 'email',
    auth_provider_id VARCHAR(255),

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at   TIMESTAMPTZ,
    deleted_at      TIMESTAMPTZ DEFAULT NULL,

    CONSTRAINT email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

CREATE INDEX idx_users_email ON users(email) WHERE deleted_at IS NULL;

-- =============================================================================
-- ORGANIZATION MEMBERSHIPS (Users can belong to multiple orgs)
-- =============================================================================

CREATE TABLE organization_members (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    user_id         UUID NOT NULL REFERENCES users(id),
    role            VARCHAR(50) NOT NULL DEFAULT 'member',  -- owner, admin, member, viewer

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    invited_by      UUID REFERENCES users(id),

    UNIQUE(organization_id, user_id)
);

CREATE INDEX idx_org_members_org ON organization_members(organization_id);
CREATE INDEX idx_org_members_user ON organization_members(user_id);

-- =============================================================================
-- TEAMS (Subdivisions within Organizations)
-- =============================================================================

CREATE TABLE teams (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    slug            VARCHAR(63) NOT NULL,
    name            VARCHAR(255) NOT NULL,
    description     TEXT,
    parent_team_id  UUID REFERENCES teams(id),  -- Hierarchical teams

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ DEFAULT NULL,

    UNIQUE(organization_id, slug)
);

CREATE INDEX idx_teams_org ON teams(organization_id) WHERE deleted_at IS NULL;

-- =============================================================================
-- TEAM MEMBERSHIPS
-- =============================================================================

CREATE TABLE team_members (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id         UUID NOT NULL REFERENCES teams(id),
    user_id         UUID NOT NULL REFERENCES users(id),
    role            VARCHAR(50) NOT NULL DEFAULT 'member',  -- lead, member

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(team_id, user_id)
);

CREATE INDEX idx_team_members_team ON team_members(team_id);

-- =============================================================================
-- DECISIONS (The Core Entity - Immutable Header)
-- =============================================================================
-- The decision table is the ANCHOR. It never changes after creation.
-- All mutable data lives in decision_versions.

CREATE TABLE decisions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id),

    -- Immutable identifier (human-readable, org-scoped)
    decision_number SERIAL,  -- Auto-incrementing within org (DEC-001, DEC-002...)

    -- Current state pointers (updated atomically)
    current_version_id UUID,  -- Points to the active version (FK added after versions table)
    status          decision_status NOT NULL DEFAULT 'draft',

    -- Ownership
    owner_team_id   UUID REFERENCES teams(id),
    created_by      UUID NOT NULL REFERENCES users(id),

    -- Timestamps
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Soft delete
    deleted_at      TIMESTAMPTZ DEFAULT NULL,

    UNIQUE(organization_id, decision_number)
);

CREATE INDEX idx_decisions_org ON decisions(organization_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_decisions_status ON decisions(organization_id, status) WHERE deleted_at IS NULL;
CREATE INDEX idx_decisions_owner_team ON decisions(owner_team_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_decisions_created_by ON decisions(created_by);

-- =============================================================================
-- DECISION VERSIONS (Immutable Content Snapshots)
-- =============================================================================
-- Every edit creates a new version. Versions are NEVER modified.
-- This is the "ledger" aspect - append-only.

CREATE TABLE decision_versions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    decision_id     UUID NOT NULL REFERENCES decisions(id),

    -- Version tracking
    version_number  INTEGER NOT NULL,  -- 1, 2, 3... within a decision

    -- Header fields (snapshot at this version)
    title           VARCHAR(500) NOT NULL,
    impact_level    impact_level NOT NULL DEFAULT 'medium',

    -- Rich content (JSONB for flexibility + full-text search)
    content         JSONB NOT NULL DEFAULT '{}',
    -- Expected structure:
    -- {
    --   "context": "Markdown describing the problem...",
    --   "choice": "What we decided...",
    --   "rationale": "Why we made this choice...",
    --   "alternatives": [
    --     {"name": "Option B", "rejected_reason": "Too expensive"},
    --     {"name": "Option C", "rejected_reason": "Too risky"}
    --   ],
    --   "consequences": "Expected outcomes...",
    --   "review_date": "2025-06-01"  -- Optional scheduled review
    -- }

    -- Metadata (flexible, schema-validated at app layer)
    tags            TEXT[] DEFAULT '{}',
    custom_fields   JSONB DEFAULT '{}',

    -- Authorship
    created_by      UUID NOT NULL REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Change tracking
    change_summary  TEXT,  -- "Updated rationale section"

    -- Cryptographic integrity (optional but recommended for compliance)
    content_hash    VARCHAR(64),  -- SHA-256 of canonical content

    UNIQUE(decision_id, version_number)
);

CREATE INDEX idx_decision_versions_decision ON decision_versions(decision_id);
CREATE INDEX idx_decision_versions_created_at ON decision_versions(created_at);
CREATE INDEX idx_decision_versions_tags ON decision_versions USING GIN(tags);
CREATE INDEX idx_decision_versions_content ON decision_versions USING GIN(content jsonb_path_ops);

-- Add FK from decisions to current version
ALTER TABLE decisions
    ADD CONSTRAINT fk_decisions_current_version
    FOREIGN KEY (current_version_id) REFERENCES decision_versions(id);

-- =============================================================================
-- DECISION RELATIONSHIPS (The Graph)
-- =============================================================================
-- Models the directed graph of decision dependencies

CREATE TABLE decision_relationships (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- The relationship: source_decision -> target_decision
    source_decision_id  UUID NOT NULL REFERENCES decisions(id),
    target_decision_id  UUID NOT NULL REFERENCES decisions(id),
    relationship_type   relationship_type NOT NULL,

    -- Context for the relationship
    description         TEXT,

    -- When this relationship was established
    created_by          UUID NOT NULL REFERENCES users(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Relationships can be invalidated but never deleted
    invalidated_at      TIMESTAMPTZ DEFAULT NULL,
    invalidated_by      UUID REFERENCES users(id),

    -- Prevent duplicate relationships
    UNIQUE(source_decision_id, target_decision_id, relationship_type),

    -- Prevent self-references
    CONSTRAINT no_self_reference CHECK (source_decision_id != target_decision_id)
);

CREATE INDEX idx_relationships_source ON decision_relationships(source_decision_id)
    WHERE invalidated_at IS NULL;
CREATE INDEX idx_relationships_target ON decision_relationships(target_decision_id)
    WHERE invalidated_at IS NULL;
CREATE INDEX idx_relationships_type ON decision_relationships(relationship_type)
    WHERE invalidated_at IS NULL;

-- =============================================================================
-- APPROVALS (Sign-Off Ledger)
-- =============================================================================
-- Tracks who approved/rejected which version and when

CREATE TABLE approvals (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- What's being approved
    decision_version_id UUID NOT NULL REFERENCES decision_versions(id),

    -- Who's approving
    user_id         UUID NOT NULL REFERENCES users(id),

    -- The verdict
    status          approval_status NOT NULL,
    comment         TEXT,

    -- When (immutable)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Each user can only have one approval per version
    UNIQUE(decision_version_id, user_id)
);

CREATE INDEX idx_approvals_version ON approvals(decision_version_id);
CREATE INDEX idx_approvals_user ON approvals(user_id);
CREATE INDEX idx_approvals_status ON approvals(decision_version_id, status);

-- =============================================================================
-- REVIEWERS (Required Approvers)
-- =============================================================================
-- Defines who MUST approve a decision version

CREATE TABLE required_reviewers (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    decision_version_id UUID NOT NULL REFERENCES decision_versions(id),
    user_id         UUID NOT NULL REFERENCES users(id),

    -- Optional: require approval from a team role
    required_role   VARCHAR(50),  -- e.g., "security_lead", "architect"

    added_by        UUID NOT NULL REFERENCES users(id),
    added_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(decision_version_id, user_id)
);

CREATE INDEX idx_required_reviewers_version ON required_reviewers(decision_version_id);

-- =============================================================================
-- AUDIT LOG (Compliance Core)
-- =============================================================================
-- Append-only log of ALL actions. Never modified, never deleted.
-- This table should be on a separate tablespace with enhanced backup.

CREATE TABLE audit_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Context
    organization_id UUID NOT NULL REFERENCES organizations(id),
    user_id         UUID REFERENCES users(id),  -- NULL for system actions

    -- Action details
    action          audit_action NOT NULL,
    resource_type   VARCHAR(50) NOT NULL,  -- 'decision', 'decision_version', etc.
    resource_id     UUID NOT NULL,

    -- Rich context
    details         JSONB DEFAULT '{}',
    -- {
    --   "version_id": "...",
    --   "fields_accessed": ["rationale", "alternatives"],
    --   "ip_address": "192.168.1.1",
    --   "user_agent": "Mozilla/5.0...",
    --   "session_id": "..."
    -- }

    -- Immutable timestamp
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Cryptographic chain (optional, for tamper evidence)
    previous_hash   VARCHAR(64),  -- Hash of previous audit entry
    entry_hash      VARCHAR(64)   -- Hash of this entry
);

-- Partition by time for performance (audit logs grow fast)
-- In production, convert to partitioned table

CREATE INDEX idx_audit_log_org_time ON audit_log(organization_id, created_at DESC);
CREATE INDEX idx_audit_log_user ON audit_log(user_id, created_at DESC);
CREATE INDEX idx_audit_log_resource ON audit_log(resource_type, resource_id);
CREATE INDEX idx_audit_log_action ON audit_log(action, created_at DESC);

-- =============================================================================
-- SESSIONS (For audit trail context)
-- =============================================================================

CREATE TABLE sessions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id),

    -- Session context (for audit)
    ip_address      INET,
    user_agent      TEXT,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL,
    revoked_at      TIMESTAMPTZ DEFAULT NULL
);

CREATE INDEX idx_sessions_user ON sessions(user_id) WHERE revoked_at IS NULL;

-- =============================================================================
-- TAGS (Centralized Tag Management)
-- =============================================================================

CREATE TABLE tags (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id),

    name            VARCHAR(100) NOT NULL,
    color           VARCHAR(7) DEFAULT '#6366f1',  -- Hex color
    description     TEXT,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(organization_id, name)
);

CREATE INDEX idx_tags_org ON tags(organization_id);


-- =============================================================================
-- VIEWS FOR COMMON QUERIES
-- =============================================================================

-- Active decisions with their current version content
CREATE VIEW active_decisions AS
SELECT
    d.id,
    d.organization_id,
    d.decision_number,
    d.status,
    d.owner_team_id,
    d.created_by,
    d.created_at,
    dv.id AS current_version_id,
    dv.version_number,
    dv.title,
    dv.impact_level,
    dv.content,
    dv.tags,
    dv.created_by AS version_created_by,
    dv.created_at AS version_created_at
FROM decisions d
JOIN decision_versions dv ON d.current_version_id = dv.id
WHERE d.deleted_at IS NULL
  AND d.status NOT IN ('superseded', 'deprecated');

-- Decision with its supersession chain
CREATE VIEW decision_lineage AS
WITH RECURSIVE lineage AS (
    -- Base case: decisions that supersede something
    SELECT
        dr.source_decision_id AS decision_id,
        dr.target_decision_id AS supersedes_id,
        1 AS depth,
        ARRAY[dr.source_decision_id] AS path
    FROM decision_relationships dr
    WHERE dr.relationship_type = 'supersedes'
      AND dr.invalidated_at IS NULL

    UNION ALL

    -- Recursive case: follow the chain
    SELECT
        l.decision_id,
        dr.target_decision_id,
        l.depth + 1,
        l.path || dr.source_decision_id
    FROM lineage l
    JOIN decision_relationships dr ON dr.source_decision_id = l.supersedes_id
    WHERE dr.relationship_type = 'supersedes'
      AND dr.invalidated_at IS NULL
      AND NOT dr.source_decision_id = ANY(l.path)  -- Prevent cycles
      AND l.depth < 100  -- Safety limit
)
SELECT * FROM lineage;

-- Pending approvals for a user
CREATE VIEW pending_approvals AS
SELECT
    rr.id AS reviewer_assignment_id,
    rr.decision_version_id,
    rr.user_id AS reviewer_id,
    d.id AS decision_id,
    d.decision_number,
    dv.title,
    dv.version_number,
    dv.created_at AS version_created_at,
    u.name AS author_name
FROM required_reviewers rr
JOIN decision_versions dv ON rr.decision_version_id = dv.id
JOIN decisions d ON dv.decision_id = d.id
JOIN users u ON dv.created_by = u.id
LEFT JOIN approvals a ON a.decision_version_id = rr.decision_version_id
                      AND a.user_id = rr.user_id
WHERE a.id IS NULL  -- No approval yet
  AND d.status = 'pending_review'
  AND d.deleted_at IS NULL;


-- =============================================================================
-- FUNCTIONS
-- =============================================================================

-- Function to create a new decision version (enforces immutability)
CREATE OR REPLACE FUNCTION create_decision_version(
    p_decision_id UUID,
    p_title VARCHAR(500),
    p_impact_level impact_level,
    p_content JSONB,
    p_tags TEXT[],
    p_created_by UUID,
    p_change_summary TEXT DEFAULT NULL
) RETURNS UUID AS $$
DECLARE
    v_version_number INTEGER;
    v_version_id UUID;
    v_content_hash VARCHAR(64);
BEGIN
    -- Get next version number
    SELECT COALESCE(MAX(version_number), 0) + 1 INTO v_version_number
    FROM decision_versions
    WHERE decision_id = p_decision_id;

    -- Calculate content hash for integrity
    v_content_hash := encode(
        digest(
            p_title || p_content::text || COALESCE(array_to_string(p_tags, ','), ''),
            'sha256'
        ),
        'hex'
    );

    -- Insert new version (this is append-only)
    INSERT INTO decision_versions (
        decision_id, version_number, title, impact_level,
        content, tags, created_by, change_summary, content_hash
    ) VALUES (
        p_decision_id, v_version_number, p_title, p_impact_level,
        p_content, p_tags, p_created_by, p_change_summary, v_content_hash
    ) RETURNING id INTO v_version_id;

    -- Update decision's current version pointer
    UPDATE decisions
    SET current_version_id = v_version_id
    WHERE id = p_decision_id;

    RETURN v_version_id;
END;
$$ LANGUAGE plpgsql;


-- Function to supersede a decision
CREATE OR REPLACE FUNCTION supersede_decision(
    p_new_decision_id UUID,
    p_old_decision_id UUID,
    p_user_id UUID,
    p_description TEXT DEFAULT NULL
) RETURNS UUID AS $$
DECLARE
    v_relationship_id UUID;
BEGIN
    -- Create supersedes relationship
    INSERT INTO decision_relationships (
        source_decision_id, target_decision_id,
        relationship_type, description, created_by
    ) VALUES (
        p_new_decision_id, p_old_decision_id,
        'supersedes', p_description, p_user_id
    ) RETURNING id INTO v_relationship_id;

    -- Mark old decision as superseded
    UPDATE decisions
    SET status = 'superseded'
    WHERE id = p_old_decision_id;

    RETURN v_relationship_id;
END;
$$ LANGUAGE plpgsql;


-- Function to get the current active decision that supersedes a given decision
-- This traverses the supersession chain to find the "latest" version
CREATE OR REPLACE FUNCTION get_current_decision(p_decision_id UUID)
RETURNS UUID AS $$
DECLARE
    v_current_id UUID := p_decision_id;
    v_next_id UUID;
    v_depth INTEGER := 0;
BEGIN
    LOOP
        -- Find if anything supersedes the current decision
        SELECT source_decision_id INTO v_next_id
        FROM decision_relationships
        WHERE target_decision_id = v_current_id
          AND relationship_type = 'supersedes'
          AND invalidated_at IS NULL
        LIMIT 1;

        -- If nothing supersedes it, we found the current version
        IF v_next_id IS NULL THEN
            RETURN v_current_id;
        END IF;

        v_current_id := v_next_id;
        v_depth := v_depth + 1;

        -- Safety valve
        IF v_depth > 100 THEN
            RAISE EXCEPTION 'Supersession chain too deep - possible cycle detected';
        END IF;
    END LOOP;
END;
$$ LANGUAGE plpgsql;


-- Function to check if a decision is fully approved
CREATE OR REPLACE FUNCTION is_decision_approved(p_version_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    v_required_count INTEGER;
    v_approved_count INTEGER;
BEGIN
    -- Count required reviewers
    SELECT COUNT(*) INTO v_required_count
    FROM required_reviewers
    WHERE decision_version_id = p_version_id;

    -- Count approvals
    SELECT COUNT(*) INTO v_approved_count
    FROM approvals
    WHERE decision_version_id = p_version_id
      AND status = 'approved';

    -- All required reviewers must approve
    RETURN v_required_count > 0 AND v_approved_count >= v_required_count;
END;
$$ LANGUAGE plpgsql;


-- =============================================================================
-- TRIGGERS
-- =============================================================================

-- Prevent updates to decision_versions (immutability enforcement)
CREATE OR REPLACE FUNCTION prevent_version_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Decision versions are immutable and cannot be updated';
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER enforce_version_immutability
    BEFORE UPDATE ON decision_versions
    FOR EACH ROW
    EXECUTE FUNCTION prevent_version_update();

-- Prevent deletion of decision_versions (audit trail preservation)
CREATE OR REPLACE FUNCTION prevent_version_delete()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Decision versions cannot be deleted for audit compliance';
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER enforce_version_no_delete
    BEFORE DELETE ON decision_versions
    FOR EACH ROW
    EXECUTE FUNCTION prevent_version_delete();

-- Prevent deletion of audit_log entries
CREATE OR REPLACE FUNCTION prevent_audit_delete()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Audit log entries cannot be deleted';
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER enforce_audit_no_delete
    BEFORE DELETE ON audit_log
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_delete();

-- Prevent updates to audit_log entries
CREATE TRIGGER enforce_audit_no_update
    BEFORE UPDATE ON audit_log
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_delete();

-- Auto-update decision status when approved
CREATE OR REPLACE FUNCTION check_approval_status()
RETURNS TRIGGER AS $$
DECLARE
    v_decision_id UUID;
    v_version_id UUID;
BEGIN
    v_version_id := NEW.decision_version_id;

    SELECT decision_id INTO v_decision_id
    FROM decision_versions
    WHERE id = v_version_id;

    -- Check if this approval completes the required approvals
    IF is_decision_approved(v_version_id) THEN
        UPDATE decisions
        SET status = 'approved'
        WHERE id = v_decision_id
          AND status = 'pending_review';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER auto_approve_decision
    AFTER INSERT ON approvals
    FOR EACH ROW
    WHEN (NEW.status = 'approved')
    EXECUTE FUNCTION check_approval_status();
