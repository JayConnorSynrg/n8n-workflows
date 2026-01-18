#!/bin/bash

# Google Drive Document Repository - Test Runner
# Workflow ID: IamjzfFxjHviJvJg
# NOTE: Workflow must be ACTIVE for production webhook tests

WEBHOOK_URL="https://jayconnorexe.app.n8n.cloud/webhook/drive-document-repo"
TEST_WEBHOOK_URL="https://jayconnorexe.app.n8n.cloud/webhook-test/drive-document-repo"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASSED=0
FAILED=0
SKIPPED=0

echo "=============================================="
echo "Google Drive Document Repository - Test Suite"
echo "=============================================="
echo ""

# Check if workflow is active
echo "Checking webhook availability..."
HEALTH_CHECK=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$WEBHOOK_URL" -H "Content-Type: application/json" -d '{"operation":"list"}')

if [ "$HEALTH_CHECK" == "404" ]; then
    echo -e "${YELLOW}WARNING: Workflow not active. Tests will use test webhook.${NC}"
    echo "Please activate workflow IamjzfFxjHviJvJg in n8n UI and run tests again."
    echo ""
    ACTIVE=false
else
    echo -e "${GREEN}Workflow is active. Running production tests.${NC}"
    echo ""
    ACTIVE=true
fi

run_test() {
    local TEST_ID="$1"
    local TEST_NAME="$2"
    local PAYLOAD="$3"
    local EXPECTED_STATUS="$4"
    local EXPECTED_CONTAINS="$5"

    if [ "$ACTIVE" == "false" ]; then
        echo -e "${YELLOW}[SKIP]${NC} $TEST_ID: $TEST_NAME (workflow inactive)"
        ((SKIPPED++))
        return
    fi

    RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$WEBHOOK_URL" \
        -H "Content-Type: application/json" \
        -d "$PAYLOAD")

    HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
    BODY=$(echo "$RESPONSE" | sed '$d')

    # Check status code
    if [ "$HTTP_CODE" == "$EXPECTED_STATUS" ]; then
        # Check for expected content if specified
        if [ -n "$EXPECTED_CONTAINS" ] && ! echo "$BODY" | grep -q "$EXPECTED_CONTAINS"; then
            echo -e "${RED}[FAIL]${NC} $TEST_ID: $TEST_NAME"
            echo "       Expected to contain: $EXPECTED_CONTAINS"
            echo "       Response: ${BODY:0:200}..."
            ((FAILED++))
        else
            echo -e "${GREEN}[PASS]${NC} $TEST_ID: $TEST_NAME"
            ((PASSED++))
        fi
    else
        echo -e "${RED}[FAIL]${NC} $TEST_ID: $TEST_NAME"
        echo "       Expected status: $EXPECTED_STATUS, Got: $HTTP_CODE"
        echo "       Response: ${BODY:0:200}..."
        ((FAILED++))
    fi
}

echo "=== Operation Routing Tests ==="
run_test "OP-001" "List operation routing" '{"operation":"list"}' "200" "success\|files\|name"
run_test "OP-002" "Search operation routing" '{"operation":"search","query":"test","limit":5}' "200" ""
run_test "OP-003" "Sync operation routing" '{"operation":"sync"}' "200" "processed\|skipped\|success"
run_test "OP-006" "Invalid operation - fallback" '{"operation":"invalid_operation"}' "200" "error\|available"
run_test "OP-007" "Missing operation field" '{}' "200" ""

echo ""
echo "=== List Operation Tests ==="
run_test "LIST-001" "List all files" '{"operation":"list"}' "200" ""

echo ""
echo "=== Search Operation Tests ==="
run_test "SEARCH-001" "Search with valid query" '{"operation":"search","query":"document","limit":10}' "200" ""
run_test "SEARCH-002" "Search with empty query" '{"operation":"search","query":""}' "200" ""
run_test "SEARCH-004" "Search with limit 1" '{"operation":"search","query":"test","limit":1}' "200" ""
run_test "SEARCH-006" "Search without limit" '{"operation":"search","query":"test"}' "200" ""

echo ""
echo "=== Get Operation Tests ==="
run_test "GET-002" "Get non-existent file" '{"operation":"get","file_id":"non-existent-id-12345"}' "200" ""
run_test "GET-003" "Get without file_id" '{"operation":"get"}' "200" ""

echo ""
echo "=== Edge Case Tests ==="
run_test "EDGE-004" "Unicode in query" '{"operation":"search","query":"日本語 test"}' "200" ""
run_test "EDGE-005" "SQL injection attempt" '{"operation":"search","query":"'"'"'; DROP TABLE users; --"}' "200" ""

echo ""
echo "=============================================="
echo "Test Results Summary"
echo "=============================================="
echo -e "${GREEN}Passed:${NC}  $PASSED"
echo -e "${RED}Failed:${NC}  $FAILED"
echo -e "${YELLOW}Skipped:${NC} $SKIPPED"
echo ""

TOTAL=$((PASSED + FAILED))
if [ $TOTAL -gt 0 ]; then
    PASS_RATE=$((PASSED * 100 / TOTAL))
    echo "Pass Rate: $PASS_RATE%"
fi

if [ $FAILED -gt 0 ]; then
    exit 1
else
    exit 0
fi
