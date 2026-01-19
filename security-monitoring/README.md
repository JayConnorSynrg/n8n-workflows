# Security Monitoring Pipeline

Automated security scanning and log aggregation system integrating GitHub Actions with n8n workflows.

## Enterprise System Components

| Component | ID | Purpose |
|-----------|-----|---------|
| GitHub Security Logs | `wEBNxJkHuOUgO2PO` | Basic markdown reports to Google Drive |
| **Enterprise Security Report Generator** | `CZYHSSuGWRzn0P17` | Multi-source aggregation (GitHub + Railway + Recall.ai) |

### Enterprise Security Report Generator

**Webhook:** `/webhook/enterprise-security-report`

**Data Sources:**
- GitHub Actions security scan results
- Railway deployment logs (GraphQL API)
- Recall.ai bot session status (REST API)

**Features:**
- Risk scoring algorithm (Critical=25pts, High=10pts, Medium=3pts)
- Automated recommendations generation
- Severity-based alerting (CRITICAL/HIGH triggers alerts)
- Google Drive upload with timestamped filenames

**Required Credentials:**
- `railwayApi` - Railway API Bearer token
- `recallAiApi` - Recall.ai API Token
- Google Drive OAuth2

### PDF Generation (Future Enhancement)

To enable PDF reports instead of markdown:
1. Create APITemplate.io account at https://apitemplate.io
2. Create PDF template using the structure in `pdf-template-structure.md`
3. Add APITemplate.io API key credential in n8n
4. Replace "Convert to Binary" node with APITemplate.io PDF generation node

**PDF Template Fields:**
- `{{company_name}}`, `{{timestamp}}`, `{{risk_score}}`
- `{{critical_count}}`, `{{high_count}}`, `{{compliance_status}}`
- `{{secrets_status}}`, `{{deps_status}}`, `{{sast_status}}`, `{{infra_status}}`
- `{{railway_error_rate}}`, `{{recall_sessions}}`, `{{recall_failures}}`
- `{{recommendations}}` (array)

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     GitHub Actions Security Pipeline                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐│
│  │   Secret    │  │ Dependency  │  │    SAST     │  │Infrastructure││
│  │  Scanning   │  │  Scanning   │  │  Scanning   │  │  Scanning   ││
│  │ TruffleHog  │  │ npm audit   │  │  Semgrep    │  │   Trivy     ││
│  │  Gitleaks   │  │  CodeQL     │  │             │  │             ││
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘│
│         │                │                │                │        │
│         └────────────────┼────────────────┼────────────────┘        │
│                          │                │                         │
│                    ┌─────┴────────────────┴─────┐                   │
│                    │   Aggregate & Report Job    │                   │
│                    └─────────────┬───────────────┘                   │
│                                  │                                   │
└──────────────────────────────────┼───────────────────────────────────┘
                                   │
                     POST to n8n webhook
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 n8n: Security Logs to Google Drive                   │
│                      Workflow ID: wEBNxJkHuOUgO2PO                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────┐    ┌─────────────┐    ┌───────────────┐              │
│  │ Webhook  │───▶│ Route by    │───▶│ Format Report │              │
│  │ Trigger  │    │ Scan Type   │    │  (Markdown)   │              │
│  └──────────┘    └─────────────┘    └───────┬───────┘              │
│                                             │                       │
│                                             ▼                       │
│                                   ┌─────────────────┐              │
│                                   │ Upload to       │              │
│                                   │ Google Drive    │              │
│                                   └────────┬────────┘              │
│                                            │                        │
│                                            ▼                        │
│                                   ┌─────────────────┐              │
│                                   │ Check Critical  │              │
│                                   │ Severity        │              │
│                                   └────────┬────────┘              │
│                                            │                        │
│                          ┌─────────────────┴─────────────────┐     │
│                          │                                   │     │
│                          ▼                                   ▼     │
│                 ┌─────────────────┐              ┌──────────────┐ │
│                 │ Prepare Alert   │──────────────▶│ Respond to   │ │
│                 │ (CRITICAL/HIGH) │              │ Webhook      │ │
│                 └─────────────────┘              └──────────────┘ │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

## Components

### GitHub Actions Workflow

**File:** `.github/workflows/security-scanning.yml`

**Triggers:**
- Push to `main` or `develop` branches
- Pull requests to `main`
- Weekly scheduled scan (Mondays at 2am UTC)
- Manual dispatch with scan type selection

**Scan Types:**
| Scan | Tools | Severity on Failure |
|------|-------|---------------------|
| Secrets | TruffleHog, Gitleaks | CRITICAL |
| Dependencies | npm audit, CodeQL | HIGH |
| SAST | Semgrep (OWASP Top 10) | MEDIUM |
| Infrastructure | Trivy, sensitive file check | HIGH/MEDIUM |

### n8n Workflow

**Workflow ID:** `wEBNxJkHuOUgO2PO`
**Webhook Path:** `/webhook/security-logs`

**Nodes:**
1. **Webhook** - Receives POST from GitHub Actions
2. **Route by Scan Type** - Routes based on `scan_type` field
3. **Format Security Report** - Generates markdown report
4. **Upload to Google Drive** - Stores report as `.md` file
5. **Check Critical Severity** - Routes CRITICAL/HIGH to alerts
6. **Prepare Alert Data** - Formats notification payload
7. **Respond to Webhook** - Returns confirmation

## Setup

### 1. GitHub Repository Secret

Add the n8n webhook URL as a repository secret:

```bash
gh secret set N8N_SECURITY_WEBHOOK_URL --body "https://your-n8n-instance.app.n8n.cloud/webhook/security-logs"
```

### 2. n8n Workflow Configuration

1. **Google Drive Credentials**
   - In n8n, add Google Drive OAuth2 credentials
   - Assign to "Upload to Google Drive" node

2. **Target Folder (Optional)**
   - Edit "Upload to Google Drive" node
   - Change `folderId` to target specific folder:
   ```json
   {
     "__rl": true,
     "value": "YOUR_FOLDER_ID",
     "mode": "id"
   }
   ```

3. **Activate Workflow**
   - Toggle workflow to active in n8n UI

### 3. Optional: Notification Integration

Connect the "Prepare Alert Data" output to a notification node:
- Slack
- Email
- SMS
- PagerDuty

## Payload Format

### GitHub Actions → n8n

```json
{
  "scan_type": "secrets",
  "repository": "owner/repo",
  "branch": "main",
  "commit": "abc123",
  "timestamp": "2026-01-18T04:50:00Z",
  "severity": "CRITICAL",
  "run_url": "https://github.com/owner/repo/actions/runs/12345",
  "trufflehog_status": "failure",
  "gitleaks_status": "success"
}
```

### n8n Response

```json
{
  "success": true,
  "message": "Security scan report processed",
  "filename": "security-scan-secrets-2026-01-18.md",
  "severity": "CRITICAL",
  "findings": 0
}
```

## Testing

### Manual Trigger

```bash
# Trigger specific scan type
gh workflow run security-scanning.yml -f scan_type=secrets

# Trigger all scans
gh workflow run security-scanning.yml -f scan_type=all
```

### Test n8n Webhook

```bash
curl -X POST https://your-n8n-instance.app.n8n.cloud/webhook/security-logs \
  -H "Content-Type: application/json" \
  -d '{
    "scan_type": "secrets",
    "severity": "HIGH",
    "repository": "test/repo",
    "branch": "main",
    "timestamp": "2026-01-18T04:50:00Z",
    "findings": [{
      "title": "Test Secret",
      "severity": "HIGH",
      "description": "Test finding",
      "location": "test.js:42",
      "recommendation": "Remove secret"
    }]
  }'
```

## Testing

### Run All Tests

```bash
./security-monitoring/tests/run-all-tests.sh
```

### Test Suites

**Bash E2E Tests** (`tests/test-security-pipeline.sh`):
- GitHub Actions workflow validation
- n8n workflow configuration
- Webhook connectivity (when URLs configured)
- Voice agent security logging
- External API connectivity (Railway, Recall.ai)
- Documentation completeness
- Security configuration (.gitignore)

**Python Tests** (`tests/test_enterprise_security.py`):
- Risk scoring algorithm (8 tests)
- Data normalization from GitHub/Railway/Recall.ai (3 tests)
- Report generation and recommendations (3 tests)
- Webhook payload validation (3 tests)
- End-to-end integration (2 tests)

### Environment Variables for Full Testing

```bash
export N8N_SECURITY_WEBHOOK_URL="https://your-n8n.app.n8n.cloud/webhook/security-logs"
export N8N_ENTERPRISE_SECURITY_WEBHOOK_URL="https://your-n8n.app.n8n.cloud/webhook/enterprise-security-report"
export RAILWAY_API_TOKEN="your-railway-token"
export RECALL_API_TOKEN="your-recall-token"
```

## Files

```
security-monitoring/
├── README.md                              # This file
├── github-security-logs-workflow.json     # n8n workflow export
└── tests/
    ├── run-all-tests.sh                   # Complete test runner
    ├── test-security-pipeline.sh          # Bash E2E tests
    └── test_enterprise_security.py        # Python unit/integration tests

.github/workflows/
└── security-scanning.yml                  # GitHub Actions workflow
```

## Monitoring

### GitHub Actions

- View runs: `gh run list --workflow=security-scanning.yml`
- View latest: `gh run view --workflow=security-scanning.yml`

### n8n

- Check executions in n8n UI for workflow `wEBNxJkHuOUgO2PO`
- Review Google Drive for security reports

### Alerts

When CRITICAL or HIGH severity issues are detected:
1. Alert data is prepared in "Prepare Alert Data" node
2. Connect to your preferred notification system
3. Manual notification currently (extend workflow for automated alerts)

## Security Considerations

1. **Webhook Secret** - Consider adding webhook authentication
2. **Credential Storage** - Use n8n's credential manager, not hardcoded keys
3. **Google Drive Access** - Use service account with minimal permissions
4. **Log Retention** - Configure Google Drive retention policies

## Troubleshooting

### Webhook Not Receiving Data

1. Verify workflow is active in n8n
2. Check `N8N_SECURITY_WEBHOOK_URL` secret is set correctly
3. Verify n8n instance is accessible from GitHub Actions

### Google Drive Upload Fails

1. Check Google Drive credentials are valid
2. Verify folder ID exists and is accessible
3. Check n8n execution logs for specific error

### Missing Scan Results

1. Check GitHub Actions run logs
2. Verify scan tools are running (check for `continue-on-error: true`)
3. Review artifact uploads for raw reports
