-- Voice Agent Tool Calls Table
-- Migration: 001_create_tool_calls.sql
-- Run this in your PostgreSQL database before deploying the workflows

-- Drop existing table if exists (for development - remove in production)
-- DROP TABLE IF EXISTS tool_calls;

CREATE TABLE IF NOT EXISTS tool_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tool_call_id VARCHAR(100) UNIQUE NOT NULL,
    session_id VARCHAR(100) NOT NULL,
    connection_id VARCHAR(100),

    -- Tool details
    function_name VARCHAR(100) NOT NULL,
    parameters JSONB NOT NULL DEFAULT '{}',
    parameters_history JSONB DEFAULT '[]',

    -- State tracking (includes PREPARED for checkpoint pattern)
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    status_history JSONB DEFAULT '[]',

    -- Execution details
    workflow_id VARCHAR(100),
    result JSONB,
    error_message TEXT,
    voice_response TEXT,

    -- Timing
    created_at TIMESTAMPTZ DEFAULT NOW(),
    confirmed_at TIMESTAMPTZ,
    prepared_at TIMESTAMPTZ,
    executed_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    execution_time_ms INTEGER,

    -- Callback for async pattern
    callback_url TEXT,

    -- Validation
    CONSTRAINT valid_status CHECK (
        status IN ('PENDING', 'MODIFIED', 'EXECUTING', 'PREPARED', 'COMPLETED', 'FAILED', 'CANCELLED')
    )
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_tool_calls_session
    ON tool_calls(session_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_tool_calls_status
    ON tool_calls(session_id, status);

CREATE INDEX IF NOT EXISTS idx_tool_calls_pending
    ON tool_calls(session_id)
    WHERE status IN ('PENDING', 'EXECUTING', 'PREPARED');

CREATE INDEX IF NOT EXISTS idx_tool_calls_tool_call_id
    ON tool_calls(tool_call_id);

-- Comments
COMMENT ON TABLE tool_calls IS 'Voice agent tool execution state machine with checkpoint pattern';
COMMENT ON COLUMN tool_calls.status IS 'PENDING → EXECUTING → PREPARED (checkpoint) → EXECUTING → COMPLETED/FAILED/CANCELLED';
COMMENT ON COLUMN tool_calls.prepared_at IS 'Timestamp when checkpoint was reached, waiting for final confirmation';
COMMENT ON COLUMN tool_calls.parameters_history IS 'Array of {field, old_value, new_value, timestamp} for audit trail';
COMMENT ON COLUMN tool_calls.status_history IS 'Array of {status, timestamp} for full state transition audit';
