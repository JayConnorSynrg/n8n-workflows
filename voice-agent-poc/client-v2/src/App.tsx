import { useEffect, useRef, useState } from 'react'
import { WebGLOrb } from './components/WebGLOrb'
import { LiveWaveform } from './components/LiveWaveform'
import { TranscriptCycler } from './components/TranscriptCycler'
import { ToolCallPanel } from './components/ToolCallCard'
import { DevTestPanel } from './components/DevTestPanel'
import { SessionReplay } from './components/SessionReplay'
import { DemoRunner } from './components/DemoRunner'
import { useLiveKitAgent } from './hooks/useLiveKitAgent'
import { useStore } from './lib/store'
import { StatusIndicator } from './components/StatusIndicator'

// Extend Window interface for global readiness state
declare global {
  interface Window {
    voiceAgentReady: boolean
    voiceAgentStatus: {
      ready: boolean
      connected: boolean
      agentConnected: boolean
      audioReady: boolean
      error: string | null
      timestamp: number
    }
  }
}

// Mock data for local UI development
const MOCK_MESSAGES = [
  { id: 'msg-1', role: 'user' as const, content: 'Can you send an email to John about the meeting?', timestamp: Date.now() - 5000 },
  { id: 'msg-2', role: 'assistant' as const, content: 'I\'ll send that email to John right away.', timestamp: Date.now() - 3000 },
  { id: 'msg-3', role: 'user' as const, content: 'Also check the database for Q3 revenue.', timestamp: Date.now() - 1000 },
]

const MOCK_TOOL_CALLS = [
  { id: 'tc-1', name: 'sendEmail', status: 'completed' as const, timestamp: Date.now() - 4000 },
  { id: 'tc-2', name: 'queryDatabase', status: 'executing' as const, timestamp: Date.now() - 500 },
  { id: 'tc-3', name: 'listFiles', status: 'pending' as const, timestamp: Date.now() - 200 },
  { id: 'tc-4', name: 'searchDrive', status: 'completed' as const, timestamp: Date.now() - 6000 },
]

function App() {
  // Get URL parameters for LiveKit connection
  //   - livekit_url: LiveKit server URL (wss://...)
  //   - token: LiveKit room token (JWT)
  //   - mock: Enable mock mode for UI development
  const params = new URLSearchParams(window.location.search)
  const livekitUrl = params.get('livekit_url') || params.get('livekit')
  const livekitToken = params.get('token') || params.get('livekit_token')
  const mockMode = params.get('mock') === 'true'
  const hasConnectionParams = !!(livekitUrl && livekitToken) || mockMode

  // Dev test panel activation: ?devtest=1 OR localStorage.getItem('aio_dev_test') === 'true'
  const isDevTest = import.meta.env.DEV && (params.has('devtest') || localStorage.getItem('aio_dev_test') === 'true')

  // Replay panel activation: ?replay=<scriptId> (defaults to 'emailSend' if value is empty)
  const isReplay = params.has('replay')
  const replayScript = params.get('replay') ?? 'emailSend'

  // Track if we've signaled readiness
  const readinessSignaled = useRef(false)

  // Mock mode state cycling
  const [mockAgentState, setMockAgentState] = useState<'listening' | 'thinking' | 'speaking' | null>('speaking')
  const [mockVolume, setMockVolume] = useState(0.5)

  // Initialize LiveKit agent hook
  const agent = useLiveKitAgent()

  const {
    agentState,
    agentConnected,
    audioStatus,
    inputVolume,
    outputVolume,
    messages,
    toolCalls
  } = useStore()

  // Mock mode: cycle through states and animate volume
  useEffect(() => {
    if (!mockMode) return

    // Cycle agent states every 3 seconds
    const stateInterval = setInterval(() => {
      setMockAgentState(prev => {
        if (prev === 'listening') return 'thinking'
        if (prev === 'thinking') return 'speaking'
        if (prev === 'speaking') return 'listening'
        return 'listening'
      })
    }, 3000)

    // Animate volume smoothly
    const volumeInterval = setInterval(() => {
      setMockVolume(Math.random() * 0.7 + 0.3) // 0.3 - 1.0
    }, 100)

    return () => {
      clearInterval(stateInterval)
      clearInterval(volumeInterval)
    }
  }, [mockMode])

  // Connect to LiveKit when parameters are available
  useEffect(() => {
    if (mockMode) return // Skip in mock mode
    if (livekitUrl && livekitToken) {
      agent.connect(livekitUrl, livekitToken)
    }

    return () => {
      agent.disconnect()
    }
  }, [livekitUrl, livekitToken, mockMode])

  // Get connection status
  const { isConnected, isConnecting, error } = agent

  // Determine if fully ready (for Recall.ai signaling)
  const isFullyReady = isConnected && agentConnected

  // Update global readiness state for Recall.ai to check
  useEffect(() => {
    const isReady = isConnected && agentConnected && audioStatus === 'playing'

    // Update global status object (always)
    window.voiceAgentStatus = {
      ready: isReady,
      connected: isConnected,
      agentConnected: agentConnected,
      audioReady: audioStatus === 'playing',
      error: error,
      timestamp: Date.now()
    }

    // Update simple ready flag
    window.voiceAgentReady = isReady

    // Log readiness once when first achieved
    if (isReady && !readinessSignaled.current) {
      readinessSignaled.current = true

      // Comprehensive Recall.ai integration logging
      const integrationContext = {
        timestamp: Date.now(),
        inIframe: window !== window.parent,
        hasParentWindow: !!window.parent,
        userAgent: navigator.userAgent,
        windowLocation: window.location.href,
        status: window.voiceAgentStatus
      }

      if (import.meta.env.DEV) { console.log('🟢 VOICE_AGENT_READY - Page fully initialized', integrationContext) }

      // Dispatch custom event that Recall.ai can listen for
      window.dispatchEvent(new CustomEvent('voiceAgentReady', {
        detail: window.voiceAgentStatus
      }))

      // Log that event was dispatched
      if (import.meta.env.DEV) { console.log('[Recall.ai] voiceAgentReady event dispatched to window') }

      // FIX: Resilient postMessage with retry — handles transient iframe comm failures
      if (window !== window.parent) {
        const signalReadiness = (attempt = 0) => {
          try {
            window.parent.postMessage({
              type: 'voiceAgentReady',
              timestamp: Date.now(),
              payload: window.voiceAgentStatus
            }, '*')
            // Also set local flag immediately as confirmation
            window.voiceAgentReady = true
            if (import.meta.env.DEV) { console.log('[Recall.ai] Posted message to parent window (attempt', attempt + 1, ')') }
          } catch (e) {
            if (import.meta.env.DEV) { console.warn('[Recall.ai] Could not post to parent (attempt', attempt + 1, '):', e) }
            if (attempt < 3) {
              setTimeout(() => signalReadiness(attempt + 1), 500 * (attempt + 1))
            }
          }
        }
        signalReadiness()
      }
    }
  }, [isConnected, agentConnected, audioStatus, error])

  // ============================================================
  // RENDERING LOGIC
  // ============================================================

  // PRODUCTION: Always show full UI immediately
  // No instructions page - orb shows "Ready" until LiveKit connects

  // Use mock or real data based on mode
  const displayAgentState = mockMode ? mockAgentState : agentState
  const displayInputVolume = mockMode ? mockVolume : inputVolume
  const displayOutputVolume = mockMode ? mockVolume : outputVolume
  const displayMessages = mockMode ? MOCK_MESSAGES : messages
  // In mock mode, use store toolCalls if any exist (allows Playwright event injection);
  // fall back to MOCK_TOOL_CALLS only when store is empty
  const displayToolCalls = mockMode && toolCalls.length === 0 ? MOCK_TOOL_CALLS : toolCalls

  // Only pass output volume to orb when speaking (for bounce/ripple effect)
  const orbOutputVolume = displayAgentState === 'speaking' ? displayOutputVolume : 0

  // FULLY CONNECTED: Show complete UI - user sees "Ready" immediately
  // Layout: Orb → State Label → Transcript (center) → Waveform → Logo
  return (
    <div data-testid="app-root" className="min-h-screen bg-white flex flex-col items-center justify-center py-4 sm:py-6">

      {/* Mode badge - top left */}
      <div className="absolute top-3 left-3">
        <span className={`px-1.5 py-0.5 text-[10px] font-medium rounded-full ${mockMode ? 'bg-amber-500/20 text-amber-700' : 'bg-[#4EEAAA]/20 text-[#1A1A1A]'}`}>
          {mockMode ? 'Mock Mode' : 'AIO Live'}
        </span>
      </div>

      {/* Main content - vertical stack, all separated */}
      <div className="flex flex-col items-center gap-2 sm:gap-4 w-full max-w-2xl sm:max-w-3xl px-3 sm:px-6">

        {/* The Orb */}
        <div style={{ height: '140px', width: '140px' }}>
          <WebGLOrb
            agentState={displayAgentState}
            inputVolume={displayInputVolume}
            outputVolume={orbOutputVolume}
            isConnected={mockMode ? true : isConnected}
            size={140}
          />
        </div>

        {/* Agent state label - 25% smaller */}
        <div className="h-6 flex items-center justify-center">
          <p
            data-testid="agent-state-label"
            data-state={displayAgentState ?? 'idle'}
            className="text-xs font-medium text-gray-400 uppercase tracking-wider"
          >
            {displayAgentState === 'listening' && 'Listening...'}
            {displayAgentState === 'thinking' && 'Processing...'}
            {displayAgentState === 'speaking' && 'Speaking...'}
            {!displayAgentState && 'Ready'}
          </p>
        </div>

        {/* Connection and audio status indicators */}
        {!mockMode && (
          <div className="flex justify-center">
            <StatusIndicator
              isConnected={isConnected}
              isConnecting={isConnecting}
              agentConnected={agentConnected}
              audioStatus={audioStatus}
              error={error}
            />
          </div>
        )}

        {/* Transcript with Tool Call Panels on sides */}
        <div className="w-full flex items-center justify-center gap-6">
          {/* Left Tool Call Panel - flex centered with padding */}
          <div
            data-testid="tool-call-panel-left"
            className="flex items-center justify-end flex-shrink-0"
            style={{ minWidth: '152px' }}
          >
            <ToolCallPanel
              toolCalls={displayToolCalls}
              position="left"
              maxVisible={3}
            />
          </div>

          {/* Transcript Cycler - CENTER */}
          <div data-testid="transcript-cycler" className="flex-1 max-w-md min-w-0">
            <TranscriptCycler
              messages={displayMessages}
              toolCalls={displayToolCalls}
              maxVisible={6}
            />
          </div>

          {/* Right Tool Call Panel - flex centered with padding */}
          <div className="flex items-center justify-start flex-shrink-0" style={{ minWidth: '152px' }}>
            <ToolCallPanel
              toolCalls={displayToolCalls}
              position="right"
              maxVisible={3}
            />
          </div>
        </div>

        {/* Input waveform - synced to user's speech via inputVolume */}
        <div className="w-full max-w-sm h-9">
          <div style={{ opacity: displayAgentState === 'listening' ? 1 : 0, transition: 'opacity 0.3s' }}>
            <LiveWaveform
              active={displayAgentState === 'listening'}
              volume={displayInputVolume}
              barColor="rgba(78, 234, 170, 0.7)"
              height={36}
            />
          </div>
        </div>

        {/* Error display */}
        {error && !mockMode && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-xl">
            <p className="text-xs text-red-600">{error}</p>
          </div>
        )}

        {/* SYNRG branding - 25% smaller, in flow not absolute */}
        <div className="text-center mt-2">
          <img
            src="/synrg-logo.png"
            alt="SYNRG"
            className="h-8 w-auto mx-auto"
          />
          <p className="text-[10px] text-gray-400 mt-1 tracking-wider">
            VOICE ASSISTANT
          </p>
        </div>
      </div>

      {/* Dev stress-test panel — only active when ?devtest=1 or aio_dev_test=true in localStorage */}
      {isDevTest && <DevTestPanel />}

      {/* Session replay panel — only active when ?replay=<scriptId> is present in URL */}
      {isReplay && <SessionReplay initialScript={replayScript} />}

      {/* Demo runner — only in dev (excluded from production build) */}
      {import.meta.env.DEV && <DemoRunner />}
    </div>
  )
}

export default App
