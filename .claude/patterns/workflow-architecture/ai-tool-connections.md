# Pattern: AI Tool Connections for Langchain Agents

> **Priority**: CRITICAL
>
> **Category**: Workflow Architecture
>
> **Date**: 2025-12-28
>
> **Verified**: YES - Confirmed in Teams Voice Bot Orchestrator

---

## Overview

When connecting Langchain AI nodes (tools, memory, language models) to an Agent node, the connection **port type** must match the node category, NOT use the default `main` port.

---

## The Problem

Using `main` port type for AI tool connections causes the tool to be **incorrectly wired** to the agent. The agent will not recognize the tool, and the workflow will fail validation or runtime.

---

## Anti-Pattern (WRONG)

```json
"TTS Tool": {
  "main": [                    // ❌ WRONG - using main port
    [
      {
        "node": "Orchestrator Agent",
        "type": "main",        // ❌ WRONG - using main type
        "index": 0
      }
    ]
  ]
}
```

**Result:** Tool not connected to agent. Agent cannot call the tool.

---

## Correct Pattern

```json
"TTS Tool": {
  "ai_tool": [                 // ✅ CORRECT - ai_tool port
    [
      {
        "node": "Orchestrator Agent",
        "type": "ai_tool",     // ✅ CORRECT - ai_tool type
        "index": 0
      }
    ]
  ]
}
```

---

## Connection Type Matrix

| Node Type | Node Category | Source Port | Target Port |
|-----------|---------------|-------------|-------------|
| `@n8n/n8n-nodes-langchain.toolWorkflow` | AI Tool | `ai_tool` | `ai_tool` |
| `@n8n/n8n-nodes-langchain.toolThink` | AI Tool | `ai_tool` | `ai_tool` |
| `@n8n/n8n-nodes-langchain.toolCode` | AI Tool | `ai_tool` | `ai_tool` |
| `n8n-nodes-base.gmailTool` | AI Tool | `ai_tool` | `ai_tool` |
| `@n8n/n8n-nodes-langchain.lmChatOpenRouter` | Language Model | `ai_languageModel` | `ai_languageModel` |
| `@n8n/n8n-nodes-langchain.lmChatOpenAi` | Language Model | `ai_languageModel` | `ai_languageModel` |
| `@n8n/n8n-nodes-langchain.memoryPostgresChat` | Memory | `ai_memory` | `ai_memory` |
| `@n8n/n8n-nodes-langchain.memoryBufferWindow` | Memory | `ai_memory` | `ai_memory` |
| `n8n-nodes-base.*` (regular nodes) | Main Flow | `main` | `main` |

---

## Full Workflow Connections Example

```json
{
  "connections": {
    // Regular flow connections use "main"
    "Webhook": {
      "main": [[{"node": "Process Data", "type": "main", "index": 0}]]
    },

    // AI Tool connections use "ai_tool"
    "Gmail Agent Tool": {
      "ai_tool": [[{"node": "Agent", "type": "ai_tool", "index": 0}]]
    },
    "TTS Tool": {
      "ai_tool": [[{"node": "Agent", "type": "ai_tool", "index": 0}]]
    },
    "Think Tool": {
      "ai_tool": [[{"node": "Agent", "type": "ai_tool", "index": 0}]]
    },

    // Language Model uses "ai_languageModel"
    "OpenRouter Chat Model": {
      "ai_languageModel": [[{"node": "Agent", "type": "ai_languageModel", "index": 0}]]
    },

    // Memory uses "ai_memory"
    "Postgres Chat Memory": {
      "ai_memory": [[{"node": "Agent", "type": "ai_memory", "index": 0}]]
    },

    // Agent output goes to regular flow via "main"
    "Agent": {
      "main": [[{"node": "Process Output", "type": "main", "index": 0}]]
    }
  }
}
```

---

## How to Identify Port Types

**Rule:** The port type matches the node's Langchain category prefix:

| Node Package | Port Type |
|--------------|-----------|
| `*Tool*` or `*tool*` | `ai_tool` |
| `lmChat*` or `*LanguageModel*` | `ai_languageModel` |
| `memory*` or `*Memory*` | `ai_memory` |
| `output*` | `ai_outputParser` |
| Regular `n8n-nodes-base.*` | `main` |

---

## MCP API Considerations

When using `n8n_update_partial_workflow` with `addConnection`:

```javascript
// This may NOT work correctly for AI nodes:
{
  "type": "addConnection",
  "source": "TTS Tool",
  "target": "Agent",
  "sourcePort": "ai_tool",   // May be ignored
  "targetPort": "ai_tool"    // May be ignored
}
```

**Recommendation:** Use `n8n_update_full_workflow` with complete connection objects for AI nodes to ensure correct port types.

---

## Troubleshooting

### Symptom: Tool not appearing in agent's available tools
**Cause:** Connection using `main` port instead of `ai_tool`
**Fix:** Update connection to use `ai_tool` port type

### Symptom: "Disconnected nodes detected" validation error
**Cause:** Node has wrong connection type and isn't recognized as connected
**Fix:** Ensure both source port AND target type use correct AI port type

### Symptom: Agent ignores tool calls
**Cause:** Tool connected via `main` instead of `ai_tool`
**Fix:** Rewire using correct port type in full workflow update

---

## Related Patterns

- [Hybrid Logging Architecture](./hybrid-logging-architecture.md) - Uses AI tools for analysis
- [Gmail Tool Configuration](../api-integration/gmail-tool-config.md) - Gmail as AI tool

---

**Date**: 2025-12-28
**Source Workflow**: Teams Voice Bot v3.0 - Agent Orchestrator (d3CxEaYk5mkC8sLo)
**Verified By**: Working implementation with Gmail Agent Tool, TTS Tool, Think Tool
