import { create } from 'zustand'
import { toolCallTracker } from './ToolCallTracker'

// =============================================================================
// STORE LOGGING SYSTEM
// =============================================================================
const storeLog = (action: string, data?: any) => {
  const timestamp = new Date().toISOString().split('T')[1].slice(0, -1)
  console.log(`[Store ${timestamp}] ${action}`, data || '')
}

const storeWarn = (action: string, data?: any) => {
  const timestamp = new Date().toISOString().split('T')[1].slice(0, -1)
  console.warn(`[Store ${timestamp}] ⚠️ ${action}`, data || '')
}

type AgentState = 'listening' | 'thinking' | 'speaking' | null

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
}

interface ToolCall {
  id: string
  name: string
  status: 'pending' | 'executing' | 'completed' | 'error'
  arguments?: Record<string, unknown>
  result?: unknown
  timestamp: number
  error?: string       // separate error field (was incorrectly stored in result before)
  subStatus?: string   // composio sub-step: "Searching...", "Executing...", etc.
  duration?: number    // ms from tool.call timestamp to completion
  taskId?: string      // async correlation with tool_result events
}

type AudioStatus = 'waiting' | 'connecting' | 'playing' | 'error'

interface VoiceAgentStore {
  // Connection state
  sessionId: string | null
  botId: string | null
  agentConnected: boolean  // True when voice agent participant joins
  audioStatus: AudioStatus  // Audio playback status for debugging

  // Agent state
  agentState: AgentState
  inputVolume: number
  outputVolume: number

  // Messages and tool calls
  messages: Message[]
  toolCalls: ToolCall[]

  // Actions
  setSessionId: (sessionId: string | null) => void
  setBotId: (botId: string | null) => void
  setAgentConnected: (connected: boolean) => void
  setAudioStatus: (status: AudioStatus) => void
  setAgentState: (state: AgentState) => void
  setInputVolume: (volume: number) => void
  setOutputVolume: (volume: number) => void
  addMessage: (message: Omit<Message, 'id' | 'timestamp'> & { timestamp?: number }) => void
  addToolCall: (toolCall: Omit<ToolCall, 'timestamp'> & { timestamp?: number }) => void
  updateToolCall: (id: string, updates: Partial<ToolCall>) => void
  registerPendingTask: (callId: string, taskId: string) => void
  resolveTaskByTaskId: (taskId: string, updates: Partial<ToolCall>) => void
  clearConversation: () => void
  reset: () => void
}

const generateId = () => `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`

export const useStore = create<VoiceAgentStore>((set) => ({
  // Initial state
  sessionId: null,
  botId: null,
  agentConnected: false,
  audioStatus: 'waiting',
  agentState: null,
  inputVolume: 0,
  outputVolume: 0,
  messages: [],
  toolCalls: [],

  // Actions with comprehensive logging
  setSessionId: (sessionId) => {
    storeLog('setSessionId', { sessionId })
    set({ sessionId })
  },

  setBotId: (botId) => {
    storeLog('setBotId', { botId })
    set({ botId })
  },

  setAgentConnected: (agentConnected) => {
    storeLog('setAgentConnected', { agentConnected })
    set({ agentConnected })
  },

  setAudioStatus: (audioStatus) => {
    storeLog('setAudioStatus', { audioStatus })
    set({ audioStatus })
  },

  setAgentState: (agentState) => {
    storeLog('setAgentState', { from: 'prev', to: agentState })
    set({ agentState })
  },

  setInputVolume: (inputVolume) => set({ inputVolume }), // Don't log - too frequent
  setOutputVolume: (outputVolume) => set({ outputVolume }), // Don't log - too frequent

  addMessage: (message) => {
    storeLog('addMessage', { role: message.role, contentLength: message.content.length })
    set((state) => {
      const now = message.timestamp ?? Date.now()
      // Deduplicate: same role+content within 200ms window (prevents double-dispatch from legacy switch + EventBus)
      const isDuplicate = state.messages.some(
        m => m.role === message.role && m.content === message.content && Math.abs((m.timestamp ?? 0) - now) < 200
      )
      if (isDuplicate) {
        storeWarn('addMessage:duplicate', { role: message.role })
        return state
      }
      const newMessage = {
        ...message,
        id: generateId(),
        timestamp: now,
      }
      storeLog('addMessage:complete', {
        id: newMessage.id,
        totalMessages: state.messages.length + 1
      })
      return {
        messages: [...state.messages, newMessage]
      }
    })
  },

  addToolCall: (toolCall) => {
    storeLog('addToolCall', {
      id: toolCall.id,
      name: toolCall.name,
      status: toolCall.status,
      hasArgs: !!toolCall.arguments
    })
    set((state) => {
      // Deduplicate by ID: prevents double-dispatch from legacy switch + EventBus both firing
      if (state.toolCalls.some(tc => tc.id === toolCall.id)) {
        storeWarn('addToolCall:duplicate', { id: toolCall.id, name: toolCall.name })
        return state
      }
      const newToolCall: ToolCall = {
        ...toolCall,
        timestamp: toolCall.timestamp ?? Date.now(),
      }
      return {
        toolCalls: [...state.toolCalls, newToolCall]
      }
    })
  },

  updateToolCall: (id, updates) => {
    storeLog('updateToolCall', { id, updates })
    set((state) => {
      const existing = state.toolCalls.find(tc => tc.id === id)
      if (!existing) {
        storeWarn('updateToolCall:notFound', { id })
        return state
      }
      return {
        toolCalls: state.toolCalls.map((tc) =>
          tc.id === id ? { ...tc, ...updates } : tc
        )
      }
    })
  },

  registerPendingTask: (callId, taskId) => {
    storeLog('registerPendingTask', { callId, taskId })
    toolCallTracker.register(callId, taskId)
    set((state) => ({
      toolCalls: state.toolCalls.map((tc) =>
        tc.id === callId ? { ...tc, taskId } : tc
      ),
    }))
  },

  resolveTaskByTaskId: (taskId, updates) => {
    storeLog('resolveTaskByTaskId', { taskId, updates })
    set((state) => {
      const tc = state.toolCalls.find((t) => t.taskId === taskId)
      if (!tc) {
        storeWarn('resolveTaskByTaskId:notFound', { taskId })
        return state
      }
      return {
        toolCalls: state.toolCalls.map((t) =>
          t.taskId === taskId ? { ...t, ...updates } : t
        ),
      }
    })
  },

  clearConversation: () => {
    storeLog('clearConversation')
    set({
      messages: [],
      toolCalls: []
    })
  },

  reset: () => {
    storeLog('reset')
    set({
      sessionId: null,
      botId: null,
      agentConnected: false,
      audioStatus: 'waiting',
      agentState: null,
      inputVolume: 0,
      outputVolume: 0,
      messages: [],
      toolCalls: []
    })
  }
}))
