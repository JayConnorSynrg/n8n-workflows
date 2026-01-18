#!/bin/bash
# Deploy LiveKit Voice Agent to Railway
# Run this script from the livekit-voice-agent directory

set -e

echo "🚀 Deploying LiveKit Voice Agent to Railway..."

# Check if railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "❌ Railway CLI not installed. Install with: npm install -g @railway/cli"
    exit 1
fi

# Check if logged in
if ! railway whoami &> /dev/null; then
    echo "❌ Not logged into Railway. Run: railway login"
    exit 1
fi

# Link to project if not already linked
echo "📋 Checking Railway project link..."
if ! railway status &> /dev/null; then
    echo "Please link to your Railway project first:"
    echo "  railway link"
    exit 1
fi

# Set environment variables
echo "🔐 Setting environment variables..."
railway variables set \
    LIVEKIT_URL="wss://synrg-voice-agent-gqv10vbf.livekit.cloud" \
    LIVEKIT_API_KEY="API3DKs8E7CmRkE" \
    LIVEKIT_API_SECRET="W77hapOtBQNH1lU1s542LjS9usBffH5o30cTCVLyj1h" \
    DEEPGRAM_API_KEY="4197230172af958f472c56f1a59458bc50464b66" \
    DEEPGRAM_MODEL="nova-3" \
    GROQ_API_KEY="${GROQ_API_KEY}" \
    GROQ_MODEL="llama-3.1-8b-instant" \
    GROQ_TEMPERATURE="0.7" \
    GROQ_MAX_TOKENS="256" \
    CARTESIA_API_KEY="sk_car_DaqnaCDij1Ms4aruoVqxjZ" \
    CARTESIA_MODEL="sonic-3" \
    CARTESIA_VOICE="5ee9feff-1265-424a-9d7f-8e4d431a12c7" \
    N8N_WEBHOOK_BASE_URL="https://jayconnorexe.app.n8n.cloud/webhook" \
    AGENT_NAME="Voice Assistant" \
    LOG_LEVEL="INFO"

# Deploy
echo "🚂 Deploying to Railway..."
railway up --detach

echo "✅ Deployment started! Check status with: railway logs"
