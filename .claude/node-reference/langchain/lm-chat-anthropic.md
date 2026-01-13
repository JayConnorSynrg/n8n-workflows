# Anthropic Claude Chat Model Node Reference

> **Node Type**: `@n8n/n8n-nodes-langchain.lmChatAnthropic`
> **Latest TypeVersion**: 1.3
> **Last Verified**: 2025-12-27
> **Source**: MCP `get_node` with full detail

---

## Overview

Advanced Claude model integration for AI chains and agents. Supports Claude Sonnet 4.5, Claude 3.5, and Claude 3 family.

**Required Credential**: `anthropicApi`

---

## Available Models (v1.3)

| Model | ID | Notes |
|-------|-----|-------|
| Claude Sonnet 4.5 | `claude-sonnet-4-5-20250929` | Latest frontier model |
| Claude 3.5 Sonnet | `claude-3-5-sonnet-20241022` | High capability |
| Claude 3 Opus | `claude-3-opus-20240229` | Most capable Claude 3 |
| Claude 3.5 Haiku | `claude-3-5-haiku-20241022` | Fast, efficient |
| Claude 3 Haiku | `claude-3-haiku-20240307` | Fastest |
| Claude 3 Sonnet | `claude-3-sonnet-20240229` | Balanced |

---

## Model Configuration

### ResourceLocator Format (v1.3)
```json
{
  "mode": "list",
  "value": "claude-sonnet-4-5-20250929",
  "cachedResultName": "Claude Sonnet 4.5"
}
```

---

## Core Parameters

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `model` | ResourceLocator | claude-sonnet-4-5 | - | Model selection |
| `maxTokensToSample` | number | 4096 | - | Max output tokens |
| `temperature` | number | 0.7 | 0-1 | Randomness control |
| `topK` | number | -1 | - | Long-tail filter (-1=disabled) |
| `topP` | number | 1 | 0-1 | Nucleus sampling |
| `thinking` | boolean | false | - | Extended thinking mode |
| `thinkingBudget` | number | 1024 | - | Tokens for thinking |

---

## Reference Configuration

### Standard Configuration
```json
{
  "type": "@n8n/n8n-nodes-langchain.lmChatAnthropic",
  "typeVersion": 1.3,
  "parameters": {
    "model": {
      "mode": "list",
      "value": "claude-sonnet-4-5-20250929",
      "cachedResultName": "Claude Sonnet 4.5"
    },
    "options": {
      "maxTokensToSample": 4096,
      "temperature": 0.7,
      "topP": 1,
      "thinking": false
    }
  },
  "credentials": {
    "anthropicApi": "{{ $credentials.anthropic }}"
  }
}
```

### With Extended Thinking
```json
{
  "parameters": {
    "model": {
      "mode": "list",
      "value": "claude-sonnet-4-5-20250929"
    },
    "options": {
      "maxTokensToSample": 8192,
      "temperature": 0.7,
      "thinking": true,
      "thinkingBudget": 2048
    }
  }
}
```

---

## Critical Rules

1. **TypeVersion 1.3 is current** - Uses ResourceLocator for model selection
2. **Extended Thinking** - Requires sufficient token budget
3. **Credential Required** - `anthropicApi` must be configured
4. **AI Chain Required** - Must connect to AI chain node

---

## AI Tool Variant

For AI Agent tool integration, use:
- **Tool Variant**: `@n8n/n8n-nodes-langchain.lmChatAnthropicTool`
- Outputs `ai_tool` type instead of `Model`
