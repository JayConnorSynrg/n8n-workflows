// =============================================================================
// AgentEventSchema.ts
// Runtime event validation for all 13 AIO Voice Agent event types.
// No external dependencies — pure TypeScript type guards.
// =============================================================================

// ---------------------------------------------------------------------------
// 1. TypeScript interfaces (static types)
// ---------------------------------------------------------------------------

export interface AgentStateEvent {
  type: 'agent.state'
  state: 'listening' | 'thinking' | 'speaking' | 'idle'
}

export interface TranscriptUserEvent {
  type: 'transcript.user'
  text: string
  is_final: boolean
}

export interface TranscriptAssistantEvent {
  type: 'transcript.assistant'
  text: string
}

export interface ToolCallEvent {
  type: 'tool.call'
  call_id: string
  name: string
  arguments: Record<string, unknown>
  timestamp: number
}

export interface ToolExecutingEvent {
  type: 'tool.executing'
  call_id: string
  timestamp: number
}

export interface ToolCompletedEvent {
  type: 'tool.completed'
  call_id: string
  result: string
  timestamp: number
}

export interface ToolErrorEvent {
  type: 'tool.error'
  call_id: string
  error: string
  timestamp: number
}

export interface ToolResultEvent {
  type: 'tool_result'
  task_id: string
  call_id: string
  tool_name: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  result?: string
  error?: string
  duration_ms: number
}

export interface ComposioSearchingEvent {
  type: 'composio.searching'
  call_id: string
  tool_slug: string
  detail: string
  timestamp: number
}

export interface ComposioExecutingEvent {
  type: 'composio.executing'
  call_id: string
  tool_slug: string
  detail: string
  timestamp: number
}

export interface ComposioCompletedEvent {
  type: 'composio.completed'
  call_id: string
  tool_slug: string
  detail: string
  duration_ms: number
  timestamp: number
}

export interface ComposioErrorEvent {
  type: 'composio.error'
  call_id: string
  tool_slug: string
  detail: string
  duration_ms: number
  timestamp: number
}

export interface ErrorEvent {
  type: 'error'
  message: string
  code?: string
  severity?: 'low' | 'medium' | 'high' | 'critical'
}

/** Discriminated union of all 13 agent event types. */
export type AgentEvent =
  | AgentStateEvent
  | TranscriptUserEvent
  | TranscriptAssistantEvent
  | ToolCallEvent
  | ToolExecutingEvent
  | ToolCompletedEvent
  | ToolErrorEvent
  | ToolResultEvent
  | ComposioSearchingEvent
  | ComposioExecutingEvent
  | ComposioCompletedEvent
  | ComposioErrorEvent
  | ErrorEvent

// ---------------------------------------------------------------------------
// 2. Primitive validators (internal helpers)
// ---------------------------------------------------------------------------

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

function isString(v: unknown): v is string {
  return typeof v === 'string'
}

function isNumber(v: unknown): v is number {
  return typeof v === 'number' && !Number.isNaN(v)
}

function isBoolean(v: unknown): v is boolean {
  return typeof v === 'boolean'
}

function isStringRecord(v: unknown): v is Record<string, unknown> {
  return isObject(v)
}

function isOneOf<T extends string>(v: unknown, allowed: readonly T[]): v is T {
  return isString(v) && (allowed as readonly string[]).includes(v)
}

// ---------------------------------------------------------------------------
// 3. Per-event-type guards (the "schemas")
// ---------------------------------------------------------------------------

export function isAgentStateEvent(v: unknown): v is AgentStateEvent {
  if (!isObject(v) || v['type'] !== 'agent.state') return false
  return isOneOf(v['state'], ['listening', 'thinking', 'speaking', 'idle'])
}

export function isTranscriptUserEvent(v: unknown): v is TranscriptUserEvent {
  if (!isObject(v) || v['type'] !== 'transcript.user') return false
  return isString(v['text']) && isBoolean(v['is_final'])
}

export function isTranscriptAssistantEvent(v: unknown): v is TranscriptAssistantEvent {
  if (!isObject(v) || v['type'] !== 'transcript.assistant') return false
  return isString(v['text'])
}

export function isToolCallEvent(v: unknown): v is ToolCallEvent {
  if (!isObject(v) || v['type'] !== 'tool.call') return false
  return (
    isString(v['call_id']) &&
    isString(v['name']) &&
    isStringRecord(v['arguments']) &&
    isNumber(v['timestamp'])
  )
}

export function isToolExecutingEvent(v: unknown): v is ToolExecutingEvent {
  if (!isObject(v) || v['type'] !== 'tool.executing') return false
  return isString(v['call_id']) && isNumber(v['timestamp'])
}

export function isToolCompletedEvent(v: unknown): v is ToolCompletedEvent {
  if (!isObject(v) || v['type'] !== 'tool.completed') return false
  return (
    isString(v['call_id']) &&
    isString(v['result']) &&
    isNumber(v['timestamp'])
  )
}

export function isToolErrorEvent(v: unknown): v is ToolErrorEvent {
  if (!isObject(v) || v['type'] !== 'tool.error') return false
  return (
    isString(v['call_id']) &&
    isString(v['error']) &&
    isNumber(v['timestamp'])
  )
}

export function isToolResultEvent(v: unknown): v is ToolResultEvent {
  if (!isObject(v) || v['type'] !== 'tool_result') return false
  const validStatus = ['pending', 'running', 'completed', 'failed'] as const
  return (
    isString(v['task_id']) &&
    isString(v['call_id']) &&
    isString(v['tool_name']) &&
    isOneOf(v['status'], validStatus) &&
    isNumber(v['duration_ms']) &&
    (v['result'] === undefined || isString(v['result'])) &&
    (v['error'] === undefined || isString(v['error']))
  )
}

export function isComposioSearchingEvent(v: unknown): v is ComposioSearchingEvent {
  if (!isObject(v) || v['type'] !== 'composio.searching') return false
  return (
    isString(v['call_id']) &&
    isString(v['tool_slug']) &&
    isString(v['detail']) &&
    isNumber(v['timestamp'])
  )
}

export function isComposioExecutingEvent(v: unknown): v is ComposioExecutingEvent {
  if (!isObject(v) || v['type'] !== 'composio.executing') return false
  return (
    isString(v['call_id']) &&
    isString(v['tool_slug']) &&
    isString(v['detail']) &&
    isNumber(v['timestamp'])
  )
}

export function isComposioCompletedEvent(v: unknown): v is ComposioCompletedEvent {
  if (!isObject(v) || v['type'] !== 'composio.completed') return false
  return (
    isString(v['call_id']) &&
    isString(v['tool_slug']) &&
    isString(v['detail']) &&
    isNumber(v['duration_ms']) &&
    isNumber(v['timestamp'])
  )
}

export function isComposioErrorEvent(v: unknown): v is ComposioErrorEvent {
  if (!isObject(v) || v['type'] !== 'composio.error') return false
  return (
    isString(v['call_id']) &&
    isString(v['tool_slug']) &&
    isString(v['detail']) &&
    isNumber(v['duration_ms']) &&
    isNumber(v['timestamp'])
  )
}

export function isErrorEvent(v: unknown): v is ErrorEvent {
  if (!isObject(v) || v['type'] !== 'error') return false
  const validSeverity = ['low', 'medium', 'high', 'critical'] as const
  return (
    isString(v['message']) &&
    (v['code'] === undefined || isString(v['code'])) &&
    (v['severity'] === undefined || isOneOf(v['severity'], validSeverity))
  )
}

// ---------------------------------------------------------------------------
// 4. Ordered validator registry (fast path: check type string first)
// ---------------------------------------------------------------------------

type GuardEntry = {
  type: AgentEvent['type']
  guard: (v: unknown) => v is AgentEvent
}

const EVENT_GUARDS: GuardEntry[] = [
  { type: 'agent.state',           guard: isAgentStateEvent as (v: unknown) => v is AgentEvent },
  { type: 'transcript.user',       guard: isTranscriptUserEvent as (v: unknown) => v is AgentEvent },
  { type: 'transcript.assistant',  guard: isTranscriptAssistantEvent as (v: unknown) => v is AgentEvent },
  { type: 'tool.call',             guard: isToolCallEvent as (v: unknown) => v is AgentEvent },
  { type: 'tool.executing',        guard: isToolExecutingEvent as (v: unknown) => v is AgentEvent },
  { type: 'tool.completed',        guard: isToolCompletedEvent as (v: unknown) => v is AgentEvent },
  { type: 'tool.error',            guard: isToolErrorEvent as (v: unknown) => v is AgentEvent },
  { type: 'tool_result',           guard: isToolResultEvent as (v: unknown) => v is AgentEvent },
  { type: 'composio.searching',    guard: isComposioSearchingEvent as (v: unknown) => v is AgentEvent },
  { type: 'composio.executing',    guard: isComposioExecutingEvent as (v: unknown) => v is AgentEvent },
  { type: 'composio.completed',    guard: isComposioCompletedEvent as (v: unknown) => v is AgentEvent },
  { type: 'composio.error',        guard: isComposioErrorEvent as (v: unknown) => v is AgentEvent },
  { type: 'error',                 guard: isErrorEvent as (v: unknown) => v is AgentEvent },
]

// Build a Map for O(1) type dispatch
const GUARD_MAP = new Map<string, (v: unknown) => v is AgentEvent>(
  EVENT_GUARDS.map(({ type, guard }) => [type, guard])
)

// ---------------------------------------------------------------------------
// 5. parseAgentEvent — the main public API
// ---------------------------------------------------------------------------

/**
 * Validates and narrows `raw` to `AgentEvent`.
 * Returns `null` if the payload is structurally invalid or the type is unknown.
 * Logs a console.warn on failure to aid runtime debugging.
 */
export function parseAgentEvent(raw: unknown): AgentEvent | null {
  if (!isObject(raw)) {
    console.warn('[AgentEventSchema] parseAgentEvent: payload is not an object', raw)
    return null
  }

  const eventType = raw['type']
  if (!isString(eventType)) {
    console.warn('[AgentEventSchema] parseAgentEvent: missing or non-string "type" field', raw)
    return null
  }

  const guard = GUARD_MAP.get(eventType)
  if (!guard) {
    // Unknown type — not a validation error, just an unrecognised event.
    // Use debug level so it doesn't pollute production logs.
    console.debug('[AgentEventSchema] parseAgentEvent: unknown event type', eventType)
    return null
  }

  if (!guard(raw)) {
    console.warn(
      `[AgentEventSchema] parseAgentEvent: invalid shape for event type "${eventType}"`,
      raw
    )
    return null
  }

  return raw
}

// ---------------------------------------------------------------------------
// 6. Type predicate for the union (useful in generic contexts)
// ---------------------------------------------------------------------------

export function isAgentEvent(v: unknown): v is AgentEvent {
  return parseAgentEvent(v) !== null
}
