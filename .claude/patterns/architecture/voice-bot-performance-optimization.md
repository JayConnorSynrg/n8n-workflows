# Voice Bot Performance Optimization Plan

**Quality Level:** Strategic Architecture
**Category:** Performance Optimization
**Created:** 2025-12-30
**Target System:** Teams Voice Bot v3.0

---

## Executive Summary

Current latency bottlenecks in the Teams Voice Bot system create noticeable delays between user speech and bot response. This plan outlines enterprise-grade optimizations targeting sub-2-second end-to-end response times.

---

## Current Architecture Analysis

### Latency Chain (Current)

```
User Speech → Recall.ai Transcription → Webhook → n8n Orchestrator →
AI Processing → TTS Generation → Base64 Encoding → Recall.ai Output Audio → Bot Speaks
```

**Estimated Current Latencies:**
| Stage | Estimated Latency | Bottleneck Level |
|-------|------------------|------------------|
| Recall.ai transcription | 500-1500ms | Medium |
| Webhook delivery | 50-200ms | Low |
| n8n workflow routing | 100-300ms | Low |
| AI response generation | 1000-3000ms | HIGH |
| TTS generation (OpenAI) | 500-1500ms | HIGH |
| Base64 encoding | 50-100ms | Low |
| Recall.ai audio delivery | 200-500ms | Medium |
| **Total** | **2.4-7.1 seconds** | - |

---

## Phase 1: Quick Wins (1-2 Days Implementation)

### 1.1 Parallel Processing Architecture

**Current:** Sequential processing
**Optimized:** Parallel preparation while AI is generating

```
                    ┌─────────────────────────────┐
                    │  AI Response Generation     │
                    │  (happens first - required) │
                    └──────────────┬──────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
              ▼                    ▼                    ▼
    ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
    │ Bot Status      │  │ Connection      │  │ Context         │
    │ Pre-validation  │  │ Keep-alive      │  │ Pre-loading     │
    └─────────────────┘  └─────────────────┘  └─────────────────┘
```

**Implementation:** Use n8n's parallel execution paths to pre-validate bot status while AI processes.

### 1.2 Conversation Context Caching

**Problem:** Each TTS request re-queries bot status and context
**Solution:** Cache bot state in workflow static data or Redis

```javascript
// In n8n Code node - Use static data for session caching
const staticData = $getWorkflowStaticData('global');

// Cache bot state for 30 seconds
const cacheKey = `bot_${bot_id}_state`;
const cachedState = staticData[cacheKey];
const now = Date.now();

if (cachedState && (now - cachedState.timestamp) < 30000) {
  // Use cached state - skip API call
  return { json: { ...cachedState.data, cached: true } };
}

// Fetch fresh state and cache
const freshState = await fetchBotState(bot_id);
staticData[cacheKey] = { data: freshState, timestamp: now };
return { json: freshState };
```

### 1.3 Optimistic Bot Status Handling

**Current:** Verify bot status → Generate TTS → Verify again → Send
**Optimized:** Generate TTS immediately, verify only on failure

```
Current Flow (Double Verification):
┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
│ Verify  │──▶│ Gen TTS │──▶│ Verify  │──▶│ Send    │──▶│ Handle  │
│ Status  │   │ Audio   │   │ Again   │   │ Audio   │   │ Error   │
└─────────┘   └─────────┘   └─────────┘   └─────────┘   └─────────┘

Optimized Flow (Optimistic):
┌─────────┐   ┌─────────┐   ┌─────────────┐
│ Gen TTS │──▶│ Send    │──▶│ Handle Error│
│ Audio   │   │ Audio   │   │ (if needed) │
└─────────┘   └─────────┘   └─────────────┘
```

**Risk Mitigation:** Implement graceful error handling for "bot completed" scenarios.

---

## Phase 2: TTS Optimization (3-5 Days Implementation)

### 2.1 TTS Provider Comparison

| Provider | Latency (TTFB) | Streaming | Quality | Cost/1M chars |
|----------|---------------|-----------|---------|---------------|
| OpenAI TTS | 500-1500ms | Yes (chunks) | Excellent | $15 |
| OpenAI Realtime | <500ms | Native WebSocket | Excellent | $100/hr |
| ElevenLabs Flash | ~75ms | Yes | Excellent | $11 |
| Deepgram Aura-2 | <200ms | WebSocket | Good | $15 |
| Cartesia Sonic-3 | 40-90ms | Yes | Excellent | $15 |

### 2.2 Recommended: Streaming TTS Implementation

**Primary Recommendation:** Cartesia Sonic-3 for lowest latency
**Fallback:** ElevenLabs Flash v2.5

#### Cartesia Implementation Pattern

```javascript
// n8n Code node - Streaming TTS with Cartesia
const CARTESIA_API_KEY = $credentials.cartesiaApi.apiKey;
const CARTESIA_VOICE_ID = 'your-voice-id';

const response = await fetch('https://api.cartesia.ai/tts/bytes', {
  method: 'POST',
  headers: {
    'X-API-Key': CARTESIA_API_KEY,
    'Cartesia-Version': '2024-06-10',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    model_id: 'sonic-english',
    transcript: $json.text,
    voice: { mode: 'id', id: CARTESIA_VOICE_ID },
    output_format: {
      container: 'mp3',
      encoding: 'mp3',
      sample_rate: 44100
    }
  })
});

const audioBuffer = await response.arrayBuffer();
const base64Audio = Buffer.from(audioBuffer).toString('base64');

return { json: { audio_base64: base64Audio, format: 'mp3' } };
```

### 2.3 Streaming Audio to Recall.ai (Advanced)

**Challenge:** Recall.ai `output_audio` expects complete audio
**Solution:** Chunked audio delivery with silence padding

```javascript
// Chunk audio into 2-second segments for progressive delivery
const CHUNK_DURATION_MS = 2000;
const chunks = splitAudioIntoChunks(audioBuffer, CHUNK_DURATION_MS);

for (const chunk of chunks) {
  await sendToRecallAi(bot_id, chunk);
  // Small delay to prevent overwhelming the bot
  await new Promise(r => setTimeout(r, 100));
}
```

---

## Phase 3: AI Response Optimization (1 Week Implementation)

### 3.1 Response Streaming Architecture

**Goal:** Start TTS generation while AI is still generating text

```
Traditional (Wait for Complete Response):
AI: "I understand..." ──────────────────────────────▶ TTS Start
                                                      │
                                                      ▼
                                                   Audio Ready

Streaming (Progressive Processing):
AI: "I" → TTS("I")
AI: "I understand" → TTS("I understand")
AI: "I understand your..." → TTS sentence → Send while generating next
```

### 3.2 Sentence-Level TTS Pipeline

```javascript
// Accumulate AI response and trigger TTS at sentence boundaries
let buffer = '';
const sentenceEnders = /[.!?]\s/;

function processAIChunk(chunk) {
  buffer += chunk;

  const match = buffer.match(sentenceEnders);
  if (match) {
    const sentenceEnd = match.index + 1;
    const sentence = buffer.slice(0, sentenceEnd);
    buffer = buffer.slice(sentenceEnd);

    // Trigger TTS for completed sentence (async, don't wait)
    queueTTSGeneration(sentence);
  }
}

async function queueTTSGeneration(text) {
  const audio = await generateTTS(text);
  await sendToRecallAi(bot_id, audio);
}
```

### 3.3 Predictive Response Caching

Cache common responses for immediate playback:
- Acknowledgments: "I understand", "Got it", "Let me check that"
- Transitions: "One moment please", "I'm looking into that"
- Errors: "I didn't catch that", "Could you repeat that?"

```javascript
const CACHED_RESPONSES = {
  acknowledgment: { audio: 'BASE64_AUDIO...', text: 'Got it, let me help with that.' },
  thinking: { audio: 'BASE64_AUDIO...', text: 'Let me think about that for a moment.' },
  clarification: { audio: 'BASE64_AUDIO...', text: 'Could you tell me more about that?' }
};

// Play acknowledgment immediately while processing
await sendToRecallAi(bot_id, CACHED_RESPONSES.acknowledgment.audio);
// Then generate and send actual response
```

---

## Phase 4: Infrastructure Optimization (2 Weeks)

### 4.1 n8n Workflow Architecture Refactoring

**Current:** Single orchestrator workflow handles everything
**Optimized:** Microservice-style workflow separation

```
┌─────────────────────────────────────────────────────────────────┐
│                    Event Router (Lightweight)                    │
│                    - Route by event type                         │
│                    - No heavy processing                         │
└──────────────┬──────────────────┬──────────────────┬────────────┘
               │                  │                  │
               ▼                  ▼                  ▼
    ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
    │ Transcript       │  │ Bot Lifecycle    │  │ Audio Response   │
    │ Processor        │  │ Manager          │  │ Generator        │
    └──────────────────┘  └──────────────────┘  └──────────────────┘
```

### 4.2 Database Optimization

**Current:** Supabase queries on every request
**Optimized:** Connection pooling + read replicas

```sql
-- Add indexes for common queries
CREATE INDEX idx_recall_bots_active ON recall_bots(external_id)
  WHERE status IN ('in_call', 'joining', 'ready');

CREATE INDEX idx_conversations_bot ON conversations(bot_external_id, created_at DESC);
```

### 4.3 Edge Deployment Consideration

For enterprise deployments, consider:
- Cloudflare Workers for webhook processing
- Regional n8n instances (us-west-2 to match Recall.ai)
- WebSocket connections instead of webhooks for lower latency

---

## Metrics & Monitoring

### Key Performance Indicators

| Metric | Current | Phase 1 Target | Phase 4 Target |
|--------|---------|----------------|----------------|
| End-to-end latency | 2.4-7.1s | 1.5-3s | <1.5s |
| TTS generation | 500-1500ms | 200-500ms | <200ms |
| Bot status check | 200-500ms | <100ms (cached) | <50ms |
| AI response time | 1-3s | 1-3s | 500ms-2s (streaming) |

### Monitoring Implementation

```javascript
// Add timing instrumentation to all critical nodes
const startTime = Date.now();

// ... operation ...

const duration = Date.now() - startTime;
console.log(JSON.stringify({
  metric: 'tts_generation_time',
  duration_ms: duration,
  bot_id: bot_id,
  timestamp: new Date().toISOString()
}));
```

---

## Implementation Roadmap

### Week 1: Quick Wins
- [ ] Implement conversation context caching
- [ ] Add optimistic bot status handling
- [ ] Remove redundant status verification

### Week 2: TTS Migration
- [ ] Integrate Cartesia Sonic-3 or ElevenLabs Flash
- [ ] Implement TTS provider fallback
- [ ] Add streaming TTS support

### Week 3: AI Optimization
- [ ] Implement sentence-level TTS pipeline
- [ ] Add predictive response caching
- [ ] Create acknowledgment audio library

### Week 4: Infrastructure
- [ ] Refactor workflow architecture
- [ ] Add database indexes
- [ ] Implement comprehensive monitoring

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Cartesia API instability | High | Maintain OpenAI TTS fallback |
| Streaming complexity | Medium | Implement gradually, test extensively |
| Cache invalidation | Medium | Short TTLs (30s), version keys |
| Cost increase | Low | Monitor usage, set alerts |

---

## References

- Recall.ai Audio Output Pattern: `.claude/patterns/api-integration/recall-ai-audio-output.md`
- TTS Tool Sub-Workflow: `Rg0vyFHB3u0yPaHY`
- Teams Voice Bot Orchestrator: `d3CxEaYk5mkC8sLo`
- [Cartesia Documentation](https://docs.cartesia.ai)
- [ElevenLabs Flash](https://elevenlabs.io/docs/api-reference/streaming)
- [Deepgram Aura](https://developers.deepgram.com/docs/tts-streaming)
