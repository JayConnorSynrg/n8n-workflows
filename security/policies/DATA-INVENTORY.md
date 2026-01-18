# Data Inventory

**Document Version:** 1.0
**Last Updated:** 2026-01-18
**Owner:** Data Protection Officer
**Review Cycle:** Quarterly
**Regulatory Framework:** GDPR Article 30 (Records of Processing Activities), SOC 2 A1.2

---

## 1. Purpose

This inventory catalogs all data types processed by the LiveKit Voice Agent system to ensure:
- GDPR Article 30 compliance (mandatory for organizations processing personal data)
- SOC 2 audit trail for data lifecycle management
- Data minimization principle enforcement
- Privacy impact assessment foundation
- Incident response preparedness

---

## 2. Inventory Summary

**Total Data Categories:** 8
**RESTRICTED Classifications:** 3 (Voice recordings, Consent records, API keys)
**CONFIDENTIAL Classifications:** 4 (Transcripts, User metadata, Audit logs, Session data)
**Cross-Border Transfers:** 4 data types (Voice → US, Transcripts → US, LLM processing → US)
**GDPR Special Category Data:** 1 (Voice recordings - biometric)

---

## 3. Data Inventory Table

| Data Type | Classification | GDPR Category | Source System | Storage Location | Processor | Retention Period | Legal Basis | Cross-Border Transfer | DPA Required |
|-----------|----------------|---------------|---------------|------------------|-----------|------------------|-------------|----------------------|--------------|
| **Voice Recordings** | RESTRICTED | Special Category (Art. 9) - Biometric | Recall.ai Bot | LiveKit Cloud (EU) → Railway Postgres (US backup) | Recall.ai, LiveKit | 30 days | Explicit Consent (Art. 6(1)(a) + Art. 9(2)(a)) | EU → US (SCCs) | Yes - Recall.ai, LiveKit |
| **Transcripts** | CONFIDENTIAL | Personal Data (Art. 4.1) | Deepgram API | Supabase PostgreSQL (EU region) | Deepgram | 90 days | Consent (Art. 6(1)(a)) | EU → US (Deepgram processing) | Yes - Deepgram |
| **User Metadata** | CONFIDENTIAL | Personal Data (Art. 4.1) | Microsoft Teams | Supabase PostgreSQL (EU region) | Microsoft | Account lifetime | Contract (Art. 6(1)(b)) | EU → US (Teams infrastructure) | Yes - Microsoft |
| **Consent Records** | RESTRICTED | Personal Data (Art. 4.1) | Internal (n8n workflow) | Supabase PostgreSQL (EU region) | None (internal) | 7 years | Legal Obligation (Art. 6(1)(c)) | None | No |
| **Audit Logs** | CONFIDENTIAL | Personal Data (Art. 4.1) | Internal (n8n, Railway) | Railway PostgreSQL (US) | Railway | 1 year | Legitimate Interest (Art. 6(1)(f)) | EU → US (storage only) | Yes - Railway |
| **Session Data** | CONFIDENTIAL | Personal Data (Art. 4.1) | LiveKit | Redis (Railway - US) | LiveKit, Railway | 24 hours | Consent (Art. 6(1)(a)) | EU → US | Yes - Railway |
| **API Keys/Credentials** | RESTRICTED | Not Personal Data | n8n Vault | n8n Vault (encrypted) + Railway env vars | n8n | Until rotation (max 90 days) | N/A | None | No |
| **Analytics/Metrics** | CONFIDENTIAL | Pseudonymized Data | Internal aggregation | Supabase PostgreSQL (EU region) | None (internal) | 1 year | Legitimate Interest (Art. 6(1)(f)) | None | No |

---

## 4. Detailed Data Specifications

### 4.1 Voice Recordings (RESTRICTED)

**Data Fields:**
- `recording_id` (UUID)
- `user_id` (Microsoft Teams user ID - pseudonymized)
- `session_id` (UUID)
- `audio_blob` (binary - MP3/WAV)
- `duration_seconds` (integer)
- `timestamp_start` (ISO 8601)
- `timestamp_end` (ISO 8601)
- `consent_id` (foreign key to consent record)

**Processing Activities:**
1. Capture: Recall.ai bot joins Teams call
2. Storage: Temporary LiveKit storage (EU region)
3. Transfer: Encrypted upload to Railway PostgreSQL (US)
4. Processing: Deepgram transcription API (US)
5. Deletion: Cryptographic erasure after 30 days

**GDPR Special Category Justification:**
Voice recordings constitute biometric data under GDPR Article 9 as they enable unique identification through voiceprint analysis. Processing requires explicit consent under Article 9(2)(a).

**Cross-Border Transfer Mechanism:**
- Standard Contractual Clauses (SCCs) with Recall.ai (EU-US)
- Encryption: AES-256-GCM in transit and at rest
- Data subject rights: Consent withdrawal triggers immediate deletion

**Risk Assessment:**
- **Privacy Risk:** HIGH - Voice data enables re-identification
- **Security Risk:** CRITICAL - Unauthorized access = GDPR breach
- **Mitigation:** 30-day retention, end-to-end encryption, access logging

**Data Processors:**
- Recall.ai (primary processor - bot recording)
- LiveKit (sub-processor - temporary storage)
- Railway (sub-processor - backup storage)
- Deepgram (sub-processor - transcription)

**Data Protection Agreements:**
- Recall.ai DPA: Required (verify SCCs include Schrems II safeguards)
- LiveKit DPA: Required
- Railway DPA: Required

---

### 4.2 Transcripts (CONFIDENTIAL)

**Data Fields:**
- `transcript_id` (UUID)
- `recording_id` (foreign key)
- `user_id` (pseudonymized)
- `text_content` (full transcript text)
- `speaker_labels` (array of speaker identifiers)
- `timestamps` (word-level timing)
- `language` (ISO 639-1 code)
- `confidence_score` (float 0-1)
- `created_at` (ISO 8601)

**Processing Activities:**
1. Generation: Deepgram Speech-to-Text API (US servers)
2. Storage: Supabase PostgreSQL (EU region - `transcripts` table)
3. Processing: Groq LLM analysis for insights (US)
4. Access: n8n workflows for business logic
5. Deletion: Automated after 90 days

**Legal Basis:**
Consent (GDPR Article 6(1)(a)) - Users consent to transcription for service functionality.

**Cross-Border Transfer:**
- Deepgram processing: US servers with SCCs
- Storage: EU-only (Supabase EU region)
- LLM processing: Groq (US) with SCCs

**Retention Justification:**
90 days balances business need (conversation history for context) with data minimization. Extended beyond voice recordings (30 days) because:
- Transcripts are less privacy-invasive than biometric voice data
- Business analytics require historical conversation patterns
- User-requested conversation summaries reference past transcripts

**Risk Assessment:**
- **Privacy Risk:** MEDIUM - Contains conversation content but no biometric data
- **Security Risk:** HIGH - Unauthorized access exposes sensitive conversations
- **Mitigation:** Column-level encryption, RBAC, 90-day auto-deletion

---

### 4.3 User Metadata (CONFIDENTIAL)

**Data Fields:**
- `user_id` (UUID - internal identifier)
- `teams_user_id` (Microsoft Teams unique ID)
- `email` (hashed with bcrypt)
- `display_name` (encrypted)
- `organization_id` (UUID)
- `timezone` (string)
- `language_preference` (ISO 639-1)
- `account_created_at` (ISO 8601)
- `last_activity_at` (ISO 8601)
- `subscription_tier` (enum: free/pro/enterprise)

**Processing Activities:**
1. Collection: Microsoft Teams OAuth flow
2. Storage: Supabase PostgreSQL (EU region - `users` table)
3. Processing: n8n workflows for personalization
4. Updates: Real-time on user activity
5. Deletion: On account deletion or GDPR erasure request

**Legal Basis:**
Contract (GDPR Article 6(1)(b)) - Necessary for service delivery.

**Cross-Border Transfer:**
Microsoft Teams infrastructure spans EU and US, but user data stored in EU Supabase instance (no transfer for storage, only authentication flow).

**Retention:**
Account lifetime + 30 days grace period after deletion request. Immediate deletion if GDPR Right to Erasure invoked.

**Risk Assessment:**
- **Privacy Risk:** MEDIUM - Standard PII (email, name)
- **Security Risk:** MEDIUM - Credential stuffing risk
- **Mitigation:** Email hashing, MFA enforcement, rate limiting

---

### 4.4 Consent Records (RESTRICTED)

**Data Fields:**
- `consent_id` (UUID)
- `user_id` (foreign key)
- `consent_type` (enum: voice_recording, transcription, analytics)
- `consent_status` (boolean)
- `consent_timestamp` (ISO 8601)
- `withdrawal_timestamp` (ISO 8601 - nullable)
- `ip_address` (hashed)
- `user_agent` (string)
- `consent_version` (string - references privacy policy version)
- `legal_signature` (encrypted - optional for explicit consent)

**Processing Activities:**
1. Collection: n8n workflow during user onboarding
2. Storage: Supabase PostgreSQL (EU region - `consent_log` table)
3. Verification: Pre-flight check before recording
4. Audit: Annual compliance review
5. Retention: 7 years (legal requirement)

**Legal Basis:**
Legal Obligation (GDPR Article 6(1)(c)) - Organizations must demonstrate consent under Article 7(1).

**Retention Justification:**
7 years aligns with:
- GDPR accountability principle (Article 5(2))
- Statute of limitations for GDPR complaints
- SOC 2 audit trail requirements

**Risk Assessment:**
- **Privacy Risk:** LOW - Metadata only, no sensitive content
- **Security Risk:** HIGH - Tampering undermines entire compliance framework
- **Mitigation:** Append-only log, cryptographic signing, immutable audit trail

---

### 4.5 Audit Logs (CONFIDENTIAL)

**Data Fields:**
- `log_id` (UUID)
- `timestamp` (ISO 8601 with microseconds)
- `actor_id` (user or system identifier)
- `action` (enum: access, modify, delete, export)
- `resource_type` (enum: recording, transcript, user)
- `resource_id` (UUID)
- `ip_address` (hashed)
- `user_agent` (string)
- `result` (enum: success, failure, unauthorized)
- `metadata` (JSONB - context-specific details)

**Processing Activities:**
1. Generation: Automatic on all RESTRICTED data access
2. Storage: Railway PostgreSQL (US - `audit_logs` table)
3. Monitoring: Real-time anomaly detection (Sentry integration)
4. Analysis: Quarterly security reviews
5. Archival: Anonymization after 1 year, retain 7 years

**Legal Basis:**
Legitimate Interest (GDPR Article 6(1)(f)) - Security monitoring outweighs privacy impact.

**Retention:**
- Active logs: 1 year (SOC 2 minimum requirement)
- Anonymized archives: 7 years (regulatory compliance)

**Cross-Border Transfer:**
Railway servers in US. Transfer justified by legitimate interest (security) + SCCs.

**Risk Assessment:**
- **Privacy Risk:** LOW - Operational metadata, minimal PII
- **Security Risk:** MEDIUM - Log tampering conceals breaches
- **Mitigation:** Write-once storage, hash chaining, external SIEM backup

---

### 4.6 Session Data (CONFIDENTIAL)

**Data Fields:**
- `session_id` (UUID)
- `user_id` (foreign key)
- `livekit_room_id` (string)
- `teams_meeting_id` (string)
- `participant_count` (integer)
- `session_start` (ISO 8601)
- `session_end` (ISO 8601 - nullable)
- `status` (enum: active, ended, error)
- `connection_metadata` (JSONB - IP, latency, quality)

**Processing Activities:**
1. Creation: LiveKit room initialization
2. Storage: Redis cache (Railway - US)
3. Updates: Real-time during call
4. Expiration: 24 hours after session end
5. Cleanup: Automated Redis TTL

**Legal Basis:**
Consent (GDPR Article 6(1)(a)) - Session tracking necessary for service functionality.

**Retention:**
24 hours - minimal retention for active session management only.

**Risk Assessment:**
- **Privacy Risk:** LOW - Ephemeral operational data
- **Security Risk:** LOW - Temporary cache with short TTL
- **Mitigation:** Automatic expiration, encrypted Redis connection

---

### 4.7 API Keys/Credentials (RESTRICTED)

**Data Fields:**
- `credential_id` (UUID)
- `service_name` (string - e.g., "OpenAI", "Deepgram")
- `api_key` (encrypted with AES-256)
- `created_at` (ISO 8601)
- `last_rotated` (ISO 8601)
- `expires_at` (ISO 8601)
- `access_scope` (string)
- `rotation_policy` (enum: manual, automatic_90day)

**Processing Activities:**
1. Storage: n8n Vault (encrypted database) + Railway environment variables
2. Access: Just-in-Time retrieval for API calls
3. Rotation: Automatic every 90 days (Vault-managed)
4. Revocation: Immediate on suspected compromise
5. Audit: Access logged for all retrievals

**Legal Basis:**
N/A - Not personal data (organizational credentials).

**Retention:**
Until rotation or service termination. Maximum 90 days per key version.

**Risk Assessment:**
- **Privacy Risk:** N/A
- **Security Risk:** CRITICAL - Compromise enables data breach
- **Mitigation:** HSM storage, automatic rotation, access monitoring, secret scanning

---

### 4.8 Analytics/Metrics (CONFIDENTIAL)

**Data Fields:**
- `metric_id` (UUID)
- `user_id` (pseudonymized hash)
- `event_type` (enum: call_started, call_ended, transcript_generated)
- `timestamp` (ISO 8601)
- `duration` (integer - seconds)
- `quality_score` (float 0-1)
- `error_code` (string - nullable)
- `aggregation_window` (enum: hourly, daily, weekly)

**Processing Activities:**
1. Collection: Automatic on service events
2. Aggregation: Hourly batch jobs (>50 users)
3. Storage: Supabase PostgreSQL (EU - `analytics` table)
4. Analysis: Business intelligence dashboards
5. Anonymization: User IDs removed after 30 days

**Legal Basis:**
Legitimate Interest (GDPR Article 6(1)(f)) - Service improvement justified by privacy-preserving aggregation.

**Retention:**
- Detailed (pseudonymized): 30 days
- Aggregated (anonymized): 1 year

**Risk Assessment:**
- **Privacy Risk:** LOW - Pseudonymized, aggregated
- **Security Risk:** LOW - No sensitive content
- **Mitigation:** k-anonymity (minimum 50 users per aggregate), pseudonymization

---

## 5. Data Flow Summary

**Inbound Data Sources:**
1. Microsoft Teams (user metadata, meeting context)
2. Recall.ai (voice recordings)
3. Deepgram (transcripts)
4. User input (consent, preferences)

**Data Processing Systems:**
1. LiveKit (real-time communication)
2. Deepgram (speech-to-text)
3. Groq (LLM analysis)
4. Cartesia (text-to-speech)
5. n8n (workflow orchestration)

**Data Storage Locations:**
1. Supabase PostgreSQL (EU) - Primary data warehouse
2. Railway PostgreSQL (US) - Audit logs, voice backup
3. Redis (Railway US) - Session cache
4. n8n Vault - Credentials

**Outbound Data Transfers:**
1. Microsoft Teams (response audio, summaries)
2. User exports (GDPR data portability)
3. Compliance audits (anonymized samples)

---

## 6. Cross-Border Transfer Register

| Data Type | Origin | Destination | Mechanism | Safeguards | Review Date |
|-----------|--------|-------------|-----------|------------|-------------|
| Voice Recordings | EU (LiveKit) | US (Railway) | SCCs | Encryption, 30-day retention, consent withdrawal protocol | 2026-04-18 |
| Transcripts (processing only) | EU (Supabase) | US (Deepgram API) | SCCs | Ephemeral processing, no US storage | 2026-04-18 |
| Audit Logs | EU (n8n) | US (Railway) | SCCs + Legitimate Interest | Pseudonymization, security purpose | 2026-04-18 |
| Session Data | EU (LiveKit) | US (Redis) | SCCs | 24-hour TTL, ephemeral | 2026-04-18 |

**Schrems II Compliance:**
- All processors assessed for US government access risk
- Supplementary measures: Encryption (renders data unintelligible to authorities), pseudonymization, data minimization
- Annual re-assessment of transfer mechanisms

---

## 7. Data Subject Rights Impact

| Right (GDPR Article) | Affected Data Types | Implementation | Response Time |
|----------------------|---------------------|----------------|---------------|
| Access (Art. 15) | All PII | n8n export workflow → JSON download | 30 days |
| Rectification (Art. 16) | User metadata, consent records | Supabase update API | 7 days |
| Erasure (Art. 17) | All data types | Cascade deletion + cryptographic erasure | 30 days |
| Portability (Art. 20) | Transcripts, user metadata | JSON export | 30 days |
| Restriction (Art. 18) | Processing suspension flag | Database soft-delete marker | 7 days |
| Objection (Art. 21) | Analytics, marketing | Opt-out flag | Immediate |

---

## 8. Data Minimization Review

**Next Review:** 2026-04-18

**Questions for Review:**
1. Can transcript retention be reduced from 90 to 60 days?
2. Can speaker labels be pseudonymized further?
3. Can audit logs be anonymized sooner (currently 1 year)?
4. Are all metadata fields in `users` table necessary?

**Action Items:**
- [ ] Survey users on value of 90-day transcript history
- [ ] Test pseudonymization impact on analytics accuracy
- [ ] Consult legal on minimum audit log retention

---

## 9. Incident Response Contacts

**Data Breaches Affecting:**
- Voice recordings (RESTRICTED): Escalate to DPO + CISO within 1 hour
- Transcripts/User metadata (CONFIDENTIAL): DPO notification within 4 hours
- Audit logs: CISO notification within 24 hours

**Notification Requirements:**
- GDPR breach notification: 72 hours to supervisory authority (if high risk)
- Affected data subjects: Without undue delay (if high risk to rights/freedoms)
- SOC 2 customers: Per contract (typically 24 hours)

---

## 10. Related Documents

- `DATA-CLASSIFICATION-POLICY.md` - Classification and handling rules
- `DATA-FLOW-DIAGRAM.md` - Visual system architecture
- `RETENTION-SCHEDULE.md` - Detailed retention rules
- `GDPR-COMPLIANCE.md` - Legal basis and rights implementation
- `DPA-TEMPLATES/` - Data Processing Agreements with processors

---

## 11. Maintenance Log

| Date | Change | Reason | Approver |
|------|--------|--------|----------|
| 2026-01-18 | Initial inventory creation | SOC 2 prep | DPO |

---

## 12. Approval

**Data Protection Officer:** ________________
**Chief Information Security Officer:** ________________
**Date:** 2026-01-18

**Next Review:** 2026-04-18 (Quarterly)
