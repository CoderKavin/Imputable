-- Migration 002: Add Teams Integration and Consensus Polling
--
-- This migration adds:
-- 1. Teams deep linking fields to decisions table
-- 2. Teams Bot Framework fields to organizations table
-- 3. Consensus polling votes table
-- 4. Message tracking table for duplicate detection
--
-- Run with: psql $DATABASE_URL -f 002_add_teams_and_polling.sql

-- =============================================================================
-- TEAMS DEEP LINKING (decisions table)
-- =============================================================================

-- Add Teams message tracking columns to decisions
ALTER TABLE decisions
ADD COLUMN IF NOT EXISTS teams_message_id VARCHAR(255);

COMMENT ON COLUMN decisions.teams_message_id IS 'Teams message ID for deep linking to source conversation';

ALTER TABLE decisions
ADD COLUMN IF NOT EXISTS teams_conversation_id VARCHAR(255);

COMMENT ON COLUMN decisions.teams_conversation_id IS 'Teams conversation/channel ID for deep linking';

-- Index for Teams lookups
CREATE INDEX IF NOT EXISTS idx_decisions_teams_message
ON decisions(teams_conversation_id, teams_message_id)
WHERE teams_message_id IS NOT NULL;

-- =============================================================================
-- TEAMS BOT FRAMEWORK (organizations table)
-- =============================================================================

-- Add Teams Bot registration fields to organizations
ALTER TABLE organizations
ADD COLUMN IF NOT EXISTS teams_tenant_id VARCHAR(255);

COMMENT ON COLUMN organizations.teams_tenant_id IS 'Azure AD tenant ID for Teams Bot authentication';

ALTER TABLE organizations
ADD COLUMN IF NOT EXISTS teams_bot_id VARCHAR(255);

COMMENT ON COLUMN organizations.teams_bot_id IS 'Teams Bot registration ID from Azure Bot Service';

ALTER TABLE organizations
ADD COLUMN IF NOT EXISTS teams_service_url TEXT;

COMMENT ON COLUMN organizations.teams_service_url IS 'Teams Bot Framework service URL for sending proactive messages';

-- =============================================================================
-- CONSENSUS POLLING
-- =============================================================================

-- Create enum for vote types if it doesn't exist
DO $$ BEGIN
    CREATE TYPE poll_vote_type AS ENUM ('agree', 'concern', 'block');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Create poll_votes table for tracking consensus poll responses
CREATE TABLE IF NOT EXISTS poll_votes (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    decision_id     UUID NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,

    -- Voter identification (one of user_id or external_user_id must be set)
    user_id         UUID REFERENCES users(id),              -- Internal Imputable user
    external_user_id VARCHAR(100),                          -- Slack user ID or Teams user ID
    external_user_name VARCHAR(255),                        -- Display name for external users

    -- Vote details
    vote_type       poll_vote_type NOT NULL,
    comment         TEXT,                                   -- Optional comment with vote

    -- Source tracking
    source          VARCHAR(20) NOT NULL DEFAULT 'slack',   -- 'slack' or 'teams'

    -- Timestamps
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints: one vote per user per decision
    -- For internal users
    CONSTRAINT uq_poll_votes_internal_user
        UNIQUE NULLS NOT DISTINCT (decision_id, user_id),
    -- For external users (by source to allow same ID across platforms)
    CONSTRAINT uq_poll_votes_external_user
        UNIQUE NULLS NOT DISTINCT (decision_id, external_user_id, source),
    -- Ensure at least one identifier is provided
    CONSTRAINT chk_poll_votes_user_identifier
        CHECK (user_id IS NOT NULL OR external_user_id IS NOT NULL)
);

-- Indexes for poll_votes
CREATE INDEX IF NOT EXISTS idx_poll_votes_decision ON poll_votes(decision_id);
CREATE INDEX IF NOT EXISTS idx_poll_votes_user ON poll_votes(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_poll_votes_external ON poll_votes(external_user_id, source) WHERE external_user_id IS NOT NULL;

-- Comment on table
COMMENT ON TABLE poll_votes IS 'Tracks votes from consensus polls in Slack/Teams. Each user can vote once per decision.';

-- =============================================================================
-- MESSAGE TRACKING (Duplicate Detection)
-- =============================================================================

-- Create logged_messages table to prevent duplicate logging of the same message
CREATE TABLE IF NOT EXISTS logged_messages (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Source message identifiers
    source          VARCHAR(20) NOT NULL,                   -- 'slack' or 'teams'
    message_id      VARCHAR(255) NOT NULL,                  -- Slack message_ts or Teams message ID
    channel_id      VARCHAR(255) NOT NULL,                  -- Channel/conversation ID

    -- Link to created decision
    decision_id     UUID NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,

    -- Timestamp
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Prevent duplicate logging of same message
    CONSTRAINT uq_logged_messages_source_message
        UNIQUE (source, message_id, channel_id)
);

-- Index for quick lookups
CREATE INDEX IF NOT EXISTS idx_logged_messages_lookup
ON logged_messages(source, message_id, channel_id);

CREATE INDEX IF NOT EXISTS idx_logged_messages_decision
ON logged_messages(decision_id);

-- Comment on table
COMMENT ON TABLE logged_messages IS 'Tracks which Slack/Teams messages have been logged as decisions to prevent duplicates.';

-- =============================================================================
-- HELPER FUNCTION: Get poll vote summary
-- =============================================================================

CREATE OR REPLACE FUNCTION get_poll_vote_summary(p_decision_id UUID)
RETURNS TABLE (
    agree_count BIGINT,
    concern_count BIGINT,
    block_count BIGINT,
    total_votes BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*) FILTER (WHERE vote_type = 'agree') AS agree_count,
        COUNT(*) FILTER (WHERE vote_type = 'concern') AS concern_count,
        COUNT(*) FILTER (WHERE vote_type = 'block') AS block_count,
        COUNT(*) AS total_votes
    FROM poll_votes
    WHERE poll_votes.decision_id = p_decision_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_poll_vote_summary IS 'Returns vote counts for a decision consensus poll';
