# TTS & Recall.ai Integration Documentation Index

**Workflow:** Teams Voice Bot v3.0 (`d3CxEaYk5mkC8sLo`)
**Generated:** 2026-01-10
**Status:** Complete Analysis & Documentation

---

## Quick Navigation

### For Quick Understanding (5 minutes)
1. Start here: **TTS_RECALL_SUMMARY.md**
   - Answers to your 5 key questions
   - Executive summary of architecture
   - Immediate action items
   - File: `/Users/jelalconnor/CODING/N8N/Workflows/TTS_RECALL_SUMMARY.md`

### For Implementation (Relay Server)
2. Go here: **RELAY_SERVER_INTEGRATION_GUIDE.md**
   - Webhook endpoint specifications
   - bot_id validation and threading
   - Error handling scenarios
   - Testing checklist
   - File: `/Users/jelalconnor/CODING/N8N/Workflows/RELAY_SERVER_INTEGRATION_GUIDE.md`

### For Deep Technical Details
3. Full architecture: **VOICE_BOT_V3_TTS_ARCHITECTURE.md**
   - Complete workflow analysis
   - All node code listings
   - Flow diagrams
   - All API integrations
   - File: `/Users/jelalconnor/CODING/N8N/Workflows/VOICE_BOT_V3_TTS_ARCHITECTURE.md`

### For Node-Specific Reference
4. Node details: **PARALLEL_TTS_SEND_NODE_REFERENCE.md**
   - Complete Parallel TTS & Send node reference
   - Step-by-step execution guide
   - Performance characteristics
   - Error handling and debugging
   - File: `/Users/jelalconnor/CODING/N8N/Workflows/PARALLEL_TTS_SEND_NODE_REFERENCE.md`

---

## Document Map

```
TTS_RECALL_DOCUMENTATION_INDEX.md (you are here)
│
├─ TTS_RECALL_SUMMARY.md (START HERE - 5 min read)
│  ├─ Answers to your 5 questions
│  ├─ Output architecture overview
│  ├─ Critical discoveries
│  ├─ bot_id critical path
│  └─ Recall.ai API usage
│
├─ RELAY_SERVER_INTEGRATION_GUIDE.md (IMPLEMENTATION - 15 min read)
│  ├─ Webhook endpoint specification
│  ├─ Payload structure and field mapping
│  ├─ bot_id validation
│  ├─ Response handling and error scenarios
│  ├─ API key configuration
│  ├─ Monitoring and observability
│  └─ Testing checklist
│
├─ VOICE_BOT_V3_TTS_ARCHITECTURE.md (DEEP DIVE - 20 min read)
│  ├─ Voice response path (complete)
│  ├─ Parallel TTS & Send node (full code)
│  ├─ Input/output contracts
│  ├─ bot_id tracking through entire workflow
│  ├─ TTS nodes analysis
│  ├─ Recall.ai integration points
│  ├─ Response routing architecture
│  ├─ Flow diagram
│  └─ Injection points for relay server
│
└─ PARALLEL_TTS_SEND_NODE_REFERENCE.md (TECHNICAL REFERENCE - 25 min read)
   ├─ Node inputs (expected format)
   ├─ Node outputs (success/skipped)
   ├─ Step-by-step execution (3 steps)
   ├─ Current hardcoded configuration
   ├─ Error handling scenarios
   ├─ Performance characteristics
   ├─ bot_id threading validation
   ├─ Testing scenarios
   ├─ Monitoring and debugging
   └─ Future improvements
```

---

## Key Questions Answered

### Q1: All nodes that handle TTS/audio output?
**Answer:** Only 2 nodes
- `Split into Sentences` - Chunks response, extracts bot_id
- `Parallel TTS & Send` - Generates audio, sends to Recall.ai

**Document:** TTS_RECALL_SUMMARY.md, Section 1

### Q2: Existing Recall.ai references?
**Answer:** Complete integration in Parallel TTS & Send (line 2)
- Bot status check: GET /api/v1/bot/{bot_id}/
- Audio delivery: POST /api/v1/bot/{bot_id}/output_audio/

**Document:** VOICE_BOT_V3_TTS_ARCHITECTURE.md, Section 5

### Q3: "Parallel TTS & Send" code node contents?
**Answer:** 150+ lines implementing 3-step process
1. Check bot status
2. Generate TTS (parallel, Promise.all)
3. Send to Recall.ai (sequential, for loop)

**Document:** PARALLEL_TTS_SEND_NODE_REFERENCE.md, Sections 3-4

### Q4: How workflow currently handles voice responses?
**Answer:** Three paths, all end at Parallel TTS & Send
- PROCESS (agent) → Orchestrator Agent → TTS
- QUICK_RESPOND (pre-router) → Quick Acknowledge/Reply → TTS
- SILENT (no response) → Log only

**Document:** VOICE_BOT_V3_TTS_ARCHITECTURE.md, Section 6

### Q5: Where bot_id variables used?
**Answer:** Extracted at start, threaded through entire pipeline to Recall.ai
- Extracted: Process Transcript
- Threaded: Load Bot State, Build Agent Context
- Critical: Split into Sentences, Parallel TTS & Send

**Document:** VOICE_BOT_V3_TTS_ARCHITECTURE.md, Section 3

---

## Critical Path Diagrams

### Bot_ID Flow
```
Webhook (body.data.bot.id)
  ↓
Process Transcript (extract)
  ↓
Route Switch (pass through)
  ↓
[PROCESS | QUICK_RESPOND | SILENT]
  ↓
Split into Sentences (MUST include)
  ↓
Parallel TTS & Send (CRITICAL - both API calls)
  ├─ GET /api/v1/bot/{bot_id}/
  └─ POST /api/v1/bot/{bot_id}/output_audio/
```

### TTS Generation & Delivery
```
Orchestrator Agent (response text)
  ↓
Check Agent Output
  ↓
Split into Sentences (chunk)
  ↓
Parallel TTS & Send
  ├─ STEP 0: Check bot active
  ├─ STEP 1: Generate audio (parallel)
  └─ STEP 2: Send to Recall.ai (sequential)
  ↓
Return tts_summary (metrics)
```

---

## Files & Location Reference

| Document | File Path | Size | Read Time |
|----------|-----------|------|-----------|
| Summary | TTS_RECALL_SUMMARY.md | ~4KB | 5 min |
| Relay Integration | RELAY_SERVER_INTEGRATION_GUIDE.md | ~8KB | 15 min |
| Architecture | VOICE_BOT_V3_TTS_ARCHITECTURE.md | ~25KB | 20 min |
| Node Reference | PARALLEL_TTS_SEND_NODE_REFERENCE.md | ~12KB | 25 min |
| This Index | TTS_RECALL_DOCUMENTATION_INDEX.md | ~8KB | 10 min |

**Location:** `/Users/jelalconnor/CODING/N8N/Workflows/`

---

## What's Already Done ✓

- [x] TTS generation with OpenAI (parallel)
- [x] Bot status checking with Recall.ai
- [x] Audio delivery to Recall.ai (sequential)
- [x] bot_id extraction and threading
- [x] Error handling and summary metrics
- [x] Support for quick + agent response paths
- [x] Sentence-level chunking for progressive audio

---

## What You Need to Do ⚠️

### Critical (Security)
- [ ] Move API keys to environment variables
  - Document: PARALLEL_TTS_SEND_NODE_REFERENCE.md, Section 4
  - Action: Migrate hardcoded keys in Parallel TTS & Send node

### High Priority (Integration)
- [ ] Build relay server webhook handler
  - Document: RELAY_SERVER_INTEGRATION_GUIDE.md, Section 2-3
  - Action: Transform Recall.ai events to n8n format, validate bot_id

- [ ] Implement response parsing
  - Document: RELAY_SERVER_INTEGRATION_GUIDE.md, Section 3
  - Action: Extract tts_summary from n8n response

### Medium Priority (Operations)
- [ ] Add monitoring to tts_summary
  - Document: RELAY_SERVER_INTEGRATION_GUIDE.md, Section 7
  - Action: Alert if send_failed > 0 or tts_failed > 0

- [ ] Test with real bot_ids
  - Document: RELAY_SERVER_INTEGRATION_GUIDE.md, Section 8
  - Action: Full integration test

### Nice-to-Have (Polish)
- [ ] Error recovery for partial TTS
- [ ] User feedback for incomplete audio
- [ ] Dashboard for metrics
- [ ] Configurable voice per user

---

## Validation Checklist

Before deploying relay server:

### Webhook Structure ✓
- [ ] Validating bot_id is present before forwarding
- [ ] Transforming payload to n8n format
  - `body.data.bot.id` = bot ID
  - `body.data.data.words[]` = sentence array
  - `body.data.data.participant.name` = speaker

### Response Handling ✓
- [ ] Parsing tts_summary from response
- [ ] Checking success criteria:
  - tts_generated > 0
  - audio_sent === tts_generated
  - send_failed === 0

### Error Handling ✓
- [ ] Timeout handling (10 seconds)
- [ ] Retry logic for failures
- [ ] Logging of metrics
- [ ] Alerting on critical failures

### Performance ✓
- [ ] Latency target: < 3 seconds for 3 sentences
- [ ] Throughput: handle 10+ concurrent calls
- [ ] No memory leaks under load

---

## Testing Workflow

### Unit Tests (Node level)
1. Test with mock bot_id
2. Test with missing bot_id
3. Test with offline bot (status check fails)
4. Test OpenAI API failure
5. Test Recall.ai delivery failure

**Document:** RELAY_SERVER_INTEGRATION_GUIDE.md, Section 8

### Integration Tests (Relay + N8N)
1. Send webhook to relay
2. Relay forwards to n8n
3. N8N processes and returns tts_summary
4. Relay parses response
5. Verify metrics

### Load Tests
1. 10 concurrent webhooks
2. 100 concurrent webhooks
3. Monitor latency and throughput
4. Check for timeouts or failures

**Document:** PARALLEL_TTS_SEND_NODE_REFERENCE.md, Section 6

---

## Monitoring Dashboard Metrics

### Per-Request Metrics
```json
{
  "bot_id": "string",
  "timestamp": "iso-datetime",
  "tts_generated": "number",
  "audio_sent": "number",
  "response_time_ms": "number",
  "bot_status": "string",
  "errors": ["array of error messages"]
}
```

### Aggregated Metrics
- TTS success rate (%)
- Delivery success rate (%)
- Average latency (ms)
- P95 latency (ms)
- Error rate (%)
- Errors by category

**Document:** RELAY_SERVER_INTEGRATION_GUIDE.md, Section 7

---

## API References

### OpenAI TTS API
```
POST https://api.openai.com/v1/audio/speech
{
  "model": "tts-1",
  "voice": "alloy",
  "input": "text to speak",
  "response_format": "mp3"
}
```

**Document:** PARALLEL_TTS_SEND_NODE_REFERENCE.md, Section 3

### Recall.ai Bot Status
```
GET https://us-west-2.recall.ai/api/v1/bot/{bot_id}/
Authorization: Token {RECALL_API_KEY}

Returns: { status_changes: [...], ... }
Valid states: in_call_recording, in_call_not_recording
```

**Document:** VOICE_BOT_V3_TTS_ARCHITECTURE.md, Section 5

### Recall.ai Audio Output
```
POST https://us-west-2.recall.ai/api/v1/bot/{bot_id}/output_audio/
Authorization: Token {RECALL_API_KEY}
{
  "kind": "mp3",
  "b64_data": "base64-encoded-mp3"
}
```

**Document:** VOICE_BOT_V3_TTS_ARCHITECTURE.md, Section 5

---

## Summary

The **Teams Voice Bot v3.0 workflow is production-ready** for TTS + Recall.ai integration. The only work needed is:

1. **Relay Server** - Webhook handler to transform and forward events
2. **API Key Migration** - Move from hardcoded to environment variables
3. **Monitoring** - Add alerting for delivery failures
4. **Testing** - Full integration test with real bot_ids

All TTS and Recall.ai logic is already implemented in the n8n workflow.

---

## Document Recommendations

### If you have 5 minutes
→ Read **TTS_RECALL_SUMMARY.md**

### If you have 15 minutes
→ Read TTS_RECALL_SUMMARY.md + RELAY_SERVER_INTEGRATION_GUIDE.md (Sections 1-3)

### If you have 30 minutes
→ Read TTS_RECALL_SUMMARY.md + RELAY_SERVER_INTEGRATION_GUIDE.md + VOICE_BOT_V3_TTS_ARCHITECTURE.md (Sections 1-3)

### If you're implementing the relay server
→ Read RELAY_SERVER_INTEGRATION_GUIDE.md carefully, then reference as needed

### If you're debugging TTS issues
→ Start with PARALLEL_TTS_SEND_NODE_REFERENCE.md Section 8 (Debugging)

### If you need the complete picture
→ Read all documents in order: Summary → Relay Guide → Architecture → Node Reference

---

## Contact/References

**N8N Workflow ID:** `d3CxEaYk5mkC8sLo`
**Workflow Name:** Teams Voice Bot v3.0 - Agent Orchestrator

**Key Nodes:**
- Split into Sentences (n8n-nodes-base.code)
- Parallel TTS & Send (n8n-nodes-base.code) ← **CRITICAL**

**External Services:**
- OpenAI TTS API
- Recall.ai Bot API
- Microsoft Teams (via Recall.ai)

---

**Generated by:** N8N MCP Workflow Analysis
**Date:** 2026-01-10
**Status:** Complete & Ready for Implementation
