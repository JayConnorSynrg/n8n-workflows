# Google Gemini Embeddings Node Reference

> **Node Type**: `@n8n/n8n-nodes-langchain.embeddingsGoogleGemini`
> **Latest TypeVersion**: 1
> **Last Verified**: 2025-12-27
> **Source**: MCP `get_node` with full detail

---

## Overview

Google Gemini embedding model integration for vector store operations.

**Required Credential**: `googlePalmApi`

---

## Model Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `modelName` | options | `models/text-embedding-004` | Embedding model |

**Default Dimensionality**: 768-dimensional embeddings

---

## Reference Configuration

```json
{
  "name": "Gemini Embeddings",
  "type": "@n8n/n8n-nodes-langchain.embeddingsGoogleGemini",
  "typeVersion": 1,
  "parameters": {
    "modelName": "models/text-embedding-004"
  },
  "credentials": {
    "googlePalmApi": "CREDENTIAL_ID"
  }
}
```

---

## Connection

- **Output Type**: `Embeddings`
- **Connect To**: Vector Store node (downstream)

---

## Critical Rules

1. **Vector Store Required** - Must connect to downstream vector store
2. **Dimensionality Consistency** - Ensure vector store matches 768D
3. **Credential Required** - `googlePalmApi` mandatory
4. **AI Tool Capable** - Requires `N8N_COMMUNITY_PACKAGES_ALLOW_TOOL_USAGE=true`
5. **Dynamic Model Loading** - Models filtered to embedding-capable only

---

## Anti-Patterns

| Issue | Cause | Fix |
|-------|-------|-----|
| Dimension mismatch | Different embedding model | Match vector store dimensions |
| Missing connection | No downstream node | Connect to vector store |
| Auth failure | Invalid credentials | Configure googlePalmApi |
