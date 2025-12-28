-- Migration 003: Add AI Analysis Support
--
-- This migration adds support for AI-generated decision records:
-- 1. Index for finding AI-generated decisions via custom_fields JSONB
-- 2. Comments documenting the AI metadata schema
--
-- The AI metadata is stored in decision_versions.custom_fields JSONB with:
-- {
--   "ai_generated": true,
--   "ai_confidence_score": 0.0-1.0,
--   "verified_by_user": true/false,
--   "verified_by_slack_user_id": "U123...",
--   "verified_by_teams_user_id": "..."
-- }
--
-- Run with: psql $DATABASE_URL -f 003_add_ai_analysis_support.sql

-- =============================================================================
-- AI-GENERATED DECISIONS INDEX
-- =============================================================================

-- Index for quickly finding AI-generated decisions
-- Uses JSONB containment operator for efficient filtering
CREATE INDEX IF NOT EXISTS idx_decision_versions_ai_generated
ON decision_versions USING gin (custom_fields jsonb_path_ops)
WHERE custom_fields @> '{"ai_generated": true}';

COMMENT ON INDEX idx_decision_versions_ai_generated IS
'Index for efficiently querying AI-generated decision versions';

-- =============================================================================
-- DOCUMENTATION: AI Metadata Schema in custom_fields
-- =============================================================================

COMMENT ON COLUMN decision_versions.custom_fields IS
'JSONB field for storing custom metadata including AI analysis results.

AI-Generated Decision Schema:
{
  "ai_generated": boolean,           -- Whether the content was AI-analyzed
  "ai_confidence_score": float,      -- AI confidence (0.0-1.0) in extraction accuracy
  "verified_by_user": boolean,       -- Whether a human reviewed the AI output
  "verified_by_slack_user_id": str,  -- Slack user ID who verified (if from Slack)
  "verified_by_teams_user_id": str   -- Teams user ID who verified (if from Teams)
}

The confidence score indicates:
- 0.9-1.0: Very clear decision with explicit consensus
- 0.7-0.9: Clear decision but some interpretation needed
- 0.5-0.7: Decision exists but context is incomplete
- 0.3-0.5: Possible decision, significant uncertainty
- 0.0-0.3: Very unclear, may not be a decision at all

When verified_by_user is true, the AI output was reviewed and potentially
edited by a human before saving, making the record more trustworthy.';

-- =============================================================================
-- HELPER FUNCTION: Get AI-generated decision stats
-- =============================================================================

CREATE OR REPLACE FUNCTION get_ai_decision_stats(p_organization_id UUID)
RETURNS TABLE (
    total_ai_decisions BIGINT,
    verified_count BIGINT,
    avg_confidence NUMERIC,
    high_confidence_count BIGINT,
    low_confidence_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*) AS total_ai_decisions,
        COUNT(*) FILTER (WHERE (custom_fields->>'verified_by_user')::boolean = true) AS verified_count,
        AVG((custom_fields->>'ai_confidence_score')::numeric) AS avg_confidence,
        COUNT(*) FILTER (WHERE (custom_fields->>'ai_confidence_score')::numeric >= 0.8) AS high_confidence_count,
        COUNT(*) FILTER (WHERE (custom_fields->>'ai_confidence_score')::numeric < 0.5) AS low_confidence_count
    FROM decision_versions dv
    JOIN decisions d ON d.current_version_id = dv.id
    WHERE d.organization_id = p_organization_id
      AND d.deleted_at IS NULL
      AND dv.custom_fields @> '{"ai_generated": true}';
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_ai_decision_stats IS
'Returns statistics about AI-generated decisions for an organization';
