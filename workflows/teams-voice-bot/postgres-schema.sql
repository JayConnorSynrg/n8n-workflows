-- Teams Voice Bot - PostgreSQL Schema
-- Created: 2025-12-28
-- Workflows: Orchestrator (d3CxEaYk5mkC8sLo), Gmail Agent (kL0AP3CkRby6OmVb), TTS Agent (DdwpUSXz7GCZuhlC)

-- ============================================
-- TABLE: bot_state
-- Purpose: Track conversation state per session
-- Used by: Load Bot State (Orchestrator)
-- ============================================
CREATE TABLE IF NOT EXISTS bot_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(255) NOT NULL,
    bot_id VARCHAR(255) NOT NULL,

    -- State tracking
    state VARCHAR(50) DEFAULT 'IDLE',
    email_chars TEXT DEFAULT '',
    pending_email JSONB DEFAULT NULL,
    message_count INTEGER DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Indexes for fast lookup
    CONSTRAINT unique_session UNIQUE (session_id)
);

CREATE INDEX IF NOT EXISTS idx_bot_state_session ON bot_state(session_id);
CREATE INDEX IF NOT EXISTS idx_bot_state_bot ON bot_state(bot_id);
CREATE INDEX IF NOT EXISTS idx_bot_state_created ON bot_state(created_at DESC);

-- ============================================
-- TABLE: interaction_logs
-- Purpose: Full interaction logging with classification
-- Used by: Save to Postgres (Orchestrator), Gmail Agent Logger
-- ============================================
CREATE TABLE IF NOT EXISTS interaction_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identifiers
    bot_id VARCHAR(255) NOT NULL,
    session_id VARCHAR(255) NOT NULL,

    -- Classification (from Fast Classifier)
    transcript TEXT,
    intent VARCHAR(100),
    route VARCHAR(50),
    is_complete_thought BOOLEAN DEFAULT FALSE,

    -- Agent decision
    action_taken VARCHAR(50),
    agent_output TEXT,

    -- TTS result
    tts_sent BOOLEAN DEFAULT FALSE,

    -- Tool calls (for sub-workflow tracking)
    tool_name VARCHAR(100),
    tool_input JSONB,
    tool_output JSONB,

    -- Timestamps
    received_at BIGINT,  -- Unix timestamp from workflow
    logged_at TIMESTAMPTZ DEFAULT NOW(),

    -- Status
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_logs_session ON interaction_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_logs_bot ON interaction_logs(bot_id);
CREATE INDEX IF NOT EXISTS idx_logs_intent ON interaction_logs(intent);
CREATE INDEX IF NOT EXISTS idx_logs_route ON interaction_logs(route);
CREATE INDEX IF NOT EXISTS idx_logs_logged ON interaction_logs(logged_at DESC);

-- ============================================
-- TABLE: n8n_chat_histories
-- Purpose: Postgres Chat Memory storage
-- Used by: Postgres Chat Memory node (auto-created by n8n, documented here)
-- Note: n8n creates this automatically, but define for completeness
-- ============================================
CREATE TABLE IF NOT EXISTS n8n_chat_histories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(255) NOT NULL,
    message JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_session ON n8n_chat_histories(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_created ON n8n_chat_histories(created_at DESC);

-- ============================================
-- TABLE: tts_logs
-- Purpose: Track TTS generation and delivery
-- Used by: TTS Agent Sub-Workflow
-- ============================================
CREATE TABLE IF NOT EXISTS tts_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identifiers
    bot_id VARCHAR(255) NOT NULL,
    session_id VARCHAR(255) NOT NULL,

    -- TTS details
    response_text TEXT,
    word_count INTEGER,
    voice_used VARCHAR(50),
    is_question BOOLEAN DEFAULT FALSE,
    is_acknowledgment BOOLEAN DEFAULT FALSE,

    -- Delivery status
    audio_generated BOOLEAN DEFAULT FALSE,
    audio_sent BOOLEAN DEFAULT FALSE,
    recall_response JSONB,

    -- Timestamps
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    sent_at TIMESTAMPTZ,

    -- Error tracking
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_tts_session ON tts_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_tts_bot ON tts_logs(bot_id);
CREATE INDEX IF NOT EXISTS idx_tts_generated ON tts_logs(generated_at DESC);

-- ============================================
-- TABLE: email_logs
-- Purpose: Track email composition and sending
-- Used by: Gmail Agent Sub-Workflow
-- ============================================
CREATE TABLE IF NOT EXISTS email_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identifiers
    bot_id VARCHAR(255),
    session_id VARCHAR(255),

    -- Email details
    recipient VARCHAR(255),
    subject VARCHAR(500),
    body TEXT,

    -- Status
    composed_at TIMESTAMPTZ DEFAULT NOW(),
    sent_at TIMESTAMPTZ,
    gmail_message_id VARCHAR(255),

    -- Result
    success BOOLEAN DEFAULT FALSE,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_email_session ON email_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_email_recipient ON email_logs(recipient);
CREATE INDEX IF NOT EXISTS idx_email_sent ON email_logs(sent_at DESC);

-- ============================================
-- FUNCTION: Update bot_state timestamp
-- ============================================
CREATE OR REPLACE FUNCTION update_bot_state_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_bot_state_timestamp
    BEFORE UPDATE ON bot_state
    FOR EACH ROW
    EXECUTE FUNCTION update_bot_state_timestamp();

-- ============================================
-- VIEWS: Useful queries for monitoring
-- ============================================

-- Recent interactions summary
CREATE OR REPLACE VIEW v_recent_interactions AS
SELECT
    session_id,
    bot_id,
    COUNT(*) as interaction_count,
    MAX(logged_at) as last_interaction,
    array_agg(DISTINCT intent) as intents,
    array_agg(DISTINCT route) as routes,
    SUM(CASE WHEN tts_sent THEN 1 ELSE 0 END) as tts_count
FROM interaction_logs
WHERE logged_at > NOW() - INTERVAL '24 hours'
GROUP BY session_id, bot_id
ORDER BY last_interaction DESC;

-- Active sessions
CREATE OR REPLACE VIEW v_active_sessions AS
SELECT
    bs.session_id,
    bs.bot_id,
    bs.state,
    bs.message_count,
    bs.updated_at,
    COUNT(il.id) as total_logs
FROM bot_state bs
LEFT JOIN interaction_logs il ON bs.session_id = il.session_id
WHERE bs.updated_at > NOW() - INTERVAL '1 hour'
GROUP BY bs.session_id, bs.bot_id, bs.state, bs.message_count, bs.updated_at
ORDER BY bs.updated_at DESC;

-- ============================================
-- GRANTS (adjust for your Supabase setup)
-- ============================================
-- GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated;
-- GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO authenticated;
