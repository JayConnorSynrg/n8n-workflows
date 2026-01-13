# OpenAI Chat Model Node Reference

> **Node Type**: `@n8n/n8n-nodes-langchain.lmChatOpenAi`
> **Latest TypeVersion**: 1.3
> **Last Verified**: 2025-12-28
> **Source**: MCP `get_node` with full detail

---

## Overview

Advanced LLM integration for AI chains and agents. Supports GPT-4, GPT-3.5, reasoning models (o1/o3), and fine-tuned models.

**Required Credential**: `openAiApi`

---

## Model Options

### Available Models
| Model | Best For | Context | Notes |
|-------|----------|---------|-------|
| `gpt-4o-mini` | Cost-effective default | 128K | Recommended for most tasks |
| `gpt-4o` | High quality | 128K | Vision capable |
| `gpt-4-turbo` | Legacy high quality | 128K | Use gpt-4o instead |
| `o1` | Complex reasoning | 128K | Uses `reasoningEffort` |
| `o3` | Advanced reasoning | 128K | Uses `reasoningEffort` |

### ResourceLocator Format (Required v1.2+)
```json
{
  "model": {
    "mode": "list",
    "value": "gpt-4o-mini"
  }
}
```

**Modes**:
- `list` - Select from available models via dropdown
- `id` - Specify custom model ID (e.g., `ft:custom-model`)

---

## Core Parameters

| Parameter | Type | Range | Default | Purpose |
|-----------|------|-------|---------|---------|
| `temperature` | number | 0-2 | 0.7 | Randomness (0=deterministic) |
| `maxTokens` | number | 1-32768 | -1 (unlimited) | Output length limit |
| `topP` | number | 0-1 | 1 | Nucleus sampling |
| `frequencyPenalty` | number | -2 to 2 | 0 | Penalize repetition |
| `presencePenalty` | number | -2 to 2 | 0 | Encourage new topics |

---

## Response Format Options

| Format | Description |
|--------|-------------|
| `text` | Standard text response (default) |
| `json_object` | Ensures valid JSON output |
| `json_schema` | Strict schema-validated JSON (v1.3+) |

---

## Responses API (v1.3+)

When `responsesApiEnabled: true`, enables advanced features:

### JSON Schema Response
```json
{
  "parameters": {
    "model": { "mode": "list", "value": "gpt-4o" },
    "responsesApiEnabled": true,
    "options": {
      "responseFormat": "json_schema",
      "responseFormatSchema": {
        "name": "data_response",
        "schema": {
          "type": "object",
          "properties": {
            "result": { "type": "string" },
            "confidence": { "type": "number" }
          },
          "required": ["result", "confidence"],
          "additionalProperties": false
        },
        "strict": true
      }
    }
  }
}
```

### Built-in Tools (v1.3+)
| Tool | Purpose | Parameters |
|------|---------|------------|
| `webSearch` | Search the web | `searchContextSize`, `allowedDomains`, `country`, `city` |
| `fileSearch` | Search uploaded files | `vectorStoreIds`, `filters`, `maxResults` |
| `codeInterpreter` | Execute Python code | `true/false` |

```json
{
  "parameters": {
    "responsesApiEnabled": true,
    "builtInTools": {
      "webSearch": {
        "enabled": true,
        "searchContextSize": "medium"
      }
    }
  }
}
```

---

## Reference Configurations

### Basic Chat Completion
```json
{
  "name": "OpenAI Chat",
  "type": "@n8n/n8n-nodes-langchain.lmChatOpenAi",
  "typeVersion": 1.3,
  "parameters": {
    "model": {
      "mode": "list",
      "value": "gpt-4o-mini"
    },
    "options": {
      "temperature": 0.7,
      "maxTokens": 1000
    }
  },
  "credentials": {
    "openAiApi": {
      "id": "your-credential-id",
      "name": "OpenAI API"
    }
  }
}
```

### Reasoning Model (o1/o3)
```json
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
}
```

**Reasoning Effort Options**:
- `low` - Faster, less thorough
- `medium` - Balanced (default)
- `high` - Most thorough reasoning

### JSON Output Mode
```json
{
  "parameters": {
    "model": { "mode": "list", "value": "gpt-4o" },
    "options": {
      "responseFormat": "json_object"
    }
  }
}
```

**Note**: When using `json_object`, include "json" or "JSON" in your prompt.

### With Web Search (v1.3+)
```json
{
  "parameters": {
    "model": { "mode": "list", "value": "gpt-4o" },
    "responsesApiEnabled": true,
    "builtInTools": {
      "webSearch": {
        "enabled": true,
        "searchContextSize": "medium",
        "allowedDomains": ["wikipedia.org", "docs.python.org"]
      }
    }
  }
}
```

### Fine-tuned Model
```json
{
  "parameters": {
    "model": {
      "mode": "id",
      "value": "ft:gpt-3.5-turbo:your-org::abc123"
    }
  }
}
```

---

## AI Agent Integration

Connect to AI Agent node via `ai_languageModel` connection:

```json
{
  "connections": {
    "OpenAI Chat": {
      "ai_languageModel": [
        [{ "node": "AI Agent", "type": "ai_languageModel", "index": 0 }]
      ]
    }
  }
}
```

---

## Critical Rules

1. **Use ResourceLocator format** for model selection (v1.2+)
2. **JSON mode requires** "json" keyword in prompt
3. **Reasoning models** (o1/o3) use `reasoningEffort` instead of `temperature`
4. **Do NOT mix** `responsesApiEnabled: true` with legacy `responseFormat` in options
5. **Always specify credential** reference

---

## Anti-Patterns (AVOID)

| Wrong | Correct | Reason |
|-------|---------|--------|
| `model: "gpt-4o"` | `model: { mode: "list", value: "gpt-4o" }` | ResourceLocator format required |
| `reasoningEffort` on GPT-4 | Only use on o1/o3 models | Only for reasoning models |
| `temperature` on o1/o3 | Use `reasoningEffort` | Reasoning models don't support temperature |
| `typeVersion: 1.2` | `typeVersion: 1.3` | Always use latest version |

---

## Version History

| Version | Key Changes |
|---------|------------|
| 1.3 | Responses API, built-in tools (web/file search, code interpreter), json_schema support |
| 1.2 | ResourceLocator for model selection |
| 1.1 | JSON mode support |
| 1.0 | Initial release |

---

## Validation Checklist

- [ ] Using typeVersion 1.3
- [ ] Model uses ResourceLocator format `{ mode, value }`
- [ ] Credential reference included
- [ ] Temperature not used with o1/o3 models
- [ ] JSON mode has "json" in prompt
- [ ] Connected to AI Agent via `ai_languageModel`
