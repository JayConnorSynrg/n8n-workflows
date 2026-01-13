# Testing Guide: Teams Voice Bot

## Webhook URL

Production webhook (when activated):
```
https://jayconnorexe.app.n8n.cloud/webhook/transcript
```

Test webhook:
```
https://jayconnorexe.app.n8n.cloud/webhook-test/transcript
```

## Test with curl

### 1. Valid Final Transcript (Should Process)

```bash
curl -X POST https://jayconnorexe.app.n8n.cloud/webhook-test/transcript \
  -H "Content-Type: application/json" \
  -d @test-payloads/transcript-event.json
```

Expected response:
```json
{
  "status": "received"
}
```

### 2. Partial Transcript (Should Filter Out)

```bash
curl -X POST https://jayconnorexe.app.n8n.cloud/webhook-test/transcript \
  -H "Content-Type: application/json" \
  -d @test-payloads/partial-transcript.json
```

This should still return `{"status": "received"}` but the AI agent will not be triggered (filtered out).

### 3. Bot Self-Transcript (Should Filter Out)

```bash
curl -X POST https://jayconnorexe.app.n8n.cloud/webhook-test/transcript \
  -H "Content-Type: application/json" \
  -d @test-payloads/bot-self-transcript.json
```

This tests that the bot doesn't respond to its own speech.

## Expected Execution Flow

For a valid transcript event:

1. **Receive Transcript** - Webhook receives POST
2. **Filter Final Transcripts** - Checks `is_final === true` and `speaker_name !== 'AI Voice Assistant'`
3. **Extract Transcript Data** - Parses transcript text, speaker, bot_id
4. **AI Voice Assistant** - Generates conversational response
5. **Send Audio to Meeting** - Prepares audio response payload
6. **Respond OK** - Returns 200 with status

## Debugging

### Check Recent Executions

```bash
# Using n8n MCP
n8n_executions action=list workflowId=gjYSN6xNjLw8qsA1 limit=5
```

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Empty AI response | Transcript not extracted properly | Check Set node field mappings |
| No response | Filter blocking all events | Verify `is_final: true` in payload |
| 500 error | OpenAI API key not set | Configure OpenAI credentials in n8n |
| Loop detected | Bot responding to itself | Verify filter excludes 'AI Voice Assistant' |

## Integration Test Checklist

- [ ] Webhook receives POST and returns 200
- [ ] Filter correctly passes final transcripts
- [ ] Filter correctly blocks partial transcripts
- [ ] Filter correctly blocks bot self-transcripts
- [ ] AI Agent generates appropriate response
- [ ] Response payload is properly formatted
- [ ] Memory persists across conversation turns
