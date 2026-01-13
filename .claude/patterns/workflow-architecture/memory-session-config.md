# Pattern: Memory Buffer Session Configuration for Non-Chat Triggers

> **Priority**: MEDIUM
>
> **Workflow**: AI Carousel Generator (ID: 8bhcEHkbbvnhdHBh)
>
> **Date**: 2025-12-04

---

## Anti-Pattern: Memory Buffer Window Node Missing Session ID Configuration for Non-Chat Triggers

### What Happened

When implementing the AI Agent with memory for carousel prompt generation, the `memoryBufferWindow` node was configured with only `contextWindowLength: 5`. At runtime, the node failed with:

```
Error: No session ID found
```

The execution showed:
```json
"parameters": {
  "sessionIdType": "fromInput",
  "sessionKey": "={{ $json.sessionId }}",
  "contextWindowLength": 5
}
```

The node defaulted to `sessionIdType: "fromInput"` which expects a `sessionId` from a Chat Trigger node. Since the workflow uses a **Form Trigger** (not Chat Trigger), no sessionId was provided in the input data.

### Impact

- 5 consecutive workflow executions failed at the "Simple Memory" node
- AI Agent couldn't process any carousel generation requests
- Workflow created folders in Google Drive but couldn't proceed to prompt generation
- Required debugging to identify the session ID requirement

### Why It Failed

1. **Trigger type mismatch**: Form Trigger doesn't provide sessionId like Chat Trigger does
2. **Default behavior assumption**: `memoryBufferWindow` v1.2+ defaults to `sessionIdType: "fromInput"`
3. **Working templates use Chat Trigger**: Most memory buffer examples are for chat workflows, not form-triggered workflows
4. **Parameter visibility**: The `sessionIdType` parameter isn't visible unless explicitly set, leading to assumption that `contextWindowLength` alone is sufficient

---

## Positive Pattern: Configure Custom Session Key for Non-Chat Trigger Workflows

### Solution

When using `memoryBufferWindow` with triggers other than Chat Trigger, explicitly set `sessionIdType: "customKey"` with a unique session key expression.

### Implementation

```json
{
  "name": "Simple Memory",
  "type": "@n8n/n8n-nodes-langchain.memoryBufferWindow",
  "typeVersion": 1.3,
  "parameters": {
    "sessionIdType": "customKey",
    "sessionKey": "={{ 'carousel_' + $('Set User Input').item.json.carousel_id }}",
    "contextWindowLength": 5
  }
}
```

**Key Configuration:**
- `sessionIdType: "customKey"` - Override default "fromInput" behavior
- `sessionKey` - Expression that generates a unique identifier per workflow execution
- Use workflow-specific data (carousel_id, timestamp, user_id, etc.) for session isolation

### Result

- Workflow now proceeds past Simple Memory node
- AI Agent receives proper memory context
- Each carousel generation has isolated memory (no cross-contamination)
- Pattern documented for future non-chat workflows

---

## Memory Buffer Window Configuration by Trigger Type

| Trigger Type | sessionIdType | sessionKey Configuration |
|--------------|---------------|-------------------------|
| Chat Trigger | `fromInput` (default) | Not needed - uses built-in sessionId |
| Form Trigger | `customKey` | `={{ 'form_' + $json.unique_field }}` |
| Webhook Trigger | `customKey` | `={{ 'webhook_' + $json.request_id }}` |
| Schedule Trigger | `customKey` | `={{ 'schedule_' + $now.toISO() }}` |
| Manual Trigger | `customKey` | `={{ 'manual_' + $executionId }}` |

---

## Decision Flow

```
Using memoryBufferWindow node?
├─ Is trigger type Chat Trigger?
│   ├─ YES: Use default (sessionIdType: "fromInput")
│   └─ NO: Set sessionIdType: "customKey"
│       └─ Create unique sessionKey expression using:
│           - Workflow-specific ID (carousel_id, order_id, etc.)
│           - Timestamp ($now)
│           - Execution ID ($executionId)
│           - Unique input field ($json.email, $json.user_id, etc.)
└─ Consider if memory is even needed (single-shot vs conversational)
```

---

## Key Learnings

- **Trigger type affects sub-node behavior** - Memory nodes expect Chat Trigger's sessionId by default
- **Empty parameters ≠ safe defaults** - `{}` parameters can hide problematic defaults
- **Working templates may not match use case** - Most memory examples use Chat Trigger
- **Session isolation matters** - Each workflow execution should have unique sessionKey to prevent memory leakage
- **Error messages are helpful** - "No session ID found" clearly indicates the issue

---

**Date**: 2025-12-04
**Source Pattern**: agents-evolution.md - Workflow Architecture Patterns
