# Pattern: Use HTTP Request for Google Docs batchUpdate

> **Priority**: MEDIUM
>
> **Workflow**: SYNRG Invoice Generator (ID: Ge33EW4K3WVHT4oG)
>
> **Date**: 2025-12-03

---

## Anti-Pattern: Using Native Google Docs Node for replaceAllText Operations

### What Happened

When building the Invoice Generator workflow, I used the native `n8n-nodes-base.googleDocs` node (typeVersion 2) with the "Update a Document" operation to replace template placeholders (e.g., `{{INVOICE_ID}}`, `{{CLIENT_NAME}}`). Despite correct credential configuration and Google Docs API being enabled, the node consistently returned:

```
Bad request - please check your parameters
```

Multiple fix attempts failed:
1. Adding `"object": "text"` property to action fields - Still failed
2. Verifying credentials were from same Google Cloud project - Still failed
3. Confirming Google Docs API was enabled - Still failed
4. Researching n8n documentation and community threads - Found evidence of known issues

### Impact

- Invoice workflow could not populate templates with client data
- PDF generation pipeline was completely blocked
- Required extensive debugging (3+ iterations) to identify root cause
- User could not generate invoices until workaround was implemented
- Delayed workflow deployment by several hours

### Why It Failed

- The native Google Docs node has known reliability issues with the `replaceAll` operation
- n8n's abstraction layer may not correctly format the batchUpdate API request
- Official n8n template #3145 ("Replace Data in Google Docs from n8n Form") notably uses HTTP Request instead of native Google Docs node for the same operation
- The native node's error messages are not helpful ("Bad request" without specifics)
- TypeVersion 2 of the Google Docs node may have bugs in the replaceAllText parameter handling

---

## Positive Pattern: Use HTTP Request Node with Google Docs batchUpdate API

### Solution

Replace the native Google Docs node with a Code node (to format requests) + HTTP Request node calling the Google Docs batchUpdate API directly.

### Implementation

**1. Add "Format Replace Requests" Code Node:**

```javascript
// Format data for Google Docs API batchUpdate
const data = $('Generate Invoice ID').first().json;
const docId = $('Copy Invoice Template').first().json.id;

// Build replaceAllText requests array
const replacements = [
  { placeholder: '{{INVOICE_ID}}', value: data.invoice_id || '' },
  { placeholder: '{{CLIENT_NAME}}', value: data.client_name || '' },
  { placeholder: '{{CLIENT_COMPANY}}', value: data.client_company || '' },
  { placeholder: '{{CLIENT_EMAIL}}', value: data.client_email || '' },
  { placeholder: '{{INVOICE_DATE}}', value: data.invoice_date || '' },
  { placeholder: '{{DUE_DATE}}', value: data.due_date || '' },
  { placeholder: '{{PAYMENT_TERMS}}', value: data.payment_terms || '' },
  { placeholder: '{{SERVICE_TYPE}}', value: data.service_type || '' },
  { placeholder: '{{PROJECT_SUMMARY}}', value: data.project_summary || '' },
  { placeholder: '{{LINE_SERVICE}}', value: data.line_service || '' },
  { placeholder: '{{LINE_DESCRIPTION}}', value: data.line_description || '' },
  { placeholder: '{{LINE_QTY}}', value: String(data.line_qty || '') },
  { placeholder: '{{LINE_RATE}}', value: data.line_rate_formatted || '' },
  { placeholder: '{{LINE_AMOUNT}}', value: data.line_amount_formatted || '' },
  { placeholder: '{{SUBTOTAL}}', value: data.subtotal_formatted || '' },
  { placeholder: '{{DISCOUNTS}}', value: data.discounts_formatted || '' },
  { placeholder: '{{TAX}}', value: data.tax_formatted || '' },
  { placeholder: '{{TOTAL_DUE}}', value: data.total_due_formatted || '' }
];

const requests = replacements.map(r => ({
  replaceAllText: {
    containsText: {
      text: r.placeholder,
      matchCase: true
    },
    replaceText: r.value
  }
}));

return [{
  json: {
    documentId: docId,
    requests: requests
  }
}];
```

**2. Add "Update Invoice Document (API)" HTTP Request Node:**

```json
{
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 4.2,
  "parameters": {
    "url": "=https://docs.googleapis.com/v1/documents/{{ $json.documentId }}:batchUpdate",
    "method": "POST",
    "authentication": "predefinedCredentialType",
    "nodeCredentialType": "googleDocsOAuth2Api",
    "sendBody": true,
    "specifyBody": "json",
    "jsonBody": "={{ JSON.stringify({ requests: $json.requests }) }}",
    "options": {}
  },
  "credentials": {
    "googleDocsOAuth2Api": {
      "id": "your-credential-id",
      "name": "Google cloud project (N8N - SYNRG)"
    }
  },
  "onError": "continueRegularOutput"
}
```

**3. Remove native Google Docs "Update a Document" node**

**4. Connect nodes:** Copy Template → Format Replace Requests → Update Document (API) → Export as PDF

### Result

- batchUpdate API calls now succeed reliably
- All 18 template placeholders replaced correctly
- PDF generation pipeline works end-to-end
- Pattern is more explicit and debuggable (can inspect exact API request)
- Workflow successfully generates invoices with populated data

---

## Google Docs Template Population Decision Matrix

| Operation | Native Google Docs Node | HTTP Request + batchUpdate |
|-----------|------------------------|---------------------------|
| Read document | ✅ Works reliably | Unnecessary |
| Create document | ✅ Works reliably | Unnecessary |
| Simple update (1-2 fields) | ⚠️ May work | Preferred for reliability |
| Template population (3+ fields) | ❌ **Known issues** | ✅ **Use this** |
| Complex formatting | ❌ Limited support | ✅ Full API access |

---

## When to Use HTTP Request Instead of Native Node

- ✅ Template population with multiple placeholders
- ✅ When native node returns vague errors ("Bad request")
- ✅ When you need full control over API request format
- ✅ When official n8n templates use HTTP Request for same operation
- ✅ Complex document operations (insertTable, updateTableCells, etc.)

---

## batchUpdate API Request Format

```json
{
  "requests": [
    {
      "replaceAllText": {
        "containsText": {
          "text": "{{PLACEHOLDER}}",
          "matchCase": true
        },
        "replaceText": "Actual Value"
      }
    }
  ]
}
```

---

## Key Learnings

- **Official templates are authoritative** - If n8n's own templates use HTTP Request, that's a signal
- **Native nodes can have bugs** - Don't assume native nodes work perfectly
- **Direct API access is more reliable** - HTTP Request with proper formatting is often more stable
- **Error messages may be misleading** - "Bad request" doesn't indicate which parameter is wrong
- **Code node for request formatting** - Clean separation between data transformation and API call
- **Credential reuse works** - Same OAuth credential works for both native node and HTTP Request

---

## API Documentation Reference

- Google Docs API batchUpdate: `https://developers.google.com/docs/api/reference/rest/v1/documents/batchUpdate`
- Endpoint: `POST https://docs.googleapis.com/v1/documents/{documentId}:batchUpdate`

---

**Date**: 2025-12-03
**Source Pattern**: agents-evolution.md - API Integration Patterns
