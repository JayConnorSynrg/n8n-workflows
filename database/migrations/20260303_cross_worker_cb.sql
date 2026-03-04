-- Cross-worker service circuit breaker state
CREATE TABLE IF NOT EXISTS service_circuit_breaker (
    service TEXT PRIMARY KEY,
    is_failed BOOLEAN NOT NULL DEFAULT FALSE,
    failure_reason TEXT,
    failed_at TIMESTAMPTZ,
    worker_id TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Cross-worker initiated connection tracking
CREATE TABLE IF NOT EXISTS initiated_connections (
    service TEXT PRIMARY KEY,
    worker_id TEXT,
    initiated_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '8 minutes',
    auth_url TEXT
);

CREATE INDEX IF NOT EXISTS idx_initiated_connections_expires ON initiated_connections(expires_at);
