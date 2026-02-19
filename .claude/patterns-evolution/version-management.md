# Version Management Patterns
Category from agents-evolution.md | 5 entries | Workflows: universal, 8bhcEHkbbvnhdHBh, gjYSN6xNjLw8qsA1
---

### ~~DEPRECATED PATTERN~~ - OVERRIDDEN BY USER DIRECTIVE (2025-11-27)

**This pattern has been superseded by the "Always Use Latest Node Versions" directive below.**

<details>
<summary>Historical Pattern (No Longer Active)</summary>

### Anti-Pattern: Upgrading AI Agent typeVersion Without Validating Compatibility

**What Happened:** When updating workflow `AI Carousel Generator - 5 Slides` (ID: 8bhcEHkbbvnhdHBh), I incorrectly upgraded the AI Agent node from `typeVersion: 2` to `typeVersion: 3` while also fixing other issues (OpenAI node types, enterprise styles, JSON expressions).

**Specific Changes:**
- Changed AI Agent `@n8n/n8n-nodes-langchain.agent` from typeVersion 2 → 3
- Reason: Saw that official node documentation listed version 3 as latest
- Assumption: Newer version = better, should always upgrade

**Impact:**
- Workflow validation showed 0 errors BUT warnings indicated AI Agent configuration issues
- User reported: "you are still failing to create the agent node correctly"
- False positive warnings: "AI Agent has no systemMessage" (even though systemMessage WAS correctly configured in options)
- User had to repeat request: "you have done this correctly in the past"
- Required investigation and rollback to typeVersion 2

**Why It Failed:**
1. **Ignored working examples** - All previous working workflows (baseline.json, FIXED.json, validated.json) used typeVersion 2
2. **Assumed latest = compatible** - TypeVersion 3 may have different validation behavior or parameter requirements
3. **Didn't verify compatibility** - Failed to check if typeVersion 3 worked with existing parameter structure
4. **Mixed multiple changes** - Combined typeVersion upgrade with other fixes, making it harder to isolate the issue

### Positive Pattern: Match TypeVersions to Working Examples, Don't Auto-Upgrade

**Solution:** When updating existing workflows, **preserve typeVersions** from working examples unless there's a specific reason to upgrade AND you've validated the new version works.

**Implementation:**
1. **Discovered Root Cause:**
   - Searched for AI Agent configurations in all local workflow files: `grep "@n8n/n8n-nodes-langchain.agent" *.json`
   - Found all working versions used typeVersion 2:
     - baseline.json: typeVersion 2 ✅
     - FIXED.json: typeVersion 2 ✅
     - validated.json: typeVersion 2 ✅
     - CORRECTED.json (my version): typeVersion 3 ❌

2. **Fixed Configuration:**
   ```json
   {
     "type": "@n8n/n8n-nodes-langchain.agent",
     "typeVersion": 2,  // ← Changed from 3 back to 2
     "parameters": {
       "promptType": "define",
       "text": "={{ ... }}",
       "hasOutputParser": true,
       "options": {
         "systemMessage": "..."  // Already correct
       }
     }
   }
   ```

3. **Validated Fix:**
   - Deployed corrected workflow with typeVersion 2
   - Validation showed 0 errors (success!)
   - Warning "Outdated typeVersion: 2. Latest is 3" is acceptable - working version > latest version

**Result:**
- Workflow validation: 0 errors (down from previous errors)
- AI Agent configuration recognized as valid
- Avoided future typeVersion upgrade mistakes
- Pattern documented: "Match working examples, don't auto-upgrade"

**Reusable Pattern:**

**TypeVersion Management Rules:**
1. **When CREATING new workflows:**
   - Search for working template/example first
   - Use SAME typeVersion as working example
   - Don't use "latest" version unless proven compatible

2. **When UPDATING existing workflows:**
   - PRESERVE existing typeVersions
   - Only upgrade typeVersion if:
     - ✅ Specific feature requires new version
     - ✅ You've tested new version works with your parameters
     - ✅ Breaking changes are documented and addressed
   - Don't blindly upgrade based on "latest is better"

3. **TypeVersion Compatibility Check:**
   ```bash
   # Before using new typeVersion, search codebase for working examples
   grep "\"type\": \"@n8n/n8n-nodes-langchain.agent\"" workflows/**/*.json -A 2

   # Count which typeVersion is most common
   grep "typeVersion" workflows/**/*.json | sort | uniq -c
   ```

4. **When In Doubt:**
   - Use typeVersion from working example
   - Validation warnings about "outdated typeVersion" are acceptable
   - Working workflow > technically "latest" version

**Key Learnings:**
- **"Latest" ≠ "Best"** - Newer typeVersions may have validation quirks or changed behavior
- **Working examples are authoritative** - If multiple working workflows use typeVersion 2, use 2
- **Validate before upgrading** - TypeVersion changes can break workflows even if validation passes
- **systemMessage validation false positives** - Validation tool may incorrectly warn about missing systemMessage even when correctly configured in `options`
- **One change at a time** - Don't mix typeVersion upgrades with other fixes

</details>

### Positive Pattern: Always Research and Use Latest Node TypeVersions

**Context:** User directive issued 2025-11-27 via SYNRG command to **override all previous conservative version patterns** and mandate always using latest node versions.

**Directive:** "I always want you to find the latest version of the node based on the documentation. Just ensure you are using it with the correct parameters. Hard code into and weave intuitively into all the documentation to actually check the latest version of the node and actually research the n8n docs on each one before implementing."

**Solution:** Before implementing ANY node in ANY workflow, ALWAYS:
1. Research n8n official documentation for latest typeVersion
2. Use latest version universally (all node types)
3. Debug and fix parameter issues until latest version works
4. Never rollback to older versions - fix forward instead

**Implementation Protocol:**

**MANDATORY PRE-IMPLEMENTATION CHECKLIST:**

**Before adding ANY node to a workflow:**

1. **Research Latest TypeVersion:**
   ```bash
   # Use n8n MCP tools to find latest version
   mcp__n8n-mcp__get_node_info({ nodeType: "nodes-base.{name}" })

   # Check official n8n documentation
   # URL: https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-base.{name}/

   # Verify latest typeVersion in documentation
   ```

2. **Get Correct Parameters for Latest Version:**
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

3. **Implement with Latest Version:**
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

4. **If Validation Errors Occur:**
   - ✅ Debug parameter configuration for latest version
   - ✅ Research breaking changes in version upgrade notes
   - ✅ Adjust parameters to match latest version requirements
   - ✅ Use `mcp__n8n-mcp__n8n_autofix_workflow` to identify fixes
   - ❌ DO NOT rollback to older typeVersion
   - ❌ DO NOT use working examples if they have outdated versions

**Result:**
- **Prevents technical debt** - No outdated node versions in workflows
- **Ensures latest features** - Access to newest node capabilities
- **Enforces best practices** - All workflows use current n8n standards
- **Eliminates version drift** - Consistent versions across all workflows

**Reusable Pattern:**

**UNIVERSAL NODE VERSION POLICY:**

**For ALL node types (no exceptions):**
- OpenAI nodes → Use latest typeVersion from n8n docs
- AI Agent nodes → Use latest typeVersion from n8n docs
- Form Trigger nodes → Use latest typeVersion from n8n docs
- HTTP Request nodes → Use latest typeVersion from n8n docs
- Set nodes → Use latest typeVersion from n8n docs
- Code nodes → Use latest typeVersion from n8n docs
- ALL OTHER NODES → Use latest typeVersion from n8n docs

**Research Sources (in priority order):**
1. **n8n MCP Tools** - `mcp__n8n-mcp__get_node_info` (authoritative)
2. **n8n Official Docs** - https://docs.n8n.io/integrations/
3. **n8n Node Schema** - `mcp__n8n-mcp__get_node_essentials`
4. **n8n Templates** - Only for parameter examples, NOT version reference

**Workflow Development Sequence (UPDATED):**

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

**When Validation Warnings Appear:**
- ⚠️ "Outdated typeVersion: X. Latest is Y" → CRITICAL ERROR - Must fix
- ✅ "Node configuration valid" → Proceed
- ❌ Ignore any patterns suggesting "working version > latest version"

**Breaking Change Management:**

When latest version has breaking changes:
1. **Document the breaking change** - What changed in parameters?
2. **Update parameter structure** - Adapt to new requirements
3. **Test thoroughly** - Ensure new version works correctly
4. **Never rollback** - Fix forward, debug until working
5. **Add to evolution patterns** - Document migration path for future reference

**Key Learnings:**
- **Latest = Required** - Always use newest typeVersion, no exceptions
- **Research before implementation** - Mandatory version checking prevents outdated code
- **Fix forward, never rollback** - Debug latest version until it works
- **Documentation is authoritative** - n8n official docs + MCP tools > working examples
- **Prevent technical debt** - No workflow should use outdated node versions
- **Universal application** - This policy applies to ALL nodes, ALL workflows, ALL situations

**Performance Impact:**
- **Research overhead**: +5-10 minutes per node (one-time cost)
- **Debugging overhead**: +10-30 minutes if breaking changes (occasional)
- **Technical debt prevention**: Eliminates future migration work (ongoing savings)
- **Feature access**: Immediate access to latest capabilities (ongoing benefit)
- **Long-term ROI**: Prevents accumulation of outdated workflows (exponential savings)

**Files Updated:**
- `.claude/agents-evolution.md` (this file - Pattern-004 overridden)
- `.claude/CLAUDE.md` (to be updated with latest version mandate)
- `.claude/WORKFLOW-DEVELOPMENT-PROTOCOL.md` (to be updated with research protocol)

**Enforcement:**
This directive OVERRIDES all previous conservative version management patterns. When conflicts arise between "use working examples" and "use latest versions", ALWAYS choose latest versions.

### Anti-Pattern: Documentation Inconsistency Causing Repeated AI Agent Failures

**What Happened:** While refactoring the Teams Voice Bot workflow, AI Agent nodes kept breaking. Investigation revealed that documentation files contained contradictory information:

- `pattern-index.json` documented typeVersion "3.1"
- `agent.md` documented typeVersion 3.1 with explicit parameters
- Working reference workflow `gjYSN6xNjLw8qsA1` actually uses typeVersion 3 with minimal parameters
- MCP `get_node` reports 3.1 as "latest" but this causes execution failures

**The Wrong Configuration (documented in files):**
```json
{
  "typeVersion": 3.1,
  "parameters": {
    "promptType": "define",
    "text": "={{ $json.chatInput }}",
    "options": {
      "systemMessage": "You are a helpful assistant",
      "maxIterations": 10
    }
  }
}
```

**Impact:**
- AI Agent nodes repeatedly broke during workflow refactoring
- Multiple debugging cycles wasted on the same issue
- Claude consistently used WRONG configuration pattern from documentation
- Root cause was documentation inconsistency, not implementation error
- `/synrg-n8ndebug` command failed to detect the contradiction

**Why It Failed:**
- Documentation files were never validated for INTERNAL consistency
- `/synrg-n8ndebug` only validated patterns against MCP, not patterns against patterns
- No mechanism existed to verify documentation files agreed with each other
- MCP "latest version" was trusted over verified working workflows

### Positive Pattern: Documentation Consistency Audit + Minimal Configuration

**Solution:** Implemented multi-part fix:

1. **Added PHASE 0.5 to `/synrg-n8ndebug`** - Documentation Consistency Audit
   - Verifies all documentation files agree on typeVersion and configuration
   - Compares: pattern-index.json, node-reference files, pattern files, reference workflows
   - Detects contradictions BEFORE debugging begins
   - Prefers verified reference workflows over MCP "latest version"

2. **Corrected All Documentation Files:**
   - `pattern-index.json` → typeVersion "3", added reference_workflow, anti_memory flag
   - `agent.md` → Complete rewrite with correct minimal configuration
   - `README.md` → Updated table to show typeVersion 3, added Anti-Memory flag
   - `ai-agent-typeversion.md` → Added explicit anti-pattern warning section

3. **Established Reference Workflow Registry:**
```json
{
  "@n8n/n8n-nodes-langchain.agent": {
    "workflow_id": "gjYSN6xNjLw8qsA1",
    "workflow_name": "Teams Voice Bot Reference",
    "verified_config": {
      "typeVersion": 3,
      "parameters": { "options": {} }
    }
  }
}
```

**The Correct Configuration (verified working):**
```json
{
  "typeVersion": 3,
  "parameters": {
    "options": {}
  }
}
```

**Result:**
- All documentation files now consistent on AI Agent configuration
- PHASE 0.5 will detect future documentation contradictions
- Reference workflow verification takes precedence over MCP "latest"
- AI Agent node flagged with anti_memory for mandatory reference reading
- Pattern explicitly documented as CRITICAL anti-pattern

**Reusable Pattern:**
```
┌─────────────────────────────────────────────────────────────┐
│  DOCUMENTATION CONSISTENCY AUDIT PROTOCOL                   │
│                                                             │
│  1. Before debugging, verify documentation internal         │
│     consistency (pattern files agree with each other)       │
│  2. Reference workflows are authoritative over MCP "latest" │
│  3. Flag known failure points with anti_memory protocol     │
│  4. Minimal parameters > explicit parameters for agents     │
│  5. When MCP says X is latest but working code uses Y,      │
│     trust the working code                                  │
└─────────────────────────────────────────────────────────────┘
```

**Key Learnings:**
- **Documentation contradictions are a root cause category** - Not just code bugs
- **MCP "latest" ≠ production verified** - Working workflows take precedence
- **Internal consistency audit is mandatory** - Patterns must agree with each other
- **Minimal configuration wins** - Over-specification causes failures
- **Anti-Memory Protocol expands** - AI Agent node now included

**Files Modified:**
- `.claude/commands/synrg-n8ndebug.md` - Added PHASE 0.5 Documentation Consistency Audit
- `.claude/node-reference/langchain/agent.md` - Complete rewrite with correct pattern
- `.claude/patterns/pattern-index.json` - Fixed typeVersion, added reference_workflow
- `.claude/node-reference/README.md` - Updated table with correct version
- `.claude/patterns/workflow-architecture/ai-agent-typeversion.md` - Added anti-pattern section

---
