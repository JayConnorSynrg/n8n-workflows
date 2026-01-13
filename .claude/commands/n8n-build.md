# N8N Workflow Builder

**Command:** `/n8n-build [workflow description]`

**Purpose:** Interactively build a new n8n workflow using native nodes first, with intelligent node suggestions and best practices.

---

## Execution Protocol

When this command is invoked, follow this structured approach:

---

### Phase 0: Pre-Build Analysis (MANDATORY - Do Not Skip)

**CRITICAL**: Before proceeding to Phase 1, complete this analysis.

**This prevents assumptions and ensures structured workflow design.**

---

#### Step 0.1: Pattern Identification

**Analyze user request and identify required patterns**:

Ask yourself:
- Does this need AI processing? → Check `ai-agent` patterns
- Multiple API calls? → Check `parallel-api-calls` pattern
- External APIs? → Check `error-handling-retry` pattern
- Image generation? → Check `image-generation-dall-e` pattern
- Database operations? → Check database patterns
- Data transformation? → Check transformation patterns

**Document identified patterns**:
```markdown
Patterns potentially needed:
- {pattern-id-1} ✅
- {pattern-id-2} ✅
- {pattern-id-3} ✅
```

---

#### Step 0.2: Load Pattern Context

**For each identified pattern**:

1. **Check if pattern exists** in `.claude/workflow-examples/patterns/`:
   - If exists → Read `pattern.md` for documentation
   - If exists → Load `pattern.json` for node structure
   - If doesn't exist → Search for similar workflows

2. **Note common mistakes**:
   - Check pattern's "common_mistakes" field
   - Review "gotchas" and "performance_notes"
   - Understand connection requirements

**Example**:
```markdown
Pattern: ai-agent-complete
Location: .claude/workflow-examples/patterns/ai-agent-complete/
Common Mistakes:
- Don't use openAi node with resource: "text" (doesn't exist)
- Must connect language model via ai_languageModel connection type
- Tools connect via ai_tool (can have multiple)
- Output parser connects via ai_outputParser (optional)

Loaded: Yes ✅
Notes: Requires 4+ nodes (agent + model + memory + tools/parser)
```

---

#### Step 0.3: Search for Similar Workflows

**Use MCP tools to find working examples**:

```javascript
// Search n8n templates
mcp__n8n-mcp__search_templates({
  query: "{user's workflow purpose}",
  limit: 5
})

// If relevant templates found, analyze top result
mcp__n8n-mcp__get_template({
  templateId: {id},
  mode: "structure"  // Get nodes + connections
})

// Search for workflows using specific nodes
mcp__n8n-mcp__list_node_templates({
  nodeTypes: ["@n8n/n8n-nodes-langchain.agent", "@n8n/n8n-nodes-langchain.openAi"]
})
```

**Document findings**:
```markdown
Similar workflows found:
- Template #{id}: "{name}"
  - Relevance: {how it relates}
  - Nodes used: {key nodes}
  - Can adapt: {what can be reused}
  - Reference: {any gotchas or lessons}

- Workflow {id}: "{name}"
  - Similarity: {what's similar}
  - Difference: {what's different}
  - Learnings: {what to apply}
```

---

#### Step 0.4: Break Down into Logical Steps

**Create step-by-step automation plan**:

```markdown
Workflow Breakdown:

**Input**: {describe input data/trigger}

**Steps**:
1. [Trigger] {trigger type}
   - Action: {what happens}
   - Data: {what data is received}
   - Validation: {what to validate}

2. [Processing] {step description}
   - Node: {tentative node type}
   - Input: {what data goes in}
   - Output: {what data comes out}
   - Error handling: {how errors are handled}

3. [Processing] {step description}
   - ...

4. [Output] {output type}
   - Action: {what happens}
   - Format: {output format}
   - Destination: {where it goes}

**Decision Points**:
- IF {condition} → {action}
- ELSE IF {condition} → {action}
- ELSE → {action}

**Data Flow**:
{Visual or text representation of data flowing through nodes}
Input → Validate → Transform → API Call → Process Response → Output

**Error Scenarios**:
- {scenario 1}: {how to handle}
- {scenario 2}: {how to handle}
```

---

#### Step 0.5: Node Selection with Verification

**For each step, select appropriate nodes**:

**Process**:
1. **Identify capability needed** for this step
2. **Search for native node**:
   ```javascript
   mcp__n8n-mcp__search_nodes({
     query: "{capability description}",
     limit: 10
   })
   ```
3. **Verify node capabilities**:
   ```javascript
   mcp__n8n-mcp__get_node_essentials({
     nodeType: "nodes-base.{selected-node}",
     includeExamples: true
   })
   ```
4. **Check pattern library** for proven configuration
5. **Document choice with reasoning**

**Example**:
```markdown
Step 2: AI text generation for prompt refinement

Capability needed: Generate refined text with AI
Search query: "AI text generation"
Found nodes:
- @n8n/n8n-nodes-langchain.agent ✅
- @n8n/n8n-nodes-langchain.lmChatOpenAi
- n8n-nodes-base.openAi

Selected: agent + lmChatOpenAi + memoryBufferWindow (3-node AI agent pattern)

Verification:
- Pattern exists: .claude/workflow-examples/patterns/ai-agent-basic/ ✅
- Documented configuration: Yes ✅
- Common mistakes noted: Yes ✅
- Working example available: Yes ✅

Reason: Proven 3-node pattern, matches requirement exactly
Alternative considered: OpenAI node directly (rejected - no conversation context)
```

**Node Selection Priority Order**:
1. ✅ Pattern from `.claude/workflow-examples/` (highest - proven structure)
2. ✅ Native n8n node (second - visual, maintainable)
3. ✅ Community node vetted (third - extended capability)
4. ⚠️ Code node (last resort - only if no native option)

---

#### Step 0.6: Plan Error Handling

**For each external service/API, plan error handling**:

```markdown
Error Handling Plan:

**Node**: {node name} ({node type})
**Service**: {external service/API}

Possible Errors:
1. {Error type} (e.g., 429 Rate Limit)
   - **Handle**: {strategy - e.g., Exponential backoff}
   - **Max retries**: {number}
   - **If still failing**: {final action}
   - **Notification**: {who/where to notify}

2. {Error type} (e.g., 500 Server Error)
   - **Handle**: {strategy}
   - **Action**: {what to do}

3. {Error type} (e.g., 400 Bad Request)
   - **Handle**: No retry (user/input error)
   - **Action**: {return error to user with details}

**Critical**: ALL external API calls MUST have error branches
```

**Error Handling Requirements** (mandatory):
- ✅ ALL external API calls must have error branches
- ✅ Retry logic for transient errors (rate limits, timeouts, 5xx errors)
- ✅ Graceful degradation where possible
- ✅ User-friendly error messages
- ✅ Error logging for debugging
- ✅ Notification on critical failures

---

#### Step 0.7: Research API Rate Limits (NEW - Added from SYNRG analysis)

**MANDATORY for workflows with external APIs**:

For each external API:
1. **Research rate limits**:
   - Requests per minute/hour/day
   - Burst limits
   - Tier-based limits

2. **Document limits**:
   ```markdown
   API: OpenAI DALL-E 3
   Rate Limit: 50 images/minute (standard tier)
   Burst: No burst allowance
   Throttling: Required for parallel processing
   ```

3. **Plan throttling strategy**:
   - Sequential processing: No throttling needed
   - Parallel processing: Add delays/batching
   - High volume: Implement queue system

**Example**:
```markdown
Workflow: Carousel Generator (5 images parallel)

OpenAI DALL-E API:
- Limit: 50 images/minute (standard tier)
- Our usage: 5 images/execution × 20 executions/hour = 100 images/hour
- Peak: 5 images in ~10 seconds = within limits ✅
- Strategy: No throttling needed (well under limit)
- Backup: If rate limited → exponential backoff retry

Action: Add retry logic with exponential backoff for 429 errors
```

---

#### Step 0.8: Present Plan to User (Required)

**Before building, show user complete plan for approval**:

```markdown
## Workflow Plan: {workflow-name}

**Purpose**: {one-sentence description}

**Patterns Used**:
1. {pattern-name} - {why this pattern}
   - Source: {where pattern comes from}
   - Nodes: {how many nodes}
   - Proven: {production-tested? yes/no}

**Workflow Structure**:
{Visual representation}
[Node1] → [Node2] → [IF condition] → [Branch A / Branch B] → [Merge] → [Output]

**Nodes Required**: {X} nodes total
- {count} {node type} - {purpose}
- {count} {node type} - {purpose}
- ...

**External Services**:
- {Service 1}: {purpose, rate limits}
- {Service 2}: {purpose, rate limits}

**Error Handling**:
- {Scenario 1} → {handling strategy}
- {Scenario 2} → {handling strategy}
- {Scenario 3} → {handling strategy}

**Performance Estimate**:
- Execution time: ~{X} seconds average
- Bottleneck: {identified bottleneck if any}
- Rate limits: {within/requires throttling}

**Complexity**: {Simple / Medium / Complex}
**Build Time Estimate**: {X} minutes
**Production Ready**: {Yes/No - what's needed for production}

**Proceed with build?**
```

**Wait for user approval** before proceeding to Phase 1.

---

**Why Phase 0 Is Mandatory**:

❌ **Without Pre-Analysis**:
- Assume node configurations exist (they don't)
- Miss existing patterns (reinvent the wheel)
- Skip error planning (fragile workflows)
- Rush to build (suboptimal architecture)
- Exceed rate limits (production failures)

✅ **With Pre-Analysis**:
- Use proven patterns (faster, reliable)
- Find working examples (no assumptions)
- Plan comprehensive error handling (robust)
- Research API constraints (no surprises)
- Present plan for approval (aligned expectations)

**This directly prevents the anti-pattern documented in `.claude/agents-evolution.md`**:
> "Always Analyze Working Examples Before Building New Workflows"

---

### Phase 1: Requirements Gathering

Ask the user clarifying questions:

1. **Workflow Purpose**
   - What is the input trigger? (Webhook, Schedule, Manual, Form, etc.)
   - What should happen? (Data transformation, API calls, notifications, etc.)
   - What is the expected output? (Database record, Webhook response, File, Email, etc.)

2. **Data Flow**
   - What data structure is coming in?
   - What external services/APIs are involved?
   - What transformations are needed?

3. **Error Handling**
   - What errors might occur?
   - How should errors be handled? (Retry, notify, log, fallback)
   - Are there rate limits to consider?

4. **Performance & Scale**
   - Expected volume? (requests/day, records/batch)
   - Any time constraints? (must respond in <Xs)
   - Will this run in production immediately?

### Phase 2: Node Discovery

Use MCP tools to find the best native nodes:

```javascript
// Search for relevant nodes
mcp__n8n-mcp__search_nodes({ query: "[user's requirement]" })

// Get node details if needed
mcp__n8n-mcp__get_node_essentials({ nodeType: "nodes-base.[nodeName]" })

// Check for templates doing similar things
mcp__n8n-mcp__search_templates({ query: "[workflow pattern]" })
```

**Prioritize:**
1. Native n8n nodes (HTTP Request, Set, IF, Switch, Merge, etc.)
2. AI nodes (OpenAI, Anthropic) if AI processing is needed
3. Integration nodes (Slack, Gmail, etc.) if those services are mentioned
4. Code nodes ONLY if absolutely necessary

### Phase 3: Workflow Design

Present the proposed workflow structure visually:

```
Example format:

Webhook Trigger
    ↓
Set (normalize incoming data)
    ↓
IF (validate required fields)
    ├─ TRUE → HTTP Request (call external API)
    │            ↓
    │         Set (transform API response)
    │            ↓
    │         OpenAI (generate summary)
    │            ↓
    │         Merge (combine all data)
    │            ↓
    │         Respond to Webhook (success)
    │
    └─ FALSE → Set (error message)
                 ↓
              Respond to Webhook (error)
```

Include:
- Node types and purposes
- Data flow direction
- Error handling branches
- Expected data transformations at each step

### Phase 4: Implementation

Create the workflow using MCP:

```javascript
mcp__n8n-mcp__n8n_create_workflow({
  name: "descriptive-workflow-name",
  nodes: [
    // Trigger node
    {
      id: "webhook",
      name: "Webhook",
      type: "n8n-nodes-base.webhook",
      typeVersion: 1,
      position: [250, 300],
      parameters: {
        path: "workflow-path",
        responseMode: "responseNode",
        options: {}
      }
    },
    // Additional nodes...
  ],
  connections: {
    "webhook": {
      "main": [[{ "node": "nextNode", "type": "main", "index": 0 }]]
    }
    // Additional connections...
  }
})
```

**Best Practices:**
- Use descriptive node names (not "HTTP Request" but "Fetch User Data from API")
- Add notes to complex nodes explaining their purpose
- Position nodes in a readable flow (left to right, top to bottom)
- Group related nodes visually
- Use sticky notes for documentation within workflow

### Phase 5: Validation

Validate the created workflow:

```javascript
mcp__n8n-mcp__n8n_validate_workflow({ id: workflowId })
```

If validation finds issues:

```javascript
mcp__n8n-mcp__n8n_autofix_workflow({
  id: workflowId,
  applyFixes: false  // Preview first
})
```

Review auto-fix suggestions with user before applying.

### Phase 6: Testing Guidance

Provide testing instructions:

1. **Manual Test:**
   - Test data to use
   - How to trigger the workflow
   - What to expect in the output
   - Where to check for errors

2. **Execution Monitoring:**
   ```javascript
   // Show how to check executions
   mcp__n8n-mcp__n8n_list_executions({ workflowId: workflowId, limit: 5 })
   ```

3. **Common Issues to Check:**
   - Credential configuration
   - Webhook URL accessibility
   - API rate limits
   - Data structure mismatches

### Phase 7: Documentation

Prompt user to document if successful:

"Once you've tested and the workflow is working, would you like me to document this pattern in `.claude/agents-evolution.md`?"

---

## Example Usage

**User:** `/n8n-build workflow to process incoming resume webhooks, extract text, send to AI for analysis, and save results to database`

**Assistant Response:**

"I'll help you build a resume processing workflow. Let me clarify a few requirements:

**Questions:**
1. What webhook payload structure are you receiving? (PDF file, JSON with resume text, etc.)
2. Which AI service should analyze the resume? (OpenAI, Anthropic, other)
3. Which database should store results? (PostgreSQL, MySQL, Supabase, etc.)
4. What analysis should the AI perform? (Skills extraction, fit score, summary, etc.)
5. Should there be error notifications if processing fails?

[After user answers...]

**Proposed Workflow Structure:**

```
Webhook Trigger (POST /api/resume)
    ↓
Set (extract resume data from payload)
    ↓
IF (check if PDF or text)
    ├─ PDF → HTTP Request (PDF text extraction API)
    └─ Text → Continue
         ↓
OpenAI (analyze resume with prompt)
    ↓
Set (structure AI response)
    ↓
PostgreSQL (insert results)
    ├─ Success → Respond to Webhook (200 + analysis)
    └─ Error → Slack (notify team) → Respond to Webhook (500)
```

**Nodes I'll use:**
- **Webhook** (trigger)
- **Set** (data normalization)
- **IF** (routing logic)
- **HTTP Request** (PDF extraction if needed)
- **OpenAI** (AI analysis - native node)
- **PostgreSQL** (database save - native node)
- **Slack** (error notification - native node)
- **Respond to Webhook** (HTTP response)

Shall I proceed with creating this workflow?"

---

## Anti-Patterns to Avoid

**Do NOT:**
- ❌ Jump to Code nodes without checking native alternatives
- ❌ Create workflows without error handling
- ❌ Ignore user's clarifying questions - always gather requirements
- ❌ Create overly complex workflows - break into sub-workflows if needed
- ❌ Hardcode values - use parameters and environment variables

**Do:**
- ✅ Search for existing templates first
- ✅ Propose visual workflow structure before building
- ✅ Include error handling from the start
- ✅ Use descriptive naming for all nodes
- ✅ Validate before declaring success

---

## Success Criteria

**Workflow is complete when:**
1. Created via MCP and validated successfully
2. Error handling paths are included
3. User understands how to test it
4. Node selection prioritized native nodes
5. Workflow naming follows conventions (dev-*, prod-*, lib-*)

---

**Version:** 1.0.0
**Last Updated:** 2025-11-22
