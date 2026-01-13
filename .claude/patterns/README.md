# N8N Workflow Development Patterns

> **LLM-Optimized Rule Library for n8n Workflow Development**
>
> This directory contains battle-tested patterns derived from real workflow development. Each pattern documents both anti-patterns (mistakes) and positive patterns (solutions).

## Quick Navigation

| Category | Description | Priority |
|----------|-------------|----------|
| [critical-directives/](./critical-directives/) | **MANDATORY** rules that override all others | HIGHEST |
| [meta-patterns/](./meta-patterns/) | Cross-cutting patterns about pattern application | HIGH |
| [node-selection/](./node-selection/) | Choosing correct node types and configurations | HIGH |
| [api-integration/](./api-integration/) | External API and service integrations | MEDIUM |
| [workflow-architecture/](./workflow-architecture/) | Workflow structure and flow patterns | MEDIUM |
| [error-handling/](./error-handling/) | Error handling and response patterns | MEDIUM |
| [data-transformation/](./data-transformation/) | Data manipulation and transformation | LOW |
| [performance-optimization/](./performance-optimization/) | Performance and efficiency patterns | LOW |
| [validation-records/](./validation-records/) | Validation confirmations and test results | REFERENCE |

---

## Pattern Application Rules

### 1. Priority Order (MANDATORY)

When patterns conflict, apply in this order:

```
1. critical-directives/     → ALWAYS apply first
2. meta-patterns/           → Apply to prevent known failure modes
3. Category-specific rules  → Apply per operation type
```

### 2. Before ANY Node Implementation

```
CHECKLIST:
[ ] Read critical-directives/latest-versions.md
[ ] Check meta-patterns/ for known failure points
[ ] Find category-specific pattern if exists
[ ] Validate with MCP tools before deployment
```

### 3. Pattern Format

Each pattern follows this structure:

```markdown
## [DATE] Workflow: {name}

### Anti-Pattern: {what went wrong}
- What Happened: {description}
- Impact: {consequences}
- Why It Failed: {root cause}

### Positive Pattern: {what works}
- Solution: {fix}
- Implementation: {code/steps}
- Result: {outcome}
- Reusable Pattern: {when to apply}
```

---

## File Index

### Critical Directives (READ FIRST)
- `critical-directives/latest-versions.md` - **MANDATORY**: Always use latest node typeVersions

### Meta-Patterns (APPLY ALWAYS)
- `meta-patterns/anti-memory-protocol.md` - Prevent memory-based implementation errors for known failure points

### Node Selection
- `node-selection/analyze-before-building.md` - Always analyze working examples first
- `node-selection/code-vs-native-nodes.md` - Native nodes over Code nodes (priority order)

### API Integration
- `api-integration/openai-image-nodes.md` - OpenAI image generation/analysis configuration (HIGH PRIORITY)
- `api-integration/google-docs-api.md` - Use HTTP Request for Google Docs batchUpdate
- `api-integration/airtable-mapping.md` - Manual column mapping for programmatic updates

### Workflow Architecture
- `workflow-architecture/memory-session-config.md` - Memory buffer session for non-chat triggers
- `workflow-architecture/ai-agent-typeversion.md` - AI Agent GPT-4o version compatibility
- `workflow-architecture/output-parser-config.md` - Structured output parser by typeVersion
- `workflow-architecture/loop-entry-expressions.md` - Fallback expressions for loop-compatible Set nodes

### Error Handling
- `error-handling/form-webhook-compatibility.md` - Form Trigger vs Webhook Trigger
- `error-handling/if-node-conditions.md` - IF node condition structure for TypeVersion 2.2

### Performance Optimization
- `performance-optimization/context-discovery-protocol.md` - SYNRG context-finding protocol for complex workflows

---

## Usage in Claude Code

This directory is automatically discoverable by Claude Code via:

1. **Project CLAUDE.md reference** - Points to this patterns directory
2. **Glob patterns** - `**/.claude/patterns/**/*.md`
3. **Direct path** - `.claude/patterns/[category]/[pattern].md`

### Searching Patterns

```bash
# Find all critical directives
ls .claude/patterns/critical-directives/

# Search for specific pattern
grep -r "OpenAI" .claude/patterns/

# Find patterns by date
grep -r "\[2025-12" .claude/patterns/
```

---

## Maintenance

### Adding New Patterns

1. Identify the correct category
2. Create file with descriptive name
3. Follow pattern format (Anti-Pattern + Positive Pattern)
4. Update this README's File Index
5. Cross-reference in related patterns if needed

### Pattern Deprecation

When a pattern is superseded:
1. Add `~~DEPRECATED~~` marker
2. Reference the superseding pattern
3. Keep for historical context in `<details>` block

---

**Source**: Extracted from `.claude/agents-evolution.md`
**Last Updated**: 2025-12-04
**Maintainer**: Claude Code
