# Pattern: Structured Output Parser Configuration by TypeVersion

> **Priority**: HIGH
>
> **Workflow**: AI Carousel Generator (ID: 8bhcEHkbbvnhdHBh)
>
> **Date**: 2025-12-04

---

## Anti-Pattern: Using Deprecated jsonSchema Parameter with Output Parser TypeVersion 1.3

### What Happened

The Output Parser node "Parse Slide Prompts" was configured with `jsonSchema` parameter (for typeVersion 1.1 and earlier), but the node was actually running at typeVersion 1.3 which uses a completely different parameter structure:

```json
// WRONG - Old parameter for typeVersion 1.1
{
  "type": "@n8n/n8n-nodes-langchain.outputParserStructured",
  "typeVersion": 1.3,
  "parameters": {
    "jsonSchema": "{ /* correct carousel schema */ }"  // ← IGNORED at runtime!
  }
}
```

At runtime, the node fell back to default parameters:
```json
{
  "schemaType": "fromJson",
  "jsonSchemaExample": "{\n\t\"state\": \"California\",\n\t\"cities\": [\"Los Angeles\", \"San Francisco\", \"San Diego\"]\n}"
}
```

This caused execution to fail with: "Model output doesn't fit required format" because the parser expected state/cities schema, not our carousel prompts schema.

### Impact

- Execution failed at Parse Slide Prompts node
- AI Agent output couldn't be parsed (even though model produced correct output)
- Workflow stopped completely - no image generation occurred
- Error message was misleading (suggested model output was wrong, but actually parser configuration was wrong)

### Why It Failed

1. **TypeVersion parameter mismatch**: `jsonSchema` is for typeVersion ≤1.1, while typeVersion 1.3 uses different parameters
2. **Silent parameter ignoring**: The old `jsonSchema` parameter was silently ignored, not errored
3. **Default fallback behavior**: Node defaulted to `schemaType: "fromJson"` with example schema
4. **MCP validation gap**: Workflow validation passed because JSON structure was valid, but semantic parameter-to-version mismatch wasn't detected

---

## Positive Pattern: Use schemaType + inputSchema Parameters for Output Parser TypeVersion 1.2+

### Solution

For Output Parser typeVersion 1.2 and later, use `schemaType: "manual"` with `inputSchema` parameter instead of the deprecated `jsonSchema` parameter.

### Implementation

**1. Research correct parameter structure for typeVersion 1.3:**
```javascript
mcp__n8n-mcp__get_node({
  nodeType: "@n8n/n8n-nodes-langchain.outputParserStructured",
  mode: "info",
  detail: "full"
})
```

**2. Parameter differences:**

| TypeVersion | Schema Mode | Parameter Name |
|-------------|-------------|----------------|
| ≤1.1 | N/A | `jsonSchema` |
| 1.2+ | `fromJson` | `jsonSchemaExample` (infer from example) |
| 1.2+ | `manual` | `inputSchema` (full JSON Schema) |

**3. Fixed Output Parser configuration:**
```json
{
  "type": "@n8n/n8n-nodes-langchain.outputParserStructured",
  "typeVersion": 1.3,
  "parameters": {
    "schemaType": "manual",
    "inputSchema": "{\n  \"type\": \"object\",\n  \"properties\": {\n    \"carousel_title\": { \"type\": \"string\" },\n    \"slide_prompts\": { \"type\": \"array\", \"items\": { ... } },\n    \"tags\": { \"type\": \"array\" }\n  },\n  \"required\": [\"carousel_title\", \"slide_prompts\", \"tags\"]\n}"
  }
}
```

### Result

- Output Parser now correctly configured for typeVersion 1.3
- Schema will properly validate carousel prompts structure
- Ready for execution testing

---

## Output Parser Parameter Structure by TypeVersion

| TypeVersion | Schema Method | Parameters Required |
|-------------|---------------|---------------------|
| 1.0-1.1 | Direct schema | `jsonSchema: "{ ... }"` |
| 1.2-1.3 | Infer from example | `schemaType: "fromJson"` + `jsonSchemaExample: "{ example }"` |
| 1.2-1.3 | Full JSON Schema | `schemaType: "manual"` + `inputSchema: "{ JSON Schema }"` |

---

## Decision Flow for Output Parser Configuration

```
Using outputParserStructured node?
├─ Check typeVersion
│   ├─ typeVersion ≤1.1 → Use jsonSchema parameter
│   └─ typeVersion 1.2+ → Check schema complexity
│       ├─ Simple structure → schemaType: "fromJson" + jsonSchemaExample
│       └─ Complex structure with validation → schemaType: "manual" + inputSchema
├─ Deploying to n8n instance?
│   └─ Verify parameter names match typeVersion on instance
└─ Execution fails with "Model output doesn't fit required format"?
    └─ Check if parameter is being silently ignored (version mismatch)
```

---

## Validation Checklist for Output Parser Nodes

- [ ] Check typeVersion of the node
- [ ] Verify parameter names match that typeVersion
- [ ] For v1.2+: Confirm `schemaType` is explicitly set
- [ ] For v1.2+ with `manual`: Use `inputSchema`, NOT `jsonSchema`
- [ ] For v1.2+ with `fromJson`: Provide representative example in `jsonSchemaExample`
- [ ] Test with actual execution (structural validation doesn't catch parameter mismatches)

---

## Key Learnings

- **Parameter names change between typeVersions** - Same node, different parameters across versions
- **Old parameters silently ignored** - No error, just falls back to defaults
- **MCP validation is structural** - Doesn't verify semantic parameter-to-version compatibility
- **Default schema is California/cities** - If you see this in errors, wrong schema mode is being used
- **Execution testing is essential** - Validation passes but runtime fails for parameter mismatches
- **schemaType is mandatory for v1.2+** - Without it, node assumes "fromJson" mode

---

**Date**: 2025-12-04
**Source Pattern**: agents-evolution.md - Workflow Architecture Patterns
