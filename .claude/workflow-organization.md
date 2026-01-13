# N8N Workflow Organization Structure

**Purpose:** Define the structure and organization for n8n workflows in this repository to maintain consistency and scalability.

---

## Directory Structure

```
Workflows/
├── .claude/                      # Claude Code configuration
│   ├── claude.md                # Main project instructions
│   ├── agents-evolution.md      # Pattern learning log
│   ├── workflow-organization.md # This file
│   ├── commands/                # Slash commands
│   │   ├── n8n-build.md
│   │   ├── n8n-validate.md
│   │   ├── n8n-debug.md
│   │   └── n8n-evolve.md
│   ├── hooks/                   # Git hooks
│   │   └── pre-commit-validate-workflows.md
│   └── prompts/                 # Prompting guidelines
│       └── workflow-building-guide.md
│
├── workflows/                   # Workflow JSON files
│   ├── production/             # Live, customer-facing workflows
│   │   ├── hr/
│   │   │   ├── resume-review.json
│   │   │   └── README.md
│   │   ├── marketing/
│   │   │   ├── carousel-generator.json
│   │   │   └── README.md
│   │   ├── operations/
│   │   └── sales/
│   │
│   ├── library/                # Reusable sub-workflows
│   │   ├── auth/
│   │   │   ├── oauth-retry.json
│   │   │   └── README.md
│   │   ├── data/
│   │   │   ├── json-transformer.json
│   │   │   └── csv-parser.json
│   │   └── notifications/
│   │       ├── slack-alert.json
│   │       └── email-template.json
│   │
│   ├── templates/              # Workflow templates
│   │   ├── data-enrichment/
│   │   │   ├── template.json
│   │   │   └── README.md
│   │   ├── webhook-processing/
│   │   └── api-integration/
│   │
│   └── development/            # WIP workflows
│       ├── experimental/
│       └── testing/
│
├── docs/                       # Documentation
│   ├── workflows/             # Workflow-specific docs
│   ├── guides/                # How-to guides
│   └── architecture/          # System architecture
│
├── tests/                     # Workflow tests
│   ├── fixtures/             # Test data
│   └── validation/           # Validation scripts
│
└── scripts/                   # Utility scripts
    ├── export-workflows.sh   # Export workflows from n8n
    ├── import-workflows.sh   # Import workflows to n8n
    └── validate-all.sh       # Validate all workflows
```

---

## Naming Conventions

### Workflow Naming

**Format:** `{stage}-{domain}-{function}`

**Stages:**
- `prod` - Production workflow (live, customer-facing)
- `dev` - Development workflow (testing, WIP)
- `lib` - Library workflow (reusable sub-workflow)
- `template` - Template workflow (starting point for new workflows)

**Domains:**
- `hr` - Human resources
- `marketing` - Marketing automation
- `sales` - Sales automation
- `operations` - Business operations
- `support` - Customer support
- `finance` - Finance and accounting
- `engineering` - Engineering/DevOps automation

**Functions:**
- Descriptive, hyphen-separated
- Max 30 characters
- Use action verbs

**Examples:**
- `prod-hr-resume-review` ✅
- `lib-auth-oauth-retry` ✅
- `template-data-enrichment` ✅
- `dev-carousel-generator` ✅
- `workflow1` ❌ (no stage, domain, or descriptive function)
- `production_workflow_for_resume_review` ❌ (wrong format)

### File Naming

**Workflow JSON files:**
- Match workflow name: `resume-review.json`
- Lowercase, hyphen-separated
- `.json` extension

**Documentation files:**
- `README.md` - Overview and usage
- `CHANGELOG.md` - Version history (optional)
- `SETUP.md` - Setup and configuration (if complex)

### Node Naming Within Workflows

**Format:** `{Action} {Subject}` (descriptive, not generic)

**Good Examples:**
- `Fetch User Data from API` ✅
- `Parse Resume Text` ✅
- `Calculate Risk Score` ✅
- `Send Alert to Slack` ✅

**Bad Examples:**
- `HTTP Request` ❌ (generic, not descriptive)
- `HTTP Request 1` ❌ (numbered generic name)
- `Code` ❌ (no context)
- `Set` ❌ (no context)

---

## Workflow Lifecycle

### 1. Development Phase

**Location:** `workflows/development/`

**Naming:** `dev-{domain}-{function}`

**Characteristics:**
- Work in progress
- May have incomplete error handling
- Testing and iteration
- Not connected to production systems

**Process:**
1. Create workflow in n8n
2. Export to `development/` directory
3. Iterate and test
4. Document in README

### 2. Testing Phase

**Location:** `workflows/development/testing/`

**Naming:** Keep `dev-` prefix

**Characteristics:**
- Feature complete
- Error handling in place
- Connected to staging/test systems
- Ready for validation

**Process:**
1. Move to `testing/` subdirectory
2. Add comprehensive tests
3. Validate with real data
4. Document edge cases

### 3. Production Phase

**Location:** `workflows/production/{domain}/`

**Naming:** Change to `prod-{domain}-{function}`

**Characteristics:**
- Fully tested and validated
- Complete error handling
- Monitoring in place
- Documentation complete
- Credentials configured

**Process:**
1. Final validation with `/n8n-validate`
2. Rename workflow (`dev-` → `prod-`)
3. Move to `production/{domain}/`
4. Deploy to production n8n instance
5. Enable monitoring
6. Document in evolution log if patterns emerged

### 4. Library Workflow Creation

**Location:** `workflows/library/{category}/`

**Naming:** `lib-{category}-{function}`

**Characteristics:**
- Reusable across multiple workflows
- Well-documented inputs/outputs
- Generic, not business-specific
- Thoroughly tested

**Process:**
1. Identify reusable pattern in existing workflows
2. Extract to standalone workflow
3. Parameterize for reusability
4. Document usage examples
5. Add to library with README

---

## Workflow Categories

### Production Workflows

**Purpose:** Live workflows serving actual business functions

**Structure:**
```
production/
├── hr/
│   ├── resume-review.json
│   ├── candidate-outreach.json
│   ├── interview-scheduling.json
│   └── README.md
├── marketing/
│   ├── carousel-generator.json
│   ├── social-scheduling.json
│   ├── email-campaigns.json
│   └── README.md
└── operations/
    ├── invoice-processing.json
    ├── expense-approval.json
    └── README.md
```

**Requirements:**
- Must have error handling
- Must have monitoring
- Must have documentation
- Must pass validation
- Must use naming convention

### Library Workflows

**Purpose:** Reusable sub-workflows called by other workflows

**Structure:**
```
library/
├── auth/
│   ├── oauth-retry.json          # OAuth with retry logic
│   ├── api-key-rotation.json     # Rotate API keys
│   └── README.md
├── data/
│   ├── json-transformer.json     # JSON transformations
│   ├── csv-parser.json           # CSV parsing
│   ├── data-validator.json       # Validate data structures
│   └── README.md
└── notifications/
    ├── slack-alert.json          # Send Slack notifications
    ├── email-template.json       # Email with template
    ├── sms-notification.json     # Send SMS
    └── README.md
```

**Requirements:**
- Clear input/output contract
- Comprehensive documentation
- Usage examples
- Error handling
- Idempotent (safe to call multiple times)

### Template Workflows

**Purpose:** Starting points for common workflow patterns

**Structure:**
```
templates/
├── webhook-processing/
│   ├── template.json
│   ├── README.md                # Usage instructions
│   └── example-customization.md # Customization guide
├── data-enrichment/
│   ├── template.json
│   └── README.md
└── api-integration/
    ├── template.json
    └── README.md
```

**Template Contents:**
- Placeholder nodes with TODO comments
- Sticky notes with instructions
- Standard error handling structure
- Common patterns implemented
- Customization points documented

---

## Documentation Standards

### Workflow README Template

Each workflow directory should have a README with:

```markdown
# {Workflow Name}

**Status:** Development | Testing | Production
**Domain:** {domain}
**Last Updated:** {date}
**Owner:** {team/person}

## Purpose

{1-2 sentence description of what this workflow does}

## Trigger

- **Type:** Webhook | Schedule | Manual | Other
- **Details:** {trigger configuration}

## Input Data Structure

```json
{
  "example": "input structure"
}
```

## Output Data Structure

```json
{
  "example": "output structure"
}
```

## Processing Steps

1. {Step 1 description}
2. {Step 2 description}
3. {Step 3 description}

## External Dependencies

- **API 1:** {purpose, endpoint}
- **Database:** {type, purpose}
- **Service:** {purpose}

## Required Credentials

- `credential-name-1` - {purpose and setup instructions}
- `credential-name-2` - {purpose and setup instructions}

## Error Handling

- **Scenario 1:** {error type} → {how it's handled}
- **Scenario 2:** {error type} → {how it's handled}

## Performance

- **Average Execution Time:** {duration}
- **Expected Volume:** {executions per timeframe}
- **Rate Limits:** {any rate limit considerations}

## Testing

**Test Data:**
```json
{
  "test": "data example"
}
```

**Expected Result:**
```json
{
  "expected": "result example"
}
```

**How to Test:**
1. {Step 1}
2. {Step 2}

## Monitoring

- **Success Metrics:** {what to track}
- **Error Alerts:** {how errors are reported}
- **Dashboard:** {link to monitoring dashboard if exists}

## Known Issues

- {Issue 1 and workaround}
- {Issue 2 and workaround}

## Version History

- **v1.0.0** (2025-11-22) - Initial production release
- **v0.2.0** (2025-11-20) - Added error handling
- **v0.1.0** (2025-11-18) - Initial development version

## Related Workflows

- {Related workflow 1} - {relationship}
- {Related workflow 2} - {relationship}
```

---

## Workflow Metadata

### JSON Metadata Fields

Each workflow JSON should include metadata:

```json
{
  "name": "prod-hr-resume-review",
  "nodes": [...],
  "connections": {...},
  "settings": {
    "executionOrder": "v1"
  },
  "tags": [
    {"id": "production", "name": "Production"},
    {"id": "hr", "name": "HR"},
    {"id": "ai-enabled", "name": "AI Enabled"}
  ],
  "meta": {
    "version": "1.0.0",
    "description": "Process candidate resumes and generate review reports",
    "owner": "hr-team",
    "lastModified": "2025-11-22",
    "documentation": "workflows/production/hr/README.md"
  }
}
```

### Tagging Strategy

**Standard Tags:**
- **Stage:** `production`, `development`, `testing`
- **Domain:** `hr`, `marketing`, `sales`, `operations`, etc.
- **Capabilities:** `ai-enabled`, `webhook-triggered`, `scheduled`
- **Complexity:** `simple`, `moderate`, `complex`
- **Priority:** `critical`, `high`, `medium`, `low`

---

## Version Control Strategy

### Branching Strategy

**Main branch:**
- Only production-ready workflows
- All workflows pass validation
- Documentation complete

**Development branch:**
- Work in progress
- Experimental workflows
- Testing iterations

**Feature branches:**
- `feature/carousel-generator`
- `fix/resume-review-error-handling`
- `refactor/library-auth-workflows`

### Commit Message Format

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:**
- `feat` - New workflow or feature
- `fix` - Bug fix in workflow
- `refactor` - Workflow restructuring
- `docs` - Documentation changes
- `test` - Test additions
- `chore` - Maintenance tasks

**Examples:**
```
feat(hr): add resume review workflow with AI scoring

- Webhook trigger for incoming resumes
- OpenAI integration for scoring
- PostgreSQL storage
- Slack notifications on completion

Closes #123
```

```
fix(marketing): add retry logic to carousel image generation

Images were failing due to rate limits.
Added exponential backoff retry (3 attempts).

Execution time increased by 2s average but success rate
improved from 85% to 99.5%.
```

---

## Workflow Dependencies

### Managing Sub-Workflow Dependencies

**Execute Workflow Node Configuration:**
```json
{
  "workflowId": "lib-auth-oauth-retry",
  "mode": "once",
  "input": {
    "api_endpoint": "...",
    "retry_count": 3
  }
}
```

**Dependency Documentation:**

In main workflow README:
```markdown
## Dependencies

This workflow calls these sub-workflows:

- **lib-auth-oauth-retry** (v1.2.0)
  - Purpose: Handle OAuth authentication with retry
  - Required version: >= 1.2.0
  - Breaking changes: None
```

### Versioning Sub-Workflows

**Semantic Versioning:**
- MAJOR: Breaking changes to input/output contract
- MINOR: New features, backward compatible
- PATCH: Bug fixes, no interface changes

**Version in Workflow Name:**
- Primary: Use tags in n8n
- Fallback: Include version in description
- Documentation: Track in README

---

## Migration and Deployment

### Exporting Workflows

**Script:** `scripts/export-workflows.sh`

```bash
#!/bin/bash
# Export all workflows from n8n to JSON files

# Use n8n API to list all workflows
# For each workflow:
#   - Export to JSON
#   - Save to appropriate directory based on tags
#   - Update README if needed
```

### Importing Workflows

**Script:** `scripts/import-workflows.sh`

```bash
#!/bin/bash
# Import workflow JSON files to n8n instance

# For each JSON file in workflows/:
#   - Validate JSON structure
#   - Check required credentials exist
#   - Import to n8n via API
#   - Apply tags
#   - Set active status (prod only)
```

### Environment Promotion

**Dev → Staging → Production**

```bash
# 1. Test in dev
./scripts/import-workflows.sh --env=dev --file=dev-hr-resume-review.json

# 2. Promote to staging
./scripts/promote-workflow.sh dev-hr-resume-review staging

# 3. Validate in staging
./scripts/validate-workflow.sh staging prod-hr-resume-review

# 4. Promote to production
./scripts/promote-workflow.sh prod-hr-resume-review production
```

---

## Maintenance

### Regular Maintenance Tasks

**Weekly:**
- Review failed executions
- Check error rates
- Update documentation if workflows changed
- Validate all production workflows

**Monthly:**
- Review and refactor complex workflows
- Extract reusable patterns to library
- Update agents-evolution.md with patterns
- Archive deprecated workflows

**Quarterly:**
- Performance audit of all workflows
- Security review (credential usage, webhook exposure)
- Update dependencies (community nodes)
- Consolidate similar workflows

### Deprecation Process

**When deprecating a workflow:**

1. **Mark as deprecated:**
   - Add `deprecated` tag
   - Update README with deprecation notice
   - Add end-of-life date

2. **Notify users:**
   - Document migration path
   - Provide replacement workflow
   - Set sunset timeline (30-90 days)

3. **Monitor usage:**
   - Track execution count
   - Contact remaining users
   - Ensure migration complete

4. **Archive:**
   - Move to `workflows/archived/`
   - Disable in n8n
   - Keep for historical reference

---

## Best Practices Summary

### Do:
- ✅ Use clear, descriptive naming conventions
- ✅ Document all workflows with README files
- ✅ Validate workflows before production
- ✅ Version control all workflow JSON
- ✅ Extract reusable patterns to library
- ✅ Include comprehensive error handling
- ✅ Tag workflows appropriately
- ✅ Test with realistic data

### Don't:
- ❌ Use generic names ("Workflow 1", "HTTP Request")
- ❌ Skip documentation
- ❌ Hardcode credentials
- ❌ Deploy untested workflows
- ❌ Duplicate logic across workflows
- ❌ Ignore error handling
- ❌ Mix development and production in same directory

---

**Version:** 1.0.0
**Last Updated:** 2025-11-22
**Maintained By:** Development Team
