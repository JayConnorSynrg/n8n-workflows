import { motion, AnimatePresence } from 'framer-motion'
import { useEffect } from 'react'

interface ToolCall {
  id: string
  name: string
  status: 'pending' | 'executing' | 'completed' | 'error'
  arguments?: Record<string, unknown>
  result?: unknown
  timestamp: number
  error?: string       // separate error field
  subStatus?: string   // composio sub-step: 'searching' | 'executing' | 'done'
  duration?: number    // ms from tool.call timestamp to completion
  taskId?: string      // async correlation with tool_result events
}

// n8n workflow mapping - tool name to workflow ID
const TOOL_WORKFLOW_MAP: Record<string, { id: string; webhook: string }> = {
  sendEmail: { id: 'kBuTRrXTJF1EEBEs', webhook: '/execute-gmail' },
  searchDrive: { id: 'IamjzfFxjHviJvJg', webhook: '/drive-document-repo' },
  listFiles: { id: 'IamjzfFxjHviJvJg', webhook: '/drive-document-repo' },
  getFile: { id: 'IamjzfFxjHviJvJg', webhook: '/drive-document-repo' },
  queryDatabase: { id: 'oaApb71EQJKvV5yo', webhook: '/voice-query-vector-db' },
  knowledgeBase: { id: 'jKMw735r3nAN6O7u', webhook: '/vector-store' },
  checkContext: { id: 'ouWMjcKzbj6nrYXz', webhook: '/agent-context-access' },
  recall: { id: '', webhook: '' }, // Memory only
  memoryStatus: { id: '', webhook: '' }, // Memory only
  recallDrive: { id: '', webhook: '' }, // Memory only
  addContact: { id: '', webhook: '/contacts' },
  getContact: { id: '', webhook: '/contacts' },
  searchContacts: { id: '', webhook: '/contacts' },
}

// =============================================================================
// LAYER 1: Auto-derivation — works for ANY tool name without registration
// =============================================================================

/**
 * Converts a camelCase or snake_case tool name to a human-readable Title Case string.
 * This is the default path for any tool not in TOOL_REGISTRY.
 */
function autoDisplayName(toolName: string): string {
  if (!toolName) return 'Unknown Tool'
  return toolName
    .replace(/([A-Z])/g, ' $1')   // camelCase → insert space before uppercase
    .replace(/_/g, ' ')            // snake_case → spaces
    .replace(/\s+/g, ' ')          // collapse multiple spaces
    .trim()
    .replace(/^\w/, c => c.toUpperCase()) // capitalize first letter
}

/**
 * Derives a relevant emoji icon from keywords in the tool name.
 * Falls back to the generic wrench for unrecognised names.
 */
function autoIcon(toolName: string): string {
  const name = toolName.toLowerCase()
  if (name.includes('email') || name.includes('mail') || name.includes('gmail')) return '📧'
  if (name.includes('drive') || name.includes('file') || name.includes('doc')) return '📁'
  if (name.includes('calendar') || name.includes('schedule') || name.includes('event')) return '📅'
  if (name.includes('message') || name.includes('chat') || name.includes('slack') || name.includes('teams')) return '💬'
  if (name.includes('search') || name.includes('query') || name.includes('find')) return '🔍'
  if (name.includes('create') || name.includes('add') || name.includes('new')) return '➕'
  if (name.includes('update') || name.includes('edit') || name.includes('modify')) return '✏️'
  if (name.includes('delete') || name.includes('remove')) return '🗑️'
  if (name.includes('database') || name.includes('vector') || name.includes('store') || name.includes('knowledge')) return '🗄️'
  if (name.includes('context') || name.includes('memory') || name.includes('recall')) return '🧠'
  if (name.includes('contact') || name.includes('person') || name.includes('user')) return '👤'
  if (name.includes('sheet') || name.includes('table') || name.includes('data')) return '📊'
  if (name.includes('notion') || name.includes('page') || name.includes('note')) return '📝'
  if (name.includes('github') || name.includes('code') || name.includes('repo')) return '💻'
  if (name.includes('zoom') || name.includes('meet') || name.includes('call')) return '📹'
  if (name.includes('twitter') || name.includes('social') || name.includes('post')) return '📣'
  return '🔧'
}

// =============================================================================
// LAYER 2: Explicit registry — only for cases where auto-derivation falls short
// =============================================================================

interface ToolCardDef {
  displayName: string
  icon: string
}

/**
 * Minimal explicit overrides.
 * Only add an entry here when autoDisplayName() produces a genuinely bad result.
 * Most tools should NOT appear here — auto-derivation handles them.
 */
const TOOL_REGISTRY: Record<string, ToolCardDef> = {
  // "Send Email" auto-derives fine; "Email" is the preferred short label for UI space
  sendEmail:    { displayName: 'Email',        icon: '✉️' },
  // Single-word names that auto-derive as-is but benefit from a cleaner label
  recall:       { displayName: 'Memory',       icon: '🧠' },
  // "Recall Drive" auto-derives but "Drive Memory" is more precise
  recallDrive:  { displayName: 'Drive Memory', icon: '📁' },
  // "Query Database" auto-derives; "Database" is the preferred short label
  queryDatabase: { displayName: 'Database',   icon: '🗄️' },
  // "Knowledge Base" auto-derives correctly; icon override only
  knowledgeBase: { displayName: 'Knowledge Base', icon: '🗄️' },
  // "Get File" auto-derives; document icon preferred over folder
  getFile:      { displayName: 'Get Document', icon: '📄' },
  // "Search Drive" auto-derives the name correctly; folder icon preferred over search icon
  searchDrive:  { displayName: 'Search Drive', icon: '📁' },
}

// Service label → icon mapping for server-side display names ("Teams: Send Message")
const SERVICE_ICONS: Record<string, string> = {
  'Teams': '💬',
  'OneDrive': '☁️',
  'Sheets': '📊',
  'Docs': '📝',
  'Calendar': '📅',
  'Drive': '📁',
  'Excel': '📊',
  'Slack': '💬',
  'Gmail': '📧',
  'GitHub': '🐙',
  'Canva': '🎨',
  'Database': '🗄️',
  'Search': '🔍',
  'Web Search': '🌐',
  'Gamma': '🎨',
  'Recall': '🎤',
  'Tools': '⚙️',
  'Google Calendar': '📅',
  'Google Drive': '📁',
  'Google Sheets': '📊',
  'Google Docs': '📝',
  'HubSpot': '🔶',
  'Salesforce': '☁️',
  'Notion': '📓',
  'Jira': '🔵',
  'Airtable': '📋',
  'Trello': '📌',
  'Asana': '🎯',
  'Discord': '💬',
  'Twitter': '🐦',
  'LinkedIn': '💼',
  'Zoom': '📹',
  'Dropbox': '📦',
  'Outlook': '📧',
  'Microsoft Teams': '💬',
}

// Composio app name mappings (SCREAMING_CASE prefix → human-readable)
const COMPOSIO_APP_NAMES: Record<string, string> = {
  GMAIL: 'Gmail',
  GOOGLECALENDAR: 'Google Calendar',
  GOOGLEDRIVE: 'Google Drive',
  GOOGLESHEETS: 'Google Sheets',
  GOOGLEDOCS: 'Google Docs',
  SLACK: 'Slack',
  NOTION: 'Notion',
  GITHUB: 'GitHub',
  JIRA: 'Jira',
  AIRTABLE: 'Airtable',
  HUBSPOT: 'HubSpot',
  SALESFORCE: 'Salesforce',
  TRELLO: 'Trello',
  ASANA: 'Asana',
  DISCORD: 'Discord',
  TWITTER: 'Twitter',
  LINKEDIN: 'LinkedIn',
  ZOOM: 'Zoom',
  DROPBOX: 'Dropbox',
  ONEDRIVE: 'OneDrive',
  MICROSOFTTEAMS: 'Microsoft Teams',
  OUTLOOK: 'Outlook',
}

/**
 * Resolves a Composio tool slug (APPNAME_ACTION_VERB) into app and action parts.
 * Returns null if the name does not match the Composio SCREAMING_CASE pattern.
 */
function resolveComposioSlug(toolName: string): { app: string; action: string } | null {
  if (!toolName || !toolName.includes('_')) return null

  // Composio slugs are ALL_CAPS — if lowercase letters are present in first segment, it's not a slug
  const parts = toolName.split('_')
  if (parts.length < 2) return null

  // Check if it looks like SCREAMING_CASE (all parts are uppercase or digits)
  const looksLikeScreamingCase = parts.every(p => p === p.toUpperCase() && p.length > 0)
  if (!looksLikeScreamingCase) return null

  const appRaw = parts[0]
  const actionRaw = parts.slice(1).join('_')

  const app = COMPOSIO_APP_NAMES[appRaw] ?? (appRaw.charAt(0) + appRaw.slice(1).toLowerCase())
  const action = actionRaw
    .split('_')
    .map(w => w.charAt(0) + w.slice(1).toLowerCase())
    .join(' ')

  return { app, action }
}

/**
 * Generates a human-readable summary of a completed tool's result.
 * Returns null if no meaningful summary can be produced.
 */
function generatePresentation(toolCall: ToolCall): string | null {
  if (!toolCall.result) return null

  const result = toolCall.result

  // String result — truncate
  if (typeof result === 'string') {
    return result.length > 120 ? result.slice(0, 120) + '…' : result
  }

  // Object result — match common patterns
  if (typeof result === 'object' && result !== null) {
    const r = result as Record<string, unknown>

    // Email sent
    if (r.messageId || r.emailId) return 'Email sent successfully'

    // Files list
    if (Array.isArray(r.files)) return `Found ${r.files.length} file(s)`
    if (r.count !== undefined) return `Returned ${r.count} result(s)`

    // Success/status indicators
    if (r.success === true) return 'Completed successfully'
    if (r.status === 'success') return 'Completed successfully'

    // Generic object — show key count or single field
    const keys = Object.keys(r).filter(k => k !== 'type' && k !== 'status')
    if (keys.length === 1) return `${keys[0]}: ${JSON.stringify(r[keys[0]]).slice(0, 80)}`
    if (keys.length > 1) return `${keys.length} fields returned`
  }

  return null
}

/**
 * Formats a duration in milliseconds into a compact display string.
 */
function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

/**
 * Resolves display name and icon for any tool name using a 2-layer strategy:
 *
 * 1. Explicit TOOL_REGISTRY — for curated overrides
 * 2. Composio slug resolver — for SCREAMING_CASE external tool slugs
 * 3. Server-side colon format — "Service: Action" labels from the agent
 * 4. Batch colon+plus format — "Service A: Action + Service B: Action"
 * 5. Auto-derivation — camelCase/snake_case → Title Case (no registration needed)
 *
 * Adding a new tool to the Python agent requires ZERO changes to this file.
 */
function resolveToolDisplay(name: string): { displayName: string; icon: string; composioResolved: { app: string; action: string } | null } {
  // Layer 1: Explicit registry (curated overrides only)
  const registered = TOOL_REGISTRY[name]
  if (registered) {
    return { displayName: registered.displayName, icon: registered.icon, composioResolved: null }
  }

  // Layer 2: Composio SCREAMING_CASE slugs (e.g. GMAIL_SEND_EMAIL)
  const composioResolved = resolveComposioSlug(name)
  if (composioResolved) {
    const { app, action } = composioResolved
    const appIcon = SERVICE_ICONS[app] ?? autoIcon(name)
    return { displayName: `${app} — ${action}`, icon: appIcon, composioResolved }
  }

  // Layer 3: Server-side display names — "Service: Action"
  const colonIdx = name.indexOf(':')
  if (colonIdx > 0) {
    const serviceLabel = name.slice(0, colonIdx).trim()
    const icon = SERVICE_ICONS[serviceLabel] ?? autoIcon(serviceLabel)
    return { displayName: name, icon, composioResolved: null }
  }

  // Layer 4: Batch names — "Teams: Send Message + Calendar: Create Event"
  if (name.includes(' + ')) {
    const firstPart = name.split(' + ')[0]
    const serviceLabel = firstPart.split(':')[0]?.trim() ?? ''
    const icon = SERVICE_ICONS[serviceLabel] ?? '⚡'
    return { displayName: name, icon, composioResolved: null }
  }

  // Layer 5: Auto-derive from camelCase / snake_case — works for any tool name
  return {
    displayName: autoDisplayName(name),
    icon: autoIcon(name),
    composioResolved: null,
  }
}

interface ToolCallCardProps {
  toolCall: ToolCall
  position: 'left' | 'right'
  index: number
}

export function ToolCallCard({ toolCall, position, index }: ToolCallCardProps) {
  const workflow = TOOL_WORKFLOW_MAP[toolCall.name] || { id: '', webhook: '' }

  // Null guard on toolCall.name before any use
  const rawName = toolCall.name ?? 'Unknown Tool'
  const { displayName, icon } = resolveToolDisplay(rawName)

  // Log tool call state changes
  useEffect(() => {
    console.log(`[ToolCallCard] ${rawName} status: ${toolCall.status}`, {
      id: toolCall.id,
      workflowId: workflow.id,
    })
  }, [toolCall.status])

  // Status colors — text color and tint rgba for the glass overlay
  const statusColors = {
    pending:   { text: 'text-gray-500',    tint: 'rgba(148,163,184,0.08)' },
    executing: { text: 'text-gray-800',    tint: 'rgba(78,234,170,0.14)' },
    completed: { text: 'text-emerald-700', tint: 'rgba(34,197,94,0.14)' },
    error:     { text: 'text-red-600',     tint: 'rgba(239,68,68,0.14)' },
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

  // Derive sub-status chip config
  const subStatusChip = (() => {
    if (!toolCall.subStatus || toolCall.subStatus === 'done') return null
    if (toolCall.subStatus === 'searching') return { label: 'Searching...', icon: '🔍' }
    if (toolCall.subStatus === 'executing') return { label: 'Executing...', icon: '⚡' }
    // Unknown sub-statuses — render as-is
    return { label: toolCall.subStatus, icon: '⏳' }
  })()

  // Duration display — only for terminal states
  const isTerminal = toolCall.status === 'completed' || toolCall.status === 'error'
  const durationLabel = isTerminal && toolCall.duration !== undefined
    ? formatDuration(toolCall.duration)
    : null

  // Result preview
  const resultPreview = toolCall.status === 'completed' ? generatePresentation(toolCall) : null

  return (
    <motion.div
      layout
      variants={cardVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      data-testid="tool-call-card"
      data-tool-id={toolCall.id}
      data-status={toolCall.status}
      className="relative overflow-hidden rounded-xl transition-all duration-300 w-full max-w-[160px] min-w-[80px] p-2 sm:p-3"
      style={{
        background: 'rgba(248,250,252,0.82)',
        backdropFilter: 'blur(20px) saturate(200%)',
        WebkitBackdropFilter: 'blur(20px) saturate(200%)',
        border: '1px solid rgba(255,255,255,0.7)',
        boxShadow: `
          8px 8px 20px rgba(0,0,0,0.13),
          -4px -4px 12px rgba(255,255,255,0.95),
          inset 0 1px 0 rgba(255,255,255,0.8),
          inset 0 -1px 0 rgba(0,0,0,0.03)
        `,
      }}
    >
      {/* Pending: slow breathing pulse — card dims and brightens to signal waiting */}
      {toolCall.status === 'pending' && (
        <motion.div
          style={{
            position: 'absolute',
            inset: 0,
            pointerEvents: 'none',
            background: 'rgba(78,234,170,0.12)',
          }}
          animate={{ opacity: [0.3, 1, 0.3] }}
          transition={{ duration: 2.2, repeat: Infinity, ease: 'easeInOut' }}
        />
      )}

      {/* Executing: single deliberate sweep left→right, long pause, then repeat — feels like work happening */}
      {toolCall.status === 'executing' && (
        <motion.div
          style={{
            position: 'absolute',
            inset: 0,
            pointerEvents: 'none',
            background: 'linear-gradient(90deg, transparent 0%, rgba(78,234,170,0.5) 30%, rgba(34,211,238,0.5) 55%, rgba(139,92,246,0.4) 80%, transparent 100%)',
          }}
          animate={{ x: ['-110%', '110%'] }}
          transition={{ duration: 2.8, repeat: Infinity, ease: 'easeInOut', repeatDelay: 0.8 }}
        />
      )}

      {/* Status tint overlay */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          background: colors.tint,
        }}
      />

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
          {/* Duration badge — inline with status indicator for terminal states */}
          {durationLabel && (
            <span className="text-[9px] text-gray-400 ml-0.5">{durationLabel}</span>
          )}
        </div>

        {/* Tool name */}
        <span
          data-testid="tool-name"
          className={`text-[10px] sm:text-xs font-medium ${colors.text} leading-tight`}
        >
          {displayName}
        </span>

        {/* Sub-status chip — only when truthy and not 'done' */}
        {subStatusChip && (
          <span className="text-[8px] text-gray-500 bg-white/60 rounded-full px-1.5 py-0.5 leading-tight">
            {subStatusChip.icon} {subStatusChip.label}
          </span>
        )}

        {/* Status text */}
        <p className="text-[9px] sm:text-[10px] text-gray-400">
          {toolCall.status === 'pending' && 'Queued'}
          {toolCall.status === 'executing' && 'Processing'}
          {toolCall.status === 'completed' && 'Done'}
          {toolCall.status === 'error' && 'Failed'}
        </p>

        {/* Error message — only when status is 'error' and error field is set */}
        {toolCall.error && toolCall.status === 'error' && (
          <p
            className="text-[8px] text-red-400 mt-0.5 leading-tight w-full truncate"
            title={toolCall.error}
          >
            {toolCall.error.length > 80 ? toolCall.error.slice(0, 80) + '…' : toolCall.error}
          </p>
        )}

        {/* Result preview — only on completed with a non-null presentation */}
        {resultPreview && (
          <p className="text-[8px] text-green-500 mt-0.5 leading-tight w-full truncate" title={resultPreview}>
            {resultPreview}
          </p>
        )}
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
