# N8N Workflow Templating System - Deployment Guide

**Version:** 1.0.0
**Last Updated:** 2026-02-06

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Converting Existing Workflows](#converting-existing-workflows)
3. [Deploying to a Department](#deploying-to-a-department)
4. [Template Development](#template-development)
5. [Troubleshooting](#troubleshooting)
6. [API Reference](#api-reference)

---

## Quick Start

### Prerequisites

1. **Node.js 18+** installed
2. **N8N Cloud account** with API access
3. **N8N API Key** (Settings → API)
4. **Credentials created in n8n** for target department

### Installation

```bash
cd /Users/jelalconnor/CODING/N8N/Workflows/federation/n8n-workflow-templates

# Install dependencies
npm install

# Create .env file
cp .env.example .env

# Edit .env with your n8n credentials
# N8N_BASE_URL=https://your-instance.app.n8n.cloud
# N8N_API_KEY=your_api_key_here
```

### Validate Setup

```bash
# Test n8n connection
npm run test -- --grep "n8n client"

# Or compile TypeScript to check for errors
npm run build
```

---

## Converting Existing Workflows

### Step 1: Identify Workflow to Convert

List all active workflows:

```bash
curl -H "X-N8N-API-KEY: $N8N_API_KEY" \
  https://jayconnorexe.app.n8n.cloud/api/v1/workflows
```

Or use the MCP tool:

```javascript
mcp__n8n-mcp__n8n_list_workflows({ active: true, limit: 100 })
```

### Step 2: Convert Workflow

```bash
npm run convert-workflow -- \
  --workflow-id=IamjzfFxjHviJvJg \
  --category=core \
  --template-id=google-drive-repository
```

**Parameters:**
- `--workflow-id` - n8n workflow ID (required)
- `--category` - Template category: `core`, `hr`, `sales-marketing`, `operations`, `finance`, `legal` (required)
- `--template-id` - Custom template ID (optional, defaults to slugified workflow name)

### Step 3: Review Generated Template

```bash
cat workflows/core/google-drive-repository.json
cat workflows/core/google-drive-repository.meta.json
```

**Check for:**
- ✓ Credential IDs replaced with `{{VARIABLE}}`
- ✓ Webhook paths templatized
- ✓ PostgreSQL schemas replaced with `{{POSTGRES_SCHEMA}}`
- ✓ n8n webhook URLs replaced with `{{N8N_WEBHOOK_BASE}}`

### Example: Convert All Core Workflows

```bash
# Google Drive Repository
npm run convert-workflow -- \
  --workflow-id=IamjzfFxjHviJvJg \
  --category=core \
  --template-id=google-drive-repository

# Agent Context Access
npm run convert-workflow -- \
  --workflow-id=ouWMjcKzbj6nrYXz \
  --category=core \
  --template-id=agent-context-access

# File Download & Email
npm run convert-workflow -- \
  --workflow-id=z61gjAE9DtszE1u2 \
  --category=core \
  --template-id=file-download-email

# Send Gmail
npm run convert-workflow -- \
  --workflow-id=kBuTRrXTJF1EEBEs \
  --category=core \
  --template-id=send-gmail

# Voice Bot
npm run convert-workflow -- \
  --workflow-id=gjYSN6xNjLw8qsA1 \
  --category=core \
  --template-id=teams-voice-bot
```

---

## Deploying to a Department

### Step 1: Create Credentials Configuration

Create `config/{department}-credentials.json`:

```json
{
  "postgres": "NI3jbq1U8xPst3j3",
  "googleDrive": "ylMLH2SMUpGQpUUr",
  "gmail": "kHDxu9JVLxm6iyMo",
  "openai": "6BIzzQu5jAD5jKlH",
  "googleSheets": "fzaSSwZ4tI357WUU",
  "googleDocs": "iNIP35ChYNUUqOCh"
}
```

**How to get credential IDs:**

1. Go to n8n → Credentials
2. Click on credential → Copy ID from URL
3. Or use API:

```bash
curl -H "X-N8N-API-KEY: $N8N_API_KEY" \
  https://jayconnorexe.app.n8n.cloud/api/v1/credentials
```

### Step 2: Dry Run (Validation Only)

```bash
npm run dry-run -- \
  --department=hr \
  --name="Human Resources" \
  --credentials=./config/hr-credentials.json
```

**Expected Output:**

```
Federation Platform - Department Deployment
============================================================

Department: Human Resources (hr)
Mode: DRY RUN (validation only)

Templates to deploy: 7
  1. google-drive-repository
  2. agent-context-access
  3. file-download-email
  4. send-gmail
  5. vector-db-add
  6. vector-db-query
  7. manage-contacts

Running validation checks...

✓ Validation PASSED

All 7 templates are valid and ready for deployment.

✓ Done!
```

### Step 3: Deploy to N8N

```bash
npm run deploy-department -- \
  --department=hr \
  --name="Human Resources" \
  --credentials=./config/hr-credentials.json
```

**Expected Output:**

```
Deploying workflows to n8n...

[hr] Loading 7 workflow templates...
[hr] Resolving workflow dependencies...
[hr] Import order: google-drive-repository -> agent-context-access -> ...
[hr] Validating credentials...
[hr] Deploying: Google Drive Document Repository...
[hr] ✓ Deployed: Google Drive Document Repository (ID: abc123)
...

============================================================
Deployment COMPLETED
============================================================

Deployed: 7/7 workflows

Deployed Workflows:

1. Human Resources - Google Drive Document Repository
   ID: abc123
   Active: false
   Webhooks:
     - https://jayconnorexe.app.n8n.cloud/webhook/hr/drive-repository

...

Workflows deployed successfully.
To activate workflows, run:
  npm run activate-workflows -- abc123 def456 ...

✓ Done!
```

### Step 4: Activate Workflows

```bash
# Activate specific workflows
npm run activate-workflows -- abc123 def456

# Or activate all workflows for a department (via API)
curl -X PATCH \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"active": true}' \
  https://jayconnorexe.app.n8n.cloud/api/v1/workflows/abc123
```

---

## Template Development

### Creating a New Template from Scratch

1. **Create workflow JSON** in `workflows/{category}/{template-id}.json`:

```json
{
  "name": "{{DEPARTMENT_NAME}} - My New Workflow",
  "nodes": [
    {
      "id": "webhook-node",
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 2,
      "position": [240, 300],
      "parameters": {
        "path": "/{{DEPARTMENT_ID}}/my-workflow",
        "httpMethod": "POST"
      }
    },
    {
      "id": "postgres-node",
      "name": "PostgreSQL",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.4,
      "position": [460, 300],
      "parameters": {
        "query": "SELECT * FROM {{POSTGRES_SCHEMA}}.my_table"
      },
      "credentials": {
        "postgres": {
          "id": "{{POSTGRES_CREDENTIAL_ID}}",
          "name": "{{DEPARTMENT_NAME}} PostgreSQL"
        }
      }
    }
  ],
  "connections": {
    "Webhook": {
      "main": [
        [
          {
            "node": "PostgreSQL",
            "type": "main",
            "index": 0
          }
        ]
      ]
    }
  }
}
```

2. **Create metadata file** in `workflows/{category}/{template-id}.meta.json`:

```json
{
  "templateId": "my-new-workflow",
  "name": "My New Workflow",
  "category": "core",
  "requiredCredentials": [
    {
      "type": "postgres",
      "namePattern": "{DEPARTMENT}_database"
    }
  ],
  "requiredWebhooks": [
    {
      "path": "/my-workflow",
      "method": "POST"
    }
  ],
  "dependencies": [],
  "description": "Custom workflow for XYZ",
  "estimatedExecutionTime": "2-5 seconds"
}
```

3. **Test locally:**

```bash
npm run test-inject -- \
  --template=my-new-workflow \
  --department=hr
```

---

## Troubleshooting

### Error: "Unreplaced template variable"

**Problem:** Template contains `{{VARIABLE}}` that wasn't replaced.

**Solution:**
1. Check if variable is defined in `src/types.ts` → `TemplateVariables`
2. Add variable to credentials config
3. Verify variable name matches exactly (case-sensitive)

```bash
# Debug: Extract variables from template
npm run extract-vars -- --template=google-drive-repository
```

### Error: "Missing credentials in n8n"

**Problem:** Credential ID doesn't exist in n8n.

**Solution:**
1. List credentials in n8n:

```bash
curl -H "X-N8N-API-KEY: $N8N_API_KEY" \
  https://jayconnorexe.app.n8n.cloud/api/v1/credentials
```

2. Create missing credential in n8n UI
3. Update `config/{department}-credentials.json` with correct ID

### Error: "Circular dependency detected"

**Problem:** Workflows have circular dependencies.

**Solution:**
1. Check `.meta.json` files for `dependencies` field
2. Remove circular references
3. Execute Workflow nodes should reference workflows deployed BEFORE current workflow

### Error: "Webhook path contains unreplaced variables"

**Problem:** Webhook path still has `{{DEPARTMENT_ID}}`.

**Solution:**
1. Ensure `DEPARTMENT_ID` is in credentials config
2. Check template variable name matches exactly
3. Re-run dry run to verify

---

## API Reference

### WorkflowInjector

```typescript
import { WorkflowInjector } from './src/injector';

const injector = new WorkflowInjector();
const injected = await injector.injectParameters(workflow, variables);
```

### DependencyResolver

```typescript
import { DependencyResolver } from './src/dependency-resolver';

const resolver = new DependencyResolver();
const order = resolver.resolveDependencies(workflows);
```

### TemplateValidator

```typescript
import { TemplateValidator } from './src/template-validator';

const validator = new TemplateValidator();
const result = validator.validateInjection(workflow);
```

### N8nClient

```typescript
import { createN8nClientFromEnv } from './src/n8n-client';

const client = createN8nClientFromEnv();
const workflow = await client.createWorkflow(workflowJSON);
```

---

## Best Practices

### 1. Always Dry Run First

```bash
npm run dry-run -- --department=hr --name="HR" --credentials=./config/hr.json
```

### 2. Version Control Templates

Commit templates to git after conversion:

```bash
git add workflows/core/google-drive-repository.*
git commit -m "feat(templates): add Google Drive Repository template"
```

### 3. Test with Staging Environment

Create staging credentials and test deployment before production:

```bash
# Deploy to staging
N8N_BASE_URL=https://staging.app.n8n.cloud \
  npm run deploy-department -- \
  --department=hr-staging \
  --name="HR Staging" \
  --credentials=./config/hr-staging.json
```

### 4. Document Template Dependencies

Always list dependencies in `.meta.json`:

```json
{
  "dependencies": ["send-gmail"]
}
```

### 5. Use Latest TypeVersions

Check for latest before deployment:

```javascript
mcp__n8n-mcp__get_node({ nodeType: "n8n-nodes-base.postgres" })
```

---

## Support

For issues or questions:
1. Check [Troubleshooting](#troubleshooting) section
2. Review template validation output
3. Contact Federation Platform team

---

**Next Steps:**
- [ ] Convert all 32 active workflows
- [ ] Deploy to pilot department (HR)
- [ ] Validate webhook URLs work
- [ ] Activate workflows
- [ ] Monitor execution logs
