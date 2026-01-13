# n8n Node Reference Library

> **Purpose**: Up-to-date node configurations for Claude Code to access when developing/debugging workflows
> **Last Updated**: 2025-12-28 (OpenAI comprehensive update + MCP validation)
> **Source**: MCP `get_node` with full detail + live workflow verification

---

## Usage Protocol

**MANDATORY: Before implementing ANY node, check this directory first.**

```javascript
// Step 1: Check if node reference exists
const nodeRef = await Read({
  file_path: `.claude/node-reference/langchain/${nodeType}.md`
});

// Step 2: If exists, use reference configuration
// Step 3: If not exists, use MCP to fetch current schema
```

---

## Directory Structure

```
.claude/node-reference/
├── README.md                      # This file
├── langchain/                     # LangChain AI nodes
│   ├── agent.md                   # AI Agent node
│   ├── chat-trigger.md            # Chat Trigger node
│   ├── lm-chat-openai.md          # OpenAI Chat Model
│   ├── lm-chat-anthropic.md       # Anthropic Claude Chat Model
│   ├── lm-chat-openrouter.md      # OpenRouter Chat Model
│   ├── lm-chat-google-gemini.md   # Google Gemini Chat Model
│   ├── memory-buffer-window.md    # Simple Memory node
│   ├── output-parser-structured.md # Structured Output Parser
│   ├── openai-image.md            # OpenAI Image (Generation/Analysis) ⚠️ ANTI-MEMORY
│   ├── openai-audio.md            # OpenAI Audio (TTS/Transcription/Translation)
│   ├── tool-workflow.md           # Call n8n Sub-Workflow Tool
│   ├── tool-http-request.md       # HTTP Request Tool
│   ├── tool-vector-store.md       # Vector Store Q&A Tool
│   ├── vector-store-pinecone.md   # Pinecone Vector Store
│   └── embeddings-google-gemini.md # Google Gemini Embeddings
└── base/                          # Standard n8n nodes
    ├── gmail.md                   # Gmail email operations
    ├── gmail-tool.md              # Gmail Tool for AI Agents ⚠️ REQUIRES explicit params
    ├── google-drive.md            # Google Drive file operations
    ├── microsoft-teams.md         # Microsoft Teams messaging
    ├── postgres.md                # PostgreSQL database operations
    ├── code.md                    # Custom JavaScript/Python code
    ├── switch.md                  # Route/Switch conditional branching
    ├── webhook.md                 # HTTP webhook trigger
    ├── split-in-batches.md        # Loop/batch processing
    └── execute-workflow.md        # Execute sub-workflow
```

---

## Node Index

### LangChain Nodes (AI/Agent)

| Node | Type | TypeVersion | Anti-Memory |
|------|------|-------------|-------------|
| [AI Agent](langchain/agent.md) | `@n8n/n8n-nodes-langchain.agent` | 3.1 | |
| [Chat Trigger](langchain/chat-trigger.md) | `@n8n/n8n-nodes-langchain.chatTrigger` | 1.4 | |
| [OpenAI Chat](langchain/lm-chat-openai.md) | `@n8n/n8n-nodes-langchain.lmChatOpenAi` | 1.3 | |
| [Anthropic Claude](langchain/lm-chat-anthropic.md) | `@n8n/n8n-nodes-langchain.lmChatAnthropic` | 1.3 | |
| [OpenRouter](langchain/lm-chat-openrouter.md) | `@n8n/n8n-nodes-langchain.lmChatOpenRouter` | 1 | |
| [Google Gemini Chat](langchain/lm-chat-google-gemini.md) | `@n8n/n8n-nodes-langchain.lmChatGoogleGemini` | 1 | |
| [Memory Buffer](langchain/memory-buffer-window.md) | `@n8n/n8n-nodes-langchain.memoryBufferWindow` | 1.3 | |
| [Output Parser](langchain/output-parser-structured.md) | `@n8n/n8n-nodes-langchain.outputParserStructured` | 1.3 | |
| [OpenAI Image](langchain/openai-image.md) | `@n8n/n8n-nodes-langchain.openAi` | 2.1 | ⚠️ YES |
| [OpenAI Audio](langchain/openai-audio.md) | `@n8n/n8n-nodes-langchain.openAi` | 2.1 | |
| [Tool Workflow](langchain/tool-workflow.md) | `@n8n/n8n-nodes-langchain.toolWorkflow` | 2.2 | |
| [Tool HTTP Request](langchain/tool-http-request.md) | `@n8n/n8n-nodes-langchain.toolHttpRequest` | 1.1 | |
| [Tool Vector Store](langchain/tool-vector-store.md) | `@n8n/n8n-nodes-langchain.toolVectorStore` | 1.1 | |
| [Pinecone Vector Store](langchain/vector-store-pinecone.md) | `@n8n/n8n-nodes-langchain.vectorStorePinecone` | 1.3 | |
| [Gemini Embeddings](langchain/embeddings-google-gemini.md) | `@n8n/n8n-nodes-langchain.embeddingsGoogleGemini` | 1 | |

### Base Nodes (Standard)

| Node | Type | TypeVersion | Notes |
|------|------|-------------|-------|
| [Gmail](base/gmail.md) | `n8n-nodes-base.gmail` | 2.2 | Send, receive, manage emails |
| [Gmail Tool](base/gmail-tool.md) | `n8n-nodes-base.gmailTool` | 2.2 | ⚠️ REQUIRES explicit resource/operation |
| [Google Drive](base/google-drive.md) | `n8n-nodes-base.googleDrive` | 3 | File/folder operations |
| [Microsoft Teams](base/microsoft-teams.md) | `n8n-nodes-base.microsoftTeams` | 2 | Channel/chat messaging |
| [Postgres](base/postgres.md) | `n8n-nodes-base.postgres` | 2.6 | Database operations |
| [Code](base/code.md) | `n8n-nodes-base.code` | 2 | JavaScript/Python execution |
| [Switch](base/switch.md) | `n8n-nodes-base.switch` | 3.4 | Conditional routing |
| [Webhook](base/webhook.md) | `n8n-nodes-base.webhook` | 2.1 | HTTP trigger |
| [Split In Batches](base/split-in-batches.md) | `n8n-nodes-base.splitInBatches` | 3 | Loop/batch processing |
| [Execute Workflow](base/execute-workflow.md) | `n8n-nodes-base.executeWorkflow` | 1.3 | Sub-workflow execution |

---

## Anti-Memory Protocol Nodes

The following nodes have documented recurring failure patterns. **ALWAYS read the reference file before configuring:**

| Node | Why Anti-Memory |
|------|-----------------|
| ⚠️ [OpenAI Image](langchain/openai-image.md) | `binaryPropertyName` contamination, model format differences (string vs ResourceLocator), operation defaults |
| ⚠️ [Gmail Tool](base/gmail-tool.md) | REQUIRES explicit `resource` and `operation` parameters - will fail silently without them |

---

## Quick Lookup by Task

### OpenAI Complete Integration
1. [OpenAI Chat Model](langchain/lm-chat-openai.md) - GPT-4o, o1/o3 reasoning, Responses API
2. [OpenAI Image](langchain/openai-image.md) - ⚠️ Generation (GPT Image 1, DALL-E 3), Analysis (GPT-4o Vision)
3. [OpenAI Audio](langchain/openai-audio.md) - TTS (6 voices), Transcription, Translation
4. [AI Agent](langchain/agent.md) - Connect OpenAI as LLM via `ai_languageModel`

### Building a Chat Agent
1. [Chat Trigger](langchain/chat-trigger.md) - Entry point
2. [AI Agent](langchain/agent.md) - Orchestration
3. [OpenAI Chat](langchain/lm-chat-openai.md) or [Anthropic](langchain/lm-chat-anthropic.md) - LLM
4. [Memory Buffer](langchain/memory-buffer-window.md) - Conversation history
5. [Output Parser](langchain/output-parser-structured.md) - Structured responses

### Building a RAG Pipeline
1. [Gemini Embeddings](langchain/embeddings-google-gemini.md) - Document embedding
2. [Pinecone Vector Store](langchain/vector-store-pinecone.md) - Storage/retrieval
3. [Tool Vector Store](langchain/tool-vector-store.md) - Agent integration

### Adding Agent Tools
1. [Tool Workflow](langchain/tool-workflow.md) - Execute sub-workflows
2. [Tool HTTP Request](langchain/tool-http-request.md) - External APIs
3. [Tool Vector Store](langchain/tool-vector-store.md) - Knowledge retrieval

### Image Generation/Analysis
1. ⚠️ [OpenAI Image](langchain/openai-image.md) - **READ ANTI-MEMORY PROTOCOL FIRST**

### Email Agent with Gmail
1. ⚠️ [Gmail Tool](base/gmail-tool.md) - **REQUIRES explicit resource/operation**
2. [AI Agent](langchain/agent.md) - Agent orchestration
3. [OpenAI Chat](langchain/lm-chat-openai.md) or [Anthropic](langchain/lm-chat-anthropic.md) - LLM

### Data Processing Pipeline
1. [Webhook](base/webhook.md) - Trigger on HTTP request
2. [Switch](base/switch.md) - Route by conditions
3. [Split In Batches](base/split-in-batches.md) - Process in batches
4. [Postgres](base/postgres.md) - Database operations

### Modular Workflows
1. [Execute Workflow](base/execute-workflow.md) - Call sub-workflows
2. [Code](base/code.md) - Custom transformations

---

## Maintenance

### Adding New Nodes
1. Fetch schema: `mcp__n8n-mcp__get_node({ nodeType, mode: "info", detail: "full" })`
2. Create file in appropriate directory
3. Update this README index
4. Update `pattern-index.json` with new mappings

### Updating Existing Nodes
1. Check MCP for latest typeVersion
2. Update reference configuration
3. Update "Last Verified" date
4. Document any breaking changes

---

## Integration with Debugging

The `/synrg-n8ndebug` command checks this directory before implementing fixes:

```javascript
// In synrg-n8ndebug PHASE 3 (Solution Research)
const nodeRef = checkNodeReference(failedNodeType);
if (nodeRef.exists) {
  // Use reference configuration
} else {
  // Fall back to MCP research
}
```

---

## Source Workflows

These nodes are documented because they're actively used in current workflows:

| Workflow | ID | Nodes Used |
|----------|-----|------------|
| AI Carousel Generator | `8bhcEHkbbvnhdHBh` | Agent, OpenAI Chat, OpenAI Image, Output Parser |
| Branded AI Chatbot | `2Ryo177xsOL2Mk6T` | Chat Trigger, Agent, Memory, Tool Workflow, Tool HTTP |
| Teams Voice Bot | `gjYSN6xNjLw8qsA1` | Agent, OpenRouter, Memory |
| Developer Agent | `ZimW7HztadhFZTyY` | Chat Trigger, Agent, Anthropic, OpenRouter, Memory, Tool Workflow |
| RAG Pipeline | `4RRsl3R2DePIGfFd` | Agent, Gemini Chat, Memory, Pinecone, Gemini Embeddings, Tool Vector Store |
