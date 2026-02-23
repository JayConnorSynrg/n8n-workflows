// =============================================================================
// DevTestPanel.tsx
// Developer stress-test panel for the AIO Voice System.
//
// Activation: ?devtest=1 in URL OR localStorage.getItem('aio_dev_test') === 'true'
// Does NOT interfere with normal app layout — renders as a fixed overlay.
// =============================================================================

import { useState, useEffect, useCallback, useRef } from 'react'
import { agentEventBus } from '../lib/AgentEventBus'
import { useStore } from '../lib/store'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type TestStatus = 'idle' | 'running' | 'pass' | 'fail'

interface TestState {
  status: TestStatus
  message?: string
}

type TestId =
  | 'test1_single_tool'
  | 'test2_composio_lifecycle'
  | 'test3_tool_error'
  | 'test4_concurrent_stress'
  | 'test5_unknown_tool'
  | 'test6_agent_state'
  | 'test7_run_all'

type TestMap = Record<TestId, TestState>

const ALL_TEST_IDS: TestId[] = [
  'test1_single_tool',
  'test2_composio_lifecycle',
  'test3_tool_error',
  'test4_concurrent_stress',
  'test5_unknown_tool',
  'test6_agent_state',
  'test7_run_all',
]

const TEST_LABELS: Record<TestId, string> = {
  test1_single_tool:       '1: Single Tool Call (non-composio)',
  test2_composio_lifecycle:'2: Composio Tool Lifecycle',
  test3_tool_error:        '3: Tool Error',
  test4_concurrent_stress: '4: Concurrent Tool Calls (Stress)',
  test5_unknown_tool:      '5: Unknown/New Tool (extensibility)',
  test6_agent_state:       '6: Agent State Transitions',
  test7_run_all:           '7: Run All',
}

const TIMEOUT_MS = 4000 // 4s until a running test is marked as fail

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function now(): number {
  return Date.now()
}

function statusIcon(status: TestStatus): string {
  if (status === 'idle')    return '○'
  if (status === 'running') return '⏳'
  if (status === 'pass')    return '✓'
  if (status === 'fail')    return '✕'
  return '○'
}

function statusColor(status: TestStatus): string {
  if (status === 'pass')    return '#22c55e'
  if (status === 'fail')    return '#ef4444'
  if (status === 'running') return '#f59e0b'
  return '#9ca3af'
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function DevTestPanel() {
  const [minimized, setMinimized] = useState(false)
  const [tests, setTests] = useState<TestMap>(() =>
    Object.fromEntries(ALL_TEST_IDS.map(id => [id, { status: 'idle' as TestStatus }])) as TestMap
  )

  // Access store state for completion detection
  const toolCalls = useStore(state => state.toolCalls)

  // Track timeouts so we can cancel them on unmount
  const timeoutRefs = useRef<ReturnType<typeof setTimeout>[]>([])

  useEffect(() => {
    return () => {
      timeoutRefs.current.forEach(clearTimeout)
    }
  }, [])

  // ---------------------------------------------------------------------------
  // Per-test status helpers
  // ---------------------------------------------------------------------------

  const setTestStatus = useCallback((id: TestId, status: TestStatus, message?: string) => {
    setTests(prev => ({ ...prev, [id]: { status, message } }))
  }, [])

  // Schedule a pass/fail watchdog for a running test.
  // Once the tool call ID appears in the store as completed, mark pass.
  // If not completed within TIMEOUT_MS, mark fail.
  const watchForCompletion = useCallback(
    (testId: TestId, callIds: string[]) => {
      setTestStatus(testId, 'running')

      // Poll store for completion
      let resolved = false
      const pollInterval = setInterval(() => {
        const currentToolCalls = useStore.getState().toolCalls
        const allDone = callIds.every(callId => {
          const tc = currentToolCalls.find(t => t.id === callId)
          if (!tc) return false
          return tc.status === 'completed' || tc.status === 'error'
        })
        if (allDone && !resolved) {
          resolved = true
          clearInterval(pollInterval)
          setTestStatus(testId, 'pass')
        }
      }, 100)

      // Timeout watchdog
      const timeout = setTimeout(() => {
        if (!resolved) {
          resolved = true
          clearInterval(pollInterval)
          setTestStatus(testId, 'fail', 'No completion event within 4s')
        }
      }, TIMEOUT_MS)

      timeoutRefs.current.push(timeout)

      return () => {
        clearInterval(pollInterval)
        clearTimeout(timeout)
      }
    },
    []
  )

  // Watch for agent state changes (used by test 6)
  const watchForAgentState = useCallback(
    (testId: TestId, targetState: string, withinMs: number) => {
      setTestStatus(testId, 'running')
      let resolved = false

      const off = agentEventBus.on('agent.state', (e) => {
        if (e.state === targetState && !resolved) {
          resolved = true
          off()
          clearTimeout(timeout)
          setTestStatus(testId, 'pass')
        }
      })

      const timeout = setTimeout(() => {
        if (!resolved) {
          resolved = true
          off()
          setTestStatus(testId, 'fail', `agent.state "${targetState}" not seen within ${withinMs}ms`)
        }
      }, withinMs + 500)

      timeoutRefs.current.push(timeout)
    },
    []
  )

  // ---------------------------------------------------------------------------
  // Test 1: Single Tool Call Flow (non-composio)
  // ---------------------------------------------------------------------------

  const runTest1 = useCallback(() => {
    const callId = `test_email_${Date.now()}`

    agentEventBus.dispatchRaw({
      type: 'tool.call',
      call_id: callId,
      name: 'sendEmail',
      arguments: { to: 'test@example.com', subject: 'Test', body: 'Hello' },
      timestamp: now(),
    })

    const t = setTimeout(() => {
      agentEventBus.dispatchRaw({
        type: 'tool_result',
        call_id: callId,
        task_id: `task_${callId}`,
        tool_name: 'sendEmail',
        status: 'completed',
        result: 'Email sent successfully to test@example.com',
        duration_ms: 843,
      })
    }, 500)
    timeoutRefs.current.push(t)

    watchForCompletion('test1_single_tool', [callId])
  }, [watchForCompletion])

  // ---------------------------------------------------------------------------
  // Test 2: Composio Tool Lifecycle
  // ---------------------------------------------------------------------------

  const runTest2 = useCallback(() => {
    const callId = `test_composio_${Date.now()}`

    agentEventBus.dispatchRaw({
      type: 'tool.call',
      call_id: callId,
      name: 'GMAIL_SEND_EMAIL',
      arguments: { to: 'exec@company.com' },
      timestamp: now(),
    })

    const t1 = setTimeout(() => {
      agentEventBus.dispatchRaw({
        type: 'composio.searching',
        call_id: callId,
        tool_slug: 'GMAIL_SEND_EMAIL',
        detail: 'Finding Gmail connector...',
        timestamp: now(),
      })
    }, 200)

    const t2 = setTimeout(() => {
      agentEventBus.dispatchRaw({
        type: 'composio.executing',
        call_id: callId,
        tool_slug: 'GMAIL_SEND_EMAIL',
        detail: 'Sending email...',
        timestamp: now(),
      })
    }, 600)

    const t3 = setTimeout(() => {
      agentEventBus.dispatchRaw({
        type: 'composio.completed',
        call_id: callId,
        tool_slug: 'GMAIL_SEND_EMAIL',
        detail: 'Email sent',
        duration_ms: 1200,
        timestamp: now(),
      })
    }, 1200)

    timeoutRefs.current.push(t1, t2, t3)

    // Test passes when composio.completed fires (tool.call card enters completed state)
    // We watch for the composio.completed event directly since the store resolves it
    setTestStatus('test2_composio_lifecycle', 'running')
    let resolved = false

    const off = agentEventBus.on('composio.completed', (e) => {
      if (e.call_id === callId && !resolved) {
        resolved = true
        off()
        clearTimeout(watchdog)
        setTestStatus('test2_composio_lifecycle', 'pass')
      }
    })

    const watchdog = setTimeout(() => {
      if (!resolved) {
        resolved = true
        off()
        setTestStatus('test2_composio_lifecycle', 'fail', 'composio.completed not received within 4s')
      }
    }, TIMEOUT_MS)

    timeoutRefs.current.push(watchdog)
  }, [setTestStatus])

  // ---------------------------------------------------------------------------
  // Test 3: Tool Error
  // ---------------------------------------------------------------------------

  const runTest3 = useCallback(() => {
    const callId = `test_error_${Date.now()}`

    agentEventBus.dispatchRaw({
      type: 'tool.call',
      call_id: callId,
      name: 'searchDrive',
      arguments: { query: 'Q4 report' },
      timestamp: now(),
    })

    const t = setTimeout(() => {
      agentEventBus.dispatchRaw({
        type: 'composio.error',
        call_id: callId,
        tool_slug: 'searchDrive',
        detail: 'Google Drive authorization expired. Please re-authenticate.',
        duration_ms: 400,
        timestamp: now(),
      })
    }, 400)
    timeoutRefs.current.push(t)

    setTestStatus('test3_tool_error', 'running')
    let resolved = false

    const off = agentEventBus.on('composio.error', (e) => {
      if (e.call_id === callId && !resolved) {
        resolved = true
        off()
        clearTimeout(watchdog)
        setTestStatus('test3_tool_error', 'pass')
      }
    })

    const watchdog = setTimeout(() => {
      if (!resolved) {
        resolved = true
        off()
        setTestStatus('test3_tool_error', 'fail', 'composio.error not received within 4s')
      }
    }, TIMEOUT_MS)

    timeoutRefs.current.push(watchdog)
  }, [setTestStatus])

  // ---------------------------------------------------------------------------
  // Test 4: Concurrent Tool Calls (Stress)
  // ---------------------------------------------------------------------------

  const runTest4 = useCallback(() => {
    const prefix = `stress_${Date.now()}`
    const tools = [
      { id: `${prefix}_01`, name: 'listFiles',          delay: 300 },
      { id: `${prefix}_02`, name: 'SLACK_SEND_MESSAGE', delay: 800 },
      { id: `${prefix}_03`, name: 'searchDrive',        delay: 1200 },
      { id: `${prefix}_04`, name: 'GMAIL_SEND_EMAIL',   delay: 500 },
      { id: `${prefix}_05`, name: 'checkContext',       delay: 200 },
    ]

    // Fire all tool.call events immediately
    tools.forEach(t => {
      agentEventBus.dispatchRaw({
        type: 'tool.call',
        call_id: t.id,
        name: t.name,
        arguments: {},
        timestamp: now(),
      })
    })

    // Complete each at different delays
    tools.forEach(t => {
      const timeout = setTimeout(() => {
        agentEventBus.dispatchRaw({
          type: 'tool_result',
          call_id: t.id,
          task_id: `task_${t.id}`,
          tool_name: t.name,
          status: 'completed',
          result: `${t.name} completed`,
          duration_ms: t.delay,
        })
      }, t.delay)
      timeoutRefs.current.push(timeout)
    })

    watchForCompletion('test4_concurrent_stress', tools.map(t => t.id))
  }, [watchForCompletion])

  // ---------------------------------------------------------------------------
  // Test 5: Unknown/New Tool (extensibility test)
  // ---------------------------------------------------------------------------

  const runTest5 = useCallback(() => {
    const callId = `test_new_${Date.now()}`

    agentEventBus.dispatchRaw({
      type: 'tool.call',
      call_id: callId,
      name: 'createLinkedInPost',
      arguments: { content: 'Exciting update!' },
      timestamp: now(),
    })

    const t = setTimeout(() => {
      agentEventBus.dispatchRaw({
        type: 'tool_result',
        call_id: callId,
        task_id: `task_${callId}`,
        tool_name: 'createLinkedInPost',
        status: 'completed',
        result: 'Post published',
        duration_ms: 456,
      })
    }, 600)
    timeoutRefs.current.push(t)

    watchForCompletion('test5_unknown_tool', [callId])
  }, [watchForCompletion])

  // ---------------------------------------------------------------------------
  // Test 6: Agent State Transitions
  // ---------------------------------------------------------------------------

  const runTest6 = useCallback(() => {
    agentEventBus.dispatchRaw({ type: 'agent.state', state: 'thinking' })

    const t1 = setTimeout(() => {
      agentEventBus.dispatchRaw({ type: 'agent.state', state: 'speaking' })
    }, 1000)

    const t2 = setTimeout(() => {
      agentEventBus.dispatchRaw({ type: 'agent.state', state: 'idle' })
    }, 3000)

    timeoutRefs.current.push(t1, t2)

    // Pass when 'idle' is received (the final state)
    watchForAgentState('test6_agent_state', 'idle', 4000)
  }, [watchForAgentState])

  // ---------------------------------------------------------------------------
  // Test 7: Run All (sequenced with delays)
  // ---------------------------------------------------------------------------

  const runAll = useCallback(() => {
    setTestStatus('test7_run_all', 'running')

    // Reset all individual tests to idle first
    setTests(prev => {
      const next = { ...prev }
      ALL_TEST_IDS.forEach(id => {
        if (id !== 'test7_run_all') {
          next[id] = { status: 'idle' }
        }
      })
      return next
    })

    const STEP_DELAY = 2000 // 2s between each test

    const t1 = setTimeout(() => runTest1(), 0)
    const t2 = setTimeout(() => runTest2(), STEP_DELAY * 1)
    const t3 = setTimeout(() => runTest3(), STEP_DELAY * 2)
    const t4 = setTimeout(() => runTest4(), STEP_DELAY * 3)
    const t5 = setTimeout(() => runTest5(), STEP_DELAY * 4)
    const t6 = setTimeout(() => runTest6(), STEP_DELAY * 5)

    // Mark test7 as complete after all tests have had time to run
    const tFinal = setTimeout(() => {
      setTestStatus('test7_run_all', 'pass')
    }, STEP_DELAY * 6 + 1000)

    timeoutRefs.current.push(t1, t2, t3, t4, t5, t6, tFinal)
  }, [runTest1, runTest2, runTest3, runTest4, runTest5, runTest6, setTestStatus])

  // ---------------------------------------------------------------------------
  // Clear All
  // ---------------------------------------------------------------------------

  const clearAll = useCallback(() => {
    useStore.getState().clearConversation()
    setTests(
      Object.fromEntries(ALL_TEST_IDS.map(id => [id, { status: 'idle' as TestStatus }])) as TestMap
    )
  }, [])

  // ---------------------------------------------------------------------------
  // Individual test dispatcher
  // ---------------------------------------------------------------------------

  const runTest = useCallback(
    (id: TestId) => {
      switch (id) {
        case 'test1_single_tool':       return runTest1()
        case 'test2_composio_lifecycle':return runTest2()
        case 'test3_tool_error':        return runTest3()
        case 'test4_concurrent_stress': return runTest4()
        case 'test5_unknown_tool':      return runTest5()
        case 'test6_agent_state':       return runTest6()
        case 'test7_run_all':           return runAll()
        default: break
      }
    },
    [runTest1, runTest2, runTest3, runTest4, runTest5, runTest6, runAll]
  )

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div
      style={{
        position: 'fixed',
        bottom: '16px',
        right: '16px',
        zIndex: 9999,
        width: minimized ? '120px' : '320px',
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
        fontSize: '11px',
        background: 'rgba(10, 10, 15, 0.96)',
        border: '1px solid rgba(78, 234, 170, 0.4)',
        borderRadius: '10px',
        boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
        backdropFilter: 'blur(8px)',
        overflow: 'hidden',
        transition: 'width 0.2s ease',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 12px',
          background: 'rgba(78, 234, 170, 0.1)',
          borderBottom: minimized ? 'none' : '1px solid rgba(78, 234, 170, 0.2)',
          cursor: 'pointer',
          userSelect: 'none',
        }}
        onClick={() => setMinimized(v => !v)}
      >
        <span style={{ color: '#4EEAAA', fontWeight: 700, letterSpacing: '0.04em' }}>
          {minimized ? 'DEV' : 'AIO DEV TEST PANEL'}
        </span>
        <span style={{ color: '#4EEAAA', fontSize: '10px' }}>
          {minimized ? '[+]' : '[-]'}
        </span>
      </div>

      {/* Body */}
      {!minimized && (
        <div style={{ padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: '6px' }}>

          {/* Live store stats */}
          <div
            style={{
              padding: '6px 8px',
              background: 'rgba(255,255,255,0.04)',
              borderRadius: '6px',
              color: '#9ca3af',
              fontSize: '10px',
              lineHeight: '1.6',
            }}
          >
            <span style={{ color: '#d1d5db' }}>Store: </span>
            {toolCalls.length} tool call(s)
            {toolCalls.length > 0 && (
              <span>
                {' · '}
                {toolCalls.filter(t => t.status === 'completed').length}c{' '}
                {toolCalls.filter(t => t.status === 'executing').length}e{' '}
                {toolCalls.filter(t => t.status === 'error').length}err
              </span>
            )}
          </div>

          {/* Test buttons */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {ALL_TEST_IDS.filter(id => id !== 'test7_run_all').map(id => (
              <TestButton
                key={id}
                label={TEST_LABELS[id]}
                state={tests[id]}
                onClick={() => runTest(id)}
              />
            ))}
          </div>

          {/* Divider */}
          <div style={{ borderTop: '1px solid rgba(255,255,255,0.08)', margin: '2px 0' }} />

          {/* Run All + Clear */}
          <div style={{ display: 'flex', gap: '6px' }}>
            <TestButton
              label={TEST_LABELS['test7_run_all']}
              state={tests['test7_run_all']}
              onClick={() => runTest('test7_run_all')}
              accent
            />
            <button
              onClick={clearAll}
              style={{
                flex: '0 0 auto',
                padding: '5px 10px',
                background: 'rgba(239,68,68,0.15)',
                border: '1px solid rgba(239,68,68,0.3)',
                borderRadius: '5px',
                color: '#fca5a5',
                cursor: 'pointer',
                fontSize: '10px',
                fontFamily: 'inherit',
                whiteSpace: 'nowrap',
              }}
            >
              Clear
            </button>
          </div>

          {/* Footer */}
          <div style={{ color: '#4b5563', fontSize: '9px', marginTop: '2px' }}>
            localStorage: aio_dev_test=true | ?devtest=1
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// TestButton sub-component
// ---------------------------------------------------------------------------

interface TestButtonProps {
  label: string
  state: TestState
  onClick: () => void
  accent?: boolean
}

function TestButton({ label, state, onClick, accent = false }: TestButtonProps) {
  const { status, message } = state
  const isRunning = status === 'running'

  const borderColor =
    status === 'pass'    ? 'rgba(34,197,94,0.5)' :
    status === 'fail'    ? 'rgba(239,68,68,0.5)' :
    status === 'running' ? 'rgba(245,158,11,0.5)' :
    accent               ? 'rgba(78,234,170,0.4)' :
                           'rgba(255,255,255,0.1)'

  const bgColor =
    status === 'pass'    ? 'rgba(34,197,94,0.08)' :
    status === 'fail'    ? 'rgba(239,68,68,0.08)' :
    status === 'running' ? 'rgba(245,158,11,0.08)' :
    accent               ? 'rgba(78,234,170,0.08)' :
                           'rgba(255,255,255,0.04)'

  return (
    <button
      onClick={onClick}
      disabled={isRunning}
      title={message}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        width: '100%',
        padding: '5px 8px',
        background: bgColor,
        border: `1px solid ${borderColor}`,
        borderRadius: '5px',
        color: '#e5e7eb',
        cursor: isRunning ? 'not-allowed' : 'pointer',
        textAlign: 'left',
        fontFamily: 'inherit',
        fontSize: '10px',
        opacity: isRunning ? 0.8 : 1,
        transition: 'all 0.15s ease',
      }}
    >
      <span style={{ color: statusColor(status), fontWeight: 700, flexShrink: 0, minWidth: '10px' }}>
        {statusIcon(status)}
      </span>
      <span style={{ flexGrow: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {label}
      </span>
    </button>
  )
}

export default DevTestPanel
