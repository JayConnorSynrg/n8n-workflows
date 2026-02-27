# Voice Agent Relay Server - Deployment Guide

## Why Not Vercel?

This relay server maintains **persistent WebSocket connections** for real-time voice conversations. Vercel's serverless architecture:
- Terminates functions after 10-60 seconds
- Cannot maintain long-running WebSocket connections
- Is stateless (cannot track sessions)

## Recommended: Railway

Railway provides:
- Full WebSocket support with persistent connections
- Native PostgreSQL database
- Automatic SSL/HTTPS
- Zero-downtime deployments
- Pay-as-you-go pricing (~$5-10/month for this app)

### Quick Deploy

#### Prerequisites
- [Railway account](https://railway.app)
- Railway CLI: `npm install -g @railway/cli`

#### Steps

```bash
# Navigate to relay server directory
cd voice-agent-poc/relay-server

# Login to Railway (opens browser for OAuth)
railway login

# Initialize new Railway project
railway init
# Select: Create new project
# Name: voice-agent-relay

# Add PostgreSQL database
railway add
# Select: Database → PostgreSQL

# Set required environment variables
railway variables set OPENAI_API_KEY="sk-your-openai-api-key"
railway variables set N8N_TOOLS_WEBHOOK="https://jayconnorexe.app.n8n.cloud/webhook/voice-tools"
railway variables set LOG_LEVEL="INFO"
railway variables set PORT="3000"
railway variables set HEALTH_PORT="3001"

# Optional: Recall.ai integration
railway variables set RECALL_API_KEY="your-recall-api-key"
railway variables set RECALL_BOT_ID="your-default-bot-id"

# Deploy
railway up

# Get your public URL
railway domain
# This returns something like: voice-agent-relay-production.up.railway.app
```

#### After Deployment

1. **Run database migrations**:
   ```bash
   # Connect to Railway PostgreSQL
   railway connect postgres

   # Run schema (copy-paste from database/schema.sql)
   ```

2. **Update n8n webhook** to point to your Railway URL

3. **Update client configuration** to use Railway WebSocket URL:
   ```javascript
   const WS_URL = 'wss://voice-agent-relay-production.up.railway.app';
   ```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | ✅ Yes | OpenAI API key for Realtime API |
| `DATABASE_URL` | ✅ Auto | Injected by Railway PostgreSQL |
| `N8N_TOOLS_WEBHOOK` | ✅ Yes | n8n webhook for tool execution |
| `PORT` | No | WebSocket port (default: 3000) |
| `HEALTH_PORT` | No | Health check port (default: 3001) |
| `LOG_LEVEL` | No | DEBUG, INFO, WARN, ERROR |
| `RECALL_API_KEY` | No | For meeting audio injection |
| `RECALL_BOT_ID` | No | Default Recall.ai bot ID |

### Health Check

After deployment, verify:

```bash
# Health endpoint
curl https://your-app.up.railway.app/health

# Expected response:
# {"status":"healthy","uptime":123,"connections":0}
```

### Monitoring

Railway provides:
- Real-time logs: `railway logs`
- Metrics dashboard in Railway UI
- Automatic restart on crash

## Alternative Platforms

| Platform | WebSocket | PostgreSQL | Command |
|----------|-----------|------------|---------|
| Railway | ✅ | ✅ Native | `railway up` |
| Render | ✅ | ✅ | `render deploy` |
| Fly.io | ✅ | ✅ | `fly launch` |
| DigitalOcean | ✅ | ✅ | App Platform UI |

## Troubleshooting

### "CRITICAL: DATABASE_URL is required"
Railway auto-injects `DATABASE_URL` when PostgreSQL is added. Run:
```bash
railway add  # Select PostgreSQL
railway up   # Redeploy
```

### WebSocket connection fails
Ensure your client uses `wss://` (not `ws://`) for Railway's automatic SSL.

### Logs show connection errors
```bash
railway logs --tail 100
```

Check OpenAI API key is valid and has Realtime API access.
