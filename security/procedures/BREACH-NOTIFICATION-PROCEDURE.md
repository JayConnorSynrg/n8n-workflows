# GDPR Breach Notification Procedure

**Document Version:** 1.0
**Effective Date:** 2026-01-18
**Last Reviewed:** 2026-01-18
**Next Review Date:** 2026-07-18
**Owner:** Data Protection Officer
**Approval Status:** DRAFT - Pending Authorization

---

## 1. Purpose and Scope

This procedure establishes the framework for GDPR-compliant breach notification in accordance with:
- **GDPR Article 33:** Notification of personal data breach to supervisory authority
- **GDPR Article 34:** Communication of personal data breach to data subjects
- **GDPR Recital 85-88:** Breach notification requirements and timelines

**Applicable Data:**
- Personal data of EU/EEA residents
- Special category data (biometric voice recordings from LiveKit)
- Enterprise data containing personal identifiers
- Authentication credentials and access logs

---

## 2. Legal Framework and Requirements

### 2.1 Key Definitions

**Personal Data Breach (GDPR Article 4(12)):**
> "A breach of security leading to the accidental or unlawful destruction, loss, alteration, unauthorised disclosure of, or access to, personal data transmitted, stored or otherwise processed."

**Breach Categories:**
- **Confidentiality Breach:** Unauthorized disclosure or access
- **Integrity Breach:** Unauthorized alteration of data
- **Availability Breach:** Accidental or unauthorized loss/destruction

### 2.2 Notification Thresholds

| Criterion | Supervisory Authority Notification | Data Subject Notification |
|-----------|-----------------------------------|---------------------------|
| **Risk Assessment** | Breach likely to result in risk to rights and freedoms | High risk to rights and freedoms |
| **Timeline** | Within 72 hours of becoming aware | Without undue delay (typically concurrent with authority notification) |
| **Exceptions** | Low-risk breaches with documented assessment | Effective technical/organizational protection measures applied OR supervisory authority determines no high risk |

**Risk Factors (GDPR Recital 75-76):**
- Type and sensitivity of data (special category = high risk)
- Volume of records affected (>1000 = presumed high risk)
- Ease of identification of individuals
- Severity of consequences (financial, reputational, physical harm)
- Vulnerable populations affected (children, employees)

---

## 3. The 72-Hour Timeline

### Hour 0: Breach Awareness
**Trigger:** First moment when organization becomes aware a breach has occurred

**Awareness Defined:**
- Receipt of credible breach report
- Detection via security monitoring
- Third-party notification of breach
- **NOT** initial suspicious activity (must confirm breach occurred)

**Immediate Actions (0-2 hours):**
1. Document exact time of breach awareness (timestamp in incident log)
2. Assign Data Protection Officer to lead notification process
3. Begin preliminary breach assessment
4. Preserve all evidence related to breach
5. Initiate containment procedures (see Incident Response Plan)

---

### Hours 0-24: Assessment and Preparation

**Breach Assessment (DPO + Security Lead)**

**Required Information Collection:**
1. **Nature of Breach**
   - Confidentiality, integrity, or availability breach
   - Attack vector and root cause
   - Duration of unauthorized access/exposure
   - Whether breach is ongoing or contained

2. **Data Categories Affected**
   - Types of personal data (names, emails, addresses, etc.)
   - Special category data (biometric voice recordings, health data)
   - Volume of records affected (exact count or reasonable estimate)
   - Data subjects affected (employees, customers, EU residents)

3. **Likely Consequences**
   - Identity theft risk
   - Financial harm potential
   - Reputational damage
   - Discrimination or other harm to vulnerable groups
   - Physical safety implications

4. **Measures Taken**
   - Containment actions completed
   - Remediation steps initiated
   - Measures to mitigate adverse effects on data subjects

**Risk Classification Decision:**
```
IF special_category_data_exposed OR records_affected > 1000 OR easy_identification:
    supervisory_authority_notification = REQUIRED
    data_subject_notification = LIKELY REQUIRED

IF risk_to_rights_and_freedoms == "unlikely":
    supervisory_authority_notification = NOT REQUIRED
    document_decision_in_breach_register = REQUIRED
```

**Deliverables (by Hour 24):**
- Completed breach assessment report
- Risk classification determination
- Notification decision (authority + data subjects)
- Draft notifications prepared

---

### Hours 24-48: Internal Approvals and Coordination

**Actions:**
1. **Legal Review**
   - General Counsel approval of notification content
   - Verify compliance with GDPR requirements
   - Assess other regulatory obligations (ePrivacy, national laws)

2. **Executive Briefing**
   - CTO and CEO notification
   - Business impact assessment
   - Reputational risk evaluation
   - Approval to proceed with notification

3. **Supervisory Authority Identification**
   - **Lead Authority:** Data protection authority of main establishment
   - **Concerned Authorities:** If cross-border processing, notify all concerned authorities
   - **For N8N Workflows:** Likely Irish DPC (if EU headquarters in Ireland) OR authority of primary EU customer base

4. **Final Notification Preparation**
   - Complete all required information fields
   - Translate notifications if required
   - Prepare supporting documentation
   - Coordinate with incident response team on technical details

---

### Hours 48-72: Notification Submission

**Supervisory Authority Notification (REQUIRED within 72 hours)**

**Submission Method:**
- Use supervisory authority's designated breach notification portal
- **Ireland (DPC):** https://forms.dataprotection.ie/contact
- **Germany (BfDI):** https://www.bfdi.bund.de/EN/Home/home_node.html
- **Alternative:** Email to authority's breach notification address

**Notification Content (GDPR Article 33(3)):**
1. Nature of personal data breach (categories, approximate records)
2. Name and contact details of Data Protection Officer
3. Description of likely consequences of breach
4. Measures taken/proposed to address breach and mitigate effects

**Documentation to Attach:**
- Incident timeline
- Technical analysis of breach
- Risk assessment report
- Evidence of containment measures

**Submission Confirmation:**
- Obtain submission receipt/reference number
- Document submission timestamp
- Schedule follow-up communications if required

---

### Hours 72-96: Data Subject Notification

**Triggers for Data Subject Notification (GDPR Article 34):**
- High risk to rights and freedoms of individuals
- Unable to demonstrate effective protection measures applied
- Supervisory authority requires notification

**Exemptions from Data Subject Notification:**
- Effective technical protection measures applied (e.g., encryption with keys not compromised)
- Subsequent measures ensure high risk no longer likely
- Disproportionate effort (large-scale breach) AND public communication made

**Notification Method:**
- **Direct Communication:** Email to each affected data subject (preferred)
- **Public Communication:** If direct contact impossible or disproportionate effort
- **Plain Language:** Clear, understandable terms (no legal jargon)

**Timing:**
- Without undue delay (typically 72-96 hours)
- May be delayed if law enforcement requests (must document)

---

## 4. Notification Templates

### 4.1 Supervisory Authority Notification Template

```
SUBJECT: Personal Data Breach Notification pursuant to GDPR Article 33

[Supervisory Authority Name]
[Address]

Date: [Submission Date]
Reference: [Internal Incident ID]

Dear [Authority Name],

We are writing to notify you of a personal data breach affecting our organization in accordance with Article 33 of the General Data Protection Regulation (GDPR).

---

1. ORGANIZATION DETAILS

Data Controller:
- Name: [Organization Legal Name]
- Registration Number: [Company Registration]
- Address: [Registered Address]
- Contact: [Primary Contact Name, Phone, Email]

Data Protection Officer:
- Name: [DPO Name]
- Email: [DPO Email]
- Phone: [DPO Phone]

---

2. BREACH AWARENESS TIMESTAMP

We became aware of this breach on [Date] at [Time] [Timezone].

This notification is submitted [within 72 hours / after 72 hours - reason for delay].

---

3. NATURE OF THE PERSONAL DATA BREACH

3.1 Breach Type:
[X] Confidentiality breach (unauthorized access/disclosure)
[ ] Integrity breach (unauthorized alteration)
[ ] Availability breach (loss/destruction)

3.2 Description of Incident:
[Detailed narrative of what occurred, how breach happened, attack vector, timeline of events]

Example:
"On [date], our security monitoring detected unauthorized access to the N8N workflow automation platform database containing customer contact information and voice recording metadata. The breach occurred through a compromised OAuth token for a third-party integration service. The unauthorized access lasted approximately [duration] before containment measures were implemented."

3.3 Affected Systems:
- N8N Workflow Platform (version [x.x.x])
- PostgreSQL Database: Microsoft Teams Agent Database
- LiveKit Voice Agent Infrastructure
- [Other affected systems]

---

4. CATEGORIES AND VOLUME OF DATA AFFECTED

4.1 Categories of Personal Data:
[ ] Names
[ ] Email addresses
[ ] Phone numbers
[ ] Postal addresses
[X] Voice recordings (biometric data - special category)
[ ] Authentication credentials
[ ] Payment information
[ ] [Other categories]

4.2 Special Category Data (GDPR Article 9):
[X] Biometric data (voice recordings used for identification)
[ ] Health data
[ ] Other: [specify]

4.3 Volume of Data Subjects Affected:
- Approximate number: [X] data subjects
- Geographic distribution: [X% EU/EEA residents]
- Vulnerable groups: [if applicable - children, employees, etc.]

4.4 Volume of Records:
- Personal data records affected: [X] records
- Special category data records: [X] voice recordings

---

5. LIKELY CONSEQUENCES OF THE BREACH

5.1 Risk Assessment:
[X] High risk to rights and freedoms
[ ] Risk (but not high risk)
[ ] Unlikely to result in risk

5.2 Potential Consequences:
[Detailed assessment of potential harm to data subjects]

Example:
"The exposure of voice recordings constitutes a breach of biometric data, creating risk of identity theft, unauthorized account access, and reputational harm. The combination of voice biometrics with contact information increases the risk of targeted social engineering attacks. Affected individuals may experience financial loss if voice authentication systems are compromised at third-party services."

5.3 Vulnerable Populations:
[If applicable - children, employees in sensitive roles, etc.]

---

6. MEASURES TAKEN OR PROPOSED

6.1 Containment Measures (Completed):
- [Date/Time] Revoked compromised OAuth token
- [Date/Time] Disabled affected n8n workflow instances
- [Date/Time] Rotated all database credentials
- [Date/Time] Implemented additional access controls
- [Date/Time] Isolated affected systems from network

6.2 Remediation Actions (In Progress):
- Enhanced monitoring deployed on affected systems
- Security audit of all third-party integrations
- Multi-factor authentication enforcement
- Vulnerability patching [completion date]

6.3 Mitigation Measures for Data Subjects:
- Credit monitoring services offered (if applicable)
- Guidance on changing voice authentication settings
- 24-hour support hotline established: [phone/email]
- Notification to affected individuals [date planned]

6.4 Preventive Measures (Planned):
- OAuth token rotation policy (quarterly)
- Enhanced anomaly detection rules
- Third-party security review process
- Staff security training program

---

7. CROSS-BORDER PROCESSING

[ ] This breach affects data subjects in multiple EU/EEA member states
[X] This is a single-country incident

If cross-border:
Lead Supervisory Authority: [Authority Name]
Concerned Authorities: [List all]

---

8. SUPPORTING DOCUMENTATION

Attached:
- Incident timeline (detailed chronology)
- Technical analysis report
- Risk assessment documentation
- Evidence of containment measures
- [Other relevant documentation]

---

9. FOLLOW-UP COMMUNICATION

[ ] This is our initial notification with partial information
[X] This is a complete notification with all required information

If phased notification:
Expected timeline for complete information: [Date]
Reason for phased approach: [Explanation]

---

10. ADDITIONAL INFORMATION

[Any other relevant information, context, or explanations]

---

We remain available to provide any additional information or clarification you may require. Please contact our Data Protection Officer at [DPO Email/Phone] for any questions.

We will provide regular updates on our remediation efforts and are committed to full cooperation with your authority.

Yours sincerely,

[Data Protection Officer Name]
Data Protection Officer
[Organization Name]

Attachments: [List all]
```

---

### 4.2 Data Subject Notification Template

**Subject Line:** Important Security Notice - Action Required

```
Dear [Data Subject Name],

We are writing to inform you of a security incident that may affect your personal information held by [Organization Name]. We take the protection of your data very seriously and want to provide you with full details of what happened, what information was involved, and what we are doing about it.

---

WHAT HAPPENED

On [Date], we discovered unauthorized access to our systems that process customer information. [Brief, clear explanation of incident in plain language].

We became aware of this incident on [Date] and immediately took steps to secure our systems and investigate the full scope of the breach.

---

WHAT INFORMATION WAS INVOLVED

Our investigation determined that the following information relating to you may have been accessed:

[ ] Your name
[ ] Your email address
[ ] Your phone number
[X] Voice recordings from [service/interaction description]
[ ] [Other data categories]

[If special category data:]
IMPORTANT: This incident involved voice recordings, which are considered biometric data under data protection law. This type of data receives enhanced protection due to its sensitive nature.

---

WHAT WE ARE DOING

We have taken immediate action to protect your information:

1. [Specific containment action - e.g., "Disabled the affected system within 2 hours"]
2. [Remediation action - e.g., "Changed all system passwords and access credentials"]
3. [Enhanced security - e.g., "Implemented additional monitoring and access controls"]
4. [External support - e.g., "Engaged cybersecurity forensics firm to investigate"]

We have also reported this incident to the [Supervisory Authority Name] as required by law.

---

WHAT YOU CAN DO

We recommend you take the following precautions:

1. **Monitor Your Accounts:** Watch for any unusual activity on accounts where you use voice authentication
2. **Change Authentication Methods:** Consider using alternative authentication methods (password, PIN) for sensitive accounts
3. **Be Alert for Scams:** Be cautious of unexpected emails, calls, or messages claiming to be from us or using your voice
4. **Review Voice Settings:** Check security settings on any services where you've enrolled voice authentication

[If offering support services:]
We are offering the following support at no cost to you:
- [Credit monitoring service for 12 months]
- [Identity theft protection assistance]
- [Dedicated support hotline: [phone] / [email]]

---

YOUR RIGHTS

Under data protection law, you have the right to:
- Request access to your personal data we hold
- Request correction of inaccurate data
- Request deletion of your data (in certain circumstances)
- Object to processing of your data
- Lodge a complaint with the supervisory authority: [Authority Name and Contact]

To exercise any of these rights, please contact our Data Protection Officer at [DPO Email/Phone].

---

MORE INFORMATION

We have created a dedicated webpage with detailed information and frequently asked questions: [URL]

If you have any questions or concerns, please contact us:
- Email: [Incident Response Email]
- Phone: [Support Hotline]
- Hours: [Availability]

We sincerely apologize for this incident and any concern it may cause. Protecting your data is our highest priority, and we are committed to preventing incidents like this in the future.

Yours sincerely,

[Senior Executive Name]
[Title]
[Organization Name]

---

Data Protection Officer Contact:
[DPO Name]
[DPO Email]
[DPO Phone]
```

---

### 4.3 Internal Escalation Notification Template

**TO:** Executive Leadership Team
**FROM:** Data Protection Officer
**SUBJECT:** URGENT: Personal Data Breach - Executive Action Required
**CLASSIFICATION:** CONFIDENTIAL

```
EXECUTIVE SUMMARY

A personal data breach affecting [X] individuals has been detected. This notification requires immediate executive decision-making and potential regulatory notification within 72 hours.

BREACH CLASSIFICATION: [SEV-1 / SEV-2 / SEV-3]
GDPR NOTIFICATION REQUIRED: [YES / NO / UNDER ASSESSMENT]
DATA SUBJECTS NOTIFICATION REQUIRED: [YES / NO / UNDER ASSESSMENT]

---

KEY FACTS

Breach Detection: [Date and Time]
Affected Data: [Brief summary - e.g., "Voice recordings (biometric data) + contact information"]
Number of Individuals: [X] data subjects ([Y%] EU/EEA residents)
Current Status: [Contained / Under Investigation / Ongoing]

---

IMMEDIATE ACTIONS REQUIRED

1. [Executive Approval] Review and approve supervisory authority notification (due: [Date/Time])
2. [Resource Allocation] Authorize incident response resources and budget
3. [Communications] Approve external communications strategy
4. [Legal] Engage external legal counsel (if required)

---

TIMELINE

Hour 0 (Breach Awareness): [Date/Time]
Hour 24: Risk assessment complete
Hour 48: Notification drafts ready for approval
Hour 72: Supervisory authority notification deadline: [Date/Time]

---

NEXT STEPS

Immediate: Executive briefing scheduled for [Date/Time]
24 Hours: Legal review and approval
48 Hours: Final notification preparation
72 Hours: Supervisory authority submission

---

CONTACT

Data Protection Officer: [Name], [Phone], [Email]
Incident Commander: [Name], [Phone], [Email]

Full incident details available in incident management system: [Ticket ID]
```

---

## 5. Internal Escalation Matrix

| Breach Severity | Notification Timing | Recipients | Method |
|----------------|-----------------------|------------|--------|
| **SEV-1** (Special category data, >1000 records) | Immediate (within 15 min) | CEO, CTO, General Counsel, DPO, Board Chair | Phone call + email |
| **SEV-2** (PII breach, <1000 records) | Within 1 hour | CTO, General Counsel, DPO | Email + Slack |
| **SEV-3** (Limited scope, no special category) | Within 4 hours | DPO, Security Lead, Legal | Email |
| **SEV-4** (No breach / false positive) | Next business day | DPO, Security Lead | Email summary |

---

## 6. Documentation and Record-Keeping

### 6.1 Breach Register (GDPR Article 33(5))

**Mandatory Documentation for ALL Breaches (even if not reported):**

| Field | Description | Example |
|-------|-------------|---------|
| Breach ID | Unique identifier | BR-2026-001 |
| Detection Date/Time | When organization became aware | 2026-01-18 14:32 UTC |
| Breach Category | Confidentiality/Integrity/Availability | Confidentiality |
| Data Categories | Types of personal data affected | Name, email, voice recordings |
| Special Category | GDPR Article 9 data involved | Biometric data (voice) |
| Data Subjects Count | Number of individuals affected | 1,247 |
| Geographic Scope | Countries/regions affected | EU (Ireland, Germany, France) |
| Root Cause | How breach occurred | Compromised OAuth token |
| Risk Assessment | Risk level determined | High risk |
| Notification Decision | Authority/subjects notified? | Both notified |
| Authority Notified | Which supervisory authority | Irish DPC |
| Notification Date | When notification submitted | 2026-01-20 09:15 UTC |
| Subject Notification | Data subjects informed? | Yes - 2026-01-20 |
| Outcome | Resolution and lessons learned | System hardened, MFA enforced |

**Retention:** Indefinite (supervisory authority may inspect at any time)

### 6.2 Supporting Documentation

**Required Documents (retain for 7 years minimum):**
1. Initial breach assessment report
2. Risk assessment and methodology
3. Notification decision rationale (if not notifying)
4. Copies of all notifications sent (authority + data subjects)
5. Supervisory authority correspondence
6. Incident response timeline
7. Evidence of containment and remediation
8. Post-incident review and lessons learned
9. Legal counsel opinions (privileged)

---

## 7. Supervisory Authority Contact Information

### Primary EU/EEA Data Protection Authorities

| Country | Authority | Breach Notification Portal | Email | Phone |
|---------|-----------|---------------------------|-------|-------|
| **Ireland** | Data Protection Commission (DPC) | https://forms.dataprotection.ie/contact | info@dataprotection.ie | +353 578 684 800 |
| **Germany** | Bundesbeauftragte für den Datenschutz und die Informationsfreiheit (BfDI) | https://www.bfdi.bund.de | poststelle@bfdi.bund.de | +49 228 997799-0 |
| **France** | Commission Nationale de l'Informatique et des Libertés (CNIL) | https://www.cnil.fr/en/notifying-data-breach | Notification via online form | +33 1 53 73 22 22 |
| **Netherlands** | Autoriteit Persoonsgegevens (AP) | https://autoriteitpersoonsgegevens.nl/en/report-a-data-breach | datalek@autoriteitpersoonsgegevens.nl | +31 70 888 8500 |
| **Spain** | Agencia Española de Protección de Datos (AEPD) | https://www.aepd.es/es/derechos-y-deberes/cumple-tus-deberes/notificaciones-brechas-seguridad | Notification via Notifica portal | +34 912 663 517 |
| **UK** (Post-Brexit) | Information Commissioner's Office (ICO) | https://ico.org.uk/for-organisations/report-a-breach/ | casework@ico.org.uk | +44 303 123 1113 |

**Note:** If cross-border processing, notify lead supervisory authority (main establishment) who will coordinate with concerned authorities.

---

## 8. Decision Tree: Do We Need to Notify?

```
START: Personal data breach detected
    |
    v
Is there risk to rights and freedoms of individuals?
    |
    +-- NO --> Document decision in breach register (no notification required)
    |
    +-- YES / UNCERTAIN --> Proceed to notification assessment
            |
            v
        Assess risk level:
            |
            +-- UNLIKELY RISK --> No notification, document in register
            |
            +-- LIKELY RISK --> Notify supervisory authority (72 hours)
            |
            +-- HIGH RISK --> Notify supervisory authority AND data subjects
                    |
                    v
                Exemptions apply?
                    |
                    +-- Effective encryption (keys not compromised) --> May exempt subject notification
                    +-- Subsequent measures eliminate high risk --> May exempt subject notification
                    +-- Disproportionate effort + public communication --> Alternative notification method
                    +-- NONE APPLY --> Direct notification to all data subjects required
```

**Risk Factors Checklist:**
- [ ] Special category data (biometric, health, etc.)
- [ ] Large volume (>1000 records = presumed high risk)
- [ ] Easy identification of individuals
- [ ] Vulnerable populations (children, employees)
- [ ] Potential for identity theft, fraud, financial loss
- [ ] Potential for discrimination or reputational harm
- [ ] Data not encrypted or encryption compromised

**If 2+ factors checked: Likely high risk - notify both authority and data subjects**

---

## 9. Training and Awareness

### 9.1 DPO Training Requirements
- GDPR breach notification procedures (annual certification)
- Risk assessment methodology
- Supervisory authority communication
- Data subject communication best practices

### 9.2 IRT Training
- Breach identification and classification
- Evidence preservation for regulatory compliance
- 72-hour timeline management
- Coordination with DPO and legal

### 9.3 Management Training
- Executive decision-making in breach scenarios
- Reputational risk management
- Media and stakeholder communications

---

## 10. Related Documents

- `INCIDENT-RESPONSE-PLAN.md` - Overall incident response procedures
- `INCIDENT-CLASSIFICATION-MATRIX.md` - Severity definitions
- `DATA-CLASSIFICATION-POLICY.md` - Data category definitions
- `PRIVACY-POLICY.md` - Public-facing privacy commitments
- `/security/templates/` - Notification templates and forms

---

## 11. Approval and Distribution

### Approval Signatures

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Data Protection Officer | ___________________ | ___________________ | ________ |
| General Counsel | ___________________ | ___________________ | ________ |
| Chief Technology Officer | ___________________ | ___________________ | ________ |

### Distribution List
- Data Protection Officer (controlled copy)
- Incident Response Team (controlled copy)
- Legal and compliance teams (controlled copy)
- Executive leadership (read-only)

---

**Document Classification:** CONFIDENTIAL - INTERNAL USE ONLY
**Retention Period:** Indefinite (regulatory requirement)
**Next Review Date:** 2026-07-18
