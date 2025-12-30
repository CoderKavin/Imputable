-- Migration 004: Add Member Status and Invitations
--
-- This migration adds:
-- 1. status field to organization_members (active/inactive)
-- 2. slack_user_id field to users table for Slack integration
-- 3. invitations table for email-based invites
-- 4. Helper functions for plan limits
--
-- Run with: psql $DATABASE_URL -f 004_add_member_status_and_invitations.sql

-- =============================================================================
-- ADD STATUS TO ORGANIZATION_MEMBERS
-- =============================================================================

-- Add status column with default 'active'
ALTER TABLE organization_members
ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'active';

-- Add constraint for valid status values
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_organization_members_status'
    ) THEN
        ALTER TABLE organization_members
        ADD CONSTRAINT chk_organization_members_status
        CHECK (status IN ('active', 'inactive'));
    END IF;
END $$;

-- Index for quickly finding active members
CREATE INDEX IF NOT EXISTS idx_org_members_active
ON organization_members(organization_id, status)
WHERE status = 'active';

COMMENT ON COLUMN organization_members.status IS
'Member status: active (can use Imputable) or inactive (imported but blocked until activated or plan upgraded)';

-- =============================================================================
-- ADD SLACK_USER_ID TO USERS
-- =============================================================================

-- Add slack_user_id for linking Slack users to Imputable users
ALTER TABLE users
ADD COLUMN IF NOT EXISTS slack_user_id VARCHAR(50);

-- Index for finding users by Slack ID
CREATE INDEX IF NOT EXISTS idx_users_slack_user_id
ON users(slack_user_id)
WHERE slack_user_id IS NOT NULL AND deleted_at IS NULL;

COMMENT ON COLUMN users.slack_user_id IS
'Slack user ID (e.g., U12345678) for linking Slack users to Imputable accounts';

-- =============================================================================
-- INVITATIONS TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS invitations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email           VARCHAR(255) NOT NULL,
    role            VARCHAR(20) NOT NULL DEFAULT 'member',
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    token           VARCHAR(100) NOT NULL UNIQUE,
    invited_by      UUID NOT NULL REFERENCES users(id),
    accepted_at     TIMESTAMPTZ,
    accepted_by     UUID REFERENCES users(id),
    expires_at      TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT chk_invitations_role CHECK (role IN ('member', 'admin')),
    CONSTRAINT chk_invitations_status CHECK (status IN ('pending', 'accepted', 'expired', 'cancelled')),

    -- One pending invite per email per org
    CONSTRAINT uq_invitations_pending_email UNIQUE (organization_id, email, status)
);

-- Drop the unique constraint that prevents multiple invites (we want to allow re-invites)
-- Instead, we'll handle duplicates in application logic
ALTER TABLE invitations DROP CONSTRAINT IF EXISTS uq_invitations_pending_email;

-- Index for looking up invites by token
CREATE INDEX IF NOT EXISTS idx_invitations_token
ON invitations(token)
WHERE status = 'pending';

-- Index for listing org invites
CREATE INDEX IF NOT EXISTS idx_invitations_org
ON invitations(organization_id, status, created_at DESC);

-- Index for finding invites by email
CREATE INDEX IF NOT EXISTS idx_invitations_email
ON invitations(email, status)
WHERE status = 'pending';

COMMENT ON TABLE invitations IS
'Email invitations for users to join organizations (used when Slack is not connected)';

-- =============================================================================
-- HELPER FUNCTIONS
-- =============================================================================

-- Function to get active member count for an organization
CREATE OR REPLACE FUNCTION get_active_member_count(p_organization_id UUID)
RETURNS INTEGER AS $$
BEGIN
    RETURN (
        SELECT COUNT(*)::INTEGER
        FROM organization_members
        WHERE organization_id = p_organization_id
        AND status = 'active'
    );
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_active_member_count IS
'Returns the count of active members in an organization for plan limit enforcement';

-- Function to get plan member limit
CREATE OR REPLACE FUNCTION get_plan_member_limit(p_subscription_tier VARCHAR)
RETURNS INTEGER AS $$
BEGIN
    RETURN CASE p_subscription_tier
        WHEN 'free' THEN 5
        WHEN 'starter' THEN 20
        WHEN 'professional' THEN -1  -- unlimited
        WHEN 'enterprise' THEN -1    -- unlimited
        ELSE 5  -- default to free tier
    END;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_plan_member_limit IS
'Returns the maximum active members allowed for a subscription tier (-1 = unlimited)';

-- Function to check if org can add active members
CREATE OR REPLACE FUNCTION can_add_active_member(p_organization_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    v_tier VARCHAR;
    v_limit INTEGER;
    v_current INTEGER;
BEGIN
    -- Get org's subscription tier
    SELECT COALESCE(subscription_tier, 'free') INTO v_tier
    FROM organizations
    WHERE id = p_organization_id;

    -- Get limit for tier
    v_limit := get_plan_member_limit(v_tier);

    -- Unlimited
    IF v_limit = -1 THEN
        RETURN TRUE;
    END IF;

    -- Get current count
    v_current := get_active_member_count(p_organization_id);

    RETURN v_current < v_limit;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION can_add_active_member IS
'Checks if an organization can add another active member based on their plan';

-- =============================================================================
-- DOCUMENTATION
-- =============================================================================

COMMENT ON COLUMN organization_members.role IS
'Member role: owner (full control + billing), admin (manage members + settings), member (use Imputable)';

-- Add helpful comment to organizations table about member limits
COMMENT ON COLUMN organizations.subscription_tier IS
'Subscription tier determines member limits: free (5), starter (20), professional/enterprise (unlimited)';
