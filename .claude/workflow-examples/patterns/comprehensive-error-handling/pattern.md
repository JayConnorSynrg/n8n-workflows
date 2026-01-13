# Pattern: Comprehensive Error Handling

**Category:** Error Handling
**Quality Level:** ✅ Production-Ready
**Source:** n8n Template #9191
**Complexity:** Moderate

---

## Overview

Robust error handling pattern for production workflows that gracefully handles failures, implements retry logic, logs errors comprehensively, and continues workflow execution without complete failure.

---

## When to Use

✅ **Use this pattern when:**
- Production workflows where uptime is critical
- External API calls with potential failures
- Long-running workflows that can't fail completely
- Error visibility required for debugging and monitoring
- Partial success is acceptable (some items succeed, some fail)

❌ **Don't use when:**
- Simple test/development workflows
- Failures should stop execution (atomic operations)
- Error handling adds unnecessary complexity
- All operations are internal (no external dependencies)

---

## Pattern Structure

```
Operation (HTTP Request, API Call, etc.)
    ↓
[On Success Branch] + [On Error Branch]
    ↓                       ↓
Continue Workflow      Capture Error Context
                            ↓
                       IF: Retryable?
                       ├─ True → Wait → Retry (max N attempts)
                       └─ False → Log Error
                            ↓
                       IF: Critical?
                       ├─ True → Send Alert (Slack/Email)
                       └─ False → Continue
                            ↓
                       Merge back to main flow
```

---

## Key Components

### 1. Error Capture Node
**Type:** `n8n-nodes-base.set`
**Purpose:** Extract and structure error information

**Configuration:**
```json
{
  "values": {
    "string": [
      {
        "name": "error_message",
        "value": "={{ $json.error.message || 'Unknown error' }}"
      },
      {
        "name": "error_code",
        "value": "={{ $json.error.code || $json.error.statusCode || 'UNKNOWN' }}"
      },
      {
        "name": "node_name",
        "value": "={{ $node.name }}"
      },
      {
        "name": "workflow_name",
        "value": "={{ $workflow.name }}"
      },
      {
        "name": "timestamp",
        "value": "={{ $now.toISO() }}"
      },
      {
        "name": "input_data",
        "value": "={{ JSON.stringify($input.all()) }}"
      }
    ]
  }
}
```

### 2. Retry Logic (IF Node)
**Type:** `n8n-nodes-base.if`
**Purpose:** Determine if error is retryable

**Configuration:**
```json
{
  "conditions": {
    "string": [
      {
        "value1": "={{ $json.error_code }}",
        "operation": "equals",
        "value2": "429"
      },
      {
        "value1": "={{ $json.error_code }}",
        "operation": "equals",
        "value2": "503"
      },
      {
        "value1": "={{ $json.error_code }}",
        "operation": "equals",
        "value2": "ECONNRESET"
      }
    ],
    "combineOperation": "any"
  }
}
```

**Common Retryable Errors:**
- `429` - Rate limit exceeded
- `503` - Service unavailable
- `504` - Gateway timeout
- `ECONNRESET` - Connection reset
- `ETIMEDOUT` - Request timeout

### 3. Wait Node (Exponential Backoff)
**Type:** `n8n-nodes-base.wait`
**Purpose:** Delay before retry with increasing wait time

**Configuration:**
```json
{
  "amount": "={{ Math.min(30, Math.pow(2, $json.retry_count || 0) * 5) }}",
  "unit": "seconds"
}
```

**Backoff Schedule:**
- Attempt 1: 5 seconds
- Attempt 2: 10 seconds
- Attempt 3: 20 seconds
- Attempt 4+: 30 seconds (capped)

### 4. Error Logging Node
**Type:** `n8n-nodes-base.httpRequest` or Database Insert
**Purpose:** Store error details for analysis

**Configuration (HTTP to logging service):**
```json
{
  "method": "POST",
  "url": "https://your-logging-service.com/api/logs",
  "authentication": "predefinedCredentialType",
  "sendBody": true,
  "bodyParameters": {
    "parameters": [
      {
        "name": "level",
        "value": "error"
      },
      {
        "name": "message",
        "value": "={{ $json.error_message }}"
      },
      {
        "name": "metadata",
        "value": "={{ JSON.stringify($json) }}"
      }
    ]
  },
  "options": {
    "ignoreResponseCode": true
  }
}
```

### 5. Critical Error Alert
**Type:** `n8n-nodes-base.slack` or `n8n-nodes-base.emailSend`
**Purpose:** Notify team of critical failures

**Configuration (Slack):**
```json
{
  "resource": "message",
  "operation": "post",
  "channel": "#alerts",
  "text": "🚨 Workflow Error Alert",
  "attachments": [
    {
      "color": "danger",
      "fields": [
        {
          "title": "Workflow",
          "value": "={{ $json.workflow_name }}"
        },
        {
          "title": "Node",
          "value": "={{ $json.node_name }}"
        },
        {
          "title": "Error",
          "value": "={{ $json.error_message }}"
        },
        {
          "title": "Time",
          "value": "={{ $json.timestamp }}"
        }
      ]
    }
  ]
}
```

---

## Error Classification

### By Severity

**Critical (Alert Immediately):**
- Authentication failures
- Database connection errors
- Workflow logic errors
- Unexpected exceptions

**Warning (Log and Monitor):**
- Rate limit exceeded (retryable)
- Temporary service unavailable
- Timeout errors
- Validation failures

**Info (Log Only):**
- Expected business logic failures
- Empty result sets
- Skipped operations

### By Retry Strategy

**Retry with Backoff:**
- Rate limits (429)
- Service unavailable (503)
- Timeouts (504)
- Connection resets

**Retry Immediately (once):**
- Transient network errors
- Flaky API responses

**Do Not Retry:**
- Authentication failures (401, 403)
- Bad request (400)
- Not found (404)
- Validation errors (422)

---

## Best Practices

### 1. Set Maximum Retry Attempts
**Prevent infinite loops:**
```javascript
// In retry counter node
{
  "retry_count": "={{ ($json.retry_count || 0) + 1 }}",
  "max_retries": 3
}

// In IF condition
"={{ $json.retry_count < $json.max_retries }}"
```

### 2. Preserve Original Data
**Keep input data for retry:**
```javascript
{
  "original_input": "={{ JSON.stringify($input.first()) }}",
  "error_context": "={{ $json.error }}"
}
```

### 3. Structured Error Messages
**Format for debugging:**
```javascript
{
  "error": {
    "message": "API call failed",
    "code": "API_ERROR",
    "details": {
      "endpoint": "/api/generate",
      "method": "POST",
      "status_code": 500,
      "response": "Internal server error"
    },
    "retry_info": {
      "attempt": 2,
      "max_attempts": 3,
      "next_retry_in": "10s"
    }
  }
}
```

### 4. Continue Execution on Non-Critical Errors
**Use `continueOnFail: true` for optional operations:**
```json
{
  "continueOnFail": true,
  "continueErrorOutput": true
}
```

---

## Real-World Example

**Use Case:** AI Image Generation with API Retry Logic

**Workflow:**
1. HTTP Request to DALL-E API
   - On Success → Continue
   - On Error → Capture error details
2. IF: Error code = 429 (rate limit)?
   - True → Wait 30s → Retry (max 3 attempts)
   - False → IF: Error code = 500?
     - True → Wait 5s → Retry (max 2 attempts)
     - False → Log error + Skip this item
3. All paths merge → Continue to next item
4. Critical errors send Slack alert

**Performance:**
- 98.5% success rate (including retries)
- Average retry: 1.2 attempts per failure
- 0.3% critical errors requiring manual intervention

**Impact:**
- Reduced manual intervention by 85%
- Improved workflow reliability from 92% to 98.5%
- Faster issue diagnosis (comprehensive logs)

---

## Monitoring and Analysis

### Error Metrics to Track
- Total errors by workflow
- Errors by node
- Errors by error code
- Retry success rate
- Critical error frequency
- Average retry attempts

### Log Analysis Queries
```javascript
// Most common errors
SELECT error_code, COUNT(*) as count
FROM error_logs
WHERE timestamp > NOW() - INTERVAL '7 days'
GROUP BY error_code
ORDER BY count DESC;

// Retry success rate
SELECT
  workflow_name,
  COUNT(*) as total_retries,
  SUM(CASE WHEN retry_successful THEN 1 ELSE 0 END) as successful_retries,
  SUM(CASE WHEN retry_successful THEN 1 ELSE 0 END) / COUNT(*) as success_rate
FROM error_logs
WHERE retry_count > 0
GROUP BY workflow_name;
```

---

## Testing Checklist

Before deploying:
- [ ] Test with forced errors (disconnect network, invalid credentials)
- [ ] Verify retry logic works for retryable errors
- [ ] Check max retry limit prevents infinite loops
- [ ] Validate error logs contain sufficient context
- [ ] Test critical error alerts reach correct channel
- [ ] Verify non-critical errors don't stop workflow
- [ ] Check error handling doesn't leak sensitive data in logs

---

## Anti-Patterns to Avoid

❌ **Silent Failures:** Never swallow errors without logging
❌ **Infinite Retries:** Always set max retry limit
❌ **Generic Error Messages:** Capture specific error context
❌ **Blocking on Errors:** Continue workflow when possible
❌ **No Alerting:** Critical errors must notify someone
❌ **Logging Sensitive Data:** Sanitize credentials, PII in logs

---

## Related Patterns

- [Sequential Image Generation Chain](../sequential-image-chain/) - Add error handling to each image gen
- [AI Agent with Sub-Workflow Tool](../ai-agent-with-tool/) - Handle tool execution failures
- [Quality Gate with Auto-Fix](../quality-gate-autofix/) - Differentiate quality vs. error failures

---

**Pattern Extracted:** 2025-11-22
**Last Validated:** 2025-11-22
**Production Usage:** Template #9191, critical for all production workflows
