// =============================================================================
// DemoRunner.tsx
// Floating "Start Demo" button that runs a scripted agent session through the
// agentEventBus without requiring LiveKit or URL params.
// =============================================================================

import { useRef, useState, useEffect, useCallback } from 'react'
import { agentEventBus } from '../lib/AgentEventBus'
import { useStore } from '../lib/store'

type DemoPhase = 'idle' | 'running' | 'done'

interface DemoStep {
  delayMs: number
  label: string
  event: Record<string, unknown>
}

// Hardcoded demo script — Full Agent Session (14 steps, ~10.5 s)
const DEMO_STEPS: DemoStep[] = [
  {
    delayMs: 0,
    label: 'Agent listening',
    event: { type: 'agent.state', state: 'listening' },
  },
  {
    delayMs: 800,
    label: 'User speaking',
    event: {
      type: 'transcript.user',
      text: "Can you send an email to Sarah about tomorrow's strategy meeting?",
      is_final: true,
    },
  },
  {
    delayMs: 1400,
    label: 'Agent thinking',
    event: { type: 'agent.state', state: 'thinking' },
  },
  {
    delayMs: 2200,
    label: 'Agent responding',
    event: {
      type: 'transcript.assistant',
      text: "Sure, I'll send Sarah an email about tomorrow's strategy meeting.",
    },
  },
  {
    delayMs: 2600,
    label: 'Agent speaking',
    event: { type: 'agent.state', state: 'speaking' },
  },
  {
    delayMs: 3200,
    label: 'Calling sendEmail',
    event: {
      type: 'tool.call',
      call_id: 'demo-tc-1',
      name: 'sendEmail',
      arguments: { to: 'sarah@example.com', subject: 'Strategy Meeting Tomorrow' },
      timestamp: 0, // filled at runtime
    },
  },
  {
    delayMs: 3600,
    label: 'Composio searching',
    event: {
      type: 'composio.searching',
      call_id: 'demo-tc-1',
      tool_slug: 'GMAIL_SEND_EMAIL',
      detail: 'Resolving tool…',
      timestamp: 0,
    },
  },
  {
    delayMs: 4200,
    label: 'Composio executing',
    event: {
      type: 'composio.executing',
      call_id: 'demo-tc-1',
      tool_slug: 'GMAIL_SEND_EMAIL',
      detail: 'Sending email…',
      timestamp: 0,
    },
  },
  {
    delayMs: 6800,
    label: 'Composio completed',
    event: {
      type: 'composio.completed',
      call_id: 'demo-tc-1',
      tool_slug: 'GMAIL_SEND_EMAIL',
      detail: 'Email sent',
      duration_ms: 3200,
      timestamp: 0,
    },
  },
  {
    delayMs: 7000,
    label: 'Tool result received',
    event: {
      type: 'tool_result',
      task_id: 'demo-task-1',
      call_id: 'demo-tc-1',
      tool_name: 'sendEmail',
      status: 'completed',
      result: 'Email sent successfully',
      error: '',
      duration_ms: 3200,
    },
  },
  {
    delayMs: 7400,
    label: 'Agent speaking',
    event: { type: 'agent.state', state: 'speaking' },
  },
  {
    delayMs: 7800,
    label: 'Agent confirms',
    event: {
      type: 'transcript.assistant',
      text: "Done! I've sent Sarah the email about the strategy meeting.",
    },
  },
  {
    delayMs: 9000,
    label: 'Agent listening',
    event: { type: 'agent.state', state: 'listening' },
  },
  {
    delayMs: 10500,
    label: 'Session complete',
    event: { type: 'agent.state', state: 'idle' },
  },
]

const TOTAL_STEPS = DEMO_STEPS.length

export function DemoRunner() {
  const [phase, setPhase] = useState<DemoPhase>('idle')
  const [currentStep, setCurrentStep] = useState(0)
  const timeoutIds = useRef<ReturnType<typeof setTimeout>[]>([])

  const clearAllTimeouts = useCallback(() => {
    timeoutIds.current.forEach((id) => clearTimeout(id))
    timeoutIds.current = []
  }, [])

  const stop = useCallback(() => {
    clearAllTimeouts()
    setPhase('idle')
    setCurrentStep(0)
  }, [clearAllTimeouts])

  const startDemo = useCallback(() => {
    clearAllTimeouts()
    useStore.getState().reset()
    setCurrentStep(0)
    setPhase('running')

    const startTime = Date.now()

    DEMO_STEPS.forEach((step, index) => {
      const id = setTimeout(() => {
        // Patch timestamps for events that need them
        const event = { ...step.event }
        if ('timestamp' in event && event.timestamp === 0) {
          event.timestamp = startTime + step.delayMs
        }

        agentEventBus.dispatchRaw(event)
        setCurrentStep(index + 1)

        // Mark done after the last step
        if (index === DEMO_STEPS.length - 1) {
          setPhase('done')
        }
      }, step.delayMs)

      timeoutIds.current.push(id)
    })
  }, [clearAllTimeouts])

  // Cleanup on unmount
  useEffect(() => {
    return () => clearAllTimeouts()
  }, [clearAllTimeouts])

  const stepLabel = phase === 'running' && currentStep < TOTAL_STEPS
    ? DEMO_STEPS[currentStep]?.label ?? ''
    : ''

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col items-end gap-1">
      {phase === 'running' && stepLabel && (
        <p className="text-[11px] text-gray-400 pr-1 transition-all duration-200">
          Step {currentStep + 1}/{TOTAL_STEPS} &middot; {stepLabel}
        </p>
      )}

      {phase === 'running' ? (
        <button
          onClick={stop}
          className="bg-black text-white rounded-full px-4 py-2 text-sm font-medium hover:bg-gray-800 transition-colors duration-150"
        >
          &#9632; Stop
        </button>
      ) : phase === 'done' ? (
        <button
          onClick={startDemo}
          className="bg-black text-white rounded-full px-4 py-2 text-sm font-medium hover:bg-gray-800 transition-colors duration-150"
        >
          &#8635; Replay
        </button>
      ) : (
        <button
          onClick={startDemo}
          className="bg-black text-white rounded-full px-4 py-2 text-sm font-medium hover:bg-gray-800 transition-colors duration-150"
        >
          &#9654; Start Demo
        </button>
      )}
    </div>
  )
}
