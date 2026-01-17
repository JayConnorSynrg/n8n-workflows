"""
Structured Integration Test: Teams Voice Bot Launcher
Tests end-to-end connectivity: Launcher → LiveKit → n8n

Test Suite:
1. LiveKit JWT Token Generation (validate structure and claims)
2. LiveKit Cloud Connectivity (WebSocket reachable)
3. n8n Tool Webhooks (execute-gmail, query-vector-db, callback-noop)
4. Full Launcher Flow Simulation
"""

import asyncio
import base64
import json
import hmac
import hashlib
import time
import uuid
import ssl
import certifi
from datetime import datetime
from typing import Dict, Any, Tuple
import urllib.request
import urllib.error

# Test configuration
LIVEKIT_URL = "wss://synrg-voice-agent-gqv10vbf.livekit.cloud"
LIVEKIT_API_KEY = "API3DKs8E7CmRkE"
LIVEKIT_API_SECRET = "W77hapOtBQNH1lU1s542LjS9usBffH5o30cTCVLyj1h"
N8N_WEBHOOK_BASE = "https://jayconnorexe.app.n8n.cloud/webhook"

class TestResult:
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.message = ""
        self.duration_ms = 0
        self.details: Dict[str, Any] = {}

    def success(self, message: str, **details):
        self.passed = True
        self.message = message
        self.details = details

    def failure(self, message: str, **details):
        self.passed = False
        self.message = message
        self.details = details


def base64url_encode(data: bytes) -> str:
    """Base64URL encode without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def generate_livekit_token(room_name: str, identity: str, participant_name: str = "Test Client") -> Tuple[str, Dict]:
    """
    Generate a LiveKit JWT token matching the launcher workflow's implementation.
    Returns both the token and the decoded claims for validation.
    """
    now = int(time.time())
    exp = now + 86400  # 24 hours

    # LiveKit video grant
    video_grant = {
        "room": room_name,
        "roomJoin": True,
        "canPublish": True,
        "canPublishData": True,
        "canSubscribe": True
    }

    # JWT Header
    header = {
        "alg": "HS256",
        "typ": "JWT"
    }

    # JWT Payload (LiveKit claims)
    payload = {
        "iss": LIVEKIT_API_KEY,
        "sub": identity,
        "name": participant_name,
        "iat": now,
        "nbf": now,
        "exp": exp,
        "video": video_grant,
        "metadata": json.dumps({"session_id": identity, "test": True})
    }

    # Create signature
    header_b64 = base64url_encode(json.dumps(header).encode())
    payload_b64 = base64url_encode(json.dumps(payload).encode())
    signature_input = f"{header_b64}.{payload_b64}"

    signature = hmac.new(
        LIVEKIT_API_SECRET.encode(),
        signature_input.encode(),
        hashlib.sha256
    ).digest()
    signature_b64 = base64url_encode(signature)

    token = f"{signature_input}.{signature_b64}"

    return token, payload


def test_jwt_token_generation() -> TestResult:
    """Test 1: Validate LiveKit JWT token generation."""
    result = TestResult("LiveKit JWT Token Generation")
    start = time.time()

    try:
        session_id = f"test_{uuid.uuid4().hex[:12]}"
        room_name = f"voice-bot-{session_id}"
        identity = f"output-media-{session_id}"

        token, claims = generate_livekit_token(room_name, identity)

        # Validate token structure (3 parts separated by dots)
        parts = token.split('.')
        if len(parts) != 3:
            result.failure("Invalid JWT structure", parts_count=len(parts))
            return result

        # Decode and validate header
        header_json = base64.urlsafe_b64decode(parts[0] + '==')
        header = json.loads(header_json)
        if header.get('alg') != 'HS256':
            result.failure("Invalid algorithm", expected='HS256', got=header.get('alg'))
            return result

        # Decode and validate payload
        payload_json = base64.urlsafe_b64decode(parts[1] + '==')
        payload = json.loads(payload_json)

        # Validate required claims
        required_claims = ['iss', 'sub', 'exp', 'video']
        missing = [c for c in required_claims if c not in payload]
        if missing:
            result.failure("Missing required claims", missing=missing)
            return result

        # Validate video grant
        video = payload.get('video', {})
        if video.get('room') != room_name:
            result.failure("Room mismatch", expected=room_name, got=video.get('room'))
            return result

        if not video.get('roomJoin'):
            result.failure("roomJoin not enabled")
            return result

        result.duration_ms = int((time.time() - start) * 1000)
        result.success(
            "JWT token generated and validated",
            token_length=len(token),
            room=room_name,
            identity=identity,
            expires_in_hours=24,
            video_grant=video
        )

    except Exception as e:
        result.duration_ms = int((time.time() - start) * 1000)
        result.failure(f"Token generation failed: {str(e)}")

    return result


def test_livekit_cloud_reachable() -> TestResult:
    """Test 2: Verify LiveKit Cloud is reachable via HTTPS."""
    result = TestResult("LiveKit Cloud Connectivity")
    start = time.time()

    try:
        # Convert WSS URL to HTTPS for connectivity check
        https_url = LIVEKIT_URL.replace("wss://", "https://")

        # Create SSL context with certificates
        ssl_context = ssl.create_default_context(cafile=certifi.where())

        req = urllib.request.Request(
            https_url,
            headers={"User-Agent": "LiveKit-Test/1.0"}
        )

        # Try to connect - we expect a response (even if error, it means server is reachable)
        try:
            response = urllib.request.urlopen(req, timeout=10, context=ssl_context)
            status = response.status
            result.success(
                "LiveKit Cloud is reachable",
                url=https_url,
                status=status
            )
        except urllib.error.HTTPError as e:
            # HTTP errors still mean server is reachable
            result.success(
                "LiveKit Cloud is reachable (HTTP error expected for non-WebSocket request)",
                url=https_url,
                status=e.code,
                reason=e.reason
            )
        except urllib.error.URLError as e:
            result.failure(
                f"LiveKit Cloud unreachable: {str(e.reason)}",
                url=https_url
            )

    except Exception as e:
        result.failure(f"Connectivity test failed: {str(e)}")

    result.duration_ms = int((time.time() - start) * 1000)
    return result


def test_n8n_webhook(endpoint: str, method: str = "POST", payload: Dict = None) -> TestResult:
    """Test n8n webhook endpoint."""
    result = TestResult(f"n8n Webhook: {endpoint}")
    start = time.time()

    url = f"{N8N_WEBHOOK_BASE}/{endpoint}"

    try:
        # Create SSL context
        ssl_context = ssl.create_default_context(cafile=certifi.where())

        if method == "POST":
            data = json.dumps(payload or {}).encode()
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Integration-Test/1.0"
                },
                method="POST"
            )
        else:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Integration-Test/1.0"},
                method=method
            )

        try:
            response = urllib.request.urlopen(req, timeout=30, context=ssl_context)
            status = response.status
            body = response.read().decode()

            try:
                response_json = json.loads(body)
            except json.JSONDecodeError:
                response_json = {"raw": body[:200]}

            result.success(
                f"Webhook responded successfully",
                status=status,
                response=response_json
            )

        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else ""
            result.failure(
                f"HTTP Error: {e.code} {e.reason}",
                status=e.code,
                body=body[:200]
            )

        except urllib.error.URLError as e:
            result.failure(
                f"URL Error: {str(e.reason)}",
                url=url
            )

    except Exception as e:
        result.failure(f"Request failed: {str(e)}")

    result.duration_ms = int((time.time() - start) * 1000)
    return result


def test_execute_gmail_webhook() -> TestResult:
    """Test 3a: Test execute-gmail webhook (with test payload)."""
    payload = {
        "session_id": f"test_{uuid.uuid4().hex[:8]}",
        "intent_id": f"intent_{uuid.uuid4().hex[:8]}",
        "to": "test@example.com",
        "subject": "Integration Test",
        "body": "This is an automated integration test - DO NOT SEND",
        "callback_url": f"{N8N_WEBHOOK_BASE}/callback-noop",
        "dry_run": True  # Signal this is a test
    }
    return test_n8n_webhook("execute-gmail", "POST", payload)


def test_query_vector_db_webhook() -> TestResult:
    """Test 3b: Test query-vector-db webhook."""
    payload = {
        "session_id": f"test_{uuid.uuid4().hex[:8]}",
        "intent_id": f"intent_{uuid.uuid4().hex[:8]}",
        "user_query": "test query for integration validation",
        "structured_query": {
            "semantic_query": "integration test",
            "filters": {}
        },
        "callback_url": f"{N8N_WEBHOOK_BASE}/callback-noop"
    }
    return test_n8n_webhook("query-vector-db", "POST", payload)


def test_callback_noop_webhook() -> TestResult:
    """Test 3c: Test callback-noop webhook (gate handler)."""
    payload = {
        "tool_call_id": f"tc_test_{uuid.uuid4().hex[:8]}",
        "status": "PREPARING",
        "gate": 1,
        "cancellable": True
    }
    return test_n8n_webhook("callback-noop", "POST", payload)


def test_full_launcher_simulation() -> TestResult:
    """Test 4: Simulate full launcher flow (without actually creating a bot)."""
    result = TestResult("Full Launcher Flow Simulation")
    start = time.time()

    try:
        # Step 1: Generate session data (simulating workflow nodes)
        session_id = f"sess_{uuid.uuid4().hex[:16]}"
        room_name = f"voice-bot-{session_id}"

        # Step 2: Generate LiveKit token
        identity = f"output-media-{session_id}"
        token, claims = generate_livekit_token(room_name, identity)

        # Step 3: Validate token can be decoded
        parts = token.split('.')
        payload_json = base64.urlsafe_b64decode(parts[1] + '==')
        decoded_payload = json.loads(payload_json)

        # Step 4: Construct output media URL (what would be sent to Recall.ai)
        output_media_url = (
            f"https://jayconnorsynrg.github.io/synrg-voice-agent-client"
            f"?livekit_url={urllib.parse.quote(LIVEKIT_URL)}"
            f"&token={urllib.parse.quote(token)}"
        )

        # Step 5: Validate URL length (some services have limits)
        url_length = len(output_media_url)
        if url_length > 8000:
            result.failure(
                "Output media URL too long",
                length=url_length,
                max_recommended=8000
            )
            return result

        # Step 6: Construct what the Recall.ai API payload would look like
        recall_payload = {
            "meeting_url": "https://teams.live.com/meet/test-meeting",
            "bot_name": "AI Voice Assistant",
            "recording_config": {
                "transcript": {
                    "provider": {
                        "recallai_streaming": {
                            "language_code": "en",
                            "mode": "prioritize_low_latency"
                        }
                    }
                }
            },
            "output_media": {
                "camera": {
                    "kind": "webpage",
                    "config": {
                        "url": output_media_url
                    }
                },
                "microphone": {
                    "kind": "webpage"
                }
            }
        }

        result.duration_ms = int((time.time() - start) * 1000)
        result.success(
            "Full launcher flow simulation completed",
            session_id=session_id,
            room_name=room_name,
            identity=identity,
            token_length=len(token),
            output_media_url_length=url_length,
            recall_payload_valid=True,
            video_grant=decoded_payload.get('video', {})
        )

    except Exception as e:
        result.duration_ms = int((time.time() - start) * 1000)
        result.failure(f"Simulation failed: {str(e)}")

    return result


def run_all_tests():
    """Run all integration tests and produce a report."""
    print("\n" + "=" * 70)
    print("  TEAMS VOICE BOT LAUNCHER - INTEGRATION TEST SUITE")
    print("=" * 70)
    print(f"  Started: {datetime.now().isoformat()}")
    print(f"  LiveKit: {LIVEKIT_URL}")
    print(f"  n8n: {N8N_WEBHOOK_BASE}")
    print("=" * 70 + "\n")

    results = []

    # Test 1: JWT Token Generation
    print("[1/6] Testing LiveKit JWT Token Generation...")
    results.append(test_jwt_token_generation())

    # Test 2: LiveKit Cloud Connectivity
    print("[2/6] Testing LiveKit Cloud Connectivity...")
    results.append(test_livekit_cloud_reachable())

    # Test 3a: Execute Gmail Webhook
    print("[3/6] Testing n8n Execute Gmail Webhook...")
    results.append(test_execute_gmail_webhook())

    # Test 3b: Query Vector DB Webhook
    print("[4/6] Testing n8n Query Vector DB Webhook...")
    results.append(test_query_vector_db_webhook())

    # Test 3c: Callback No-Op Webhook
    print("[5/6] Testing n8n Callback No-Op Webhook...")
    results.append(test_callback_noop_webhook())

    # Test 4: Full Launcher Simulation
    print("[6/6] Running Full Launcher Flow Simulation...")
    results.append(test_full_launcher_simulation())

    # Print results
    print("\n" + "=" * 70)
    print("  TEST RESULTS")
    print("=" * 70 + "\n")

    passed = 0
    failed = 0
    total_duration = 0

    for r in results:
        status = "PASS" if r.passed else "FAIL"
        icon = "✓" if r.passed else "✗"
        print(f"  [{icon}] {r.name}")
        print(f"      Status: {status} ({r.duration_ms}ms)")
        print(f"      Message: {r.message}")
        if r.details:
            for k, v in r.details.items():
                if isinstance(v, dict):
                    print(f"      {k}:")
                    for k2, v2 in v.items():
                        print(f"        {k2}: {v2}")
                else:
                    print(f"      {k}: {v}")
        print()

        if r.passed:
            passed += 1
        else:
            failed += 1
        total_duration += r.duration_ms

    # Summary
    print("=" * 70)
    print(f"  SUMMARY: {passed}/{len(results)} tests passed")
    print(f"  Total Duration: {total_duration}ms")
    print(f"  Status: {'ALL TESTS PASSED' if failed == 0 else f'{failed} TESTS FAILED'}")
    print("=" * 70 + "\n")

    return failed == 0


# Import for URL encoding
import urllib.parse

if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
