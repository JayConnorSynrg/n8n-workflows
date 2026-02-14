# Voice Tool: Vector Database Operations

**Workflow IDs:**
- Query Vector DB: `z02K1a54akYXMkyj`
- Add to Vector DB: `jKMw735r3nAN6O7u`

**Created:** 2026-01-17
**Status:** Production Ready

## Purpose

Two gated voice tool sub-workflows for the SYNRG AIO Voice Agent that enable:
1. **Query Vector DB** - Search the knowledge base and return relevant information
2. **Add to Vector DB** - Store new information in the knowledge base for later retrieval

Both workflows implement the gated execution pattern with callback-based flow control, allowing the voice agent to confirm actions before execution.

## Architecture

See [docs/architecture.md](./docs/architecture.md) for detailed technical design.

```
┌─────────────────────────────────────────────────────────────────┐
│                    VOICE AGENT TOOLS                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Voice Agent (LiveKit)                                           │
│       │                                                          │
│       ├─► POST /add-to-vector-db (3 gates - confirmation)        │
│       │   Gate 1: "I'll add this to the knowledge base..."       │
│       │   Gate 2: "Ready to store. Confirm to proceed?"          │
│       │   Gate 3: "Successfully stored X chunks"                 │
│       │                                                          │
│       └─► POST /query-vector-db (2 gates - search)               │
│           Gate 1: "Searching the knowledge base..."              │
│           Gate 2: "I found X relevant results..."                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Testing

See [docs/testing.md](./docs/testing.md) for test procedures.

### Quick Test - Query

```bash
curl -X POST https://jayconnorexe.app.n8n.cloud/webhook/query-vector-db \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-session-001",
    "callback_url": "https://jayconnorexe.app.n8n.cloud/webhook/callback-noop",
    "query": "What is the vacation policy?",
    "top_k": 5
  }'
```

### Quick Test - Add

```bash
curl -X POST https://jayconnorexe.app.n8n.cloud/webhook/add-to-vector-db \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-session-001",
    "callback_url": "https://jayconnorexe.app.n8n.cloud/webhook/callback-noop",
    "content": "The vacation policy states that employees receive 15 days of paid leave annually.",
    "metadata": {
      "source": "hr_manual",
      "category": "policies"
    }
  }'
```

## LiveKit Agent Integration

Add these tools to your LiveKit voice agent:

```python
@llm.function_tool(
    name="query_knowledge_base",
    description="Search the knowledge base for information about policies, procedures, or previously stored information."
)
async def query_knowledge_base_tool(query: str, top_k: int = 5) -> str:
    response = await http_client.post(
        f"{N8N_WEBHOOK_BASE}/query-vector-db",
        json={"session_id": session_id, "callback_url": callback_url, "query": query, "top_k": top_k}
    )
    return response.json().get("voice_response", "No results found.")

@llm.function_tool(
    name="add_to_knowledge_base",
    description="Store information in the knowledge base. ALWAYS confirm before storing."
)
async def add_to_knowledge_base_tool(content: str, category: str = "general") -> str:
    response = await http_client.post(
        f"{N8N_WEBHOOK_BASE}/add-to-vector-db",
        json={"session_id": session_id, "callback_url": callback_url, "content": content, "metadata": {"category": category}}
    )
    return response.json().get("voice_response", "Information stored.")
```

## Credentials Required

| Credential | Purpose | ID |
|------------|---------|-----|
| PostgreSQL | Tool call tracking | `NI3jbq1U8xPst3j3` |
| Google Gemini | Embeddings | `mVh9oGzTvuTD7mxB` |
| Pinecone | Vector storage | `GAblF7Hlg8tSKQlW` |

## Pinecone Index

- **Index Name:** `autopayplus-hr-semantic-archive`
- **Dimensions:** 1024
- **Embedding Model:** Google Gemini `gemini-embedding-001` (with `outputDimensionality: 1024`)
- **Host:** `https://autopayplus-hr-semantic-archive-nzlkkal.svc.aped-4627-b74a.pinecone.io`
- **Chunk Size:** 1000 characters with 100 char overlap

> **Note:** The old index `resume-review-autopayplus` (768 dims, text-embedding-004) was deprecated after Google shut down text-embedding-004 on Jan 14, 2026.

## Related Workflows

| Workflow | ID | Purpose |
|----------|-----|---------|
| Voice Tool: Send Gmail | `kBuTRrXTJF1EEBEs` | Email sending tool |
| Callback No-Op | `Y6CuLuSu87qKQzK1` | Gate callback handler |
| RAG Chatbot (Reference) | `4RRsl3R2DePIGfFd` | Original combined workflow |

## Changelog

### 2026-01-17 - v1.0.0
- Initial creation of both workflows
- Implemented 3-gate pattern for Add workflow
- Implemented 2-gate pattern for Query workflow
- Applied gated-execution-callbacks pattern from Send Gmail
- Integrated with existing Pinecone index and Google Gemini embeddings
