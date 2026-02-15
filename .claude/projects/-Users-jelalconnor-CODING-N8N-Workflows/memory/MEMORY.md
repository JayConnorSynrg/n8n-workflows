# N8N Workflows - Auto Memory

## Critical Patterns

### n8n Connection Type Bug (2026-02-14)
**Issue:** `n8n_update_partial_workflow` `addConnection` operations create connections with `"type": "0"` instead of `"type": "main"`. This causes nodes to appear disconnected in the n8n UI even though the API returns success.

**Fix:** Use `n8n_update_full_workflow` with a complete connections object where ALL connections use `"type": "main"`. Never rely on `addConnection` from partial updates for new node wiring.

**SplitInBatches (Loop Over Items) connection format:**
```json
"Loop Over Items": {
  "main": [
    [],  // index 0 = "done" output
    [{ "node": "NextNode", "type": "main", "index": 0 }]  // index 1 = "loop" output
  ]
}
```

**See also:** `.claude/node-reference/base/split-in-batches-connections.md` (to be created after verification)

### n8n Partial Update Connection Operations - Use Full Update Instead
When adding multiple new nodes that need wiring, prefer `n8n_update_full_workflow` with the complete connections object rather than individual `addConnection` operations via `n8n_update_partial_workflow`. The partial API has a known issue where connection types get set to `"0"` instead of `"main"`.

### n8n updateNode REPLACES parameters — does NOT merge (2026-02-15)
**Severity:** CRITICAL — caused 3 failures in one session
**Issue:** `updateNode` with `updates.parameters` REPLACES the entire parameters object. Sending only `{ options: { systemMessage: "..." } }` erases `promptType` and `text`.
**Rule:** ALWAYS GET current parameters first, merge your changes, send COMPLETE object.
**Workflow AQjMRh9pqK5PebFq AI Agent requires ALL THREE:**
- `promptType: "define"`
- `text: "={{ $('Get chat message').item.json.body.content.replace(/<[^>]*>/g, '') }}"`
- `options.systemMessage: "..."`

### Anti-Pattern: Trusting sub-agent "success" without independent verification (2026-02-15)
**Severity:** CRITICAL — leads to false confidence and compounding errors
**Issue:** Sub-agents report "update applied successfully" based on API 200 responses, but the actual workflow state may not reflect the intended changes. Partial parameter erasure, wrong values, or no-ops can all return "success."
**Rule:** After EVERY workflow update, spawn a SEPARATE sub-agent to independently fetch the workflow and verify each expected change exists. Never trust the updating agent's own success report.
**Added:** Phase 4.75 to `.claude/skills/n8n-debugging/SKILL.md`

### Anti-Pattern: Fabricating technical explanations for unknown behavior (2026-02-15)
**Severity:** HIGH — creates false beliefs that persist across sessions
**Issue:** When encountering "Powered by this n8n workflow" in output, I fabricated the explanation "n8n AI Agent framework appends attribution" without evidence. I then implemented a band-aid regex fix based on this false belief. Investigation showed NO source for this text in any node, tool description, or webhook response.
**Rule:** When encountering unexpected behavior, investigate the actual source before explaining it. Never fabricate a technical explanation to justify a quick fix. If the source is unknown, say so.

### Microsoft Teams HTML Line Breaks (2026-02-15)
**Issue:** Teams "Create chat message" node uses `contentType: "html"`. HTML ignores `\n` characters — line breaks don't render.
**Fix:** Convert newlines to `<br>` tags BEFORE sending to Teams. Use a Code node (Format Enforcer) between AI Agent and Create chat message:
```javascript
text = text.replace(/\n\n/g, '<br><br>');  // paragraph breaks
text = text.replace(/\n/g, '<br>');         // line breaks
```
**Workflow AQjMRh9pqK5PebFq** has this implemented in the "Format Enforcer" node.

### Teams AI Agent Response Calibration (2026-02-15)
**User-approved format for workflow AQjMRh9pqK5PebFq:**
- 3 sections: TALENT POOL ASSESSMENT → STRONGEST MATCHES → RECOMMENDED NEXT SEARCH
- ALL CAPS section labels, blank lines between sections
- 100-150 words total (60-120 was too short, 80-200 was too verbose)
- 1-2 sentence pool overview, then 2-3 candidates with specific insights, then search refinement
- Plain text only — no asterisks, no markdown, no HTML
- Candidate names on own line with em dash + insight
- System prompt MUST include data-grounding directive: "Reference specific skills, certifications, and experience from each candidate profile"
- LLM settings: temperature 0.3, maxTokens 600 (450 was too low — truncated responses), topP 0.9

### Teams UX Patterns (2026-02-15)
- **Searching feedback:** Add "Searching applicant database now..." message BEFORE AI Agent for instant user feedback
- **Error handler:** AI Agent `onError: "continueErrorOutput"` + error path sends "Error database unavailable."
- **Both use contentType: "text"** (not html) for simple status messages

### SplitInBatches Done/Loop Output Index (2026-02-15)
**Issue:** When modifying SplitInBatches connections via API (especially replaceConnections), the empty array `[]` placeholder for the "done" output (index 0) gets dropped, causing the loop output to shift from index 1 to index 0. The node outputs data on index 1 but nothing is connected there.
**Fix:** ALWAYS include both array entries:
```json
"LoopNode": { "main": [ [], [{ "node": "Next", "type": "main", "index": 0 }] ] }
```
Index 0 = done (empty or final), Index 1 = loop body. Never omit the empty array.

### Code Node Return Statement Audit (2026-02-15)
**Issue:** Code nodes are opaque boundaries. Fields read into local variables but NOT included in the return statement are permanently lost. Downstream nodes referencing `$json.fieldName` get undefined.
**Rule:** After writing any Code node, audit the return statement against ALL downstream `$json.*` references (email templates, expressions, etc.). Every referenced field must be in the return object.

### Structured Output Parser Schema = AI Output Contract (2026-02-15)
**Issue:** If a downstream node reads `aiAnalysis.fieldName` but that field is NOT in the Structured Output Parser's jsonSchemaExample, the AI won't produce it. Silent failure — no error, just missing data.
**Rule:** Map ALL fields that downstream Code nodes read from AI output. Every such field MUST exist in the parser schema AND be mentioned in the system prompt's output requirements.
