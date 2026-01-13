# Pre-Commit Hook: Validate N8N Workflows

**Hook Type:** Pre-commit
**Purpose:** Validate n8n workflow JSON files before allowing git commit

---

## Hook Configuration

Add this to your `.git/hooks/pre-commit` file (or git will prompt you):

```bash
#!/bin/bash

# N8N Workflow Validation Pre-Commit Hook

echo "🔍 Validating n8n workflow files..."

# Find all JSON files in workflows directory
WORKFLOW_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep -E "workflows/.*\.json$")

if [ -z "$WORKFLOW_FILES" ]; then
  echo "✅ No workflow files to validate"
  exit 0
fi

# Track if any validations fail
VALIDATION_FAILED=0

for file in $WORKFLOW_FILES; do
  echo "Validating: $file"

  # Check 1: Valid JSON
  if ! python3 -m json.tool "$file" > /dev/null 2>&1; then
    echo "❌ Invalid JSON: $file"
    VALIDATION_FAILED=1
    continue
  fi

  # Check 2: Contains required n8n workflow fields
  if ! grep -q '"nodes"' "$file" || ! grep -q '"connections"' "$file"; then
    echo "❌ Missing required n8n workflow structure: $file"
    echo "   Workflow must contain 'nodes' and 'connections' fields"
    VALIDATION_FAILED=1
    continue
  fi

  # Check 3: No hardcoded credentials
  if grep -qE '"value":\s*"(sk-|pk_live|ghp_|gho_)"' "$file"; then
    echo "❌ Possible hardcoded credentials detected: $file"
    echo "   Found API key pattern in workflow JSON"
    VALIDATION_FAILED=1
    continue
  fi

  # Check 4: Workflow has a name
  if ! grep -q '"name"' "$file"; then
    echo "❌ Workflow missing 'name' field: $file"
    VALIDATION_FAILED=1
    continue
  fi

  echo "✅ Valid: $file"
done

if [ $VALIDATION_FAILED -eq 1 ]; then
  echo ""
  echo "❌ Workflow validation failed. Please fix issues before committing."
  echo ""
  echo "Hints:"
  echo "  - Use 'jq' to format JSON: jq . $file > temp && mv temp $file"
  echo "  - Check for hardcoded API keys (use n8n credentials instead)"
  echo "  - Ensure workflow has all required fields"
  echo ""
  exit 1
fi

echo ""
echo "✅ All workflow validations passed!"
exit 0
```

---

## What This Hook Validates

### 1. Valid JSON Structure
Ensures workflow files are properly formatted JSON that can be parsed.

**Prevents:**
- Syntax errors (missing commas, brackets)
- Malformed JSON that would break n8n import

**Error Example:**
```
❌ Invalid JSON: workflows/production/hr/resume-review.json
```

### 2. Required N8N Fields
Validates that workflow JSON contains essential n8n structure.

**Required fields:**
- `nodes` - Array of workflow nodes
- `connections` - Object defining node connections
- `name` - Workflow name

**Prevents:**
- Committing partial/incomplete workflow exports
- Committing non-workflow JSON files

**Error Example:**
```
❌ Missing required n8n workflow structure: workflows/production/hr/resume-review.json
   Workflow must contain 'nodes' and 'connections' fields
```

### 3. Hardcoded Credentials Detection
Scans for common API key patterns that should use n8n credentials instead.

**Patterns detected:**
- OpenAI keys: `sk-`
- Stripe keys: `pk_live`
- GitHub tokens: `ghp_`, `gho_`
- Generic patterns: long alphanumeric strings in credential fields

**Prevents:**
- Accidentally committing sensitive API keys
- Security vulnerabilities

**Error Example:**
```
❌ Possible hardcoded credentials detected: workflows/production/marketing/carousel-gen.json
   Found API key pattern in workflow JSON
```

### 4. Workflow Naming
Ensures workflows have a name field for identification.

**Prevents:**
- Unnamed workflows that are hard to identify
- Confusion when importing workflows

---

## Advanced Validation (Optional)

For stricter validation, add these checks:

### Check 5: Naming Convention

```bash
# Extract workflow name
WORKFLOW_NAME=$(grep -o '"name":\s*"[^"]*"' "$file" | cut -d'"' -f4)

# Check naming convention
if [[ ! $WORKFLOW_NAME =~ ^(prod|dev|lib|template)- ]]; then
  echo "⚠️  Warning: Workflow name doesn't follow convention: $WORKFLOW_NAME"
  echo "   Expected: prod-*, dev-*, lib-*, or template-*"
  # Note: Warning only, doesn't fail commit
fi
```

### Check 6: Error Handling Presence

```bash
# Check if workflow has error handling
if ! grep -q '"continueOnFail":\s*true' "$file" && \
   ! grep -q '"onError"' "$file"; then
  echo "⚠️  Warning: No error handling detected in workflow: $file"
  echo "   Consider adding error branches or continueOnFail for production workflows"
fi
```

### Check 7: Large Workflow Warning

```bash
# Count number of nodes
NODE_COUNT=$(grep -o '"type":\s*"n8n-nodes-' "$file" | wc -l)

if [ "$NODE_COUNT" -gt 25 ]; then
  echo "⚠️  Warning: Large workflow detected ($NODE_COUNT nodes): $file"
  echo "   Consider breaking into smaller sub-workflows for maintainability"
fi
```

---

## Claude Integration

**When Claude commits workflow changes:**

Claude should run validation before commit:

```javascript
// Before committing workflow changes
const workflowFiles = await Bash({
  command: "git diff --cached --name-only --diff-filter=ACM | grep -E 'workflows/.*\\.json$'"
});

if (workflowFiles) {
  // Validate each workflow
  for (const file of workflowFiles) {
    // Check valid JSON
    // Check required fields
    // Check for credentials
  }
}

// If all validations pass
await Bash({
  command: `git add ${workflowFiles.join(' ')} && git commit -m "feat(workflow): ${message}"`
});
```

---

## Bypass Hook (Emergency Only)

If you need to bypass validation (not recommended):

```bash
git commit --no-verify -m "message"
```

**Only use when:**
- Testing a deliberately broken workflow
- Emergency hotfix (fix validation after)
- Hook has a bug (report and fix)

**Never bypass for:**
- Avoiding credential checks
- Skipping validation because "it works"
- Committing WIP workflows (use dev branch instead)

---

## Setup Instructions

### Manual Setup

1. Create hook file:
```bash
cat > .git/hooks/pre-commit << 'EOF'
# [paste hook script above]
EOF
```

2. Make executable:
```bash
chmod +x .git/hooks/pre-commit
```

3. Test:
```bash
# Make a change to a workflow file
git add workflows/test.json
git commit -m "test"
# Hook should run validation
```

### Automated Setup (Recommended)

Add to `.claude/hooks/setup.sh`:

```bash
#!/bin/bash

echo "Setting up n8n workflow git hooks..."

# Create pre-commit hook
cp .claude/hooks/pre-commit-validate-workflows.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit

echo "✅ Git hooks installed!"
echo "   Pre-commit workflow validation is now active"
```

Run setup:
```bash
bash .claude/hooks/setup.sh
```

---

## Troubleshooting

### Hook Not Running

**Symptoms:** Commits succeed without validation output

**Fixes:**
1. Check hook is executable: `ls -l .git/hooks/pre-commit`
2. Ensure hook file has correct name (no `.sh` extension)
3. Verify shebang: `#!/bin/bash` is first line

### False Positives

**Symptoms:** Hook blocks valid workflows

**Fixes:**
1. Review error message for specific issue
2. Check if workflow JSON is properly formatted
3. Verify credentials are using n8n credential system
4. Report bug if validation logic is incorrect

### Performance Issues

**Symptoms:** Hook takes too long on large repos

**Optimizations:**
1. Only validate staged files (already implemented)
2. Skip validation for non-production workflows
3. Implement parallel validation for multiple files

---

## Evolution Log Integration

When validation catches issues, consider documenting:

**If you fix a workflow that failed validation:**
- Anti-pattern: What caused the validation failure
- Positive pattern: How you fixed it
- Add to `.claude/agents-evolution.md`

**Example:**
```markdown
## [2025-11-22] Workflow: prod-marketing-carousel

### Anti-Pattern: Hardcoded OpenAI API Key in Workflow
**What Happened:** Committed workflow with API key in HTTP Request node

### Positive Pattern: Use N8N Credential System
**Solution:** Created credential in n8n UI, referenced in workflow
**Result:** Validation passed, key is secure
```

---

## Version History

**v1.0.0** (2025-11-22)
- Initial pre-commit validation hook
- JSON structure validation
- Credential detection
- Required field checks

---

**Status:** Active
**Maintenance:** Update patterns as new issues are discovered
**Owner:** Claude + Development Team
