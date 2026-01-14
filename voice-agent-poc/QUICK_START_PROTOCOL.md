# Voice Agent Quick Start Protocol

## System Overview

```
Browser → Relay Server (Railway) → OpenAI Realtime API
              ↕                         ↕
         n8n Workflows ←──────────── Tool Calls
              ↓
         PostgreSQL (audit trail)
```

---

## 1. Prerequisites Checklist

### n8n Workflows (3 total)
| Workflow | ID | Status | Webhook Path |
|----------|-----|--------|--------------|
| Voice Tool: Send Gmail | `kBuTRrXTJF1EEBEs` | **NEEDS ACTIVATION** | `/execute-gmail` |
| Voice Tool: Query Vector DB | `uuf3Qaba5O8YsKaI` | Active | `/query-vector-db` |
| Voice Tool: Get Session Context | `Hk1ro3MuzlDNuAFi` | Active | `/get-session-context` |

**To Activate Send Gmail:**
1. Open n8n Cloud → Workflows
2. Find "Voice Tool: Send Gmail"
3. Toggle the activation switch to ON

### Required Environment Variables (Railway)
```bash
# Required
OPENAI_API_KEY=sk-...
CALLBACK_BASE_URL=https://your-railway-app.up.railway.app

# Optional (defaults shown)
N8N_BASE_URL=https://jayconnorexe.app.n8n.cloud
PORT=3000
LOG_LEVEL=INFO
GATE2_CONFIRMATION_TIMEOUT_MS=30000

# Security (recommended for production)
N8N_WEBHOOK_SECRET=shared-secret-with-n8n
```

---

## 2. Testing Without Deployment (Local)

### Start Local Relay Server
```bash
cd voice-agent-poc/relay-server
npm install
OPENAI_API_KEY=sk-... CALLBACK_BASE_URL=http://localhost:3000 npm run dev
```

### Test Health Endpoint
```bash
curl http://localhost:3000/health
# Expected: {"status":"ok","timestamp":"..."}
```

### Test n8n Workflows Directly

**Query Vector DB (2-gate workflow):**
```bash
curl -X POST https://jayconnorexe.app.n8n.cloud/webhook/query-vector-db \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test_session_001",
    "intent_id": "intent_001",
    "callback_url": "http://localhost:3000/tool-progress",
    "parameters": {
      "user_query": "Q3 sales northwest region",
      "structured_query": {
        "filters": {"region": ["WA", "OR", "ID"]},
        "semantic_query": "quarterly sales data"
      }
    }
  }'
```

**Get Session Context:**
```bash
curl -X POST https://jayconnorexe.app.n8n.cloud/webhook/get-session-context \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test_session_001",
    "context_key": "last_query_results"
  }'
```

**Send Gmail (3-gate workflow - requires activation):**
```bash
curl -X POST https://jayconnorexe.app.n8n.cloud/webhook/execute-gmail \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test_session_001",
    "intent_id": "intent_002",
    "callback_url": "http://localhost:3000/tool-progress",
    "parameters": {
      "to": "test@example.com",
      "subject": "Test Email",
      "body": "This is a test email from the voice agent."
    }
  }'
```

---

## 3. Gated Execution Flow

### Gate Callback Format
n8n workflows POST to `CALLBACK_BASE_URL/tool-progress` with:

```json
{
  "tool_call_id": "tc_xxxx",
  "intent_id": "intent_xxxx",
  "status": "PREPARING|READY_TO_SEND|COMPLETED|CANCELLED|FAILED",
  "gate": 1|2|3,
  "cancellable": true|false,
  "requires_confirmation": true|false,
  "message": "Human-readable status",
  "voice_response": "TTS response for agent",
  "result": { ... },
  "execution_time_ms": 1234
}
```

### Expected Responses by Gate

| Gate | Status | Relay Response | Effect |
|------|--------|----------------|--------|
| 1 | PREPARING | `{continue: true, cancel: false}` | Proceed to next step |
| 1 | PREPARING | `{continue: false, cancel: true, reason: "..."}` | Cancel workflow |
| 2 | READY_TO_SEND | (Waits for confirmation) | Holds HTTP until user confirms |
| 3 | COMPLETED | `{received: true, status: "acknowledged"}` | Workflow ends |

### Gate 2 Confirmation (Human-in-the-Loop)

The relay server holds the HTTP response at Gate 2 until:
- **User confirms**: POST `/tool-confirm` with `{tool_call_id, confirmed: true}`
- **User cancels**: POST `/tool-cancel` with `{tool_call_id, reason: "..."}`
- **Timeout (30s)**: Auto-cancels for safety

---

## 4. Workflow Data Flow

### Send Gmail (3-Gate)
```
Webhook → Generate ID → INSERT EXECUTING
    ↓
GATE 1: HTTP callback {status: "PREPARING", cancellable: true}
    ↓ (on continue)
GATE 2: HTTP callback {status: "READY_TO_SEND", requires_confirmation: true}
    ↓ (on confirmation)
Gmail: Send Email → Format Result → UPDATE COMPLETED
    ↓
GATE 3: HTTP callback {status: "COMPLETED", voice_response: "..."}
    ↓
Respond to Webhook: Success
```

### Query Vector DB (2-Gate)
```
Webhook → Generate ID → INSERT EXECUTING
    ↓
GATE 1: HTTP callback {status: "QUERYING", cancellable: true}
    ↓ (on continue)
Execute Vector Query → Format Results → UPSERT session_context
    ↓
UPDATE COMPLETED
    ↓
GATE 2: HTTP callback {status: "COMPLETED", context_available: true}
    ↓
Respond to Webhook: Success
```

---

## 5. Debugging

### Check n8n Executions
- **URL**: https://jayconnorexe.app.n8n.cloud/executions
- Filter by workflow to see gate callback results
- Look for IF node routing (TRUE = cancelled, FALSE = continue)

### Common Issues

| Issue | Solution |
|-------|----------|
| Gate 1 returns cancel | Check relay server logs for cancellation request |
| Gate 2 timeout | Increase `GATE2_CONFIRMATION_TIMEOUT_MS` or confirm faster |
| HMAC failure | Set `N8N_WEBHOOK_SECRET` to same value in n8n HTTP nodes |
| Missing callback | Verify `CALLBACK_BASE_URL` is set and accessible |
| Gmail not sending | Activate workflow in n8n UI |

### View Relay Server Logs
```bash
# Local
LOG_LEVEL=DEBUG npm run dev

# Railway
railway logs
```

---

## 6. Railway Deployment

### Deploy Command
```bash
cd voice-agent-poc/relay-server
railway up
```

### Set Environment Variables
```bash
railway variables set OPENAI_API_KEY=sk-...
railway variables set CALLBACK_BASE_URL=https://your-app.up.railway.app
railway variables set N8N_WEBHOOK_SECRET=your-shared-secret
```

### Verify Deployment
```bash
# Get deployment URL
railway status

# Test health
curl https://your-app.up.railway.app/health
```

---

## 7. End-to-End Test Script

Save as `test-gated-flow.sh`:
```bash
#!/bin/bash
# Test full gated execution flow

RELAY_URL="${1:-http://localhost:3000}"
N8N_URL="${2:-https://jayconnorexe.app.n8n.cloud}"
SESSION_ID="test_$(date +%s)"

echo "=== Testing Voice Agent Gated Flow ==="
echo "Relay: $RELAY_URL"
echo "n8n: $N8N_URL"
echo "Session: $SESSION_ID"
echo ""

# Test 1: Health check
echo "1. Health check..."
curl -s "$RELAY_URL/health" | jq .
echo ""

# Test 2: Query Vector DB
echo "2. Query Vector DB (2-gate)..."
curl -s -X POST "$N8N_URL/webhook/query-vector-db" \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$SESSION_ID\",
    \"intent_id\": \"intent_query\",
    \"callback_url\": \"$RELAY_URL/tool-progress\",
    \"parameters\": {
      \"user_query\": \"Q3 sales\",
      \"structured_query\": {}
    }
  }" | jq .
echo ""

# Test 3: Get Session Context
echo "3. Get Session Context..."
sleep 2  # Wait for context to be stored
curl -s -X POST "$N8N_URL/webhook/get-session-context" \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$SESSION_ID\",
    \"context_key\": \"last_query_results\"
  }" | jq .
echo ""

echo "=== Tests Complete ==="
```

Usage:
```bash
chmod +x test-gated-flow.sh
./test-gated-flow.sh http://localhost:3000
```

---

## 8. PostgreSQL Schema Reference

```sql
-- Tool calls audit table
CREATE TABLE tool_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tool_call_id VARCHAR(100) UNIQUE NOT NULL,
    session_id VARCHAR(100) NOT NULL,
    intent_id VARCHAR(100),
    function_name VARCHAR(100) NOT NULL,
    parameters JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(20) NOT NULL DEFAULT 'EXECUTING',
    result JSONB,
    error_message TEXT,
    voice_response TEXT,
    callback_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    execution_time_ms INTEGER
);

-- Session context (cross-tool data sharing)
CREATE TABLE session_context (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(100) NOT NULL,
    context_key VARCHAR(100) NOT NULL,
    context_value JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    UNIQUE(session_id, context_key)
);
```

---

## Quick Reference Card

| Action | Command |
|--------|---------|
| Start local | `npm run dev` |
| Deploy | `railway up` |
| View logs | `railway logs` |
| Test health | `curl $URL/health` |
| Confirm Gate 2 | `POST /tool-confirm {tool_call_id, confirmed: true}` |
| Cancel | `POST /tool-cancel {tool_call_id, reason}` |
| n8n executions | https://jayconnorexe.app.n8n.cloud/executions |
