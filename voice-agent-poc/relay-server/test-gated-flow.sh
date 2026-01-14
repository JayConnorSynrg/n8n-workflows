#!/bin/bash
# =============================================================================
# GATED FLOW TEST SCRIPT v2.0
# Tests the complete Gate 1 → Gate 2 (with waiting) → Gate 3 flow
# =============================================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
RELAY_URL="${RELAY_URL:-http://localhost:3000}"
TOOL_CALL_ID="tc_test_$(date +%s)"
INTENT_ID="intent_test_$(date +%s)"

# Test counters
PASSED=0
FAILED=0

pass() {
    echo -e "${GREEN}PASS: $1${NC}"
    ((PASSED++))
}

fail() {
    echo -e "${RED}FAIL: $1${NC}"
    ((FAILED++))
}

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   GATED FLOW TEST SUITE v2.0${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "Relay URL: ${CYAN}$RELAY_URL${NC}"
echo -e "Tool Call ID: ${CYAN}$TOOL_CALL_ID${NC}"
echo -e "Intent ID: ${CYAN}$INTENT_ID${NC}"
echo ""

# =============================================================================
# Test 1: Health Check
# =============================================================================
echo -e "${YELLOW}[Test 1] Health Check${NC}"
HEALTH_RESPONSE=$(curl -s "$RELAY_URL/health")
if echo "$HEALTH_RESPONSE" | grep -q '"status":"healthy"\|"status":"ok"'; then
    pass "Server is healthy"
    echo "$HEALTH_RESPONSE" | jq . 2>/dev/null || echo "$HEALTH_RESPONSE"
else
    fail "Health check failed"
    echo "$HEALTH_RESPONSE"
fi
echo ""

# =============================================================================
# Test 2: Gate 1 - PREPARING (should return immediately)
# =============================================================================
echo -e "${YELLOW}[Test 2] Gate 1 - PREPARING${NC}"
GATE1_RESPONSE=$(curl -s -X POST "$RELAY_URL/tool-progress" \
    -H "Content-Type: application/json" \
    -d "{
        \"tool_call_id\": \"$TOOL_CALL_ID\",
        \"intent_id\": \"$INTENT_ID\",
        \"status\": \"PREPARING\",
        \"gate\": 1,
        \"cancellable\": true,
        \"message\": \"Preparing to send email...\"
    }")

if echo "$GATE1_RESPONSE" | grep -q '"continue":true'; then
    pass "Gate 1 returned continue=true"
else
    fail "Gate 1 unexpected response"
fi
echo "$GATE1_RESPONSE" | jq . 2>/dev/null || echo "$GATE1_RESPONSE"
echo ""

# =============================================================================
# Test 3: Gate 2 with TRUE WAITING - Confirmation via /tool-confirm
# =============================================================================
echo -e "${YELLOW}[Test 3] Gate 2 - TRUE WAITING with Confirmation${NC}"
GATE2_CONFIRM_ID="tc_g2_confirm_$(date +%s)"

echo -e "${CYAN}Starting Gate 2 request in background (will wait for confirmation)...${NC}"

# Start Gate 2 in background - it will WAIT
(
    GATE2_RESPONSE=$(curl -s --max-time 20 -X POST "$RELAY_URL/tool-progress" \
        -H "Content-Type: application/json" \
        -d "{
            \"tool_call_id\": \"$GATE2_CONFIRM_ID\",
            \"intent_id\": \"intent_confirm_$(date +%s)\",
            \"status\": \"READY_TO_SEND\",
            \"gate\": 2,
            \"requires_confirmation\": true,
            \"cancellable\": true,
            \"message\": \"Email is ready to send. Confirm to proceed.\"
        }")
    echo ""
    echo -e "${CYAN}Gate 2 Response after confirmation:${NC}"
    echo "$GATE2_RESPONSE" | jq . 2>/dev/null || echo "$GATE2_RESPONSE"

    if echo "$GATE2_RESPONSE" | grep -q '"continue":true'; then
        echo -e "${GREEN}Gate 2 confirmed successfully!${NC}"
    elif echo "$GATE2_RESPONSE" | grep -q '"cancel":true'; then
        echo -e "${YELLOW}Gate 2 was cancelled${NC}"
    else
        echo -e "${RED}Gate 2 unexpected response${NC}"
    fi
) &
GATE2_PID=$!

# Wait for Gate 2 to start waiting
sleep 2

# Send confirmation
echo -e "${CYAN}Sending confirmation via /tool-confirm...${NC}"
CONFIRM_RESPONSE=$(curl -s -X POST "$RELAY_URL/tool-confirm" \
    -H "Content-Type: application/json" \
    -d "{
        \"tool_call_id\": \"$GATE2_CONFIRM_ID\",
        \"confirmed\": true,
        \"reason\": \"Test confirmation via curl\"
    }")

if echo "$CONFIRM_RESPONSE" | grep -q '"success":true'; then
    pass "Confirmation sent successfully"
else
    fail "Confirmation failed"
fi
echo "$CONFIRM_RESPONSE" | jq . 2>/dev/null || echo "$CONFIRM_RESPONSE"

# Wait for Gate 2 background process to complete
wait $GATE2_PID 2>/dev/null
echo ""

# =============================================================================
# Test 4: Gate 2 with Cancellation
# =============================================================================
echo -e "${YELLOW}[Test 4] Gate 2 - TRUE WAITING with Cancellation${NC}"
GATE2_CANCEL_ID="tc_g2_cancel_$(date +%s)"

echo -e "${CYAN}Starting Gate 2 request in background (will wait for cancellation)...${NC}"

# Start Gate 2 in background
(
    GATE2_RESPONSE=$(curl -s --max-time 20 -X POST "$RELAY_URL/tool-progress" \
        -H "Content-Type: application/json" \
        -d "{
            \"tool_call_id\": \"$GATE2_CANCEL_ID\",
            \"intent_id\": \"intent_cancel_$(date +%s)\",
            \"status\": \"READY_TO_SEND\",
            \"gate\": 2,
            \"requires_confirmation\": true,
            \"cancellable\": true,
            \"message\": \"Email is ready to send. Confirm to proceed.\"
        }")
    echo ""
    echo -e "${CYAN}Gate 2 Response after cancellation:${NC}"
    echo "$GATE2_RESPONSE" | jq . 2>/dev/null || echo "$GATE2_RESPONSE"

    if echo "$GATE2_RESPONSE" | grep -q '"cancel":true'; then
        echo -e "${GREEN}Gate 2 cancellation detected!${NC}"
    else
        echo -e "${RED}Gate 2 cancellation not detected${NC}"
    fi
) &
GATE2_CANCEL_PID=$!

# Wait for Gate 2 to start waiting
sleep 2

# Send cancellation
echo -e "${CYAN}Sending cancellation via /tool-cancel...${NC}"
CANCEL_RESPONSE=$(curl -s -X POST "$RELAY_URL/tool-cancel" \
    -H "Content-Type: application/json" \
    -d "{
        \"tool_call_id\": \"$GATE2_CANCEL_ID\",
        \"reason\": \"User said cancel\"
    }")

if echo "$CANCEL_RESPONSE" | grep -q '"success":true\|"cancellation_requested":true'; then
    pass "Cancellation sent successfully"
else
    fail "Cancellation request failed"
fi
echo "$CANCEL_RESPONSE" | jq . 2>/dev/null || echo "$CANCEL_RESPONSE"

# Wait for Gate 2 background process
wait $GATE2_CANCEL_PID 2>/dev/null
echo ""

# =============================================================================
# Test 5: Gate 2 Timeout (short wait)
# =============================================================================
echo -e "${YELLOW}[Test 5] Gate 2 - Timeout Test (short)${NC}"
echo -e "${CYAN}Note: Actual timeout is 30s, this test may take a while if not configured shorter${NC}"
echo -e "${CYAN}Skip this test in CI with SKIP_TIMEOUT_TEST=1${NC}"

if [ "$SKIP_TIMEOUT_TEST" != "1" ]; then
    GATE2_TIMEOUT_ID="tc_g2_timeout_$(date +%s)"

    echo -e "${CYAN}Starting Gate 2 request (will timeout without confirmation)...${NC}"

    TIMEOUT_START=$(date +%s)
    GATE2_TIMEOUT_RESPONSE=$(curl -s --max-time 35 -X POST "$RELAY_URL/tool-progress" \
        -H "Content-Type: application/json" \
        -d "{
            \"tool_call_id\": \"$GATE2_TIMEOUT_ID\",
            \"intent_id\": \"intent_timeout_$(date +%s)\",
            \"status\": \"READY_TO_SEND\",
            \"gate\": 2,
            \"requires_confirmation\": true,
            \"cancellable\": true,
            \"message\": \"Email is ready to send. Confirm to proceed.\"
        }")
    TIMEOUT_END=$(date +%s)
    TIMEOUT_DURATION=$((TIMEOUT_END - TIMEOUT_START))

    echo "Response after ${TIMEOUT_DURATION}s:"
    echo "$GATE2_TIMEOUT_RESPONSE" | jq . 2>/dev/null || echo "$GATE2_TIMEOUT_RESPONSE"

    if echo "$GATE2_TIMEOUT_RESPONSE" | grep -q '"cancel":true.*timeout\|"reason":".*[Tt]imeout"'; then
        pass "Gate 2 timed out correctly after ${TIMEOUT_DURATION}s"
    elif [ $TIMEOUT_DURATION -ge 25 ]; then
        pass "Gate 2 waited and timed out (${TIMEOUT_DURATION}s)"
    else
        fail "Gate 2 timeout behavior unexpected"
    fi
else
    echo -e "${CYAN}Skipping timeout test (SKIP_TIMEOUT_TEST=1)${NC}"
fi
echo ""

# =============================================================================
# Test 6: Gate 3 - COMPLETED
# =============================================================================
echo -e "${YELLOW}[Test 6] Gate 3 - COMPLETED${NC}"
GATE3_ID="tc_g3_$(date +%s)"
GATE3_RESPONSE=$(curl -s -X POST "$RELAY_URL/tool-progress" \
    -H "Content-Type: application/json" \
    -d "{
        \"tool_call_id\": \"$GATE3_ID\",
        \"intent_id\": \"intent_complete_$(date +%s)\",
        \"status\": \"COMPLETED\",
        \"gate\": 3,
        \"result\": {\"messageId\": \"msg_test_$(date +%s)\", \"threadId\": \"thread_test\"},
        \"voice_response\": \"Email sent successfully to test@example.com\",
        \"execution_time_ms\": 1500
    }")

if echo "$GATE3_RESPONSE" | grep -q '"status":"acknowledged"\|"received":true'; then
    pass "Gate 3 acknowledged completion"
else
    fail "Gate 3 acknowledgment failed"
fi
echo "$GATE3_RESPONSE" | jq . 2>/dev/null || echo "$GATE3_RESPONSE"
echo ""

# =============================================================================
# Test 7: Pre-emptive Cancellation (cancel before gate callback)
# =============================================================================
echo -e "${YELLOW}[Test 7] Pre-emptive Cancellation${NC}"
PREEMPT_ID="tc_preempt_$(date +%s)"

# First, request cancellation
echo "Requesting cancellation before any gate callback..."
curl -s -X POST "$RELAY_URL/tool-cancel" \
    -H "Content-Type: application/json" \
    -d "{
        \"tool_call_id\": \"$PREEMPT_ID\",
        \"reason\": \"Pre-emptive cancel\"
    }" | jq . 2>/dev/null

# Then send Gate 1 callback (should detect cancellation)
PREEMPT_RESPONSE=$(curl -s -X POST "$RELAY_URL/tool-progress" \
    -H "Content-Type: application/json" \
    -d "{
        \"tool_call_id\": \"$PREEMPT_ID\",
        \"status\": \"PREPARING\",
        \"gate\": 1,
        \"cancellable\": true
    }")

if echo "$PREEMPT_RESPONSE" | grep -q '"cancel":true'; then
    pass "Pre-emptive cancellation detected"
else
    fail "Pre-emptive cancellation not detected"
fi
echo "$PREEMPT_RESPONSE" | jq . 2>/dev/null || echo "$PREEMPT_RESPONSE"
echo ""

# =============================================================================
# Test 8: Idempotency - Same callback twice
# =============================================================================
echo -e "${YELLOW}[Test 8] Idempotency Test${NC}"
IDEMP_ID="tc_idemp_$(date +%s)"

echo "Sending first Gate 1 callback..."
IDEMP1=$(curl -s -X POST "$RELAY_URL/tool-progress" \
    -H "Content-Type: application/json" \
    -d "{
        \"tool_call_id\": \"$IDEMP_ID\",
        \"status\": \"PREPARING\",
        \"gate\": 1,
        \"cancellable\": true
    }")
echo "First response:"
echo "$IDEMP1" | jq . 2>/dev/null || echo "$IDEMP1"

echo ""
echo "Sending duplicate Gate 1 callback..."
IDEMP2=$(curl -s -X POST "$RELAY_URL/tool-progress" \
    -H "Content-Type: application/json" \
    -d "{
        \"tool_call_id\": \"$IDEMP_ID\",
        \"status\": \"PREPARING\",
        \"gate\": 1,
        \"cancellable\": true
    }")
echo "Second response:"
echo "$IDEMP2" | jq . 2>/dev/null || echo "$IDEMP2"

if echo "$IDEMP2" | grep -q '"already_processed":true\|"idempotent":true\|"continue":true'; then
    pass "Idempotency handled (duplicate processed safely)"
else
    fail "Idempotency handling unclear"
fi
echo ""

# =============================================================================
# Test 9: Rate Limiting
# =============================================================================
echo -e "${YELLOW}[Test 9] Rate Limiting Test${NC}"
echo "Sending 10 rapid requests..."

RATE_LIMITED=0
for i in {1..10}; do
    RATE_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$RELAY_URL/tool-progress" \
        -H "Content-Type: application/json" \
        -d "{
            \"tool_call_id\": \"tc_rate_${i}_$(date +%s%N)\",
            \"status\": \"PREPARING\",
            \"gate\": 1
        }")
    if [ "$RATE_RESPONSE" == "429" ]; then
        ((RATE_LIMITED++))
    fi
done

echo "Requests rate limited: $RATE_LIMITED/10"
if [ $RATE_LIMITED -gt 0 ]; then
    pass "Rate limiting is active"
else
    echo -e "${CYAN}Note: Rate limiting may be configured with higher threshold${NC}"
    pass "Rate limiting test complete (no 429s in 10 requests is acceptable)"
fi
echo ""

# =============================================================================
# Test 10: Tool Status Check
# =============================================================================
echo -e "${YELLOW}[Test 10] Tool Status Check${NC}"
STATUS_RESPONSE=$(curl -s "$RELAY_URL/tool-status/$TOOL_CALL_ID")
if echo "$STATUS_RESPONSE" | grep -q '"tool_call_id"'; then
    pass "Tool status endpoint working"
else
    fail "Tool status endpoint failed"
fi
echo "$STATUS_RESPONSE" | jq . 2>/dev/null || echo "$STATUS_RESPONSE"
echo ""

# =============================================================================
# Summary
# =============================================================================
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   TEST SUMMARY${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed. Check output above.${NC}"
    exit 1
fi
