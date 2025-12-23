-- Migration: Add Slack source tracking fields to decisions table
-- Date: 2025-12-23
-- Description: Adds source, slack_channel_id, slack_message_ts, slack_thread_ts columns
--              to enable "View in Slack" functionality

-- Add source column (default 'web' for existing decisions)
ALTER TABLE decisions
ADD COLUMN IF NOT EXISTS source VARCHAR(20) DEFAULT 'web';

COMMENT ON COLUMN decisions.source IS 'Origin of the decision: web, slack';

-- Add Slack-specific columns
ALTER TABLE decisions
ADD COLUMN IF NOT EXISTS slack_channel_id VARCHAR(50);

COMMENT ON COLUMN decisions.slack_channel_id IS 'Slack channel ID where decision was created';

ALTER TABLE decisions
ADD COLUMN IF NOT EXISTS slack_message_ts VARCHAR(50);

COMMENT ON COLUMN decisions.slack_message_ts IS 'Slack message timestamp for deep linking';

ALTER TABLE decisions
ADD COLUMN IF NOT EXISTS slack_thread_ts VARCHAR(50);

COMMENT ON COLUMN decisions.slack_thread_ts IS 'Slack thread timestamp if created in a thread';

-- Create index for finding Slack-created decisions
CREATE INDEX IF NOT EXISTS idx_decisions_source
ON decisions(source)
WHERE deleted_at IS NULL AND source = 'slack';
