# CRITICAL DIRECTIVE: Always Use Latest Node Versions

> **Priority**: MAXIMUM - This directive OVERRIDES all other version-related patterns
>
> **Issued**: 2025-11-27 via SYNRG command
>
> **Scope**: ALL nodes, ALL workflows, ALL situations

---

## The Rule

**Before implementing ANY node in ANY workflow:**

1. Research n8n official documentation for latest typeVersion
2. Use latest version universally (all node types)
3. Debug and fix parameter issues until latest version works
4. **Never rollback to older versions** - fix forward instead

---

## Mandatory Pre-Implementation Checklist

### Step 1: Research Latest TypeVersion

```bash
# Use n8n MCP tools to find latest version
mcp__n8n-mcp__get_node_info({ nodeType: "nodes-base.{name}" })

# Check official n8n documentation
# URL: https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-base.{name}/
```

### Step 2: Get Correct Parameters for Latest Version

```bash
# Use node essentials with examples
mcp__n8n-mcp__get_node_essentials({
  nodeType: "nodes-base.{name}",
  includeExamples: true
})

# Validate parameter structure
mcp__n8n-mcp__validate_node_operation({
  nodeType: "nodes-base.{name}",
  config: { /* latest version params */ },
  profile: "ai-friendly"
})
```

### Step 3: Implement with Latest Version

```json
{
  "type": "n8n-nodes-base.{name}",
  "typeVersion": X,  // ← ALWAYS use latest from docs
  "parameters": {
    // Use parameter structure for latest version
    // Debug until working - DO NOT rollback to older version
  }
}
```

### Step 4: If Validation Errors Occur

- ✅ Debug parameter configuration for latest version
- ✅ Research breaking changes in version upgrade notes
- ✅ Adjust parameters to match latest version requirements
- ✅ Use `mcp__n8n-mcp__n8n_autofix_workflow` to identify fixes
- ❌ DO NOT rollback to older typeVersion
- ❌ DO NOT use working examples if they have outdated versions

---

## Universal Node Version Policy

**For ALL node types (no exceptions):**

| Node Type | Directive |
|-----------|-----------|
| OpenAI nodes | Use latest typeVersion from n8n docs |
| AI Agent nodes | Use latest typeVersion from n8n docs |
| Form Trigger nodes | Use latest typeVersion from n8n docs |
| HTTP Request nodes | Use latest typeVersion from n8n docs |
| Set nodes | Use latest typeVersion from n8n docs |
| Code nodes | Use latest typeVersion from n8n docs |
| **ALL OTHER NODES** | Use latest typeVersion from n8n docs |

---

## Research Sources (Priority Order)

1. **n8n MCP Tools** - `mcp__n8n-mcp__get_node_info` (authoritative)
2. **n8n Official Docs** - https://docs.n8n.io/integrations/
3. **n8n Node Schema** - `mcp__n8n-mcp__get_node_essentials`
4. **n8n Templates** - Only for parameter examples, NOT version reference

---

## Workflow Development Sequence

```
PHASE 1: NODE RESEARCH (MANDATORY)
├─ Step 1: Identify required node type
├─ Step 2: Research latest typeVersion via MCP/docs
├─ Step 3: Get parameter structure for latest version
└─ Step 4: Document version number before implementation

PHASE 2: IMPLEMENTATION
├─ Step 1: Implement node with LATEST typeVersion
├─ Step 2: Configure parameters per latest version docs
├─ Step 3: Validate configuration
└─ Step 4: Fix errors (never rollback version)

PHASE 3: DEBUGGING (if errors)
├─ Step 1: Analyze validation/execution errors
├─ Step 2: Research breaking changes in version notes
├─ Step 3: Adjust parameters to match latest requirements
├─ Step 4: Re-validate until 0 errors
└─ Step 5: Document any non-obvious parameter changes

PHASE 4: DOCUMENTATION
├─ Step 1: Record typeVersion used in workflow
├─ Step 2: Note any version-specific configuration
└─ Step 3: Update pattern library if novel pattern discovered
```

---

## Validation Warning Handling

| Warning | Action |
|---------|--------|
| "Outdated typeVersion: X. Latest is Y" | **CRITICAL ERROR** - Must fix immediately |
| "Node configuration valid" | Proceed |
| Any pattern suggesting "working version > latest version" | **IGNORE** - always use latest |

---

## Breaking Change Management

When latest version has breaking changes:

1. **Document the breaking change** - What changed in parameters?
2. **Update parameter structure** - Adapt to new requirements
3. **Test thoroughly** - Ensure new version works correctly
4. **Never rollback** - Fix forward, debug until working
5. **Add to evolution patterns** - Document migration path for future reference

---

## Benefits

- **Prevents technical debt** - No outdated node versions in workflows
- **Ensures latest features** - Access to newest node capabilities
- **Enforces best practices** - All workflows use current n8n standards
- **Eliminates version drift** - Consistent versions across all workflows

---

## Performance Impact

| Aspect | Impact |
|--------|--------|
| Research overhead | +5-10 minutes per node (one-time cost) |
| Debugging overhead | +10-30 minutes if breaking changes (occasional) |
| Technical debt prevention | Eliminates future migration work (ongoing savings) |
| Feature access | Immediate access to latest capabilities (ongoing benefit) |
| Long-term ROI | Prevents accumulation of outdated workflows (exponential savings) |

---

## Enforcement

This directive **OVERRIDES** all previous conservative version management patterns.

When conflicts arise between "use working examples" and "use latest versions":

**ALWAYS choose latest versions.**

---

**Date**: 2025-11-27
**Source Pattern**: agents-evolution.md lines 223-379
