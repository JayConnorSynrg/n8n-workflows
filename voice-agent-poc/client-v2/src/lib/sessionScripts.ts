// =============================================================================
// sessionScripts.ts
// Pre-defined session replay scripts for the AIO Voice System SessionReplay panel.
// Each script simulates a complete, realistic agent session with realistic timing.
// =============================================================================

export interface ScriptStep {
  delay: number                      // ms from session start
  event: Record<string, unknown>     // raw event payload — dispatchRaw handles validation
  label: string                      // visible description shown in the replay log
  phase?: 'connect' | 'listening' | 'thinking' | 'tool' | 'responding' | 'complete'
}

export interface SessionScript {
  id: string
  name: string
  description: string
  totalDuration: number              // ms — sum of all delays
  steps: ScriptStep[]
}

// =============================================================================
// Script 1: emailSend — "Schedule email to executive team"
// Duration: ~5 seconds | 1 tool call (sendEmail via Gmail)
// =============================================================================

const emailSendScript: SessionScript = {
  id: 'emailSend',
  name: 'Send Email to Executive Team',
  description: 'Agent receives a request to email the executive team, calls Gmail, and confirms delivery.',
  totalDuration: 5000,
  steps: [
    {
      delay: 0,
      event: { type: 'agent.state', state: 'listening' },
      label: 'Agent listening',
      phase: 'listening',
    },
    {
      delay: 600,
      event: {
        type: 'transcript.user',
        text: "Send a meeting summary to the executive team about today's Q4 planning session.",
        is_final: true,
        timestamp: Date.now(),
      },
      label: 'User request received',
      phase: 'listening',
    },
    {
      delay: 900,
      event: { type: 'agent.state', state: 'thinking' },
      label: 'Agent processing request',
      phase: 'thinking',
    },
    {
      delay: 1200,
      event: {
        type: 'tool.call',
        call_id: 'call_email_001',
        name: 'sendEmail',
        arguments: {
          to: 'executives@synrg.com',
          subject: 'Q4 Planning Session Summary',
          body: "Team,\n\nHere is a summary from today's Q4 planning session...",
        },
        timestamp: Date.now(),
      },
      label: 'Composing and sending email',
      phase: 'tool',
    },
    {
      delay: 1400,
      event: {
        type: 'composio.searching',
        call_id: 'call_email_001',
        tool_slug: 'GMAIL_SEND_EMAIL',
        detail: 'Connecting to Gmail...',
        timestamp: Date.now(),
      },
      label: 'Connecting to Gmail',
      phase: 'tool',
    },
    {
      delay: 1900,
      event: {
        type: 'composio.executing',
        call_id: 'call_email_001',
        tool_slug: 'GMAIL_SEND_EMAIL',
        detail: 'Sending email to executives@synrg.com...',
        timestamp: Date.now(),
      },
      label: 'Sending email',
      phase: 'tool',
    },
    {
      delay: 2800,
      event: {
        type: 'composio.completed',
        call_id: 'call_email_001',
        tool_slug: 'GMAIL_SEND_EMAIL',
        detail: 'Email delivered successfully',
        duration_ms: 1400,
        timestamp: Date.now(),
      },
      label: 'Email sent successfully',
      phase: 'tool',
    },
    {
      delay: 2850,
      event: {
        type: 'tool_result',
        task_id: 'task_001',
        call_id: 'call_email_001',
        tool_name: 'sendEmail',
        status: 'completed',
        duration_ms: 1600,
        result: 'Email sent to executives@synrg.com. Message ID: msg_4f8a2c.',
      },
      label: 'Tool completed',
      phase: 'tool',
    },
    {
      delay: 3100,
      event: { type: 'agent.state', state: 'speaking' },
      label: 'Agent responding',
      phase: 'responding',
    },
    {
      delay: 3300,
      event: {
        type: 'transcript.assistant',
        text: "Done — I've sent the Q4 planning summary to the executive team at executives@synrg.com. The email was delivered successfully.",
        timestamp: Date.now(),
      },
      label: 'Agent speaks response',
      phase: 'responding',
    },
    {
      delay: 5000,
      event: { type: 'agent.state', state: 'listening' },
      label: 'Ready for next request',
      phase: 'complete',
    },
  ],
}

// =============================================================================
// Script 2: multiTool — "Research and notify"
// Duration: ~8 seconds | 2 sequential tools (searchDrive → sendEmail)
// =============================================================================

const multiToolScript: SessionScript = {
  id: 'multiTool',
  name: 'Research and Notify (Multi-Tool)',
  description: 'Agent finds a board presentation in Drive then emails a link to a colleague — two sequential tools.',
  totalDuration: 8000,
  steps: [
    {
      delay: 0,
      event: { type: 'agent.state', state: 'listening' },
      label: 'Agent listening',
      phase: 'listening',
    },
    {
      delay: 800,
      event: {
        type: 'transcript.user',
        text: 'Find the board presentation from last week and email a link to Sarah at sarah@synrg.com',
        is_final: true,
        timestamp: Date.now(),
      },
      label: 'User request received',
      phase: 'listening',
    },
    {
      delay: 1100,
      event: { type: 'agent.state', state: 'thinking' },
      label: 'Agent planning multi-step task',
      phase: 'thinking',
    },
    {
      delay: 1400,
      event: {
        type: 'tool.call',
        call_id: 'call_drive_001',
        name: 'searchDrive',
        arguments: { query: 'board presentation', limit: 5 },
        timestamp: Date.now(),
      },
      label: 'Searching Google Drive',
      phase: 'tool',
    },
    {
      delay: 1600,
      event: {
        type: 'composio.searching',
        call_id: 'call_drive_001',
        tool_slug: 'GOOGLEDRIVE_SEARCH_FILES',
        detail: 'Searching Google Drive...',
        timestamp: Date.now(),
      },
      label: 'Connecting to Google Drive',
      phase: 'tool',
    },
    {
      delay: 2100,
      event: {
        type: 'composio.executing',
        call_id: 'call_drive_001',
        tool_slug: 'GOOGLEDRIVE_SEARCH_FILES',
        detail: 'Scanning recent files...',
        timestamp: Date.now(),
      },
      label: 'Scanning recent Drive files',
      phase: 'tool',
    },
    {
      delay: 2900,
      event: {
        type: 'composio.completed',
        call_id: 'call_drive_001',
        tool_slug: 'GOOGLEDRIVE_SEARCH_FILES',
        detail: 'Found 3 matching files',
        duration_ms: 800,
        timestamp: Date.now(),
      },
      label: 'Drive search complete — 3 files found',
      phase: 'tool',
    },
    {
      delay: 2950,
      event: {
        type: 'tool_result',
        task_id: 'task_002',
        call_id: 'call_drive_001',
        tool_name: 'searchDrive',
        status: 'completed',
        duration_ms: 1500,
        result: 'Found 3 files: "Board_Presentation_2026_Q1.pptx", "Board_Meeting_Notes_Feb.docx", "Q1_Exec_Summary.pdf"',
      },
      label: 'Drive search result received',
      phase: 'tool',
    },
    {
      delay: 3100,
      event: { type: 'agent.state', state: 'thinking' },
      label: 'Agent selecting file and composing email',
      phase: 'thinking',
    },
    {
      delay: 3400,
      event: {
        type: 'tool.call',
        call_id: 'call_email_002',
        name: 'sendEmail',
        arguments: {
          to: 'sarah@synrg.com',
          subject: 'Board Presentation - Feb 2026',
          body: "Hi Sarah, here's the link to the board presentation from last week...",
        },
        timestamp: Date.now(),
      },
      label: 'Sending email to Sarah',
      phase: 'tool',
    },
    {
      delay: 3600,
      event: {
        type: 'composio.searching',
        call_id: 'call_email_002',
        tool_slug: 'GMAIL_SEND_EMAIL',
        detail: 'Connecting to Gmail...',
        timestamp: Date.now(),
      },
      label: 'Connecting to Gmail',
      phase: 'tool',
    },
    {
      delay: 4100,
      event: {
        type: 'composio.executing',
        call_id: 'call_email_002',
        tool_slug: 'GMAIL_SEND_EMAIL',
        detail: 'Sending email to sarah@synrg.com...',
        timestamp: Date.now(),
      },
      label: 'Sending email to sarah@synrg.com',
      phase: 'tool',
    },
    {
      delay: 5300,
      event: {
        type: 'composio.completed',
        call_id: 'call_email_002',
        tool_slug: 'GMAIL_SEND_EMAIL',
        detail: 'Email delivered to sarah@synrg.com',
        duration_ms: 1200,
        timestamp: Date.now(),
      },
      label: 'Email to Sarah delivered',
      phase: 'tool',
    },
    {
      delay: 5350,
      event: {
        type: 'tool_result',
        task_id: 'task_003',
        call_id: 'call_email_002',
        tool_name: 'sendEmail',
        status: 'completed',
        duration_ms: 1950,
        result: 'Email sent to sarah@synrg.com. Message ID: msg_9c3e17.',
      },
      label: 'Email tool completed',
      phase: 'tool',
    },
    {
      delay: 5600,
      event: { type: 'agent.state', state: 'speaking' },
      label: 'Agent responding',
      phase: 'responding',
    },
    {
      delay: 5800,
      event: {
        type: 'transcript.assistant',
        text: "I found the board presentation — 'Board_Presentation_2026_Q1.pptx' — and sent the link to Sarah at sarah@synrg.com. She should have it in her inbox now.",
        timestamp: Date.now(),
      },
      label: 'Agent speaks response',
      phase: 'responding',
    },
    {
      delay: 8000,
      event: { type: 'agent.state', state: 'listening' },
      label: 'Ready for next request',
      phase: 'complete',
    },
  ],
}

// =============================================================================
// Script 3: errorRecovery — "Failed tool, graceful recovery"
// Duration: ~6 seconds | 1 tool that fails, agent explains gracefully
// =============================================================================

const errorRecoveryScript: SessionScript = {
  id: 'errorRecovery',
  name: 'Error Recovery (OAuth Expired)',
  description: 'Google Drive authorization has expired. Agent detects the failure and explains how to fix it.',
  totalDuration: 5500,
  steps: [
    {
      delay: 0,
      event: { type: 'agent.state', state: 'listening' },
      label: 'Agent listening',
      phase: 'listening',
    },
    {
      delay: 700,
      event: {
        type: 'transcript.user',
        text: 'Search my drive for the vendor contracts from Q3',
        is_final: true,
        timestamp: Date.now(),
      },
      label: 'User request received',
      phase: 'listening',
    },
    {
      delay: 1000,
      event: { type: 'agent.state', state: 'thinking' },
      label: 'Agent processing request',
      phase: 'thinking',
    },
    {
      delay: 1300,
      event: {
        type: 'tool.call',
        call_id: 'call_drive_err',
        name: 'searchDrive',
        arguments: { query: 'vendor contracts Q3' },
        timestamp: Date.now(),
      },
      label: 'Initiating Drive search',
      phase: 'tool',
    },
    {
      delay: 1500,
      event: {
        type: 'composio.searching',
        call_id: 'call_drive_err',
        tool_slug: 'GOOGLEDRIVE_SEARCH_FILES',
        detail: 'Connecting to Google Drive...',
        timestamp: Date.now(),
      },
      label: 'Connecting to Google Drive',
      phase: 'tool',
    },
    {
      delay: 2200,
      event: {
        type: 'composio.error',
        call_id: 'call_drive_err',
        tool_slug: 'GOOGLEDRIVE_SEARCH_FILES',
        detail: 'Google Drive authorization expired. Please re-authenticate your account in the settings.',
        duration_ms: 200,
        timestamp: Date.now(),
      },
      label: 'Authorization error — OAuth token expired',
      phase: 'tool',
    },
    {
      delay: 2250,
      event: {
        type: 'tool_result',
        task_id: 'task_err_001',
        call_id: 'call_drive_err',
        tool_name: 'searchDrive',
        status: 'failed',
        duration_ms: 700,
        error: 'Authorization failed: Google Drive OAuth token expired',
      },
      label: 'Tool failed — authorization error',
      phase: 'tool',
    },
    {
      delay: 2500,
      event: { type: 'agent.state', state: 'speaking' },
      label: 'Agent explaining the error',
      phase: 'responding',
    },
    {
      delay: 2700,
      event: {
        type: 'transcript.assistant',
        text: "I wasn't able to access Google Drive right now — the authorization has expired. You'll need to re-authenticate your Google account in the settings, and then I can search for those vendor contracts.",
        timestamp: Date.now(),
      },
      label: 'Agent explains error and next steps',
      phase: 'responding',
    },
    {
      delay: 5500,
      event: { type: 'agent.state', state: 'listening' },
      label: 'Ready for next request',
      phase: 'complete',
    },
  ],
}

// =============================================================================
// Script 4: concurrent — "Multiple parallel tools"
// Duration: ~7.5 seconds | 3 tools fire simultaneously, complete at different times
// =============================================================================

const concurrentScript: SessionScript = {
  id: 'concurrent',
  name: 'Parallel Status Check (3 Tools)',
  description: 'Agent runs three tools simultaneously — Gmail, Drive, and context — each completing independently.',
  totalDuration: 7500,
  steps: [
    {
      delay: 0,
      event: { type: 'agent.state', state: 'listening' },
      label: 'Agent listening',
      phase: 'listening',
    },
    {
      delay: 600,
      event: {
        type: 'transcript.user',
        text: "Give me a status update — check my emails, list recent drive files, and pull the latest context from our session.",
        is_final: true,
        timestamp: Date.now(),
      },
      label: 'User request received',
      phase: 'listening',
    },
    {
      delay: 900,
      event: { type: 'agent.state', state: 'thinking' },
      label: 'Agent planning parallel execution',
      phase: 'thinking',
    },
    // All 3 tool.call events fire at ~1200ms
    {
      delay: 1200,
      event: {
        type: 'tool.call',
        call_id: 'call_ctx',
        name: 'checkContext',
        arguments: {},
        timestamp: Date.now(),
      },
      label: 'Fetching session context',
      phase: 'tool',
    },
    {
      delay: 1210,
      event: {
        type: 'tool.call',
        call_id: 'call_files',
        name: 'listFiles',
        arguments: {},
        timestamp: Date.now(),
      },
      label: 'Listing Drive files',
      phase: 'tool',
    },
    {
      delay: 1220,
      event: {
        type: 'tool.call',
        call_id: 'call_mail',
        name: 'GMAIL_LIST_EMAILS',
        arguments: { max_results: 10 },
        timestamp: Date.now(),
      },
      label: 'Fetching Gmail inbox',
      phase: 'tool',
    },
    // Gmail connects via Composio
    {
      delay: 1400,
      event: {
        type: 'composio.searching',
        call_id: 'call_mail',
        tool_slug: 'GMAIL_LIST_EMAILS',
        detail: 'Connecting to Gmail...',
        timestamp: Date.now(),
      },
      label: 'Connecting to Gmail',
      phase: 'tool',
    },
    // Context resolves fastest (internal, no external API)
    {
      delay: 1400,
      event: {
        type: 'tool_result',
        task_id: 'task_ctx',
        call_id: 'call_ctx',
        tool_name: 'checkContext',
        status: 'completed',
        duration_ms: 200,
        result: 'Session focus: Q4 planning. Recent topics: executive email, board presentation, Drive access.',
      },
      label: 'Context retrieved',
      phase: 'tool',
    },
    // listFiles begins executing
    {
      delay: 1600,
      event: {
        type: 'tool.executing',
        call_id: 'call_files',
        timestamp: Date.now(),
      },
      label: 'Drive file listing in progress',
      phase: 'tool',
    },
    // Gmail begins executing
    {
      delay: 1900,
      event: {
        type: 'composio.executing',
        call_id: 'call_mail',
        tool_slug: 'GMAIL_LIST_EMAILS',
        detail: 'Fetching inbox messages...',
        timestamp: Date.now(),
      },
      label: 'Fetching Gmail messages',
      phase: 'tool',
    },
    // listFiles completes
    {
      delay: 1800,
      event: {
        type: 'tool_result',
        task_id: 'task_files',
        call_id: 'call_files',
        tool_name: 'listFiles',
        status: 'completed',
        duration_ms: 600,
        result: '8 recent files in Drive including Board_Presentation_2026_Q1.pptx and Q4_Revenue_Report.xlsx',
      },
      label: 'Drive files listed — 8 recent files',
      phase: 'tool',
    },
    // Gmail Composio completes
    {
      delay: 2600,
      event: {
        type: 'composio.completed',
        call_id: 'call_mail',
        tool_slug: 'GMAIL_LIST_EMAILS',
        detail: 'Inbox fetched successfully',
        duration_ms: 1200,
        timestamp: Date.now(),
      },
      label: 'Gmail fetch complete',
      phase: 'tool',
    },
    // Gmail tool_result
    {
      delay: 2650,
      event: {
        type: 'tool_result',
        task_id: 'task_mail',
        call_id: 'call_mail',
        tool_name: 'GMAIL_LIST_EMAILS',
        status: 'completed',
        duration_ms: 1430,
        result: '5 unread emails, 2 flagged items. Latest: "Re: Q4 Budget Review" from CFO.',
      },
      label: 'Gmail result — 5 unread, 2 flagged',
      phase: 'tool',
    },
    {
      delay: 2900,
      event: { type: 'agent.state', state: 'speaking' },
      label: 'Agent summarizing all results',
      phase: 'responding',
    },
    {
      delay: 3100,
      event: {
        type: 'transcript.assistant',
        text: "Here's your status: 5 unread emails with 2 flagged items, 8 recent files in Drive including the board presentation, and your session context shows we've been focused on Q4 planning. Want me to dig into any of these?",
        timestamp: Date.now(),
      },
      label: 'Agent speaks consolidated status',
      phase: 'responding',
    },
    {
      delay: 7500,
      event: { type: 'agent.state', state: 'listening' },
      label: 'Ready for next request',
      phase: 'complete',
    },
  ],
}

// =============================================================================
// Exported registry
// =============================================================================

export const SESSION_SCRIPTS: SessionScript[] = [
  emailSendScript,
  multiToolScript,
  errorRecoveryScript,
  concurrentScript,
]

export const SESSION_SCRIPTS_BY_ID: Record<string, SessionScript> = Object.fromEntries(
  SESSION_SCRIPTS.map(s => [s.id, s])
)
