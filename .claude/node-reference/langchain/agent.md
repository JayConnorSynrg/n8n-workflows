# AI Agent Node Reference

> **Node Type**: `@n8n/n8n-nodes-langchain.agent`
> **Latest TypeVersion**: 3.1
> **Verified Working Version**: 3
> **Last Verified**: 2025-12-28
> **Source**: MCP `get_node` + reference workflow verification

---

## Overview

The AI Agent node generates action plans and executes them using external tools. Works as both a standalone node and as a tool within other AI workflows.

**AI Tool Capable**: Yes (requires `N8N_COMMUNITY_PACKAGES_ALLOW_TOOL_USAGE=true`)

---

## Version Guidance

| Version | Status | Notes |
|---------|--------|-------|
| 3.1 | Latest | `guardrails` promptType removed |
| 3 | Verified Working | Recommended for production |
| 2.x | Legacy | Not compatible with GPT-4o |

**Recommendation**: Use `typeVersion: 3` with minimal config for proven stability, or `3.1` for latest features.

---

## Connection Types

| Connection Type | Purpose | Required |
|-----------------|---------|----------|
| `ai_languageModel` | Primary LLM (OpenAI, Anthropic, etc.) | **Yes** |
| `ai_tool` | Tool integration (HTTP, Code, Workflow, etc.) | Optional |
| `ai_memory` | Conversation history via Memory node | Optional |
| `ai_outputParser` | Structured output parsing | Optional |

### Connection JSON
```json
{
  "connections": {
    "Chat Trigger": {
      "main": [
        [{ "node": "AI Agent", "type": "main", "index": 0 }]
      ]
    },
    "OpenAI Chat Model": {
      "ai_languageModel": [
        [{ "node": "AI Agent", "type": "ai_languageModel", "index": 0 }]
      ]
    },
    "Memory Buffer": {
      "ai_memory": [
        [{ "node": "AI Agent", "type": "ai_memory", "index": 0 }]
      ]
    },
    "Tool Workflow": {
      "ai_tool": [
        [{ "node": "AI Agent", "type": "ai_tool", "index": 0 }]
      ]
    }
  }
}
```

---

## Core Parameters

### Prompt Configuration

| Parameter | Type | Options | Default | Description |
|-----------|------|---------|---------|-------------|
| `promptType` | options | `auto`, `define` | `auto` | How to handle agent prompt |
| `text` | string | - | - | Input text (when `promptType: define`) |
| `hasOutputParser` | boolean | - | `false` | Enable structured output |

### Options Collection

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `systemMessage` | string | "You are a helpful assistant" | Initial system prompt |
| `maxIterations` | number | 10 | Max agent cycles before halt |
| `returnIntermediateSteps` | boolean | false | Include reasoning steps in output |
| `enableStreaming` | boolean | true | Stream response chunks |
| `passthroughBinaryImages` | boolean | true | Auto-pass binary images to LLM |

---

## Reference Configurations

### Minimal Configuration (Recommended)
```json
{
  "name": "AI Agent",
  "type": "@n8n/n8n-nodes-langchain.agent",
  "typeVersion": 3,
  "position": [600, 400],
  "parameters": {
    "options": {}
  }
}
```

**Why minimal works**: The agent receives input from the connected Chat Trigger and uses defaults for everything else.

### With Custom System Message
```json
{
  "name": "AI Agent",
  "type": "@n8n/n8n-nodes-langchain.agent",
  "typeVersion": 3.1,
  "parameters": {
    "options": {
      "systemMessage": "You are an expert assistant specializing in data analysis.",
      "maxIterations": 15
    }
  }
}
```

### With Output Parser
```json
{
  "name": "AI Agent",
  "type": "@n8n/n8n-nodes-langchain.agent",
  "typeVersion": 3.1,
  "parameters": {
    "hasOutputParser": true,
    "options": {}
  }
}
```

Requires `ai_outputParser` connection to Structured Output Parser node.

---

## OpenAI Integration

### Full Agent Setup with OpenAI

```json
{
  "nodes": [
    {
      "name": "Chat Trigger",
      "type": "@n8n/n8n-nodes-langchain.chatTrigger",
      "typeVersion": 1.1,
      "position": [200, 400],
      "webhookId": "unique-id",
      "parameters": {}
    },
    {
      "name": "AI Agent",
      "type": "@n8n/n8n-nodes-langchain.agent",
      "typeVersion": 3,
      "position": [600, 400],
      "parameters": {
        "options": {}
      }
    },
    {
      "name": "OpenAI Chat Model",
      "type": "@n8n/n8n-nodes-langchain.lmChatOpenAi",
      "typeVersion": 1.3,
      "position": [400, 600],
      "parameters": {
        "model": {
          "mode": "list",
          "value": "gpt-4o"
        },
        "options": {
          "temperature": 0.7
        }
      },
      "credentials": {
        "openAiApi": {
          "id": "credential-id",
          "name": "OpenAI API"
        }
      }
    },
    {
      "name": "Window Buffer Memory",
      "type": "@n8n/n8n-nodes-langchain.memoryBufferWindow",
      "typeVersion": 1.3,
      "position": [400, 200],
      "parameters": {
        "sessionIdType": "fromInput",
        "sessionKey": "={{ $json.sessionId }}"
      }
    }
  ],
  "connections": {
    "Chat Trigger": {
      "main": [
        [{ "node": "AI Agent", "type": "main", "index": 0 }]
      ]
    },
    "OpenAI Chat Model": {
      "ai_languageModel": [
        [{ "node": "AI Agent", "type": "ai_languageModel", "index": 0 }]
      ]
    },
    "Window Buffer Memory": {
      "ai_memory": [
        [{ "node": "AI Agent", "type": "ai_memory", "index": 0 }]
      ]
    }
  }
}
```

### Agent with OpenAI Tools

Connect multiple tools to the agent:

```json
{
  "nodes": [
    {
      "name": "AI Agent",
      "type": "@n8n/n8n-nodes-langchain.agent",
      "typeVersion": 3,
      "parameters": { "options": {} }
    },
    {
      "name": "HTTP Request Tool",
      "type": "@n8n/n8n-nodes-langchain.toolHttpRequest",
      "typeVersion": 1.1,
      "parameters": {
        "name": "fetch_data",
        "description": "Fetches data from an API"
      }
    },
    {
      "name": "Workflow Tool",
      "type": "@n8n/n8n-nodes-langchain.toolWorkflow",
      "typeVersion": 2.2,
      "parameters": {
        "name": "process_document",
        "description": "Processes a document",
        "workflowId": {
          "__rl": true,
          "value": "workflow-id",
          "mode": "list"
        }
      }
    }
  ],
  "connections": {
    "HTTP Request Tool": {
      "ai_tool": [
        [{ "node": "AI Agent", "type": "ai_tool", "index": 0 }]
      ]
    },
    "Workflow Tool": {
      "ai_tool": [
        [{ "node": "AI Agent", "type": "ai_tool", "index": 0 }]
      ]
    }
  }
}
```

### Agent with Reasoning Model (o1/o3)

```json
{
  "nodes": [
    {
      "name": "OpenAI Reasoning",
      "type": "@n8n/n8n-nodes-langchain.lmChatOpenAi",
      "typeVersion": 1.3,
      "parameters": {
        "model": {
          "mode": "list",
          "value": "o1"
        },
        "options": {
          "reasoningEffort": "high"
        }
      }
    },
    {
      "name": "AI Agent",
      "type": "@n8n/n8n-nodes-langchain.agent",
      "typeVersion": 3,
      "parameters": {
        "options": {
          "maxIterations": 20
        }
      }
    }
  ]
}
```

---

## Version 3.1 Changes

| Change | Impact |
|--------|--------|
| `guardrails` promptType removed | Use `auto` or `define` only |
| Improved streaming | Better real-time output |
| Enhanced tool handling | More reliable tool calls |

---

## Anti-Patterns (AVOID)

| Wrong | Correct | Reason |
|-------|---------|--------|
| `typeVersion: 2.0` | `typeVersion: 3` or `3.1` | v2 incompatible with GPT-4o |
| Over-specified params | `{"options": {}}` | Let n8n handle defaults |
| `promptType: "guardrails"` | `"auto"` or `"define"` | Removed in v3.1 |
| `maxIterations: 100` | `10-20` | Prevents infinite loops |
| Missing LLM connection | Connect via `ai_languageModel` | Required for operation |

---

## Validation Checklist

- [ ] Using typeVersion 3 or 3.1
- [ ] LLM connected via `ai_languageModel`
- [ ] Chat Trigger connected via `main`
- [ ] Memory connected via `ai_memory` (if needed)
- [ ] Tools connected via `ai_tool` (if needed)
- [ ] Output Parser connected via `ai_outputParser` (if `hasOutputParser: true`)
- [ ] `maxIterations` set to reasonable value (10-20)
- [ ] Minimal parameters used

---

## Related Documentation

- [OpenAI Chat Model](lm-chat-openai.md) - LLM configuration
- [Anthropic Claude](lm-chat-anthropic.md) - Alternative LLM
- [Memory Buffer Window](memory-buffer-window.md) - Conversation memory
- [Tool Workflow](tool-workflow.md) - Sub-workflow tools
- [Output Parser](output-parser-structured.md) - Structured output
