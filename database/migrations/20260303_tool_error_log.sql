-- =============================================================================
-- Migration: tool_error_log
-- Created:   2026-03-03
-- Purpose:   Per-call error ledger for the AIO Composio router.
--
--            composio_router.py classifies every failed tool call into one of
--            nine error types (AUTH_401, PERMISSION_403, TIMEOUT, SLUG_NOT_FOUND,
--            CB_TRIPPED, RATE_LIMIT, PARAM_ERROR, NETWORK, SERVER_5XX) plus a
--            catch-all UNKNOWN bucket.  This table captures the full resolution
--            context — slug overrides, tier traversal, retry count, circuit-breaker
--            state, worker identity, and wall-clock duration — so that:
--
--              - Top-failing slugs can be ranked over any time window
--              - Service-level error breakdowns can be generated without scanning
--                the full conversation_log
--              - Per-worker failure skew can be detected across the 8 Railway
--                worker processes
--              - circuit_breaker state transitions can be correlated with errors
--
-- Idempotent: safe to apply multiple times.
--             CREATE TABLE / INDEX all use IF NOT EXISTS.
--             View uses CREATE OR REPLACE.
--             Pruning function uses CREATE OR REPLACE.
-- =============================================================================


-- =============================================================================
-- SECTION 1: TABLE DEFINITION
-- =============================================================================

CREATE TABLE IF NOT EXISTS tool_error_log (

    -- Surrogate primary key. BIGSERIAL handles 8 Railway workers each logging
    -- dozens of errors per hour without sequence exhaustion for years.
    id                  BIGSERIAL       PRIMARY KEY,

    -- The raw Composio slug as passed by the LLM or agent code before any
    -- override resolution (e.g. "GOOGLEDRIVE_FIND_FILE").
    -- Never NULL — a slug is always present even when it cannot be resolved.
    slug                TEXT            NOT NULL,

    -- Slug after _SLUG_OVERRIDES mapping has been applied in composio_router.py.
    -- NULL when the router never reached override resolution (e.g. CB_TRIPPED
    -- before the lookup stage) or when no override exists and slug == resolved_slug.
    resolved_slug       TEXT,

    -- Service component extracted from the slug prefix, normalised to lowercase
    -- (e.g. "googledrive", "gamma", "gmail").  Populated by
    -- composio_router._extract_service(slug).  NULL if extraction fails.
    service             TEXT,

    -- Classified error bucket.  Constrained to the ten values that
    -- composio_router.py emits, plus UNKNOWN as a safe default.
    --
    --   AUTH_401        — HTTP 401, triggers circuit-breaker trip
    --   PERMISSION_403  — HTTP 403, permission denied, CB NOT tripped
    --   TIMEOUT         — asyncio.TimeoutError or httpx read timeout
    --   SLUG_NOT_FOUND  — slug absent from all six resolution tiers
    --   CB_TRIPPED      — call rejected because CB is OPEN for the service
    --   RATE_LIMIT      — HTTP 429
    --   PARAM_ERROR     — bad/missing parameters returned by the API (4xx other)
    --   NETWORK         — connection-level failures (DNS, TCP reset, SSL)
    --   SERVER_5XX      — HTTP 5xx from Composio backend
    --   UNKNOWN         — exception not matching any of the above
    error_type          TEXT            NOT NULL DEFAULT 'UNKNOWN',

    -- Which resolution tier (1–6) first located the slug in the router's
    -- internal index.  NULL means the slug was never found in any tier
    -- (correlates with SLUG_NOT_FOUND error_type but can also appear when a
    -- slug is found yet the call still fails for another reason).
    --
    --   Tier 1 — exact match in _slug_schemas pre-fetched cache
    --   Tier 2 — case-insensitive match in pre-fetched cache
    --   Tier 3 — _SLUG_OVERRIDES static map
    --   Tier 4 — live fetch via get_raw_composio_tools() + cache
    --   Tier 5 — service prefix scan across full tool index
    --   Tier 6 — fuzzy / partial-name match
    tier_resolved       INTEGER,

    -- Number of retry attempts made before giving up.  Matches the retry logic
    -- in composio_router.execute_composio_tool() (typically 0–3).
    retry_count         INTEGER         NOT NULL DEFAULT 0,

    -- Circuit-breaker state of the service at the moment the call was attempted.
    --
    --   CLOSED    — service healthy, calls allowed through
    --   OPEN      — service tripped, calls rejected immediately (CB_TRIPPED)
    --   HALF_OPEN — recovery probe allowed through after cool-down window
    cb_state            TEXT,

    -- Railway worker process identifier (e.g. "worker-12345").  Populated from
    -- the module-level _WORKER_ID = f"worker-{os.getpid()}" in composio_router.py.
    -- Enables per-worker failure skew detection across the 8 concurrent processes.
    worker_id           TEXT,

    -- Total wall-clock time for the call including all retries, in milliseconds.
    -- NULL when the call was rejected before any network I/O (CB_TRIPPED,
    -- SLUG_NOT_FOUND before lookup).
    duration_ms         INTEGER,

    -- First 500 characters of the raw exception message or API error body.
    -- Truncation at 500 chars is enforced by the application layer in
    -- composio_router.py to keep this column bounded.
    raw_error           TEXT,

    -- LiveKit session ID for joining with conversation_log and sessions tables.
    -- NULL for calls that occur outside an active room (background health checks,
    -- warmup probes).
    session_id          TEXT,

    -- User identity string resolved by user_identity.py (6-tier resolution).
    -- NULL when the call originates from a background task with no user context.
    user_id             TEXT,

    -- Row insertion timestamp.  Used as the primary dimension for all range
    -- scans and for the 30-day pruning policy.
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    -- Enforce the closed set of error type values recognised by the router.
    CONSTRAINT tool_error_log_error_type_check CHECK (
        error_type IN (
            'AUTH_401',
            'PERMISSION_403',
            'TIMEOUT',
            'SLUG_NOT_FOUND',
            'CB_TRIPPED',
            'RATE_LIMIT',
            'PARAM_ERROR',
            'NETWORK',
            'SERVER_5XX',
            'UNKNOWN'
        )
    ),

    -- Circuit-breaker state is one of three well-known values or NULL.
    CONSTRAINT tool_error_log_cb_state_check CHECK (
        cb_state IS NULL OR cb_state IN ('OPEN', 'CLOSED', 'HALF_OPEN')
    ),

    -- Tier must be 1–6 if present.
    CONSTRAINT tool_error_log_tier_check CHECK (
        tier_resolved IS NULL OR tier_resolved BETWEEN 1 AND 6
    ),

    -- retry_count is non-negative.
    CONSTRAINT tool_error_log_retry_check CHECK (retry_count >= 0),

    -- duration_ms is non-negative when present.
    CONSTRAINT tool_error_log_duration_check CHECK (
        duration_ms IS NULL OR duration_ms >= 0
    )
);


-- =============================================================================
-- SECTION 2: INDEXES
--
-- Three targeted composite indexes covering the three primary query shapes
-- described in the requirements.  All include created_at DESC as the trailing
-- key so that time-bounded range scans (WHERE created_at > NOW() - INTERVAL x)
-- can be served from the index without a separate sort.
-- =============================================================================

-- Top-failing-slugs query pattern:
--   SELECT slug, COUNT(*) FROM tool_error_log
--   WHERE slug = $1 AND created_at > NOW() - INTERVAL '24 hours'
--   GROUP BY slug ORDER BY COUNT(*) DESC;
--
--   Also serves: single-slug drill-down, slug-specific error-type breakdown.
CREATE INDEX IF NOT EXISTS idx_tool_error_log_slug_time
    ON tool_error_log (slug, created_at DESC);

-- Service-level error breakdown query pattern:
--   SELECT service, error_type, COUNT(*) FROM tool_error_log
--   WHERE service = $1 AND created_at > NOW() - INTERVAL '1 hour'
--   GROUP BY service, error_type;
--
--   Also serves: cross-service comparison, error_type-only aggregations
--   (partial index scan on leading columns).
CREATE INDEX IF NOT EXISTS idx_tool_error_log_service_error_time
    ON tool_error_log (service, error_type, created_at DESC);

-- Per-worker failure analysis query pattern:
--   SELECT worker_id, error_type, COUNT(*) FROM tool_error_log
--   WHERE worker_id = $1 AND created_at > NOW() - INTERVAL '6 hours'
--   GROUP BY worker_id, error_type;
--
--   Also serves: all-worker rollup (omit WHERE clause, index still prunes by time).
CREATE INDEX IF NOT EXISTS idx_tool_error_log_worker_time
    ON tool_error_log (worker_id, created_at DESC);

-- Supplementary: session-scoped join with conversation_log / sessions tables.
--   SELECT * FROM tool_error_log WHERE session_id = $1 ORDER BY created_at DESC;
CREATE INDEX IF NOT EXISTS idx_tool_error_log_session
    ON tool_error_log (session_id, created_at DESC);


-- =============================================================================
-- SECTION 3: SUMMARY VIEW
--
-- tool_error_summary provides a pre-aggregated view over the last 24 hours,
-- grouped by (slug, service, error_type).  Designed for dashboard polling and
-- alerting rules.
--
-- CREATE OR REPLACE VIEW is idempotent — safe to re-run if the view definition
-- needs to be updated in a future migration.
-- =============================================================================

CREATE OR REPLACE VIEW tool_error_summary AS
SELECT
    slug,
    service,
    error_type,

    -- Total occurrences of this (slug, service, error_type) combination in the
    -- rolling 24-hour window.
    COUNT(*)                        AS count,

    -- Most recent occurrence — useful for "last seen" staleness checks.
    MAX(created_at)                 AS last_seen,

    -- Average wall-clock time across calls that recorded a duration.
    -- NULL when all matching rows have NULL duration_ms (e.g. CB_TRIPPED rows).
    AVG(duration_ms)::INTEGER       AS avg_duration_ms,

    -- Average retry count — elevated values indicate retry storms.
    AVG(retry_count)::NUMERIC(4,2)  AS avg_retry_count,

    -- Maximum retries seen — useful for detecting worst-case retry thrash.
    MAX(retry_count)                AS max_retry_count

FROM tool_error_log
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY slug, service, error_type;

COMMENT ON VIEW tool_error_summary IS
    'Rolling 24-hour aggregation of tool errors grouped by (slug, service, error_type). '
    'Refreshes on each query — no materialisation required at current write volume.';


-- =============================================================================
-- SECTION 4: PRUNING STRATEGY
--
-- Goal: keep the table bounded to ~30 days of data.
--
-- Approach: a stored procedure that DELETEs rows older than 30 days in batches
-- of 10,000 to avoid long-running lock contention on the live table.  The
-- procedure is idempotent and safe to call repeatedly.
--
-- Invocation options:
--   A) pg_cron (preferred if available on Railway):
--        SELECT cron.schedule('prune-tool-error-log', '0 3 * * *',
--            $$CALL prune_tool_error_log()$$);
--
--   B) n8n Schedule trigger workflow (no pg_cron dependency):
--        - Schedule: daily at 03:00 UTC
--        - Postgres node: CALL prune_tool_error_log();
--
--   C) Railway CRON service (external):
--        psql $DATABASE_URL -c "CALL prune_tool_error_log();"
--
-- The 30-day cutoff is defined as a parameter default so it can be overridden
-- for ad-hoc retention adjustments without altering the procedure.
-- =============================================================================

CREATE OR REPLACE PROCEDURE prune_tool_error_log(
    -- Rows older than this interval are eligible for deletion.
    retention_interval INTERVAL DEFAULT INTERVAL '30 days',

    -- Maximum rows deleted per call.  Keeps DELETE batches short to avoid
    -- holding table locks across many index pages on a busy Railway instance.
    batch_limit        INTEGER  DEFAULT 10000
)
LANGUAGE plpgsql
AS $$
DECLARE
    deleted_count  BIGINT;
    total_deleted  BIGINT := 0;
    cutoff_time    TIMESTAMPTZ;
BEGIN
    cutoff_time := NOW() - retention_interval;

    -- Loop in batches until no rows older than the cutoff remain.
    -- Each iteration commits implicitly because CALL is run outside an
    -- explicit transaction in the pg_cron / psql invocation contexts.
    LOOP
        DELETE FROM tool_error_log
        WHERE id IN (
            SELECT id
            FROM   tool_error_log
            WHERE  created_at < cutoff_time
            LIMIT  batch_limit
        );

        GET DIAGNOSTICS deleted_count = ROW_COUNT;
        total_deleted := total_deleted + deleted_count;

        -- Exit when the batch was empty (no rows left to prune).
        EXIT WHEN deleted_count = 0;

        -- Yield briefly to allow other sessions to proceed between batches.
        PERFORM pg_sleep(0.05);
    END LOOP;

    RAISE NOTICE 'prune_tool_error_log: deleted % rows older than % (cutoff: %)',
        total_deleted, retention_interval, cutoff_time;
END;
$$;

COMMENT ON PROCEDURE prune_tool_error_log IS
    'Batch-deletes tool_error_log rows older than retention_interval (default 30 days). '
    'Run nightly via pg_cron, n8n Schedule, or an external CRON job. '
    'Uses a 10,000-row batch loop to bound lock duration on live Railway instances.';


-- =============================================================================
-- SECTION 5: TABLE AND COLUMN COMMENTS
-- Provides self-documenting metadata visible in psql \d+ and pg admin tools.
-- =============================================================================

COMMENT ON TABLE tool_error_log IS
    'Per-call error ledger for the AIO Composio router (composio_router.py). '
    'Captures slug resolution context, error classification, circuit-breaker state, '
    'worker identity, and timing for every failed Composio tool invocation. '
    'Pruned to 30 days by prune_tool_error_log().';

COMMENT ON COLUMN tool_error_log.slug            IS 'Raw Composio slug as submitted by the LLM/agent before any override resolution.';
COMMENT ON COLUMN tool_error_log.resolved_slug   IS 'Slug after _SLUG_OVERRIDES mapping. NULL when slug == resolved_slug or resolution did not reach override stage.';
COMMENT ON COLUMN tool_error_log.service         IS 'Lowercase service prefix extracted from slug (e.g. "googledrive", "gamma").';
COMMENT ON COLUMN tool_error_log.error_type      IS 'Classified error bucket emitted by composio_router.py. One of AUTH_401/PERMISSION_403/TIMEOUT/SLUG_NOT_FOUND/CB_TRIPPED/RATE_LIMIT/PARAM_ERROR/NETWORK/SERVER_5XX/UNKNOWN.';
COMMENT ON COLUMN tool_error_log.tier_resolved   IS 'Resolution tier (1–6) where the slug was first located. NULL if slug not found in any tier.';
COMMENT ON COLUMN tool_error_log.retry_count     IS 'Number of retry attempts before terminal failure (0 = first attempt failed with no retry).';
COMMENT ON COLUMN tool_error_log.cb_state        IS 'Circuit-breaker state for the service at call time: OPEN/CLOSED/HALF_OPEN.';
COMMENT ON COLUMN tool_error_log.worker_id       IS 'Railway worker process ID from module-level _WORKER_ID = f"worker-{os.getpid()}".';
COMMENT ON COLUMN tool_error_log.duration_ms     IS 'Total elapsed time including retries in milliseconds. NULL for calls rejected before network I/O.';
COMMENT ON COLUMN tool_error_log.raw_error       IS 'First 500 chars of the raw exception message or API error body. Truncation enforced by composio_router.py.';
COMMENT ON COLUMN tool_error_log.session_id      IS 'LiveKit session ID. Foreign key (soft) to sessions.session_id.';
COMMENT ON COLUMN tool_error_log.user_id         IS 'User identity string from user_identity.py 6-tier resolution. NULL for background/warmup calls.';
COMMENT ON COLUMN tool_error_log.created_at      IS 'Row insertion timestamp. Primary dimension for all time-bounded scans and 30-day pruning.';


-- =============================================================================
-- SECTION 6: VERIFICATION QUERIES
-- Execute manually after applying the migration to confirm correctness.
-- =============================================================================

-- Confirm table and all indexes exist
SELECT
    t.table_name,
    c.column_name,
    c.data_type,
    c.column_default,
    c.is_nullable
FROM information_schema.tables    t
JOIN information_schema.columns   c USING (table_name)
WHERE t.table_schema = 'public'
  AND t.table_name   = 'tool_error_log'
ORDER BY c.ordinal_position;

-- List indexes on the table
SELECT indexname, indexdef
FROM   pg_indexes
WHERE  tablename = 'tool_error_log'
ORDER BY indexname;

-- Confirm view exists and is queryable (will return zero rows on a fresh table)
SELECT * FROM tool_error_summary LIMIT 0;

-- Confirm procedure exists
SELECT proname, pronargs
FROM   pg_proc
WHERE  proname = 'prune_tool_error_log';
