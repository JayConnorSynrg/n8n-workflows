-- Migration: Add session_facts_log table for PostgreSQL secondary memory
-- Run against Railway PostgreSQL (NI3jbq1U8xPst3j3)
--
-- Purpose: Persists volatile session_facts.py data to PostgreSQL for:
--   1. Durability across agent restarts (Railway redeploys)
--   2. Cross-session context injection at session start
--   3. Fact retrieval via recallSession agent tool
--
-- Load assessment:
--   ~10-30 facts per session, ~5 sessions/day → ~50-150 rows/day
--   90-day retention = ~4,500-13,500 rows max
--   PostgreSQL handles this trivially — no alternative DB needed

CREATE TABLE IF NOT EXISTS session_facts_log (
    id          BIGSERIAL   PRIMARY KEY,
    session_id  TEXT        NOT NULL,
    user_id     TEXT        NOT NULL DEFAULT '_default',
    key         TEXT        NOT NULL,
    value       TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_session_facts_user_key
    ON session_facts_log (user_id, key, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_session_facts_session
    ON session_facts_log (session_id);

COMMENT ON TABLE session_facts_log IS
    'Persisted session facts from session_facts.py — structured key/value pairs '
    'extracted during voice sessions (gammaUrl, topics, decisions, etc). '
    'Used for cross-session context injection and recallSession tool queries. '
    '90-day retention recommended.';

-- Retention cleanup (run periodically via pg_cron or scheduled task):
-- DELETE FROM session_facts_log WHERE created_at < NOW() - INTERVAL '90 days';
