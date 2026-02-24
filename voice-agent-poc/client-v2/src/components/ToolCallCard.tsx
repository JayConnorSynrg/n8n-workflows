import { motion, AnimatePresence } from 'framer-motion'
import { useEffect, useState } from 'react'

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
 *
 * Uses boundary-aware regex — does NOT space individual uppercase letters in
 * all-caps sequences (avoids "M I C R O S O F T" from "MICROSOFTTEAMS").
 */
function autoDisplayName(toolName: string): string {
  if (!toolName) return 'Unknown Tool'
  return toolName
    .replace(/_/g, ' ')                            // snake_case → spaces first
    .replace(/([a-z\d])([A-Z])/g, '$1 $2')         // camelCase: lower/digit → UPPER
    .replace(/([A-Z]+)([A-Z][a-z])/g, '$1 $2')     // all-caps prefix: "HTMLParser" → "HTML Parser"
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/^\w/, c => c.toUpperCase())
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
  /** Opacity override — used by panel to fade error cards before removal */
  fadeOpacity?: number
}

export function ToolCallCard({ toolCall, position, index, fadeOpacity = 1 }: ToolCallCardProps) {
  // Null guard on toolCall.name before any use
  const rawName = toolCall.name ?? 'Unknown Tool'
  const { displayName, icon, composioResolved } = resolveToolDisplay(rawName)

  // Compact label: show only the action, not the service prefix
  // Priority: Composio action → colon-format action → full displayName
  // Truncate to 15 chars to fit the compact card width
  const compactLabel = (() => {
    if (composioResolved) {
      const a = composioResolved.action
      return a.length > 15 ? a.slice(0, 14) + '…' : a
    }
    // Colon-format from Python agent ("Teams: Send Message") → extract action after colon
    const colonIdx = displayName.indexOf(':')
    if (colonIdx > 0) {
      const action = displayName.slice(colonIdx + 1).trim()
      return action.length > 15 ? action.slice(0, 14) + '…' : action
    }
    return displayName.length > 15 ? displayName.slice(0, 14) + '…' : displayName
  })()

  const cardVariants = {
    initial: {
      opacity: 0,
      x: position === 'left' ? -24 : 24,
      scale: 0.92,
    },
    animate: {
      opacity: fadeOpacity,
      x: 0,
      scale: 1,
      transition: {
        type: 'spring',
        stiffness: 340,
        damping: 28,
        delay: index * 0.06,
      },
    },
    exit: {
      opacity: 0,
      x: position === 'left' ? -16 : 16,
      scale: 0.94,
      transition: { duration: 0.18, ease: 'easeOut' },
    },
  }

  // Status dot config
  const statusDot = {
    pending:   { color: 'bg-gray-300',      pulse: false },
    executing: { color: 'bg-[#4EEAAA]',     pulse: true  },
    completed: { color: 'bg-emerald-400',   pulse: false },
    error:     { color: 'bg-red-400',       pulse: false },
  }[toolCall.status]

  // Tint overlay per status
  const tint = {
    pending:   'rgba(148,163,184,0.06)',
    executing: 'rgba(78,234,170,0.10)',
    completed: 'rgba(34,197,94,0.08)',
    error:     'rgba(239,68,68,0.10)',
  }[toolCall.status]

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
      // Compact horizontal pill — ~30px tall, fits 4+ cards in the panel
      className="relative overflow-hidden rounded-lg w-full max-w-[148px] min-w-[100px]"
      style={{
        background: 'rgba(248,250,252,0.85)',
        backdropFilter: 'blur(16px) saturate(180%)',
        WebkitBackdropFilter: 'blur(16px) saturate(180%)',
        border: '1px solid rgba(255,255,255,0.65)',
        boxShadow: '4px 4px 12px rgba(0,0,0,0.09), -2px -2px 8px rgba(255,255,255,0.9), inset 0 1px 0 rgba(255,255,255,0.75)',
      }}
    >
      {/* Executing sweep animation */}
      {toolCall.status === 'executing' && (
        <motion.div
          style={{
            position: 'absolute',
            inset: 0,
            pointerEvents: 'none',
            background: 'linear-gradient(90deg, transparent 0%, rgba(78,234,170,0.35) 40%, rgba(34,211,238,0.35) 65%, transparent 100%)',
          }}
          animate={{ x: ['-110%', '110%'] }}
          transition={{ duration: 2.4, repeat: Infinity, ease: 'easeInOut', repeatDelay: 0.6 }}
        />
      )}

      {/* Status tint */}
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', background: tint }} />

      {/* Single-row content: icon · name · spacer · status dot */}
      <div className="relative flex items-center gap-1.5 px-2 py-1.5">
        {/* Icon */}
        <span className="text-sm flex-shrink-0 leading-none">{icon}</span>

        {/* Tool name — truncated, fills available space */}
        <span
          data-testid="tool-name"
          className="text-[9px] font-medium text-gray-600 leading-tight truncate flex-1 min-w-0"
        >
          {compactLabel}
        </span>

        {/* Status indicator */}
        <span className="flex-shrink-0 flex items-center">
          {statusDot.pulse ? (
            <motion.span
              className={`w-1.5 h-1.5 rounded-full ${statusDot.color}`}
              animate={{ opacity: [1, 0.35, 1] }}
              transition={{ duration: 0.9, repeat: Infinity }}
            />
          ) : (
            <span className={`w-1.5 h-1.5 rounded-full ${statusDot.color}`} />
          )}
        </span>
      </div>
    </motion.div>
  )
}

interface ToolCallPanelProps {
  toolCalls: ToolCall[]
  position: 'left' | 'right'
  maxVisible?: number
}

// How long (ms) an error card is visible before being dismissed
const ERROR_DISMISS_DELAY = 2800

export function ToolCallPanel({ toolCalls, position, maxVisible = 3 }: ToolCallPanelProps) {
  // Track which error card IDs have been scheduled for dismissal
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set())
  // Track which error card IDs are currently in their fade phase (opacity reduced)
  const [fadingIds, setFadingIds] = useState<Set<string>>(new Set())

  // When new error cards appear, schedule fade → dismiss
  useEffect(() => {
    const newErrors = toolCalls.filter(
      tc => tc.status === 'error' && !dismissedIds.has(tc.id) && !fadingIds.has(tc.id)
    )
    if (newErrors.length === 0) return

    const fadeTimers = newErrors.map(tc =>
      setTimeout(() => {
        setFadingIds(prev => new Set([...prev, tc.id]))
      }, ERROR_DISMISS_DELAY * 0.6) // fade starts at 60% of delay
    )

    const dismissTimers = newErrors.map(tc =>
      setTimeout(() => {
        setDismissedIds(prev => new Set([...prev, tc.id]))
      }, ERROR_DISMISS_DELAY)
    )

    return () => {
      fadeTimers.forEach(clearTimeout)
      dismissTimers.forEach(clearTimeout)
    }
  }, [toolCalls]) // eslint-disable-line react-hooks/exhaustive-deps

  // Active tools first (pending/executing)
  const activeTools = toolCalls
    .filter(tc => (tc.status === 'pending' || tc.status === 'executing') && !dismissedIds.has(tc.id))
    .slice(0, maxVisible)

  // Recently completed (not errors) fill remaining slots
  const recentCompleted = toolCalls
    .filter(tc => tc.status === 'completed' && !dismissedIds.has(tc.id))
    .sort((a, b) => b.timestamp - a.timestamp)
    .slice(0, Math.max(0, maxVisible - activeTools.length))

  // Error cards that haven't been dismissed yet
  const errorTools = toolCalls
    .filter(tc => tc.status === 'error' && !dismissedIds.has(tc.id))
    .sort((a, b) => b.timestamp - a.timestamp)
    .slice(0, Math.max(0, maxVisible - activeTools.length - recentCompleted.length))

  const visibleTools = [...activeTools, ...recentCompleted, ...errorTools].slice(0, maxVisible)

  return (
    <div
      className={`
        flex flex-col gap-1.5
        w-full max-w-[148px]
        items-center justify-center
        min-h-[80px]
      `}
    >
      <AnimatePresence mode="popLayout">
        {visibleTools.map((toolCall, index) => (
          <ToolCallCard
            key={toolCall.id}
            toolCall={toolCall}
            position={position}
            index={index}
            fadeOpacity={fadingIds.has(toolCall.id) ? 0.15 : 1}
          />
        ))}
      </AnimatePresence>

      {visibleTools.length === 0 && (
        <div className="h-8 w-full opacity-0" />
      )}
    </div>
  )
}
