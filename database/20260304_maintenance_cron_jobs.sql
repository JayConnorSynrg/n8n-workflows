-- =============================================================================
-- Migration: 20260304_maintenance_cron_jobs.sql
-- Date: 2026-03-04
-- Severity: OPTIONAL (Railway managed PG may not support pg_cron)
--
-- Purpose:
--   Register 5 scheduled maintenance jobs via pg_cron. If pg_cron is not
--   available on this PostgreSQL instance (Railway managed databases often
--   restrict extensions), the entire block raises a NOTICE and exits cleanly —
--   the migration still completes successfully with no schema changes.
--
-- Jobs registered:
--   1. expire-session-context       every 6 hours     — purge expired rows
--   2. timeout-stalled-tool-calls   every hour        — fail stuck EXECUTING rows
--   3. prune-conversation-log       daily at 03:00    — 90-day retention
--   4. close-orphaned-sessions      daily at 03:15    — mark sessions ended
--   5. prune-old-sessions           daily at 03:30    — 90-day retention
--
-- Idempotency:
--   cron.schedule() uses ON CONFLICT (jobname) DO UPDATE to upsert each job
--   definition. Re-running this migration updates schedules safely.
--
-- Safety:
--   All cron job creation is wrapped in a single DO block with EXCEPTION
--   handling. If pg_cron is unavailable, a NOTICE is emitted and execution
--   continues — no ERROR is raised, the migration succeeds.
-- =============================================================================

DO $$
BEGIN

    -- Attempt to load the pg_cron extension.
    -- CREATE EXTENSION IF NOT EXISTS is itself idempotent.
    BEGIN
        CREATE EXTENSION IF NOT EXISTS pg_cron;
    EXCEPTION
        WHEN insufficient_privilege THEN
            RAISE NOTICE 'pg_cron: insufficient privilege to CREATE EXTENSION — skipping cron job setup. Apply manually as superuser if needed.';
            RETURN;
        WHEN undefined_file THEN
            RAISE NOTICE 'pg_cron: extension not available on this PostgreSQL instance — skipping cron job setup.';
            RETURN;
        WHEN OTHERS THEN
            RAISE NOTICE 'pg_cron: could not enable extension (%). Skipping cron job setup.', SQLERRM;
            RETURN;
    END;

    -- Job 1: expire-session-context
    -- Runs every 6 hours. Deletes rows from session_context where the TTL has
    -- passed. Keeps the n8n Launcher dedup table from growing unboundedly.
    -- session_context rows have 3-hour TTL (inserted by kUcUSyPgz4Z9mYBt workflow).
    PERFORM cron.schedule(
        'expire-session-context',
        '0 */6 * * *',
        $$DELETE FROM session_context WHERE expires_at < NOW()$$
    );
    RAISE NOTICE 'Cron job registered: expire-session-context (every 6 hours)';

    -- Job 2: timeout-stalled-tool-calls
    -- Runs every hour. Marks tool_calls rows that have been EXECUTING for
    -- more than 15 minutes as FAILED. Prevents the audit table from accumulating
    -- ghost rows from crashed workers or lost callbacks.
    PERFORM cron.schedule(
        'timeout-stalled-tool-calls',
        '0 * * * *',
        $$
        UPDATE tool_calls
        SET
            status        = 'FAILED',
            error_message = 'Timed out',
            completed_at  = NOW()
        WHERE status     = 'EXECUTING'
          AND created_at < NOW() - INTERVAL '15 minutes'
        $$
    );
    RAISE NOTICE 'Cron job registered: timeout-stalled-tool-calls (every hour)';

    -- Job 3: prune-conversation-log
    -- Runs daily at 03:00 UTC. Deletes conversation_log rows older than 90
    -- days. At ~750 rows/day the table would otherwise reach ~270K rows/year.
    -- 90-day window retains ~67K rows — sufficient for all retrospective
    -- debugging and LLM context recall needs.
    PERFORM cron.schedule(
        'prune-conversation-log',
        '0 3 * * *',
        $$DELETE FROM conversation_log WHERE created_at < NOW() - INTERVAL '90 days'$$
    );
    RAISE NOTICE 'Cron job registered: prune-conversation-log (daily 03:00 UTC)';

    -- Job 4: close-orphaned-sessions
    -- Runs daily at 03:15 UTC. Sessions without ended_at that started more
    -- than 4 hours ago are assumed to have ended abnormally (agent crash,
    -- Railway restart, network drop). Sets ended_at = started_at + 4 hours
    -- rather than NOW() to preserve approximate session duration in analytics.
    PERFORM cron.schedule(
        'close-orphaned-sessions',
        '15 3 * * *',
        $$
        UPDATE sessions
        SET ended_at = started_at + INTERVAL '4 hours'
        WHERE ended_at  IS NULL
          AND started_at < NOW() - INTERVAL '4 hours'
        $$
    );
    RAISE NOTICE 'Cron job registered: close-orphaned-sessions (daily 03:15 UTC)';

    -- Job 5: prune-old-sessions + prune-old-session-facts
    -- Runs daily at 03:30 UTC (staggered 15 min after close-orphaned-sessions).
    -- Deletes sessions and their associated session_facts_log rows older than
    -- 90 days. Two statements in one job keep them transactionally aligned.
    PERFORM cron.schedule(
        'prune-old-sessions',
        '30 3 * * *',
        $$
        DELETE FROM sessions          WHERE created_at < NOW() - INTERVAL '90 days';
        DELETE FROM session_facts_log WHERE created_at < NOW() - INTERVAL '90 days';
        $$
    );
    RAISE NOTICE 'Cron job registered: prune-old-sessions (daily 03:30 UTC)';

EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'pg_cron job registration failed unexpectedly: %. Cron jobs were NOT registered. Review pg_cron availability.', SQLERRM;
END $$;

-- Verification (only meaningful if pg_cron is available):
-- SELECT jobid, jobname, schedule, command FROM cron.job ORDER BY jobname;
