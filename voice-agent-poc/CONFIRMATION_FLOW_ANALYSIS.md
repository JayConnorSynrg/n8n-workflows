# Enterprise Voice Agent - Confirmation Flow Analysis

**Generated:** 2026-01-13
**Purpose:** Analyze implementation status of the multi-step confirmation flow

---

## User Requirements (Requested)

The user specified the following flow:
1. Agent identifies request
2. Confirms with the user
3. Asks for info
4. Confirms the info
5. At webhook confirmation point, asks again to execute

Plus capabilities for:
- Chat session history access
- Database query via SQL
- n8n tools query for context

---

## Current Implementation Status

### Level 1: OpenAI Prompt-Based Confirmation (IMPLEMENTED)

**Location:** `index-enhanced.js:550-556`

```javascript
EMAIL WORKFLOW:
When asked to send an email:
1. Confirm the recipient, subject, and key points with the user
2. Draft the email content
3. Read back the draft and ask for confirmation
4. Only call send_email after explicit user confirmation
5. Report success/failure after sending
```

**Status:** IMPLEMENTED via OpenAI session instructions
**Behavior:** Agent is prompted to confirm before calling tools

### Level 2: n8n Gated Workflow (PARTIALLY IMPLEMENTED)

**Location:** `n8n-workflows/voice-tool-send-gmail.json`

The n8n workflow has gated execution:

| Gate | Status | Callback Payload | Purpose |
|------|--------|------------------|---------|
| 1 | PREPARING | `{status: "PREPARING", gate: 1, cancellable: true}` | Pre-execution checkpoint |
| 2 | READY_TO_SEND | `{status: "READY_TO_SEND", gate: 2, requires_confirmation: true}` | Final confirmation before Gmail send |
| 3 | COMPLETED | `{status: "COMPLETED", result, voice_response}` | Completion notification |

**Status:** WORKFLOW EXISTS but callbacks have no receiver

### Level 3: Relay Server Callback Endpoint (NOT IMPLEMENTED)

**Gap Identified:** The relay server does NOT have a callback endpoint.

**Current endpoints in `index-enhanced.js:1743-1759`:**
- `/health` (GET) - Health check only
- All other HTTP requests get 426 Upgrade Required

**Missing endpoints (from plan `dynamic-finding-axolotl.md`):**
- `POST /tool-progress` - Receive gate callbacks from n8n
- `POST /tool-complete` - Receive completion notifications

**Consequence:** n8n workflows send callbacks to `callback_url`, but there's no endpoint to:
1. Receive the PREPARING/READY_TO_SEND status
2. Check if user requested cancellation
3. Respond with `{continue: true}` or `{cancel: true}`

---

## Chat History & Context Capabilities

### Session History (IMPLEMENTED)

**Location:** `index-enhanced.js:607-726`

```javascript
class ConversationContext {
  constructor(connectionId) {
    this.items = []; // Full conversation history
    this.toolCalls = []; // Just tool calls for quick reference
  }

  addUserMessage(transcript) { ... }
  addAssistantMessage(transcript) { ... }
  addToolCall(name, args, callId) { ... }
  setToolResult(callId, result) { ... }

  getToolExecutionContext() {
    return {
      recentMessages: this.items.slice(-10),
      previousToolCalls: this.toolCalls.map(tc => ({...})),
      messageCount: this.items.length,
      toolCallCount: this.toolCalls.length
    };
  }
}
```

**Status:** IMPLEMENTED - Full conversation tracking with tool calls

### Session Cache (IMPLEMENTED)

**Location:** `index-enhanced.js:99-290`

```javascript
class SessionCache {
  async getContext(contextKey) { ... }   // Memory-first, DB fallback
  async setContext(contextKey, value, ttlSeconds) { ... }  // Write-through
  async setQueryResults(queryId, data) { ... }
  async getQueryResults(queryId) { ... }
  async addCompletedTool(toolData) { ... }
  async getAgentContext() { ... }  // Returns pending + recent tool calls
}
```

**Status:** IMPLEMENTED - Write-through cache with PostgreSQL persistence

### Database Query (IMPLEMENTED)

**Location:** `index-enhanced.js:1518-1531` (Cache-first pattern)

The `get_session_context` tool allows the agent to query stored context.

**Status:** IMPLEMENTED

### n8n Tools Query (IMPLEMENTED)

Three tools available:
1. `send_email` - Gmail send
2. `get_session_context` - Session data retrieval
3. `query_vector_db` - Vector database search

**Status:** IMPLEMENTED

---

## Gap Analysis Summary

| Requirement | Status | Gap |
|-------------|--------|-----|
| Agent confirms before executing | IMPLEMENTED | Via OpenAI prompt |
| Agent asks for info | IMPLEMENTED | Via OpenAI prompt |
| Agent confirms info | IMPLEMENTED | Via OpenAI prompt |
| Webhook checkpoint confirmation | PARTIAL | n8n workflow exists, relay endpoint missing |
| Chat session history | IMPLEMENTED | ConversationContext class |
| Database query | IMPLEMENTED | get_session_context tool |
| n8n tools context | IMPLEMENTED | Tool context passed to n8n |

### Critical Gap: Callback Endpoint Missing

The architecture in the plan (`dynamic-finding-axolotl.md`) specifies:

```
Relay: Callback Endpoint: POST /tool-progress
    ├── Receives: { status, progress, gate, cancellable }
    ├── Checks: cancelRequests[intent_id]
    └── Returns: { continue: true } or { cancel: true }
```

**This endpoint does NOT exist in the current relay server.**

---

## What Works Today

1. Agent prompted to confirm email details before calling tool
2. Agent confirms info verbally
3. Tool executes via n8n webhook
4. Results returned to agent
5. Agent announces completion

**This is a 3-step flow:**
```
User request → Agent confirms → Tool executes → Agent announces
```

---

## What the Plan Specifies

The plan specifies a **5-gate flow** with HTTP callbacks:

```
User request
    ↓
Agent confirms (relay local - no n8n)
    ↓
User confirms
    ↓
n8n GATE 1: PREPARING → callback → relay responds continue/cancel
    ↓
n8n GATE 2: READY_TO_SEND → callback → Agent asks "Send it?" → relay responds
    ↓
n8n GATE 3: Tool executes (Gmail)
    ↓
n8n GATE 4: COMPLETED → callback → Agent announces
```

**Missing components for full gated flow:**
1. `/tool-progress` HTTP endpoint in relay
2. `cancelRequests` state management
3. Response handling to continue/cancel
4. Integration between callback response and agent voice

---

## Recommendations

### Option A: Current Flow is Sufficient (MVP)

The existing prompt-based confirmation provides:
- User confirmation before tool execution
- Agent verbal confirmation of details
- Single execution path (no cancellation mid-flight)

**Pros:** Simple, working today
**Cons:** No mid-execution cancellation, no webhook-level checkpoint

### Option B: Implement Full Gated Flow

Add to relay server:
1. HTTP endpoint `/tool-progress` to receive n8n callbacks
2. State management for `cancelRequests`
3. OpenAI notification when gate callbacks arrive
4. Response logic for continue/cancel

**Pros:** Full control, true human-in-the-loop at n8n level
**Cons:** Significant relay server changes

---

## Current Behavior vs Planned Behavior

### Current (Working)

```
User: "Send email to john@example.com"
Agent: "I'll send an email to john@example.com. Is that correct?"
User: "Yes"
Agent: [calls send_email tool via n8n]
n8n: [executes Gmail, sends callbacks to nowhere]
Agent: "Email sent successfully!"
```

### Planned (Not Yet Implemented)

```
User: "Send email to john@example.com"
Agent: "I'll send an email to john@example.com. Is that correct?"
User: "Yes"
Agent: [calls n8n workflow]
n8n Gate 1: [callback to relay] "PREPARING..."
Relay: [checks cancel] → returns {continue: true}
n8n Gate 2: [callback to relay] "READY_TO_SEND"
Relay: → Agent: "Email is ready to send. Confirm?"
User: "Send it"
Relay: → returns {continue: true}
n8n Gate 3: [Gmail sends]
n8n Gate 4: [callback to relay] "COMPLETED"
Agent: "Email sent successfully!"
```

---

## Files Referenced

| File | Purpose |
|------|---------|
| `relay-server/index-enhanced.js:534-575` | OpenAI session instructions |
| `relay-server/index-enhanced.js:607-726` | ConversationContext class |
| `relay-server/index-enhanced.js:99-290` | SessionCache class |
| `relay-server/index-enhanced.js:1743-1759` | HTTP server (no callback endpoint) |
| `n8n-workflows/voice-tool-send-gmail.json` | Gated Gmail workflow |
| `.claude/plans/dynamic-finding-axolotl.md` | Full architecture plan |

---

*Analysis generated for Enterprise Voice Agent POC*
