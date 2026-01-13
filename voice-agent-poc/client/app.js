/**
 * Voice Agent App
 * Real-time voice assistant using OpenAI Realtime API
 * Designed for Recall.ai Output Media integration
 */

import { WavRecorder, WavStreamPlayer, RealtimeClient } from './lib/wavtools.js';

// ============================================================
// CONFIGURATION
// ============================================================

const CONFIG = {
  // Get relay server URL from query parameter
  relayServerUrl: new URLSearchParams(window.location.search).get('wss'),

  // Audio settings (matching OpenAI requirements)
  sampleRate: 24000,

  // n8n webhook URLs for tool execution
  n8nWebhooks: {
    calendar: new URLSearchParams(window.location.search).get('calendar_webhook'),
    email: new URLSearchParams(window.location.search).get('email_webhook'),
    crm: new URLSearchParams(window.location.search).get('crm_webhook'),
    knowledge: new URLSearchParams(window.location.search).get('knowledge_webhook')
  },

  // Webhook authentication
  webhookSecret: new URLSearchParams(window.location.search).get('webhook_secret') || ''
};

// System instructions for the voice agent
const SYSTEM_INSTRUCTIONS = `You are SYNRG, an intelligent voice assistant participating in a Microsoft Teams meeting.

## Your Capabilities
- You can hear all participants in the meeting
- You can respond with voice in real-time
- You have access to tools for calendar, email, and CRM operations

## Behavioral Guidelines
1. Be concise and professional - meetings have limited time
2. Speak naturally, as if you're a helpful colleague
3. When asked to perform actions, confirm before executing
4. If you miss something, politely ask for clarification
5. Keep responses under 30 seconds unless elaboration is requested

## Tool Usage
When users ask you to:
- Schedule/cancel/reschedule meetings → Use calendar tools
- Send/read emails → Use email tools
- Look up contacts or log interactions → Use CRM tools
- Answer questions about company data → Use knowledge base

## Personality
- Professional but warm
- Proactive in offering help
- Clear and articulate
- Patient with interruptions

## Important
- Always confirm before taking actions that affect external systems
- If unsure about a request, ask clarifying questions
- Announce when you're about to perform an action
`;

// Tool definitions for OpenAI function calling
const TOOLS = [
  {
    type: 'function',
    name: 'schedule_meeting',
    description: 'Schedule a new meeting on the calendar',
    parameters: {
      type: 'object',
      properties: {
        title: { type: 'string', description: 'Meeting title' },
        attendees: {
          type: 'array',
          items: { type: 'string' },
          description: 'List of attendee email addresses'
        },
        datetime: {
          type: 'string',
          description: 'Meeting start time in ISO 8601 format'
        },
        duration_minutes: {
          type: 'integer',
          description: 'Meeting duration in minutes',
          default: 30
        },
        description: { type: 'string', description: 'Meeting description' }
      },
      required: ['title', 'datetime']
    }
  },
  {
    type: 'function',
    name: 'check_calendar_availability',
    description: 'Check calendar availability for a specific time range',
    parameters: {
      type: 'object',
      properties: {
        start_datetime: { type: 'string', description: 'Start of time range (ISO 8601)' },
        end_datetime: { type: 'string', description: 'End of time range (ISO 8601)' },
        attendees: {
          type: 'array',
          items: { type: 'string' },
          description: 'Email addresses to check availability for'
        }
      },
      required: ['start_datetime', 'end_datetime']
    }
  },
  {
    type: 'function',
    name: 'send_email',
    description: 'Send an email',
    parameters: {
      type: 'object',
      properties: {
        to: {
          type: 'array',
          items: { type: 'string' },
          description: 'Recipient email addresses'
        },
        subject: { type: 'string', description: 'Email subject line' },
        body: { type: 'string', description: 'Email body content' },
        cc: {
          type: 'array',
          items: { type: 'string' },
          description: 'CC recipients'
        }
      },
      required: ['to', 'subject', 'body']
    }
  },
  {
    type: 'function',
    name: 'search_contacts',
    description: 'Search for contacts in CRM',
    parameters: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Search query (name, email, company)' },
        limit: { type: 'integer', description: 'Maximum results to return', default: 5 }
      },
      required: ['query']
    }
  },
  {
    type: 'function',
    name: 'query_knowledge_base',
    description: 'Search company knowledge base for information',
    parameters: {
      type: 'object',
      properties: {
        question: { type: 'string', description: 'Question to answer' },
        context: { type: 'string', description: 'Additional context for the search' }
      },
      required: ['question']
    }
  }
];

// ============================================================
// APPLICATION STATE
// ============================================================

const state = {
  connectionStatus: 'disconnected', // disconnected, connecting, connected
  isRecording: false,
  isSpeaking: false,
  error: null
};

// Client instances
let client = null;
let wavRecorder = null;
let wavStreamPlayer = null;

// ============================================================
// UI FUNCTIONS
// ============================================================

function updateUI() {
  const statusDot = document.getElementById('status-dot');
  const statusLabel = document.getElementById('status-label');
  const statusUrl = document.getElementById('status-url');
  const errorMessage = document.getElementById('error-message');
  const speakingIndicator = document.getElementById('speaking-indicator');

  // Update status dot color
  statusDot.className = 'status-dot';
  if (state.error) {
    statusDot.classList.add('error');
    statusLabel.textContent = 'Error:';
    statusUrl.textContent = state.error;
  } else {
    statusDot.classList.add(state.connectionStatus);
    switch (state.connectionStatus) {
      case 'connecting':
        statusLabel.textContent = 'Connecting to:';
        break;
      case 'connected':
        statusLabel.textContent = 'Connected to:';
        break;
      default:
        statusLabel.textContent = 'Disconnected';
    }
    statusUrl.textContent = CONFIG.relayServerUrl || 'No server configured';
  }

  // Update speaking indicator
  if (speakingIndicator) {
    speakingIndicator.style.display = state.isSpeaking ? 'flex' : 'none';
  }

  // Update error message
  if (errorMessage) {
    errorMessage.style.display = state.error ? 'block' : 'none';
    errorMessage.textContent = state.error || '';
  }
}

function setStatus(status) {
  state.connectionStatus = status;
  updateUI();
}

function setError(error) {
  state.error = error;
  updateUI();
}

function setSpeaking(speaking) {
  state.isSpeaking = speaking;
  updateUI();
}

// ============================================================
// TOOL EXECUTION
// ============================================================

async function executeTool(toolName, args) {
  console.log(`[Tool] Executing: ${toolName}`, args);

  // Map tool names to webhook endpoints
  const toolToWebhook = {
    'schedule_meeting': { base: CONFIG.n8nWebhooks.calendar, action: 'schedule' },
    'check_calendar_availability': { base: CONFIG.n8nWebhooks.calendar, action: 'availability' },
    'send_email': { base: CONFIG.n8nWebhooks.email, action: 'send' },
    'search_contacts': { base: CONFIG.n8nWebhooks.crm, action: 'search' },
    'query_knowledge_base': { base: CONFIG.n8nWebhooks.knowledge, action: 'query' }
  };

  const webhook = toolToWebhook[toolName];

  if (!webhook || !webhook.base) {
    console.warn(`[Tool] No webhook configured for: ${toolName}`);
    return {
      success: false,
      error: `Tool ${toolName} is not configured. Please set up the corresponding n8n webhook.`
    };
  }

  const webhookUrl = `${webhook.base}/${webhook.action}`;

  try {
    const response = await fetch(webhookUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Webhook-Secret': CONFIG.webhookSecret
      },
      body: JSON.stringify(args)
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const result = await response.json();
    console.log(`[Tool] Result:`, result);
    return result;

  } catch (error) {
    console.error(`[Tool] Error executing ${toolName}:`, error);
    return {
      success: false,
      error: error.message
    };
  }
}

// ============================================================
// MAIN CONNECTION LOGIC
// ============================================================

async function connectVoiceAgent() {
  // Validate configuration
  if (!CONFIG.relayServerUrl) {
    setError('Missing "wss" parameter in URL. Example: ?wss=wss://your-relay-server.com');
    return;
  }

  try {
    new URL(CONFIG.relayServerUrl);
  } catch {
    setError(`Invalid relay server URL: ${CONFIG.relayServerUrl}`);
    return;
  }

  setStatus('connecting');
  setError(null);

  try {
    // Initialize audio components
    wavRecorder = new WavRecorder({ sampleRate: CONFIG.sampleRate });
    wavStreamPlayer = new WavStreamPlayer({ sampleRate: CONFIG.sampleRate });

    // Initialize audio capture
    await wavRecorder.begin();
    console.log('[App] Microphone initialized');

    // Initialize audio output
    await wavStreamPlayer.connect();
    console.log('[App] Speaker initialized');

    // Initialize WebSocket client
    client = new RealtimeClient({ url: CONFIG.relayServerUrl });

    // Set up event handlers BEFORE connecting
    setupEventHandlers();

    // Connect to relay server
    await client.connect();
    console.log('[App] Connected to relay server');

    setStatus('connected');

    // Configure session
    client.updateSession({
      instructions: SYSTEM_INSTRUCTIONS,
      input_audio_format: 'pcm16',
      output_audio_format: 'pcm16',
      modalities: ['text', 'audio'],
      voice: 'alloy',
      turn_detection: {
        type: 'server_vad',
        threshold: 0.5,
        prefix_padding_ms: 300,
        silence_duration_ms: 500
      },
      tools: TOOLS,
      tool_choice: 'auto'
    });

    // Start recording microphone
    await wavRecorder.record((data) => {
      if (client && client.isConnected) {
        client.appendInputAudio(data.mono);
      }
    });

    state.isRecording = true;
    console.log('[App] Voice agent ready');

    // Send initial greeting prompt
    setTimeout(() => {
      client.sendUserMessageContent([{
        type: 'input_text',
        text: 'You have just joined a Teams meeting. Introduce yourself briefly.'
      }]);
    }, 1000);

  } catch (error) {
    console.error('[App] Connection failed:', error);
    setError(`Connection failed: ${error.message}`);
    setStatus('disconnected');
  }
}

function setupEventHandlers() {
  // Handle errors
  client.on('error', (event) => {
    console.error('[App] Client error:', event);
    setError(`Client error: ${event.message || 'Unknown error'}`);
  });

  // Handle disconnection
  client.on('disconnected', (event) => {
    console.log('[App] Disconnected:', event);
    setStatus('disconnected');
    state.isRecording = false;
  });

  // Handle audio output from OpenAI
  client.on('conversation.updated', async ({ item, delta }) => {
    if (delta?.audio) {
      setSpeaking(true);
      wavStreamPlayer.add16BitPCM(delta.audio, item.id);
    }
  });

  // Handle response completion
  client.on('response.done', (event) => {
    setSpeaking(false);
    console.log('[App] Response completed');
  });

  // Handle interruption (user started speaking while bot was talking)
  client.on('conversation.interrupted', async () => {
    console.log('[App] Interrupted by user');
    setSpeaking(false);

    const trackInfo = await wavStreamPlayer.interrupt();
    if (trackInfo?.trackId) {
      await client.cancelResponse(trackInfo.trackId, trackInfo.offset);
    }
  });

  // Handle function calls from OpenAI
  client.on('response.function_call_arguments.done', async (event) => {
    console.log('[App] Function call:', event);

    const { name, arguments: argsString, call_id } = event;

    try {
      const args = JSON.parse(argsString);
      const result = await executeTool(name, args);

      // Send tool result back to OpenAI
      client.send('conversation.item.create', {
        item: {
          type: 'function_call_output',
          call_id: call_id,
          output: JSON.stringify(result)
        }
      });

      // Trigger response with the tool result
      client.createResponse();

    } catch (error) {
      console.error('[App] Tool execution error:', error);

      // Send error back to OpenAI
      client.send('conversation.item.create', {
        item: {
          type: 'function_call_output',
          call_id: call_id,
          output: JSON.stringify({ error: error.message })
        }
      });
      client.createResponse();
    }
  });

  // Handle session creation confirmation
  client.on('session.created', (event) => {
    console.log('[App] Session created:', event.session?.id);
  });

  // Handle session update confirmation
  client.on('session.updated', (event) => {
    console.log('[App] Session updated');
  });

  // Log speech detection events
  client.on('input_audio_buffer.speech_started', () => {
    console.log('[App] User speech detected');
  });

  client.on('input_audio_buffer.speech_stopped', () => {
    console.log('[App] User speech ended');
  });
}

// ============================================================
// CLEANUP
// ============================================================

async function disconnect() {
  console.log('[App] Disconnecting...');

  if (wavRecorder) {
    await wavRecorder.end();
    wavRecorder = null;
  }

  if (wavStreamPlayer) {
    await wavStreamPlayer.disconnect();
    wavStreamPlayer = null;
  }

  if (client) {
    client.reset();
    client = null;
  }

  state.isRecording = false;
  setStatus('disconnected');
}

// Handle page unload
window.addEventListener('beforeunload', () => {
  disconnect();
});

// ============================================================
// INITIALIZATION
// ============================================================

// Auto-connect when page loads
document.addEventListener('DOMContentLoaded', () => {
  updateUI();
  connectVoiceAgent();
});

// Export for debugging
window.voiceAgent = {
  state,
  client,
  wavRecorder,
  wavStreamPlayer,
  connect: connectVoiceAgent,
  disconnect,
  executeTool
};
