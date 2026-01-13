# Pattern: AI Agent with Sub-Workflow Tool

**Category:** Workflow Architecture
**Quality Level:** ✅ Production-Ready
**Source:** n8n Template #9191
**Complexity:** Complex

---

## Overview

Create an AI Agent that can dynamically call sub-workflows as tools. The agent decides when and how to use tools based on its system prompt and user input, enabling modular, intelligent automation.

---

## When to Use

✅ **Use this pattern when:**
- AI needs to decide dynamically which operations to perform
- Complex capabilities should be abstracted into reusable tools
- Multiple workflows need access to the same functionality
- Decision-making logic is better handled by AI than hardcoded conditionals
- You want to extend agent capabilities without modifying main workflow

❌ **Don't use when:**
- Simple linear workflow (no decision-making needed)
- Operations always execute in same order (use regular Execute Workflow)
- Tool logic is trivial (1-2 nodes)
- Performance is critical (AI decisions add latency)

---

## Pattern Structure

```
AI Agent Node
├─ Connection: ai_languageModel → OpenAI Chat Model Node
├─ Connection: ai_memory → Memory Node
└─ Connection: ai_tool → Tool: Workflow Node
                             ↓
                    Execute Sub-Workflow
                             ↓
                    Return Structured Result
                             ↓
                    Agent Processes Result
                             ↓
                    Agent Continues or Calls More Tools
```

---

## Key Components

### 1. AI Agent Node
**Type:** `@n8n/n8n-nodes-langchain.agent`
**Purpose:** Orchestrate decision-making and tool usage

**Configuration:**
```json
{
  "promptType": "define",
  "text": "={{ $json.user_input }}",
  "hasOutputParser": true,
  "options": {
    "systemMessage": "You are an expert assistant that helps with [domain]. You have access to tools that can [capabilities]. Use these tools when appropriate to accomplish the user's request."
  }
}
```

**Connections Required:**
- `ai_languageModel` → OpenAI Chat Model Node
- `ai_memory` → Memory Node
- `ai_tool` → Tool: Workflow Node(s) (can connect multiple tools)

### 2. OpenAI Chat Model Node
**Type:** `@n8n/n8n-nodes-langchain.lmChatOpenAi`
**Purpose:** Provide language model for agent reasoning

**Configuration:**
```json
{
  "model": "gpt-4-turbo",
  "options": {
    "temperature": 0.7,
    "maxTokens": 2000
  }
}
```

### 3. Memory Node
**Type:** `@n8n/n8n-nodes-langchain.memoryBufferWindow`
**Purpose:** Maintain conversation context

**Configuration:**
```json
{
  "contextWindowLength": 5
}
```

### 4. Tool: Workflow Node
**Type:** `@n8n/n8n-nodes-langchain.toolWorkflow`
**Purpose:** Connect agent to sub-workflow capability

**Configuration:**
```json
{
  "name": "generate_image",
  "description": "Generates an AI image based on a text prompt. Returns the image URL and metadata. Use this when the user asks to create, generate, or make an image.",
  "workflowId": "{{ $parameter.workflowId }}",
  "fields": {
    "values": [
      {
        "name": "prompt",
        "type": "string",
        "description": "The detailed text prompt describing the image to generate"
      },
      {
        "name": "size",
        "type": "options",
        "description": "Image size (default: 1024x1024)",
        "options": ["1024x1024", "1024x1792", "1792x1024"]
      }
    ]
  },
  "specifyInputSchema": true
}
```

### 5. Output Parser Node
**Type:** `@n8n/n8n-nodes-langchain.outputParserStructured`
**Purpose:** Extract structured data from agent's final response

**Configuration:**
```json
{
  "jsonSchemaExample": {
    "type": "object",
    "properties": {
      "result": {
        "type": "string",
        "description": "The final result or answer"
      },
      "images_generated": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "url": { "type": "string" },
            "description": { "type": "string" }
          }
        }
      },
      "status": {
        "type": "string",
        "enum": ["success", "partial_success", "failure"]
      }
    },
    "required": ["result", "status"]
  }
}
```

---

## Sub-Workflow Requirements

The workflow called by the tool MUST:
1. Accept input via `Execute Workflow Trigger` node
2. Return structured output via `Respond to Workflow` node
3. Handle errors gracefully (don't crash parent workflow)

**Example Sub-Workflow Structure:**
```
Execute Workflow Trigger
    ↓
Extract Parameters (Set node)
    ↓
Perform Operation (HTTP Request, etc.)
    ↓
IF: Success?
├─ True → Format Success Response
└─ False → Format Error Response
    ↓
Respond to Workflow (structured JSON)
```

**Response Format:**
```json
{
  "success": true,
  "result": {
    "image_url": "https://...",
    "metadata": { "size": "1024x1024", "model": "dall-e-3" }
  },
  "error": null
}
```

---

## Connection Types Explained

**Why Special Connections?**

n8n AI nodes use typed connections to ensure compatibility:

- `ai_languageModel` - Connects agent to LLM (OpenAI, Anthropic, etc.)
- `ai_memory` - Connects agent to conversation memory
- `ai_tool` - Connects agent to tools (can have MULTIPLE tool connections)
- `ai_outputParser` - Connects agent to output parser

**You cannot use regular connections for AI nodes!**

---

## Advantages

✅ **Dynamic Decision-Making:** Agent decides when to use tools
✅ **Modular:** Sub-workflows are reusable across multiple agents
✅ **Extensible:** Add new tools without changing main workflow
✅ **Intelligent:** Agent can chain multiple tools together
✅ **Separation of Concerns:** Complex logic isolated in sub-workflows

---

## Disadvantages

❌ **Complexity:** More nodes than direct implementation
❌ **Latency:** AI decisions add 1-3 seconds per operation
❌ **Cost:** LLM API calls can add up quickly
❌ **Unpredictability:** Agent may not use tools as expected
❌ **Debugging:** Harder to trace execution path

---

## Best Practices

### Tool Naming and Description
- **Name:** Short, verb-based (e.g., `generate_image`, `search_database`)
- **Description:** Clear, specific, include when to use
- **Examples:** Provide example inputs in description

**Good:**
```
Name: generate_image
Description: Generates an AI image based on a text prompt. Returns the image URL and metadata. Use this when the user asks to create, generate, or make an image.
```

**Bad:**
```
Name: img
Description: Makes pictures
```

### System Prompt Guidelines
- Define agent's role and capabilities clearly
- Explicitly list available tools
- Provide examples of when to use each tool
- Set expectations for response format

**Example:**
```
You are an expert content creator that helps generate social media carousels.

You have access to these tools:
- generate_image: Creates AI images from text prompts
- analyze_quality: Analyzes image quality and suggests improvements
- upload_to_drive: Uploads files to Google Drive and returns public URL

When the user requests a carousel:
1. Generate 5 images using generate_image tool
2. Analyze each image quality using analyze_quality tool
3. If quality score < 7, regenerate with improved prompt
4. Upload final images using upload_to_drive tool
5. Return all image URLs in structured format

Always confirm with the user before uploading.
```

### Error Handling in Sub-Workflows
- Always return structured responses (even on error)
- Include `success: boolean` field
- Provide helpful error messages
- Don't let sub-workflow crash (use try/catch)

---

## Real-World Example

**Use Case:** AI-powered blog post generator with image creation

**Main Workflow (Agent):**
- User provides blog topic
- Agent uses `research_topic` tool to gather information
- Agent uses `generate_content` tool to write blog post
- Agent uses `generate_image` tool to create featured image
- Agent uses `optimize_seo` tool to improve SEO
- Agent returns complete blog post with image

**Sub-Workflows (Tools):**
1. `lib-research-topic` - Searches web, summarizes findings
2. `lib-generate-content` - Calls GPT-4 with structured template
3. `lib-generate-image` - Creates DALL-E image, validates quality
4. `lib-optimize-seo` - Analyzes content, suggests improvements

**Performance:** ~45-60 seconds end-to-end
**Success Rate:** 94% (agent sometimes skips SEO optimization step)

---

## Debugging Tips

**Agent not using tools:**
- Check tool description is clear and specific
- Verify system prompt mentions the tool
- Test tool independently (call sub-workflow directly)
- Check tool input schema matches agent's expectations

**Tool execution failing:**
- Check sub-workflow has Execute Workflow Trigger
- Verify Respond to Workflow node is present
- Test sub-workflow independently with sample input
- Check error handling in sub-workflow

**Agent using wrong tool:**
- Make tool descriptions more distinct
- Provide examples in tool description
- Adjust system prompt with clearer guidelines
- Consider using fewer, more focused tools

---

## Testing Checklist

Before deploying:
- [ ] Test each sub-workflow independently
- [ ] Verify agent uses correct tool for each scenario
- [ ] Test error cases (tool failure, invalid input)
- [ ] Check structured output parser returns expected format
- [ ] Validate memory maintains context across multiple messages
- [ ] Test with edge cases (ambiguous requests, multiple tools needed)
- [ ] Monitor LLM token usage and costs

---

## Related Patterns

- [Sequential Image Generation Chain](../sequential-image-chain/) - Can be wrapped as a tool
- [Quality Gate with Auto-Fix](../quality-gate-autofix/) - Useful for tool response validation
- [Comprehensive Error Handling](../comprehensive-error-handling/) - Essential for sub-workflows

---

**Pattern Extracted:** 2025-11-22
**Last Validated:** 2025-11-22
**Production Usage:** Template #9191, multiple custom implementations
