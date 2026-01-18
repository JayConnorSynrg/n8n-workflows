# GDPR Vendor Management Documentation Suite
## Voice Agent System Compliance

**Created:** 2026-01-18
**Status:** 🔴 CRITICAL - Immediate Action Required
**Document Suite Version:** 1.0

---

## Executive Overview

This documentation suite provides comprehensive vendor risk management and GDPR compliance tracking for the Voice Agent system, which processes personal data (including biometric voice recordings) through 8 third-party vendors.

**Current Compliance Status:**
- DPAs Executed: 0/8 ❌
- SCCs Executed: 0/8 ❌
- Transfer Impact Assessments: 0/8 ❌
- Security Certifications Verified: 7/8 ⚠️ (Recall.ai unknown)

**Legal Risk Level:** 🔴 **CRITICAL**
- Processing without DPAs violates GDPR Art. 28
- Cross-border transfers without SCCs violate GDPR Art. 46
- Penalty exposure: Up to €20M or 4% of global turnover

---

## Document Index

### 1. VENDOR-RISK-REGISTER.md
**Purpose:** Complete vendor inventory with risk assessment and compliance tracking

**Key Contents:**
- Comprehensive vendor profile table (8 vendors)
- Risk level classification (Critical, High, Medium)
- SOC 2 certification status
- DPA and SCC execution status
- Cross-border transfer analysis
- Sub-processor disclosure tracking
- Data retention and deletion policies
- Incident response capabilities
- Audit rights status
- Vendor contact registry

**Primary Use Cases:**
- Monthly compliance reviews
- Vendor onboarding/offboarding
- Risk assessment and prioritization
- Audit preparation
- Executive reporting

**Critical Findings:**
- Recall.ai: SOC 2 status UNKNOWN (P0 priority)
- All 8 vendors: No DPAs executed (illegal processing)
- All 8 vendors: No SCCs executed (illegal transfers)
- 0/8 Transfer Impact Assessments completed

**Action Required:** Initiate DPA negotiations with all vendors (priority: Recall.ai → High-risk → Medium-risk)

---

### 2. DPA-TRACKING.md
**Purpose:** Data Processing Agreement execution workflow and status tracker

**Key Contents:**
- DPA execution tracker (all 8 vendors)
- DPA template library and review checklist
- Negotiation process guide (6-step workflow)
- SCC completion requirements
- Transfer Impact Assessment tracker
- Vendor contact initiation templates
- Compliance monitoring schedule
- Escalation procedures

**Primary Use Cases:**
- Track DPA negotiation progress
- Document vendor communications
- Manage legal review cycles
- Monitor execution timelines
- Identify negotiation blockers

**Workflow Stages:**
1. Initial Contact (Day 1)
2. Document Review (Day 2-5)
3. Negotiation (Day 6-14)
4. Execution (Day 15-21)
5. Administration (Day 22+)

**Action Required:** Send initial DPA request emails to all 8 vendors (templates provided)

---

### 3. SCC-REQUIREMENTS.md
**Purpose:** Standard Contractual Clauses requirements and Transfer Impact Assessment methodology

**Key Contents:**
- EU Commission 2021 SCCs overview (Module 2: Controller-to-Processor)
- SCC structure and required annexes (Annex I, II, III)
- Transfer Impact Assessment (TIA) methodology (Post-Schrems II)
- US surveillance law analysis (FISA 702, EO 12333, CLOUD Act)
- Supplementary measures framework (technical, contractual, organizational)
- Vendor-specific SCC requirements
- Implementation roadmap (16-week plan)
- Compliance dashboard

**Primary Use Cases:**
- Complete SCC annexes before execution
- Conduct Transfer Impact Assessments
- Identify supplementary measures for US transfers
- Document legal basis for cross-border transfers
- Annual TIA review and reassessment

**Critical Legal Requirements:**
- **Annex I.A:** List of Parties (data exporter and importer)
- **Annex I.B:** Description of Transfer (data categories, processing purpose, retention)
- **Annex I.C:** Competent Supervisory Authority (select DPA)
- **Annex II:** Technical and Organizational Measures (security controls)
- **Annex III:** Sub-Processor List (with locations and security measures)

**Transfer Impact Assessment (TIA) Process:**
1. Assess laws in destination country (USA surveillance laws)
2. Identify and implement supplementary measures
3. Document decision and monitoring plan

**Action Required:** Complete TIA for Recall.ai (CRITICAL priority), then high-risk vendors

---

### 4. VENDOR-SECURITY-QUESTIONNAIRE.md
**Purpose:** Comprehensive 90-question security and compliance assessment template

**Key Contents:**
- 11 sections covering all GDPR and security domains
- 90 detailed questions with response templates
- Supporting document request checklist
- Internal risk scoring matrix
- Vendor signature section

**Question Categories:**
1. Vendor Information (Q1-Q4)
2. Data Processing Details (Q5-Q18)
3. Security Certifications and Compliance (Q19-Q27)
4. Sub-Processors and Third Parties (Q28-Q32)
5. Technical and Organizational Security Measures (Q33-Q51)
6. Incident Response and Business Continuity (Q52-Q65)
7. Personnel Security (Q66-Q70)
8. Data Subject Rights and Assistance (Q71-Q74)
9. Audit Rights and Transparency (Q75-Q79)
10. Contractual and Legal (Q80-Q87)
11. Additional Information (Q88-Q90)

**Primary Use Cases:**
- Vendor due diligence before DPA execution
- Complete SCC Annex II (Technical and Organizational Measures)
- Identify security gaps requiring contractual remediation
- Support Transfer Impact Assessment (TIA)
- Ongoing vendor monitoring (annual review)

**Critical Questions (Deal-Breakers):**
- Q19: SOC 2 Type II certification
- Q24: GDPR compliance confirmation
- Q33-Q34: Encryption at rest and in transit
- Q53: Breach notification timeline (<72 hours)
- Q80-Q81: Willingness to execute DPA and SCCs

**Action Required:** Send questionnaire to all 8 vendors immediately (14-day response deadline)

---

## Implementation Roadmap

### Phase 1: Immediate Actions (Week 1-2)

**Priority 0: Recall.ai (CRITICAL)**
- [ ] Contact legal@recall.ai requesting SOC 2 Type II report
- [ ] Send Vendor Security Questionnaire
- [ ] Send DPA template and SCC Module 2
- [ ] Escalate to executive team if no response within 7 days

**All Vendors:**
- [ ] Send Vendor Security Questionnaire to all 8 vendors
- [ ] Send DPA request emails (use templates in DPA-TRACKING.md)
- [ ] Request sub-processor lists
- [ ] Request standard SCCs (if vendors have them)

**Internal Preparation:**
- [ ] Designate DPA negotiation lead (Legal Counsel)
- [ ] Assign vendor contacts to each vendor
- [ ] Set up contract management repository
- [ ] Schedule weekly compliance review meetings

---

### Phase 2: Documentation (Week 3-4)

**Receive and Review:**
- [ ] Review vendor security questionnaire responses
- [ ] Analyze vendor-provided DPAs (use checklist in DPA-TRACKING.md)
- [ ] Obtain SOC 2 reports (verify validity)
- [ ] Document sub-processor lists in Annex III

**Complete SCC Annexes:**
- [ ] Draft Annex I.A (List of Parties) for each vendor
- [ ] Draft Annex I.B (Processing Details) for each vendor
- [ ] Draft Annex I.C (Select Supervisory Authority)
- [ ] Draft Annex II (TOMs based on questionnaire responses)
- [ ] Draft Annex III (Sub-Processor Lists)

**Legal Review:**
- [ ] Internal legal counsel review all drafts
- [ ] Identify negotiation points
- [ ] Prepare redlines for vendor DPAs

---

### Phase 3: Execution (Week 5-8)

**Negotiate and Execute:**
- [ ] Send final DPAs to all vendors
- [ ] Conduct negotiation calls for contested clauses
- [ ] Execute DPAs via DocuSign/Adobe Sign
- [ ] Execute SCCs (Module 2) with all annexes
- [ ] Exchange fully executed copies

**Verify Execution:**
- [ ] Confirm both parties signed
- [ ] File in contract management system
- [ ] Update VENDOR-RISK-REGISTER.md status
- [ ] Update DPA-TRACKING.md status

---

### Phase 4: Transfer Impact Assessments (Week 9-12)

**Conduct TIAs (Use SCC-REQUIREMENTS.md methodology):**
- [ ] Recall.ai TIA (CRITICAL priority)
- [ ] LiveKit TIA (HIGH priority)
- [ ] Deepgram TIA (HIGH priority)
- [ ] Railway TIA (HIGH priority)
- [ ] Supabase TIA (HIGH priority)
- [ ] Groq TIA (MEDIUM priority)
- [ ] Cartesia TIA (MEDIUM priority)
- [ ] n8n Cloud TIA (MEDIUM priority)

**For Each TIA:**
1. Assess US surveillance law applicability
2. Identify required supplementary measures
3. Document residual risk
4. Obtain DPO and legal approval
5. Document decision to proceed/suspend

---

### Phase 5: Supplementary Measures (Week 13-16)

**Technical Measures:**
- [ ] Implement pseudonymization for participant IDs (Recall.ai, LiveKit)
- [ ] Implement PII redaction filters (Groq LLM inputs)
- [ ] Configure customer-managed encryption keys (if available)
- [ ] Test data deletion APIs (all vendors)

**Organizational Measures:**
- [ ] Migrate Supabase to EU region (Frankfurt/London)
- [ ] Migrate n8n Cloud to EU region
- [ ] Establish vendor transparency report monitoring
- [ ] Set up breach notification contact matrix

**Contractual Measures:**
- [ ] Verify transparency obligations in DPAs
- [ ] Verify legal challenge commitments in DPAs
- [ ] Document data localization migration plans

---

### Phase 6: Ongoing Monitoring (Continuous)

**Monthly Reviews:**
- [ ] Update DPA-TRACKING.md status
- [ ] Review vendor breach notifications
- [ ] Track sub-processor change notifications
- [ ] Update VENDOR-RISK-REGISTER.md

**Quarterly Reviews:**
- [ ] Verify all active vendors have executed DPAs
- [ ] Review security certifications (expiry dates)
- [ ] Test breach notification procedures
- [ ] Update risk scores

**Annual Reviews:**
- [ ] Reassess all Transfer Impact Assessments
- [ ] Obtain updated SOC 2 reports
- [ ] Review and update SCC Annexes
- [ ] Conduct vendor audits or review audit reports
- [ ] DPA renewal negotiations (if expiring)

---

## Vendor Contact Workflow

### Initial Outreach Email Template

```
Subject: Data Processing Agreement and GDPR Compliance - [Vendor Name]

Dear [Vendor Legal Team],

We are a current customer of [Vendor Service] (Account ID: [ID]) and require
execution of a Data Processing Agreement (DPA) and EU Commission 2021 Standard
Contractual Clauses (SCCs) to comply with GDPR.

We process personal data (including special category biometric data) from EU/EEA
data subjects and must ensure all vendor relationships meet regulatory requirements.

Please provide by [Date - 14 days from today]:

1. Your standard Data Processing Agreement (DPA) for enterprise customers
2. EU Commission 2021 Standard Contractual Clauses (Module 2: Controller-to-Processor)
3. Valid SOC 2 Type II report or equivalent security certification
4. Complete list of sub-processors (with locations and processing activities)
5. Responses to the attached Vendor Security Questionnaire

Alternatively, please review our attached DPA template and SCCs and advise on your
availability to execute these documents.

Our team:
- Legal Contact: [Name], [Email]
- Privacy Officer: [Name], [Email]
- Account Manager (your side): [Name, if known]

Target execution date: [Date - 30 days from today]

Please acknowledge receipt and confirm your point of contact for this process.

Thank you,
[Your Name]
[Title]
[Company]

Attachments:
- Vendor Security Questionnaire (90 questions)
- Standard DPA Template (if sending ours)
- EU Commission 2021 SCCs Module 2 (if sending ours)
```

---

## Escalation Matrix

### Vendor Non-Responsiveness

| Timeline | Action |
|----------|--------|
| Day 0 | Send initial contact email |
| Day 7 | Follow-up email to legal contact + sales contact |
| Day 14 | Escalate to account manager/customer success manager |
| Day 21 | Escalate to vendor executive sponsor (VP level) |
| Day 30 | Legal counsel letter of intent to suspend service |
| Day 45 | Service termination planning; identify replacement vendor |

### Unacceptable DPA Terms

| Issue | Response |
|-------|----------|
| No audit rights | Negotiate SOC 2 report sharing as alternative |
| Liability cap too low | Negotiate uncapped liability for GDPR violations |
| Breach notification >72 hours | Negotiate 24-hour SLA or contractual penalty |
| Broad license to use data | Negotiate "no training use" clause |
| No SCC willingness | **Deal-breaker** - cannot use vendor without SCCs |

### Critical Risk Vendors (Recall.ai)

**If Recall.ai cannot provide SOC 2 within 7 days:**
- [ ] Escalate to executive team (CTO, CEO, Legal)
- [ ] Initiate search for alternative meeting recording providers
- [ ] Assess self-hosted alternatives (Jitsi, BigBlueButton)
- [ ] Plan service migration within 30 days
- [ ] Notify affected customers of potential service change

---

## Key Performance Indicators (KPIs)

### Compliance Metrics

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| DPAs Executed | 100% (8/8) | 0% (0/8) | 🔴 CRITICAL |
| SCCs Executed | 100% (8/8) | 0% (0/8) | 🔴 CRITICAL |
| TIAs Completed | 100% (8/8) | 0% (0/8) | 🔴 CRITICAL |
| SOC 2 Verified | 100% (8/8) | 88% (7/8) | ⚠️ WARNING |
| Sub-Processor Lists Obtained | 100% (8/8) | 25% (2/8) | 🔴 CRITICAL |
| Audit Rights Established | 100% (8/8) | 0% (0/8) | 🔴 CRITICAL |

**Overall Compliance Score:** 🔴 **32/100** (CRITICAL - Immediate action required)

### Risk Metrics

| Vendor | DPA | SCC | TIA | SOC 2 | Overall Risk |
|--------|-----|-----|-----|-------|--------------|
| Recall.ai | ❌ | ❌ | ❌ | ❌ | 🔴 CRITICAL |
| LiveKit | ❌ | ❌ | ❌ | ✅ | 🟠 HIGH |
| Deepgram | ❌ | ❌ | ❌ | ✅ | 🟠 HIGH |
| Railway | ❌ | ❌ | ❌ | ✅ | 🟠 HIGH |
| Supabase | ❌ | ❌ | ❌ | ✅ | 🟠 HIGH |
| Groq | ❌ | ❌ | ❌ | ✅ | 🟡 MEDIUM |
| Cartesia | ❌ | ❌ | ❌ | ✅ | 🟡 MEDIUM |
| n8n Cloud | ❌ | ❌ | ❌ | ✅ | 🟡 MEDIUM |

---

## Responsible Parties

| Role | Responsibilities | Primary Contact |
|------|------------------|-----------------|
| **Legal Counsel** | DPA negotiation, SCC execution, legal review | [TBD] |
| **Data Protection Officer (DPO)** | TIA approval, GDPR oversight, DPA compliance | [TBD] |
| **Vendor Management Lead** | Vendor communications, tracking, escalation | [TBD] |
| **Security Team** | SOC 2 review, security questionnaire assessment | [TBD] |
| **Engineering/Product** | Technical supplementary measures, data architecture | [TBD] |
| **Executive Sponsor** | Final approval, budget allocation, strategic decisions | [TBD] |

---

## References and Resources

### GDPR Legal Basis
- **Article 28:** Processor obligations (DPA requirement)
- **Article 46:** Transfers via appropriate safeguards (SCCs)
- **Chapter V:** Transfers to third countries (TIA requirement)

### EU Commission Resources
- [EU Commission 2021 SCCs (Decision 2021/914)](https://eur-lex.europa.eu/eli/dec_impl/2021/914/oj)
- [EDPB Recommendations 01/2020: Supplementary Measures](https://edpb.europa.eu/our-work-tools/our-documents/recommendations/recommendations-012020-measures-supplement-transfer_en)

### Internal Documents
- VENDOR-RISK-REGISTER.md - Complete vendor inventory and risk assessment
- DPA-TRACKING.md - DPA execution workflow and status
- SCC-REQUIREMENTS.md - SCC structure, TIA methodology, implementation roadmap
- VENDOR-SECURITY-QUESTIONNAIRE.md - 90-question due diligence assessment

### Templates to Create (Future Work)
- `/compliance/gdpr/templates/STANDARD-DPA-TEMPLATE.md`
- `/compliance/gdpr/templates/SCC-MODULE-2-TEMPLATE.md`
- `/compliance/gdpr/templates/ANNEX-I-TEMPLATE.md`
- `/compliance/gdpr/templates/ANNEX-II-TEMPLATE.md`
- `/compliance/gdpr/templates/ANNEX-III-TEMPLATE.md`
- `/compliance/gdpr/templates/TIA-TEMPLATE.md`
- `/compliance/gdpr/templates/TIA-USA-SURVEILLANCE-ANALYSIS.md`

---

## Next Steps (Immediate Action Items)

### This Week (Week 1)
1. **Assign responsible parties** to roles above
2. **Send Vendor Security Questionnaire** to all 8 vendors (14-day deadline)
3. **Send DPA request emails** to all 8 vendors (use template above)
4. **Contact Recall.ai urgently** requesting SOC 2 Type II report (7-day deadline)
5. **Schedule weekly compliance meetings** (Legal, DPO, Vendor Management, Security)
6. **Set up contract repository** for tracking executed DPAs and SCCs

### Next Week (Week 2)
1. **Follow up** with vendors who haven't acknowledged (Day 7 escalation)
2. **Review incoming** security questionnaire responses
3. **Begin drafting** SCC Annex I for vendors who responded
4. **Legal counsel** begins DPA template review
5. **Identify** alternative vendors for Recall.ai (contingency planning)

### Week 3-4
1. **Complete all** SCC Annex drafts (I, II, III)
2. **Conduct legal review** of vendor-provided DPAs
3. **Prepare negotiation** talking points for contested clauses
4. **Internal approval** of DPA execution strategy

### Week 5-8
1. **Execute DPAs** with all vendors
2. **Execute SCCs** with all vendors
3. **File executed documents** in contract repository
4. **Update tracking** documents (VENDOR-RISK-REGISTER.md, DPA-TRACKING.md)

---

## Document Control

| Document | Version | Last Updated | Owner |
|----------|---------|--------------|-------|
| README.md (this file) | 1.0 | 2026-01-18 | Compliance Team |
| VENDOR-RISK-REGISTER.md | 1.0 | 2026-01-18 | Compliance Team |
| DPA-TRACKING.md | 1.0 | 2026-01-18 | Legal & Compliance |
| SCC-REQUIREMENTS.md | 1.0 | 2026-01-18 | Legal & Compliance |
| VENDOR-SECURITY-QUESTIONNAIRE.md | 1.0 | 2026-01-18 | Compliance Team |

**Document Suite Review Frequency:** Monthly
**Next Review Date:** 2026-02-18

**Approvals Required:**
- [ ] Legal Counsel
- [ ] Data Protection Officer (DPO)
- [ ] Chief Technology Officer (CTO)
- [ ] Chief Executive Officer (CEO)

---

## FAQ

**Q: Why are DPAs and SCCs required?**
A: GDPR Article 28 mandates written contracts (DPAs) with all processors. GDPR Article 46 requires "appropriate safeguards" (SCCs) for transfers to countries without an EU adequacy decision (including the USA).

**Q: What happens if we don't execute DPAs and SCCs?**
A: Processing personal data without DPAs is illegal under GDPR and exposes the company to:
- Supervisory authority fines (up to €20M or 4% of global turnover)
- Enforcement actions (suspension of processing)
- Civil liability (data subject compensation claims)
- Reputational damage

**Q: Can we continue using vendors while negotiating DPAs?**
A: Legally, no. However, practical reality requires risk-based prioritization:
- **CRITICAL risk (Recall.ai):** Urgent execution or service suspension
- **HIGH risk:** Accelerated timeline (30 days)
- **MEDIUM risk:** Standard timeline (60 days)

Document the risk acceptance decision with executive approval.

**Q: What if a vendor refuses to sign SCCs?**
A: SCCs are non-negotiable for US-based vendors. If a vendor refuses, you must either:
1. Find an alternative vendor with SCC willingness
2. Migrate to a vendor with EU establishment and data residency
3. Cease using the vendor (service termination)

**Q: How long does DPA execution typically take?**
A: Industry benchmarks:
- **Fast track (vendor has standard DPA):** 2-4 weeks
- **Standard negotiation:** 6-8 weeks
- **Complex negotiation:** 3-6 months

Our target: 30 days for all high-priority vendors.

**Q: Do we need a Transfer Impact Assessment (TIA) for every vendor?**
A: Yes, Post-Schrems II CJEU ruling requires a case-by-case TIA for each third-country transfer. This is not optional for US vendors.

**Q: Can we use a single DPA for all vendors?**
A: No, each vendor must have a separate DPA and SCC execution. However, you can use a standard template and customize Annexes.

**Q: What if Recall.ai cannot provide SOC 2?**
A: This is a deal-breaker for processing special category biometric data. Options:
1. Request alternative certification (ISO 27001)
2. Conduct direct third-party audit (expensive, time-consuming)
3. Replace vendor within 30 days

Our recommendation: Identify replacement vendors immediately as contingency.

---

## Contact Information

**For questions about this documentation suite:**
- Compliance Team: [compliance@company.com]
- Legal Counsel: [legal@company.com]
- Data Protection Officer: [dpo@company.com]

**For vendor-specific questions, see:**
- VENDOR-RISK-REGISTER.md (Vendor Contact Registry section)

---

**Document Status:** 🔴 ACTIVE - CRITICAL PRIORITY
**Action Required:** Immediate (Week 1 checklist above)
**Next Update:** 2026-01-25 (weekly during execution phase)
