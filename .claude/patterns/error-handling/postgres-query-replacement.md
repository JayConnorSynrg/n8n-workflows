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

## Anti-Pattern: Comma-Separated Values Breaking on Text Content

### What Happened (Google Drive Document Repository - 2026-01-17)

When inserting documents with comma-separated queryReplacement format:

```json
// WRONG - Breaks when extracted_text contains commas
{
  "options": {
    "queryReplacement": "={{ $json.drive_file_id }}, {{ $json.drive_folder_id }}, {{ $json.file_name }}, {{ $json.mime_type }}, {{ $json.file_size_bytes }}, {{ $json.web_view_link }}, {{ $json.extracted_text }}, {{ $json.text_length }}, {{ $json.extraction_method }}, {{ $json.drive_modified_time }}, {{ $json.extraction_status }}"
  }
}
```

### Impact

- PostgreSQL INSERT failed when `extracted_text` field contained commas
- Parameters were incorrectly split at commas within string content
- Database writes failed unpredictably based on content

### Why It Failed

- Comma-separated format is ambiguous when values contain commas
- n8n parser splits on commas, creating incorrect parameter count
- String content commas were interpreted as parameter delimiters

### Solution: Use Array Format

```json
// CORRECT - Array format handles commas in content
{
  "options": {
    "queryReplacement": "={{ [$json.drive_file_id, $json.drive_folder_id, $json.file_name, $json.mime_type, $json.file_size_bytes, $json.web_view_link, $json.extracted_text, $json.text_length, $json.extraction_method, $json.drive_modified_time, $json.extraction_status] }}"
  }
}
```

### Result

- Array format properly handles values with commas
- Each array element becomes one parameter
- No ambiguity in parameter parsing

---

## queryReplacement Syntax Rules

| Value Type | Syntax | Example |
|------------|--------|---------|
| Static string | `{{ 'value' }}` | `{{ 'CANCELLED' }}` |
| Dynamic field | `{{ $json.field }}` | `{{ $json.tool_call_id }}` |
| Node reference | `{{ $('NodeName').first().json.field }}` | `{{ $('Code: Generate ID').first().json.tool_call_id }}` |
| JSON stringify | `{{ JSON.stringify($json.obj) }}` | `{{ JSON.stringify($json.parameters) }}` |
| Array format (recommended) | `={{ [val1, val2, ...] }}` | `={{ [$json.id, $json.name] }}` |

---

## PostgreSQL queryReplacement Checklist

- [ ] Use **array format** for multi-parameter queries (prevents comma-in-content issues)
- [ ] ALL values wrapped in `{{ }}` expression syntax (if using comma-separated format)
- [ ] Static strings use single quotes inside: `{{ 'static' }}`
- [ ] Number of parameters matches number of `$N` placeholders in query
- [ ] JSON fields for JSONB columns use `JSON.stringify()`
- [ ] Node references use full path: `$('NodeName').first().json.field`
- [ ] **CRITICAL**: If any value might contain commas → ALWAYS use array format

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
