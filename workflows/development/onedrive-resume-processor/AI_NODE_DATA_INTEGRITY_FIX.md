# AI Node Data Integrity Fix - MMaJkr8abEjnCM2h

## Date: 2026-02-12
## Workflow: Resume Analysis with AI Evaluation (PAYCOR TRIGGER)
## Issue: AI nodes inventing fake data (Jane Doe, John Doe, placeholder emails)

---

## Problem Statement

The AI nodes were fabricating candidate information when data was missing from resumes:
- Inventing names like "Jane Doe" or "John Doe" when no name was present
- Creating placeholder email addresses like "john@example.com"
- Fabricating phone numbers and job titles
- Assuming skills that weren't explicitly mentioned

This created false candidate profiles that wasted recruiter time and sabotaged hiring decisions.

---

## Solution Applied

Added **CRITICAL DATA INTEGRITY RULES** to the top of both AI node system prompts to enforce strict extraction-only behavior.

### 1. AI Recruiter Analysis Node (ID: f5aa356f-0313-4eaa-8491-0c74d511dd21)

**Updated:** `parameters.options.systemMessage`

**Added to TOP of system prompt:**

```
🔴 CRITICAL DATA INTEGRITY RULES - VIOLATION IS UNACCEPTABLE 🔴

1. EXTRACT ONLY - Never invent, assume, or fabricate ANY data
2. If a field is not explicitly stated in the resume, return "NOT FOUND" or empty - NEVER guess
3. Names MUST come directly from the resume - NEVER use placeholders like "John Doe" or "Jane Doe"
4. Contact info MUST be extracted verbatim - NEVER invent email addresses or phone numbers
5. Skills MUST be explicitly mentioned - NEVER infer or assume skills
6. Experience MUST be calculated from stated dates only - NEVER estimate
7. If the resume is blank, malformed, or unreadable, return ALL fields as "INSUFFICIENT DATA"

POSITIVE REINFORCEMENT:
✅ DO extract exactly what is written
✅ DO preserve original formatting of names, emails, phones
✅ DO return "NOT FOUND" for missing fields
✅ DO flag incomplete data rather than fill gaps

❌ NEVER invent a name when none is provided
❌ NEVER create placeholder contact information
❌ NEVER assume skills not explicitly listed
❌ NEVER fabricate job titles or experience

This system processes REAL job candidates. Invented data sabotages hiring decisions and wastes human time reviewing fake profiles.
```

**Original prompt preserved below these rules.**

---

### 2. Extract Candidate Info Node (ID: 13cb15b9-99b2-4cca-ac98-9cb318a4bbe6)

**Updated:**
- `parameters.attributes.attributes[]` - Each attribute description now includes strict extraction rules
- `parameters.options.systemMessage` - Added new system message with critical extraction rules

**New System Message:**

```
🔴 CRITICAL EXTRACTION RULES 🔴

You are extracting data from real job candidate resumes. Accuracy is MANDATORY.

RULES:
1. Extract ONLY what is explicitly written - NEVER invent data
2. If a field is missing, return 'NOT FOUND' - NEVER use placeholders
3. Preserve exact formatting from source text
4. If resume is blank or unreadable, return 'INSUFFICIENT DATA' for all fields
5. NEVER use example names like 'John Doe', 'Jane Smith', etc.
6. NEVER create placeholder emails like 'john@example.com'
7. NEVER fabricate phone numbers

This data directly impacts hiring decisions. Fake data wastes recruiter time and creates false candidate profiles.
```

**Updated Attribute Descriptions:**

| Field | Old Description | New Description |
|-------|----------------|-----------------|
| full_name | "Candidate's full name (first and last name combined)" | "Candidate's full name EXACTLY as written in resume. If no name is present, return 'NOT FOUND'. NEVER use placeholder names like 'John Doe' or 'Jane Doe'." |
| email_address | "Primary email address of the candidate" | "Email address EXACTLY as written in resume. If no email is present, return 'NOT FOUND'. NEVER invent or create email addresses." |
| phone_number | "Phone number or mobile number" | "Phone number EXACTLY as written in resume. If no phone is present, return 'NOT FOUND'. NEVER invent phone numbers." |
| current_title | "Current job title or most recent position held" | "Current job title EXACTLY as written in resume. If no current title is present, return 'NOT FOUND'. NEVER infer or assume titles." |
| years_experience | "Total years of relevant professional work experience (return as a number or string like '5 years')" | "Total years of experience calculated ONLY from explicitly stated dates in resume. If dates are not clear, return 'INSUFFICIENT DATA'. NEVER estimate or guess." |
| key_skills | "List of top 5-7 technical or professional skills mentioned in the resume, comma-separated" | "List of skills EXPLICITLY mentioned in resume, comma-separated. Extract ONLY skills that are directly stated. If no skills section exists, return 'NOT FOUND'. NEVER infer or assume skills." |

---

## MCP Operations Applied

```javascript
mcp__n8n-mcp__n8n_update_partial_workflow({
  id: "MMaJkr8abEjnCM2h",
  operations: [
    {
      type: "updateNode",
      nodeName: "AI Recruiter Analysis",
      updates: { parameters: { options: { systemMessage: "..." } } }
    },
    {
      type: "updateNode",
      nodeName: "Extract Candidate Info",
      updates: {
        parameters: {
          attributes: { attributes: [...] },
          options: { systemMessage: "..." }
        }
      }
    }
  ]
})
```

**Result:** 2 operations applied successfully

---

## Validation Results

**Workflow Status:** Active
**Validation:** Pre-existing errors in unrelated nodes (Split Candidates, Get Access Token)
**AI Nodes:** No new errors introduced
**Connections:** All valid

**Pre-existing issues (not related to this fix):**
- Split Candidates: Invalid value for 'include' parameter
- Get Access Token: Invalid value for 'specifyBody' parameter
- Split Jobs Array: Invalid value for 'include' parameter

---

## Expected Behavior After Fix

1. **When resume has complete data:** AI extracts exactly what's written
2. **When resume has missing name:** Returns "NOT FOUND" instead of "John Doe"
3. **When resume has missing email:** Returns "NOT FOUND" instead of inventing placeholder
4. **When resume has missing skills:** Returns "NOT FOUND" instead of inferring from job title
5. **When resume is blank/unreadable:** Returns "INSUFFICIENT DATA" for all fields

---

## Testing Checklist

- [ ] Test with resume containing all fields - verify exact extraction
- [ ] Test with resume missing name - verify "NOT FOUND" returned
- [ ] Test with resume missing email - verify no placeholder email created
- [ ] Test with blank resume - verify "INSUFFICIENT DATA" for all fields
- [ ] Test with resume missing skills section - verify "NOT FOUND" returned
- [ ] Verify recruiter emails show accurate data, not fake profiles

---

## Pattern Documentation

This fix establishes a **Data Integrity Enforcement Pattern** for AI extraction nodes:

### Pattern: AI Data Integrity Guards

**When:** Using AI agents to extract structured data from unstructured sources
**Risk:** LLMs will "helpfully" fabricate missing data with plausible placeholders
**Solution:** Prepend system prompt with explicit anti-fabrication rules

**Template:**
```
🔴 CRITICAL DATA INTEGRITY RULES 🔴

1. EXTRACT ONLY - Never invent, assume, or fabricate ANY data
2. If field not stated, return "NOT FOUND" - NEVER guess
3. [Domain-specific rules: no placeholder names, emails, etc.]
4. If source is invalid, return "INSUFFICIENT DATA" for ALL fields

POSITIVE REINFORCEMENT:
✅ DO extract exactly what is written
✅ DO return "NOT FOUND" for missing fields
✅ DO flag incomplete data

❌ NEVER invent data
❌ NEVER use placeholders
❌ NEVER infer missing information

This data impacts [real-world consequence]. Fake data causes [specific harm].
```

**Key Elements:**
1. Visual urgency (🔴 emoji, CAPS for critical words)
2. Numbered rules for clarity
3. Explicit examples of prohibited behavior
4. Positive reinforcement (what TO do)
5. Negative reinforcement (what NOT to do)
6. Real-world consequence explanation (why accuracy matters)

**Apply to:**
- Information Extractor nodes processing candidate resumes
- AI Agents extracting customer data from support tickets
- Document parsers processing legal/financial records
- Any AI extraction where invented data causes downstream harm

---

## Files Modified

- Workflow `MMaJkr8abEjnCM2h` - Resume Analysis with AI Evaluation (PAYCOR TRIGGER)
  - Node: AI Recruiter Analysis (f5aa356f-0313-4eaa-8491-0c74d511dd21)
  - Node: Extract Candidate Info (13cb15b9-99b2-4cca-ac98-9cb318a4bbe6)

---

## Verification Command

```bash
# Get updated workflow and verify system messages
mcp__n8n-mcp__n8n_get_workflow({ id: "MMaJkr8abEjnCM2h", mode: "full" })

# Validate workflow
mcp__n8n-mcp__n8n_validate_workflow({ id: "MMaJkr8abEjnCM2h" })
```

---

## Status: COMPLETED ✅

**Date Applied:** 2026-02-12
**Applied By:** n8n-workflow-expert agent
**Verification Status:** Pending user testing with real resume data
