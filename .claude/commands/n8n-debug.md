# N8N Workflow Debugger

**Command:** `/n8n-debug [workflow-name or execution-id]`

**Purpose:** Debug failed or problematic n8n workflow executions with intelligent error analysis and solution suggestions.

---

## Execution Protocol

### Phase 1: Identify Target

**Option 1: Debug specific execution**
```javascript
// Get execution details
const execution = await mcp__n8n-mcp__n8n_get_execution({
  id: executionId,
  mode: "filtered",  // Start with filtered view
  itemsLimit: 5
});
```

**Option 2: Debug workflow (find recent failed executions)**
```javascript
// List recent executions for workflow
const executions = await mcp__n8n-mcp__n8n_list_executions({
  workflowId: workflowId,
  status: "error",
  limit: 10
});

// Show user the failed executions
// Let them pick which to debug
```

**Option 3: No parameter provided**
```javascript
// List all recent failed executions across all workflows
const recentFailures = await mcp__n8n-mcp__n8n_list_executions({
  status: "error",
  limit: 20
});

// Present to user for selection
```

### Phase 2: Execution Analysis

Analyze the execution data:

```markdown
# Debug Report: {workflow-name}

**Execution ID:** {executionId}
**Status:** {status}
**Started:** {startTime}
**Finished:** {finishTime}
**Duration:** {duration}

---

## Execution Flow

{Visual representation of which nodes executed}

✅ Webhook Trigger → ✅ Set Data → ✅ HTTP Request → ❌ OpenAI → ⏹️ (stopped)

**Successful Nodes:** {count}
**Failed Node:** {node name}
**Skipped Nodes:** {count} (due to failure)

---

## Error Details

**Failed at Node:** {node name} ({node type})
**Error Type:** {error type}
**Error Message:**
```
{full error message}
```

**Error Stack Trace:**
```
{stack trace if available}
```

---

## Input Data to Failed Node

{Show the data that was passed to the failed node}

```json
{
  "json": {
    "field1": "value1",
    "field2": "value2"
  },
  "binary": {}
}
```

**Potential Issues:**
- {Analysis of input data - missing fields, wrong format, etc.}
```

### Phase 3: Root Cause Analysis (5-Why Protocol - MANDATORY)

**CRITICAL**: DO NOT skip this step. Superficial fixes lead to recurring failures.

**This protocol aligns with SYNRG Error Analysis requirements.**

---

### 5-Why Analysis Process

**Perform exactly 5 iterations** to reach root cause:

```markdown
## 5-Why Root Cause Analysis

### Why 1 - Surface Symptom
**Question**: Why did the workflow fail?
**Answer**: {Specific error message or failure symptom}

**Example**: "Why did workflow fail?" → "OpenAI node returned 429 error"

---

### Why 2 - Immediate Cause
**Question**: Why did {answer from Why 1} occur?
**Answer**: {Technical immediate cause}

**Example**: "Why 429?" → "Rate limit exceeded"

---

### Why 3 - Technical Cause
**Question**: Why did {answer from Why 2} happen?
**Answer**: {Technical decision or configuration that enabled this}

**Example**: "Why rate limit exceeded?" → "5 parallel image generation calls hit API simultaneously"

---

### Why 4 - Design Cause
**Question**: Why did {answer from Why 3} happen?
**Answer**: {Design choice or architecture decision}

**Example**: "Why parallel without throttling?" → "Used Split-Merge pattern without rate limit planning"

---

### Why 5 - Root Cause (Process/Knowledge Gap)
**Question**: Why did {answer from Why 4} happen?
**Answer**: {Process failure, knowledge gap, or missing best practice}

**Example**: "Why no rate planning?" → "Didn't research API constraints before implementation"

---

## Root Cause Identified

**Category**: {Process Gap | Knowledge Gap | Tool Misuse | Design Flaw}

**Root Cause**: {Must be process/knowledge level, NOT just technical symptom}

**Example**: "Failed to research API rate limits during workflow design phase"
```

---

### Pattern Classification

After identifying root cause, **classify the failure type**:

#### Process Gap
Missing step in development workflow

**Indicators**:
- "Didn't check..."
- "Skipped validation..."
- "Deployed without testing..."

**Action**:
→ Update `.claude/CLAUDE.md` with new requirement
→ Add to Pre-Build Analysis checklist

**Example**:
```
Root Cause: Didn't research API rate limits before parallelizing
Action: Add "Research API rate limits" to mandatory Pre-Build Analysis
File: .claude/commands/n8n-build.md
```

---

#### Knowledge Gap
Unknown pattern or best practice

**Indicators**:
- "Wasn't aware of..."
- "Didn't know about..."
- "Assumed it would..."

**Action**:
→ Document in `agents-evolution.md`
→ Add to `.claude/workflow-examples/` if reusable pattern
→ Create pattern documentation

**Example**:
```
Root Cause: Didn't know Split-Merge requires rate throttling
Action: Document "parallel-api-calls-with-throttling" pattern
Pattern: Add to workflow-examples/patterns/
```

---

#### Tool Misuse
Incorrect node usage or configuration

**Indicators**:
- "Used wrong node type..."
- "Configured incorrectly..."
- "Missing required parameter..."

**Action**:
→ Update relevant command documentation
→ Add to "common mistakes" in pattern library
→ Create working example

**Example**:
```
Root Cause: Used openAi node with resource: "text" (doesn't exist)
Action: Update ai-agent pattern with common mistakes section
File: .claude/workflow-examples/patterns/ai-agent-complete/pattern.md
```

---

#### Design Flaw
Architectural or structural issue

**Indicators**:
- "Workflow architecture doesn't support..."
- "No error handling for..."
- "Missing retry logic..."

**Action**:
→ Create architectural pattern for future reference
→ Document in evolution log with solution
→ Update workflow organization guidelines

**Example**:
```
Root Cause: No retry architecture for external API failures
Action: Create "error-handling-retry" pattern with exponential backoff
Pattern: error-handling-retry (already exists - reference it)
```

---

### Complete Analysis Example

```markdown
## Workflow: prod-marketing-carousel-generator
**Failure**: 85% of executions failing with 429 errors in past 24 hours

### 5-Why Analysis

**Why 1**: Why are executions failing?
→ OpenAI DALL-E node returning 429 rate limit errors

**Why 2**: Why is rate limit being exceeded?
→ 5 parallel image generation calls per carousel, 20 carousels/hour = 100 images/hour

**Why 3**: Why are calls happening in parallel without throttling?
→ Used Split-Merge pattern for speed optimization without considering rate limits

**Why 4**: Why wasn't rate limiting planned during optimization?
→ Focused only on execution speed, didn't research OpenAI's rate limits

**Why 5**: Why wasn't API research part of optimization process?
→ Pre-Build Analysis checklist doesn't include "Research API rate limits" as mandatory step

### Root Cause Identified

**Category**: Process Gap
**Root Cause**: Missing "API rate limit research" in Pre-Build Analysis protocol
**Impact**: 85% failure rate, production workflow unusable

### Classification & Action

**Type**: Process Gap
**Action Required**:
1. Immediate fix: Add exponential backoff retry to DALL-E nodes
2. Long-term fix: Update Pre-Build Analysis checklist
3. Pattern creation: Document "parallel-api-calls-with-throttling"
4. Evolution log: Document anti-pattern and solution

**Files to Update**:
- `.claude/commands/n8n-build.md` - Add rate limit research requirement
- `.claude/agents-evolution.md` - Document this anti-pattern
- `.claude/workflow-examples/patterns/parallel-api-calls/` - Add throttling variation

### Pattern for Evolution Log

**Anti-Pattern**: Parallelizing API calls without checking rate limits
**Impact**: 85% failure rate in production
**Solution**: Research rate limits, add throttling/backoff
**Reusable**: Yes - applies to any parallel API processing
```

---

### Common Root Cause Categories

| Category | Typical Indicators | Preventive Action |
|----------|-------------------|-------------------|
| **Insufficient Research** | "Didn't check docs", "Assumed it would work" | Add research phase to workflow development |
| **Assumption Without Verification** | "Thought node existed", "Assumed configuration valid" | Require prototype analysis before building |
| **Skipped Validation** | "Deployed without testing", "No dry run" | Make validation mandatory pre-deployment |
| **Missing Error Handling** | "Didn't plan for failures", "No retry logic" | Add error planning to Pre-Build Analysis |
| **Performance Blindness** | "Didn't consider scale", "No rate limit check" | Add performance requirements to all prompts |
| **Configuration Drift** | "Worked before, now broken", "Credentials changed" | Implement configuration monitoring |
| **Dependency Failure** | "External service changed", "API deprecated" | Monitor external service health/changes |

---

### Next Steps After 5-Why Analysis

**MANDATORY - Complete ALL steps**:

1. ✅ **Fix Immediate Issue**
   - Apply technical fix to resolve current failure
   - Test fix thoroughly
   - Monitor executions after fix

2. ✅ **Document Root Cause**
   - Add execution notes with full 5-Why analysis
   - Reference in workflow documentation

3. ✅ **Check Evolution Log**
   - Search `.claude/agents-evolution.md` for similar patterns
   - If pattern exists → Reference it
   - If new pattern → Add to evolution log

4. ✅ **Update Process/Documentation**
   - If Process Gap → Update `.claude/CLAUDE.md` or commands
   - If Knowledge Gap → Add to workflow-examples patterns
   - If Tool Misuse → Update pattern library "common mistakes"
   - If Design Flaw → Create architectural pattern

5. ✅ **Prevent Recurrence**
   - Add checks to Pre-Build Analysis if applicable
   - Create pattern documentation if reusable
   - Update validation tools if detectable

**Template for Evolution Log Entry**:
```markdown
## [YYYY-MM-DD] Workflow: {workflow-name}

### Anti-Pattern: {concise description from Why 5}
**What Happened**: {detailed description of failure}
**Impact**: {what broke, metrics if available}
**Why It Failed**: {root cause from 5-Why analysis}

### Positive Pattern: {concise solution}
**Solution**: {what fixed it}
**Implementation**: {step-by-step what was done}
**Result**: {measurable improvement}
**Reusable Pattern**: {when to apply this solution again}
```

### Phase 4: Solution Suggestions

Provide specific, actionable solutions:

```markdown
## Recommended Solutions

### Solution 1: {Most likely fix} 🎯

**Problem:** {What's wrong}

**Fix:**
1. {Step-by-step fix}
2. {Step-by-step fix}
3. {Step-by-step fix}

**Why This Works:** {Explanation}

**Confidence:** HIGH | MEDIUM | LOW

---

### Solution 2: {Alternative fix}

**Problem:** {What might be wrong}

**Fix:**
1. {Step-by-step fix}
2. {Step-by-step fix}

**Why This Works:** {Explanation}

**Confidence:** MEDIUM | LOW

---

### Solution 3: {Long-shot fix}

**Problem:** {Less likely issue}

**Fix:**
1. {Step-by-step fix}

**Confidence:** LOW
```

### Phase 5: Check Evolution Log

Search agents-evolution.md for similar patterns:

```javascript
const evolutionContent = await Read({
  file_path: ".claude/agents-evolution.md"
});

// Search for similar error patterns
// Check if documented anti-pattern matches
```

**If found:**

```markdown
## Related Patterns from Evolution Log 📚

**Similar Issue Documented:**
- **Date:** {date from evolution log}
- **Workflow:** {workflow name from evolution log}
- **Anti-Pattern:** {anti-pattern title}
- **Solution:** {positive pattern solution}
- **Reference:** See `.claude/agents-evolution.md` for full details

This error matches a known pattern. The documented solution:
{summary of solution from evolution log}
```

### Phase 6: Compare with Working Executions

If workflow has successful executions, compare:

```javascript
const successfulExecution = await mcp__n8n-mcp__n8n_get_execution({
  // Find most recent successful execution
  // Compare with failed execution
});
```

**Show differences:**

```markdown
## Comparison with Successful Execution

**Successful Execution:** {executionId} (ran {time ago})

**Differences Detected:**

1. **Input Data Structure:**
   - Success: {structure}
   - Failed: {structure}
   - **Difference:** {what changed}

2. **Environment/Credentials:**
   - {Any detectable differences}

3. **External Factors:**
   - {API availability, rate limits, etc.}
```

### Phase 7: Interactive Debugging

Offer next steps:

```markdown
## Next Steps

Would you like me to:

1. **Apply suggested fix** - I can update the workflow with the recommended solution
2. **Test with sample data** - Trigger the workflow with test data to reproduce the issue
3. **Add error handling** - Add error branches to prevent this failure in the future
4. **Document pattern** - Add this to evolution log if it's a new pattern
5. **Show full execution data** - Get complete execution details for deeper analysis

Please select an option (1-5) or ask a specific question about the error.
```

---

## Error Type Specific Handlers

### HTTP Request Errors

```markdown
## HTTP Request Error Analysis

**Status Code:** {statusCode}
**URL:** {url}
**Method:** {method}

**Common Causes for {statusCode}:**
- {Specific cause for this status code}
- {Specific cause for this status code}

**Headers Sent:**
```json
{headers}
```

**Authentication:**
- Credential used: {credentialName}
- Auth type: {authType}
- **Check:** Is credential still valid?

**Recommended Fix:**
{Specific fix for HTTP errors}
```

### OpenAI / AI Node Errors

```markdown
## AI Node Error Analysis

**AI Provider:** {provider}
**Model:** {model}
**Token Count:** {if available}

**Common Causes:**
- Rate limit exceeded (check API usage)
- Invalid API key or expired credential
- Prompt too long (exceeds model context window)
- Model not accessible with current API key tier

**Prompt Sent:**
```
{prompt text}
```

**Recommended Fix:**
1. Check API key is valid in n8n credentials
2. Verify model availability (some models are restricted)
3. Add rate limiting or retry logic
4. Consider reducing prompt size if >4000 tokens
```

### Database Errors

```markdown
## Database Error Analysis

**Database Type:** {type}
**Operation:** {operation}
**Query:** {query}

**Common Causes:**
- Connection string incorrect
- Credentials don't have required permissions
- Table/column doesn't exist
- Data type mismatch
- Constraint violation (unique, foreign key)

**Query Attempted:**
```sql
{query}
```

**Recommended Fix:**
{Database-specific fix}
```

### Code Node Errors

```markdown
## Code Node Error Analysis

**Error in Code Node:** {nodeName}

**JavaScript Error:**
```
{error message}
```

**Code:**
```javascript
{code from node}
```

**Line {lineNumber}:** {problematic line}

**Common Causes:**
- Undefined variable or property
- Incorrect data structure assumption
- Missing return statement
- Async/await issue

**Recommended Fix:**
1. Add null checks: `if (data?.property)`
2. Log data structure: `console.log(JSON.stringify(items))`
3. Handle edge cases (empty arrays, null values)

**Better Approach:**
{If native nodes could replace this Code node, suggest it}
```

---

## Example Usage

**User:** `/n8n-debug prod-hr-resume-review`

**Assistant:**

```markdown
I found 3 recent failed executions for prod-hr-resume-review:

1. Execution #1247 - Failed 2 hours ago at "OpenAI" node
2. Execution #1245 - Failed 5 hours ago at "OpenAI" node
3. Execution #1240 - Failed 1 day ago at "PostgreSQL" node

Which would you like to debug? (1-3 or 'all' for pattern analysis)
```

**User:** `1`

**Assistant:**

```markdown
# Debug Report: prod-hr-resume-review

**Execution ID:** 1247
**Status:** ERROR
**Started:** 2025-11-22 12:30:15
**Duration:** 3.2 seconds
**Error:** OpenAI API rate limit exceeded

---

## Execution Flow

✅ Webhook → ✅ Extract Resume Text → ✅ Set Prompt → ❌ OpenAI Analysis → ⏹️ Stopped

**Failed at:** OpenAI Analysis (nodes-base.openAi)

---

## Error Details

**Error Message:**
```
Rate limit exceeded. You've made 60 requests in the last minute. Limit is 60/minute.
```

**Error Code:** 429 (Too Many Requests)

---

## Root Cause Analysis

### Error Pattern: API Rate Limit Exceeded

**Common Causes:**
1. **High volume of concurrent requests** - Multiple workflow executions hitting API simultaneously
2. **No rate limiting in workflow** - Workflow doesn't throttle requests
3. **API tier limitation** - Free/basic tier has strict rate limits

**Diagnostic Questions:**
- How many resume reviews are processed per minute during peak times?
- What's your OpenAI API tier?
- Are there multiple instances of this workflow running?

---

## Recommended Solutions

### Solution 1: Add Exponential Backoff Retry Logic 🎯

**Problem:** Workflow fails immediately on rate limit instead of retrying

**Fix:**
1. Add error branch to OpenAI node
2. Add "Wait" node with exponential backoff (5s, 10s, 20s)
3. Add "IF" node to check retry attempts (max 3)
4. Loop back to OpenAI or fallback to error handler

**Why This Works:** Rate limits are temporary. Retrying after a delay usually succeeds.

**Confidence:** HIGH

**Would you like me to implement this fix?**

---

### Solution 2: Implement Request Queue

**Problem:** Too many simultaneous API calls

**Fix:**
1. Add "Queue" node before OpenAI (community node: n8n-nodes-queue)
2. Configure max concurrent requests: 30/minute
3. Workflow will automatically throttle

**Confidence:** MEDIUM

---

## Related Patterns from Evolution Log 📚

No matching patterns found in evolution log yet.

**Would you like to document this after fixing?** This would be a valuable pattern for the evolution log.

---

## Next Steps

1. **Apply retry logic** (recommended) - I can update the workflow now
2. **Upgrade API tier** - Check if OpenAI tier upgrade is feasible
3. **Add rate limiting** - Prevent hitting limit in the first place
4. **Document pattern** - Add to evolution log once fixed

What would you like to do?
```

---

## Success Criteria

**Debugging is complete when:**
1. Error root cause is identified
2. Specific, actionable solutions provided
3. Evolution log checked for similar patterns
4. User has clear next steps
5. Confidence levels assigned to solutions

---

**Version:** 1.0.0
**Last Updated:** 2025-11-22
