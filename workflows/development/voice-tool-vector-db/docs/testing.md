# Testing Guide: Voice Tool Vector DB Workflows

## Overview

This guide covers testing procedures for both vector database voice tools.

---

## Test Environment Setup

### Prerequisites
1. n8n instance running at `https://jayconnorexe.app.n8n.cloud`
2. Both workflows activated
3. Pinecone index `resume-review-autopayplus` accessible
4. Google Gemini API credentials active
5. PostgreSQL database with `tool_calls` table

### Callback URL Options

| Option | URL | Behavior |
|--------|-----|----------|
| No-Op (Always Continue) | `https://jayconnorexe.app.n8n.cloud/webhook/callback-noop` | Returns `{cancel: false}` |
| Manual Test | Your test server | Full control over cancel/continue |
| Skip Callbacks | `null` | Workflow errors (callback required) |

---

## Query Vector DB Tests

### Test 1: Basic Query

**Purpose:** Verify query execution and result formatting

```bash
curl -X POST https://jayconnorexe.app.n8n.cloud/webhook/query-vector-db \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-query-001",
    "callback_url": "https://jayconnorexe.app.n8n.cloud/webhook/callback-noop",
    "query": "vacation policy",
    "top_k": 5
  }'
```

**Expected Response:**
```json
{
  "status": "COMPLETED",
  "tool_call_id": "tc_query_xxx_xxx",
  "result": {
    "results_count": 3,
    "top_results": [...]
  },
  "voice_response": "I found 3 relevant results. The vacation policy states..."
}
```

### Test 2: No Results Query

**Purpose:** Verify graceful handling of empty results

```bash
curl -X POST https://jayconnorexe.app.n8n.cloud/webhook/query-vector-db \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-query-002",
    "callback_url": "https://jayconnorexe.app.n8n.cloud/webhook/callback-noop",
    "query": "xyzzy nonexistent topic 12345",
    "top_k": 5
  }'
```

**Expected Response:**
```json
{
  "status": "COMPLETED",
  "result": { "results_count": 0, "top_results": [] },
  "voice_response": "I could not find any relevant information in the knowledge base."
}
```

### Test 3: Cancel at Gate 1

**Purpose:** Verify cancellation flow works

**Setup:** Create a callback server that returns `{cancel: true}`

```bash
# Mock callback server (Node.js example)
const express = require('express');
const app = express();
app.use(express.json());
app.post('/test-callback', (req, res) => {
  console.log('Gate', req.body.gate, 'received');
  res.json({ cancel: true }); // Always cancel
});
app.listen(3000);
```

```bash
curl -X POST https://jayconnorexe.app.n8n.cloud/webhook/query-vector-db \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-query-003",
    "callback_url": "http://your-server:3000/test-callback",
    "query": "test query",
    "top_k": 3
  }'
```

**Expected Response:**
```json
{
  "status": "CANCELLED",
  "voice_response": "Search cancelled."
}
```

---

## Add to Vector DB Tests

### Test 1: Basic Add

**Purpose:** Verify content storage and chunking

```bash
curl -X POST https://jayconnorexe.app.n8n.cloud/webhook/add-to-vector-db \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-add-001",
    "callback_url": "https://jayconnorexe.app.n8n.cloud/webhook/callback-noop",
    "content": "The company remote work policy allows employees to work from home up to 3 days per week. Requests must be submitted through the HR portal at least 48 hours in advance. Managers have final approval authority.",
    "metadata": {
      "source": "hr_policy_manual",
      "category": "remote_work"
    }
  }'
```

**Expected Response:**
```json
{
  "status": "COMPLETED",
  "tool_call_id": "tc_add_xxx_xxx",
  "result": {
    "chunks_stored": 1,
    "content_length": 256,
    "category": "remote_work"
  },
  "voice_response": "Successfully stored 1 chunk in the knowledge base under the remote_work category."
}
```

### Test 2: Large Content (Multiple Chunks)

**Purpose:** Verify text splitting works correctly

```bash
# Generate large content (2500+ characters to create multiple chunks)
LARGE_CONTENT=$(cat <<EOF
The comprehensive employee benefits package includes several key components that all full-time employees are entitled to receive upon completing their 90-day probationary period.

Health Insurance: Employees can choose between three tiers of health coverage - Basic, Standard, and Premium. The Basic plan covers 60% of medical expenses with a $2000 annual deductible. The Standard plan covers 80% with a $1000 deductible. The Premium plan covers 90% with a $500 deductible. Dental and vision insurance are included in all tiers.

Retirement Benefits: The company offers a 401(k) plan with matching contributions up to 6% of salary. Vesting occurs over a 4-year period, with 25% vested each year. Employees become eligible to participate after 6 months of employment.

Paid Time Off: All employees receive 15 days of vacation, 10 sick days, and 3 personal days annually. Vacation days accrue monthly and can be carried over up to 5 days to the following year. Sick days do not carry over.

Parental Leave: Primary caregivers receive 12 weeks of paid parental leave. Secondary caregivers receive 4 weeks. Leave can be taken any time within the first year after birth or adoption.

Professional Development: Each employee has access to a $2000 annual professional development budget for courses, conferences, and certifications relevant to their role.
EOF
)

curl -X POST https://jayconnorexe.app.n8n.cloud/webhook/add-to-vector-db \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"test-add-002\",
    \"callback_url\": \"https://jayconnorexe.app.n8n.cloud/webhook/callback-noop\",
    \"content\": \"$LARGE_CONTENT\",
    \"metadata\": {
      \"source\": \"employee_handbook\",
      \"category\": \"benefits\"
    }
  }"
```

**Expected Response:**
```json
{
  "status": "COMPLETED",
  "result": {
    "chunks_stored": 3,
    "content_length": 1650,
    "category": "benefits"
  },
  "voice_response": "Successfully stored 3 chunks in the knowledge base under the benefits category."
}
```

### Test 3: Cancel at Gate 2

**Purpose:** Verify user can cancel before storage

```bash
# Use callback server that cancels only at gate 2
app.post('/test-callback', (req, res) => {
  if (req.body.gate === 2) {
    res.json({ cancel: true }); // Cancel at confirmation
  } else {
    res.json({ cancel: false }); // Continue at gate 1
  }
});
```

**Expected Response:**
```json
{
  "status": "CANCELLED",
  "voice_response": "Storage cancelled by user."
}
```

### Test 4: Empty Content Validation

**Purpose:** Verify validation rejects empty content

```bash
curl -X POST https://jayconnorexe.app.n8n.cloud/webhook/add-to-vector-db \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-add-003",
    "callback_url": "https://jayconnorexe.app.n8n.cloud/webhook/callback-noop",
    "content": "",
    "metadata": {}
  }'
```

**Expected Response:**
```json
{
  "error": "Content is required"
}
```

---

## Database Verification

### Check PostgreSQL Records

```sql
-- View recent tool calls
SELECT
  tool_call_id,
  function_name,
  status,
  voice_response,
  created_at,
  completed_at
FROM tool_calls
WHERE function_name IN ('query_vector_db', 'add_to_vector_db')
ORDER BY created_at DESC
LIMIT 10;
```

### Check Pinecone Index

Use the Pinecone console or API to verify vectors were stored:

```bash
# List vectors in index
curl "https://resume-review-autopayplus-xxx.svc.xxx.pinecone.io/describe_index_stats" \
  -H "Api-Key: YOUR_PINECONE_API_KEY"
```

---

## Integration Test: Add Then Query

**Purpose:** Verify end-to-end flow of storing and retrieving information

### Step 1: Add unique content

```bash
curl -X POST https://jayconnorexe.app.n8n.cloud/webhook/add-to-vector-db \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "integration-test-001",
    "callback_url": "https://jayconnorexe.app.n8n.cloud/webhook/callback-noop",
    "content": "The SYNRG integration test policy states that all tests must be run before deployment. Test coverage should exceed 80%. Integration tests must pass in staging environment before production deployment.",
    "metadata": {
      "source": "integration_test",
      "category": "testing_policies"
    }
  }'
```

### Step 2: Query for the content (wait 5 seconds for indexing)

```bash
sleep 5

curl -X POST https://jayconnorexe.app.n8n.cloud/webhook/query-vector-db \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "integration-test-001",
    "callback_url": "https://jayconnorexe.app.n8n.cloud/webhook/callback-noop",
    "query": "SYNRG integration test policy coverage",
    "top_k": 3
  }'
```

**Expected:** Query results should include the content just added.

---

## Performance Benchmarks

| Operation | Expected Latency | Acceptable Range |
|-----------|-----------------|------------------|
| Query (5 results) | ~800ms | 500-1500ms |
| Add (short content) | ~1200ms | 800-2000ms |
| Add (large content, 3 chunks) | ~2500ms | 1500-4000ms |

---

## Troubleshooting

### Gate Callback Timeout

**Symptom:** Workflow fails with timeout error at HTTP Request node

**Causes:**
1. Callback URL unreachable
2. Callback server slow to respond
3. Network issues

**Solution:**
- Increase timeout in HTTP Request node (currently 10s for Gate 1, 35s for Gate 2)
- Use no-op callback for testing
- Check callback server logs

### Pinecone Insert Fails

**Symptom:** Error at Pinecone Vector Store node

**Causes:**
1. Invalid API key
2. Index doesn't exist
3. Embedding dimension mismatch

**Solution:**
- Verify Pinecone credentials
- Check index exists in Pinecone console
- Ensure Google Gemini embedding model matches index configuration

### Empty Results from Query

**Symptom:** Query returns 0 results even for content that should match

**Causes:**
1. Content not yet indexed (Pinecone takes 1-5 seconds)
2. Query too specific
3. Wrong index being queried

**Solution:**
- Wait 5-10 seconds after adding content
- Try broader query terms
- Verify index name in workflow configuration
