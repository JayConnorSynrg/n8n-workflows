# SYNRG Context-Finding Protocol

**Version:** 1.0.0
**Created:** 2025-11-22
**Purpose:** Systematic protocol for identifying and selecting ideal workflow context for n8n workflow development

---

## Protocol Overview

This protocol ensures optimal context selection when developing n8n workflows by systematically searching, evaluating, and selecting working examples that align with target workflow requirements.

**Core Principle:** Always build on proven patterns from working examples rather than assumptions.

---

## Phase 1: Requirement Analysis

### Step 1.1: Extract Target Workflow Requirements

**Process:**
1. Parse user's workflow description
2. Identify core capabilities needed
3. Classify requirements by category

**Requirement Categories:**

**Functional Requirements:**
- Trigger type (webhook, schedule, manual, form)
- Data processing needs (transformation, enrichment, validation)
- External integrations (APIs, databases, services)
- AI capabilities (agents, image generation, text processing)
- Output destinations (database, file, webhook response, email)

**Technical Requirements:**
- Node types needed (native, AI, integration, code)
- Data flow patterns (linear, branching, loop, parallel)
- Error handling complexity (simple retry, complex fallback)
- Performance constraints (rate limits, execution time)

**Architecture Requirements:**
- Modularity (single workflow vs. sub-workflows)
- Scalability (batch processing, queuing)
- Monitoring (logging, notifications)

**Output Format:**
```markdown
## Target Workflow: {workflow-name}

**Purpose**: {one-sentence description}

**Core Capabilities Required**:
1. {capability-1} - {why needed}
2. {capability-2} - {why needed}
3. {capability-3} - {why needed}

**Node Types Needed**:
- [ ] Trigger: {type}
- [ ] AI Processing: {specific nodes}
- [ ] External APIs: {services}
- [ ] Data Storage: {type}
- [ ] Loop/Iteration: {yes/no}

**Critical Features**:
- {feature-1}: {requirement}
- {feature-2}: {requirement}

**Complexity Level**: {Simple / Medium / Complex}
```

---

## Phase 2: Multi-Source Search Strategy

### Step 2.1: Search n8n Official Templates

**Rationale:** Official templates are production-tested and follow best practices

**Method:**
```javascript
// Primary search - broad match
mcp__n8n-mcp__search_templates({
  query: "{workflow purpose keywords}",
  limit: 20
})

// Secondary search - specific capabilities
mcp__n8n-mcp__search_templates({
  query: "{specific node type or integration}",
  limit: 10
})
```

**Evaluation Criteria:**
- Views (popularity indicator)
- Node count (complexity match)
- Description match (purpose alignment)
- Created date (recency for modern practices)

**Output:**
```markdown
### Official Templates Found:

1. **Template #{id}: "{name}"**
   - Views: {count}
   - Nodes: {count}
   - Relevance: {0-100%}
   - Key nodes: {list}
   - Match reason: {why relevant}
   - URL: {n8n.io link}

2. **Template #{id}: "{name}"**
   - ...
```

### Step 2.2: Search Community Workflows (n8n-workflows MCP)

**Rationale:** Real-world implementations may contain patterns not in official templates

**Method:**
```javascript
// Search repository code for specific node types
mcp__n8n-workflows__search_code({
  q: "{node-type} in:file language:json repo:Zie619/n8n-workflows"
})

// Search for workflow descriptions
mcp__n8n-workflows__search_code({
  q: "{workflow-purpose-keywords} in:file extension:json repo:Zie619/n8n-workflows"
})
```

**Search Patterns:**
1. **By Node Type:**
   - `"@n8n/n8n-nodes-langchain.agent" in:file`
   - `"n8n-nodes-base.googleDrive" in:file`
   - `"type": "Loop" in:file`

2. **By Capability:**
   - `"image" AND "generate" in:file`
   - `"loop" AND "items" in:file`
   - `"ai" AND "agent" in:file`

3. **By Integration:**
   - Service name + "tool" or "api"
   - Credential type searches

**Output:**
```markdown
### Community Workflows Found:

1. **File: {path}**
   - Repository: Zie619/n8n-workflows
   - Match type: {node-type / keyword / integration}
   - Preview: {code snippet}
   - Relevance: {0-100%}
   - Action: Retrieve full file ✓

2. **File: {path}**
   - ...
```

### Step 2.3: Search Working n8n Instance Workflows

**Rationale:** Your own working workflows are proven in your environment

**Method:**
```javascript
// List all workflows
mcp__n8n-mcp__n8n_list_workflows({
  limit: 100
})

// Get specific workflow details for candidates
mcp__n8n-mcp__n8n_get_workflow_structure({
  id: "{workflow-id}"
})

// Check execution success rate
mcp__n8n-mcp__n8n_list_executions({
  workflowId: "{workflow-id}",
  limit: 50
})
```

**Evaluation Criteria:**
- Active status (currently in use)
- Execution success rate (>90% preferred)
- Recency (actively maintained)
- Similar node composition

**Output:**
```markdown
### Instance Workflows Found:

1. **Workflow: {name} (ID: {id})**
   - Status: {active/inactive}
   - Success rate: {X}%
   - Recent executions: {count in last 30 days}
   - Similar nodes: {list}
   - Relevance: {0-100%}

2. **Workflow: {name}**
   - ...
```

### Step 2.4: Search Pattern Library

**Rationale:** Documented patterns in `.claude/workflow-examples/` are curated and proven

**Method:**
```bash
# Search pattern index
cat .claude/workflow-examples/_index.json | jq '.patterns[] | select(.tags | contains(["ai-agent"]))'

# Read specific pattern
cat .claude/workflow-examples/patterns/{pattern-id}/pattern.json
cat .claude/workflow-examples/patterns/{pattern-id}/pattern.md
```

**Evaluation Criteria:**
- Tag match (pattern tags align with requirements)
- Complexity level (matches target workflow)
- Production readiness (marked as tested)
- Common mistakes documented (helps avoid pitfalls)

**Output:**
```markdown
### Pattern Library Matches:

1. **Pattern: {pattern-id}**
   - Tags: {list}
   - Complexity: {Simple/Medium/Complex}
   - Nodes: {count}
   - Production tested: {yes/no}
   - Common mistakes: {count documented}
   - Relevance: {0-100%}

2. **Pattern: {pattern-id}**
   - ...
```

---

## Phase 3: Context Candidate Evaluation

### Step 3.1: Score Each Candidate

**Scoring Matrix** (0-100 points total):

| Criterion | Weight | Scoring Method |
|-----------|--------|---------------|
| **Capability Match** | 30 pts | Count matching required capabilities / total required × 30 |
| **Node Type Similarity** | 20 pts | Count matching node types / total node types needed × 20 |
| **Production Readiness** | 15 pts | Has executions? Error handling? Tested? (5 pts each) |
| **Architectural Alignment** | 15 pts | Similar complexity? Similar data flow? Similar scale? (5 pts each) |
| **Recency & Maintenance** | 10 pts | Last updated <3 months: 10 pts, <6 months: 7 pts, <12 months: 4 pts, >12 months: 0 pts |
| **Documentation Quality** | 10 pts | Has README? Comments? Sticky notes? (3/3/4 pts) |

**Process:**
1. Evaluate each candidate against scoring matrix
2. Calculate total score
3. Rank candidates by score
4. Document reasoning for top 3

**Output:**
```markdown
## Candidate Evaluation Results

### Top Candidates (Ranked):

**1. {workflow-name} - Score: {X}/100**
- Capability match: {X}/30 - {reasoning}
- Node similarity: {X}/20 - {reasoning}
- Production readiness: {X}/15 - {reasoning}
- Architecture alignment: {X}/15 - {reasoning}
- Recency: {X}/10 - {reasoning}
- Documentation: {X}/10 - {reasoning}
- **Total: {X}/100**

**2. {workflow-name} - Score: {X}/100**
- ...

**3. {workflow-name} - Score: {X}/100**
- ...
```

### Step 3.2: Analyze Top Candidate in Detail

**Process:**
1. Retrieve full workflow JSON
2. Extract all node configurations
3. Analyze connection patterns
4. Document unique approaches
5. Identify reusable patterns
6. Note potential issues or limitations

**Method:**
```javascript
// Get complete workflow
mcp__n8n-mcp__get_template({
  templateId: {id},
  mode: "full"
})

// OR for community workflows
mcp__n8n-workflows__get_file_contents({
  owner: "Zie619",
  repo: "n8n-workflows",
  path: "{workflow-file-path}"
})

// OR for instance workflows
mcp__n8n-mcp__n8n_get_workflow({
  id: "{workflow-id}"
})
```

**Analysis Checklist:**
- [ ] All node types documented
- [ ] Connection patterns mapped
- [ ] Parameter configurations extracted
- [ ] Error handling approaches identified
- [ ] Data transformation methods noted
- [ ] Performance considerations documented
- [ ] Potential issues flagged

**Output:**
```markdown
## Detailed Analysis: {workflow-name}

### Architecture Overview:
```
{Visual representation of workflow structure}
[Trigger] → [Process 1] → [AI Agent] → [Process 2] → [Output]
              ↓ error
         [Error Handler]
```

### Node Breakdown:

**1. {Node Name} ({node.type})**
- **Type Version**: {typeVersion}
- **Purpose**: {what it does}
- **Key Parameters**:
  ```json
  {relevant parameters}
  ```
- **Connections**:
  - Input: {from where}
  - Output: {to where}
  - Error: {error handling}

**2. {Node Name}**
- ...

### Connection Patterns:

**Pattern 1: {pattern-name}**
- **Structure**: {description}
- **Purpose**: {why used}
- **Reusable**: {yes/no}

### Data Flow:

**Input Format:**
```json
{example input}
```

**Transformations:**
1. {Node name}: {input} → {output}
2. {Node name}: {input} → {output}

**Output Format:**
```json
{example output}
```

### Error Handling Strategy:

- **Retry logic**: {description}
- **Error branches**: {list}
- **Notifications**: {what/where}
- **Fallback**: {approach}

### Unique Approaches:

1. **{Approach 1}**: {description and why interesting}
2. **{Approach 2}**: {description and why interesting}

### Reusable Patterns Identified:

1. **Pattern: {pattern-name}**
   - **Nodes involved**: {list}
   - **Use case**: {when to apply}
   - **Implementation**: {how to replicate}

### Potential Issues:

1. **Issue**: {description}
   - **Impact**: {what could break}
   - **Mitigation**: {how to avoid}

### Adaptation Notes:

**What to keep:**
- {aspect 1}
- {aspect 2}

**What to modify:**
- {aspect 1}: {why and how}
- {aspect 2}: {why and how}

**What to add:**
- {missing feature 1}
- {missing feature 2}
```

---

## Phase 4: Context Selection Decision

### Step 4.1: Make Selection Decision

**Decision Criteria:**

**Select Single Best Candidate if:**
- ✅ Score >80/100
- ✅ Covers >90% of required capabilities
- ✅ Production-tested
- ✅ Architecture directly transferable

**Select Multiple Candidates if:**
- ⚠️ No single candidate scores >80
- ⚠️ Different candidates excel in different areas
- ⚠️ Hybrid approach would be optimal

**Continue Search if:**
- ❌ Top candidate scores <60/100
- ❌ Critical capabilities missing
- ❌ Architecture mismatch too severe

**Output:**
```markdown
## Context Selection Decision

**Decision**: {Single candidate / Multiple candidates / Continue search}

**Selected Context:**

**Primary:** {workflow-name} (Score: {X}/100)
- **Why selected**: {reasoning}
- **What to extract**: {specific patterns/nodes/approaches}
- **Coverage**: {X}% of requirements

**Secondary** (if applicable): {workflow-name} (Score: {X}/100)
- **Why selected**: {reasoning}
- **What to extract**: {specific patterns/nodes/approaches}
- **Fills gaps**: {what primary doesn't cover}

**Justification:**
{Detailed reasoning for selection decision, including trade-offs considered}

**Confidence Level**: {High / Medium / Low}
- {reasoning for confidence level}
```

### Step 4.2: Document Context Usage Plan

**Process:**
1. Map selected context to target workflow requirements
2. Identify exact nodes/patterns to reuse
3. Identify modifications needed
4. Plan integration approach
5. Document extraction steps

**Output:**
```markdown
## Context Usage Plan

### Requirement Mapping:

| Target Requirement | Source in Context | Modification Needed |
|-------------------|-------------------|---------------------|
| {requirement 1} | {node/pattern in context} | {none / minor / major} |
| {requirement 2} | {node/pattern in context} | {none / minor / major} |
| {requirement 3} | {not in context - need to build} | N/A |

### Reusable Components:

**1. {Component Name} (Nodes: {list})**
- **Source**: {workflow-name}, nodes {IDs}
- **Purpose**: {what it does}
- **Reuse approach**: {copy exact / modify parameters / adapt structure}
- **Parameters to change**:
  - {param 1}: {old value} → {new value}
  - {param 2}: {old value} → {new value}

**2. {Component Name}**
- ...

### Net-New Components Needed:

**1. {Component Name}**
- **Purpose**: {what it does}
- **Why not in context**: {reasoning}
- **Build approach**: {strategy}
- **Estimated complexity**: {Simple / Medium / Complex}

### Integration Strategy:

**Phase 1: Core Flow (from context)**
- Copy nodes: {list}
- Establish connections: {description}
- Test basic flow

**Phase 2: Adaptations**
- Modify parameters: {what}
- Add error handling: {what}
- Adjust data transformations: {what}

**Phase 3: Extensions**
- Add net-new components: {what}
- Integrate with core flow
- Test complete workflow

### Success Criteria:

- [ ] All required capabilities implemented
- [ ] Context patterns successfully adapted
- [ ] Error handling in place
- [ ] Validation passing
- [ ] Test execution successful
```

---

## Phase 5: Context Extraction and Integration

### Step 5.1: Extract Context to Project

**Process:**

**For Official Templates:**
```javascript
// Get template in full mode
const template = mcp__n8n-mcp__get_template({
  templateId: {id},
  mode: "full"
})

// Save to pattern library
// File: .claude/workflow-examples/contexts/{workflow-name}/source.json
```

**For Community Workflows:**
```javascript
// Get file contents
const workflow = mcp__n8n-workflows__get_file_contents({
  owner: "Zie619",
  repo: "n8n-workflows",
  path: "{path}"
})

// Save to pattern library
// File: .claude/workflow-examples/contexts/{workflow-name}/source.json
```

**For Instance Workflows:**
```javascript
// Get workflow
const workflow = mcp__n8n-mcp__n8n_get_workflow({
  id: "{workflow-id}"
})

// Save to pattern library
// File: .claude/workflow-examples/contexts/{workflow-name}/source.json
```

**Directory Structure:**
```
.claude/workflow-examples/contexts/{workflow-name}/
├── source.json           # Original workflow JSON
├── analysis.md           # Detailed analysis from Phase 3.2
├── usage-plan.md         # Context usage plan from Phase 4.2
├── extracted-patterns/   # Specific reusable patterns
│   ├── {pattern-1}.json
│   ├── {pattern-2}.json
│   └── README.md
└── README.md             # Context overview
```

**README.md Template:**
```markdown
# Context: {workflow-name}

**Source**: {template / community / instance}
**Retrieved**: {date}
**Score**: {X}/100
**Relevance**: {target workflow purpose}

## Overview
{Brief description of workflow and why it was selected as context}

## Key Patterns Extracted
1. **{Pattern 1}**: {description}
2. **{Pattern 2}**: {description}

## Usage
See `usage-plan.md` for detailed integration strategy.

## Analysis
See `analysis.md` for complete node-by-node analysis.

## Source
- Original ID: {id}
- URL: {if applicable}
- Repository: {if applicable}
```

### Step 5.2: Create Pattern Library Entries

**Process:**
1. Extract reusable patterns identified in analysis
2. Create pattern JSON (nodes + connections only)
3. Create pattern documentation
4. Add to pattern index

**Pattern JSON Format:**
```json
{
  "pattern_id": "{pattern-name}",
  "pattern_name": "{Human Readable Name}",
  "description": "{what this pattern does}",
  "complexity": "simple|medium|complex",
  "nodes_count": 3,
  "tags": ["ai-agent", "structured-output", "tools"],
  "use_cases": [
    "When you need AI with specific output format",
    "When AI needs to call external tools"
  ],
  "common_mistakes": [
    "Don't forget to set hasOutputParser: true on agent node",
    "Tools must connect via ai_tool connection type"
  ],
  "nodes": [...],
  "connections": {...},
  "example_configurations": {
    "basic": {...},
    "advanced": {...}
  }
}
```

**Pattern Documentation Format:**
```markdown
# Pattern: {pattern-name}

**Complexity**: {Simple/Medium/Complex}
**Nodes**: {count}
**Source**: {original context}

## Purpose
{What this pattern accomplishes}

## Use Cases
- {Use case 1}
- {Use case 2}

## Architecture
```
{Visual diagram}
```

## Node Configuration

### Node 1: {name}
- **Type**: {type}
- **Purpose**: {what it does}
- **Key Parameters**:
  ```json
  {parameters}
  ```

## Common Mistakes
1. **{Mistake 1}**: {description}
   - **Fix**: {solution}

## Implementation Steps
1. {Step 1}
2. {Step 2}

## Example Usage
{When and how to use this pattern}
```

### Step 5.3: Update Pattern Index

**File:** `.claude/workflow-examples/_index.json`

**Update:**
```json
{
  "contexts": [
    {
      "id": "{workflow-name}",
      "source_type": "template|community|instance",
      "source_id": "{id}",
      "retrieved": "2025-11-22",
      "score": 85,
      "target_workflow": "{what it was selected for}",
      "patterns_extracted": [
        "{pattern-1-id}",
        "{pattern-2-id}"
      ],
      "capabilities": [
        "ai-agent",
        "image-generation",
        "loop"
      ]
    }
  ],
  "patterns": [
    {
      "id": "{pattern-id}",
      "name": "{Pattern Name}",
      "source_context": "{workflow-name}",
      "complexity": "medium",
      "tags": ["ai-agent", "tools"],
      "production_tested": true
    }
  ]
}
```

---

## Phase 6: Context Application to Build

### Step 6.1: Inject Context into Build Process

**Integration with `/n8n-build` command:**

When building new workflow:
1. **Phase 0.2** (Load Pattern Context) - Reference extracted patterns
2. **Phase 0.3** (Search Similar Workflows) - Reference contexts
3. **Phase 0.5** (Node Selection) - Use documented configurations from context
4. **Phase 4** (Implementation) - Copy node structures from extracted patterns

**Context Injection Points:**

**Before node configuration:**
```markdown
Reference: Context {workflow-name}, Pattern {pattern-id}

Proven configuration:
```json
{node configuration from pattern}
```

Modifications for current workflow:
- {param 1}: {change}
- {param 2}: {change}
```

**During implementation:**
- Copy nodes from `extracted-patterns/{pattern}.json`
- Modify parameters per usage plan
- Maintain connection types exactly as in pattern
- Add sticky notes explaining context source

### Step 6.2: Validation Against Context

**Process:**
1. Compare built workflow to context usage plan
2. Verify all reusable components were integrated
3. Check modifications were applied correctly
4. Confirm net-new components were added

**Checklist:**
- [ ] All patterns from context integrated
- [ ] All required modifications made
- [ ] Connection types match pattern
- [ ] Parameter values updated correctly
- [ ] Error handling maintained/improved
- [ ] Sticky notes document context source
- [ ] New components tested individually

**Output:**
```markdown
## Context Application Validation

**Context Used**: {workflow-name}
**Patterns Applied**: {list}

**Validation Results**:

✅ Pattern {pattern-1}: Integrated successfully
   - Nodes: {list}
   - Modifications: {list}
   - Testing: {status}

✅ Pattern {pattern-2}: Integrated successfully
   - ...

**Deviations from Context**:
1. **{Deviation 1}**:
   - **Reason**: {why deviated}
   - **Impact**: {what changed}
   - **Validated**: {yes/no}

**Net-New Components**:
1. **{Component 1}**: {status}
2. **{Component 2}**: {status}

**Overall Assessment**: {Success / Partial / Failed}
```

---

## Protocol Usage Examples

### Example 1: Building Carousel Generator Workflow

**Target Workflow:**
- Purpose: Generate AI carousels with image generation, analysis, and storage
- Requirements: AI agents, DALL-E image generation, image analysis, Google Drive storage, loop over multiple slides

**Protocol Application:**

**Phase 1:** Requirements Analysis
- Identified 5 core capabilities (AI agent, image gen, image analysis, storage, loop)
- Node types needed: AI agent, OpenAI DALL-E, image analysis tool, Google Drive, Loop
- Complexity: Complex (multiple AI calls, loop, external integrations)

**Phase 2:** Multi-Source Search
- Search templates: `mcp__n8n-mcp__search_templates({ query: "image generation AI carousel" })`
- Search community: `mcp__n8n-workflows__search_code({ q: "DALL-E AND loop in:file" })`
- Search patterns: Check for "ai-agent-complete", "loop-over-items", "image-generation"

**Phase 3:** Candidate Evaluation
- Found 3 candidates: "AI Image Generator" (template), "Content Machine" (community), "AI Agent Complete" (pattern)
- Scored: 78/100, 65/100, 85/100
- Selected: "AI Agent Complete" pattern as primary, "AI Image Generator" as secondary

**Phase 4:** Selection Decision
- Primary context: AI Agent Complete (covers AI agent with tools)
- Secondary context: AI Image Generator (covers DALL-E + loop pattern)
- Confidence: High - 95% coverage of requirements

**Phase 5:** Context Extraction
- Extracted AI agent pattern (6 nodes)
- Extracted image generation + loop pattern (4 nodes)
- Created usage plan: Combine both patterns, add image analysis and Google Drive nodes

**Phase 6:** Application
- Built workflow using AI agent pattern from context
- Added DALL-E node configuration from secondary context
- Integrated loop pattern
- Added Google Drive node (net-new)
- Validated all patterns integrated correctly

---

## Success Metrics

**Protocol is successful when:**
- ✅ Identified context scores >70/100
- ✅ Context covers >80% of target requirements
- ✅ Build time reduced by >40% (vs. building from scratch)
- ✅ First execution success rate >80%
- ✅ No critical anti-patterns introduced
- ✅ Reusable patterns extracted for future use

**Protocol needs refinement when:**
- ⚠️ Context score <60/100
- ⚠️ Multiple searches yield no relevant results
- ⚠️ Build deviates significantly from context
- ⚠️ First execution fails due to context-based assumptions

---

## Anti-Patterns to Avoid

**DON'T:**
- ❌ Skip requirement analysis and jump to searching
- ❌ Select context based on title/name only
- ❌ Ignore scoring matrix and make subjective choice
- ❌ Copy context blindly without understanding
- ❌ Skip extraction step and work from memory
- ❌ Forget to document deviations from context

**DO:**
- ✅ Complete all phases systematically
- ✅ Document reasoning for all decisions
- ✅ Extract context to project for reference
- ✅ Validate application against usage plan
- ✅ Update pattern library with learnings
- ✅ Iterate if initial context insufficient

---

## Integration with Existing Systems

**Alignment with `.claude/CLAUDE.md`:**
- Complements Pre-Modification Protocol (analyze before changing)
- Extends Pre-Build Analysis Phase 0 (find context before building)
- Integrates with Pattern Library (`.claude/workflow-examples/`)

**Alignment with `/n8n-build` command:**
- Phase 0.2: Load Pattern Context → Use extracted patterns
- Phase 0.3: Search Similar Workflows → Use this protocol
- Phase 0.5: Node Selection → Reference context configurations

**Alignment with `/n8n-debug` command:**
- 5-Why Analysis → May reveal missing context usage
- Root cause may be "didn't use proven pattern" → Fix with this protocol

**Alignment with `agents-evolution.md`:**
- Document when context usage succeeded/failed
- Extract patterns from documented outcomes
- Feed successful patterns back into library

---

## Continuous Improvement

**After each workflow build:**
1. Document context effectiveness in `agents-evolution.md`
2. Update pattern library with new extractions
3. Refine scoring matrix based on outcomes
4. Add new search strategies if gaps found

**Monthly review:**
- Analyze most-used contexts
- Identify gaps in pattern library
- Update protocol based on learnings
- Archive outdated contexts

---

**Last Updated:** 2025-11-22
**Maintained By:** SYNRG Framework Integration
**Status:** Active Protocol
