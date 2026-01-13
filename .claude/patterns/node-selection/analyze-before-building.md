# Pattern: Always Analyze Working Examples Before Building

> **Priority**: HIGH
>
> **Workflow**: dev-marketing-image-quality-loop (ID: 8bhcEHkbbvnhdHBh)
>
> **Date**: 2025-11-22

---

## Anti-Pattern: Assumed Node Types Without Verifying Working Implementation

### What Happened

When building workflow `dev-marketing-image-quality-loop` to create an iterative image quality loop, I created three nodes based on assumptions instead of analyzing the working prototype first:

1. **"Refine Prompt with GPT-4"** - Used `@n8n/n8n-nodes-langchain.openAi` with `resource: "text"` and `operation: "generate"` - This node configuration doesn't exist in n8n
2. **"Generate Image with DALL-E-3"** - Used correct node type but didn't verify exact parameter structure
3. **"Analyze Quality with Vision AI"** - Guessed at configuration instead of replicating proven working setup

### Impact

- Workflow creation failed completely - all three nodes were non-functional
- Required user intervention to troubleshoot
- Wasted development time creating invalid nodes
- User had to provide prototype workflow ID (bEA0VHpyvazFmhYO) for reference
- Had to rebuild workflow from scratch

### Why It Failed

- Skipped the critical discovery step of analyzing working examples before implementation
- Assumed that n8n OpenAI nodes had a `resource: "text"` configuration when they don't
- Didn't understand that AI text generation in n8n requires the **AI Agent pattern**: `@n8n/n8n-nodes-langchain.agent` connected to separate `lmChatOpenAi` and `memoryBufferWindow` nodes via special connection types (`ai_languageModel` and `ai_memory`)
- Didn't use available MCP tool (`mcp__n8n-mcp__n8n_get_workflow`) to fetch and analyze the prototype structure first

---

## Positive Pattern: Always Analyze Working Examples Before Building New Workflows

### Solution

Fetch and thoroughly analyze working prototype workflows using MCP tools BEFORE attempting to build similar functionality.

### Implementation

1. **Discovery Phase** - User provided prototype workflow ID `bEA0VHpyvazFmhYO`

2. **Analysis Phase** - Called `mcp__n8n-mcp__n8n_get_workflow({ id: "bEA0VHpyvazFmhYO" })` to fetch complete workflow structure

3. **Documentation Phase** - Documented exact node configurations:
   - **AI Agent for text generation:**
     - Type: `@n8n/n8n-nodes-langchain.agent` (typeVersion 2)
     - Parameters: `promptType: "define"`, `text: "{{ prompt }}"`, `options.systemMessage: "..."`
     - Requires separate `lmChatOpenAi` node connected via `ai_languageModel` connection type
     - Requires separate `memoryBufferWindow` node connected via `ai_memory` connection type
   - **Image Generation:**
     - Type: `@n8n/n8n-nodes-langchain.openAi`
     - Parameters: `resource: "image"`, `model: "dall-e-3"`, `prompt: "={{ $json.output }}"`
   - **Image Analysis:**
     - Type: `@n8n/n8n-nodes-langchain.openAi`
     - Parameters: `resource: "image"`, `operation: "analyze"`, `modelId: "chatgpt-4o-latest"`, `inputType: "base64"`, `binaryPropertyName: "data"`

4. **Rebuild Phase** - Used `mcp__n8n-mcp__n8n_update_full_workflow` to replace broken nodes with correct configurations

5. **Validation Phase** - Called `mcp__n8n-mcp__n8n_validate_workflow` to confirm workflow structure was valid

### Result

- Workflow `dev-marketing-image-quality-loop` now has correctly configured nodes
- All three critical nodes (AI Agent, Image Generation, Image Analysis) are functional
- Workflow passed validation (only expected "cycle" warning for intentional quality loop)
- Pattern documented to prevent future similar mistakes

---

## Reusable Pattern: Workflow Development Sequence

**ALWAYS follow this workflow development sequence:**

```
1. DISCOVER - Search for similar working workflows or templates
   Use: mcp__n8n-mcp__search_templates({ query: "..." })
   Use: mcp__n8n-mcp__search_nodes({ query: "..." })

2. ANALYZE - Fetch and study working examples
   Use: mcp__n8n-mcp__n8n_get_workflow({ id: "prototype-id" })
   Document exact node types, parameters, connections

3. REPLICATE - Build new workflow using proven node structures
   Don't assume or guess - copy working configurations exactly

4. CUSTOMIZE - Modify parameters for your specific use case
   Keep node types and connection patterns the same

5. VALIDATE - Check workflow structure
   Use: mcp__n8n-mcp__n8n_validate_workflow({ id: "..." })
```

---

## Key Learnings

- n8n AI nodes use **specific patterns** that aren't obvious:
  - Text generation = AI Agent + Language Model + Memory (3 nodes, 2 special connections)
  - Image generation = `openAi` node with `resource: "image"`, `model: "dall-e-3"`
  - Image analysis = `openAi` node with `resource: "image"`, `operation: "analyze"`
- There is NO `resource: "text"` configuration for OpenAI nodes
- Model names must be exact: `"dall-e-3"` not `"gpt-image-1"`, `"gpt-4-turbo"` not `"gpt-5"`
- MCP tools provide the ground truth - always check actual implementation before building

---

**Date**: 2025-11-22
**Source Pattern**: agents-evolution.md - Node Selection Patterns
