# Key Rotation: Step-by-Step Execution Guide

**Total Keys:** 12 credentials to rotate
**Estimated Time:** 2-3 hours (with verification)
**Risk Level:** HIGH - Do during low-traffic period

---

## Pre-Rotation Checklist

- [ ] Notify team of planned rotation window
- [ ] Ensure access to all vendor dashboards (log in to verify)
- [ ] Have secrets manager ready (environment variables / Railway)
- [ ] Keep old credentials documented until rotation is verified

---

## Execution Order (Dependency-Safe)

**Phase 1: Infrastructure First** (do these first - others depend on them)
1. Railway Token
2. PostgreSQL Password
3. Supabase Connection

**Phase 2: Core Services** (voice agent dependencies)
4. LiveKit API Key + Secret
5. Deepgram API Key
6. Cartesia API Key
7. Groq API Key

**Phase 3: External Integrations**
8. Recall.ai API Key
9. OpenAI API Key

**Phase 4: OAuth Credentials** (do last - requires re-authorization)
10. Google OAuth Client
11. Gmail API (depends on #10)
12. n8n JWT Secret (do last - invalidates all sessions)

---

## Step-by-Step Instructions

### 1. Railway Deployment Token

**Dashboard:** https://railway.app/account/tokens

```bash
# Step 1: Log into Railway dashboard
# Step 2: Go to Account Settings → Tokens
# Step 3: Create new token, name it "production-deploy-YYYYMMDD"
# Step 4: Copy the token

# Step 5: Update Railway environment
railway variables set RAILWAY_TOKEN="new-token-here"

# Step 6: Test deployment
railway up --detach

# Step 7: If successful, delete old token in dashboard
# Step 8: Verify old token fails (optional test)
```

**Evidence:** Screenshot of new token created + old token deleted

---

### 2. PostgreSQL Password

**Dashboard:** Supabase → Settings → Database

```bash
# Step 1: Generate new password
openssl rand -base64 24

# Step 2: In Supabase dashboard, go to Settings → Database → Reset password
# Step 3: Update your .env file locally
PGPASSWORD="new-password-here"

# Step 4: Test connection
source .env && psql "postgresql://$PGUSER:$PGPASSWORD@$PGHOST:5432/$PGDATABASE?sslmode=require" -c "SELECT 1;"

# Step 5: Update Railway environment variables
railway variables set PGPASSWORD="new-password-here"

# Step 6: Restart services
railway up --detach
```

**Evidence:** Screenshot of password reset + successful connection test

---

### 3. Supabase Connection String

**Dashboard:** https://supabase.com/dashboard → Project Settings → Database

```bash
# Same as #2 - the connection string uses the same password
# After resetting password, copy the new connection string

# Update Railway:
railway variables set DATABASE_URL="postgresql://postgres:NEW-PASSWORD@db.xxx.supabase.co:5432/postgres"
```

---

### 4. LiveKit API Key + Secret

**Dashboard:** https://cloud.livekit.io

```bash
# Step 1: Log into LiveKit Cloud dashboard
# Step 2: Go to Project Settings → Keys
# Step 3: Create new API key pair
# Step 4: Copy both LIVEKIT_API_KEY and LIVEKIT_API_SECRET

# Step 5: Update Railway environment
railway variables set LIVEKIT_API_KEY="new-key-here"
railway variables set LIVEKIT_API_SECRET="new-secret-here"

# Step 6: Restart voice agent
railway up --detach

# Step 7: Test by joining a room
# Go to your LiveKit dashboard → Rooms → Create test room

# Step 8: Delete old API key from LiveKit dashboard
```

**Evidence:** Screenshot of new key + test room creation

---

### 5. Deepgram API Key

**Dashboard:** https://console.deepgram.com

```bash
# Step 1: Log into Deepgram console
# Step 2: Go to API Keys
# Step 3: Create new key with same permissions as old key
# Step 4: Copy the key (shown only once!)

# Step 5: Update Railway environment
railway variables set DEEPGRAM_API_KEY="new-key-here"

# Step 6: Restart voice agent
railway up --detach

# Step 7: Test transcription (speak into voice agent)

# Step 8: Delete old API key from Deepgram console
```

**Evidence:** Screenshot of new key + successful transcription log

---

### 6. Cartesia API Key

**Dashboard:** https://play.cartesia.ai/console

```bash
# Step 1: Log into Cartesia dashboard
# Step 2: Go to API Keys
# Step 3: Create new API key
# Step 4: Copy the key

# Step 5: Update Railway environment
railway variables set CARTESIA_API_KEY="new-key-here"

# Step 6: Restart voice agent
railway up --detach

# Step 7: Test TTS (trigger voice response)

# Step 8: Delete old API key from Cartesia dashboard
```

**Evidence:** Screenshot of new key + audio playback test

---

### 7. Groq API Key

**Dashboard:** https://console.groq.com/keys

```bash
# Step 1: Log into Groq console
# Step 2: Go to API Keys
# Step 3: Create new API key
# Step 4: Copy the key

# Step 5: Update Railway environment
railway variables set GROQ_API_KEY="new-key-here"

# Step 6: Restart voice agent
railway up --detach

# Step 7: Test LLM response (ask voice agent a question)

# Step 8: Delete old API key from Groq console
```

**Evidence:** Screenshot of new key + successful LLM response

---

### 8. Recall.ai API Key

**Dashboard:** https://app.recall.ai

```bash
# Step 1: Log into Recall.ai dashboard
# Step 2: Go to Settings → API Keys
# Step 3: Create new API key
# Step 4: Copy the key

# Step 5: Update Railway environment
railway variables set RECALL_API_KEY="new-key-here"

# Step 6: Restart voice agent
railway up --detach

# Step 7: Test bot creation (if applicable)

# Step 8: Delete old API key from Recall.ai dashboard
```

**Evidence:** Screenshot of new key

---

### 9. OpenAI API Key

**Dashboard:** https://platform.openai.com/api-keys

```bash
# Step 1: Log into OpenAI platform
# Step 2: Go to API Keys
# Step 3: Create new secret key, name it "n8n-production-YYYYMMDD"
# Step 4: Copy the key (shown only once!)

# Step 5: Update n8n credential
# Go to n8n → Settings → Credentials → OpenAi account (ID: 6BIzzQu5jAD5jKlH)
# Click Edit → Paste new API key → Save

# Step 6: Test in n8n
# Run a workflow that uses OpenAI node

# Step 7: Delete old API key from OpenAI dashboard
```

**Evidence:** Screenshot of new key + n8n workflow execution success

---

### 10. Google OAuth Client

**Dashboard:** https://console.cloud.google.com/apis/credentials

```bash
# Step 1: Log into Google Cloud Console
# Step 2: Go to APIs & Services → Credentials
# Step 3: Create new OAuth 2.0 Client ID (Web application)
# Step 4: Add authorized redirect URIs:
#         - https://jayconnorexe.app.n8n.cloud/rest/oauth2-credential/callback
# Step 5: Copy Client ID and Client Secret

# Step 6: Update n8n Google credentials (ALL of them):
#         - Google Sheets account (fzaSSwZ4tI357WUU)
#         - Google Docs account (iNIP35ChYNUUqOCh)
#         - Google Drive account (ylMLH2SMUpGQpUUr)
#         - Gmail account 2 (kHDxu9JVLxm6iyMo)

# For EACH credential:
# n8n → Settings → Credentials → [credential name]
# Click Edit → Update Client ID + Secret → Re-authorize

# Step 7: Test each integration
# Run workflows using Google nodes

# Step 8: Delete old OAuth Client ID from GCP Console
```

**Evidence:** Screenshot of new OAuth client + re-authorization success for each

---

### 11. Gmail API Token

**Dashboard:** Same as #10 (uses Google OAuth)

```bash
# Step 1: After updating OAuth Client (#10), the Gmail token needs refresh

# Step 2: In n8n, go to:
# Settings → Credentials → Gmail account 2 (kHDxu9JVLxm6iyMo)

# Step 3: Click "Connect" to re-authorize
# Step 4: Complete OAuth flow in popup
# Step 5: Save credential

# Step 6: Test by running email workflow
```

**Evidence:** Screenshot of successful re-authorization + test email sent

---

### 12. n8n JWT Secret

**Dashboard:** n8n environment variables

```bash
# ⚠️ WARNING: This invalidates ALL user sessions
# Do this LAST and notify team first

# Step 1: Generate new JWT secret
openssl rand -base64 32

# Step 2: If using n8n Cloud, contact support
# If self-hosted, update environment variable:
N8N_JWT_SECRET="new-secret-here"

# Step 3: Restart n8n service

# Step 4: All users will need to log in again
```

**Evidence:** Screenshot of service restart + successful re-login

---

## Post-Rotation Verification

### Quick Health Check

```bash
# Test voice agent
railway logs --tail 50  # Check for errors

# Test database
source .env && psql "postgresql://$PGUSER:$PGPASSWORD@$PGHOST:5432/$PGDATABASE?sslmode=require" -c "SELECT COUNT(*) FROM session_context;"

# Test n8n
# Run each workflow type manually and check execution history
```

### Verify Old Keys Are Dead

For each service, attempt to use the old key and confirm it fails with 401/403.

---

## Rotation Summary Template

Copy this and fill in as you complete each rotation:

```markdown
| # | Service | Old Key (last 4) | New Key (last 4) | Rotated | Tested | Old Revoked |
|---|---------|------------------|------------------|---------|--------|-------------|
| 1 | Railway | ____ | ____ | [ ] | [ ] | [ ] |
| 2 | PostgreSQL | ____ | ____ | [ ] | [ ] | [ ] |
| 3 | Supabase | ____ | ____ | [ ] | [ ] | [ ] |
| 4 | LiveKit | ____ | ____ | [ ] | [ ] | [ ] |
| 5 | Deepgram | ____ | ____ | [ ] | [ ] | [ ] |
| 6 | Cartesia | ____ | ____ | [ ] | [ ] | [ ] |
| 7 | Groq | ____ | ____ | [ ] | [ ] | [ ] |
| 8 | Recall.ai | ____ | ____ | [ ] | [ ] | [ ] |
| 9 | OpenAI | ____ | ____ | [ ] | [ ] | [ ] |
| 10 | Google OAuth | ____ | ____ | [ ] | [ ] | [ ] |
| 11 | Gmail API | ____ | ____ | [ ] | [ ] | [ ] |
| 12 | n8n JWT | ____ | ____ | [ ] | [ ] | [ ] |

Rotation Date: ____________
Rotated By: ____________
```

---

## Emergency Rollback

If something breaks:

1. **Don't panic** - you have 5-10 minutes before rate limits kick in
2. **Check logs** - `railway logs --tail 100`
3. **Re-add old key temporarily** - Most services allow multiple active keys
4. **Debug** - Fix the issue with new key
5. **Remove old key again** once fixed

---

## Schedule Next Rotation

Set calendar reminder for **90 days from today**:
- API keys: Rotate every 90 days
- OAuth tokens: Rotate every 6 months
- Database passwords: Rotate every 90 days
- JWT secrets: Rotate annually (or after team changes)

---

**Document Version:** 1.0
**Created:** January 20, 2026
