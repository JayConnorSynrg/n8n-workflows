-- Orchestrator Logs Schema
-- Teams Voice Bot - Parallel Architecture
-- Version: 2.0

-- Main orchestrator decision log
CREATE TABLE IF NOT EXISTS orchestrator_logs (
    id SERIAL PRIMARY KEY,
    bot_id VARCHAR(255) NOT NULL,
    session_id VARCHAR(255),
    timestamp TIMESTAMPTZ DEFAULT NOW(),

    -- Classification Results
    transcript TEXT,
    intent VARCHAR(50),
    route VARCHAR(50),
    is_complete_thought BOOLEAN,
    should_respond BOOLEAN,
    confidence_score DECIMAL(3,2),

    -- State Context
    previous_state VARCHAR(50),
    new_state VARCHAR(50),
    state_data JSONB,

    -- Tool Calls (if any)
    tool_called VARCHAR(100),
    tool_input JSONB,
    tool_output JSONB,
    tool_success BOOLEAN,
    tool_duration_ms INTEGER,
    tool_error TEXT,

    -- Response
    response_text TEXT,
    response_type VARCHAR(50), -- 'tts', 'silent', 'acknowledgment'
    tts_duration_ms INTEGER,

    -- Timing
    classification_ms INTEGER,
    total_processing_ms INTEGER,

    -- Error Tracking
    error_code VARCHAR(50),
    error_message TEXT,
    error_stack TEXT,

    -- Metadata
    workflow_version VARCHAR(20),
    node_path TEXT[], -- Array of node names executed

    CONSTRAINT valid_route CHECK (
        route IN ('silent_ignore', 'greeting_direct', 'spelling_mode',
                  'tool_call', 'chat_agent', 'error_handle')
    ),
    CONSTRAINT valid_intent CHECK (
        intent IN ('irrelevant', 'greeting', 'question', 'email_request',
                   'spelling_continue', 'confirmation', 'command', 'error')
    )
);

-- Chat session management
CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id VARCHAR(255) PRIMARY KEY,
    bot_id VARCHAR(255) NOT NULL,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    last_activity TIMESTAMPTZ DEFAULT NOW(),
    message_count INTEGER DEFAULT 0,

    -- Session State
    current_state VARCHAR(50) DEFAULT 'IDLE',
    context_summary TEXT,

    -- Accumulated Data
    email_chars TEXT,
    pending_email JSONB,
    pending_tool_calls JSONB[],

    -- Metrics
    total_responses INTEGER DEFAULT 0,
    total_tool_calls INTEGER DEFAULT 0,
    total_silent_ignores INTEGER DEFAULT 0,

    -- Session End
    ended_at TIMESTAMPTZ,
    end_reason VARCHAR(50),

    CONSTRAINT valid_session_state CHECK (
        current_state IN ('IDLE', 'LISTENING', 'SPELLING_EMAIL',
                          'CONFIRMING_EMAIL', 'TOOL_EXECUTING', 'ENDED')
    )
);

-- Conversation history for context
CREATE TABLE IF NOT EXISTS conversation_history (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    bot_id VARCHAR(255) NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW(),

    -- Message
    role VARCHAR(20) NOT NULL, -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,

    -- Context
    intent VARCHAR(50),
    tool_used VARCHAR(100),

    -- For memory window queries
    sequence_num INTEGER,

    CONSTRAINT valid_role CHECK (
        role IN ('user', 'assistant', 'system', 'tool')
    )
);

-- Tool execution audit log
CREATE TABLE IF NOT EXISTS tool_executions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255),
    bot_id VARCHAR(255) NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW(),

    -- Tool Details
    tool_name VARCHAR(100) NOT NULL,
    tool_type VARCHAR(50), -- 'gmail', 'calendar', 'search', etc.
    sub_workflow_id VARCHAR(255),

    -- Execution
    input_data JSONB,
    output_data JSONB,
    success BOOLEAN,
    error_message TEXT,
    duration_ms INTEGER,

    -- Parallel Execution Context
    parallel_with TEXT, -- ID of parallel TTS execution
    acknowledgment_sent BOOLEAN,
    result_tts_sent BOOLEAN
);

-- Performance metrics aggregation (materialized for dashboard)
CREATE TABLE IF NOT EXISTS performance_metrics (
    date DATE PRIMARY KEY,

    -- Volume
    total_transcripts INTEGER DEFAULT 0,
    total_responses INTEGER DEFAULT 0,
    total_silent_ignores INTEGER DEFAULT 0,
    total_tool_calls INTEGER DEFAULT 0,

    -- Intent Distribution
    intent_greeting INTEGER DEFAULT 0,
    intent_question INTEGER DEFAULT 0,
    intent_email INTEGER DEFAULT 0,
    intent_other INTEGER DEFAULT 0,

    -- Timing (averages in ms)
    avg_classification_ms DECIMAL(10,2),
    avg_total_processing_ms DECIMAL(10,2),
    avg_tool_duration_ms DECIMAL(10,2),

    -- Quality
    tool_success_rate DECIMAL(5,2),
    error_rate DECIMAL(5,2),

    -- Session Stats
    total_sessions INTEGER DEFAULT 0,
    avg_session_duration_minutes DECIMAL(10,2),
    avg_messages_per_session DECIMAL(10,2)
);

-- Indexes for query performance
CREATE INDEX IF NOT EXISTS idx_logs_bot_id ON orchestrator_logs(bot_id);
CREATE INDEX IF NOT EXISTS idx_logs_session ON orchestrator_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON orchestrator_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_logs_intent ON orchestrator_logs(intent);
CREATE INDEX IF NOT EXISTS idx_logs_route ON orchestrator_logs(route);
CREATE INDEX IF NOT EXISTS idx_logs_errors ON orchestrator_logs(error_code) WHERE error_code IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_sessions_bot ON chat_sessions(bot_id);
CREATE INDEX IF NOT EXISTS idx_sessions_activity ON chat_sessions(last_activity);
CREATE INDEX IF NOT EXISTS idx_sessions_state ON chat_sessions(current_state);

CREATE INDEX IF NOT EXISTS idx_history_session ON conversation_history(session_id);
CREATE INDEX IF NOT EXISTS idx_history_timestamp ON conversation_history(timestamp);
CREATE INDEX IF NOT EXISTS idx_history_lookup ON conversation_history(session_id, sequence_num DESC);

CREATE INDEX IF NOT EXISTS idx_tools_session ON tool_executions(session_id);
CREATE INDEX IF NOT EXISTS idx_tools_name ON tool_executions(tool_name);
CREATE INDEX IF NOT EXISTS idx_tools_success ON tool_executions(success);

-- Partitioning for orchestrator_logs (daily partitions for high volume)
-- Uncomment if using PostgreSQL 12+ with high volume
/*
CREATE TABLE orchestrator_logs_template (LIKE orchestrator_logs INCLUDING ALL)
PARTITION BY RANGE (timestamp);

-- Create partitions for current month
-- Run monthly maintenance to create new partitions and drop old ones
*/

-- Function to update session on new log entry
CREATE OR REPLACE FUNCTION update_session_on_log()
RETURNS TRIGGER AS $$
BEGIN
    -- Update or create session
    INSERT INTO chat_sessions (session_id, bot_id, last_activity, message_count)
    VALUES (NEW.session_id, NEW.bot_id, NEW.timestamp, 1)
    ON CONFLICT (session_id)
    DO UPDATE SET
        last_activity = NEW.timestamp,
        message_count = chat_sessions.message_count + 1,
        current_state = COALESCE(NEW.new_state, chat_sessions.current_state),
        total_responses = CASE WHEN NEW.should_respond THEN chat_sessions.total_responses + 1
                              ELSE chat_sessions.total_responses END,
        total_silent_ignores = CASE WHEN NOT NEW.should_respond THEN chat_sessions.total_silent_ignores + 1
                                   ELSE chat_sessions.total_silent_ignores END,
        total_tool_calls = CASE WHEN NEW.tool_called IS NOT NULL THEN chat_sessions.total_tool_calls + 1
                               ELSE chat_sessions.total_tool_calls END;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update session
DROP TRIGGER IF EXISTS trg_update_session ON orchestrator_logs;
CREATE TRIGGER trg_update_session
    AFTER INSERT ON orchestrator_logs
    FOR EACH ROW
    EXECUTE FUNCTION update_session_on_log();

-- Function to aggregate daily metrics
CREATE OR REPLACE FUNCTION aggregate_daily_metrics(target_date DATE)
RETURNS VOID AS $$
BEGIN
    INSERT INTO performance_metrics (
        date,
        total_transcripts,
        total_responses,
        total_silent_ignores,
        total_tool_calls,
        intent_greeting,
        intent_question,
        intent_email,
        intent_other,
        avg_classification_ms,
        avg_total_processing_ms,
        avg_tool_duration_ms,
        tool_success_rate,
        error_rate,
        total_sessions,
        avg_session_duration_minutes,
        avg_messages_per_session
    )
    SELECT
        target_date,
        COUNT(*),
        COUNT(*) FILTER (WHERE should_respond),
        COUNT(*) FILTER (WHERE NOT should_respond),
        COUNT(*) FILTER (WHERE tool_called IS NOT NULL),
        COUNT(*) FILTER (WHERE intent = 'greeting'),
        COUNT(*) FILTER (WHERE intent = 'question'),
        COUNT(*) FILTER (WHERE intent = 'email_request'),
        COUNT(*) FILTER (WHERE intent NOT IN ('greeting', 'question', 'email_request')),
        AVG(classification_ms),
        AVG(total_processing_ms),
        AVG(tool_duration_ms) FILTER (WHERE tool_duration_ms IS NOT NULL),
        (COUNT(*) FILTER (WHERE tool_success))::DECIMAL / NULLIF(COUNT(*) FILTER (WHERE tool_called IS NOT NULL), 0) * 100,
        (COUNT(*) FILTER (WHERE error_code IS NOT NULL))::DECIMAL / COUNT(*) * 100,
        (SELECT COUNT(DISTINCT session_id) FROM orchestrator_logs WHERE DATE(timestamp) = target_date),
        (SELECT AVG(EXTRACT(EPOCH FROM (last_activity - started_at)) / 60) FROM chat_sessions WHERE DATE(started_at) = target_date),
        (SELECT AVG(message_count) FROM chat_sessions WHERE DATE(started_at) = target_date)
    FROM orchestrator_logs
    WHERE DATE(timestamp) = target_date
    ON CONFLICT (date) DO UPDATE SET
        total_transcripts = EXCLUDED.total_transcripts,
        total_responses = EXCLUDED.total_responses,
        total_silent_ignores = EXCLUDED.total_silent_ignores,
        total_tool_calls = EXCLUDED.total_tool_calls,
        intent_greeting = EXCLUDED.intent_greeting,
        intent_question = EXCLUDED.intent_question,
        intent_email = EXCLUDED.intent_email,
        intent_other = EXCLUDED.intent_other,
        avg_classification_ms = EXCLUDED.avg_classification_ms,
        avg_total_processing_ms = EXCLUDED.avg_total_processing_ms,
        avg_tool_duration_ms = EXCLUDED.avg_tool_duration_ms,
        tool_success_rate = EXCLUDED.tool_success_rate,
        error_rate = EXCLUDED.error_rate,
        total_sessions = EXCLUDED.total_sessions,
        avg_session_duration_minutes = EXCLUDED.avg_session_duration_minutes,
        avg_messages_per_session = EXCLUDED.avg_messages_per_session;
END;
$$ LANGUAGE plpgsql;

-- Retention policy: Delete logs older than 30 days
CREATE OR REPLACE FUNCTION cleanup_old_logs()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM orchestrator_logs
    WHERE timestamp < NOW() - INTERVAL '30 days';
    GET DIAGNOSTICS deleted_count = ROW_COUNT;

    DELETE FROM conversation_history
    WHERE timestamp < NOW() - INTERVAL '30 days';

    DELETE FROM tool_executions
    WHERE timestamp < NOW() - INTERVAL '30 days';

    -- Mark old sessions as ended
    UPDATE chat_sessions
    SET ended_at = last_activity, end_reason = 'timeout'
    WHERE ended_at IS NULL
    AND last_activity < NOW() - INTERVAL '24 hours';

    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions (adjust role names as needed)
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO n8n_app;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO n8n_app;

COMMENT ON TABLE orchestrator_logs IS 'Primary log table for all orchestrator routing decisions';
COMMENT ON TABLE chat_sessions IS 'Session state management for multi-turn conversations';
COMMENT ON TABLE conversation_history IS 'Message history for AI context window';
COMMENT ON TABLE tool_executions IS 'Audit log for all tool/sub-workflow executions';
COMMENT ON TABLE performance_metrics IS 'Daily aggregated metrics for dashboards';
