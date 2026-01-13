# Quick Reference: Integration Points

## Question 1: Does "Build Immutable Log" pass `session_state` to logging sub-workflow?

**Answer: YES ✓**

**Line of Code:**
```javascript
session_state: classifier.session_state || {
  last_orchestrator_cues: '',
  pending_actions: [],
  processing_count: 0
}
```

**Data Structure:**
```json
{
  "last_orchestrator_cues": "string",
  "pending_actions": ["tool1", "tool2"],
  "processing_count": 3,
  "session_start_time": 1234567890123
}
```

---

## Question 2: Does "Process Transcript" detect `is_first_message` and track `session_state`?

**Answer: YES to both ✓**

### is_first_message Detection

```javascript
const isFirstMessage = botState.processingCount === 0 || timeSinceLastProcess > 300000;
```

**Triggers:**
- Bot has never processed a message (processingCount === 0)
- OR no processing for 5+ minutes (300000ms)

### session_state Tracking

Uses **global workflow static data** keyed by bot_id:

```javascript
const botState = staticData.botTranscripts[bot_id];
```

**Tracked Fields:**
| Field | Type | Purpose |
|-------|------|---------|
| lastProcessedTranscript | string | Previous user input |
| lastProcessedTime | number | Timestamp of last processing |
| processingCount | number | Message counter per session |
| sessionStartTime | number | When session began |
| lastOrchestratorCues | string | AI output (updated by Build Immutable Log) |
| pendingActions | array | Tool calls awaiting user response |

---

## Question 3: What parameters are passed to logging sub-workflow (8LX5tt3SkO8GNuLj)?

**Answer: Complete immutable log record with session data**

### Parameters Passed from "Build Immutable Log" Node:

```javascript
{
  // Session tracking (from classifier)
  "session_state": { /* see above */ },
  "is_first_message": boolean,

  // User input
  "transcript_exact": string,

  // AI processing
  "agent_output_raw": string,
  "tool_calls": [
    {
      "tool": "string (tool name)",
      "input": { /* tool parameters */ },
      "output": string | null
    }
  ],

  // Timing
  "timestamps": {
    "received_at": number (ms),
    "processed_at": number (ms),
    "logged_at": string (ISO)
  },

  // Identifiers
  "session_id": string,
  "bot_id": string,

  // Classification
  "classifier_route": string ("PROCESS" | "SILENT" | "WAIT_LOG" | "LISTEN"),
  "classifier_intent": string ("email_request" | "greeting" | etc),

  // TTS/Audio
  "tts_result": {
    "success": boolean,
    "audio_sent": boolean,
    "call_count": number,
    "chunked": boolean,
    "source": "sentence_loop"
  },

  // Metadata
  "workflow_source": "orchestrator",
  "error_flags": {
    "agent_error": boolean,
    "tts_error": boolean
  }
}
```

### Node Configuration

```javascript
{
  "type": "n8n-nodes-base.executeWorkflow",
  "workflowId": {
    "__rl": true,
    "value": "8LX5tt3SkO8GNuLj",
    "mode": "id"
  },
  "options": {}
}
```

---

## Data Flow Summary

```
Process Transcript
  ├ Output: is_first_message (boolean)
  └ Output: session_state (4-field object)
           ↓
Build Immutable Log
  ├ Input: classifier.is_first_message ✓
  ├ Input: classifier.session_state ✓
  └ Output: Complete record including session_state + is_first_message
           ↓
Call Logging Agent (executeWorkflow)
  └ Calls: 8LX5tt3SkO8GNuLj with all data above
```

---

## Static Data Updates (Persistence Across Iterations)

**Build Immutable Log updates global state:**

```javascript
const staticData = $getWorkflowStaticData('global');
staticData.botTranscripts[context.bot_id].lastOrchestratorCues = agent.output || '';
staticData.botTranscripts[context.bot_id].pendingActions = pendingTools;
```

This feeds back into **Process Transcript** on the next webhook call:

```javascript
const botState = staticData.botTranscripts[bot_id];
// Uses updated lastOrchestratorCues and pendingActions in next iteration
```

---

## Key Node IDs

| Component | ID |
|-----------|-----|
| Process Transcript | `process-transcript` |
| Build Immutable Log | `log-1` |
| Call Logging Agent | `call-logging-agent` |
| Target Sub-workflow | `8LX5tt3SkO8GNuLj` |
| Main Workflow | `d3CxEaYk5mkC8sLo` |
