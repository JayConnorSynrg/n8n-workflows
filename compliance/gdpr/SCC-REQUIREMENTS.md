# Standard Contractual Clauses (SCC) Requirements
## EU Commission 2021 SCCs for Cross-Border Data Transfers

**Last Updated:** 2026-01-18
**Regulatory Basis:** GDPR Article 46(2)(c), EU Commission Implementing Decision 2021/914
**Applicable Module:** Module 2 (Controller-to-Processor)

---

## Executive Summary

**Legal Requirement:** All 8 vendors are US-based and transfer personal data outside the EU/EEA. Under GDPR Chapter V, cross-border transfers require an "appropriate safeguard" — Standard Contractual Clauses (SCCs) are the primary mechanism post-Schrems II.

**Current Status:**
- SCCs Executed: 0/8 ❌
- Transfer Impact Assessments (TIA): 0/8 ❌
- Supplementary Measures: 0/8 ❌

**Legal Risk:** 🔴 **CRITICAL** - Cross-border transfers without SCCs violate GDPR Art. 46
**Penalty Exposure:** Up to €20M or 4% of global turnover (Art. 83(5))

**Regulatory Context (Post-Schrems II):**
The Court of Justice of the European Union (CJEU) invalidated the EU-US Privacy Shield in *Schrems II* (C-311/18, July 2020). SCCs remain valid BUT require:
1. Transfer Impact Assessment (TIA) before each transfer
2. Supplementary measures if destination country laws undermine SCCs
3. Suspension of transfers if adequate protection cannot be ensured

---

## Why SCCs Are Required

### GDPR Chapter V: Transfers to Third Countries

**Article 46(1):** "In the absence of an adequacy decision, a controller or processor may transfer personal data to a third country... only if the controller or processor has provided appropriate safeguards..."

**Article 46(2)(c):** "Appropriate safeguards include... standard data protection clauses adopted by the Commission..."

**Third Country Status:**
- 🇺🇸 United States: NO adequacy decision (Privacy Shield invalidated)
- All 8 vendors operate from the USA = automatic Chapter V applicability

**Consequence of Non-Compliance:**
- Transfers without SCCs = unlawful processing (Art. 83(5) penalty tier)
- Supervisory authorities can order suspension of transfers (Art. 58(2)(f))
- Data subjects can claim compensation (Art. 82)

---

## EU Commission 2021 SCCs: Module Selection

### Available Modules

The EU Commission 2021 SCCs provide **four modules** for different transfer scenarios:

| Module | Transfer Type | Applicability to Voice Agent |
|--------|--------------|------------------------------|
| Module 1 | Controller → Controller | ❌ Not applicable |
| **Module 2** | **Controller → Processor** | ✅ **PRIMARY MODULE** (all 8 vendors) |
| Module 3 | Processor → Sub-Processor | ⏳ If vendor uses sub-processors |
| Module 4 | Processor → Controller | ❌ Not applicable |

**Why Module 2:**
- We are the **data controller** (determine purposes and means of processing)
- Vendors are **data processors** (process on our documented instructions)
- This is the standard B2B SaaS relationship structure

**Module 3 Consideration:**
- If a vendor (as processor) uses sub-processors in third countries, they must execute Module 3 SCCs with those sub-processors
- Example: If Railway uses AWS (US entity), Railway must have Module 3 SCCs with AWS
- We must verify this in vendor due diligence (see VENDOR-SECURITY-QUESTIONNAIRE.md)

---

## SCC Structure & Required Annexes

### SCC Clauses (Standard, Cannot Be Modified)

**Section I: Purpose and Scope**
- Clause 1: Purpose
- Clause 2: Invariability of clauses
- Clause 3: Interpretation
- Clause 4: Hierarchy
- Clause 5: Description of transfers (→ Annex I)
- Clause 6: Description of processing (→ Annex I)
- Clause 7: Docking clause (optional)

**Section II: Obligations of the Parties**
- Clause 8: Data protection safeguards
- Clause 9: Use of sub-processors (→ Annex III)
- Clause 10: Data subject rights
- Clause 11: Redress
- Clause 12: Liability
- Clause 13: Supervision

**Section III: Local Laws and Obligations**
- Clause 14: Local laws affecting compliance
- Clause 15: Obligations in case of access by public authorities

**Section IV: Final Provisions**
- Clause 16: Non-compliance and termination
- Clause 17: Governing law (EU Member State)
- Clause 18: Choice of forum and jurisdiction (EU Member State)

⚠️ **Critical:** Clauses cannot be modified. Only Annexes are customizable.

---

### Annex I: List of Parties & Processing Details

**Required Information:**

#### Annex I.A: List of Parties

**Data Exporter (Our Company):**
- Name: [Company Legal Name]
- Address: [Registered Office Address]
- Contact: [DPO Name], [DPO Email]
- Role: Controller
- Signature: _______________

**Data Importer (Vendor):**
- Name: [Vendor Legal Name]
- Address: [Vendor Registered Address]
- Contact: [Vendor DPO/Legal Contact]
- Role: Processor
- Signature: _______________

#### Annex I.B: Description of Transfer

| Field | Example (Recall.ai) | Example (Groq) |
|-------|---------------------|----------------|
| **Categories of data subjects** | End-user customers participating in recorded meetings | End-user customers using voice agent |
| **Categories of personal data transferred** | Voice recordings (biometric), video recordings, participant names, email addresses, meeting metadata | Text transcripts of conversations, conversation metadata |
| **Sensitive data** | Special category: Biometric data (voice recordings) | None (unless transcript content includes health/etc.) |
| **Frequency of transfer** | Continuous during meeting recordings | Continuous during LLM inference requests |
| **Nature of processing** | Recording, storage, transcription of meetings | LLM inference on conversation transcripts |
| **Purpose of transfer** | Provide meeting recording and transcription services | Generate AI responses in voice agent conversations |
| **Retention period** | 30 days from recording date (then deletion) | 0 days (immediate deletion post-inference) |
| **Sub-processors** | See Annex III | See Annex III |

**Template for Each Vendor:**

```markdown
### [Vendor Name] - Annex I.B

**Categories of data subjects:**
- End-user customers interacting with voice agent
- [Add other categories if applicable]

**Categories of personal data transferred:**
- [Data type 1]
- [Data type 2]
- [Metadata types]

**Sensitive data (if any):**
- [Special category under Art. 9 GDPR]
- Legal basis: [Explicit consent / Necessity for contract / Other]

**Frequency of transfer:**
- [Continuous / Periodic / On-demand]

**Nature of processing:**
- [Storage / Analysis / Transformation / etc.]

**Purpose of transfer and further processing:**
- [Business purpose aligned with privacy notice]

**Period for which personal data will be retained:**
- [Retention period in days/months]
- Deletion mechanism: [API call / Automated / Manual request]

**For transfers to sub-processors:**
- See Annex III for sub-processor list
- Sub-processor location: [Country]
```

#### Annex I.C: Competent Supervisory Authority

**Selection Criteria:**
- If we have an establishment in an EU Member State: That state's DPA
- If no EU establishment: DPA of the Member State where data subjects are located
- Common choice for multi-jurisdiction: Irish DPC (if no specific establishment)

**Our Selection:** [To be determined based on business structure]
- Option 1: Irish Data Protection Commission (if no EU establishment)
- Option 2: [Specific national DPA if we have an EU subsidiary]

**Contact:**
- Name: [e.g., Data Protection Commission (Ireland)]
- Address: 21 Fitzwilliam Square South, Dublin 2, D02 RD28, Ireland
- Email: info@dataprotection.ie

---

### Annex II: Technical and Organizational Measures (TOMs)

**Purpose:** Describe security measures the data importer (vendor) implements to protect personal data (GDPR Art. 32).

**Required Categories:**

#### 1. Measures of Pseudonymization and Encryption

**Example (Recall.ai):**
```markdown
**Encryption:**
- Data in transit: TLS 1.3 for all API communications
- Data at rest: AES-256 encryption for stored recordings
- Key management: AWS KMS with automatic key rotation

**Pseudonymization:**
- Meeting participant identifiers hashed before storage
- Voice recordings not linked to PII except via encrypted lookup table

**Status:** ⏳ To verify with vendor in security questionnaire
```

**Template Questions for Vendor:**
- What encryption algorithms are used (at rest / in transit)?
- Where are encryption keys stored and managed?
- Is pseudonymization applied to personal data fields?
- Are biometric templates stored separately from identifiers?

---

#### 2. Measures for Ensuring Ongoing Confidentiality, Integrity, Availability, and Resilience

**Sub-Categories:**

**a) Physical Access Controls**
- Data center security (ISO 27001 certified facilities)
- Badge access, biometric controls, 24/7 monitoring
- Visitor logs and escort requirements

**b) Logical Access Controls**
- Role-based access control (RBAC)
- Multi-factor authentication (MFA) for admin access
- Principle of least privilege
- Access reviews (frequency: quarterly)

**c) Confidentiality Agreements**
- All personnel sign confidentiality agreements
- Background checks for personnel with data access
- Security awareness training (frequency: annual)

**d) Integrity Controls**
- Data validation and checksums
- Immutable audit logs
- Change management procedures
- Version control for configurations

**e) Availability & Resilience**
- Redundancy: Multi-availability zone deployment
- Uptime SLA: 99.9%
- Backup frequency: Daily incremental, weekly full
- Backup retention: 30 days
- Disaster recovery plan: RTO 4 hours, RPO 1 hour
- Tested recovery procedures: Quarterly

**Template for Vendor:**
```markdown
### [Vendor Name] - Annex II: TOMs

**Encryption:**
- In transit: [TLS version, cipher suites]
- At rest: [Algorithm, key size]
- Key management: [HSM / Cloud KMS / Other]

**Access Controls:**
- Authentication: [MFA required? SSO supported?]
- Authorization: [RBAC / ABAC]
- Access review frequency: [Monthly / Quarterly]

**Physical Security:**
- Data center certification: [ISO 27001 / SOC 2 / etc.]
- Location: [Country, region]

**Availability:**
- Uptime SLA: [Percentage]
- Backup frequency: [Daily / Real-time]
- RTO: [Hours]
- RPO: [Minutes/Hours]

**Monitoring:**
- Intrusion detection: [Yes/No, system used]
- Security logging: [Retention period]
- SIEM: [System used]

**Status:** ⏳ To complete via vendor security questionnaire
```

---

#### 3. Measures for Ensuring Ability to Restore Availability and Access

**Required Information:**
- Backup procedures and frequency
- Backup encryption and storage location
- Restoration testing frequency
- Recovery time objective (RTO)
- Recovery point objective (RPO)

**Example:**
```markdown
**Backup Strategy:**
- Frequency: Continuous replication + daily snapshots
- Retention: 30 days
- Encryption: AES-256 (same as primary)
- Storage location: [US-East, US-West - multi-region]

**Disaster Recovery:**
- RTO: 4 hours (time to restore service)
- RPO: 15 minutes (maximum data loss)
- Tested: Quarterly DR drills
- Last test: [Date]
- Test results: [Pass/Fail, issues identified]
```

---

#### 4. Processes for Regular Testing, Assessment, and Evaluation

**Required Information:**
- Penetration testing frequency and scope
- Vulnerability scanning frequency
- Security audit schedule
- Compliance certifications (SOC 2, ISO 27001)
- Incident response plan testing

**Example:**
```markdown
**Security Testing:**
- Penetration testing: Annual (last: [Date])
- Vulnerability scanning: Weekly automated
- Code security review: Pre-deployment (static analysis)

**Audits:**
- SOC 2 Type II: Annual (valid until [Date])
- ISO 27001: [If applicable]
- Internal audit: Quarterly

**Incident Response:**
- Plan documented: ✅ Yes
- Plan tested: Annually (last: [Date])
- Breach notification SLA: 24 hours

**Compliance Monitoring:**
- Automated compliance checks: Daily
- Manual review: Monthly
- Remediation SLA: Critical within 24h, High within 7 days
```

---

### Annex III: List of Sub-Processors

**Purpose:** Module 2 Clause 9 requires disclosure of sub-processors and general authorization.

**Required Information for Each Sub-Processor:**
- Name and contact details
- Location (country)
- Processing activities performed
- Security measures implemented

**Example (Railway - Infrastructure Provider):**

| Sub-Processor | Location | Processing Activity | Security Measures |
|---------------|----------|---------------------|-------------------|
| Amazon Web Services (AWS) | USA (us-east-1) | Infrastructure hosting, database storage | SOC 2 Type II, ISO 27001, encryption at rest/transit |
| Cloudflare | USA | CDN, DDoS protection | SOC 2 Type II, TLS 1.3 |
| [To be disclosed by vendor] | [Country] | [Activity] | [Measures] |

**Vendor Obligations:**
- Disclose all sub-processors before initial data transfer
- Notify 30 days before engaging new sub-processors
- Provide objection rights (if we object, vendor must offer alternative or allow termination)
- Flow down SCC obligations to sub-processors (Module 3 SCCs required)

**Action Required:**
- Request sub-processor list from each vendor (see VENDOR-SECURITY-QUESTIONNAIRE.md, Question 28)
- Verify Module 3 SCCs exist between vendor and sub-processors
- Document general authorization in Annex III

---

## Transfer Impact Assessment (TIA) Requirements

### Legal Basis (Schrems II Judgment)

**CJEU Requirement:**
"Before transferring personal data to a third country on the basis of standard contractual clauses, the controller or processor must verify, on a case-by-case basis, whether the level of protection required by EU law is respected in that third country." (*Schrems II*, para. 134)

**Three-Step Process:**

#### Step 1: Assess Laws in Destination Country

**For USA (All 8 Vendors):**

**Relevant Surveillance Laws:**

1. **FISA Section 702** (Foreign Intelligence Surveillance Act)
   - Allows NSA to compel US companies to provide data on non-US persons
   - No individualized warrant required
   - Applies to "electronic communication service providers"
   - **Risk:** High for vendors storing communications data (Recall.ai, LiveKit, Deepgram)

2. **Executive Order 12333**
   - Authorizes intelligence collection outside USA
   - Bulk data collection from international cables
   - **Risk:** Medium for all vendors (infrastructure-level exposure)

3. **CLOUD Act** (Clarifying Lawful Overseas Use of Data Act)
   - US law enforcement can compel US companies to produce data stored abroad
   - **Risk:** Medium for all vendors (extraterritorial reach)

**Assessment Questions:**
- Is the vendor an "electronic communication service provider" under FISA 702?
- Does the vendor have the ability to challenge government data requests?
- Has the vendor ever received NSLs (National Security Letters) or FISA orders? (Check transparency reports)
- What jurisdictional safeguards exist in vendor's country of incorporation?

**Example (Recall.ai TIA):**
```markdown
### Recall.ai Transfer Impact Assessment

**Destination Country:** United States

**Applicable Laws:**
- FISA Section 702: ✅ Applies (electronic communications service)
- EO 12333: ✅ Applies (US-based infrastructure)
- CLOUD Act: ✅ Applies (US company)

**Vendor's Ability to Resist:**
- Legal challenge history: ⏳ Unknown (research transparency reports)
- Data localization options: ❌ None (US-only infrastructure)
- Encryption preventing access: ⏳ To verify (end-to-end encryption?)
- Warrant canary: ⏳ Unknown

**Risk Level:** 🔴 HIGH (special category data + FISA 702 exposure)
```

---

#### Step 2: Identify and Assess Supplementary Measures

**If destination country laws undermine SCC protections, implement supplementary measures:**

**Technical Measures:**

1. **End-to-End Encryption (E2EE)**
   - **Goal:** Data encrypted client-side, vendor cannot access plaintext
   - **Applicability:** Difficult for AI services requiring plaintext access (STT, LLM)
   - **Example:** Encrypt meeting metadata, but voice must be decrypted for Deepgram STT
   - **Status:** ⏳ Assess vendor-by-vendor feasibility

2. **Pseudonymization**
   - **Goal:** Separate personal identifiers from processing data
   - **Example:** Hash participant IDs before sending to Recall.ai
   - **Limitation:** Voice recordings remain biometric (pseudonymization limited)
   - **Status:** ✅ Implementable for metadata

3. **Data Minimization**
   - **Goal:** Transfer only necessary data
   - **Example:** Redact PII from transcripts before sending to Groq
   - **Status:** ✅ Implementable (pre-processing filters)

4. **Split Processing**
   - **Goal:** Process sensitive operations in EU, non-sensitive in USA
   - **Example:** Store raw recordings in EU (Supabase EU region), process transcripts in USA
   - **Status:** ⏳ Requires architecture redesign

**Contractual Measures:**

1. **Transparency Obligations**
   - Vendor must disclose all government data requests (unless legally gagged)
   - Annual transparency reports required
   - Immediate notification of NSLs/FISA orders (if legally permissible)

2. **Legal Challenge Commitments**
   - Vendor commits to challenge overbroad or unlawful requests
   - Legal fees coverage for challenges
   - Documented process for objecting to requests

3. **Data Localization Options**
   - Vendor offers EU region for data storage (Supabase, n8n Cloud)
   - Migration plan to EU region within 90 days

**Organizational Measures:**

1. **Breach of SCC Notification**
   - Vendor must notify immediately if government request undermines SCCs
   - Suspension of transfers if no adequate protection can be ensured

2. **Regular TIA Reviews**
   - Reassess TIA annually or when legal landscape changes
   - Monitor court decisions, new surveillance laws, transparency reports

---

#### Step 3: Document Decision and Implement Monitoring

**Required Documentation:**

```markdown
### Transfer Impact Assessment - [Vendor Name]

**Assessment Date:** [Date]
**Assessor:** [Legal Counsel, DPO]
**Next Review:** [Date + 12 months]

**1. Destination Country Laws:**
- FISA 702 Applicability: [Yes/No, analysis]
- EO 12333 Applicability: [Yes/No, analysis]
- CLOUD Act Applicability: [Yes/No, analysis]
- Vendor's Legal Challenge Capability: [Assessment]

**2. Supplementary Measures Implemented:**
- Technical: [E2EE / Pseudonymization / Data Minimization]
- Contractual: [Transparency / Legal Challenge / Data Localization]
- Organizational: [Monitoring / Review Procedures]

**3. Residual Risk Assessment:**
- Risk Level: [Low / Medium / High / Critical]
- Justification: [Analysis]
- Mitigation: [Measures applied]

**4. Decision:**
- ✅ Transfers may proceed with supplementary measures
- ⏳ Transfers suspended pending additional safeguards
- ❌ Transfers prohibited (inadequate protection)

**5. Monitoring Plan:**
- Review trigger events: [New surveillance laws, court decisions, vendor breaches]
- Review frequency: [Annual minimum]
- Responsible party: [DPO, Legal Counsel]

**Approval:**
- DPO: _______________ Date: ___________
- Legal Counsel: _______________ Date: ___________
```

**TIA Template Location:** `/compliance/gdpr/templates/TIA-TEMPLATE.md` (to be created)

---

## Vendor-Specific SCC Requirements

### Critical Priority: Recall.ai

**Specific Considerations:**
- **Special category data:** Biometric voice recordings (Art. 9 GDPR)
- **Legal basis required:** Explicit consent OR necessity for contract
- **TIA Risk:** 🔴 CRITICAL (FISA 702 directly applicable to electronic communications)

**Supplementary Measures Required:**
1. ⚠️ **Mandatory:** Client-side pseudonymization of participant identifiers
2. ⚠️ **Mandatory:** Contractual prohibition on using data for training/improvement
3. ⚠️ **Mandatory:** 30-day maximum retention with certified deletion
4. ⚠️ **Mandatory:** Immediate breach notification (<24 hours)
5. ⚠️ **Recommended:** Explore E2EE options (if technically feasible)

**SCC Annex I.B - Sensitive Data Section:**
```markdown
**Sensitive data transferred:**
- Biometric data: Voice recordings (Art. 9(1) GDPR)

**Legal basis for processing special category data (Art. 9(2)):**
- [✅] Explicit consent (Art. 9(2)(a))
  - Consent mechanism: [Describe opt-in process]
  - Withdrawal procedure: [Describe]
- [ ] Necessity for contract performance (Art. 9(2)(b))
- [ ] Other: [Specify]

**Additional safeguards for special category data:**
- Encryption: AES-256 at rest, TLS 1.3 in transit
- Access controls: RBAC with MFA
- Retention: 30 days maximum
- Deletion: Automated, verified via API
- No training use: Contractually prohibited
```

---

### High Priority: LiveKit, Deepgram, Railway, Supabase

**LiveKit (Real-Time Voice Infrastructure):**
- **Data:** Voice streams (biometric potential)
- **TIA Risk:** 🟠 HIGH (real-time communications infrastructure)
- **Supplementary Measures:** Pseudonymization of session metadata, 0-day retention for voice streams

**Deepgram (Speech-to-Text):**
- **Data:** Voice recordings → transcripts
- **TIA Risk:** 🟠 HIGH (processes biometric input)
- **Supplementary Measures:** No training clause, 30-day max retention, deletion verification

**Railway (Infrastructure Hosting):**
- **Data:** All application data (infrastructure level)
- **TIA Risk:** 🟠 HIGH (full data access at infrastructure layer)
- **Supplementary Measures:** Encryption at rest (customer-managed keys if available), EU region migration planning

**Supabase (Database & Auth):**
- **Data:** Transcripts, user metadata, auth tokens
- **TIA Risk:** 🟡 MEDIUM (EU region available → reduces transfer scope)
- **Supplementary Measures:** ✅ Migrate to EU region (Frankfurt or London), row-level security (RLS)

---

### Medium Priority: Groq, Cartesia, n8n Cloud

**Groq (LLM Inference):**
- **Data:** Text transcripts (no biometric data at this stage)
- **TIA Risk:** 🟡 MEDIUM (text-only processing)
- **Supplementary Measures:** 0-day retention, no training clause, PII redaction pre-processing

**Cartesia (Text-to-Speech):**
- **Data:** Text content → synthetic voice (output only)
- **TIA Risk:** 🟡 MEDIUM (no biometric input data)
- **Supplementary Measures:** Ephemeral processing, no storage of synthesis requests

**n8n Cloud (Workflow Orchestration):**
- **Data:** Workflow metadata, execution logs
- **TIA Risk:** 🟡 MEDIUM (metadata only, EU region available)
- **Supplementary Measures:** ✅ Migrate to EU region, 14-day log retention

---

## SCC Execution Process

### Step 1: Prepare Annexes (Before Sending SCCs)

**Required Documents:**
- [ ] Annex I.A: List of Parties (our details + vendor details)
- [ ] Annex I.B: Description of Transfer (complete template per vendor)
- [ ] Annex I.C: Competent Supervisory Authority (select DPA)
- [ ] Annex II: Technical and Organizational Measures (from vendor security questionnaire)
- [ ] Annex III: Sub-Processor List (from vendor disclosure)

**Timeline:**
- Week 1: Send vendor security questionnaire (see VENDOR-SECURITY-QUESTIONNAIRE.md)
- Week 2: Receive vendor responses
- Week 3: Complete all annexes
- Week 4: Internal legal review

---

### Step 2: Send SCCs to Vendor (With DPA)

**Recommended Approach:** Attach SCCs as Annex IV to the DPA

**Email Template:**
```
Subject: Standard Contractual Clauses for Data Transfer - [Vendor Name]

Dear [Vendor Legal Team],

Further to our Data Processing Agreement discussions, please find attached the
EU Commission 2021 Standard Contractual Clauses (Module 2: Controller-to-Processor)
required for our cross-border data transfers.

Attached documents:
1. Data Processing Agreement (DPA)
2. EU Commission 2021 SCCs - Module 2 (Annex IV to DPA)
3. Annex I: Processing details (completed)
4. Annex II: Technical and organizational measures (based on your responses)
5. Annex III: Sub-processor list (as disclosed)

Please review and execute both the DPA and SCCs. If you have standard SCCs you
prefer to use, please ensure they are the EU Commission 2021 version (Module 2).

We also require confirmation of:
- Module 3 SCCs with your sub-processors (for third-country sub-processors)
- Availability of supplementary measures to address US surveillance law risks
- Transparency reporting procedures for government data requests

Target execution date: [Date - 14 days]

Thank you,
[Legal/Compliance Team]
```

---

### Step 3: Negotiate and Execute

**Common Negotiation Points:**

1. **Governing Law (Clause 17):**
   - Must be an EU Member State law
   - Common choices: Ireland, Germany, Netherlands
   - ⚠️ Cannot be US law or non-EU law

2. **Choice of Forum (Clause 18):**
   - Must be courts of an EU Member State
   - Typically aligned with governing law choice
   - Data subjects retain right to sue in their own Member State

3. **Docking Clause (Clause 7 - Optional):**
   - Allows third parties (e.g., sub-processors) to join SCCs
   - Useful for complex processing chains
   - Consider enabling for flexibility

4. **Optional Clauses:**
   - Clause 9(a): General authorization for sub-processors (RECOMMENDED)
   - Clause 11(a): Independent dispute resolution (RECOMMENDED for US vendors)

**Execution:**
- Both parties sign SCCs (manual or electronic signature)
- Attach all completed annexes
- Exchange fully executed copies
- File in contract management system

---

### Step 4: Conduct Transfer Impact Assessment (TIA)

**Timing:** BEFORE first data transfer (or immediately if already transferring)

**Process:**
1. Complete TIA template for each vendor (see template above)
2. Document supplementary measures
3. Assess residual risk
4. Obtain DPO and legal counsel approval
5. Document decision to proceed or suspend transfers

**TIA Documentation Required:**
- [ ] Recall.ai TIA
- [ ] LiveKit TIA
- [ ] Deepgram TIA
- [ ] Groq TIA
- [ ] Cartesia TIA
- [ ] Railway TIA
- [ ] Supabase TIA
- [ ] n8n Cloud TIA

**Timeline:** Complete all TIAs within 30 days of SCC execution

---

### Step 5: Implement Monitoring and Review

**Ongoing Obligations:**

1. **Monitor Vendor Transparency Reports:**
   - Review annually for government data requests
   - Escalate if requests indicate SCC undermining

2. **Track Legal Developments:**
   - US surveillance law changes (Congress, Executive Orders)
   - CJEU case law (follow-on Schrems decisions)
   - National DPA guidance (EDPB recommendations)

3. **Annual TIA Review:**
   - Reassess each vendor TIA every 12 months
   - Update supplementary measures as needed
   - Document decision to continue or suspend

4. **Vendor Breach Notifications:**
   - If vendor reports government access, reassess TIA immediately
   - Consider suspension of transfers if SCCs compromised

**Responsibility:** Data Protection Officer (DPO) + Legal Counsel

---

## Practical Implementation Roadmap

### Phase 1: Immediate Actions (Week 1-2)

**Priority 0 (Recall.ai):**
- [ ] Send vendor security questionnaire (VENDOR-SECURITY-QUESTIONNAIRE.md)
- [ ] Request SOC 2 Type II report
- [ ] Request sub-processor list with locations
- [ ] Draft Annex I.B (processing details)

**Priority 1 (High-Risk Vendors):**
- [ ] Send security questionnaires to LiveKit, Deepgram, Railway, Supabase
- [ ] Request standard SCCs from vendors (if available)
- [ ] Begin Annex II completion (security measures)

---

### Phase 2: Documentation (Week 3-4)

- [ ] Complete all Annex I drafts (8 vendors)
- [ ] Complete all Annex II drafts (8 vendors)
- [ ] Complete all Annex III drafts (8 vendors)
- [ ] Internal legal review of all annexes
- [ ] Prepare TIA templates for each vendor

---

### Phase 3: Execution (Week 5-8)

- [ ] Send SCCs + DPAs to all vendors
- [ ] Negotiate any vendor-proposed modifications
- [ ] Execute SCCs with all 8 vendors
- [ ] File executed SCCs in contract repository

---

### Phase 4: TIA Completion (Week 9-12)

- [ ] Complete TIA for Recall.ai (CRITICAL priority)
- [ ] Complete TIAs for LiveKit, Deepgram, Railway, Supabase (HIGH priority)
- [ ] Complete TIAs for Groq, Cartesia, n8n Cloud (MEDIUM priority)
- [ ] DPO and legal counsel approval for all TIAs
- [ ] Document final transfer authorization decisions

---

### Phase 5: Implementation of Supplementary Measures (Week 13-16)

- [ ] Implement pseudonymization for participant IDs (Recall.ai, LiveKit)
- [ ] Implement PII redaction filters (Groq transcripts)
- [ ] Migrate Supabase to EU region (Frankfurt/London)
- [ ] Migrate n8n Cloud to EU region
- [ ] Configure customer-managed encryption keys (Railway, if available)
- [ ] Test deletion verification mechanisms (all vendors)

---

### Phase 6: Ongoing Monitoring (Continuous)

- [ ] Monthly: Review vendor transparency reports
- [ ] Quarterly: Review sub-processor change notifications
- [ ] Annually: Reassess all TIAs
- [ ] As needed: Respond to legal/regulatory changes

---

## Resources and Templates

### Official EU Commission Resources

**2021 SCCs Full Text:**
- [EU Commission Implementing Decision 2021/914](https://eur-lex.europa.eu/eli/dec_impl/2021/914/oj)
- Module 2 text: Annexes to Decision (pages 34-53)

**EDPB Guidance:**
- [Recommendations 01/2020 on Supplementary Measures](https://edpb.europa.eu/our-work-tools/our-documents/recommendations/recommendations-012020-measures-supplement-transfer_en)
- [Recommendations 02/2020 on European Essential Guarantees](https://edpb.europa.eu/our-work-tools/our-documents/recommendations/recommendations-022020-european-essential-guarantees_en)

**Transfer Impact Assessment:**
- EDPB: "Examples of supplementary measures" (Annex 2 to Recommendations 01/2020)

---

### Internal Templates (To Be Created)

**Location:** `/compliance/gdpr/templates/`

- [ ] `SCC-MODULE-2-TEMPLATE.md` - Blank SCC Module 2 with annexes
- [ ] `ANNEX-I-TEMPLATE.md` - Processing details template
- [ ] `ANNEX-II-TEMPLATE.md` - Security measures template
- [ ] `ANNEX-III-TEMPLATE.md` - Sub-processor list template
- [ ] `TIA-TEMPLATE.md` - Transfer Impact Assessment template
- [ ] `TIA-USA-SURVEILLANCE-ANALYSIS.md` - Standard US law assessment

---

## Compliance Dashboard

**SCC Execution Status:**

| Vendor | SCC Sent | SCC Signed | TIA Complete | Supplementary Measures | Overall Status |
|--------|----------|------------|--------------|----------------------|----------------|
| Recall.ai | ⏳ Pending | ❌ Not signed | ⏳ Pending | ⏳ Pending | 🔴 BLOCKED |
| LiveKit | ⏳ Pending | ❌ Not signed | ⏳ Pending | ⏳ Pending | 🔴 BLOCKED |
| Deepgram | ⏳ Pending | ❌ Not signed | ⏳ Pending | ⏳ Pending | 🔴 BLOCKED |
| Railway | ⏳ Pending | ❌ Not signed | ⏳ Pending | ⏳ Pending | 🔴 BLOCKED |
| Supabase | ⏳ Pending | ❌ Not signed | ⏳ Pending | 🟡 EU migration planned | 🟠 IN PROGRESS |
| Groq | ⏳ Pending | ❌ Not signed | ⏳ Pending | ⏳ Pending | 🔴 BLOCKED |
| Cartesia | ⏳ Pending | ❌ Not signed | ⏳ Pending | ⏳ Pending | 🔴 BLOCKED |
| n8n Cloud | ⏳ Pending | ❌ Not signed | ⏳ Pending | 🟡 EU migration planned | 🟠 IN PROGRESS |

**Overall Compliance:** 🔴 0% (0/8 SCCs executed, 0/8 TIAs complete)

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-18 | Legal & Compliance | Initial SCC requirements document |

**Next Review:** 2026-02-18
**Approval:** Legal Counsel, DPO, Privacy Team
