# Expression & Syntax Patterns
Category from agents-evolution.md | 6 entries | Workflows: AQjMRh9pqK5PebFq, MMaJkr8abEjnCM2h
---

### Anti-Pattern: HTML contentType ignores newline characters in Teams messages
**What Happened:** AI Agent produced properly structured responses with `\n` line breaks, but Microsoft Teams rendered them as one continuous paragraph. The "Create chat message" node uses `contentType: "html"`, and HTML ignores `\n` characters entirely.

**Impact:**
- All formatting (section headers, candidate separations, search suggestions) collapsed into unreadable wall of text
- Multiple iteration cycles wasted adjusting system prompts when the issue was rendering, not generation

**Why It Failed:** Knowledge gap — no documentation existed for Teams HTML rendering behavior with n8n nodes.

### Positive Pattern: Format Enforcer Code node converts newlines to HTML breaks
**Solution:** Insert a Code node ("Format Enforcer") between AI Agent and Create chat message that converts `\n\n` to `<br><br>` and `\n` to `<br>`. Also strips markdown artifacts (asterisks, backticks, hashes) since Teams renders HTML, not markdown.

**Implementation:**
1. Add Code node (n8n-nodes-base.code v2) between AI Agent and Teams reply
2. Convert double newlines to `<br><br>` (paragraph spacing)
3. Convert single newlines to `<br>` (line breaks)
4. Strip all markdown: `*`, `_`, backticks, `#` headings, bullet points
5. Normalize ALL CAPS section headers

**Result:**
- Line breaks render correctly in Microsoft Teams chat
- Section headers (TALENT POOL ASSESSMENT, STRONGEST MATCHES, RECOMMENDED NEXT SEARCH) display on separate lines
- Candidate names separated from descriptions visually

**Reusable Pattern:** Apply whenever using AI Agent → Microsoft Teams chat with contentType "html". Always convert newlines to `<br>` tags before sending.

---

### Anti-Pattern 1: AI Agent field reference mismatch with upstream Set node
**What Happened:** AI Agent prompt referenced `$('Standardize Resume Data').item.json.candidateResume` but the Standardize Resume Data (Set) node outputs the field as `resumeText`. The AI Agent received "Resume text not available" and took a shortcut path producing markdown instead of JSON.

**Impact:**
- AI saw no resume data despite it being present upstream
- Cascaded into markdown output instead of JSON
- Structured Output Parser failed, passing raw string
- ALL downstream AI fields arrived empty

**Why It Failed:** Knowledge Gap — when the Standardize Resume Data node was created, it renamed fields, but the AI Agent prompt was written referencing the original Paycor field name (`candidateResume`) instead of the standardized name (`resumeText`).

### Positive Pattern 1: Verify field names across node boundaries
**Solution:** Always trace field names from source node through Set/Code transformations to consuming node. Use the exact output field name from the immediate upstream node, not the original source field name.

**Implementation:**
1. Check the output schema of the node referenced in expressions
2. Verify field names match EXACTLY (case-sensitive)
3. When Set nodes rename fields, ALL downstream references must use the NEW name

**Reusable Pattern:**
When an AI Agent or any node references `$('NodeName').item.json.fieldName`, verify that `fieldName` exists in NodeName's output schema. Field name mismatches are silent failures — the expression returns undefined/empty, not an error.

---

### Anti-Pattern 5: Code node reads fields but omits them from return statement
**What Happened:** Prepare Email Data Code node extracted `current_title`, `years_experience`, `key_skills`, `overall_score`, and `matched_job_title` into local variables but never included them in the `return` JSON object. Email templates referenced these via `$json.current_title` etc. and got undefined.

**Impact:**
- 5 fields visible as "Not specified" or empty in both email templates
- Data existed upstream but was silently dropped at PED

**Why It Failed:** Knowledge Gap — the return statement was manually constructed and these fields were accidentally omitted. No field-level validation exists between Code node output and downstream template references.

### Positive Pattern 5: Return statement field audit against downstream consumers
**Solution:** Added the 5 missing fields to the return statement. When building Code nodes that feed email templates or other consumers, audit the return object against ALL downstream field references.

**Implementation:**
1. List ALL `$json.fieldName` references in downstream nodes (email HTML, expressions, etc.)
2. Verify EVERY referenced field exists in the Code node's return statement
3. Add any missing fields with appropriate fallbacks

**Reusable Pattern:**
Code nodes are opaque boundaries — they consume ALL upstream fields and output ONLY what's in the return statement. Any field not explicitly included in `return [{ json: { ... } }]` is permanently lost. Always audit return statements against downstream `$json.*` references. Consider adding a comment listing expected downstream consumers.

---
