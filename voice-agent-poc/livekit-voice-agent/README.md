# LiveKit Voice Agent

Enterprise-grade voice assistant using LiveKit Cloud, Cartesia TTS, Groq LLM, and Deepgram STT.

## Architecture

```
Audio In → Silero VAD → Deepgram STT → Groq LLM → Cartesia TTS → Audio Out
                                          ↓
                                    n8n Webhooks
                                   (Email, Database)
```

## Target Latency

| Stage | Target | Notes |
|-------|--------|-------|
| VAD | <30ms | Silero local |
| STT | <200ms | Deepgram Nova-3 |
| LLM | <250ms | Groq TTFT |
| TTS | <100ms | Cartesia TTFA |
| **Total** | **<500ms** | End-to-end |

## Quick Start

### 1. Get API Keys

1. **LiveKit Cloud**: [cloud.livekit.io](https://cloud.livekit.io)
2. **Deepgram**: [console.deepgram.com](https://console.deepgram.com)
3. **Groq**: [console.groq.com](https://console.groq.com)
4. **Cartesia**: [play.cartesia.ai](https://play.cartesia.ai)

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run Agent

```bash
python -m src.agent start
```

## Deployment (Railway)

```bash
# Push to GitHub, Railway auto-deploys
railway link
railway up
```

## Tools Available

1. **send_email** - Send emails via Gmail (n8n webhook)
2. **query_database** - Search vector database (n8n webhook)

## Cost Estimate

~$0.012/min voice (65% cheaper than OpenAI Realtime)

See [ENTERPRISE_IMPLEMENTATION_GUIDE.md](../ENTERPRISE_IMPLEMENTATION_GUIDE.md) for full documentation.
