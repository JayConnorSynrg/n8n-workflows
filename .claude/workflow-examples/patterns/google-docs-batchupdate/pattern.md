# Google Docs Template Population via HTTP Request + batchUpdate API

**Quality Level:** ✅ Production-Ready
**Category:** API Integration
**Discovered:** 2025-12-03
**Source Workflow:** SYNRG Invoice Generator (Ge33EW4K3WVHT4oG)

---

## When to Use This Pattern

Use this pattern when:
- ✅ Replacing 3+ template placeholders in a Google Doc
- ✅ Native Google Docs node returns "Bad request" errors
- ✅ You need reliable, debuggable template population
- ✅ Complex document operations (insertTable, updateTableCells, etc.)
- ✅ Building invoice/report/contract generation workflows

Do NOT use this pattern when:
- ❌ Simple read/create document operations (native node works fine)
- ❌ Only 1-2 placeholder replacements (native node may work)
- ❌ You don't have Google OAuth credentials configured

---

## Problem Solved

The native `n8n-nodes-base.googleDocs` node has known reliability issues with the `replaceAll` operation for template population. It often returns vague "Bad request - please check your parameters" errors even with correct configuration.

This pattern bypasses the native node entirely by calling the Google Docs API directly via HTTP Request, providing:
1. Reliable template population
2. Full control over the API request format
3. Better error messages from the API directly
4. Support for all batchUpdate operations (not just replaceAllText)

---

## Implementation

### Node 1: Format Replace Requests (Code Node)

```json
{
  "id": "format-replace-requests",
  "name": "Format Replace Requests",
  "type": "n8n-nodes-base.code",
  "typeVersion": 2,
  "position": [0, 0],
  "parameters": {
    "jsCode": "// Format data for Google Docs API batchUpdate\n// Adapt sourceNode references for your workflow\nconst data = $('YourDataNode').first().json;\nconst docId = $('CopyTemplateNode').first().json.id;\n\n// Define your placeholder mappings\nconst replacements = [\n  { placeholder: '{{FIELD_1}}', value: data.field_1 || '' },\n  { placeholder: '{{FIELD_2}}', value: data.field_2 || '' },\n  { placeholder: '{{FIELD_3}}', value: data.field_3 || '' }\n  // Add more placeholders as needed\n];\n\n// Build replaceAllText requests array\nconst requests = replacements.map(r => ({\n  replaceAllText: {\n    containsText: {\n      text: r.placeholder,\n      matchCase: true\n    },\n    replaceText: r.value\n  }\n}));\n\nreturn [{\n  json: {\n    documentId: docId,\n    requests: requests\n  }\n}];"
  }
}
```

### Node 2: Update Document via API (HTTP Request Node)

```json
{
  "id": "update-doc-api",
  "name": "Update Document (API)",
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 4.2,
  "position": [200, 0],
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
      "name": "Your Google OAuth Credential"
    }
  },
  "onError": "continueRegularOutput"
}
```

### Connection

```json
{
  "source": "format-replace-requests",
  "target": "update-doc-api",
  "sourceHandle": "main",
  "targetHandle": "main"
}
```

---

## API Reference

### Endpoint
```
POST https://docs.googleapis.com/v1/documents/{documentId}:batchUpdate
```

### Request Body Format
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

### Required OAuth Scopes
- `https://www.googleapis.com/auth/documents`
- `https://www.googleapis.com/auth/drive` (if also copying/exporting)

---

## Complete Example: Invoice Template

### Code Node (18 placeholders)

```javascript
// Format data for Google Docs API batchUpdate
const data = $('Generate Invoice ID').first().json;
const docId = $('Copy Invoice Template').first().json.id;

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

---

## Comparison: Native Node vs HTTP Request

| Aspect | Native Google Docs Node | HTTP Request + batchUpdate |
|--------|------------------------|---------------------------|
| Reliability | ❌ Known issues with replaceAll | ✅ Direct API, reliable |
| Error Messages | ❌ Vague "Bad request" | ✅ Specific API errors |
| Debuggability | ❌ Hidden request formatting | ✅ Full visibility |
| Setup Complexity | ✅ Simple (but may not work) | ⚠️ Moderate (2 nodes) |
| Credential | Google Docs OAuth | Same OAuth credential |
| Operations | Limited to UI options | All batchUpdate operations |

---

## Troubleshooting

### Error: 401 Unauthorized
- Check OAuth credential is valid and not expired
- Verify credential has Google Docs API scope

### Error: 404 Document Not Found
- Check `documentId` is correct
- Verify the OAuth account has access to the document

### Error: 400 Invalid Request
- Check placeholder text matches exactly (case-sensitive)
- Verify JSON body format is correct
- Ensure all values are strings (use `String()` for numbers)

### Placeholders Not Replaced
- Verify placeholders in template use exact same format (e.g., `{{FIELD}}`)
- Check `matchCase: true` setting matches your template's case
- Ensure value is not `undefined` (use `|| ''` fallback)

---

## Related Patterns

- [Quality Gate with Auto-Fix](../quality-gate-autofix/) - Validate output quality
- [Google Drive Upload + Public URL](../gdrive-upload-url/) - Store generated documents

---

## References

- [Google Docs API batchUpdate](https://developers.google.com/docs/api/reference/rest/v1/documents/batchUpdate)
- [n8n Template #3145](https://n8n.io/workflows/3145) - Uses HTTP Request for same operation
- [agents-evolution.md](../../../agents-evolution.md) - Full pattern documentation
