# Enterprise Voice Agent - Comprehensive Testing Plan

**Date:** 2026-01-13
**System:** Railway Relay Server + n8n + Supabase + OpenAI Realtime

---

## 1. System Components Under Test

| Component | Endpoint/Location | Purpose |
|-----------|-------------------|---------|
| **Relay Server** | `voice-agent-relay-production.up.railway.app` | WebSocket relay, TTS, tool execution |
| **n8n Instance** | `jayconnorexe.app.n8n.cloud` | Workflow orchestration |
| **PostgreSQL** | `db.shaefijojvpougpvdvqi.supabase.co` | State persistence |
| **OpenAI Realtime** | `api.openai.com/v1/realtime` | Voice AI |
| **Recall.ai** | `us-west-2.recall.ai` | Meeting audio injection |

---

## 2. Test Categories

### A. Infrastructure Tests

| Test | Command | Expected Result |
|------|---------|-----------------|
| Relay Health | `curl https://voice-agent-relay-production.up.railway.app/health` | `{"status":"healthy","database":"connected"}` |
| Database Connection | `psql $DATABASE_URL -c "SELECT 1"` | Returns `1` |
| n8n API Health | `curl https://jayconnorexe.app.n8n.cloud/healthz` | `200 OK` |

### B. Database Schema Tests

| Table | Test Query | Purpose |
|-------|-----------|---------|
| `tool_calls` | `SELECT COUNT(*) FROM tool_calls` | Gated execution tracking |
| `session_context` | `SELECT COUNT(*) FROM session_context` | Cross-tool data sharing |
| `chat_messages` | `SELECT COUNT(*) FROM chat_messages` | Conversation history |
| `session_summaries` | `SELECT COUNT(*) FROM session_summaries` | AI-generated summaries |
| `tool_executions` | `SELECT COUNT(*) FROM tool_executions` | Legacy tool logging |
| `audit_trail` | `SELECT COUNT(*) FROM audit_trail` | Compliance logging |

### C. Webhook Endpoint Tests

| Workflow | Webhook Path | Method | Test Status |
|----------|--------------|--------|-------------|
| Send Gmail | `/execute-gmail` | POST | Pending deploy |
| Query Vector DB | `/query-vector-db` | POST | Pending deploy |
| Get Session Context | `/get-session-context` | GET | Pending deploy |
| Session Summary | `/session-ended` | POST | Pending deploy |
| Voice Tools (legacy) | `/voice-tools` | POST | Pending verify |

### D. Data Flow Tests

#### D1. TTS Pipeline Flow
```
User Speech → OpenAI Realtime (STT)
    ↓
OpenAI Realtime (AI Response)
    ↓
Relay: sendAudioToRecallBot()
    ↓
OpenAI TTS API (POST /v1/audio/speech)
    ↓
Recall.ai (POST /bot/{id}/output_audio)
    ↓
Meeting Audio Output
```

**Test:** Verify transcript → TTS → Recall.ai flow completes within 3 seconds.

#### D2. Tool Call Flow
```
User Intent → OpenAI function_call
    ↓
Relay: executeToolViaN8n()
    ↓
n8n Webhook → Gated Workflow
    ↓
PostgreSQL: INSERT tool_calls
    ↓
Callback: Gate 1 (cancellable)
    ↓
Execute Tool (Gmail/Vector DB)
    ↓
PostgreSQL: UPDATE COMPLETED
    ↓
Callback: Gate 3 (completion)
```

**Test:** Verify tool call from intent to completion in < 5 seconds.

#### D3. Session Summary Flow
```
Session End Event → Relay
    ↓
POST /session-ended
    ↓
n8n: Fetch chat_messages, tool_calls, analytics
    ↓
OpenAI GPT-4: Generate summary
    ↓
PostgreSQL: INSERT session_summaries
    ↓
Callback: summary_generated
```

**Test:** Verify async summary generation completes within 30 seconds.

---

## 3. Test Execution Scripts

### Test 1: Infrastructure Health
```bash
# Relay Server
curl -s https://voice-agent-relay-production.up.railway.app/health | jq .

# Database Tables
psql $DATABASE_URL -c "\dt"

# Table Row Counts
psql $DATABASE_URL -c "
SELECT
  'tool_calls' as table_name, COUNT(*) FROM tool_calls
UNION ALL
SELECT 'session_context', COUNT(*) FROM session_context
UNION ALL
SELECT 'chat_messages', COUNT(*) FROM chat_messages
UNION ALL
SELECT 'session_summaries', COUNT(*) FROM session_summaries;
"
```

### Test 2: Insert Test Data
```sql
-- Test session context
INSERT INTO session_context (session_id, context_key, context_value)
VALUES ('test_session_001', 'test_key', '{"test": true}')
ON CONFLICT (session_id, context_key) DO UPDATE SET context_value = '{"test": true}';

-- Test tool call
INSERT INTO tool_calls (tool_call_id, session_id, function_name, status, parameters)
VALUES ('tc_test_001', 'test_session_001', 'send_email', 'COMPLETED', '{"to": "test@example.com"}');

-- Test chat message
INSERT INTO chat_messages (session_id, message_index, role, content)
VALUES ('test_session_001', 1, 'user', 'Hello, this is a test message');

-- Verify
SELECT * FROM session_context WHERE session_id = 'test_session_001';
SELECT * FROM tool_calls WHERE session_id = 'test_session_001';
SELECT * FROM chat_messages WHERE session_id = 'test_session_001';
```

### Test 3: Webhook Connectivity (after deployment)
```bash
# Test voice tools webhook
curl -X POST https://jayconnorexe.app.n8n.cloud/webhook-test/voice-tools \
  -H "Content-Type: application/json" \
  -d '{"function": "test", "args": {}, "session_id": "test_001"}'

# Test session summary webhook
curl -X POST https://jayconnorexe.app.n8n.cloud/webhook-test/session-ended \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test_session_001", "user_email": "test@example.com"}'
```

---

## 4. Symbiotic Ecosystem Validation

### Data Flow Relationships

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SYMBIOTIC ECOSYSTEM DATA FLOWS                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Browser/Meeting Client                                                      │
│       │                                                                      │
│       │ WebSocket                                                            │
│       ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ RELAY SERVER (Railway)                                               │    │
│  │   ├─ OpenAI Realtime ←→ Voice AI                                     │    │
│  │   ├─ TTS Pipeline → Recall.ai                                        │    │
│  │   ├─ Tool Execution → n8n                                            │    │
│  │   └─ Session Logging → PostgreSQL                                    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│       │              │                    │                                  │
│       │              │                    │                                  │
│       ▼              ▼                    ▼                                  │
│  ┌─────────┐   ┌─────────────┐    ┌─────────────────────────────────────┐   │
│  │ Recall  │   │ PostgreSQL  │    │ n8n Instance                        │   │
│  │ .ai     │   │             │    │   ├─ /execute-gmail                 │   │
│  │         │   │ Tables:     │    │   ├─ /query-vector-db               │   │
│  │ Audio   │   │ • tool_calls│    │   ├─ /get-session-context           │   │
│  │ Output  │   │ • chat_msgs │    │   └─ /session-ended (async)         │   │
│  │         │   │ • summaries │    │                                     │   │
│  └─────────┘   │ • context   │    └─────────────────────────────────────┘   │
│                └─────────────┘                                               │
│                      ↑                                                       │
│                      │                                                       │
│                      └── Session Summary Workflow reads all data             │
│                          and writes executive summaries                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Cross-Component Dependencies

| Source | Target | Data Type | Purpose |
|--------|--------|-----------|---------|
| Relay → PostgreSQL | Direct | tool_calls, audit_trail | Real-time logging |
| Relay → n8n | HTTP | Tool execution requests | Gated workflow execution |
| n8n → PostgreSQL | Direct | tool_calls updates | State tracking |
| n8n → Relay | HTTP | Callbacks | Gate progress notifications |
| Session Summary → PostgreSQL | Read | chat_messages, tool_calls | Summary generation |
| Session Summary → PostgreSQL | Write | session_summaries | Store results |

---

## 5. Test Results

| Test Category | Status | Notes |
|---------------|--------|-------|
| Relay Health | ✅ PASS | Healthy, DB connected |
| Database Schema | ✅ PASS | All 13 tables created |
| Chat Messages Table | ✅ NEW | Created for conversation tracking |
| Session Summaries Table | ✅ NEW | Created for async summaries |
| n8n Workflows | ⚠️ PENDING | Need deployment (API key issue) |
| Webhook Endpoints | ⚠️ PENDING | Blocked by workflow deployment |
| TTS Pipeline | ⚠️ MANUAL | Requires live session test |
| Tool Call Flow | ⚠️ MANUAL | Requires live session test |

---

## 6. Next Steps

1. **Resolve n8n API Key** - Verify permissions in n8n cloud dashboard
2. **Deploy Workflows** - Import JSON files to n8n instance
3. **Activate Webhooks** - Enable workflows after deployment
4. **Live Integration Test** - Connect browser client, test full flow
5. **Load Testing** - Simulate multiple concurrent sessions

---

## 7. Appendix: Workflow Files

| File | Webhook | Purpose |
|------|---------|---------|
| `voice-tool-send-gmail.json` | `/execute-gmail` | Gated email with 3 checkpoints |
| `voice-tool-query-vector-db.json` | `/query-vector-db` | Vector query + context storage |
| `voice-tool-get-session-context.json` | `/get-session-context` | Context retrieval |
| `voice-session-summary.json` | `/session-ended` | Async summary generation |
| `voice-agent-tools.json` | `/voice-tools` | Legacy tool router |
