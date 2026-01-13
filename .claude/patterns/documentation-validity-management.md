# Documentation Validity Management System (DVMS)

**Version:** 1.0.0
**Created:** 2025-12-28
**Purpose:** Ensure all n8n workflow documentation remains valid, current, and contradiction-free

---

## Core Principles

1. **Documentation is Evidence-Based** - All patterns require validation before acceptance
2. **Freshness is Mandatory** - Stale documentation (>90 days unverified) triggers re-validation
3. **Contradictions are Resolved Immediately** - Never maintain conflicting patterns
4. **MCP is Source of Truth** - n8n MCP tools provide authoritative current information
5. **Deprecation is Formal** - Patterns are deprecated, not deleted, with clear migration paths

---

## 1. Freshness Validation Protocol

### 1.1 Freshness Tiers

| Tier | Age | Status | Action Required |
|------|-----|--------|-----------------|
| **FRESH** | 0-30 days | Valid | None |
| **AGING** | 31-60 days | Valid with warning | Optional re-validation |
| **STALE** | 61-90 days | Requires attention | Re-validate before use |
| **EXPIRED** | >90 days | Invalid until verified | MANDATORY re-validation |

### 1.2 Automatic Freshness Check

```javascript
function checkDocumentationFreshness(pattern) {
  const now = new Date();
  const lastVerified = new Date(pattern.last_verified);
  const daysSinceVerification = (now - lastVerified) / (1000 * 60 * 60 * 24);

  if (daysSinceVerification <= 30) {
    return { tier: 'FRESH', action: 'PROCEED', color: 'green' };
  } else if (daysSinceVerification <= 60) {
    return { tier: 'AGING', action: 'OPTIONAL_VERIFY', color: 'yellow' };
  } else if (daysSinceVerification <= 90) {
    return { tier: 'STALE', action: 'VERIFY_BEFORE_USE', color: 'orange' };
  } else {
    return { tier: 'EXPIRED', action: 'MANDATORY_VERIFY', color: 'red' };
  }
}
```

### 1.3 MCP-Based Re-Validation Protocol

**When freshness check returns STALE or EXPIRED:**

```
STEP 1: Fetch current node schema from MCP
┌─────────────────────────────────────────────────────────────────┐
│  Delegate to n8n-mcp-delegate:                                  │
│                                                                 │
│  Task({                                                         │
│    subagent_type: "n8n-mcp-delegate",                          │
│    prompt: `Fetch current schema for node type: {nodeType}      │
│             Include: typeVersion, required parameters,          │
│             parameter formats, and any breaking changes`,       │
│    model: "haiku"                                               │
│  })                                                             │
└─────────────────────────────────────────────────────────────────┘

STEP 2: Compare documented configuration with MCP response
- Check typeVersion matches (or is superseded)
- Verify parameter names still valid
- Confirm parameter formats unchanged
- Identify any new required parameters

STEP 3: Update or Deprecate
- If match: Update last_verified date
- If minor changes: Update pattern, note changes
- If breaking changes: Trigger deprecation lifecycle
```

### 1.4 Freshness Metadata Schema

```json
{
  "validity": {
    "last_verified": "2025-12-28",
    "verified_against": "mcp__n8n-mcp__get_node v1.3",
    "verification_method": "automatic|manual|user_confirmed",
    "freshness_tier": "FRESH|AGING|STALE|EXPIRED",
    "next_verification_due": "2026-03-28",
    "verification_history": [
      {
        "date": "2025-12-28",
        "result": "VALID|UPDATED|DEPRECATED",
        "changes": ["list of changes if any"],
        "verified_by": "agent_id or user"
      }
    ]
  }
}
```

---

## 2. Contradiction Detection Protocol

### 2.1 Contradiction Types

| Type | Severity | Example |
|------|----------|---------|
| **DIRECT** | CRITICAL | Pattern A says `"data"`, Pattern B says `"=data"` for same param |
| **VERSION** | HIGH | Pattern A uses typeVersion 2, Pattern B uses typeVersion 3 |
| **BEHAVIORAL** | MEDIUM | Pattern A expects sync response, Pattern B expects async |
| **SUBTLE** | LOW | Different but equivalent approaches documented |

### 2.2 Automated Contradiction Detection

**Run on every pattern access and pattern creation:**

```javascript
async function detectContradictions(nodeType, newPattern) {
  const contradictions = [];

  // 1. Load all patterns for this node type
  const existingPatterns = await loadPatternsForNodeType(nodeType);

  // 2. Check each parameter in new pattern against existing
  for (const [paramName, paramValue] of Object.entries(newPattern.parameters)) {
    for (const existing of existingPatterns) {
      if (existing.parameters[paramName] !== undefined) {
        const existingValue = existing.parameters[paramName];

        // Check for direct contradiction
        if (existingValue !== paramValue) {
          contradictions.push({
            type: 'DIRECT',
            severity: 'CRITICAL',
            parameter: paramName,
            pattern_a: { id: existing.id, value: existingValue },
            pattern_b: { id: newPattern.id, value: paramValue },
            resolution_required: true
          });
        }
      }
    }
  }

  // 3. Check typeVersion conflicts
  const versionConflicts = existingPatterns.filter(p =>
    p.typeVersion !== newPattern.typeVersion
  );

  if (versionConflicts.length > 0) {
    contradictions.push({
      type: 'VERSION',
      severity: 'HIGH',
      details: versionConflicts.map(p => ({
        pattern_id: p.id,
        typeVersion: p.typeVersion
      })),
      new_version: newPattern.typeVersion,
      resolution_required: true
    });
  }

  return contradictions;
}
```

### 2.3 Contradiction Alert Format

```markdown
## ⚠️ CONTRADICTION DETECTED

**Node Type:** @n8n/n8n-nodes-langchain.openAi
**Parameter:** binaryPropertyName
**Severity:** CRITICAL

### Conflicting Patterns:

| Pattern | Location | Value | Last Verified |
|---------|----------|-------|---------------|
| openai-image-nodes | api-integration/ | `"data"` | 2025-12-27 |
| NEW PATTERN | (proposed) | `"=data"` | 2025-12-28 |

### Resolution Required

This contradiction MUST be resolved before proceeding.
Use Resolution Protocol (Section 3) to determine valid pattern.
```

---

## 3. Contradiction Resolution Protocol

### 3.1 Resolution Hierarchy

```
PRIORITY ORDER (highest first):

1. MCP SOURCE OF TRUTH
   └─ Current n8n MCP response is authoritative

2. WORKING PRODUCTION WORKFLOW
   └─ If pattern works in verified workflow, it's valid

3. MOST RECENT VERIFICATION
   └─ More recently verified pattern takes precedence

4. OFFICIAL N8N DOCUMENTATION
   └─ docs.n8n.io as secondary source

5. TEMPLATE ANALYSIS
   └─ How do popular templates configure this?
```

### 3.2 MCP-First Resolution

```
┌─────────────────────────────────────────────────────────────────┐
│  MANDATORY FIRST STEP: Query MCP for authoritative answer       │
│                                                                 │
│  Task({                                                         │
│    subagent_type: "n8n-mcp-delegate",                          │
│    prompt: `                                                    │
│      Contradiction Resolution Request:                          │
│                                                                 │
│      Node: {nodeType}                                           │
│      Parameter: {parameterName}                                 │
│      Conflicting Values: {valueA} vs {valueB}                   │
│                                                                 │
│      1. Get current node schema with get_node                   │
│      2. Check parameter requirements and format                 │
│      3. Search templates for common usage patterns              │
│      4. Return: which value is CURRENTLY correct and why        │
│    `,                                                           │
│    model: "haiku"                                               │
│  })                                                             │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 Resolution Decision Matrix

| MCP Says | Template Usage | Production Test | Resolution |
|----------|---------------|-----------------|------------|
| Value A | Value A | N/A | **Value A** (high confidence) |
| Value A | Value B | N/A | **Value A** (MCP authoritative) |
| Value A | Mixed | Value A works | **Value A** (verified) |
| Unclear | Value A | Value A works | **Value A** (empirically valid) |
| Unclear | Mixed | Neither tested | **ESCALATE** to user |

### 3.4 Resolution Documentation

**When contradiction is resolved, document:**

```json
{
  "resolution": {
    "resolved_date": "2025-12-28",
    "winning_value": "data",
    "losing_value": "=data",
    "resolution_method": "mcp_verification",
    "evidence": {
      "mcp_response": "Node schema shows binaryPropertyName is property reference, not expression",
      "template_count": 15,
      "templates_using_winning": 15,
      "templates_using_losing": 0
    },
    "confidence": "HIGH",
    "deprecated_patterns": ["pattern-id-that-was-wrong"],
    "resolved_by": "agent_id"
  }
}
```

---

## 4. Pattern Deprecation Lifecycle

### 4.1 Deprecation States

```
ACTIVE ──────────────────────────────────────────────────────────►
   │
   │ Contradiction found & resolved
   │ OR MCP shows breaking change
   │ OR Pattern proven incorrect
   ▼
DEPRECATED (Day 0) ───────────────────────────────────────────────►
   │ - Pattern marked deprecated: true
   │ - deprecation_reason documented
   │ - superseded_by points to replacement
   │ - Warning shown on every access
   │
   │ 30-day sunset period
   ▼
SUNSET (Day 30) ──────────────────────────────────────────────────►
   │ - Pattern still accessible
   │ - STRONG warning: "This pattern will be archived"
   │ - Migration guide provided
   │
   │ 30-day grace period
   ▼
ARCHIVED (Day 60) ────────────────────────────────────────────────►
   │ - Pattern moved to archive/
   │ - Not included in normal lookups
   │ - Still accessible for historical reference
   │ - Clearly marked as ARCHIVED
   │
   │ 90-day retention
   ▼
PURGED (Day 150) ─────────────────────────────────────────────────►
     - Pattern permanently removed
     - Only audit log entry remains
```

### 4.2 Deprecation Metadata Schema

```json
{
  "deprecation": {
    "status": "ACTIVE|DEPRECATED|SUNSET|ARCHIVED",
    "deprecated_date": null,
    "deprecation_reason": null,
    "superseded_by": null,
    "sunset_date": null,
    "archive_date": null,
    "purge_date": null,
    "migration_guide": null,
    "breaking_change": false,
    "deprecation_history": []
  }
}
```

### 4.3 Deprecation Trigger Protocol

```javascript
async function deprecatePattern(patternId, reason, supersededBy) {
  const pattern = await loadPattern(patternId);
  const now = new Date();

  // Calculate lifecycle dates
  const sunsetDate = new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000);
  const archiveDate = new Date(now.getTime() + 60 * 24 * 60 * 60 * 1000);
  const purgeDate = new Date(now.getTime() + 150 * 24 * 60 * 60 * 1000);

  // Update pattern metadata
  pattern.deprecation = {
    status: 'DEPRECATED',
    deprecated_date: now.toISOString().split('T')[0],
    deprecation_reason: reason,
    superseded_by: supersededBy,
    sunset_date: sunsetDate.toISOString().split('T')[0],
    archive_date: archiveDate.toISOString().split('T')[0],
    purge_date: purgeDate.toISOString().split('T')[0],
    migration_guide: generateMigrationGuide(pattern, supersededBy),
    breaking_change: isBreakingChange(pattern, supersededBy)
  };

  // Add to deprecation history
  pattern.deprecation.deprecation_history.push({
    date: now.toISOString(),
    action: 'DEPRECATED',
    reason: reason,
    by: 'dvms_system'
  });

  // Save updated pattern
  await savePattern(pattern);

  // Log deprecation event
  await logDeprecationEvent(patternId, reason, supersededBy);

  return pattern;
}
```

### 4.4 Deprecation Warning Format

```markdown
## ⚠️ DEPRECATED PATTERN

**Pattern:** openai-image-old
**Status:** DEPRECATED (Day 15 of 30)
**Deprecated:** 2025-12-13
**Reason:** typeVersion 1 superseded by typeVersion 2

### Migration Required

This pattern will be **SUNSET** on 2026-01-12.
After sunset, this pattern will be **ARCHIVED** on 2026-02-11.

### Replacement Pattern

Use: `openai-image-nodes` (api-integration/openai-image-nodes.md)

### Migration Guide

1. Update `typeVersion` from 1 to 2
2. Change `model` to `modelId` with ResourceLocator format
3. Verify `binaryPropertyName` is `"data"` not `"=data"`

### Continue Anyway?

[Yes - I understand the risks] [No - Show replacement pattern]
```

---

## 5. Integration Points

### 5.1 Pattern Index Schema Updates

Add to each pattern entry in `pattern-index.json`:

```json
{
  "id": "openai-image-nodes",
  "file": "api-integration/openai-image-nodes.md",
  "validity": {
    "last_verified": "2025-12-28",
    "freshness_tier": "FRESH",
    "verified_against": "mcp__n8n-mcp__get_node",
    "next_verification_due": "2026-03-28"
  },
  "deprecation": {
    "status": "ACTIVE",
    "deprecated_date": null,
    "superseded_by": null
  },
  "contradiction_check": {
    "last_checked": "2025-12-28",
    "conflicts_found": 0,
    "resolved_conflicts": []
  }
}
```

### 5.2 synrg-n8ndebug Integration

Add DVMS Phase to debugging flow:

```markdown
## Phase 0.25: Documentation Validity Check (DVMS)

**Before consulting ANY pattern:**

1. **Freshness Gate**
   - Check pattern.validity.freshness_tier
   - If EXPIRED: Trigger re-validation before use
   - If STALE: Warn and optionally re-validate

2. **Deprecation Gate**
   - Check pattern.deprecation.status
   - If DEPRECATED/SUNSET: Show warning, offer replacement
   - If ARCHIVED: Block usage, redirect to replacement

3. **Contradiction Scan**
   - Check pattern.contradiction_check.conflicts_found
   - If conflicts exist: Trigger resolution before use

4. **MCP Currency Verification**
   - For anti_memory nodes: ALWAYS verify against MCP
   - Compare documented typeVersion with MCP current
   - Flag any discrepancies for immediate resolution
```

### 5.3 Automatic Maintenance Tasks

```javascript
// Daily validity maintenance
async function dailyValidityMaintenance() {
  const allPatterns = await loadAllPatterns();

  for (const pattern of allPatterns) {
    // 1. Update freshness tiers
    pattern.validity.freshness_tier = calculateFreshnessTier(pattern);

    // 2. Advance deprecation lifecycle
    await advanceDeprecationLifecycle(pattern);

    // 3. Check for expired patterns needing re-validation
    if (pattern.validity.freshness_tier === 'EXPIRED') {
      await queueForRevalidation(pattern);
    }

    // 4. Archive/purge patterns past their dates
    await processLifecycleTransitions(pattern);
  }

  // 5. Run contradiction scan across all active patterns
  await runGlobalContradictionScan();

  // 6. Generate validity report
  await generateValidityReport();
}
```

---

## 6. Audit Trail

### 6.1 Validity Audit Log

Location: `.claude/patterns/audit/validity-log.jsonl`

```jsonl
{"timestamp":"2025-12-28T10:00:00Z","event":"FRESHNESS_CHECK","pattern":"openai-image-nodes","result":"FRESH","tier":"FRESH"}
{"timestamp":"2025-12-28T10:01:00Z","event":"CONTRADICTION_DETECTED","patterns":["pattern-a","pattern-b"],"type":"DIRECT","parameter":"binaryPropertyName"}
{"timestamp":"2025-12-28T10:02:00Z","event":"RESOLUTION_COMPLETE","winning":"pattern-a","losing":"pattern-b","method":"mcp_verification"}
{"timestamp":"2025-12-28T10:03:00Z","event":"DEPRECATION_TRIGGERED","pattern":"pattern-b","reason":"Contradiction resolved","superseded_by":"pattern-a"}
{"timestamp":"2025-12-28T10:04:00Z","event":"REVALIDATION_COMPLETE","pattern":"openai-image-nodes","result":"VALID","changes":[]}
```

### 6.2 Validity Report Format

```markdown
# Documentation Validity Report
**Generated:** 2025-12-28 10:00:00

## Summary

| Metric | Count |
|--------|-------|
| Total Patterns | 15 |
| FRESH | 12 |
| AGING | 2 |
| STALE | 1 |
| EXPIRED | 0 |
| DEPRECATED | 1 |
| ARCHIVED | 0 |
| Contradictions Pending | 0 |

## Patterns Requiring Attention

### STALE (Re-validation Recommended)
- `memory-session-config` - Last verified: 2025-10-15 (74 days ago)

### DEPRECATED
- `old-openai-pattern` - Sunset: 2026-01-15 - Use: `openai-image-nodes`

## Recent Resolutions

| Date | Pattern | Resolution | Confidence |
|------|---------|------------|------------|
| 2025-12-28 | binaryPropertyName conflict | `"data"` wins | HIGH |

## Next Scheduled Verifications

| Pattern | Due Date |
|---------|----------|
| openai-image-nodes | 2026-03-28 |
| ai-agent-typeversion | 2026-03-27 |
```

---

## 7. Quick Reference Commands

### For Agents

```javascript
// Check pattern validity before use
const validity = await checkPatternValidity(patternId);
if (validity.requiresAction) {
  await handleValidityAction(validity);
}

// Resolve contradiction
await resolveContradiction(patternA, patternB, nodeType);

// Deprecate pattern
await deprecatePattern(patternId, reason, supersededBy);

// Re-validate pattern against MCP
await revalidatePattern(patternId);
```

### For Manual Audits

```bash
# Run validity check on all patterns
DVMS.checkAll()

# Force re-validation of specific pattern
DVMS.revalidate("openai-image-nodes")

# View deprecation queue
DVMS.showDeprecationQueue()

# Generate validity report
DVMS.generateReport()
```

---

**DVMS Version:** 1.0.0
**Maintained By:** SYNRG Evolution System
**Next Review:** 2026-01-28
