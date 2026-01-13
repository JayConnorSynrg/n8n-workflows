/**
 * Fast Classifier Code Node
 * Teams Voice Bot - Orchestrator Architecture v2.0
 *
 * Purpose: Ultra-fast intent classification without LLM overhead
 * Position: After Load Bot State, before Logging Agent
 *
 * Input: $json from Extract Transcript Data + state from Load Bot State
 * Output: { route, intent, isCompleteThought, shouldRespond, confidence, metadata }
 */

// =============================================================================
// CONFIGURATION
// =============================================================================

const BOT_NAMES = [
  'bot', 'assistant', 'ai', 'hey bot', 'hello bot', 'ok bot',
  'synergy', 'synrg', 'hey assistant', 'voice assistant'
];

const EMAIL_PATTERNS = [
  /send\s*(an?\s*)?email/i,
  /email\s*(to|about)/i,
  /compose\s*(an?\s*)?email/i,
  /draft\s*(an?\s*)?email/i,
  /write\s*(an?\s*)?email/i,
  /message\s*to\s*\S+@/i
];

const QUESTION_PATTERNS = [
  /\?$/,
  /^(what|how|when|where|why|who|which|can you|could you|would you|will you|is there|are there|do you|does|did)/i,
  /tell me (about|how|what|when|where|why)/i,
  /explain/i,
  /help me/i
];

const GREETING_PATTERNS = [
  /^(hi|hello|hey|good morning|good afternoon|good evening)/i,
  /^(greetings|howdy|what'?s up)/i
];

const CONFIRMATION_YES = [
  'yes', 'yeah', 'yep', 'correct', 'right', 'that\'s right',
  'affirmative', 'confirm', 'confirmed', 'absolutely', 'definitely'
];

const CONFIRMATION_NO = [
  'no', 'nope', 'incorrect', 'wrong', 'that\'s wrong',
  'negative', 'cancel', 'restart', 'start over', 'try again'
];

const SPELLING_END_KEYWORDS = [
  'done', 'finished', 'complete', 'that\'s it', 'thats it',
  'end', 'stop', 'okay done', 'ok done'
];

// NATO phonetic alphabet + common spoken characters
const NATO_PHONETIC = {
  'alpha': 'a', 'bravo': 'b', 'charlie': 'c', 'delta': 'd', 'echo': 'e',
  'foxtrot': 'f', 'golf': 'g', 'hotel': 'h', 'india': 'i', 'juliet': 'j',
  'kilo': 'k', 'lima': 'l', 'mike': 'm', 'november': 'n', 'oscar': 'o',
  'papa': 'p', 'quebec': 'q', 'romeo': 'r', 'sierra': 's', 'tango': 't',
  'uniform': 'u', 'victor': 'v', 'whiskey': 'w', 'x-ray': 'x', 'xray': 'x',
  'yankee': 'y', 'zulu': 'z',
  // Special characters
  'at': '@', 'at sign': '@', 'at symbol': '@',
  'dot': '.', 'period': '.', 'point': '.',
  'dash': '-', 'hyphen': '-',
  'underscore': '_', 'under score': '_',
  // Numbers
  'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
  'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9'
};

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

function normalizeText(text) {
  return (text || '').toLowerCase().trim();
}

function containsBotAddress(transcript) {
  const normalized = normalizeText(transcript);
  return BOT_NAMES.some(name => normalized.includes(name));
}

function matchesPatterns(transcript, patterns) {
  return patterns.some(pattern => pattern.test(transcript));
}

function isCompleteThought(transcript) {
  const normalized = normalizeText(transcript);

  // Ends with punctuation
  if (/[.!?]$/.test(normalized)) return true;

  // Contains polite closers
  if (/\b(please|thanks|thank you|that's all)\b/i.test(normalized)) return true;

  // Is a confirmation
  if (CONFIRMATION_YES.some(c => normalized.includes(c))) return true;
  if (CONFIRMATION_NO.some(c => normalized.includes(c))) return true;

  // Short complete phrases
  if (normalized.split(' ').length <= 3 && containsBotAddress(normalized)) return true;

  return false;
}

function detectSpellingEnd(transcript) {
  const normalized = normalizeText(transcript);
  return SPELLING_END_KEYWORDS.some(kw => normalized.includes(kw));
}

function extractSpellingChars(transcript) {
  const normalized = normalizeText(transcript);
  const words = normalized.split(/\s+/);
  const chars = [];

  for (const word of words) {
    // Check NATO phonetic
    if (NATO_PHONETIC[word]) {
      chars.push(NATO_PHONETIC[word]);
    }
    // Check single letter/number
    else if (/^[a-z0-9]$/.test(word)) {
      chars.push(word);
    }
    // Check letter name ("letter a", "the letter b")
    else if (/^(letter\s+)?[a-z]$/i.test(word)) {
      const match = word.match(/[a-z]$/i);
      if (match) chars.push(match[0].toLowerCase());
    }
  }

  return chars;
}

function classifyConfirmation(transcript) {
  const normalized = normalizeText(transcript);

  if (CONFIRMATION_YES.some(c => normalized.includes(c))) {
    return 'yes';
  }
  if (CONFIRMATION_NO.some(c => normalized.includes(c))) {
    return 'no';
  }
  return 'unclear';
}

// =============================================================================
// MAIN CLASSIFICATION LOGIC
// =============================================================================

const input = $input.first().json;
const stateData = $('Load Bot State').first().json;

const transcript = input.transcript || '';
const normalizedTranscript = normalizeText(transcript);
const currentState = stateData.state || 'IDLE';
const messageCount = stateData.message_count || 0;

// Initialize result
const result = {
  route: 'silent_ignore',
  intent: 'irrelevant',
  isCompleteThought: false,
  shouldRespond: false,
  confidence: 0.0,
  metadata: {
    currentState,
    messageCount,
    transcript,
    timestamp: new Date().toISOString()
  }
};

// =============================================================================
// STATE-AWARE ROUTING
// =============================================================================

if (currentState === 'SPELLING_EMAIL') {
  // In spelling mode - handle character accumulation or completion
  result.isCompleteThought = detectSpellingEnd(transcript);

  if (result.isCompleteThought) {
    result.route = 'spelling_mode';
    result.intent = 'spelling_complete';
    result.shouldRespond = true;
    result.confidence = 0.95;
  } else {
    // Extract and accumulate characters
    const newChars = extractSpellingChars(transcript);
    result.route = 'spelling_mode';
    result.intent = 'spelling_continue';
    result.shouldRespond = newChars.length > 0;
    result.confidence = newChars.length > 0 ? 0.9 : 0.5;
    result.metadata.extractedChars = newChars;
  }
}
else if (currentState === 'CONFIRMING_EMAIL') {
  // In confirmation mode - handle yes/no
  const confirmation = classifyConfirmation(transcript);
  result.route = 'confirmation_mode';
  result.intent = `confirmation_${confirmation}`;
  result.isCompleteThought = confirmation !== 'unclear';
  result.shouldRespond = true;
  result.confidence = confirmation !== 'unclear' ? 0.95 : 0.6;
  result.metadata.confirmation = confirmation;
}
else if (currentState === 'TOOL_EXECUTING') {
  // Tool is still executing - acknowledge but don't process new commands
  result.route = 'silent_ignore';
  result.intent = 'tool_in_progress';
  result.shouldRespond = false;
  result.confidence = 0.99;
}
else {
  // IDLE or LISTENING state - full classification

  // Check if bot is addressed
  const botAddressed = containsBotAddress(transcript);
  result.metadata.botAddressed = botAddressed;

  if (!botAddressed) {
    // Not addressed - silent ignore (background chatter)
    result.route = 'silent_ignore';
    result.intent = 'irrelevant';
    result.shouldRespond = false;
    result.confidence = 0.85;
  }
  else {
    // Bot is addressed - classify intent
    result.isCompleteThought = isCompleteThought(transcript);

    // Check for first message (greeting)
    if (messageCount === 0 && matchesPatterns(transcript, GREETING_PATTERNS)) {
      result.route = 'greeting_direct';
      result.intent = 'greeting';
      result.shouldRespond = true;
      result.confidence = 0.95;
    }
    // Check for email request
    else if (matchesPatterns(transcript, EMAIL_PATTERNS)) {
      result.route = 'tool_call';
      result.intent = 'email_request';
      result.shouldRespond = true;
      result.confidence = 0.9;
      result.metadata.toolType = 'gmail';
    }
    // Check for question
    else if (matchesPatterns(transcript, QUESTION_PATTERNS)) {
      result.route = 'chat_agent';
      result.intent = 'question';
      result.shouldRespond = result.isCompleteThought;
      result.confidence = 0.85;
    }
    // Default to chat agent for addressed but unclassified
    else {
      result.route = 'chat_agent';
      result.intent = 'command';
      result.shouldRespond = result.isCompleteThought;
      result.confidence = 0.7;
    }
  }
}

// =============================================================================
// COMPLETE THOUGHT GATING
// =============================================================================

// For chat agent route, require complete thought before responding
if (result.route === 'chat_agent' && !result.isCompleteThought) {
  // User still speaking - wait for more
  result.shouldRespond = false;
  result.metadata.waitingForComplete = true;
}

// =============================================================================
// RETURN RESULT
// =============================================================================

return [result];
