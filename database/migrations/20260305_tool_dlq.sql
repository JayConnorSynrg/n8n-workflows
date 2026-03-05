-- =============================================================================
-- Migration: tool_dlq
-- Created:   2026-03-05
-- Purpose:   Dead Letter Queue for failed AIO tool calls.
--
--            composio_router.py encounters three transient error classes that
--            are safe to retry after a delay — SERVER_5XX (Composio backend
--            fault), TIMEOUT (asyncio/httpx timeout before a response), and
--            NETWORK (DNS failure, TCP reset, SSL handshake error).  Unlike
--            AUTH_401, PERMISSION_403, and SLUG_NOT_FOUND — which are permanent
--            failures requiring human intervention — these three types have a
--            reasonable probability of succeeding on a subsequent attempt.
--
--            This table is the persistence layer for that retry mechanism:
--
--              1. pg_logger.enqueue_dlq() inserts a row on each terminal
--                 transient failure in composio_router.py.
--
--              2. A background task in agent.py polls every 60 seconds,
--                 selects rows WHERE retry_after <= NOW() AND resolved_at IS NULL,
--                 re-executes the call via composio_router, and either:
--                   - Sets resolved_at = NOW() on success, or
--                   - Increments attempt and pushes retry_after forward on
--                     continued failure (exponential back-off), or
--                   - Sets resolved_at = NOW() when attempt == max_attempts
--                     (exhausted — permanently abandoned).
--
--              3. Rows auto-expire via prune_tool_dlq() (see SECTION 4).
--                 The maintenance n8n workflow invokes this daily at 03:00 UTC.
--
--            Scope: only tool calls that already completed their in-router
--            retry_count cycle.  The DLQ is a second-layer retry, not a
--            replacement for the immediate per-call retry logic in the router.
--
-- Idempotent: safe to apply multiple times.
--             CREATE TABLE / INDEX all use IF NOT EXISTS.
--             View uses CREATE OR REPLACE.
--             Pruning procedure uses CREATE OR REPLACE.
-- =============================================================================


-- =============================================================================
-- SECTION 1: TABLE DEFINITION
-- =============================================================================

CREATE TABLE IF NOT EXISTS tool_dlq (

    -- Surrogate primary key.  BIGSERIAL is consistent with tool_error_log and
    -- conversation_log — no sequence exhaustion risk at AIO call volumes.
    id              BIGSERIAL       PRIMARY KEY,

    -- LiveKit session ID at the time the call failed.  Used by the consumer
    -- to reconstruct the call context and to join with conversation_log.
    -- Never NULL — empty string when the call originates from a background task.
    session_id      TEXT            NOT NULL,

    -- User identity string resolved by user_identity.py.
    -- NULL for background or warmup calls with no participant context.
    user_id         TEXT,

    -- Raw Composio slug as submitted by the LLM/agent before any override
    -- resolution.  The consumer re-submits this through the full router
    -- resolution pipeline so that any newly-registered overrides are applied.
    slug            TEXT            NOT NULL,

    -- Full argument payload forwarded to the Composio SDK call.
    -- Stored as JSONB for structural validation and efficient retrieval.
    -- Defaults to an empty object — never NULL (some slugs take no arguments).
    arguments       JSONB           NOT NULL DEFAULT '{}',

    -- Error class that triggered the enqueue.  Constrained to the three
    -- retryable error types recognised by composio_router.py.
    --
    --   SERVER_5XX  — HTTP 5xx from Composio backend (transient server fault)
    --   TIMEOUT     — asyncio.TimeoutError or httpx read timeout
    --   NETWORK     — connection-level failure (DNS, TCP reset, SSL handshake)
    error_type      TEXT            NOT NULL,

    -- Current attempt number.  Starts at 1 (set on INSERT — the first enqueue
    -- counts as attempt 1).  Incremented by the consumer before each retry.
    -- The consumer stops retrying when attempt reaches max_attempts and sets
    -- resolved_at instead.
    attempt         INT             NOT NULL DEFAULT 1,

    -- Maximum number of attempts before the row is abandoned.  Default 3 gives
    -- two consumer-driven retries beyond the initial failure.  Can be raised
    -- per-row for high-priority calls (not used in current implementation but
    -- preserved for future flexibility).
    max_attempts    INT             NOT NULL DEFAULT 3,

    -- Earliest timestamp at which the consumer is allowed to retry this row.
    -- Set to NOW() + retry_delay_secs on INSERT.
    -- Updated by the consumer to NOW() + exponential_back_off on each failure.
    -- Consumer query: WHERE retry_after <= NOW() AND resolved_at IS NULL.
    retry_after     TIMESTAMPTZ     NOT NULL,

    -- Row insertion timestamp.  Used as the primary dimension for age-based
    -- pruning (24-hour retention policy).
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    -- Set by the consumer when the call either succeeds or exhausts max_attempts.
    -- NULL means the row is still pending.  Non-NULL means fully resolved.
    -- Partial index on resolved_at IS NULL keeps all hot-path queries fast.
    resolved_at     TIMESTAMPTZ,

    -- Railway worker process identifier of the consumer that last touched this
    -- row (e.g. "worker-12345").  Populated from the module-level _WORKER_ID
    -- in the consumer task.  Enables per-worker claim tracking and stale-lock
    -- detection.  NULL until the consumer claims the row.
    worker_id       TEXT,

    -- Constrain error_type to the three retryable buckets.  Any other error
    -- type indicates a programming error in the caller — reject at DB level.
    CONSTRAINT tool_dlq_error_type_check CHECK (
        error_type IN ('SERVER_5XX', 'TIMEOUT', 'NETWORK')
    ),

    -- attempt and max_attempts must be positive integers.
    CONSTRAINT tool_dlq_attempt_check CHECK (attempt >= 1),
    CONSTRAINT tool_dlq_max_attempts_check CHECK (max_attempts >= 1),

    -- attempt must never exceed max_attempts (enforced by consumer, validated here).
    CONSTRAINT tool_dlq_attempt_le_max CHECK (attempt <= max_attempts)
);


-- =============================================================================
-- SECTION 2: INDEXES
--
-- Three partial indexes, all scoped to unresolved rows (resolved_at IS NULL).
-- Resolved rows are cold — they exist only for audit purposes until pruned —
-- so including them in hot-path indexes wastes storage and index maintenance
-- overhead on a write-heavy table.
-- =============================================================================

-- Consumer poll query:
--   SELECT * FROM tool_dlq
--   WHERE retry_after <= NOW() AND resolved_at IS NULL
--   ORDER BY retry_after
--   LIMIT 50;
--
-- retry_after is the primary sort key for the consumer.  The partial index
-- covers exactly the rows the consumer needs to scan.
CREATE INDEX IF NOT EXISTS idx_tool_dlq_retry
    ON tool_dlq (retry_after)
    WHERE resolved_at IS NULL;

-- Session-scoped lookup (for context reconstruction and conversation_log joins):
--   SELECT * FROM tool_dlq
--   WHERE session_id = $1 AND resolved_at IS NULL
--   ORDER BY created_at DESC;
CREATE INDEX IF NOT EXISTS idx_tool_dlq_session
    ON tool_dlq (session_id, resolved_at)
    WHERE resolved_at IS NULL;

-- Age-based pruning query (see prune_tool_dlq procedure):
--   SELECT id FROM tool_dlq
--   WHERE created_at < cutoff AND resolved_at IS NULL
--   LIMIT batch_limit;
--
-- Note: resolved rows are pruned separately via the unfiltered created_at scan
-- in the procedure — this index only accelerates the unresolved-row check used
-- for monitoring (are old unresolved rows accumulating?).
CREATE INDEX IF NOT EXISTS idx_tool_dlq_cleanup
    ON tool_dlq (created_at)
    WHERE resolved_at IS NULL;


-- =============================================================================
-- SECTION 3: SUMMARY VIEW
--
-- tool_dlq_summary provides a rolling 24-hour snapshot of DLQ state, grouped
-- by (slug, error_type).  Designed for the live_trace.py --db-summary flag
-- and for n8n dashboard workflows.
-- =============================================================================

CREATE OR REPLACE VIEW tool_dlq_summary AS
SELECT
    slug,
    error_type,

    -- Total rows enqueued in the 24-hour window.
    COUNT(*)                                            AS total_enqueued,

    -- Pending rows (not yet resolved) — indicates backlog pressure.
    COUNT(*) FILTER (WHERE resolved_at IS NULL)        AS pending,

    -- Resolved rows — either succeeded or exhausted max_attempts.
    COUNT(*) FILTER (WHERE resolved_at IS NOT NULL)    AS resolved,

    -- Rows that exhausted max_attempts (attempt == max_attempts at resolve time).
    -- These represent permanently lost calls — useful for alerting.
    COUNT(*) FILTER (
        WHERE resolved_at IS NOT NULL AND attempt = max_attempts
    )                                                   AS exhausted,

    -- Maximum attempt number seen — elevated values indicate persistent failures.
    MAX(attempt)                                        AS max_attempt_seen,

    -- Most recent enqueue — useful for "last seen" staleness checks.
    MAX(created_at)                                     AS last_enqueued

FROM tool_dlq
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY slug, error_type;

COMMENT ON VIEW tool_dlq_summary IS
    'Rolling 24-hour aggregation of tool_dlq state grouped by (slug, error_type). '
    'pending = rows awaiting retry; exhausted = rows that hit max_attempts. '
    'Refreshes on each query — no materialisation required at current DLQ volume.';


-- =============================================================================
-- SECTION 4: PRUNING STRATEGY
--
-- Retention policy: 24 hours for resolved rows, 48 hours for unresolved rows
-- (unresolved rows older than 48h indicate a consumer bug — keep them longer
-- for post-mortem analysis).
--
-- Implementation: stored procedure using batched DELETE to avoid long-running
-- locks on the live table.  Invoked nightly by the existing maintenance n8n
-- workflow (same invocation that calls prune_tool_error_log).
-- =============================================================================

CREATE OR REPLACE PROCEDURE prune_tool_dlq(
    -- Resolved rows older than this interval are eligible for deletion.
    resolved_retention  INTERVAL DEFAULT INTERVAL '24 hours',

    -- Unresolved rows older than this interval are also pruned (abandoned).
    unresolved_retention INTERVAL DEFAULT INTERVAL '48 hours',

    -- Maximum rows deleted per call (bounding lock duration).
    batch_limit         INTEGER  DEFAULT 10000
)
LANGUAGE plpgsql
AS $$
DECLARE
    deleted_count   BIGINT;
    total_deleted   BIGINT := 0;
    resolved_cutoff TIMESTAMPTZ;
    stale_cutoff    TIMESTAMPTZ;
BEGIN
    resolved_cutoff := NOW() - resolved_retention;
    stale_cutoff    := NOW() - unresolved_retention;

    -- Phase 1: prune resolved rows beyond the resolved_retention window.
    LOOP
        DELETE FROM tool_dlq
        WHERE id IN (
            SELECT id
            FROM   tool_dlq
            WHERE  resolved_at IS NOT NULL
              AND  created_at < resolved_cutoff
            LIMIT  batch_limit
        );

        GET DIAGNOSTICS deleted_count = ROW_COUNT;
        total_deleted := total_deleted + deleted_count;
        EXIT WHEN deleted_count = 0;
        PERFORM pg_sleep(0.05);
    END LOOP;

    -- Phase 2: prune stale unresolved rows (consumer abandonment / bug).
    LOOP
        DELETE FROM tool_dlq
        WHERE id IN (
            SELECT id
            FROM   tool_dlq
            WHERE  resolved_at IS NULL
              AND  created_at < stale_cutoff
            LIMIT  batch_limit
        );

        GET DIAGNOSTICS deleted_count = ROW_COUNT;
        total_deleted := total_deleted + deleted_count;
        EXIT WHEN deleted_count = 0;
        PERFORM pg_sleep(0.05);
    END LOOP;

    RAISE NOTICE 'prune_tool_dlq: deleted % rows (resolved cutoff: %, stale cutoff: %)',
        total_deleted, resolved_cutoff, stale_cutoff;
END;
$$;

COMMENT ON PROCEDURE prune_tool_dlq IS
    'Batch-deletes tool_dlq rows beyond retention windows. '
    'Resolved rows: pruned after 24 hours. Unresolved rows: pruned after 48 hours. '
    'Run nightly via the existing AIO maintenance n8n workflow. '
    'Uses 10,000-row batch loop to bound lock duration on live Railway instances.';


-- =============================================================================
-- SECTION 5: TABLE AND COLUMN COMMENTS
-- =============================================================================

COMMENT ON TABLE tool_dlq IS
    'Dead Letter Queue for failed AIO Composio tool calls. '
    'Stores SERVER_5XX, TIMEOUT, and NETWORK errors for background retry. '
    'Consumer in agent.py polls every 60s and retries eligible rows. '
    'Pruned by prune_tool_dlq(): resolved rows after 24h, stale unresolved after 48h.';

COMMENT ON COLUMN tool_dlq.session_id   IS 'LiveKit session ID at call time. Empty string for background calls. Soft FK to sessions.session_id.';
COMMENT ON COLUMN tool_dlq.user_id      IS 'User identity from user_identity.py 6-tier resolution. NULL for background/warmup calls.';
COMMENT ON COLUMN tool_dlq.slug         IS 'Raw Composio slug as submitted by the LLM/agent. Consumer re-submits through full router resolution pipeline.';
COMMENT ON COLUMN tool_dlq.arguments    IS 'Full argument payload forwarded to the Composio SDK call. Stored as JSONB.';
COMMENT ON COLUMN tool_dlq.error_type   IS 'Retryable error class: SERVER_5XX | TIMEOUT | NETWORK.';
COMMENT ON COLUMN tool_dlq.attempt      IS 'Current attempt number, starting at 1. Incremented by the consumer before each retry.';
COMMENT ON COLUMN tool_dlq.max_attempts IS 'Maximum attempts before the row is abandoned and resolved_at is set. Default 3.';
COMMENT ON COLUMN tool_dlq.retry_after  IS 'Earliest timestamp at which the consumer may retry. Set to NOW()+delay on INSERT; updated with exponential back-off on each consumer failure.';
COMMENT ON COLUMN tool_dlq.created_at   IS 'Row insertion timestamp. Primary dimension for pruning policy.';
COMMENT ON COLUMN tool_dlq.resolved_at  IS 'Set by the consumer on success or max_attempts exhaustion. NULL means pending.';
COMMENT ON COLUMN tool_dlq.worker_id    IS 'Railway worker process ID of the consumer that last claimed this row.';


-- =============================================================================
-- SECTION 6: VERIFICATION QUERIES
-- Execute manually after applying the migration to confirm correctness.
-- =============================================================================

-- Confirm table and all columns exist
SELECT
    t.table_name,
    c.column_name,
    c.data_type,
    c.column_default,
    c.is_nullable
FROM information_schema.tables  t
JOIN information_schema.columns c USING (table_name)
WHERE t.table_schema = 'public'
  AND t.table_name   = 'tool_dlq'
ORDER BY c.ordinal_position;

-- List indexes on the table
SELECT indexname, indexdef
FROM   pg_indexes
WHERE  tablename = 'tool_dlq'
ORDER BY indexname;

-- Confirm view exists and is queryable
SELECT * FROM tool_dlq_summary LIMIT 0;

-- Confirm procedure exists
SELECT proname, pronargs
FROM   pg_proc
WHERE  proname = 'prune_tool_dlq';

-- Verify constraints are registered
SELECT conname, contype, consrc
FROM   pg_constraint
WHERE  conrelid = 'tool_dlq'::regclass
ORDER BY conname;
