# SYNRG Invoice Generator Workflow

**Version:** 1.0
**Platform:** n8n Cloud
**Status:** Development
**Created:** 2025-12-02

---

## Overview

Automated invoice generation workflow that creates professional PDF invoices from web form submissions. The system handles:
- Auto-incrementing invoice numbers (starting at 4200)
- Airtable record creation for invoices and line items
- Google Docs template-based PDF generation
- Conditional email delivery with PDF attachment
- Status tracking throughout the workflow

---

## Flow Diagram

```
Form Trigger → Process Form Data → Get Last Invoice → Generate Invoice ID
                                                              ↓
    ┌─────────────────────────────────────────────────────────┘
    ↓
Create Invoice Record → Create Line Item → Copy Template → Update Document
                                                                  ↓
    ┌─────────────────────────────────────────────────────────────┘
    ↓
Export as PDF → Check Email Provided ─┬─ [Email Exists] → Send Email ──┐
                                      │                                 │
                                      └─ [No Email] ───────────────────┼→ Update Stage → Form Response
                                                                        │
                                        ←──────────────────────────────┘
```

---

## Nodes (13 Total)

| # | Node Name | Type | Version | Purpose |
|---|-----------|------|---------|---------|
| 1 | Invoice Form | formTrigger | 2.3 | Web form for client/invoice data entry |
| 2 | Process Form Data | code | 2 | Calculate dates, totals, apply defaults |
| 3 | Get Last Invoice | airtable | 2.1 | Fetch highest invoice number |
| 4 | Generate Invoice ID | code | 2 | Increment invoice number |
| 5 | Create Invoice Record | airtable | 2.1 | Insert invoice into SYNRG_Invoices |
| 6 | Create Line Item | airtable | 2.1 | Insert line item with invoice link |
| 7 | Copy Invoice Template | googleDrive | 3 | Duplicate template document |
| 8 | Update Invoice Document | googleDocs | 2 | Replace placeholders with data |
| 9 | Export as PDF | googleDrive | 3 | Convert to PDF format |
| 10 | Check Email Provided | if | 2.2 | Conditional email check |
| 11 | Send Invoice Email | gmail | 2.1 | Email PDF to client |
| 12 | Update Invoice Stage | airtable | 2.1 | Set stage to "Distribution" |
| 13 | Form Response | respondToWebhook | 1.4 | Return success JSON |

---

## Required Credentials

### Airtable Personal Access Token
- **Name:** SYNRG Airtable
- **Scopes:** `data.records:read`, `data.records:write`, `schema.bases:read`

### Google OAuth2
- **Name:** SYNRG Google
- **Scopes:**
  - `https://www.googleapis.com/auth/documents`
  - `https://www.googleapis.com/auth/drive`
  - `https://www.googleapis.com/auth/drive.file`
  - `https://www.googleapis.com/auth/gmail.send`

---

## Airtable Configuration

### Base & Table IDs
- **Base ID:** `app9XfArSh5A2BJ3x`
- **SYNRG_Invoices Table ID:** `tblcuPbud8EYloNHh`
- **Line_Items Table ID:** `tblzcObEwjIvZe9Kp`

### SYNRG_Invoices Fields
| Field | Type | Description |
|-------|------|-------------|
| Invoice_ID | Number/Text | Auto-incremented (4200+) |
| Client_Name | Text | Required |
| Client_Email | Email | Optional |
| Client_Company | Text | Optional |
| Invoice_Date | Date | ISO format |
| Due_Date | Date | ISO format |
| Payment_Terms | Single Select | Due on Receipt, Net 7/15/30 |
| Service_Type | Single Select | Tech Services, Automation, etc. |
| Project_Summary | Long Text | Project description |
| Subtotal | Currency | Numeric value |
| Discounts | Currency | Numeric value |
| Tax | Currency | Numeric value |
| Total_Due | Currency | Calculated |
| Payment_Status | Single Select | Pending/Paid |
| STAGE | Single Select | Intake/Distribution |

### Line_Items Fields
| Field | Type | Description |
|-------|------|-------------|
| Service | Text | Service type |
| Description | Long Text | Line item description |
| Qty_Hrs | Number | Quantity or hours |
| Rate | Currency | Rate per unit |
| Amount | Currency | Calculated (Qty * Rate) |
| Invoice | Linked Record | Link to SYNRG_Invoices |

---

## Google Docs Template

### Required Placeholders
Your Google Docs template must contain these exact placeholders:

```
{{INVOICE_ID}}
{{CLIENT_NAME}}
{{CLIENT_COMPANY}}
{{CLIENT_EMAIL}}
{{INVOICE_DATE}}
{{DUE_DATE}}
{{PAYMENT_TERMS}}
{{SERVICE_TYPE}}
{{PROJECT_SUMMARY}}
{{LINE_SERVICE}}
{{LINE_DESCRIPTION}}
{{LINE_QTY}}
{{LINE_RATE}}
{{LINE_AMOUNT}}
{{SUBTOTAL}}
{{DISCOUNTS}}
{{TAX}}
{{TOTAL_DUE}}
```

### Template Setup
1. Create a Google Doc with your invoice design
2. Insert the placeholders above where data should appear
3. Get the Document ID from the URL
4. Update the `Copy Invoice Template` node with your template ID

**Current Template ID:** `13mnhbrhpb-J910qOjsjwvgWbbppG-BeW`

---

## Form Fields

| Field ID | Label | Type | Required | Default |
|----------|-------|------|----------|---------|
| client_name | Client Name | text | YES | - |
| client_email | Client Email | email | NO | - |
| client_company | Client Company | text | NO | - |
| service_type | Service Type | dropdown | NO | Tech Services |
| payment_terms | Payment Terms | dropdown | NO | Net 7 |
| project_summary | Project Summary | textarea | NO | (default text) |
| line_service | Line Item - Service | text | NO | Tech Services |
| line_description | Line Item - Description | textarea | NO | (default text) |
| line_qty | Quantity/Hours | number | NO | 1 |
| line_rate | Rate ($) | number | NO | 5000 |
| subtotal | Subtotal ($) | number | NO | 5000 |
| discounts | Discounts ($) | number | NO | 0 |
| tax | Tax ($) | number | NO | 0 |

---

## Error Handling

| Node | Error Behavior | Rationale |
|------|---------------|-----------|
| Get Last Invoice | Continue on error | First invoice scenario |
| Create Invoice Record | Stop workflow | Critical - can't proceed without record |
| Create Line Item | Continue on error | Non-critical for PDF generation |
| Copy Invoice Template | Stop workflow | Critical - template needed for PDF |
| Update Invoice Document | Continue on error | PDF still created if replace fails |
| Export as PDF | Stop workflow | Critical - PDF required for email |
| Send Invoice Email | Continue on error | Invoice still created without email |
| Update Invoice Stage | Continue on error | Non-critical status update |

---

## Deployment Steps

1. **Credentials Setup**
   - Create Airtable Personal Access Token
   - Configure Google OAuth2 with required scopes

2. **Airtable Tables**
   - Verify SYNRG_Invoices table has all required fields
   - Verify Line_Items table with Invoice linked record field

3. **Google Docs Template**
   - Create invoice template with placeholders
   - Update template ID in workflow

4. **Deploy to n8n**
   - Import workflow JSON
   - Configure credential references
   - Activate workflow

5. **Test**
   - Submit test form
   - Verify Airtable records
   - Check PDF generation
   - Confirm email delivery (if address provided)

---

## Form URL

Once deployed, form will be available at:
```
https://[your-n8n-instance]/form/invoice-form
```

---

## Response Format

```json
{
  "success": true,
  "message": "Invoice 4200 created successfully!",
  "invoice_id": "4200",
  "client_name": "John Doe",
  "total_due": "$5,000.00",
  "email_sent": true
}
```

---

## Changelog

### v1.0 (2025-12-02)
- Initial workflow implementation
- 13 nodes with latest typeVersions
- Form trigger with 13 fields
- Auto-incrementing invoice numbers starting at 4200
- PDF generation via Google Docs template
- Conditional email delivery
- Airtable integration for records and line items
- Error handling on all critical nodes
