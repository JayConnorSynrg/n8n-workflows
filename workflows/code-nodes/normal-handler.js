/**
 * Normal Handler Code Node
 * Teams Voice Bot - Orchestrator Architecture v2.0
 *
 * Purpose: Handle normal conversation mode - detect email commands, route to AI
 * Position: Output from State Router → normal (IDLE/LISTENING state)
 *
 * Input: Fast Classifier output + state data + transcript
 * Output: { response_text, new_state, pending_action, skip_ai }
 */

// =============================================================================
// CONFIGURATION
// =============================================================================

const GREETING_RESPONSES = [
  "Hi! I'm your AI assistant. How can I help you today?",
  "Hello! I'm ready to help. What would you like to do?",
  "Hey there! I can help you send emails, answer questions, or assist with other tasks."
];

const EMAIL_DETECTED_RESPONSE = "I'd be happy to help you send an email. To make sure I get the address right, please spell it out using phonetic letters like Alpha for A, Bravo for B, or just say the letters clearly.";

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

function getRandomGreeting() {
  return GREETING_RESPONSES[Math.floor(Math.random() * GREETING_RESPONSES.length)];
}

function extractEmailFromTranscript(transcript) {
  // Try to find email address directly in transcript
  const emailMatch = transcript.match(/([a-zA-Z0-9._-]+@[a-zA-Z0-9._-]+\.[a-zA-Z0-9_-]+)/);
  return emailMatch ? emailMatch[1] : null;
}

function extractRecipientName(transcript) {
  // Try to extract recipient name from phrases like "email to John" or "send John an email"
  const patterns = [
    /email\s+(?:to\s+)?([A-Z][a-z]+)/i,
    /send\s+([A-Z][a-z]+)\s+an?\s+email/i,
    /message\s+(?:to\s+)?([A-Z][a-z]+)/i
  ];

  for (const pattern of patterns) {
    const match = transcript.match(pattern);
    if (match && match[1]) {
      return match[1];
    }
  }
  return null;
}

// =============================================================================
// MAIN HANDLER LOGIC
// =============================================================================

const classifierResult = $('Fast Classifier').first().json;
const stateData = $('Load Bot State').first().json;
const transcript = classifierResult.metadata.transcript || '';
const intent = classifierResult.intent;
const route = classifierResult.route;

// Initialize result
const result = {
  response_text: '',
  new_state: 'LISTENING',
  pending_action: null,
  skip_ai: false,
  metadata: {
    intent,
    route,
    transcript,
    previousState: stateData.state
  }
};

// =============================================================================
// ROUTE BY INTENT
// =============================================================================

switch (intent) {
  case 'greeting':
    // Simple greeting - direct response
    result.response_text = getRandomGreeting();
    result.new_state = 'LISTENING';
    result.skip_ai = true;
    result.pending_action = 'greeted';
    break;

  case 'email_request':
    // User wants to send an email
    const directEmail = extractEmailFromTranscript(transcript);
    const recipientName = extractRecipientName(transcript);

    if (directEmail) {
      // Email address was spoken directly - skip to confirmation
      const spoken = directEmail
        .replace(/@/g, ' at ')
        .replace(/\./g, ' dot ');

      result.response_text = `I heard ${spoken}. Is that correct?`;
      result.new_state = 'CONFIRMING_EMAIL';
      result.email_chars = directEmail;
      result.skip_ai = true;
      result.pending_action = 'await_confirmation';
    }
    else if (recipientName) {
      // Got a name but need email address
      result.response_text = `I'll help you email ${recipientName}. Please spell their email address using phonetic letters like Alpha, Bravo, Charlie.`;
      result.new_state = 'SPELLING_EMAIL';
      result.skip_ai = true;
      result.pending_action = 'await_spelling';
      result.metadata.recipientName = recipientName;
    }
    else {
      // No email or name detected - prompt for spelling
      result.response_text = EMAIL_DETECTED_RESPONSE;
      result.new_state = 'SPELLING_EMAIL';
      result.skip_ai = true;
      result.pending_action = 'await_spelling';
    }
    break;

  case 'question':
  case 'command':
    // Route to AI agent for processing
    result.skip_ai = false;
    result.new_state = 'LISTENING';
    result.pending_action = 'ai_processing';

    // Don't set response_text - let AI generate it
    break;

  case 'irrelevant':
    // Should have been filtered as silent_ignore
    result.skip_ai = true;
    result.new_state = stateData.state || 'IDLE';
    result.pending_action = 'no_action';
    break;

  default:
    // Unknown intent - route to AI as fallback
    result.skip_ai = false;
    result.new_state = 'LISTENING';
    result.pending_action = 'ai_fallback';
}

// =============================================================================
// COMPLETE THOUGHT CHECK
// =============================================================================

// If routing to AI but thought is incomplete, wait for more
if (!result.skip_ai && !classifierResult.isCompleteThought) {
  result.skip_ai = true;
  result.new_state = 'LISTENING';
  result.pending_action = 'awaiting_complete_thought';
  result.metadata.incompleteThought = true;
  // No response - silently wait for more speech
}

// =============================================================================
// RETURN RESULT
// =============================================================================

return [result];
