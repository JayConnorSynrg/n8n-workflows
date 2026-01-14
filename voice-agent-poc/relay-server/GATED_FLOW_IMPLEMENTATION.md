# Gated Execution Flow - Implementation Complete

**Completed:** 2026-01-13
**Status:** IMPLEMENTED - Ready for deployment testing

---

## Overview

The gated execution flow enables human-in-the-loop confirmation at multiple checkpoints during tool execution. When the AI agent executes a tool (like sending an email), the workflow pauses at gates to:

1. Notify the user of progress
2. Check for cancellation requests
3. Allow the AI to speak status updates

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    GATED EXECUTION FLOW                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Browser/Client                                                              │
│       │                                                                      │
│       │ WebSocket                                                            │
│       ▼                                                                      │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ RELAY SERVER (index-enhanced.js)                                      │  │
│  │                                                                       │  │
│  │  WebSocket ←→ OpenAI Realtime API                                     │  │
│  │       │                                                               │  │
│  │       │ Tool Call Detected                                            │  │
│  │       ▼                                                               │  │
│  │  HTTP POST → n8n Webhook                                              │  │
│  │       │      (with callback_url)                                      │  │
│  │       │                                                               │  │
│  │  ┌────────────────────────────────────────────────────────────────┐  │  │
│  │  │ CALLBACK ENDPOINTS                                             │  │  │
│  │  │                                                                │  │  │
│  │  │ POST /tool-progress  ← n8n gate callbacks                      │  │  │
│  │  │ POST /tool-cancel    ← User cancellation requests              │  │  │
│  │  │ GET  /tool-status/:id ← Status queries                         │  │  │
│  │  │                                                                │  │  │
│  │  └────────────────────────────────────────────────────────────────┘  │  │
│  │       │                                                               │  │
│  │       │ Status Update                                                 │  │
│  │       ▼                                                               │  │
│  │  notifyAgentOfGateStatus()                                            │  │
│  │       │                                                               │  │
│  │       │ response.create (with instructions)                           │  │
│  │       ▼                                                               │  │
│  │  OpenAI Agent speaks to user                                          │  │
│  │                                                                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│       │                                                                      │
│       │ POST /execute-gmail                                                  │
│       ▼                                                                      │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ N8N WORKFLOW (voice-tool-send-gmail.json)                             │  │
│  │                                                                       │  │
│  │  Webhook → Generate ID → INSERT record → Gate 1 → Check Cancel        │  │
│  │                                              │                        │  │
│  │                    ┌─────────────────────────┘                        │  │
│  │                    │                                                  │  │
│  │              [cancelled?]                                             │  │
│  │               YES  │  NO                                              │  │
│  │                ▼   ▼                                                  │  │
│  │           Cancel  Gate 2 → Check Cancel → Gmail Send → Format Result  │  │
│  │                                                              │        │  │
│  │                                                              ▼        │  │
│  │                               UPDATE COMPLETED → Gate 3 → Respond     │  │
│  │                                                                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Gate Flow Sequence

| Gate | Status | Callback Payload | Response |
|------|--------|------------------|----------|
| 1 | PREPARING | `{status: "PREPARING", gate: 1, cancellable: true}` | `{continue: true}` or `{cancel: true}` |
| 2 | READY_TO_SEND | `{status: "READY_TO_SEND", gate: 2, requires_confirmation: true}` | `{continue: true}` or `{cancel: true}` |
| 3 | COMPLETED | `{status: "COMPLETED", result, voice_response}` | `{received: true, status: "acknowledged"}` |

---

## Key Components

### 1. Relay Server Endpoints (index-enhanced.js)

```javascript
// POST /tool-progress - Receive gate callbacks
// Handles: PREPARING, READY_TO_SEND, COMPLETED, CANCELLED, FAILED

// POST /tool-cancel - Request cancellation
// Sets cancelRequests[tool_call_id] = {cancelled: true, reason}

// GET /tool-status/:id - Query status
// Returns current status and cancel state
```

### 2. Agent Notification Function

```javascript
function notifyAgentOfGateStatus(connectionId, gateStatus, details) {
  // Sends response.create to OpenAI with instructions
  // Agent speaks status update to user
}
```

### 3. n8n Workflow Structure

**File:** `n8n-workflows/voice-tool-send-gmail.json`

- **15 nodes** with proper connection flow
- All HTTP callbacks reference `$('Code: Generate ID').first().json.callback_url`
- IF conditions check `$json.cancel` from HTTP response
- Parameters stored in Generate ID node for reference throughout

---

## Cancellation Flow

```
User says "Stop!" or "Cancel"
       │
       ▼
Relay: POST /tool-cancel
       │
       │ cancelRequests[id] = {cancelled: true, reason: "User requested"}
       │
       ▼
n8n: Gate callback arrives
       │
       │ checkCancellation(id) → found!
       │
       ▼
Relay: Returns {cancel: true, reason: "User requested"}
       │
       ▼
n8n: IF node routes to cancel branch
       │
       │ UPDATE status = 'CANCELLED'
       │ POST callback {status: "CANCELLED"}
       │
       ▼
Agent: "I've cancelled that action."
```

---

## Testing

### Test Script
```bash
cd /Users/jelalconnor/CODING/N8N/Workflows/voice-agent-poc/relay-server
chmod +x test-gated-flow.sh
./test-gated-flow.sh
```

### Manual Testing

```bash
# Health check
curl http://localhost:3000/health

# Gate 1 callback
curl -X POST http://localhost:3000/tool-progress \
  -H "Content-Type: application/json" \
  -d '{"tool_call_id":"tc_test","status":"PREPARING","gate":1,"cancellable":true}'

# Cancellation request
curl -X POST http://localhost:3000/tool-cancel \
  -H "Content-Type: application/json" \
  -d '{"tool_call_id":"tc_test","reason":"User requested"}'

# Status check
curl http://localhost:3000/tool-status/tc_test
```

---

## Deployment Requirements

### Environment Variables

```env
# Required for gated flow
CALLBACK_BASE_URL=https://your-relay.railway.app

# Required for server
OPENAI_API_KEY=sk-...
DATABASE_URL=postgres://...

# n8n integration
N8N_BASE_URL=https://jayconnorexe.app.n8n.cloud

# Security (Priority 3 - Optional but recommended)
N8N_WEBHOOK_SECRET=your-shared-secret-key  # HMAC authentication for callbacks

# Timeouts
GATE2_CONFIRMATION_TIMEOUT_MS=30000  # 30 seconds to confirm Gate 2
```

### HMAC Authentication

When `N8N_WEBHOOK_SECRET` is set, callback endpoints require HMAC-SHA256 authentication:

**n8n HTTP Request Node Configuration:**
```
Headers:
  x-n8n-signature: <HMAC-SHA256 hex of "timestamp.body">
  x-n8n-timestamp: <Unix timestamp in seconds>
```

**Security features:**
- Constant-time signature comparison (prevents timing attacks)
- 5-minute timestamp tolerance (prevents replay attacks)
- Graceful fallback when HMAC is disabled (for testing)

### Database Tables

The `tool_calls` table stores execution state:

```sql
CREATE TABLE tool_calls (
    tool_call_id VARCHAR(100) PRIMARY KEY,
    session_id VARCHAR(100),
    intent_id VARCHAR(100),
    function_name VARCHAR(100),
    parameters JSONB,
    status VARCHAR(20),  -- EXECUTING, COMPLETED, CANCELLED, FAILED
    result JSONB,
    voice_response TEXT,
    callback_url TEXT,
    created_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);
```

---

## Files Modified

| File | Changes |
|------|---------|
| `index-enhanced.js:1907-1984` | Added `notifyAgentOfGateStatus()` function |
| `index-enhanced.js:2030-2180` | Updated gate handlers to call notification |
| `voice-tool-send-gmail.json` | Fixed callback_url references throughout |

---

## Success Criteria Met

**Core Functionality:**
- [x] POST /tool-progress endpoint receives gate callbacks
- [x] Cancel requests tracked in cancelRequests Map
- [x] Gate response logic returns continue/cancel
- [x] OpenAI agent notified via response.create
- [x] n8n workflow properly passes callback_url

**Priority 1 - Critical:**
- [x] True Gate 2 waiting mechanism (HTTP response held until confirmation)
- [x] Callback URL whitelist validation

**Priority 2 - Before Scale:**
- [x] Rate limiting on callback endpoints (100 req/min per IP)
- [x] Idempotency keys to prevent duplicate processing
- [x] Timeout on n8n calls with AbortSignal
- [x] Clean session cache on error paths

**Priority 3 - Hardening:**
- [x] HMAC authentication for callback endpoints (optional, env-based)
- [x] Detailed Gate 2 flow logging `[GATE2-FLOW]` prefix
- [x] Comprehensive test script for gated flow

**Testing:**
- [x] test-gated-flow.sh with 10 test cases

---

## Railway CLI Deployment Pattern

### Quick Reference

```bash
# Check current context
railway status          # Shows: Project, Environment, Service
railway whoami          # Shows logged-in user

# Get deployment URL
railway domain          # Production URL: https://voice-agent-relay-production.up.railway.app

# View logs and variables
railway logs            # View recent deployment logs
railway logs --lines N  # View N most recent lines
railway variables       # View environment variables

# Deploy
railway up              # Upload and deploy from current directory
railway up --detach     # Deploy in background (returns build URL)
railway redeploy --yes  # Force redeploy current deployment

# Check deployment status
railway deployment list # List all deployments with status (SUCCESS/FAILED/REMOVED)
railway logs --deployment <ID>  # View logs for specific deployment
```

### Troubleshooting Deployments

1. **Check deployment status**: `railway deployment list`
2. **If FAILED**: `railway logs --deployment <ID>` to see error
3. **Common issues**:
   - JavaScript hoisting errors (use `node --check` locally first)
   - Missing dependencies (check package.json)
   - Environment variable issues (check `railway variables`)

### Current Deployment

- **URL**: `https://voice-agent-relay-production.up.railway.app`
- **Project**: VOICE AGENT - N8N
- **Service**: voice-agent-relay
- **Environment**: production

---

## Next Steps

1. ~~**Deploy to Railway** with proper environment variables~~ ✅ Completed 2026-01-14
2. **Activate n8n workflow** at jayconnorexe.app.n8n.cloud
3. **Live testing** with actual voice conversation
4. **Monitor** gate callbacks in logs

---

*Implementation completed by SYNRG orchestration*
