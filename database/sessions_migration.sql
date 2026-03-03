-- Migration: Add sessions table for session lifecycle tracking
-- Run against Railway PostgreSQL (NI3jbq1U8xPst3j3)
-- Written by: src/utils/pg_logger.py — log_session_start() and log_session_end()
-- Safe to re-run: all DDL uses IF NOT EXISTS / ON CONFLICT DO NOTHING

CREATE TABLE IF NOT EXISTS sessions (
    id              BIGSERIAL   PRIMARY KEY,
    session_id      TEXT        NOT NULL UNIQUE,
    user_id         TEXT,
    room_name       TEXT,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at        TIMESTAMPTZ,
    message_count   INTEGER     NOT NULL DEFAULT 0,
    tool_call_count INTEGER     NOT NULL DEFAULT 0,
    summary         TEXT,
    metadata        JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sessions_session_id ON sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id    ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_started_at ON sessions(started_at DESC);

COMMENT ON TABLE sessions IS
    'Session lifecycle records written by pg_logger.py. '
    'log_session_start() INSERTs at join (ON CONFLICT DO NOTHING). '
    'log_session_end() upserts ended_at, summary, message_count, tool_call_count. '
    'Retention: 90 days recommended.';

-- Retention cleanup (run periodically):
-- DELETE FROM sessions WHERE created_at < NOW() - INTERVAL '90 days';
