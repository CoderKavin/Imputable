-- =============================================================================
-- ROW LEVEL SECURITY (Multi-Tenancy Isolation)
-- =============================================================================
-- This file implements strict organization-level data isolation using PostgreSQL RLS.
-- Every query automatically filters to the user's organization context.

-- =============================================================================
-- APPLICATION ROLE SETUP
-- =============================================================================

-- Create an application role that will be used by the API
-- (Run as superuser during initial setup)

-- DROP ROLE IF EXISTS decision_ledger_app;
-- CREATE ROLE decision_ledger_app WITH LOGIN PASSWORD 'your-secure-password';

-- Grant necessary permissions
-- GRANT USAGE ON SCHEMA public TO decision_ledger_app;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO decision_ledger_app;
-- GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO decision_ledger_app;

-- =============================================================================
-- SESSION CONTEXT VARIABLES
-- =============================================================================
-- The application sets these at the start of each request/transaction

-- Set organization context:
-- SET LOCAL app.current_organization_id = 'uuid-here';

-- Set user context:
-- SET LOCAL app.current_user_id = 'uuid-here';

-- Helper function to get current org (safely handles unset variable)
CREATE OR REPLACE FUNCTION current_org_id()
RETURNS UUID AS $$
BEGIN
    RETURN NULLIF(current_setting('app.current_organization_id', TRUE), '')::UUID;
EXCEPTION
    WHEN OTHERS THEN
        RETURN NULL;
END;
$$ LANGUAGE plpgsql STABLE;

-- Helper function to get current user
CREATE OR REPLACE FUNCTION current_app_user_id()
RETURNS UUID AS $$
BEGIN
    RETURN NULLIF(current_setting('app.current_user_id', TRUE), '')::UUID;
EXCEPTION
    WHEN OTHERS THEN
        RETURN NULL;
END;
$$ LANGUAGE plpgsql STABLE;

-- Helper to check if user is org member
CREATE OR REPLACE FUNCTION is_org_member(org_id UUID, user_id UUID)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM organization_members
        WHERE organization_id = org_id
          AND organization_members.user_id = is_org_member.user_id
    );
END;
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;

-- Helper to check user's org role
CREATE OR REPLACE FUNCTION get_org_role(org_id UUID, user_id UUID)
RETURNS VARCHAR AS $$
DECLARE
    v_role VARCHAR;
BEGIN
    SELECT role INTO v_role
    FROM organization_members
    WHERE organization_id = org_id
      AND organization_members.user_id = get_org_role.user_id;
    RETURN v_role;
END;
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;


-- =============================================================================
-- ENABLE RLS ON ALL TENANT-SCOPED TABLES
-- =============================================================================

ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE decision_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE decision_relationships ENABLE ROW LEVEL SECURITY;
ALTER TABLE approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE required_reviewers ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE tags ENABLE ROW LEVEL SECURITY;

-- Users table is special - no org isolation, but still protected
ALTER TABLE users ENABLE ROW LEVEL SECURITY;


-- =============================================================================
-- ORGANIZATIONS POLICIES
-- =============================================================================

-- Users can only see organizations they belong to
CREATE POLICY org_member_select ON organizations
    FOR SELECT
    USING (
        id = current_org_id()
        OR EXISTS (
            SELECT 1 FROM organization_members
            WHERE organization_id = organizations.id
              AND user_id = current_app_user_id()
        )
    );

-- Only org owners can update their org
CREATE POLICY org_owner_update ON organizations
    FOR UPDATE
    USING (
        get_org_role(id, current_app_user_id()) = 'owner'
    );


-- =============================================================================
-- ORGANIZATION MEMBERS POLICIES
-- =============================================================================

-- Members can see other members in their org
CREATE POLICY org_members_select ON organization_members
    FOR SELECT
    USING (
        organization_id = current_org_id()
        OR is_org_member(organization_id, current_app_user_id())
    );

-- Only admins/owners can add members
CREATE POLICY org_members_insert ON organization_members
    FOR INSERT
    WITH CHECK (
        get_org_role(organization_id, current_app_user_id()) IN ('owner', 'admin')
    );

-- Only admins/owners can modify memberships (except owners can't demote themselves)
CREATE POLICY org_members_update ON organization_members
    FOR UPDATE
    USING (
        get_org_role(organization_id, current_app_user_id()) IN ('owner', 'admin')
    );


-- =============================================================================
-- TEAMS POLICIES
-- =============================================================================

-- Teams visible within organization
CREATE POLICY teams_org_isolation ON teams
    FOR SELECT
    USING (organization_id = current_org_id());

CREATE POLICY teams_insert ON teams
    FOR INSERT
    WITH CHECK (
        organization_id = current_org_id()
        AND get_org_role(organization_id, current_app_user_id()) IN ('owner', 'admin')
    );

CREATE POLICY teams_update ON teams
    FOR UPDATE
    USING (
        organization_id = current_org_id()
        AND get_org_role(organization_id, current_app_user_id()) IN ('owner', 'admin')
    );


-- =============================================================================
-- TEAM MEMBERS POLICIES
-- =============================================================================

CREATE POLICY team_members_select ON team_members
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM teams
            WHERE teams.id = team_members.team_id
              AND teams.organization_id = current_org_id()
        )
    );

CREATE POLICY team_members_insert ON team_members
    FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM teams
            WHERE teams.id = team_members.team_id
              AND teams.organization_id = current_org_id()
              AND get_org_role(teams.organization_id, current_app_user_id()) IN ('owner', 'admin')
        )
    );


-- =============================================================================
-- DECISIONS POLICIES (Core Business Logic)
-- =============================================================================

-- All org members can view decisions
CREATE POLICY decisions_org_isolation ON decisions
    FOR SELECT
    USING (organization_id = current_org_id());

-- All org members can create decisions
CREATE POLICY decisions_insert ON decisions
    FOR INSERT
    WITH CHECK (
        organization_id = current_org_id()
        AND is_org_member(organization_id, current_app_user_id())
    );

-- Only the creator, team owner, or admins can update decision status
CREATE POLICY decisions_update ON decisions
    FOR UPDATE
    USING (
        organization_id = current_org_id()
        AND (
            created_by = current_app_user_id()
            OR get_org_role(organization_id, current_app_user_id()) IN ('owner', 'admin')
            OR EXISTS (
                SELECT 1 FROM team_members tm
                JOIN teams t ON tm.team_id = t.id
                WHERE t.id = decisions.owner_team_id
                  AND tm.user_id = current_app_user_id()
                  AND tm.role = 'lead'
            )
        )
    );

-- Soft delete only - no hard deletes allowed
CREATE POLICY decisions_no_delete ON decisions
    FOR DELETE
    USING (FALSE);  -- Always deny


-- =============================================================================
-- DECISION VERSIONS POLICIES
-- =============================================================================

-- All org members can view versions
CREATE POLICY versions_org_isolation ON decision_versions
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM decisions
            WHERE decisions.id = decision_versions.decision_id
              AND decisions.organization_id = current_org_id()
        )
    );

-- Any org member can create a new version (of an existing decision they can see)
CREATE POLICY versions_insert ON decision_versions
    FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM decisions
            WHERE decisions.id = decision_versions.decision_id
              AND decisions.organization_id = current_org_id()
        )
        AND created_by = current_app_user_id()
    );

-- No updates or deletes (enforced by triggers, but RLS adds another layer)
CREATE POLICY versions_no_update ON decision_versions
    FOR UPDATE
    USING (FALSE);

CREATE POLICY versions_no_delete ON decision_versions
    FOR DELETE
    USING (FALSE);


-- =============================================================================
-- DECISION RELATIONSHIPS POLICIES
-- =============================================================================

CREATE POLICY relationships_select ON decision_relationships
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM decisions
            WHERE decisions.id = decision_relationships.source_decision_id
              AND decisions.organization_id = current_org_id()
        )
    );

CREATE POLICY relationships_insert ON decision_relationships
    FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM decisions d1
            JOIN decisions d2 ON d1.organization_id = d2.organization_id
            WHERE d1.id = decision_relationships.source_decision_id
              AND d2.id = decision_relationships.target_decision_id
              AND d1.organization_id = current_org_id()
        )
        AND created_by = current_app_user_id()
    );

-- Can only invalidate, not delete
CREATE POLICY relationships_update ON decision_relationships
    FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM decisions
            WHERE decisions.id = decision_relationships.source_decision_id
              AND decisions.organization_id = current_org_id()
        )
    );


-- =============================================================================
-- APPROVALS POLICIES
-- =============================================================================

CREATE POLICY approvals_select ON approvals
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM decision_versions dv
            JOIN decisions d ON dv.decision_id = d.id
            WHERE dv.id = approvals.decision_version_id
              AND d.organization_id = current_org_id()
        )
    );

-- Users can only create approvals for themselves
CREATE POLICY approvals_insert ON approvals
    FOR INSERT
    WITH CHECK (
        user_id = current_app_user_id()
        AND EXISTS (
            SELECT 1 FROM decision_versions dv
            JOIN decisions d ON dv.decision_id = d.id
            WHERE dv.id = approvals.decision_version_id
              AND d.organization_id = current_org_id()
        )
    );

-- No updates to approvals (immutable)
CREATE POLICY approvals_no_update ON approvals
    FOR UPDATE
    USING (FALSE);


-- =============================================================================
-- REQUIRED REVIEWERS POLICIES
-- =============================================================================

CREATE POLICY reviewers_select ON required_reviewers
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM decision_versions dv
            JOIN decisions d ON dv.decision_id = d.id
            WHERE dv.id = required_reviewers.decision_version_id
              AND d.organization_id = current_org_id()
        )
    );

CREATE POLICY reviewers_insert ON required_reviewers
    FOR INSERT
    WITH CHECK (
        added_by = current_app_user_id()
        AND EXISTS (
            SELECT 1 FROM decision_versions dv
            JOIN decisions d ON dv.decision_id = d.id
            WHERE dv.id = required_reviewers.decision_version_id
              AND d.organization_id = current_org_id()
        )
    );


-- =============================================================================
-- AUDIT LOG POLICIES
-- =============================================================================

-- Only org admins/owners can view audit logs
CREATE POLICY audit_admin_only ON audit_log
    FOR SELECT
    USING (
        organization_id = current_org_id()
        AND get_org_role(current_org_id(), current_app_user_id()) IN ('owner', 'admin')
    );

-- System can always insert (via SECURITY DEFINER function)
CREATE POLICY audit_insert ON audit_log
    FOR INSERT
    WITH CHECK (organization_id = current_org_id());

-- No updates or deletes (triggers also enforce this)
CREATE POLICY audit_no_update ON audit_log
    FOR UPDATE
    USING (FALSE);

CREATE POLICY audit_no_delete ON audit_log
    FOR DELETE
    USING (FALSE);


-- =============================================================================
-- USERS POLICIES
-- =============================================================================

-- Users can see other users in their organizations
CREATE POLICY users_org_visibility ON users
    FOR SELECT
    USING (
        id = current_app_user_id()
        OR EXISTS (
            SELECT 1 FROM organization_members om1
            JOIN organization_members om2 ON om1.organization_id = om2.organization_id
            WHERE om1.user_id = current_app_user_id()
              AND om2.user_id = users.id
        )
    );

-- Users can only update themselves
CREATE POLICY users_self_update ON users
    FOR UPDATE
    USING (id = current_app_user_id());


-- =============================================================================
-- TAGS POLICIES
-- =============================================================================

CREATE POLICY tags_org_isolation ON tags
    FOR SELECT
    USING (organization_id = current_org_id());

CREATE POLICY tags_insert ON tags
    FOR INSERT
    WITH CHECK (
        organization_id = current_org_id()
        AND is_org_member(organization_id, current_app_user_id())
    );


-- =============================================================================
-- BYPASS FOR SERVICE ROLE (migrations, admin tasks)
-- =============================================================================

-- Create a service role that bypasses RLS (use sparingly!)
-- CREATE ROLE decision_ledger_service BYPASSRLS;
-- GRANT decision_ledger_service TO decision_ledger_app;

-- For maintenance operations, the app can do:
-- SET ROLE decision_ledger_service;
-- ... do admin stuff ...
-- RESET ROLE;
