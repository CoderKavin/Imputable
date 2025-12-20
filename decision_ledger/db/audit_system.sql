-- =============================================================================
-- AUDIT LOGGING SYSTEM
-- =============================================================================
-- Comprehensive audit trail for compliance requirements.
-- Every read/write action is logged with full context.

-- =============================================================================
-- AUDIT LOGGING FUNCTION (Core)
-- =============================================================================

-- Central function to log audit events (SECURITY DEFINER to bypass RLS for logging)
CREATE OR REPLACE FUNCTION log_audit_event(
    p_action audit_action,
    p_resource_type VARCHAR(50),
    p_resource_id UUID,
    p_details JSONB DEFAULT '{}'
) RETURNS UUID AS $$
DECLARE
    v_org_id UUID;
    v_user_id UUID;
    v_audit_id UUID;
    v_previous_hash VARCHAR(64);
    v_entry_hash VARCHAR(64);
BEGIN
    v_org_id := current_org_id();
    v_user_id := current_app_user_id();

    -- Get hash of the most recent audit entry for this org (chain integrity)
    SELECT entry_hash INTO v_previous_hash
    FROM audit_log
    WHERE organization_id = v_org_id
    ORDER BY created_at DESC
    LIMIT 1;

    -- Generate unique ID
    v_audit_id := uuid_generate_v4();

    -- Calculate entry hash (includes previous hash for chain)
    v_entry_hash := encode(
        digest(
            v_audit_id::text ||
            COALESCE(v_org_id::text, '') ||
            COALESCE(v_user_id::text, '') ||
            p_action::text ||
            p_resource_type ||
            p_resource_id::text ||
            p_details::text ||
            COALESCE(v_previous_hash, 'genesis'),
            'sha256'
        ),
        'hex'
    );

    INSERT INTO audit_log (
        id, organization_id, user_id, action,
        resource_type, resource_id, details,
        previous_hash, entry_hash
    ) VALUES (
        v_audit_id, v_org_id, v_user_id, p_action,
        p_resource_type, p_resource_id, p_details,
        v_previous_hash, v_entry_hash
    );

    RETURN v_audit_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;


-- =============================================================================
-- AUTOMATIC AUDIT TRIGGERS
-- =============================================================================

-- Generic audit trigger for INSERT
CREATE OR REPLACE FUNCTION audit_insert_trigger()
RETURNS TRIGGER AS $$
DECLARE
    v_resource_type VARCHAR(50);
    v_resource_id UUID;
    v_details JSONB;
BEGIN
    v_resource_type := TG_TABLE_NAME;
    v_resource_id := NEW.id;

    -- Build details based on table
    CASE TG_TABLE_NAME
        WHEN 'decisions' THEN
            v_details := jsonb_build_object(
                'decision_number', NEW.decision_number,
                'status', NEW.status,
                'owner_team_id', NEW.owner_team_id
            );
        WHEN 'decision_versions' THEN
            v_details := jsonb_build_object(
                'decision_id', NEW.decision_id,
                'version_number', NEW.version_number,
                'title', NEW.title,
                'impact_level', NEW.impact_level,
                'content_hash', NEW.content_hash
            );
        WHEN 'approvals' THEN
            v_details := jsonb_build_object(
                'decision_version_id', NEW.decision_version_id,
                'status', NEW.status,
                'user_id', NEW.user_id
            );
        WHEN 'decision_relationships' THEN
            v_details := jsonb_build_object(
                'source_decision_id', NEW.source_decision_id,
                'target_decision_id', NEW.target_decision_id,
                'relationship_type', NEW.relationship_type
            );
        ELSE
            v_details := to_jsonb(NEW);
    END CASE;

    PERFORM log_audit_event('create'::audit_action, v_resource_type, v_resource_id, v_details);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- Generic audit trigger for UPDATE
CREATE OR REPLACE FUNCTION audit_update_trigger()
RETURNS TRIGGER AS $$
DECLARE
    v_resource_type VARCHAR(50);
    v_resource_id UUID;
    v_details JSONB;
    v_changes JSONB;
BEGIN
    v_resource_type := TG_TABLE_NAME;
    v_resource_id := NEW.id;

    -- Calculate what changed
    v_changes := jsonb_build_object();

    -- Compare OLD and NEW to find changes
    -- This is a simplified version; production would iterate all columns
    CASE TG_TABLE_NAME
        WHEN 'decisions' THEN
            IF OLD.status IS DISTINCT FROM NEW.status THEN
                v_changes := v_changes || jsonb_build_object(
                    'status', jsonb_build_object('old', OLD.status, 'new', NEW.status)
                );
            END IF;
            IF OLD.current_version_id IS DISTINCT FROM NEW.current_version_id THEN
                v_changes := v_changes || jsonb_build_object(
                    'current_version_id', jsonb_build_object('old', OLD.current_version_id, 'new', NEW.current_version_id)
                );
            END IF;
            IF OLD.deleted_at IS DISTINCT FROM NEW.deleted_at THEN
                v_changes := v_changes || jsonb_build_object(
                    'deleted_at', jsonb_build_object('old', OLD.deleted_at, 'new', NEW.deleted_at)
                );
            END IF;
        WHEN 'decision_relationships' THEN
            IF OLD.invalidated_at IS DISTINCT FROM NEW.invalidated_at THEN
                v_changes := v_changes || jsonb_build_object(
                    'invalidated_at', jsonb_build_object('old', OLD.invalidated_at, 'new', NEW.invalidated_at),
                    'invalidated_by', NEW.invalidated_by
                );
            END IF;
        ELSE
            v_changes := jsonb_build_object('updated', true);
    END CASE;

    v_details := jsonb_build_object('changes', v_changes);

    PERFORM log_audit_event('update'::audit_action, v_resource_type, v_resource_id, v_details);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- Specific audit for status changes (supersede, deprecate)
CREATE OR REPLACE FUNCTION audit_status_change_trigger()
RETURNS TRIGGER AS $$
DECLARE
    v_action audit_action;
    v_details JSONB;
BEGIN
    -- Determine specific action based on status change
    IF NEW.status = 'superseded' AND OLD.status != 'superseded' THEN
        v_action := 'supersede';
    ELSIF NEW.status = 'deprecated' AND OLD.status != 'deprecated' THEN
        v_action := 'deprecate';
    ELSE
        RETURN NEW;  -- Not a status change we care about
    END IF;

    v_details := jsonb_build_object(
        'old_status', OLD.status,
        'new_status', NEW.status,
        'decision_number', NEW.decision_number
    );

    PERFORM log_audit_event(v_action, 'decision', NEW.id, v_details);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- =============================================================================
-- ATTACH AUDIT TRIGGERS TO TABLES
-- =============================================================================

-- Decisions
CREATE TRIGGER audit_decisions_insert
    AFTER INSERT ON decisions
    FOR EACH ROW
    EXECUTE FUNCTION audit_insert_trigger();

CREATE TRIGGER audit_decisions_update
    AFTER UPDATE ON decisions
    FOR EACH ROW
    EXECUTE FUNCTION audit_update_trigger();

CREATE TRIGGER audit_decisions_status_change
    AFTER UPDATE OF status ON decisions
    FOR EACH ROW
    WHEN (OLD.status IS DISTINCT FROM NEW.status)
    EXECUTE FUNCTION audit_status_change_trigger();

-- Decision Versions
CREATE TRIGGER audit_versions_insert
    AFTER INSERT ON decision_versions
    FOR EACH ROW
    EXECUTE FUNCTION audit_insert_trigger();

-- Approvals
CREATE TRIGGER audit_approvals_insert
    AFTER INSERT ON approvals
    FOR EACH ROW
    EXECUTE FUNCTION audit_insert_trigger();

-- Relationships
CREATE TRIGGER audit_relationships_insert
    AFTER INSERT ON decision_relationships
    FOR EACH ROW
    EXECUTE FUNCTION audit_insert_trigger();

CREATE TRIGGER audit_relationships_update
    AFTER UPDATE ON decision_relationships
    FOR EACH ROW
    EXECUTE FUNCTION audit_update_trigger();


-- =============================================================================
-- READ AUDIT (Application-Level - Call from API)
-- =============================================================================

-- Function to log read access (called explicitly from application)
CREATE OR REPLACE FUNCTION log_decision_read(
    p_decision_id UUID,
    p_version_id UUID DEFAULT NULL,
    p_fields_accessed TEXT[] DEFAULT '{}'
) RETURNS VOID AS $$
DECLARE
    v_details JSONB;
BEGIN
    v_details := jsonb_build_object(
        'decision_id', p_decision_id,
        'version_id', p_version_id,
        'fields_accessed', p_fields_accessed
    );

    PERFORM log_audit_event('read'::audit_action, 'decision', p_decision_id, v_details);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;


-- Function to log export events
CREATE OR REPLACE FUNCTION log_decision_export(
    p_decision_ids UUID[],
    p_format VARCHAR(20),
    p_include_history BOOLEAN DEFAULT FALSE
) RETURNS VOID AS $$
DECLARE
    v_decision_id UUID;
    v_details JSONB;
BEGIN
    v_details := jsonb_build_object(
        'format', p_format,
        'include_history', p_include_history,
        'decision_count', array_length(p_decision_ids, 1)
    );

    -- Log for each exported decision
    FOREACH v_decision_id IN ARRAY p_decision_ids LOOP
        PERFORM log_audit_event('export'::audit_action, 'decision', v_decision_id, v_details);
    END LOOP;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;


-- =============================================================================
-- AUDIT VERIFICATION (Tamper Detection)
-- =============================================================================

-- Verify the audit chain integrity for an organization
CREATE OR REPLACE FUNCTION verify_audit_chain(p_org_id UUID)
RETURNS TABLE (
    is_valid BOOLEAN,
    broken_at_id UUID,
    expected_hash VARCHAR(64),
    actual_hash VARCHAR(64)
) AS $$
DECLARE
    v_entry RECORD;
    v_previous_hash VARCHAR(64) := 'genesis';
    v_calculated_hash VARCHAR(64);
BEGIN
    FOR v_entry IN
        SELECT * FROM audit_log
        WHERE organization_id = p_org_id
        ORDER BY created_at ASC
    LOOP
        -- Calculate what the hash should be
        v_calculated_hash := encode(
            digest(
                v_entry.id::text ||
                COALESCE(v_entry.organization_id::text, '') ||
                COALESCE(v_entry.user_id::text, '') ||
                v_entry.action::text ||
                v_entry.resource_type ||
                v_entry.resource_id::text ||
                v_entry.details::text ||
                v_previous_hash,
                'sha256'
            ),
            'hex'
        );

        -- Check if it matches
        IF v_calculated_hash != v_entry.entry_hash THEN
            RETURN QUERY SELECT
                FALSE,
                v_entry.id,
                v_calculated_hash,
                v_entry.entry_hash;
            RETURN;
        END IF;

        -- Check previous_hash chain
        IF v_entry.previous_hash IS DISTINCT FROM
           (CASE WHEN v_previous_hash = 'genesis' THEN NULL ELSE v_previous_hash END) THEN
            RETURN QUERY SELECT
                FALSE,
                v_entry.id,
                v_previous_hash,
                v_entry.previous_hash;
            RETURN;
        END IF;

        v_previous_hash := v_entry.entry_hash;
    END LOOP;

    -- All good
    RETURN QUERY SELECT TRUE, NULL::UUID, NULL::VARCHAR(64), NULL::VARCHAR(64);
END;
$$ LANGUAGE plpgsql;


-- =============================================================================
-- AUDIT REPORTING VIEWS
-- =============================================================================

-- Recent activity view
CREATE VIEW recent_audit_activity AS
SELECT
    al.id,
    al.action,
    al.resource_type,
    al.resource_id,
    al.created_at,
    u.name AS user_name,
    u.email AS user_email,
    CASE
        WHEN al.resource_type = 'decision' THEN (
            SELECT dv.title
            FROM decisions d
            LEFT JOIN decision_versions dv ON d.current_version_id = dv.id
            WHERE d.id = al.resource_id
        )
        WHEN al.resource_type = 'decision_version' THEN (
            SELECT dv.title FROM decision_versions dv WHERE dv.id = al.resource_id
        )
        ELSE NULL
    END AS resource_title,
    al.details
FROM audit_log al
LEFT JOIN users u ON al.user_id = u.id
ORDER BY al.created_at DESC;


-- Compliance summary (grouped by action type)
CREATE VIEW audit_summary AS
SELECT
    organization_id,
    action,
    resource_type,
    COUNT(*) AS event_count,
    MIN(created_at) AS first_occurrence,
    MAX(created_at) AS last_occurrence
FROM audit_log
GROUP BY organization_id, action, resource_type
ORDER BY organization_id, last_occurrence DESC;


-- User activity report
CREATE VIEW user_audit_report AS
SELECT
    al.user_id,
    u.name AS user_name,
    u.email AS user_email,
    al.action,
    COUNT(*) AS action_count,
    MAX(al.created_at) AS last_activity
FROM audit_log al
LEFT JOIN users u ON al.user_id = u.id
GROUP BY al.user_id, u.name, u.email, al.action
ORDER BY last_activity DESC;
