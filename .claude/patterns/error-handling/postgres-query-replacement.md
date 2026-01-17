# Pattern: PostgreSQL queryReplacement Parameter Syntax

> **Priority**: HIGH
>
> **Workflow**: Voice Tool: Send Gmail (ID: kBuTRrXTJF1EEBEs)
>
> **Date**: 2026-01-14

---

## Anti-Pattern: Mixed Static/Dynamic Values in queryReplacement

### What Happened

When executing a PostgreSQL UPDATE statement with parameterized values via the `queryReplacement` option, the workflow failed with:

```
ERROR: there is no parameter $2
```

The queryReplacement was configured with a mix of static and dynamic values:

```json
// WRONG - Static value not wrapped in expression syntax
{
  "options": {
    "queryReplacement": "CANCELLED, {{ $('Code: Generate ID').first().json.tool_call_id }}"
  }
}
```

### Impact

- PostgreSQL query failed - UPDATE statement not executed
- Workflow stopped at the cancellation branch
- Tool call status remained in incorrect state

### Why It Failed

- n8n's queryReplacement parser expects **ALL values** to be wrapped in `{{ }}` expression syntax
- Static string `CANCELLED` was interpreted as a literal expression, not a separate parameter
- The parser didn't split it into two separate $1, $2 parameters
- Only one parameter was recognized, causing "$2 not found" error

---

## Positive Pattern: Wrap ALL Values in Expression Syntax

### Solution

Wrap **every value** in expression syntax, including static strings.

### Implementation

```json
// CORRECT - ALL values wrapped in {{ }}
{
  "operation": "executeQuery",
  "query": "UPDATE tool_calls SET status = $1, completed_at = NOW() WHERE tool_call_id = $2 RETURNING *;",
  "options": {
    "queryReplacement": "{{ 'CANCELLED' }}, {{ $('Code: Generate ID').first().json.tool_call_id }}"
  }
}
```

### Example from Working INSERT Statement

```json
// CORRECT - Reference implementation from working node
{
  "query": "INSERT INTO tool_calls (tool_call_id, session_id, intent_id, function_name, parameters, status, callback_url, created_at) VALUES ($1, $2, $3, 'send_email', $4::jsonb, 'EXECUTING', $5, NOW()) RETURNING *;",
  "options": {
    "queryReplacement": "{{ $json.tool_call_id }}, {{ $json.session_id }}, {{ $json.intent_id }}, {{ JSON.stringify($json.parameters) }}, {{ $json.callback_url }}"
  }
}
```

### Result

- Query executed successfully
- All parameters properly bound ($1, $2, etc.)
- Tool call status updated correctly

---

## queryReplacement Syntax Rules

| Value Type | Syntax | Example |
|------------|--------|---------|
| Static string | `{{ 'value' }}` | `{{ 'CANCELLED' }}` |
| Dynamic field | `{{ $json.field }}` | `{{ $json.tool_call_id }}` |
| Node reference | `{{ $('NodeName').first().json.field }}` | `{{ $('Code: Generate ID').first().json.tool_call_id }}` |
| JSON stringify | `{{ JSON.stringify($json.obj) }}` | `{{ JSON.stringify($json.parameters) }}` |

---

## PostgreSQL queryReplacement Checklist

- [ ] ALL values wrapped in `{{ }}` expression syntax
- [ ] Static strings use single quotes inside: `{{ 'static' }}`
- [ ] Values separated by `, ` (comma-space)
- [ ] Number of expressions matches number of `$N` placeholders in query
- [ ] JSON fields for JSONB columns use `JSON.stringify()`
- [ ] Node references use full path: `$('NodeName').first().json.field`

---

## Related Patterns

- **IF Node Branch Routing**: Same workflow uses IF nodes for conditional flow
- **Gated Execution Callbacks**: Part of the callback-based execution pattern

---

## Key Learnings

- **Parser is strict about syntax** - n8n queryReplacement requires consistent expression wrapping
- **Static values aren't automatic** - Even constants need `{{ 'value' }}` syntax
- **Debug by comparing working nodes** - The INSERT node in the same workflow showed correct syntax
- **Test with single-parameter queries first** - Isolate the issue before complex multi-param queries

---

**Date**: 2026-01-14
**Source Pattern**: Voice Agent POC - Gated Execution Debugging Session
