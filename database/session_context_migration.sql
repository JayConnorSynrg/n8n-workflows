-- Migration: create session_context table
-- Date: 2026-03-03
-- Purpose: Dedup guard for n8n Launcher (kUcUSyPgz4Z9mYBt) and vector query workflow (z02K1a54akYXMkyj)
-- Used for: ephemeral key-value session state with TTL expiry

CREATE TABLE IF NOT EXISTS session_context (
  id BIGSERIAL PRIMARY KEY,
  session_id TEXT NOT NULL,
  context_key TEXT NOT NULL,
  context_value TEXT,
  expires_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (session_id, context_key)
);

CREATE INDEX IF NOT EXISTS idx_session_context_session_id ON session_context (session_id);
CREATE INDEX IF NOT EXISTS idx_session_context_expires_at ON session_context (expires_at);
