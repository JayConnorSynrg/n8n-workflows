# Microsoft Excel 365 Node Reference

**Node Type:** `n8n-nodes-base.microsoftExcel`
**TypeVersion:** 2.2
**Last Verified:** 2026-02-13
**Anti-Memory:** true

---

## CRITICAL: Known Failure Patterns

### Anti-Pattern 1: Wrong dataMode value
- **WRONG:** `dataMode: "defineBelow"` — this value does NOT exist
- **CORRECT:** `dataMode: "define"` — the actual parameter for "Map Each Column Below"
- **Impact:** Node silently fails or produces errors. No columns get mapped.

### Anti-Pattern 2: Wrong ResourceLocator mode for workbook/worksheet
- **WRONG:** `workbook.mode: "id"`, `worksheet.mode: "name"` with string value
- **CORRECT:** Both must use `mode: "list"` with ResourceLocator format including `__rl`, `cachedResultName`, `cachedResultUrl`
- **Impact:** Node cannot find the workbook/worksheet, silent failure

### Anti-Pattern 3: Missing upsert match parameters
- **WRONG:** Omitting `columnToMatchOn` and `valueToMatchOn` for upsert operation
- **CORRECT:** Both are REQUIRED for upsert — `columnToMatchOn` is the Excel column header, `valueToMatchOn` is the expression
- **Impact:** Upsert cannot determine which row to update

### Anti-Pattern 4: Wrong field value property name
- **WRONG:** `{ "column": "Name", "value": "..." }` — "value" is wrong
- **CORRECT:** `{ "column": "Name", "fieldValue": "..." }` — must be "fieldValue"
- **Impact:** Column values silently ignored

### Anti-Pattern 5: Including match column in fieldsUi
- **WRONG:** Adding `columnToMatchOn` column (e.g. compositeKey) to `fieldsUi.values[]`
- **CORRECT:** Only map NON-match columns in `fieldsUi.values[]` — the match column is written automatically by the upsert operation via `columnToMatchOn`/`valueToMatchOn`
- **Impact:** "Value not supported" error on that column entry. The node uses `getWorksheetColumnRowSkipColumnToMatchOn` which explicitly excludes the match column from available mapping targets.

---

## Verified Working Configuration: UPSERT with Manual Mapping

### Operation: upsert on worksheet resource

```json
{
  "resource": "worksheet",
  "operation": "upsert",
  "workbook": {
    "__rl": true,
    "value": "<WORKBOOK_ID>",
    "mode": "list",
    "cachedResultName": "<Workbook Display Name>",
    "cachedResultUrl": "<SharePoint URL>"
  },
  "worksheet": {
    "__rl": true,
    "value": "<WORKSHEET_GUID_WITH_BRACES>",
    "mode": "list",
    "cachedResultName": "<Sheet Tab Name>",
    "cachedResultUrl": "<SharePoint URL>"
  },
  "dataMode": "define",
  "columnToMatchOn": "<unique_column_name>",
  "valueToMatchOn": "={{ $json.<unique_field> }}",
  "fieldsUi": {
    "values": [
      {
        "column": "<Excel Column Header>",
        "fieldValue": "={{ $json.<input_field> }}"
      }
    ]
  },
  "options": {}
}
```

### Parameter Reference

| Parameter | Type | Required | Values | Notes |
|-----------|------|----------|--------|-------|
| `resource` | string | Yes | `"worksheet"` | For sheet-level operations |
| `operation` | string | Yes | `"upsert"`, `"append"`, `"update"`, `"delete"` | Operation type |
| `workbook` | ResourceLocator | Yes | `mode: "list"` | MUST include `__rl`, `cachedResultName`, `cachedResultUrl` |
| `worksheet` | ResourceLocator | Yes | `mode: "list"` | Value is sheet GUID in braces e.g. `{96A0F21B-...}` |
| `dataMode` | string | Yes | `"autoMap"` or `"define"` | "define" = Map Each Column Below. NOT "defineBelow" |
| `columnToMatchOn` | string | Yes (upsert) | Column header name | The column used for matching existing rows |
| `valueToMatchOn` | string | Yes (upsert) | Expression | e.g. `={{ $json.compositeKey }}` |
| `fieldsUi.values` | array | Yes (define mode) | `[{ column, fieldValue }]` | Each entry maps one column |
| `fieldsUi.values[].column` | string | Yes | Exact Excel column header | Case-sensitive match |
| `fieldsUi.values[].fieldValue` | string | Yes | Static or expression | Use `={{ $json.field }}` for dynamic values |

### dataMode Options (Comprehensive)

| Value | UI Label | Description |
|-------|----------|-------------|
| `"autoMap"` | "Auto-Map Input Data to Columns" | Matches input field names to Excel headers automatically |
| `"define"` | "Map Each Column Below" | Explicit column-by-column mapping via fieldsUi |

**NOTE:** `"defineBelow"` does NOT exist. `"raw"` exists only for append operation, not upsert.

---

## Reference Workflow

**Workflow:** Resume Analysis with AI Evaluation (PAYCOR TRIGGER)
**ID:** MMaJkr8abEjnCM2h
**Node:** "Append New Record"
**Verified:** 2026-02-13
**Status:** Working — 31 data columns mapped + compositeKey as match column (32 total)
