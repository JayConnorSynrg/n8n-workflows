#!/bin/bash
# ============================================
# AUTOMATED COMPLIANCE AUDIT SCRIPT
# ============================================
# Run: ./scripts/compliance/audit-compliance.sh
# CI/CD: Called by GitHub Actions weekly
# Output: JSON report + markdown summary
# ============================================

# Note: Removed 'set -e' because arithmetic operations like ((PASS++))
# return exit code 1 when the value is 0, causing premature exit

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Output files
REPORT_DIR="compliance/audit-reports"
DATE=$(date +%Y-%m-%d)
JSON_REPORT="$REPORT_DIR/audit-$DATE.json"
MD_REPORT="$REPORT_DIR/audit-$DATE.md"

mkdir -p "$REPORT_DIR"

echo "============================================"
echo "   ENTERPRISE COMPLIANCE AUDIT"
echo "   Date: $DATE"
echo "============================================"
echo ""

# Initialize counters
PASS=0
FAIL=0
WARN=0

# Initialize JSON structure
echo "{" > "$JSON_REPORT"
echo "  \"audit_date\": \"$DATE\"," >> "$JSON_REPORT"
echo "  \"audit_time\": \"$(date -u +%H:%M:%S)Z\"," >> "$JSON_REPORT"
echo "  \"checks\": [" >> "$JSON_REPORT"

# Initialize Markdown
echo "# Compliance Audit Report" > "$MD_REPORT"
echo "" >> "$MD_REPORT"
echo "**Date:** $DATE" >> "$MD_REPORT"
echo "**Time:** $(date -u +%H:%M:%S) UTC" >> "$MD_REPORT"
echo "" >> "$MD_REPORT"
echo "## Summary" >> "$MD_REPORT"
echo "" >> "$MD_REPORT"

first_check=true

# Function to add check result
add_check() {
    local id=$1
    local name=$2
    local status=$3
    local details=$4
    local framework=$5

    if [ "$first_check" = false ]; then
        echo "," >> "$JSON_REPORT"
    fi
    first_check=false

    echo "    {" >> "$JSON_REPORT"
    echo "      \"id\": \"$id\"," >> "$JSON_REPORT"
    echo "      \"name\": \"$name\"," >> "$JSON_REPORT"
    echo "      \"status\": \"$status\"," >> "$JSON_REPORT"
    echo "      \"details\": \"$details\"," >> "$JSON_REPORT"
    echo "      \"framework\": \"$framework\"" >> "$JSON_REPORT"
    echo "    }" >> "$JSON_REPORT"

    if [ "$status" = "PASS" ]; then
        echo -e "${GREEN}[PASS]${NC} $id: $name"
        ((PASS++))
    elif [ "$status" = "FAIL" ]; then
        echo -e "${RED}[FAIL]${NC} $id: $name - $details"
        ((FAIL++))
    else
        echo -e "${YELLOW}[WARN]${NC} $id: $name - $details"
        ((WARN++))
    fi
}

echo "=== DOCUMENTATION CHECKS ==="
echo ""

# Check 1: Security policies exist
if [ -d "security/policies" ] && [ "$(ls -1 security/policies/*.md 2>/dev/null | wc -l)" -ge 4 ]; then
    count=$(ls -1 security/policies/*.md 2>/dev/null | wc -l | tr -d ' ')
    add_check "DOC-001" "Security policies exist" "PASS" "$count policy files found" "SOC2-CC1"
else
    add_check "DOC-001" "Security policies exist" "FAIL" "Missing security policies" "SOC2-CC1"
fi

# Check 2: Incident response plan exists
if [ -f "security/procedures/INCIDENT-RESPONSE-PLAN.md" ]; then
    add_check "DOC-002" "Incident response plan" "PASS" "Plan documented" "SOC2-CC7.3"
else
    add_check "DOC-002" "Incident response plan" "FAIL" "No incident response plan" "SOC2-CC7.3"
fi

# Check 3: Data classification policy exists
if [ -f "security/policies/DATA-CLASSIFICATION-POLICY.md" ]; then
    add_check "DOC-003" "Data classification policy" "PASS" "Policy documented" "SOC2-CC6.6"
else
    add_check "DOC-003" "Data classification policy" "FAIL" "No data classification policy" "SOC2-CC6.6"
fi

# Check 4: GDPR documentation exists
if [ -d "compliance/gdpr" ] && [ "$(ls -1 compliance/gdpr/*.md 2>/dev/null | wc -l)" -ge 3 ]; then
    count=$(ls -1 compliance/gdpr/*.md 2>/dev/null | wc -l | tr -d ' ')
    add_check "DOC-004" "GDPR documentation" "PASS" "$count GDPR documents found" "GDPR-Art5"
else
    add_check "DOC-004" "GDPR documentation" "FAIL" "Insufficient GDPR documentation" "GDPR-Art5"
fi

# Check 5: Compliance index exists
if [ -f "SECURITY-COMPLIANCE-INDEX.md" ]; then
    add_check "DOC-005" "Compliance index" "PASS" "Index documented" "SOC2-CC1"
else
    add_check "DOC-005" "Compliance index" "FAIL" "No compliance index" "SOC2-CC1"
fi

echo ""
echo "=== SECURITY CONFIGURATION CHECKS ==="
echo ""

# Check 6: .gitignore has security patterns
if [ -f ".gitignore" ]; then
    security_patterns=$(grep -c "\.env\|\.mcp\|credential\|secret\|\.key\|\.pem" .gitignore 2>/dev/null || echo "0")
    if [ "$security_patterns" -ge 5 ]; then
        add_check "SEC-001" "Gitignore security patterns" "PASS" "$security_patterns patterns found" "SOC2-CC6.1"
    else
        add_check "SEC-001" "Gitignore security patterns" "WARN" "Only $security_patterns patterns (need 5+)" "SOC2-CC6.1"
    fi
else
    add_check "SEC-001" "Gitignore security patterns" "FAIL" "No .gitignore file" "SOC2-CC6.1"
fi

# Check 7: No secrets in tracked files (excludes dist/, build/, node_modules)
secrets_found=$(grep -rE "(api_key|apikey|secret|password).*['\"][A-Za-z0-9]{20,}" --include="*.js" --include="*.ts" --include="*.json" --include="*.py" . 2>/dev/null | grep -v node_modules | grep -v ".example" | grep -v "/dist/" | grep -v "/build/" | grep -v ".min.js" | wc -l | tr -d ' ')
if [ "$secrets_found" -eq 0 ]; then
    add_check "SEC-002" "No hardcoded secrets" "PASS" "No secrets detected" "SOC2-CC6.1"
else
    add_check "SEC-002" "No hardcoded secrets" "FAIL" "$secrets_found potential secrets found" "SOC2-CC6.1"
fi

# Check 8: Pre-commit hooks configured
if [ -f ".pre-commit-config.yaml" ]; then
    add_check "SEC-003" "Pre-commit hooks" "PASS" "Hooks configured" "SOC2-CC8.1"
else
    add_check "SEC-003" "Pre-commit hooks" "WARN" "No pre-commit hooks" "SOC2-CC8.1"
fi

# Check 9: GitHub Actions security workflow
if [ -f ".github/workflows/security-scanning.yml" ]; then
    add_check "SEC-004" "Security scanning CI" "PASS" "Workflow configured" "SOC2-CC7.1"
else
    add_check "SEC-004" "Security scanning CI" "FAIL" "No security scanning workflow" "SOC2-CC7.1"
fi

# Check 10: No .env files tracked
env_tracked=$(git ls-files | grep -E "^\.env$|\.env\." | grep -v ".example" | wc -l | tr -d ' ')
if [ "$env_tracked" -eq 0 ]; then
    add_check "SEC-005" "No .env files tracked" "PASS" "Environment files not tracked" "SOC2-CC6.1"
else
    add_check "SEC-005" "No .env files tracked" "FAIL" "$env_tracked .env files in git" "SOC2-CC6.1"
fi

echo ""
echo "=== COMPLIANCE CHECKLIST CHECKS ==="
echo ""

# Check 11: Credential rotation checklist exists
if [ -f "compliance/checklists/CREDENTIAL-ROTATION-CHECKLIST.md" ]; then
    add_check "CMP-001" "Credential rotation checklist" "PASS" "Checklist exists" "SOC2-CC6.1"
else
    add_check "CMP-001" "Credential rotation checklist" "FAIL" "No rotation checklist" "SOC2-CC6.1"
fi

# Check 12: Vendor risk register exists
if [ -f "compliance/gdpr/VENDOR-RISK-REGISTER.md" ]; then
    add_check "CMP-002" "Vendor risk register" "PASS" "Register documented" "GDPR-Art28"
else
    add_check "CMP-002" "Vendor risk register" "FAIL" "No vendor risk register" "GDPR-Art28"
fi

# Check 13: Retention schedule exists
if [ -f "security/policies/RETENTION-SCHEDULE.md" ]; then
    add_check "CMP-003" "Data retention schedule" "PASS" "Schedule documented" "GDPR-Art5"
else
    add_check "CMP-003" "Data retention schedule" "FAIL" "No retention schedule" "GDPR-Art5"
fi

# Check 14: DPA tracking exists
if [ -f "compliance/gdpr/DPA-TRACKING.md" ]; then
    add_check "CMP-004" "DPA tracking" "PASS" "DPA tracking documented" "GDPR-Art28"
else
    add_check "CMP-004" "DPA tracking" "FAIL" "No DPA tracking" "GDPR-Art28"
fi

echo ""
echo "=== AUTOMATION CHECKS ==="
echo ""

# Check 15: Weekly compliance report workflow
if [ -f ".github/workflows/weekly-compliance-report.yml" ]; then
    add_check "AUTO-001" "Weekly compliance report" "PASS" "Workflow configured" "SOC2-CC4.1"
else
    add_check "AUTO-001" "Weekly compliance report" "WARN" "No weekly report automation" "SOC2-CC4.1"
fi

# Check 16: Policy review reminders
if [ -f ".github/workflows/policy-review-reminders.yml" ]; then
    add_check "AUTO-002" "Policy review reminders" "PASS" "Workflow configured" "SOC2-CC1.4"
else
    add_check "AUTO-002" "Policy review reminders" "WARN" "No policy review automation" "SOC2-CC1.4"
fi

# Check 17: Retention automation SQL
if [ -f "scripts/compliance/retention-automation.sql" ]; then
    add_check "AUTO-003" "Retention automation SQL" "PASS" "SQL scripts ready" "GDPR-Art5"
else
    add_check "AUTO-003" "Retention automation SQL" "WARN" "No retention SQL scripts" "GDPR-Art5"
fi

# Close JSON array
echo "" >> "$JSON_REPORT"
echo "  ]," >> "$JSON_REPORT"

# Calculate score
TOTAL=$((PASS + FAIL + WARN))
SCORE=$((PASS * 100 / TOTAL))

echo "" >> "$JSON_REPORT"
echo "  \"summary\": {" >> "$JSON_REPORT"
echo "    \"total_checks\": $TOTAL," >> "$JSON_REPORT"
echo "    \"passed\": $PASS," >> "$JSON_REPORT"
echo "    \"failed\": $FAIL," >> "$JSON_REPORT"
echo "    \"warnings\": $WARN," >> "$JSON_REPORT"
echo "    \"score\": $SCORE" >> "$JSON_REPORT"
echo "  }" >> "$JSON_REPORT"
echo "}" >> "$JSON_REPORT"

# Complete markdown report
echo "" >> "$MD_REPORT"
echo "| Metric | Value |" >> "$MD_REPORT"
echo "|--------|-------|" >> "$MD_REPORT"
echo "| Total Checks | $TOTAL |" >> "$MD_REPORT"
echo "| Passed | $PASS |" >> "$MD_REPORT"
echo "| Failed | $FAIL |" >> "$MD_REPORT"
echo "| Warnings | $WARN |" >> "$MD_REPORT"
echo "| **Score** | **$SCORE%** |" >> "$MD_REPORT"
echo "" >> "$MD_REPORT"

if [ $FAIL -gt 0 ]; then
    echo "## Action Required" >> "$MD_REPORT"
    echo "" >> "$MD_REPORT"
    echo "The following checks failed and require immediate attention:" >> "$MD_REPORT"
    echo "" >> "$MD_REPORT"
fi

echo ""
echo "============================================"
echo "   AUDIT COMPLETE"
echo "============================================"
echo ""
echo -e "Total Checks: $TOTAL"
echo -e "${GREEN}Passed: $PASS${NC}"
echo -e "${RED}Failed: $FAIL${NC}"
echo -e "${YELLOW}Warnings: $WARN${NC}"
echo ""
echo -e "Score: ${SCORE}%"
echo ""
echo "Reports saved to:"
echo "  - $JSON_REPORT"
echo "  - $MD_REPORT"
echo ""

# Exit with error if any critical failures
if [ $FAIL -gt 3 ]; then
    echo -e "${RED}CRITICAL: More than 3 compliance checks failed!${NC}"
    exit 1
fi

exit 0
