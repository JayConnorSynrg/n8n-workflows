# Structured Output Parser Node Reference

> **Node Type**: `@n8n/n8n-nodes-langchain.outputParserStructured`
> **Latest TypeVersion**: 1.3
> **Last Verified**: 2025-12-27
> **Source**: MCP `get_node` with full detail

---

## Overview

Enforces AI output into a defined JSON format. Validates output against schema and optionally retries with LLM if invalid.

---

## Schema Configuration Modes

### 1. Generate From JSON Example (`fromJson`)
- Simplest approach - provide example JSON
- Schema auto-generated from structure
- **Limitation v1.3+**: All properties become required
- Use manual mode for optional properties

### 2. Define Using JSON Schema (`manual`)
- Full control via JSON Schema specification
- Supports optional properties, complex validation
- Includes `required` array for conditional fields

---

## Core Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `schemaType` | options | `fromJson` | `fromJson` or `manual` |
| `jsonSchemaExample` | json | - | Example JSON (for fromJson mode) |
| `inputSchema` | json | - | JSON Schema (for manual mode) |
| `autoFix` | boolean | false | Retry with LLM if invalid |
| `customizeRetryPrompt` | boolean | false | Custom retry template |
| `prompt` | string | - | Retry template with placeholders |

---

## Reference Configuration

### From JSON Example
```json
{
  "name": "Output Parser",
  "type": "@n8n/n8n-nodes-langchain.outputParserStructured",
  "typeVersion": 1.3,
  "parameters": {
    "schemaType": "fromJson",
    "jsonSchemaExample": "{\n  \"title\": \"Example Title\",\n  \"summary\": \"Brief summary\",\n  \"score\": 85\n}"
  }
}
```

### Manual JSON Schema
```json
{
  "parameters": {
    "schemaType": "manual",
    "inputSchema": {
      "type": "object",
      "properties": {
        "title": { "type": "string" },
        "summary": { "type": "string" },
        "score": { "type": "number" }
      },
      "required": ["title", "summary"]
    }
  }
}
```

### With Auto-Fix
```json
{
  "parameters": {
    "schemaType": "manual",
    "inputSchema": { /* schema */ },
    "autoFix": true,
    "customizeRetryPrompt": false
  }
}
```

---

## Connection

- **Input**: AI chain node (required)
- **Output**: Single output port ("Output Parser")
- **AI Tool Capable**: Yes (requires env var)

---

## Critical Rules

1. **Version 1.3** makes all `fromJson` properties required - use `manual` for optional fields
2. **autoFix** adds latency due to additional LLM call
3. **Recommended** for agentic workflows needing deterministic output structure
4. **Retry Placeholders**: `{instructions}`, `{completion}`, `{error}`

---

## Related Patterns

- `.claude/patterns/workflow-architecture/output-parser-config.md`
