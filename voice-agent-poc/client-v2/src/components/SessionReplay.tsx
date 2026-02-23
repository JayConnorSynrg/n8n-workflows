// =============================================================================
// SessionReplay.tsx
// Visual session replay panel for the AIO Voice System.
// Fires pre-scripted agent events into the live event bus so all UI components
// react as they would during a real session.
//
// Activation: append ?replay=<scriptId> to the app URL.
// =============================================================================

import { useState, useEffect, useRef, useCallback } from 'react'
import { agentEventBus } from '../lib/AgentEventBus'
import { useStore } from '../lib/store'
import { SESSION_SCRIPTS, SESSION_SCRIPTS_BY_ID, SessionScript, ScriptStep } from '../lib/sessionScripts'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ReplaySpeed = 0.5 | 1 | 1.5 | 2
type ReplayStatus = 'idle' | 'playing' | 'paused' | 'complete'

interface LogEntry {
  stepIndex: number
  timeMs: number
  label: string
  phase?: ScriptStep['phase']
  eventType: string
}

interface SessionReplayProps {
  initialScript?: string
}

// ---------------------------------------------------------------------------
// Phase badge config
// ---------------------------------------------------------------------------

const PHASE_CONFIG: Record<
  NonNullable<ScriptStep['phase']>,
  { label: string; bg: string; text: string }
> = {
  connect:    { label: 'CONNECT',    bg: 'bg-gray-600',   text: 'text-gray-100' },
  listening:  { label: 'LISTEN',     bg: 'bg-green-700',  text: 'text-green-100' },
  thinking:   { label: 'THINK',      bg: 'bg-amber-600',  text: 'text-amber-100' },
  tool:       { label: 'TOOL',       bg: 'bg-blue-700',   text: 'text-blue-100' },
  responding: { label: 'RESPOND',    bg: 'bg-purple-700', text: 'text-purple-100' },
  complete:   { label: 'DONE',       bg: 'bg-teal-700',   text: 'text-teal-100' },
}

const DEFAULT_PHASE_CONFIG = { label: 'EVENT', bg: 'bg-gray-700', text: 'text-gray-100' }

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTime(ms: number): string {
  return (ms / 1000).toFixed(1) + 's'
}

function resolveScript(scriptId: string | undefined): SessionScript {
  if (scriptId && SESSION_SCRIPTS_BY_ID[scriptId]) {
    return SESSION_SCRIPTS_BY_ID[scriptId]
  }
  return SESSION_SCRIPTS[0]
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SessionReplay({ initialScript }: SessionReplayProps) {
  const [selectedScript, setSelectedScript] = useState<SessionScript>(
    () => resolveScript(initialScript)
  )
  const [status, setStatus] = useState<ReplayStatus>('idle')
  const [speed, setSpeed] = useState<ReplaySpeed>(1)
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(0)
  const [log, setLog] = useState<LogEntry[]>([])

  // Refs for imperative control — avoids stale closure issues in timeouts
  const timeoutRefs = useRef<ReturnType<typeof setTimeout>[]>([])
  const logEndRef = useRef<HTMLDivElement>(null)
  const statusRef = useRef<ReplayStatus>('idle')

  // Keep statusRef in sync
  useEffect(() => {
    statusRef.current = status
  }, [status])

  // Auto-scroll log to bottom on new entries
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [log])

  // ---------------------------------------------------------------------------
  // Cancel all pending timeouts
  // ---------------------------------------------------------------------------

  const cancelAllTimeouts = useCallback(() => {
    for (const id of timeoutRefs.current) {
      clearTimeout(id)
    }
    timeoutRefs.current = []
  }, [])

  // ---------------------------------------------------------------------------
  // Core play logic — schedules all steps as timeouts adjusted by speed
  // ---------------------------------------------------------------------------

  const scheduleSteps = useCallback(
    (script: SessionScript, speedMultiplier: ReplaySpeed, fromStepIndex = 0) => {
      const steps = script.steps

      // Compute the base offset — the delay of the first step to play
      const baseDelay = fromStepIndex > 0 ? steps[fromStepIndex].delay : 0

      for (let i = fromStepIndex; i < steps.length; i++) {
        const step = steps[i]
        const adjustedDelay = (step.delay - baseDelay) / speedMultiplier

        const id = setTimeout(() => {
          // Guard: if paused or reset, do not fire
          if (statusRef.current !== 'playing') return

          // Inject the event into the live event bus
          agentEventBus.dispatchRaw({ ...step.event, timestamp: Date.now() })

          // Update UI state
          setCurrentStepIndex(i)
          setLog(prev => [
            ...prev,
            {
              stepIndex: i,
              timeMs: step.delay,
              label: step.label,
              phase: step.phase,
              eventType: String(step.event.type ?? 'unknown'),
            },
          ])

          // Mark complete after final step
          if (i === steps.length - 1) {
            setStatus('complete')
          }
        }, adjustedDelay)

        timeoutRefs.current.push(id)
      }
    },
    []
  )

  // ---------------------------------------------------------------------------
  // Controls
  // ---------------------------------------------------------------------------

  const handlePlay = useCallback(() => {
    if (status === 'playing') return

    if (status === 'complete' || status === 'idle') {
      // Fresh start — reset store and log first
      useStore.getState().reset()
      setLog([])
      setCurrentStepIndex(0)
      setStatus('playing')
      scheduleSteps(selectedScript, speed, 0)
    } else if (status === 'paused') {
      // Resume from current step
      setStatus('playing')
      scheduleSteps(selectedScript, speed, currentStepIndex)
    }
  }, [status, selectedScript, speed, currentStepIndex, scheduleSteps])

  const handlePause = useCallback(() => {
    if (status !== 'playing') return
    cancelAllTimeouts()
    setStatus('paused')
  }, [status, cancelAllTimeouts])

  const handleRestart = useCallback(() => {
    cancelAllTimeouts()
    useStore.getState().reset()
    setLog([])
    setCurrentStepIndex(0)
    setStatus('playing')
    scheduleSteps(selectedScript, speed, 0)
  }, [cancelAllTimeouts, selectedScript, speed, scheduleSteps])

  // Clean up on unmount
  useEffect(() => {
    return () => {
      cancelAllTimeouts()
    }
  }, [cancelAllTimeouts])

  // ---------------------------------------------------------------------------
  // Script change — reset replay
  // ---------------------------------------------------------------------------

  const handleScriptChange = useCallback(
    (scriptId: string) => {
      cancelAllTimeouts()
      useStore.getState().reset()
      setLog([])
      setCurrentStepIndex(0)
      setStatus('idle')
      setSelectedScript(resolveScript(scriptId))
    },
    [cancelAllTimeouts]
  )

  // ---------------------------------------------------------------------------
  // Speed change — if playing, restart from current step at new speed
  // ---------------------------------------------------------------------------

  const handleSpeedChange = useCallback(
    (newSpeed: ReplaySpeed) => {
      setSpeed(newSpeed)
      if (status === 'playing') {
        cancelAllTimeouts()
        scheduleSteps(selectedScript, newSpeed, currentStepIndex)
      }
    },
    [status, currentStepIndex, selectedScript, cancelAllTimeouts, scheduleSteps]
  )

  // ---------------------------------------------------------------------------
  // Derived display values
  // ---------------------------------------------------------------------------

  const totalSteps = selectedScript.steps.length
  const progressRatio = totalSteps > 1 ? currentStepIndex / (totalSteps - 1) : 0
  const currentStep = selectedScript.steps[currentStepIndex]

  const statusLabel = {
    idle: 'Ready',
    playing: 'Playing',
    paused: 'Paused',
    complete: 'Complete',
  }[status]

  const statusDot = {
    idle: 'bg-gray-500',
    playing: 'bg-green-400',
    paused: 'bg-amber-400',
    complete: 'bg-teal-400',
  }[status]

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div
      data-testid="session-replay-panel"
      className="fixed bottom-0 right-0 w-80 max-h-96 flex flex-col bg-gray-900 text-white rounded-tl-xl shadow-2xl z-50 overflow-hidden border border-gray-700"
      style={{ fontFamily: 'monospace' }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-gray-800 border-b border-gray-700 flex-shrink-0">
        <div className="flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full ${statusDot} ${status === 'playing' ? 'animate-pulse' : ''}`}
          />
          <span className="text-[10px] font-bold tracking-widest text-gray-300 uppercase">
            AIO SESSION REPLAY
          </span>
        </div>
        <span className="text-[9px] text-gray-500 uppercase tracking-wider">{statusLabel}</span>
      </div>

      {/* Script selector + controls */}
      <div className="px-3 py-2 bg-gray-850 border-b border-gray-700 flex-shrink-0 space-y-2">
        {/* Script dropdown */}
        <select
          data-testid="replay-script-select"
          value={selectedScript.id}
          onChange={e => handleScriptChange(e.target.value)}
          className="w-full text-[10px] bg-gray-800 text-gray-200 border border-gray-600 rounded px-2 py-1 focus:outline-none focus:border-teal-500"
        >
          {SESSION_SCRIPTS.map(script => (
            <option key={script.id} value={script.id}>
              {script.name}
            </option>
          ))}
        </select>

        {/* Control row */}
        <div className="flex items-center gap-1.5">
          {/* Play */}
          <button
            data-testid="replay-play-btn"
            onClick={handlePlay}
            disabled={status === 'playing'}
            className="flex items-center justify-center w-7 h-7 rounded bg-green-700 hover:bg-green-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-xs"
            title="Play"
          >
            &#9654;
          </button>

          {/* Pause */}
          <button
            data-testid="replay-pause-btn"
            onClick={handlePause}
            disabled={status !== 'playing'}
            className="flex items-center justify-center w-7 h-7 rounded bg-amber-700 hover:bg-amber-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-[9px] font-bold"
            title="Pause"
          >
            &#9646;&#9646;
          </button>

          {/* Restart */}
          <button
            data-testid="replay-restart-btn"
            onClick={handleRestart}
            disabled={status === 'idle'}
            className="flex items-center justify-center w-7 h-7 rounded bg-gray-700 hover:bg-gray-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-[10px]"
            title="Restart"
          >
            &#8635;
          </button>

          {/* Speed selector */}
          <div className="ml-auto flex items-center gap-1">
            {([0.5, 1, 1.5, 2] as ReplaySpeed[]).map(s => (
              <button
                key={s}
                onClick={() => handleSpeedChange(s)}
                className={`text-[9px] px-1.5 py-0.5 rounded transition-colors ${
                  speed === s
                    ? 'bg-teal-600 text-white'
                    : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                }`}
              >
                {s}x
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Progress bar + step label */}
      <div className="px-3 py-2 bg-gray-900 border-b border-gray-700 flex-shrink-0 space-y-1">
        <div
          data-testid="replay-progress"
          data-progress={`${currentStepIndex}/${totalSteps}`}
          className="relative w-full h-1.5 bg-gray-700 rounded-full overflow-hidden"
        >
          <div
            className="h-full bg-teal-500 transition-all duration-300 rounded-full"
            style={{ width: `${progressRatio * 100}%` }}
          />
        </div>
        <div className="flex items-center justify-between">
          <span
            data-testid="replay-step-label"
            className="text-[9px] text-gray-400 truncate flex-1 mr-2"
          >
            {status === 'idle'
              ? selectedScript.description
              : currentStep?.label ?? 'Ready'}
          </span>
          <span className="text-[9px] text-gray-600 flex-shrink-0">
            {currentStepIndex + 1}/{totalSteps}
          </span>
        </div>
      </div>

      {/* Event log */}
      <div
        data-testid="replay-log"
        className="flex-1 overflow-y-auto px-2 py-1.5 space-y-0.5 min-h-0"
        style={{ maxHeight: '160px' }}
      >
        {log.length === 0 ? (
          <div className="text-[9px] text-gray-600 italic text-center py-3">
            Press play to start the session replay
          </div>
        ) : (
          log.map((entry, idx) => {
            const phaseConf = entry.phase
              ? PHASE_CONFIG[entry.phase]
              : DEFAULT_PHASE_CONFIG
            return (
              <div
                key={`${entry.stepIndex}-${idx}`}
                className="flex items-start gap-1.5 text-[9px] leading-tight"
              >
                {/* Time */}
                <span className="text-gray-600 flex-shrink-0 w-8 text-right">
                  {formatTime(entry.timeMs)}
                </span>
                {/* Phase badge */}
                <span
                  className={`${phaseConf.bg} ${phaseConf.text} rounded px-1 py-0.5 flex-shrink-0 text-[8px] font-bold tracking-wide`}
                >
                  {phaseConf.label}
                </span>
                {/* Label */}
                <span className="text-gray-300 leading-tight">{entry.label}</span>
              </div>
            )
          })
        )}
        <div ref={logEndRef} />
      </div>
    </div>
  )
}
