/**
 * Confirmation Handler Code Node
 * Teams Voice Bot - Orchestrator Architecture v2.0
 *
 * Purpose: Handle yes/no confirmation for spelled email
 * Position: Output from State Router → confirmation_mode
 *
 * Input: Fast Classifier output + state data
 * Output: { response_text, new_state, confirmed_email, pending_action }
 */

// =============================================================================
// MAIN HANDLER LOGIC
// =============================================================================

const classifierResult = $('Fast Classifier').first().json;
const stateData = $('Load Bot State').first().json;
const confirmation = classifierResult.metadata.confirmation;
const emailAddress = stateData.email_chars || stateData.pending_email?.to || '';

// Initialize result
const result = {
  response_text: '',
  new_state: 'IDLE',
  confirmed_email: null,
  pending_action: null,
  skip_ai: true,
  metadata: {
    confirmation,
    emailAddress,
    previousState: stateData.state
  }
};

// =============================================================================
// HANDLE CONFIRMATION RESPONSE
// =============================================================================

if (confirmation === 'yes') {
  // User confirmed email is correct
  if (emailAddress && emailAddress.includes('@')) {
    result.confirmed_email = emailAddress;
    result.new_state = 'TOOL_EXECUTING';
    result.pending_action = 'send_email';
    result.skip_ai = false; // Route to AI agent for email composition

    // Set up data for AI agent
    result.ai_instruction = 'USER_CONFIRMED_EMAIL_ADDRESS';
    result.response_text = `Perfect. I'll compose and send that email now.`;

    // This will trigger parallel execution:
    // 1. TTS acknowledgment (this response_text)
    // 2. Gmail sub-workflow execution
  }
  else {
    // No email address found (shouldn't happen, but handle it)
    result.response_text = "I'm sorry, I don't have an email address to confirm. Let's start over. Who would you like to send an email to?";
    result.new_state = 'IDLE';
    result.pending_action = 'error_no_email';
  }
}
else if (confirmation === 'no') {
  // User said email is incorrect
  result.response_text = "No problem. Let's try again. Please spell the email address using phonetic letters like Alpha, Bravo, Charlie.";
  result.new_state = 'SPELLING_EMAIL';
  result.pending_action = 'restart_spelling';
  result.email_chars = ''; // Clear accumulated characters
}
else {
  // Unclear confirmation - ask again
  const formatEmail = (email) => {
    return email
      .replace(/@/g, ' at ')
      .replace(/\./g, ' dot ')
      .replace(/-/g, ' dash ')
      .replace(/_/g, ' underscore ');
  };

  const spoken = formatEmail(emailAddress);
  result.response_text = `I need a yes or no. Is ${spoken} the correct email address?`;
  result.new_state = 'CONFIRMING_EMAIL';
  result.pending_action = 'await_confirmation';
  result.email_chars = emailAddress; // Preserve the email
}

// =============================================================================
// RETURN RESULT
// =============================================================================

return [result];
