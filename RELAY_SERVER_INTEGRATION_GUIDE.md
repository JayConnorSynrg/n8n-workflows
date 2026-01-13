# Relay Server → N8N Voice Bot Integration Guide

**Document Purpose:** Technical specifications for relay-server to integrate with Teams Voice Bot v3.0 (workflow ID: `d3CxEaYk5mkC8sLo`)

---

## 1. WEBHOOK ENDPOINT SPECIFICATION

### Relay Server Responsibility

Forward all Recall.ai transcript events to the n8n webhook endpoint.

### Endpoint Details

```
n8n Webhook URL: https://<n8n-instance>/webhook/voice-bot-v3
HTTP Method: POST
Content-Type: application/json
```

### Required Payload Structure

```json
{
  "body": {
    "event": "transcript_sent",
    "data": {
      "bot": {
        "id": "bot_12345"          // CRITICAL: Must be present
      },
      "data": {
        "words": [
          { "text": "hello" },
          { "text": "world" }
        ],
        "participant": {
          "name": "John Doe",
          "id": "participant_abc123",
          "is_host": false
        }
      }
    }
  }
}
```

### Field Mapping from Recall.ai to N8N

| Recall.ai Field | N8N Path | Required | Notes |
|-----------------|----------|----------|-------|
| `bot.id` | `body.data.bot.id` | **YES** | Used for Recall.ai output_audio API calls |
| `speaker.name` | `body.data.data.participant.name` | YES | Logged in session state |
| `speaker.id` | `body.data.data.participant.id` | No | For tracking |
| `words[].text` | `body.data.data.words[].text` | Yes | Joined to create transcript |
| `event` | `body.event` | Yes | Determines routing (transcript_sent = PROCESS) |

---

## 2. BOT_ID CRITICAL PATH

### Where bot_id Travels Through N8N

```
Webhook Input (body.data.bot.id)
  ↓
Process Transcript (extracts to json.bot_id)
  ↓
Route Switch (passed through all branches)
  ↓
Three paths:
  ├─ PROCESS: Load Bot State → Build Agent Context → Orchestrator Agent
  ├─ QUICK_RESPOND: Pre-Router → Quick Acknowledge/Reply
  └─ SILENT: Log only (no audio)
  ↓
Split into Sentences (must extract bot_id from context)
  ↓
Parallel TTS & Send (FINAL DELIVERY)
  ├─ Bot Status Check: GET /api/v1/bot/{bot_id}/
  └─ Audio Delivery: POST /api/v1/bot/{bot_id}/output_audio/
```

### Critical Verification Points

**✓ Check 1: Webhook Input**
```javascript
// In relay server before POST to n8n:
if (!payload.body?.data?.bot?.id) {
  throw new Error('Missing bot.id in webhook payload');
}
```

**✓ Check 2: Process Transcript Output**
```javascript
// In n8n Process Transcript node (already done):
bot_id = body.data.bot.id;  // Extracted correctly
```

**✓ Check 3: Split into Sentences**
```javascript
// In n8n Split into Sentences node (already done):
botId = input.bot_id || agentContext.bot_id || 'unknown';
// Returns in every sentence item
```

---

## 3. RESPONSE HANDLING

### What the N8N Workflow Returns

The webhook endpoint returns a JSON response with audio delivery status:

```json
{
  "tts_summary": {
    "total_sentences": 3,        // How many sentences to read
    "tts_generated": 3,          // Successfully created MP3s
    "tts_failed": 0,             // Failed OpenAI TTS calls
    "audio_sent": 3,             // Successfully posted to Recall.ai
    "send_failed": 0,            // Failed Recall.ai POST calls
    "send_errors": [],           // Error messages from failed sends
    "bot_status": "in_call_recording",  // Bot's current state
    "skipped_reason": null       // If bot not active, why TTS was skipped
  }
}
```

### Success Criteria

```javascript
// Audio successfully delivered if:
tts_generated === total_sentences &&
audio_sent === tts_generated &&
send_failed === 0
```

### Error Handling

```javascript
// Handle these failure scenarios:

if (response.tts_failed > 0) {
  // OpenAI API issue or invalid sentence
  log.warn(`${tts_failed} sentences failed TTS generation`);
}

if (response.send_failed > 0) {
  // Recall.ai delivery failed
  log.error(`Failed to send ${send_failed} audio chunks`);
  log.error(`Errors: ${send_errors}`);
}

if (response.skipped_reason) {
  // Bot not active, audio was NOT generated
  log.warn(`Audio generation skipped: ${skipped_reason}`);
  // Expected during call setup/teardown
}

if (response.bot_status === 'check_failed') {
  // Couldn't verify bot status
  // TTS was skipped to avoid wasted API calls
  log.warn('Could not verify bot status');
}
```

---

## 4. WEBHOOK FLOW TIMING

### Expected Response Times

```
Webhook POST received
  ├─ Process Transcript: ~10ms
  ├─ Route classification: ~5ms
  ├─ Load Bot State (if PROCESS): ~50-100ms
  ├─ Orchestrator Agent (if PROCESS): ~1000-3000ms
  ├─ TTS Generation (parallel): ~500-2000ms
  ├─ Recall.ai Status Check: ~100-200ms
  ├─ Recall.ai Audio Delivery (sequential): ~50-500ms per sentence
  └─ Response returned to relay: ~2000-5000ms total
```

### Timeout Handling

```javascript
// Recommended webhook timeout in relay server:
const WEBHOOK_TIMEOUT_MS = 10000;  // 10 seconds

// If n8n doesn't respond in 10 seconds:
// 1. Check if agent is still running (could be slow LLM call)
// 2. Return 504 Gateway Timeout to Recall.ai
// 3. Log the timeout for debugging
```

---

## 5. ERROR SCENARIOS & RECOVERY

### Scenario 1: Missing bot.id

**Error:** N8N workflow will extract bot_id as `'unknown'`

**Impact:** Recall.ai status check fails (can't call `/api/v1/bot/unknown/`)

**Solution in Relay:**
```javascript
if (!payload.body?.data?.bot?.id) {
  throw new Error('bot.id required in webhook payload');
  // Don't forward to n8n
}
```

### Scenario 2: Bot Not Active

**Error:** N8N gets status response with `bot_status !== 'in_call_recording'`

**Impact:** TTS generation skipped, audio not sent

**Response:**
```json
{
  "tts_summary": {
    "tts_generated": 0,
    "audio_sent": 0,
    "bot_status": "in_call_not_recording",
    "skipped_reason": "Bot not active (status: in_call_not_recording)"
  }
}
```

**In Relay:** This is normal during call setup. Log but don't alert.

### Scenario 3: OpenAI API Failure

**Error:** Parallel TTS generation fails for one or more sentences

**Response:**
```json
{
  "tts_summary": {
    "total_sentences": 3,
    "tts_generated": 2,
    "tts_failed": 1,
    "audio_sent": 2,
    "send_failed": 0
  }
}
```

**In Relay:** Partial audio sent. Alert that user heard incomplete response.

### Scenario 4: Recall.ai API Failure

**Error:** POST to output_audio endpoint fails

**Response:**
```json
{
  "tts_summary": {
    "total_sentences": 3,
    "tts_generated": 3,
    "tts_failed": 0,
    "audio_sent": 1,
    "send_failed": 2,
    "send_errors": [
      "Connection timeout",
      "Connection timeout"
    ]
  }
}
```

**In Relay:** TTS was generated but not delivered. Retry or escalate.

---

## 6. API KEY CONFIGURATION

### Current Security Issue

API keys are **hardcoded** in the Parallel TTS & Send node:

```javascript
const OPENAI_API_KEY = 'sk-proj-...';
const RECALL_API_KEY = '4f12c2c033fc1f0fe1e4ca2fcd0aad92b547ff43';
```

### Required Migration

Move keys to **n8n Environment Variables**:

```
N8N_OPENAI_API_KEY=sk-proj-...
N8N_RECALL_API_KEY=4f12c2c033fc1f0fe1e4ca2fcd0aad92b547ff43
```

Or use **n8n Credentials Manager**:
1. Create "OpenAI" credential
2. Create "Recall.ai" credential
3. Reference in nodes instead of hardcoding

### Relay Server Responsibility

**Do NOT** store these keys in relay server. They should be:
- In n8n environment only
- Rotated regularly
- Never logged or exposed in error messages
- Scoped to minimal required permissions

---

## 7. MONITORING & OBSERVABILITY

### What to Log in Relay Server

```javascript
// Per webhook call:
{
  timestamp: new Date().toISOString(),
  bot_id: payload.body.data.bot.id,
  speaker: payload.body.data.data.participant.name,
  transcript_length: payload.body.data.data.words.length,

  // After n8n response:
  n8n_response_time_ms: responseTime,
  tts_generated: response.tts_summary.tts_generated,
  audio_sent: response.tts_summary.audio_sent,
  bot_status: response.tts_summary.bot_status,
  errors: response.tts_summary.send_errors
}
```

### Alerts to Set Up

```
Alert if:
- send_failed > 0 (Recall.ai delivery failed)
- tts_failed > 0 (OpenAI failed)
- n8n_response_time_ms > 5000ms (slow response)
- bot_status === 'check_failed' (Recall.ai status endpoint down)
- response.error (n8n workflow error)
```

### Dashboard Metrics

```
- Total webhooks received (per bot_id)
- TTS success rate (audio_sent / total_sentences)
- Average response time (percentiles: p50, p95, p99)
- Recall.ai delivery latency
- OpenAI TTS latency (parallel generation time)
- Bot uptime by bot_id
```

---

## 8. TESTING CHECKLIST

### Pre-Deployment Test

```javascript
// Test 1: Webhook payload validation
POST /voice-bot-v3
{
  "body": {
    "data": {
      "bot": { "id": "test-bot-1" },
      "data": {
        "words": [{ "text": "hello" }],
        "participant": { "name": "Test User" }
      }
    }
  }
}
// Expected: 200 OK with tts_summary

// Test 2: Missing bot.id
POST /voice-bot-v3
{
  "body": {
    "data": {
      "data": { ... }  // No "bot" field
    }
  }
}
// Expected: bot_id extracted as 'unknown', workflow continues

// Test 3: Multi-sentence response
// Input: Long transcript that triggers agent response
// Expected: Each sentence gets TTS, sent sequentially

// Test 4: Bot offline scenario
// With bot not in active call
// Expected: tts_summary.skipped_reason populated

// Test 5: Load test
// 100 concurrent webhooks
// Expected: All complete within 10 seconds, Recall.ai throttling handled
```

---

## 9. QUICK REFERENCE: bot_id INJECTION

### In Relay Server Code

```javascript
// NodeJS/Express example
app.post('/voice-webhook', async (req, res) => {
  const transcriptEvent = req.body;

  // Extract bot_id from Recall.ai webhook
  const botId = transcriptEvent.bot?.id;

  if (!botId) {
    return res.status(400).json({ error: 'Missing bot.id' });
  }

  // Transform to n8n format
  const n8nPayload = {
    body: {
      event: 'transcript_sent',
      data: {
        bot: { id: botId },        // ← CRITICAL
        data: {
          words: transcriptEvent.words || [],
          participant: transcriptEvent.speaker || {}
        }
      }
    }
  };

  // Forward to n8n
  const n8nResponse = await fetch(
    'https://n8n-instance/webhook/voice-bot-v3',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(n8nPayload),
      timeout: 10000
    }
  );

  const result = await n8nResponse.json();

  // Return TTS summary to Recall.ai
  res.json({
    success: result.tts_summary.audio_sent > 0,
    tts_summary: result.tts_summary
  });
});
```

---

## 10. DEPLOYMENT CHECKLIST

- [ ] Webhook endpoint configured in relay server
- [ ] bot.id validation in place
- [ ] Error handling for missing bot.id
- [ ] Timeout set to 10 seconds
- [ ] tts_summary parsing implemented
- [ ] Logging/monitoring configured
- [ ] Test with real Recall.ai bot_id
- [ ] Test with bot online/offline
- [ ] Test multi-sentence response
- [ ] Load test with concurrent calls
- [ ] API keys moved to environment variables (in n8n)
- [ ] Documentation updated for ops team

---

## Summary

The relay server is a **thin proxy** that:

1. ✓ Receives Recall.ai transcript events
2. ✓ Validates bot.id is present
3. ✓ Transforms to n8n webhook format
4. ✓ Forwards to `/webhook/voice-bot-v3`
5. ✓ Receives tts_summary response
6. ✓ Logs metrics and errors
7. ✓ Returns status to Recall.ai

**The actual TTS→Recall.ai delivery is handled entirely within the n8n workflow** (Parallel TTS & Send node). The relay server just ensures the bot_id reaches the workflow correctly.
