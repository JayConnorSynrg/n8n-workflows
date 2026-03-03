-- Migration: Add perplexity_searches table for Perplexity AI search logging
-- Run against Railway PostgreSQL (NI3jbq1U8xPst3j3)
-- Written by: src/utils/tool_logger.py — log_perplexity_search() -> _write_perplexity_log()
-- Safe to re-run: all DDL uses IF NOT EXISTS
--
-- NOTE: Canonical schema derived from the actual INSERT statement in tool_logger.py.
-- Columns: user_id, query, model, response_content, search_results (JSONB), usage (JSONB),
--   duration_ms, success, error_message

CREATE TABLE IF NOT EXISTS perplexity_searches (
    id               BIGSERIAL   PRIMARY KEY,
    user_id          TEXT,
    query            TEXT        NOT NULL,   -- arguments["userContent"], capped at 2000 chars
    model            TEXT,                   -- arguments.get("model", "sonar")
    response_content TEXT,                   -- choices[0].message.content, capped at 8000 chars
    search_results   JSONB,                  -- the search_results array from API response
    usage            JSONB,                  -- token counts + cost from API response
    duration_ms      INTEGER,
    success          BOOLEAN     NOT NULL,
    error_message    TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_perplexity_searches_user_id ON perplexity_searches(user_id);
CREATE INDEX IF NOT EXISTS idx_perplexity_searches_created ON perplexity_searches(created_at DESC);

COMMENT ON TABLE perplexity_searches IS
    'Perplexity AI search calls with full structured response data. '
    'Written fire-and-forget by tool_logger.py log_perplexity_search(). '
    'Richer schema than composio_tool_log: stores parsed model, response_content, '
    'search_results, usage separately for analytics. '
    'Retention: 90 days recommended.';

-- Retention cleanup (run periodically):
-- DELETE FROM perplexity_searches WHERE created_at < NOW() - INTERVAL '90 days';
