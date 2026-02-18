# AIO Tools Registry

**Last Updated:** 2026-02-06
**Version:** 1.1.0

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

### 7. File Download & Email Subworkflow
| Property | Value |
|----------|-------|
| **n8n Workflow ID** | `z61gjAE9DtszE1u2` |
| **Operation Type** | MIXED (download=READ, email=WRITE) |
| **Confirmation Required** | Yes (email operations) |
| **Security Rating** | **B** |
| **n8n Backend** | `/file-download-email` webhook |

**Supported File Types with Format-Specific Schemas:**
| File Type | MIME Type | Schema Includes |
|-----------|-----------|-----------------|
| CSV | `text/csv` | columns, row_count, sample_data |
| Excel | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | columns, row_count, sample_data |
| PDF | `application/pdf` | page_count, word_count, content_preview |
| DOCX | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | word_count, paragraph_count, content_preview |
| Images | `image/*` | width, height, format, ai_description |
| Text | `text/plain` | line_count, word_count, content |

**Operations:**
- `download` - Returns file with format-specific schema (READ)
- `email` - Sends file link via email (WRITE - requires confirmation)
- `download_and_email` - Downloads file, formats email with schema preview, sends (WRITE - requires confirmation)

**Confirmation Gate:**
- Email operations return `requires_confirmation: true` by default
- Caller must resend with `confirmed: true` to execute
- Bypassed with `requires_confirmation: false` (not recommended)

**Security Notes:**
- Confirmation gate for all WRITE operations (good)
- File metadata retrieved from database (file_id validated)
- Email recipients passed without sanitization

**Improvements Needed:**
- [ ] Add email address format validation
- [ ] Sanitize HTML in custom email_body
- [ ] Add rate limiting for email operations
- [ ] Log all email operations to audit table

**Usage Examples:**
```json
// Download with schema
{
  "operation": "download",
  "file_id": "1abc...",
  "session_id": "livekit-session-123"
}

// Email (requires confirmation)
{
  "operation": "email",
  "file_id": "1abc...",
  "email_to": "user@example.com",
  "email_subject": "Requested File",
  "confirmed": true  // Required after confirmation prompt
}

// Download and email with formatted preview
{
  "operation": "download_and_email",
  "file_id": "1abc...",
  "email_to": "user@example.com",
  "confirmed": true
}
```

---

### 8. Contact Management Tool
| Property | Value |
|----------|-------|
| **File** | `src/tools/contact_tool.py` |
| **Operation Type** | MIXED (add=WRITE, get/search=READ) |
| **Confirmation Required** | Yes (for add_contact - multi-gate) |
| **Security Rating** | **A** |
| **n8n Backend** | `/manage-contacts` webhook |
| **n8n Workflow ID** | `ng5O0VNKosn5x728` |

**Operations:**
| Operation | Type | Gates | Description |
|-----------|------|-------|-------------|
| `add_contact` | WRITE | 3 | Gate 1: confirm name, Gate 2: confirm email, Gate 3: save |
| `get_contact` | READ | 0 | Lookup by name, email, or ID |
| `search_contacts` | READ | 0 | Fuzzy search across name, email, company |

**Multi-Gate Flow for add_contact:**
1. **Gate 1 (confirm_name)**: Returns phonetic name (e.g., "J-E-L-A-L"), asks user to confirm
2. **Gate 2 (confirm_email)**: Returns email spelled out (e.g., "J-C-O-N at gmail dot com"), asks user to confirm
3. **Gate 3 (save)**: Saves to PostgreSQL `contacts` table with `email_confirmed=true`

**Security Notes:**
- Multi-gate confirmation prevents spelling errors (good)
- Structured PostgreSQL storage replaces unstructured vector DB (good)
- Email format validation via database constraint
- Session-scoped contacts

**Database Table:** `contacts`
```sql
CREATE TABLE contacts (
    id UUID PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    name_phonetic VARCHAR(255),  -- Stored for future reference
    email VARCHAR(255),
    email_confirmed BOOLEAN,     -- True after Gate 2 confirmation
    phone VARCHAR(50),
    company VARCHAR(255),
    notes TEXT,
    tags TEXT[]
);
```

**Usage Examples:**
```json
// Gate 1: Initial add request
{"operation": "add_contact", "name": "Jelal", "email": "jconrumi16@gmail.com"}
// Response: {gate: 1, voice_response: "I have the name spelled as J-E-L-A-L..."}

// Gate 2: After name confirmed
{"operation": "add_contact", "name": "Jelal", "name_confirmed": true, "email": "jconrumi16@gmail.com", "gate": 2}
// Response: {gate: 2, voice_response: "I have the email as J-C-O-N-R-U-M-I-1-6..."}

// Gate 3: After email confirmed
{"operation": "add_contact", "name": "Jelal", "name_confirmed": true, "email": "jconrumi16@gmail.com", "email_confirmed": true, "gate": 3}
// Response: {success: true, voice_response: "I've saved the contact for Jelal."}

// Get contact
{"operation": "get_contact", "query": "Jelal"}
// Response: {found: true, contact: {...}, voice_response: "Found Jelal..."}
```

---

## Security Priority Matrix

| Priority | Tool | Rating | Key Issue |
|----------|------|--------|-----------|
| 1 | Vector Store | C | No confirmation for writes |
| 2 | Email | B | No input sanitization |
| 3 | Google Drive | B | No file_id validation |
| 4 | Database | B | Query sanitization gap |
| 5 | Async Wrappers | B | Inconsistent validation |
| 6 | File Download & Email | B | Email recipient validation |
| 7 | Agent Context | A | Minor - already good |
| 8 | Contact Management | A | Multi-gate confirmation, structured storage |

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

**Tool Count:** 8 active tools
**Average Security Rating:** B+
**Highest Priority:** Vector Store (needs confirmation for writes)

**Subworkflows:**
- `z61gjAE9DtszE1u2` - File Download & Email (webhook: `/file-download-email`)
- `ng5O0VNKosn5x728` - Contact Management (webhook: `/manage-contacts`)

---

## Related Documentation

| Document | Location |
|----------|----------|
| Agent Config | `src/agent.py` |
| Tool Wrappers | `src/tools/async_wrappers.py` |
| Memory System | `src/utils/short_term_memory.py` |
| n8n Workflows | Documented in root `CLAUDE.md` |
