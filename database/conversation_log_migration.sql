-- Migration: Add conversation_log table for full session context storage
-- Run against the Railway PostgreSQL instance (NI3jbq1U8xPst3j3)
-- Load assessment: ~150 rows/session, ~750/day, 90-day retention = ~67,500 rows max
-- PostgreSQL handles this trivially. No alternative database needed.

CREATE TABLE IF NOT EXISTS conversation_log (
    id          BIGSERIAL PRIMARY KEY,
    session_id  TEXT        NOT NULL,
    role        TEXT        NOT NULL CHECK (role IN ('user', 'assistant', 'tool', 'system')),
    content     TEXT        NOT NULL,
    tool_name   TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conv_log_session ON conversation_log(session_id);
CREATE INDEX IF NOT EXISTS idx_conv_log_created ON conversation_log(created_at DESC);

-- Retention cleanup (run periodically via cron or pg_cron extension):
-- DELETE FROM conversation_log WHERE created_at < NOW() - INTERVAL '90 days';

COMMENT ON TABLE conversation_log IS
    'Full conversation transcript per session. Used for context retrieval, '
    'session replay, and training data. 90-day retention recommended.';
