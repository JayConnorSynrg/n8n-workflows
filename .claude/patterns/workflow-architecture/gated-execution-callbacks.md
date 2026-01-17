# Pattern: Gated Execution with Callback-Based Flow Control

> **Priority**: HIGH
>
> **Workflow**: Voice Tool: Send Gmail (ID: kBuTRrXTJF1EEBEs)
>
> **Date**: 2026-01-14

---

## Pattern Overview

Gated execution enables interruptible tool calls where:
1. External system (relay server) receives progress updates at each gate
2. User can cancel at any checkpoint before irreversible action
3. Workflow waits for confirmation before proceeding
4. Full audit trail tracks state transitions

---

## Architecture: 3-Gate Email Workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    GATED EXECUTION FLOW                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Webhook: POST /execute-gmail                                       │
│       │                                                             │
│       ▼                                                             │
│  Code: Generate tool_call_id                                        │
│       │                                                             │
│       ▼                                                             │
│  PostgreSQL: INSERT (status: EXECUTING)                             │
│       │                                                             │
│       ▼                                                             │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ GATE 1: Progress Callback                                   │   │
│  │                                                             │   │
│  │ HTTP POST → callback_url                                    │   │
│  │ { status: "PREPARING", gate: 1, cancellable: true }         │   │
│  │                                                             │   │
│  │ Response: { cancel: true/false }                            │   │
│  └─────────────────────────────────────────────────────────────┘   │
│       │                                                             │
│       ▼                                                             │
│  IF: Check Cancel (Gate 1)                                          │
│       │                                                             │
│       ├─ TRUE (cancel) → PostgreSQL: CANCELLED → Callback → End    │
│       │                                                             │
│       └─ FALSE (continue)                                          │
│             │                                                       │
│             ▼                                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ GATE 2: Confirmation Checkpoint                             │   │
│  │                                                             │   │
│  │ HTTP POST → callback_url                                    │   │
│  │ { status: "READY_TO_SEND", gate: 2,                         │   │
│  │   requires_confirmation: true, cancellable: true }          │   │
│  │                                                             │   │
│  │ Agent: "Email ready to send. Confirm?"                      │   │
│  │ Response: { cancel: true/false }                            │   │
│  └─────────────────────────────────────────────────────────────┘   │
│       │                                                             │
│       ▼                                                             │
│  IF: Check Cancel (Gate 2)                                          │
│       │                                                             │
│       ├─ TRUE (cancel) → PostgreSQL: CANCELLED → Callback → End    │
│       │                                                             │
│       └─ FALSE (continue)                                          │
│             │                                                       │
│             ▼                                                       │
│  Gmail: Send Email  ← IRREVERSIBLE ACTION                          │
│       │                                                             │
│       ▼                                                             │
│  Code: Format Result                                                │
│       │                                                             │
│       ▼                                                             │
│  PostgreSQL: UPDATE (status: COMPLETED)                             │
│       │                                                             │
│       ▼                                                             │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ GATE 3: Completion Callback                                 │   │
│  │                                                             │   │
│  │ HTTP POST → callback_url                                    │   │
│  │ { status: "COMPLETED", gate: 3,                             │   │
│  │   result: {...}, voice_response: "Email sent..." }          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│       │                                                             │
│       ▼                                                             │
│  Respond to Webhook: Success                                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Details

### Gate Callback Node Configuration

```json
{
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 4.3,
  "parameters": {
    "method": "POST",
    "url": "={{ $json.callback_url }}",
    "sendHeaders": true,
    "headerParameters": {
      "parameters": [
        { "name": "Content-Type", "value": "application/json" }
      ]
    },
    "sendBody": true,
    "specifyBody": "json",
    "jsonBody": "={{ JSON.stringify({ status: 'PREPARING', gate: 1, cancellable: true, tool_call_id: $('Code: Generate ID').first().json.tool_call_id, intent_id: $('Code: Generate ID').first().json.intent_id, message: 'Preparing to send email...' }) }}",
    "options": {
      "timeout": 35000
    }
  },
  "retryOnFail": true,
  "maxTries": 3,
  "waitBetweenTries": 1000
}
```

### IF Node for Cancel Check

```json
{
  "type": "n8n-nodes-base.if",
  "typeVersion": 2.3,
  "parameters": {
    "conditions": {
      "options": {
        "version": 2,
        "leftValue": "",
        "caseSensitive": true,
        "typeValidation": "strict"
      },
      "combinator": "and",
      "conditions": [
        {
          "leftValue": "={{ $json.cancel }}",
          "operator": {
            "operation": "equals",
            "type": "boolean"
          },
          "rightValue": true,
          "id": "condition-check-cancel"
        }
      ]
    }
  },
  "onError": "continueErrorOutput"
}
```

---

## Anti-Pattern: Connection Bypassing IF Nodes

### What Happened

When copying/modifying connections, the IF node was accidentally bypassed:

```json
// WRONG - Gate 1 connects directly to Gate 2, bypassing IF check
"HTTP Request: Gate 1": {
  "main": [[{"node": "HTTP Request: Gate 2", "type": "main", "index": 0}]]
}
```

### Impact

- Cancel checks never evaluated
- User cancellation requests ignored
- Workflow proceeded to irreversible action without consent

### Correct Connection Routing

```json
// CORRECT - Gate 1 routes through IF check
"HTTP Request: Gate 1": {
  "main": [[{"node": "IF: Check Cancel (Gate 1)", "type": "main", "index": 0}]]
},
"IF: Check Cancel (Gate 1)": {
  "main": [
    [{"node": "Postgres: UPDATE CANCELLED", "type": "main", "index": 0}],  // TRUE = cancel
    [{"node": "HTTP Request: Gate 2", "type": "main", "index": 0}]         // FALSE = continue
  ]
}
```

### IF Node Branch Semantics

| Branch Index | Meaning | Action |
|--------------|---------|--------|
| 0 (first array) | TRUE - condition matched | Cancel flow |
| 1 (second array) | FALSE - condition not matched | Continue flow |

---

## Callback Payload Structure

### Gate 1: Progress (Cancellable)
```json
{
  "status": "PREPARING",
  "gate": 1,
  "cancellable": true,
  "tool_call_id": "tc_xxx",
  "intent_id": "intent_xxx",
  "message": "Preparing to send email..."
}
```

### Gate 2: Confirmation Required
```json
{
  "status": "READY_TO_SEND",
  "gate": 2,
  "requires_confirmation": true,
  "cancellable": true,
  "tool_call_id": "tc_xxx",
  "intent_id": "intent_xxx",
  "message": "Email is ready to send. Confirm to proceed."
}
```

### Gate 3: Completion
```json
{
  "status": "COMPLETED",
  "gate": 3,
  "tool_call_id": "tc_xxx",
  "intent_id": "intent_xxx",
  "result": { "messageId": "msg_xxx", "threadId": "thread_xxx" },
  "voice_response": "Email sent successfully to recipient@example.com",
  "execution_time_ms": 1850
}
```

---

## Gated Execution Checklist

- [ ] Each gate sends HTTP callback with status and cancellable flag
- [ ] IF node follows each gate to check cancel response
- [ ] IF node TRUE branch (index 0) goes to cancel flow
- [ ] IF node FALSE branch (index 1) continues to next gate
- [ ] Irreversible action (Gmail send) only after all gates pass
- [ ] PostgreSQL records status at each transition
- [ ] Final gate sends completion with voice_response

---

## Database Status Flow

```
EXECUTING → (Gate 1 cancel) → CANCELLED
EXECUTING → (Gate 2 cancel) → CANCELLED
EXECUTING → (Gate 3 complete) → COMPLETED
```

---

## Relay Server Callback Handler

```javascript
// Express endpoint for gate callbacks
app.post('/tool-progress', async (req, res) => {
  const { intent_id, tool_call_id, status, gate, cancellable, message } = req.body;

  // Check if user requested cancellation
  if (cancellable && cancelRequests.has(intent_id)) {
    cancelRequests.delete(intent_id);
    return res.json({ cancel: true });
  }

  // For Gate 2, wait for user confirmation
  if (gate === 2 && req.body.requires_confirmation) {
    // Agent speaks and waits for user response
    // Return cancel: true/false based on user's decision
  }

  // Continue execution
  return res.json({ cancel: false });
});
```

---

## Key Learnings

- **Gates provide natural checkpoints** - Each gate is an opportunity to cancel
- **IF nodes must not be bypassed** - Verify connections route through conditional checks
- **Branch index 0 = TRUE** - Counter-intuitive but consistent in n8n IF nodes
- **Timeout tuning matters** - Gate 2 needs longer timeout (35s) for user confirmation
- **Voice response at completion** - Gate 3 payload includes text for TTS

---

**Date**: 2026-01-14
**Source Pattern**: Voice Agent POC - Gated Execution Implementation
