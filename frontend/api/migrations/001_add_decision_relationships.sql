-- Migration: Add decision_relationships table for mind map visualization
-- Run this migration against your PostgreSQL database

-- Create relationship type enum if it doesn't exist
DO $$ BEGIN
    CREATE TYPE relationship_type AS ENUM (
        'influenced_by',
        'led_to',
        'related_to',
        'supersedes',
        'conflicts_with',
        'blocked_by',
        'implements'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create the decision_relationships table
CREATE TABLE IF NOT EXISTS decision_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    source_decision_id UUID NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
    target_decision_id UUID NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
    relationship_type relationship_type NOT NULL,
    description TEXT,
    confidence_score FLOAT,
    is_ai_generated BOOLEAN DEFAULT true,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP,

    -- Prevent self-references
    CONSTRAINT no_self_reference CHECK (source_decision_id != target_decision_id),

    -- Unique constraint for relationship type between two decisions
    CONSTRAINT unique_relationship UNIQUE (source_decision_id, target_decision_id, relationship_type)
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_decision_relationships_org ON decision_relationships(organization_id);
CREATE INDEX IF NOT EXISTS idx_decision_relationships_source ON decision_relationships(source_decision_id);
CREATE INDEX IF NOT EXISTS idx_decision_relationships_target ON decision_relationships(target_decision_id);
CREATE INDEX IF NOT EXISTS idx_decision_relationships_type ON decision_relationships(relationship_type);

-- Add comment for documentation
COMMENT ON TABLE decision_relationships IS 'Stores relationships between decisions for mind map visualization. Supports both AI-generated and user-created relationships.';
