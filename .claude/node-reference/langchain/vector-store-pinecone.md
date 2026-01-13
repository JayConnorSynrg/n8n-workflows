# Pinecone Vector Store Node Reference

> **Node Type**: `@n8n/n8n-nodes-langchain.vectorStorePinecone`
> **Latest TypeVersion**: 1.3
> **Last Verified**: 2025-12-27
> **Source**: MCP `get_node` with full detail

---

## Overview

Pinecone vector database integration for document storage, retrieval, and semantic search.

**Required Credential**: `pineconeApi`

---

## Operation Modes

| Mode | Value | Use Case |
|------|-------|----------|
| Get Ranked Documents | `load` | Query and retrieve top-K results |
| Insert Documents | `insert` | Add documents with embeddings |
| Retrieve as Vector Store | `retrieve` | Use with Chain/Tool nodes |
| Retrieve as Tool | `retrieve-as-tool` | Use with AI Agent |
| Update Documents | `update` | Update existing by ID |

---

## Core Parameters

### Required
- `pineconeIndex` (ResourceLocator): Index ID
- `pineconeApi` (Credential): API authentication

### Load Mode (Query)
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `prompt` | string | - | Search query (required) |
| `topK` | number | 4 | Number of results |
| `includeDocumentMetadata` | boolean | true | Include metadata |
| `useReranker` | boolean | false | Apply reranking |
| `options.pineconeNamespace` | string | - | Namespace filter |

### Insert Mode
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `embeddingBatchSize` | number | 200 | Documents per batch |
| `options.clearNamespace` | boolean | false | Clear before insert |

### Retrieve as Tool Mode
| Parameter | Type | Description |
|-----------|------|-------------|
| `toolName` | string | Tool name for AI Agent (v≤1.2) |
| `toolDescription` | string | Tool description for LLM |
| `topK` | number | Result limit |

---

## Reference Configuration

### Load (Query)
```json
{
  "name": "Pinecone Query",
  "type": "@n8n/n8n-nodes-langchain.vectorStorePinecone",
  "typeVersion": 1.3,
  "parameters": {
    "mode": "load",
    "pineconeIndex": {
      "mode": "list",
      "value": "my-index-id"
    },
    "prompt": "={{ $json.query }}",
    "topK": 5,
    "includeDocumentMetadata": true,
    "options": {
      "pineconeNamespace": "production"
    }
  },
  "credentials": {
    "pineconeApi": "CREDENTIAL_ID"
  }
}
```

### Insert Documents
```json
{
  "parameters": {
    "mode": "insert",
    "pineconeIndex": {
      "mode": "list",
      "value": "my-index-id"
    },
    "embeddingBatchSize": 200,
    "options": {
      "clearNamespace": false,
      "pineconeNamespace": "production"
    }
  }
}
```

### Retrieve as Tool (for AI Agent)
```json
{
  "parameters": {
    "mode": "retrieve-as-tool",
    "pineconeIndex": {
      "mode": "list",
      "value": "my-index-id"
    },
    "toolDescription": "Search company knowledge base for relevant documents",
    "topK": 4,
    "includeDocumentMetadata": true
  }
}
```

---

## Connection

- **Output Types**: `Document` (load), `VectorStore` (retrieve), `ai_tool` (retrieve-as-tool)
- **Upstream**: Connect Embeddings node for insert operations

---

## Critical Rules

1. **Mode Selection**: Choose based on downstream integration
2. **Namespace Support**: Enables multi-tenant partitioning
3. **Batch Sizing**: 200 documents default optimizes embedding performance
4. **Reranking**: Improves result relevance but adds latency
5. **AI Tool Mode**: Use `retrieve-as-tool` for AI Agent integration
