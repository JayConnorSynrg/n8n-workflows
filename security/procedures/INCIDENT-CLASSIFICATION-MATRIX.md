# Incident Classification Matrix

**Document Version:** 1.0
**Effective Date:** 2026-01-18
**Last Reviewed:** 2026-01-18
**Next Review Date:** 2026-07-18
**Owner:** Security Operations
**Approval Status:** DRAFT - Pending Authorization

---

## 1. Purpose

This document defines the severity classification system for security incidents affecting the N8N workflow automation platform and associated systems. Proper classification ensures appropriate response prioritization, resource allocation, and stakeholder communication.

**Classification Authority:** Incident Commander (may reclassify based on evolving information)

---

## 2. Severity Levels Overview

| Severity | Business Impact | Data Impact | Response SLA | Escalation |
|----------|----------------|-------------|--------------|------------|
| **SEV-1** | Critical - Business operations severely impaired | Special category data exposed OR >1000 records | 15 minutes | Immediate executive notification |
| **SEV-2** | High - Significant service disruption or data risk | PII breach <1000 records OR credential compromise | 1 hour | Executive notification within 1 hour |
| **SEV-3** | Medium - Limited impact, contained threat | Attempted breach, single account compromise | 4 hours | Management notification within 4 hours |
| **SEV-4** | Low - Minimal risk, policy violation | No data exposure, false positive | 24 hours | Next business day summary |

**Response SLA:** Maximum time from incident detection to Incident Response Team activation.

---

## 3. SEV-1: Critical Incidents

### 3.1 Definition
Incidents causing immediate, severe impact to business operations, data security, or legal/regulatory compliance. These incidents require immediate executive-level attention and all-hands response.

### 3.2 Severity Criteria (ANY of the following)

**Data Exposure:**
- [ ] Special category personal data breach (biometric voice recordings, health data)
- [ ] >1,000 personal data records exposed
- [ ] Complete database exfiltration or unauthorized export
- [ ] Source code or intellectual property theft
- [ ] Encryption keys or master credentials compromised

**System Impact:**
- [ ] Critical infrastructure completely unavailable (>50% of business operations affected)
- [ ] Active ransomware or destructive malware deployment
- [ ] Complete loss of data (no backup recovery possible)
- [ ] Root/admin compromise of production systems

**Threat Actor:**
- [ ] Active, ongoing data exfiltration in progress
- [ ] Advanced persistent threat (APT) detection
- [ ] Insider threat with privileged access
- [ ] Nation-state actor indicators

**Regulatory/Legal:**
- [ ] GDPR breach requiring supervisory authority notification
- [ ] Breach with immediate legal/regulatory deadline
- [ ] Public disclosure already occurred (media coverage)

### 3.3 Examples

**Example 1: Biometric Data Breach**
- **Scenario:** Unauthorized access to LiveKit voice agent database containing 5,000 voice recordings
- **Classification:** SEV-1 (special category data + high volume)
- **Rationale:** Voice recordings are biometric identifiers (GDPR Article 9), high-risk data requiring supervisory authority notification

**Example 2: Active Data Exfiltration**
- **Scenario:** Security monitoring detects large-scale data transfer to external IP address from PostgreSQL database
- **Classification:** SEV-1 (active threat, potential mass data exposure)
- **Rationale:** Ongoing exfiltration requires immediate containment; scope unknown but potentially massive

**Example 3: Ransomware Deployment**
- **Scenario:** Ransomware encrypted N8N workflow files and database backups, ransom note displayed
- **Classification:** SEV-1 (critical availability breach, business operations halted)
- **Rationale:** Complete service disruption, potential data loss, immediate recovery required

**Example 4: Admin Account Takeover**
- **Scenario:** Attacker gains full administrative access to N8N platform, can modify all workflows and access all credentials
- **Classification:** SEV-1 (privileged access compromise, potential for massive damage)
- **Rationale:** Complete platform control enables lateral movement, data exfiltration, and system destruction

### 3.4 Response Requirements

**Timeline:**
- **Detection to IRT Activation:** 15 minutes maximum
- **Incident Commander Notification:** Immediate (phone call)
- **Executive Notification:** Within 15 minutes (CEO, CTO, General Counsel)
- **Containment Initiation:** Within 30 minutes
- **Initial Status Update:** Every 1 hour until containment achieved

**Team Activation:**
- Full Incident Response Team (all roles)
- Executive leadership on standby
- Legal counsel engaged
- External forensics firm (if required)
- Law enforcement liaison (if criminal activity)

**Communication:**
- Dedicated war room (physical or virtual)
- Executive briefing every 2-4 hours
- Stakeholder notification within 4 hours
- Public communications plan prepared

**Documentation:**
- Detailed timeline (minute-by-minute)
- All decisions documented with decision-maker
- Evidence preservation (forensic images)
- Regulatory notification preparation begins immediately

### 3.5 Reclassification Triggers

**Upgrade to SEV-1:**
- SEV-2 incident reveals special category data exposed
- Initial assessment of 500 records revised to >1,000
- Media coverage of incident occurs
- Regulatory authority inquiry received

**Downgrade from SEV-1:**
- Initial assessment of data exposure proven incorrect (false positive)
- Effective encryption confirmed (data unreadable to attacker)
- Scope significantly smaller than initially assessed (<100 records)

---

## 4. SEV-2: High Severity Incidents

### 4.1 Definition
Incidents with significant impact to data security or operations, requiring urgent response but not immediately business-critical. Executive notification required but not instant escalation.

### 4.2 Severity Criteria (ANY of the following)

**Data Exposure:**
- [ ] Personal data breach: 100-999 records
- [ ] PII exposure (names, emails, phone numbers, addresses)
- [ ] Authentication credentials compromised (OAuth tokens, API keys)
- [ ] Financial data exposure (payment card data, bank account numbers)
- [ ] Employee data breach (HR records, salaries, performance reviews)

**System Impact:**
- [ ] Major service disruption (25-50% of operations affected)
- [ ] Unauthorized administrative access (limited duration, contained)
- [ ] Data integrity compromise (unauthorized modifications detected)
- [ ] Critical vulnerability actively exploited

**Threat Actor:**
- [ ] Sophisticated external attack (not APT level)
- [ ] Insider threat without privileged access
- [ ] Supply chain compromise (third-party vendor breach)

**Regulatory/Legal:**
- [ ] Potential GDPR notification (under assessment)
- [ ] Customer contractual breach (SLA violation)
- [ ] Regulatory inquiry or audit finding

### 4.3 Examples

**Example 1: OAuth Token Compromise**
- **Scenario:** Attacker obtains OAuth token for Google Drive integration, accesses 300 customer documents
- **Classification:** SEV-2 (credential compromise, moderate data exposure)
- **Rationale:** Limited scope (<1,000 records), no special category data, contained to single integration

**Example 2: Database Unauthorized Access**
- **Scenario:** SQL injection vulnerability exploited, attacker queries customer table (read-only, no export detected)
- **Classification:** SEV-2 (unauthorized access, data viewed but not exfiltrated)
- **Rationale:** Confidentiality breach confirmed, but limited scope and no evidence of mass exfiltration

**Example 3: Employee Account Takeover**
- **Scenario:** Phishing attack compromises employee account with access to 500 customer records in N8N workflows
- **Classification:** SEV-2 (PII exposure, credential compromise)
- **Rationale:** Moderate volume of personal data, requires notification assessment, contained to single account

**Example 4: Third-Party Breach Notification**
- **Scenario:** OpenAI notifies of API key exposure in their system, potential access to prompt history containing customer data
- **Classification:** SEV-2 (supply chain compromise, uncertain scope)
- **Rationale:** Requires investigation to determine actual exposure, potential PII in prompts

### 4.4 Response Requirements

**Timeline:**
- **Detection to IRT Activation:** 1 hour maximum
- **Incident Commander Notification:** Within 30 minutes
- **Executive Notification:** Within 1 hour (CTO, General Counsel if data breach)
- **Containment Initiation:** Within 2 hours
- **Initial Status Update:** Every 4 hours

**Team Activation:**
- Core Incident Response Team
- Legal counsel (if data breach)
- System administrators and security engineers
- Communications lead (if external notification likely)

**Communication:**
- Incident Slack/Teams channel established
- Executive briefing within 4 hours
- Stakeholder notification if required (within 24 hours)
- Customer notification preparation (if applicable)

**Documentation:**
- Incident timeline (hourly granularity)
- Affected systems and data inventory
- Breach assessment for GDPR notification decision
- Evidence preservation

### 4.5 Reclassification Triggers

**Upgrade to SEV-1:**
- Data exposure exceeds 1,000 records
- Special category data discovered
- Active exfiltration detected
- Media coverage or regulatory inquiry

**Downgrade to SEV-3:**
- Initial assessment overestimated scope (<100 records)
- Effective encryption confirmed (data protected)
- Incident contained with no data exposure

---

## 5. SEV-3: Medium Severity Incidents

### 5.1 Definition
Incidents with limited impact, successfully contained, or representing potential threats that did not result in actual compromise. Standard business-hours response acceptable.

### 5.2 Severity Criteria (ANY of the following)

**Data Exposure:**
- [ ] Personal data breach: <100 records
- [ ] Single user account data exposure
- [ ] Non-sensitive data exposure (public information, non-PII)
- [ ] Metadata exposure (logs, usage statistics without PII)

**System Impact:**
- [ ] Minor service disruption (<25% of operations)
- [ ] Failed intrusion attempt (blocked by security controls)
- [ ] Non-production environment compromise (dev/test systems)
- [ ] Vulnerability detected but not exploited

**Threat Actor:**
- [ ] Opportunistic attack (automated scanning, script kiddies)
- [ ] Unsuccessful social engineering attempt
- [ ] Suspicious activity under investigation

**Compliance:**
- [ ] Policy violation (no data exposure)
- [ ] Security control failure (detected and remediated)
- [ ] Audit finding (non-critical)

### 5.3 Examples

**Example 1: Single Account Compromise**
- **Scenario:** User reports account logged in from unusual location, password reset performed, no suspicious activity detected
- **Classification:** SEV-3 (single user, no data exposure evidence)
- **Rationale:** Limited scope, quickly contained, no evidence of broader compromise

**Example 2: Failed Intrusion Attempt**
- **Scenario:** Firewall logs show repeated authentication failures from external IP, automatically blocked after 5 attempts
- **Classification:** SEV-3 (unsuccessful attack, controls effective)
- **Rationale:** Attack blocked by security controls, no system access achieved

**Example 3: Non-Production Data Exposure**
- **Scenario:** Development environment database with synthetic test data exposed due to misconfiguration
- **Classification:** SEV-3 (non-production, no real data)
- **Rationale:** Test data only, no real customer information, but indicates security control gap

**Example 4: Suspicious Email Reported**
- **Scenario:** Employee reports phishing email targeting organization, IT confirms link clicked but no credentials entered
- **Classification:** SEV-3 (attempted attack, unsuccessful)
- **Rationale:** Awareness training effective, no compromise occurred, monitoring required

### 5.4 Response Requirements

**Timeline:**
- **Detection to IRT Activation:** 4 hours maximum
- **Security Lead Notification:** Within 2 hours
- **Management Notification:** Within 4 hours
- **Containment Initiation:** Within 8 hours
- **Status Update:** Daily until resolved

**Team Activation:**
- Security engineer (primary responder)
- System administrator (if system changes required)
- Incident Commander (monitoring, may not actively direct)

**Communication:**
- Email updates to security team
- Management summary report
- No executive escalation unless reclassified

**Documentation:**
- Incident ticket with standard fields
- Timeline (daily granularity acceptable)
- Remediation actions documented

### 5.5 Reclassification Triggers

**Upgrade to SEV-2:**
- Investigation reveals >100 records exposed
- PII discovered in initially assessed "non-sensitive" data
- Evidence of successful unauthorized access
- Related incidents suggest coordinated campaign

**Downgrade to SEV-4:**
- Confirmed false positive
- No actual security control failure
- Duplicate report of already-addressed issue

---

## 6. SEV-4: Low Severity Incidents

### 6.1 Definition
Minimal risk incidents, policy violations without security impact, or confirmed false positives. Standard ticketing process, no emergency response required.

### 6.2 Severity Criteria (ANY of the following)

**Security Events:**
- [ ] Confirmed false positive from security tools
- [ ] Policy violation with no data exposure
- [ ] Security awareness test (simulated phishing)
- [ ] Expired certificate or routine maintenance issue

**Compliance:**
- [ ] Minor policy deviation (documented exception)
- [ ] Security hygiene issue (password complexity, outdated software on non-critical system)
- [ ] Informational vulnerability scan finding (low severity)

**User Reports:**
- [ ] Duplicate report of known issue
- [ ] Misclassified incident (not actually security-related)
- [ ] Request for security guidance or training

### 6.3 Examples

**Example 1: False Positive Alert**
- **Scenario:** Intrusion detection system flags legitimate admin activity as suspicious, investigation confirms authorized action
- **Classification:** SEV-4 (false positive)
- **Rationale:** No actual security incident, tool tuning required

**Example 2: Policy Violation (No Impact)**
- **Scenario:** Employee shared non-sensitive document via unapproved cloud service, document contained no confidential information
- **Classification:** SEV-4 (policy violation, no data risk)
- **Rationale:** Training opportunity, no sensitive data exposed

**Example 3: Simulated Phishing Test**
- **Scenario:** Security awareness training phishing simulation, employee reports suspicious email (correct behavior)
- **Classification:** SEV-4 (training event)
- **Rationale:** Expected outcome of security training program

**Example 4: Vulnerability Scan Finding (Low)**
- **Scenario:** Automated scan detects informational SSL/TLS configuration issue on internal system
- **Classification:** SEV-4 (low-severity finding, internal system)
- **Rationale:** No active exploit, internal-only access, standard remediation timeline

### 6.4 Response Requirements

**Timeline:**
- **Detection to Assignment:** 24 hours (next business day)
- **Security Team Review:** Within 48 hours
- **Resolution:** Per standard SLA (typically 7-30 days)
- **Status Update:** Weekly or as needed

**Team Activation:**
- Security analyst or system administrator
- No IRT activation required
- Standard ticket workflow

**Communication:**
- Ticket updates in standard tracking system
- No management escalation
- Summary included in weekly security report

**Documentation:**
- Standard ticket documentation
- Resolution notes for knowledge base
- Trend analysis (if recurring pattern)

### 6.5 Reclassification Triggers

**Upgrade to SEV-3:**
- False positive revealed actual security issue upon deeper investigation
- Pattern of SEV-4 incidents suggests systemic problem
- Related to active SEV-3/2/1 incident

---

## 7. Special Considerations

### 7.1 Biometric Data (Voice Recordings)

**Automatic Classification Rules:**
- ANY exposure of voice recordings = Minimum SEV-2
- >100 voice recordings exposed = SEV-1 (special category data)
- Voice recordings + contact information = SEV-1 (high re-identification risk)

**Rationale:** GDPR Article 9 special category data, high-risk processing, supervisory authority notification likely required.

### 7.2 Cross-Border Data Transfers

**Classification Impact:**
- Incidents affecting EU/EEA resident data escalate one severity level (SEV-3 → SEV-2)
- GDPR notification requirements override standard classification in some cases
- Multiple supervisory authorities may require coordination

### 7.3 Third-Party/Supply Chain Incidents

**Initial Classification:**
- Vendor notification of breach affecting your data: SEV-2 pending assessment
- Vendor service outage (no data exposure): SEV-3 or SEV-4 based on business impact

**Assessment Required:**
- Determine scope of data exposure
- Verify vendor containment and notification
- Assess impact to customers/data subjects

### 7.4 Cumulative Incidents

**Pattern Recognition:**
- Multiple SEV-4 incidents from same source = Potential SEV-3
- Multiple SEV-3 incidents targeting same system = Escalate to SEV-2
- Coordinated attack indicators = Escalate one level

**Example:** Three separate failed login attempts (each SEV-4) from same IP range within 24 hours may indicate coordinated attack (reclassify as SEV-3 for investigation).

---

## 8. Classification Decision Tree

```
START: Security event detected
    |
    v
Is data exposure confirmed or likely?
    |
    +-- NO --> Assess system impact
    |           |
    |           +-- Critical system down (>50%) --> SEV-1
    |           +-- Major disruption (25-50%) --> SEV-2
    |           +-- Minor disruption (<25%) --> SEV-3
    |           +-- No disruption --> SEV-4
    |
    +-- YES --> Assess data type and volume
            |
            v
        Special category data (biometric, health)?
            |
            +-- YES --> SEV-1 (GDPR high-risk)
            |
            +-- NO --> Assess volume
                    |
                    +-- >1,000 records --> SEV-1
                    +-- 100-999 records --> SEV-2
                    +-- <100 records --> SEV-3
                    +-- No records (false positive) --> SEV-4

Additional considerations:
- Active exfiltration? --> Escalate to SEV-1
- Privileged access compromised? --> Escalate to SEV-1
- Media coverage or regulatory inquiry? --> Escalate to SEV-1
- Effective encryption (data unreadable)? --> Downgrade one level
```

---

## 9. Reclassification Protocol

### 9.1 Authority to Reclassify
- **Incident Commander:** Primary authority for all reclassifications
- **Security Lead:** May reclassify SEV-3/4, must consult IC for SEV-1/2
- **DPO:** May escalate based on regulatory assessment

### 9.2 Reclassification Triggers (Escalation)

| Original | New | Trigger |
|----------|-----|---------|
| SEV-2 | SEV-1 | Special category data discovered, volume >1,000, active exfiltration, media coverage |
| SEV-3 | SEV-2 | >100 records exposed, PII confirmed, credential compromise, regulatory inquiry |
| SEV-4 | SEV-3 | False positive revealed actual issue, related to higher-severity incident |

### 9.3 Reclassification Triggers (De-escalation)

| Original | New | Trigger |
|----------|-----|---------|
| SEV-1 | SEV-2 | Scope <1,000 records, no special category data, effective encryption confirmed |
| SEV-2 | SEV-3 | Scope <100 records, no PII, incident contained with minimal impact |
| SEV-3 | SEV-4 | Confirmed false positive, no security impact, duplicate report |

### 9.4 Reclassification Documentation
- Document decision rationale in incident ticket
- Update incident timeline with reclassification timestamp
- Notify IRT and stakeholders of change
- Adjust response procedures to match new severity

---

## 10. Severity-Based Response Matrix

| Element | SEV-1 | SEV-2 | SEV-3 | SEV-4 |
|---------|-------|-------|-------|-------|
| **Response SLA** | 15 min | 1 hour | 4 hours | 24 hours |
| **IRT Activation** | Full team | Core team | Security engineer | Analyst |
| **Executive Notification** | Immediate (phone) | 1 hour (email) | 4 hours (summary) | Weekly report |
| **Status Updates** | Hourly | Every 4 hours | Daily | Weekly |
| **War Room** | Required | As needed | No | No |
| **After-Hours Response** | Immediate | On-call activation | Next business day | Next business day |
| **External Support** | Forensics firm | As needed | No | No |
| **Legal Involvement** | Immediate | Within 2 hours | If data breach | No |
| **Communication Plan** | Full stakeholder | Affected parties | Internal only | Ticket notes |
| **Post-Incident Review** | Mandatory (5 days) | Mandatory (10 days) | Optional | Quarterly trends |

---

## 11. Related Documents

- `INCIDENT-RESPONSE-PLAN.md` - Overall incident response procedures
- `BREACH-NOTIFICATION-PROCEDURE.md` - GDPR compliance and notification
- `INCIDENT-RESPONSE-CHECKLIST.md` - Step-by-step response actions
- `/security/runbooks/` - System-specific incident playbooks
- `DATA-CLASSIFICATION-POLICY.md` - Data sensitivity levels

---

## 12. Approval and Distribution

### Approval Signatures

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Chief Technology Officer | ___________________ | ___________________ | ________ |
| Security Lead | ___________________ | ___________________ | ________ |
| Data Protection Officer | ___________________ | ___________________ | ________ |

### Distribution List
- All Incident Response Team members (controlled copy)
- Security operations team (controlled copy)
- Management (read-only)

---

**Document Classification:** CONFIDENTIAL - INTERNAL USE ONLY
**Retention Period:** 7 years from supersession date
**Next Review Date:** 2026-07-18
