# Voice Tool: Vector Database Operations - Architecture

## Overview

Two gated voice tool sub-workflows for the SYNRG AIO Voice Agent:
1. **Voice Tool: Add to Vector DB** - Chunks, embeds, and stores information
2. **Voice Tool: Query Vector DB** - Retrieves relevant information from knowledge base

Both workflows implement the gated execution pattern with callback-based flow control.

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                    VOICE AGENT VECTOR DB TOOL ARCHITECTURE                        │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  LIVEKIT VOICE AGENT (Railway)                                                    │
│       │                                                                           │
│       │  Function Tool Calls                                                      │
│       ▼                                                                           │
│  ┌──────────────────────────────────────────────────────────────────────────┐    │
│  │                    N8N CLOUD                                              │    │
│  │                    https://jayconnorexe.app.n8n.cloud                     │    │
│  ├──────────────────────────────────────────────────────────────────────────┤    │
│  │                                                                           │    │
│  │  POST /webhook/add-to-vector-db ──────→ Voice Tool: Add to Vector DB     │    │
│  │       │                                                                   │    │
│  │       ├─ Gate 1: "I'll add this to the knowledge base..."                │    │
│  │       ├─ Gate 2: "Ready to store. Confirm to proceed?"                   │    │
│  │       ├─ [Chunk + Embed + Store in Pinecone]                             │    │
│  │       └─ Gate 3: "Information stored successfully"                       │    │
│  │                                                                           │    │
│  │  POST /webhook/query-vector-db ───────→ Voice Tool: Query Vector DB      │    │
│  │       │                                                                   │    │
│  │       ├─ Gate 1: "Searching the knowledge base..."                       │    │
│  │       ├─ [Query Pinecone + Retrieve Results]                             │    │
│  │       └─ Gate 2: "Here's what I found..."                                │    │
│  │                                                                           │    │
│  │  POST /webhook/callback-noop ─────────→ Callback No-Op                   │    │
│  │                                                                           │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│                              │                                                    │
│                              ▼                                                    │
│  ┌──────────────────────────────────────────────────────────────────────────┐    │
│  │                    PINECONE VECTOR DATABASE                               │    │
│  │                    Index: resume-review-autopayplus                       │    │
│  │                                                                           │    │
│  │  Embeddings: Google Gemini (768/1536 dimensions)                         │    │
│  │  Chunks: ~1000 chars with 100 char overlap                               │    │
│  │                                                                           │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Workflow 1: Voice Tool - Add to Vector DB

### Purpose
Accepts text content from the voice agent, chunks it, creates embeddings, and stores in Pinecone.

### Webhook Endpoint
`POST /webhook/add-to-vector-db`

### Request Schema
```json
{
  "session_id": "string",
  "callback_url": "string (optional)",
  "content": "string - The text content to add",
  "metadata": {
    "source": "string - Where this info came from",
    "category": "string - Topic category",
    "added_by": "string - User or agent identifier"
  }
}
```

### Gated Execution Flow

```
Webhook: POST /add-to-vector-db
    ↓
Code: Generate tool_call_id, validate content
    ↓
PostgreSQL: INSERT (status: EXECUTING, function_name: 'add_to_vector_db')
    ↓
┌─────────────────────────────────────────────────────────────┐
│ GATE 1: Progress Callback                                   │
│ Voice: "I'll add this information to the knowledge base..." │
│ Cancellable: YES                                            │
└─────────────────────────────────────────────────────────────┘
    ↓
IF: Check Cancel
    ├─ TRUE → PostgreSQL: CANCELLED → Return
    └─ FALSE ↓
    ↓
Code: Prepare content for chunking (format, clean)
    ↓
┌─────────────────────────────────────────────────────────────┐
│ GATE 2: Confirmation Required                               │
│ Voice: "Ready to store [X] characters. Confirm to proceed?" │
│ Cancellable: YES                                            │
└─────────────────────────────────────────────────────────────┘
    ↓
IF: Check Cancel
    ├─ TRUE → PostgreSQL: CANCELLED → Return
    └─ FALSE ↓
    ↓
┌─────────────────────────────────────────────────────────────┐
│ [IRREVERSIBLE: VECTOR DB OPERATIONS]                        │
│                                                             │
│ Default Data Loader (text → documents)                      │
│     ↓                                                       │
│ Recursive Character Text Splitter (1000 chars, 100 overlap) │
│     ↓                                                       │
│ Embeddings Google Gemini (chunks → vectors)                 │
│     ↓                                                       │
│ Pinecone Vector Store (mode: insert)                        │
└─────────────────────────────────────────────────────────────┘
    ↓
PostgreSQL: UPDATE (status: COMPLETED, chunks_stored: N)
    ↓
┌─────────────────────────────────────────────────────────────┐
│ GATE 3: Completion Callback                                 │
│ Voice: "Successfully stored [N] chunks in the knowledge     │
│        base under category [category]"                      │
└─────────────────────────────────────────────────────────────┘
    ↓
Respond to Webhook with voice_response
```

### Node List (Estimated: 18 nodes)

| # | Node Name | Type | Purpose |
|---|-----------|------|---------|
| 1 | Webhook: Add to Vector DB | n8n-nodes-base.webhook | Receive add request |
| 2 | Code: Generate IDs | n8n-nodes-base.code | tool_call_id, validation |
| 3 | PostgreSQL: Insert Record | n8n-nodes-base.postgres | Track execution |
| 4 | HTTP: Gate 1 Callback | n8n-nodes-base.httpRequest | Progress notification |
| 5 | IF: Check Cancel 1 | n8n-nodes-base.if | Cancel branch |
| 6 | PostgreSQL: Update Cancelled | n8n-nodes-base.postgres | Mark cancelled |
| 7 | Code: Prepare Content | n8n-nodes-base.code | Format for chunking |
| 8 | HTTP: Gate 2 Callback | n8n-nodes-base.httpRequest | Confirmation request |
| 9 | IF: Check Cancel 2 | n8n-nodes-base.if | Cancel branch |
| 10 | Default Data Loader | @n8n/n8n-nodes-langchain.documentDefaultDataLoader | Text to docs |
| 11 | Text Splitter | @n8n/n8n-nodes-langchain.textSplitterRecursiveCharacterTextSplitter | Chunk docs |
| 12 | Embeddings Gemini | @n8n/n8n-nodes-langchain.embeddingsGoogleGemini | Create embeddings |
| 13 | Pinecone Insert | @n8n/n8n-nodes-langchain.vectorStorePinecone | Store vectors |
| 14 | PostgreSQL: Update Completed | n8n-nodes-base.postgres | Mark completed |
| 15 | HTTP: Gate 3 Callback | n8n-nodes-base.httpRequest | Completion notification |
| 16 | Code: Build Response | n8n-nodes-base.code | Format voice_response |
| 17 | Respond to Webhook | n8n-nodes-base.respondToWebhook | Return result |
| 18 | Sticky Note | n8n-nodes-base.stickyNote | Documentation |

---

## Workflow 2: Voice Tool - Query Vector DB

### Purpose
Accepts a search query from the voice agent, retrieves relevant documents from Pinecone, and returns formatted results.

### Webhook Endpoint
`POST /webhook/query-vector-db`

### Request Schema
```json
{
  "session_id": "string",
  "callback_url": "string (optional)",
  "query": "string - The search query",
  "top_k": "number (optional, default: 5) - Number of results",
  "filter": {
    "category": "string (optional) - Filter by category"
  }
}
```

### Gated Execution Flow

```
Webhook: POST /query-vector-db
    ↓
Code: Generate tool_call_id, validate query
    ↓
PostgreSQL: INSERT (status: EXECUTING, function_name: 'query_vector_db')
    ↓
┌─────────────────────────────────────────────────────────────┐
│ GATE 1: Progress Callback                                   │
│ Voice: "Searching the knowledge base for [query preview]..."│
│ Cancellable: YES (brief window)                             │
└─────────────────────────────────────────────────────────────┘
    ↓
IF: Check Cancel
    ├─ TRUE → PostgreSQL: CANCELLED → Return
    └─ FALSE ↓
    ↓
┌─────────────────────────────────────────────────────────────┐
│ [VECTOR DB QUERY - Non-destructive, no Gate 2 needed]       │
│                                                             │
│ Embeddings Google Gemini (query → vector)                   │
│     ↓                                                       │
│ Pinecone Vector Store (mode: retrieve, topK)                │
│     ↓                                                       │
│ Code: Format results for voice output                       │
└─────────────────────────────────────────────────────────────┘
    ↓
PostgreSQL: UPDATE (status: COMPLETED, results_count: N)
    ↓
┌─────────────────────────────────────────────────────────────┐
│ GATE 2: Completion Callback                                 │
│ Voice: "I found [N] relevant results. [Summary of top 3]"   │
└─────────────────────────────────────────────────────────────┘
    ↓
Respond to Webhook with voice_response + results
```

### Node List (Estimated: 14 nodes)

| # | Node Name | Type | Purpose |
|---|-----------|------|---------|
| 1 | Webhook: Query Vector DB | n8n-nodes-base.webhook | Receive query request |
| 2 | Code: Generate IDs | n8n-nodes-base.code | tool_call_id, validation |
| 3 | PostgreSQL: Insert Record | n8n-nodes-base.postgres | Track execution |
| 4 | HTTP: Gate 1 Callback | n8n-nodes-base.httpRequest | Progress notification |
| 5 | IF: Check Cancel | n8n-nodes-base.if | Cancel branch |
| 6 | PostgreSQL: Update Cancelled | n8n-nodes-base.postgres | Mark cancelled |
| 7 | Embeddings Gemini | @n8n/n8n-nodes-langchain.embeddingsGoogleGemini | Query to vector |
| 8 | Pinecone Retrieve | @n8n/n8n-nodes-langchain.vectorStorePinecone | Search vectors |
| 9 | Code: Format Results | n8n-nodes-base.code | Voice-friendly output |
| 10 | PostgreSQL: Update Completed | n8n-nodes-base.postgres | Mark completed |
| 11 | HTTP: Gate 2 Callback | n8n-nodes-base.httpRequest | Completion notification |
| 12 | Code: Build Response | n8n-nodes-base.code | Format voice_response |
| 13 | Respond to Webhook | n8n-nodes-base.respondToWebhook | Return result |
| 14 | Sticky Note | n8n-nodes-base.stickyNote | Documentation |

---

## Shared Infrastructure

### PostgreSQL Schema
Uses existing `tool_calls` table from voice agent architecture:

```sql
CREATE TABLE tool_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tool_call_id VARCHAR(100) UNIQUE NOT NULL,
    session_id VARCHAR(100) NOT NULL,
    intent_id VARCHAR(100),
    function_name VARCHAR(100) NOT NULL,  -- 'add_to_vector_db' or 'query_vector_db'
    parameters JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(20) NOT NULL DEFAULT 'EXECUTING',
    result JSONB,
    error_message TEXT,
    voice_response TEXT,
    callback_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    execution_time_ms INTEGER,
    -- Vector DB specific fields (in result JSONB)
    -- For add: { chunks_stored: N, content_length: N }
    -- For query: { results_count: N, top_results: [...] }
    CONSTRAINT valid_status CHECK (
        status IN ('EXECUTING', 'COMPLETED', 'FAILED', 'CANCELLED')
    )
);
```

### Credentials Required

| Credential | Purpose | ID (from reference) |
|------------|---------|---------------------|
| Google Gemini API | Embeddings | `mVh9oGzTvuTD7mxB` |
| Pinecone | Vector storage | `GAblF7Hlg8tSKQlW` |
| PostgreSQL | Status tracking | (existing from send-gmail workflow) |

### Pinecone Index
- **Index Name**: `resume-review-autopayplus`
- **Embedding Dimension**: Matches Google Gemini output
- **Metadata Schema**: `{ source, category, added_by, timestamp }`

---

## Callback Payload Specifications

### Add Workflow - Gate 1 (Progress)
```json
{
  "status": "PREPARING",
  "gate": 1,
  "tool_call_id": "tc_add_xxx",
  "function_name": "add_to_vector_db",
  "cancellable": true,
  "message": "I'll add this information to the knowledge base. This will store {content_length} characters.",
  "voice_response": "I'll add this information to the knowledge base."
}
```

### Add Workflow - Gate 2 (Confirmation)
```json
{
  "status": "READY_TO_STORE",
  "gate": 2,
  "tool_call_id": "tc_add_xxx",
  "requires_confirmation": true,
  "cancellable": true,
  "message": "Ready to store {chunk_count} chunks under category '{category}'. Confirm to proceed?",
  "voice_response": "Ready to store the information. Should I proceed?"
}
```

### Add Workflow - Gate 3 (Completion)
```json
{
  "status": "COMPLETED",
  "gate": 3,
  "tool_call_id": "tc_add_xxx",
  "result": {
    "chunks_stored": 5,
    "content_length": 4500,
    "category": "policies"
  },
  "voice_response": "Successfully stored 5 chunks in the knowledge base under the policies category.",
  "execution_time_ms": 2340
}
```

### Query Workflow - Gate 1 (Progress)
```json
{
  "status": "SEARCHING",
  "gate": 1,
  "tool_call_id": "tc_query_xxx",
  "function_name": "query_vector_db",
  "cancellable": true,
  "message": "Searching the knowledge base for: {query_preview}",
  "voice_response": "Searching the knowledge base..."
}
```

### Query Workflow - Gate 2 (Completion)
```json
{
  "status": "COMPLETED",
  "gate": 2,
  "tool_call_id": "tc_query_xxx",
  "result": {
    "results_count": 3,
    "top_results": [
      { "score": 0.92, "content_preview": "The vacation policy states..." },
      { "score": 0.87, "content_preview": "Employees are entitled to..." },
      { "score": 0.81, "content_preview": "Requests must be submitted..." }
    ]
  },
  "voice_response": "I found 3 relevant results. The vacation policy states that employees are entitled to 15 days of paid leave annually. Requests must be submitted at least 2 weeks in advance.",
  "execution_time_ms": 890
}
```

---

## LiveKit Agent Tool Definitions

### add_to_knowledge_base Tool
```python
@llm.function_tool(
    name="add_to_knowledge_base",
    description="Add information to the knowledge base. Use when user asks to remember, store, or save information for later. ALWAYS confirm before storing."
)
async def add_to_knowledge_base_tool(
    content: str,
    category: str = "general",
    source: str = "voice_conversation"
) -> str:
    """Add content to vector database.

    Args:
        content: The text content to store
        category: Topic category (general, policies, procedures, contacts, etc.)
        source: Where this information came from
    """
    response = await http_client.post(
        f"{N8N_WEBHOOK_BASE}/add-to-vector-db",
        json={
            "session_id": session_id,
            "callback_url": f"{CALLBACK_BASE}/tool-progress",
            "content": content,
            "metadata": {
                "source": source,
                "category": category,
                "added_by": "voice_agent"
            }
        }
    )
    return response.json().get("voice_response", "Information stored.")
```

### query_knowledge_base Tool
```python
@llm.function_tool(
    name="query_knowledge_base",
    description="Search the knowledge base for information. Use when user asks about policies, procedures, or previously stored information."
)
async def query_knowledge_base_tool(
    query: str,
    top_k: int = 5
) -> str:
    """Query vector database for relevant information.

    Args:
        query: The search query
        top_k: Number of results to retrieve (default: 5)
    """
    response = await http_client.post(
        f"{N8N_WEBHOOK_BASE}/query-vector-db",
        json={
            "session_id": session_id,
            "callback_url": f"{CALLBACK_BASE}/tool-progress",
            "query": query,
            "top_k": top_k
        }
    )
    return response.json().get("voice_response", "No results found.")
```

---

## Design Decisions

### Why 3 Gates for Add, 2 Gates for Query?

**Add Operation (3 Gates)**:
- Gate 1: Initial acknowledgment (cancellable during prep)
- Gate 2: Confirmation before irreversible storage
- Gate 3: Completion notification

**Query Operation (2 Gates)**:
- Gate 1: Search in progress (brief cancel window)
- Gate 2: Results delivery (no confirmation needed - read-only)

Query is non-destructive, so no confirmation gate is required.

### Why Not Use AI Agent for Query?

The reference workflow uses an AI Agent for queries, but for the voice tool:
- Voice agent already has LLM (Groq) for response formatting
- Direct retrieval is faster (~500ms vs ~1500ms with agent)
- Voice agent can interpret results and ask follow-up questions

### Chunking Strategy

Using reference workflow settings:
- Chunk size: ~1000 characters (default)
- Overlap: 100 characters (preserves context across boundaries)
- Splitter: Recursive Character (handles paragraphs, sentences, words)

---

## Error Handling

### Add Workflow Errors
| Error | Handling | Voice Response |
|-------|----------|----------------|
| Empty content | Reject at Code node | "I need some content to store. What would you like me to remember?" |
| Embedding failed | PostgreSQL: FAILED | "I couldn't process that information. Please try again." |
| Pinecone timeout | Retry once, then FAILED | "The storage system is slow. Let me try again." |
| Content too long | Split into multiple adds | "That's quite long. I'll store it in multiple parts." |

### Query Workflow Errors
| Error | Handling | Voice Response |
|-------|----------|----------------|
| Empty query | Reject at Code node | "What would you like me to search for?" |
| No results | Return empty gracefully | "I couldn't find anything matching that query." |
| Pinecone timeout | Retry once, then partial | "The search is taking longer than expected." |

---

## Testing Payloads

See `test-payloads/` folder for sample requests.
