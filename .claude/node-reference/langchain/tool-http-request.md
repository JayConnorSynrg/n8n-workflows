# Tool HTTP Request Node Reference

> **Node Type**: `@n8n/n8n-nodes-langchain.toolHttpRequest`
> **Latest TypeVersion**: 1.1
> **Last Verified**: 2025-12-27
> **Source**: MCP `get_node` with full detail

---

## Overview

Makes HTTP requests as an AI agent tool. Uses placeholders that LLM fills in based on context.

**AI Tool Capable**: Requires `N8N_COMMUNITY_PACKAGES_ALLOW_TOOL_USAGE=true`

---

## Core Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `toolDescription` | string | "" | Explain to LLM what this tool does (CRITICAL) |
| `method` | options | GET | GET, POST, PUT, PATCH, DELETE |
| `url` | string | "" | Request URL (supports `{placeholder}`) |
| `authentication` | options | none | none, predefinedCredentialType, genericCredentialType |

---

## Placeholder System

Use `{placeholderName}` in URL, query, headers, or body. LLM fills based on definitions.

### Placeholder Definition
```json
{
  "placeholderDefinitions": {
    "values": [
      {
        "name": "location",
        "description": "City name for weather lookup",
        "type": "string"
      }
    ]
  }
}
```

**Placeholder Types**: `string`, `number`, `boolean`, `json`

---

## Query/Headers/Body Configuration

### Value Provider Options
- `modelRequired` - LLM must provide
- `modelOptional` - LLM can optionally provide
- `fieldValue` - Fixed value in workflow

### Specification Modes
- `keypair` - Manual key-value pairs
- `json` - Raw JSON
- `model` - LLM decides

---

## Response Optimization

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `optimizeResponse` | boolean | false | Reduce data for LLM |
| `responseType` | options | json | json, html, text |
| `dataField` | string | "" | JSON field with data |
| `fieldsToInclude` | options | all | all, selected, except |
| `truncateResponse` | boolean | false | Limit size |
| `maxLength` | number | 1000 | Max characters |

---

## Reference Configuration

### Weather API with Placeholder
```json
{
  "name": "Weather Lookup",
  "type": "@n8n/n8n-nodes-langchain.toolHttpRequest",
  "typeVersion": 1.1,
  "parameters": {
    "toolDescription": "Gets current weather for a specified city",
    "method": "GET",
    "url": "https://api.weather.com/v1/current?city={location}",
    "placeholderDefinitions": {
      "values": [
        {
          "name": "location",
          "description": "City name",
          "type": "string"
        }
      ]
    },
    "optimizeResponse": true,
    "responseType": "json",
    "fieldsToInclude": "selected",
    "fields": "temperature,conditions,humidity"
  }
}
```

---

## Connection

- **Output Type**: `ai_tool`
- **Connect To**: AI Agent node

---

## Critical Rules

1. **Always define `toolDescription`** - LLM uses this to decide when to invoke
2. **Use placeholders for model inputs** - Format: `{parameterName}`
3. **Define placeholder types** - For type safety
4. **Optimize responses for cost** - Use field filtering and truncation
5. **Connection type**: Set to `type: "main"` (not "0")
