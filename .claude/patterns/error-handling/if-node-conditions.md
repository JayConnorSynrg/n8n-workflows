# Pattern: IF Node Conditions Structure for TypeVersion 2.2

> **Priority**: MEDIUM
>
> **Workflow**: SYNRG Invoice Generator (ID: Ge33EW4K3WVHT4oG)
>
> **Date**: 2025-12-02

---

## Anti-Pattern: IF Node Conditions Missing Required Fields in Options

### What Happened

When deploying the SYNRG Invoice Generator workflow, the n8n API rejected the workflow with validation error:

```
Node "Check Email Provided" (index 9): Missing required field "conditions.options.leftValue". Expected value: ""
```

The IF node conditions were structured without `leftValue` in the `options` object, and the operator was missing the `name` field:

```json
// WRONG - Missing conditions.options.leftValue and operator.name
{
  "conditions": {
    "options": {
      "version": 2,
      "caseSensitive": true,
      "typeValidation": "strict"
    },
    "conditions": [{
      "operator": {
        "type": "string",
        "operation": "notEmpty"
      },
      "leftValue": "={{ $json.field }}"
    }]
  }
}
```

### Impact

- Workflow creation failed via MCP API
- Required researching n8n templates to discover correct structure
- Delayed deployment while fixing IF node configuration

### Why It Failed

- n8n IF node typeVersion 2.2 requires specific structure in `conditions.options`
- `leftValue: ""` must be present in options object (even if empty)
- `operator.name` field is required (e.g., `"filter.operator.notEmpty"`)
- The MCP validation tool's error message was accurate but non-obvious

---

## Positive Pattern: Complete IF Node Conditions Structure for TypeVersion 2.2

### Solution

Use the complete conditions structure with all required fields.

### Implementation

```json
// CORRECT - Complete structure for IF node typeVersion 2.2
{
  "type": "n8n-nodes-base.if",
  "typeVersion": 2.2,
  "parameters": {
    "options": {},  // ← options at parameter level (empty object OK)
    "conditions": {
      "options": {
        "version": 2,
        "leftValue": "",        // ← REQUIRED even if empty
        "caseSensitive": true,
        "typeValidation": "strict"
      },
      "combinator": "and",
      "conditions": [
        {
          "id": "unique-condition-id",
          "operator": {
            "name": "filter.operator.notEmpty",  // ← REQUIRED - full operator name
            "type": "string",
            "operation": "notEmpty"
          },
          "leftValue": "={{ $json.fieldToCheck }}",
          "rightValue": ""
        }
      ]
    }
  }
}
```

### Key Fields That Must Be Present

1. `parameters.options` - Empty object `{}` at parameter level
2. `conditions.options.leftValue` - Empty string `""` (required by schema)
3. `conditions.options.version` - Set to `2` for typeVersion 2.2
4. `operator.name` - Full operator name like `"filter.operator.notEmpty"` or `"filter.operator.equals"`

### Result

- Workflow deployed successfully after correcting IF node structure
- No validation errors from n8n API
- Pattern documented for future IF node implementations

---

## IF Node Operator Name Reference

| Operation | Operator Name |
|-----------|---------------|
| Not Empty | `filter.operator.notEmpty` |
| Equals | `filter.operator.equals` |
| Not Equals | `filter.operator.notEquals` |
| Contains | `filter.operator.contains` |
| Starts With | `filter.operator.startsWith` |
| Ends With | `filter.operator.endsWith` |
| Greater Than | `filter.operator.gt` |
| Less Than | `filter.operator.lt` |
| Is True | `filter.operator.true` |
| Is False | `filter.operator.false` |

---

## IF Node Validation Checklist

- [ ] `parameters.options` exists (can be empty `{}`)
- [ ] `conditions.options.leftValue` exists (can be empty `""`)
- [ ] `conditions.options.version` is `2` for typeVersion 2.2
- [ ] Each condition has `operator.name` field with full operator path
- [ ] Each condition has unique `id` field

---

## Key Learnings

- **Schema validation is strict** - n8n API requires ALL fields even if semantically empty
- **Research templates for correct structure** - Fetch working templates via MCP to see exact field requirements
- **Operator requires full name** - Not just `operation` but also `name` with `filter.operator.` prefix
- **TypeVersion 2.2 structure differs from older versions** - Don't assume same structure across versions

---

**Date**: 2025-12-02
**Source Pattern**: agents-evolution.md - Error Handling Patterns
