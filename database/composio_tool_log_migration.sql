-- Migration: Add composio_tool_log and perplexity_searches tables for tool call logging
-- Run against Railway PostgreSQL (NI3jbq1U8xPst3j3)
-- Written by: src/utils/tool_logger.py — log_composio_call() and log_perplexity_search()
-- Safe to re-run: all DDL uses IF NOT EXISTS
--
-- NOTE: Canonical schema derived from the actual INSERT statements in tool_logger.py.
-- composio_tool_log columns: user_id, source, slug, arguments (JSONB), result_data (JSONB),
--   voice_result, success, error_message, duration_ms
-- perplexity_searches columns: user_id, query, model, response_content, search_results (JSONB),
--   usage (JSONB), duration_ms, success, error_message

-- All Composio + native tool calls
CREATE TABLE IF NOT EXISTS composio_tool_log (
    id            BIGSERIAL   PRIMARY KEY,
    user_id       TEXT,
    source        TEXT        NOT NULL DEFAULT 'composio',  -- 'composio' | 'native'
    slug          TEXT        NOT NULL,                      -- e.g. PERPLEXITYAI_PERPLEXITY_AI_SEARCH
    arguments     JSONB,                                     -- input arguments dict
    result_data   JSONB,                                     -- result["data"] from SDK (raw)
    voice_result  TEXT,                                      -- string returned to LLM
    success       BOOLEAN     NOT NULL,
    error_message TEXT,
    duration_ms   INTEGER,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_composio_tool_log_slug    ON composio_tool_log(slug);
CREATE INDEX IF NOT EXISTS idx_composio_tool_log_user_id ON composio_tool_log(user_id);
CREATE INDEX IF NOT EXISTS idx_composio_tool_log_created ON composio_tool_log(created_at DESC);

COMMENT ON TABLE composio_tool_log IS
    'All Composio and native tool executions. Written fire-and-forget by tool_logger.py '
    'log_composio_call(). source field distinguishes composio vs native tool origin. '
    'Retention: 90 days recommended.';

-- Retention cleanup (run periodically):
-- DELETE FROM composio_tool_log WHERE created_at < NOW() - INTERVAL '90 days';
