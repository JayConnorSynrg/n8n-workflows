-- ============================================================
-- ENTERPRISE VOICE AGENT - DATABASE SCHEMA
-- ============================================================
-- Run this SQL to set up the required tables for logging and analytics

-- 1. Tool Executions (core logging)
-- Tracks every tool call made by the voice agent
CREATE TABLE IF NOT EXISTS tool_executions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL,
    connection_id VARCHAR(100) NOT NULL,
    function_name VARCHAR(100) NOT NULL,
    args JSONB,
    result JSONB,
    voice_response TEXT,
    status VARCHAR(20) DEFAULT 'success', -- success, error, timeout
    execution_time_ms INTEGER,
    retry_attempts INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tool_exec_session ON tool_executions(session_id);
CREATE INDEX IF NOT EXISTS idx_tool_exec_function ON tool_executions(function_name);
CREATE INDEX IF NOT EXISTS idx_tool_exec_status ON tool_executions(status);
CREATE INDEX IF NOT EXISTS idx_tool_exec_created ON tool_executions(created_at DESC);

-- 2. Audit Trail (compliance + debugging)
-- Tracks all significant events for debugging and compliance
CREATE TABLE IF NOT EXISTS audit_trail (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(100) NOT NULL,
    connection_id VARCHAR(100) NOT NULL,
    event_type VARCHAR(50) NOT NULL,  -- tool_call, error, state_change, connection
    event_source VARCHAR(50),          -- relay_server, n8n, openai, recall_ai
    severity VARCHAR(20) DEFAULT 'INFO', -- DEBUG, INFO, WARN, ERROR, CRITICAL
    event_data JSONB NOT NULL,
    user_email VARCHAR(255),
    meeting_id VARCHAR(100),
    latency_ms INTEGER,
    trace_id VARCHAR(36),
    event_timestamp TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_session ON audit_trail(session_id);
CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_trail(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_severity ON audit_trail(severity);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_trail(event_timestamp DESC);

-- 3. Training Metrics (employee learning)
-- Tracks training interactions and knowledge assessments
CREATE TABLE IF NOT EXISTS training_metrics (
    id SERIAL PRIMARY KEY,
    user_email VARCHAR(255) NOT NULL,
    session_id VARCHAR(100) NOT NULL,
    topic VARCHAR(100),
    event_type VARCHAR(50),  -- concept_explanation, knowledge_check, procedure_step, quiz_complete
    question_asked TEXT,
    user_response TEXT,
    correct_answer TEXT,
    is_correct BOOLEAN,
    confidence_score FLOAT,
    knowledge_gap VARCHAR(255),
    time_spent_seconds INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_training_user ON training_metrics(user_email);
CREATE INDEX IF NOT EXISTS idx_training_topic ON training_metrics(topic);
CREATE INDEX IF NOT EXISTS idx_training_created ON training_metrics(created_at DESC);

-- 4. User Session Analytics (daily usage)
-- Aggregated session statistics for reporting
CREATE TABLE IF NOT EXISTS user_session_analytics (
    id SERIAL PRIMARY KEY,
    user_email VARCHAR(255) NOT NULL,
    session_id VARCHAR(100) NOT NULL,
    bot_id VARCHAR(100),
    session_duration_seconds INTEGER,
    total_interactions INTEGER,
    tools_called INTEGER,
    tools_successful INTEGER,
    training_interactions INTEGER,
    documentation_queries INTEGER,
    sentiment_score FLOAT,
    audio_quality_score FLOAT,
    packet_loss_rate FLOAT,
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analytics_user ON user_session_analytics(user_email);
CREATE INDEX IF NOT EXISTS idx_analytics_started ON user_session_analytics(started_at DESC);

-- ============================================================
-- ANALYTICS VIEWS
-- ============================================================

-- Tool success rate by hour
CREATE OR REPLACE VIEW v_tool_success_rates AS
SELECT
    function_name,
    DATE_TRUNC('hour', created_at) as hour,
    COUNT(*) as total,
    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful,
    ROUND(100.0 * SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
FROM tool_executions
GROUP BY function_name, DATE_TRUNC('hour', created_at)
ORDER BY hour DESC;

-- User engagement metrics (last 30 days)
CREATE OR REPLACE VIEW v_user_engagement AS
SELECT
    user_email,
    COUNT(DISTINCT session_id) as total_sessions,
    SUM(total_interactions) as total_interactions,
    AVG(session_duration_seconds) as avg_session_duration,
    SUM(training_interactions) as training_activities,
    SUM(documentation_queries) as doc_queries,
    AVG(audio_quality_score) as avg_audio_quality
FROM user_session_analytics
WHERE started_at > NOW() - INTERVAL '30 days'
GROUP BY user_email
ORDER BY total_interactions DESC;

-- Training progress by topic
CREATE OR REPLACE VIEW v_training_progress AS
SELECT
    user_email,
    topic,
    COUNT(*) as total_attempts,
    SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) as correct,
    ROUND(100.0 * SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) / COUNT(*), 2) as accuracy_pct,
    AVG(confidence_score) as avg_confidence,
    SUM(time_spent_seconds) as total_time_spent_seconds
FROM training_metrics
WHERE is_correct IS NOT NULL
GROUP BY user_email, topic
ORDER BY user_email, accuracy_pct DESC;

-- Error frequency by type (last 7 days)
CREATE OR REPLACE VIEW v_error_frequency AS
SELECT
    event_type,
    event_source,
    severity,
    COUNT(*) as error_count,
    DATE_TRUNC('day', event_timestamp) as day
FROM audit_trail
WHERE severity IN ('ERROR', 'CRITICAL')
  AND event_timestamp > NOW() - INTERVAL '7 days'
GROUP BY event_type, event_source, severity, DATE_TRUNC('day', event_timestamp)
ORDER BY day DESC, error_count DESC;

-- Active sessions summary
CREATE OR REPLACE VIEW v_active_sessions AS
SELECT
    session_id,
    user_email,
    bot_id,
    started_at,
    EXTRACT(EPOCH FROM (NOW() - started_at)) / 60 as duration_minutes,
    total_interactions,
    tools_called,
    audio_quality_score
FROM user_session_analytics
WHERE ended_at IS NULL
ORDER BY started_at DESC;

-- ============================================================
-- SAMPLE DATA (for testing - remove in production)
-- ============================================================

-- Uncomment to insert test data:
-- INSERT INTO tool_executions (session_id, connection_id, function_name, args, result, status, execution_time_ms)
-- VALUES
--   ('test_session_1', 'conn_1', 'send_email', '{"to": "test@example.com", "subject": "Test"}', '{"success": true}', 'success', 342),
--   ('test_session_1', 'conn_1', 'schedule_meeting', '{"title": "Team Sync"}', '{"eventId": "evt_123"}', 'success', 256);

-- ============================================================
-- GATED EXECUTION TABLES (Voice Agent v2)
-- ============================================================

-- Tool Calls with Gated Execution Status
-- Tracks tool calls through EXECUTING → COMPLETED/FAILED/CANCELLED states
CREATE TABLE IF NOT EXISTS tool_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tool_call_id VARCHAR(100) UNIQUE NOT NULL,
    session_id VARCHAR(100) NOT NULL,
    intent_id VARCHAR(100),
    function_name VARCHAR(100) NOT NULL,
    parameters JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(20) NOT NULL DEFAULT 'EXECUTING',
    result JSONB,
    error_message TEXT,
    voice_response TEXT,
    callback_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    execution_time_ms INTEGER,
    CONSTRAINT valid_tool_call_status CHECK (
        status IN ('EXECUTING', 'COMPLETED', 'FAILED', 'CANCELLED')
    )
);

CREATE INDEX IF NOT EXISTS idx_tool_calls_session
ON tool_calls(session_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_tool_calls_status
ON tool_calls(status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_tool_calls_id
ON tool_calls(tool_call_id);

COMMENT ON TABLE tool_calls IS 'Gated execution tracking for voice agent tool calls';
COMMENT ON COLUMN tool_calls.tool_call_id IS 'Unique identifier (tc_xxx format) for relay correlation';
COMMENT ON COLUMN tool_calls.intent_id IS 'Intent ID from pre-confirmation phase in relay';
COMMENT ON COLUMN tool_calls.status IS 'Gate status: EXECUTING, COMPLETED, FAILED, CANCELLED';
COMMENT ON COLUMN tool_calls.voice_response IS 'TTS text for agent to speak on completion';
COMMENT ON COLUMN tool_calls.callback_url IS 'Relay server endpoint for gate callbacks';

-- Session Context for Cross-Tool Data Sharing
-- Stores query results that can be referenced in email drafting
CREATE TABLE IF NOT EXISTS session_context (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(100) NOT NULL,
    context_key VARCHAR(100) NOT NULL,
    context_value JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '1 hour'),
    UNIQUE(session_id, context_key)
);

-- Partial index for active (non-expired) context lookups
CREATE INDEX IF NOT EXISTS idx_session_context_lookup
ON session_context(session_id, context_key)
WHERE expires_at > NOW();

-- Index for cleanup of expired entries
CREATE INDEX IF NOT EXISTS idx_session_context_expiry
ON session_context(expires_at);

COMMENT ON TABLE session_context IS 'Cross-tool data sharing with 1-hour default expiry';
COMMENT ON COLUMN session_context.context_key IS 'Named key (e.g., last_query_results)';
COMMENT ON COLUMN session_context.context_value IS 'JSONB data for cross-tool reference';

-- Update trigger for session_context.updated_at
CREATE OR REPLACE FUNCTION update_session_context_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_session_context_updated_at ON session_context;
CREATE TRIGGER trigger_session_context_updated_at
    BEFORE UPDATE ON session_context
    FOR EACH ROW
    EXECUTE FUNCTION update_session_context_updated_at();

-- Cleanup function for expired session context
CREATE OR REPLACE FUNCTION cleanup_expired_session_context()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM session_context WHERE expires_at < NOW();
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- CLEANUP (if needed)
-- ============================================================

-- To drop all tables and start fresh:
-- DROP TABLE IF EXISTS tool_executions CASCADE;
-- DROP TABLE IF EXISTS audit_trail CASCADE;
-- DROP TABLE IF EXISTS training_metrics CASCADE;
-- DROP TABLE IF EXISTS user_session_analytics CASCADE;
-- DROP TABLE IF EXISTS tool_calls CASCADE;
-- DROP TABLE IF EXISTS session_context CASCADE;
-- DROP VIEW IF EXISTS v_tool_success_rates;
-- DROP VIEW IF EXISTS v_user_engagement;
-- DROP VIEW IF EXISTS v_training_progress;
-- DROP VIEW IF EXISTS v_error_frequency;
-- DROP VIEW IF EXISTS v_active_sessions;
