# SYNRG N8N Workflow Debugger

**Command:** `/synrg-n8ndebug [workflow-id or "last"]`

**Version:** 1.7.0
**Created:** 2025-12-03
**Updated:** 2025-12-28
**Philosophy:** SYNRG Director/Orchestrator + Value-First + Robustness-First + **Self-Correcting Documentation** + **Documentation Consistency Audit** + **DVMS (Documentation Validity Management)** + **Topology-Aware Debugging** + **Node-Reference First** + **Mandatory User Verification Gate**

---

## Purpose

Comprehensive n8n workflow debugging that:
1. **Asks** whether to check last execution before full analysis
2. **Identifies** issues from execution history OR workflow structure
3. **Analyzes** root cause using 5-Why methodology
4. **Audits documentation validity** - questions whether patterns/rules that led to the error are themselves incorrect
5. **Consults node-reference** - ALWAYS check `.claude/node-reference/` BEFORE using MCP tools
6. **Researches** solutions from authoritative sources (node-reference, MCP tools, templates)
7. **Implements** corrected configuration using verified reference configs
8. **Verifies** fix works before documenting
9. **Corrects documentation** if patterns were wrong, documents new patterns if discovered

**Core Principle:** Never delete or modify existing value. Only integrate new patterns. **EXCEPTION:** Modify existing patterns/rules when they are proven incorrect or contradictory.

**Critical Rule:** ONLY document patterns AFTER the fix has been confirmed working. Never document speculative or untested solutions.

---

## 🔴 CRITICAL: Documentation Validity Audit

**If `/synrg-n8ndebug` is being invoked, something failed.** This means ONE of these is true:

1. **LLM Error** - Claude made a mistake despite correct documentation
2. **Documentation Error** - The patterns/rules in `.claude/` are wrong or incomplete
3. **Knowledge Gap** - No documentation existed for this scenario
4. **External Change** - n8n API/schema changed since documentation was written

**MANDATORY AUDIT QUESTIONS (ask in Phase 2):**

```markdown
### Documentation Validity Audit

**Question 1:** What pattern/rule was followed to create the failing node?
- Pattern file: {path or "none"}
- Rule applied: {specific rule or "memory-based"}

**Question 2:** Is that pattern/rule CORRECT according to authoritative sources?
- [ ] YES - Pattern is correct, LLM made implementation error
- [ ] NO - Pattern itself is WRONG and must be corrected
- [ ] PARTIAL - Pattern is incomplete, needs additional rules
- [ ] N/A - No pattern existed (knowledge gap)

**Question 3:** What is the authoritative source of truth?
- MCP tool: `mcp__n8n-mcp__get_node` with `mode: 'docs'`
- n8n template examples: `mcp__n8n-mcp__search_templates`
- Live workflow that works: `mcp__n8n-mcp__n8n_get_workflow`

**Audit Verdict:** {LLM Error | Documentation Error | Knowledge Gap | External Change}
```

**If Documentation Error is found:**
- The pattern file MUST be corrected in Phase 6
- Add anti-pattern warning to prevent future misuse
- Update CLAUDE.md if core rules were wrong

---

## 🔴 CRITICAL: Node-Reference Lookup Protocol (MANDATORY)

**BEFORE using ANY MCP tool for node configuration, ALWAYS check the node-reference library first.**

**Why This Is Required:**
- Node-reference contains VERIFIED configurations from live workflows
- Anti-Memory Protocol nodes are flagged with explicit warnings
- Saves MCP calls by using cached, validated configurations
- Prevents recurring failures by using known-working patterns

### Lookup Protocol (4 Steps)

```javascript
// Step 1: Check if node reference exists
const patternIndex = await Read({
  file_path: '.claude/patterns/pattern-index.json'
});

// Step 2: Look up node type in node_references
const nodeRef = patternIndex.node_references.langchain[nodeType];

if (nodeRef) {
  // Step 3: Read reference file
  const reference = await Read({
    file_path: `.claude/node-reference/${nodeRef.file}`
  });

  // Step 4: Check anti_memory flag
  if (nodeRef.anti_memory === true) {
    // MANDATORY: Read file EVERY TIME, do not trust memory
    console.log("⚠️ ANTI-MEMORY NODE: Read reference file before implementing");
  }

  // Use reference configuration
  return reference;
} else {
  // No reference exists - use MCP to fetch schema
  const nodeInfo = await mcp__n8n-mcp__get_node({
    nodeType: nodeType,
    mode: 'info',
    detail: 'full'
  });
}
```

### Node Reference Directory

**Location:** `.claude/node-reference/`
**Index:** `.claude/node-reference/README.md`

| Category | Path | Content |
|----------|------|---------|
| LangChain AI | `langchain/` | Agent, Chat Models, Memory, Tools, Vector Stores |
| Standard Nodes | `base/` | (to be populated) |

### Anti-Memory Nodes (ALWAYS Read Reference)

These nodes have documented recurring failure patterns:

| Node | Reference File | Known Issues |
|------|----------------|--------------|
| OpenAI Image | `langchain/openai-image.md` | `binaryPropertyName` contamination, typeVersion confusion |

**⚠️ For Anti-Memory nodes, you MUST read the reference file before EVERY implementation. Do NOT trust memory.**

### Integration with PHASE 3

In Solution Research (PHASE 3), the lookup order is:

1. **Node Reference** (`.claude/node-reference/`) - FIRST
2. **Pattern Library** (`.claude/patterns/`) - SECOND
3. **MCP Tools** (`mcp__n8n-mcp__get_node`) - THIRD (if no reference exists)
4. **Templates** (`mcp__n8n-mcp__search_templates`) - FOURTH (for examples)

---

## 🔴 CRITICAL: DVMS Integration (Documentation Validity Management System)

**Version:** 1.0.0
**Reference:** `.claude/patterns/documentation-validity-management.md`

The Documentation Validity Management System (DVMS) ensures all patterns are:
1. **FRESH** - Verified within acceptable timeframe
2. **CONSISTENT** - No contradictions between patterns
3. **CURRENT** - Reflects latest n8n MCP schema

### PHASE 0.25: DVMS Validity Gate (MANDATORY - Before Pattern Access)

**Execute BEFORE accessing ANY pattern:**

```javascript
// For EVERY pattern access, run DVMS validity gate
async function dvmsValidityGate(patternId, nodeType) {
  const patternIndex = await Read({
    file_path: '.claude/patterns/pattern-index.json'
  });

  const pattern = patternIndex.patterns.find(p => p.id === patternId);

  // Check 1: Freshness Tier
  const freshness = pattern?.validity?.freshness_tier;
  if (freshness === 'EXPIRED') {
    // MANDATORY: Re-validate against MCP before use
    console.log("⚠️ DVMS: Pattern EXPIRED - Triggering MCP re-validation");
    await triggerMCPRevalidation(pattern, nodeType);
  } else if (freshness === 'STALE') {
    console.log("⚠️ DVMS: Pattern STALE - Recommended re-validation");
  }

  // Check 2: Deprecation Status
  const deprecation = pattern?.deprecation?.status;
  if (deprecation === 'DEPRECATED') {
    console.log("⚠️ DVMS: Pattern DEPRECATED");
    console.log(`   Superseded by: ${pattern.deprecation.superseded_by}`);
    console.log(`   Sunset date: ${pattern.deprecation.sunset_date}`);
    // Show migration guide but allow continued use
  } else if (deprecation === 'SUNSET' || deprecation === 'ARCHIVED') {
    console.log("🛑 DVMS: Pattern SUNSET/ARCHIVED - Must use replacement");
    return pattern.deprecation.superseded_by;
  }

  return pattern;
}

// MCP Re-validation Protocol
async function triggerMCPRevalidation(pattern, nodeType) {
  // Delegate to n8n-mcp-delegate for current schema
  const mcpResult = await Task({
    subagent_type: "n8n-mcp-delegate",
    prompt: `Re-validate pattern for node type: ${nodeType}
             1. Get current node schema with get_node
             2. Compare with documented pattern
             3. Report any discrepancies
             4. Recommend update if needed`,
    model: "haiku"
  });

  // Update pattern validity
  pattern.validity.last_verified = new Date().toISOString().split('T')[0];
  pattern.validity.freshness_tier = 'FRESH';
  pattern.validity.next_verification_due = calculateNextDue();

  return mcpResult;
}
```

### DVMS Freshness Tiers

| Tier | Age | Visual | Action Required |
|------|-----|--------|-----------------|
| **FRESH** | 0-30 days | 🟢 | Proceed normally |
| **AGING** | 31-60 days | 🟡 | Optional re-validation |
| **STALE** | 61-90 days | 🟠 | Verify before critical use |
| **EXPIRED** | >90 days | 🔴 | MANDATORY re-validation |

### DVMS Deprecation States

| State | Meaning | Action |
|-------|---------|--------|
| **ACTIVE** | Pattern is valid | Use normally |
| **DEPRECATED** | Replaced, still usable | Show warning, offer replacement |
| **SUNSET** | Being phased out | Strong warning, migration required |
| **ARCHIVED** | No longer usable | Block access, redirect to replacement |

### Integration with Phase 0.5

DVMS enhances the Documentation Consistency Audit (Phase 0.5):

1. **Before contradiction check:** Run freshness validation
2. **During contradiction detection:** Use DVMS resolution protocol
3. **After resolution:** Trigger deprecation if pattern proven wrong
4. **Document resolution:** Update pattern validity metadata

### Contradiction Resolution with DVMS

```javascript
// When contradiction detected in Phase 0.5
async function resolveWithDVMS(patternA, patternB, nodeType) {
  // Step 1: Query MCP for authoritative answer
  const mcpResult = await Task({
    subagent_type: "n8n-mcp-delegate",
    prompt: `Contradiction Resolution:
             Node: ${nodeType}
             Pattern A: ${patternA.id} says ${patternA.value}
             Pattern B: ${patternB.id} says ${patternB.value}

             1. Get current node schema
             2. Determine which value is CORRECT
             3. Search templates for common usage
             4. Return winning value with confidence`,
    model: "haiku"
  });

  // Step 2: Deprecate losing pattern
  if (mcpResult.winner !== patternA.id) {
    await deprecatePattern(patternA.id,
      'Contradiction resolved',
      patternB.id
    );
  } else {
    await deprecatePattern(patternB.id,
      'Contradiction resolved',
      patternA.id
    );
  }

  // Step 3: Document resolution
  await logContradictionResolution({
    nodeType,
    winner: mcpResult.winner,
    loser: mcpResult.loser,
    evidence: mcpResult.evidence,
    date: new Date().toISOString()
  });

  return mcpResult.winner;
}
```

### DVMS Quick Reference

| Check | Location | Trigger |
|-------|----------|---------|
| Freshness | `pattern.validity.freshness_tier` | Before every pattern access |
| Deprecation | `pattern.deprecation.status` | Before using pattern |
| Contradiction | `pattern.contradiction_check` | In Phase 0.5 |
| Re-validation | `n8n-mcp-delegate` | When EXPIRED or contradiction |

---

## 🔴 MANDATORY: Sub-Agent Delegation Protocol (v4.3)

**BEFORE executing any debug phase, delegate to specialized n8n agents:**

```
┌─────────────────────────────────────────────────────────────┐
│  N8N DEBUG DELEGATION (MANDATORY)                           │
│                                                             │
│  1. IDENTIFY task type from error/issue                     │
│  2. SELECT appropriate atomic agent from matrix below       │
│  3. DELEGATE using Task tool (not pseudocode)               │
│  4. CONSOLIDATE results from specialized agents             │
└─────────────────────────────────────────────────────────────┘
```

### N8N Agent Selection Matrix

| Issue Type | Primary Agent | Use For |
|------------|---------------|---------|
| Invalid nodes | `n8n-node-validator` | Schema validation, parameter checking |
| Connection errors | `n8n-connection-fixer` | type field, wiring issues |
| Version warnings | `n8n-version-researcher` | typeVersion lookup, migrations |
| Expression errors | `n8n-expression-debugger` | = prefix, {{ }} syntax |
| Pattern lookup | `n8n-pattern-retriever` | Retrieve relevant patterns |
| Complex/multi-step | `n8n-workflow-expert` | Full workflow operations |

### Real Delegation Example

```javascript
// PHASE 1: Delegate to pattern retriever first
Task({
  subagent_type: "general-purpose",
  prompt: `Retrieve patterns for node type @n8n/n8n-nodes-langchain.openAi
  Pattern library: /Users/jelalconnor/CODING/N8N/Workflows/.claude/patterns/
  Return: anti-patterns, correct patterns, critical rules`,
  model: "haiku"
})

// PHASE 2: Delegate validation to node validator
Task({
  subagent_type: "general-purpose",
  prompt: `Validate OpenAI node in workflow 8bhcEHkbbvnhdHBh
  Check against patterns retrieved in previous step
  Use MCP tools: mcp__n8n-mcp__validate_node`,
  model: "haiku"
})
```

---

## SYNRG Director/Orchestrator Integration

This command leverages SYNRG v4.0 principles:

**Value-First Analysis:**
- Assess current workflow value before changes
- Quantify what's working vs. what's broken
- Preserve functioning components

**Robustness-First Execution:**
- Take as long as needed for correct solutions
- Complete 5-Why root cause analysis on every error
- Predict future impact before implementing fixes

**Pattern Evolution:**
- Document every discovery in agents-evolution.md
- Create reusable patterns in pattern library
- Seamlessly integrate without disrupting existing documentation

---

## Execution Protocol

### PHASE 0: Pre-Debug Triage (MANDATORY)

**Director Objective:** Determine debug approach before full analysis

**CRITICAL:** Before spawning full reconnaissance agents, ask the user how to proceed.

```markdown
## PHASE 0: Pre-Debug Triage

**Workflow:** {workflow-id}

Before proceeding with full debug analysis, I need to understand the issue context:

**Question 1:** Should I check the last execution for this workflow?
- [ ] **Yes, check execution** - Error may be visible in execution logs
- [ ] **No, check structure** - Error is in workflow configuration itself (node won't execute)
- [ ] **Both** - Check execution logs AND validate workflow structure

**Question 2:** What's the primary symptom?
- [ ] **Runtime error** - Workflow executes but fails at a node
- [ ] **Configuration error** - Workflow won't execute at all
- [ ] **Logic error** - Workflow executes but produces wrong results
- [ ] **Unknown** - Need to investigate

---

**Why this matters:**
- **Runtime errors** → Check execution logs first (PHASE 1 standard path)
- **Configuration errors** → Validate workflow structure first (skip execution analysis)
- **Logic errors** → Need both execution data AND workflow review

*Awaiting user response before proceeding...*
```

**Triage Decision Tree:**

```
User selects "check execution" OR "both"
├─ Proceed with PHASE 1: Issue Identification (execution analysis)
│
User selects "check structure" only
├─ Skip execution analysis
├─ Go directly to workflow validation
│   └─ mcp__n8n-mcp__n8n_validate_workflow({ id, options: { profile: 'strict' }})
├─ Identify structural errors
└─ Proceed to PHASE 2 with structural issues
```

**After Triage, Announce Path:**

```markdown
## Debug Path Selected

**Approach:** {execution-based | structure-based | combined}
**Reasoning:** {why this path was selected}

Proceeding with {PHASE 0.5 / Documentation Consistency Audit}...
```

---

### PHASE 0.5: Documentation Consistency Audit (MANDATORY - HARDCODED)

**Director Objective:** Verify ALL documentation for workflow node types is internally consistent BEFORE debugging

**CRITICAL:** This phase is MANDATORY and HARDCODED. Documentation contradictions are a ROOT CAUSE of repeated failures. If documentation files disagree on typeVersion, configuration, or patterns for the same node type, the debug process will fail.

**Why This Phase Exists:**
- Pattern files may say typeVersion X, while node-reference says typeVersion Y
- pattern-index.json may be out of sync with actual file contents
- Reference workflows may use different configurations than documented
- These contradictions cause Claude to implement incorrect configurations repeatedly

**Audit Scope (For EACH node type in the workflow):**

```javascript
// Step 1: Identify all node types in the workflow
const workflow = await mcp__n8n-mcp__n8n_get_workflow({
  id: workflowId,
  mode: 'structure'
});

const nodeTypes = [...new Set(workflow.nodes.map(n => n.type))];

// Step 2: For each node type, gather ALL documentation references
for (const nodeType of nodeTypes) {
  const auditReport = {
    nodeType: nodeType,
    sources: [],
    contradictions: [],
    verified: false
  };

  // Source 1: pattern-index.json
  const patternIndex = await Read({
    file_path: '.claude/patterns/pattern-index.json'
  });
  const indexEntry = patternIndex.node_references?.langchain?.[nodeType];
  if (indexEntry) {
    auditReport.sources.push({
      source: 'pattern-index.json',
      typeVersion: indexEntry.typeVersion,
      file: indexEntry.file
    });
  }

  // Source 2: node-reference file
  if (indexEntry?.file) {
    const nodeRef = await Read({
      file_path: `.claude/node-reference/${indexEntry.file}`
    });
    // Extract typeVersion from file (look for "typeVersion": X or **TypeVersion**: X)
    auditReport.sources.push({
      source: `node-reference/${indexEntry.file}`,
      typeVersion: extractTypeVersion(nodeRef),
      config: extractReferenceConfig(nodeRef)
    });
  }

  // Source 3: Related pattern files
  const patternMappings = patternIndex.node_type_mappings?.[nodeType] || [];
  for (const patternId of patternMappings) {
    const pattern = patternIndex.patterns.find(p => p.id === patternId);
    if (pattern) {
      const patternFile = await Read({
        file_path: `.claude/patterns/${pattern.file}`
      });
      // Extract any typeVersion mentions
      auditReport.sources.push({
        source: `patterns/${pattern.file}`,
        typeVersion: extractTypeVersion(patternFile),
        rules: extractRules(patternFile)
      });
    }
  }

  // Source 4: Reference workflows (known working)
  const referenceWorkflows = {
    '@n8n/n8n-nodes-langchain.agent': 'gjYSN6xNjLw8qsA1',  // Teams Voice Bot
    // Add other reference workflow IDs as discovered
  };

  if (referenceWorkflows[nodeType]) {
    const refWorkflow = await mcp__n8n-mcp__n8n_get_workflow({
      id: referenceWorkflows[nodeType],
      mode: 'full'
    });
    const refNode = refWorkflow.nodes.find(n => n.type === nodeType);
    if (refNode) {
      auditReport.sources.push({
        source: `reference-workflow:${referenceWorkflows[nodeType]}`,
        typeVersion: refNode.typeVersion,
        config: refNode.parameters,
        verified: true  // This is a WORKING configuration
      });
    }
  }

  // Step 3: Detect contradictions
  const typeVersions = auditReport.sources
    .map(s => s.typeVersion)
    .filter(v => v !== undefined);

  const uniqueVersions = [...new Set(typeVersions)];
  if (uniqueVersions.length > 1) {
    auditReport.contradictions.push({
      type: 'TYPE_VERSION_MISMATCH',
      severity: 'CRITICAL',
      values: uniqueVersions,
      sources: auditReport.sources.filter(s => s.typeVersion)
    });
  }

  // Step 4: If contradictions found, verify against authority
  if (auditReport.contradictions.length > 0) {
    // Priority order for resolution:
    // 1. Working reference workflow (proven to work)
    // 2. MCP authoritative source (n8n's actual schema)
    // 3. Newest/highest version (if no reference available)

    const refSource = auditReport.sources.find(s => s.verified);
    if (refSource) {
      auditReport.authoritative = {
        source: refSource.source,
        typeVersion: refSource.typeVersion,
        config: refSource.config,
        reason: 'Verified working in production workflow'
      };
    } else {
      // Fall back to MCP
      const mcpInfo = await mcp__n8n-mcp__get_node({
        nodeType: nodeType,
        mode: 'info',
        detail: 'standard'
      });
      // NOTE: MCP "latest" may not match what works - prefer reference workflows
    }
  }
}
```

**Documentation Consistency Report (REQUIRED OUTPUT):**

```markdown
## PHASE 0.5: Documentation Consistency Audit

**Workflow:** {workflowId}
**Node Types Audited:** {count}

---

### Audit Results by Node Type

#### Node: {nodeType}

**Documentation Sources Found:**

| Source | TypeVersion | Config Pattern |
|--------|-------------|----------------|
| pattern-index.json | {version} | N/A |
| node-reference/{file} | {version} | {minimal/explicit} |
| patterns/{file} | {version} | {rules} |
| reference-workflow:{id} | {version} | {working config} ✅ |

**Contradictions Detected:** {count}

| Contradiction | Severity | Details |
|---------------|----------|---------|
| TYPE_VERSION_MISMATCH | CRITICAL | Sources disagree: {list versions} |
| CONFIG_PATTERN_MISMATCH | HIGH | {description} |

**Authoritative Source:** {source name}
**Reason:** {why this is authoritative - e.g., "Verified working in production"}

**Required Corrections:**
1. {file1} - Change typeVersion from {X} to {Y}
2. {file2} - Update config pattern to match reference

---

### Audit Status

**Status:** {PASSED | FAILED - CONTRADICTIONS FOUND}

**If PASSED:** Proceed to PHASE 1 (Issue Identification)
**If FAILED:**
  - Present contradictions to user
  - Correct ALL documentation files before proceeding
  - Mark corrections in agents-evolution.md
```

**Contradiction Handling Protocol:**

```
Contradictions Found?
        │
        ├─ NO → Proceed to PHASE 1
        │
        └─ YES → HALT
               │
               ├─ Present contradictions to user
               │
               ├─ Identify authoritative source (prefer reference workflow)
               │
               ├─ Correct ALL inconsistent documentation:
               │   - pattern-index.json
               │   - node-reference files
               │   - pattern files
               │
               ├─ Document correction in agents-evolution.md
               │
               └─ THEN proceed to PHASE 1
```

**Reference Workflow Registry:**

Maintain a registry of known-working workflows for verification:

```json
{
  "reference_workflows": {
    "@n8n/n8n-nodes-langchain.agent": {
      "workflow_id": "gjYSN6xNjLw8qsA1",
      "workflow_name": "Teams Voice Bot Reference",
      "verified_date": "2025-12-27",
      "verified_config": {
        "typeVersion": 3,
        "parameters": { "options": {} }
      }
    }
  }
}
```

**Anti-Pattern Warning (HARDCODED):**

```markdown
⚠️ **AI Agent Node Anti-Pattern (v1.0 - 2025-12-27)**

**WRONG (causes execution failures):**
```json
{
  "typeVersion": 3.1,
  "parameters": {
    "promptType": "define",
    "text": "={{ $json.chatInput }}",
    "options": { "systemMessage": "..." }
  }
}
```

**CORRECT (verified working):**
```json
{
  "typeVersion": 3,
  "parameters": {
    "options": {}
  }
}
```

**Rules:**
1. Use `typeVersion: 3` (NOT 3.1)
2. Use MINIMAL parameters: `{"options": {}}`
3. Let n8n UI handle defaults
4. ALWAYS verify against reference workflow gjYSN6xNjLw8qsA1
```

---

### PHASE 1: Issue Identification (Director Spawns Sub-Agents)

**Director Objective:** Gather comprehensive execution context

```javascript
// SYNRG Director spawns parallel sub-agents for reconnaissance
const reconAgents = [
  {
    id: 'execution-analyzer',
    task: 'Fetch and analyze recent workflow executions',
    tools: ['mcp__n8n-mcp__n8n_executions'],
    deliverable: 'Execution history with error details'
  },
  {
    id: 'workflow-inspector',
    task: 'Get current workflow structure and configuration',
    tools: ['mcp__n8n-mcp__n8n_get_workflow'],
    deliverable: 'Complete workflow JSON with node configurations'
  },
  {
    id: 'pattern-searcher',
    task: 'Search evolution log for similar error patterns',
    tools: ['Read', 'Grep'],
    deliverable: 'Matching patterns from agents-evolution.md'
  }
];
```

**Execution:**

```javascript
// 1. Get workflow ID from user or find last failed
const workflowId = args || await findLastFailedWorkflow();

// 2. Fetch recent executions
const executions = await mcp__n8n-mcp__n8n_executions({
  action: 'list',
  workflowId: workflowId,
  status: 'error',
  limit: 10
});

// 3. Get most recent failed execution details
const failedExecution = await mcp__n8n-mcp__n8n_executions({
  action: 'get',
  id: executions[0].id,
  mode: 'full',
  includeInputData: true
});

// 4. Get current workflow structure
const workflow = await mcp__n8n-mcp__n8n_get_workflow({
  id: workflowId,
  mode: 'full'
});

// 5. Search evolution log for similar patterns
const evolutionContent = await Read({
  file_path: '.claude/agents-evolution.md'
});
```

**Director Consolidation Output:**

```markdown
## PHASE 1: Issue Identification Report

**Workflow:** {workflow-name} (ID: {workflowId})
**Status:** {active/inactive}
**Last Execution:** {executionId}
**Failure Count:** {count} in last 24 hours

---

### Execution Flow Analysis

{Visual flow diagram}
✅ Node A → ✅ Node B → ❌ Node C (FAILED) → ⏹️ (stopped)

**Successful Nodes:** {count}
**Failed Node:** {nodeName} ({nodeType})
**Skipped Nodes:** {count}

---

### Error Details

**Error at Node:** {nodeName}
**Node Type:** {nodeType} (typeVersion: {version})
**Error Type:** {errorType}
**Error Message:**
```
{full error message}
```

**Input Data to Failed Node:**
```json
{input data structure}
```

---

### Pattern Search Results

**Matching Patterns Found:** {count}
{List any matching patterns from agents-evolution.md}

**Relevance Score:** {HIGH/MEDIUM/LOW/NONE}
```

---

### PHASE 2: Root Cause Analysis (5-Why Protocol - MANDATORY)

**Director Objective:** Identify true root cause, not just symptoms

**CRITICAL:** This phase is MANDATORY. Superficial fixes lead to recurring failures.

```markdown
## PHASE 2: 5-Why Root Cause Analysis

### Why 1 - Surface Symptom
**Question:** Why did the workflow execution fail?
**Answer:** {Specific error message or failure symptom}
**Evidence:** {Log entries, error codes, stack traces}

---

### Why 2 - Immediate Cause
**Question:** Why did {answer from Why 1} occur?
**Answer:** {Technical immediate cause}
**Evidence:** {Node configuration, data structure, API response}

---

### Why 3 - Technical Cause
**Question:** Why did {answer from Why 2} happen?
**Answer:** {Technical decision or configuration that enabled this}
**Evidence:** {Workflow design, node parameters, connection patterns}

---

### Why 4 - Design Cause
**Question:** Why did {answer from Why 3} happen?
**Answer:** {Design choice, architecture decision, or missing validation}
**Evidence:** {Workflow structure, error handling gaps, validation gaps}

---

### Why 5 - Root Cause (Process/Knowledge Gap)
**Question:** Why did {answer from Why 4} happen?
**Answer:** {Process failure, knowledge gap, or missing best practice}
**Evidence:** {Missing documentation, undocumented pattern, process gap}

---

## Root Cause Identified

**Category:** {Documentation Error | LLM Error | Process Gap | Knowledge Gap | Tool Misuse | Design Flaw | API Change | Configuration Drift}

**Root Cause Statement:**
{Clear, actionable statement of the true root cause}

**Pattern Classification:**
- [ ] Matches existing pattern in agents-evolution.md → Reference: {pattern name}
- [ ] New pattern discovered → Document in Phase 6

---

## 🔴 MANDATORY: Documentation Validity Audit

**This audit is REQUIRED before proceeding to Phase 3.**

### Audit Step 1: Identify Source of Node Configuration

**What pattern/rule was followed to create the failing node(s)?**

| Failing Node | Pattern File Used | Specific Rule Applied |
|--------------|-------------------|----------------------|
| {node name} | {path or "none/memory"} | {rule text or "N/A"} |

### Audit Step 2: Verify Pattern Against Authoritative Sources

**For EACH failing node, run:**
```javascript
// Get authoritative node schema
const nodeInfo = await mcp__n8n-mcp__get_node({
  nodeType: '{failing node type}',
  mode: 'docs',
  detail: 'full'
});

// Search for working examples
const examples = await mcp__n8n-mcp__search_templates({
  searchMode: 'by_nodes',
  nodeTypes: ['{failing node type}'],
  limit: 5
});
```

**Compare pattern rules against MCP results:**

| Rule in Pattern | MCP Says | Match? |
|-----------------|----------|--------|
| {rule 1} | {actual} | ✅/❌ |
| {rule 2} | {actual} | ✅/❌ |

### Audit Step 3: Determine Verdict

**Audit Verdict:** {select one}

- [ ] **Documentation Error** - Pattern file contains incorrect rules → MUST correct in Phase 6
- [ ] **LLM Error** - Pattern was correct, Claude failed to follow it → Add emphasis/examples
- [ ] **Knowledge Gap** - No pattern existed → Create new pattern in Phase 6
- [ ] **External Change** - n8n changed since pattern was written → Update pattern in Phase 6

**Files requiring correction (if Documentation Error):**
- {pattern file 1}
- {CLAUDE.md rule if applicable}
```

**Root Cause Categories:**

| Category | Indicators | Documentation Target |
|----------|-----------|---------------------|
| **Documentation Error** | "Pattern said X but correct is Y", "Rule was wrong" | **CORRECT the pattern file**, add anti-pattern warning |
| **LLM Error** | "Pattern was correct but Claude implemented wrong" | Add explicit examples to pattern, strengthen wording |
| **Process Gap** | "Skipped validation", "Deployed without testing" | `.claude/CLAUDE.md` or protocol updates |
| **Knowledge Gap** | "Didn't know about...", "Wasn't aware..." | `agents-evolution.md` + pattern library |
| **Tool Misuse** | "Wrong node type", "Incorrect parameters" | Command docs + pattern common mistakes |
| **Design Flaw** | "No error handling", "Missing retry logic" | Architectural pattern creation |
| **API Change** | "API deprecated", "Response format changed" | Integration pattern update |
| **Configuration Drift** | "Credentials expired", "Environment changed" | Monitoring + validation updates |

**⚠️ Documentation Error is the most critical category** - it means our own rules are causing failures.

---

### PHASE 3: Solution Research (Parallel Sub-Agents)

**Director Objective:** Find proven solutions from multiple sources

**🔴 CRITICAL: Node-Reference Lookup FIRST**

Before spawning research agents, check the node-reference library:

```javascript
// STEP 0: Node-Reference Lookup (MANDATORY - DO THIS FIRST)
const patternIndex = await Read({
  file_path: '.claude/patterns/pattern-index.json'
});

const nodeType = failedNode.type; // e.g., "@n8n/n8n-nodes-langchain.openAi"
const nodeRef = patternIndex.node_references?.langchain?.[nodeType];

if (nodeRef) {
  // Reference exists - read it
  const reference = await Read({
    file_path: `.claude/node-reference/${nodeRef.file}`
  });

  // Check anti-memory flag
  if (nodeRef.anti_memory === true) {
    // ⚠️ ANTI-MEMORY NODE - Use reference config EXACTLY as documented
    console.log("⚠️ ANTI-MEMORY NODE DETECTED");
    console.log("Using verified configuration from reference file");
    console.log("DO NOT modify based on memory - trust the reference");
  }

  // Reference configuration is the PRIMARY source
  // Skip MCP lookup for node schema - use reference instead
}
```

**ONLY if no reference exists, spawn MCP research agents:**

```javascript
// SYNRG Director spawns parallel research agents
const researchAgents = [
  {
    id: 'node-reference-checker',
    task: 'Check node-reference library for verified configurations',
    tools: ['Read'],
    deliverable: 'Verified node configuration from .claude/node-reference/',
    priority: 1  // HIGHEST - check first
  },
  {
    id: 'pattern-library',
    task: 'Search local pattern library for solutions',
    tools: ['Glob', 'Read'],
    deliverable: 'Matching patterns from .claude/patterns/',
    priority: 2
  },
  {
    id: 'node-documentation',
    task: 'Get correct node configuration from n8n MCP (ONLY if no reference)',
    tools: ['mcp__n8n-mcp__get_node', 'mcp__n8n-mcp__search_nodes'],
    deliverable: 'Authoritative node parameters and examples',
    priority: 3  // Only if no local reference
  },
  {
    id: 'template-researcher',
    task: 'Search n8n templates for working implementations',
    tools: ['mcp__n8n-mcp__search_templates', 'mcp__n8n-mcp__get_template'],
    deliverable: 'Matching template configurations',
    priority: 4
  },
  {
    id: 'evolution-solutions',
    task: 'Find positive patterns from evolution log',
    tools: ['Grep', 'Read'],
    deliverable: 'Proven solutions from similar issues',
    priority: 5
  }
];
```

**Research Protocol:**

```javascript
// 1. CHECK NODE-REFERENCE FIRST (MANDATORY)
const patternIndex = JSON.parse(await Read({
  file_path: '.claude/patterns/pattern-index.json'
}));

// Check if node has a reference
const nodeRef = patternIndex.node_references?.langchain?.[failedNode.type];

if (nodeRef) {
  const reference = await Read({
    file_path: `.claude/node-reference/${nodeRef.file}`
  });
  // USE THIS CONFIGURATION - it's verified
  // Skip steps 2-3 (MCP calls) - we have verified config
}

// 2. Search local pattern library
const patternFiles = await Glob({
  pattern: '.claude/patterns/**/*.md'
});

// 3. ONLY IF NO REFERENCE: Get node documentation from MCP
if (!nodeRef) {
  const nodeInfo = await mcp__n8n-mcp__get_node({
    nodeType: failedNode.type,
    mode: 'docs',
    detail: 'full'
  });

  const nodeExamples = await mcp__n8n-mcp__get_node({
    nodeType: failedNode.type,
    mode: 'info',
    includeExamples: true
  });
}

// 4. Search n8n templates for examples
const templates = await mcp__n8n-mcp__search_templates({
  query: '{relevant keywords from failed node}',
  limit: 10
});

// 5. Search evolution log for positive patterns
const positivePatterns = await Grep({
  pattern: 'Positive Pattern:',
  path: '.claude/agents-evolution.md',
  output_mode: 'content',
  '-C': 10
});
```

**Director Consolidation Output:**

```markdown
## PHASE 3: Solution Research Report

### 🔴 Node-Reference Lookup (CHECKED FIRST)

**Node Type:** {nodeType}
**Reference Found:** ✅ YES / ❌ NO

**If YES:**
- **Reference File:** `.claude/node-reference/{path}`
- **TypeVersion:** {version from reference}
- **Anti-Memory Flag:** {true/false}
- **Last Verified:** {date}

**Reference Configuration (VERIFIED):**
```json
{configuration from node-reference file}
```

⚠️ **Anti-Memory Warning (if applicable):**
> This node has documented recurring failure patterns.
> USE REFERENCE CONFIGURATION EXACTLY - do not modify based on memory.

---

### Pattern Library Matches

**Pattern 1:** {pattern name}
- **Location:** `.claude/patterns/{pattern}/`
- **Relevance:** {HIGH/MEDIUM/LOW}
- **Solution Summary:** {what the pattern solves}

---

### Node Documentation (MCP - ONLY IF NO REFERENCE)

**Note:** This section only populated if no node-reference exists.

**Node Type:** {nodeType}
**Latest TypeVersion:** {version}
**Required Parameters:**
- {param1}: {description}
- {param2}: {description}

**Common Mistakes:**
- {mistake 1}
- {mistake 2}

**Correct Configuration Example:**
```json
{authoritative configuration from docs}
```

---

### Template Examples Found

**Template 1:** {template name} (ID: {id})
- **Relevance:** {HIGH/MEDIUM/LOW}
- **Key Insight:** {what can be learned}
- **Node Configuration:**
```json
{relevant node configuration from template}
```

---

### Evolution Log Positive Patterns

**Matching Pattern:** {pattern name} ({date})
- **Original Issue:** {what was wrong}
- **Solution Applied:** {what fixed it}
- **Reusable Guidance:** {when to apply}

---

### Recommended Solution

**Primary Source:** {node-reference | pattern-library | MCP | template}
**Primary Solution:** {description}
**Confidence:** {HIGH/MEDIUM/LOW}
**Evidence:** {source of solution - reference file, template, docs, pattern}

**Alternative Solutions:**
1. {alternative 1} - Confidence: {level}
2. {alternative 2} - Confidence: {level}
```

---

### PHASE 4: Implementation (Robustness-First)

**Director Objective:** Implement correct solution with full validation

**Implementation Principles:**
- Take as long as needed for correct implementation
- Validate thoroughly before applying
- Create rollback capability
- Test before declaring success

```javascript
// 1. Create corrected node configuration
const correctedConfig = {
  // Based on research from Phase 3
  // Using authoritative documentation
  // Following proven patterns
};

// 2. Validate configuration before applying
const validation = await mcp__n8n-mcp__validate_node({
  nodeType: failedNode.type,
  config: correctedConfig,
  mode: 'full',
  profile: 'strict'
});

if (!validation.valid) {
  // Debug and fix validation errors
  // DO NOT proceed with invalid configuration
}

// 3. Apply fix using partial update (safer than full update)
const updateResult = await mcp__n8n-mcp__n8n_update_partial_workflow({
  id: workflowId,
  operations: [
    {
      type: 'updateNode',
      nodeName: failedNode.name,
      updates: {
        parameters: correctedConfig
      }
    }
  ],
  validateOnly: false
});

// 4. Validate workflow after update
const workflowValidation = await mcp__n8n-mcp__n8n_validate_workflow({
  id: workflowId
});

// 5. Test execution (if possible)
// Note: Only if workflow can be safely triggered
```

**Implementation Report:**

```markdown
## PHASE 4: Implementation Report

### Changes Applied

**Node Modified:** {nodeName}
**Operation Type:** updateNode

**Before:**
```json
{previous configuration}
```

**After:**
```json
{new configuration}
```

---

### Validation Results

**Pre-Apply Validation:** {PASSED/FAILED}
**Post-Apply Workflow Validation:** {PASSED/FAILED}
- Errors: {count}
- Warnings: {count}

---

### Test Execution (if performed)

**Execution ID:** {id}
**Status:** {SUCCESS/FAILED}
**Duration:** {time}

---

### Rollback Information

**Rollback Command:**
```javascript
await mcp__n8n-mcp__n8n_update_partial_workflow({
  id: '{workflowId}',
  operations: [
    {
      type: 'updateNode',
      nodeName: '{nodeName}',
      updates: {
        parameters: {previous configuration}
      }
    }
  ]
});
```

**Version History:** Workflow version saved before modification
```

---

### PHASE 4.5: Topology Validation (MANDATORY - HARDCODED)

**Director Objective:** Validate ALL nodes upstream AND downstream from the fix location

**CRITICAL:** This phase is MANDATORY and HARDCODED. Every fix MUST trigger complete topology validation. Node issues cascade - a fix at one point often reveals or creates issues at connected nodes.

**Why This Is Required:**
- Node failures often have upstream causes (wrong input data type, missing binary data)
- Fixes can break downstream nodes (changed output schema, missing expected fields)
- Route/Switch nodes amplify cascading failures across multiple branches
- Anti-Memory failures (e.g., Chat→Image chain) only surface at downstream nodes

```javascript
// MANDATORY: Run topology validation for EVERY fix
const topologyValidation = async (workflowId, fixedNodeName) => {
  // 1. Get full workflow structure
  const workflow = await mcp__n8n-mcp__n8n_get_workflow({
    id: workflowId,
    mode: 'structure'
  });

  // 2. Map ALL upstream nodes
  const upstreamNodes = mapUpstream(workflow, fixedNodeName);

  // 3. Map ALL downstream nodes
  const downstreamNodes = mapDownstream(workflow, fixedNodeName);

  // 4. Validate each node in topology
  const issues = [];

  for (const node of [...upstreamNodes, ...downstreamNodes]) {
    const validation = await mcp__n8n-mcp__validate_node({
      nodeType: node.type,
      config: node.parameters,
      mode: 'full',
      profile: 'strict'
    });

    if (!validation.valid) {
      issues.push({ node: node.name, errors: validation.errors });
    }
  }

  return { upstreamNodes, downstreamNodes, issues };
};
```

**Topology Validation Report (REQUIRED OUTPUT):**

```markdown
## PHASE 4.5: Topology Validation Report

**Fixed Node:** {nodeName}
**Validation Scope:** ALL connected nodes upstream and downstream

---

### Upstream Topology (nodes that feed INTO fixed node)

**Upstream Chain:**
```
{Node A} → {Node B} → {Node C} → **[FIXED: {nodeName}]**
```

**Upstream Nodes Validated:** {count}

| Node Name | Type | Valid? | Issues |
|-----------|------|--------|--------|
| {name} | {type} | ✅/❌ | {issues or "None"} |
| {name} | {type} | ✅/❌ | {issues or "None"} |

**Upstream Data Flow Check:**
- [ ] All upstream nodes produce expected output schema
- [ ] Binary data flows correctly (if applicable)
- [ ] No type mismatches (e.g., Chat node feeding Image node)

---

### Downstream Topology (nodes that receive FROM fixed node)

**Downstream Chain:**
```
**[FIXED: {nodeName}]** → {Node D} → {Node E} → {Node F}
```

**Downstream Nodes Validated:** {count}

| Node Name | Type | Valid? | Issues |
|-----------|------|--------|--------|
| {name} | {type} | ✅/❌ | {issues or "None"} |
| {name} | {type} | ✅/❌ | {issues or "None"} |

**Downstream Data Flow Check:**
- [ ] Fixed node output matches downstream input expectations
- [ ] All downstream nodes receive correct data types
- [ ] Route/Switch branches all validated

---

### Cascade Impact Analysis

**Potential Cascade Issues Found:** {count}

| Issue | Location | Root Cause | Required Fix |
|-------|----------|------------|--------------|
| {issue} | {upstream/downstream node} | {cause} | {fix needed} |

---

### Topology Validation Status

**Status:** {PASSED | FAILED | PARTIAL}

- **PASSED:** All upstream/downstream nodes validated, no cascade issues
- **FAILED:** Critical issues found in topology - MUST fix before proceeding
- **PARTIAL:** Warnings found but not blocking - document and monitor

**If FAILED:** Return to PHASE 4 - fix cascade issues before verification
**If PASSED/PARTIAL:** Proceed to PHASE 5 (Verification)
```

**Common Topology Failure Patterns (HARDCODED CHECKS):**

| Pattern | Upstream Check | Downstream Check |
|---------|---------------|------------------|
| **Binary Data Chain** | Does upstream produce binary? | Does downstream expect binary? |
| **Chat→Image Mismatch** | Is upstream Chat node? | Is downstream Image node? Remove Chat. |
| **Route/Switch Branches** | Is trigger valid? | Are ALL branches valid? |
| **JSON Schema Mismatch** | What schema does upstream output? | What schema does downstream expect? |
| **Missing Fields** | What fields does upstream provide? | What fields does downstream require? |

**HARDCODED RULE:** If Route/Switch node is in topology:
1. Validate EVERY branch endpoint
2. Check that each branch has compatible node chains
3. Verify no branch has type mismatches

---

### PHASE 5: Verification Gate (MANDATORY HARDCODED - NO BYPASS)

**Director Objective:** Confirm fix works BEFORE documenting

## 🔴🔴🔴 CRITICAL: HARDCODED VERIFICATION GATE 🔴🔴🔴

**This phase is MANDATORY and CANNOT be bypassed. Documentation (PHASE 6) is LOCKED until verification passes.**

**Why This Is Hardcoded:**
- Documenting unverified patterns causes recursive failures
- Anti-patterns documented as "correct" poison future implementations
- User confirmation ensures real-world validation, not just schema validation
- MCP validators can have false positives (e.g., `toolDescription` vs `description` bug)

**HARD RULES:**
1. ❌ **NEVER proceed to PHASE 6 without explicit user confirmation**
2. ❌ **NEVER document patterns based on schema validation alone**
3. ❌ **NEVER assume a fix works - require proof**
4. ✅ **ALWAYS present findings to user and wait for confirmation**
5. ✅ **ALWAYS ask user to test workflow before documenting**

```markdown
## PHASE 5: Verification Gate (HARD GATE - BLOCKING)

### 🔴 MANDATORY: User Confirmation Required

**Before ANY documentation can occur, the user MUST confirm one of:**

- [ ] **Option A:** "Yes, the workflow now executes correctly" (user tested)
- [ ] **Option B:** "Yes, I verified the node configuration is correct" (manual verification)
- [ ] **Option C:** Provide execution ID showing successful run

**Without explicit user confirmation, PHASE 6 is LOCKED.**

---

### Verification Checklist

**Structural Verification (Claude performs):**
- [ ] Workflow validation passes (0 critical errors)
- [ ] No blocking warnings that would prevent execution
- [ ] All node configurations validate successfully
- [ ] Validation errors analyzed for false positives (MCP validator bugs)

**Runtime Verification (User performs or confirms):**
- [ ] Workflow executes without the original error
- [ ] Expected output is produced
- [ ] No new errors introduced

---

### Present Findings to User

**REQUIRED OUTPUT before proceeding:**

```markdown
## Verification Gate - Awaiting User Confirmation

**Workflow:** {workflowId}
**Fix Applied:** {description of fix}

### Structural Validation Results

**Errors:** {count}
**Warnings:** {count}

**Error Analysis:**
| Error | Analysis | Verdict |
|-------|----------|---------|
| {error} | {is this real or false positive?} | {REAL/FALSE_POSITIVE} |

### Fix Summary

**Node:** {nodeName}
**Change:** {before → after}

**Configuration Now:**
```json
{current configuration}
```

---

## 🔴 CONFIRMATION REQUIRED

Before I document any patterns, please confirm:

**Does the workflow now work correctly?**

- [ ] **YES** - Workflow executes as expected (proceed to documentation)
- [ ] **NO** - Still broken (return to debugging)
- [ ] **UNTESTED** - I need to test it first (pause and wait)

*Awaiting your confirmation before proceeding to Phase 6...*
```

---

### Verification Status

**Verification Method:** {structural | execution | user-confirmed}
**User Response:** {WAITING | YES | NO | UNTESTED}
**Status:** {BLOCKED | PASSED | FAILED}

**Status Definitions:**
- **BLOCKED:** Waiting for user confirmation - CANNOT proceed to PHASE 6
- **PASSED:** User confirmed fix works - proceed to PHASE 6
- **FAILED:** User reported still broken - return to PHASE 4

**If BLOCKED:** Wait for user response. Do NOT proceed.
**If PASSED:** Proceed to PHASE 6 (Documentation)
**If FAILED:** Return to PHASE 4 (Implementation) with user feedback
```

**Verification Flow:**

```
Fix Applied (PHASE 4)
        │
        ▼
  Topology Validation (PHASE 4.5)
        │
        ▼
  Validate Workflow Structure
        │
        ├─ FAIL → Return to PHASE 4
        │
        ▼
  🔴 HARD GATE: Present findings to user
        │
        ▼
  🔴 HARD GATE: Wait for user confirmation
        │
        ├─ User says YES → PHASE 6 (Documentation) UNLOCKED
        │
        ├─ User says NO → Return to PHASE 4 with feedback
        │
        └─ User says UNTESTED → WAIT (stay blocked)
        │
        └─ NO RESPONSE → STAY BLOCKED (do not proceed)
```

## 🔴 ANTI-PATTERN: Proceeding Without Confirmation

**The following is EXPLICITLY FORBIDDEN:**

```markdown
❌ WRONG: "The workflow validates, proceeding to document the pattern..."
❌ WRONG: "Fix applied successfully, updating agents-evolution.md..."
❌ WRONG: "No critical errors, documenting the solution..."

✅ CORRECT: "Fix applied. Awaiting your confirmation before documenting..."
✅ CORRECT: "Please test the workflow and confirm it works before I update documentation."
```

**NEVER document patterns that haven't been verified by the user.**

---

### PHASE 6: Documentation (ONLY After Verification)

**Director Objective:** Document VERIFIED patterns AND correct incorrect documentation

**PREREQUISITE:** PHASE 5 Verification MUST be PASSED before this phase.

**CRITICAL RULES:**
- ✅ Only document patterns that have been VERIFIED working
- ✅ Only add new content - never delete existing patterns
- ✅ **CORRECT existing patterns if Documentation Error was found in Phase 2 audit**
- ✅ Format entries to match existing documentation style
- ✅ Update statistics accurately
- ✅ Maintain intuitive structure for all experience levels
- ❌ NEVER document speculative or untested solutions

---

## 🔴 IF DOCUMENTATION ERROR WAS FOUND: Correction Protocol

**When Phase 2 audit verdict = "Documentation Error", you MUST:**

### Step 0: Correct the Incorrect Pattern File

**Before adding new patterns, FIX the source of the error:**

```markdown
## Pattern Correction Required

**File:** {pattern file path}
**Error Found:** {what was wrong}
**Correction Applied:** {what was fixed}

### Before (INCORRECT):
```json
{old incorrect configuration}
```

### After (CORRECT - verified working):
```json
{new correct configuration}
```

**Anti-Pattern Warning Added:**
> ⚠️ **INCORRECT (causes {error type}):** {old way}
> ✅ **CORRECT:** {new way}
```

**Correction Checklist:**
- [ ] Pattern file corrected with verified working configuration
- [ ] Anti-pattern warning added to prevent future misuse
- [ ] "Last Verified" date updated in pattern file
- [ ] If CLAUDE.md rule was wrong, CLAUDE.md updated
- [ ] agents-evolution.md entry added documenting the correction

**Documentation Targets:**

```javascript
// Determine what needs documenting based on root cause category
const documentationPlan = determineDocumentationNeeds({
  rootCauseCategory: analysis.category,
  isNewPattern: !existingPatternMatch,
  severity: analysis.severity,
  reusability: analysis.reusability
});

// Documentation targets by category:
const targets = {
  'Documentation Error': [
    '{pattern file that was wrong}',     // CORRECT the incorrect pattern
    '.claude/agents-evolution.md',       // Document the correction
    '.claude/CLAUDE.md'                  // Update if core rules were wrong
  ],
  'LLM Error': [
    '{pattern file}',                    // Add explicit examples, strengthen wording
    '.claude/agents-evolution.md'        // Document failure mode for future reference
  ],
  'Process Gap': [
    '.claude/CLAUDE.md',                 // Update protocol
    '.claude/WORKFLOW-DEVELOPMENT-PROTOCOL.md'  // Add checklist item
  ],
  'Knowledge Gap': [
    '.claude/agents-evolution.md',       // Document anti-pattern + positive pattern
    '.claude/patterns/{category}/'       // Create reusable pattern
  ],
  'Tool Misuse': [
    '.claude/agents-evolution.md',       // Document mistake and fix
    '.claude/commands/{relevant-command}.md'  // Update command docs
  ],
  'Design Flaw': [
    '.claude/agents-evolution.md',       // Document architectural pattern
    '.claude/patterns/{category}/'       // Create design pattern
  ],
  'API Change': [
    '.claude/agents-evolution.md',       // Document API behavior change
    '{affected pattern files}'           // Update all affected patterns
  ],
  'Configuration Drift': [
    '.claude/WORKFLOW-DEVELOPMENT-PROTOCOL.md',  // Add validation step
    'Update monitoring recommendations'
  ]
};
```

**Documentation Protocol:**

#### Step 1: Add to agents-evolution.md (Always)

```markdown
## [YYYY-MM-DD] Workflow: {workflow-name} ({workflowId})

### Anti-Pattern: {concise description of what went wrong}
**What Happened:** {2-3 sentences describing the failure}

**Impact:**
- {Specific impact 1}
- {Specific impact 2}
- {Metrics if available}

**Why It Failed:** {Root cause from 5-Why analysis}

### Positive Pattern: {concise description of solution}
**Solution:** {2-3 sentences describing the fix}

**Implementation:**
1. {Step 1}
2. {Step 2}
3. {Step 3}

**Result:**
- {Measurable result 1}
- {Measurable result 2}
- {Validation evidence}

**Reusable Pattern:**
{When to apply this pattern - specific scenarios and indicators}

**Reference Files:**
- Workflow: `workflows/development/{workflow-name}/`
- Pattern: `.claude/workflow-examples/patterns/{pattern-name}/` (if created)
```

#### Step 2: Create Pattern in Pattern Library (If Reusable)

```bash
mkdir -p .claude/workflow-examples/patterns/{pattern-name}
```

**pattern.md:**
```markdown
# {Pattern Name}

**Quality Level:** ✅ Production-Ready
**Category:** {category}
**Discovered:** {date}
**Source Workflow:** {workflow-name} ({workflowId})

---

## When to Use This Pattern

Use this pattern when:
- ✅ {condition 1}
- ✅ {condition 2}

Do NOT use when:
- ❌ {exception 1}
- ❌ {exception 2}

---

## Problem Solved

{Description of the problem this pattern solves}

---

## Implementation

### Node Configuration

```json
{correct node configuration}
```

### Connection Pattern

```
{visual flow diagram}
```

---

## Common Mistakes

1. **{Mistake 1}:** {description and how to avoid}
2. **{Mistake 2}:** {description and how to avoid}

---

## Troubleshooting

### Error: {common error}
- **Cause:** {why it happens}
- **Fix:** {how to resolve}

---

## References

- [agents-evolution.md](../../../agents-evolution.md) - Full pattern documentation
- [n8n Docs]({relevant n8n doc link}) - Official documentation
```

**pattern.json:**
```json
{
  "name": "{Pattern Name}",
  "description": "{Brief description}",
  "version": "1.0",
  "nodes": [
    {correct node configuration}
  ],
  "connections": {
    // Correct connection pattern
  }
}
```

#### Step 3: Update Pattern Library README

Add new pattern to index:

```markdown
### {Category} Patterns
{existing patterns}
N. ✅ [{Pattern Name}](./{pattern-name}/) - **NEW** {brief description}
```

#### Step 4: Update Statistics

In agents-evolution.md:

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

#### Step 5: Verify Integration Integrity

```javascript
// Verify no existing value was harmed
const verifyIntegrity = async () => {
  // 1. Check agents-evolution.md still valid markdown
  // 2. Verify pattern library README links work
  // 3. Confirm no duplicate patterns
  // 4. Validate statistics are accurate
  // 5. Check pattern.json is valid
};
```

**Documentation Report:**

```markdown
## PHASE 5: Documentation Report

### Files Modified

1. **`.claude/agents-evolution.md`**
   - Added: Anti-pattern + Positive pattern entry
   - Updated: Pattern statistics
   - Integrity: ✅ Verified

2. **`.claude/workflow-examples/patterns/{pattern-name}/`** (if created)
   - Created: pattern.md, pattern.json
   - Quality Level: ✅ Production-Ready

3. **`.claude/workflow-examples/patterns/README.md`**
   - Added: Pattern index entry
   - Total Patterns: {new count}

---

### Integration Verification

- [ ] No existing patterns deleted
- [ ] No existing documentation modified (unless correcting errors)
- [ ] Statistics accurately updated
- [ ] Pattern follows existing format
- [ ] Accessible to all experience levels

---

### Commit Message (if requested)

```
docs(evolution): add pattern for {category} - {brief description}

Anti-pattern: {one-line summary}
Positive pattern: {one-line summary}
Workflow: {workflow-name} ({workflowId})
Root cause: {category} - {brief root cause}

Files:
- .claude/agents-evolution.md
- .claude/workflow-examples/patterns/{pattern-name}/ (if created)
- .claude/workflow-examples/patterns/README.md
```
```

---

## Complete Execution Example

**User:** `/synrg-n8ndebug Ge33EW4K3WVHT4oG`

**SYNRG N8N Debugger Response:**

```markdown
# SYNRG N8N Debug Session

**Target Workflow:** SYNRG Invoice Generator (Ge33EW4K3WVHT4oG)
**Protocol:** SYNRG Director/Orchestrator v4.0
**Mode:** Full Debug + Documentation

---

## PHASE 1: Issue Identification

**Director:** Spawning 3 parallel sub-agents for reconnaissance...

### Execution History Analysis

**Recent Executions:**
- Execution #1892: ERROR at "Update Invoice Document" (2 hours ago)
- Execution #1890: ERROR at "Update Invoice Document" (3 hours ago)
- Execution #1887: SUCCESS (5 hours ago)

**Failure Rate:** 66% in last 5 hours

### Failed Execution Details

**Execution ID:** 1892
**Failed Node:** Update Invoice Document
**Node Type:** n8n-nodes-base.googleDocs (typeVersion: 2)
**Error:**
```
Bad request - please check your parameters
```

**Input to Failed Node:**
```json
{
  "documentId": "19B9nOPr...",
  "actionsUi": {
    "actionFields": [
      {
        "action": "replaceAll",
        "searchValue": "{{INVOICE_ID}}",
        "replaceValue": "4203"
      }
      // ... 17 more replacements
    ]
  }
}
```

### Pattern Search Results

**Matching Patterns:** 0 (NEW pattern type)

---

## PHASE 2: 5-Why Root Cause Analysis

### Why 1 - Surface Symptom
**Q:** Why did the workflow fail?
**A:** Google Docs node returned "Bad request - please check your parameters"

### Why 2 - Immediate Cause
**Q:** Why did the Google Docs node return this error?
**A:** The native node's replaceAll operation is not formatting the API request correctly

### Why 3 - Technical Cause
**Q:** Why is the replaceAll operation failing?
**A:** n8n's native Google Docs node has known reliability issues with batchUpdate operations

### Why 4 - Design Cause
**Q:** Why was the native node used despite known issues?
**A:** Pattern for using HTTP Request + batchUpdate API was not documented in project

### Why 5 - Root Cause
**Q:** Why was this pattern not documented?
**A:** Knowledge gap - no prior experience with Google Docs template population in this project

## Root Cause Identified

**Category:** Knowledge Gap
**Root Cause:** Native Google Docs node has undocumented reliability issues with replaceAll operations. Official n8n templates use HTTP Request for this operation.

---

## PHASE 3: Solution Research

**Director:** Spawning 4 parallel research agents...

### Template Research

**Found:** Template #3145 "Replace Data in Google Docs from n8n Form"
- Uses HTTP Request node instead of native Google Docs node
- Calls batchUpdate API directly
- **Relevance:** HIGH

### Node Documentation

**Google Docs Node (typeVersion 2):**
- replaceAll operation exists but has known issues
- Documentation recommends using for simple operations

**HTTP Request + Google Docs API:**
- batchUpdate endpoint: `POST /documents/{documentId}:batchUpdate`
- Full control over request format
- More reliable for complex operations

### Recommended Solution

**Primary Solution:** Replace native Google Docs node with HTTP Request calling batchUpdate API
**Confidence:** HIGH
**Evidence:** Official template #3145 uses this pattern

---

## PHASE 4: Implementation

### Changes Applied

**Added Nodes:**
1. "Format Replace Requests" (Code node) - Builds API request body
2. "Update Invoice Document (API)" (HTTP Request) - Calls batchUpdate

**Removed Nodes:**
1. "Update Invoice Document" (native Google Docs node)

**Validation Results:**
- Pre-Apply: PASSED
- Post-Apply: PASSED (0 errors, 0 warnings)

---

## PHASE 5: Documentation

### Pattern Created

**Location:** `.claude/workflow-examples/patterns/google-docs-batchupdate/`

**Added to agents-evolution.md:**
- Anti-Pattern: Using Native Google Docs Node for replaceAllText Operations
- Positive Pattern: Use HTTP Request Node with Google Docs batchUpdate API

**Pattern Library Updated:**
- Total Patterns: 5 → 6

### Documentation Integrity

- ✅ No existing patterns deleted
- ✅ No existing documentation modified
- ✅ Statistics accurately updated
- ✅ Pattern follows existing format

---

## Summary

**Issue:** Native Google Docs node failing on template population
**Root Cause:** Knowledge gap - undocumented node reliability issue
**Solution:** HTTP Request + batchUpdate API (pattern from template #3145)
**Documentation:** Pattern added to agents-evolution.md and pattern library

**Would you like me to commit these changes?**
```

---

## Success Criteria

**Debug session is complete when:**

1. ✅ Pre-debug triage completed (PHASE 0)
2. ✅ **Documentation Consistency Audit completed** (PHASE 0.5 - MANDATORY HARDCODED)
3. ✅ **All documentation contradictions resolved** (PHASE 0.5 - if any found)
4. ✅ Issue identified with execution/structural context (PHASE 1)
5. ✅ 5-Why root cause analysis completed (PHASE 2)
6. ✅ **Documentation Validity Audit completed** (PHASE 2 - MANDATORY)
7. ✅ **Node-Reference checked FIRST before MCP tools** (PHASE 3 - MANDATORY)
8. ✅ Solution researched from authoritative sources (PHASE 3)
9. ✅ Fix implemented and validated (PHASE 4)
10. ✅ **Topology validation completed - ALL upstream/downstream nodes checked** (PHASE 4.5 - MANDATORY HARDCODED)
11. ✅ **Fix VERIFIED working** (PHASE 5 - MANDATORY)
12. ✅ **If Documentation Error: incorrect patterns CORRECTED** (PHASE 6)
13. ✅ Pattern documented in agents-evolution.md (PHASE 6 - ONLY after verification)
14. ✅ Reusable pattern created (if applicable)
15. ✅ Statistics updated
16. ✅ No existing CORRECT documentation harmed (incorrect docs MUST be fixed)

**CRITICAL:** Steps 12-16 MUST NOT occur until Step 11 (Verification) passes.
**CRITICAL:** Step 2-3 (Documentation Consistency Audit) is HARDCODED - cannot be skipped. Contradictions MUST be resolved before debugging.
**CRITICAL:** Step 7 (Node-Reference Lookup) is MANDATORY - check local reference BEFORE using MCP tools.
**CRITICAL:** Step 10 (Topology Validation) is HARDCODED - cannot be skipped for ANY fix.
**CRITICAL:** Step 11 (User Verification) is HARDCODED - user MUST explicitly confirm fix works before ANY documentation. MCP validators can have false positives.

**DOCUMENTATION ERROR HANDLING:** If audit finds incorrect patterns, those patterns MUST be corrected in Phase 6. This is the ONLY case where existing documentation is modified.

---

## Integration with Existing Commands

**This command integrates with:**

- `/n8n-debug` - Basic debugging (synrg-n8ndebug is enhanced version)
- `/n8n-evolve` - Pattern documentation (integrated into Phase 5)
- `/n8n-validate` - Workflow validation (used in Phase 4)
- `/n8n-build` - Workflow creation (patterns feed back here)

**Workflow:**
```
Error Occurs → /synrg-n8ndebug → Fix Applied → Pattern Documented → /n8n-build uses pattern
```

---

## Quick Reference

**Command Variants:**

```bash
# Debug specific workflow
/synrg-n8ndebug Ge33EW4K3WVHT4oG

# Debug last failed workflow
/synrg-n8ndebug last

# Debug with specific execution
/synrg-n8ndebug --execution 1892
```

**Phases:**
0. **Triage** - Ask about execution check vs structure check
0.5. **Consistency Audit** - Verify documentation internal consistency (MANDATORY HARDCODED)
1. **Identify** - Gather execution/structural context
2. **Analyze** - 5-Why root cause + **Documentation Validity Audit** (MANDATORY)
3. **Research** - **Node-Reference FIRST** → patterns → MCP (only if no reference) → templates
4. **Implement** - Apply and validate fix using verified reference configurations
4.5. **Topology** - Validate ALL upstream/downstream nodes (MANDATORY HARDCODED)
5. **Verify** - CONFIRM fix works (MANDATORY gate)
6. **Document** - Correct incorrect patterns (if found) + integrate VERIFIED patterns

---

## Documentation Integrity Rules

**NEVER:**
- ❌ Delete existing CORRECT patterns
- ❌ Skip documentation phase
- ❌ Create duplicate patterns
- ❌ Document unverified solutions

**ALWAYS:**
- ✅ Add new content in appropriate sections
- ✅ Follow existing documentation format
- ✅ Update statistics accurately
- ✅ Verify integrity after changes
- ✅ Make content accessible to all experience levels
- ✅ **CORRECT incorrect patterns when Documentation Error is found**

**MODIFICATION IS REQUIRED WHEN:**
- Documentation Validity Audit finds a pattern rule is WRONG
- MCP authoritative source contradicts existing pattern
- Verified working fix contradicts documented pattern

**When modifying incorrect patterns:**
1. Add anti-pattern warning to the old incorrect rule
2. Document the correction in agents-evolution.md
3. Update "Last Verified" date
4. Keep history of what was wrong for learning

---

**Version:** 1.5.0
**Last Updated:** 2025-12-27
**Philosophy:** SYNRG v4.0 - Value-First + Robustness-First + **Self-Correcting Documentation** + **Documentation Consistency Audit** + **Topology-Aware Debugging** + **Node-Reference First**

---

## Changelog

### v1.6.0 (2025-12-28)
- **ADDED:** PHASE 5 - Mandatory User Verification Gate (HARDCODED - NO BYPASS)
  - Documentation (PHASE 6) is now LOCKED until user explicitly confirms fix works
  - Cannot proceed to documentation based on schema validation alone
  - MCP validators can have false positives (e.g., `toolDescription` vs `description` bug discovered)
  - User must confirm: "YES workflow works", "NO still broken", or "UNTESTED need to test"
  - Explicit anti-pattern examples of what NOT to do (proceeding without confirmation)
- **ROOT CAUSE:** Claude was documenting unverified patterns, causing recursive failures
- **EVOLUTION:** This ensures only VERIFIED patterns are documented, preventing poisoned documentation

### v1.5.0 (2025-12-27)
- **ADDED:** PHASE 0.5 - Documentation Consistency Audit (MANDATORY HARDCODED)
  - Verifies all documentation files agree on typeVersion and configuration for each node type
  - Compares: pattern-index.json, node-reference files, pattern files, reference workflows
  - Detects contradictions BEFORE debugging begins
  - Halts and corrects documentation if contradictions found
  - Prefers verified reference workflows over MCP "latest version" claims
- **ADDED:** Reference Workflow Registry for verified working configurations
- **ADDED:** AI Agent Node Anti-Pattern documentation (typeVersion 3.1 → 3)
- **ROOT CAUSE:** Documentation inconsistency between files caused repeated implementation failures
- **EVOLUTION:** This enhancement ensures documentation is internally consistent before trusting it
