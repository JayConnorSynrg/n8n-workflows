// =============================================================================
// AgentEventBus.ts
// Typed, deduplicated, replayable event bus for AIO Voice Agent events.
// =============================================================================

import { AgentEvent, parseAgentEvent } from './AgentEventSchema'

// ---------------------------------------------------------------------------
// 1. Handler types
// ---------------------------------------------------------------------------

/**
 * Handler for a specific event type T.
 * The generic Extract narrows the event to the concrete interface.
 */
export type AgentEventHandler<T extends AgentEvent> = (event: T) => void

/** Handler for any event — used for metrics and logging subscribers. */
export type AnyEventHandler = (event: AgentEvent) => void

// ---------------------------------------------------------------------------
// 2. Internal constants
// ---------------------------------------------------------------------------

const REPLAY_BUFFER_SIZE = 20
const DEDUP_WINDOW_MS = 50

// ---------------------------------------------------------------------------
// 3. AgentEventBus class
// ---------------------------------------------------------------------------

export class AgentEventBus {
  // Per-type handler map: event.type → Set of handlers
  private readonly _handlers = new Map<string, Set<AnyEventHandler>>()

  // Catch-all subscribers (onAny)
  private readonly _anyHandlers = new Set<AnyEventHandler>()

  // Deduplication: key = `${type}:${call_id}` → last dispatched timestamp
  private readonly _dedupMap = new Map<string, number>()

  // Circular replay buffer
  private readonly _replayBuffer: AgentEvent[] = []
  private _replayHead = 0
  private _replayCount = 0

  // ---------------------------------------------------------------------------
  // 3a. Subscribe to a specific event type
  // ---------------------------------------------------------------------------

  /**
   * Subscribe to events of a specific type.
   *
   * @returns Unsubscribe function — call it to remove this handler.
   *
   * @example
   * const off = bus.on('tool.call', (e) => console.log(e.call_id))
   * // later:
   * off()
   */
  on<T extends AgentEvent['type']>(
    type: T,
    handler: AgentEventHandler<Extract<AgentEvent, { type: T }>>
  ): () => void {
    let handlers = this._handlers.get(type)
    if (!handlers) {
      handlers = new Set()
      this._handlers.set(type, handlers)
    }
    // Cast is safe: the handler is only called when event.type === T
    handlers.add(handler as AnyEventHandler)

    return () => this.off(type, handler)
  }

  // ---------------------------------------------------------------------------
  // 3b. Unsubscribe from a specific event type
  // ---------------------------------------------------------------------------

  off<T extends AgentEvent['type']>(
    type: T,
    handler: AgentEventHandler<Extract<AgentEvent, { type: T }>>
  ): void {
    const handlers = this._handlers.get(type)
    if (handlers) {
      handlers.delete(handler as AnyEventHandler)
      if (handlers.size === 0) {
        this._handlers.delete(type)
      }
    }
  }

  // ---------------------------------------------------------------------------
  // 3c. Subscribe to all events (for metrics / logging)
  // ---------------------------------------------------------------------------

  /**
   * Subscribe to every dispatched event regardless of type.
   *
   * @returns Unsubscribe function.
   */
  onAny(handler: AnyEventHandler): () => void {
    this._anyHandlers.add(handler)
    return () => this._anyHandlers.delete(handler)
  }

  // ---------------------------------------------------------------------------
  // 3d. Dispatch an event
  // ---------------------------------------------------------------------------

  /**
   * Validate, deduplicate, buffer, and dispatch an event to all subscribers.
   *
   * Validation: `parseAgentEvent` is called; invalid payloads are silently
   * dropped (parseAgentEvent already logs a warning).
   *
   * Deduplication: events sharing the same `type` and `call_id` (if present)
   * within DEDUP_WINDOW_MS (50 ms) are dropped.
   */
  dispatch(event: AgentEvent): void {
    // Re-validate to ensure the event still conforms (handles external callers)
    const validated = parseAgentEvent(event)
    if (!validated) return

    // Deduplication check
    // Double-cast through unknown because AgentEvent is a discriminated union,
    // not an index-signature type. Not all members have call_id, and that is fine —
    // if absent, dedupKey will just use the type string alone.
    const callId = (validated as unknown as Record<string, unknown>)['call_id']
    const dedupKey = `${validated.type}:${typeof callId === 'string' ? callId : ''}`
    const now = Date.now()
    const lastSeen = this._dedupMap.get(dedupKey)

    if (lastSeen !== undefined && now - lastSeen < DEDUP_WINDOW_MS) {
      console.debug(
        `[AgentEventBus] Duplicate event dropped (within ${DEDUP_WINDOW_MS}ms): ${dedupKey}`
      )
      return
    }
    this._dedupMap.set(dedupKey, now)

    // Write to circular replay buffer
    this._writeToBuffer(validated)

    // Notify type-specific handlers
    const handlers = this._handlers.get(validated.type)
    if (handlers && handlers.size > 0) {
      for (const handler of handlers) {
        try {
          handler(validated)
        } catch (err) {
          console.error(`[AgentEventBus] Handler threw for event "${validated.type}":`, err)
        }
      }
    }

    // Notify catch-all handlers
    if (this._anyHandlers.size > 0) {
      for (const handler of this._anyHandlers) {
        try {
          handler(validated)
        } catch (err) {
          console.error('[AgentEventBus] onAny handler threw:', err)
        }
      }
    }
  }

  /**
   * Dispatch a raw unknown payload.
   * Parses and validates before dispatching.
   * Useful for wiring directly to LiveKit's DataReceived callback.
   */
  dispatchRaw(raw: unknown): void {
    const event = parseAgentEvent(raw)
    if (event) this.dispatch(event)
  }

  // ---------------------------------------------------------------------------
  // 3e. Replay buffer
  // ---------------------------------------------------------------------------

  /**
   * Returns the last up-to-20 events in chronological order.
   */
  getReplayBuffer(): AgentEvent[] {
    if (this._replayCount < REPLAY_BUFFER_SIZE) {
      return this._replayBuffer.slice(0, this._replayCount)
    }
    // Unwrap the circular buffer into chronological order
    const tail = this._replayBuffer.slice(this._replayHead)
    const head = this._replayBuffer.slice(0, this._replayHead)
    return [...tail, ...head]
  }

  /**
   * Replay all buffered events to a handler in chronological order.
   * Intended for reconnect scenarios: new subscriber receives recent history.
   * Events are delivered synchronously; errors in the handler are caught and logged.
   */
  replayTo(handler: AnyEventHandler): void {
    const events = this.getReplayBuffer()
    for (const event of events) {
      try {
        handler(event)
      } catch (err) {
        console.error('[AgentEventBus] replayTo handler threw:', err)
      }
    }
  }

  // ---------------------------------------------------------------------------
  // 3f. Clear all state
  // ---------------------------------------------------------------------------

  /**
   * Remove all handlers, clear the dedup map, and empty the replay buffer.
   */
  clear(): void {
    this._handlers.clear()
    this._anyHandlers.clear()
    this._dedupMap.clear()
    this._replayBuffer.length = 0
    this._replayHead = 0
    this._replayCount = 0
  }

  // ---------------------------------------------------------------------------
  // Private helpers
  // ---------------------------------------------------------------------------

  private _writeToBuffer(event: AgentEvent): void {
    if (this._replayBuffer.length < REPLAY_BUFFER_SIZE) {
      this._replayBuffer.push(event)
      this._replayCount++
    } else {
      // Overwrite oldest slot
      this._replayBuffer[this._replayHead] = event
      this._replayHead = (this._replayHead + 1) % REPLAY_BUFFER_SIZE
    }
  }
}

// ---------------------------------------------------------------------------
// 4. Singleton export
// ---------------------------------------------------------------------------

/**
 * Application-wide singleton event bus.
 * Import this in any component or hook — do not instantiate AgentEventBus directly.
 */
export const agentEventBus = new AgentEventBus()
