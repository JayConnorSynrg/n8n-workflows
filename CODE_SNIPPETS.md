# Exact Code Snippets from Integration Points

## File Locations
- Workflow: `/Users/jelalconnor/CODING/N8N/Workflows/d3CxEaYk5mkC8sLo.json` (main workflow)
- Sub-workflow: Target ID `8LX5tt3SkO8GNuLj`

---

## 1. Process Transcript Node (process-transcript)

### is_first_message Detection

```javascript
// === SESSION STATE & DEDUPLICATION v3 ===
const staticData = $getWorkflowStaticData('global');
const now = Date.now();

if (!staticData.botTranscripts) staticData.botTranscripts = {};
if (!staticData.botTranscripts[bot_id]) {
  staticData.botTranscripts[bot_id] = {
    lastProcessedTranscript: '',
    lastProcessedTime: 0,
    processingCount: 0,
    sessionStartTime: now,
    lastOrchestratorCues: '',
    pendingActions: []
  };
}

const botState = staticData.botTranscripts[bot_id];
const lastTranscript = botState.lastProcessedTranscript;
const timeSinceLastProcess = now - botState.lastProcessedTime;

// First message detection (no prior processing OR > 5 min inactive)
const isFirstMessage = botState.processingCount === 0 || timeSinceLastProcess > 300000;
if (isFirstMessage && timeSinceLastProcess > 300000) {
  botState.sessionStartTime = now;
  botState.processingCount = 0;
  botState.lastOrchestratorCues = '';
  botState.pendingActions = [];
}
```

### Session State in Output

```javascript
return {
  json: {
    // ... other fields ...
    is_first_message: isFirstMessage,
    response_timing: {
      is_complete_thought: isCompleteThought,
      has_end_punctuation: hasEndPunctuation,
      word_count: wordCount,
      speaking_duration_ms: speakingDurationMs,
      response_urgency: responseUrgency
    },
    session_state: {
      last_orchestrator_cues: botState.lastOrchestratorCues,
      pending_actions: botState.pendingActions,
      processing_count: botState.processingCount,
      session_start_time: botState.sessionStartTime
    },
    dedup: {
      is_duplicate: isDuplicate,
      is_extension: isExtension,
      reason: dedupReason,
      last_processed: lastTranscript,
      time_since_last_ms: timeSinceLastProcess,
      processing_count: botState.processingCount
    },
    classified_at: new Date().toISOString()
  }
};
```

---

## 2. Build Immutable Log Node (log-1)

### Complete Source Code

```javascript
// Build Immutable Log v2.1 - Enhanced with session_state and is_first_message
const agent = $('Orchestrator Agent').first().json;
const context = $('Build Agent Context').first().json;
const classifier = $('Process Transcript').first().json;

let ttsSuccess = false, sentenceCount = 0;
let ttsMessage = agent.output || '';

try {
  const sentenceData = $('Split into Sentences').first();
  if (sentenceData && sentenceData.json) {
    sentenceCount = sentenceData.json.total_sentences || 1;
    ttsSuccess = true;
  }
} catch (e) { sentenceCount = 1; }

try {
  const sendResults = $('Send Sentence Audio').all();
  if (sendResults && sendResults.length > 0) {
    ttsSuccess = sendResults.every(r => !r.json.error);
  }
} catch (e) {}

let toolCalls = [];
try {
  if (agent.intermediateSteps) {
    toolCalls = agent.intermediateSteps.map(step => ({
      tool: (step.action && step.action.tool) || 'unknown',
      input: (step.action && step.action.toolInput) || {},
      output: step.observation || null
    }));
  }
  if (agent.steps && agent.steps.length > 0) {
    toolCalls = agent.steps.map(step => ({
      tool: (step.action && step.action.tool) || 'unknown',
      input: (step.action && step.action.toolInput) || {},
      output: step.observation || null
    }));
  }
} catch (e) { toolCalls = []; }

toolCalls.push({
  tool: 'chunked_tts',
  input: { message: ttsMessage, sentence_count: sentenceCount },
  output: ttsSuccess ? 'Sent ' + sentenceCount + ' audio chunks' : 'TTS failed'
});

// Update static data with orchestrator cues for next iteration
const staticData = $getWorkflowStaticData('global');
if (staticData.botTranscripts && staticData.botTranscripts[context.bot_id]) {
  // Store the AI output for next iteration's session_state
  staticData.botTranscripts[context.bot_id].lastOrchestratorCues = agent.output || '';
  // Track pending actions from tool calls
  const pendingTools = toolCalls.filter(tc =>
    tc.tool !== 'chunked_tts' && tc.tool !== 'think' &&
    tc.output && tc.output.includes && tc.output.includes('pending')
  ).map(tc => tc.tool);
  staticData.botTranscripts[context.bot_id].pendingActions = pendingTools;
}

return {
  transcript_exact: context.user_input || '',
  agent_output_raw: agent.output || '',
  tool_calls: toolCalls,
  timestamps: {
    received_at: context.received_at,
    processed_at: Date.now(),
    logged_at: new Date().toISOString()
  },
  session_id: context.session_id,
  bot_id: context.bot_id,
  classifier_route: classifier.route,
  classifier_intent: classifier.intent,
  tts_result: {
    success: ttsSuccess,
    audio_sent: ttsSuccess,
    call_count: sentenceCount,
    chunked: true,
    source: 'sentence_loop'
  },
  workflow_source: 'orchestrator',
  error_flags: {
    agent_error: !agent.output,
    tts_error: !ttsSuccess
  },
  // NEW: Pass session state and first message flag to logging sub-workflow
  session_state: classifier.session_state || {
    last_orchestrator_cues: '',
    pending_actions: [],
    processing_count: 0
  },
  is_first_message: classifier.is_first_message || false
};
```

### Key Lines Accessing Classifier Data

```javascript
// Line 3: Retrieve Process Transcript output
const classifier = $('Process Transcript').first().json;

// Line 72-82: Access classifier data in return object
classifier_route: classifier.route,
classifier_intent: classifier.intent,

// Line 94-99: Access session_state and is_first_message
session_state: classifier.session_state || {
  last_orchestrator_cues: '',
  pending_actions: [],
  processing_count: 0
},
is_first_message: classifier.is_first_message || false
```

---

## 3. Call Logging Agent Node Configuration

### Node Configuration (n8n-nodes-base.executeWorkflow)

```json
{
  "type": "n8n-nodes-base.executeWorkflow",
  "typeVersion": 1.2,
  "id": "call-logging-agent",
  "name": "Call Logging Agent",
  "position": [1200, 500],
  "parameters": {
    "workflowId": {
      "__rl": true,
      "value": "8LX5tt3SkO8GNuLj",
      "mode": "id"
    },
    "options": {}
  }
}
```

### Data Flow from Build Immutable Log

The complete output from Build Immutable Log becomes the input to the sub-workflow:

**Passed Parameters:**
```javascript
{
  // From classifier (Process Transcript output)
  "session_state": {
    "last_orchestrator_cues": "string",
    "pending_actions": ["string"],
    "processing_count": 3,
    "session_start_time": 1234567890
  },
  "is_first_message": true,

  // From context (Build Agent Context)
  "transcript_exact": "hello bot",
  "session_id": "bot-123_session",
  "bot_id": "bot-123",

  // From agent (Orchestrator Agent)
  "agent_output_raw": "Hello! How can I help?",

  // Tool tracking
  "tool_calls": [
    {
      "tool": "gmail_agent",
      "input": { "email_address": "test@example.com" },
      "output": "Email sent"
    },
    {
      "tool": "chunked_tts",
      "input": { "message": "Hello! How can I help?", "sentence_count": 1 },
      "output": "Sent 1 audio chunks"
    }
  ],

  // Timing
  "timestamps": {
    "received_at": 1234567890000,
    "processed_at": 1234567891000,
    "logged_at": "2026-01-09T18:22:39.628Z"
  },

  // Classification
  "classifier_route": "PROCESS",
  "classifier_intent": "greeting",

  // Audio result
  "tts_result": {
    "success": true,
    "audio_sent": true,
    "call_count": 1,
    "chunked": true,
    "source": "sentence_loop"
  },

  // Metadata
  "workflow_source": "orchestrator",
  "error_flags": {
    "agent_error": false,
    "tts_error": false
  }
}
```

---

## Static Data Mechanism (Cross-Iteration State)

### How Process Transcript Accesses Previous Session State

```javascript
const staticData = $getWorkflowStaticData('global');
const botState = staticData.botTranscripts[bot_id];

// These values were set by Build Immutable Log in previous iteration:
console.log(botState.lastOrchestratorCues);  // AI response from previous
console.log(botState.pendingActions);         // Tools awaiting input from previous
console.log(botState.processingCount);        // Running counter
```

### How Build Immutable Log Updates for Next Iteration

```javascript
const staticData = $getWorkflowStaticData('global');
if (staticData.botTranscripts && staticData.botTranscripts[context.bot_id]) {
  // Update for next iteration
  staticData.botTranscripts[context.bot_id].lastOrchestratorCues = agent.output || '';
  staticData.botTranscripts[context.bot_id].pendingActions = pendingTools;

  // Note: processingCount is updated by Process Transcript, not here
  // Note: sessionStartTime is updated by Process Transcript on isFirstMessage detection
}
```

---

## Connection Definition

### Workflow Connections

```json
{
  "Build Immutable Log": {
    "main": [[
      {
        "node": "Call Logging Agent",
        "type": "main",
        "index": 0
      }
    ]]
  }
}
```

This means:
- Output from "Build Immutable Log" (main output 0) flows to "Call Logging Agent"
- All data in the return object becomes available as input to Call Logging Agent
- Call Logging Agent passes this data to sub-workflow `8LX5tt3SkO8GNuLj`

---

## Example Execution Trace

```
1. Webhook receives: { body: { data: { words: [...], participant: {...} } } }

2. Process Transcript executes:
   - Static data lookup by bot_id
   - Detects is_first_message (e.g., processingCount = 0)
   - Creates session_state object
   - Returns: { is_first_message: true, session_state: {...}, ... }

3. Route Switch: Routes to PROCESS (assumes complete thought)

4. Build Agent Context: Loads history, builds system prompt

5. Orchestrator Agent: Calls LLM with system prompt
   - Returns: { output: "Hello! How can I help?", intermediateSteps: [...] }

6. Build Immutable Log executes:
   - Accesses classifier.is_first_message ✓
   - Accesses classifier.session_state ✓
   - Updates static data: lastOrchestratorCues = "Hello! How can I help?"
   - Returns: { session_state: {...}, is_first_message: true, ... }

7. Call Logging Agent executes:
   - Calls 8LX5tt3SkO8GNuLj with all data from step 6
   - Sub-workflow receives: session_state, is_first_message, etc.

8. Next webhook arrives for same bot:
   - Process Transcript reads static data
   - processingCount is now 1 (was incremented in step 2)
   - isFirstMessage = false (processingCount !== 0)
   - lastOrchestratorCues = "Hello! How can I help?" (from step 6)
```
