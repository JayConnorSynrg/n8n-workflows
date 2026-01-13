---
name: n8n-debugging
description: |
  Debug n8n workflow issues using systematic 5-Why analysis. Use when:
  - Workflow execution fails at a node
  - Node configuration errors occur
  - Expression syntax issues appear
  - Connection/wiring problems detected
  - Version compatibility warnings shown
  Provides debugging methodology, root cause analysis, and fix implementation protocols.
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Edit
  - Write
  - mcp__n8n-mcp__*
---

# N8N Debugging Skill

**Version:** 1.0.0
**Source:** Derived from synrg-n8ndebug v1.1.0
**Purpose:** Provide sub-agents with systematic n8n debugging methodology

---

## Quick Reference: Debug Phases

| Phase | Objective | Key Actions |
|-------|-----------|-------------|
| 0 | Triage | Determine: execution vs structure issue |
| 1 | Identify | Gather context: executions, workflow JSON, patterns |
| 2 | Analyze | 5-Why root cause analysis |
| 3 | Research | Find solutions from templates, docs, patterns |
| 4 | Implement | Apply fix with validation |
| 5 | Verify | Confirm fix works (MANDATORY gate) |
| 6 | Document | Record verified patterns only |

---

## Phase 0: Triage

**Determine debug approach before full analysis:**

```
Runtime error? → Check execution logs first
Configuration error? → Validate workflow structure
Logic error? → Both execution AND structure review
```

**MCP Tools:**
```javascript
// Check if workflow can execute
mcp__n8n-mcp__n8n_validate_workflow({ id: workflowId })

// Get recent executions
mcp__n8n-mcp__n8n_executions({
  action: 'list',
  workflowId,
  status: 'error',
  limit: 10
})
```

---

## Phase 1: Issue Identification

**Gather comprehensive context:**

```javascript
// 1. Get execution details
const execution = await mcp__n8n-mcp__n8n_executions({
  action: 'get',
  id: executionId,
  mode: 'full',
  includeInputData: true
});

// 2. Get workflow structure
const workflow = await mcp__n8n-mcp__n8n_get_workflow({
  id: workflowId,
  mode: 'full'
});

// 3. Search pattern library
// Pattern index: .claude/patterns/pattern-index.json
// Patterns: .claude/patterns/[category]/*.md
```

**Identify:**
- Failed node name and type
- Error message
- Input data to failed node
- Matching patterns from library

---

## Phase 2: 5-Why Root Cause Analysis (MANDATORY)

**Structured root cause discovery:**

| Why | Focus | Question Pattern |
|-----|-------|-----------------|
| 1 | Surface | Why did execution fail? |
| 2 | Immediate | Why did [answer 1] occur? |
| 3 | Technical | Why did [answer 2] happen? |
| 4 | Design | Why did [answer 3] happen? |
| 5 | Root | Why did [answer 4] happen? |

**Root Cause Categories:**

| Category | Indicators | Action |
|----------|-----------|--------|
| Process Gap | Skipped validation | Update protocols |
| Knowledge Gap | Didn't know pattern | Document in agents-evolution.md |
| Tool Misuse | Wrong parameters | Update command docs |
| Design Flaw | Missing error handling | Create pattern |
| API Change | Response format changed | Update integration pattern |
| Config Drift | Credentials expired | Add monitoring |

---

## Phase 3: Solution Research

**Search multiple sources:**

```javascript
// 1. Templates with working implementations
mcp__n8n-mcp__search_templates({ query: 'relevant keywords' })

// 2. Node documentation
mcp__n8n-mcp__get_node({
  nodeType: failedNode.type,
  mode: 'docs',
  detail: 'full'
})

// 3. Node examples
mcp__n8n-mcp__get_node({
  nodeType: failedNode.type,
  mode: 'info',
  includeExamples: true
})

// 4. Pattern library
// Read: .claude/patterns/pattern-index.json
// Check node_type_mappings for patterns
```

---

## Phase 4: Implementation

**Apply fix with validation:**

```javascript
// 1. Validate node config BEFORE applying
const validation = await mcp__n8n-mcp__validate_node({
  nodeType: failedNode.type,
  config: correctedConfig,
  mode: 'full',
  profile: 'strict'
});

// 2. Apply via partial update (safer)
await mcp__n8n-mcp__n8n_update_partial_workflow({
  id: workflowId,
  operations: [{
    type: 'updateNode',
    nodeName: failedNode.name,
    updates: { parameters: correctedConfig }
  }]
});

// 3. Validate workflow after update
await mcp__n8n-mcp__n8n_validate_workflow({ id: workflowId });
```

---

## Phase 5: Verification Gate (MANDATORY)

**NEVER proceed to documentation until verified:**

```
Verification Checklist:
- [ ] Workflow validation passes (0 critical errors)
- [ ] No blocking warnings
- [ ] All node configurations validate
- [ ] Workflow executes without original error (if testable)
- [ ] User confirms fix resolves issue
```

**Verification Status:**
- PASSED → Proceed to Phase 6
- FAILED → Return to Phase 4
- PENDING → Ask user to confirm

---

## Phase 6: Documentation (ONLY After Verification)

**Document VERIFIED patterns only:**

**Location:** `.claude/agents-evolution.md`

**Format:**
```markdown
## [YYYY-MM-DD] Workflow: {name} ({id})

### Anti-Pattern: {description}
**What Happened:** {failure description}
**Impact:** {what broke}
**Why It Failed:** {root cause}

### Positive Pattern: {description}
**Solution:** {fix description}
**Implementation:** {steps}
**Result:** {measurable outcome}
**Reusable Pattern:** {when to apply}
```

---

## Critical N8N Rules (Always Apply)

### 1. Always Use Latest TypeVersions
```javascript
// BEFORE any node implementation
mcp__n8n-mcp__get_node({ nodeType: 'nodes-base.{name}' })
// Check typeVersion and use latest
```

### 2. Expression Syntax
| Type | Format | Example |
|------|--------|---------|
| Static | `"value"` | `"data"` |
| Dynamic | `"={{ expr }}"` | `"={{ $json.field }}"` |
| Property name | `"name"` (NO prefix) | `"binaryPropertyName": "data"` |

### 3. OpenAI Image Nodes (Anti-Memory Protocol)
```
ALWAYS READ: .claude/patterns/api-integration/openai-image-nodes.md

Critical rules:
- binaryPropertyName: "data" NOT "=data"
- modelId requires ResourceLocator: { "__rl": true, "value": "gpt-4o", "mode": "list" }
```

### 4. Connection Syntax
- `type` must be `"main"` not `"0"`
- `index` must be integer not string

---

## Pattern Library Access

**Index:** `.claude/patterns/pattern-index.json`

**Categories:**
- `critical-directives/` - ALWAYS check first
- `api-integration/` - External API configs
- `workflow-architecture/` - Loops, memory, parsers
- `error-handling/` - Triggers, conditionals
- `node-selection/` - Choosing node types

**Lookup Protocol:**
1. Read `pattern-index.json`
2. Check `node_type_mappings` for node type
3. Read corresponding pattern file
4. Apply rules before implementation

---

## Sub-Agent Delegation

When debugging requires specialized focus:

| Issue | Agent | Model |
|-------|-------|-------|
| Invalid nodes | `n8n-node-validator` | haiku |
| Connection errors | `n8n-connection-fixer` | haiku |
| Version issues | `n8n-version-researcher` | haiku |
| Expression errors | `n8n-expression-debugger` | haiku |
| Pattern lookup | `n8n-pattern-retriever` | haiku |
| Complex/multi-step | `n8n-workflow-expert` | sonnet |

---

## Success Criteria

Debug complete when:
1. Issue identified with context
2. 5-Why root cause analysis done
3. Solution researched from multiple sources
4. Fix implemented and validated
5. Fix VERIFIED working
6. Pattern documented (only if verified)
7. No existing documentation harmed

---

**Philosophy:** Value-First + Robustness-First
**Never:** Document unverified fixes, delete existing patterns, skip verification
