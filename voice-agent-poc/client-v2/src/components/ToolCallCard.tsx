import { motion, AnimatePresence } from 'framer-motion'
import { useEffect, useState } from 'react'

interface ToolCall {
  id: string
  name: string
  status: 'pending' | 'executing' | 'completed' | 'error'
  arguments?: Record<string, unknown>
  result?: unknown
  timestamp: number
}

// n8n workflow mapping - tool name to workflow ID
const TOOL_WORKFLOW_MAP: Record<string, { id: string; webhook: string }> = {
  sendEmail: { id: 'kBuTRrXTJF1EEBEs', webhook: '/execute-gmail' },
  searchDrive: { id: 'IamjzfFxjHviJvJg', webhook: '/drive-document-repo' },
  listFiles: { id: 'IamjzfFxjHviJvJg', webhook: '/drive-document-repo' },
  getFile: { id: 'IamjzfFxjHviJvJg', webhook: '/drive-document-repo' },
  queryDatabase: { id: 'z02K1a54akYXMkyj', webhook: '/database-query' },
  knowledgeBase: { id: 'jKMw735r3nAN6O7u', webhook: '/vector-store' },
  checkContext: { id: 'ouWMjcKzbj6nrYXz', webhook: '/agent-context-access' },
  recall: { id: '', webhook: '' }, // Memory only
  memoryStatus: { id: '', webhook: '' }, // Memory only
  recallDrive: { id: '', webhook: '' }, // Memory only
  addContact: { id: '', webhook: '/contacts' },
  getContact: { id: '', webhook: '/contacts' },
  searchContacts: { id: '', webhook: '/contacts' },
}

// Tool display names
const TOOL_DISPLAY_NAMES: Record<string, string> = {
  sendEmail: 'Email',
  searchDrive: 'Drive Search',
  listFiles: 'Drive Files',
  getFile: 'Get Document',
  queryDatabase: 'Database',
  knowledgeBase: 'Knowledge Base',
  checkContext: 'Context',
  recall: 'Memory',
  memoryStatus: 'Memory Status',
  recallDrive: 'Drive Memory',
  addContact: 'Add Contact',
  getContact: 'Get Contact',
  searchContacts: 'Search Contacts',
}

// Tool icons
const TOOL_ICONS: Record<string, string> = {
  sendEmail: '✉️',
  searchDrive: '🔍',
  listFiles: '📁',
  getFile: '📄',
  queryDatabase: '🗄️',
  knowledgeBase: '🧠',
  checkContext: '💭',
  recall: '💾',
  memoryStatus: '📊',
  recallDrive: '💿',
  addContact: '👤',
  getContact: '📇',
  searchContacts: '🔎',
}

interface ToolCallCardProps {
  toolCall: ToolCall
  position: 'left' | 'right'
  index: number
}

export function ToolCallCard({ toolCall, position, index }: ToolCallCardProps) {
  const [progress, setProgress] = useState(0)
  const workflow = TOOL_WORKFLOW_MAP[toolCall.name] || { id: '', webhook: '' }
  const displayName = TOOL_DISPLAY_NAMES[toolCall.name] || toolCall.name
  const icon = TOOL_ICONS[toolCall.name] || '⚙️'

  // Animate progress for executing status
  useEffect(() => {
    if (toolCall.status === 'executing') {
      const startTime = Date.now()
      const duration = 3000 // 3 second estimate

      const animate = () => {
        const elapsed = Date.now() - startTime
        const newProgress = Math.min(90, (elapsed / duration) * 100) // Cap at 90% until complete
        setProgress(newProgress)

        if (toolCall.status === 'executing' && newProgress < 90) {
          requestAnimationFrame(animate)
        }
      }
      requestAnimationFrame(animate)
    } else if (toolCall.status === 'completed') {
      setProgress(100)
    } else if (toolCall.status === 'error') {
      setProgress(100)
    } else {
      setProgress(0)
    }
  }, [toolCall.status])

  // Log tool call state changes
  useEffect(() => {
    console.log(`[ToolCallCard] ${toolCall.name} status: ${toolCall.status}`, {
      id: toolCall.id,
      workflowId: workflow.id,
      progress
    })
  }, [toolCall.status, progress])

  // Status colors
  const statusColors = {
    pending: { bg: 'from-gray-100 to-gray-200', text: 'text-gray-500', shadow: 'shadow-gray-200/50' },
    executing: { bg: 'from-synrg-mint/20 to-synrg-cyan/20', text: 'text-synrg-black', shadow: 'shadow-synrg-mint/30' },
    completed: { bg: 'from-success/10 to-success/20', text: 'text-success', shadow: 'shadow-success/20' },
    error: { bg: 'from-error/10 to-error/20', text: 'text-error', shadow: 'shadow-error/20' },
  }

  const colors = statusColors[toolCall.status]

  // Animation variants
  const cardVariants = {
    initial: {
      opacity: 0,
      x: position === 'left' ? -50 : 50,
      scale: 0.9,
    },
    animate: {
      opacity: 1,
      x: 0,
      scale: 1,
      transition: {
        type: 'spring',
        stiffness: 300,
        damping: 25,
        delay: index * 0.1,
      },
    },
    exit: {
      opacity: 0,
      x: position === 'left' ? -30 : 30,
      scale: 0.95,
      transition: {
        duration: 0.2,
        ease: 'easeOut',
      },
    },
  }

  return (
    <motion.div
      layout
      variants={cardVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      className={`
        relative overflow-hidden rounded-xl
        bg-gradient-to-br ${colors.bg}
        ${colors.shadow}
        transition-all duration-300
        w-full max-w-[160px] min-w-[80px]
        p-2 sm:p-3
      `}
      style={{
        // Neumorphic shadow effect
        boxShadow: `
          6px 6px 12px rgba(0, 0, 0, 0.08),
          -6px -6px 12px rgba(255, 255, 255, 0.9),
          inset 1px 1px 2px rgba(255, 255, 255, 0.5),
          inset -1px -1px 2px rgba(0, 0, 0, 0.03)
        `,
      }}
    >
      {/* Progress bar - gradient fill left to right */}
      <div className="absolute bottom-0 left-0 right-0 h-1 bg-gray-200/50 overflow-hidden rounded-b-xl">
        <motion.div
          className="h-full rounded-b-xl"
          style={{
            background: toolCall.status === 'error'
              ? 'linear-gradient(90deg, #EF4444 0%, #F87171 100%)'
              : 'linear-gradient(90deg, #4EEAAA 0%, #22D3EE 50%, #8B5CF6 100%)',
          }}
          initial={{ width: '0%' }}
          animate={{ width: `${progress}%` }}
          transition={{
            duration: 0.3,
            ease: 'easeOut',
          }}
        />
      </div>

      {/* Content - centered, stacked layout */}
      <div className="flex flex-col items-center text-center gap-1">
        {/* Icon + Status indicator row */}
        <div className="flex items-center justify-center gap-1">
          <span className="text-base sm:text-lg">{icon}</span>
          {toolCall.status === 'executing' && (
            <motion.span
              className="w-1.5 h-1.5 rounded-full bg-synrg-mint"
              animate={{ opacity: [1, 0.4, 1] }}
              transition={{ duration: 1, repeat: Infinity }}
            />
          )}
          {toolCall.status === 'completed' && (
            <span className="text-[10px] text-success">✓</span>
          )}
          {toolCall.status === 'error' && (
            <span className="text-[10px] text-error">✕</span>
          )}
        </div>

        {/* Tool name - wraps on small screens */}
        <span className={`text-[10px] sm:text-xs font-medium ${colors.text} leading-tight`}>
          {displayName}
        </span>

        {/* Status text */}
        <p className="text-[9px] sm:text-[10px] text-gray-400">
          {toolCall.status === 'pending' && 'Queued'}
          {toolCall.status === 'executing' && 'Processing'}
          {toolCall.status === 'completed' && 'Done'}
          {toolCall.status === 'error' && 'Failed'}
        </p>
      </div>
    </motion.div>
  )
}

interface ToolCallPanelProps {
  toolCalls: ToolCall[]
  position: 'left' | 'right'
  maxVisible?: number
}

export function ToolCallPanel({ toolCalls, position, maxVisible = 3 }: ToolCallPanelProps) {
  // Filter for active/recent tool calls
  const activeTools = toolCalls
    .filter(tc => tc.status === 'pending' || tc.status === 'executing')
    .slice(0, maxVisible)

  const recentCompleted = toolCalls
    .filter(tc => tc.status === 'completed' || tc.status === 'error')
    .sort((a, b) => b.timestamp - a.timestamp)
    .slice(0, Math.max(0, maxVisible - activeTools.length))

  const visibleTools = [...activeTools, ...recentCompleted].slice(0, maxVisible)

  // Log panel state
  useEffect(() => {
    if (visibleTools.length > 0) {
      console.log(`[ToolCallPanel:${position}] Visible tools:`, visibleTools.map(t => `${t.name}:${t.status}`))
    }
  }, [visibleTools, position])

  return (
    <div
      className={`
        flex flex-col gap-2 sm:gap-3
        w-full max-w-[120px] sm:max-w-[160px]
        min-h-[150px] sm:min-h-[200px]
        items-center justify-center
      `}
    >
      <AnimatePresence mode="popLayout">
        {visibleTools.map((toolCall, index) => (
          <ToolCallCard
            key={toolCall.id}
            toolCall={toolCall}
            position={position}
            index={index}
          />
        ))}
      </AnimatePresence>

      {/* Empty state placeholder - maintains vertical centering */}
      {visibleTools.length === 0 && (
        <div className="h-14 w-full opacity-0" />
      )}
    </div>
  )
}
