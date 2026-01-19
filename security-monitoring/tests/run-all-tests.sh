#!/bin/bash
# ============================================================================
# Security Monitoring - Complete Test Runner
# ============================================================================
# Runs all tests for the security monitoring pipeline:
# 1. Bash E2E tests (test-security-pipeline.sh)
# 2. Python unit/integration tests (pytest)
# ============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo -e "${BLUE}============================================================================${NC}"
echo -e "${BLUE} Security Monitoring - Complete Test Suite${NC}"
echo -e "${BLUE}============================================================================${NC}"
echo ""
echo "Started at: $(date)"
echo "Project root: $PROJECT_ROOT"
echo ""

TOTAL_SUITES=0
PASSED_SUITES=0
FAILED_SUITES=0

# ============================================================================
# Test Suite 1: Bash E2E Tests
# ============================================================================

run_bash_tests() {
    echo -e "\n${BLUE}[Suite 1/2]${NC} Running Bash E2E Tests..."
    echo "============================================"
    ((TOTAL_SUITES++))

    if bash "$SCRIPT_DIR/test-security-pipeline.sh"; then
        echo -e "${GREEN}[Suite 1/2] Bash E2E Tests: PASSED${NC}"
        ((PASSED_SUITES++))
        return 0
    else
        echo -e "${RED}[Suite 1/2] Bash E2E Tests: FAILED${NC}"
        ((FAILED_SUITES++))
        return 1
    fi
}

# ============================================================================
# Test Suite 2: Python Tests
# ============================================================================

run_python_tests() {
    echo -e "\n${BLUE}[Suite 2/2]${NC} Running Python Tests..."
    echo "============================================"
    ((TOTAL_SUITES++))

    # Check if pytest is available
    if ! command -v pytest &> /dev/null; then
        echo -e "${YELLOW}[SKIP] pytest not installed - skipping Python tests${NC}"
        return 0
    fi

    cd "$SCRIPT_DIR"

    if pytest test_enterprise_security.py -v --tb=short; then
        echo -e "${GREEN}[Suite 2/2] Python Tests: PASSED${NC}"
        ((PASSED_SUITES++))
        return 0
    else
        echo -e "${RED}[Suite 2/2] Python Tests: FAILED${NC}"
        ((FAILED_SUITES++))
        return 1
    fi
}

# ============================================================================
# Main
# ============================================================================

main() {
    local exit_code=0

    # Run all test suites
    run_bash_tests || exit_code=1
    run_python_tests || exit_code=1

    # Summary
    echo ""
    echo -e "${BLUE}============================================================================${NC}"
    echo -e "${BLUE} Test Suite Summary${NC}"
    echo -e "${BLUE}============================================================================${NC}"
    echo ""
    echo -e "  Total Suites: $TOTAL_SUITES"
    echo -e "  ${GREEN}Passed:${NC} $PASSED_SUITES"
    echo -e "  ${RED}Failed:${NC} $FAILED_SUITES"
    echo ""
    echo "Finished at: $(date)"

    if [[ $exit_code -eq 0 ]]; then
        echo -e "\n${GREEN}All test suites passed!${NC}"
    else
        echo -e "\n${RED}Some test suites failed!${NC}"
    fi

    return $exit_code
}

main "$@"
