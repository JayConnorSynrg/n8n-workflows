# n8n Workflow Development Protocol

**Last Updated:** 2025-11-23
**Status:** ACTIVE - Integrated with CLAUDE.md

---

## Core Principles

### 1. Local-First Development

**ALWAYS develop workflows locally before deploying:**

```
Local JSON File → Validation → Testing → Deployment to Instance
```

**Never:**
- ❌ Edit workflows directly in n8n UI
- ❌ Create workflows in instance first
- ❌ Deploy without local validation
- ❌ Modify workflows without local backup

**Always:**
- ✅ Create/edit JSON files locally in `workflows/` directory
- ✅ Validate with n8n MCP tools before deployment
- ✅ Test parameter completeness locally
- ✅ Document changes in local files
- ✅ Version control all workflow changes

---

### 2. Context Sources for Development

**Primary Context Source: n8n-workflows MCP (GitHub Templates)**

Use `mcp__n8n-workflows__*` tools for:
- ✅ Template discovery
- ✅ Pattern examples
- ✅ Node configuration references
- ✅ Best practices from community

**Do NOT use n8n instance for context:**
- ❌ Do NOT list workflows from instance for examples
- ❌ Do NOT fetch workflows from instance as templates
- ❌ Only interact with instance for deployment/updates of specific workflow IDs

**Exception:**
- ✅ Fetch specific workflow by ID when updating (with explicit user permission)
- ✅ Check workflow status after deployment
- ✅ Get execution results for debugging

---

### 3. Workflow ID Management

**When working on existing workflows:**

**Rule:** Only modify workflows with explicitly provided IDs

**Example:**
```javascript
// CORRECT - User provided ID
const workflowId = '8bhcEHkbbvnhdHBh';
await updateWorkflow(workflowId, localWorkflowJSON);

// INCORRECT - Creating new workflow
await createWorkflow(localWorkflowJSON);  // ❌ Not allowed unless explicitly requested
```

**ID Assignment:**
- User provides target workflow ID
- Only that ID is modified
- No other workflows touched
- No new workflows created (unless explicitly requested)

---

## Development Workflow

### Phase 1: Fetch Current State (If Updating)

**Only when user provides workflow ID:**

```javascript
// Fetch current workflow structure
const currentWorkflow = await mcp__n8n-mcp__n8n_get_workflow({
  id: '8bhcEHkbbvnhdHBh'
});

// Save to local file for baseline
const fs = require('fs');
fs.writeFileSync(
  'workflows/development/carousel-generator/workflow-8bhcEHkbbvnhdHBh-baseline.json',
  JSON.stringify(currentWorkflow, null, 2)
);
```

---

### Phase 2: Local Development

**Directory Structure:**

```
workflows/
├── development/
│   └── [workflow-name]/
│       ├── workflow-[ID].json           # Current version
│       ├── workflow-[ID]-baseline.json  # Original fetched state
│       ├── workflow-[ID]-validated.json # After validation
│       └── CHANGELOG.md                 # Version history
├── production/
│   └── [deployed-workflows]/
└── library/
    └── [reusable-sub-workflows]/
```

**Development Steps:**

1. **Create local workflow file:**
```bash
mkdir -p workflows/development/carousel-generator
touch workflows/development/carousel-generator/workflow-8bhcEHkbbvnhdHBh.json
```

2. **Build workflow JSON with complete parameters:**
```json
{
  "name": "AI Carousel Generator",
  "nodes": [
    {
      "id": "node-uuid-1",
      "name": "Node Name",
      "type": "node-type",
      "typeVersion": 1,
      "position": [x, y],
      "parameters": {
        // ALL parameters defined
        // NO placeholders like "YOUR_VALUE_HERE"
        // NO undefined or null values
      },
      "credentials": {
        // Exact credential references
      }
    }
    // ... all nodes
  ],
  "connections": {
    // All connections defined
  },
  "settings": {
    // Workflow settings
  }
}
```

3. **Document changes:**
```markdown
# CHANGELOG.md

## [2025-11-23] - Complete Rebuild
### Changed
- Replaced all nodes with correct AI Agent architecture
- Added comprehensive error handling
- Implemented rate limiting for DALL-E API
- Added quality validation with GPT-4 Vision

### Fixed
- Incorrect node types (removed invalid resource: "text")
- Missing AI Agent connections (ai_languageModel, ai_memory)
- Incomplete parameter definitions
```

---

### Phase 3: Local Validation

**Validation Checklist:**

```javascript
// 1. JSON Schema Validation
const validation = await mcp__n8n-mcp__validate_workflow({
  workflow: localWorkflowJSON
});

console.log('Validation Result:', validation);
// Expected: { valid: true, errors: [] }

// 2. Parameter Completeness Check
function checkParameterCompleteness(workflow) {
  const issues = [];

  workflow.nodes.forEach(node => {
    // Check for placeholders
    const json = JSON.stringify(node.parameters);
    if (json.match(/YOUR_|PLACEHOLDER|TODO|undefined|null/i)) {
      issues.push(`${node.name}: Contains placeholders or undefined values`);
    }

    // Check required fields per node type
    if (node.type === 'n8n-nodes-base.httpRequest') {
      if (!node.parameters.url) issues.push(`${node.name}: Missing URL`);
      if (!node.parameters.method) issues.push(`${node.name}: Missing method`);
    }

    if (node.type === '@n8n/n8n-nodes-langchain.agent') {
      if (!node.parameters.text) issues.push(`${node.name}: Missing prompt text`);
    }

    // Check AI connections
    if (node.type.includes('langchain.agent')) {
      const hasLLM = workflow.connections[node.name]?.ai_languageModel;
      const hasMemory = workflow.connections[node.name]?.ai_memory;
      if (!hasLLM) issues.push(`${node.name}: Missing ai_languageModel connection`);
      if (!hasMemory) issues.push(`${node.name}: Missing ai_memory connection`);
    }
  });

  return { valid: issues.length === 0, issues };
}

const completeness = checkParameterCompleteness(localWorkflowJSON);
console.log('Parameter Completeness:', completeness);

// 3. Connection Validation
function validateConnections(workflow) {
  const issues = [];
  const nodeNames = new Set(workflow.nodes.map(n => n.name));

  Object.entries(workflow.connections).forEach(([source, targets]) => {
    if (!nodeNames.has(source)) {
      issues.push(`Connection source "${source}" not found in nodes`);
    }

    Object.values(targets).flat().forEach(conn => {
      if (conn.node && !nodeNames.has(conn.node)) {
        issues.push(`Connection target "${conn.node}" not found in nodes`);
      }
    });
  });

  return { valid: issues.length === 0, issues };
}

const connections = validateConnections(localWorkflowJSON);
console.log('Connection Validation:', connections);

// 4. Save validated version
if (validation.valid && completeness.valid && connections.valid) {
  fs.writeFileSync(
    'workflows/development/carousel-generator/workflow-8bhcEHkbbvnhdHBh-validated.json',
    JSON.stringify(localWorkflowJSON, null, 2)
  );
  console.log('✅ Workflow validated and saved');
} else {
  console.error('❌ Validation failed:', { validation, completeness, connections });
}
```

**Validation Must Pass:**
- ✅ JSON schema validation (0 errors)
- ✅ Parameter completeness (0 placeholders)
- ✅ Connection validation (all references valid)
- ✅ Node type validation (all types exist)
- ✅ Credential references (all exist in instance)

---

### Phase 4: Documentation Update

**Update project rules to include workflow:**

**File:** `.claude/CLAUDE.md`

```markdown
### Active Workflows

**AI Carousel Generator**
- **ID:** `8bhcEHkbbvnhdHBh`
- **Status:** Active Development
- **Location:** `workflows/development/carousel-generator/workflow-8bhcEHkbbvnhdHBh.json`
- **Purpose:** Generate 5-slide AI carousels with image generation and quality validation
- **Last Updated:** 2025-11-23
- **Documentation:** `workflows/development/carousel-generator/README.md`

**Development Protocol:**
- Local JSON file is source of truth
- Validate locally before deployment
- Update instance only after validation passes
- Document all changes in CHANGELOG.md
```

**Create README:**

```markdown
# AI Carousel Generator Workflow

**Workflow ID:** `8bhcEHkbbvnhdHBh`
**Type:** AI-Powered Content Generation
**Status:** Active Development

## Overview

Generates 5-slide carousels using AI:
- AI Agent generates coherent slide prompts
- DALL-E 3 creates images for each slide
- GPT-4 Vision validates quality
- Images stored in Google Drive
- Returns public URLs for all images

## Architecture

[Detailed architecture diagram and node descriptions]

## Usage

[How to trigger and use the workflow]

## Parameters

[All configurable parameters documented]

## Error Handling

[Error scenarios and recovery mechanisms]

## Monitoring

[How to monitor execution and debug issues]
```

---

### Phase 5: Deployment

**Only deploy when 100% validated:**

```javascript
// Load validated workflow
const validatedWorkflow = require('./workflows/development/carousel-generator/workflow-8bhcEHkbbvnhdHBh-validated.json');

// Deploy to specific workflow ID (user-provided)
const result = await mcp__n8n-mcp__n8n_update_full_workflow({
  id: '8bhcEHkbbvnhdHBh',
  ...validatedWorkflow
});

console.log('Deployment Result:', result);

// Verify deployment
const deployed = await mcp__n8n-mcp__n8n_get_workflow({
  id: '8bhcEHkbbvnhdHBh'
});

console.log('Deployed Successfully:', deployed.name);
```

**Post-Deployment:**

```javascript
// Test execution
const execution = await mcp__n8n-mcp__n8n_trigger_webhook_workflow({
  webhookUrl: 'https://jayconnorexe.app.n8n.cloud/webhook/carousel-test',
  data: { theme: 'Test Theme' },
  waitForResponse: true
});

console.log('Test Execution:', execution);

// Check for errors
const executionDetails = await mcp__n8n-mcp__n8n_get_execution({
  id: execution.id,
  mode: 'preview'
});

console.log('Execution Status:', executionDetails.status);
```

---

## Context Discovery with n8n-workflows MCP

**Use GitHub templates for patterns and examples:**

```javascript
// Search for carousel/image generation templates
const templates = await mcp__n8n-workflows__search_repositories({
  query: 'carousel image generation dall-e',
  page: 1,
  perPage: 10
});

console.log('Found Templates:', templates.items.length);

// Get specific template for reference
const templateContent = await mcp__n8n-workflows__get_file_contents({
  owner: 'template-owner',
  repo: 'template-repo',
  path: 'workflows/carousel-generator.json'
});

console.log('Template Content:', templateContent);

// Use template as reference for node configurations
// Adapt to our specific needs
// DO NOT copy blindly - validate all parameters
```

**Pattern Examples from n8n-workflows MCP:**

```javascript
// Example: AI Agent with Tool pattern
const aiAgentExample = await mcp__n8n-workflows__get_file_contents({
  owner: 'n8n-io',
  repo: 'n8n-docs',
  path: 'examples/ai-agent-with-tools.json'
});

// Example: Image generation with DALL-E
const dalleExample = await mcp__n8n-workflows__search_code({
  q: 'dall-e-3 image generation n8n',
  per_page: 5
});

// Example: Google Drive upload pattern
const gdriveExample = await mcp__n8n-workflows__search_code({
  q: 'google drive upload n8n public url',
  per_page: 5
});
```

---

## Integration with Project Structure

### File Organization

```
/Users/jelalconnor/CODING/N8N/Workflows/
├── workflows/
│   ├── development/
│   │   └── carousel-generator/
│   │       ├── workflow-8bhcEHkbbvnhdHBh.json
│   │       ├── workflow-8bhcEHkbbvnhdHBh-baseline.json
│   │       ├── workflow-8bhcEHkbbvnhdHBh-validated.json
│   │       ├── CHANGELOG.md
│   │       └── README.md
│   ├── production/
│   │   └── [deployed-workflows]
│   └── library/
│       └── [sub-workflows]
├── .claude/
│   ├── CLAUDE.md (updated with workflow info)
│   ├── agents-evolution.md (patterns documented)
│   └── WORKFLOW-DEVELOPMENT-PROTOCOL.md (this file)
└── scripts/
    ├── validate-workflow.js
    └── deploy-workflow.js
```

### Git Integration

**Commit workflow changes:**

```bash
git add workflows/development/carousel-generator/
git commit -m "feat(workflows): complete rebuild of AI Carousel Generator (8bhcEHkbbvnhdHBh)

- Replaced incorrect node types with proper AI Agent architecture
- Added comprehensive error handling and retry logic
- Implemented quality validation with GPT-4 Vision
- Added rate limiting for DALL-E API
- All parameters defined (0 placeholders)
- Local validation passed

Workflow ID: 8bhcEHkbbvnhdHBh
Local File: workflows/development/carousel-generator/workflow-8bhcEHkbbvnhdHBh.json"
```

---

## Best Practices

### Parameter Definition

**Complete Parameter Coverage:**

```json
{
  "parameters": {
    // ✅ GOOD - Explicit value
    "url": "https://api.openai.com/v1/images/generations",
    "method": "POST",

    // ✅ GOOD - Dynamic expression with fallback
    "prompt": "={{ $json.prompt || 'Default prompt' }}",

    // ✅ GOOD - Credential reference
    "authentication": "predefinedCredentialType",

    // ❌ BAD - Placeholder
    "apiKey": "YOUR_API_KEY_HERE",

    // ❌ BAD - Undefined
    "timeout": undefined,

    // ❌ BAD - Null
    "retries": null
  }
}
```

### Error Handling

**Every workflow must include:**

1. **Error Trigger Workflow** (optional but recommended)
2. **Try-catch in Code nodes**
3. **Error branches on critical nodes**
4. **Retry logic for external APIs**
5. **Error logging to external system**

### Testing Protocol

**Before deployment:**

1. ✅ JSON validation passes
2. ✅ Parameter completeness check passes
3. ✅ Connection validation passes
4. ✅ All credential references exist
5. ✅ Dry-run simulation successful
6. ✅ Documentation complete

**After deployment:**

1. ✅ Manual test execution successful
2. ✅ No errors in execution logs
3. ✅ Output matches expected format
4. ✅ Error handling triggers correctly
5. ✅ Monitoring shows healthy state

---

## Troubleshooting

### Common Issues

**Issue: "Node type not found"**
- **Cause:** Incorrect node type reference
- **Solution:** Verify node type with `mcp__n8n-mcp__list_nodes`

**Issue: "Parameter validation failed"**
- **Cause:** Missing required parameter
- **Solution:** Check node documentation with `mcp__n8n-mcp__get_node_info`

**Issue: "Connection reference invalid"**
- **Cause:** Connection points to non-existent node
- **Solution:** Verify all node names in connections match nodes array

**Issue: "Credential not found"**
- **Cause:** Credential reference doesn't exist in instance
- **Solution:** Create credential in n8n instance first, then reference ID

### Anti-Patterns and Corrections

**CRITICAL CORRECTION (2025-11-23):**

**❌ INCORRECT Anti-Pattern:**
```markdown
"Don't use newer node typeVersions just because they exist. Always reference
working examples from the instance to identify correct typeVersions."

Example:
- Image Generation: model: "dall-e-3", typeVersion: 2 ❌
- Image Generation: model: "gpt-image-1", typeVersion: 1.8 ✅
```

**✅ CORRECT Approach:**
```markdown
"ALWAYS prioritize newest node typeVersions. Configuration errors are more
common than version incompatibilities. Verify parameter requirements for
the version you're using."

Example:
- DALL-E 3 Image Generation (Latest Version):
  - typeVersion: Latest available in n8n
  - model: "dall-e-3" (loaded dynamically from OpenAI API)
  - Ensure proper parameter configuration for the version

Key Insight:
- The issue was improper node configuration, NOT version incompatibility
- Model IDs like "gpt-image-1" are dynamically loaded from OpenAI API
- n8n filters models with: model.id.startsWith('dall-')
- Always check official n8n documentation for latest parameter requirements
```

**Model Selection Best Practices:**

For OpenAI Image Generation node:
1. **Use latest typeVersion** available in n8n
2. **Model field loads dynamically** from OpenAI `/v1/models` API
3. **Valid models:** Any starting with `dall-` (e.g., `dall-e-2`, `dall-e-3`)
4. **Verify parameters** match typeVersion requirements:
   - Check `options` field for quality, size, style (DALL-E 3 specific)
   - Validate prompt length limits (1000 for DALL-E 2, 4000 for DALL-E 3)
   - Confirm response format options (binaryData vs imageUrl)

**Reference Documentation:**
- Comprehensive AI Models Guide: `.reference/ai-models-and-n8n-nodes-2025.md`
- Official n8n Docs: https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-langchain.openai/image-operations/

---

## Integration with CLAUDE.md

**This protocol is now part of the official project ruleset.**

**Add to `.claude/CLAUDE.md`:**

```markdown
## n8n Workflow Development

**Protocol:** See `.claude/WORKFLOW-DEVELOPMENT-PROTOCOL.md`

**Key Rules:**
1. **Local-First Development** - Create JSON files locally, validate before deploying
2. **Workflow ID Management** - Only modify user-specified workflow IDs
3. **Context from n8n-workflows MCP** - Use GitHub templates, not instance workflows
4. **100% Parameter Coverage** - No placeholders, all values defined
5. **Validation Required** - Pass all checks before deployment

**Current Workflows:**
- **AI Carousel Generator** (ID: `8bhcEHkbbvnhdHBh`)
  - Location: `workflows/development/carousel-generator/`
  - Status: Active Development
  - Last Updated: 2025-11-23
```

---

## Quick Reference

**Workflow Development Checklist:**

- [ ] Create local directory: `workflows/development/[workflow-name]/`
- [ ] Fetch baseline (if updating): `workflow-[ID]-baseline.json`
- [ ] Build workflow: `workflow-[ID].json`
- [ ] Validate JSON schema: `mcp__n8n-mcp__validate_workflow`
- [ ] Check parameter completeness: Custom validation script
- [ ] Validate connections: Custom validation script
- [ ] Create README.md and CHANGELOG.md
- [ ] Update .claude/CLAUDE.md with workflow info
- [ ] Save validated version: `workflow-[ID]-validated.json`
- [ ] Deploy to instance: `mcp__n8n-mcp__n8n_update_full_workflow`
- [ ] Test execution: Trigger workflow and verify output
- [ ] Commit to git: Version control all changes

**Context Discovery:**
- Use `mcp__n8n-workflows__*` for templates and examples
- Search GitHub repos for patterns
- Get file contents for reference implementations
- Adapt to specific needs (don't copy blindly)

**Deployment:**
- Only to user-specified workflow IDs
- Only after 100% validation
- Only when documentation complete
- Test immediately after deployment

---

## Form Trigger Configuration Patterns

### Critical Pattern: Form Trigger + Respond to Webhook

**Discovered:** 2025-11-24 (Execution #1427)

**Context:** Form Trigger node requires explicit `responseMode` configuration when paired with "Respond to Webhook" node.

#### The Pattern

**When using Form Trigger WITH Respond to Webhook node:**

```json
{
  "name": "Form Trigger",
  "type": "n8n-nodes-base.formTrigger",
  "typeVersion": 2.1,
  "parameters": {
    "path": "your-form-path",
    "formTitle": "Your Form Title",
    "formDescription": "Form description",
    "formFields": { /* form fields config */ },
    "responseMode": "responseNode",  // ✅ CRITICAL - Must be set
    "options": {
      "respondWithOptions": {
        "values": {
          "formSubmittedText": "Processing... Please wait."
        }
      }
    }
  }
}
```

#### responseMode Options

**`"onReceived"` (default if not specified):**
- Form responds immediately when webhook triggered
- Cannot use with "Respond to Webhook" node at end of workflow
- Use when: Simple form submission with immediate confirmation
- Response: Shows `formSubmittedText` from options immediately

**`"responseNode"` (recommended for long workflows):**
- Delegates response handling to "Respond to Webhook" node
- Required when: Workflow has "Respond to Webhook" node at end
- Use when: Need to process data before responding (AI generation, API calls, etc.)
- Response: Controlled by "Respond to Webhook" node parameters

**`"lastNode"` (advanced):**
- Form responds with data from last node execution
- No explicit "Respond to Webhook" node needed
- Use when: Want to return workflow execution results directly
- Response: JSON/data from final node

#### Common Error

**Error Message:**
```
Form Trigger node not correctly configured: Set the "Respond When" parameter
to "Using Respond to Webhook Node" or remove the Respond to Webhook node
```

**Root Cause:**
- Form Trigger missing `responseMode` parameter (defaults to `"onReceived"`)
- Workflow has "Respond to Webhook" node at end
- Conflict: Form tries to respond immediately but workflow expects delayed response

**Fix:**
```json
{
  "parameters": {
    "responseMode": "responseNode"  // Add this line
  }
}
```

#### When to Use Each Mode

| Scenario | responseMode | Respond to Webhook Node |
|----------|--------------|------------------------|
| Simple contact form | `"onReceived"` | No |
| AI generation (3-5 min) | `"responseNode"` | Yes (at end) |
| Data enrichment | `"responseNode"` | Yes (at end) |
| Multi-step processing | `"responseNode"` | Yes (at end) |
| Quick confirmation | `"lastNode"` | No |

#### Real-World Example

**Scenario:** AI Carousel Generator (Workflow: 8bhcEHkbbvnhdHBh)

**Requirements:**
- User submits form
- Workflow takes 3-5 minutes (AI generation + image creation)
- Return complete carousel metadata with image URLs

**Implementation:**
```json
{
  "nodes": [
    {
      "name": "Form Trigger",
      "type": "n8n-nodes-base.formTrigger",
      "parameters": {
        "path": "carousel-form",
        "responseMode": "responseNode",  // ✅ Required for long workflow
        "options": {
          "respondWithOptions": {
            "values": {
              "formSubmittedText": "Generating your carousel... This may take 3-5 minutes."
            }
          }
        }
      }
    },
    // ... processing nodes (AI Agent, DALL-E, etc.)
    {
      "name": "Respond to Form",
      "type": "n8n-nodes-base.respondToWebhook",
      "parameters": {
        "respondWith": "allEntries",
        "responseBody": "={{ JSON.stringify($json, null, 2) }}"
      }
    }
  ]
}
```

**Flow:**
1. User submits form → Shows immediate message: "Generating your carousel..."
2. Form stays open (waiting for response)
3. Workflow processes (3-5 minutes)
4. "Respond to Webhook" returns final data
5. Form displays final response

#### Anti-Pattern

**❌ WRONG - Missing responseMode:**
```json
{
  "name": "Form Trigger",
  "parameters": {
    "path": "carousel-form",
    // Missing: "responseMode": "responseNode"
  }
}
// Result: Error when workflow has Respond to Webhook node
```

**❌ WRONG - Using onReceived with long workflow:**
```json
{
  "name": "Form Trigger",
  "parameters": {
    "responseMode": "onReceived"  // Form closes immediately
  }
}
// Result: Form closes before workflow completes, user never sees final result
```

#### Validation Checklist

When using Form Trigger:

- [ ] Does workflow have "Respond to Webhook" node?
  - Yes → `"responseMode": "responseNode"` required
  - No → `"responseMode": "onReceived"` or `"lastNode"` okay
- [ ] Is workflow execution time > 5 seconds?
  - Yes → Use `"responseMode": "responseNode"` with custom response
  - No → `"onReceived"` acceptable
- [ ] Do you need to return processed data?
  - Yes → Use `"responseMode": "responseNode"` or `"lastNode"`
  - No → `"onReceived"` with simple confirmation
- [ ] Is `formSubmittedText` set for user feedback?
  - Should explain expected wait time
  - Example: "Processing... This may take 3-5 minutes."

#### Documentation References

- Form Trigger Node: `workflows/development/carousel-generator/workflow-8bhcEHkbbvnhdHBh-form-trigger.json:76`
- Execution Error: n8n Execution #1427
- Pattern Documented: `.claude/agents-evolution.md` (Pattern-009)

---

**Last Updated:** 2025-11-24
**Status:** ACTIVE - Integrated with project ruleset
**Maintained By:** Claude Code with SYNRG protocols
