# Railway Integration Plan — client-v2

**Date**: 2026-02-22
**Branch**: `feat/aio-tools-registry`
**Repo**: `JayConnorSynrg/synrg-voice-agent-client`
**Risk Level**: LOW — additive only, zero changes to existing services

---

## Executive Summary

This plan deploys `client-v2` as a **new, independent Railway service** alongside the existing `livekit-voice-agent`. No existing services are modified or restarted. The Python agent, PostgreSQL, and relay remain completely untouched. Rollback is instant (delete the new service).

---

## Pre-Flight Verification (Complete Before Any Action)

### 1. Interface Compatibility (CONFIRMED ✅)

Scout B confirmed 100% event compatibility:

| Event Type | Published by Agent | Handled by client-v2 |
|------------|-------------------|----------------------|
| `agent.state` | ✅ | ✅ |
| `transcript.user` | ✅ | ✅ |
| `transcript.assistant` | ✅ | ✅ |
| `tool.call` | ✅ | ✅ |
| `tool.executing` | ✅ | ✅ |
| `tool.completed` | ✅ | ✅ |
| `tool.error` | ✅ | ✅ |
| `tool_result` | ✅ | ✅ |
| `composio.searching` | ✅ | ✅ |
| `composio.executing` | ✅ | ✅ |
| `composio.completed` | ✅ | ✅ |
| `composio.error` | ✅ | ✅ |
| `error` | ✅ | ✅ |

**Dead code**: `agent.volume` — not published by agent, client-v2 does not depend on it.

### 2. Build Health (CONFIRMED ✅)

```
vite build → 2.40s, no errors, no warnings
Chunks: livekit (vendor), vendor (react/zustand), animation (framer-motion), main
sourcemap: false (no source exposure)
drop_console: true (no log leakage)
```

### 3. Environment Variables Required

**None required for build.** All connection params are URL-driven:

| Param | Source | Notes |
|-------|--------|-------|
| `livekit_url` | URL query string `?livekit_url=wss://...` | Injected by launcher workflow |
| `token` | URL query string `?token=<jwt>` | Injected by LiveKit token endpoint |
| `PORT` | Railway auto-provision | `process.env.PORT \|\| 3000` |

**No Railway env vars to configure.** Railway injects `PORT` automatically.

### 4. Current Railway Context

```
Project: VOICE AGENT - N8N
Environment: production
Service: livekit-voice-agent  ← currently linked (DO NOT TOUCH)
```

---

## Phase 1: Create Railway Service (Zero Downtime)

### Step 1.1 — Commit branch to remote

Ensure `feat/aio-tools-registry` is pushed:

```bash
cd /Users/jelalconnor/CODING/N8N/Workflows/voice-agent-poc/client-v2
git status          # confirm clean working tree
git push origin feat/aio-tools-registry
```

### Step 1.2 — Create new Railway service via Dashboard

> **Use Railway dashboard** for initial service creation (avoids accidentally modifying the linked `livekit-voice-agent` context).

1. Open **railway.app** → Project: `VOICE AGENT - N8N`
2. Click **`+ New Service`** → **`GitHub Repo`**
3. Select repo: `JayConnorSynrg/synrg-voice-agent-client`
4. Select branch: `feat/aio-tools-registry`
5. Railway auto-detects NIXPACKS (Node.js)

### Step 1.3 — Configure service settings (Dashboard)

| Setting | Value |
|---------|-------|
| Service Name | `voice-agent-client-v2` |
| Builder | NIXPACKS (auto-detected) |
| Build Command | `npm install && npm run build` |
| Start Command | `npm run start` |
| Environment | `production` |

**No environment variables to add** — `PORT` is provided automatically.

### Step 1.4 — First deploy

Railway triggers deploy automatically on service creation. Monitor:

```bash
# After linking new service context (separate terminal)
railway logs --service voice-agent-client-v2
```

Expected success output:
```
> vite build
✓ 2400ms built
Voice Agent client running on port XXXX
```

---

## Phase 2: Staging Validation (Do Not Route Traffic Yet)

Railway assigns a `.up.railway.app` URL to the new service. Test against the **live production Python agent** without affecting any active sessions.

### Step 2.1 — Smoke test (browser)

Open the Railway-assigned URL with production LiveKit parameters:

```
https://voice-agent-client-v2.up.railway.app/?livekit_url=<PROD_WSS>&token=<TEST_TOKEN>&mock=true
```

Verify:
- [ ] Page loads (HTTP 200)
- [ ] Orb renders (WebGL canvas)
- [ ] Mode badge shows "Mock Mode"
- [ ] `window.voiceAgentStatus` accessible in DevTools

### Step 2.2 — Mock mode demo test (browser)

```
https://voice-agent-client-v2.up.railway.app/?mock=true
```

Verify:
- [ ] Orb cycles: listening → thinking → speaking
- [ ] Tool call cards appear on left/right panels
- [ ] Cards show pending (breathing pulse), executing (sweep), completed (green)
- [ ] DemoRunner is **NOT visible** (production build, dev-gated)
- [ ] DevTestPanel is **NOT visible** (dev-gated)

### Step 2.3 — Live agent connection test

Use a **test LiveKit room** (not a live customer session):

1. Generate a test token via the launcher workflow
2. Open: `https://voice-agent-client-v2.up.railway.app/?livekit_url=<WSS>&token=<JWT>`
3. Verify:
   - [ ] Connects to LiveKit room (no WebSocket errors)
   - [ ] `agentConnected = true` after agent joins
   - [ ] Orb transitions state on speech
   - [ ] Tool call events render on side panels
   - [ ] `voiceAgentReady` event fires (check DevTools console: should be silent — drop_console active)
   - [ ] `window.voiceAgentReady === true` after full init

### Step 2.4 — Recall.ai integration test

If a test meeting is available:
- [ ] Bot joins call
- [ ] Client URL returned by launcher is the new service URL
- [ ] Audio flows through LiveKit to new client
- [ ] Tool calls from the Python agent render on card panels

**Gate**: Do not proceed to Phase 3 until ALL Phase 2 checks pass.

---

## Phase 3: Traffic Migration

Once validation passes, update the launcher workflow to point new sessions at the new client URL.

### Step 3.1 — Update Recall.ai launcher n8n workflow

Workflow: `kUcUSyPgz4Z9mYBt` (Launcher v4.2)

The launcher constructs the client URL passed to Recall.ai. Update the base URL from the old client endpoint to the new service URL:

```
OLD: https://<old-client>.up.railway.app/
NEW: https://voice-agent-client-v2.up.railway.app/
```

The query params (`livekit_url`, `token`) are appended dynamically — no other changes needed.

### Step 3.2 — Verify first live session

After launcher update, the next meeting invitation will use the new client. Monitor:

```bash
railway logs --service voice-agent-client-v2
```

Confirm:
- [ ] Request logs showing Recall.ai bot loading the client
- [ ] No 500 errors
- [ ] `voiceAgentReady` signal received by Recall.ai bot

### Step 3.3 — Monitor for 24 hours

Watch:
- Railway metrics for `voice-agent-client-v2` (memory, response time)
- n8n execution logs for launcher workflow (session creation success rate)
- `livekit-voice-agent` logs unchanged (agent unaffected)

---

## Rollback Procedure

Since this is a **new additive service**, rollback has zero risk:

### Instant rollback (< 2 minutes)

1. Revert the launcher workflow (`kUcUSyPgz4Z9mYBt`) to the old client URL
2. New sessions immediately use the old client
3. In-flight sessions on the new client complete normally (no interruption)
4. Optionally: pause or delete `voice-agent-client-v2` service in Railway dashboard

**No restarts, no downtime, no data loss.**

---

## What Is NOT Changed

| Component | Status | Notes |
|-----------|--------|-------|
| `livekit-voice-agent` | ✅ Untouched | Python agent, tools, Fireworks LLM — zero changes |
| `voice-agent-relay` | ✅ Untouched | WebSocket relay — zero changes |
| `Postgres` | ✅ Untouched | Database — zero changes |
| n8n workflows (11 active) | ✅ Untouched | Only launcher URL changes in Phase 3 |
| Railway env vars | ✅ Untouched | New service needs none |
| Recall.ai config | ✅ Untouched | Only the client URL in sessions changes |

---

## Branch → Merge Strategy

After production validation (Phase 3 stable for 24h+):

```bash
# Merge feat/aio-tools-registry → main
git checkout main
git merge feat/aio-tools-registry --no-ff -m "feat(client-v2): production-ready with tool registry, Playwright tests, Railway hardening"
git push origin main

# Update Railway service to track main
# Railway Dashboard → voice-agent-client-v2 → Settings → Branch: main
```

---

## Service Configuration Summary

```
Service: voice-agent-client-v2
Project: VOICE AGENT - N8N
Environment: production
Repo: JayConnorSynrg/synrg-voice-agent-client
Branch: feat/aio-tools-registry → main (post-validation)
Builder: NIXPACKS
Build: npm install && npm run build
Start: npm run start (node server.js)
Port: Railway-provided PORT
Env vars: none
```

---

## Risk Matrix

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Build fails on Railway | Low | Low | Tested clean locally (2.40s) |
| WebSocket fails in prod | Low | Medium | Test in Phase 2.3 before traffic switch |
| Recall.ai URL change breaks session | Low | Medium | Test one session in Phase 3.2 before going live |
| Python agent incompatibility | None | N/A | 13/13 events confirmed compatible |
| Rollback required | Low | Low | Revert launcher URL in < 2 min, zero downtime |

---

**Overall assessment**: This is the safest possible deployment path. The client is stateless (all state in LiveKit room + Zustand in-memory), URL-param driven, and completely independent from the Python agent. Adding a new service with an instant-revert rollback is the minimum viable risk approach.
