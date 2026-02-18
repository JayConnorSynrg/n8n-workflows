#!/bin/bash
# Deploy LiveKit Voice Agent to Railway
# Run this script from the livekit-voice-agent directory
#
# PREREQUISITES:
#   1. Railway CLI installed: npm install -g @railway/cli
#   2. Logged in: railway login
#   3. Linked to project: railway link
#   4. .env file populated with real credentials (copy from .env.example)

set -e

echo "Deploying LiveKit Voice Agent to Railway..."

# Check if railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "Railway CLI not installed. Install with: npm install -g @railway/cli"
    exit 1
fi

# Check if logged in
if ! railway whoami &> /dev/null; then
    echo "Not logged into Railway. Run: railway login"
    exit 1
fi

# Check if linked to project
echo "Checking Railway project link..."
if ! railway status &> /dev/null; then
    echo "Please link to your Railway project first:"
    echo "  railway link"
    exit 1
fi

# Load .env file if it exists
if [ -f .env ]; then
    echo "Loading environment variables from .env..."
    set -a
    source .env
    set +a
else
    echo "WARNING: No .env file found. Railway env vars must already be set."
fi

# Set environment variables from .env (only if values are present)
echo "Setting environment variables on Railway..."
railway variables set \
    LIVEKIT_URL="${LIVEKIT_URL}" \
    LIVEKIT_API_KEY="${LIVEKIT_API_KEY}" \
    LIVEKIT_API_SECRET="${LIVEKIT_API_SECRET}" \
    DEEPGRAM_API_KEY="${DEEPGRAM_API_KEY}" \
    DEEPGRAM_MODEL="${DEEPGRAM_MODEL:-nova-3}" \
    CEREBRAS_API_KEY="${CEREBRAS_API_KEY}" \
    CEREBRAS_MODEL="${CEREBRAS_MODEL:-zai-glm-4.7}" \
    CEREBRAS_TEMPERATURE="${CEREBRAS_TEMPERATURE:-0.7}" \
    CEREBRAS_MAX_TOKENS="${CEREBRAS_MAX_TOKENS:-150}" \
    CARTESIA_API_KEY="${CARTESIA_API_KEY}" \
    CARTESIA_MODEL="${CARTESIA_MODEL:-sonic-3}" \
    CARTESIA_VOICE="${CARTESIA_VOICE}" \
    N8N_WEBHOOK_BASE_URL="${N8N_WEBHOOK_BASE_URL}" \
    MCP_SERVER_URL="${MCP_SERVER_URL:-}" \
    AGENT_NAME="${AGENT_NAME:-Voice Assistant}" \
    LOG_LEVEL="${LOG_LEVEL:-INFO}"

# Deploy
echo "Deploying to Railway..."
railway up --detach

echo "Deployment started! Check status with: railway logs"
