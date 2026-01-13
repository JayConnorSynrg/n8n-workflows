# N8N Workflow Pattern Library

**Purpose:** Reusable, proven workflow patterns extracted from successful implementations and n8n templates.

**Last Updated:** 2025-12-03
**Total Patterns:** 6

---

## Pattern Index

### Workflow Architecture Patterns
1. [Sequential Image Generation Chain](./sequential-image-chain/) - Generate multiple related images in sequence
2. [AI Agent with Sub-Workflow Tool](./ai-agent-with-tool/) - Give AI agents access to complex capabilities

### Integration Patterns
3. [Google Drive Upload + Public URL](./gdrive-upload-url/) - Store files and get shareable links
4. [Quality Gate with Auto-Fix](./quality-gate-autofix/) - Validate output quality with automatic improvement
5. ✅ [Google Docs batchUpdate via HTTP Request](./google-docs-batchupdate/) - **NEW** Reliable template population bypassing native node issues

### Error Handling Patterns
6. [Comprehensive Error Handling](./comprehensive-error-handling/) - Robust production-grade error handling

---

## Pattern Format

Each pattern directory contains:
- `pattern.md` - When to use, how to implement, examples
- `pattern.json` - Example node configuration (copy-paste ready)
- `variations.md` - Common adaptations and modifications (optional)

---

## Using Patterns

**Quick Start:**
1. Browse pattern index above
2. Read `pattern.md` in relevant pattern directory
3. Copy node configuration from `pattern.json`
4. Adapt parameters for your specific use case
5. Validate with `mcp__n8n-mcp__n8n_validate_workflow`

**Pattern Quality Levels:**
- ✅ **Production-Ready** - Tested in live workflows, proven error handling
- 🧪 **Tested** - Validated in development, needs production monitoring
- 📝 **Documented** - Extracted from templates, needs testing

---

## Contributing Patterns

**Add a pattern when:**
- ✅ Successfully used in production workflow
- ✅ Solves a common problem
- ✅ Reusable across multiple use cases
- ✅ Non-trivial (>3 nodes or complex configuration)

**Process:**
1. Create directory: `.claude/workflow-examples/patterns/{pattern-name}/`
2. Add `pattern.md` with usage guide
3. Add `pattern.json` with example node configuration
4. Update this README with pattern entry
5. Commit with: `docs(patterns): add {pattern-name} pattern`

---

## Pattern Categories

### Workflow Architecture
Patterns for structuring workflow logic, flow control, and modular design.

### Integration
Patterns for connecting to external services, APIs, and platforms.

### Error Handling
Patterns for graceful failure handling, retries, and monitoring.

### Data Transformation
Patterns for processing, enriching, and transforming data.

### Performance Optimization
Patterns for improving workflow speed, reducing costs, and optimizing resources.

---

## Pattern Sources

**Extracted From:**
- ✅ Production workflows in this repository
- ✅ n8n Official Templates (https://n8n.io/workflows)
- ✅ Community workflows (n8n-workflows GitHub)
- ✅ SYNRG Context-Finding Protocol discoveries

**Documentation Standard:**
All patterns must include real-world examples and measurable outcomes.

---

## Related Commands

Commands that interact with this pattern library:

| Command | Description | Pattern Interaction |
|---------|-------------|---------------------|
| `/synrg-n8ndebug` | Comprehensive workflow debugging with 5-Why analysis | Creates new patterns from debugging discoveries |
| `/n8n-evolve` | Document patterns in agents-evolution.md | References patterns, updates statistics |
| `/n8n-build` | Interactive workflow builder | Consumes patterns for implementation |
| `/n8n-validate` | Validate workflow structure | Used during pattern creation |

---

## Related Resources

- [Agents Evolution](../../agents-evolution.md) - Anti-patterns and lessons learned
- [SYNRG Context-Finding Protocol](../../SYNRG-CONTEXT-PROTOCOL.md) - Systematic context discovery
- [Workflow Contexts](../contexts/) - Complete workflow implementation guides
- [SYNRG N8N Debugger](../../commands/synrg-n8ndebug.md) - Full debugging protocol with pattern creation
