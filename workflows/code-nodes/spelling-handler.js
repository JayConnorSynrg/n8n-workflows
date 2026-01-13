/**
 * Spelling Handler Code Node
 * Teams Voice Bot - Orchestrator Architecture v2.0
 *
 * Purpose: Handle email spelling mode (NATO phonetic alphabet)
 * Position: Output from State Router → spelling_mode
 *
 * Input: Fast Classifier output + state data
 * Output: { response_text, new_state, email_chars, pending_action }
 */

// =============================================================================
// NATO PHONETIC ALPHABET MAP
// =============================================================================

const NATO_PHONETIC = {
  // Letters
  'alpha': 'a', 'bravo': 'b', 'charlie': 'c', 'delta': 'd', 'echo': 'e',
  'foxtrot': 'f', 'golf': 'g', 'hotel': 'h', 'india': 'i', 'juliet': 'j',
  'kilo': 'k', 'lima': 'l', 'mike': 'm', 'november': 'n', 'oscar': 'o',
  'papa': 'p', 'quebec': 'q', 'romeo': 'r', 'sierra': 's', 'tango': 't',
  'uniform': 'u', 'victor': 'v', 'whiskey': 'w', 'x-ray': 'x', 'xray': 'x',
  'yankee': 'y', 'zulu': 'z',

  // Special characters
  'at': '@', 'at sign': '@', 'at symbol': '@',
  'dot': '.', 'period': '.', 'point': '.',
  'dash': '-', 'hyphen': '-', 'minus': '-',
  'underscore': '_', 'under score': '_',
  'plus': '+',

  // Numbers
  'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
  'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9',

  // Common domain shortcuts
  'gmail': 'gmail', 'hotmail': 'hotmail', 'yahoo': 'yahoo',
  'outlook': 'outlook', 'icloud': 'icloud',
  'com': 'com', 'org': 'org', 'net': 'net', 'edu': 'edu', 'gov': 'gov'
};

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

function extractCharsFromTranscript(transcript) {
  const normalized = transcript.toLowerCase().trim();
  const words = normalized.split(/\s+/);
  const chars = [];

  for (let i = 0; i < words.length; i++) {
    const word = words[i];

    // Check multi-word phrases first ("at sign", "under score")
    const twoWordPhrase = words.slice(i, i + 2).join(' ');
    if (NATO_PHONETIC[twoWordPhrase]) {
      chars.push(NATO_PHONETIC[twoWordPhrase]);
      i++; // Skip next word
      continue;
    }

    // Check NATO phonetic
    if (NATO_PHONETIC[word]) {
      chars.push(NATO_PHONETIC[word]);
    }
    // Check single letter
    else if (/^[a-z]$/.test(word)) {
      chars.push(word);
    }
    // Check single digit
    else if (/^[0-9]$/.test(word)) {
      chars.push(word);
    }
    // Check "letter X" pattern
    else if (i + 1 < words.length && word === 'letter' && /^[a-z]$/.test(words[i + 1])) {
      chars.push(words[i + 1]);
      i++;
    }
    // Check "number X" pattern
    else if (i + 1 < words.length && word === 'number' && /^[0-9]$/.test(words[i + 1])) {
      chars.push(words[i + 1]);
      i++;
    }
  }

  return chars;
}

function isEmailValid(email) {
  // Basic email validation
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

function formatEmailForSpeech(email) {
  // Format email for TTS readback
  return email
    .replace(/@/g, ' at ')
    .replace(/\./g, ' dot ')
    .replace(/-/g, ' dash ')
    .replace(/_/g, ' underscore ');
}

// =============================================================================
// MAIN HANDLER LOGIC
// =============================================================================

const classifierResult = $('Fast Classifier').first().json;
const stateData = $('Load Bot State').first().json;
const transcript = classifierResult.metadata.transcript || '';

// Get accumulated characters from state
let accumulatedChars = (stateData.email_chars || '').split('');
const intent = classifierResult.intent;

// Initialize result
const result = {
  response_text: '',
  new_state: 'SPELLING_EMAIL',
  email_chars: '',
  pending_action: null,
  skip_ai: true,
  metadata: {
    previousChars: stateData.email_chars || '',
    transcript
  }
};

// =============================================================================
// HANDLE DIFFERENT INTENTS
// =============================================================================

if (intent === 'spelling_complete') {
  // User said "done" - finalize email
  const finalEmail = accumulatedChars.join('');

  if (finalEmail.length === 0) {
    // No characters accumulated
    result.response_text = "I haven't received any characters yet. Please spell the email address using letters like Alpha, Bravo, Charlie.";
    result.new_state = 'SPELLING_EMAIL';
  }
  else if (!isEmailValid(finalEmail)) {
    // Invalid email format
    const spoken = formatEmailForSpeech(finalEmail);
    result.response_text = `I have ${spoken}, but it doesn't look like a complete email address. Would you like to continue spelling, or say 'start over' to begin again?`;
    result.new_state = 'SPELLING_EMAIL';
    result.email_chars = accumulatedChars.join('');
  }
  else {
    // Valid email - move to confirmation
    const spoken = formatEmailForSpeech(finalEmail);
    result.response_text = `I have ${spoken}. Is that correct?`;
    result.new_state = 'CONFIRMING_EMAIL';
    result.email_chars = finalEmail;
    result.pending_action = 'await_confirmation';
  }
}
else if (intent === 'spelling_continue') {
  // Extract new characters from transcript
  const newChars = extractCharsFromTranscript(transcript);

  if (newChars.length > 0) {
    // Add new characters
    accumulatedChars.push(...newChars);
    const current = accumulatedChars.join('');
    const spoken = formatEmailForSpeech(current);

    result.response_text = `Got it. So far I have: ${spoken}`;
    result.email_chars = current;
    result.new_state = 'SPELLING_EMAIL';
  }
  else {
    // No characters recognized - provide help
    result.response_text = "I didn't catch that. Please use phonetic letters like Alpha for A, Bravo for B, or say 'at sign' for @.";
    result.email_chars = accumulatedChars.join('');
    result.new_state = 'SPELLING_EMAIL';
  }
}
else {
  // Unexpected intent in spelling mode
  result.response_text = "I'm currently in email spelling mode. Please continue spelling, or say 'done' when finished, or 'cancel' to exit.";
  result.email_chars = accumulatedChars.join('');
  result.new_state = 'SPELLING_EMAIL';
}

// Check for cancel/restart commands
const lowerTranscript = transcript.toLowerCase();
if (lowerTranscript.includes('cancel') || lowerTranscript.includes('start over') || lowerTranscript.includes('restart')) {
  result.response_text = "Okay, I've cleared the email address. You can spell a new one, or say something else if you'd like to do something different.";
  result.email_chars = '';
  result.new_state = 'IDLE';
  result.pending_action = 'cancelled';
}

// =============================================================================
// RETURN RESULT
// =============================================================================

result.metadata.newChars = accumulatedChars.join('');
return [result];
