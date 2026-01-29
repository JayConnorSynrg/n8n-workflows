# AIO Tools Registry

**Last Updated:** 2026-01-29
**Version:** 1.0.0

Quick reference for all AIO (All-In-One) Voice Assistant tools with security assessments.

---

## Security Rating Scale

| Rating | Level | Description |
|--------|-------|-------------|
| **A** | Excellent | Minimal attack surface, proper validation, no sensitive data exposure |
| **B** | Good | Minor improvements possible, acceptable for production |
| **C** | Needs Attention | Security gaps that should be addressed |
| **D** | Critical | Significant vulnerabilities requiring immediate attention |

---

## Tool Registry

### 1. Email Tool
| Property | Value |
|----------|-------|
| **File** | `src/tools/email_tool.py` |
| **Operation Type** | WRITE |
| **Confirmation Required** | Yes |
| **Security Rating** | **B** |
| **n8n Backend** | `/email-sender` webhook |

**Security Notes:**
- Requires user confirmation before execution (good)
- Email addresses passed directly to n8n webhook
- No input sanitization on `to`, `cc`, `subject`, `body` fields

**Improvements Needed:**
- [ ] Add email address format validation
- [ ] Sanitize HTML/script content in body
- [ ] Rate limiting on send operations

---

### 2. Google Drive Tool
| Property | Value |
|----------|-------|
| **File** | `src/tools/google_drive_tool.py` |
| **Operation Type** | READ |
| **Confirmation Required** | No |
| **Security Rating** | **B** |
| **n8n Backend** | `/drive-document-repo` webhook |

**Security Notes:**
- Read-only operations (good)
- Auto-saves to short-term memory (contained within session)
- File IDs passed without validation

**Improvements Needed:**
- [ ] Validate file_id format before API call
- [ ] Add query length limits to prevent abuse
- [ ] Consider content scanning for sensitive data before memory storage

---

### 3. Database Tool
| Property | Value |
|----------|-------|
| **File** | `src/tools/database_tool.py` |
| **Operation Type** | READ |
| **Confirmation Required** | No |
| **Security Rating** | **B** |
| **n8n Backend** | `/database-query` webhook |

**Security Notes:**
- Read-only vector search operations
- Query passed to n8n which handles SQL construction
- Results stored in short-term memory

**Improvements Needed:**
- [ ] Add query sanitization layer
- [ ] Limit query complexity/length
- [ ] Add result filtering for PII

---

### 4. Vector Store Tool
| Property | Value |
|----------|-------|
| **File** | `src/tools/vector_store_tool.py` |
| **Operation Type** | WRITE |
| **Confirmation Required** | No (via async_wrappers) |
| **Security Rating** | **C** |
| **n8n Backend** | `/vector-store` webhook |

**Security Notes:**
- Stores arbitrary content to Pinecone
- No content validation or sanitization
- Category field unvalidated

**Improvements Needed:**
- [ ] Add confirmation for store operations
- [ ] Validate/sanitize content before storage
- [ ] Whitelist allowed categories
- [ ] Add content size limits

---

### 5. Agent Context Tool
| Property | Value |
|----------|-------|
| **File** | `src/tools/agent_context_tool.py` |
| **Operation Type** | READ |
| **Confirmation Required** | No |
| **Security Rating** | **A** |
| **n8n Backend** | `/agent-context` webhook |

**Security Notes:**
- Cache-first pattern reduces external calls (good)
- Read-only session context access
- Context types are validated against enum

**Improvements Needed:**
- [ ] Consider adding query sanitization (minor)

---

### 6. Async Wrappers (LLM Interface)
| Property | Value |
|----------|-------|
| **File** | `src/tools/async_wrappers.py` |
| **Operation Type** | MIXED |
| **Confirmation Required** | Per-tool basis |
| **Security Rating** | **B** |
| **n8n Backend** | Delegates to individual tools |

**Security Notes:**
- Proper WRITE/READ operation separation
- Clear tool descriptions guide LLM behavior
- Memory tools are read-only

**Improvements Needed:**
- [ ] Ensure all WRITE operations require confirmation
- [ ] Add input validation at wrapper level
- [ ] Consider rate limiting at wrapper level

---

## Security Priority Matrix

| Priority | Tool | Rating | Key Issue |
|----------|------|--------|-----------|
| 1 | Vector Store | C | No confirmation for writes |
| 2 | Email | B | No input sanitization |
| 3 | Google Drive | B | No file_id validation |
| 4 | Database | B | Query sanitization gap |
| 5 | Async Wrappers | B | Inconsistent validation |
| 6 | Agent Context | A | Minor - already good |

---

## Adding New Tools

When adding a new tool to the AIO ecosystem:

### 1. Create Tool File
```
src/tools/{tool_name}_tool.py
```

### 2. Classify Operation Type
- **READ** - Retrieves data, immediate execution
- **WRITE** - Modifies data, requires confirmation

### 3. Add to Async Wrappers
```python
@llm.function_tool(
    name="{tool_name}",
    description="""{OPERATION TYPE} - {confirmation requirement}.
    {Clear description of what tool does}.
    {How LLM should report results}.""",
)
async def {tool_name}_async(...) -> str:
    # Implementation
```

### 4. Register in ASYNC_TOOLS
```python
ASYNC_TOOLS = [
    # ... existing tools
    {tool_name}_async,
]
```

### 5. Add to This Registry
Copy template below and fill in details:

```markdown
### N. {Tool Name}
| Property | Value |
|----------|-------|
| **File** | `src/tools/{file}.py` |
| **Operation Type** | READ/WRITE |
| **Confirmation Required** | Yes/No |
| **Security Rating** | **?** |
| **n8n Backend** | `/{webhook-path}` webhook |

**Security Notes:**
- {Assessment points}

**Improvements Needed:**
- [ ] {Specific improvements}
```

### 6. Update Security Priority Matrix
Add entry with appropriate priority based on rating.

---

## Security Improvement Tracking

### Completed
- [x] Separated READ/WRITE operations (2026-01-29)
- [x] Added confirmation requirement for email sends (2026-01-29)
- [x] Implemented session-based memory (not TTL) (2026-01-29)

### In Progress
- [ ] Input validation layer for all tools
- [ ] Rate limiting implementation
- [ ] PII detection in results

### Planned
- [ ] Content scanning before memory storage
- [ ] Audit logging for all tool calls
- [ ] Anomaly detection for usage patterns

---

## Quick Reference

**When user mentions "AIO tools"** - refers to this complete tool ecosystem.

**Tool Count:** 6 active tools
**Average Security Rating:** B
**Highest Priority:** Vector Store (needs confirmation for writes)

---

## Related Documentation

| Document | Location |
|----------|----------|
| Agent Config | `src/agent.py` |
| Tool Wrappers | `src/tools/async_wrappers.py` |
| Memory System | `src/utils/short_term_memory.py` |
| n8n Workflows | Documented in root `CLAUDE.md` |
