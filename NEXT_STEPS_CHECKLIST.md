# Teams Voice Bot v3.0 - Next Steps Checklist

**Date:** 2026-01-10
**Status:** Analysis Complete - Ready for Implementation
**Workflow ID:** `d3CxEaYk5mkC8sLo`

---

## Phase 1: Understanding (Complete ✓)

- [x] Analyzed workflow TTS architecture
- [x] Identified Recall.ai integration points
- [x] Traced bot_id through entire pipeline
- [x] Documented all response paths
- [x] Created comprehensive documentation

**Documents Created:**
- TTS_RECALL_SUMMARY.md
- RELAY_SERVER_INTEGRATION_GUIDE.md
- VOICE_BOT_V3_TTS_ARCHITECTURE.md
- PARALLEL_TTS_SEND_NODE_REFERENCE.md
- TTS_RECALL_DOCUMENTATION_INDEX.md

---

## Phase 2: Security Fix (CRITICAL - Do First)

### Move API Keys to Environment Variables

**Current Issue:** Keys hardcoded in Parallel TTS & Send node
```javascript
const OPENAI_API_KEY = 'sk-proj-...';  // ⚠️ UNSAFE
const RECALL_API_KEY = 'RECALL_API_KEY_FROM_ENV';  // ⚠️ UNSAFE
```

**Steps:**

1. **Update N8N Environment**
   ```bash
   # Add to n8n .env or deployment config:
   N8N_OPENAI_API_KEY=sk-proj-...
   N8N_RECALL_API_KEY=RECALL_API_KEY_FROM_ENV
   ```

2. **Update Parallel TTS & Send Node**
   - Edit code node
   - Replace hardcoded keys with environment variable access:
   ```javascript
   const OPENAI_API_KEY = process.env.N8N_OPENAI_API_KEY;
   const RECALL_API_KEY = process.env.N8N_RECALL_API_KEY;

   if (!OPENAI_API_KEY || !RECALL_API_KEY) {
     throw new Error('Missing required API keys in environment');
   }
   ```

3. **Test**
   - Send test webhook
   - Verify TTS generation works
   - Check Recall.ai delivery

4. **Verify**
   - [ ] Keys no longer in workflow JSON
   - [ ] Keys in environment only
   - [ ] TTS still generates successfully

**Effort:** 15 minutes
**Priority:** CRITICAL (Security)

---

## Phase 3: Relay Server Implementation (HIGH Priority)

### Build Webhook Handler

**Location:** `/Users/jelalconnor/CODING/N8N/Workflows/voice-agent-poc/relay-server`

**Endpoint:** POST `/voice-bot-v3`

**Steps:**

1. **Create Endpoint Handler**
   ```javascript
   app.post('/voice-bot-v3', async (req, res) => {
     // 1. Validate bot_id
     // 2. Transform payload
     // 3. Forward to n8n
     // 4. Parse response
     // 5. Return status
   });
   ```

   Reference: RELAY_SERVER_INTEGRATION_GUIDE.md, Section 9

2. **Input Validation**
   - Check `req.body.bot.id` exists
   - Return 400 if missing

   Reference: RELAY_SERVER_INTEGRATION_GUIDE.md, Section 2

3. **Payload Transformation**
   - From Recall.ai format → N8N format
   - Ensure `body.data.bot.id` is set

   Reference: RELAY_SERVER_INTEGRATION_GUIDE.md, Section 9

4. **Forward to N8N**
   ```javascript
   const n8nResponse = await fetch(
     'https://n8n-instance/webhook/voice-bot-v3',
     {
       method: 'POST',
       headers: { 'Content-Type': 'application/json' },
       body: JSON.stringify(n8nPayload),
       timeout: 10000  // 10 seconds
     }
   );
   ```

5. **Response Parsing**
   - Extract `tts_summary` from response
   - Log metrics
   - Return status to caller

6. **Error Handling**
   - Missing bot_id → 400 Bad Request
   - N8N timeout → 504 Gateway Timeout
   - N8N error → 500 Internal Error

   Reference: RELAY_SERVER_INTEGRATION_GUIDE.md, Section 5

**Effort:** 30-45 minutes
**Priority:** HIGH (Required for integration)

---

## Phase 4: Monitoring & Observability (MEDIUM Priority)

### Add Metrics Collection

**Steps:**

1. **Log Per-Request Metrics**
   ```javascript
   {
     timestamp: new Date().toISOString(),
     bot_id: payload.bot.id,
     speaker: payload.speaker.name,
     n8n_response_time_ms: duration,
     tts_generated: response.tts_summary.tts_generated,
     audio_sent: response.tts_summary.audio_sent,
     send_failed: response.tts_summary.send_failed,
     bot_status: response.tts_summary.bot_status
   }
   ```

2. **Set Up Alerting**
   - Alert if `send_failed > 0`
   - Alert if `tts_failed > 0`
   - Alert if response time > 5 seconds
   - Alert if bot status check fails

3. **Create Dashboard**
   - TTS success rate (%)
   - Delivery success rate (%)
   - Average latency (ms)
   - Errors by category

Reference: RELAY_SERVER_INTEGRATION_GUIDE.md, Section 7

**Effort:** 45-60 minutes
**Priority:** MEDIUM (Operations)

---

## Phase 5: Testing (HIGH Priority)

### Unit Tests

**Test 1: Bot ID Validation**
```bash
# Missing bot_id
POST /voice-bot-v3
{ "words": [...] }
Expected: 400 Bad Request
```

**Test 2: Successful Path**
```bash
# Valid payload
POST /voice-bot-v3
{
  "bot": { "id": "test-bot-1" },
  "words": [{ "text": "hello" }],
  "speaker": { "name": "Test User" }
}
Expected: 200 OK with tts_summary
```

**Test 3: Error Handling**
```bash
# Bot offline
POST /voice-bot-v3
{ "bot": { "id": "offline-bot" }, ... }
Expected: tts_summary with skipped_reason
```

Reference: RELAY_SERVER_INTEGRATION_GUIDE.md, Section 8

**Effort:** 30 minutes
**Priority:** HIGH (Validation)

### Integration Test

**Setup:**
- Real Recall.ai bot_id
- Live n8n instance
- Real speech to Recall.ai

**Flow:**
1. Send webhook with bot_id
2. Relay transforms and forwards to n8n
3. N8N generates TTS
4. N8N sends to Recall.ai
5. Relay parses response
6. Verify metrics in logs

**Effort:** 45 minutes
**Priority:** HIGH (Pre-deployment)

---

## Phase 6: Deployment (After Testing)

### Deployment Checklist

**Pre-Deployment:**
- [ ] API keys moved to environment variables
- [ ] Relay server tested with unit tests
- [ ] Integration test passed
- [ ] Monitoring configured
- [ ] Error handling verified
- [ ] Load test passed (10+ concurrent calls)

**Deployment:**
- [ ] Deploy relay server
- [ ] Deploy n8n with environment variables
- [ ] Test webhook endpoint is accessible
- [ ] Verify metrics are logging

**Post-Deployment:**
- [ ] Monitor first 100 requests
- [ ] Check TTS success rate
- [ ] Check Recall.ai delivery rate
- [ ] Check latency (should be < 3 seconds)
- [ ] Alert on failures

**Effort:** 30 minutes
**Priority:** FINAL STEP

---

## Timeline Estimate

| Phase | Task | Effort | Priority | Status |
|-------|------|--------|----------|--------|
| 1 | Understanding | ✓ Done | - | COMPLETE |
| 2 | API Key Migration | 15 min | CRITICAL | TODO |
| 3 | Relay Server Build | 30-45 min | HIGH | TODO |
| 4 | Monitoring Setup | 45-60 min | MEDIUM | TODO |
| 5 | Testing | 75 min | HIGH | TODO |
| 6 | Deployment | 30 min | FINAL | TODO |
| **TOTAL** | | **~3.5 hours** | | |

---

## Files to Keep Handy

### Reference Documents
- RELAY_SERVER_INTEGRATION_GUIDE.md (implementation details)
- PARALLEL_TTS_SEND_NODE_REFERENCE.md (for debugging)
- VOICE_BOT_V3_TTS_ARCHITECTURE.md (complete context)

### During Implementation
- Section 9 of RELAY_SERVER_INTEGRATION_GUIDE.md (code template)
- Section 2 of RELAY_SERVER_INTEGRATION_GUIDE.md (payload format)
- Section 5 of RELAY_SERVER_INTEGRATION_GUIDE.md (error scenarios)

### During Testing
- Section 8 of RELAY_SERVER_INTEGRATION_GUIDE.md (test cases)
- PARALLEL_TTS_SEND_NODE_REFERENCE.md Section 8 (debugging tips)

---

## Critical Success Criteria

### Minimum Viable Product (MVP)
- [x] Understand TTS architecture (DONE)
- [ ] Relay server forwards webhooks
- [ ] bot_id reaches Recall.ai APIs
- [ ] tts_summary returned correctly
- [ ] API keys in environment

### Production Ready
- [ ] All tests passing
- [ ] Monitoring in place
- [ ] Error handling verified
- [ ] Load tested (10+ concurrent)
- [ ] Documentation updated
- [ ] Team trained on monitoring

---

## Troubleshooting Quick Links

**If bot_id is missing:**
→ RELAY_SERVER_INTEGRATION_GUIDE.md, Section 5 (Scenario 1)

**If TTS fails:**
→ PARALLEL_TTS_SEND_NODE_REFERENCE.md, Section 8

**If Recall.ai delivery fails:**
→ RELAY_SERVER_INTEGRATION_GUIDE.md, Section 5 (Scenarios 3-4)

**If workflow is slow:**
→ PARALLEL_TTS_SEND_NODE_REFERENCE.md, Section 6

**If monitoring is missing:**
→ RELAY_SERVER_INTEGRATION_GUIDE.md, Section 7

---

## Questions to Answer Before Starting

1. **Where is n8n deployed?**
   - Used in Phase 3, Step 4

2. **What are the actual API keys?**
   - Needed for Phase 2

3. **How is relay server deployed?**
   - Needed for Phase 6

4. **Who monitors alerts?**
   - Needed for Phase 4

5. **What's the bot_id format from Recall.ai?**
   - Needed for Phase 5 (testing)

---

## Sign-Off Checklist

- [ ] Documentation reviewed
- [ ] API keys secured
- [ ] Relay server implemented
- [ ] Tests passing
- [ ] Monitoring configured
- [ ] Team trained
- [ ] Ready for production

---

**Next Action:** Start Phase 2 (Security) → Migrate API keys to environment variables

**Estimated Time to Production:** 3-4 hours of active work

**Date to Review:** 2026-01-11 (next day)

---

**Questions?** Refer to the TTS_RECALL_DOCUMENTATION_INDEX.md for navigation to relevant sections.
