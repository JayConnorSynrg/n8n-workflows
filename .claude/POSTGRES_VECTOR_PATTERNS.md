# PostgreSQL Vector Query Patterns for Query Vector DB Workflow

**Reference Implementation:** Voice Tool: Send Gmail (Postgres pattern)
**Target:** Query Vector DB workflow
**Database:** PostgreSQL with pgvector extension

---

## 1. Parameterized Query Pattern

### Pattern: Safe Parameter Replacement
**From Send Gmail INSERT:**
```sql
INSERT INTO tool_calls (
  tool_call_id, session_id, intent_id, function_name, parameters, status, callback_url, created_at
) VALUES ($1, $2, $3, 'query_vector_db', $4::jsonb, 'EXECUTING', $5, NOW()) RETURNING *;
```

**Query Replacement Expression:**
```
{{ $json.tool_call_id }},
{{ $json.session_id }},
{{ $json.intent_id }},
{{ JSON.stringify($json.parameters) }},
{{ $json.callback_url }}
```

### Why This Pattern
- **Security:** Prevents SQL injection (parameterized queries)
- **Type Safety:** Explicit type casting ($4::jsonb)
- **Clarity:** $1-$5 placeholders match replacement order
- **Reusability:** Same pattern for all Postgres nodes

### Applied to Vector Query
```sql
SELECT id, content, embedding <-> $1::vector AS distance
FROM documents
WHERE embedding <-> $1::vector < $2
ORDER BY embedding <-> $1::vector
LIMIT $3
RETURNING id, content, distance;
```

**Query Replacement Expression:**
```
{{ JSON.stringify($('Code: Generate ID').first().json.parameters.embedding) }},
{{ $('Code: Generate ID').first().json.parameters.similarity_threshold || 0.8 }},
{{ $('Code: Generate ID').first().json.parameters.limit || 10 }}
```

**Critical Notes:**
- Embedding must be JSON stringified: `JSON.stringify(array)`
- pgvector will parse the JSON string to vector type via `$1::vector`
- Default threshold 0.8 if not provided
- Default limit 10 if not provided

---

## 2. Vector Operation Operators

### Cosine Similarity (<->)
**Most Common:** Use for semantic similarity
```sql
-- Similarity search
SELECT id, content, embedding <-> query_embedding AS distance
FROM documents
ORDER BY embedding <-> query_embedding
LIMIT 10;
```

**Distance Interpretation:**
- Range: [0, 2] for unit vectors
- 0 = identical vectors (perfect match)
- 1 = orthogonal vectors (no similarity)
- 2 = opposite vectors (most different)

### Euclidean Distance (<->)
```sql
-- By default <-> uses cosine distance
-- For L2 distance, use <->
SELECT id, content, embedding <-> query_embedding AS distance
FROM documents
ORDER BY embedding <-> query_embedding
LIMIT 10;
```

### Inner Product (<#>)
**When:** Maximizing similarity (dot product)
```sql
-- Note: Inner product has opposite ordering
SELECT id, content, embedding <#> query_embedding AS similarity
FROM documents
ORDER BY embedding <#> query_embedding DESC
LIMIT 10;
```

**Implementation Note:** n8n uses cosine distance (<->) by default

---

## 3. Full Query Patterns

### Pattern A: Simple Similarity Search
**Use Case:** Find most similar documents

```sql
SELECT
  id,
  content,
  embedding <-> $1::vector AS distance
FROM documents
ORDER BY embedding <-> $1::vector
LIMIT $2
RETURNING id, content, distance;
```

**Parameters:**
1. Embedding vector (stringified JSON)
2. Limit count

**Query Replacement:**
```
{{ JSON.stringify($('Code: Generate ID').first().json.parameters.embedding) }},
{{ $('Code: Generate ID').first().json.parameters.limit || 10 }}
```

### Pattern B: Filtered Similarity Search
**Use Case:** Find similar documents within distance threshold

```sql
SELECT
  id,
  content,
  embedding <-> $1::vector AS distance
FROM documents
WHERE embedding <-> $1::vector < $2
ORDER BY embedding <-> $1::vector
LIMIT $3
RETURNING id, content, distance;
```

**Parameters:**
1. Embedding vector (stringified JSON)
2. Distance threshold (0.0-2.0)
3. Limit count

**Query Replacement:**
```
{{ JSON.stringify($('Code: Generate ID').first().json.parameters.embedding) }},
{{ $('Code: Generate ID').first().json.parameters.similarity_threshold || 0.8 }},
{{ $('Code: Generate ID').first().json.parameters.limit || 10 }}
```

### Pattern C: Filtered + Metadata Search
**Use Case:** Similar documents matching criteria

```sql
SELECT
  id,
  content,
  category,
  embedding <-> $1::vector AS distance
FROM documents
WHERE
  embedding <-> $1::vector < $2
  AND category = $3
  AND created_at > NOW() - INTERVAL '30 days'
ORDER BY embedding <-> $1::vector
LIMIT $4
RETURNING id, content, category, distance;
```

**Parameters:**
1. Embedding vector
2. Distance threshold
3. Category filter
4. Limit count

---

## 4. Index Strategy

### Required: pgvector Index
**Must create for performance:**

```sql
CREATE EXTENSION IF NOT EXISTS vector;

-- IVFFlat index (fastest, good for millions of documents)
CREATE INDEX ON documents USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- HNSW index (better quality, slower to build)
CREATE INDEX ON documents USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

**Optimization Parameters:**
- **IVFFlat `lists`**: ~sqrt(rows/1000), typical 100 for 1M docs
- **HNSW `m`**: Connection count per node, 16-64 typical
- **HNSW `ef_construction`**: Higher = better quality, slower build

### Performance Expectations
| Table Size | Index Type | Query Time |
|------------|-----------|-----------|
| 10K docs | IVFFlat | 1-5ms |
| 100K docs | IVFFlat | 5-20ms |
| 1M docs | IVFFlat | 20-100ms |
| 10M docs | HNSW | 50-200ms |

---

## 5. N8N Implementation Details

### Embedding Format (Critical)
**Input to Postgres Query:**
```javascript
// From Code: Generate ID parameters
{
  embedding: [0.123, -0.456, 0.789, ..., 1536 values],
  similarity_threshold: 0.8,
  limit: 10
}
```

**In Query Replacement (Convert to pgvector):**
```
{{ JSON.stringify($('Code: Generate ID').first().json.parameters.embedding) }}
```

**What happens:**
1. JS array: `[0.123, -0.456, ...]`
2. JSON stringified: `"[0.123, -0.456, ...]"`
3. PostgreSQL parses: `embedding <-> '...'::vector`
4. pgvector converts string → vector type

### Example Format Result Node
```javascript
const genData = $('Code: Generate ID').first().json;
const queryResults = $('Postgres: Query Vector DB').first().json;

// queryResults = [
//   { id: 1, content: "...", distance: 0.15 },
//   { id: 2, content: "...", distance: 0.23 },
//   ...
// ]

return [{
  status: 'COMPLETED',
  tool_call_id: genData.tool_call_id,
  intent_id: genData.intent_id,
  callback_url: genData.callback_url,
  result: {
    matches: queryResults.map(row => ({
      id: row.id,
      content: row.content,
      distance: parseFloat(row.distance).toFixed(4),  // 0.1500
      similarity: (1 - row.distance).toFixed(4)       // 0.8500 (inverse)
    })),
    total_results: queryResults.length,
    query_params: {
      limit: genData.parameters.limit,
      threshold: genData.parameters.similarity_threshold,
      embedding_dimension: genData.parameters.embedding.length
    },
    metadata: {
      query_type: 'cosine_similarity',
      index_used: 'ivfflat' // For monitoring
    }
  },
  voice_response: `Vector query found ${queryResults.length} matching documents. ${
    queryResults.length > 0
      ? `Top match has similarity score ${(1 - queryResults[0].distance).toFixed(2)}.`
      : 'No documents matched your query.'
  }`,
  execution_time_ms: 0
}];
```

---

## 6. Common Issues & Solutions

### Issue 1: Embedding Array Format Error
**Error:** "invalid input syntax for type vector"
**Cause:** Not stringifying the array
**Solution:**
```javascript
// WRONG
{{ $json.parameters.embedding }}

// CORRECT
{{ JSON.stringify($json.parameters.embedding) }}
```

### Issue 2: Null/Undefined in WHERE Clause
**Error:** Query fails silently
**Cause:** Optional parameters missing
**Solution:**
```sql
-- Use NULL checks
WHERE embedding <-> $1::vector < COALESCE($2, 1.0)
```

Or in n8n:
```
{{ $('Code: Generate ID').first().json.parameters.similarity_threshold || 0.8 }}
```

### Issue 3: Index Not Used (Slow Queries)
**Symptom:** Queries run in 1-2 seconds
**Diagnosis:** Check query plan
```sql
EXPLAIN ANALYZE
SELECT id, content, embedding <-> '[0.1, 0.2, ...]'::vector AS distance
FROM documents
ORDER BY embedding <-> '[0.1, 0.2, ...]'::vector
LIMIT 10;
```

**Solution:**
- Ensure index created: `CREATE INDEX ... USING ivfflat ...`
- Index must match operator: `vector_cosine_ops`
- Verify statistics: `ANALYZE documents;`

### Issue 4: Large Result Sets (Memory)
**Error:** Workflow hangs with 100K+ results
**Cause:** n8n loads full result set in memory
**Solution:**
```sql
-- Always limit results
LIMIT {{ parameters.limit || 100 }}  -- Max 1000 for safety

-- Or paginate
OFFSET {{ parameters.offset || 0 }}
LIMIT {{ parameters.limit || 100 }}
```

### Issue 5: Type Casting in Query Replacement
**Error:** "Cannot cast type numeric to vector"
**Cause:** pgvector expects specific format
**Solution:**
```sql
-- WRONG: Loses precision
{{ parameters.embedding }} AS vector

-- CORRECT: JSON → vector conversion
{{ JSON.stringify(parameters.embedding) }}::vector
```

---

## 7. Production Configuration

### Recommended Workflow Settings
```json
{
  "errorWorkflow": null,
  "executionOrder": "v1",
  "saveDataSuccessExecution": "all",
  "saveDataErrorExecution": "all",
  "saveManualExecutions": true,
  "timezone": "UTC"
}
```

### Postgres Node Retry Settings
```json
{
  "retryOnFail": true,
  "maxTries": 3,
  "waitBetweenTries": 1000
}
```

**Rationale:**
- Database connections may timeout
- Vector operations are deterministic (safe to retry)
- 3 retries covers transient network issues

### Gate Callback Retry Settings
```json
{
  "retryOnFail": true,
  "maxTries": 3,
  "waitBetweenTries": 1000  // Gate 1
  "waitBetweenTries": 2000  // Gate 2 (longer for user interaction)
}
```

---

## 8. Testing Queries

### Create Test Data
```sql
-- Install pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Create table
CREATE TABLE documents (
  id SERIAL PRIMARY KEY,
  content TEXT,
  category VARCHAR(50),
  embedding vector(1536),
  created_at TIMESTAMP DEFAULT NOW()
);

-- Insert test documents with sample embeddings
INSERT INTO documents (content, category, embedding) VALUES
  ('Sample document 1', 'tech', '[0.1, 0.2, 0.3, ...(1536 values total)]'::vector),
  ('Sample document 2', 'tech', '[0.11, 0.19, 0.31, ...(1536 values total)]'::vector),
  ('Sample document 3', 'news', '[0.5, 0.6, 0.7, ...(1536 values total)]'::vector);

-- Create index
CREATE INDEX ON documents USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);
```

### Test Query Patterns
```sql
-- Simple search
SELECT id, content, embedding <-> '[0.1, 0.2, 0.3, ...]'::vector AS distance
FROM documents
ORDER BY embedding <-> '[0.1, 0.2, 0.3, ...]'::vector
LIMIT 5;

-- Filtered search
SELECT id, content, category, embedding <-> '[0.1, 0.2, 0.3, ...]'::vector AS distance
FROM documents
WHERE embedding <-> '[0.1, 0.2, 0.3, ...]'::vector < 0.8
  AND category = 'tech'
ORDER BY embedding <-> '[0.1, 0.2, 0.3, ...]'::vector
LIMIT 10;

-- Paginated search
SELECT id, content, embedding <-> '[0.1, 0.2, 0.3, ...]'::vector AS distance
FROM documents
ORDER BY embedding <-> '[0.1, 0.2, 0.3, ...]'::vector
LIMIT 10 OFFSET 0;
```

### Benchmark Query
```sql
EXPLAIN ANALYZE
SELECT id, content, embedding <-> '[0.1, 0.2, 0.3, ...]'::vector AS distance
FROM documents
ORDER BY embedding <-> '[0.1, 0.2, 0.3, ...]'::vector
LIMIT 10;

-- Expected: Index Scan, ~1-20ms depending on table size
```

---

## 9. Schema Reference

### Full documents Table
```sql
CREATE TABLE documents (
  id SERIAL PRIMARY KEY,
  content TEXT NOT NULL,
  category VARCHAR(100),
  source VARCHAR(255),
  metadata JSONB,
  embedding vector(1536) NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),

  -- Indexes
  CONSTRAINT embedding_not_null CHECK (embedding IS NOT NULL)
);

-- Vector search index
CREATE INDEX idx_documents_embedding
ON documents USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Metadata search index (optional)
CREATE INDEX idx_documents_category ON documents(category);
CREATE INDEX idx_documents_created_at ON documents(created_at DESC);

-- Full-text search index (optional)
CREATE INDEX idx_documents_content_fts
ON documents USING GIN (to_tsvector('english', content));
```

### Query Execution Summary
```sql
-- View all indexes
SELECT * FROM pg_indexes WHERE tablename = 'documents';

-- Check index usage
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
WHERE tablename = 'documents';

-- Monitor query performance
SELECT query, calls, total_time, mean_time
FROM pg_stat_statements
WHERE query LIKE '%documents%'
ORDER BY mean_time DESC;
```

---

## 10. Migration from Send Gmail Pattern

### Shared Queries (No Changes)
- `Postgres: INSERT tool_call`
- `Postgres: UPDATE CANCELLED`
- `Postgres: UPDATE COMPLETED`

### New Query Required
- `Postgres: Query Vector DB` (replaces Gmail: Send)

### Modification Mapping
| Send Gmail | Query Vector DB | Change |
|------------|-----------------|--------|
| INSERT | INSERT | function_name only |
| Gate callbacks | Gate callbacks | message text only |
| Gmail: Send | Query Vector DB | **New query** |
| Format Result | Format Result | Output structure |
| UPDATE COMPLETED | UPDATE COMPLETED | No change |

---

## 11. Performance Optimization Checklist

- [ ] pgvector extension installed
- [ ] Vector index created (IVFFlat or HNSW)
- [ ] Index statistics updated: `ANALYZE documents;`
- [ ] LIMIT always applied (max 1000)
- [ ] Distance threshold in WHERE clause when possible
- [ ] Embedding dimension consistent (1536 for OpenAI)
- [ ] Query plans reviewed (EXPLAIN ANALYZE)
- [ ] Slow query log monitored
- [ ] Connection pooling configured
- [ ] Retry strategy implemented (3 attempts)

---

## 12. Connection from Code: Generate ID

### Expected Parameters Structure
```javascript
// From webhook request body
{
  intent_id: "intent-123",
  callback_url: "https://callback.example.com/notify",
  session_id: "session-xyz",
  parameters: {
    // These are passed to Postgres query
    embedding: [0.123, -0.456, 0.789, ..., /* 1536 values */],
    similarity_threshold: 0.8,      // Distance cutoff
    limit: 10,                      // Max results
    category: "tech"                // Optional filter
  }
}
```

### Query Replacement in Postgres Node
```
Parameters 1-3 extracted from:
{{ JSON.stringify($('Code: Generate ID').first().json.parameters.embedding) }},
{{ $('Code: Generate ID').first().json.parameters.similarity_threshold || 0.8 }},
{{ $('Code: Generate ID').first().json.parameters.limit || 10 }}
```

---

## Summary

**Key Pattern Differences:**

| Aspect | Send Gmail | Query Vector DB |
|--------|-----------|-----------------|
| Action Node | Gmail API | Postgres Query |
| Query Type | N/A | Vector similarity |
| Result Format | Message ID | Document list |
| Index Required | N/A | pgvector index |
| Primary Operator | N/A | <-> (cosine) |
| Parameter Format | To/Subject/Body | Embedding array |
| Output Rows | 1 message | 0-1000 documents |

**File Location for Reference:**
- Pattern: `/Users/jelalconnor/CODING/N8N/Workflows/.claude/GATED_EXECUTION_TEMPLATE.md`
- Application: `/Users/jelalconnor/CODING/N8N/Workflows/.claude/QUERY_VECTOR_DB_TEMPLATE_APPLICATION.md`
