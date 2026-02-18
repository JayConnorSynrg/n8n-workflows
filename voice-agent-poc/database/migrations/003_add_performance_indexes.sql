-- Migration: Add performance indexes for context queries
-- Created: 2026-01-18
-- Purpose: Optimize session_context queries that were taking 2,922ms
--
-- Root Cause Analysis:
-- 1. Missing composite index on (session_id, created_at DESC) caused full table scans
-- 2. PostgreSQL had to sort 500+ rows before applying LIMIT 50
--
-- Expected Impact:
-- - Query time: 2,922ms → 300-500ms (83-90% faster)
-- - Index-only scans for session lookups
-- - Proper DESC ordering without sort step

-- Create composite index for session_context queries
-- CONCURRENTLY allows index creation without blocking writes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tool_calls_session_created
ON tool_calls(session_id, created_at DESC);

-- Create index for tool_history queries by function name
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tool_calls_function_status
ON tool_calls(function_name, status, created_at DESC);

-- Create partial index for active (non-completed) tool calls
-- Useful for checking in-progress operations
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tool_calls_active
ON tool_calls(session_id, created_at DESC)
WHERE status NOT IN ('SUCCESS', 'FAILED', 'CANCELLED');

-- Create index for session_context table (if exists)
-- Optimizes cross-tool data sharing lookups
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_session_context_lookup
ON session_context(session_id, context_key, expires_at DESC)
WHERE expires_at > NOW();

-- Analyze tables to update statistics
ANALYZE tool_calls;
ANALYZE session_context;

-- Comments for documentation
COMMENT ON INDEX idx_tool_calls_session_created IS
'Composite index for fast session_context queries - reduces 2.9s to <500ms';

COMMENT ON INDEX idx_tool_calls_function_status IS
'Index for tool_history queries filtered by function name';

COMMENT ON INDEX idx_tool_calls_active IS
'Partial index for finding in-progress tool calls';

COMMENT ON INDEX idx_session_context_lookup IS
'Composite index for session context lookups with TTL filtering';
