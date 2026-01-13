# Recall.ai Audio Output Pattern

**Quality Level:** Production-Ready
**Category:** API Integration
**Discovered:** 2025-12-30
**Source Workflow:** TTS Tool Sub-Workflow (`Rg0vyFHB3u0yPaHY`)
**Verified:** 2025-12-30

---

## Overview

This pattern documents how to successfully send audio to a Recall.ai bot in a Microsoft Teams meeting using n8n workflows.

---

## Positive Patterns (CORRECT)

### 1. Bot Creation with Audio Output Enabled

**CRITICAL:** Bots MUST be created with `automatic_audio_output` configuration to use the output_audio endpoint.

```json
{
  "meeting_url": "{{ $json.meeting_url }}",
  "bot_name": "{{ $json.bot_name }}",
  "recording_config": {
    "transcript": {
      "provider": {
        "recallai_streaming": {
          "language_code": "en",
          "mode": "prioritize_low_latency"
        }
      }
    },
    "realtime_endpoints": [{
      "type": "webhook",
      "url": "https://your-domain/webhook/voice-bot-v3",
      "events": ["transcript.data", "transcript.partial_data"]
    }]
  },
  "automatic_audio_output": {
    "in_call_recording": {
      "data": {
        "kind": "mp3",
        "b64_data": "//uQxAAAAAANIAAAAAExBTUUzLjEwMFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
      }
    }
  },
  "status_callback_url": "https://your-domain/webhook/recall-bot-events"
}
```

**Why:** Without `automatic_audio_output`, the Recall.ai API will reject all `/output_audio/` requests.

---

### 2. HTTP Request Node with Authentication

**CRITICAL:** HTTP Request nodes calling Recall.ai API MUST include BOTH:
- `authentication: "predefinedCredentialType"`
- `nodeCredentialType: "httpHeaderAuth"`

```json
{
  "parameters": {
    "url": "=https://us-west-2.recall.ai/api/v1/bot/{{ $('Set Defaults').item.json.bot_id }}/output_audio/",
    "method": "POST",
    "authentication": "predefinedCredentialType",
    "nodeCredentialType": "httpHeaderAuth",
    "sendBody": true,
    "specifyBody": "json",
    "jsonBody": "={{ { \"kind\": \"mp3\", \"b64_data\": $('Convert to Base64').item.json.audio_base64 } }}",
    "options": {}
  },
  "credentials": {
    "httpHeaderAuth": {
      "id": "your-credential-id",
      "name": "Recall AI header Auth"
    }
  }
}
```

---

### 3. Binary Data to Base64 Conversion

**CORRECT syntax for n8n Code nodes:**

```javascript
// Get binary data properly using n8n's helpers
const items = $input.all();
const results = [];

for (let i = 0; i < items.length; i++) {
  const item = items[i];
  const binaryData = item.binary?.data;

  if (binaryData) {
    // CORRECT: Use this.helpers (NOT $helpers)
    const buffer = await this.helpers.getBinaryDataBuffer(i, 'data');
    const base64Audio = buffer.toString('base64');

    results.push({
      json: {
        ...item.json,
        audio_base64: base64Audio,
        audio_format: 'mp3'
      }
    });
  } else {
    results.push({
      json: {
        ...item.json,
        error: 'No audio binary data found',
        audio_base64: null
      }
    });
  }
}

return results;
```

---

### 4. Data Flow Preservation with Node References

**CRITICAL:** When intermediate nodes (like HTTP GET for status check) are inserted in the flow, use explicit node references to preserve data from upstream nodes.

```javascript
// CORRECT: Reference specific upstream node
"jsonBody": "={{ { \"kind\": \"mp3\", \"b64_data\": $('Convert to Base64').item.json.audio_base64 } }}"

// Access bot_id from Set Defaults node (not current $json)
"url": "=https://us-west-2.recall.ai/api/v1/bot/{{ $('Set Defaults').item.json.bot_id }}/output_audio/"
```

---

### 5. Bot Status Validation (Positive Matching)

**CORRECT:** Use positive status matching (check for valid states):

```json
{
  "conditions": {
    "conditions": [
      {
        "leftValue": "={{ $json.status }}",
        "rightValue": "in_call",
        "operator": { "type": "string", "operation": "equals" }
      },
      {
        "leftValue": "={{ $json.status }}",
        "rightValue": "joining",
        "operator": { "type": "string", "operation": "equals" }
      },
      {
        "leftValue": "={{ $json.status }}",
        "rightValue": "ready",
        "operator": { "type": "string", "operation": "equals" }
      }
    ],
    "combinator": "or"
  }
}
```

---

### 6. Real-Time Bot Verification via API

Before sending audio, verify bot is still active via Recall.ai API:

```json
{
  "method": "GET",
  "url": "=https://us-west-2.recall.ai/api/v1/bot/{{ $('Set Defaults').item.json.bot_id }}/",
  "authentication": "predefinedCredentialType",
  "nodeCredentialType": "httpHeaderAuth"
}
```

Check the last status in `status_changes` array:

```javascript
// CORRECT: Check last element of status_changes array
"={{ $json.status_changes[$json.status_changes.length - 1].code }}"

// Valid active states:
// - "in_call_recording"
// - "in_call_not_recording"
```

---

## Anti-Patterns (WRONG)

### 1. Missing Authentication Parameters

```json
// WRONG - Has credentials but missing authentication parameters
{
  "parameters": {
    "url": "...",
    "method": "POST",
    "sendBody": true,
    "specifyBody": "json",
    "jsonBody": "..."
    // MISSING: authentication and nodeCredentialType
  },
  "credentials": {
    "httpHeaderAuth": { "id": "...", "name": "..." }
  }
}
```

**Error:** `401 - {"code":"not_authenticated","detail":"Authentication credentials were not provided."}`

**Fix:** Add `authentication: "predefinedCredentialType"` and `nodeCredentialType: "httpHeaderAuth"` to parameters.

---

### 2. Wrong Helper Syntax in Code Nodes

```javascript
// WRONG - $helpers does not exist in Code nodes
const buffer = await $helpers.getBinaryDataBuffer(i, 'data');
```

**Error:** `$helpers is not defined [line X]`

**Fix:** Use `this.helpers.getBinaryDataBuffer(i, 'data')`

---

### 3. Lost Data Context After Intermediate Nodes

```javascript
// WRONG - $json now contains HTTP GET response, not audio data
"jsonBody": "={{ { \"kind\": \"mp3\", \"b64_data\": $json.audio_base64 } }}"
```

**Error:** `400 - {"b64_data":["This field is required."]}`

**Cause:** When you insert an HTTP GET node (e.g., to verify bot status), that node's output becomes the new `$json`. The audio_base64 from the Convert to Base64 node is lost.

**Fix:** Use explicit node reference: `$('Convert to Base64').item.json.audio_base64`

---

### 4. Negative Status Matching

```json
// WRONG - Negative matching passes when status is undefined/null
{
  "conditions": [
    {
      "leftValue": "={{ $json.status }}",
      "rightValue": "completed",
      "operator": { "type": "string", "operation": "notEquals" }
    },
    {
      "leftValue": "={{ $json.status }}",
      "rightValue": "errored",
      "operator": { "type": "string", "operation": "notEquals" }
    }
  ],
  "combinator": "and"
}
```

**Error:** `Cannot send a command to a bot which has completed`

**Cause:** When status is `undefined` or `null`, `!= completed AND != errored` evaluates to TRUE.

**Fix:** Use positive matching for known active states (`in_call`, `joining`, `ready`).

---

### 5. Optional Chaining in n8n Expressions

```javascript
// WRONG - Optional chaining not supported in n8n expressions
"={{ $json.status_changes?.[$json.status_changes?.length - 1]?.code }}"
```

**Error:** Expression parsing error

**Fix:** Use ternary conditionals or explicit array access:
```javascript
"={{ $json.status_changes[$json.status_changes.length - 1].code }}"
```

---

### 6. Missing automatic_audio_output in Bot Creation

```json
// WRONG - Bot created without audio output capability
{
  "meeting_url": "...",
  "bot_name": "...",
  "recording_config": { ... }
  // MISSING: automatic_audio_output
}
```

**Error:** Any call to `/output_audio/` endpoint will fail

**Fix:** Always include `automatic_audio_output` with a silent MP3 placeholder if not playing immediate audio.

---

## Complete Working Flow

```
Workflow Input
    │
    ▼
Set Defaults (bot_id, message, voice)
    │
    ▼
Check Bot Status (Postgres DB)
    │
    ▼
Is Bot Active? (IF: status = in_call OR joining OR ready)
    │
    ├─ TRUE ─────────────────────────────────────────┐
    │                                                 │
    ▼                                                 │
Generate TTS Audio (OpenAI)                          │
    │                                                 │
    ▼                                                 │
Convert to Base64 (Code node: this.helpers)          │
    │                                                 │
    ▼                                                 │
Verify Bot Still Live (HTTP GET Recall.ai API)       │
    │                                                 │
    ▼                                                 │
Bot Still Active? (IF: in_call_recording OR in_call_not_recording)
    │                                                 │
    ├─ TRUE                                          │
    │   │                                            │
    │   ▼                                            │
    │   Send Audio to Recall.ai                      │
    │   (HTTP POST with authentication params)       │
    │   (Reference: $('Convert to Base64').item.json.audio_base64)
    │   │                                            │
    │   ▼                                            │
    │   Return Result                                │
    │                                                 │
    └─ FALSE ─► Bot Ended - Skip                     │
                                                     │
    ├─ FALSE (from Is Bot Active?) ─► Bot Ended - Skip Audio
```

---

## API Reference

### Recall.ai Output Audio Endpoint

**URL:** `POST https://us-west-2.recall.ai/api/v1/bot/{bot_id}/output_audio/`

**Headers:**
```
Authorization: Token YOUR_RECALL_API_KEY
Content-Type: application/json
```

**Body:**
```json
{
  "kind": "mp3",
  "b64_data": "BASE64_ENCODED_MP3_AUDIO"
}
```

**Requirements:**
- Bot must be created with `automatic_audio_output` configuration
- Bot must be in active state (`in_call_recording` or `in_call_not_recording`)

---

## Debugging Checklist

When audio is not being sent to the bot:

1. [ ] Is `automatic_audio_output` configured in Create Bot request?
2. [ ] Does HTTP Request have `authentication: "predefinedCredentialType"`?
3. [ ] Does HTTP Request have `nodeCredentialType: "httpHeaderAuth"`?
4. [ ] Are credentials properly assigned to the node?
5. [ ] Is `b64_data` referencing the correct upstream node?
6. [ ] Is the bot still in an active state?
7. [ ] Is the Code node using `this.helpers` (not `$helpers`)?

---

## References

- [Recall.ai Output Audio Documentation](https://docs.recall.ai/docs/output-audio-in-meetings)
- Workflow: TTS Tool Sub-Workflow (`Rg0vyFHB3u0yPaHY`)
- Workflow: Teams Voice Bot - Launcher (`kUcUSyPgz4Z9mYBt`)
