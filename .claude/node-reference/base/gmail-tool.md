# Gmail Tool Node Reference

> **Node Type**: `n8n-nodes-base.gmailTool`
> **Latest TypeVersion**: 2.2
> **Last Verified**: 2025-12-28
> **Source**: MCP `get_node` with full detail
> **Anti-Memory Protocol**: APPLIES - REQUIRES explicit resource/operation

---

## CRITICAL: Configuration Requirements

**Gmail Tool REQUIRES explicit `resource` and `operation` parameters.**

Unlike the regular Gmail node which defaults, the Gmail Tool used with AI Agents must have these explicitly set or it will fail silently.

---

## Overview

The Gmail Tool node provides Gmail integration for AI Agents. It allows agents to send, read, and manage emails autonomously.

**Connection Type**: `ai_tool` (connects to AI Agent's tool input)

---

## Correct Configuration - COPY EXACTLY

### Send Email Tool
```json
{
  "name": "Gmail",
  "type": "n8n-nodes-base.gmailTool",
  "typeVersion": 2.2,
  "parameters": {
    "resource": "message",
    "operation": "send",
    "sendTo": "={{ /*provide recipient*/ }}",
    "subject": "={{ /*provide subject*/ }}",
    "emailType": "text",
    "message": "={{ /*provide message*/ }}"
  },
  "credentials": {
    "gmailOAuth2": {
      "id": "your-credential-id",
      "name": "Gmail OAuth2"
    }
  }
}
```

### Get Emails Tool
```json
{
  "name": "Gmail - Read",
  "type": "n8n-nodes-base.gmailTool",
  "typeVersion": 2.2,
  "parameters": {
    "resource": "message",
    "operation": "getAll",
    "returnAll": false,
    "limit": 10,
    "filters": {
      "includeSpamTrash": false,
      "labelIds": ["INBOX"]
    }
  },
  "credentials": {
    "gmailOAuth2": {
      "id": "your-credential-id",
      "name": "Gmail OAuth2"
    }
  }
}
```

### Reply Tool
```json
{
  "name": "Gmail - Reply",
  "type": "n8n-nodes-base.gmailTool",
  "typeVersion": 2.2,
  "parameters": {
    "resource": "message",
    "operation": "reply",
    "messageId": {
      "__rl": true,
      "value": "={{ /*provide messageId*/ }}",
      "mode": "id"
    },
    "message": "={{ /*provide reply message*/ }}"
  },
  "credentials": {
    "gmailOAuth2": {
      "id": "your-credential-id",
      "name": "Gmail OAuth2"
    }
  }
}
```

---

## Resources & Operations

Same as regular Gmail node:

### Message Resource
| Operation | Description |
|-----------|-------------|
| `send` | Send an email |
| `reply` | Reply to an email |
| `get` | Get a single email |
| `getAll` | Get multiple emails |
| `delete` | Delete an email |
| `markAsRead` | Mark email as read |
| `markAsUnread` | Mark email as unread |
| `addLabels` | Add labels to email |
| `removeLabels` | Remove labels from email |

### Draft Resource
| Operation | Description |
|-----------|-------------|
| `create` | Create a draft |
| `get` | Get a draft |
| `getAll` | Get all drafts |
| `delete` | Delete a draft |

### Label Resource
| Operation | Description |
|-----------|-------------|
| `create` | Create a label |
| `get` | Get a label |
| `getAll` | Get all labels |
| `delete` | Delete a label |

### Thread Resource
| Operation | Description |
|-----------|-------------|
| `get` | Get a thread |
| `getAll` | Get all threads |
| `delete` | Delete a thread |
| `reply` | Reply to a thread |
| `trash` | Trash a thread |
| `untrash` | Untrash a thread |
| `addLabels` | Add labels to thread |
| `removeLabels` | Remove labels from thread |

---

## Anti-Patterns (AVOID THESE)

### 1. Missing Resource Parameter
```json
// WRONG - Will fail silently
{
  "parameters": {
    "operation": "send",
    "sendTo": "recipient@example.com"
  }
}

// CORRECT - Explicit resource
{
  "parameters": {
    "resource": "message",
    "operation": "send",
    "sendTo": "recipient@example.com"
  }
}
```

### 2. Missing Operation Parameter
```json
// WRONG - No default operation
{
  "parameters": {
    "resource": "message",
    "sendTo": "recipient@example.com"
  }
}

// CORRECT - Explicit operation
{
  "parameters": {
    "resource": "message",
    "operation": "send",
    "sendTo": "recipient@example.com"
  }
}
```

---

## Connection to AI Agent

Gmail Tool connects to AI Agent's tool input:

```json
{
  "connections": {
    "Gmail": {
      "ai_tool": [
        [
          {
            "node": "AI Agent",
            "type": "ai_tool",
            "index": 0
          }
        ]
      ]
    }
  }
}
```

---

## AI Agent Tool Usage

When the AI Agent uses this tool, it will:
1. Receive the tool's capabilities based on configured resource/operation
2. Execute email actions autonomously based on conversation context
3. Return results to continue the conversation

### Multiple Gmail Tools Pattern

For comprehensive email capabilities, attach multiple Gmail Tool nodes:

```
AI Agent
├── Gmail - Send (resource: message, operation: send)
├── Gmail - Read (resource: message, operation: getAll)
├── Gmail - Reply (resource: message, operation: reply)
└── Gmail - Search (resource: message, operation: getAll with filters)
```

---

## Reference Workflow

Working example: `kL0AP3CkRby6OmVb`

---

## Validation Checklist

- [ ] Using typeVersion 2.2
- [ ] `resource` parameter explicitly set
- [ ] `operation` parameter explicitly set
- [ ] Credentials configured
- [ ] Connected to AI Agent via `ai_tool` connection type
- [ ] MessageId uses ResourceLocator format where required

---

## Related Patterns

- `.claude/patterns/api-integration/gmail-tool-config.md` - Full pattern documentation
- `.claude/node-reference/base/gmail.md` - Regular Gmail node reference
