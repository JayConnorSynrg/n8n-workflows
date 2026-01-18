# Pre-Deployment Security Gate Checklist

**Purpose:** Mandatory security validation before ANY deployment to production
**Authority:** Security Officer + Change Control Board
**Enforcement:** CI/CD pipeline gate (automated + manual approval)
**Status:** ACTIVE

---

## Overview

This checklist MUST be completed and approved before deploying code, configurations, workflows, or infrastructure changes to production. All items must pass (✅) for deployment to proceed.

**Pass Criteria:** 5/5 sections passed with documented evidence
**Failure Action:** Deployment BLOCKED until all items resolved
**Documentation Location:** `/compliance/evidence/pre-deployment/YYYY-MM-DD-<deployment-id>/`

---

## Deployment Information

**Deployment ID:** _____________________
**Deployment Date/Time:** _____________________
**Deployed By:** _____________________
**Change Request ID:** _____________________
**Description:**
_____________________________________________________________________________________
_____________________________________________________________________________________

**Deployment Type:**
- [ ] Code deployment (application/service)
- [ ] n8n workflow deployment
- [ ] Infrastructure change (server, network, database)
- [ ] Configuration change (secrets, environment variables)
- [ ] Security patch
- [ ] Emergency hotfix (expedited process - requires VP approval)

---

## Section 1: Secrets Scanning

**Status:** ⬜ PASS | ⬜ FAIL | ⬜ NOT APPLICABLE

**Requirement:** No hardcoded secrets, API keys, passwords, or tokens in code/configs.

### Automated Scanning

**Scan Results:**
- [ ] truffleHog scan completed (exit code 0 = no secrets found)
- [ ] git-secrets scan completed
- [ ] GitHub Advanced Security scan passed (if enabled)
- [ ] Custom secrets regex scan passed

**Scan Commands:**
```bash
# truffleHog scan
truffleHog git file:///path/to/repo --since-commit $(git describe --tags --abbrev=0)

# git-secrets scan
git secrets --scan

# Custom regex scan (API keys, passwords)
grep -rE "(api[_-]?key|password|secret|token)\s*=\s*['\"][^'\"]+['\"]" . --exclude-dir={node_modules,.git}
```

**Scan Output Location:** `/compliance/evidence/pre-deployment/<deployment-id>/secrets-scan.log`

### Manual Review

**Code Review Checklist:**
- [ ] No `.env` files in commit
- [ ] No `credentials.json` or similar files
- [ ] No hardcoded database connection strings
- [ ] No hardcoded URLs with embedded credentials (e.g., `https://user:pass@api.example.com`)
- [ ] All secrets referenced from secrets manager (e.g., `process.env.API_KEY`)

**Reviewed By:** _____________________ Date: _________

### Evidence Required

1. Secrets scan log (all tools)
2. Code review notes
3. Confirmation that all secrets use secrets manager

**Failure Criteria:**
- Any secret detected in code/config
- `.env` file committed
- Hardcoded credentials in connection strings

**If FAIL:**
- [ ] Secrets removed from code
- [ ] Secrets migrated to secrets manager
- [ ] Git history cleaned (if secrets previously committed)
- [ ] Re-scan completed (PASS required)

---

## Section 2: Test Coverage & Results

**Status:** ⬜ PASS | ⬜ FAIL | ⬜ NOT APPLICABLE

**Requirement:** All automated tests passing with acceptable coverage.

### Unit Tests

**Test Results:**
- [ ] All unit tests passing (0 failures)
- [ ] Code coverage ≥70% (or project-defined threshold)
- [ ] No skipped/ignored critical tests

**Test Command:** _____________________
**Test Output Location:** `/compliance/evidence/pre-deployment/<deployment-id>/unit-tests.log`

**Coverage Report:**
- Overall Coverage: _____%
- Critical Modules Coverage: _____%
- Coverage Report Location: _____________________

### Integration Tests

**Test Results:**
- [ ] All integration tests passing (0 failures)
- [ ] API endpoint tests passing
- [ ] Database integration tests passing
- [ ] Third-party service integration tests passing

**Test Command:** _____________________
**Test Output Location:** `/compliance/evidence/pre-deployment/<deployment-id>/integration-tests.log`

### End-to-End Tests (if applicable)

**Test Results:**
- [ ] All E2E tests passing (0 failures)
- [ ] User flows tested (authentication, data submission, etc.)
- [ ] Cross-browser/device testing completed (if UI change)

**Test Command:** _____________________
**Test Output Location:** `/compliance/evidence/pre-deployment/<deployment-id>/e2e-tests.log`

### n8n Workflow Tests (if applicable)

**Test Results:**
- [ ] Workflow validation passed (`mcp__n8n-mcp__validate_workflow`)
- [ ] Test execution successful (all nodes executed without errors)
- [ ] Test data verified (correct output from workflow)

**Workflow ID:** _____________________
**Test Execution ID:** _____________________
**Test Output Location:** `/compliance/evidence/pre-deployment/<deployment-id>/workflow-test.json`

### Evidence Required

1. Test execution logs (unit, integration, E2E)
2. Coverage report (HTML or JSON)
3. Screenshot of CI/CD test results (all green)

**Failure Criteria:**
- Any test failure
- Coverage below threshold
- Critical tests skipped

**If FAIL:**
- [ ] Failing tests debugged and fixed
- [ ] Coverage improved (new tests added)
- [ ] Re-test completed (PASS required)

---

## Section 3: Security Review

**Status:** ⬜ PASS | ⬜ FAIL | ⬜ NOT APPLICABLE

**Requirement:** Security review completed for high-risk changes.

### Risk Assessment

**Change Risk Level:**
- [ ] LOW - Minor bug fix, documentation, UI text change
- [ ] MEDIUM - New feature, API change, configuration update
- [ ] HIGH - Authentication/authorization change, encryption, data processing logic
- [ ] CRITICAL - Security patch, infrastructure change, payment processing

**Security Review Required:**
- LOW: Self-review (checklist below)
- MEDIUM: Peer review + security checklist
- HIGH: Security Officer review + penetration test
- CRITICAL: External security audit + SOC 2 auditor notification

### Security Checklist

**Input Validation:**
- [ ] All user inputs validated (type, length, format)
- [ ] SQL injection prevention (parameterized queries or ORM)
- [ ] XSS prevention (output encoding, CSP headers)
- [ ] Command injection prevention (no shell execution with user input)

**Authentication & Authorization:**
- [ ] Authentication required for all protected endpoints
- [ ] Authorization checks enforce least privilege
- [ ] Session management secure (httpOnly, secure, SameSite cookies)
- [ ] No hardcoded admin credentials or backdoors

**Data Protection:**
- [ ] Sensitive data encrypted in transit (TLS 1.2+)
- [ ] Sensitive data encrypted at rest (if stored)
- [ ] Personal data processing complies with GDPR (legal basis, purpose limitation)
- [ ] Data retention policy enforced (automated deletion)

**Error Handling & Logging:**
- [ ] No sensitive data in error messages (stack traces sanitized)
- [ ] Security events logged (authentication, access, errors)
- [ ] Logs do not contain passwords, API keys, or PII

**Dependencies & Libraries:**
- [ ] No known vulnerabilities in dependencies (npm audit, Snyk)
- [ ] Dependencies up-to-date (security patches applied)
- [ ] Unused dependencies removed

**API Security (if applicable):**
- [ ] Rate limiting enforced
- [ ] API authentication required (API key, OAuth)
- [ ] CORS configured correctly (restrictive origin list)
- [ ] API versioning implemented (no breaking changes to v1)

### Vulnerability Scanning

**Scan Results:**
- [ ] SAST scan completed (SonarQube, Checkmarx, Semgrep)
- [ ] Dependency vulnerability scan completed (npm audit, Snyk)
- [ ] No HIGH or CRITICAL vulnerabilities found
- [ ] MEDIUM vulnerabilities documented and accepted (risk acceptance form)

**Scan Output Location:** `/compliance/evidence/pre-deployment/<deployment-id>/vulnerability-scan.log`

**Vulnerability Summary:**
- CRITICAL: ____ (must be 0)
- HIGH: ____ (must be 0)
- MEDIUM: ____ (documented below)
- LOW: ____ (acceptable)

**MEDIUM Vulnerabilities (if any):**

| CVE/ID | Component | Description | Risk Acceptance | Mitigating Controls |
|--------|-----------|-------------|-----------------|---------------------|
| - | - | - | - | - |

### Evidence Required

1. Security review notes (peer review or Security Officer sign-off)
2. Vulnerability scan report
3. Risk acceptance forms (if MEDIUM vulnerabilities present)

**Failure Criteria:**
- HIGH or CRITICAL vulnerability present
- Security review not completed for high-risk change
- Injection vulnerability detected

**If FAIL:**
- [ ] Vulnerabilities patched
- [ ] Security issues resolved
- [ ] Re-scan completed (PASS required)

**Security Reviewer:** _____________________ Date: _________
**Security Officer (HIGH/CRITICAL only):** _____________________ Date: _________

---

## Section 4: Change Request Approval

**Status:** ⬜ PASS | ⬜ FAIL | ⬜ NOT APPLICABLE

**Requirement:** Change request documented and approved per change control policy.

### Change Request Details

**Change Request ID:** _____________________
**Change Request System:** _____________________ (Jira, ServiceNow, etc.)
**Submitted By:** _____________________
**Submission Date:** _____________________

**Change Type:**
- [ ] Standard Change (pre-approved, low risk)
- [ ] Normal Change (requires approval)
- [ ] Emergency Change (expedited approval, requires post-deployment review)

### Approvals Required

**Technical Approval:**
- [ ] Technical Lead approved
  - Name: _____________________ Date: _________

**Security Approval (MEDIUM+ risk):**
- [ ] Security Officer approved
  - Name: _____________________ Date: _________

**Management Approval (HIGH+ risk):**
- [ ] Manager/Director approved
  - Name: _____________________ Title: _____________________ Date: _________

**Emergency Change Approval (CRITICAL):**
- [ ] VP/C-Level approved
  - Name: _____________________ Title: _____________________ Date: _________

### Change Control Board Review (HIGH/CRITICAL)

**CCB Meeting Date:** _____________________
**CCB Decision:** ⬜ APPROVED | ⬜ CONDITIONAL | ⬜ REJECTED

**Conditions (if applicable):**
_____________________________________________________________________________________

**CCB Members Present:**
1. _____________________ (Chair)
2. _____________________
3. _____________________

### Evidence Required

1. Change request document (screenshot or export)
2. Email approvals or approval system notifications
3. CCB meeting minutes (if applicable)

**Failure Criteria:**
- Change request not submitted
- Required approvals missing
- Change rejected by CCB

**If FAIL:**
- [ ] Submit change request
- [ ] Obtain required approvals
- [ ] Address CCB conditions

---

## Section 5: Rollback Plan

**Status:** ⬜ PASS | ⬜ FAIL | ⬜ NOT APPLICABLE

**Requirement:** Documented rollback plan tested and ready.

### Rollback Strategy

**Rollback Method:**
- [ ] Git revert (code deployment)
- [ ] Previous container image (Docker/Kubernetes)
- [ ] Database migration rollback (if schema change)
- [ ] n8n workflow deactivation (if workflow deployment)
- [ ] Configuration rollback (restore previous secrets/env vars)
- [ ] Infrastructure as Code rollback (Terraform destroy/apply)

**Rollback Command/Procedure:**
```bash
# Document exact rollback commands here
# Example:
# git revert <commit-hash> && git push
# kubectl rollout undo deployment/app-name
# n8n workflow deactivate <workflow-id>
```

**Rollback Time Estimate:** _____ minutes

### Rollback Testing

**Rollback Test Completed:**
- [ ] Rollback tested in staging environment
- [ ] Rollback restores system to previous working state
- [ ] No data loss during rollback
- [ ] Rollback time within acceptable window (typically <30 min)

**Test Date:** _________
**Test Performed By:** _____________________
**Test Evidence Location:** `/compliance/evidence/pre-deployment/<deployment-id>/rollback-test.log`

### Data Backup

**Backup Completed:**
- [ ] Database backup created before deployment
- [ ] Configuration backup created
- [ ] Workflow backup exported (if n8n deployment)
- [ ] Backup verified (restore test successful)

**Backup Location:** _____________________
**Backup Timestamp:** _____________________
**Backup Verified By:** _____________________ Date: _________

### Rollback Triggers

**Criteria for Rollback:**
- [ ] Application errors >5% of requests
- [ ] Database connection failures
- [ ] Authentication failures
- [ ] Data corruption detected
- [ ] Performance degradation >50%
- [ ] Security incident detected

**Rollback Decision Authority:** _____________________
**Rollback Notification:** _____________________ (Slack, PagerDuty, email)

### Evidence Required

1. Rollback procedure document
2. Rollback test results (staging)
3. Backup verification log
4. Rollback trigger criteria

**Failure Criteria:**
- No rollback plan documented
- Rollback not tested
- Backup not verified

**If FAIL:**
- [ ] Document rollback procedure
- [ ] Test rollback in staging
- [ ] Verify backups functional

**Rollback Plan Approved By:** _____________________ Date: _________

---

## Final Deployment Approval

### Overall Status

| Section | Status | Evidence | Reviewer | Date |
|---------|--------|----------|----------|------|
| 1. Secrets Scanning | ⬜ | - | - | - |
| 2. Test Coverage | ⬜ | - | - | - |
| 3. Security Review | ⬜ | - | - | - |
| 4. Change Request | ⬜ | - | - | - |
| 5. Rollback Plan | ⬜ | - | - | - |

**Overall Pass Criteria:** 5/5 sections ✅ PASS

**DEPLOYMENT AUTHORIZATION:** ⬜ APPROVED | ⬜ REJECTED

---

### Deployment Approval Sign-Off

**I certify that all pre-deployment security gate requirements have been met and deployment is authorized to proceed.**

**Technical Lead:**
Signature: _____________________ Date: _________
Name: _____________________

**Security Officer:**
Signature: _____________________ Date: _________
Name: _____________________

**Change Control Board Chair (HIGH/CRITICAL only):**
Signature: _____________________ Date: _________
Name: _____________________

---

### Deployment Execution

**Deployment Window:** _____________________ (start time) to _____________________ (end time)
**Maintenance Mode:** ⬜ YES | ⬜ NO
**User Notification Sent:** ⬜ YES | ⬜ NO | ⬜ N/A

**Deployment Steps:**
1. _____________________________________________________________________________________
2. _____________________________________________________________________________________
3. _____________________________________________________________________________________

**Deployment Executed By:** _____________________ Date/Time: _________

**Deployment Status:** ⬜ SUCCESS | ⬜ PARTIAL | ⬜ FAILED | ⬜ ROLLED BACK

**Post-Deployment Notes:**
_____________________________________________________________________________________
_____________________________________________________________________________________

---

## Post-Deployment Monitoring

**Monitoring Duration:** 60 minutes minimum

**Monitoring Checklist:**
- [ ] Application logs reviewed (no errors)
- [ ] Error rate within normal range (<1%)
- [ ] Response time within SLA (<500ms P95)
- [ ] Database connections stable
- [ ] No security alerts triggered
- [ ] User-reported issues: ____ (acceptable: 0)

**Monitoring Completed By:** _____________________ Date/Time: _________

**Deployment Validation:** ⬜ SUCCESSFUL | ⬜ ISSUES DETECTED | ⬜ ROLLBACK INITIATED

---

## Emergency Hotfix Process

**ONLY use for critical production issues requiring immediate fix.**

**Emergency Justification:**
_____________________________________________________________________________________

**Expedited Approvals:**
- [ ] Security Officer notified (verbal/Slack approval acceptable)
- [ ] Technical Lead approval obtained
- [ ] VP/C-Level approval obtained (email or Slack)

**Post-Deployment Requirements (within 24 hours):**
- [ ] Complete full security gate checklist (retroactive)
- [ ] Submit formal change request
- [ ] Conduct post-incident review
- [ ] Document lessons learned

**Emergency Hotfix Authorized By:** _____________________ Title: _____________________ Date/Time: _________

---

## Compliance Notes

**SOC 2 Control Mapping:**
- CC6.1: Logical and physical access controls
- CC6.6: Prevention of processing deviant from specified changes
- CC8.1: Change management process

**GDPR Compliance:**
- Article 32: Security of processing
- Article 25: Data protection by design and by default

**Audit Trail:**
All deployment approvals, evidence, and logs retained for 7 years per SOC 2 requirements.

**Evidence Archive Location:** `/compliance/evidence/pre-deployment/<deployment-id>/`
