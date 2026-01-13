# OpenRouter Chat Model Node Reference

> **Node Type**: `@n8n/n8n-nodes-langchain.lmChatOpenRouter`
> **Latest TypeVersion**: 1
> **Last Verified**: 2025-12-27
> **Source**: MCP `get_node` with full detail

---

## Overview

Multi-model LLM integration via OpenRouter API. Provides access to hundreds of models from various providers through a single API.

**Required Credential**: `openRouterApi`

---

## Model Selection

- **Default**: `openai/gpt-4.1-mini`
- **Options**: Dynamically loaded from OpenRouter API
- **Documentation**: [OpenRouter Models](https://openrouter.ai/docs/models)

---

## Core Parameters

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `model` | options | openai/gpt-4.1-mini | dynamic | Model selection |
| `temperature` | number | 0.7 | 0-2 | Randomness control |
| `topP` | number | 1 | 0-1 | Nucleus sampling |
| `frequencyPenalty` | number | 0 | -2 to 2 | Penalize repetition |
| `presencePenalty` | number | 0 | -2 to 2 | Encourage new topics |
| `maxTokens` | number | -1 | -1 to 32768 | Output limit |
| `timeout` | number | 360000 | ms | Request timeout (6 min) |
| `maxRetries` | number | 2 | - | Retry attempts |
| `responseFormat` | options | text | text/json_object | Output format |

---

## Reference Configuration

```json
{
  "name": "OpenRouter Chat",
  "type": "@n8n/n8n-nodes-langchain.lmChatOpenRouter",
  "typeVersion": 1,
  "position": [500, 300],
  "parameters": {
    "model": "openai/gpt-4.1-mini",
    "options": {
      "temperature": 0.7,
      "maxTokens": -1,
      "timeout": 360000,
      "maxRetries": 2,
      "responseFormat": "text"
    }
  },
  "credentials": {
    "openRouterApi": "CREDENTIAL_ID"
  }
}
```

---

## Critical Rules

1. **JSON Response Format**: Include "json" keyword in prompt when using `json_object`
2. **Use Recent Models**: For JSON output, use models released post-November 2023
3. **AI Chain Required**: Must connect to AI chain node
4. **AI Tool Capable**: Requires `N8N_COMMUNITY_PACKAGES_ALLOW_TOOL_USAGE=true`
