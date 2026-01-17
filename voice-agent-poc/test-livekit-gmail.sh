#!/bin/bash

# LiveKit credentials from n8n workflow
LIVEKIT_API_KEY="API3DKs8E7CmRkE"
LIVEKIT_API_SECRET="W77hapOtBQNH1lU1s542LjS9usBffH5o30cTCVLyj1h"
LIVEKIT_URL="wss://synrg-voice-agent-gqv10vbf.livekit.cloud"
LIVEKIT_HTTP_URL="https://synrg-voice-agent-gqv10vbf.livekit.cloud"

# Generate room name
ROOM_NAME="test-room-$(date +%s)"
echo "Room name: $ROOM_NAME"

# Generate admin JWT token
NOW=$(date +%s)
EXP=$((NOW + 300))

# JWT Header
HEADER=$(echo -n '{"alg":"HS256","typ":"JWT"}' | base64 | tr -d '=' | tr '+/' '-_' | tr -d '\n')

# JWT Payload with admin grants
PAYLOAD=$(echo -n "{\"iss\":\"$LIVEKIT_API_KEY\",\"sub\":\"test-admin\",\"iat\":$NOW,\"nbf\":$NOW,\"exp\":$EXP,\"video\":{\"roomCreate\":true,\"roomList\":true,\"roomAdmin\":true,\"room\":\"$ROOM_NAME\"}}" | base64 | tr -d '=' | tr '+/' '-_' | tr -d '\n')

# Create signature
SIGNATURE=$(echo -n "${HEADER}.${PAYLOAD}" | openssl dgst -sha256 -hmac "$LIVEKIT_API_SECRET" -binary | base64 | tr -d '=' | tr '+/' '-_' | tr -d '\n')

ADMIN_TOKEN="${HEADER}.${PAYLOAD}.${SIGNATURE}"
echo "Admin token generated"

# Step 1: Create LiveKit Room
echo ""
echo "=== Step 1: Creating LiveKit Room ==="
ROOM_RESPONSE=$(curl -s -X POST "$LIVEKIT_HTTP_URL/twirp/livekit.RoomService/CreateRoom" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"$ROOM_NAME\",\"empty_timeout\":300,\"max_participants\":10}")

echo "Room response: $ROOM_RESPONSE"

# Step 2: Dispatch Agent to Room
echo ""
echo "=== Step 2: Dispatching Agent to Room ==="
DISPATCH_RESPONSE=$(curl -s -X POST "$LIVEKIT_HTTP_URL/twirp/livekit.AgentDispatchService/CreateDispatch" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"agent_name\":\"synrg-voice-agent\",\"room\":\"$ROOM_NAME\"}")

echo "Dispatch response: $DISPATCH_RESPONSE"

# Step 3: Wait for agent to connect
echo ""
echo "=== Step 3: Waiting for agent to connect (5 seconds) ==="
sleep 5

# Step 4: List participants to verify agent joined
echo ""
echo "=== Step 4: Checking room participants ==="
PARTICIPANTS_RESPONSE=$(curl -s -X POST "$LIVEKIT_HTTP_URL/twirp/livekit.RoomService/ListParticipants" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"room\":\"$ROOM_NAME\"}")

echo "Participants: $PARTICIPANTS_RESPONSE"

echo ""
echo "=== Test Complete ==="
echo "Room: $ROOM_NAME"
