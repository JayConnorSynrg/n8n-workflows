# Parallel TTS & Send Node - Complete Technical Reference

**Node Type:** `n8n-nodes-base.code`
**Node Name:** `Parallel TTS & Send`
**Workflow:** Teams Voice Bot v3.0 (`d3CxEaYk5mkC8sLo`)
**Last Updated:** 2026-01-10

---

## 1. NODE INPUTS

### Expected Input Format

**Array of sentence items** (from Split into Sentences node):

```javascript
[
  {
    "json": {
      "sentence": "Hello there.",
      "sentence_index": 0,
      "total_sentences": 3,
      "bot_id": "bot_12345",           // CRITICAL
      "is_first": true,
      "is_last": false,
      "full_output": "Hello there. How are you? Nice to meet you.",
      "response_type": "agent|quick",
      "route_taken": "FULL_PROCESS|QUICK_RESPOND"
    }
  },
  {
    "json": {
      "sentence": "How are you?",
      "sentence_index": 1,
      "total_sentences": 3,
      "bot_id": "bot_12345",           // CRITICAL
      "is_first": false,
      "is_last": false,
      ...
    }
  },
  ...
]
```

### Required Fields
- `sentence` - Text to convert to speech
- `sentence_index` - Order position (0-based)
- `bot_id` - **CRITICAL for Recall.ai API calls**
- `total_sentences` - Total count for logging

### Optional Fields
- `voice` - Voice name (defaults to "alloy" if not in parent)
- `response_type` - "agent" or "quick" (for logging)
- `route_taken` - Route classification (for logging)

---

## 2. NODE OUTPUTS

### Success Output

```javascript
{
  "json": {
    // All original fields from input item preserved
    "sentence": "Hello there.",
    "bot_id": "bot_12345",
    ...

    // New summary added
    "tts_summary": {
      "total_sentences": 3,
      "tts_generated": 3,           // Successfully created MP3s
      "tts_failed": 0,              // Failed OpenAI calls
      "audio_sent": 3,              // Successfully posted to Recall.ai
      "send_failed": 0,             // Failed Recall.ai sends
      "send_errors": [],            // Error messages from failures
      "bot_status": "in_call_recording",  // From Recall.ai status check
      "skipped_reason": null        // If TTS skipped, reason why
    }
  }
}
```

### Skipped Output (Bot Not Active)

```javascript
{
  "json": {
    "bot_id": "bot_12345",
    ...
    "tts_summary": {
      "total_sentences": 3,
      "tts_generated": 0,
      "tts_failed": 0,
      "audio_sent": 0,
      "send_failed": 0,
      "send_errors": [],
      "skipped_reason": "Bot not active (status: in_call_not_recording)"
    }
  }
}
```

---

## 3. STEP-BY-STEP EXECUTION

### Step 0: Bot Status Validation

**Purpose:** Check if bot is actively recording before generating audio

```javascript
// Get items
const items = $input.all();
if (!items.length) {
  return [{ json: { success: false, error: 'No sentences to process' } }];
}

// Extract bot_id from first item
const bot_id = items[0].json.bot_id;

// Call Recall.ai API
const statusResponse = await this.helpers.httpRequest({
  method: 'GET',
  url: `https://us-west-2.recall.ai/api/v1/bot/${bot_id}/`,
  headers: {
    'Authorization': `Token ${RECALL_API_KEY}`
  },
  returnFullResponse: false
});

// Check status
const lastStatus = statusResponse.status_changes[statusResponse.status_changes.length - 1];
const botStatus = lastStatus.code;

// Valid active states:
const botActive = ['in_call_recording', 'in_call_not_recording'].includes(botStatus);

if (!botActive) {
  // Skip all TTS generation
  return [{
    json: {
      ...items[0].json,
      tts_summary: {
        total_sentences: items.length,
        tts_generated: 0,
        tts_failed: 0,
        audio_sent: 0,
        send_failed: 0,
        send_errors: [],
        skipped_reason: `Bot not active (status: ${botStatus})`
      }
    }
  }];
}
```

**Possible Bot Status Codes:**
- `in_call_recording` - ACTIVE ✓
- `in_call_not_recording` - ACTIVE ✓ (can receive audio)
- `between_calls` - INACTIVE ✗
- `call_ended` - INACTIVE ✗
- `error` - INACTIVE ✗

---

### Step 1: Parallel TTS Generation

**Purpose:** Convert all sentences to MP3 audio in parallel

```javascript
// Create promise for each sentence
const ttsPromises = items.map(async (item, index) => {
  const sentence = item.json.sentence;
  const sentenceIndex = item.json.sentence_index ?? index;

  try {
    // Call OpenAI TTS API
    const response = await this.helpers.httpRequest({
      method: 'POST',
      url: 'https://api.openai.com/v1/audio/speech',
      headers: {
        'Authorization': `Bearer ${OPENAI_API_KEY}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model: 'tts-1',              // Fast model (vs tts-1-hd)
        voice: 'alloy',              // Configurable: alloy|echo|fable|onyx|nova|shimmer
        input: sentence,             // Max ~4096 chars per request
        response_format: 'mp3'       // MP3 format
      }),
      encoding: 'arraybuffer',       // Get binary data
      returnFullResponse: false
    });

    // Convert binary → Base64
    const audio_base64 = Buffer.from(response).toString('base64');

    return {
      sentenceIndex,
      sentence,
      audio_base64,
      success: true
    };
  } catch (error) {
    return {
      sentenceIndex,
      sentence,
      error: error.message,
      success: false
    };
  }
});

// Wait for all TTS calls to complete
const allAudio = await Promise.all(ttsPromises);

// Separate successes from failures
const failures = allAudio.filter(a => !a.success);
const successfulAudio = allAudio.filter(a => a.success);

// Sort by sentence index to maintain order
successfulAudio.sort((a, b) => a.sentenceIndex - b.sentenceIndex);
```

**Configuration Options:**
- `model`: "tts-1" (fast, low latency) or "tts-1-hd" (slower, higher quality)
- `voice`: "alloy" (recommended), "echo", "fable", "onyx", "nova", "shimmer"
- `input`: Max 4096 characters per request
- `response_format`: "mp3", "opus", "aac", "flac"

---

### Step 2: Sequential Recall.ai Delivery

**Purpose:** Send audio chunks to Recall.ai in sentence order

```javascript
// Send each audio chunk sequentially (IMPORTANT: not parallel!)
const sendResults = [];

for (const audio of successfulAudio) {
  try {
    await this.helpers.httpRequest({
      method: 'POST',
      url: `https://us-west-2.recall.ai/api/v1/bot/${bot_id}/output_audio/`,
      headers: {
        'Authorization': `Token ${RECALL_API_KEY}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        kind: 'mp3',                    // Audio format
        b64_data: audio.audio_base64    // Base64-encoded MP3 data
      }),
      returnFullResponse: false
    });

    sendResults.push({
      sentenceIndex: audio.sentenceIndex,
      sent: true
    });
  } catch (error) {
    sendResults.push({
      sentenceIndex: audio.sentenceIndex,
      sent: false,
      error: error.message
    });
  }
}
```

**Why Sequential?**
- Maintains sentence order in Recall.ai playback
- Prevents race conditions with speech timing
- Easier error tracking per sentence

---

### Step 3: Return Summary

```javascript
return [{
  json: {
    ...items[0].json,  // Preserve original fields
    tts_summary: {
      total_sentences: items.length,
      tts_generated: successfulAudio.length,
      tts_failed: failures.length,
      audio_sent: sendResults.filter(r => r.sent).length,
      send_failed: sendResults.filter(r => !r.sent).length,
      send_errors: sendResults.filter(r => !r.sent).map(r => r.error),
      bot_status: botStatus
    }
  }
}];
```

---

## 4. CURRENT HARDCODED CONFIGURATION

### API Keys (SECURITY ISSUE - Move to environment variables)

```javascript
const OPENAI_API_KEY = 'process.env.OPENAI_API_KEY';
const RECALL_API_KEY = 'RECALL_API_KEY_FROM_ENV';
```

### Migration Required

```javascript
// Change to:
const OPENAI_API_KEY = process.env.N8N_OPENAI_API_KEY;
const RECALL_API_KEY = process.env.N8N_RECALL_API_KEY;

// Or use n8n Credentials:
// const openaiCreds = await this.helpers.getCredentials('openai');
// const recallCreds = await this.helpers.getCredentials('recallai');
```

---

## 5. ERROR HANDLING

### Recoverable Errors

```javascript
// OpenAI TTS failure
{
  success: false,
  error: "Invalid API key",
  // Remaining sentences still processed
}

// Recall.ai delivery failure
{
  sent: false,
  error: "Connection timeout",
  // Other sentences continue being sent
}
```

### Non-Recoverable Errors

```javascript
// Bot status check fails
{
  botStatus: 'check_failed',
  botActive: false,
  skipped_reason: "Bot status check failed"
  // All TTS generation skipped
}

// No sentences to process
{
  success: false,
  error: 'No sentences to process'
  // Return immediately
}
```

---

## 6. PERFORMANCE CHARACTERISTICS

### Latency Breakdown (for 3 sentences)

```
Recall.ai status check:        ~100-200ms
OpenAI TTS (parallel, 3x):     ~500-2000ms  (bottleneck)
Recall.ai delivery (seq, 3x):  ~150-500ms
Total for 3 sentences:         ~800-2700ms
```

### Throughput

```
Max concurrent TTS calls:      ~5 (per account, respect rate limits)
Max sequential audio uploads:  ~10 sentences/second
Typical response size:         ~200KB per sentence (MP3 audio)
```

### Cost Estimation

```
OpenAI TTS pricing:           $0.015 per 1000 characters input
Recall.ai output_audio:       Included in subscription
Example: 3 sentences (~150 chars) = ~$0.0023 per response
```

---

## 7. BOT_ID THREADING

### Input Validation

```javascript
const bot_id = items[0].json.bot_id;

if (!bot_id) {
  // This will fail API calls - better to log warning
  console.warn('bot_id not provided, will use "unknown"');
}

// Both API calls REQUIRE valid bot_id:
// 1. GET /api/v1/bot/{bot_id}/
// 2. POST /api/v1/bot/{bot_id}/output_audio/
```

### Trace Through Workflow

```
1. Webhook POST body.data.bot.id = "bot_12345"
2. Process Transcript extracts → json.bot_id = "bot_12345"
3. Split into Sentences must find bot_id:
   - Priority 1: input.bot_id (quick path)
   - Priority 2: Build Agent Context.bot_id (agent path)
   - Priority 3: Pre-Route Switch.bot_id (fallback)
4. Parallel TTS & Send receives items[0].json.bot_id
5. Uses for both Recall.ai API calls
```

---

## 8. TESTING SCENARIOS

### Test 1: Successful Full Path
```
Input:  3 sentences with valid bot_id
Output: tts_generated=3, audio_sent=3, send_failed=0
```

### Test 2: Bot Offline
```
Input:  Sentences with bot not in call
Output: tts_generated=0 (skipped), skipped_reason populated
```

### Test 3: OpenAI Failure
```
Input:  Invalid API key
Output: tts_failed=1, audio_sent=2 (partial)
```

### Test 4: Recall.ai Delivery Failure
```
Input:  Valid audio but Recall.ai API down
Output: tts_generated=3, audio_sent=0, send_errors populated
```

### Test 5: Missing bot_id
```
Input:  Sentences without bot_id
Output: API calls fail, errors logged
```

---

## 9. MONITORING & DEBUGGING

### Key Metrics to Track

```javascript
// Per execution:
- tts_summary.total_sentences
- tts_summary.tts_generated
- tts_summary.tts_failed
- tts_summary.audio_sent
- tts_summary.send_failed
- execution_time_ms
- bot_status

// Aggregated:
- TTS success rate (tts_generated / total)
- Recall.ai delivery success rate (audio_sent / tts_generated)
- Average latency
- Error categories
```

### Debug Logging

```javascript
console.log(`TTS Processing:
  Total: ${items.length}
  Generated: ${successfulAudio.length}
  Failed: ${failures.length}
  Bot Status: ${botStatus}
`);

failures.forEach(f => {
  console.error(`TTS failed for sentence ${f.sentenceIndex}: ${f.error}`);
});

sendResults.filter(r => !r.sent).forEach(r => {
  console.error(`Delivery failed for sentence ${r.sentenceIndex}: ${r.error}`);
});
```

---

## 10. FUTURE IMPROVEMENTS

### Potential Enhancements

1. **Configurable voice per user**
   - Read from user preferences
   - Pass in Split into Sentences

2. **Retry logic for failed sends**
   - Exponential backoff
   - Max 3 retries

3. **Stream audio directly**
   - Instead of collecting all, stream as generated
   - Reduce memory footprint

4. **Support other TTS providers**
   - Google Cloud TTS
   - Amazon Polly
   - Fallback if OpenAI unavailable

5. **Audio caching**
   - Cache frequently said phrases
   - Reduce API calls and latency

---

## Summary: Node Execution Flow

```
Input: Array of sentences
   ↓
Step 0: Check bot status in Recall.ai
   ├─ If not active: Skip all TTS, return skip reason
   └─ If active: Continue to Step 1
   ↓
Step 1: Generate TTS in parallel (Promise.all)
   ├─ Call OpenAI for each sentence
   ├─ Collect successes and failures
   └─ Sort by sentence_index
   ↓
Step 2: Send audio sequentially to Recall.ai
   ├─ For each successful audio
   ├─ POST to /bot/{bot_id}/output_audio/
   └─ Track sent/not-sent
   ↓
Output: Return summary with metrics
   └─ tts_summary.{total_sentences, tts_generated, audio_sent, send_failed, ...}
```

**Critical Requirements:**
- ✓ bot_id must be in items[0].json.bot_id
- ✓ TTS generation must be PARALLEL (for speed)
- ✓ Recall.ai delivery must be SEQUENTIAL (for order)
- ✓ API keys must move to environment variables
- ✓ All errors must be caught and summarized
