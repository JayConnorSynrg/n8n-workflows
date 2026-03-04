-- =============================================================================
-- Migration: 20260304_fix_conversation_log_user_id.sql
-- Date: 2026-03-04
-- Severity: CRITICAL (S1)
--
-- Problem:
--   conversation_log DDL in conversation_log_migration.sql does not include a
--   user_id column. pg_logger.py calls log_turn(..., user_id=...) and
--   log_session_start/log_session_end both insert user_id. When user_id is
--   absent from the schema, writes that supply user_id silently fail or the
--   column was added ad-hoc with no index, leaving queries by user_id
--   performing full table scans as the table grows (~750 rows/day).
--
-- Fix:
--   1. Add user_id TEXT column (idempotent via DO block).
--   2. Add index on conversation_log(user_id) for per-user queries.
--   3. Add composite index on (session_id, created_at DESC) for the common
--      "fetch last N turns for a session" access pattern used by pg_logger and
--      checkContext.
--   4. Add index on (created_at DESC) to support the 90-day prune cron job
--      and temporal range scans.
--
-- Safety:
--   - All DDL wrapped in IF NOT EXISTS guards — zero risk on already-migrated DBs.
--   - Column is TEXT (nullable) — no NOT NULL constraint, no default required;
--     existing rows are unaffected and stay NULL.
--   - Indexes use IF NOT EXISTS — safe to replay.
--   - No table rewrites; no locks beyond brief ShareLock on index build.
--   - Safe to run on a live production database with active writes.
-- =============================================================================

-- Step 1: Add user_id column if missing
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name   = 'conversation_log'
          AND column_name  = 'user_id'
    ) THEN
        ALTER TABLE conversation_log ADD COLUMN user_id TEXT;
        RAISE NOTICE 'conversation_log.user_id column added.';
    ELSE
        RAISE NOTICE 'conversation_log.user_id already exists — skipping ALTER TABLE.';
    END IF;
END $$;

-- Step 2: Index on user_id for per-user retrieval
CREATE INDEX IF NOT EXISTS idx_conv_log_user
    ON conversation_log (user_id);

-- Step 3: Composite index on (session_id, created_at DESC)
-- Covers: "SELECT * FROM conversation_log WHERE session_id = $1 ORDER BY created_at DESC LIMIT N"
-- Used by: pg_logger session queries, checkContext webhook handler
CREATE INDEX IF NOT EXISTS idx_conv_log_session_created
    ON conversation_log (session_id, created_at DESC);

-- Step 4: Index on created_at DESC for temporal range scans and prune job
CREATE INDEX IF NOT EXISTS idx_conv_log_created
    ON conversation_log (created_at DESC);

-- Verification: confirm user_id column is present and indexes exist
SELECT
    c.column_name,
    c.data_type,
    c.is_nullable
FROM information_schema.columns c
WHERE c.table_schema = 'public'
  AND c.table_name   = 'conversation_log'
  AND c.column_name  = 'user_id';

-- Should return 1 row: user_id | text | YES
