# Data Classification Policy

**Document Version:** 1.0
**Effective Date:** 2026-01-18
**Owner:** Security & Compliance Team
**Review Cycle:** Annual
**Regulatory Framework:** GDPR, SOC 2, CCPA

---

## 1. Purpose

This policy establishes a standardized data classification framework for all data processed, stored, and transmitted by the LiveKit Voice Agent system. The classification system ensures appropriate security controls, regulatory compliance, and risk management aligned with GDPR Article 32 (Security of Processing) and SOC 2 Trust Services Criteria.

---

## 2. Scope

Applies to all data assets within the LiveKit Voice Agent ecosystem including:
- Voice recordings and transcripts
- User and organizational metadata
- System logs and audit trails
- Configuration and credential data
- Third-party service integrations (Recall.ai, Deepgram, Groq, Cartesia, Microsoft Teams)

---

## 3. Classification Levels

### 3.1 PUBLIC
**Definition:** Information approved for unrestricted public disclosure.

**Examples:**
- Marketing materials
- Published documentation
- Public API documentation
- Open-source code repositories

**Handling Requirements:**
- Encryption: Not required (optional for integrity)
- Access Control: None required
- Transmission: Any method permitted
- Storage: No restrictions
- Labeling: "PUBLIC" watermark on documents
- Retention: Per business need
- Disposal: Standard deletion

**Risk Impact if Compromised:** None

---

### 3.2 INTERNAL
**Definition:** Information for internal use that could cause minor inconvenience if disclosed.

**Examples:**
- Internal communications
- Non-sensitive operational data
- General system metrics
- Internal documentation

**Handling Requirements:**
- Encryption: TLS 1.3 for transmission
- Access Control: Authenticated users only
- Transmission: Encrypted channels
- Storage: Standard file permissions
- Labeling: "INTERNAL USE ONLY" header
- Retention: 1 year default
- Disposal: Secure deletion (single-pass overwrite)

**Risk Impact if Compromised:** Low - Minor operational disruption

---

### 3.3 CONFIDENTIAL
**Definition:** Sensitive information requiring protection under contractual, regulatory, or business obligations. Unauthorized disclosure could cause significant harm.

**GDPR Mapping:** Personal Data (Article 4.1)
**SOC 2 Criteria:** CC6.1 (Logical Access), CC6.6 (Encryption)

**Examples:**
- User transcripts and conversation data
- User metadata (names, emails, Teams IDs)
- Customer organization data
- Business analytics and usage patterns
- Audit logs
- Vendor contracts

**Handling Requirements:**

**Encryption:**
- At Rest: AES-256 encryption mandatory
- In Transit: TLS 1.3 with mutual TLS for API calls
- Database: Column-level encryption for PII fields

**Access Control:**
- Role-Based Access Control (RBAC) required
- Principle of least privilege
- Multi-factor authentication (MFA) mandatory
- Access logged and monitored
- Annual access reviews

**Transmission:**
- Encrypted API calls only
- VPN or private network for internal transfers
- No email transmission without encryption
- Cross-border transfers: Standard Contractual Clauses (SCCs)

**Storage:**
- Encrypted databases (Supabase with encryption at rest)
- Geographically appropriate data centers (EU data in EU regions)
- Backup encryption mandatory
- No storage on portable devices

**Labeling:**
- "CONFIDENTIAL" header/footer on documents
- Metadata tags in database records
- File naming convention: `CONF_<filename>`

**Retention:**
- Default: 90 days from last use
- Maximum: As per RETENTION-SCHEDULE.md
- Deletion: GDPR Article 17 (Right to Erasure) triggers

**Disposal:**
- Secure deletion with cryptographic erasure
- Database: Multi-pass overwrite (DoD 5220.22-M standard)
- Logs: Anonymization before archival
- Physical media: Destruction certificate required

**Risk Impact if Compromised:** High - Regulatory fines, reputational damage, customer churn

---

### 3.4 RESTRICTED
**Definition:** Highly sensitive data requiring maximum protection. Unauthorized disclosure could result in severe legal, financial, or operational consequences.

**GDPR Mapping:** Special Category Data (Article 9 - Biometric Data)
**Legal Requirements:** Explicit consent, data minimization, purpose limitation

**Examples:**
- Voice recordings (biometric identifiers under GDPR)
- API keys and credentials
- Encryption keys
- Authentication tokens
- Consent records with legal signatures
- Financial data
- Security vulnerability reports

**Handling Requirements:**

**Encryption:**
- At Rest: AES-256-GCM with hardware security modules (HSM)
- In Transit: TLS 1.3 with certificate pinning
- Voice recordings: End-to-end encryption from capture to deletion
- Keys: Vault-managed with automatic rotation

**Access Control:**
- Named individual authorization required
- Just-in-Time (JIT) access provisioning
- Time-limited access (max 8 hours)
- Manager approval + security team review
- Biometric or hardware token authentication
- All access generates audit event
- Real-time anomaly detection

**Transmission:**
- Dedicated encrypted channels
- No cross-border transfer without explicit consent + SCCs
- Data Loss Prevention (DLP) monitoring
- Tokenization for external systems

**Storage:**
- Dedicated encrypted partitions
- Geographic restrictions enforced
- Air-gapped backups for credentials
- Hardware security modules for keys
- No cloud storage without customer-managed encryption keys (CMEK)

**Labeling:**
- "RESTRICTED - BIOMETRIC DATA" for voice recordings
- "RESTRICTED - CONFIDENTIAL" for credentials
- Red background watermark on documents
- Database: `classification='RESTRICTED'` tag

**Retention:**
- Voice recordings: 30 days maximum (GDPR minimization)
- Credentials: Until rotation (max 90 days)
- Consent records: 7 years (legal requirement)
- Immediate deletion on consent withdrawal

**Disposal:**
- Voice recordings: Cryptographic erasure + verification
- Credentials: Immediate revocation + key rotation
- Physical media: Certified destruction (NIST 800-88 standards)
- Audit trail of disposal retained for 7 years

**Risk Impact if Compromised:** Critical - Regulatory sanctions (GDPR fines up to 4% revenue), legal liability, complete loss of customer trust, business continuity risk

---

## 4. Classification Decision Tree

```
START
  |
  ├─ Is data publicly available? → YES → PUBLIC
  |
  ├─ Contains biometric data (voice) or credentials? → YES → RESTRICTED
  |
  ├─ Contains PII or customer data? → YES → CONFIDENTIAL
  |
  ├─ Internal business use only? → YES → INTERNAL
  |
  └─ Default → INTERNAL (escalate for review)
```

---

## 5. Cross-Classification Rules

**Data Aggregation:**
- Multiple CONFIDENTIAL data points → RESTRICTED if re-identification possible
- RESTRICTED + PUBLIC → RESTRICTED (highest classification wins)

**Derived Data:**
- Anonymized transcripts (no PII) → CONFIDENTIAL (maintain original classification until verified)
- Statistical aggregates (>50 users) → INTERNAL

**Temporary Elevation:**
- Data under active investigation → Elevate one level
- Data subject to legal hold → RESTRICTED regardless of content

---

## 6. Labeling Standards

### 6.1 Document Labeling
- Header: `[CLASSIFICATION] - Document Title`
- Footer: `Classification: [LEVEL] | Review Date: [DATE]`
- Watermark: For CONFIDENTIAL and RESTRICTED

### 6.2 Database Labeling
Required metadata fields:
```json
{
  "classification": "RESTRICTED",
  "data_category": "biometric",
  "retention_date": "2026-02-18",
  "legal_basis": "consent",
  "consent_id": "uuid",
  "geographic_restriction": "EU"
}
```

### 6.3 Email Labeling
Subject line prefix: `[RESTRICTED]` or `[CONFIDENTIAL]`

---

## 7. Transmission Requirements

| Classification | Email | API | Physical | Cross-Border |
|----------------|-------|-----|----------|--------------|
| PUBLIC | Allowed | Allowed | Allowed | Allowed |
| INTERNAL | Encrypted only | TLS 1.3 | Tracked | Allowed |
| CONFIDENTIAL | Encrypted + DLP | TLS 1.3 + mTLS | Courier + tracking | SCCs required |
| RESTRICTED | Prohibited | TLS 1.3 + mTLS + tokenization | Prohibited | Explicit consent + SCCs + encryption |

---

## 8. Storage Requirements

### 8.1 Geographic Restrictions
- EU user data: Must remain in EU data centers (GDPR Article 44)
- Voice recordings: Same region as data subject
- Exception: With explicit consent + SCCs (Schrems II compliance)

### 8.2 Retention Enforcement
- Automated deletion workflows (n8n scheduled triggers)
- Daily retention sweeps for RESTRICTED data
- Weekly for CONFIDENTIAL
- Deletion verification audit trail

### 8.3 Backup Requirements
| Classification | Backup Frequency | Backup Encryption | Retention |
|----------------|------------------|-------------------|-----------|
| PUBLIC | Optional | Not required | 30 days |
| INTERNAL | Daily | AES-256 | 30 days |
| CONFIDENTIAL | Daily | AES-256 + separate key | 90 days |
| RESTRICTED | Real-time replication | AES-256-GCM + HSM | 30 days |

---

## 9. Disposal Procedures

### 9.1 RESTRICTED Data Disposal
1. Identify records for deletion (retention schedule or consent withdrawal)
2. Generate disposal ticket with approver
3. Execute cryptographic erasure
4. Overwrite storage blocks (3-pass DoD standard)
5. Verify deletion with hash comparison
6. Document in disposal log with timestamp, operator, verification hash
7. Retain disposal record for 7 years

**Voice Recording Disposal Protocol:**
```
1. User consent withdrawal OR 30-day retention expiry
2. Generate disposal event: {user_id, recording_id, reason, timestamp}
3. Execute: DELETE FROM recordings WHERE id = <id>
4. Trigger: Cryptographic key destruction (rendering encrypted data unrecoverable)
5. Verify: Query returns zero records
6. Log: Audit trail entry with verification hash
7. Notify: Data protection officer if consent-triggered
```

### 9.2 CONFIDENTIAL Data Disposal
- Secure deletion (single-pass overwrite)
- Anonymization option for analytics (if business need)
- Deletion log retained for 1 year

### 9.3 INTERNAL/PUBLIC Data Disposal
- Standard deletion
- Optional recycling bin retention

---

## 10. Reclassification

**Triggers for Reclassification:**
- Data minimization (PII removed → downgrade)
- Aggregation (individual → statistical)
- Regulatory change
- Business need change
- Security incident

**Process:**
1. Submit reclassification request to Data Protection Officer
2. Document justification
3. Security review
4. Update metadata tags
5. Apply new handling requirements
6. Notify affected users if downgrading protection

---

## 11. Compliance Mapping

### 11.1 GDPR Compliance
| Requirement | Implementation |
|-------------|----------------|
| Article 5(1)(c) - Data Minimization | 30-day retention for voice recordings |
| Article 5(1)(e) - Storage Limitation | Automated retention enforcement |
| Article 9 - Special Category Data | RESTRICTED classification for biometric |
| Article 25 - Privacy by Design | Classification required before processing |
| Article 32 - Security | Encryption mandatory for CONFIDENTIAL+ |

### 11.2 SOC 2 Trust Services Criteria
| Criteria | Implementation |
|----------|----------------|
| CC6.1 - Logical Access | RBAC for CONFIDENTIAL, JIT for RESTRICTED |
| CC6.6 - Encryption | AES-256 at rest, TLS 1.3 in transit |
| CC6.7 - Key Management | Vault with automatic rotation |
| CC7.2 - Monitoring | Real-time access logging for RESTRICTED |
| A1.2 - Data Classification | This policy + DATA-INVENTORY.md |

---

## 12. Roles and Responsibilities

**Data Owner:**
- Assign initial classification
- Approve access requests for RESTRICTED data
- Annual classification review

**Data Protection Officer:**
- Policy enforcement
- Reclassification approvals
- Incident response for data breaches

**Security Team:**
- Technical controls implementation
- Access monitoring
- Disposal verification

**All Employees:**
- Adhere to handling requirements
- Report misclassification
- Complete annual training

---

## 13. Training Requirements

- Annual data classification training (mandatory)
- RESTRICTED data handling certification for authorized personnel
- Incident response drills (quarterly)

---

## 14. Policy Violations

**Consequences:**
- Minor (incorrect labeling): Retraining
- Moderate (transmission violation): Written warning + access suspension
- Major (unauthorized RESTRICTED access): Termination + legal review
- All violations logged and reported to DPO

---

## 15. Policy Review and Updates

- Annual review cycle
- Triggered review on regulatory change
- Version control with change log
- All updates communicated to stakeholders within 30 days

---

## 16. Related Documents

- `DATA-INVENTORY.md` - Complete data catalog
- `DATA-FLOW-DIAGRAM.md` - System architecture with classification labels
- `RETENTION-SCHEDULE.md` - Retention periods by data type
- `INCIDENT-RESPONSE.md` - Breach procedures
- `GDPR-COMPLIANCE.md` - GDPR article mapping

---

## 17. Approval

**Approved by:**
- Chief Information Security Officer (CISO): ________________
- Data Protection Officer (DPO): ________________
- Legal Counsel: ________________

**Date:** 2026-01-18

**Next Review:** 2027-01-18

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-18 | Security Team | Initial policy creation for LiveKit Voice Agent system |
