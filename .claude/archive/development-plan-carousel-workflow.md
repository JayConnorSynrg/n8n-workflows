# AI Carousel Generator - Development Execution Plan

**Date:** 2025-11-23
**Status:** PLANNING PHASE
**Objective:** Develop production-ready AI Carousel Generator workflow with 100% parameter coverage and validation

---

## Executive Summary

This plan outlines the systematic development, validation, and deployment of the AI Carousel Generator workflow. Following SYNRG v4.0 Value-First and v3.0 Robustness-First principles, we will:

1. **Assess existing value** (if any similar workflows exist)
2. **Develop locally** with complete parameter validation
3. **Test comprehensively** before deployment
4. **Integrate with project** structure and documentation
5. **Deploy to n8n instance** only when 100% validated

**Time Estimate:** 8-12 hours (production-grade development)
**Quality Target:** All parameters defined, all edge cases handled, zero deployment failures

---

## Phase 0: Value-First Pre-Development Analysis

### Objective
Understand what exists, assess value, determine approach

### Steps

#### 0.1 Check for Existing Carousel Workflows

**Action:**
```bash
# Check n8n instance for existing carousel workflows
mcp__n8n-mcp__n8n_list_workflows | grep -i "carousel\|image\|slide"

# Check local workflow directory
ls -la workflows/ | grep -i "carousel\|image"

# Check templates for similar patterns
mcp__n8n-mcp__search_templates({ query: "carousel image generation" })
```

**Decision Matrix:**
- **If existing workflow found:**
  - Analyze current value (uptime, usage, error rate)
  - Determine if enhancement or replacement needed
  - Follow PRESERVE_AND_ENHANCE if value ≥70
  - Follow COMPREHENSIVE_RESTRUCTURE if value <40

- **If no existing workflow:**
  - Proceed with clean implementation
  - Use proven patterns from context discovery
  - Build production-ready from start

#### 0.2 Assess Current State

**Check:**
- [ ] Existing workflows in n8n instance
- [ ] Similar patterns in local repository
- [ ] Template context availability
- [ ] Required credentials configured
- [ ] n8n instance health status

---

## Phase 1: Project Structure Setup

### Objective
Create intuitive, senior-developer-minded directory structure

### Directory Structure Design

```
/Users/jelalconnor/CODING/N8N/Workflows/
├── workflows/                          # Production workflow definitions
│   ├── production/                     # Live, deployed workflows
│   │   └── marketing/                  # Marketing automation
│   │       └── carousel-generator/     # AI Carousel Generator
│   │           ├── main-workflow.json
│   │           ├── sub-workflow-image-generator.json
│   │           ├── README.md
│   │           ├── CHANGELOG.md
│   │           └── validation-results.md
│   ├── development/                    # WIP workflows
│   │   └── carousel-generator-dev/     # Development version
│   └── library/                        # Reusable sub-workflows
│       └── image-generation/           # Image generation utilities
├── tests/                              # Workflow validation tests
│   └── carousel-generator/
│       ├── unit-tests.json
│       ├── integration-tests.json
│       └── test-data/
├── docs/                               # Documentation
│   └── workflows/
│       └── carousel-generator/
│           ├── architecture.md
│           ├── api-reference.md
│           └── troubleshooting.md
└── .claude/                            # Claude context (existing)
    ├── workflow-examples/
    │   ├── contexts/
    │   │   └── carousel-generator-context/
    │   └── patterns/
    └── agents-evolution.md
```

**Rationale:**
- `production/` - Clear separation of live vs. development
- `marketing/` - Domain-based organization
- `carousel-generator/` - Self-contained workflow package
- `library/` - Reusable components for DRY principle
- `tests/` - Comprehensive validation suite
- `docs/` - User and developer documentation

### Implementation

**Action:**
```bash
# Create directory structure
mkdir -p workflows/{production/marketing/carousel-generator,development/carousel-generator-dev,library/image-generation}
mkdir -p tests/carousel-generator/test-data
mkdir -p docs/workflows/carousel-generator

# Verify structure
tree workflows/ tests/ docs/workflows/
```

---

## Phase 2: Main Workflow Development

### Objective
Develop complete main workflow JSON with all parameters defined

### Sub-Tasks

#### 2.1 Define Workflow Metadata

**Complete Workflow Properties:**
```json
{
  "name": "AI Carousel Generator",
  "nodes": [],
  "connections": {},
  "active": false,
  "settings": {
    "executionOrder": "v1",
    "saveDataErrorExecution": "all",
    "saveDataSuccessExecution": "all",
    "saveManualExecutions": true,
    "saveExecutionProgress": true,
    "callerPolicy": "workflowsFromSameOwner",
    "errorWorkflow": "",
    "timezone": "America/New_York",
    "executionTimeout": 600
  },
  "staticData": {},
  "tags": [
    { "id": "marketing", "name": "Marketing" },
    { "id": "ai-automation", "name": "AI Automation" }
  ],
  "triggerCount": 1,
  "versionId": "1"
}
```

#### 2.2 Define All Nodes

**Node Inventory (Complete Parameter Coverage):**

1. **Manual Trigger** - Entry point
2. **Set User Input** - Define carousel parameters
3. **OpenAI Chat Model** - GPT-4 Turbo for prompts
4. **Memory Buffer Window** - Conversation context
5. **Structured Output Parser** - Parse slide prompts
6. **AI Agent** - Carousel prompt generator
7. **Split Slide Prompts** - Individual slide processing
8. **Execute Workflow (Sub)** - Call image generator
9. **Merge All Slides** - Collect results
10. **Generate Metadata** - Carousel metadata
11. **Error Handler** - Comprehensive error handling
12. **Progress Tracker** - Google Sheets integration

**Each node MUST include:**
- Complete `parameters` object (no placeholders)
- Exact `position` coordinates [x, y]
- Correct `typeVersion`
- All `options` and `credentials`
- Connection definitions

#### 2.3 Define All Connections

**Connection Types:**
- Regular connections: `{ main: [[{ node: "NodeName", type: "main", index: 0 }]] }`
- AI connections: `ai_languageModel`, `ai_memory`, `ai_outputParser`, `ai_tool`
- Error connections: Handle failures

**Validation:**
- All nodes have connections (no orphans)
- Connection references point to existing nodes
- AI connections use correct types
- Dependency order is correct

---

## Phase 3: Sub-Workflow Development

### Objective
Develop image generation sub-workflow with complete error handling

### Components

#### 3.1 Image Generator Sub-Workflow

**Nodes:**
1. Execute Workflow Trigger
2. Extract Parameters
3. Rate Limit Manager (Code)
4. Wait (If Rate Limited)
5. HTTP Request - DALL-E 3
6. Extract Image Data
7. HTTP Request - GPT-4 Vision
8. Parse Quality Analysis
9. Quality Check (IF)
10. Modify Prompt (Code) - If quality low
11. Google Drive Upload
12. Set Public Permissions
13. Format Response
14. Respond to Workflow

**Complete Parameter Coverage:**
- DALL-E 3 API: model, prompt, size, quality, style, response_format
- GPT-4 Vision API: model, messages, response_format, max_tokens
- Google Drive: folderId, name, permissions
- Rate Limiting: maxCallsPerMinute, windowMs, retry logic

#### 3.2 Error Handling Nodes

**Error Scenarios:**
- API timeout
- Rate limit exceeded
- Invalid response format
- Quality check failure
- Google Drive failure

**Handling:**
- Try-catch blocks in Code nodes
- Error branches with logging
- Retry logic with exponential backoff
- User-friendly error messages

---

## Phase 4: Local Validation (Pre-Deployment)

### Objective
100% validation before touching n8n instance

### Validation Layers

#### 4.1 JSON Schema Validation

**Validate:**
```bash
# Use n8n MCP validation
mcp__n8n-mcp__validate_workflow({ workflow: mainWorkflowJSON })

# Check for:
# - Valid node types
# - Correct parameter structures
# - Valid connection references
# - No circular dependencies
```

**Expected:**
- ✅ 0 validation errors
- ✅ 0 validation warnings
- ✅ All nodes recognized
- ✅ All connections valid

#### 4.2 Parameter Completeness Check

**Create validation script:**
```javascript
// scripts/validate-workflow-params.js
function validateParameterCompleteness(workflow) {
  const issues = [];

  workflow.nodes.forEach(node => {
    // Check for placeholder values
    const hasPlaceholders = JSON.stringify(node.parameters).match(/YOUR_.*_HERE|PLACEHOLDER|TODO/i);
    if (hasPlaceholders) {
      issues.push(`Node ${node.name}: Contains placeholders`);
    }

    // Check for empty required fields
    if (node.type === 'n8n-nodes-base.httpRequest') {
      if (!node.parameters.url) issues.push(`Node ${node.name}: Missing URL`);
      if (!node.parameters.authentication) issues.push(`Node ${node.name}: Missing authentication`);
    }

    // Check credentials are configured
    if (node.credentials && Object.keys(node.credentials).length === 0) {
      issues.push(`Node ${node.name}: Credentials not configured`);
    }
  });

  return { valid: issues.length === 0, issues };
}
```

#### 4.3 Dependency Analysis

**Check:**
- [ ] All required credentials exist in n8n
- [ ] All sub-workflows exist before main workflow
- [ ] API rate limits understood and configured
- [ ] Google Drive folder exists
- [ ] Environment variables set

#### 4.4 Dry-Run Simulation

**Simulate workflow execution:**
```javascript
// Simulate each node's execution
// Validate expected inputs/outputs
// Check for potential runtime errors
// Verify error handling paths
```

---

## Phase 5: Integration with Project Structure

### Objective
Weave workflow into existing project ruleset

### Integration Points

#### 5.1 Update .claude/CLAUDE.md

**Add section:**
```markdown
### AI Carousel Generator Workflow

**Purpose:** Generate 5-slide carousels with AI-powered image generation and quality validation

**Location:** `workflows/production/marketing/carousel-generator/`

**Workflow IDs:**
- Main: [ID after deployment]
- Sub-workflow: [ID after deployment]

**Trigger:** Manual (webhook available)

**Output:** 5 images + metadata (Google Drive URLs)

**Error Handling:** Comprehensive retry logic, Google Sheets logging

**Monitoring:** Progress tracking in Google Sheets

**Documentation:** `docs/workflows/carousel-generator/`
```

#### 5.2 Update agents-evolution.md

**Document development patterns:**
```markdown
## [2025-11-23] Workflow: AI Carousel Generator

### Positive Pattern: Value-First Local Development Before Deployment

**Solution:** Develop workflows locally with complete validation before n8n deployment

**Implementation:**
1. Created local workflow JSON with 100% parameter coverage
2. Validated with n8n MCP tools (schema, parameters, connections)
3. Simulated execution with dry-run testing
4. Documented all assumptions and decisions
5. Deployed only when validation passed

**Result:**
- Zero deployment failures
- All parameters pre-validated
- Comprehensive error handling included
- Documentation complete before deployment

**Reusable Pattern:** Always develop workflows locally first, deploy only after 100% validation
```

#### 5.3 Create Workflow Documentation

**Files to create:**
- `workflows/production/marketing/carousel-generator/README.md` - User guide
- `docs/workflows/carousel-generator/architecture.md` - Technical details
- `docs/workflows/carousel-generator/api-reference.md` - Parameter reference
- `docs/workflows/carousel-generator/troubleshooting.md` - Common issues

---

## Phase 6: Deployment to n8n Instance

### Objective
Deploy validated workflows with zero failures

### Deployment Steps

#### 6.1 Pre-Deployment Checklist

**Verify:**
- [ ] All validation passed (Phase 4)
- [ ] Documentation complete
- [ ] Credentials configured in n8n
- [ ] Google Drive folder created
- [ ] Error logging sheet created
- [ ] n8n instance healthy
- [ ] Backup of existing workflows

#### 6.2 Deploy Sub-Workflow First

**Action:**
```javascript
// Deploy image generator sub-workflow
const subWorkflow = require('./workflows/production/marketing/carousel-generator/sub-workflow-image-generator.json');

const result = await mcp__n8n-mcp__n8n_create_workflow(subWorkflow);

console.log('Sub-workflow ID:', result.id);
console.log('Status:', result.active ? 'Active' : 'Inactive');
```

**Validation:**
- ✅ Sub-workflow created successfully
- ✅ ID captured for main workflow reference
- ✅ Test execution passes

#### 6.3 Update Main Workflow with Sub-Workflow ID

**Action:**
```javascript
// Update Execute Workflow node with actual sub-workflow ID
mainWorkflow.nodes.find(n => n.name === 'Generate Slide Image').parameters.workflowId = subWorkflowId;
```

#### 6.4 Deploy Main Workflow

**Action:**
```javascript
const mainWorkflow = require('./workflows/production/marketing/carousel-generator/main-workflow.json');

const result = await mcp__n8n-mcp__n8n_create_workflow(mainWorkflow);

console.log('Main workflow ID:', result.id);
```

#### 6.5 Post-Deployment Validation

**Test:**
```javascript
// 1. Manual execution test
const execution = await mcp__n8n-mcp__n8n_trigger_webhook_workflow({
  webhookUrl: 'https://jayconnorexe.app.n8n.cloud/webhook/carousel/test',
  data: {
    theme: 'AI automation benefits for small businesses',
    style: 'vivid',
    audience: 'business owners'
  },
  waitForResponse: true
});

// 2. Verify output structure
console.log('Execution ID:', execution.id);
console.log('Status:', execution.finished ? 'Success' : 'Failed');

// 3. Check for errors
const executionDetails = await mcp__n8n-mcp__n8n_get_execution({
  id: execution.id,
  mode: 'preview'
});

console.log('Errors:', executionDetails.data.resultData.error || 'None');
```

---

## Phase 7: Monitoring & Iteration

### Objective
Ensure production stability and continuous improvement

### Monitoring Plan

#### 7.1 Success Metrics

**Track:**
- Execution success rate (target: >95%)
- Average execution time (target: <5 minutes)
- Image quality score (target: average >7.5)
- Retry frequency (target: <10% of executions)
- Error types and frequency

#### 7.2 Error Logging

**Google Sheets Structure:**
```
| Timestamp | Carousel ID | Slide # | Error Type | Error Message | Retry Count | Status |
```

#### 7.3 Iteration Protocol

**When issues arise:**
1. Analyze error logs
2. Identify root cause (5-Why)
3. Update workflow locally
4. Validate changes
5. Deploy update
6. Document in agents-evolution.md

---

## Parameter Definition Strategy

### Approach

**For each node, define:**

1. **Required Parameters** - No defaults, must be explicit
2. **Optional Parameters** - Defaults provided with rationale
3. **Credential References** - Exact credential types
4. **Dynamic Expressions** - n8n expression syntax verified
5. **Edge Cases** - Handle empty, null, undefined

### Parameter Documentation Template

```javascript
// Node: [Name]
{
  "parameters": {
    // REQUIRED
    "requiredParam": "value",  // Why required: [reason]

    // OPTIONAL (with defaults)
    "optionalParam": "default",  // Default rationale: [reason]

    // DYNAMIC (expressions)
    "dynamicParam": "={{ $json.field }}",  // Source: [node/field]

    // EDGE CASES HANDLED
    "edgeCaseParam": "={{ $json.field || 'fallback' }}"  // Handles: null, undefined
  },

  // CREDENTIALS
  "credentials": {
    "credentialType": {
      "id": "credentialId",  // Must exist in n8n
      "name": "credentialName"
    }
  }
}
```

---

## Risk Assessment & Mitigation

### Identified Risks

**Risk 1: API Rate Limiting**
- **Probability:** HIGH (DALL-E has strict limits)
- **Impact:** MEDIUM (execution fails mid-carousel)
- **Mitigation:**
  - Rate limit manager with workflow static data
  - Wait periods between images
  - Exponential backoff on 429 errors

**Risk 2: Quality Check False Negatives**
- **Probability:** MEDIUM (AI judgment variability)
- **Impact:** LOW (lower quality images accepted)
- **Mitigation:**
  - Threshold tuning (test with various quality levels)
  - Multiple quality criteria (not just one score)
  - User override option

**Risk 3: Google Drive Upload Failure**
- **Probability:** LOW (stable API)
- **Impact:** HIGH (images generated but not stored)
- **Mitigation:**
  - Retry logic (3 attempts)
  - Alternative storage fallback (local n8n storage)
  - Error notification

**Risk 4: Sub-Workflow Execution Failure**
- **Probability:** MEDIUM (complex workflow)
- **Impact:** HIGH (entire carousel fails)
- **Mitigation:**
  - Comprehensive error handling in sub-workflow
  - Return error status (don't throw)
  - Main workflow handles sub-workflow errors gracefully

**Risk 5: Incomplete Parameter Definitions**
- **Probability:** MEDIUM (complex workflow, many nodes)
- **Impact:** HIGH (deployment failure)
- **Mitigation:**
  - THIS PLAN - systematic parameter definition
  - Validation scripts
  - Dry-run testing before deployment

---

## Success Criteria

### Deployment Success

**MUST achieve:**
- ✅ Workflow deploys without errors
- ✅ All nodes have complete parameters (0 placeholders)
- ✅ Credentials configured and accessible
- ✅ Test execution completes end-to-end
- ✅ All 5 images generated successfully
- ✅ Images uploaded to Google Drive
- ✅ Public URLs returned and accessible
- ✅ Metadata generated correctly
- ✅ Error handling triggers on forced errors
- ✅ Progress tracking updates Google Sheets

### Quality Success

**MUST achieve:**
- ✅ Average image quality score >7.5
- ✅ Execution success rate >95%
- ✅ Average execution time <5 minutes
- ✅ Zero manual interventions required
- ✅ Comprehensive error logs
- ✅ Documentation complete and accurate

### Production Readiness

**MUST achieve:**
- ✅ Can run 10 executions consecutively without failure
- ✅ Rate limiting prevents API errors
- ✅ Retry logic handles transient failures
- ✅ Error recovery does not corrupt state
- ✅ Monitoring shows all metrics
- ✅ Can deploy to production immediately after validation

---

## Timeline Estimate

**Phase 0:** Value-First Analysis - 30 minutes
**Phase 1:** Project Structure - 15 minutes
**Phase 2:** Main Workflow Development - 3 hours
**Phase 3:** Sub-Workflow Development - 3 hours
**Phase 4:** Local Validation - 1 hour
**Phase 5:** Project Integration - 1 hour
**Phase 6:** Deployment - 30 minutes
**Phase 7:** Monitoring Setup - 30 minutes

**Total:** 9.5 hours (conservative estimate for production-grade)

---

## Next Actions

**Immediate (User Approval Required):**
1. ✅ Development plan created
2. ⏳ User reviews and approves plan
3. ⏳ Begin Phase 0: Value-First Analysis

**Upon Approval:**
1. Execute Phase 0 (check existing workflows)
2. Create directory structure (Phase 1)
3. Begin systematic workflow development (Phase 2-3)
4. Validate locally before deployment (Phase 4)
5. Deploy only when 100% validated (Phase 6)

---

**Development Philosophy:**
- Take time to do it right
- Validate everything before deployment
- Document comprehensively
- Zero deployment failures acceptable

**Quality Standard:** Production-ready from day one.
