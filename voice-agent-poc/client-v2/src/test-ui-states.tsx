import { useState, useEffect } from 'react'
import { WebGLOrb } from './components/WebGLOrb'
import { LiveWaveform } from './components/LiveWaveform'
import { TranscriptCycler } from './components/TranscriptCycler'
import { ToolCallPanel } from './components/ToolCallCard'

type AgentState = 'listening' | 'thinking' | 'speaking' | null

interface TestScenario {
  name: string
  agentState: AgentState
  isConnected: boolean
  inputVolume: number
  outputVolume: number
  toolCalls: Array<{
    id: string
    name: string
    status: 'pending' | 'executing' | 'completed' | 'error'
    timestamp: number
  }>
  messages: Array<{
    id: string
    role: 'user' | 'assistant'
    content: string
    timestamp: number
  }>
  duration: number // ms to show this state
}

const TEST_SCENARIOS: TestScenario[] = [
  {
    name: 'IDLE - Ready State',
    agentState: null,
    isConnected: true,
    inputVolume: 0,
    outputVolume: 0,
    toolCalls: [],
    messages: [],
    duration: 2000,
  },
  {
    name: 'CONNECTING - Not Connected',
    agentState: null,
    isConnected: false,
    inputVolume: 0,
    outputVolume: 0,
    toolCalls: [],
    messages: [],
    duration: 2000,
  },
  {
    name: 'LISTENING - Low Volume',
    agentState: 'listening',
    isConnected: true,
    inputVolume: 0.2,
    outputVolume: 0,
    toolCalls: [],
    messages: [
      { id: 'msg-1', role: 'user', content: 'Hello...', timestamp: Date.now() },
    ],
    duration: 2000,
  },
  {
    name: 'LISTENING - High Volume',
    agentState: 'listening',
    isConnected: true,
    inputVolume: 0.85,
    outputVolume: 0,
    toolCalls: [],
    messages: [
      { id: 'msg-1', role: 'user', content: 'CAN YOU SEND AN EMAIL TO JOHN ABOUT THE QUARTERLY REPORT?', timestamp: Date.now() },
    ],
    duration: 2500,
  },
  {
    name: 'THINKING - Processing Request',
    agentState: 'thinking',
    isConnected: true,
    inputVolume: 0,
    outputVolume: 0,
    toolCalls: [
      { id: 'tc-1', name: 'send_email', status: 'pending', timestamp: Date.now() },
    ],
    messages: [
      { id: 'msg-1', role: 'user', content: 'Can you send an email to John about the quarterly report?', timestamp: Date.now() - 3000 },
    ],
    duration: 2500,
  },
  {
    name: 'THINKING - Multiple Tools Queued',
    agentState: 'thinking',
    isConnected: true,
    inputVolume: 0,
    outputVolume: 0,
    toolCalls: [
      { id: 'tc-1', name: 'search_drive', status: 'pending', timestamp: Date.now() },
      { id: 'tc-2', name: 'query_db', status: 'pending', timestamp: Date.now() + 100 },
      { id: 'tc-3', name: 'send_email', status: 'pending', timestamp: Date.now() + 200 },
    ],
    messages: [
      { id: 'msg-1', role: 'user', content: 'Find the Q3 report and email it to the team', timestamp: Date.now() - 3000 },
    ],
    duration: 2000,
  },
  {
    name: 'EXECUTING TOOLS - Single Tool',
    agentState: 'thinking',
    isConnected: true,
    inputVolume: 0,
    outputVolume: 0,
    toolCalls: [
      { id: 'tc-1', name: 'search_drive', status: 'executing', timestamp: Date.now() - 1000 },
    ],
    messages: [
      { id: 'msg-1', role: 'user', content: 'Search for the quarterly report', timestamp: Date.now() - 5000 },
    ],
    duration: 3000,
  },
  {
    name: 'EXECUTING TOOLS - Multiple Tools',
    agentState: 'thinking',
    isConnected: true,
    inputVolume: 0,
    outputVolume: 0,
    toolCalls: [
      { id: 'tc-1', name: 'search_drive', status: 'completed', timestamp: Date.now() - 5000 },
      { id: 'tc-2', name: 'query_db', status: 'executing', timestamp: Date.now() - 2000 },
      { id: 'tc-3', name: 'send_email', status: 'pending', timestamp: Date.now() },
    ],
    messages: [
      { id: 'msg-1', role: 'user', content: 'Find the Q3 report and email it', timestamp: Date.now() - 8000 },
    ],
    duration: 3000,
  },
  {
    name: 'TOOL ERROR - Failed Execution',
    agentState: 'thinking',
    isConnected: true,
    inputVolume: 0,
    outputVolume: 0,
    toolCalls: [
      { id: 'tc-1', name: 'query_db', status: 'error', timestamp: Date.now() - 3000 },
      { id: 'tc-2', name: 'recall', status: 'executing', timestamp: Date.now() - 500 },
    ],
    messages: [
      { id: 'msg-1', role: 'user', content: 'What was the revenue last quarter?', timestamp: Date.now() - 5000 },
    ],
    duration: 2500,
  },
  {
    name: 'SPEAKING - Low Volume Response',
    agentState: 'speaking',
    isConnected: true,
    inputVolume: 0,
    outputVolume: 0.3,
    toolCalls: [
      { id: 'tc-1', name: 'search_drive', status: 'completed', timestamp: Date.now() - 8000 },
    ],
    messages: [
      { id: 'msg-1', role: 'user', content: 'Find the report', timestamp: Date.now() - 10000 },
      { id: 'msg-2', role: 'assistant', content: 'I found the quarterly report in your Drive...', timestamp: Date.now() - 1000 },
    ],
    duration: 2500,
  },
  {
    name: 'SPEAKING - High Volume Response',
    agentState: 'speaking',
    isConnected: true,
    inputVolume: 0,
    outputVolume: 0.9,
    toolCalls: [
      { id: 'tc-1', name: 'send_email', status: 'completed', timestamp: Date.now() - 5000 },
      { id: 'tc-2', name: 'search_drive', status: 'completed', timestamp: Date.now() - 8000 },
    ],
    messages: [
      { id: 'msg-1', role: 'user', content: 'Send that report to the whole team', timestamp: Date.now() - 12000 },
      { id: 'msg-2', role: 'assistant', content: 'DONE! I have sent the Q3 financial report to all 15 team members. They should receive it within the next few minutes.', timestamp: Date.now() - 500 },
    ],
    duration: 3000,
  },
  {
    name: 'FULL CONVERSATION - Multiple Turns',
    agentState: 'listening',
    isConnected: true,
    inputVolume: 0.4,
    outputVolume: 0,
    toolCalls: [
      { id: 'tc-1', name: 'send_email', status: 'completed', timestamp: Date.now() - 30000 },
      { id: 'tc-2', name: 'search_drive', status: 'completed', timestamp: Date.now() - 25000 },
      { id: 'tc-3', name: 'query_db', status: 'completed', timestamp: Date.now() - 15000 },
    ],
    messages: [
      { id: 'msg-1', role: 'user', content: 'Find the Q3 report', timestamp: Date.now() - 35000 },
      { id: 'msg-2', role: 'assistant', content: 'Found it in your Google Drive', timestamp: Date.now() - 32000 },
      { id: 'msg-3', role: 'user', content: 'Email it to the team', timestamp: Date.now() - 28000 },
      { id: 'msg-4', role: 'assistant', content: 'Sent to all 15 team members', timestamp: Date.now() - 24000 },
      { id: 'msg-5', role: 'user', content: 'What was the total revenue?', timestamp: Date.now() - 18000 },
      { id: 'msg-6', role: 'assistant', content: 'Q3 revenue was $2.4M, up 15% from Q2', timestamp: Date.now() - 12000 },
    ],
    duration: 4000,
  },
  {
    name: 'ALL TOOL TYPES - Showcase',
    agentState: 'thinking',
    isConnected: true,
    inputVolume: 0,
    outputVolume: 0,
    toolCalls: [
      { id: 'tc-1', name: 'send_email', status: 'completed', timestamp: Date.now() - 10000 },
      { id: 'tc-2', name: 'search_drive', status: 'completed', timestamp: Date.now() - 8000 },
      { id: 'tc-3', name: 'query_db', status: 'executing', timestamp: Date.now() - 3000 },
      { id: 'tc-4', name: 'knowledge_base', status: 'pending', timestamp: Date.now() - 1000 },
      { id: 'tc-5', name: 'recall', status: 'pending', timestamp: Date.now() - 500 },
      { id: 'tc-6', name: 'check_context', status: 'pending', timestamp: Date.now() },
    ],
    messages: [
      { id: 'msg-1', role: 'user', content: 'Run a full analysis of our Q3 performance', timestamp: Date.now() - 15000 },
    ],
    duration: 4000,
  },
]

export function TestUIStates() {
  const [currentScenarioIndex, setCurrentScenarioIndex] = useState(0)
  const [isPaused, setIsPaused] = useState(false)
  const [animatedVolume, setAnimatedVolume] = useState(0)

  const scenario = TEST_SCENARIOS[currentScenarioIndex]

  // Auto-advance through scenarios
  useEffect(() => {
    if (isPaused) return

    const timer = setTimeout(() => {
      setCurrentScenarioIndex((prev) => (prev + 1) % TEST_SCENARIOS.length)
    }, scenario.duration)

    return () => clearTimeout(timer)
  }, [currentScenarioIndex, isPaused, scenario.duration])

  // Animate volume for more realistic display
  useEffect(() => {
    const targetVolume = scenario.agentState === 'speaking'
      ? scenario.outputVolume
      : scenario.inputVolume

    const interval = setInterval(() => {
      // Add some random variation to simulate real audio
      const variation = (Math.random() - 0.5) * 0.3
      setAnimatedVolume(Math.max(0, Math.min(1, targetVolume + variation * targetVolume)))
    }, 100)

    return () => clearInterval(interval)
  }, [scenario])

  const displayInputVolume = scenario.agentState === 'listening' ? animatedVolume : 0
  const displayOutputVolume = scenario.agentState === 'speaking' ? animatedVolume : 0

  return (
    <div className="min-h-screen bg-white flex flex-col">
      {/* Test Controls */}
      <div className="fixed top-0 left-0 right-0 bg-gray-900 text-white p-3 z-50 flex items-center gap-4">
        <div className="flex-1">
          <h1 className="text-sm font-bold">UI State Tester</h1>
          <p className="text-xs text-gray-400">
            Scenario {currentScenarioIndex + 1}/{TEST_SCENARIOS.length}: {scenario.name}
          </p>
        </div>

        <button
          onClick={() => setIsPaused(!isPaused)}
          className={`px-3 py-1 rounded text-xs font-medium ${
            isPaused ? 'bg-green-600' : 'bg-yellow-600'
          }`}
        >
          {isPaused ? 'Resume' : 'Pause'}
        </button>

        <button
          onClick={() => setCurrentScenarioIndex((prev) => (prev - 1 + TEST_SCENARIOS.length) % TEST_SCENARIOS.length)}
          className="px-3 py-1 bg-gray-700 rounded text-xs"
        >
          Prev
        </button>

        <button
          onClick={() => setCurrentScenarioIndex((prev) => (prev + 1) % TEST_SCENARIOS.length)}
          className="px-3 py-1 bg-gray-700 rounded text-xs"
        >
          Next
        </button>

        <select
          value={currentScenarioIndex}
          onChange={(e) => setCurrentScenarioIndex(Number(e.target.value))}
          className="bg-gray-700 text-white text-xs rounded px-2 py-1"
        >
          {TEST_SCENARIOS.map((s, i) => (
            <option key={i} value={i}>
              {s.name}
            </option>
          ))}
        </select>
      </div>

      {/* State Debug Panel */}
      <div className="fixed bottom-0 left-0 right-0 bg-gray-900 text-white p-2 z-50 flex gap-6 text-[10px] font-mono">
        <div>
          <span className="text-gray-500">state:</span>{' '}
          <span className={`${
            scenario.agentState === 'speaking' ? 'text-green-400' :
            scenario.agentState === 'listening' ? 'text-cyan-400' :
            scenario.agentState === 'thinking' ? 'text-purple-400' :
            'text-gray-400'
          }`}>
            {scenario.agentState || 'null'}
          </span>
        </div>
        <div>
          <span className="text-gray-500">connected:</span>{' '}
          <span className={scenario.isConnected ? 'text-green-400' : 'text-red-400'}>
            {scenario.isConnected.toString()}
          </span>
        </div>
        <div>
          <span className="text-gray-500">inputVol:</span>{' '}
          <span className="text-cyan-400">{displayInputVolume.toFixed(2)}</span>
        </div>
        <div>
          <span className="text-gray-500">outputVol:</span>{' '}
          <span className="text-green-400">{displayOutputVolume.toFixed(2)}</span>
        </div>
        <div>
          <span className="text-gray-500">tools:</span>{' '}
          <span className="text-yellow-400">{scenario.toolCalls.length}</span>
        </div>
        <div>
          <span className="text-gray-500">messages:</span>{' '}
          <span className="text-blue-400">{scenario.messages.length}</span>
        </div>
      </div>

      {/* Main UI (copy of App.tsx layout) */}
      <div className="flex-1 flex flex-col items-center justify-center py-20 px-4">
        <div className="flex flex-col items-center gap-4 w-full max-w-2xl">
          {/* The Orb */}
          <div style={{ height: '140px', width: '140px' }}>
            <WebGLOrb
              agentState={scenario.agentState}
              inputVolume={displayInputVolume}
              outputVolume={displayOutputVolume}
              isConnected={scenario.isConnected}
              size={140}
            />
          </div>

          {/* Agent state label */}
          <div className="h-6 flex items-center justify-center">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">
              {scenario.agentState === 'listening' && 'Listening...'}
              {scenario.agentState === 'thinking' && 'Processing...'}
              {scenario.agentState === 'speaking' && 'Speaking...'}
              {!scenario.agentState && (scenario.isConnected ? 'Ready' : 'Connecting...')}
            </p>
          </div>

          {/* Transcript with Tool Call Panels on sides */}
          <div className="w-full flex items-center justify-center gap-6">
            {/* Left Tool Call Panel - flex centered */}
            <div className="hidden md:flex items-center justify-end flex-shrink-0" style={{ minWidth: '180px' }}>
              <ToolCallPanel
                toolCalls={scenario.toolCalls}
                position="left"
                maxVisible={3}
              />
            </div>

            {/* Transcript Cycler - CENTER */}
            <div className="flex-1 max-w-md min-w-0">
              <TranscriptCycler
                messages={scenario.messages}
                toolCalls={scenario.toolCalls}
                maxVisible={6}
              />
            </div>

            {/* Right Tool Call Panel - flex centered */}
            <div className="hidden md:flex items-center justify-start flex-shrink-0" style={{ minWidth: '180px' }}>
              <ToolCallPanel
                toolCalls={scenario.toolCalls}
                position="right"
                maxVisible={3}
              />
            </div>
          </div>

          {/* Input waveform - synced to user's speech */}
          <div className="w-full max-w-sm h-9">
            <div style={{ opacity: scenario.agentState === 'listening' ? 1 : 0, transition: 'opacity 0.3s' }}>
              <LiveWaveform
                active={scenario.agentState === 'listening'}
                volume={displayInputVolume}
                barColor="rgba(78, 234, 170, 0.7)"
                height={36}
              />
            </div>
          </div>

          {/* SYNRG branding */}
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
      </div>
    </div>
  )
}

export default TestUIStates
