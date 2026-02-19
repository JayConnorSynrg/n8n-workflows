# N8N Workflow Inventory for Federation Platform

**Version:** 1.0.0
**Source:** n8n Cloud (jayconnorexe.app.n8n.cloud)
**Date:** 2026-02-06

---

## Summary

- **Total Workflows:** 32 active
- **Core (Universal):** 10 workflows
- **HR:** 3 workflows
- **Sales/Marketing:** 4 workflows
- **Operations:** 3 workflows
- **Other:** 12 workflows

---

## Core Workflows (Universal - All Departments)

| Template ID | Workflow Name | n8n ID | Priority | Status |
|-------------|---------------|--------|----------|--------|
| `google-drive-repository` | Google Drive Document Repository | IamjzfFxjHviJvJg | HIGH | Ready |
| `agent-context-access` | Agent Context Access - Universal Query | ouWMjcKzbj6nrYXz | HIGH | Ready |
| `file-download-email` | File Download & Email Subworkflow | z61gjAE9DtszE1u2 | HIGH | Ready |
| `send-gmail` | Voice Tool: Send Gmail | kBuTRrXTJF1EEBEs | HIGH | Ready |
| `teams-voice-bot` | Teams Voice Bot - Recall.ai + OpenAI TTS | gjYSN6xNjLw8qsA1 | HIGH | Ready |
| `vector-db-add` | Voice Tool: Add to Vector DB | jKMw735r3nAN6O7u | MEDIUM | Ready |
| `vector-db-query` | Voice Tool: Query Vector DB | z02K1a54akYXMkyj | MEDIUM | Ready |
| `manage-contacts` | Voice Tool: Manage Contacts | ng5O0VNKosn5x728 | MEDIUM | Ready |
| `callback-noop` | Callback No-Op (LiveKit) | Y6CuLuSu87qKQzK1 | LOW | Ready |
| `voice-session-summary` | Voice Session Summary Generator | WEfjWyowdTgoVlvM | LOW | Ready |

**Dependencies:**
- `teams-voice-bot` depends on `send-gmail` (Execute Workflow node)

---

## HR Workflows

| Template ID | Workflow Name | n8n ID | Priority | Status |
|-------------|---------------|--------|----------|--------|
| `paycor-resume-analysis` | PAYCOR - Resume Analysis (Complete) | cDyEyBnfQlIYc7K4 | HIGH | Ready |
| `job-descriptions` | Job Descriptions by Job ID - SubWorkflow | STBpKtgEEJy4ltlu | MEDIUM | Ready |
| `paycor-resume-processor` | PAYCOR - 2-Node Optimized Resume Processor | jElXD1AvCWzVNfvP | LOW | Archived |

---

## Sales/Marketing Workflows

| Template ID | Workflow Name | n8n ID | Priority | Status |
|-------------|---------------|--------|----------|--------|
| `carousel-generator` | AI Carousel Generator - 5 Slides x 3 Variations | 8bhcEHkbbvnhdHBh | HIGH | Ready |
| `lead-scraper` | LEAD INFO SCRAPER - Complex (Jamaal Hook) | jGFXXiUhH9QbDktp | HIGH | Ready |
| `website-chatbot` | Branded AI-Powered Website Chatbot | 2Ryo177xsOL2Mk6T | MEDIUM | Ready |
| `custom-research-agent` | Custom RESEARCH AGENT (JAY CONNOR) | UTlhpU9Til0LBPVe | LOW | Ready |

---

## Operations Workflows

| Template ID | Workflow Name | n8n ID | Priority | Status |
|-------------|---------------|--------|----------|--------|
| `security-report-generator` | Enterprise Security Report Generator | CZYHSSuGWRzn0P17 | HIGH | Ready |
| `github-security-logs` | GitHub Security Logs to Google Drive | wEBNxJkHuOUgO2PO | MEDIUM | Ready |
| `invoice-generator` | SYNRG Invoice Generator | Ge33EW4K3WVHT4oG | MEDIUM | Ready |

---

## Other Workflows (Categorization Pending)

| Workflow Name | n8n ID | Category | Priority |
|---------------|--------|----------|----------|
| Run Migration SQL | 3giADfjgVzvseehN | Operations | LOW |
| CUSTOM EMAIL AGENT | 7axDZTdOfFv62CVS | Core | MEDIUM |
| AI ROI DATA INGEST V2 | 7jMpgtZmM0KWcwmj | Operations | LOW |
| TTS Agent Sub-Workflow | DdwpUSXz7GCZuhlC | Core | LOW |
| FlowForge Status Reporter | FDWX4cg2ih4YfMCK | Operations | LOW |
| Recall.ai Bot Event Handler | ZtHr8tzwDhwEr2o0 | Core | MEDIUM |
| CALENDLY SCHEDULED EMAIL/TASK | cZaKnpE5hzrqYOAD | Marketing | LOW |
| Teams Voice Bot - Launcher v4.2 | kUcUSyPgz4Z9mYBt | Core | MEDIUM |
| Email Agent (Nate Herk) | oP7kgQCy5fuVeCmF | Deprecated | LOW |
| Custom Calendar Agent | q8GEBvvhOGakkvr1 | Core | LOW |
| Calendar Agent (Nate Herk) | tZnB4b34Zn7Y0sWX | Deprecated | LOW |
| DEVELOPER AGENT + MACHINE | ZimW7HztadhFZTyY | Operations | LOW |

---

## Conversion Priority

### Phase 1: Core Workflows (Required for All Departments)

1. ✅ Google Drive Document Repository
2. ✅ Agent Context Access
3. ✅ File Download & Email Subworkflow
4. ✅ Send Gmail
5. ✅ Teams Voice Bot
6. ✅ Vector DB Add
7. ✅ Vector DB Query
8. ✅ Manage Contacts

**Status:** Ready for conversion (8/8)

### Phase 2: Department-Specific (HR Pilot)

1. ⏳ PAYCOR Resume Analysis
2. ⏳ Job Descriptions
3. ⏳ Carousel Generator (if HR needs marketing)

**Status:** Pending conversion (0/3)

### Phase 3: Sales/Marketing

1. ⏳ Carousel Generator
2. ⏳ Lead Scraper
3. ⏳ Website Chatbot
4. ⏳ Research Agent

**Status:** Pending conversion (0/4)

### Phase 4: Operations

1. ⏳ Security Report Generator
2. ⏳ GitHub Security Logs
3. ⏳ Invoice Generator

**Status:** Pending conversion (0/3)

---

## Workflow Dependencies Map

```
teams-voice-bot
  └─> send-gmail (Execute Workflow)

file-download-email
  (standalone, called by other workflows)

agent-context-access
  (standalone, universal query interface)

google-drive-repository
  (standalone, data source for voice tools)

vector-db-add
  (standalone, adds to vector store)

vector-db-query
  (standalone, queries vector store)

manage-contacts
  (standalone, CRUD contacts)
```

---

## Credential Requirements by Category

### Core Workflows

| Credential Type | Purpose | Variable |
|----------------|---------|----------|
| PostgreSQL | Database access | `{{POSTGRES_CREDENTIAL_ID}}` |
| Google Drive OAuth | Drive repository | `{{GOOGLE_DRIVE_CREDENTIAL_ID}}` |
| Gmail OAuth | Email sending | `{{GMAIL_CREDENTIAL_ID}}` |
| OpenAI API | AI generation | `{{OPENAI_CREDENTIAL_ID}}` |

### HR Workflows

| Credential Type | Purpose | Variable |
|----------------|---------|----------|
| All Core | Inherited | - |
| Paycor API | Resume data | `{{PAYCOR_CREDENTIAL_ID}}` |

### Sales/Marketing Workflows

| Credential Type | Purpose | Variable |
|----------------|---------|----------|
| All Core | Inherited | - |
| LinkedIn API | Lead scraping | `{{LINKEDIN_CREDENTIAL_ID}}` |
| Google Sheets OAuth | Data export | `{{GOOGLE_SHEETS_CREDENTIAL_ID}}` |

### Operations Workflows

| Credential Type | Purpose | Variable |
|----------------|---------|----------|
| All Core | Inherited | - |
| GitHub OAuth | Security logs | `{{GITHUB_CREDENTIAL_ID}}` |

---

## Next Actions

### Immediate (Phase 1)

- [ ] Convert 8 core workflows using `npm run convert-workflow`
- [ ] Test injection with HR credentials
- [ ] Dry run deployment
- [ ] Deploy to HR pilot department

### Short-term (Phase 2)

- [ ] Convert HR-specific workflows
- [ ] Deploy to HR production
- [ ] Validate webhook URLs
- [ ] Monitor execution logs

### Medium-term (Phase 3-4)

- [ ] Convert Sales/Marketing workflows
- [ ] Convert Operations workflows
- [ ] Deploy to additional departments
- [ ] Create monitoring dashboard

---

## Template Conversion Commands

### Core Workflows

```bash
# Google Drive Repository
npm run convert-workflow -- --workflow-id=IamjzfFxjHviJvJg --category=core --template-id=google-drive-repository

# Agent Context Access
npm run convert-workflow -- --workflow-id=ouWMjcKzbj6nrYXz --category=core --template-id=agent-context-access

# File Download & Email
npm run convert-workflow -- --workflow-id=z61gjAE9DtszE1u2 --category=core --template-id=file-download-email

# Send Gmail
npm run convert-workflow -- --workflow-id=kBuTRrXTJF1EEBEs --category=core --template-id=send-gmail

# Teams Voice Bot
npm run convert-workflow -- --workflow-id=gjYSN6xNjLw8qsA1 --category=core --template-id=teams-voice-bot

# Vector DB Add
npm run convert-workflow -- --workflow-id=jKMw735r3nAN6O7u --category=core --template-id=vector-db-add

# Vector DB Query
npm run convert-workflow -- --workflow-id=z02K1a54akYXMkyj --category=core --template-id=vector-db-query

# Manage Contacts
npm run convert-workflow -- --workflow-id=ng5O0VNKosn5x728 --category=core --template-id=manage-contacts
```

### HR Workflows

```bash
# PAYCOR Resume Analysis
npm run convert-workflow -- --workflow-id=cDyEyBnfQlIYc7K4 --category=hr --template-id=paycor-resume-analysis

# Job Descriptions
npm run convert-workflow -- --workflow-id=STBpKtgEEJy4ltlu --category=hr --template-id=job-descriptions
```

### Sales/Marketing Workflows

```bash
# Carousel Generator
npm run convert-workflow -- --workflow-id=8bhcEHkbbvnhdHBh --category=sales-marketing --template-id=carousel-generator

# Lead Scraper
npm run convert-workflow -- --workflow-id=jGFXXiUhH9QbDktp --category=sales-marketing --template-id=lead-scraper

# Website Chatbot
npm run convert-workflow -- --workflow-id=2Ryo177xsOL2Mk6T --category=sales-marketing --template-id=website-chatbot
```

### Operations Workflows

```bash
# Security Report Generator
npm run convert-workflow -- --workflow-id=CZYHSSuGWRzn0P17 --category=operations --template-id=security-report-generator

# GitHub Security Logs
npm run convert-workflow -- --workflow-id=wEBNxJkHuOUgO2PO --category=operations --template-id=github-security-logs

# Invoice Generator
npm run convert-workflow -- --workflow-id=Ge33EW4K3WVHT4oG --category=operations --template-id=invoice-generator
```

---

## Deployment Test Plan

### Test 1: Dry Run (Validation)

```bash
npm run dry-run -- \
  --department=hr-test \
  --name="HR Test" \
  --credentials=./config/hr-credentials.json
```

**Expected:** All validations pass, no unreplaced variables.

### Test 2: Deploy to Staging

```bash
npm run deploy-department -- \
  --department=hr-staging \
  --name="HR Staging" \
  --credentials=./config/hr-staging-credentials.json
```

**Expected:** 8 workflows created in n8n, webhook URLs generated.

### Test 3: Test Webhook

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"test": true}' \
  https://jayconnorexe.app.n8n.cloud/webhook/hr-staging/drive-repository
```

**Expected:** 200 OK, workflow executes successfully.

### Test 4: Deploy to Production

```bash
npm run deploy-department -- \
  --department=hr \
  --name="Human Resources" \
  --credentials=./config/hr-credentials.json
```

**Expected:** All workflows deployed and activated.

---

## Success Criteria

Template system is production-ready when:

- [x] TypeScript compiles with no errors
- [x] All type definitions complete
- [x] Injector handles all variable types
- [x] Dependency resolver works (topological sort)
- [x] Validator detects unreplaced variables
- [x] N8N client successfully deploys workflows
- [ ] 8 core workflows converted to templates
- [ ] Dry run passes for HR department
- [ ] Deploy to HR staging successful
- [ ] Webhook URLs accessible
- [ ] Workflows execute without errors
