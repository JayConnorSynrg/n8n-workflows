# Incident Response Checklist

**Document Version:** 1.0
**Effective Date:** 2026-01-18
**Last Reviewed:** 2026-01-18
**Next Review Date:** 2026-07-18
**Owner:** Security Operations
**Approval Status:** DRAFT - Pending Authorization

---

## How to Use This Checklist

**Purpose:** Step-by-step tactical checklist for executing incident response procedures.

**Instructions:**
1. Print or access digitally during incident response
2. Assign checklist owner (typically Incident Commander)
3. Check boxes as tasks complete
4. Document timestamps in incident timeline
5. Note any deviations or issues in incident ticket
6. Attach completed checklist to final incident report

**Severity-Specific Sections:**
- All incidents: Complete Phases 1-5
- SEV-1/2 only: Additional GDPR notification steps (marked with [GDPR])
- SEV-3/4: Abbreviated checklist (core steps only)

---

## Phase 1: Detection and Identification

**Objective:** Confirm incident, classify severity, activate response team
**Timeline:** 0-15 minutes for SEV-1, 0-1 hour for SEV-2/3

### 1.1 Initial Alert Review

- [ ] **Record detection timestamp** (exact date/time incident first detected)
  - Timestamp: ___________________
  - Detection source: [ ] Monitoring system [ ] User report [ ] Third-party notification [ ] Security scan [ ] Other: ___________

- [ ] **Validate alert authenticity**
  - [ ] Review alert details and indicators
  - [ ] Rule out false positive (check known issues, expected activity)
  - [ ] Confirm incident actually occurred (vs. potential/suspected)
  - Decision: [ ] Confirmed incident [ ] False positive (close ticket) [ ] Requires further investigation

- [ ] **Document initial indicators of compromise (IOCs)**
  - Suspicious IP addresses: ___________________
  - Unusual user accounts: ___________________
  - Malicious files/hashes: ___________________
  - Exploit CVEs: ___________________
  - Other indicators: ___________________

### 1.2 Preliminary Severity Assessment

- [ ] **Identify affected systems** (check all that apply)
  - [ ] N8N workflow platform (production)
  - [ ] PostgreSQL databases (specify): ___________________
  - [ ] LiveKit voice agent infrastructure
  - [ ] OpenAI API integration
  - [ ] Google Workspace services (Drive, Sheets, Docs, Gmail)
  - [ ] Microsoft Teams integration
  - [ ] Authentication systems (OAuth, credentials)
  - [ ] Other: ___________________

- [ ] **Assess data exposure** (check all that apply)
  - [ ] Special category data (biometric voice recordings)
  - [ ] Personal data (names, emails, phone numbers, addresses)
  - [ ] Financial data (payment cards, bank accounts)
  - [ ] Credentials (passwords, API keys, OAuth tokens)
  - [ ] Enterprise data (confidential documents, communications)
  - [ ] No data exposure confirmed
  - Estimated number of records: ___________________
  - Geographic scope: [ ] EU/EEA residents [ ] Other: ___________

- [ ] **Determine threat status**
  - [ ] Active ongoing attack (data exfiltration, system access in progress)
  - [ ] Contained historical incident (occurred in past, no longer active)
  - [ ] Uncertain (requires investigation to determine)

- [ ] **Classify incident severity** (reference INCIDENT-CLASSIFICATION-MATRIX.md)
  - Initial severity: [ ] SEV-1 [ ] SEV-2 [ ] SEV-3 [ ] SEV-4
  - Classification rationale: ___________________

### 1.3 Team Activation and Communication Setup

- [ ] **Notify Incident Commander**
  - IC name: ___________________
  - Notification timestamp: ___________________
  - Contact method: [ ] Phone [ ] Email [ ] Slack/Teams [ ] In-person

- [ ] **Assemble Incident Response Team** (based on severity)
  - SEV-1/2: Full team required
  - SEV-3: Security engineer + system admin
  - SEV-4: Security analyst only

  **Core Team (check when notified and confirmed available):**
  - [ ] Incident Commander: ___________________ (Time: _______)
  - [ ] Security Lead: ___________________ (Time: _______)
  - [ ] Systems Engineer: ___________________ (Time: _______)
  - [ ] Legal Counsel: ___________________ (Time: ______) [SEV-1/2]
  - [ ] Communications Lead: ___________________ (Time: ______) [SEV-1/2]
  - [ ] Data Protection Officer: ___________________ (Time: ______) [GDPR]

  **Extended Team (activate as needed):**
  - [ ] Forensics Specialist: ___________________ (Time: _______)
  - [ ] Business Continuity Lead: ___________________ (Time: _______)
  - [ ] HR Representative: ___________________ (Time: ______) [insider threat]
  - [ ] External forensics firm: ___________________ (Time: _______)

- [ ] **Establish incident communication channel**
  - [ ] Create dedicated Slack/Teams channel: #incident-[ID]
  - [ ] Set up war room (if SEV-1): Location/link: ___________________
  - [ ] Configure conference bridge: Number/link: ___________________
  - [ ] Ensure all IRT members have access

- [ ] **Executive notification** (based on severity)
  - SEV-1: Immediate phone call
  - SEV-2: Within 1 hour
  - SEV-3: Within 4 hours
  - SEV-4: Next business day summary

  **Executives notified:**
  - [ ] CEO: ___________________ (Time: _______)
  - [ ] CTO: ___________________ (Time: _______)
  - [ ] General Counsel: ___________________ (Time: _______)
  - [ ] Board Chair (if SEV-1): ___________________ (Time: _______)

### 1.4 Documentation Initiation

- [ ] **Create incident ticket**
  - Ticket ID: ___________________
  - Ticketing system: [ ] Jira [ ] ServiceNow [ ] Other: ___________
  - Assigned to: ___________________
  - Priority: [ ] P1 (SEV-1) [ ] P2 (SEV-2) [ ] P3 (SEV-3) [ ] P4 (SEV-4)

- [ ] **Initiate incident timeline log**
  - [ ] Document detection timestamp
  - [ ] Record all notifications sent (who, when, method)
  - [ ] Note all actions taken with timestamps
  - Timeline storage location: ___________________

- [ ] **Begin evidence preservation chain of custody**
  - [ ] Create evidence folder with access controls
  - [ ] Document all evidence collected (what, when, who collected)
  - [ ] Ensure forensic tools available (write-blockers, imaging software)
  - Evidence storage location: ___________________

---

## Phase 2: Containment

**Objective:** Stop incident progression, preserve evidence, minimize damage
**Timeline:** 15-30 minutes (short-term), 1-4 hours (long-term)

### 2.1 Short-Term Containment (Immediate Actions)

**Critical: Balance containment with evidence preservation. Consult forensics specialist before destructive actions.**

- [ ] **Disable compromised user accounts**
  - [ ] Identify all affected user accounts: ___________________
  - [ ] Disable accounts in identity provider (Okta, Azure AD, etc.)
  - [ ] Force logout of all active sessions
  - [ ] Document account names and disable timestamps
  - Accounts disabled: ___________________

- [ ] **Revoke suspect credentials**
  - [ ] Identify compromised API keys: ___________________
  - [ ] Revoke OAuth tokens (Google, Microsoft, OpenAI)
  - [ ] Rotate database passwords
  - [ ] Invalidate service account credentials
  - [ ] Update credential vault with new credentials
  - Credentials revoked/rotated: ___________________

- [ ] **Isolate affected N8N workflow instances**
  - [ ] Identify affected workflows: ___________________
  - [ ] Pause/disable affected workflows (do not delete - preserve evidence)
  - [ ] Disconnect from external integrations
  - [ ] Document workflow states before modification
  - Workflows isolated: ___________________

- [ ] **Block malicious network activity**
  - [ ] Identify malicious IP addresses/domains: ___________________
  - [ ] Implement firewall rules to block IPs
  - [ ] Add domains to DNS blocklist
  - [ ] Document firewall rule changes
  - Network blocks implemented: ___________________

- [ ] **Enforce enhanced access controls**
  - [ ] Enable MFA requirement for all administrative accounts
  - [ ] Restrict admin access to authorized personnel only
  - [ ] Implement just-in-time access (if available)
  - [ ] Review and tighten OAuth scopes
  - Access controls updated: ___________________

### 2.2 Evidence Preservation (CRITICAL - Do Before Long-Term Containment)

- [ ] **Create forensic snapshots** (before making system changes)
  - [ ] Snapshot affected VM instances (preserve full state)
  - [ ] Export database dumps (pre-remediation state)
  - [ ] Capture memory dumps (if active compromise)
  - [ ] Screenshot malicious activity (ransomware notes, unauthorized access)
  - Forensic images created: ___________________
  - Storage location: ___________________

- [ ] **Preserve logs and audit trails**
  - [ ] Export N8N execution logs (past 90 days)
  - [ ] Export database audit logs
  - [ ] Export authentication logs (SSO, OAuth)
  - [ ] Export firewall/network logs
  - [ ] Export third-party service logs (LiveKit, OpenAI, Google)
  - [ ] Document log retention and export timestamps
  - Logs preserved: ___________________

- [ ] **Document chain of custody**
  - [ ] Record who collected evidence (name, role)
  - [ ] Record collection timestamps
  - [ ] Record evidence storage location and access controls
  - [ ] Use write-blocking tools for disk imaging
  - [ ] Hash all evidence files (SHA-256)
  - Chain of custody log: ___________________

### 2.3 Long-Term Containment

- [ ] **Network segmentation**
  - [ ] Isolate affected systems in separate VLAN
  - [ ] Restrict network traffic to/from compromised systems
  - [ ] Monitor isolated network segment for lateral movement
  - [ ] Document network topology changes
  - Segmentation implemented: ___________________

- [ ] **Establish clean backup restoration points**
  - [ ] Identify last known-good backup before compromise
  - [ ] Verify backup integrity (checksums, test restore)
  - [ ] Quarantine potentially compromised backups
  - [ ] Document backup selection rationale
  - Clean backup identified: ___________________ (Date/time)

- [ ] **Threat hunting for lateral movement**
  - [ ] Review logs for unauthorized access to other systems
  - [ ] Check for new user accounts created
  - [ ] Search for suspicious scheduled tasks/cron jobs
  - [ ] Analyze authentication logs for anomalous patterns
  - [ ] Verify no backdoors installed on other systems
  - Additional compromised systems found: ___________________

### 2.4 Communication Preparation

- [ ] **Draft internal stakeholder notification**
  - [ ] Prepare summary for executive leadership
  - [ ] Identify affected business units
  - [ ] Draft communication to affected teams
  - [ ] Coordinate with Communications Lead
  - Internal notification sent: ___________________ (Time)

- [ ] **[GDPR] Assess breach notification requirements**
  - [ ] Complete GDPR risk assessment (see BREACH-NOTIFICATION-PROCEDURE.md)
  - [ ] Determine if supervisory authority notification required
  - [ ] Determine if data subject notification required
  - [ ] Calculate 72-hour deadline: ___________________ (Date/time)
  - Notification required: [ ] Yes - Authority [ ] Yes - Data subjects [ ] No [ ] Under assessment

- [ ] **Coordinate with legal on disclosure**
  - [ ] Review contractual notification obligations (customer SLAs)
  - [ ] Assess regulatory reporting requirements (beyond GDPR)
  - [ ] Determine law enforcement notification (if criminal activity)
  - [ ] Prepare holding statements for media inquiries
  - Legal review completed: ___________________

---

## Phase 3: Eradication

**Objective:** Remove threat actor access, eliminate malware, fix root cause
**Timeline:** 4-24 hours

### 3.1 Threat Removal

- [ ] **Remove malicious code and unauthorized access**
  - [ ] Delete malicious scripts/files identified (document locations first)
  - [ ] Remove unauthorized user accounts
  - [ ] Delete unauthorized SSH keys, API tokens
  - [ ] Terminate unauthorized processes/services
  - [ ] Verify removal with security scans
  - Threats removed: ___________________

- [ ] **Purge compromised credentials from all systems**
  - [ ] Rotate ALL credentials (assume full compromise if privileged access)
  - [ ] Update API keys in N8N workflows
  - [ ] Regenerate OAuth client secrets
  - [ ] Change database passwords
  - [ ] Update service account credentials
  - [ ] Verify old credentials no longer valid
  - Credential rotation completed: ___________________

### 3.2 Vulnerability Remediation

- [ ] **Patch exploited vulnerabilities**
  - [ ] Identify root cause vulnerability/misconfiguration: ___________________
  - [ ] Apply security patches (OS, applications, N8N)
  - [ ] Update dependencies with known vulnerabilities
  - [ ] Test patches in non-production environment first
  - [ ] Document patch levels and versions
  - Patches applied: ___________________

- [ ] **Fix security misconfigurations**
  - [ ] Correct excessive OAuth scopes
  - [ ] Fix overly permissive IAM/RBAC policies
  - [ ] Disable unnecessary services/ports
  - [ ] Harden system configurations per CIS benchmarks
  - [ ] Update security group rules
  - Misconfigurations remediated: ___________________

### 3.3 Security Hardening

- [ ] **Implement enhanced monitoring**
  - [ ] Deploy additional logging for affected systems
  - [ ] Configure alerts for IOCs from this incident
  - [ ] Enable anomaly detection rules
  - [ ] Increase log retention period (if not already max)
  - [ ] Monitor for recurrence of attack patterns
  - Enhanced monitoring deployed: ___________________

- [ ] **Add detection rules based on incident**
  - [ ] Create SIEM rules for attack signatures
  - [ ] Configure IDS/IPS rules for exploit patterns
  - [ ] Add file integrity monitoring for critical paths
  - [ ] Implement data exfiltration detection rules
  - Detection rules created: ___________________

### 3.4 Verification of Eradication

- [ ] **Conduct security scans**
  - [ ] Vulnerability scan (verify patches applied)
  - [ ] Malware scan (verify malicious code removed)
  - [ ] Configuration audit (verify hardening applied)
  - [ ] Penetration test (if SEV-1, verify exploit no longer works)
  - Scan results: [ ] Clean [ ] Issues found: ___________

- [ ] **Review audit logs for residual activity**
  - [ ] Check logs for continued malicious activity
  - [ ] Search for persistence mechanisms (backdoors, scheduled tasks)
  - [ ] Verify no unauthorized access after containment
  - Residual activity found: [ ] No [ ] Yes: ___________

- [ ] **Confirm threat eradication**
  - [ ] Security Lead sign-off: ___________________ (Name, Date)
  - [ ] No indicators of continued compromise
  - [ ] All vulnerabilities remediated
  - [ ] System hardened and monitored
  - Eradication confirmed: [ ] Yes [ ] No (continue Phase 3)

---

## Phase 4: Recovery

**Objective:** Restore normal operations, validate integrity, monitor for recurrence
**Timeline:** 24-72 hours

### 4.1 Service Restoration Planning

- [ ] **Develop restoration plan**
  - [ ] Identify restoration priorities (critical services first)
  - [ ] Define restoration sequence (dependencies)
  - [ ] Prepare rollback plan if issues detected
  - [ ] Schedule restoration timeline: ___________________
  - [ ] Communicate planned downtime to stakeholders

- [ ] **Prepare clean restore environment**
  - [ ] Verify infrastructure secured (no residual threats)
  - [ ] Test connectivity to dependent systems
  - [ ] Ensure all credentials rotated
  - [ ] Confirm monitoring and logging active
  - Environment ready: ___________________

### 4.2 Data and System Restoration

- [ ] **Restore from clean backups** (if data loss or corruption)
  - [ ] Restore from last known-good backup (pre-compromise)
  - [ ] Verify backup integrity (checksums, test queries)
  - [ ] Validate data completeness (record counts, critical data spot-checks)
  - [ ] Document any data loss (if unavoidable)
  - Backup restoration completed: ___________________

- [ ] **Restore N8N workflows**
  - [ ] Restore workflow configurations from clean version control
  - [ ] Update with new credentials (rotated API keys, OAuth tokens)
  - [ ] Verify workflow logic not tampered with (code review)
  - [ ] Test workflows in isolated environment first
  - Workflows restored: ___________________

- [ ] **Reconnect integrations**
  - [ ] Re-establish Google Workspace connections (new OAuth tokens)
  - [ ] Reconnect OpenAI API (new API key)
  - [ ] Restore Microsoft Teams integration
  - [ ] Reconnect database connections (new credentials)
  - [ ] Test each integration with limited scope first
  - Integrations restored: ___________________

### 4.3 Integrity Validation

- [ ] **Verify data integrity**
  - [ ] Run database integrity checks (checksums, foreign key constraints)
  - [ ] Spot-check critical data for unauthorized modifications
  - [ ] Compare record counts to pre-incident baselines
  - [ ] Verify no malicious data injected
  - Data integrity confirmed: [ ] Yes [ ] Issues found: ___________

- [ ] **Validate system functionality**
  - [ ] Test critical workflows end-to-end
  - [ ] Verify authentication systems working (user login tests)
  - [ ] Confirm integrations functioning (test API calls)
  - [ ] Check performance metrics (no degradation)
  - System functionality validated: ___________________

### 4.4 Phased Service Restoration

- [ ] **Phase 1: Limited pilot** (10% capacity, critical users only)
  - [ ] Enable workflows for pilot user group
  - [ ] Monitor closely for anomalies (15-minute intervals)
  - [ ] Gather user feedback
  - [ ] Verify no incidents during pilot
  - Pilot successful: [ ] Yes (proceed to Phase 2) [ ] No (rollback)

- [ ] **Phase 2: Gradual rollout** (50% capacity)
  - [ ] Expand to broader user base
  - [ ] Continue enhanced monitoring (hourly intervals)
  - [ ] Address any issues identified
  - Rollout successful: [ ] Yes (proceed to Phase 3) [ ] No (rollback)

- [ ] **Phase 3: Full restoration** (100% capacity)
  - [ ] Enable all workflows and services
  - [ ] Transition to standard monitoring (maintain enhancements)
  - [ ] Declare incident resolved (pending post-incident review)
  - Full restoration completed: ___________________ (Date/time)

### 4.5 Enhanced Monitoring Period

- [ ] **Configure incident-specific monitoring** (2 weeks minimum)
  - [ ] Alert on any IOCs from this incident
  - [ ] Monitor for similar attack patterns
  - [ ] Daily security scans of affected systems
  - [ ] Review authentication logs daily
  - Monitoring period: ___________________ (Start date) to ___________________ (End date)

- [ ] **Schedule daily check-ins**
  - [ ] Security Lead daily review of alerts
  - [ ] Daily report to Incident Commander
  - [ ] Weekly summary to executive leadership
  - Daily reviews scheduled: ___________________

---

## Phase 5: Post-Incident Review

**Objective:** Learn from incident, improve security posture, document lessons
**Timeline:** 72 hours - 2 weeks post-resolution

### 5.1 Incident Review Meeting

- [ ] **Schedule post-incident review meeting** (within 5 business days)
  - Meeting date/time: ___________________
  - Required attendees: Full IRT + affected business unit leads
  - Facilitator: ___________________ (typically IC or Security Lead)

- [ ] **Prepare meeting agenda**
  - [ ] Incident timeline review
  - [ ] Response effectiveness evaluation
  - [ ] Identification of what went well
  - [ ] Identification of gaps and improvement opportunities
  - [ ] Root cause analysis (Five Whys)
  - [ ] Remediation action planning

- [ ] **Conduct meeting and document outcomes**
  - [ ] Review complete incident timeline
  - [ ] Discuss response challenges and successes
  - [ ] Identify contributing factors to incident
  - [ ] Brainstorm preventive measures
  - [ ] Assign remediation action owners and deadlines
  - Meeting notes location: ___________________

### 5.2 Root Cause Analysis

- [ ] **Perform Five Whys analysis**
  - Problem statement: ___________________
  - Why 1: ___________________
  - Why 2: ___________________
  - Why 3: ___________________
  - Why 4: ___________________
  - Why 5 (root cause): ___________________

- [ ] **Identify contributing factors**
  - [ ] Technical factors (vulnerabilities, misconfigurations)
  - [ ] Process factors (gaps in procedures, missed steps)
  - [ ] Human factors (training gaps, awareness issues)
  - [ ] External factors (vendor security, supply chain)
  - Contributing factors: ___________________

### 5.3 Final Documentation

- [ ] **Complete final incident report** (template in INCIDENT-RESPONSE-PLAN.md)
  - [ ] Executive summary (1 page)
  - [ ] Incident overview (detection, classification, scope)
  - [ ] Detailed timeline of events
  - [ ] Impact assessment (data, systems, business)
  - [ ] Response actions taken (all phases)
  - [ ] Root cause analysis
  - [ ] Lessons learned (what worked, what didn't)
  - [ ] Remediation plan with timelines and owners
  - [ ] Appendices (evidence, communications, regulatory filings)
  - Report completion date: ___________________
  - Report reviewed and approved by: ___________________

- [ ] **Update breach register** (if data breach)
  - [ ] Document incident in GDPR breach register
  - [ ] Include all required fields (date, data categories, scope, actions)
  - [ ] Attach final incident report
  - [ ] Note supervisory authority notification (if applicable)
  - Breach register updated: ___________________

- [ ] **Preserve evidence and documentation** (7-year retention)
  - [ ] Archive all logs, forensic images, communications
  - [ ] Secure storage with access controls
  - [ ] Document storage location and retention period
  - [ ] Create evidence inventory
  - Evidence archived location: ___________________

### 5.4 Remediation and Improvement Planning

- [ ] **Security control enhancements**
  - [ ] Identify new security controls needed: ___________________
  - [ ] Prioritize by risk reduction impact
  - [ ] Assign owners and implementation deadlines
  - [ ] Budget requests for tools/resources: ___________________

- [ ] **Policy and procedure updates**
  - [ ] Update Incident Response Plan (if gaps identified)
  - [ ] Revise security policies (if needed)
  - [ ] Update runbooks and playbooks
  - [ ] Improve detection and monitoring rules
  - Documents to update: ___________________

- [ ] **Training needs identification**
  - [ ] Security awareness training updates
  - [ ] IRT training on new tools/procedures
  - [ ] Role-specific training (developers, admins)
  - [ ] Tabletop exercise scenarios based on incident
  - Training plan: ___________________

- [ ] **Implement quick wins** (immediate improvements)
  - [ ] Deploy critical security patches
  - [ ] Fix high-risk misconfigurations
  - [ ] Add detection rules for this attack type
  - [ ] Enhanced monitoring for similar threats
  - Quick wins completed: ___________________

### 5.5 Regulatory Compliance

- [ ] **[GDPR] Finalize breach notification** (if applicable)
  - [ ] Submit supervisory authority notification (within 72 hours)
  - [ ] Send data subject notifications (within 96 hours typically)
  - [ ] Respond to supervisory authority follow-up questions
  - [ ] Document all regulatory communications
  - GDPR compliance completed: ___________________

- [ ] **SOC 2 audit documentation**
  - [ ] Update security incident log for SOC 2
  - [ ] Document corrective actions taken
  - [ ] Provide evidence of remediation to auditor
  - [ ] Update control descriptions if needed
  - SOC 2 documentation updated: ___________________

- [ ] **Customer/contractual notifications**
  - [ ] Notify customers per SLA requirements
  - [ ] Provide incident summary and remediation
  - [ ] Respond to customer security questionnaires
  - [ ] Update trust center/status page
  - Customer notifications completed: ___________________

### 5.6 Incident Closure

- [ ] **Verify all remediation actions completed**
  - [ ] Review remediation action tracker
  - [ ] Confirm all assigned tasks closed
  - [ ] Validate effectiveness of improvements
  - All actions completed: [ ] Yes [ ] No (track separately)

- [ ] **Executive sign-off**
  - [ ] CTO review and approval: ___________________ (Name, Date)
  - [ ] General Counsel review (if data breach): ___________________ (Name, Date)
  - [ ] DPO review (if GDPR): ___________________ (Name, Date)

- [ ] **Close incident ticket**
  - [ ] Update ticket status to "Resolved"
  - [ ] Attach final incident report
  - [ ] Document lessons learned in ticket notes
  - [ ] Archive incident communication channel
  - Incident closed: ___________________ (Date/time)

- [ ] **Communicate closure to stakeholders**
  - [ ] Notify IRT of incident closure
  - [ ] Send summary to executive leadership
  - [ ] Update affected business units on resolution
  - [ ] Thank IRT members for response efforts
  - Closure communication sent: ___________________

---

## Severity-Specific Quick Reference

### SEV-1 Critical Incident Checklist (Abbreviated)

**Immediate (0-15 minutes):**
- [ ] Detect and confirm incident
- [ ] Notify Incident Commander (phone)
- [ ] Classify as SEV-1
- [ ] Activate full IRT
- [ ] Notify executives (CEO, CTO, GC)
- [ ] Create incident ticket and timeline

**Short-term containment (15-30 minutes):**
- [ ] Disable compromised accounts
- [ ] Revoke credentials
- [ ] Isolate affected systems
- [ ] Block malicious IPs
- [ ] Preserve forensic evidence

**Within 24 hours:**
- [ ] Complete GDPR risk assessment
- [ ] Draft supervisory authority notification
- [ ] Engage external forensics (if needed)
- [ ] Brief executives (every 2-4 hours)

**Within 72 hours:**
- [ ] Submit GDPR notification (if required)
- [ ] Notify data subjects (if high risk)
- [ ] Complete eradication
- [ ] Begin phased recovery

**Within 5 business days:**
- [ ] Conduct post-incident review
- [ ] Complete final incident report
- [ ] Document lessons learned

---

### SEV-3/4 Low-Severity Checklist (Abbreviated)

**Within 4 hours:**
- [ ] Detect and confirm incident
- [ ] Classify as SEV-3 or SEV-4
- [ ] Assign to security analyst/engineer
- [ ] Create incident ticket

**Within 24-48 hours:**
- [ ] Investigate and contain (if needed)
- [ ] Remediate issue
- [ ] Verify no broader impact
- [ ] Document in ticket

**Within 1 week:**
- [ ] Complete remediation
- [ ] Update knowledge base
- [ ] Close ticket
- [ ] Include in weekly security report

---

## GDPR Breach Notification Quick Checklist

**For SEV-1/SEV-2 incidents involving personal data:**

- [ ] **Hour 0:** Document breach awareness timestamp
- [ ] **Hours 0-24:** Complete GDPR risk assessment
  - [ ] Identify data categories (special category?)
  - [ ] Count affected individuals (>1000?)
  - [ ] Assess risk to rights and freedoms
  - [ ] Decision: [ ] Notify authority [ ] Notify data subjects [ ] Neither (document why)
- [ ] **Hours 24-48:** Prepare notifications
  - [ ] Draft supervisory authority notification
  - [ ] Draft data subject notification (if required)
  - [ ] Legal and executive review
  - [ ] Identify correct supervisory authority
- [ ] **Hours 48-72:** Submit notifications
  - [ ] Submit to supervisory authority (deadline: 72 hours)
  - [ ] Send data subject notifications (concurrently or soon after)
  - [ ] Document submission timestamps and confirmations
- [ ] **Follow-up:** Respond to supervisory authority questions, update breach register

**Reference:** BREACH-NOTIFICATION-PROCEDURE.md for detailed GDPR procedures and templates.

---

## Emergency Contacts

| Role | Name | Phone | Email | Backup |
|------|------|-------|-------|--------|
| **Incident Commander** | _____________ | _____________ | _____________ | _____________ |
| **Security Lead** | _____________ | _____________ | _____________ | _____________ |
| **Data Protection Officer** | _____________ | _____________ | _____________ | _____________ |
| **General Counsel** | _____________ | _____________ | _____________ | _____________ |
| **CTO** | _____________ | _____________ | _____________ | _____________ |
| **External Forensics** | _____________ | _____________ | _____________ | N/A |

**Supervisory Authority (GDPR):** _________________ | Phone: _____________ | Email: _____________

---

## Related Documents

- `INCIDENT-RESPONSE-PLAN.md` - Comprehensive incident response procedures
- `BREACH-NOTIFICATION-PROCEDURE.md` - GDPR breach notification requirements
- `INCIDENT-CLASSIFICATION-MATRIX.md` - Severity definitions and examples
- `/security/runbooks/` - System-specific response playbooks
- `/security/templates/` - Notification templates and forms

---

**Document Classification:** CONFIDENTIAL - INTERNAL USE ONLY
**Print Date:** ___________________
**Incident ID:** ___________________
**Checklist Owner:** ___________________

---

## Approval and Distribution

### Approval Signatures

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Chief Technology Officer | ___________________ | ___________________ | ________ |
| Security Lead | ___________________ | ___________________ | ________ |
| Data Protection Officer | ___________________ | ___________________ | ________ |

### Distribution List
- All Incident Response Team members (controlled copy)
- Security operations team (controlled copy)

---

**Next Review Date:** 2026-07-18
