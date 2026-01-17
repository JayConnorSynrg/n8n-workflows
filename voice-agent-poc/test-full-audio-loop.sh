#!/bin/bash

# LiveKit credentials
LIVEKIT_API_KEY="API3DKs8E7CmRkE"
LIVEKIT_API_SECRET="W77hapOtBQNH1lU1s542LjS9usBffH5o30cTCVLyj1h"
LIVEKIT_URL="wss://synrg-voice-agent-gqv10vbf.livekit.cloud"
LIVEKIT_HTTP_URL="https://synrg-voice-agent-gqv10vbf.livekit.cloud"

# Generate room name
ROOM_NAME="audio-test-$(date +%s)"
echo "=== Full Audio Loop Test ==="
echo "Room: $ROOM_NAME"
echo ""

# Generate admin JWT token
NOW=$(date +%s)
EXP=$((NOW + 3600))  # 1 hour expiry

# JWT Header
HEADER=$(echo -n '{"alg":"HS256","typ":"JWT"}' | base64 | tr -d '=' | tr '+/' '-_' | tr -d '\n')

# Admin payload for room creation/dispatch
ADMIN_PAYLOAD=$(echo -n "{\"iss\":\"$LIVEKIT_API_KEY\",\"sub\":\"test-admin\",\"iat\":$NOW,\"nbf\":$NOW,\"exp\":$EXP,\"video\":{\"roomCreate\":true,\"roomList\":true,\"roomAdmin\":true,\"room\":\"$ROOM_NAME\"}}" | base64 | tr -d '=' | tr '+/' '-_' | tr -d '\n')
ADMIN_SIG=$(echo -n "${HEADER}.${ADMIN_PAYLOAD}" | openssl dgst -sha256 -hmac "$LIVEKIT_API_SECRET" -binary | base64 | tr -d '=' | tr '+/' '-_' | tr -d '\n')
ADMIN_TOKEN="${HEADER}.${ADMIN_PAYLOAD}.${ADMIN_SIG}"

# Client payload for room joining
CLIENT_PAYLOAD=$(echo -n "{\"iss\":\"$LIVEKIT_API_KEY\",\"sub\":\"test-user\",\"iat\":$NOW,\"nbf\":$NOW,\"exp\":$EXP,\"name\":\"Test User\",\"video\":{\"roomJoin\":true,\"room\":\"$ROOM_NAME\",\"canPublish\":true,\"canSubscribe\":true,\"canPublishData\":true}}" | base64 | tr -d '=' | tr '+/' '-_' | tr -d '\n')
CLIENT_SIG=$(echo -n "${HEADER}.${CLIENT_PAYLOAD}" | openssl dgst -sha256 -hmac "$LIVEKIT_API_SECRET" -binary | base64 | tr -d '=' | tr '+/' '-_' | tr -d '\n')
CLIENT_TOKEN="${HEADER}.${CLIENT_PAYLOAD}.${CLIENT_SIG}"

echo "Step 1: Creating LiveKit Room..."
ROOM_RESPONSE=$(curl -s -X POST "$LIVEKIT_HTTP_URL/twirp/livekit.RoomService/CreateRoom" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"$ROOM_NAME\",\"empty_timeout\":300,\"max_participants\":10}")
echo "Room created: $(echo $ROOM_RESPONSE | jq -r '.name // .error // "error"')"

echo ""
echo "Step 2: Dispatching Agent..."
DISPATCH_RESPONSE=$(curl -s -X POST "$LIVEKIT_HTTP_URL/twirp/livekit.AgentDispatchService/CreateDispatch" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"agent_name\":\"synrg-voice-agent\",\"room\":\"$ROOM_NAME\"}")
echo "Dispatch ID: $(echo $DISPATCH_RESPONSE | jq -r '.id // .error // "error"')"

echo ""
echo "Step 3: Waiting for agent to connect (8 seconds)..."
sleep 8

echo ""
echo "Step 4: Checking room participants..."
PARTICIPANTS=$(curl -s -X POST "$LIVEKIT_HTTP_URL/twirp/livekit.RoomService/ListParticipants" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"room\":\"$ROOM_NAME\"}")
echo "$PARTICIPANTS" | jq '.participants[] | {identity, kind, state, tracks: (.tracks | length)}'

echo ""
echo "=== Client Connection Info ==="
echo ""
echo "To test audio in browser, open the client with these parameters:"
echo ""
echo "URL: http://localhost:5173?livekit_url=${LIVEKIT_URL}&token=${CLIENT_TOKEN}"
echo ""
echo "Or use the full connection string:"
echo ""
echo "LiveKit URL: $LIVEKIT_URL"
echo "Room: $ROOM_NAME"
echo "Token: $CLIENT_TOKEN"
echo ""
echo "=== Test Complete ==="
