-- =============================================================================
-- SUPERSESSION LOGIC: Efficient Queries for Decision Graphs
-- =============================================================================
-- This file documents the supersession pattern and provides optimized queries
-- for common access patterns.

-- =============================================================================
-- THE SUPERSESSION MODEL
-- =============================================================================
--
-- Decision A (approved) ─────superseded by────▶ Decision B (approved) ─────superseded by────▶ Decision C (current)
--                                                        │
--                                                        └──── Decision D (branches off, also current)
--
-- Key Concepts:
-- 1. A decision can be superseded by ONE OR MORE decisions (branching)
-- 2. A decision can supersede ONE OR MORE decisions (consolidation)
-- 3. The "current" decision is one that has NOT been superseded
-- 4. Status 'superseded' is set automatically when a supersession relationship is created
--
-- Performance Strategy:
-- - Use indexes on (target_decision_id, relationship_type) for "who supersedes me?" queries
-- - Use indexes on (source_decision_id, relationship_type) for "who do I supersede?" queries
-- - For deep chains, use recursive CTEs with depth limits
-- - Cache the "current version" pointer for frequently accessed decisions


-- =============================================================================
-- INDEX OPTIMIZATION FOR SUPERSESSION QUERIES
-- =============================================================================

-- Fast lookup: "What supersedes this decision?"
CREATE INDEX IF NOT EXISTS idx_supersedes_target
ON decision_relationships(target_decision_id)
WHERE relationship_type = 'supersedes' AND invalidated_at IS NULL;

-- Fast lookup: "What does this decision supersede?"
CREATE INDEX IF NOT EXISTS idx_supersedes_source
ON decision_relationships(source_decision_id)
WHERE relationship_type = 'supersedes' AND invalidated_at IS NULL;

-- Combined index for graph traversal
CREATE INDEX IF NOT EXISTS idx_supersedes_both
ON decision_relationships(source_decision_id, target_decision_id)
WHERE relationship_type = 'supersedes' AND invalidated_at IS NULL;


-- =============================================================================
-- QUERY 1: Get the Current Active Decision for a Given Decision
-- =============================================================================
-- Use case: User clicks on old decision, show them the current version
-- Time complexity: O(depth of chain), typically O(1-3)

-- Option A: Using the stored function (simplest)
-- SELECT get_current_decision('decision-uuid-here');

-- Option B: Direct query (avoids function call overhead)
WITH RECURSIVE current_finder AS (
    -- Start with the given decision
    SELECT
        id AS original_id,
        id AS current_id,
        0 AS depth
    FROM decisions
    WHERE id = 'decision-uuid-here'::uuid

    UNION ALL

    -- Follow the supersession chain forward
    SELECT
        cf.original_id,
        dr.source_decision_id AS current_id,
        cf.depth + 1
    FROM current_finder cf
    JOIN decision_relationships dr ON dr.target_decision_id = cf.current_id
    WHERE dr.relationship_type = 'supersedes'
      AND dr.invalidated_at IS NULL
      AND cf.depth < 100  -- Safety limit
)
SELECT current_id
FROM current_finder
ORDER BY depth DESC
LIMIT 1;


-- =============================================================================
-- QUERY 2: Get Full History Chain (All Ancestors)
-- =============================================================================
-- Use case: Show "This decision evolved from: A → B → C → Current"
-- Returns the chain in order from oldest to newest

WITH RECURSIVE history AS (
    -- Start with the current decision
    SELECT
        d.id,
        d.decision_number,
        dv.title,
        dv.version_number,
        d.status,
        d.created_at,
        0 AS chain_position,
        ARRAY[d.id] AS path
    FROM decisions d
    JOIN decision_versions dv ON d.current_version_id = dv.id
    WHERE d.id = 'current-decision-uuid'::uuid

    UNION ALL

    -- Go backwards: find what this decision supersedes
    SELECT
        d.id,
        d.decision_number,
        dv.title,
        dv.version_number,
        d.status,
        d.created_at,
        h.chain_position + 1,
        h.path || d.id
    FROM history h
    JOIN decision_relationships dr ON dr.source_decision_id = h.id
    JOIN decisions d ON dr.target_decision_id = d.id
    JOIN decision_versions dv ON d.current_version_id = dv.id
    WHERE dr.relationship_type = 'supersedes'
      AND dr.invalidated_at IS NULL
      AND NOT d.id = ANY(h.path)  -- Prevent cycles
      AND h.chain_position < 100
)
SELECT * FROM history
ORDER BY chain_position DESC;  -- Oldest first


-- =============================================================================
-- QUERY 3: Get All Current (Non-Superseded) Decisions
-- =============================================================================
-- Use case: Dashboard showing all active decisions
-- This is the MOST COMMON query - optimize it heavily

-- Strategy: Use NOT EXISTS (generally faster than LEFT JOIN for this pattern)

SELECT
    d.id,
    d.decision_number,
    d.status,
    d.created_at,
    dv.title,
    dv.impact_level,
    dv.tags,
    t.name AS team_name,
    u.name AS created_by_name
FROM decisions d
JOIN decision_versions dv ON d.current_version_id = dv.id
LEFT JOIN teams t ON d.owner_team_id = t.id
LEFT JOIN users u ON d.created_by = u.id
WHERE d.organization_id = current_org_id()
  AND d.deleted_at IS NULL
  AND d.status NOT IN ('superseded', 'deprecated')
  -- Ensure nothing supersedes this decision
  AND NOT EXISTS (
      SELECT 1 FROM decision_relationships dr
      WHERE dr.target_decision_id = d.id
        AND dr.relationship_type = 'supersedes'
        AND dr.invalidated_at IS NULL
  )
ORDER BY d.created_at DESC;


-- =============================================================================
-- QUERY 4: Get Decisions That Block Another Decision
-- =============================================================================
-- Use case: Show "This decision is blocked by: X, Y, Z"

SELECT
    d.id,
    d.decision_number,
    dv.title,
    d.status,
    dr.description AS blocking_reason
FROM decision_relationships dr
JOIN decisions d ON dr.target_decision_id = d.id
JOIN decision_versions dv ON d.current_version_id = dv.id
WHERE dr.source_decision_id = 'blocked-decision-uuid'::uuid
  AND dr.relationship_type = 'blocked_by'
  AND dr.invalidated_at IS NULL
  AND d.deleted_at IS NULL;


-- =============================================================================
-- QUERY 5: Impact Analysis - What Depends on This Decision?
-- =============================================================================
-- Use case: Before deprecating a decision, show what would be affected

WITH RECURSIVE dependents AS (
    -- Direct dependents
    SELECT
        d.id,
        d.decision_number,
        dv.title,
        d.status,
        dr.relationship_type,
        1 AS distance
    FROM decision_relationships dr
    JOIN decisions d ON dr.source_decision_id = d.id
    JOIN decision_versions dv ON d.current_version_id = dv.id
    WHERE dr.target_decision_id = 'decision-to-deprecate'::uuid
      AND dr.invalidated_at IS NULL
      AND d.deleted_at IS NULL

    UNION

    -- Transitive dependents (decisions blocked by our dependents, etc.)
    SELECT
        d.id,
        d.decision_number,
        dv.title,
        d.status,
        dr.relationship_type,
        dep.distance + 1
    FROM dependents dep
    JOIN decision_relationships dr ON dr.target_decision_id = dep.id
    JOIN decisions d ON dr.source_decision_id = d.id
    JOIN decision_versions dv ON d.current_version_id = dv.id
    WHERE dr.invalidated_at IS NULL
      AND d.deleted_at IS NULL
      AND dep.distance < 10  -- Limit depth
)
SELECT DISTINCT ON (id) * FROM dependents
ORDER BY id, distance;


-- =============================================================================
-- QUERY 6: Decision Graph Visualization Data
-- =============================================================================
-- Use case: Build a visual graph of related decisions
-- Returns nodes and edges in a format suitable for D3.js or similar

-- Nodes (all decisions in the graph)
WITH RECURSIVE graph AS (
    -- Start from a focal decision
    SELECT id, 0 AS distance
    FROM decisions
    WHERE id = 'focal-decision-uuid'::uuid

    UNION

    -- Expand in both directions
    SELECT
        CASE
            WHEN dr.source_decision_id = g.id THEN dr.target_decision_id
            ELSE dr.source_decision_id
        END AS id,
        g.distance + 1
    FROM graph g
    JOIN decision_relationships dr
        ON dr.source_decision_id = g.id OR dr.target_decision_id = g.id
    WHERE dr.invalidated_at IS NULL
      AND g.distance < 5  -- Limit radius
)
SELECT DISTINCT ON (d.id)
    d.id,
    d.decision_number,
    dv.title,
    d.status,
    dv.impact_level,
    g.distance
FROM graph g
JOIN decisions d ON g.id = d.id
JOIN decision_versions dv ON d.current_version_id = dv.id
WHERE d.deleted_at IS NULL;

-- Edges (all relationships between those nodes)
WITH RECURSIVE graph AS (
    SELECT id FROM decisions WHERE id = 'focal-decision-uuid'::uuid
    UNION
    SELECT
        CASE
            WHEN dr.source_decision_id = g.id THEN dr.target_decision_id
            ELSE dr.source_decision_id
        END
    FROM graph g
    JOIN decision_relationships dr
        ON dr.source_decision_id = g.id OR dr.target_decision_id = g.id
    WHERE dr.invalidated_at IS NULL
)
SELECT
    dr.id AS edge_id,
    dr.source_decision_id AS source,
    dr.target_decision_id AS target,
    dr.relationship_type AS type
FROM decision_relationships dr
WHERE dr.source_decision_id IN (SELECT id FROM graph)
  AND dr.target_decision_id IN (SELECT id FROM graph)
  AND dr.invalidated_at IS NULL;


-- =============================================================================
-- QUERY 7: Search with Supersession Awareness
-- =============================================================================
-- Use case: Full-text search that returns current versions only

SELECT
    d.id,
    d.decision_number,
    dv.title,
    d.status,
    dv.content->>'context' AS context_preview,
    ts_rank(
        to_tsvector('english', dv.title || ' ' || COALESCE(dv.content->>'context', '')),
        plainto_tsquery('english', 'search terms here')
    ) AS relevance
FROM decisions d
JOIN decision_versions dv ON d.current_version_id = dv.id
WHERE d.organization_id = current_org_id()
  AND d.deleted_at IS NULL
  AND d.status NOT IN ('superseded')  -- Include deprecated for historical search
  AND to_tsvector('english', dv.title || ' ' || COALESCE(dv.content->>'context', ''))
      @@ plainto_tsquery('english', 'search terms here')
ORDER BY relevance DESC, d.created_at DESC
LIMIT 20;


-- =============================================================================
-- MATERIALIZED VIEW: Current Decisions Cache
-- =============================================================================
-- For very high-traffic scenarios, materialize the "current decisions" query
-- Refresh periodically or on decision status changes

CREATE MATERIALIZED VIEW IF NOT EXISTS current_decisions_cache AS
SELECT
    d.id,
    d.organization_id,
    d.decision_number,
    d.status,
    d.owner_team_id,
    d.created_by,
    d.created_at,
    dv.id AS current_version_id,
    dv.title,
    dv.impact_level,
    dv.content,
    dv.tags,
    dv.created_at AS version_created_at
FROM decisions d
JOIN decision_versions dv ON d.current_version_id = dv.id
WHERE d.deleted_at IS NULL
  AND d.status NOT IN ('superseded', 'deprecated')
  AND NOT EXISTS (
      SELECT 1 FROM decision_relationships dr
      WHERE dr.target_decision_id = d.id
        AND dr.relationship_type = 'supersedes'
        AND dr.invalidated_at IS NULL
  );

CREATE UNIQUE INDEX ON current_decisions_cache(id);
CREATE INDEX ON current_decisions_cache(organization_id);
CREATE INDEX ON current_decisions_cache USING GIN(tags);

-- Refresh function (call after any supersession change)
CREATE OR REPLACE FUNCTION refresh_current_decisions_cache()
RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY current_decisions_cache;
END;
$$ LANGUAGE plpgsql;


-- =============================================================================
-- PERFORMANCE NOTES
-- =============================================================================
--
-- 1. Most queries are O(1) or O(n) where n is the result set size
-- 2. Supersession chain traversal is O(depth), typically 1-5 levels
-- 3. The recursive CTEs have depth limits to prevent runaway queries
-- 4. For large organizations (10k+ decisions), consider:
--    - Using the materialized view for dashboard queries
--    - Partitioning audit_log by month
--    - Adding a "current_successor_id" denormalized column
--
-- 5. Cycle detection: The path array in recursive CTEs prevents infinite loops
-- 6. The NOT EXISTS pattern for "current decisions" is index-friendly
