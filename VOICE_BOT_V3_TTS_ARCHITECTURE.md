# Teams Voice Bot v3.0 - TTS & Recall.ai Architecture Analysis

**Workflow ID:** `d3CxEaYk5mkC8sLo`
**Status:** ACTIVE (Last updated: 2026-01-10)
**Architecture:** Agent Orchestrator with Parallel TTS → Sequential Recall.ai Delivery

---

## 1. VOICE RESPONSE PATH (Output Architecture)

### Data Flow: Agent Response → TTS → Recall.ai

```
Orchestrator Agent (AI response)
         ↓
Check Agent Output (extract text)
         ↓
Split into Sentences (chunk for TTS)
         ↓
Parallel TTS & Send (CRITICAL NODE)
         ├─ Step 1: Check bot status in Recall.ai
         ├─ Step 2: Generate ALL audio in parallel (OpenAI TTS)
         └─ Step 3: Send sequentially to Recall.ai output_audio endpoint
         ↓
Return Summary (success/failure metrics)
```

### Alternative Quick Path (Pre-Router Fast Track)

```
Ultra-Fast Pre-Router (detects immediate responses)
         ↓
Pre-Route Switch (routes QUICK_RESPOND path)
         ↓
Quick Acknowledge or Quick Reply (fast text generation)
         ↓
Split into Sentences (chunks quick response)
         ↓
Parallel TTS & Send (same TTS/Recall pipeline)
```

---

## 2. PARALLEL TTS & SEND NODE (Complete Architecture)

**Node Name:** `Parallel TTS & Send`
**Node Type:** `n8n-nodes-base.code`
**Location in Flow:** Final stage before webhook response

### Critical Implementation Details

#### Step 0: Bot Status Validation
```javascript
// Verify bot is actively recording/in-call before sending audio
GET https://us-west-2.recall.ai/api/v1/bot/{bot_id}/

// Valid active states:
// - in_call_recording
// - in_call_not_recording

// If bot not active → SKIP all TTS generation, return summary with skip reason
```

#### Step 1: Parallel TTS Generation
```javascript
// For EACH sentence (in parallel):
POST https://api.openai.com/v1/audio/speech
{
  model: "tts-1",
  voice: "alloy" (configurable per user),
  input: "sentence text",
  response_format: "mp3"
}
// Returns MP3 audio → Base64 encode
```

#### Step 2: Sequential Recall.ai Delivery
```javascript
// For EACH generated audio (sequential, in-order):
POST https://us-west-2.recall.ai/api/v1/bot/{bot_id}/output_audio/
{
  "kind": "mp3",
  "b64_data": "base64-encoded-mp3-data"
}
// Must maintain sentence order!
```

### Input Contract (from Split into Sentences)
```json
{
  "sentence": "string - single sentence",
  "sentence_index": "number - order position",
  "total_sentences": "number - total count",
  "bot_id": "string - REQUIRED for Recall.ai API call",
  "response_type": "quick|agent - determines origin",
  "full_output": "string - original response",
  "route_taken": "FULL_PROCESS|QUICK_RESPOND"
}
```

### Output Contract (to webhook response)
```json
{
  "tts_summary": {
    "total_sentences": 3,
    "tts_generated": 3,       // Successfully created audio
    "tts_failed": 0,          // Failed OpenAI calls
    "audio_sent": 3,          // Successfully sent to Recall.ai
    "send_failed": 0,         // Failed Recall.ai sends
    "send_errors": [],        // Error messages from failed sends
    "bot_status": "in_call_recording|in_call_not_recording|check_failed|unknown",
    "skipped_reason": "if bot_status check failed"
  }
}
```

---

## 3. BOT_ID VARIABLE TRACKING

### Where bot_id Originates
```
Webhook POST body
  ↓
Process Transcript (extracts from body.data.bot)
  ↓
bot_id field created in JSON payload
```

### bot_id Usage Throughout Pipeline

| Node | Usage | Source |
|------|-------|--------|
| Process Transcript | Extracts from webhook | `body.data.bot.id` |
| Route Switch | Routes based on intent | Passed through |
| Load Bot State | Filters bot-specific history | Uses as WHERE clause |
| Build Agent Context | Includes in system context | For reference only |
| Split into Sentences | MUST pass to TTS node | `input.bot_id` or via Pre-Route Switch |
| Parallel TTS & Send | **CRITICAL REQUIRED** | For both Status & output_audio endpoints |

### Critical Path: bot_id to Recall.ai

**Split into Sentences → Parallel TTS & Send**

```javascript
// In Split into Sentences v3.0:
let botId = 'unknown';

// Priority 1: From Quick Response input
if (input.response_text) {
  botId = input.bot_id || 'unknown';  // ← Quick path
}

// Priority 2: From Build Agent Context (agent path)
else if (input.output) {
  try {
    const agentContext = $('Build Agent Context').first().json;
    botId = agentContext.bot_id || 'unknown';  // ← Agent path
  } catch (e) {
    // Fallback to Pre-Route Switch
    botId = $('Pre-Route Switch').first().json.bot_id || 'unknown';
  }
}

// Returns in every sentence item:
{ sentence: "text", bot_id: botId, ... }
```

**Then in Parallel TTS & Send:**

```javascript
const items = $input.all();
const bot_id = items[0].json.bot_id;  // ← CRITICAL: Used for both API calls

// Bot Status Check:
GET https://us-west-2.recall.ai/api/v1/bot/${bot_id}/

// Audio Delivery:
POST https://us-west-2.recall.ai/api/v1/bot/${bot_id}/output_audio/
```

---

## 4. TTS NODES & AUDIO OUTPUT HANDLING

### Node: Split into Sentences
**Purpose:** Chunk agent response for progressive audio delivery
**Input:** Agent output text or quick response
**Output:** Array of sentence items (one item per sentence)

**Key Logic:**
```javascript
// Sentence pattern: ends with . ! ? (with/without trailing space)
const sentencePattern = /[^.!?]*[.!?]+(?:\s|$)/g;
let sentences = responseText.match(sentencePattern) || [responseText];

// If no punctuation found, treat entire response as one sentence
// Returns array where each item has: sentence, sentence_index, bot_id
```

**bot_id Extraction Priority:**
1. From `input.response_text` path (Quick Acknowledge/Quick Reply)
2. From `Build Agent Context` (Orchestrator Agent path)
3. From `Pre-Route Switch` (fallback)

### Node: Parallel TTS & Send
**Purpose:** Convert sentences to MP3 and deliver to Recall.ai
**Input:** Array of sentence items
**Output:** Summary with success/failure metrics

**APIs Used:**
- **OpenAI TTS:** `POST https://api.openai.com/v1/audio/speech`
  - Returns binary MP3 data → convert to Base64
  - Parallel execution (Promise.all)

- **Recall.ai Bot Status:** `GET https://us-west-2.recall.ai/api/v1/bot/{bot_id}/`
  - Checks `status_changes[last].code`
  - Valid states: `in_call_recording`, `in_call_not_recording`

- **Recall.ai Output Audio:** `POST https://us-west-2.recall.ai/api/v1/bot/{bot_id}/output_audio/`
  - Sends MP3 data in sequence
  - Payload: `{ "kind": "mp3", "b64_data": "base64..." }`

---

## 5. RECALL.AI INTEGRATION POINTS

### Current Implementation

#### 1. Bot Status Checking (v2 feature)
```javascript
// STEP 0 of Parallel TTS & Send
const statusResponse = await this.helpers.httpRequest({
  method: 'GET',
  url: `https://us-west-2.recall.ai/api/v1/bot/${bot_id}/`,
  headers: { 'Authorization': `Token ${RECALL_API_KEY}` },
  returnFullResponse: false
});

// Check last status in status_changes array
if (statusResponse.status_changes && statusResponse.status_changes.length > 0) {
  const lastStatus = statusResponse.status_changes[statusResponse.status_changes.length - 1];
  botStatus = lastStatus.code;
  botActive = ['in_call_recording', 'in_call_not_recording'].includes(botStatus);
}

// If not active: Return skip summary without generating TTS
```

#### 2. Audio Output Delivery (Sequential)
```javascript
// STEP 2 of Parallel TTS & Send
for (const audio of successfulAudio) {
  // Send each sentence's audio in order
  await this.helpers.httpRequest({
    method: 'POST',
    url: `https://us-west-2.recall.ai/api/v1/bot/${bot_id}/output_audio/`,
    headers: {
      'Authorization': `Token ${RECALL_API_KEY}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      kind: 'mp3',
      b64_data: audio.audio_base64
    }),
    returnFullResponse: false
  });
}
```

#### 3. Credentials/Constants (Hardcoded - SECURITY RISK)
```javascript
const OPENAI_API_KEY = 'OPENAI_API_KEY_REDACTED';
const RECALL_API_KEY = '4f12c2c033fc1f0fe1e4ca2fcd0aad92b547ff43';
```

**⚠️ CRITICAL SECURITY ISSUE:** API keys hardcoded in workflow

---

## 6. RESPONSE ROUTING ARCHITECTURE

### Three Paths to TTS

#### Path A: PROCESS (Full Agent Execution)
```
Process Transcript → Route Switch (PROCESS) → Load Bot State
  ↓
Build Agent Context → Orchestrator Agent → Check Agent Output
  ↓
Split into Sentences ← input.output (agent response)
  ↓
Parallel TTS & Send (bot_id from Build Agent Context)
```

#### Path B: QUICK_RESPOND (Pre-Router Fast Track)
```
Process Transcript → Route Switch (FULL_PROCESS)
  ↓
Ultra-Fast Pre-Router → Pre-Route Switch (QUICK_RESPOND)
  ↓
Quick Acknowledge or Quick Reply → Split into Sentences
  ↓
Split into Sentences ← input.response_text (quick response)
  ↓
Parallel TTS & Send (bot_id from input.response_text)
```

#### Path C: WAIT_LOG or SILENT (No Audio)
```
Process Transcript → Route Switch → Wait Log Only or Log Silent
  ↓
No TTS, No Recall.ai delivery
```

### Pre-Route Switch Decision Points
```javascript
// "Pre-Route Switch" node determines QUICK_RESPOND eligibility:
// - is_bot_addressed? → Quick Acknowledge
// - has_request? → Quick Reply (with context)
// - Everything else → FULL_PROCESS
```

---

## 7. CURRENT BOT_ID FLOW VERIFICATION

### From Webhook to Recall.ai

```
1. Webhook receives POST
   ├── body.data.bot.id = "bot_12345"
   └── body.data.data.participant.name = "John"

2. Process Transcript extracts:
   ├── bot_id = body.data.bot.id
   ├── speaker = participant.name
   └── transcript = words joined

3. Route Switch branches (based on route classification)

4a. PROCESS Path:
    ├── Load Bot State (uses bot_id as filter)
    ├── Build Agent Context (includes bot_id)
    ├── Orchestrator Agent (uses for context only)
    └── Check Agent Output (passes bot_id through)

4b. QUICK_RESPOND Path:
    ├── Quick Acknowledge/Reply (generates response)
    └── Passes bot_id explicitly

5. Split into Sentences:
   ├── Extracts bot_id from:
   │   ├── input.bot_id (quick path), OR
   │   ├── Build Agent Context.bot_id (agent path), OR
   │   └── Pre-Route Switch.bot_id (fallback)
   └── Creates sentence items with bot_id included

6. Parallel TTS & Send:
   ├── Receives items[0].json.bot_id
   ├── Checks bot status: GET /api/v1/bot/{bot_id}/
   ├── Generates TTS for all sentences (parallel)
   └── Sends audio to: POST /api/v1/bot/{bot_id}/output_audio/
```

---

## 8. EXISTING RECALL.AI REFERENCES

### In Codebase
- **Parallel TTS & Send:** Lines 45-150+ (complete Recall.ai integration)
  - Bot status check (GET endpoint)
  - Output audio delivery (POST endpoint)
  - Error handling and summary reporting

### In Comments
- Line 2: "PARALLEL TTS GENERATION → SEQUENTIAL RECALL.AI DELIVERY"
- Line 3: "v2: Added bot status check before sending"
- Step 0, Step 1, Step 2 comments document the flow

### API Keys Location
- Hardcoded in Parallel TTS & Send node
- **NEEDS MIGRATION** to n8n Environment Variables or Credentials Manager

---

## 9. KEY ARCHITECTURE DECISIONS

| Decision | Current Implementation | Why |
|----------|------------------------|-----|
| TTS Generation | **Parallel** (Promise.all) | Minimize latency for multi-sentence responses |
| Recall.ai Delivery | **Sequential** (for loop) | Maintain sentence order for coherent speech |
| Bot Status Check | **Pre-TTS** (Step 0) | Skip expensive OpenAI calls if bot offline |
| Sentence Splitting | **Regex punctuation** | Natural speech boundaries, no ML overhead |
| bot_id Handling | **Multi-path extraction** | Support both quick and agent paths |
| Voice Selection | **Configurable "alloy"** | Can be overridden per user in input |

---

## 10. INTEGRATION REQUIREMENTS FOR RELAY SERVER

### What the Relay Server Must Do

1. **Forward Recall.ai Status Webhook**
   - Receive bot status changes from Recall.ai
   - Update session state if needed
   - Pass through to n8n if required

2. **Provide bot_id Context**
   - Include in POST /voice-bot-v3 payload
   - Set in `body.data.bot.id` field
   - Use consistent format across all calls

3. **Handle Audio Acknowledgment**
   - Receive summary from Parallel TTS & Send
   - Return tts_summary metrics to caller
   - Monitor send_failed and tts_failed counts

4. **Credentials Management**
   - **DO NOT** hardcode API keys in relay
   - Get from environment variables or secure vault
   - Pass to n8n via environment injection

### Webhook Payload Structure (Expected)
```json
{
  "body": {
    "data": {
      "bot": {
        "id": "bot_12345"        // CRITICAL
      },
      "data": {
        "words": [
          { "text": "hello" },
          { "text": "world" }
        ],
        "participant": {
          "name": "John",
          "is_host": false,
          "id": "participant_123"
        }
      }
    },
    "event": "transcript_sent",  // Event type
    "transcript": "hello world"  // Pre-computed (optional)
  }
}
```

---

## 11. FLOW DIAGRAM

```
┌─────────────────────────────────────────────────────────────────────┐
│                    WEBHOOK INGESTION (REST API)                     │
│                    POST /voice-bot-v3 {body}                       │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  Process Transcript     │
                    │  (Extract bot_id,      │
                    │   speaker, transcript) │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │    Route Switch        │
                    │  (Classify intent)     │
                    └────────────┬────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
    SILENT/WAIT            PROCESS                QUICK_RESPOND
    (Log only)          (Full Agent)            (Pre-Router)
         │                    │                        │
         │      ┌─────────────┼─────────────┐          │
         │      │             │             │          │
    ┌────▼──┐┌─────▼──┐   ┌──▼──┐  ┌─────▼────┐    ┌──▼──┐
    │Log    ││Load    │   │Build│  │Ultra-Fast│    │Quick│
    │Silent ││Bot     │   │Agent│  │Pre-Router│    │Ack/ │
    │       ││State   │   │Ctx  │  │          │    │Reply│
    └───────┘└────┬───┘   └──┬──┘  └─────┬────┘    └──┬──┘
                  │          │           │            │
                  │      ┌───▼───────────┼────────┐   │
                  │      │               │        │   │
                  │   ┌──▼────┐   ┌──────▼──┐  ┌─▼─┐ │
                  │   │Build  │   │Orchestr-│  │Pre-│ │
                  │   │Agent  │   │ator     │  │Rte │ │
                  │   │Ctx    │   │Agent    │  │Sw  │ │
                  │   └───────┘   └────┬────┘  └────┘ │
                  │                    │               │
                  │            ┌───────▼────────────┬──┘
                  │            │                    │
                  │       ┌────▼────┐   ┌──────────▼──┐
                  │       │Check    │   │Get response │
                  │       │Agent    │   │text from    │
                  │       │Output   │   │context/log  │
                  │       └────┬────┘   └──────┬──────┘
                  │            │               │
                  │       ┌────▼───────────────▼────┐
                  │       │  Split into Sentences   │
                  │       │  (Chunk + extract      │
                  │       │   bot_id)              │
                  │       └────┬───────────────────┘
                  │            │
                  │       ┌────▼──────────────────────┐
                  └──────►│ Parallel TTS & Send       │
                          │ ┌──────────────────────┐  │
                          │ │1. Check bot status   │  │
                          │ │   GET Recall.ai      │  │
                          │ │                      │  │
                          │ │2. Generate TTS       │  │
                          │ │   (Parallel OpenAI)  │  │
                          │ │                      │  │
                          │ │3. Send to Recall.ai  │  │
                          │ │   (Sequential POST)  │  │
                          │ └──────────────────────┘  │
                          └────┬──────────────────────┘
                               │
                    ┌──────────▼────────────┐
                    │ Return tts_summary    │
                    │ (to webhook response) │
                    └───────────────────────┘
```

---

## 12. INJECTION POINTS FOR RELAY SERVER

### Where Recall.ai Integration Happens

| Layer | Current | Required Change | Priority |
|-------|---------|-----------------|----------|
| **Webhook Input** | Relay passes body.data | Ensure bot_id in body.data.bot.id | HIGH |
| **Process Transcript** | Extracts bot_id | No change needed | - |
| **Split into Sentences** | Passes bot_id through | No change needed | - |
| **Parallel TTS & Send** | Calls Recall.ai APIs | Move credentials to env vars | CRITICAL |
| **Credentials** | Hardcoded in node | Use n8n Credentials Manager | CRITICAL |

### Relay Server Responsibilities

1. **Validate webhook payload structure**
   - Ensure `body.data.bot.id` is present
   - Log bot_id for tracing

2. **Inject bot_id into context**
   - Don't rely on n8n to extract it
   - Pass explicitly if workflow needs it

3. **Handle Recall.ai status webhooks** (if bidirectional)
   - Receive bot status updates from Recall.ai
   - Update bot session state
   - Forward to n8n monitoring if needed

4. **Monitor TTS delivery**
   - Check tts_summary in response
   - Alert if send_failed > 0
   - Track audio delivery latency

---

## Summary

The Teams Voice Bot v3.0 has a **complete, functional Recall.ai integration** in the "Parallel TTS & Send" node. It:

✓ Validates bot status before generating audio
✓ Generates MP3 audio in parallel (OpenAI TTS)
✓ Sends audio to Recall.ai in sequential order
✓ Returns detailed success/failure summary
✓ Supports both quick response and agent paths
✓ Properly threads bot_id through the entire pipeline

**The only gaps are:**
- API keys hardcoded (security) → Move to environment variables
- No error alerting → Add monitoring to tts_summary metrics
- No relay server integration guide → This document provides it
