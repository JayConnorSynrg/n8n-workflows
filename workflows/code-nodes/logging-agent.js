/**
 * Logging Agent Code Node
 * Teams Voice Bot - Orchestrator Architecture v2.0
 *
 * Purpose: Prepare log entry for Postgres INSERT
 * Position: After Fast Classifier, before State Router
 *
 * NOTE: This code node prepares the log data. The actual INSERT
 * is performed by a Postgres node immediately after this.
 *
 * Input: Fast Classifier output + all upstream data
 * Output: { log_entry, original_data } (passes through to next nodes)
 */

// =============================================================================
// GATHER ALL CONTEXT
// =============================================================================

const classifier = $('Fast Classifier').first().json;
const stateData = $('Load Bot State').first().json;
const extractedData = $('Extract Transcript Data').first().json;

// Calculate timing
const receivedAt = extractedData.received_at || Date.now();
const classificationComplete = Date.now();
const classificationMs = classificationComplete - receivedAt;

// =============================================================================
// BUILD LOG ENTRY
// =============================================================================

const logEntry = {
  // Identity
  bot_id: extractedData.bot_id || stateData.bot_id || 'unknown',
  session_id: stateData.session_id || `session_${Date.now()}`,

  // Transcript
  transcript: classifier.metadata.transcript || '',

  // Classification Results
  intent: classifier.intent,
  route: classifier.route,
  is_complete_thought: classifier.isCompleteThought,
  should_respond: classifier.shouldRespond,
  confidence_score: classifier.confidence,

  // State Context
  previous_state: stateData.state || 'IDLE',
  new_state: null, // Will be set after handler processes

  // Timing
  classification_ms: classificationMs,

  // Metadata (as JSONB)
  state_data: {
    messageCount: stateData.message_count || 0,
    emailChars: stateData.email_chars || null,
    pendingEmail: stateData.pending_email || null,
    botAddressed: classifier.metadata.botAddressed || false
  },

  // Workflow version for debugging
  workflow_version: '2.0.0',

  // Node path tracking (will be updated by subsequent nodes)
  node_path: ['Webhook', 'Filter', 'Extract', 'Load State', 'Fast Classifier', 'Logging Agent']
};

// =============================================================================
// GENERATE SESSION ID IF NEEDED
// =============================================================================

// If this is a new conversation (IDLE state, first message), generate new session
if (stateData.state === 'IDLE' || !stateData.session_id) {
  const botId = extractedData.bot_id || 'bot';
  logEntry.session_id = `${botId}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

// =============================================================================
// PASS THROUGH ORIGINAL DATA
// =============================================================================

// We need to pass through the classifier result for the next nodes
const result = {
  ...classifier,
  log_entry: logEntry,
  _logging: {
    classificationMs,
    timestamp: new Date().toISOString()
  }
};

return [result];


// =============================================================================
// POSTGRES INSERT CONFIGURATION (for reference)
// =============================================================================

/*
The Postgres node after this should use:

Table: orchestrator_logs

Insert Query (use Execute Query operation):

INSERT INTO orchestrator_logs (
  bot_id,
  session_id,
  transcript,
  intent,
  route,
  is_complete_thought,
  should_respond,
  confidence_score,
  previous_state,
  classification_ms,
  state_data,
  workflow_version,
  node_path
) VALUES (
  {{ $json.log_entry.bot_id }},
  {{ $json.log_entry.session_id }},
  {{ $json.log_entry.transcript }},
  {{ $json.log_entry.intent }},
  {{ $json.log_entry.route }},
  {{ $json.log_entry.is_complete_thought }},
  {{ $json.log_entry.should_respond }},
  {{ $json.log_entry.confidence_score }},
  {{ $json.log_entry.previous_state }},
  {{ $json.log_entry.classification_ms }},
  {{ JSON.stringify($json.log_entry.state_data) }}::jsonb,
  {{ $json.log_entry.workflow_version }},
  {{ $json.log_entry.node_path }}::text[]
)
RETURNING id;

OR use the Postgres node with:
- Operation: Insert
- Table: orchestrator_logs
- Columns to match: Map each field from $json.log_entry
*/
