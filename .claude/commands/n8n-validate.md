# N8N Workflow Validator

**Command:** `/n8n-validate [workflow-name or workflow-id]`

**Purpose:** Comprehensively validate n8n workflow structure, connections, expressions, and best practices.

---

## Execution Protocol

### Phase 1: Workflow Identification

If user provides workflow name:
```javascript
// List workflows to find ID
const workflows = await mcp__n8n-mcp__n8n_list_workflows({ limit: 100 });
const targetWorkflow = workflows.find(w => w.name.includes(workflowName));
```

If user provides workflow ID directly, use it.

If no parameter provided, ask: "Which workflow would you like to validate? (provide name or ID)"

### Phase 2: Comprehensive Validation

Run full validation:

```javascript
const validationResult = await mcp__n8n-mcp__n8n_validate_workflow({
  id: workflowId,
  options: {
    validateNodes: true,
    validateConnections: true,
    validateExpressions: true,
    profile: "runtime"
  }
});
```

### Phase 3: Analysis & Reporting

**Present results in structured format:**

```markdown
# Workflow Validation Report: {workflow-name}

**Workflow ID:** {id}
**Validated:** {timestamp}
**Overall Status:** ✅ PASS | ⚠️ WARNINGS | ❌ FAIL

---

## Summary

- **Total Nodes:** {count}
- **Total Connections:** {count}
- **Errors Found:** {count}
- **Warnings:** {count}
- **Suggestions:** {count}

---

## Critical Issues ❌

{List any errors that prevent workflow execution}

Example:
- **Node "HTTP Request 1":** Missing required parameter "url"
- **Connection:** Node "IF" output port has no connection
- **Expression:** Invalid syntax in Set node field "email": {{ $json.contact }}

---

## Warnings ⚠️

{List issues that may cause problems}

Example:
- **Node "Code":** Could be replaced with native Set node
- **Rate Limiting:** HTTP Request to API has no rate limiting
- **Error Handling:** No error branch configured on "OpenAI" node

---

## Best Practice Suggestions 💡

{List improvements based on n8n best practices}

Example:
- Consider adding retry logic to HTTP Request nodes
- Use Error Trigger for centralized error handling
- Add Sticky Notes to document complex logic
- Break workflow into sub-workflows (currently 25+ nodes)

---

## Node-by-Node Analysis

{For each node with issues}

### Node: {node-name} ({node-type})

**Issues:**
- {issue description}

**Impact:** {what could go wrong}

**Fix:** {how to resolve}

---

## Connections Analysis

**Valid Connections:** {count}
**Missing Connections:** {count}
**Circular Dependencies:** {detected or none}

{List any connection issues}

---

## Expression Validation

**Total Expressions:** {count}
**Valid:** {count}
**Invalid:** {count}

{List expression issues}

Example:
- **Node:** Set Data
- **Field:** customerEmail
- **Expression:** `{{ $json.customer.email }}`
- **Issue:** Property "customer" may be undefined
- **Suggestion:** Use `{{ $json.customer?.email || 'no-email@example.com' }}`

---

## Performance Considerations

{Analyze workflow for performance issues}

- **Sequential Operations:** {count} - Consider parallelizing if possible
- **Large Data Processing:** Detected in {node-names}
- **API Calls:** {count} external API calls per execution
- **Estimated Execution Time:** {estimate based on nodes}

---

## Security Checks

- **Hardcoded Credentials:** {detected or none}
- **Exposed Sensitive Data:** {detected or none}
- **Webhook Security:** {configured or missing}
- **Input Validation:** {present or missing}

---

## Recommendations

{Prioritized list of actions}

### High Priority 🔴
1. {Critical fix needed}
2. {Critical fix needed}

### Medium Priority 🟡
1. {Important improvement}
2. {Important improvement}

### Low Priority 🟢
1. {Nice to have optimization}
2. {Nice to have optimization}
```

### Phase 4: Auto-Fix Suggestions

If errors are found, offer auto-fix:

```javascript
const autofixPreview = await mcp__n8n-mcp__n8n_autofix_workflow({
  id: workflowId,
  applyFixes: false,  // Preview mode
  confidenceThreshold: "medium"
});
```

Present auto-fix options:

```markdown
## Auto-Fix Available 🔧

I can automatically fix {count} issues:

{List fixes with confidence levels}

1. **Fix typeVersion mismatch** (Confidence: HIGH)
   - Node: HTTP Request
   - Change: Update typeVersion from 1 to 2

2. **Add error output** (Confidence: MEDIUM)
   - Node: OpenAI
   - Change: Configure error output path

Would you like me to apply these fixes? (yes/no/selective)
```

### Phase 5: Pattern Recognition

Check against documented patterns in agents-evolution.md:

```javascript
// Read agents-evolution.md
const evolutionPatterns = await Read({ file_path: ".claude/agents-evolution.md" });

// Check if current issues match known anti-patterns
// Suggest known positive patterns
```

**Add to report:**

```markdown
## Related Patterns from Evolution Log

{If matching patterns found}

This workflow exhibits patterns similar to:
- **Anti-Pattern:** {pattern name from evolution log}
- **Recommended Solution:** {positive pattern from evolution log}
- **Reference:** See agents-evolution.md, entry dated {date}
```

### Phase 6: Comparison with Templates

If similar templates exist:

```javascript
// Search for similar workflow templates
const templates = await mcp__n8n-mcp__search_templates({
  query: "{workflow purpose keywords}"
});
```

**Suggest if found:**

```markdown
## Similar Templates Found

Your workflow is similar to these templates:
1. **{template name}** - {description}
   - Differences: {what's different}
   - Lessons: {what could be adopted}
```

---

## Validation Levels

**Quick Validation** (default):
- Node configuration
- Connection validity
- Critical expression errors

**Full Validation** (use flag `--full`):
- Everything in Quick
- Performance analysis
- Security checks
- Best practice recommendations
- Pattern matching against evolution log

**Strict Validation** (use flag `--strict`):
- Everything in Full
- Enforce naming conventions
- Require error handling on all nodes
- Enforce documentation (sticky notes)
- Check credential security

---

## Example Usage

**User:** `/n8n-validate prod-hr-resume-review`

**Assistant:**

```markdown
# Workflow Validation Report: prod-hr-resume-review

**Workflow ID:** 42
**Validated:** 2025-11-22 14:30:00
**Overall Status:** ⚠️ WARNINGS (2 issues, workflow is functional)

---

## Summary

- **Total Nodes:** 12
- **Total Connections:** 14
- **Errors Found:** 0
- **Warnings:** 2
- **Suggestions:** 3

---

## Warnings ⚠️

1. **Node "Parse Resume Text":** Using Code node for simple field extraction
   - **Impact:** Harder to maintain, debugging requires code inspection
   - **Fix:** Replace with Set node using expressions
   - **Related Pattern:** See agents-evolution.md - "Use Set Node with Expressions"

2. **Missing Error Handling:** OpenAI node has no error branch
   - **Impact:** Workflow fails without recovery if API is down
   - **Fix:** Add error branch with retry logic or fallback

---

## Best Practice Suggestions 💡

1. Add retry logic to OpenAI node (API can be rate-limited)
2. Consider extracting "email sending" logic to reusable sub-workflow
3. Add execution time logging for monitoring

---

## Auto-Fix Available 🔧

I can automatically fix 1 issue:

1. **Add error output to OpenAI node** (Confidence: HIGH)

Would you like me to apply this fix?
```

---

## Integration with Evolution Log

After validation, if issues were found and fixed, prompt:

"Would you like me to document this validation session in `.claude/agents-evolution.md`? I found patterns worth recording."

---

## Success Criteria

**Validation is complete when:**
1. Full validation report presented
2. All critical issues identified
3. Auto-fix suggestions provided (if applicable)
4. Related patterns from evolution log referenced
5. Clear action items given to user

---

**Version:** 1.0.0
**Last Updated:** 2025-11-22
