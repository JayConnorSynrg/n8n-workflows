# N8N Workflows - Claude Code Configuration

**Repository Type:** n8n Production Workflow Development
**Purpose:** Business in a Box - Complete automation suite with pattern evolution
**Claude Integration:** Optimized for n8n workflow building, validation, and maintenance

---

## Quick Start

### For Claude Code Users

This repository is configured for automated n8n workflow development. Key features:

1. **Intelligent Workflow Building** - Use `/n8n-build` to create workflows with native node prioritization
2. **Validation & Debugging** - Use `/n8n-validate` and `/n8n-debug` for quality assurance
3. **Pattern Learning** - Document successful patterns in `agents-evolution.md` with `/n8n-evolve`
4. **Git Integration** - Pre-commit hooks validate workflows automatically
5. **MCP Tools** - Direct access to n8n API for workflow management

### Quick Commands

```bash
# Build a new workflow
/n8n-build workflow description

# Validate existing workflow
/n8n-validate workflow-name

# Debug failed execution
/n8n-debug workflow-name or execution-id

# Document learned pattern
/n8n-evolve

# See all available commands
ls .claude/commands/
```

---

## Repository Structure

```
.claude/
├── README.md                        # This file
├── claude.md                        # Main project instructions for Claude
├── agents-evolution.md              # Pattern learning log (grows over time)
├── workflow-organization.md         # Workflow structure and standards
│
├── commands/                        # Slash commands
│   ├── n8n-build.md                # Build new workflows
│   ├── n8n-validate.md             # Validate workflow structure
│   ├── n8n-debug.md                # Debug executions
│   └── n8n-evolve.md               # Document patterns
│
├── hooks/                          # Git hooks
│   └── pre-commit-validate-workflows.md
│
└── prompts/                        # Prompting guidelines
    └── workflow-building-guide.md  # How to prompt for workflows
```

---

## Key Files

### 1. claude.md
**Purpose:** Main instructions for Claude Code when working in this repository

**Contains:**
- n8n development philosophy (native nodes first)
- MCP tool reference (n8n workflow management)
- Workflow naming conventions
- Error handling requirements
- Pattern evolution system
- Development workflow process

**When Claude reads this:** Automatically optimizes for n8n workflow building

---

### 2. agents-evolution.md
**Purpose:** Living document of proven patterns and anti-patterns

**Structure:**
- Anti-patterns: Mistakes that caused issues
- Positive patterns: Solutions that worked
- Only documents REAL outcomes (no speculation)

**How it works:**
1. You encounter a problem while building a workflow
2. You find a solution that works
3. You document it with `/n8n-evolve`
4. Future workflow development benefits from this knowledge

**Example entry:**
```markdown
## [2025-11-22] Workflow: prod-marketing-carousel

### Anti-Pattern: Sequential API Calls
**What Happened:** 5 sequential image generation calls took 50s
**Impact:** User timeouts, poor experience

### Positive Pattern: Parallel Split-Merge
**Solution:** Used Split → 5 parallel branches → Merge
**Result:** Execution time dropped from 50s to 12s (76% faster)
**Reusable Pattern:** Use whenever you have independent API calls >2s each
```

---

### 3. workflow-organization.md
**Purpose:** Define workflow directory structure and standards

**Key concepts:**
- Naming: `prod-hr-resume-review`, `lib-auth-oauth-retry`
- Directory layout: `production/`, `library/`, `templates/`, `development/`
- Workflow lifecycle: dev → testing → production
- Version control strategy
- Documentation requirements

**Use this:** When organizing workflows or deciding where to put new files

---

### 4. Slash Commands

#### /n8n-build
Interactive workflow builder that:
- Asks clarifying questions about requirements
- Searches for relevant templates and nodes
- Proposes workflow structure visually
- Creates workflow using MCP tools
- Validates and suggests testing approach

**Usage:**
```
/n8n-build workflow that processes resumes via webhook, scores with AI, saves to database
```

#### /n8n-validate
Comprehensive validation that checks:
- Node configuration
- Connection validity
- Expression syntax
- Error handling presence
- Best practice adherence
- Pattern matching against evolution log

**Usage:**
```
/n8n-validate prod-hr-resume-review
```

#### /n8n-debug
Intelligent debugging that:
- Analyzes failed executions
- Identifies root cause
- Provides specific solutions
- Compares with successful runs
- Checks evolution log for similar issues

**Usage:**
```
/n8n-debug prod-marketing-carousel
```

#### /n8n-evolve
Pattern documentation helper that:
- Guides you through documenting a pattern
- Validates documentation criteria (only real outcomes)
- Formats entry correctly
- Updates statistics
- Offers git commit

**Usage:**
```
/n8n-evolve
# Then answer questions about what happened
```

---

## MCP Tools Available

Claude has direct n8n access via MCP. Key tools:

### Workflow Management
```javascript
// Create workflow
mcp__n8n-mcp__n8n_create_workflow({ name, nodes, connections })

// Get workflow
mcp__n8n-mcp__n8n_get_workflow({ id })

// Update workflow
mcp__n8n-mcp__n8n_update_partial_workflow({ id, operations })

// Validate workflow
mcp__n8n-mcp__n8n_validate_workflow({ id })

// Auto-fix issues
mcp__n8n-mcp__n8n_autofix_workflow({ id, applyFixes: true })
```

### Node Discovery
```javascript
// Search nodes
mcp__n8n-mcp__search_nodes({ query: "database" })

// Get node info
mcp__n8n-mcp__get_node_essentials({ nodeType: "nodes-base.postgres" })

// List AI tools
mcp__n8n-mcp__list_ai_tools()
```

### Templates
```javascript
// Search templates
mcp__n8n-mcp__search_templates({ query: "webhook processing" })

// Get template
mcp__n8n-mcp__get_template({ templateId: 123 })
```

### Execution & Debugging
```javascript
// List executions
mcp__n8n-mcp__n8n_list_executions({ workflowId, status: "error" })

// Get execution details
mcp__n8n-mcp__n8n_get_execution({ id, mode: "filtered" })
```

**Claude automatically uses these tools when building/debugging workflows.**

---

## Development Philosophy

### 1. Native Nodes First
Always prioritize n8n native nodes over Code nodes.

**Order of preference:**
1. Native nodes (HTTP Request, Set, IF, Switch, OpenAI, etc.)
2. Community nodes (vetted)
3. Code nodes (only when necessary)

**Why:** Native nodes are visual, maintainable, and easier to debug.

---

### 2. Pattern Evolution
Learn from real experiences, not speculation.

**Process:**
1. Build workflow
2. Encounter issue OR find optimization
3. Test solution
4. Document in `agents-evolution.md`
5. Pattern becomes reusable knowledge

**Rule:** Only document what actually worked.

---

### 3. Modular Architecture
Build reusable sub-workflows using Execute Workflow nodes.

**Pattern:**
- Main workflows in `production/{domain}/`
- Reusable utilities in `library/{category}/`
- Call library workflows via Execute Workflow node

**Benefits:**
- Changes propagate automatically
- Easier testing
- Reduced duplication

---

### 4. Comprehensive Error Handling
Every production workflow must handle errors.

**Requirements:**
- Error branches on external API calls
- Retry logic with exponential backoff
- Error notifications (Slack, email)
- Graceful degradation

---

## Workflow Lifecycle

```
1. Development
   ├─ Create in n8n
   ├─ Export to `workflows/development/`
   ├─ Iterate and test
   └─ Document basic README

2. Testing
   ├─ Move to `development/testing/`
   ├─ Add comprehensive tests
   ├─ Validate with `/n8n-validate`
   └─ Test with production-like data

3. Production
   ├─ Rename: `dev-*` → `prod-*`
   ├─ Move to `workflows/production/{domain}/`
   ├─ Complete documentation
   ├─ Enable monitoring
   └─ Deploy to production n8n

4. Evolution
   ├─ Document patterns with `/n8n-evolve`
   ├─ Extract reusable logic to library
   └─ Optimize based on real usage
```

---

## Current Workflows

### Production
- ✅ **prod-hr-resume-review** - Candidate resume processing with AI scoring

### Development
- 🚧 **dev-marketing-carousel-generator** - AI-powered carousel creation with image generation

### Planned
- ⏳ Candidate outreach automation (HR)
- ⏳ Interview scheduling (HR)
- ⏳ Social media scheduling (Marketing)
- ⏳ Invoice processing (Operations)
- ⏳ Lead enrichment (Sales)

---

## Best Practices

### When Building Workflows

**Do:**
- ✅ Use descriptive node names ("Fetch User Data" not "HTTP Request")
- ✅ Add error handling from the start
- ✅ Search for templates before building from scratch
- ✅ Use Set node with expressions instead of Code when possible
- ✅ Document as you build

**Don't:**
- ❌ Use generic node names
- ❌ Skip error handling
- ❌ Hardcode credentials
- ❌ Build monolithic workflows (>20 nodes)
- ❌ Duplicate logic that could be in library

---

### When Prompting Claude

**Good prompts include:**
- Clear purpose
- Input/output data structures
- Error scenarios to handle
- Performance requirements
- Workflow stage (dev/prod)

**Example:**
```
Build a workflow: prod-hr-resume-review

Trigger: Webhook POST /api/review-resume
Input: { "resume_text": "...", "job_id": "123" }
Output: { "score": 0-100, "recommendation": "...", "skills": [...] }

Processing:
1. Validate input has required fields
2. Send resume to OpenAI for analysis
3. Calculate fit score
4. Save to PostgreSQL
5. Return JSON response

Error handling:
- Invalid input: Return 400
- OpenAI failure: Retry 3x, then return 500
- Database failure: Log and notify Slack

Expected volume: 50-100 per day
Must complete in < 10 seconds
```

See `.claude/prompts/workflow-building-guide.md` for comprehensive prompting guide.

---

## Git Integration

### Pre-Commit Hook

Automatically validates workflows before commit:

- ✅ Valid JSON structure
- ✅ Required n8n fields present
- ✅ No hardcoded credentials
- ✅ Workflow has name

**Setup:**
```bash
# Hook documentation at:
.claude/hooks/pre-commit-validate-workflows.md
```

### Commit Messages

Format: `<type>(<scope>): <description>`

**Examples:**
```bash
git commit -m "feat(hr): add resume review workflow"
git commit -m "fix(marketing): add retry logic to carousel generator"
git commit -m "docs(evolution): document parallel API call pattern"
```

---

## Pattern Learning Examples

### Example 1: Node Selection

**Anti-Pattern:** Used Code node for simple field extraction
**Impact:** Hard to maintain, required JavaScript knowledge
**Solution:** Replaced with Set node using expressions
**Result:** 50ms faster, visually clear, easier to modify

### Example 2: Performance

**Anti-Pattern:** 5 sequential API calls (50s total)
**Impact:** User timeouts, poor experience
**Solution:** Split → Parallel branches → Merge
**Result:** 12s execution (76% faster)

### Example 3: Error Handling

**Anti-Pattern:** No retry logic on OpenAI API
**Impact:** 15% failure rate due to rate limits
**Solution:** Exponential backoff retry (3 attempts)
**Result:** Failure rate dropped to 0.5%

**These patterns are documented in `agents-evolution.md` and inform future development.**

---

## Troubleshooting

### Claude isn't using MCP tools

**Check:** MCP server is running
```bash
# List available MCP tools
claude code --list-mcp-tools | grep n8n
```

**Solution:** Ensure n8n MCP server is configured in Claude settings

---

### Workflows failing validation

**Use:**
```
/n8n-validate workflow-name
```

**Check:**
- JSON structure valid
- Required fields present
- No hardcoded credentials
- Error handling exists

---

### Can't find workflow in n8n

**List all workflows:**
```javascript
mcp__n8n-mcp__n8n_list_workflows({ limit: 100 })
```

**Search by name:**
Filter results by workflow name

---

### Pattern documentation unclear

**Review examples:**
- Check `agents-evolution.md` for existing patterns
- Use `/n8n-evolve` for guided documentation
- Ensure you're documenting REAL outcomes, not theories

---

## Resources

### Internal Documentation
- `.claude/claude.md` - Main project instructions
- `.claude/agents-evolution.md` - Pattern library
- `.claude/workflow-organization.md` - Structure and standards
- `.claude/prompts/workflow-building-guide.md` - How to prompt effectively

### External Resources
- [n8n Official Docs](https://docs.n8n.io)
- [n8n Community](https://community.n8n.io)
- [n8n Node Library](https://n8n.io/integrations)
- [n8n Workflow Templates](https://n8n.io/workflows)

---

## Roadmap

### Phase 1: Foundation (Current)
- ✅ Claude Code configuration
- ✅ Pattern evolution system
- ✅ Slash commands for workflow management
- ✅ Git hooks for validation
- 🚧 Initial production workflows

### Phase 2: Expansion
- ⏳ Complete HR automation suite
- ⏳ Marketing automation workflows
- ⏳ Operations workflow library
- ⏳ Sales automation system

### Phase 3: Optimization
- ⏳ Advanced monitoring and alerting
- ⏳ Performance optimization patterns
- ⏳ Workflow testing framework
- ⏳ Automated deployment pipeline

### Phase 4: Business in a Box
- ⏳ Complete end-to-end business automation
- ⏳ Industry-specific workflow packs
- ⏳ Template marketplace
- ⏳ Pattern-driven automation recommendations

---

## Contributing

### Adding a New Workflow

1. Build in development:
   ```
   /n8n-build [workflow description]
   ```

2. Test thoroughly

3. Validate:
   ```
   /n8n-validate dev-domain-function
   ```

4. Document patterns if learned:
   ```
   /n8n-evolve
   ```

5. Move to production when ready

6. Commit:
   ```bash
   git add workflows/production/domain/
   git commit -m "feat(domain): add workflow-name"
   ```

---

### Documenting Patterns

**Only document when:**
- ✅ You encountered a real problem
- ✅ You implemented and tested a solution
- ✅ The solution measurably improved the workflow
- ✅ The pattern is reusable in other contexts

**Use `/n8n-evolve` command for guided documentation.**

---

## Support

### Questions?

1. **Check documentation:**
   - `.claude/claude.md` for project guidelines
   - `.claude/workflow-organization.md` for structure
   - `.claude/prompts/workflow-building-guide.md` for prompting

2. **Review evolution log:**
   - `.claude/agents-evolution.md` for learned patterns

3. **Use slash commands:**
   - `/n8n-build` for building
   - `/n8n-validate` for validation
   - `/n8n-debug` for troubleshooting

### Issues?

1. **Validate workflow:** `/n8n-validate`
2. **Debug execution:** `/n8n-debug`
3. **Check evolution log** for similar issues
4. **Document solution** if new pattern emerges

---

## Version History

**v1.0.0** (2025-11-22)
- Initial .claude/ configuration
- Slash commands: build, validate, debug, evolve
- Pattern evolution system
- Git hooks for validation
- Comprehensive documentation

---

**Maintained by:** Claude Code + Development Team
**Last Updated:** 2025-11-22
**License:** Internal Use

---

## Quick Reference Card

```bash
# Build new workflow
/n8n-build [description]

# Validate workflow
/n8n-validate [workflow-name]

# Debug failed execution
/n8n-debug [workflow-name]

# Document pattern
/n8n-evolve

# List all workflows
Use MCP: mcp__n8n-mcp__n8n_list_workflows()

# Search for nodes
Use MCP: mcp__n8n-mcp__search_nodes({ query: "..." })

# Check evolution patterns
Read: .claude/agents-evolution.md

# See prompting guide
Read: .claude/prompts/workflow-building-guide.md
```

---

**Ready to build workflows? Start with:**
```
/n8n-build [describe what you want to automate]
```

**Claude will guide you through the process!**
