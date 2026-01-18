# Query Vector DB - Quick Start Implementation

**Status:** Ready to implement
**Based On:** Voice Tool: Send Gmail (kBuTRrXTJF1EEBEs)
**Template Files:** See file references below

---

## Step 1: Database Setup (5 minutes)

### 1.1 Connect to PostgreSQL
```bash
psql -h your-db-host -U your-user -d your-database
```

### 1.2 Install pgvector Extension
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### 1.3 Create Documents Table
```sql
CREATE TABLE documents (
  id SERIAL PRIMARY KEY,
  content TEXT NOT NULL,
  category VARCHAR(100),
  source VARCHAR(255),
  metadata JSONB,
  embedding vector(1536),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);
```

### 1.4 Create Vector Index
```sql
CREATE INDEX idx_documents_embedding
ON documents USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

ANALYZE documents;
```

### 1.5 Insert Sample Data (Optional)
Use OpenAI API to generate embeddings, then insert:
```sql
INSERT INTO documents (content, category, embedding) VALUES
  ('Your document text here...', 'category', '[0.1, 0.2, ..., 1536 values]'::vector);
```

---

## Step 2: Create Workflow in n8n UI (10 minutes)

### 2.1 Create New Workflow
1. n8n Dashboard → Create New Workflow
2. Name: "Query Vector DB"
3. Start with blank workflow

### 2.2 Add Webhook Node
1. Add node → Core → Webhook
2. Configure:
   - Path: `query-vector-db`
   - Method: POST
   - Response Mode: responseNode
3. Click "Execute Workflow" to activate webhook

### 2.3 Copy Nodes from Send Gmail
**Simplest approach: Import from template**

```bash
# Export Send Gmail workflow
curl -X GET "https://n8n-instance/api/v1/workflows/kBuTRrXTJF1EEBEs" \
  -H "X-N8N-API-KEY: your-api-key" > send-gmail.json

# Create Query Vector DB from it
# Then customize as needed (see QUERY_VECTOR_DB_TEMPLATE_APPLICATION.md)
```

### 2.4 Node-by-Node Setup (Manual)

#### Nodes to Copy Exactly (No Changes)
1. Code: Generate ID
2. Postgres: INSERT tool_call
3. IF: Check Cancel (Gate 1)
4. IF: Check Cancel (Gate 2)
5. Postgres: UPDATE CANCELLED
6. Respond: Cancelled
7. Postgres: UPDATE COMPLETED
8. HTTP Request: Gate 3
9. Respond to Webhook

Copy-paste from Send Gmail (Ctrl+C/Cmd+C) → paste in Query Vector DB

#### Nodes to Modify (Text Only)
1. **HTTP Request: Gate 1**
   - Change message: "Preparing vector database query..."

2. **HTTP: Cancel Callback**
   - Change voice_response: "Vector database query cancelled by user."

3. **HTTP Request: Gate 2**
   - Change status: "READY_TO_QUERY"
   - Change message: "Vector query is ready. Review results limit and embedding similarity threshold."

#### Nodes to Create New
1. **Postgres: Query Vector DB** (replaces Gmail: Send)
   - Type: Postgres v2.6
   - Operation: executeQuery
   - Query: See POSTGRES_VECTOR_PATTERNS.md section 3
   - Query Replacement: See step 2.5 below

2. **Code: Format Result** (substantial changes)
   - See QUERY_VECTOR_DB_TEMPLATE_APPLICATION.md section 2.12

### 2.5 Postgres: Query Vector DB Configuration

**Node Settings:**
```
Type: n8n-nodes-base.postgres v2.6
Operation: executeQuery
Credentials: [Select your Postgres connection]
```

**Query:**
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

**Query Replacement:**
```
{{ JSON.stringify($('Code: Generate ID').first().json.parameters.embedding) }},
{{ $('Code: Generate ID').first().json.parameters.similarity_threshold || 0.8 }},
{{ $('Code: Generate ID').first().json.parameters.limit || 10 }}
```

**Retry Settings:**
```
Retry On Fail: checked
Max Tries: 3
Wait Between Tries: 1000
```

### 2.6 Code: Format Result Configuration

```javascript
const genData = $('Code: Generate ID').first().json;
const queryResults = $('Postgres: Query Vector DB').first().json;

return [{
  status: 'COMPLETED',
  tool_call_id: genData.tool_call_id,
  intent_id: genData.intent_id,
  callback_url: genData.callback_url,
  result: {
    matches: queryResults.map(row => ({
      id: row.id,
      content: row.content,
      distance: parseFloat(row.distance).toFixed(4)
    })),
    total_results: queryResults.length,
    query_params: {
      limit: genData.parameters.limit,
      threshold: genData.parameters.similarity_threshold
    }
  },
  voice_response: `Vector query found ${queryResults.length} documents matching your request.`,
  execution_time_ms: 0
}];
```

---

## Step 3: Connect Nodes (5 minutes)

### Connection Order (Must Follow)
```
Webhook
  ↓ [output 0]
Code: Generate ID
  ↓ [output 0]
Postgres: INSERT tool_call
  ↓ [output 0]
HTTP Request: Gate 1
  ↓ [output 0]
IF: Check Cancel (Gate 1)
  ├─ [TRUE branch, output 0]
  │ Postgres: UPDATE CANCELLED
  │   ↓ [output 0]
  │ HTTP: Cancel Callback
  │   ↓ [output 0]
  │ Respond: Cancelled
  │
  └─ [FALSE branch, output 1]
    HTTP Request: Gate 2
      ↓ [output 0]
    IF: Check Cancel (Gate 2)
      ├─ [TRUE branch, output 0]
      │ Postgres: UPDATE CANCELLED
      │   ↓ [output 0]
      │ HTTP: Cancel Callback
      │   ↓ [output 0]
      │ Respond: Cancelled
      │
      └─ [FALSE branch, output 1]
        Postgres: Query Vector DB
          ↓ [output 0]
        Code: Format Result
          ↓ [output 0]
        Postgres: UPDATE COMPLETED
          ↓ [output 0]
        HTTP Request: Gate 3
          ↓ [output 0]
        Respond to Webhook: Success
```

### Quick Connection Guide
1. Click Webhook node → drag from output handle to Code: Generate ID
2. Repeat for each sequential connection
3. For IF node TRUE branch: click second output handle
4. For IF node FALSE branch: click first output handle
5. Verify: View → Show Node Output on hover

---

## Step 4: Test the Workflow (10 minutes)

### 4.1 Get Webhook URL
In Webhook node, copy the URL (appears after node configuration)

### 4.2 Generate Test Embedding
```python
# Using OpenAI to generate embedding
import openai
openai.api_key = "your-api-key"

response = openai.Embedding.create(
  input="your test query text",
  model="text-embedding-3-large"  # Returns 1536 dimensions
)

embedding = response['data'][0]['embedding']  # List of 1536 floats
```

### 4.3 Test with curl
```bash
curl -X POST https://n8n-instance/webhook/query-vector-db \
  -H "Content-Type: application/json" \
  -d '{
    "intent_id": "test-001",
    "callback_url": "https://your-callback-endpoint.com/notify",
    "session_id": "session-test",
    "parameters": {
      "embedding": [0.1, -0.2, 0.3, ..., 1536 values total],
      "similarity_threshold": 0.8,
      "limit": 10
    }
  }'
```

### 4.4 Expected Response Sequence
1. Workflow receives request
2. INSERT creates tool_call record with status 'EXECUTING'
3. POST to callback_url: `{status: 'PREPARING', gate: 1, ...}`
4. Wait for callback response with cancel flag
5. If cancel: FALSE, continue to Gate 2
6. POST to callback_url: `{status: 'READY_TO_QUERY', gate: 2, ...}`
7. Wait for callback response
8. If cancel: FALSE, execute Postgres vector query
9. Format results
10. UPDATE tool_calls status to 'COMPLETED'
11. POST to callback_url: `{status: 'COMPLETED', gate: 3, result: {...}}`
12. Return webhook response

### 4.5 Troubleshooting
**Issue: Workflow never completes**
- Check callback_url is reachable (should respond 200)
- Check timeout settings (10s for Gate 1, 35s for Gate 2)
- Verify Postgres connection

**Issue: Vector query returns no results**
- Check embedding is correct format (array of 1536 floats)
- Verify documents exist: `SELECT count(*) FROM documents;`
- Test query directly in psql
- Reduce similarity_threshold to 1.5

**Issue: Expression errors in nodes**
- Check node references: `$('Code: Generate ID')` must match exact node name
- Verify JSON syntax in Code nodes
- Use Expression Editor (gear icon) to test expressions

---

## Step 5: Production Deployment (5 minutes)

### 5.1 Pre-Deployment Checklist
- [ ] Database created with pgvector extension
- [ ] Vector index created and analyzed
- [ ] Postgres credentials added to n8n
- [ ] Webhook path configured: `query-vector-db`
- [ ] All node configurations reviewed
- [ ] Test execution successful
- [ ] Error handling paths validated
- [ ] Callback URL accessible from n8n instance

### 5.2 Activate Workflow
1. Click "Save" in n8n editor
2. Click "Activate" toggle (top right)
3. Verify: Status shows "Active"

### 5.3 Monitor Execution
1. Click "Executions" tab
2. Watch for incoming requests
3. Verify: status → 'EXECUTING' → 'COMPLETED' or 'CANCELLED'
4. Check: results table populated

### 5.4 Performance Optimization
1. Monitor slow queries: Check pgSQL execution logs
2. If needed, add more IVFFlat lists:
   ```sql
   REINDEX INDEX idx_documents_embedding;
   ```
3. Archive old documents to separate table
4. Update index statistics regularly:
   ```sql
   ANALYZE documents;
   ```

---

## Step 6: Integration with Voice Agent (Optional)

### 6.1 Voice Agent Config
Update your voice agent to call the webhook:
```python
# In your voice agent code
import requests

response = requests.post(
  'https://n8n-instance/webhook/query-vector-db',
  json={
    'intent_id': intent_id,
    'callback_url': callback_endpoint,
    'session_id': session_id,
    'parameters': {
      'embedding': user_query_embedding,
      'similarity_threshold': 0.8,
      'limit': 5
    }
  }
)
```

### 6.2 Callback Handler
Implement callback handler to receive gate notifications:
```python
@app.route('/notify', methods=['POST'])
def handle_gate_callback():
  data = request.json
  gate = data.get('gate')
  status = data.get('status')

  if gate == 1:
    # User interaction: prepare
    return {'cancel': False}  # or True to cancel
  elif gate == 2:
    # User interaction: confirm
    return {'cancel': False}  # or True to cancel
  elif gate == 3:
    # Results received
    results = data.get('result', {}).get('matches', [])
    voice_response = data.get('voice_response')
    # Update UI with results
    return {'acknowledged': True}
```

---

## Reference Documents

### Complete Documentation
1. **GATED_EXECUTION_TEMPLATE.md** - Full pattern explanation
2. **QUERY_VECTOR_DB_TEMPLATE_APPLICATION.md** - Node-by-node configuration
3. **POSTGRES_VECTOR_PATTERNS.md** - PostgreSQL vector queries
4. **QUERY_VECTOR_DB_QUICKSTART.md** - This file

### File Locations
```
/Users/jelalconnor/CODING/N8N/Workflows/.claude/
├── GATED_EXECUTION_TEMPLATE.md                    (source pattern)
├── QUERY_VECTOR_DB_TEMPLATE_APPLICATION.md        (adaptation guide)
├── POSTGRES_VECTOR_PATTERNS.md                    (vector queries)
└── QUERY_VECTOR_DB_QUICKSTART.md                  (this file)
```

### Pattern Index
Update `.claude/patterns/pattern-index.json`:
```json
{
  "node_type_mappings": {
    "n8n-nodes-base.postgres": [
      "error-handling/postgres-query-replacement.md",
      "api-integration/vector-similarity-search.md"
    ]
  },
  "task_mappings": {
    "vector_database_query": [
      "workflow-architecture/gated-execution-callbacks.md"
    ]
  }
}
```

---

## Validation Checklist (Before Activation)

- [ ] Webhook node responds to test POST
- [ ] Code: Generate ID outputs tool_call_id, callback_url, parameters
- [ ] Postgres: INSERT succeeds (check tool_calls table)
- [ ] Gate 1 callback reaches callback_url
- [ ] IF node correctly detects cancel flag (test both true/false)
- [ ] Gate 2 callback reaches callback_url
- [ ] Postgres: Query Vector DB executes and returns results
- [ ] Code: Format Result transforms results correctly
- [ ] Postgres: UPDATE COMPLETED updates status
- [ ] Gate 3 callback sends completion notification
- [ ] Webhook responds with final result
- [ ] Error paths work (cancel at Gate 1 and Gate 2)
- [ ] Retry logic functions (test connection failure)

---

## Performance Expectations

### Query Latency
- Small dataset (10K docs): 5-10ms
- Medium dataset (100K docs): 10-50ms
- Large dataset (1M docs): 50-200ms
- Huge dataset (10M+ docs): 200-500ms+

### Workflow Duration (End-to-End)
- Database query: 10-100ms
- Gate 1 roundtrip: 100-500ms (user interaction)
- Gate 2 roundtrip: 500-2000ms (user review)
- Total: 1-3 seconds

### Database Load
- Single query: ~5% CPU
- Concurrent queries (10): ~30% CPU
- Index size: ~3-5x embedding table size

---

## Support & Troubleshooting

### Common Issues
| Issue | Cause | Solution |
|-------|-------|----------|
| "invalid input syntax for type vector" | Embedding format wrong | Use JSON.stringify() |
| Timeout at Gate 2 | User not responding | Increase timeout to 60s |
| No results from query | Threshold too strict | Reduce similarity_threshold |
| Slow queries (>200ms) | Missing index | Run ANALYZE or REINDEX |
| Duplicate cancellations | Race condition | Add DB constraint |

### Debug Mode
Enable detailed logging in n8n:
1. Workflow → Settings → Save Execution Data
2. View → Show Node Output → All nodes
3. Executions → Click execution → See raw data

### Performance Profiling
```sql
-- Enable slow query log
ALTER SYSTEM SET log_min_duration_statement = 100; -- Log queries > 100ms
SELECT pg_reload_conf();

-- View logs
tail -f /var/log/postgresql/postgresql.log | grep 'duration:'
```

---

## Next Steps

1. **Complete Steps 1-3:** Database + workflow setup (20 minutes)
2. **Complete Step 4:** Local testing (10 minutes)
3. **Complete Step 5:** Production activation (5 minutes)
4. **Monitor:** First 24 hours of production
5. **Optimize:** Adjust timeouts/thresholds based on real usage

---

**Ready to implement? Start with Step 1: Database Setup**
