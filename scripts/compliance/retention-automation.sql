-- ============================================
-- AUTOMATED DATA RETENTION ENFORCEMENT
-- ============================================
-- Deploy to: Supabase / Railway PostgreSQL
-- Schedule: Daily at 3 AM UTC via pg_cron
-- SOC 2: CC6.5, CC6.6 | GDPR: Article 5(1)(e)
-- ============================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- ============================================
-- AUDIT TRAIL TABLE (if not exists)
-- ============================================
CREATE TABLE IF NOT EXISTS retention_audit_log (
    id SERIAL PRIMARY KEY,
    table_name VARCHAR(100) NOT NULL,
    records_deleted INTEGER NOT NULL DEFAULT 0,
    retention_days INTEGER NOT NULL,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    execution_time_ms INTEGER,
    status VARCHAR(20) NOT NULL DEFAULT 'SUCCESS',
    error_message TEXT
);

-- ============================================
-- RETENTION CLEANUP FUNCTIONS
-- ============================================

-- 1. Voice Recordings: 24 hours (delete after transcription)
-- GDPR Article 9: Biometric data minimization
CREATE OR REPLACE FUNCTION cleanup_voice_recordings()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
    start_time TIMESTAMPTZ;
    end_time TIMESTAMPTZ;
BEGIN
    start_time := clock_timestamp();

    -- Delete voice recordings older than 24 hours where transcription is complete
    DELETE FROM voice_recordings
    WHERE created_at < NOW() - INTERVAL '24 hours'
    AND (transcription_complete = true OR created_at < NOW() - INTERVAL '48 hours');

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    end_time := clock_timestamp();

    -- Log the operation
    INSERT INTO retention_audit_log (table_name, records_deleted, retention_days, execution_time_ms)
    VALUES ('voice_recordings', deleted_count, 1, EXTRACT(MILLISECONDS FROM (end_time - start_time))::INTEGER);

    RETURN deleted_count;
EXCEPTION WHEN OTHERS THEN
    INSERT INTO retention_audit_log (table_name, records_deleted, retention_days, status, error_message)
    VALUES ('voice_recordings', 0, 1, 'ERROR', SQLERRM);
    RETURN 0;
END;
$$ LANGUAGE plpgsql;

-- 2. Session Context: 1 hour (real-time cleanup)
-- Temporary data minimization
CREATE OR REPLACE FUNCTION cleanup_session_context()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
    start_time TIMESTAMPTZ;
    end_time TIMESTAMPTZ;
BEGIN
    start_time := clock_timestamp();

    DELETE FROM session_context
    WHERE expires_at < NOW()
    OR created_at < NOW() - INTERVAL '2 hours';

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    end_time := clock_timestamp();

    INSERT INTO retention_audit_log (table_name, records_deleted, retention_days, execution_time_ms)
    VALUES ('session_context', deleted_count, 0, EXTRACT(MILLISECONDS FROM (end_time - start_time))::INTEGER);

    RETURN deleted_count;
EXCEPTION WHEN OTHERS THEN
    INSERT INTO retention_audit_log (table_name, records_deleted, retention_days, status, error_message)
    VALUES ('session_context', 0, 0, 'ERROR', SQLERRM);
    RETURN 0;
END;
$$ LANGUAGE plpgsql;

-- 3. Tool Execution Logs: 90 days
-- SOC 2 CC4.1: Audit trail retention
CREATE OR REPLACE FUNCTION cleanup_tool_executions()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
    start_time TIMESTAMPTZ;
    end_time TIMESTAMPTZ;
BEGIN
    start_time := clock_timestamp();

    DELETE FROM tool_executions
    WHERE created_at < NOW() - INTERVAL '90 days';

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    end_time := clock_timestamp();

    INSERT INTO retention_audit_log (table_name, records_deleted, retention_days, execution_time_ms)
    VALUES ('tool_executions', deleted_count, 90, EXTRACT(MILLISECONDS FROM (end_time - start_time))::INTEGER);

    RETURN deleted_count;
EXCEPTION WHEN OTHERS THEN
    INSERT INTO retention_audit_log (table_name, records_deleted, retention_days, status, error_message)
    VALUES ('tool_executions', 0, 90, 'ERROR', SQLERRM);
    RETURN 0;
END;
$$ LANGUAGE plpgsql;

-- 4. Tool Calls: 90 days
CREATE OR REPLACE FUNCTION cleanup_tool_calls()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
    start_time TIMESTAMPTZ;
    end_time TIMESTAMPTZ;
BEGIN
    start_time := clock_timestamp();

    DELETE FROM tool_calls
    WHERE created_at < NOW() - INTERVAL '90 days';

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    end_time := clock_timestamp();

    INSERT INTO retention_audit_log (table_name, records_deleted, retention_days, execution_time_ms)
    VALUES ('tool_calls', deleted_count, 90, EXTRACT(MILLISECONDS FROM (end_time - start_time))::INTEGER);

    RETURN deleted_count;
EXCEPTION WHEN OTHERS THEN
    INSERT INTO retention_audit_log (table_name, records_deleted, retention_days, status, error_message)
    VALUES ('tool_calls', 0, 90, 'ERROR', SQLERRM);
    RETURN 0;
END;
$$ LANGUAGE plpgsql;

-- 5. Training Metrics: 1 year
-- Learning analytics retention
CREATE OR REPLACE FUNCTION cleanup_training_metrics()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
    start_time TIMESTAMPTZ;
    end_time TIMESTAMPTZ;
BEGIN
    start_time := clock_timestamp();

    DELETE FROM training_metrics
    WHERE created_at < NOW() - INTERVAL '1 year';

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    end_time := clock_timestamp();

    INSERT INTO retention_audit_log (table_name, records_deleted, retention_days, execution_time_ms)
    VALUES ('training_metrics', deleted_count, 365, EXTRACT(MILLISECONDS FROM (end_time - start_time))::INTEGER);

    RETURN deleted_count;
EXCEPTION WHEN OTHERS THEN
    INSERT INTO retention_audit_log (table_name, records_deleted, retention_days, status, error_message)
    VALUES ('training_metrics', 0, 365, 'ERROR', SQLERRM);
    RETURN 0;
END;
$$ LANGUAGE plpgsql;

-- 6. Session Analytics: 6 months
-- Usage analytics retention
CREATE OR REPLACE FUNCTION cleanup_session_analytics()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
    start_time TIMESTAMPTZ;
    end_time TIMESTAMPTZ;
BEGIN
    start_time := clock_timestamp();

    DELETE FROM user_session_analytics
    WHERE created_at < NOW() - INTERVAL '6 months';

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    end_time := clock_timestamp();

    INSERT INTO retention_audit_log (table_name, records_deleted, retention_days, execution_time_ms)
    VALUES ('user_session_analytics', deleted_count, 180, EXTRACT(MILLISECONDS FROM (end_time - start_time))::INTEGER);

    RETURN deleted_count;
EXCEPTION WHEN OTHERS THEN
    INSERT INTO retention_audit_log (table_name, records_deleted, retention_days, status, error_message)
    VALUES ('user_session_analytics', 0, 180, 'ERROR', SQLERRM);
    RETURN 0;
END;
$$ LANGUAGE plpgsql;

-- 7. Retention Audit Log: 2 years (meta-retention)
CREATE OR REPLACE FUNCTION cleanup_retention_audit_log()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM retention_audit_log
    WHERE executed_at < NOW() - INTERVAL '2 years';

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- MASTER CLEANUP ORCHESTRATOR
-- ============================================
CREATE OR REPLACE FUNCTION run_daily_retention_cleanup()
RETURNS TABLE(
    table_name TEXT,
    records_deleted INTEGER,
    status TEXT
) AS $$
BEGIN
    -- Run all cleanup functions and return results
    RETURN QUERY
    SELECT 'session_context'::TEXT, cleanup_session_context(), 'completed'::TEXT
    UNION ALL
    SELECT 'voice_recordings'::TEXT, cleanup_voice_recordings(), 'completed'::TEXT
    UNION ALL
    SELECT 'tool_executions'::TEXT, cleanup_tool_executions(), 'completed'::TEXT
    UNION ALL
    SELECT 'tool_calls'::TEXT, cleanup_tool_calls(), 'completed'::TEXT
    UNION ALL
    SELECT 'training_metrics'::TEXT, cleanup_training_metrics(), 'completed'::TEXT
    UNION ALL
    SELECT 'user_session_analytics'::TEXT, cleanup_session_analytics(), 'completed'::TEXT
    UNION ALL
    SELECT 'retention_audit_log'::TEXT, cleanup_retention_audit_log(), 'completed'::TEXT;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- SCHEDULE CRON JOBS
-- ============================================

-- Remove existing jobs if any
SELECT cron.unschedule('retention-cleanup-daily') WHERE EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'retention-cleanup-daily');
SELECT cron.unschedule('session-cleanup-hourly') WHERE EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'session-cleanup-hourly');

-- Daily retention cleanup at 3 AM UTC
SELECT cron.schedule(
    'retention-cleanup-daily',
    '0 3 * * *',
    'SELECT * FROM run_daily_retention_cleanup()'
);

-- Hourly session context cleanup
SELECT cron.schedule(
    'session-cleanup-hourly',
    '0 * * * *',
    'SELECT cleanup_session_context()'
);

-- ============================================
-- VERIFICATION QUERIES
-- ============================================

-- View scheduled jobs
-- SELECT * FROM cron.job;

-- View recent cleanup history
-- SELECT * FROM retention_audit_log ORDER BY executed_at DESC LIMIT 20;

-- View cleanup summary by table
-- SELECT table_name, SUM(records_deleted) as total_deleted, COUNT(*) as executions
-- FROM retention_audit_log
-- WHERE executed_at > NOW() - INTERVAL '7 days'
-- GROUP BY table_name
-- ORDER BY total_deleted DESC;

-- ============================================
-- GDPR DATA SUBJECT RIGHTS FUNCTIONS
-- ============================================

-- Article 15: Right to Access - Export all user data
CREATE OR REPLACE FUNCTION gdpr_export_user_data(user_email_param VARCHAR)
RETURNS JSON AS $$
DECLARE
    result JSON;
BEGIN
    SELECT json_build_object(
        'export_date', NOW(),
        'user_email', user_email_param,
        'tool_executions', (SELECT COALESCE(json_agg(t), '[]'::json) FROM tool_executions t WHERE user_email = user_email_param),
        'tool_calls', (SELECT COALESCE(json_agg(t), '[]'::json) FROM tool_calls t WHERE user_email = user_email_param),
        'training_metrics', (SELECT COALESCE(json_agg(t), '[]'::json) FROM training_metrics t WHERE user_email = user_email_param),
        'session_analytics', (SELECT COALESCE(json_agg(t), '[]'::json) FROM user_session_analytics t WHERE user_email = user_email_param),
        'consent_records', (SELECT COALESCE(json_agg(t), '[]'::json) FROM consent_records t WHERE user_email = user_email_param)
    ) INTO result;

    -- Log the access request
    INSERT INTO retention_audit_log (table_name, records_deleted, retention_days, status)
    VALUES ('GDPR_ACCESS_REQUEST', 0, 0, 'ACCESS_REQUEST: ' || user_email_param);

    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- Article 17: Right to Erasure - Delete all user data
CREATE OR REPLACE FUNCTION gdpr_erase_user_data(user_email_param VARCHAR)
RETURNS JSON AS $$
DECLARE
    tool_exec_count INTEGER;
    tool_calls_count INTEGER;
    training_count INTEGER;
    analytics_count INTEGER;
BEGIN
    -- Delete from all tables (keep consent records for proof)
    DELETE FROM tool_executions WHERE user_email = user_email_param;
    GET DIAGNOSTICS tool_exec_count = ROW_COUNT;

    DELETE FROM tool_calls WHERE user_email = user_email_param;
    GET DIAGNOSTICS tool_calls_count = ROW_COUNT;

    DELETE FROM training_metrics WHERE user_email = user_email_param;
    GET DIAGNOSTICS training_count = ROW_COUNT;

    DELETE FROM user_session_analytics WHERE user_email = user_email_param;
    GET DIAGNOSTICS analytics_count = ROW_COUNT;

    -- Mark consent as withdrawn (don't delete - needed for proof)
    UPDATE consent_records
    SET withdrawn_at = NOW()
    WHERE user_email = user_email_param AND withdrawn_at IS NULL;

    -- Log the erasure request
    INSERT INTO retention_audit_log (table_name, records_deleted, retention_days, status)
    VALUES ('GDPR_ERASURE_REQUEST', tool_exec_count + tool_calls_count + training_count + analytics_count, 0, 'ERASED: ' || user_email_param);

    RETURN json_build_object(
        'erasure_date', NOW(),
        'user_email', user_email_param,
        'records_deleted', json_build_object(
            'tool_executions', tool_exec_count,
            'tool_calls', tool_calls_count,
            'training_metrics', training_count,
            'session_analytics', analytics_count
        ),
        'status', 'COMPLETED'
    );
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- DEPLOYMENT VERIFICATION
-- ============================================
-- Run this after deployment to verify setup:

-- DO $$
-- BEGIN
--     RAISE NOTICE 'Retention automation deployed successfully';
--     RAISE NOTICE 'Scheduled jobs: %', (SELECT COUNT(*) FROM cron.job);
--     RAISE NOTICE 'Tables covered: voice_recordings, session_context, tool_executions, tool_calls, training_metrics, user_session_analytics';
-- END $$;
