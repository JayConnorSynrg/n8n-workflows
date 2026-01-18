# Audit Evidence Collection

**Purpose:** Centralized repository for compliance audit evidence
**Retention:** Minimum 2 years (SOC 2 requirement)
**Classification:** Confidential
**Access Control:** Security Team, DPO, Auditors only

## Directory Structure

```
evidence/
├── access-logs/          # System and administrative access logs
├── reviews/              # Policy reviews, training records, assessments
└── incidents/            # Security incidents and responses
```

## Evidence Categories

### Access Logs (`access-logs/`)

**Purpose:** Demonstrate access control effectiveness

**Required Logs:**
- User authentication events
- Administrative access to biometric data
- Privileged account usage
- Failed login attempts
- Access control changes

**Retention:** 90 days minimum (active), 2 years (archived)

**Format:** JSON log files with timestamp, user, action, resource

**Collection:** Automated export from SIEM/logging platform

### Reviews (`reviews/`)

**Purpose:** Document periodic reviews and assessments

**Subdirectories:**
- `policy-reviews/` - Annual policy review documentation
- `access-reviews/` - Quarterly access certification
- `training/` - Training completion records
- `risk-assessments/` - Periodic risk assessments
- `vendor-assessments/` - Third-party security reviews
- `policy-exceptions/` - Approved policy exceptions

**Retention:** 2 years minimum

**Format:** PDF documents with approval signatures, dates

### Incidents (`incidents/`)

**Purpose:** Track security incidents and responses

**Required Documentation:**
- Incident report (initial)
- Investigation notes
- Root cause analysis
- Remediation actions
- Post-incident review
- Lessons learned

**Retention:** 2 years minimum (5 years for data breaches)

**Format:** Structured incident report template

## Evidence Collection Schedule

| Evidence Type | Frequency | Owner | Automation |
|--------------|-----------|-------|------------|
| Access logs | Daily | Security Team | Automated export |
| Policy reviews | Annual | Policy Owners | Manual + Git tags |
| Access reviews | Quarterly | Security Team | Semi-automated |
| Training records | Per completion | HR | LMS export |
| Risk assessments | Quarterly | Security Team | Manual |
| Vendor assessments | Annual | Procurement | Manual |
| Incident reports | Per incident | Security Team | Manual |

## Evidence Index

Maintain evidence index in `evidence-index.json`:

```json
{
  "evidence_type": "access-logs",
  "date_range": "2026-01-01 to 2026-01-31",
  "file_path": "access-logs/2026-01/access-log-2026-01.json.gz",
  "hash": "sha256:...",
  "collected_by": "automated-export",
  "collection_date": "2026-02-01"
}
```

## Chain of Custody

All evidence must maintain chain of custody:

1. **Collection:** Automated or manual with timestamp
2. **Hashing:** SHA-256 hash recorded
3. **Storage:** Encrypted at rest
4. **Access:** Logged with audit trail
5. **Retention:** Archived per schedule
6. **Destruction:** Secure deletion after retention period

## Audit Preparation

Before external audit:

1. Review evidence index for completeness
2. Verify all required evidence collected
3. Test evidence retrieval process
4. Prepare evidence summary report
5. Provide auditor access to evidence portal

## Access Control

Evidence access restricted to:
- Security Team (read/write)
- DPO (read/write)
- External Auditors (read, time-limited)
- Executive Team (read, on request)

All access logged and reviewed quarterly.

---

**CONFIDENTIAL - Internal Use Only**
