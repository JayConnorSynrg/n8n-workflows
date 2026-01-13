---
name: documentation-validity-audit
description: |
  Audit and validate n8n pattern documentation using DVMS. Use when:
  - Patterns may be stale (>30 days since verification)
  - Contradictions suspected between patterns
  - Before implementing nodes with anti_memory flag
  - After debugging failures to verify documentation correctness
  - Periodically for maintenance audits
  Provides freshness validation, contradiction detection, and deprecation lifecycle management.
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Edit
  - Write
  - mcp__n8n-mcp__*
---

# Documentation Validity Audit Skill

**Version:** 1.0.0
**DVMS Version:** 1.0.0
**Purpose:** Provide sub-agents with systematic documentation validity auditing methodology

---

## Quick Reference: Audit Phases

| Phase | Objective | Key Actions |
|-------|-----------|-------------|
| 1 | Freshness Check | Calculate days since last_verified, determine tier |
| 2 | Deprecation Check | Verify pattern is ACTIVE, not deprecated |
| 3 | Contradiction Scan | Cross-reference patterns for same node type |
| 4 | MCP Verification | Validate against current n8n schema |
| 5 | Resolution | Apply DVMS resolution protocol if issues found |
| 6 | Update | Refresh validity metadata |

---

## Phase 1: Freshness Validation

**Check pattern age and determine required action:**

```javascript
function checkFreshness(pattern) {
  const lastVerified = new Date(pattern.validity.last_verified);
  const now = new Date();
  const daysSince = Math.floor((now - lastVerified) / (1000 * 60 * 60 * 24));

  if (daysSince <= 30) {
    return {
      tier: 'FRESH',
      visual: '🟢',
      action: 'PROCEED',
      days: daysSince,
      message: 'Pattern is current'
    };
  } else if (daysSince <= 60) {
    return {
      tier: 'AGING',
      visual: '🟡',
      action: 'OPTIONAL_VERIFY',
      days: daysSince,
      message: 'Pattern aging - verification recommended'
    };
  } else if (daysSince <= 90) {
    return {
      tier: 'STALE',
      visual: '🟠',
      action: 'VERIFY_BEFORE_USE',
      days: daysSince,
      message: 'Pattern stale - verify before critical use'
    };
  } else {
    return {
      tier: 'EXPIRED',
      visual: '🔴',
      action: 'MANDATORY_VERIFY',
      days: daysSince,
      message: 'Pattern EXPIRED - re-validation REQUIRED'
    };
  }
}
```

**Freshness Audit Output:**

```markdown
## Freshness Audit: {patternId}

**Last Verified:** {date}
**Days Since Verification:** {days}
**Freshness Tier:** {tier} {visual}
**Action Required:** {action}

{message}
```

---

## Phase 2: Deprecation Status Check

**Verify pattern is still active:**

```javascript
function checkDeprecation(pattern) {
  const status = pattern.deprecation?.status || 'ACTIVE';

  switch (status) {
    case 'ACTIVE':
      return {
        usable: true,
        warning: null,
        action: 'PROCEED'
      };

    case 'DEPRECATED':
      const sunsetDate = new Date(pattern.deprecation.sunset_date);
      const daysUntilSunset = Math.floor((sunsetDate - new Date()) / (1000 * 60 * 60 * 24));
      return {
        usable: true,
        warning: `DEPRECATED - Sunset in ${daysUntilSunset} days`,
        action: 'SHOW_WARNING',
        replacement: pattern.deprecation.superseded_by,
        reason: pattern.deprecation.deprecation_reason
      };

    case 'SUNSET':
      return {
        usable: true,
        warning: 'SUNSET - Pattern will be archived soon',
        action: 'STRONG_WARNING',
        replacement: pattern.deprecation.superseded_by,
        migrationGuide: pattern.deprecation.migration_guide
      };

    case 'ARCHIVED':
      return {
        usable: false,
        warning: 'ARCHIVED - Pattern no longer available',
        action: 'BLOCK_AND_REDIRECT',
        replacement: pattern.deprecation.superseded_by
      };

    default:
      return {
        usable: true,
        warning: null,
        action: 'PROCEED'
      };
  }
}
```

**Deprecation Audit Output:**

```markdown
## Deprecation Status: {patternId}

**Status:** {status}
**Usable:** {yes/no}

{If DEPRECATED or SUNSET:}
**Replacement:** {superseded_by}
**Reason:** {deprecation_reason}
**Migration Guide:** {link or inline}
```

---

## Phase 3: Contradiction Scan

**Check for conflicts with other patterns for same node type:**

```javascript
async function scanForContradictions(pattern, nodeType) {
  const patternIndex = await Read({
    file_path: '.claude/patterns/pattern-index.json'
  });

  // Find all patterns that apply to this node type
  const relatedPatternIds = patternIndex.node_type_mappings[nodeType] || [];
  const contradictions = [];

  for (const patternId of relatedPatternIds) {
    if (patternId === pattern.id) continue;

    const otherPattern = patternIndex.patterns.find(p => p.id === patternId);
    if (!otherPattern) continue;

    // Check for value conflicts
    if (pattern.correct_patterns && otherPattern.correct_patterns) {
      for (const myPattern of pattern.correct_patterns) {
        for (const theirPattern of otherPattern.correct_patterns) {
          // Extract parameter name and value
          const myMatch = myPattern.match(/(\w+):\s*['"]?([^'"]+)/);
          const theirMatch = theirPattern.match(/(\w+):\s*['"]?([^'"]+)/);

          if (myMatch && theirMatch && myMatch[1] === theirMatch[1]) {
            if (myMatch[2] !== theirMatch[2]) {
              contradictions.push({
                type: 'DIRECT',
                severity: 'CRITICAL',
                parameter: myMatch[1],
                pattern_a: { id: pattern.id, value: myMatch[2] },
                pattern_b: { id: otherPattern.id, value: theirMatch[2] }
              });
            }
          }
        }
      }
    }

    // Check for typeVersion conflicts via node-reference
    const myNodeRef = patternIndex.node_references?.langchain?.[nodeType];
    if (myNodeRef && otherPattern.node_reference) {
      // Load and compare typeVersions
      // (Implementation would load files and compare)
    }
  }

  return contradictions;
}
```

**Contradiction Scan Output:**

```markdown
## Contradiction Scan: {patternId}

**Node Type:** {nodeType}
**Related Patterns Checked:** {count}

{If no contradictions:}
**Status:** ✅ No contradictions found

{If contradictions found:}
### Contradictions Detected: {count}

| Type | Severity | Parameter | Pattern A | Pattern B |
|------|----------|-----------|-----------|-----------|
| {type} | {severity} | {param} | {patternA.id}: {value} | {patternB.id}: {value} |

**Resolution Required:** Use DVMS Resolution Protocol
```

---

## Phase 4: MCP Verification

**Validate pattern against current n8n schema:**

```javascript
async function verifyAgainstMCP(pattern, nodeType) {
  // Delegate to n8n-mcp-delegate
  const mcpResult = await Task({
    subagent_type: "n8n-mcp-delegate",
    prompt: `Verify pattern validity for node: ${nodeType}

    Pattern ID: ${pattern.id}
    Documented typeVersion: ${pattern.node_reference || 'N/A'}
    Key configurations:
    ${JSON.stringify(pattern.correct_patterns || [], null, 2)}

    1. Get current node schema with get_node
    2. Verify typeVersion is still current (or identify latest)
    3. Verify documented parameters still exist and have same format
    4. Identify any breaking changes since last verification
    5. Return verification result with confidence`,
    model: "haiku"
  });

  return {
    verified: mcpResult.valid,
    currentTypeVersion: mcpResult.typeVersion,
    discrepancies: mcpResult.discrepancies || [],
    breakingChanges: mcpResult.breakingChanges || [],
    confidence: mcpResult.confidence
  };
}
```

**MCP Verification Output:**

```markdown
## MCP Verification: {patternId}

**Node Type:** {nodeType}
**Documented Version:** {documented}
**Current MCP Version:** {current}

{If versions match:}
**Status:** ✅ Version current

{If versions differ:}
**Status:** ⚠️ Version outdated

### Discrepancies

| Field | Documented | Current |
|-------|------------|---------|
| {field} | {doc_value} | {current_value} |

### Breaking Changes
{list of breaking changes if any}

**Confidence:** {HIGH/MEDIUM/LOW}
**Recommendation:** {update pattern / deprecate / no action}
```

---

## Phase 5: Resolution Protocol

**Apply DVMS resolution when issues found:**

```javascript
async function resolveIssues(auditResults) {
  const resolutions = [];

  // Handle expired patterns
  if (auditResults.freshness.tier === 'EXPIRED') {
    // Re-validate and update
    const mcpVerification = await verifyAgainstMCP(
      auditResults.pattern,
      auditResults.nodeType
    );

    if (mcpVerification.verified) {
      resolutions.push({
        type: 'FRESHNESS_UPDATE',
        action: 'Update last_verified to today',
        newTier: 'FRESH'
      });
    } else {
      resolutions.push({
        type: 'PATTERN_UPDATE',
        action: 'Update pattern to match current MCP schema',
        changes: mcpVerification.discrepancies
      });
    }
  }

  // Handle contradictions
  if (auditResults.contradictions.length > 0) {
    for (const contradiction of auditResults.contradictions) {
      // Query MCP for authoritative answer
      const resolution = await Task({
        subagent_type: "n8n-mcp-delegate",
        prompt: `Resolve contradiction:
                Parameter: ${contradiction.parameter}
                Value A: ${contradiction.pattern_a.value}
                Value B: ${contradiction.pattern_b.value}

                Which is correct according to current n8n?`,
        model: "haiku"
      });

      resolutions.push({
        type: 'CONTRADICTION_RESOLUTION',
        action: 'Deprecate losing pattern',
        winner: resolution.winner,
        loser: resolution.loser,
        evidence: resolution.evidence
      });
    }
  }

  return resolutions;
}
```

---

## Phase 6: Update Validity Metadata

**After resolution, update pattern-index.json:**

```javascript
async function updateValidityMetadata(patternId, auditResult) {
  const patternIndex = await Read({
    file_path: '.claude/patterns/pattern-index.json'
  });

  // Find and update pattern
  const pattern = patternIndex.patterns.find(p => p.id === patternId);
  if (!pattern) return;

  // Update validity
  pattern.validity = {
    last_verified: new Date().toISOString().split('T')[0],
    freshness_tier: 'FRESH',
    verified_against: 'mcp__n8n-mcp__get_node',
    verification_method: 'automatic',
    next_verification_due: calculateNextDue()
  };

  // Update contradiction check if performed
  if (auditResult.contradictions !== undefined) {
    pattern.contradiction_check = {
      last_checked: new Date().toISOString().split('T')[0],
      conflicts_found: auditResult.contradictions.length,
      resolved_conflicts: auditResult.resolutions
        .filter(r => r.type === 'CONTRADICTION_RESOLUTION')
        .map(r => r.winner)
    };
  }

  // Write updated index
  await Write({
    file_path: '.claude/patterns/pattern-index.json',
    content: JSON.stringify(patternIndex, null, 2)
  });

  // Log audit event
  await logAuditEvent({
    timestamp: new Date().toISOString(),
    event: 'VALIDITY_AUDIT_COMPLETE',
    pattern: patternId,
    result: auditResult.freshness.tier,
    resolutions: auditResult.resolutions.length
  });
}

function calculateNextDue() {
  const nextDue = new Date();
  nextDue.setDate(nextDue.getDate() + 90); // 90-day cycle
  return nextDue.toISOString().split('T')[0];
}
```

---

## Complete Audit Workflow

**Run full audit on a pattern:**

```javascript
async function runFullAudit(patternId, nodeType) {
  console.log(`\n=== DVMS Validity Audit: ${patternId} ===\n`);

  // Load pattern
  const patternIndex = await Read({
    file_path: '.claude/patterns/pattern-index.json'
  });
  const pattern = patternIndex.patterns.find(p => p.id === patternId);

  if (!pattern) {
    return { error: 'Pattern not found' };
  }

  const auditResult = {
    pattern: pattern,
    nodeType: nodeType,
    timestamp: new Date().toISOString()
  };

  // Phase 1: Freshness
  console.log('Phase 1: Checking freshness...');
  auditResult.freshness = checkFreshness(pattern);
  console.log(`  ${auditResult.freshness.visual} ${auditResult.freshness.tier}`);

  // Phase 2: Deprecation
  console.log('Phase 2: Checking deprecation status...');
  auditResult.deprecation = checkDeprecation(pattern);
  console.log(`  Status: ${pattern.deprecation?.status || 'ACTIVE'}`);

  // Phase 3: Contradictions
  console.log('Phase 3: Scanning for contradictions...');
  auditResult.contradictions = await scanForContradictions(pattern, nodeType);
  console.log(`  Found: ${auditResult.contradictions.length} contradictions`);

  // Phase 4: MCP Verification (if needed)
  if (auditResult.freshness.tier === 'EXPIRED' ||
      auditResult.contradictions.length > 0) {
    console.log('Phase 4: MCP verification required...');
    auditResult.mcpVerification = await verifyAgainstMCP(pattern, nodeType);
  }

  // Phase 5: Resolution (if needed)
  if (auditResult.freshness.tier === 'EXPIRED' ||
      auditResult.contradictions.length > 0 ||
      !auditResult.deprecation.usable) {
    console.log('Phase 5: Applying resolutions...');
    auditResult.resolutions = await resolveIssues(auditResult);
  }

  // Phase 6: Update metadata
  console.log('Phase 6: Updating validity metadata...');
  await updateValidityMetadata(patternId, auditResult);

  console.log(`\n=== Audit Complete ===\n`);
  return auditResult;
}
```

---

## Audit Report Template

```markdown
# Documentation Validity Audit Report

**Pattern:** {patternId}
**Node Type:** {nodeType}
**Audit Date:** {date}
**Auditor:** {agent_id}

---

## Summary

| Check | Result | Action |
|-------|--------|--------|
| Freshness | {tier} {visual} | {action} |
| Deprecation | {status} | {action} |
| Contradictions | {count} found | {action} |
| MCP Verification | {passed/failed} | {action} |

**Overall Status:** {PASSED | ACTION_REQUIRED | BLOCKED}

---

## Details

### Freshness Analysis
{details}

### Deprecation Status
{details}

### Contradiction Scan
{details}

### MCP Verification
{details}

---

## Resolutions Applied

{list of resolutions with details}

---

## Recommendations

1. {recommendation}
2. {recommendation}

---

**Next Scheduled Audit:** {next_verification_due}
```

---

## Sub-Agent Integration

When using this skill from sub-agents:

```javascript
// Quick freshness check
const freshness = await checkFreshness(pattern);
if (freshness.action === 'MANDATORY_VERIFY') {
  const auditResult = await runFullAudit(patternId, nodeType);
}

// Before implementing anti_memory node
if (nodeRef.anti_memory === true) {
  // ALWAYS run full audit
  const auditResult = await runFullAudit(patternId, nodeType);
  if (auditResult.contradictions.length > 0) {
    // Resolve before proceeding
    await resolveIssues(auditResult);
  }
}
```

---

## Success Criteria

Audit complete when:
1. Freshness tier is FRESH or AGING
2. No unresolved contradictions
3. Pattern matches current MCP schema
4. Validity metadata updated
5. Audit logged to validity-log.jsonl

---

**Philosophy:** Trust Nothing, Verify Everything, Update Always
**Never:** Use stale patterns, ignore contradictions, skip MCP verification for anti_memory nodes
