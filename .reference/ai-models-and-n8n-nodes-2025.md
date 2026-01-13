# AI Models & n8n Nodes Reference Guide (2025)

**Last Updated:** 2025-11-23
**Audience:** Senior Developers
**Purpose:** Authoritative reference for current AI models and n8n node capabilities

---

## Table of Contents

1. [OpenAI Models](#openai-models)
2. [Google AI Models](#google-ai-models)
3. [Anthropic Claude Models](#anthropic-claude-models)
4. [n8n Image Generation Nodes](#n8n-image-generation-nodes)
5. [n8n AI-Capable Nodes](#n8n-ai-capable-nodes)
6. [Best Practices](#best-practices)

---

## OpenAI Models

### Current Generation (2025)

#### GPT-5 Series

**GPT-5** (Released: August 7, 2025)
- **Status:** Production
- **Description:** OpenAI's best AI system with state-of-the-art performance
- **Strengths:** Coding, math, writing, health, visual perception
- **Model ID:** `gpt-5`

**GPT-5.1 Instant** (Released: November 2025)
- **Status:** Production (Rolling out to paid users first)
- **Description:** Most-used model with warmer, more intelligent responses
- **Features:**
  - Adaptive reasoning (decides when to think before responding)
  - Dynamically adapts thinking time based on task complexity
  - Significantly faster and more token-efficient on simple tasks
- **Model ID:** `gpt-5.1` or `gpt-5.1-instant`

**GPT-5.1 Thinking**
- **Status:** Production
- **Description:** Extended reasoning for complex challenges
- **Use Cases:** Complex problem-solving requiring deeper analysis
- **Model ID:** `gpt-5.1-thinking`

**GPT-5.1-Codex** (Public Preview: November 13, 2025)
- **Status:** Public Preview (GitHub Copilot)
- **Description:** Specialized coding model
- **Variants:**
  - `gpt-5.1-codex`
  - `gpt-5.1-codex-mini`
  - `gpt-5.1-codex-max` (Frontier agentic coding model)

#### DALL-E Series

**DALL-E 3**
- **Status:** Production
- **Model ID:** `dall-e-3`
- **Capabilities:**
  - Text-to-image generation
  - Maximum prompt length: 4000 characters
  - Resolutions: 1024x1024, 1792x1024, 1024x1792
  - Quality options: Standard, HD
  - Style options: Natural, Vivid

**DALL-E 2**
- **Status:** Production (Legacy)
- **Model ID:** `dall-e-2`
- **Capabilities:**
  - Text-to-image generation
  - Maximum prompt length: 1000 characters
  - Resolutions: 256x256, 512x512, 1024x1024

#### Legacy Models

**GPT-4 Turbo**
- **Status:** Legacy (superseded by GPT-5)
- **Model ID:** `gpt-4-turbo`

**GPT-4**
- **Status:** Legacy
- **Model ID:** `gpt-4`

**GPT-3.5 Turbo**
- **Status:** Legacy
- **Model ID:** `gpt-3.5-turbo`

---

## Google AI Models

### Gemini Series (2024-2025)

#### Gemini 2.5 (March 2025)

**Gemini 2.5 Pro Experimental**
- **Status:** Production (Experimental)
- **Description:** Most intelligent AI model from Google
- **Ranking:** #1 on LMArena by significant margin
- **Model ID:** `gemini-2.5-pro`

#### Gemini 2.0 (December 2024)

**Gemini 2.0 Flash** (Default as of January 30, 2025)
- **Status:** Production
- **Description:** Enhanced performance at fast response times
- **Features:**
  - Outperforms 1.5 Pro on key benchmarks at 2x speed
  - Multimodal inputs: images, video, audio
  - Multimodal outputs: natively generated images, text, TTS audio
  - Native tool calling (Google Search, code execution, user-defined functions)
- **Context Window:** Standard
- **Model ID:** `gemini-2.0-flash`

**Gemini 2.0 Pro** (Released: February 5, 2025)
- **Status:** Production
- **Description:** Strongest coding and complex prompt handling
- **Features:**
  - Best coding performance in Gemini 2.0 family
  - Enhanced reasoning and world knowledge understanding
  - 2 million token context window
- **Context Window:** 2,000,000 tokens
- **Model ID:** `gemini-2.0-pro`

**Gemini 2.0 Flash-Lite**
- **Status:** Production
- **Description:** Better quality than 1.5 Flash, same speed/cost
- **Model ID:** `gemini-2.0-flash-lite`

#### Gemini 1.5 (Legacy)

**Gemini 1.5 Pro**
- **Status:** Legacy (superseded by 2.0 Flash)
- **Model ID:** `gemini-1.5-pro`

**Gemini 1.5 Flash**
- **Status:** Legacy
- **Model ID:** `gemini-1.5-flash`

---

## Anthropic Claude Models

### Claude 4 Family (May 2025)

**Claude Sonnet 4.5** (September 2025)
- **Status:** Production
- **Description:** Best coding model in the world
- **Performance:**
  - SWE-bench Verified: 77.2%
  - World-class coding capabilities
- **Pricing:**
  - Input: $3 per million tokens
  - Output: $15 per million tokens
- **Model ID:** `claude-sonnet-4-5` or `claude-sonnet-4.5-20250929`

**Claude Opus 4.1** (August 2025)
- **Status:** Production
- **Description:** Upgrade focused on agentic tasks, real-world coding, reasoning
- **Performance:**
  - SWE-bench Verified: 74.5%
  - Advanced agentic capabilities
- **Pricing:**
  - Input: $15 per million tokens
  - Output: $75 per million tokens
- **Model ID:** `claude-opus-4-1` or `claude-opus-4.1`

**Claude Haiku 4.5** (November 2025)
- **Status:** Production
- **Description:** Most efficient and cost-effective in Claude 4 family
- **Performance:**
  - Near-frontier coding quality
  - Matches Sonnet 4 on coding tasks
- **Use Cases:** High-volume, cost-sensitive applications
- **Model ID:** `claude-haiku-4-5`

**Claude Opus 4 & Sonnet 4** (May 2025)
- **Status:** Production
- **Description:** Hybrid models with two modes
- **Modes:**
  - Near-instant responses
  - Extended thinking for deeper reasoning
- **Availability:** Anthropic API, Amazon Bedrock, Google Cloud Vertex AI
- **Model IDs:** `claude-opus-4`, `claude-sonnet-4`

### Model Comparison Table

| Model | Coding | Reasoning | Speed | Cost | Best For |
|-------|--------|-----------|-------|------|----------|
| Sonnet 4.5 | ★★★★★ | ★★★★★ | ★★★★☆ | $$$ | Production coding |
| Opus 4.1 | ★★★★★ | ★★★★★ | ★★★☆☆ | $$$$$ | Agentic tasks |
| Haiku 4.5 | ★★★★☆ | ★★★★☆ | ★★★★★ | $ | High-volume tasks |

---

## n8n Image Generation Nodes

### OpenAI Node (nodes-base.openAi)

**Current Version:** 1.1 (Node version notice: newer version available)

#### Image Resource Configuration

**Supported Models:**
- `dall-e-2` (Legacy)
- `dall-e-3` (Current)
- Model selection via dynamic load from `/v1/models` API

**IMPORTANT:** n8n loads models dynamically from OpenAI API. The node filters for models starting with `dall-`:
```javascript
filter: "={{ $responseItem.id.startsWith('dall-') }}"
```

#### DALL-E 3 Configuration

**Model Field:**
- **Parameter Name:** `imageModel` (v1.1+) or `model` (v1.0)
- **Type:** Dynamic options (loaded from API)
- **Default:** `dall-e-2`
- **Valid Values:** Any model ID starting with `dall-` from OpenAI API

**Prompt Field:**
- **Parameter Name:** `prompt`
- **Type:** String
- **Max Length:**
  - DALL-E 2: 1000 characters
  - DALL-E 3: 4000 characters

**Response Format:**
- **Parameter Name:** `responseFormat`
- **Options:**
  - `binaryData` - Returns image as binary file in n8n
  - `imageUrl` - Returns OpenAI-hosted image URL

**Optional Parameters (DALL-E 3 Only):**

1. **Quality** (`quality`)
   - Options: `standard`, `hd`
   - Default: `standard`
   - HD creates finer details and greater consistency

2. **Resolution** (`size`)
   - Options: `1024x1024`, `1792x1024`, `1024x1792`
   - Default: `1024x1024`

3. **Style** (`style`)
   - Options: `natural`, `vivid`
   - Default: `vivid`
   - Natural: More natural-looking images
   - Vivid: Hyper-real and dramatic images

4. **Number of Images** (`n`)
   - Range: 1-10
   - Default: 1

#### DALL-E 2 Configuration

**Resolution** (`size`)
- Options: `256x256`, `512x512`, `1024x1024`
- Default: `1024x1024`

#### Example Workflow Configuration

```json
{
  "nodes": [
    {
      "type": "n8n-nodes-base.openAi",
      "typeVersion": 1.1,
      "parameters": {
        "resource": "image",
        "operation": "create",
        "imageModel": "dall-e-3",
        "prompt": "A futuristic cityscape with flying cars",
        "responseFormat": "binaryData",
        "options": {
          "quality": "hd",
          "size": "1792x1024",
          "style": "vivid",
          "n": 1
        }
      },
      "credentials": {
        "openAiApi": {
          "id": "your-credential-id",
          "name": "OpenAI Account"
        }
      }
    }
  ]
}
```

### OpenAI Langchain Node (@n8n/n8n-nodes-langchain.openAi)

**Description:** Advanced OpenAI integration for AI chains
- **Package:** `@n8n/n8n-nodes-langchain`
- **Category:** Transform
- **Use Cases:** Message assistants, GPT interactions, image analysis, audio generation
- **Integration:** Works with AI Agent nodes and langchain workflows

---

## n8n AI-Capable Nodes

### Total AI Tools: 274 Nodes

n8n has **274 nodes** with the `usableAsTool: true` property, optimized for AI agent usage.

**IMPORTANT:** ANY node in n8n can be used as an AI tool by connecting it to the AI Agent's tool port.

### Top AI Integration Nodes

#### OpenAI Ecosystem

1. **OpenAI** (`nodes-base.openAi`)
   - Chat completions (GPT models)
   - Image generation (DALL-E)
   - Text completions
   - Moderation

2. **OpenAI Chat Model** (`nodes-langchain.lmChatOpenAi`)
   - Advanced langchain integration
   - For AI chains and workflows

3. **OpenAI Assistant** (`nodes-langchain.openAiAssistant`)
   - OpenAI Assistant API integration
   - Persistent conversation threads

4. **Azure OpenAI Chat Model** (`nodes-langchain.lmChatAzureOpenAi`)
   - Enterprise Azure integration

#### Anthropic Ecosystem

1. **Anthropic** (`nodes-langchain.anthropic`)
   - Claude model interactions

2. **Anthropic Chat Model** (`nodes-langchain.lmChatAnthropic`)
   - Advanced langchain Claude integration

#### Google Ecosystem

1. **Google Gemini** (`nodes-langchain.googleGemini`)
   - Gemini model integration

2. **Google Cloud Natural Language** (`nodes-base.googleCloudNaturalLanguage`)
   - Text analysis and NLP

#### Other Major AI Providers

1. **Cohere** (`nodes-langchain.lmChatCohere`)
   - Cohere language models

2. **Hugging Face Inference Model** (`nodes-langchain.lmOpenHuggingFaceInference`)
   - Open-source model access

3. **Ollama** (`nodes-langchain.ollama`)
   - Local AI model integration

4. **Mistral AI** (`nodes-base.mistralAi`)
   - Mistral model access

5. **Perplexity** (`nodes-base.perplexity`)
   - AI responses with citations

#### Specialized AI Nodes

1. **AI Transform** (`nodes-base.aiTransform`)
   - Modify data with plain English instructions

2. **Guardrails** (`nodes-langchain.guardrails`)
   - Safeguard AI from malicious input/output

3. **Embeddings OpenAI** (`nodes-langchain.embeddingsOpenAi`)
   - Vector embeddings for RAG

4. **Embeddings Cohere** (`nodes-langchain.embeddingsCohere`)
   - Alternative embedding provider

5. **Question and Answer Chain** (`nodes-langchain.chainRetrievalQa`)
   - RAG workflows

6. **Summarization Chain** (`nodes-langchain.chainSummarization`)
   - Text summarization

### AI Workflow Patterns

#### Pattern 1: Image Generation Workflow
```
Form Trigger → OpenAI Image Node (DALL-E 3) → Google Drive Upload → Slack Notification
```

#### Pattern 2: AI-Powered Data Processing
```
Webhook → AI Transform → Supabase Insert → Respond to Webhook
```

#### Pattern 3: Multi-Model Comparison
```
Schedule → [GPT-5.1, Gemini 2.0 Pro, Claude Sonnet 4.5] (parallel) → Compare Results → Store Best
```

#### Pattern 4: RAG (Retrieval Augmented Generation)
```
Question → Vector Store Retrieval → Reranker → QA Chain → Response
```

---

## Best Practices

### Model Selection Guidelines

#### Choose GPT-5.1 Instant When:
- ✅ Need adaptive reasoning
- ✅ Mix of simple and complex tasks
- ✅ Speed matters
- ✅ Token efficiency is important

#### Choose GPT-5.1 Thinking When:
- ✅ Complex problem-solving required
- ✅ Accuracy > Speed
- ✅ Multi-step reasoning needed

#### Choose Gemini 2.0 Pro When:
- ✅ Need 2M token context window
- ✅ Coding-heavy workloads
- ✅ Complex prompt handling
- ✅ Multimodal input/output

#### Choose Claude Sonnet 4.5 When:
- ✅ Production coding tasks
- ✅ Need world-class code generation
- ✅ SWE-bench performance critical
- ✅ Balanced cost and performance

#### Choose Claude Haiku 4.5 When:
- ✅ High-volume applications
- ✅ Cost optimization critical
- ✅ Fast responses needed
- ✅ Coding quality still important

### n8n Node Version Strategy

**CRITICAL CORRECTION:** Always prioritize newest node versions.

**Anti-Pattern (Incorrect):**
```
❌ "Don't use newer typeVersions, they might not work"
❌ "Use typeVersion 1.8 instead of 2 because it's more stable"
```

**Correct Pattern:**
```
✅ Use latest available typeVersion from n8n
✅ Configure node parameters correctly for the version
✅ Reference official n8n documentation for parameter requirements
✅ Test with proper configuration before assuming version incompatibility
```

**Why This Matters:**
- Newer versions have bug fixes and improvements
- Configuration errors are more common than version incompatibilities
- Downgrading versions can miss important features

### Image Generation Best Practices

#### DALL-E 3 Optimization

1. **Prompt Engineering**
   - Use detailed, specific descriptions (up to 4000 chars)
   - Include style, lighting, composition details
   - Specify aspect ratio needs upfront

2. **Quality Selection**
   - Use HD for final production images
   - Use Standard for prototyping/testing

3. **Style Selection**
   - Natural: Professional photography, realistic scenes
   - Vivid: Marketing materials, eye-catching content

4. **Response Format**
   - `binaryData`: For immediate processing in n8n workflow
   - `imageUrl`: For web display or external storage

#### Multi-Model Strategy

For critical image generation:
```
Trigger → [DALL-E 3, Stable Diffusion, Midjourney API] (parallel)
       → Human Review
       → Select Best
       → Finalize
```

### AI Agent Configuration

**Enable Community Nodes as Tools:**
```bash
export N8N_COMMUNITY_PACKAGES_ALLOW_TOOL_USAGE=true
```

**Connect Any Node as AI Tool:**
1. Add AI Agent node
2. Connect desired node to AI Agent's `ai_tool` port
3. Node becomes available to AI for execution

**Example Use Cases:**
- Slack node → AI can send messages
- Google Sheets node → AI can read/write spreadsheet data
- HTTP Request node → AI can call external APIs
- Supabase node → AI can query/update database

### Error Handling

**Always include:**
- ✅ Try-catch in Code nodes processing AI responses
- ✅ Validation of AI output format
- ✅ Fallback models if primary fails
- ✅ Rate limiting and retry logic
- ✅ Cost monitoring (token usage tracking)

**Example Error Handling:**
```javascript
try {
  const response = await openai.generate(prompt);
  // Validate response structure
  if (!response.choices || response.choices.length === 0) {
    throw new Error('Invalid AI response format');
  }
  return response.choices[0].message.content;
} catch (error) {
  // Fallback to different model or cached response
  console.error('AI generation failed:', error);
  return fallbackResponse;
}
```

### Cost Optimization

**Token Usage Strategies:**

1. **Prompt Optimization**
   - Remove unnecessary context
   - Use shorter prompts when possible
   - Cache system prompts

2. **Model Selection**
   - Use cheaper models for simple tasks
   - Reserve expensive models for complex reasoning

3. **Batch Processing**
   - Combine multiple requests when possible
   - Use streaming for long responses

4. **Caching**
   - Cache frequent responses
   - Implement semantic caching for similar prompts

**Cost Comparison (per 1M tokens):**

| Model | Input Cost | Output Cost | Use Case |
|-------|-----------|-------------|----------|
| GPT-5.1 Instant | ~$5-10 | ~$15-20 | General purpose |
| Gemini 2.0 Pro | ~$3-5 | ~$10-15 | Coding, long context |
| Claude Sonnet 4.5 | $3 | $15 | Production coding |
| Claude Haiku 4.5 | <$1 | <$5 | High volume |

*(Estimates - check official pricing)*

---

## Version History

- **2025-11-23:** Initial comprehensive reference
  - Documented GPT-5/5.1 series
  - Documented Gemini 2.0/2.5 series
  - Documented Claude 4 family
  - Corrected node version strategy anti-pattern
  - Added n8n DALL-E configuration details

---

## Sources

- [OpenAI GPT-5.1 Announcement](https://openai.com/index/gpt-5-1/)
- [Google Gemini 2.0 Launch](https://blog.google/technology/google-deepmind/google-gemini-ai-update-december-2024/)
- [Anthropic Claude Sonnet 4.5](https://www.anthropic.com/news/claude-sonnet-4-5)
- [n8n OpenAI Image Operations](https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-langchain.openai/image-operations/)
- [n8n Node Documentation](https://docs.n8n.io/integrations/builtin/)

---

**Maintained By:** SYNRG Director-Orchestrator
**Repository:** `/Users/jelalconnor/CODING/N8N/Workflows/.reference/`
