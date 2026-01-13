# N8N Pattern Evolution Documenter

**Command:** `/n8n-evolve`

**Purpose:** Document successful patterns and anti-patterns in `.claude/agents-evolution.md` based on actual workflow development experiences.

---

## Core Principles

**CRITICAL RULES:**
- ✅ Only document **actual outcomes** - what really happened
- ✅ Only document **tested solutions** - what actually worked
- ❌ Never document speculative improvements
- ❌ Never document untested theories
- ❌ Never document general best practices (those go in docs)

**This command documents real development experiences, not hypothetical scenarios.**

---

## Execution Protocol

### Phase 1: Context Gathering

Ask the user structured questions:

```markdown
I'll help you document a pattern in the evolution log. Please provide:

1. **Workflow Name:** Which workflow did this happen in?
2. **Date:** When did you encounter this? (YYYY-MM-DD)
3. **Category:** Which category does this pattern fit?
   - Node Selection
   - Error Handling
   - Data Transformation
   - API Integration
   - Workflow Architecture
   - Performance Optimization

4. **What was the problem/anti-pattern?**
   - What did you try first?
   - What went wrong?
   - What was the impact?

5. **What was the solution/positive pattern?**
   - What did you change?
   - How did you implement it?
   - What was the result?

6. **Is this a reusable pattern?**
   - When should someone apply this pattern again?
   - What are the indicators that this pattern is needed?
```

### Phase 2: Validate Documentation Criteria

Before documenting, verify:

**Checklist:**
- [ ] User encountered an actual problem (not theoretical)
- [ ] User implemented a solution
- [ ] Solution was tested and confirmed working
- [ ] There's a measurable result (faster, more reliable, clearer, etc.)
- [ ] Pattern is reusable in other workflows

**If any checklist item is false:**
"This doesn't meet the criteria for evolution documentation. Evolution log is only for proven patterns from real workflow development. Would you like to note this in another way?"

### Phase 3: Read Current Evolution Log

```javascript
const evolutionContent = await Read({
  file_path: ".claude/agents-evolution.md"
});
```

Parse the content to:
- Find the correct category section
- Check if similar pattern already exists
- Get current pattern count for statistics

### Phase 4: Format the Pattern Entry

Structure the entry according to template:

```markdown
## [YYYY-MM-DD] Workflow: {workflow-name}

### Anti-Pattern: {concise descriptive title}
**What Happened:** {2-3 sentences describing what was tried and what went wrong}

**Impact:**
- {Specific impact 1}
- {Specific impact 2}
- {Specific impact 3}

**Why It Failed:** {Root cause analysis - why did this approach not work}

### Positive Pattern: {concise descriptive title}
**Solution:** {2-3 sentences describing what actually fixed it}

**Implementation:**
1. {Step-by-step what was done - action 1}
2. {Step-by-step what was done - action 2}
3. {Step-by-step what was done - action 3}

**Result:**
- {Measurable result 1 - with numbers if possible}
- {Measurable result 2}
- {Measurable result 3}

**Reusable Pattern:**
{When to apply this pattern again - specific scenarios and indicators}

**Code/Config Example:** {if applicable}
```

### Phase 5: Insert into Evolution Log

Find the appropriate category section and insert the new pattern:

```javascript
await Edit({
  file_path: ".claude/agents-evolution.md",
  old_string: "{appropriate section to append to}",
  new_string: "{section + new pattern entry}"
});
```

### Phase 6: Update Statistics

Update the pattern statistics at the bottom of the file:

```markdown
## Pattern Statistics

**Total Patterns Documented:** {new count}
**Last Updated:** {today's date}
**Categories:**
- Node Selection: {count}
- Error Handling: {count}
- Data Transformation: {count}
- API Integration: {count}
- Workflow Architecture: {count}
- Performance Optimization: {count}
```

### Phase 7: Commit to Git

Prompt user:

```markdown
Pattern documented successfully!

Would you like me to commit this to git?

Proposed commit message:
```
docs(evolution): add pattern for {category} - {brief description}

Anti-pattern: {one-line summary}
Positive pattern: {one-line summary}
Workflow: {workflow-name}
```

If yes:
```javascript
await Bash({
  command: `git add .claude/agents-evolution.md && git commit -m "docs(evolution): add pattern for {category} - {brief description}

Anti-pattern: {summary}
Positive pattern: {summary}
Workflow: {workflow-name}"`
});
```

---

## Example Interaction

**User:** `/n8n-evolve`

**Assistant:**

```markdown
I'll help you document a pattern in the evolution log. Please provide:

1. **Workflow Name:** Which workflow did this happen in?
2. **Date:** When did you encounter this? (YYYY-MM-DD)
3. **Category:** Node Selection / Error Handling / Data Transformation / API Integration / Workflow Architecture / Performance Optimization
4. **What was the problem/anti-pattern?**
5. **What was the solution/positive pattern?**
6. **Is this measurable and tested?**
```

**User:**
```
1. prod-marketing-carousel-generator
2. 2025-11-22
3. Performance Optimization
4. Used sequential HTTP Request nodes for 5 image generation API calls. Each took 10 seconds. Total workflow execution was 50+ seconds. Users were timing out.
5. Replaced with Split node → 5 parallel HTTP Request branches → Merge node. All API calls happen simultaneously. Execution time dropped to 12 seconds (10s for slowest request + 2s overhead).
6. Yes - tested with 10 carousel generations, average time went from 51s to 12s.
```

**Assistant:**

```markdown
Perfect! This meets the criteria for evolution documentation. Let me format this:

---

## [2025-11-22] Workflow: prod-marketing-carousel-generator

### Anti-Pattern: Sequential API Calls for Independent Operations
**What Happened:** Initial implementation used 5 sequential HTTP Request nodes to call image generation API for carousel slides. Each API call took ~10 seconds, resulting in 50+ second total execution time.

**Impact:**
- Users experienced timeout errors (workflow took >45 seconds)
- Poor user experience waiting for carousel generation
- Unnecessary sequential processing when API calls were independent

**Why It Failed:** Sequential execution forced each API call to wait for the previous one to complete, despite no dependencies between them. n8n can parallelize independent operations.

### Positive Pattern: Parallelize Independent API Calls with Split-Merge
**Solution:** Restructured workflow to execute all image generation API calls in parallel using Split → Parallel Branches → Merge pattern.

**Implementation:**
1. Added Split node after prompt generation to create 5 parallel paths
2. Configured HTTP Request node in each branch to call image gen API
3. Added Merge node to collect all responses
4. Each branch executes simultaneously instead of sequentially

**Result:**
- Execution time reduced from 51s to 12s (76% faster)
- User timeout errors eliminated
- Workflow can now handle peak load without delays
- Same result, 4x faster execution

**Reusable Pattern:**
Use Split-Merge parallelization whenever:
- Multiple independent API calls are needed (no data dependencies)
- Each operation takes significant time (>2-3 seconds)
- Operations can safely run concurrently (no rate limit issues)
- Order of results doesn't matter or can be re-sorted after merge

---

Would you like me to add this to .claude/agents-evolution.md and commit to git?
```

---

## Quality Checks

Before adding pattern, verify:

**Anti-Pattern Section:**
- [ ] Describes what was actually tried (not hypothetical)
- [ ] Explains specific impact (not vague "it didn't work")
- [ ] Includes root cause analysis

**Positive Pattern Section:**
- [ ] Describes tested solution (not proposal)
- [ ] Has step-by-step implementation
- [ ] Includes measurable results (numbers, metrics, observations)
- [ ] Provides reusable guidance

**Overall:**
- [ ] Based on real workflow development
- [ ] Solution was implemented and validated
- [ ] Pattern is specific enough to be actionable
- [ ] Pattern is general enough to be reusable

---

## Anti-Pattern Detection

**Do NOT document these:**

❌ "Use better error handling" (too vague, not specific)
❌ "This might work better if..." (speculative, not tested)
❌ "According to best practices..." (general knowledge, not experience)
❌ "I think this would be faster" (not measured)

**Do document these:**

✅ "Changed from X to Y, execution time dropped from 10s to 2s" (measured)
✅ "This caused 15% error rate, switching to Z eliminated errors" (tested)
✅ "Replaced Code node with Set node, maintenance time decreased by half" (observed)
✅ "Added retry logic, success rate improved from 85% to 99.5%" (measured)

---

## Integration with Other Commands

**Workflow:**
1. Build workflow with `/n8n-build`
2. Encounter issue or find optimization
3. Test solution
4. Document with `/n8n-evolve`
5. Pattern is now available for future reference

**The evolution log becomes smarter over time as you build more workflows.**

---

## Success Criteria

**Pattern documentation is complete when:**
1. Entry follows template exactly
2. Anti-pattern and positive pattern are both documented
3. Results are measurable and specific
4. Pattern is placed in correct category
5. Statistics are updated
6. User is prompted for git commit

---

**Version:** 1.0.0
**Last Updated:** 2025-11-22
