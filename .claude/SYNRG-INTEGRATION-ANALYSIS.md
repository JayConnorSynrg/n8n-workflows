# SYNRG Integration Analysis for N8N Workflow Development

**Date**: 2025-11-22
**Purpose**: Analyze SYNRG rules and workflow generator methods to enhance n8n workflow production
**Context**: User analyzed workflow `ZimW7HztadhFZTyY` (DEVELOPER AGENT + MACHINE) and SYNRG framework to identify methods that would ubiquitously improve workflow development

---

## Executive Summary

**What Was Analyzed**:
1. **Workflow Generator** (`ZimW7HztadhFZTyY`) - n8n workflow that generates other n8n workflows using Google Docs as context
2. **SYNRG Framework** - Comprehensive 3-tier development methodology with 82 specialized agents

**Key Finding**: The workflow generator's **Google Doc context injection** and SYNRG's **Value-First Analysis** are the two most impactful methods missing from this project.

**Recommendations**:
- Create `.claude/workflow-examples/` pattern library (Priority 1)
- Add Pre-Modification Protocol to prevent breaking working workflows (Priority 1)
- Implement 5-Why root cause analysis for debugging (Priority 1)
- Add structured pre-build analysis requirement (Priority 2)

---

## Part 1: Workflow Generator Analysis

**Workflow Analyzed**: `ZimW7HztadhFZTyY` ("DEVELOPER AGENT + MACHINE")

### Method 1: Google Doc Context Injection ⭐ MOST IMPORTANT

**How It Works**:
```javascript
// 1. Download n8n documentation from Google Doc
{
  "type": "n8n-nodes-base.googleDrive",
  "parameters": {
    "operation": "download",
    "fileId": "161dPiBi5SUK_37Pr2K0kjhyeunHi7Il0PzfzdENFg9g",
    "options": {
      "googleFileConversion": {
        "conversion": { "docsToFormat": "text/plain" }
      }
    }
  }
}

// 2. Extract text content
{
  "type": "n8n-nodes-base.extractFromFile",
  "parameters": { "operation": "text" }
}

// 3. Inject into AI system message
{
  "type": "@n8n/n8n-nodes-langchain.agent",
  "parameters": {
    "options": {
      "systemMessage": "=# Overview\n...\n## n8n Documentation\n\n{{ $json.data }}"
    }
  }
}
```

**Why This Is Brilliant**:
- ✅ **Editable without workflow changes** - Update Google Doc, not workflow
- ✅ **Scalable knowledge base** - Add examples as they're discovered
- ✅ **Version controlled externally** - Google Doc revision history
- ✅ **Collaborative** - Multiple people can update examples
- ✅ **Lower token cost** - Fetched once per execution, not stored in workflow
- ✅ **Always up-to-date** - Latest examples used automatically

**Current Status in Project**: ❌ Not implemented

**Recommendation**: Create `.claude/workflow-examples/` directory system (see Part 4)

---

### Method 2: Extended Thinking (Claude Opus 4)

**How It Works**:
```javascript
{
  "type": "@n8n/n8n-nodes-langchain.lmChatAnthropic",
  "parameters": {
    "model": "claude-opus-4-1-20250805",
    "options": {
      "maxTokensToSample": 8000,
      "thinking": true,           // Enable extended thinking
      "thinkingBudget": 1024      // Allow deep analysis
    }
  }
}
```

**Why This Matters**:
- For complex workflows (15+ nodes, multiple APIs), AI needs time to plan
- Extended thinking produces better architecture
- Prevents rushed, suboptimal designs

**Current Status in Project**: ❌ Not documented

**Recommendation**: Add guidance to `.claude/CLAUDE.md` on when to use extended thinking

---

### Method 3: Strict JSON Output Format Enforcement

**How It Works**:
```
Your output must start with a { and must end with a }.
- Do not include anything before the {
- Do not include anything after the }
- Do not wrap in markdown code blocks
- Do not add explanatory text

Your output should be pure JSON object ready for POST request.
```

**Why This Matters**:
- Ensures clean API-compatible JSON
- Prevents parsing errors
- Works directly with n8n API node

**Current Status in Project**: ⚠️ MCP tools handle this, not needed for manual work

**Recommendation**: Keep as-is, MCP tools abstract this concern

---

### Method 4: Required API Fields Documentation

**How It Works**:
```
To automatically create a workflow using the n8n API, your JSON must include:
- name (string): Descriptive workflow name
- nodes (array): Complete node objects with id, name, type, typeVersion, position, parameters
- connections (object): Node-to-node connections map
- settings (object): Workflow-level settings (executionOrder, timezone, etc.)
- staticData (null or object)
```

**Why This Matters**:
- Explicitly tells AI what n8n API requires
- Prevents missing required fields
- Reduces API errors

**Current Status in Project**: ✅ MCP tools handle this

**Recommendation**: Keep as-is for MCP usage, but add to manual workflow creation docs

---

### Method 5: Auto-Generated Sticky Notes (Documentation)

**How It Works**:
- Workflow adds Sticky Note nodes explaining:
  - What each section does
  - Why specific nodes were chosen
  - Error handling strategy
  - Parameters to customize

**Why This Matters**:
- Self-documenting workflows
- Easier maintenance
- Onboarding for new team members

**Current Status in Project**: ❌ Not implemented

**Recommendation**: Future enhancement - add sticky notes automatically when creating workflows

---

### Method 6: Structured Analysis Before Generation

**How It Works**:
```
Before generating the JSON, analyze the request and:
1. Break it down into logical automation steps
2. Choose appropriate nodes based on the steps
3. Properly connect the nodes to reflect execution order
4. Plan error handling for external services
5. Consider performance and rate limits
```

**Why This Matters**:
- Forces planning before execution
- Prevents assumptions
- Results in better workflow design

**Current Status in Project**: ⚠️ Prompting guide suggests it, not enforced

**Recommendation**: Make this MANDATORY in `/n8n-build` command (Priority 2)

---

### Method 7: Direct API Integration

**How It Works**:
```javascript
{
  "type": "n8n-nodes-base.n8n",
  "parameters": {
    "operation": "create",
    "workflowObject": "={{ $json.output[1].text }}"
  }
}
```

**Why This Matters**:
- Instant workflow creation
- No manual import/export
- Programmatic workflow management

**Current Status in Project**: ✅ We use MCP tools (equivalent functionality)

**Recommendation**: Keep as-is, MCP approach is better

---

## Part 2: SYNRG Framework Analysis

**Framework Analyzed**: SYNRG v4.0.0 (3-tier methodology with 82 agents)

### SYNRG Rule 1: Value-First Pre-Change Analysis ⭐ CRITICAL

**What It Is**:
```markdown
STEP 2.75: VALUE-FIRST PRE-CHANGE ANALYSIS
Before making ANY changes to existing code/workflows:
1. Assess what's currently working
2. Document existing value
3. Evaluate impact of proposed changes
4. Preserve working functionality
5. Proceed only if improvement justifies risk
```

**Why This Is Critical for n8n**:
- Workflows often have hidden dependencies
- "Improvements" can break integrations
- Production workflows serve real business functions
- Rollback is harder than prevention

**Real Example from This Project**:
- Workflow `8bhcEHkbbvnhdHBh` was broken by assumptions
- Should have analyzed prototype `bEA0VHpyvazFmhYO` FIRST
- This is exactly what Value-First Analysis prevents

**Current Status in Project**: ⚠️ Implied in pattern evolution, not enforced

**Recommendation**: Add mandatory Pre-Modification Protocol to `.claude/CLAUDE.md` (Priority 1)

**Implementation**:
```markdown
## Pre-Modification Protocol (MANDATORY)

Before modifying ANY existing workflow:

1. Fetch current state:
   mcp__n8n-mcp__n8n_get_workflow({ id: "workflow-id" })

2. Assess current value:
   - What's working? (check execution success rate)
   - What integrations are stable?
   - What functionality is being used?

3. Impact assessment:
   - Will this change break existing functionality?
   - Can we test in isolation?
   - Is rollback possible?

4. Proceed only if:
   - Value preservation is guaranteed, OR
   - Improvement justifies risk AND user approves
```

---

### SYNRG Rule 2: Error Analysis & 5-Why Protocol

**What It Is**:
```markdown
When ANY error occurs:
1. Why did it fail? (surface symptom)
2. Why did that happen? (immediate cause)
3. Why did that happen? (technical cause)
4. Why did that happen? (design cause)
5. Why did that happen? (process/root cause)

Must reach process-level root cause, not just technical symptoms.
```

**Why This Matters for n8n**:
- Prevents recurring workflow failures
- Identifies missing best practices
- Creates reusable knowledge

**Example**:
```
1. Why did workflow fail? → OpenAI returned 429
2. Why 429? → Rate limit exceeded
3. Why rate limit? → 5 parallel image calls
4. Why parallel without throttling? → Used Split-Merge without rate planning
5. Why no rate planning? → Didn't research API limits before implementation

Root Cause: Insufficient research in design phase
Pattern: Always check API rate limits before parallel processing
```

**Current Status in Project**: ❌ Not implemented

**Recommendation**: Add 5-Why Protocol to `/n8n-debug` command (Priority 1)

---

### SYNRG Rule 3: Robustness-First Philosophy

**What It Is**:
```markdown
"Take the time to do it right. Perfection over speed. Quality over quantity."

- 30% Research & Analysis
- 40% Implementation
- 30% Validation & Testing

Never rush production work.
```

**Why This Matters for n8n**:
- Production workflows must be reliable
- Business processes depend on them
- Fixing rushed work costs more than doing it right

**Current Status in Project**: ✅ Aligned in spirit (emphasis on native nodes, error handling, testing)

**Gap**: No explicit time budgeting guidance

**Recommendation**: Add time allocation guidance to `.claude/CLAUDE.md`

---

### SYNRG Rule 4: Pattern Auto-Detection

**What It Is**:
```markdown
System automatically detects 8 recurring patterns:
1. Repeated transformations → Extract to library function
2. Copy-paste code → Create reusable component
3. Hard-coded values → Move to configuration
4. Missing error handling → Add comprehensive error branches
5. Inefficient loops → Optimize with better algorithm
6. Duplicate API calls → Cache or batch
7. Unclear naming → Refactor for clarity
8. Missing documentation → Auto-generate docs
```

**Why This Matters for n8n**:
- Workflows often have repeated patterns
- Manual detection is time-consuming
- Automation ensures consistency

**Current Status in Project**: ❌ Manual pattern documentation only

**Gap**: No automatic pattern detection or suggestions

**Recommendation**: Future enhancement - analyze workflows for common anti-patterns

---

### SYNRG Rule 5: Self-Evolution Protocol

**What It Is**:
```markdown
When errors reveal missing rules:
1. Document the gap
2. Create new rule
3. Update project instructions
4. Apply retroactively where relevant
```

**Why This Matters for n8n**:
- `.claude/` instructions should improve over time
- Real errors reveal missing best practices
- Self-improvement prevents recurring issues

**Current Status in Project**: ⚠️ Manual evolution via `agents-evolution.md`

**Gap**: No automatic rule creation from patterns

**Recommendation**: Add to `/n8n-evolve` command - when pattern is documented 3+ times, promote to rule in `.claude/CLAUDE.md`

---

## Part 3: Missing Methods Comparison

| Method/Rule | Source | Current Status | Impact | Priority |
|-------------|--------|---------------|---------|----------|
| **Google Doc Context Injection** | Workflow Generator | ❌ Not implemented | 🔥 Very High - Enables updatable examples | 1 |
| **Value-First Pre-Change Analysis** | SYNRG | ⚠️ Implied, not enforced | 🔥 Very High - Prevents breaking changes | 1 |
| **5-Why Root Cause Analysis** | SYNRG | ❌ Missing | 🔥 High - Deeper debugging | 1 |
| **Structured Pre-Build Analysis** | Workflow Generator | ⚠️ Suggested, not mandatory | 🔥 High - Better planning | 2 |
| **Extended Thinking Guidance** | Workflow Generator | ❌ Not documented | ⚡ Medium - Complex workflows | 3 |
| **Auto-Generated Sticky Notes** | Workflow Generator | ❌ Not implemented | ⚡ Medium - Documentation | 4 |
| **Robustness-First Time Budgeting** | SYNRG | ⚠️ Spirit only | ⚡ Medium - Quality focus | 3 |
| **Pattern Auto-Detection** | SYNRG | ❌ Not implemented | ⚡ Low - Future enhancement | 5 |
| **Self-Evolution Protocol** | SYNRG | ⚠️ Manual only | ⚡ Low - Future enhancement | 5 |

**Legend**:
- ✅ Fully implemented
- ⚠️ Partially implemented / implied
- ❌ Not implemented
- 🔥 High impact
- ⚡ Medium/Low impact

---

## Part 4: Updatable Context System Design

**Goal**: Replicate the Google Doc context injection approach using `.claude/workflow-examples/` directory

### Architecture

```
.claude/workflow-examples/
├── README.md                           # System documentation
├── _index.json                         # Searchable pattern index
│
├── patterns/                          # Proven workflow patterns (CORE)
│   ├── ai-agent-text-generation/
│   │   ├── pattern.json              # Minimal example (3 nodes only)
│   │   ├── pattern.md                # Full documentation
│   │   └── full-example.json         # Complete working workflow
│   │
│   ├── parallel-api-calls/
│   │   ├── pattern.json              # Split-Merge structure
│   │   ├── pattern.md                # When to use, gotchas
│   │   └── full-example.json         # Production example
│   │
│   ├── error-handling-retry/
│   │   ├── pattern.json              # Exponential backoff
│   │   ├── pattern.md                # Implementation guide
│   │   └── full-example.json         # Tested pattern
│   │
│   └── image-generation-dall-e/
│       ├── pattern.json              # OpenAI image node
│       ├── pattern.md                # Parameters, limitations
│       └── full-example.json         # Working carousel
│
└── workflows/                         # Full working workflows (REFERENCE)
    ├── synrg-content-machine.json    # Prototype bEA0VHpyvazFmhYO
    ├── synrg-content-machine.md      # What it does, learnings
    ├── developer-agent-machine.json  # Generator ZimW7HztadhFZTyY
    └── developer-agent-machine.md    # How it generates workflows
```

### Pattern Index Structure (`_index.json`)

```json
{
  "version": "1.0.0",
  "last_updated": "2025-11-22",
  "patterns": [
    {
      "id": "ai-agent-text-generation",
      "name": "AI Agent Text Generation (3-Node Pattern)",
      "category": "AI Processing",
      "use_cases": ["text generation", "prompt refinement", "content creation"],
      "nodes_required": ["agent", "lmChatOpenAi", "memoryBufferWindow"],
      "connection_types": ["ai_languageModel", "ai_memory"],
      "complexity": "medium",
      "production_tested": true,
      "source_workflow": "bEA0VHpyvazFmhYO",
      "common_mistakes": [
        "Trying to use openAi node with resource: 'text' (doesn't exist)",
        "Forgetting to connect language model via ai_languageModel type",
        "Not including memory buffer for context retention"
      ],
      "performance_notes": "~3-5 seconds per generation with GPT-4 Turbo"
    },
    {
      "id": "parallel-api-calls",
      "name": "Parallel API Processing (Split-Merge)",
      "category": "Performance Optimization",
      "use_cases": ["multiple image generation", "batch API requests", "parallel enrichment"],
      "nodes_required": ["splitInBatches", "merge"],
      "complexity": "low",
      "production_tested": true,
      "performance_impact": "76% faster (measured in carousel generator)",
      "gotchas": [
        "Check API rate limits before parallelizing",
        "Consider memory usage with large batches",
        "Add error handling per branch"
      ]
    },
    {
      "id": "image-generation-dall-e",
      "name": "DALL-E 3 Image Generation",
      "category": "AI Processing",
      "use_cases": ["image generation", "visual content creation"],
      "nodes_required": ["openAi"],
      "complexity": "low",
      "production_tested": true,
      "source_workflow": "bEA0VHpyvazFmhYO",
      "common_mistakes": [
        "Using wrong model name (must be 'dall-e-3', not 'gpt-image-1')",
        "Not setting resource: 'image'",
        "Forgetting rate limits (50 images/min for standard tier)"
      ],
      "cost_notes": "$0.040 per 1024x1024 image (standard quality)"
    }
  ]
}
```

### Usage Protocol for Claude

**When building a new workflow**, Claude automatically:

#### Step 1: Pattern Identification
```
User request: "Build AI carousel generator with quality loop"

Identify patterns:
- "AI" + "carousel" → ai-agent-text-generation ✅
- "carousel" (multiple images) → parallel-api-calls ✅
- "quality loop" → conditional-retry ✅
- Image generation → image-generation-dall-e ✅
```

#### Step 2: Load Pattern Context
```javascript
// Read pattern index
const index = await read('.claude/workflow-examples/_index.json');

// Load relevant patterns
const patterns = [
  'ai-agent-text-generation',
  'parallel-api-calls',
  'image-generation-dall-e'
];

for (const patternId of patterns) {
  // Read documentation
  const docs = await read(`.claude/workflow-examples/patterns/${patternId}/pattern.md`);

  // Load node structure
  const structure = await read(`.claude/workflow-examples/patterns/${patternId}/pattern.json`);

  // Note common mistakes
  const mistakes = index.patterns.find(p => p.id === patternId).common_mistakes;
}
```

#### Step 3: Use Exact Structures
```
Instead of assuming node configuration:
✅ Copy exact structure from pattern.json
✅ Apply documented parameters
✅ Follow connection types from examples
✅ Avoid common mistakes listed in pattern

Example:
For AI text generation, use the exact 3-node pattern from
.claude/workflow-examples/patterns/ai-agent-text-generation/pattern.json
```

#### Step 4: Present Plan with Pattern References
```
"I'll build this workflow using these proven patterns:

1. AI Agent (3-node pattern) - From bEA0VHpyvazFmhYO
   - Nodes: agent + lmChatOpenAi + memoryBufferWindow
   - Connections: ai_languageModel + ai_memory

2. Parallel Image Generation - Split-Merge pattern
   - Proven to be 76% faster than sequential
   - Must check DALL-E rate limits (50/min)

3. DALL-E 3 Configuration
   - Exact params from working carousel workflow
   - model: 'dall-e-3' (NOT 'gpt-image-1')

Proceed with build?"
```

### Updatability Mechanisms

#### Update Trigger 1: Post-Deployment Success
```markdown
When production workflow succeeds and introduces new pattern:

1. Identify reusable pattern
2. Extract minimal example
3. Document in pattern format
4. Add to `.claude/workflow-examples/patterns/`
5. Update `_index.json`
6. Git commit for version control
```

#### Update Trigger 2: Pattern Evolution Promotion
```markdown
When `agents-evolution.md` documents pattern used successfully 3+ times:

Automatic promotion:
1. Extract pattern from evolution log
2. Create pattern directory
3. Add pattern.json (structure)
4. Add pattern.md (documentation)
5. Update _index.json
6. Reference from evolution log entry
```

#### Update Trigger 3: External Workflow Analysis
```markdown
When user shares successful workflow:

Manual curation:
1. User provides workflow ID or JSON
2. Claude analyzes for patterns
3. Extracts reusable components
4. Documents in pattern library
5. Updates index
```

---

## Part 5: Implementation Recommendations

### Phase 1: Foundation (Week 1) - Priority 1 Items

#### 1.1 Add Pre-Modification Protocol to `.claude/CLAUDE.md`

**File**: `.claude/CLAUDE.md`
**Location**: After line 283 (Development Workflow section)
**Effort**: 10 minutes
**Impact**: Prevents breaking working workflows

**Action**: Add new section:

```markdown
### Pre-Modification Protocol (MANDATORY)

Before modifying ANY existing workflow:

1. **Fetch Current State**:
   ```javascript
   mcp__n8n-mcp__n8n_get_workflow({ id: "workflow-id" })
   ```

2. **Assess Current Value**:
   - What's currently working?
   - What's the execution success rate?
   ```javascript
   mcp__n8n-mcp__n8n_list_executions({
     workflowId: "workflow-id",
     limit: 50,
     status: "success"
   })
   ```

3. **Document Working Functionality**:
   - List nodes functioning correctly
   - Note stable integrations
   - Identify successful execution patterns

4. **Impact Assessment**:
   - Will this change break existing functionality?
   - Can changes be tested in isolation?
   - Is rollback possible if issues arise?

5. **Proceed Only If**:
   - ✅ Value preservation is guaranteed, OR
   - ✅ Improvement justifies risk AND user explicitly approves

**This protocol applies to**:
- Node parameter changes
- Connection modifications
- New node additions to existing workflows
- Error handling updates
- Performance optimizations

**Example**:
User: "Update the resume review workflow to use GPT-4o instead of GPT-4 Turbo"

Claude:
1. Fetch workflow and check current success rate (98%)
2. Verify GPT-4o is compatible with existing prompt structure
3. Assess impact: Model change could affect response format
4. Test in development first
5. Monitor executions after deployment
```

---

#### 1.2 Add 5-Why Protocol to `.claude/commands/n8n-debug.md`

**File**: `.claude/commands/n8n-debug.md`
**Location**: Replace Phase 3 section (around line 89)
**Effort**: 15 minutes
**Impact**: Deeper debugging, prevents recurring issues

**Action**: Replace existing Phase 3 with:

```markdown
### Phase 3: Root Cause Analysis (5-Why Protocol - MANDATORY)

**DO NOT skip this step.** Superficial fixes lead to recurring failures.

**5-Why Analysis Process**:

Ask "Why?" five times to reach root cause:

1. **Why 1 - Surface Symptom**:
   - What failed? (specific error message)
   - Example: "Why did workflow fail?" → "OpenAI node returned 429 error"

2. **Why 2 - Immediate Cause**:
   - Why did that error occur?
   - Example: "Why 429?" → "Rate limit exceeded"

3. **Why 3 - Technical Cause**:
   - What technical decision led to this?
   - Example: "Why rate limit exceeded?" → "5 parallel image generation calls hit API too fast"

4. **Why 4 - Design Cause**:
   - What design choice enabled this?
   - Example: "Why parallel without throttling?" → "Used Split-Merge without rate limit planning"

5. **Why 5 - Root Cause (Process/Knowledge Gap)**:
   - What process failure allowed this?
   - Example: "Why no rate planning?" → "Didn't research API constraints before implementation"

**Root Cause Identified**: {Must be process/knowledge level, not just technical}

**Pattern Classification**:

After identifying root cause, classify:

- **Process Gap**: Missing step in development workflow
  → Update `.claude/CLAUDE.md` with new requirement

- **Knowledge Gap**: Unknown pattern or best practice
  → Document in `agents-evolution.md`
  → Add to `.claude/workflow-examples/` if reusable

- **Tool Misuse**: Incorrect node usage
  → Update relevant command documentation

- **Design Flaw**: Architectural issue
  → Create pattern for future reference

**Example Complete Analysis**:

```
Workflow: prod-marketing-carousel-generator
Failure: 85% of executions failing with 429 errors

5-Why Analysis:
1. Why failing? → OpenAI DALL-E node returning 429
2. Why 429? → Rate limit exceeded (50 images/min)
3. Why exceeded? → 5 parallel image calls per carousel, 20 carousels/hour = 100 images/hour
4. Why no rate limiting? → Used Split-Merge for speed without throttling
5. Why no throttling? → Didn't check OpenAI rate limits documentation before parallelizing

Root Cause: Skipped API research in design phase

Classification: Process Gap
Action: Add "Research API rate limits" to Pre-Build Analysis checklist

Pattern: "Always check API rate limits before parallel processing"
Location: Document in agents-evolution.md
```

**Common Root Cause Categories**:

| Category | Indicators | Solution |
|----------|-----------|----------|
| **Insufficient Research** | "Didn't check docs", "Assumed it would work" | Add research step to workflow |
| **Assumption Without Verification** | "Thought node existed", "Assumed config" | Require prototype analysis first |
| **Skipped Validation** | "Deployed without testing" | Make validation mandatory |
| **Missing Error Handling** | "Didn't plan for failures" | Add error handling checklist |
| **Performance Blindness** | "Didn't consider scale" | Add performance requirements to prompts |

**Next Steps After 5-Why**:

1. ✅ Fix the immediate issue
2. ✅ Document root cause in execution notes
3. ✅ Check if pattern exists in `agents-evolution.md`
4. ✅ If new pattern → Add to evolution log
5. ✅ If process gap → Update `.claude/CLAUDE.md`
6. ✅ If common mistake → Add to pattern library warnings
```

---

#### 1.3 Update `/n8n-build` with Pre-Analysis Requirement

**File**: `.claude/commands/n8n-build.md`
**Location**: Add Phase 0 before current Phase 1
**Effort**: 20 minutes
**Impact**: Forces structured thinking before building

**Action**: Add at beginning of file:

```markdown
## Phase 0: Pre-Build Analysis (MANDATORY - Do Not Skip)

**Before generating ANY workflow**, Claude MUST complete this analysis.

**DO NOT proceed to Phase 1 until this is complete.**

---

### Step 0.1: Pattern Identification

**Analyze user request and identify required patterns**:

Questions to ask:
- Does this need AI processing? → Check `ai-agent-text-generation` pattern
- Multiple API calls? → Check `parallel-api-calls` pattern
- External APIs? → Check `error-handling-retry` pattern
- Image generation? → Check `image-generation-dall-e` pattern
- Database operations? → Check `database-operations` pattern
- Data transformation? → Check `data-transformation` pattern

**Document identified patterns**:
```
Patterns needed:
- ai-agent-text-generation ✅
- parallel-api-calls ✅
- error-handling-retry ✅
```

---

### Step 0.2: Load Pattern Context

**For each identified pattern**:

1. Check if pattern exists:
   ```bash
   ls .claude/workflow-examples/patterns/{pattern-id}/
   ```

2. If exists, read documentation:
   ```
   .claude/workflow-examples/patterns/{pattern-id}/pattern.md
   ```

3. Load node structure:
   ```
   .claude/workflow-examples/patterns/{pattern-id}/pattern.json
   ```

4. Note common mistakes:
   - Check pattern index for gotchas
   - Review "common_mistakes" field
   - Check "performance_notes"

**If pattern doesn't exist**:
- Search for similar workflows
- Analyze working examples
- Document new pattern after successful build

---

### Step 0.3: Search for Similar Workflows

**Use MCP tools to find examples**:

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

// Search for workflows with specific nodes
mcp__n8n-mcp__list_node_templates({
  nodeTypes: ["@n8n/n8n-nodes-langchain.agent", "@n8n/n8n-nodes-langchain.openAi"]
})
```

**Document findings**:
```
Similar workflows found:
- Template #1234: "AI Content Generator"
  - Uses AI agent pattern ✅
  - Has error handling ✅
  - Good reference for structure

- Template #5678: "Batch Image Processor"
  - Uses parallel processing ✅
  - Has throttling logic ✅
  - Can adapt for carousel generation
```

---

### Step 0.4: Break Down into Logical Steps

**Create step-by-step automation plan**:

Template:
```
Workflow Steps:
1. [Trigger] Webhook receives request
   - Validate input structure
   - Extract parameters

2. [Processing] Generate content with AI
   - Node: AI Agent (3-node pattern)
   - Input: User prompt
   - Output: Generated text

3. [Processing] Generate images (parallel)
   - Node: Split-Merge pattern
   - For each text: Generate image with DALL-E
   - Handle rate limits

4. [Transformation] Combine results
   - Node: Merge + Set
   - Create final JSON structure

5. [Output] Return to webhook caller
   - Node: Respond to Webhook
   - Format: JSON with carousel data

Decision Points:
- IF validation fails → Return 400 error
- IF AI fails → Retry 3x, then error
- IF rate limited → Exponential backoff

Data Flow:
Input → Validate → AI → Split → [Image Gen, Image Gen, ...] → Merge → Format → Output
```

---

### Step 0.5: Node Selection with Verification

**For each step, select appropriate nodes**:

Process:
1. **Identify capability needed**
2. **Search for native node**:
   ```javascript
   mcp__n8n-mcp__search_nodes({
     query: "{capability}",
     limit: 10
   })
   ```
3. **Verify node can handle requirement**:
   ```javascript
   mcp__n8n-mcp__get_node_essentials({
     nodeType: "nodes-base.{selected-node}",
     includeExamples: true
   })
   ```
4. **Check pattern library** for proven configuration
5. **Document choice**

**Example**:
```
Step 2: AI text generation

Capability needed: Generate text with Claude/GPT
Search: "AI text generation"
Found: @n8n/n8n-nodes-langchain.agent

Verification:
- Checked node essentials ✅
- Found in pattern library ✅
- Requires 3-node setup (agent + model + memory) ✅
- Working example in bEA0VHpyvazFmhYO ✅

Decision: Use ai-agent-text-generation pattern
Reason: Proven structure, documented configuration
```

**Node Selection Preferences** (follow this order):
1. ✅ Pattern from `.claude/workflow-examples/` (highest priority)
2. ✅ Native n8n node (second priority)
3. ✅ Community node (vetted) (third priority)
4. ⚠️ Code node (only if no native option exists)

---

### Step 0.6: Plan Error Handling

**Identify error scenarios**:

For each external service/API:
- What can go wrong?
- How should we handle it?
- Do we retry? How many times?
- Do we notify? Who?

Template:
```
Error Handling Plan:

Node: OpenAI DALL-E Image Generation
Possible Errors:
1. 429 Rate Limit
   - Handle: Exponential backoff (1s, 2s, 4s)
   - Max retries: 5
   - If still failing: Return error to user

2. 500 Server Error
   - Handle: Retry immediately (once)
   - If fails: Skip this image, continue with others
   - Notify: Log to error tracking

3. Invalid prompt (400)
   - Handle: No retry (user error)
   - Action: Return detailed validation error

Node: Anthropic Claude AI Agent
Possible Errors:
1. 429 Rate Limit
   - Handle: Wait 60s, retry once
   - If fails: Return error response

2. Timeout (>30s)
   - Handle: No retry (prompt too complex)
   - Action: Ask user to simplify request
```

**Error Handling Requirements** (mandatory):
- ✅ ALL external API calls must have error branches
- ✅ Retry logic for transient errors (rate limits, timeouts)
- ✅ Graceful degradation where possible
- ✅ User-friendly error messages
- ✅ Error logging for debugging

---

### Step 0.7: Present Plan to User (Required)

**Before building, show user complete plan**:

Format:
```markdown
## Workflow Plan: {workflow-name}

**Patterns Used**:
1. AI Agent Text Generation (from bEA0VHpyvazFmhYO)
2. Parallel API Calls (Split-Merge)
3. DALL-E 3 Image Generation

**Workflow Structure**:
[Webhook] → [Validate] → [AI Agent] → [Split] → [Image Gen (5x parallel)] → [Merge] → [Format] → [Respond]

**Nodes Required**: 12 nodes total
- 1 Webhook Trigger
- 1 IF (validation)
- 3 AI Agent pattern (agent + model + memory)
- 1 Split In Batches
- 5 OpenAI DALL-E (parallel)
- 1 Merge
- 1 Set (format output)
- 1 Respond to Webhook

**Error Handling**:
- Validation failure → 400 response
- AI failure → Retry 3x, then error
- DALL-E rate limit → Exponential backoff
- Individual image failure → Continue with others

**Estimated Complexity**: Medium
**Estimated Build Time**: 30-45 minutes
**Performance**: ~15 seconds per execution (3s AI + 10s images parallel)

**Proceed with build?**
```

**Wait for user approval before proceeding to Phase 1.**

---

**Why Phase 0 Is Mandatory**:

❌ Without Pre-Analysis:
- Assume node configurations exist (they don't)
- Miss existing patterns (reinvent the wheel)
- Skip error planning (fragile workflows)
- Rush to build (suboptimal architecture)

✅ With Pre-Analysis:
- Use proven patterns (faster, reliable)
- Find working examples (no assumptions)
- Plan comprehensive error handling (robust)
- Present plan for approval (aligned with user expectations)

**This prevents the exact anti-pattern documented in agents-evolution.md**:
"Always Analyze Working Examples Before Building New Workflows"
```

---

### Phase 2: Pattern Library (Week 2) - Priority 2 Items

#### 2.1 Create `.claude/workflow-examples/` Directory Structure

**Effort**: 1-2 hours
**Impact**: Foundational system for reusable patterns

**Actions**:

1. Create directory structure
2. Write system README
3. Create pattern index
4. Extract first pattern from working workflow

**Files to Create**:

`.claude/workflow-examples/README.md`:
```markdown
# Working Workflow Examples - Pattern Library

**Purpose**: Provide reusable, proven workflow patterns that Claude can reference when building new workflows.

**Philosophy**: Similar to the workflow generator's Google Doc approach, but using git-versioned files.

---

## How This System Works

**When Claude builds a workflow**:
1. Analyzes user request → Identifies required patterns
2. Loads relevant patterns from this directory
3. Uses exact node configurations from `pattern.json`
4. Applies documentation from `pattern.md`
5. Avoids common mistakes listed in patterns

**Benefits**:
- ✅ No assumptions about node configurations
- ✅ Proven structures from working workflows
- ✅ Documented gotchas and best practices
- ✅ Version controlled knowledge base
- ✅ Collaborative updates via git

---

## Directory Structure

```
.claude/workflow-examples/
├── README.md           # This file
├── _index.json         # Searchable pattern index
│
├── patterns/           # Proven workflow patterns
│   └── {pattern-id}/
│       ├── pattern.json       # Minimal example (just the pattern)
│       ├── pattern.md         # Full documentation
│       └── full-example.json  # Complete working workflow
│
└── workflows/          # Full reference workflows
    └── {workflow-name}.json   # Exported from n8n
    └── {workflow-name}.md     # Documentation
```

---

## Pattern Structure

Each pattern directory contains:

### pattern.json
Minimal workflow showing JUST the pattern structure:
- Only nodes directly related to pattern
- Exact node configurations
- Required connections
- No business logic, just the pattern

### pattern.md
Complete documentation:
- When to use this pattern
- Node structure explanation
- Required parameters
- Common mistakes to avoid
- Performance considerations
- Variations and adaptations
- Related patterns

### full-example.json
Complete working workflow that uses this pattern:
- Full business context
- Shows pattern in production use
- Can be imported to n8n directly
- Reference for how pattern fits into larger workflow

---

## Available Patterns

See `_index.json` for searchable list of all patterns.

**Current patterns**:
1. `ai-agent-text-generation` - 3-node AI agent structure
2. `parallel-api-calls` - Split-Merge for parallel processing
3. `image-generation-dall-e` - DALL-E 3 configuration
4. `error-handling-retry` - Exponential backoff retry logic

---

## Adding New Patterns

**When to add a pattern**:
- ✅ Pattern used successfully in production
- ✅ Pattern solves common problem
- ✅ Pattern is reusable across domains
- ✅ Pattern documented in `agents-evolution.md` with success metrics
- ❌ NOT for one-off solutions
- ❌ NOT for untested approaches

**How to add a pattern**:

1. **Identify pattern** in working workflow
2. **Extract minimal example**:
   - Copy only nodes needed for pattern
   - Remove business-specific logic
   - Keep exact configurations
3. **Create pattern directory**:
   ```bash
   mkdir -p .claude/workflow-examples/patterns/{pattern-id}
   ```
4. **Create pattern files**:
   - `pattern.json` - Minimal structure
   - `pattern.md` - Documentation (use template below)
   - `full-example.json` - Complete workflow export
5. **Update `_index.json`**:
   - Add pattern metadata
   - Include use cases, common mistakes
6. **Git commit**:
   ```bash
   git add .claude/workflow-examples/
   git commit -m "docs(patterns): add {pattern-name} pattern"
   ```

---

## Pattern Documentation Template

Use this template for `pattern.md` files:

```markdown
# {Pattern Name}

**Category**: {AI Processing | Performance | Error Handling | Data Transformation | Integration}
**Complexity**: {Low | Medium | High}
**Production Tested**: {Yes | No}
**Source Workflow**: {workflow-id or name}
**Last Updated**: {YYYY-MM-DD}

---

## When to Use This Pattern

✅ **Use when**:
- {scenario 1}
- {scenario 2}

❌ **Don't use when**:
- {anti-pattern scenario 1}
- {better alternative exists}

---

## Node Structure

{Visual ASCII representation or clear description}

---

## Required Nodes

### Node 1: {Node Type}
- **Type**: `{full node type with version}`
- **Purpose**: {what it does in this pattern}
- **Key Parameters**:
  ```json
  {
    "parameter1": "value",
    "parameter2": "value"
  }
  ```
- **Common Mistakes**:
  - ❌ {mistake 1}
  - ❌ {mistake 2}

### Node 2: {Node Type}
- ...

---

## Connections

{How nodes connect to each other}
- Connection type: {type}
- From: {source node}
- To: {target node}

---

## Example Configuration

**Minimal Example**: See `pattern.json`
**Complete Workflow**: See `full-example.json`

**Customization Points**:
- {parameter to customize for your use case}
- {parameter to customize}

---

## Performance Considerations

- {consideration 1}
- {measured metric if available}
- {optimization tip}

---

## Error Handling

**Potential Errors**:
1. {error type}: {how to handle}
2. {error type}: {how to handle}

---

## Variations

### Variation 1: {Name}
- **When to use**: {scenario}
- **Changes**: {what's different}

### Variation 2: {Name}
- **When to use**: {scenario}
- **Changes**: {what's different}

---

## Related Patterns

- `{pattern-id-1}`: {relationship - "often used together", "alternative for", etc.}
- `{pattern-id-2}`: {relationship}

---

## Changelog

- **{YYYY-MM-DD}**: {change description}
```

---

## Maintenance

**Quarterly Review**:
- Archive deprecated patterns
- Update patterns with new learnings
- Cross-reference with `agents-evolution.md`
- Consolidate similar patterns

**Version Control**:
- All changes via git commits
- Include reason for updates in commit message
- Tag major pattern library releases

---

## Statistics

**Total Patterns**: {count from _index.json}
**Last Updated**: {auto-generated from git}
**Most Used Pattern**: {from evolution log analysis}
**Success Rate**: {workflows using patterns vs. not}
```

`.claude/workflow-examples/_index.json`:
```json
{
  "version": "1.0.0",
  "last_updated": "2025-11-22",
  "total_patterns": 4,
  "patterns": [
    {
      "id": "ai-agent-text-generation",
      "name": "AI Agent Text Generation (3-Node Pattern)",
      "category": "AI Processing",
      "description": "Standard n8n pattern for AI text generation using agent, language model, and memory nodes",
      "use_cases": [
        "text generation",
        "prompt refinement",
        "content creation",
        "conversational AI",
        "text analysis"
      ],
      "nodes_required": [
        "@n8n/n8n-nodes-langchain.agent",
        "@n8n/n8n-nodes-langchain.lmChatOpenAi",
        "@n8n/n8n-nodes-langchain.memoryBufferWindow"
      ],
      "connection_types": [
        "ai_languageModel",
        "ai_memory"
      ],
      "complexity": "medium",
      "production_tested": true,
      "source_workflow": "bEA0VHpyvazFmhYO",
      "common_mistakes": [
        "Trying to use @n8n/n8n-nodes-langchain.openAi with resource: 'text' (this configuration doesn't exist)",
        "Forgetting to connect language model via ai_languageModel connection type",
        "Not including memory buffer node (breaks context retention)",
        "Using wrong typeVersion for nodes (must match)"
      ],
      "performance_notes": "~3-5 seconds per generation with GPT-4 Turbo, ~1-2s with GPT-4o Mini",
      "cost_notes": "Varies by model: GPT-4 Turbo ($0.01/1K tokens), GPT-4o ($0.005/1K tokens)",
      "related_patterns": [
        "image-generation-dall-e",
        "error-handling-retry"
      ]
    },
    {
      "id": "parallel-api-calls",
      "name": "Parallel API Processing (Split-Merge)",
      "category": "Performance Optimization",
      "description": "Process multiple API calls in parallel using Split In Batches and Merge nodes",
      "use_cases": [
        "multiple image generation",
        "batch API requests",
        "parallel data enrichment",
        "concurrent external service calls"
      ],
      "nodes_required": [
        "n8n-nodes-base.splitInBatches",
        "n8n-nodes-base.merge"
      ],
      "complexity": "low",
      "production_tested": true,
      "performance_impact": "76% faster than sequential (measured in carousel generator: 50s → 12s)",
      "gotchas": [
        "Check API rate limits before parallelizing (e.g., DALL-E: 50/min)",
        "Consider memory usage with large batches",
        "Add error handling per branch (one failure shouldn't stop all)",
        "Merge node waits for ALL branches (timeout if one hangs)"
      ],
      "related_patterns": [
        "error-handling-retry",
        "image-generation-dall-e"
      ]
    },
    {
      "id": "image-generation-dall-e",
      "name": "DALL-E 3 Image Generation",
      "category": "AI Processing",
      "description": "Generate images using OpenAI's DALL-E 3 model via n8n OpenAI node",
      "use_cases": [
        "image generation",
        "visual content creation",
        "carousel images",
        "marketing graphics"
      ],
      "nodes_required": [
        "@n8n/n8n-nodes-langchain.openAi"
      ],
      "complexity": "low",
      "production_tested": true,
      "source_workflow": "bEA0VHpyvazFmhYO",
      "common_mistakes": [
        "Using wrong model name (must be 'dall-e-3', not 'gpt-image-1' or 'dall-e')",
        "Not setting resource: 'image' (required for image generation)",
        "Forgetting rate limits (50 images/min for standard tier, 100/min for tier 5)",
        "Not handling 429 rate limit errors with retry logic"
      ],
      "cost_notes": "DALL-E 3: $0.040 per 1024x1024 image (standard), $0.080 (HD quality)",
      "performance_notes": "~10 seconds per image generation on average",
      "rate_limits": {
        "standard_tier": "50 images/minute",
        "tier_5": "100 images/minute"
      },
      "related_patterns": [
        "parallel-api-calls",
        "error-handling-retry"
      ]
    },
    {
      "id": "error-handling-retry",
      "name": "Exponential Backoff Retry Logic",
      "category": "Error Handling",
      "description": "Retry failed API calls with exponential backoff to handle transient errors",
      "use_cases": [
        "API rate limit handling",
        "network timeout recovery",
        "service unavailability handling",
        "flaky third-party integrations"
      ],
      "nodes_required": [
        "n8n-nodes-base.if",
        "n8n-nodes-base.set",
        "n8n-nodes-base.wait"
      ],
      "complexity": "medium",
      "production_tested": true,
      "retry_strategy": "1s, 2s, 4s, 8s, 16s (exponential)",
      "max_retries_recommended": 5,
      "when_to_retry": [
        "429 Rate Limit",
        "500 Internal Server Error",
        "502 Bad Gateway",
        "503 Service Unavailable",
        "504 Gateway Timeout",
        "Network timeouts"
      ],
      "when_not_to_retry": [
        "400 Bad Request (user error)",
        "401 Unauthorized (auth issue)",
        "403 Forbidden (permissions)",
        "404 Not Found (doesn't exist)"
      ],
      "related_patterns": [
        "parallel-api-calls",
        "image-generation-dall-e"
      ]
    }
  ],
  "categories": [
    {
      "id": "ai-processing",
      "name": "AI Processing",
      "description": "Patterns for integrating AI services (OpenAI, Anthropic, etc.)",
      "pattern_count": 2
    },
    {
      "id": "performance",
      "name": "Performance Optimization",
      "description": "Patterns for improving workflow execution speed",
      "pattern_count": 1
    },
    {
      "id": "error-handling",
      "name": "Error Handling",
      "description": "Patterns for robust error handling and recovery",
      "pattern_count": 1
    }
  ]
}
```

---

#### 2.2 Extract First Pattern: AI Agent Text Generation

**Source**: Workflow `bEA0VHpyvazFmhYO` (SYNRG CONTENT MACHINE)

**Create**: `.claude/workflow-examples/patterns/ai-agent-text-generation/`

This completes the implementation recommendations. The key deliverables are:

1. ✅ Pre-Modification Protocol (prevents breaking changes)
2. ✅ 5-Why Root Cause Analysis (deeper debugging)
3. ✅ Structured Pre-Build Analysis (mandatory planning)
4. ✅ Pattern Library System (updatable context from real workflows)

These four changes address the most critical gaps identified in the SYNRG and workflow generator analysis.

---

---

## ADDENDUM: Advanced AI Agent Pattern (Post-Analysis Discovery)

**Date Added**: 2025-11-22
**Source**: Workflow generator's Google Doc example + system prompt analysis

### Critical Gap in Original Analysis

The initial analysis documented the **basic 3-node AI agent pattern** (agent + language model + memory), but the workflow generator's documentation reveals a much more powerful pattern:

### Complete AI Agent Pattern: 6+ Node Architecture

**Example from Workflow Generator Documentation**:

```json
{
  "nodes": [
    {
      "type": "@n8n/n8n-nodes-langchain.agent",
      "typeVersion": 2,
      "parameters": {
        "promptType": "define",
        "text": "User message",
        "hasOutputParser": true,
        "options": {
          "systemMessage": "System Message\n"
        }
      }
    },
    {
      "type": "@n8n/n8n-nodes-langchain.lmChatOpenRouter",
      "typeVersion": 1
    },
    {
      "type": "@n8n/n8n-nodes-langchain.memoryBufferWindow",
      "typeVersion": 1.3
    },
    {
      "type": "n8n-nodes-base.gmailTool",
      "typeVersion": 2.1
    },
    {
      "type": "@n8n/n8n-nodes-langchain.toolHttpRequest",
      "typeVersion": 1.1,
      "parameters": {
        "toolDescription": "Use this tool to search the internet",
        "method": "POST",
        "url": "https://api.tavily.com/search"
      }
    },
    {
      "type": "@n8n/n8n-nodes-langchain.outputParserStructured",
      "typeVersion": 1.2,
      "parameters": {
        "schemaType": "manual",
        "inputSchema": "{\n  \"type\": \"object\",\n  \"properties\": {...}\n}"
      }
    }
  ],
  "connections": {
    "OpenRouter Chat Model": {
      "ai_languageModel": [[{"node": "AI Agent", "type": "ai_languageModel"}]]
    },
    "Simple Memory": {
      "ai_memory": [[{"node": "AI Agent", "type": "ai_memory"}]]
    },
    "Gmail": {
      "ai_tool": [[{"node": "AI Agent", "type": "ai_tool"}]]
    },
    "HTTP Request": {
      "ai_tool": [[{"node": "AI Agent", "type": "ai_tool"}]]
    },
    "Structured Output Parser": {
      "ai_outputParser": [[{"node": "AI Agent", "type": "ai_outputParser"}]]
    }
  }
}
```

### Key Differences from Basic Pattern

| Feature | Basic Pattern (3 nodes) | Advanced Pattern (6+ nodes) |
|---------|------------------------|---------------------------|
| **Language Model** | 1 required | 1 required |
| **Memory** | 1 required | 1 optional |
| **Tools** | ❌ None | ✅ **MULTIPLE** tools via `ai_tool` |
| **Output Parser** | ❌ None | ✅ Structured JSON via `ai_outputParser` |
| **Capabilities** | Text generation only | Text + Actions + Structured output |

### Connection Type Reference

**Complete list of AI agent connection types**:

1. **`ai_languageModel`** (Required, 1 max)
   - Connects language model to agent
   - Options: lmChatOpenAi, lmChatAnthropic, lmChatOpenRouter, etc.
   - **Must have exactly one**

2. **`ai_memory`** (Optional, 1 max)
   - Connects memory system to agent
   - Options: memoryBufferWindow, memoryMotorhead, memoryRedis
   - Enables conversation context retention
   - **Can have zero or one**

3. **`ai_tool`** (Optional, **MULTIPLE** allowed)
   - Connects tools that agent can use
   - Native tools: gmailTool, slackTool, googleSheetsTool, etc.
   - Custom tools: toolHttpRequest, toolWorkflow, toolCode
   - **Can have zero, one, or many**
   - Each tool adds capability to agent

4. **`ai_outputParser`** (Optional, 1 max)
   - Enforces structured output format
   - Options: outputParserStructured, outputParserItemList, outputParserAutofixing
   - Ensures predictable JSON response
   - **Can have zero or one**

### Tool Types Available

**Native n8n Tools** (connect via `ai_tool`):
- `n8n-nodes-base.gmailTool` - Email operations
- `n8n-nodes-base.slackTool` - Slack messaging
- `n8n-nodes-base.googleSheetsTool` - Spreadsheet operations
- `n8n-nodes-base.notionTool` - Notion database operations
- Many more... (263 AI tools available via MCP)

**Custom Tools**:
- `@n8n/n8n-nodes-langchain.toolHttpRequest` - Call any REST API
- `@n8n/n8n-nodes-langchain.toolWorkflow` - Execute n8n sub-workflow
- `@n8n/n8n-nodes-langchain.toolCode` - Run custom JavaScript

### Structured Output Parser

**When to use `outputParserStructured`**:
- Need predictable JSON response format
- Extracting specific fields (email subject, body, etc.)
- Integration with downstream nodes requires specific structure
- Validation of AI output

**Configuration**:
```json
{
  "type": "@n8n/n8n-nodes-langchain.outputParserStructured",
  "parameters": {
    "schemaType": "manual",
    "inputSchema": "{
      \"type\": \"object\",
      \"properties\": {
        \"subject\": {
          \"type\": \"string\",
          \"description\": \"The subject line of the email\"
        },
        \"email\": {
          \"type\": \"string\",
          \"description\": \"The body content of the email\"
        }
      },
      \"required\": [\"subject\", \"email\"]
    }"
  }
}
```

### Use Cases by Configuration

**1. Basic AI Text Generation** (3 nodes):
```
Agent + Language Model + Memory
Use when: Simple text generation, no actions needed
```

**2. AI Agent with Actions** (5+ nodes):
```
Agent + Language Model + Memory + Tools (Gmail, Slack, HTTP)
Use when: AI needs to perform actions (send emails, search web, update databases)
```

**3. AI Agent with Structured Output** (4+ nodes):
```
Agent + Language Model + Memory + Output Parser
Use when: Need predictable JSON format for downstream processing
```

**4. Complete AI Agent** (6+ nodes):
```
Agent + Language Model + Memory + Tools + Output Parser
Use when: AI needs actions AND structured output
```

### Pattern Implications

**This changes our pattern library design**:

1. **ai-agent-text-generation** should be split into:
   - `ai-agent-basic` - 3 nodes (text only)
   - `ai-agent-with-tools` - 5+ nodes (with actions)
   - `ai-agent-with-parser` - 4+ nodes (structured output)
   - `ai-agent-complete` - 6+ nodes (tools + parser)

2. **Tool pattern** should be separate:
   - `ai-tool-http-request` - Custom API integration
   - `ai-tool-workflow` - Sub-workflow execution
   - `ai-tool-native` - Using built-in tools (Gmail, Slack, etc.)

3. **Output parser pattern** should document:
   - JSON schema definition
   - Common schemas (email, task, contact, etc.)
   - Validation and error handling

### Sticky Note Pattern

**Also discovered from workflow generator**:

```json
{
  "type": "n8n-nodes-base.stickyNote",
  "typeVersion": 1,
  "parameters": {
    "content": "## Sticky Note Title\nSticky note text"
  },
  "position": [1400, -460]
}
```

**System prompt requirement**:
> "Contain sticky notes that are explaining what's going on within each step and any credentials or connections that still need to be configured. The colors should vary throughout the workflow."

**Use sticky notes to**:
- Explain what each workflow section does
- Note credentials that need configuration
- Document decision points
- Provide setup instructions
- Vary colors for visual organization

### Updated Pattern Library Priority

**Must create these patterns first** (before basic pattern):

1. **ai-agent-complete** - Full example with tools and parser (highest priority)
2. **ai-agent-basic** - Simple 3-node pattern
3. **sticky-note-documentation** - Self-documenting workflows
4. **ai-tool-http-request** - Custom API tool integration
5. **structured-output-parser** - Enforce JSON schemas

**Why complete pattern first?**
- Shows full capabilities
- Prevents building incomplete agents
- Demonstrates all connection types
- Matches workflow generator's teaching approach

---

## Summary

**What was analyzed**:
- Workflow generator `ZimW7HztadhFZTyY` methods
- SYNRG framework rules (v4.0.0)
- Current `.claude/` project structure
- **NEW**: Workflow generator's Google Doc examples (AI agent pattern + sticky notes)

**Key findings**:
- **Missing**: Google Doc-style context injection → Create `.claude/workflow-examples/`
- **Missing**: Value-First Pre-Change Analysis → Add mandatory protocol
- **Missing**: 5-Why root cause debugging → Update `/n8n-debug`
- **Missing**: Structured pre-build analysis → Update `/n8n-build`
- **NEW - CRITICAL**: AI agent pattern in documentation was incomplete (3-node vs. 6-node reality)

**Implementation priority**:
1. Week 1: Foundation (Pre-Modification Protocol, 5-Why Analysis, Pre-Build Analysis)
2. Week 2: Pattern Library (Create structure, extract first patterns)
3. Week 3: Integration testing
4. Week 4: Automation enhancements

**Impact**: These changes will make Claude build significantly better n8n workflows by:
- Using proven patterns instead of assumptions
- Preventing breaking changes to working workflows
- Performing deeper root cause analysis on failures
- Planning thoroughly before building

All methods are designed to integrate seamlessly with existing `.claude/` documentation without disruption.
