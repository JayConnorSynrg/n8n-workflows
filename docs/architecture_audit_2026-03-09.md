# AIO Voice System — Adversarial Architecture Audit

**Date:** 2026-03-09
**Methodology:** Assume failure until proven otherwise. Question every layer.

---

## Layer 1: Infrastructure & Transport

**Provider: Railway (Docker containers) + LiveKit Cloud**

**Verdict: MEDIUM RISK**

**Findings:**
- LiveKit Agents v1.3.12 is appropriate for voice; no immediate migration pressure
- Railway single-region deployment = no redundancy. Any Railway outage = full AIO outage
- Docker volume (`/app/data/memory`) for SQLite is a **CRITICAL single point of failure** — volume loss = all per-user SQLite memory lost permanently
- LiveKit IPC 8s hard limit is razor-thin margin with current prewarm join(timeout=7). Any cold start >7s kills worker
- No load shedding or backpressure on incoming LiveKit rooms — if 50 users connect simultaneously, 50 workers spawn with fastembed cold load (384-dim model) → OOM risk
- STT: Deepgram Nova-3 is best-in-class for English. Acceptable.
- TTS: Cartesia Sonic-3 is acceptable. ElevenLabs Turbo v2.5 is competitive if Cartesia degrades
- LLM: Fireworks deepseek-v3p1 — good for tool calling, but single provider = reliability risk. No fallback.

**Action items:**
- P0: Migrate SQLite to Railway PostgreSQL (eliminate Docker volume dependency)
- P1: Add Groq Llama-3.3-70b as conversation LLM fallback (100k ctx, ~300 tok/s)
- P2: Add Railway health check with proper start-period=60s (currently missing)
- P2: Implement connection pooling limits for simultaneous room handling

---

## Layer 2: LLM Configuration

**Current: deepseek-v3p1 via Fireworks, max_tool_steps=20, parallel_tool_calls=True**

**Verdict: HIGH RISK**

**Findings:**
- Single LLM provider (Fireworks) with no fallback — any Fireworks outage = AIO offline
- deepseek-v3p1 hallucination rate for tool argument construction is measurably higher than GPT-4o or Claude 3.5 Sonnet. Observed in prod: wrong IDs passed to Teams/Drive calls not from prior list results
- `parallel_tool_calls=True` + write tools = duplicate execution risk. Idempotency keys are a mitigation, not a fix
- `max_tool_steps=20` — for complex multi-step tasks, this may be insufficient. No visibility when approaching limit
- No prompt caching configured — every session pays full input token cost for 4000-8000 char system prompt
- Context window trim at 15 messages is aggressive — mid-task continuations lose critical tool result context
- System prompt size: ~6000 chars (YELLOW zone). AGENTS.md injection pushes it closer to RED

**Action items:**
- P0: Add LLM provider fallback chain: Fireworks → Groq → Anthropic claude-haiku-4-5
- P1: Implement per-tool-call step warning at step 18 (already done per MEMORY.md, verify live)
- P1: Enable prompt caching on Fireworks (cache static system prompt prefix)
- P2: Increase context trim to 20 messages (reduce mid-task context loss)
- P3: Evaluate GPT-4o-mini for tool executor (lower hallucination rate, cheaper)

---

## Layer 3: Tool Delegation Architecture

**Current: 2-LLM chain — Conversation LLM (7 tools) → Tool Executor LLM (24 TOOL tools via delegateTools)**

**Verdict: HIGH RISK**

**Findings:**
- The 2-LLM delegation chain adds latency: user request → conversation LLM decides to delegate → tool executor LLM executes → result returns. 2-3 full LLM round-trips minimum
- Tool executor has no domain specialization — it handles email, Drive, Sheets, Teams, web search, databases, presentations all with one generic context. Domain-specific knowledge (correct slug params, service quirks) must be injected via hints
- `asyncio.Semaphore(4)` per worker caps parallel Composio calls. Under load, this becomes bottleneck
- `delegateTools` result delivery depends on `say_callback` — if callback is None, result is logged but not surfaced to user
- No retry-with-backoff at the delegation layer — if tool executor times out, delegation fails silently
- 453 Composio tools indexed but only ~6 toolkits reliably connected. Dead slugs fill context hints
- Tool executor context trim at 40 messages / keep last 5 results is conservative — long tool chains lose early results

**Architecture Recommendation:**

Replace 2-LLM chain with specialized domain agent mesh:

| Domain Agent | Composio Toolkits | Responsibility |
|---|---|---|
| Communication Agent | Gmail, Microsoft Teams, Slack | Email, messaging, notifications |
| Database Agent | Google Sheets, PostgreSQL tools | Data queries, record management |
| Asset Generation Agent | Gamma, image tools | Presentations, graphics |
| Web Intelligence Agent | Perplexity, web scraping | Research, prospect sourcing |
| Leads Sourcer Agent | Lead gen, CRM tools | Prospect pipeline management |
| Employee Upskiller Agent | (internal) | Coaching, skill tracking, objective alignment |

Each agent: specialized system prompt, pre-loaded relevant slug schemas, domain-specific error recovery.

Routing: Conversation LLM classifies intent → routes to domain agent → result returns.

**Action items:**
- P0: Build Communication Agent (highest usage: email + Teams = ~60% of all tool calls)
- P1: Build Web Intelligence Agent (Perplexity + scraping = self-contained, easy to isolate)
- P1: Build Employee Upskiller Agent (core AIO mission — currently 0% implemented)
- P2: Build Database Agent (Google Sheets — most complex slug param handling)
- P3: Build Asset Generation Agent (Gamma — already well-understood)
- P3: Build Leads Sourcer Agent

---

## Layer 4: Memory Architecture

**Current: SQLite (per-user, Docker volume) + pgvector (Railway) + session_facts (in-memory + PG flush)**

**Verdict: CRITICAL**

**Findings:**
- **SQLite on Docker volume = CRITICAL risk.** Railway volume loss or container migration loses ALL per-user SQLite data. This is not recoverable.
- MEMORY.md auto-append is unbounded — no pruning, grows forever. Not loaded into system prompt (good), but `deepRecall` searches it and slowness increases linearly
- pgvector is only written when SQLite write succeeds — dual-write is not atomic. SQLite failure = pgvector miss
- session_facts are in-memory during session, flushed to PG at end — any mid-session crash loses all facts
- Per-user `/app/data/memory/users/{user_id}/` directory structure has 7 workspace files. All 7 loaded into system prompt context on every session start
- MEMORY.md loaded into system prompt as context has no size cap — could grow to 50KB+ for heavy users
- No cross-user memory (organizational knowledge not shared between employees at same company)

**Action items:**
- P0: Migrate all SQLite storage to Railway PostgreSQL
  - `aio_memories` table (already in pgvector — promote to primary)
  - `session_summaries` → PG table (already partially in pgvector)
  - `deep_store` → PG `deep_store` table
  - Remove Docker volume mount
- P0: Add `company_id` column to all memory tables for organizational knowledge sharing
- P1: Add MEMORY.md size cap: when > 10KB, run nightly summarization and replace with condensed version
- P1: Flush critical session_facts to PG on every tool completion (not just session end)
- P2: Implement organizational memory: facts marked `scope=company` accessible to all users with same `company_id`

---

## Layer 5: Composio Integration

**Current: 100% dynamic slug resolution, 6-tier chain, circuit breakers, idempotency keys**

**Verdict: HIGH RISK**

**Findings:**
- Composio as sole mechanism for 453 tools creates vendor lock-in. Any Composio SDK breaking change = all tools offline
- Slug resolution 6-tier chain adds latency on every first call per session (slug index rebuild ~2-3s)
- Circuit breakers reset after session end — cross-session CB state persists in PG but PG pool teardown/rebuild between sessions adds latency
- OAuth token expiry not proactively detected — tools fail with 401 and circuit breaker trips, then user must manually re-authenticate
- `manageConnections` auth link flow depends on email delivery — if email fails, user cannot authenticate
- No webhook for Composio connection status changes — agent can't proactively notify user that a service expired

**Action items:**
- P0: Add proactive OAuth expiry detection — check token expiry at session start for all connected services
- P1: Add SMS/chat fallback for auth link delivery (not just email)
- P1: Implement Composio connection health check on session start (lightweight — just list connected services)
- P2: Add non-Composio fallback for critical tools (Gmail SMTP direct, Drive API direct) for resilience
- P3: Evaluate moving from Composio SDK to direct API calls for top 5 most-used slugs

---

## Layer 6: AIO Core Mission — Employee Growth Coach

**Current: 0% implemented**

**Verdict: CRITICAL — THIS IS THE ENTIRE PRODUCT VALUE PROPOSITION**

**Findings:**
- AIO's stated mission is to "facilitate employee improvement in all areas they engage with AIO"
- Zero coaching logic exists in the codebase
- No `company_objectives` table — cannot align employee actions to company goals
- No `employee_metrics` table — cannot track skill development over time
- No `skill_progression` schema — cannot identify growth trends
- No `coaching_events` table — cannot record when coaching advice was given or accepted
- No coaching cadence logic — AIO never proactively suggests next steps
- MEMORY.md stores raw interaction facts but has no semantic categorization by skill domain
- The Employee Upskiller Agent does not exist
- Without this layer, AIO is a voice-controlled tool executor, not a growth coach

**Required Schema:**

```sql
-- Company goals (drives all coaching decisions)
company_objectives(
  id BIGSERIAL PRIMARY KEY,
  company_id TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT,
  target_metric TEXT,         -- e.g., "client_retention_rate"
  target_value NUMERIC,
  current_value NUMERIC,
  deadline DATE,
  status TEXT DEFAULT 'active',
  created_at TIMESTAMPTZ DEFAULT NOW()
)

-- Per-employee skill tracking
employee_metrics(
  id BIGSERIAL PRIMARY KEY,
  user_id TEXT NOT NULL,
  company_id TEXT NOT NULL,
  skill_domain TEXT NOT NULL,  -- e.g., "client_retention", "email_follow_up", "data_analysis"
  proficiency_score NUMERIC,   -- 0.0 - 1.0
  interaction_count INTEGER DEFAULT 0,
  last_activity TIMESTAMPTZ,
  trend TEXT,                  -- 'improving', 'stable', 'declining'
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, skill_domain)
)

-- Skill progression events
skill_progression(
  id BIGSERIAL PRIMARY KEY,
  user_id TEXT NOT NULL,
  company_id TEXT NOT NULL,
  skill_domain TEXT NOT NULL,
  event_type TEXT NOT NULL,    -- 'task_completed', 'feedback_given', 'objective_met', 'coaching_accepted'
  score_delta NUMERIC,
  notes TEXT,
  session_id TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
)

-- Coaching interactions
coaching_events(
  id BIGSERIAL PRIMARY KEY,
  user_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  coaching_type TEXT NOT NULL, -- 'proactive_suggestion', 'task_reflection', 'objective_alignment', 'next_steps'
  content TEXT NOT NULL,
  skill_domain TEXT,
  company_objective_id BIGINT REFERENCES company_objectives(id),
  accepted BOOLEAN,            -- NULL = user didn't respond, TRUE/FALSE = responded
  created_at TIMESTAMPTZ DEFAULT NOW()
)
```

**Required Logic (Employee Upskiller Agent):**

1. **Objective alignment**: On every task completion, query `company_objectives` for the user's `company_id`. If task domain matches an objective, log to `skill_progression`.

2. **Pattern detection**: After N interactions in a skill domain, compute trend. If declining → generate coaching event. If improving → positive reinforcement.

3. **Proactive next steps**: At end of session, Upskiller Agent analyzes interaction history → generates 1-3 actionable next steps aligned to company objectives → delivers via voice + stores to `coaching_events`.

4. **Coaching cadence**: First check in `coaching_events` to avoid repetition. Only surface coaching if last coaching event for this domain was > 3 sessions ago.

**Action items:**
- P0: Create all 4 coaching tables (migration SQL)
- P0: Build Employee Upskiller Agent
- P0: Wire `company_id` to user_identity resolution (company = Auto Pay Plus → `company_id=autopayplus`)
- P1: Implement objective alignment scoring on tool completion
- P1: Implement proactive next-steps at session end
- P2: Implement weekly coaching report (extends `weekly_summaries` workflow)

---

## Layer 7: Observability

**Current: live_trace.py (8 patterns), tool_error_log (14 columns), pg_logger fire-and-forget**

**Verdict: MEDIUM RISK**

**Findings:**
- No distributed tracing — no correlation ID across conversation_log, tool_calls, tool_error_log
- live_trace.py classifies 8 patterns but requires manual `--follow` invocation — no automated alerting
- `tool_error_log` is excellent but only covers Composio errors. n8n webhook errors not in structured log
- `weekly_summaries` workflow generates AI summaries but no real-time dashboard
- No SLA tracking — cannot measure p50/p95 tool call latency at the tool level
- `pg_logger` fire-and-forget means DB write failures are silent — no dead letter queue for log events

**Action items:**
- P1: Add `correlation_id` UUID to all log events (conversation_log, tool_calls, tool_error_log)
- P1: Add Railway alert rule: any CRITICAL log line → Slack notification
- P2: Build lightweight dashboard querying `tool_error_log` + `tool_calls` (extend live_trace.py `--dashboard`)
- P3: Add n8n webhook error logging to `tool_error_log` via n8n error handler nodes

---

## Layer 8: Scale & Multi-Tenancy

**Current: Single Railway service, single company (Auto Pay Plus trial)**

**Verdict: HIGH RISK (for when scale arrives)**

**Findings:**
- No `company_id` partitioning in any table — adding a second client requires schema migration
- Composio entity `pg-test-49ecc67f-362b-4475-b0cc-92804c604d1c` is hardcoded — all users share one Composio entity. Multi-tenant Composio requires per-company entity IDs
- SQLite memory on Docker volume cannot be shared across Railway replicas — horizontal scaling impossible with current architecture
- n8n webhook URLs are single-instance — no multi-tenant workflow routing
- Conversation LLM has no company context injection — cannot personalize to Auto Pay Plus vs another client

**Action items:**
- P0: Add `company_id` to user_identity resolution pipeline
- P0: Add `company_id` to all tables (via migration, with default `'_default'`)
- P1: Per-company Composio entity ID registry (stored in `company_config` table)
- P2: Multi-tenant n8n workflow routing via company-specific webhook paths
- P3: Evaluate Railway private networking + replicas for horizontal scale

---

## Priority Action Roadmap

### P0 — Architecture Blockers (do before adding any new features)
1. Migrate SQLite to Railway PostgreSQL (eliminates CRITICAL single point of failure)
2. Create coaching data tables (company_objectives, employee_metrics, skill_progression, coaching_events)
3. Build Employee Upskiller Agent (implements AIO core mission)
4. Add company_id to all tables and user_identity resolution

### P1 — High Impact (next sprint)
1. Add LLM provider fallback (Fireworks → Groq → Anthropic)
2. Build Communication Agent (specialized for email + Teams)
3. Implement objective alignment scoring on task completion
4. Add proactive OAuth expiry detection
5. Add correlation_id to all log events

### P2 — Stability (ongoing)
1. Build Web Intelligence Agent
2. Build Database Agent
3. Implement organizational memory (company-scoped facts)
4. Restore Dockerfile healthcheck start-period=60s
5. Add Railway alert for CRITICAL log lines

### P3 — Optimization (when P0-P2 complete)
1. Build Asset Generation Agent
2. Build Leads Sourcer Agent
3. Implement prompt caching on Fireworks
4. Evaluate GPT-4o-mini for tool executor
5. Build lightweight observability dashboard

---

## Audit Conclusion

AIO is technically functional as a voice-controlled tool executor. The Composio integration, resilience layer (circuit breakers, DLQ, idempotency keys), and memory architecture are well-engineered. However, **the product's stated core mission — employee growth coaching — has 0% implementation**. This is the most critical gap.

The Docker volume SQLite dependency is a data loss risk that will materialize during any Railway infrastructure event. This must be resolved before AIO is deployed to production clients.

The 2-LLM delegation chain works but is generic. Domain-specialized agents will reduce latency, reduce hallucination (domain-specific prompts + pre-loaded schemas), and enable the coaching layer.
