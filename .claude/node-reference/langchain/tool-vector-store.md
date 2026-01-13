# Vector Store Tool Node Reference

> **Node Type**: `@n8n/n8n-nodes-langchain.toolVectorStore`
> **Latest TypeVersion**: 1.1
> **Last Verified**: 2025-12-27
> **Source**: MCP `get_node` with full detail

---

## Overview

Enables AI agents to query vector stores for semantic search and question answering.

**AI Tool Capable**: Requires `N8N_COMMUNITY_PACKAGES_ALLOW_TOOL_USAGE=true`

---

## Core Parameters

| Parameter | Type | Default | Required | Description |
|-----------|------|---------|----------|-------------|
| `name` | string | "" | Yes | Data identifier for agent |
| `description` | string | "" | Yes | Data explanation for agent |
| `topK` | number | 4 | No | Max results from search |

---

## Agent Integration

Tool description auto-generated as:
> "Useful for when you need to answer questions about [name]. Whenever you need information about [description], you should ALWAYS use this. Input should be a fully formed question."

---

## Reference Configuration

```json
{
  "name": "Vector Store Q&A",
  "type": "@n8n/n8n-nodes-langchain.toolVectorStore",
  "typeVersion": 1.1,
  "parameters": {
    "name": "Product Documentation",
    "description": "Company product guides, API references, and feature documentation",
    "topK": 4
  }
}
```

---

## Connection

- **Output Type**: `ai_tool`
- **Connect To**: AI Agent node
- **Upstream**: Connect vector store node for data source

---

## Critical Rules

1. **Must connect to AI agent** - Cannot function standalone
2. **Requires vector store upstream** - Data source must be initialized
3. **Input format** - Agent passes fully formed questions
4. **topK tuning** - Adjust based on expected result density
