# AI Carousel Generator - Implementation Build Plan

**Date:** 2025-11-22
**Target Workflow:** `dev-carousel-generator` (replacement for broken workflow 8bhcEHkbbvnhdHBh)
**Architecture:** AI Agent + Sub-Workflow Tools
**Estimated Build Time:** 10 hours

---

## Executive Summary

This plan details the step-by-step implementation of an AI-powered carousel generator that:
- Generates 5 coherent slide prompts via AI Agent
- Creates DALL-E 3 images for each slide
- Validates image quality with GPT-4 Vision
- Retries low-quality images (max 2 attempts)
- Uploads images to Google Drive
- Returns public URLs for all slides
- Handles errors gracefully
- Tracks progress in real-time

**Implementation Strategy:** Incremental build + test at each phase
**Pattern Sources:** Template #4028 (85/100) + Template #9191 (82/100)
**Context Coverage:** 95% from proven templates

---

## Architecture Overview

```
Manual Trigger
    ↓
AI Agent (Generate 5 Slide Prompts)
├─ Connected to: OpenAI Chat Model (gpt-4-turbo)
├─ Connected to: Memory Buffer Window
├─ Connected to: Structured Output Parser
└─ Connected to: Tool: Image Generator Sub-Workflow
    ↓
Split Slide Prompts (1-by-1)
    ↓
Loop: For Each Slide (5 iterations)
    ↓
    Call Sub-Workflow: lib-dalle3-image-generator
    ├─ Rate Limit Check → Wait if needed
    ├─ Generate Image (DALL-E 3 API)
    ├─ Analyze Quality (GPT-4 Vision API)
    ├─ IF Quality < 7 → Regenerate (max 2 retries)
    ├─ Upload to Google Drive
    └─ Return Image URL
    ↓
Merge All Slides
    ↓
Generate Carousel Metadata
    ↓
Final Output (5 image URLs + metadata)
```

---

## Pre-Build Checklist

**Before starting implementation:**

- [ ] OpenAI API key configured in n8n credentials
- [ ] OpenAI account tier confirmed (check DALL-E 3 rate limits)
- [ ] Google Drive API enabled and credentials configured
- [ ] Google Drive folder created for carousel images (note folder ID)
- [ ] Google Sheet created for progress tracking (optional but recommended)
- [ ] Review patterns in `.claude/workflow-examples/patterns/`
- [ ] Read usage-plan.md and analysis.md for context

---

## Phase 1: Foundation Setup (30 minutes)

### Objective
Create main workflow with AI Agent architecture (without tool yet)

### Steps

#### 1.1 Create Main Workflow

**Action:**
```bash
# Using MCP tool
mcp__n8n-mcp__n8n_create_workflow({
  name: "dev-carousel-generator",
  nodes: [...], # Will add incrementally
  connections: {...}
})
```

**Manual Alternative:**
1. Open n8n UI
2. Create new workflow: "dev-carousel-generator"
3. Add nodes as specified below

---

#### 1.2 Add Manual Trigger

**Node:** Manual Trigger
**ID:** `trigger-001`
**Parameters:** Default configuration
**Position:** [250, 300]

**Purpose:** Start workflow manually for testing

---

#### 1.3 Add Set Node (Define User Input)

**Node:** Set
**ID:** `set-user-input`
**Name:** "Set User Input"
**Position:** [450, 300]

**Parameters:**
```json
{
  "values": {
    "string": [
      {
        "name": "carousel_theme",
        "value": "={{ $json.theme || 'AI automation benefits for small businesses' }}"
      },
      {
        "name": "carousel_style",
        "value": "={{ $json.style || 'vivid' }}"
      },
      {
        "name": "target_audience",
        "value": "={{ $json.audience || 'business owners' }}"
      }
    ],
    "number": [
      {
        "name": "slide_count",
        "value": 5
      }
    ]
  },
  "options": {
    "keepOnlySet": false
  }
}
```

**Connection:** Manual Trigger → Set User Input

---

#### 1.4 Add OpenAI Chat Model Node

**Node:** OpenAI Chat Model
**Type:** `@n8n/n8n-nodes-langchain.lmChatOpenAi`
**ID:** `openai-model-001`
**Name:** "OpenAI GPT-4 Turbo"
**Position:** [650, 200]

**Parameters:**
```json
{
  "model": "gpt-4-turbo",
  "options": {
    "temperature": 0.7,
    "maxTokens": 2000,
    "topP": 1
  }
}
```

**Credentials:** OpenAI API (predefined)

---

#### 1.5 Add Memory Node

**Node:** Memory Buffer Window
**Type:** `@n8n/n8n-nodes-langchain.memoryBufferWindow`
**ID:** `memory-001`
**Name:** "Simple Memory"
**Position:** [650, 350]

**Parameters:**
```json
{
  "contextWindowLength": 5
}
```

---

#### 1.6 Add Structured Output Parser

**Node:** Structured Output Parser
**Type:** `@n8n/n8n-nodes-langchain.outputParserStructured`
**ID:** `output-parser-001`
**Name:** "Parse Slide Prompts"
**Position:** [650, 500]

**Parameters:**
```json
{
  "jsonSchemaExample": {
    "type": "object",
    "properties": {
      "carousel_title": {
        "type": "string",
        "description": "Catchy title for the carousel (5-8 words)"
      },
      "carousel_description": {
        "type": "string",
        "description": "Brief description of carousel theme (15-20 words)"
      },
      "slide_prompts": {
        "type": "array",
        "description": "Array of 5 detailed DALL-E 3 prompts",
        "items": {
          "type": "object",
          "properties": {
            "slide_number": {
              "type": "number",
              "description": "Slide number (1-5)"
            },
            "prompt": {
              "type": "string",
              "description": "Detailed visual description for DALL-E 3"
            },
            "style": {
              "type": "string",
              "description": "Image style (vivid or natural)",
              "enum": ["vivid", "natural"]
            },
            "description": {
              "type": "string",
              "description": "Brief slide description (10-15 words)"
            }
          },
          "required": ["slide_number", "prompt", "style", "description"]
        },
        "minItems": 5,
        "maxItems": 5
      },
      "tags": {
        "type": "array",
        "description": "3-5 relevant tags",
        "items": { "type": "string" }
      }
    },
    "required": ["carousel_title", "carousel_description", "slide_prompts", "tags"]
  }
}
```

---

#### 1.7 Add AI Agent Node

**Node:** AI Agent
**Type:** `@n8n/n8n-nodes-langchain.agent`
**ID:** `agent-001`
**Name:** "Carousel Prompt Generator"
**Position:** [850, 300]

**Parameters:**
```json
{
  "promptType": "define",
  "text": "Theme: {{ $json.carousel_theme }}\nStyle: {{ $json.carousel_style }}\nTarget Audience: {{ $json.target_audience }}\n\nGenerate 5 carousel slides about this theme.",
  "hasOutputParser": true,
  "options": {
    "systemMessage": "You are an expert carousel designer and visual storyteller. Your task is to generate 5 compelling slide prompts for DALL-E 3 that tell a cohesive story.\n\nGuidelines:\n1. Each prompt should be 150-250 characters (DALL-E 3 works best with detailed prompts)\n2. Prompts should build on each other to create a narrative flow\n3. Use vivid, specific visual descriptions\n4. Include composition details (e.g., 'close-up', 'wide angle', 'centered')\n5. Specify style consistently (modern, minimalist, vibrant, etc.)\n6. Ensure subject matter is clear and focused\n7. Avoid text in images (DALL-E 3 struggles with text)\n8. Consider target audience when choosing visual metaphors\n\nSlide Structure:\n- Slide 1: Hook (attention-grabbing visual)\n- Slide 2: Context (set the scene)\n- Slide 3: Core concept (main idea)\n- Slide 4: Supporting detail (expand on concept)\n- Slide 5: Call-to-action visual (memorable conclusion)\n\nGenerate carousel_title, carousel_description, 5 detailed slide_prompts, and relevant tags."
  }
}
```

**Connections (Special AI Connections):**
- `ai_languageModel` → OpenAI GPT-4 Turbo (ID: `openai-model-001`)
- `ai_memory` → Simple Memory (ID: `memory-001`)
- `ai_outputParser` → Parse Slide Prompts (ID: `output-parser-001`)

**Regular Connection:**
- Set User Input → Carousel Prompt Generator (main input)

---

### Phase 1 Testing

**Test Steps:**
1. Click "Execute Workflow" in n8n
2. Provide test input: `{ "theme": "AI benefits for businesses" }`
3. Verify agent generates 5 slide prompts
4. Check output structure matches schema
5. Validate prompt quality (detailed, visual, coherent)

**Expected Output:**
```json
{
  "carousel_title": "AI Transforms Small Business",
  "carousel_description": "Discover how AI automation saves time, reduces costs, and scales your business effortlessly",
  "slide_prompts": [
    {
      "slide_number": 1,
      "prompt": "Modern small business owner overwhelmed by paperwork, sitting at messy desk with stacks of documents, laptop showing spreadsheets, warm office lighting, photo-realistic, medium shot, slightly stressed expression",
      "style": "vivid",
      "description": "The problem: Manual work overload"
    },
    // ... 4 more slides
  ],
  "tags": ["AI", "automation", "business", "productivity", "technology"]
}
```

**Validation Checklist:**
- [ ] Agent executes without errors
- [ ] Output matches structured schema
- [ ] All 5 slide prompts generated
- [ ] Prompts are detailed (150-250 chars each)
- [ ] Prompts tell a cohesive story
- [ ] Style is consistent across slides

---

## Phase 2: Image Generation Sub-Workflow (2 hours)

### Objective
Create reusable sub-workflow that generates and validates images

### Steps

#### 2.1 Create Sub-Workflow

**Action:**
Create new workflow: `lib-dalle3-image-generator`

**Purpose:** Generate single image with quality validation and retry logic

---

#### 2.2 Add Execute Workflow Trigger

**Node:** Execute Workflow Trigger
**ID:** `sub-trigger-001`
**Name:** "Workflow Trigger"
**Position:** [250, 300]

**Parameters:**
```json
{
  "mode": "singleItem"
}
```

---

#### 2.3 Add Set Node (Extract Parameters)

**Node:** Set
**ID:** `set-params-001`
**Name:** "Extract Parameters"
**Position:** [450, 300]

**Parameters:**
```json
{
  "values": {
    "string": [
      {
        "name": "prompt",
        "value": "={{ $json.prompt }}"
      },
      {
        "name": "style",
        "value": "={{ $json.style || 'vivid' }}"
      },
      {
        "name": "slide_number",
        "value": "={{ $json.slide_number || 1 }}"
      },
      {
        "name": "expected_subject",
        "value": "={{ $json.description || $json.prompt.slice(0, 50) }}"
      }
    ],
    "number": [
      {
        "name": "retry_count",
        "value": "={{ $json.retry_count || 0 }}"
      },
      {
        "name": "max_retries",
        "value": 2
      }
    ]
  },
  "options": {
    "keepOnlySet": false
  }
}
```

**Connection:** Workflow Trigger → Extract Parameters

---

#### 2.4 Add Code Node (Rate Limit Manager)

**Node:** Code
**ID:** `code-rate-limit-001`
**Name:** "Rate Limit Check"
**Position:** [650, 300]

**Code:**
```javascript
// DALL-E 3 Rate Limit Manager
// Tracks API calls and enforces rate limits

const now = Date.now();
const windowMs = 60 * 1000; // 1 minute window
const maxCallsPerMinute = 5; // Adjust based on your OpenAI tier

// Get existing tracking from workflow static data
let tracking = $workflow.staticData.rateLimit || {
  calls: [],
  lastReset: now
};

// Remove calls outside current window
tracking.calls = tracking.calls.filter(time => now - time < windowMs);

// Check if we can proceed
if (tracking.calls.length >= maxCallsPerMinute) {
  // Calculate wait time
  const oldestCall = tracking.calls[0];
  const waitMs = windowMs - (now - oldestCall) + 1000; // +1s buffer

  return {
    json: {
      can_proceed: false,
      wait_seconds: Math.ceil(waitMs / 1000),
      calls_in_window: tracking.calls.length,
      message: `Rate limit reached. Waiting ${Math.ceil(waitMs / 1000)}s before next call.`
    }
  };
}

// Add current call to tracking
tracking.calls.push(now);
$workflow.staticData.rateLimit = tracking;

return {
  json: {
    can_proceed: true,
    wait_seconds: 0,
    calls_in_window: tracking.calls.length,
    message: `Proceeding with API call (${tracking.calls.length}/${maxCallsPerMinute} calls in window)`
  }
};
```

**Connection:** Extract Parameters → Rate Limit Check

---

#### 2.5 Add IF Node (Can Proceed?)

**Node:** IF
**ID:** `if-can-proceed-001`
**Name:** "Can Proceed?"
**Position:** [850, 300]

**Parameters:**
```json
{
  "conditions": {
    "boolean": [
      {
        "value1": "={{ $json.can_proceed }}",
        "operation": "equal",
        "value2": true
      }
    ]
  }
}
```

**Connections:**
- Rate Limit Check → Can Proceed?
- FALSE branch → Wait Node (create next)
- TRUE branch → HTTP Request (create later)

---

#### 2.6 Add Wait Node

**Node:** Wait
**ID:** `wait-rate-limit-001`
**Name:** "Wait for Rate Limit"
**Position:** [850, 450]

**Parameters:**
```json
{
  "amount": "={{ $json.wait_seconds + 1 }}",
  "unit": "seconds"
}
```

**Connection:** Wait for Rate Limit → Rate Limit Check (loop back)

---

#### 2.7 Add HTTP Request (Generate Image)

**Node:** HTTP Request
**ID:** `http-dalle-001`
**Name:** "Generate Image - DALL-E 3"
**Position:** [1050, 300]

**Parameters:**
```json
{
  "method": "POST",
  "url": "https://api.openai.com/v1/images/generations",
  "authentication": "predefinedCredentialType",
  "nodeCredentialType": "openAiApi",
  "sendHeaders": true,
  "headerParameters": {
    "parameters": [
      {
        "name": "Content-Type",
        "value": "application/json"
      }
    ]
  },
  "sendBody": true,
  "specifyBody": "json",
  "jsonBody": "={\n  \"model\": \"dall-e-3\",\n  \"prompt\": \"{{ $json.prompt }}\",\n  \"size\": \"1024x1024\",\n  \"quality\": \"hd\",\n  \"style\": \"{{ $json.style }}\",\n  \"response_format\": \"b64_json\"\n}",
  "options": {
    "redirect": {
      "redirect": {
        "followRedirects": true
      }
    },
    "response": {
      "response": {
        "responseFormat": "json"
      }
    },
    "timeout": {
      "timeout": 120000
    }
  }
}
```

**Connection:** Can Proceed? (TRUE) → Generate Image

---

#### 2.8 Add Set Node (Extract Image Data)

**Node:** Set
**ID:** `set-image-data-001`
**Name:** "Extract Image Data"
**Position:** [1250, 300]

**Parameters:**
```json
{
  "values": {
    "string": [
      {
        "name": "image_base64",
        "value": "={{ $json.data[0].b64_json }}"
      },
      {
        "name": "revised_prompt",
        "value": "={{ $json.data[0].revised_prompt || $json.prompt }}"
      }
    ]
  },
  "options": {
    "keepOnlySet": false
  }
}
```

**Connection:** Generate Image → Extract Image Data

---

#### 2.9 Add HTTP Request (Analyze Quality)

**Node:** HTTP Request
**ID:** `http-vision-001`
**Name:** "Analyze Image Quality"
**Position:** [1450, 300]

**Parameters:**
```json
{
  "method": "POST",
  "url": "https://api.openai.com/v1/chat/completions",
  "authentication": "predefinedCredentialType",
  "nodeCredentialType": "openAiApi",
  "sendHeaders": true,
  "headerParameters": {
    "parameters": [
      {
        "name": "Content-Type",
        "value": "application/json"
      }
    ]
  },
  "sendBody": true,
  "specifyBody": "json",
  "jsonBody": "={\n  \"model\": \"gpt-4o\",\n  \"messages\": [\n    {\n      \"role\": \"system\",\n      \"content\": \"You are an expert image quality analyst. Analyze carousel slide images and provide structured quality assessments.\"\n    },\n    {\n      \"role\": \"user\",\n      \"content\": [\n        {\n          \"type\": \"text\",\n          \"text\": \"Analyze this carousel slide image.\\n\\nExpected subject: {{ $json.expected_subject }}\\n\\nRate the following (0-10 scale):\\n- Overall quality\\n- Subject relevance (does it match expected subject?)\\n- Visual clarity (sharp, well-composed)\\n- Professional appearance\\n\\nList any issues found.\\nProvide recommendations if quality is below 7.\"\n        },\n        {\n          \"type\": \"image_url\",\n          \"image_url\": {\n            \"url\": \"data:image/png;base64,{{ $json.image_base64 }}\"\n          }\n        }\n      ]\n    }\n  ],\n  \"response_format\": {\n    \"type\": \"json_schema\",\n    \"json_schema\": {\n      \"name\": \"image_quality_analysis\",\n      \"strict\": true,\n      \"schema\": {\n        \"type\": \"object\",\n        \"properties\": {\n          \"quality_score\": {\n            \"type\": \"number\",\n            \"description\": \"Overall quality score 0-10\"\n          },\n          \"subject_match\": {\n            \"type\": \"number\",\n            \"description\": \"How well image matches expected subject, 0-10\"\n          },\n          \"clarity_score\": {\n            \"type\": \"number\",\n            \"description\": \"Visual clarity score 0-10\"\n          },\n          \"professional_score\": {\n            \"type\": \"number\",\n            \"description\": \"Professional appearance score 0-10\"\n          },\n          \"issues\": {\n            \"type\": \"array\",\n            \"description\": \"List of issues found\",\n            \"items\": { \"type\": \"string\" }\n          },\n          \"recommendations\": {\n            \"type\": \"string\",\n            \"description\": \"Recommendations for improvement\"\n          }\n        },\n        \"required\": [\"quality_score\", \"subject_match\", \"clarity_score\", \"professional_score\", \"issues\", \"recommendations\"],\n        \"additionalProperties\": false\n      }\n    }\n  },\n  \"max_tokens\": 500\n}",
  "options": {
    "timeout": {
      "timeout": 60000
    }
  }
}
```

**Connection:** Extract Image Data → Analyze Image Quality

---

#### 2.10 Add Set Node (Parse Quality Analysis)

**Node:** Set
**ID:** `set-quality-001`
**Name:** "Parse Quality Analysis"
**Position:** [1650, 300]

**Parameters:**
```json
{
  "values": {
    "number": [
      {
        "name": "quality_score",
        "value": "={{ JSON.parse($json.choices[0].message.content).quality_score }}"
      },
      {
        "name": "subject_match",
        "value": "={{ JSON.parse($json.choices[0].message.content).subject_match }}"
      }
    ],
    "string": [
      {
        "name": "quality_issues",
        "value": "={{ JSON.parse($json.choices[0].message.content).issues.join(', ') }}"
      },
      {
        "name": "recommendations",
        "value": "={{ JSON.parse($json.choices[0].message.content).recommendations }}"
      }
    ]
  },
  "options": {
    "keepOnlySet": false
  }
}
```

**Connection:** Analyze Image Quality → Parse Quality Analysis

---

#### 2.11 Add IF Node (Quality Check)

**Node:** IF
**ID:** `if-quality-001`
**Name:** "Quality Check"
**Position:** [1850, 300]

**Parameters:**
```json
{
  "conditions": {
    "options": {
      "combineOperation": "any",
      "conditions": [
        {
          "number": [
            {
              "value1": "={{ $json.quality_score }}",
              "operation": "largerEqual",
              "value2": 7
            }
          ]
        },
        {
          "number": [
            {
              "value1": "={{ $json.retry_count }}",
              "operation": "largerEqual",
              "value2": "={{ $json.max_retries }}"
            }
          ]
        }
      ]
    }
  }
}
```

**Logic:** Pass if quality >= 7 OR max retries reached

**Connections:**
- Parse Quality Analysis → Quality Check
- TRUE branch → Upload to Google Drive (create next)
- FALSE branch → Regenerate with modified prompt (create next)

---

#### 2.12 Add Code Node (Modify Prompt for Retry)

**Node:** Code
**ID:** `code-modify-prompt-001`
**Name:** "Modify Prompt for Retry"
**Position:** [1850, 450]

**Code:**
```javascript
// Modify prompt based on quality issues

const issues = $json.quality_issues.split(', ');
const recommendations = $json.recommendations;
let modifiedPrompt = $json.prompt;

// Add specific improvements based on issues
if (issues.some(i => i.toLowerCase().includes('clarity') || i.toLowerCase().includes('blurry'))) {
  modifiedPrompt += ', highly detailed, sharp focus, crystal clear, 8k resolution';
}

if (issues.some(i => i.toLowerCase().includes('composition'))) {
  modifiedPrompt += ', professional composition, rule of thirds, balanced framing';
}

if (issues.some(i => i.toLowerCase().includes('subject') || i.toLowerCase().includes('relevance'))) {
  modifiedPrompt = 'IMPORTANT: Focus on ' + $json.expected_subject + '. ' + modifiedPrompt;
}

if (issues.some(i => i.toLowerCase().includes('lighting'))) {
  modifiedPrompt += ', professional studio lighting, well-lit, proper exposure';
}

// Add general quality boost
if ($json.retry_count === 0) {
  modifiedPrompt += ', award-winning photography, professional quality';
}

return {
  json: {
    prompt: modifiedPrompt,
    style: $json.style,
    slide_number: $json.slide_number,
    expected_subject: $json.expected_subject,
    retry_count: $json.retry_count + 1,
    max_retries: $json.max_retries,
    original_prompt: $json.original_prompt || $json.prompt,
    retry_reason: issues.join('; ')
  }
};
```

**Connection:** Quality Check (FALSE) → Modify Prompt for Retry → Extract Parameters (loop back)

---

#### 2.13 Add Google Drive Upload Node

**Node:** Google Drive
**ID:** `gdrive-upload-001`
**Name:** "Upload to Google Drive"
**Position:** [2050, 300]

**Parameters:**
```json
{
  "resource": "file",
  "operation": "upload",
  "name": "={{ 'carousel_' + $now.format('YYYY-MM-DD_HHmmss') + '_slide_' + $json.slide_number + '.png' }}",
  "folderId": {
    "__rl": true,
    "value": "YOUR_FOLDER_ID_HERE",
    "mode": "id"
  },
  "options": {
    "binaryData": "={{ $json.image_base64 }}",
    "mimeType": "image/png"
  }
}
```

**Note:** Replace `YOUR_FOLDER_ID_HERE` with actual Google Drive folder ID

**Connection:** Quality Check (TRUE) → Upload to Google Drive

---

#### 2.14 Add Google Drive Share Node

**Node:** Google Drive
**ID:** `gdrive-share-001`
**Name:** "Set Public Permissions"
**Position:** [2250, 300]

**Parameters:**
```json
{
  "resource": "file",
  "operation": "share",
  "fileId": "={{ $json.id }}",
  "permissions": {
    "permissionsUi": {
      "permissionsValues": [
        {
          "role": "reader",
          "type": "anyone"
        }
      ]
    }
  }
}
```

**Connection:** Upload to Google Drive → Set Public Permissions

---

#### 2.15 Add Set Node (Format Response)

**Node:** Set
**ID:** `set-response-001`
**Name:** "Format Response"
**Position:** [2450, 300]

**Parameters:**
```json
{
  "values": {
    "string": [
      {
        "name": "image_url",
        "value": "=https://drive.google.com/uc?export=view&id={{ $json.id }}"
      },
      {
        "name": "file_id",
        "value": "={{ $json.id }}"
      },
      {
        "name": "file_name",
        "value": "={{ $json.name }}"
      }
    ],
    "number": [
      {
        "name": "slide_number",
        "value": "={{ $json.slide_number }}"
      },
      {
        "name": "quality_score",
        "value": "={{ $json.quality_score }}"
      },
      {
        "name": "retry_count",
        "value": "={{ $json.retry_count }}"
      }
    ]
  },
  "options": {
    "keepOnlySet": true
  }
}
```

**Connection:** Set Public Permissions → Format Response

---

#### 2.16 Add Respond to Workflow Node

**Node:** Respond to Workflow
**ID:** `respond-001`
**Name:** "Return Result"
**Position:** [2650, 300]

**Parameters:**
```json
{
  "respondWith": "allInputData",
  "options": {}
}
```

**Connection:** Format Response → Return Result

---

### Phase 2 Testing

**Test Sub-Workflow Independently:**

1. Open `lib-dalle3-image-generator` workflow
2. Manually trigger with test input:
```json
{
  "prompt": "Modern office workspace with laptop, coffee cup, natural lighting, minimalist design, professional photography",
  "style": "vivid",
  "slide_number": 1,
  "description": "Professional workspace"
}
```
3. Verify each step executes successfully
4. Check rate limit manager logs
5. Verify image generation completes
6. Check quality analysis returns score
7. Verify Google Drive upload succeeds
8. Test public URL is accessible

**Validation Checklist:**
- [ ] Sub-workflow executes end-to-end
- [ ] Rate limit manager prevents rapid-fire calls
- [ ] DALL-E 3 generates image successfully
- [ ] Quality analysis returns structured JSON
- [ ] Low quality triggers retry (test with forced low score)
- [ ] Max retry limit (2) is enforced
- [ ] Image uploads to Google Drive
- [ ] Public URL is accessible
- [ ] Response includes all required fields

---

## Phase 3: Tool Integration (1 hour)

### Objective
Connect AI Agent to image generation sub-workflow

### Steps

#### 3.1 Return to Main Workflow

Open `dev-carousel-generator` workflow

---

#### 3.2 Add Tool: Workflow Node

**Node:** Tool Workflow
**Type:** `@n8n/n8n-nodes-langchain.toolWorkflow`
**ID:** `tool-image-gen-001`
**Name:** "Tool: Generate Carousel Image"
**Position:** [650, 650]

**Parameters:**
```json
{
  "name": "generate_carousel_slide_image",
  "description": "Generates a high-quality AI image for a carousel slide using DALL-E 3. Automatically validates image quality and retries if quality is below threshold. Returns the Google Drive public URL of the generated image. Use this tool for each slide in the carousel.",
  "workflowId": "lib-dalle3-image-generator",
  "fields": {
    "values": [
      {
        "name": "prompt",
        "type": "string",
        "description": "Detailed visual description for DALL-E 3 (150-250 characters recommended)"
      },
      {
        "name": "style",
        "type": "options",
        "description": "Image style (vivid for vibrant colors, natural for realistic)",
        "options": ["vivid", "natural"]
      },
      {
        "name": "slide_number",
        "type": "number",
        "description": "Slide number (1-5)"
      },
      {
        "name": "description",
        "type": "string",
        "description": "Brief description of expected image content for quality validation"
      }
    ]
  },
  "specifyInputSchema": true
}
```

---

#### 3.3 Connect Tool to AI Agent

**Connection (ai_tool):** Tool: Generate Carousel Image → Carousel Prompt Generator (agent-001)

**Note:** This is a special `ai_tool` connection type, not a regular connection

---

### Phase 3 Testing

**Test Agent with Tool:**

1. Execute main workflow
2. Provide test input: `{ "theme": "AI automation benefits" }`
3. Verify agent generates slide prompts
4. **Agent should NOT automatically call tool yet** (we'll add loop in next phase)
5. Check agent output includes structured slide prompts

**Validation Checklist:**
- [ ] Tool is connected to agent
- [ ] Agent recognizes tool in system context
- [ ] Agent output structure is correct
- [ ] No errors in execution

---

## Phase 4: Sequential Loop (1.5 hours)

### Objective
Loop through slide prompts and generate images for each

### Steps

#### 4.1 Add Split Out Node

**Node:** Split Out
**ID:** `split-slides-001`
**Name:** "Split Slide Prompts"
**Position:** [1050, 300]

**Parameters:**
```json
{
  "fieldToSplitOut": "slide_prompts",
  "include": "noOtherFields"
}
```

**Purpose:** Convert array of 5 slides into 5 separate items

**Connection:** Carousel Prompt Generator → Split Slide Prompts

---

#### 4.2 Add Code Node (Prepare Tool Input)

**Node:** Code
**ID:** `code-prep-tool-001`
**Name:** "Prepare Tool Input"
**Position:** [1250, 300]

**Code:**
```javascript
// Prepare input for image generation tool

return {
  json: {
    prompt: $json.prompt,
    style: $json.style,
    slide_number: $json.slide_number,
    description: $json.description
  }
};
```

**Connection:** Split Slide Prompts → Prepare Tool Input

---

#### 4.3 Add Execute Workflow Node

**Node:** Execute Workflow
**ID:** `exec-workflow-001`
**Name:** "Generate Slide Image"
**Position:** [1450, 300]

**Parameters:**
```json
{
  "source": "database",
  "workflowId": "lib-dalle3-image-generator",
  "waitForCompletion": true,
  "options": {}
}
```

**Connection:** Prepare Tool Input → Generate Slide Image

---

#### 4.4 Add Set Node (Add Slide Context)

**Node:** Set
**ID:** `set-slide-result-001`
**Name:** "Add Slide Context"
**Position:** [1650, 300]

**Parameters:**
```json
{
  "values": {
    "string": [
      {
        "name": "slide_description",
        "value": "={{ $json.description }}"
      },
      {
        "name": "original_prompt",
        "value": "={{ $json.prompt }}"
      }
    ]
  },
  "options": {
    "keepOnlySet": false
  }
}
```

**Connection:** Generate Slide Image → Add Slide Context

---

#### 4.5 Add Merge Node

**Node:** Merge
**ID:** `merge-slides-001`
**Name:** "Merge All Slides"
**Position:** [1850, 300]

**Parameters:**
```json
{
  "mode": "append",
  "options": {}
}
```

**Purpose:** Collect all 5 slides back into single array

**Connection:** Add Slide Context → Merge All Slides

---

### Phase 4 Testing

**Test Full Loop:**

1. Execute main workflow
2. Agent generates 5 slide prompts
3. Split creates 5 separate executions
4. Each execution generates image via sub-workflow
5. Results merge back into array
6. Verify final output has 5 image URLs

**Validation Checklist:**
- [ ] Agent generates 5 prompts
- [ ] Split creates 5 items
- [ ] Each item triggers sub-workflow
- [ ] 5 images generated successfully
- [ ] Merge combines all 5 results
- [ ] Final array has 5 items with image URLs

---

## Phase 5: Error Handling & Progress (1 hour)

### Objective
Add comprehensive error handling and progress tracking

### Steps

#### 5.1 Add Error Handling to Main Workflow

**For Each Critical Node, Add:**

1. `continueOnFail: true`
2. Error branch with logging

**Example: After Generate Slide Image node**

---

#### 5.2 Add Error Capture Node

**Node:** Set
**ID:** `set-error-001`
**Name:** "Capture Error"
**Position:** [1450, 450]

**Parameters:**
```json
{
  "values": {
    "string": [
      {
        "name": "error_message",
        "value": "={{ $json.error.message }}"
      },
      {
        "name": "error_node",
        "value": "={{ $json.error.node }}"
      },
      {
        "name": "slide_number",
        "value": "={{ $json.slide_number }}"
      }
    ],
    "string": [
      {
        "name": "timestamp",
        "value": "={{ $now.toISO() }}"
      }
    ]
  }
}
```

**Connection:** Generate Slide Image (on error) → Capture Error

---

#### 5.3 Add Google Sheets Error Log

**Node:** Google Sheets
**ID:** `sheets-error-log-001`
**Name:** "Log Error to Sheet"
**Position:** [1650, 450]

**Parameters:**
```json
{
  "operation": "appendOrUpdate",
  "documentId": "YOUR_SHEET_ID",
  "sheetName": "error_logs",
  "columns": {
    "mappings": [
      {
        "column": "timestamp",
        "value": "={{ $json.timestamp }}"
      },
      {
        "column": "workflow",
        "value": "dev-carousel-generator"
      },
      {
        "column": "slide_number",
        "value": "={{ $json.slide_number }}"
      },
      {
        "column": "error_message",
        "value": "={{ $json.error_message }}"
      },
      {
        "column": "error_node",
        "value": "={{ $json.error_node }}"
      }
    ]
  }
}
```

**Connection:** Capture Error → Log Error to Sheet

---

#### 5.4 Add Progress Tracking (Optional)

**Add Google Sheets node after key milestones:**

1. After agent generates prompts: `status: 'prompts_generated'`
2. After each image: `current_slide: N, status: 'generating'`
3. After merge: `status: 'completed'`

**Sheet Structure:**
| timestamp | carousel_id | status | current_slide | total_slides | completed_slides | error_count |

---

### Phase 5 Testing

**Test Error Scenarios:**

1. **Test 1:** Disconnect network → Verify error logged
2. **Test 2:** Invalid API key → Verify error captured
3. **Test 3:** Force quality check to fail → Verify retry logic
4. **Test 4:** Exceed max retries → Verify workflow continues

**Validation Checklist:**
- [ ] Errors are captured with context
- [ ] Errors logged to Google Sheet
- [ ] Workflow continues after non-critical errors
- [ ] Progress tracking updates correctly
- [ ] Error messages are actionable

---

## Phase 6: Final Assembly & Testing (1 hour)

### Objective
Complete workflow with metadata and final output structure

### Steps

#### 6.1 Add Code Node (Generate Carousel Metadata)

**Node:** Code
**ID:** `code-metadata-001`
**Name:** "Generate Carousel Metadata"
**Position:** [2050, 300]

**Code:**
```javascript
// Generate comprehensive carousel metadata

const slides = $input.all();
const carousel_id = 'car_' + Date.now();

return {
  json: {
    carousel_id: carousel_id,
    title: $('Carousel Prompt Generator').item.json.carousel_title,
    description: $('Carousel Prompt Generator').item.json.carousel_description,
    tags: $('Carousel Prompt Generator').item.json.tags,
    slide_count: slides.length,
    slides: slides.map((slide, index) => ({
      slide_number: slide.json.slide_number,
      image_url: slide.json.image_url,
      file_id: slide.json.file_id,
      file_name: slide.json.file_name,
      description: slide.json.slide_description,
      quality_score: slide.json.quality_score,
      retry_count: slide.json.retry_count || 0
    })),
    created_at: new Date().toISOString(),
    average_quality_score: slides.reduce((sum, s) => sum + s.json.quality_score, 0) / slides.length,
    total_retries: slides.reduce((sum, s) => sum + (s.json.retry_count || 0), 0)
  }
};
```

**Connection:** Merge All Slides → Generate Carousel Metadata

---

#### 6.2 Add Final Output Node (Optional)

**Node:** Set
**ID:** `set-final-output-001`
**Name:** "Final Output"
**Position:** [2250, 300]

**Purpose:** Format for downstream systems or webhooks

**Connection:** Generate Carousel Metadata → Final Output

---

### Phase 6 Testing

**End-to-End Test:**

1. Trigger workflow with theme: "Benefits of AI automation for small businesses"
2. Monitor execution through all phases
3. Verify 5 images generated
4. Check all images accessible via URLs
5. Validate metadata structure
6. Measure total execution time

**Expected Timeline:**
- Agent prompt generation: ~10 seconds
- Image 1 generation: ~15-20 seconds
- Image 2-5 generation: ~15-20 seconds each (with rate limiting)
- Total: ~2-3 minutes (assuming no retries)

**Success Criteria:**
- [ ] All 5 images generated successfully
- [ ] All image URLs are accessible
- [ ] Average quality score >= 7.5
- [ ] Execution completes in < 10 minutes
- [ ] Metadata is accurate and complete
- [ ] No critical errors encountered
- [ ] Error logging works for forced errors

---

## Post-Build Tasks

### 1. Workflow Validation

```bash
# Using MCP
mcp__n8n-mcp__n8n_validate_workflow({
  id: "workflow-id"
})
```

**Fix any validation warnings or errors**

---

### 2. Documentation

**Update:**
- `.claude/agents-evolution.md` with build outcomes
- Pattern library if new reusable patterns emerged
- README with carousel workflow details

---

### 3. Optimization

**Review and optimize:**
- Remove any unnecessary nodes
- Consolidate Set nodes where possible
- Check for redundant API calls
- Optimize rate limit settings based on tier

---

### 4. Production Readiness

**Before moving to production:**
- [ ] Rename workflow: `dev-carousel-generator` → `prod-carousel-generator`
- [ ] Update Google Drive folder to production folder
- [ ] Review API rate limits (consider upgrading tier if needed)
- [ ] Set up monitoring/alerting for errors
- [ ] Create user documentation
- [ ] Test with real-world use cases (10+ different themes)
- [ ] Measure cost per carousel generation
- [ ] Set up usage tracking in Google Sheets

---

## Troubleshooting Guide

### Issue: Agent doesn't generate structured output

**Solution:**
- Verify output parser is connected via `ai_outputParser`
- Check JSON schema is valid
- Test agent prompt in isolation
- Reduce schema complexity if needed

---

### Issue: Images fail quality check repeatedly

**Solution:**
- Review quality thresholds (7 may be too high)
- Check prompt refinement logic in retry node
- Increase max_retries to 3
- Add more specific improvement instructions

---

### Issue: Rate limiting causing delays

**Solution:**
- Check OpenAI tier limits
- Adjust `maxCallsPerMinute` in rate limit manager
- Consider upgrading OpenAI tier
- Implement parallel processing (advanced)

---

### Issue: Google Drive upload fails

**Solution:**
- Verify credentials are valid
- Check folder ID is correct
- Ensure folder permissions allow upload
- Test binary data format is correct

---

### Issue: Sub-workflow not returning results

**Solution:**
- Verify "Respond to Workflow" node is present
- Check workflow ID in Execute Workflow node
- Ensure sub-workflow is activated
- Test sub-workflow independently first

---

## Completion Checklist

**Workflow Implementation:**
- [ ] Phase 1: Foundation (AI Agent setup)
- [ ] Phase 2: Image generation sub-workflow
- [ ] Phase 3: Tool integration
- [ ] Phase 4: Sequential loop
- [ ] Phase 5: Error handling
- [ ] Phase 6: Final assembly

**Testing:**
- [ ] Test 1: Single image generation
- [ ] Test 2: AI agent tool integration
- [ ] Test 3: Multi-slide generation
- [ ] Test 4: Quality rejection & retry
- [ ] Test 5: Rate limit handling
- [ ] Test 6: Error recovery
- [ ] Test 7: Concurrent execution

**Documentation:**
- [ ] Build outcomes in agents-evolution.md
- [ ] Pattern extraction complete
- [ ] Troubleshooting guide created
- [ ] User documentation written

**Production Readiness:**
- [ ] Workflow validated
- [ ] Error handling comprehensive
- [ ] Monitoring/alerting configured
- [ ] Cost per execution calculated
- [ ] Real-world testing complete

---

**Build Status:** Ready to Implement
**Estimated Total Time:** 10 hours
**Confidence Level:** High (95% from proven patterns)

**Next Action:** Begin Phase 1 - Foundation Setup
