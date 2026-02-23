// =============================================================================
// ToolCallTracker.ts
// Bidirectional call_id ↔ task_id correlation for async tool execution.
// Handles async n8n workflows that return a task_id on tool.call but send
// results via tool_result with a task_id → call_id back-reference.
// =============================================================================

// ---------------------------------------------------------------------------
// 1. Internal types
// ---------------------------------------------------------------------------

interface CorrelationEntry {
  callId: string
  taskId: string
  expiresAt: number
}

// ---------------------------------------------------------------------------
// 2. Constants
// ---------------------------------------------------------------------------

const DEFAULT_TTL_MS = 300_000       // 5 minutes
const CLEANUP_INTERVAL_MS = 60_000   // 1 minute

// ---------------------------------------------------------------------------
// 3. ToolCallTracker class
// ---------------------------------------------------------------------------

export class ToolCallTracker {
  // Primary storage keyed by callId
  private readonly _byCallId = new Map<string, CorrelationEntry>()

  // Reverse index keyed by taskId → callId (for O(1) reverse lookup)
  private readonly _byTaskId = new Map<string, string>()

  // Auto-cleanup interval handle
  private _cleanupInterval: ReturnType<typeof setInterval> | null

  constructor() {
    this._cleanupInterval = setInterval(() => {
      this.cleanup()
    }, CLEANUP_INTERVAL_MS)
  }

  // ---------------------------------------------------------------------------
  // 3a. Register a call_id / task_id correlation
  // ---------------------------------------------------------------------------

  /**
   * Register a bidirectional mapping between a LiveKit `call_id` and an
   * async n8n `task_id`.
   *
   * @param callId  - The call_id from the `tool.call` event.
   * @param taskId  - The task_id returned by the n8n backend.
   * @param ttl     - Time-to-live in milliseconds. Defaults to 300,000 (5 min).
   */
  register(callId: string, taskId: string, ttl: number = DEFAULT_TTL_MS): void {
    if (!callId || !taskId) {
      console.warn('[ToolCallTracker] register: callId and taskId must be non-empty strings', {
        callId,
        taskId
      })
      return
    }

    const expiresAt = Date.now() + ttl

    const entry: CorrelationEntry = { callId, taskId, expiresAt }

    // If callId is being re-registered, remove the old taskId reverse index
    const existing = this._byCallId.get(callId)
    if (existing) {
      this._byTaskId.delete(existing.taskId)
    }

    this._byCallId.set(callId, entry)
    this._byTaskId.set(taskId, callId)

    console.debug('[ToolCallTracker] registered', { callId, taskId, ttlMs: ttl })
  }

  // ---------------------------------------------------------------------------
  // 3b. Lookups
  // ---------------------------------------------------------------------------

  /**
   * Given a `task_id` (from a `tool_result` event), return the correlated `call_id`.
   * Returns `null` if not found or expired.
   */
  resolveCallId(taskId: string): string | null {
    const callId = this._byTaskId.get(taskId)
    if (!callId) return null

    const entry = this._byCallId.get(callId)
    if (!entry) return null

    if (Date.now() > entry.expiresAt) {
      this._evict(callId, taskId)
      return null
    }

    return callId
  }

  /**
   * Given a `call_id` (from a `tool.call` event), return the correlated `task_id`.
   * Returns `null` if not found or expired.
   */
  resolveTaskId(callId: string): string | null {
    const entry = this._byCallId.get(callId)
    if (!entry) return null

    if (Date.now() > entry.expiresAt) {
      this._evict(callId, entry.taskId)
      return null
    }

    return entry.taskId
  }

  /**
   * Returns `true` if a non-expired entry exists for the given `call_id`.
   */
  has(callId: string): boolean {
    const entry = this._byCallId.get(callId)
    if (!entry) return false

    if (Date.now() > entry.expiresAt) {
      this._evict(callId, entry.taskId)
      return false
    }

    return true
  }

  // ---------------------------------------------------------------------------
  // 3c. Cleanup
  // ---------------------------------------------------------------------------

  /**
   * Purge all entries whose TTL has elapsed.
   * Called automatically every 60 seconds; can also be called manually.
   */
  cleanup(): void {
    const now = Date.now()
    let purged = 0

    for (const [callId, entry] of this._byCallId) {
      if (now > entry.expiresAt) {
        this._evict(callId, entry.taskId)
        purged++
      }
    }

    if (purged > 0) {
      console.debug(`[ToolCallTracker] cleanup: purged ${purged} expired entries`)
    }
  }

  // ---------------------------------------------------------------------------
  // 3d. Destroy (for component unmount)
  // ---------------------------------------------------------------------------

  /**
   * Stop the auto-cleanup interval and clear all internal state.
   * Must be called when the owning component unmounts to prevent memory leaks.
   */
  destroy(): void {
    if (this._cleanupInterval !== null) {
      clearInterval(this._cleanupInterval)
      this._cleanupInterval = null
    }
    this._byCallId.clear()
    this._byTaskId.clear()
    console.debug('[ToolCallTracker] destroyed')
  }

  // ---------------------------------------------------------------------------
  // 3e. Diagnostics (dev-only)
  // ---------------------------------------------------------------------------

  /**
   * Returns the current number of tracked entries (including expired ones
   * that have not yet been cleaned up).
   */
  get size(): number {
    return this._byCallId.size
  }

  // ---------------------------------------------------------------------------
  // Private helpers
  // ---------------------------------------------------------------------------

  private _evict(callId: string, taskId: string): void {
    this._byCallId.delete(callId)
    this._byTaskId.delete(taskId)
  }
}

// ---------------------------------------------------------------------------
// 4. Singleton export
// ---------------------------------------------------------------------------

/**
 * Application-wide singleton ToolCallTracker.
 * Import this wherever call_id ↔ task_id correlation is needed.
 * Call `toolCallTracker.destroy()` when the app tears down (e.g., in App unmount).
 */
export const toolCallTracker = new ToolCallTracker()
