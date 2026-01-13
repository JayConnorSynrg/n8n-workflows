# Memory Buffer Window Node Reference

> **Node Type**: `@n8n/n8n-nodes-langchain.memoryBufferWindow`
> **Latest TypeVersion**: 1.3
> **Last Verified**: 2025-12-27
> **Source**: MCP `get_node` with full detail

---

## Overview

Simple conversation memory for AI agents. Stores previous messages in a window buffer for context retention.

**No Credentials Required** - Stores in n8n workflow execution context

---

## Session ID Configuration

### v1.3 (Current)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sessionIdType` | options | `fromInput` | `fromInput` or `customKey` |
| `sessionKey` | string | `={{ $json.sessionId }}` | Session identifier expression |
| `contextWindowLength` | number | 5 | Messages to retain |

---

## Reference Configuration

### From Chat Trigger Session
```json
{
  "name": "Memory - Simple Memory",
  "type": "@n8n/n8n-nodes-langchain.memoryBufferWindow",
  "typeVersion": 1.3,
  "parameters": {
    "sessionIdType": "fromInput",
    "sessionKey": "={{ $json.sessionId }}",
    "contextWindowLength": 10
  }
}
```

### Custom Session ID
```json
{
  "parameters": {
    "sessionIdType": "customKey",
    "sessionKey": "={{ $json.userId }}_conversation",
    "contextWindowLength": 5
  }
}
```

---

## Connection

- **Output Type**: `ai_memory`
- **Connect To**: AI Agent node
- **Required**: Must be connected to AI agent

---

## Critical Rules

1. **TypeVersion 1.3 is current** - Uses `sessionIdType` selector
2. **AI Agent Required** - Must connect to AI agent node
3. **Expression Syntax** - Session ID accepts full n8n expressions (prefix with `=`)
4. **Buffer Behavior** - `contextWindowLength: 5` = keep last 5 message exchanges
5. **No Credentials** - Memory stored locally in execution context

---

## Related Patterns

- `.claude/patterns/workflow-architecture/memory-session-config.md`
