# Pattern: Gmail Tool (gmailTool) Configuration

> **Priority**: HIGH
>
> **Workflow**: Gmail Agent Sub-Workflow (ID: kL0AP3CkRby6OmVb)
>
> **Date**: 2025-12-28
>
> **Verified**: YES - User confirmed fix works

---

## Anti-Pattern: Gmail Tool Without resource/operation Parameters

### What Happened

When implementing the Gmail Tool node (`n8n-nodes-base.gmailTool`) for AI Agent integration, the node was configured with only the visible parameters (`sendTo`, `subject`, `message`) without the required `resource` and `operation` parameters.

```json
{
  "parameters": {
    "sendTo": "={{ $json.to }}",
    "subject": "={{ $json.subject }}",
    "message": "={{ $json.body }}",
    "options": {}
  },
  "type": "n8n-nodes-base.gmailTool",
  "typeVersion": 2.2
}
```

### Impact

- Workflow validation failed with: `"Invalid value for 'operation'. Must be one of: addLabels, delete, get, getAll, markAsRead, markAsUnread, removeLabels, reply, send, sendAndWait"`
- AI Agent could not invoke the Gmail tool
- Email sending functionality completely broken

### Why It Failed

- The `resource` and `operation` parameters are **REQUIRED** even though they have schema defaults
- MCP schema shows `resource` default is "message" but it must be explicitly set
- The `operation` parameter has NO visible default - must be explicitly set to "send"
- Without these parameters, n8n cannot determine which API operation to execute
- The conditional visibility of `sendTo`, `subject`, `message` depends on `resource: "message"` AND `operation: "send"` being set

---

## Positive Pattern: Gmail Tool with Explicit resource/operation

### Solution

Always explicitly set `resource` and `operation` parameters when configuring Gmail Tool nodes.

### Correct Configuration

```json
{
  "parameters": {
    "resource": "message",
    "operation": "send",
    "sendTo": "={{ $json.to }}",
    "subject": "={{ $json.subject }}",
    "message": "={{ $json.body }}",
    "options": {}
  },
  "type": "n8n-nodes-base.gmailTool",
  "typeVersion": 2.2
}
```

### Key Rules

| Parameter | Required | Value for Sending Email |
|-----------|----------|------------------------|
| `resource` | YES | `"message"` |
| `operation` | YES | `"send"` |
| `sendTo` | YES | Email address(es) |
| `subject` | YES | Email subject |
| `message` | YES | Email body |

### Available Operations by Resource

| Resource | Operations |
|----------|------------|
| `message` | send, reply, get, getAll, delete, markAsRead, markAsUnread, addLabels, removeLabels, sendAndWait |
| `draft` | create, delete, get, getAll |
| `label` | create, delete, get, getAll |
| `thread` | get, getAll, delete, addLabels, removeLabels, reply, trash, untrash |

---

## Tool Variant Note

The `gmailTool` node is the **AI Tool variant** of the regular Gmail node:

- **Base node**: `n8n-nodes-base.gmail` - For standalone use in workflows
- **Tool variant**: `n8n-nodes-base.gmailTool` - For AI Agent integration via `ai_tool` connection

Both require the same `resource`/`operation` structure.

---

## Validation

When validating Gmail Tool nodes, check:

1. `resource` parameter is explicitly set
2. `operation` parameter is explicitly set
3. Required parameters for that resource/operation combination are present
4. Node connects to AI Agent via `ai_tool` connection type

---

## Decision Flow

```
Implementing Gmail Tool?
├─ Set resource: "message" (for email operations)
├─ Set operation: "send" (for sending)
├─ Add required fields (sendTo, subject, message)
├─ Configure options if needed
└─ Connect to AI Agent via ai_tool
```

---

**Date**: 2025-12-28
**Source Workflow**: Gmail Agent Sub-Workflow (kL0AP3CkRby6OmVb)
**Verified By**: User confirmation after fix applied
