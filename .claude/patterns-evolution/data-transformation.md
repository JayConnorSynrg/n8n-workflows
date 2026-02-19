# Data Transformation Patterns
Category from agents-evolution.md | 2 entries | Workflows: prod-hr-resume-review
---

### Anti-Pattern: Using Code Node for Simple JSON Field Extraction
**What Happened:** Initial implementation used a Code node with 15 lines of JavaScript to extract email, name, and phone from resume JSON.
**Impact:**
- Workflow was harder to maintain (required JavaScript knowledge)
- Debugging required diving into code instead of visual inspection
- New team members couldn't understand workflow at a glance
**Why It Failed:** Overengineered solution. Native Set node could handle simple field extraction with expressions like `{{ $json.contact.email }}`.

### Positive Pattern: Use Set Node with Expressions for Field Extraction
**Solution:** Replaced Code node with Set node using n8n expressions
**Implementation:**
1. Deleted Code node
2. Added Set node with fields:
   - `email`: `{{ $json.contact.email }}`
   - `name`: `{{ $json.contact.firstName }} {{ $json.contact.lastName }}`
   - `phone`: `{{ $json.contact.phone }}`
3. Connected to next node in workflow

**Result:**
- Workflow execution time reduced by 50ms (Code node overhead eliminated)
- Visual clarity improved - any team member can see exactly what fields are extracted
- Easier to modify - just add another field in Set node UI

**Reusable Pattern:**
Always try Set node with expressions before reaching for Code node. Use Code only when:
- Complex conditionals that IF/Switch can't handle
- Array transformations that native nodes can't do
- External library requirements (npm packages)
```
