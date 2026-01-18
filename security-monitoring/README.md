# Security Monitoring Pipeline

Automated security scanning and log aggregation system integrating GitHub Actions with n8n workflows.

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

## Files

```
security-monitoring/
├── README.md                              # This file
└── github-security-logs-workflow.json     # n8n workflow export

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
