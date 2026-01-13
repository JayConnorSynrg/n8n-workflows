# Pattern: Native Nodes First - Code Node as Last Resort

> **Priority**: MEDIUM
>
> **Scope**: All n8n workflow development
>
> **Date**: 2025-11-22

---

## Anti-Pattern: Using Code Nodes for Operations Native Nodes Can Handle

### What Happens

Developers reach for Code nodes when simpler native node combinations would suffice:
- Using Code node for simple field mapping (Set node does this)
- Using Code node for conditional logic (IF/Switch nodes handle this)
- Using Code node for data filtering (Filter node exists)
- Using Code node for array operations (Split/Merge nodes available)

### Impact

- **Maintainability**: Code nodes require JavaScript knowledge to debug
- **Visibility**: Native nodes show data flow in UI, Code nodes are black boxes
- **pairedItem chain**: Code nodes break item lineage tracking (see loop-entry-expressions pattern)
- **Error handling**: Native nodes have built-in retry and error handling
- **Performance**: Some native nodes are optimized for specific operations

### Why It Happens

- Familiarity with JavaScript vs. n8n node ecosystem
- Not knowing which native nodes exist
- Time pressure (writing code feels faster than exploring nodes)
- Complex operations that seem to need code

---

## Positive Pattern: Node Selection Priority Order

### Decision Flow

```
Need to transform data?
├─ Simple field mapping → Set node
├─ Conditional field values → IF node → Set nodes
├─ Array iteration → Split In Batches → process → Merge
├─ Data filtering → Filter node
├─ Complex object transformation → Code node (last resort)
└─ Document WHY Code node was necessary

Need conditional logic?
├─ Binary decision → IF node
├─ Multiple branches → Switch node
├─ Value-based routing → Switch node with rules
└─ Complex boolean logic → Code node (last resort)

Need to combine data?
├─ Append items → Merge node (Append mode)
├─ Combine by field → Merge node (Combine mode)
├─ SQL-like join → Merge node (SQL Join)
├─ Custom combination logic → Code node (last resort)
```

### Native Node Capabilities Often Overlooked

| Need | Native Solution | Avoid |
|------|-----------------|-------|
| Map field names | Set node (rename) | Code node for mapping |
| Add calculated field | Set node with expression | Code node for math |
| Filter items | Filter node | Code node with filter() |
| Split array to items | Split In Batches | Code node with forEach |
| Combine arrays | Merge node | Code node with concat |
| Format dates | Date & Time node | Code node with Date() |
| String manipulation | Expressions `{{ $json.field.toLowerCase() }}` | Code node |

---

## When Code Nodes ARE Appropriate

| Scenario | Example | Why Code |
|----------|---------|----------|
| Complex data parsing | Parse nested XML to JSON | Native parsing limited |
| Algorithm implementation | Sorting by multiple criteria | No native sort node |
| External library needs | Using lodash/moment | Native expressions limited |
| Multi-step calculations | Financial formulas | Too many Set nodes |
| Dynamic structure generation | Building form from schema | Structure unknown at design |

### Code Node Best Practices

When Code node is necessary:
1. **Document why** - Add Sticky Note explaining why native nodes couldn't work
2. **Keep it minimal** - Extract reusable logic to sub-workflows
3. **Handle errors** - Wrap in try/catch, return meaningful errors
4. **Preserve pairedItem** - If in loop, manually preserve lineage (see loop-entry-expressions)
5. **Comment the code** - Future maintainers need context

```javascript
// Example: Proper Code node structure
try {
  // Document: Using Code node because Set node can't do recursive object transformation
  const result = transformNestedObject($input.item.json);

  return [{
    json: result,
    // Preserve pairedItem for loop compatibility
    pairedItem: $input.item.pairedItem
  }];
} catch (error) {
  throw new Error(`Transform failed: ${error.message}`);
}
```

---

## Key Learnings

- **Native nodes are self-documenting** - Workflow structure shows data flow
- **Code nodes are maintenance burden** - Require JavaScript knowledge
- **Expression language is powerful** - Many operations possible without Code nodes
- **Search before coding** - `mcp__n8n-mcp__search_nodes` often finds native solutions
- **pairedItem chain matters** - Code nodes break loop functionality if not careful

---

**Date**: 2025-11-22
**Source Pattern**: agents-evolution.md - Node Selection Priority
