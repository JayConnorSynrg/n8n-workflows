# Vendor Risk Register
## Voice Agent System - GDPR Compliance

**Last Updated:** 2026-01-18
**Document Owner:** Compliance Team
**Review Frequency:** Monthly
**Next Review:** 2026-02-18

---

## Executive Summary

**Total Vendors:** 8
**Critical Risk:** 1 (Recall.ai - SOC 2 status unknown)
**High Risk:** 3 (LiveKit, Railway, Supabase)
**Medium Risk:** 4 (Groq, Cartesia, n8n Cloud, Deepgram)
**DPAs Executed:** 0/8 ⚠️ **CRITICAL GAP**
**SCCs Executed:** 0/8 ⚠️ **CRITICAL GAP**

---

## Complete Vendor Inventory

| Vendor | Service | Data Processed | Personal Data Categories | SOC 2 Type II | DPA Status | SCC Status | Risk Level | Action Priority |
|--------|---------|----------------|-------------------------|---------------|------------|------------|------------|-----------------|
| **Recall.ai** | Meeting recording infrastructure | Voice recordings (biometric), video, participant metadata | Special category (biometric), contact details, behavioral data | ❌ **UNKNOWN** | ⏳ Pending | ⏳ Required | 🔴 **CRITICAL** | **P0 - URGENT** |
| **LiveKit** | Real-time voice infrastructure | Voice streams, WebRTC connections, session metadata | Voice data, IP addresses, session timing | ✅ Yes | ⏳ Pending | ⏳ Required | 🟠 **HIGH** | **P1** |
| **Deepgram** | Speech-to-Text processing | Voice recordings → text transcripts | Voice data (biometric potential), transcripts | ✅ Yes | ⏳ Pending | ⏳ Required | 🟠 **HIGH** | **P1** |
| **Railway** | Infrastructure hosting | All application data, logs, database backups | All categories (infrastructure level) | ✅ Yes | ⏳ Pending | ⏳ Required | 🟠 **HIGH** | **P1** |
| **Supabase** | Database & authentication | Transcripts, user metadata, authentication tokens | Contact details, transcripts, usage data | ✅ Yes | ⏳ Pending | ⏳ Required | 🟠 **HIGH** | **P1** |
| **Groq** | LLM inference | Text transcripts, prompt data | Transcript content, conversation metadata | ✅ Yes | ⏳ Pending | ⏳ Required | 🟡 **MEDIUM** | **P2** |
| **Cartesia** | Text-to-Speech | Text content, voice synthesis requests | Text content, synthesis metadata | ✅ Yes | ⏳ Pending | ⏳ Required | 🟡 **MEDIUM** | **P2** |
| **n8n Cloud** | Workflow orchestration | Workflow metadata, webhook triggers, execution logs | Metadata, trigger data, integration tokens | ✅ Yes | ⏳ Pending | ⏳ Required | 🟡 **MEDIUM** | **P2** |

---

## Risk Assessment Details

### 🔴 CRITICAL RISK: Recall.ai

**Risk Factors:**
- ❌ SOC 2 Type II status **UNKNOWN** - no verified security certification
- 🔴 Processes **special category data** (biometric voice recordings)
- 🔴 No DPA in place - **illegal processing under GDPR Art. 28**
- 🔴 No SCCs - **illegal cross-border transfer under GDPR Art. 46**
- 🔴 Core infrastructure dependency - cannot operate without
- 📍 US-based - requires Transfer Impact Assessment (TIA)

**Immediate Actions Required:**
1. ⚠️ **URGENT:** Obtain SOC 2 Type II report or halt processing
2. ⚠️ **URGENT:** Initiate DPA negotiation (use template in DPA-TRACKING.md)
3. ⚠️ **URGENT:** Execute EU Commission 2021 SCCs (Module 2)
4. ⚠️ **URGENT:** Conduct Transfer Impact Assessment (TIA) for US data transfers
5. ⚠️ Document legal basis for special category processing (Art. 9 GDPR)

**Contingency Planning:**
- Identify alternative meeting recording providers with verified compliance
- Evaluate self-hosted alternatives (Jitsi, BigBlueButton)
- Timeline to migrate if Recall.ai cannot provide compliance evidence: **30 days**

---

### 🟠 HIGH RISK VENDORS

#### LiveKit
**Why High Risk:**
- Real-time voice streaming = continuous special category processing
- Infrastructure level access to all voice data
- US-based = cross-border transfer risk

**Mitigations:**
- ✅ SOC 2 Type II certified
- ⏳ DPA negotiation in progress
- ⏳ SCC execution required
- 🔄 Regular security audits scheduled

#### Railway (Infrastructure)
**Why High Risk:**
- Full infrastructure access = access to ALL data categories
- Database backups contain all personal data
- Breach would expose entire system

**Mitigations:**
- ✅ SOC 2 Type II certified
- 🔒 Encryption at rest enabled
- 🔒 Encryption in transit (TLS 1.3)
- ⏳ DPA negotiation in progress

#### Supabase
**Why High Risk:**
- Primary database = master repository of all persistent data
- Authentication system = identity management
- Transcript storage = special category potential

**Mitigations:**
- ✅ SOC 2 Type II certified
- ✅ EU region available (migration path)
- 🔒 Row-level security (RLS) implemented
- ⏳ DPA negotiation in progress

#### Deepgram
**Why High Risk:**
- Processes raw voice recordings (biometric data)
- Voice-to-text conversion = full content access
- Potential for training data usage (verify contract)

**Mitigations:**
- ✅ SOC 2 Type II certified
- 🔒 Enterprise plan with no-training clause
- ⏳ DPA negotiation in progress

---

### 🟡 MEDIUM RISK VENDORS

#### Groq
**Risk Profile:** Text-only processing, no biometric data, SOC 2 certified
**Mitigations:** ✅ SOC 2, ⏳ DPA pending, 🔒 No training on customer data (verify)

#### Cartesia
**Risk Profile:** Text-to-speech synthesis, generated audio only
**Mitigations:** ✅ SOC 2, ⏳ DPA pending, 🔒 Ephemeral processing model

#### n8n Cloud
**Risk Profile:** Workflow metadata only, no primary data processing
**Mitigations:** ✅ SOC 2, ⏳ DPA pending, 🔒 EU region available

---

## Cross-Border Data Transfers

**All vendors are US-based = Chapter V GDPR compliance required**

### Legal Framework (Post-Schrems II)

| Vendor | Data Location | EU Presence | Transfer Mechanism | TIA Status |
|--------|---------------|-------------|-------------------|------------|
| Recall.ai | USA | ❌ No | ⏳ SCCs required | ⏳ Pending |
| LiveKit | USA | ❌ No | ⏳ SCCs required | ⏳ Pending |
| Deepgram | USA | ❌ No | ⏳ SCCs required | ⏳ Pending |
| Groq | USA | ❌ No | ⏳ SCCs required | ⏳ Pending |
| Cartesia | USA | ❌ No | ⏳ SCCs required | ⏳ Pending |
| Railway | USA | ❌ No | ⏳ SCCs required | ⏳ Pending |
| Supabase | USA (EU available) | ✅ Yes | ⏳ SCCs + EU region migration | ⏳ Pending |
| n8n Cloud | USA (EU available) | ✅ Yes | ⏳ SCCs + EU region migration | ⏳ Pending |

**Required Actions:**
1. Execute EU Commission 2021 Standard Contractual Clauses (Module 2: Controller-to-Processor)
2. Conduct Transfer Impact Assessment (TIA) for each vendor:
   - Assess US government access risks (FISA 702, EO 12333)
   - Document supplementary measures (encryption, pseudonymization)
   - Legal review of vendor's ability to challenge data requests
3. Migrate Supabase and n8n Cloud to EU regions (reduce transfer scope)

---

## Sub-Processor Disclosure

**GDPR Article 28(2) & 28(4) Requirement:** Prior written authorization for sub-processors

| Vendor | Sub-Processor Disclosure | Update Mechanism | Authorization Status |
|--------|-------------------------|------------------|---------------------|
| Recall.ai | ⏳ Request pending | ⏳ Unknown | ❌ Not authorized |
| LiveKit | ⏳ Request pending | ⏳ Unknown | ❌ Not authorized |
| Deepgram | ⏳ Request pending | ⏳ Unknown | ❌ Not authorized |
| Groq | ⏳ Request pending | ⏳ Unknown | ❌ Not authorized |
| Cartesia | ⏳ Request pending | ⏳ Unknown | ❌ Not authorized |
| Railway | ⏳ Request pending | ⏳ Unknown | ❌ Not authorized |
| Supabase | 🔗 Public list available | Email + Dashboard | ⏳ Review required |
| n8n Cloud | 🔗 Public list available | Email notification | ⏳ Review required |

**Action Items:**
- Request sub-processor lists from all vendors (use VENDOR-SECURITY-QUESTIONNAIRE.md)
- Establish notification procedures for new sub-processors (30-day objection period)
- Document general authorization in DPAs for disclosed sub-processors

---

## Data Retention & Deletion

| Vendor | Data Retention Policy | Deletion Timeline | Verification Method | Compliance Status |
|--------|----------------------|-------------------|--------------------|--------------------|
| Recall.ai | ⏳ Unknown | ⏳ Unknown | ⏳ To confirm | ❌ Not verified |
| LiveKit | ⏳ To confirm | ⏳ To confirm | ⏳ To confirm | ⏳ Pending |
| Deepgram | 30 days (claimed) | Immediate on request | API confirmation | ⏳ Verify in DPA |
| Groq | 0 days (claimed) | Immediate | API confirmation | ⏳ Verify in DPA |
| Cartesia | 0 days (claimed) | Immediate | API confirmation | ⏳ Verify in DPA |
| Railway | Backup: 30 days | 30 days | Manual confirmation | ⏳ Verify in DPA |
| Supabase | User-controlled | Immediate | SQL verification | ✅ Verified |
| n8n Cloud | Execution logs: 14 days | Immediate on deletion | UI confirmation | ✅ Verified |

**Required Actions:**
1. Document retention policies in each DPA (Annex II)
2. Implement automated deletion workflows for GDPR Art. 17 requests
3. Establish quarterly verification audits

---

## Incident Response & Breach Notification

**GDPR Article 33 Requirement:** Processor must notify controller "without undue delay" (interpreted as <24 hours)

| Vendor | Breach Notification SLA | Contact Method | Notification Tested | DPA Clause |
|--------|------------------------|----------------|--------------------|-----------|
| Recall.ai | ⏳ Unknown | ⏳ Unknown | ❌ No | ⏳ Required |
| LiveKit | ⏳ To confirm | ⏳ To confirm | ❌ No | ⏳ Required |
| Deepgram | ⏳ To confirm | ⏳ To confirm | ❌ No | ⏳ Required |
| Groq | ⏳ To confirm | ⏳ To confirm | ❌ No | ⏳ Required |
| Cartesia | ⏳ To confirm | ⏳ To confirm | ❌ No | ⏳ Required |
| Railway | ⏳ To confirm | ⏳ To confirm | ❌ No | ⏳ Required |
| Supabase | 24 hours (claimed) | Email + Dashboard | ❌ No | ⏳ Required |
| n8n Cloud | 72 hours (claimed) | Email | ❌ No | ⏳ Required |

**Required Actions:**
1. Negotiate 24-hour breach notification SLA in all DPAs
2. Establish vendor incident response contact matrix
3. Conduct annual breach simulation exercises with critical vendors

---

## Audit Rights (GDPR Article 28(3)(h))

| Vendor | Audit Rights Granted | Audit Frequency | Last Audit | Next Audit |
|--------|---------------------|-----------------|------------|----------|
| Recall.ai | ⏳ To negotiate | ⏳ To negotiate | Never | ⏳ TBD |
| LiveKit | ⏳ To negotiate | ⏳ To negotiate | Never | ⏳ TBD |
| Deepgram | ⏳ To negotiate | ⏳ To negotiate | Never | ⏳ TBD |
| Groq | ⏳ To negotiate | ⏳ To negotiate | Never | ⏳ TBD |
| Cartesia | ⏳ To negotiate | ⏳ To negotiate | Never | ⏳ TBD |
| Railway | ⏳ To negotiate | ⏳ To negotiate | Never | ⏳ TBD |
| Supabase | SOC 2 report sharing | Annual | Never | 2026 Q2 |
| n8n Cloud | SOC 2 report sharing | Annual | Never | 2026 Q2 |

**Audit Strategy:**
- **Tier 1 (Critical/High Risk):** Direct audit rights or third-party assessments
- **Tier 2 (Medium Risk):** SOC 2 Type II report review sufficient
- **Minimum Frequency:** Annual for all vendors

---

## Vendor Contact Registry

| Vendor | Primary Contact | Email | DPA Contact | Security Contact |
|--------|----------------|-------|-------------|------------------|
| Recall.ai | ⏳ TBD | legal@recall.ai | ⏳ TBD | security@recall.ai |
| LiveKit | ⏳ TBD | sales@livekit.io | ⏳ TBD | security@livekit.io |
| Deepgram | ⏳ TBD | legal@deepgram.com | ⏳ TBD | security@deepgram.com |
| Groq | ⏳ TBD | legal@groq.com | ⏳ TBD | security@groq.com |
| Cartesia | ⏳ TBD | legal@cartesia.ai | ⏳ TBD | security@cartesia.ai |
| Railway | ⏳ TBD | legal@railway.app | ⏳ TBD | security@railway.app |
| Supabase | ⏳ TBD | legal@supabase.io | ⏳ TBD | security@supabase.io |
| n8n Cloud | ⏳ TBD | legal@n8n.io | ⏳ TBD | security@n8n.io |

---

## Risk Mitigation Roadmap

### Phase 1: Critical Gaps (Week 1-2)
- [ ] **Recall.ai SOC 2 verification** - URGENT
- [ ] Initiate DPA negotiations with all 8 vendors
- [ ] Request SCC execution (EU Commission 2021 templates)
- [ ] Conduct Transfer Impact Assessments (TIAs)

### Phase 2: Documentation (Week 3-4)
- [ ] Complete vendor security questionnaires (all 8)
- [ ] Obtain sub-processor lists
- [ ] Document data retention policies
- [ ] Establish breach notification procedures

### Phase 3: Execution (Week 5-8)
- [ ] Execute DPAs with all vendors
- [ ] Execute SCCs with all vendors
- [ ] Migrate Supabase to EU region
- [ ] Migrate n8n Cloud to EU region

### Phase 4: Monitoring (Ongoing)
- [ ] Monthly vendor compliance reviews
- [ ] Quarterly security questionnaire updates
- [ ] Annual audit rights exercise
- [ ] Continuous TIA reassessment

---

## Compliance Dashboard

**GDPR Article 28 Compliance:**
- DPAs Executed: 0/8 (0%) ❌
- SCCs Executed: 0/8 (0%) ❌
- Security Certifications Verified: 7/8 (88%) ⚠️
- Sub-Processor Lists Obtained: 2/8 (25%) ❌
- Audit Rights Established: 0/8 (0%) ❌

**Overall Vendor Risk Score:** 🔴 **68/100 (High Risk)**

**Blockers to Production:**
1. Recall.ai SOC 2 status unknown
2. No DPAs executed (illegal processing under Art. 28)
3. No SCCs executed (illegal transfers under Art. 46)

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-18 | Compliance Team | Initial vendor risk register |

**Approval Required:**
- [ ] Legal Counsel
- [ ] Data Protection Officer
- [ ] CTO
- [ ] CEO

**Next Actions:** Proceed to DPA-TRACKING.md for execution workflow
