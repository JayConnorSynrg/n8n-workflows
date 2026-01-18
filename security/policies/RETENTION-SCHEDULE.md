# Data Retention Schedule

**Document Version:** 1.0
**Effective Date:** 2026-01-18
**Owner:** Data Protection Officer & Legal Compliance
**Review Cycle:** Annual (triggered by regulatory changes)
**Regulatory Framework:** GDPR Article 5(1)(e), CCPA, SOC 2, Industry Standards

---

## 1. Purpose

This schedule defines retention periods for all data types processed by the LiveKit Voice Agent system to ensure:
- **GDPR Compliance:** Storage limitation principle (Article 5(1)(e)) - data kept no longer than necessary
- **SOC 2 Compliance:** Audit trail requirements (CC7.2 - 1 year minimum)
- **Legal Defense:** Statute of limitations for claims (7 years for GDPR complaints)
- **Data Minimization:** Reduce privacy risk and storage costs
- **Business Continuity:** Balance operational needs with privacy obligations

---

## 2. Retention Framework

### 2.1 Guiding Principles

1. **Necessity Test:** Retention justified by specific business or legal need
2. **Minimization Default:** Shortest period that satisfies purpose
3. **Automated Enforcement:** Scheduled deletion workflows (no manual intervention)
4. **Deletion Verification:** Cryptographic proof of erasure for RESTRICTED data
5. **User Rights:** GDPR Article 17 (Right to Erasure) overrides retention periods
6. **Legal Hold:** Litigation/investigation suspends automated deletion

### 2.2 Retention Categories

| Category | Definition | Minimum | Maximum | Justification Source |
|----------|------------|---------|---------|---------------------|
| **Transactional** | Real-time processing data | None | 24 hours | Operational necessity |
| **Operational** | Business activity data | 30 days | 90 days | Service delivery need |
| **Compliance** | Regulatory audit trails | 1 year | 7 years | Legal requirement |
| **Archival** | Historical records (anonymized) | 1 year | Indefinite | Business intelligence |

---

## 3. Retention Schedule by Data Type

### 3.1 RESTRICTED Data

#### Voice Recordings (Biometric Data)

| Attribute | Value |
|-----------|-------|
| **Classification** | RESTRICTED |
| **GDPR Category** | Special Category Data (Article 9 - Biometric) |
| **Retention Period** | **30 days** from recording date |
| **Legal Basis** | Explicit Consent (Article 6(1)(a) + Article 9(2)(a)) |
| **Business Justification** | Dispute resolution, quality assurance, transcription error correction |
| **Regulatory Driver** | GDPR Article 5(1)(c) - Data Minimization |
| **Deletion Method** | Cryptographic erasure (key destruction) + 3-pass overwrite (DoD 5220.22-M) |
| **Deletion Trigger** | Automated (daily retention sweep at 00:00 UTC) |
| **User Override** | Consent withdrawal → Immediate deletion (within 24 hours) |
| **Legal Hold** | Suspended deletion, segregated storage, DPO notification |
| **Verification** | Deletion hash logged in audit trail, quarterly compliance audit |

**Retention Justification Analysis:**

**Why 30 days?**
- **Technical Need:** Transcription errors may require re-processing (average detection: 7 days)
- **Support Need:** User disputes about conversation content (average ticket resolution: 14 days)
- **Privacy Impact:** Voice data is highest-risk biometric identifier
- **Industry Benchmark:** Call center compliance standards (15-30 days typical)
- **GDPR Minimization:** Shortest period balancing operational need vs. privacy risk

**Alternatives Considered:**
- 7 days: Insufficient for support ticket resolution
- 60 days: Excessive for biometric data (fails proportionality test)
- 90 days: Only justified for highly regulated industries (finance, healthcare) - not applicable

**Cross-Border Impact:**
- EU users: 30 days enforced strictly
- US users: Same standard (no state law requires longer retention for non-financial voice data)

**Deletion Workflow:**
```sql
-- Automated n8n workflow (daily 00:00 UTC)
DELETE FROM recordings
WHERE created_at < NOW() - INTERVAL '30 days'
  AND legal_hold = false
RETURNING recording_id, user_id, deletion_timestamp;

-- Cascade to related tables
DELETE FROM recording_metadata WHERE recording_id IN (deleted_ids);

-- Cryptographic erasure (separate process)
EXECUTE destroy_encryption_keys(deleted_ids);

-- Audit log entry
INSERT INTO audit_logs (action, resource_type, resource_ids, verification_hash, timestamp)
VALUES ('deletion', 'voice_recording', deleted_ids, SHA256(deleted_ids), NOW());
```

---

#### Consent Records

| Attribute | Value |
|-----------|-------|
| **Classification** | RESTRICTED |
| **GDPR Category** | Personal Data (Article 4.1) |
| **Retention Period** | **7 years** from consent date (active consent) <br/> **7 years** from withdrawal date (withdrawn consent) |
| **Legal Basis** | Legal Obligation (Article 6(1)(c)) - GDPR accountability |
| **Business Justification** | Demonstrate compliance with Article 7 (Conditions for consent) |
| **Regulatory Driver** | GDPR Article 7(1) - Controller must demonstrate consent <br/> Statute of limitations for GDPR complaints (varies by EU member state, 7 years maximum) |
| **Deletion Method** | Secure deletion (cannot use cryptographic erasure - must prove consent) <br/> Archival to immutable append-only storage |
| **Deletion Trigger** | Manual review after 7 years (annual compliance audit) |
| **User Override** | None - Legal obligation overrides Right to Erasure (Article 17(3)(b)) |
| **Legal Hold** | Already maximum retention, no suspension needed |
| **Verification** | Annual audit by DPO + external compliance auditor |

**Retention Justification Analysis:**

**Why 7 years?**
- **Legal Defense:** GDPR complaints statute of limitations (3-7 years depending on EU member state)
- **Regulatory Audits:** Supervisory authorities may request historical consent records
- **Best Practice:** SOC 2 Type II requires 1 year minimum, extended to 7 for legal certainty
- **Article 7 Requirement:** "Controller shall be able to demonstrate that the data subject has consented"

**What is Stored:**
- Consent grant timestamp, IP address (hashed), user agent, consent version
- Consent withdrawal timestamp (if applicable)
- Legal signature (encrypted) if explicit consent (voice recording)

**What is NOT Stored:**
- Full consent form text (reference to versioned policy document instead)
- PII beyond user_id (minimal data principle)

**Immutability Requirement:**
- Consent records cannot be modified (append-only log)
- Blockchain-style hash chaining for tamper detection
- Quarterly integrity verification

---

#### API Keys and Credentials

| Attribute | Value |
|-----------|-------|
| **Classification** | RESTRICTED |
| **GDPR Category** | Not Personal Data (organizational credentials) |
| **Retention Period** | **Until rotation** (maximum 90 days per key version) |
| **Legal Basis** | N/A (non-personal data) |
| **Business Justification** | Service integration, security access control |
| **Security Driver** | NIST 800-63B (credential rotation), SOC 2 CC6.1 |
| **Deletion Method** | Immediate revocation + key rotation + audit log |
| **Deletion Trigger** | Automated rotation (90 days) OR manual revocation (security incident) |
| **Audit Requirement** | All key access logged (real-time monitoring) |
| **Storage** | HashiCorp Vault (encrypted, access-controlled) |
| **Backup Retention** | Previous key version: 30 days (grace period for rotation issues) |

**Rotation Schedule:**

| Credential Type | Rotation Frequency | Automation | Grace Period |
|----------------|-------------------|------------|--------------|
| OpenAI API Key | 90 days | Yes (Vault auto-rotation) | 7 days overlap |
| Deepgram API Key | 90 days | Yes | 7 days overlap |
| Groq API Key | 90 days | Yes | 7 days overlap |
| Cartesia API Key | 90 days | Yes | 7 days overlap |
| Recall.ai API Key | 90 days | Manual (vendor limitation) | 14 days overlap |
| LiveKit API Secret | 90 days | Yes | 7 days overlap |
| Railway Database Password | 90 days | Yes | Immediate (connection pool) |
| Supabase Service Role Key | 90 days | Manual (requires app restart) | 7 days overlap |
| n8n Webhook Secrets | 180 days | Manual | 30 days overlap |

**Emergency Revocation:**
- Security incident: Immediate revocation (< 1 hour)
- Suspected leak: Revoke + rotate within 4 hours
- Employee offboarding: Revoke all JIT credentials within 1 hour

---

### 3.2 CONFIDENTIAL Data

#### Transcripts

| Attribute | Value |
|-----------|-------|
| **Classification** | CONFIDENTIAL |
| **GDPR Category** | Personal Data (Article 4.1) |
| **Retention Period** | **90 days** from transcript generation date |
| **Legal Basis** | Consent (Article 6(1)(a)) |
| **Business Justification** | Conversation history for context, analytics, user-requested summaries |
| **Regulatory Driver** | GDPR Article 5(1)(e) - Storage limitation with business need balance |
| **Deletion Method** | Secure deletion (single-pass overwrite) OR anonymization (PII removal) |
| **Deletion Trigger** | Automated (weekly retention sweep every Sunday 00:00 UTC) |
| **User Override** | Consent withdrawal → Immediate deletion <br/> GDPR Right to Erasure → 30-day deletion |
| **Legal Hold** | Suspended deletion, flagged in database (`legal_hold = true`) |
| **Anonymization Option** | After 90 days: Remove PII → downgrade to INTERNAL (analytics use) |

**Retention Justification Analysis:**

**Why 90 days vs. 30 days (voice recordings)?**
- **Privacy Risk:** Transcripts lack biometric data (lower risk than voice)
- **Business Need:** Users reference past conversations for continuity (average: 45 days)
- **Analytics Value:** Conversation pattern analysis requires 60-90 day window
- **Re-identification Risk:** Lower than voice (text alone insufficient for unique identification)

**Proportionality Test:**
- Risk: MEDIUM (text PII, no biometric)
- Business Value: MEDIUM-HIGH (conversation context, product improvement)
- Data Subject Impact: LOW (users expect conversation history)
- **Conclusion:** 90 days proportional and justified

**Anonymization Workflow (Optional):**
```sql
-- After 90 days, anonymize instead of delete for analytics
UPDATE transcripts
SET
  user_id = NULL,
  speaker_labels = ARRAY_REPLACE(speaker_labels, user_name, 'Speaker A'),
  text_content = anonymize_pii(text_content),  -- Remove names, emails, phone numbers
  classification = 'INTERNAL'
WHERE created_at < NOW() - INTERVAL '90 days'
  AND anonymized = false
  AND legal_hold = false;
```

**Anonymization Criteria (if pursued):**
- k-anonymity: Minimum 50 transcripts per aggregation
- Remove: Names, emails, phone numbers, company names, locations
- Retain: Conversation structure, topics, sentiment, language
- Use Case: Product analytics (e.g., "30% of conversations mention pricing questions")

---

#### User Metadata

| Attribute | Value |
|-----------|-------|
| **Classification** | CONFIDENTIAL |
| **GDPR Category** | Personal Data (Article 4.1) |
| **Retention Period** | **Account lifetime** + 30-day grace period after account deletion request |
| **Legal Basis** | Contract (Article 6(1)(b)) - Necessary for service delivery |
| **Business Justification** | User authentication, personalization, support |
| **Regulatory Driver** | GDPR Article 17 (Right to Erasure) - deletion on request |
| **Deletion Method** | Cascade deletion across all tables + audit log entry |
| **Deletion Trigger** | User-initiated account deletion OR 2 years of inactivity (abandoned accounts) |
| **User Override** | GDPR Right to Erasure → Immediate processing (30-day completion) |
| **Legal Hold** | Suspended deletion, user notified of legal obligation to retain |
| **Grace Period Justification** | 30 days allows recovery from accidental deletion requests |

**Inactive Account Policy:**

| Inactivity Period | Action | Notification |
|-------------------|--------|--------------|
| 12 months | Email warning: "Account inactive, will be deleted in 12 months" | Sent quarterly |
| 18 months | Email warning: "Account deletion in 6 months" | Sent monthly |
| 23 months | Final email: "Account deletion in 30 days" | Sent weekly |
| 24 months | Account deletion scheduled | Confirmation email |
| 24 months + 30 days | Permanent deletion | No notification (account deleted) |

**Deletion Workflow:**
```sql
-- User-initiated deletion request
UPDATE users SET deletion_requested_at = NOW() WHERE user_id = ?;

-- 30-day grace period (user can cancel)
-- After 30 days (automated job):
DELETE FROM users WHERE deletion_requested_at < NOW() - INTERVAL '30 days';

-- Cascade deletions (foreign key constraints):
-- - transcripts (linked to user_id)
-- - session_data (linked to user_id)
-- - analytics (anonymize instead of delete)
-- - consent_records (RETAIN - legal obligation, but mark user as deleted)

-- Audit log
INSERT INTO audit_logs (action, user_id, timestamp, verification_hash)
VALUES ('account_deletion', ?, NOW(), SHA256(?));
```

**What is Deleted:**
- Email, display name, timezone, language preference
- Transcripts, session data, preferences

**What is RETAINED (Legal Obligation):**
- Consent records (7 years)
- Audit logs (1 year active, 7 years anonymized)
- Financial records if applicable (7 years for tax purposes)

---

#### Audit Logs

| Attribute | Value |
|-----------|-------|
| **Classification** | CONFIDENTIAL |
| **GDPR Category** | Personal Data (Article 4.1) - contains user_id, IP addresses |
| **Retention Period** | **Active logs: 1 year** <br/> **Anonymized archives: 7 years** |
| **Legal Basis** | Legitimate Interest (Article 6(1)(f)) - Security monitoring outweighs privacy impact |
| **Business Justification** | Security incident response, SOC 2 audit trail, fraud detection |
| **Regulatory Driver** | SOC 2 CC7.2 - 1 year minimum for audit trails <br/> GDPR breach investigation - 7 years statute of limitations |
| **Deletion Method** | Active logs: Purge after 1 year <br/> Archives: Anonymize (remove user_id, hash IP) |
| **Deletion Trigger** | Automated (monthly archival job) |
| **User Override** | None - Legitimate interest overrides Right to Erasure (Article 17(3)(f)) |
| **Legal Hold** | Suspended deletion for logs related to investigation |

**Retention Tiers:**

| Log Age | Storage | PII Status | Use Case |
|---------|---------|------------|----------|
| 0-90 days | Hot storage (PostgreSQL) | Full PII | Real-time security monitoring, active incident response |
| 91-365 days | Warm storage (compressed) | Full PII | Historical analysis, SOC 2 audits, quarterly reviews |
| 1-7 years | Cold storage (S3 Glacier) | Anonymized | Legal defense, regulatory audits, pattern analysis |
| >7 years | Deleted | N/A | No retention beyond statute of limitations |

**Anonymization Process (After 1 Year):**
```sql
-- Move to archive table with anonymization
INSERT INTO audit_logs_archive (
  log_id,
  timestamp,
  actor_id_hash,  -- SHA256(actor_id) - cannot reverse
  action,
  resource_type,
  result,
  ip_hash,  -- SHA256(ip_address)
  metadata_sanitized  -- Remove PII from JSONB field
)
SELECT
  log_id,
  timestamp,
  SHA256(actor_id),
  action,
  resource_type,
  result,
  SHA256(ip_address),
  sanitize_metadata(metadata)
FROM audit_logs
WHERE timestamp < NOW() - INTERVAL '1 year';

-- Delete original (PII) logs
DELETE FROM audit_logs WHERE timestamp < NOW() - INTERVAL '1 year';
```

**Legal Basis for Retention (Legitimate Interest Assessment):**
- **Purpose:** Security monitoring, fraud prevention, regulatory compliance
- **Necessity:** Cannot achieve security without audit logs
- **Balancing Test:** Security interest outweighs privacy impact (logs are metadata, not sensitive content)
- **Safeguards:** Anonymization after 1 year, access controls, automated analysis (minimal human review)

---

#### Session Data

| Attribute | Value |
|-----------|-------|
| **Classification** | CONFIDENTIAL |
| **GDPR Category** | Personal Data (Article 4.1) |
| **Retention Period** | **24 hours** from session end (or 48 hours if session still active) |
| **Legal Basis** | Consent (Article 6(1)(a)) |
| **Business Justification** | Active call management, real-time monitoring, connection troubleshooting |
| **Regulatory Driver** | GDPR Article 5(1)(c) - Data minimization (ephemeral data) |
| **Deletion Method** | Automatic Redis TTL expiration (no manual deletion needed) |
| **Deletion Trigger** | Redis TTL = 24 hours (automatic) |
| **User Override** | Session end → Immediate expiration (TTL set to 5 minutes) |
| **Legal Hold** | Not applicable (ephemeral data expires before legal hold possible) |

**Data Stored:**
- Session ID, user ID, LiveKit room ID, Teams meeting ID
- Connection metadata (IP address, latency, audio quality)
- Participant list (real-time only)

**Storage Technology:**
- Redis cache (in-memory, not persisted to disk)
- TTL automatically enforced (no scheduled jobs needed)
- No backups (intentionally ephemeral)

**Why 24 hours?**
- Typical meeting duration: 1-2 hours
- Edge case (all-day workshop): 8 hours
- Grace period for reconnection issues: 16 hours
- **Total: 24 hours balances operational need with privacy**

---

#### Analytics/Metrics

| Attribute | Value |
|-----------|-------|
| **Classification** | CONFIDENTIAL (detailed) → INTERNAL (aggregated) |
| **GDPR Category** | Pseudonymized Personal Data (Article 4.5) |
| **Retention Period** | **Detailed (pseudonymized): 30 days** <br/> **Aggregated (anonymized): 1 year** |
| **Legal Basis** | Legitimate Interest (Article 6(1)(f)) - Product improvement with privacy safeguards |
| **Business Justification** | Service quality monitoring, product analytics, capacity planning |
| **Regulatory Driver** | GDPR Recital 26 - Anonymized data not subject to GDPR |
| **Deletion Method** | Detailed: Purge after 30 days <br/> Aggregated: Retain indefinitely (no PII) |
| **Deletion Trigger** | Automated (daily aggregation job + cleanup) |
| **User Override** | Right to Erasure removes user from detailed logs, aggregates unaffected |
| **Anonymization Threshold** | k-anonymity: Minimum 50 users per aggregate |

**Data Lifecycle:**

```
Day 0-30: Detailed Metrics (CONFIDENTIAL)
  - user_id: hashed (SHA256 + salt)
  - event_type: call_started, transcript_generated
  - timestamp: exact time
  - duration: seconds
  - quality_score: 0-1

Day 30-365: Aggregated Metrics (INTERNAL)
  - time_window: hourly/daily/weekly
  - event_count: integer
  - avg_duration: seconds
  - avg_quality: 0-1
  - user_count: >50 (k-anonymity)
  - user_ids: REMOVED

Day 365+: Historical Trends (PUBLIC potential)
  - Monthly aggregates only
  - No linkage to individual users possible
```

**Legitimate Interest Assessment:**
- **Purpose:** Product improvement, bug detection, capacity planning
- **Necessity:** Cannot optimize service without usage data
- **Balancing Test:** Business interest vs. low privacy impact (pseudonymized, aggregated)
- **Safeguards:** Pseudonymization, 30-day detailed retention, k-anonymity aggregation
- **Transparency:** Privacy policy discloses analytics use
- **Opt-Out:** Users can object (Article 21) → exclude from analytics entirely

---

### 3.3 Special Retention Scenarios

#### Legal Hold

**Trigger Events:**
- Litigation filed or threatened
- Regulatory investigation initiated
- GDPR complaint filed with supervisory authority
- Internal investigation (fraud, security breach)

**Process:**
1. Legal/Compliance team issues legal hold notice
2. DPO identifies affected data (by user, date range, data type)
3. Database flag: `legal_hold = true` for affected records
4. Automated deletion workflows SKIP flagged records
5. Segregated storage (access restricted to legal team + DPO)
6. Monthly review of legal hold status
7. Release: Legal team authorizes, DPO removes flag, normal retention resumes

**Documentation:**
- Legal hold register (case name, affected data, hold date, release date)
- Audit log entry for each hold/release action
- Annual compliance review

---

#### GDPR Right to Erasure (Article 17)

**User Request Process:**
1. User submits erasure request (email, support ticket, in-app form)
2. Identity verification (MFA, email confirmation)
3. DPO reviews for valid grounds (consent withdrawal, no legal basis, etc.)
4. Legal team reviews for exceptions (Article 17(3) - legal claims, compliance)
5. If approved: Execute deletion within 30 days
6. Notify user of completion + provide deletion certificate

**Deletion Scope:**

| Data Type | Action | Timeline | Exception |
|-----------|--------|----------|-----------|
| Voice Recordings | Delete + cryptographic erasure | 24 hours | Legal hold |
| Transcripts | Delete | 7 days | Legal hold |
| User Metadata | Delete | 30 days | None |
| Consent Records | RETAIN (legal obligation) | N/A | Article 17(3)(b) |
| Audit Logs | Anonymize user_id | 30 days | Article 17(3)(f) |
| Session Data | Expire immediately | 1 hour | None |
| Analytics (detailed) | Remove user_id | 7 days | None |
| Analytics (aggregated) | No action (anonymous) | N/A | Already anonymous |

**Deletion Certificate (Provided to User):**
```
GDPR ERASURE CERTIFICATE

User ID: [redacted]
Request Date: 2026-01-18
Completion Date: 2026-02-17

Data Deleted:
- Voice Recordings: 12 files (verification hash: 0x...)
- Transcripts: 42 records
- User Profile: Complete
- Session Data: Expired
- Analytics: Pseudonymized ID removed

Data Retained (Legal Obligation):
- Consent Records: 7-year retention (Article 17(3)(b))
- Audit Logs: Anonymized (Article 17(3)(f))

Verification:
- Deletion Method: Cryptographic erasure (voice), secure deletion (other)
- Verification Hash: SHA256(deleted_record_ids)
- Compliance Officer: [DPO Name]

This certificate confirms compliance with GDPR Article 17.
```

---

#### Data Breach Retention

**Incident Data Retention:**
- Breach investigation records: 7 years
- Affected data snapshots (forensic copies): Until investigation closed + 7 years
- Notification records (to authority, users): 7 years
- Remediation documentation: 7 years

**Justification:**
- GDPR Article 33(5) - Document all data breaches
- Statute of limitations for claims
- Regulatory audit requirements

---

## 4. Retention Enforcement Mechanisms

### 4.1 Automated Deletion Workflows

**Daily Jobs (00:00 UTC):**
```javascript
// n8n scheduled workflow: Voice Recording Cleanup
- Query: SELECT * FROM recordings WHERE created_at < NOW() - INTERVAL '30 days' AND legal_hold = false
- For each record:
  - Execute cryptographic erasure (destroy encryption keys)
  - Delete database record
  - Cascade to metadata tables
  - Log deletion in audit trail
  - Verify deletion (query returns 0 rows)
- Send summary to DPO (records deleted, errors)
```

**Weekly Jobs (Sunday 00:00 UTC):**
```javascript
// n8n scheduled workflow: Transcript Cleanup
- Query: SELECT * FROM transcripts WHERE created_at < NOW() - INTERVAL '90 days' AND legal_hold = false
- Option A: Delete
  - Execute secure deletion
  - Log in audit trail
- Option B: Anonymize (if analytics needed)
  - Remove PII (user_id, names, emails, phone numbers)
  - Downgrade classification to INTERNAL
  - Log anonymization action
```

**Monthly Jobs (1st day 00:00 UTC):**
```javascript
// n8n scheduled workflow: Audit Log Archival
- Query: SELECT * FROM audit_logs WHERE timestamp < NOW() - INTERVAL '1 year'
- Anonymize:
  - Hash user_id, IP address
  - Sanitize metadata JSONB field
- Move to archive table (cold storage)
- Delete original records
- Verify archive integrity (row count match)
```

**Quarterly Jobs:**
- Inactive account cleanup (2 years no activity)
- Legal hold review (ensure holds still active)
- Retention compliance audit (manual DPO review)

---

### 4.2 Monitoring and Alerts

**Real-Time Alerts:**
- Legal hold bypassed (deletion attempted on flagged record) → CRITICAL alert to DPO
- Deletion failure (record not removed after 3 attempts) → HIGH alert to Engineering
- Retention policy drift (records older than max retention) → MEDIUM alert to DPO

**Weekly Reports:**
- Records deleted (by data type, count, verification status)
- Legal holds active (case name, data volume, age)
- Retention exceptions (records exceeding policy)

**Quarterly Compliance Dashboard:**
- Retention policy adherence (% records within policy)
- Deletion verification rate (cryptographic proof logged)
- User erasure requests (count, avg response time, completion rate)
- Legal holds (total active, avg duration)

---

### 4.3 Manual Review Requirements

**Annual DPO Review:**
- [ ] Validate retention periods still justified (business need analysis)
- [ ] Review legal hold register (release expired holds)
- [ ] Audit deletion verification logs (sample 5% of cryptographic proofs)
- [ ] Update policy for regulatory changes
- [ ] Train staff on updated policy

**Triggered Reviews:**
- New data type introduced → Assign retention period
- Regulatory guidance update → Assess impact
- Data breach → Review retention of affected data
- Supervisory authority inquiry → Prepare documentation

---

## 5. Cross-Functional Responsibilities

| Team | Responsibility | Frequency |
|------|----------------|-----------|
| **Data Protection Officer** | Policy oversight, compliance audits, erasure request review | Ongoing |
| **Engineering** | Automated deletion workflows, verification mechanisms | Ongoing |
| **Legal** | Legal hold management, statute of limitations tracking | Ongoing |
| **Security** | Cryptographic erasure verification, audit log integrity | Quarterly |
| **Product** | Business justification for retention periods, user communication | Annual |
| **Support** | User erasure request intake, identity verification | Ongoing |

---

## 6. Compliance Mapping

### 6.1 GDPR Article 5(1)(e) - Storage Limitation

> Personal data shall be kept in a form which permits identification of data subjects for no longer than is necessary for the purposes for which the personal data are processed.

**Implementation:**
- Voice recordings: 30 days (shortest period for biometric data)
- Transcripts: 90 days (balanced with business need)
- Consent records: 7 years (legal obligation exception)
- Audit logs: 1 year active, 7 years anonymized (security exception)

**Compliance Evidence:**
- This retention schedule (documented necessity)
- Automated deletion workflows (enforcement)
- Quarterly compliance audits (verification)

---

### 6.2 SOC 2 Trust Services Criteria

**CC7.2 - System Monitoring:**
> The entity monitors the system and takes action to maintain the achievement of the entity's objectives.

**Implementation:**
- Audit logs: 1 year minimum (meets SOC 2 requirement)
- Real-time monitoring for deletion failures
- Quarterly compliance dashboard

**Audit Evidence:**
- Deletion verification logs
- Retention compliance reports
- Incident response records

---

### 6.3 CCPA (California Consumer Privacy Act)

**§1798.105 - Right to Deletion:**
> A consumer shall have the right to request that a business delete any personal information about the consumer.

**Implementation:**
- GDPR Right to Erasure process (30-day response)
- Deletion certificate provided to user
- Exceptions documented (legal obligations, security)

---

## 7. Exceptions and Overrides

### 7.1 Retention Extension (Rare)

**Allowed Scenarios:**
1. **Legal Hold:** Litigation/investigation
2. **Regulatory Request:** Supervisory authority demands retention
3. **User Request:** User explicitly requests extended retention (transcript backup)

**Approval Process:**
1. DPO + Legal review
2. Document justification
3. Set new expiration date
4. Notify user (if applicable)
5. Quarterly review of extensions

**Maximum Extension:** 2x standard retention (e.g., transcripts 90 days → max 180 days)

---

### 7.2 Early Deletion (User Request)

**Allowed Scenarios:**
1. User invokes GDPR Right to Erasure
2. User withdraws consent
3. Security incident (compromised data)

**Process:**
- Immediate processing (no waiting for scheduled job)
- Manual deletion by authorized personnel
- Audit log entry with justification
- Deletion certificate issued

---

## 8. User Communication

### 8.1 Privacy Policy Disclosure

**Required Elements:**
- Retention periods for each data type (table format)
- Justification (legal basis + business need)
- User rights (erasure, portability)
- Contact: DPO email for retention questions

**Example Privacy Policy Language:**

> **Data Retention**
>
> We retain your data only as long as necessary to provide our services and comply with legal obligations:
>
> - **Voice Recordings:** 30 days (quality assurance, dispute resolution)
> - **Transcripts:** 90 days (conversation history, service improvement)
> - **Account Information:** Until account deletion (service delivery)
> - **Consent Records:** 7 years (legal compliance)
> - **Audit Logs:** 1 year (security monitoring)
>
> You may request early deletion of your data at any time by contacting [dpo@example.com]. We will respond within 30 days.

---

### 8.2 Deletion Notifications

**User-Facing Messages:**

**Account Deletion Confirmation:**
> Your account deletion request has been received. Your data will be permanently deleted in 30 days. To cancel this request, log in before [date].

**Deletion Completed:**
> Your data has been permanently deleted. We have removed all personal information as required by law. Consent records are retained for 7 years to demonstrate compliance. [Download Deletion Certificate]

**Inactivity Warning (18 months):**
> Your account has been inactive for 18 months. To prevent deletion, please log in within 6 months. If you no longer use our service, no action is needed.

---

## 9. Audit Trail

### 9.1 Deletion Verification Log

**Required Fields:**
- `deletion_id` (UUID)
- `data_type` (enum: voice_recording, transcript, user_metadata, etc.)
- `resource_ids` (array of deleted record IDs)
- `deletion_method` (enum: cryptographic_erasure, secure_deletion, anonymization)
- `verification_hash` (SHA256 of deleted IDs)
- `triggered_by` (enum: automated_retention, user_request, legal_hold_release)
- `timestamp` (ISO 8601)
- `verification_status` (enum: success, failed, partial)

**Quarterly Audit Process:**
1. DPO samples 5% of deletion log entries
2. Re-query database for deleted IDs (should return 0 rows)
3. Verify cryptographic erasure (encryption keys destroyed)
4. Document findings in compliance report

---

### 9.2 Retention Compliance Metrics

**Key Performance Indicators:**

| Metric | Target | Actual (Q1 2026) | Status |
|--------|--------|------------------|--------|
| Voice recordings within 30-day retention | 100% | TBD | ⏳ Pending |
| Transcripts within 90-day retention | 100% | TBD | ⏳ Pending |
| User erasure requests completed < 30 days | 95% | TBD | ⏳ Pending |
| Deletion verification success rate | 99% | TBD | ⏳ Pending |
| Legal holds reviewed quarterly | 100% | TBD | ⏳ Pending |

**Escalation Triggers:**
- >1% of records exceed retention policy → DPO investigation
- >5% deletion failures → Engineering escalation
- User erasure request >30 days → Legal review

---

## 10. Related Documents

- `DATA-CLASSIFICATION-POLICY.md` - Classification rules (determines retention requirements)
- `DATA-INVENTORY.md` - Complete data catalog (links retention to data types)
- `DATA-FLOW-DIAGRAM.md` - Data lifecycle visualization
- `GDPR-COMPLIANCE.md` - Legal basis and user rights
- `INCIDENT-RESPONSE.md` - Breach notification (retention during investigation)

---

## 11. Policy Review and Updates

**Annual Review Checklist:**
- [ ] Business need still justifies each retention period
- [ ] Regulatory changes (GDPR amendments, new state laws)
- [ ] User feedback on retention periods
- [ ] Technology changes (new storage options, better anonymization)
- [ ] Supervisory authority guidance (EDPB opinions)
- [ ] Industry benchmarks (competitor practices, standards)

**Update Process:**
1. Propose changes (Product, Legal, DPO collaboration)
2. Privacy impact assessment (if extending retention)
3. Legal review (compliance check)
4. Executive approval (if material change)
5. Update policy document + version control
6. Communicate changes to users (privacy policy update)
7. Update automated workflows (engineering)
8. Train staff (annual compliance training)

---

## 12. Approval

**Data Protection Officer:** ________________
**Legal Counsel:** ________________
**Chief Information Security Officer:** ________________

**Date:** 2026-01-18
**Next Review:** 2027-01-18 (Annual)

---

## Appendix: Deletion Method Standards

### A.1 Cryptographic Erasure (RESTRICTED Data)

**Method:** Encryption key destruction renders encrypted data permanently unrecoverable.

**Process:**
1. Identify records for deletion (retention expiry)
2. Retrieve encryption key IDs for affected records
3. Execute key destruction in Vault/HSM
4. Verify key no longer exists (query Vault returns 404)
5. Log destruction event with timestamp + key ID hash
6. Encrypted data remains in database but is now unreadable

**Advantages:**
- Instant (no data overwrite needed)
- Verifiable (key absence provable)
- Complies with GDPR "erasure" (data no longer accessible)

**Standards:** NIST SP 800-88 (cryptographic erasure accepted method)

---

### A.2 Secure Deletion (CONFIDENTIAL Data)

**Method:** DoD 5220.22-M (3-pass overwrite)

**Process:**
1. Overwrite data with random bytes (Pass 1)
2. Overwrite with complement of random bytes (Pass 2)
3. Overwrite with random bytes again (Pass 3)
4. Verify data unrecoverable (forensic sampling)
5. Delete database record

**Use Case:** Transcripts, user metadata (non-biometric data)

---

### A.3 Anonymization (Analytics Retention)

**Method:** Irreversible PII removal + k-anonymity

**Process:**
1. Remove direct identifiers (user_id, email, name, IP)
2. Hash remaining indirect identifiers (session_id → SHA256)
3. Aggregate to minimum 50 users (k-anonymity)
4. Verify re-identification impossible (manual review)
5. Downgrade classification (CONFIDENTIAL → INTERNAL)

**Use Case:** Analytics data requiring longer retention for business intelligence

**GDPR Status:** Anonymized data not subject to GDPR (Recital 26)

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-18 | DPO + Legal | Initial retention schedule for LiveKit Voice Agent system |
