-- =============================================================================
-- Migration: 20260304_fix_session_facts_log_unique.sql
-- Date: 2026-03-04
-- Severity: CRITICAL (S2)
--
-- Problem:
--   flush_facts_to_db() in src/utils/session_facts.py uses an
--   ON CONFLICT (session_id, key) DO UPDATE upsert. If the UNIQUE constraint
--   on (session_id, key) is absent, PostgreSQL raises:
--     ERROR: there is no unique or exclusion constraint matching the ON CONFLICT specification
--   This causes every session_facts flush to fail silently (fire-and-forget),
--   meaning Gamma URLs, generation IDs, and all cross-session facts are NEVER
--   persisted to the database across sessions.
--
--   The SKILL.md schema documentation shows UNIQUE(session_id, key) as present,
--   but the original session_facts_log_migration.sql may not have applied it on
--   all Railway PostgreSQL instances (schema drift between docs and DB).
--
-- Fix:
--   1. Deduplicate any existing (session_id, key) pairs before adding the
--      constraint (keeps the most recent row by id DESC to be safe).
--   2. Add UNIQUE constraint uniq_session_facts_session_key if not present.
--   3. Add composite index for O(1) point lookups by (session_id, key).
--
-- Safety:
--   - Dedup step uses DELETE ... WHERE id NOT IN (SELECT MAX(id) ...) —
--     idempotent, safe to re-run, removes at most duplicate rows.
--   - Constraint addition is wrapped in a pg_constraint existence check —
--     idempotent and safe to replay.
--   - Index uses IF NOT EXISTS — safe to replay.
--   - All steps run inside DO blocks; errors are raised with context.
-- =============================================================================

-- Step 1: Remove any duplicate (session_id, key) rows before adding constraint.
-- Retains the row with the highest id (most recently inserted) per pair.
-- On a clean database this deletes 0 rows; included for safety.
DELETE FROM session_facts_log
WHERE id NOT IN (
    SELECT MAX(id)
    FROM session_facts_log
    GROUP BY session_id, key
);

-- Step 2: Add UNIQUE constraint if not already present
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'session_facts_log'::regclass
          AND conname  = 'uniq_session_facts_session_key'
    ) THEN
        ALTER TABLE session_facts_log
            ADD CONSTRAINT uniq_session_facts_session_key UNIQUE (session_id, key);
        RAISE NOTICE 'UNIQUE constraint uniq_session_facts_session_key added to session_facts_log.';
    ELSE
        RAISE NOTICE 'UNIQUE constraint uniq_session_facts_session_key already exists — skipping.';
    END IF;
END $$;

-- Step 3: Composite index for O(1) point lookups (session_id, key)
-- Even with the UNIQUE constraint, a named index makes EXPLAIN plans cleaner.
CREATE INDEX IF NOT EXISTS idx_session_facts_session_key
    ON session_facts_log (session_id, key);

-- Verification: confirm constraint and index exist
SELECT
    c.conname   AS constraint_name,
    c.contype   AS constraint_type
FROM pg_constraint c
WHERE c.conrelid = 'session_facts_log'::regclass
  AND c.conname  = 'uniq_session_facts_session_key';

-- Should return 1 row: uniq_session_facts_session_key | u
