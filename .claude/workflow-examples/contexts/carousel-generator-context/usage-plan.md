# Carousel Generator - Context Usage Plan

**Date:** 2025-11-22
**Selected Contexts:**
- **Primary:** Template #4028 - "Generate and Publish Carousels for TikTok and Instagram"
- **Secondary:** Template #9191 - "Generate blog posts from keywords to Webflow"

---

## Requirement Mapping

| Target Requirement | Source in Context | Modification Needed |
|-------------------|-------------------|---------------------|
| AI Agent orchestration | Template #9191 - AI Agent node | Minor - adapt system prompt for carousel |
| Sequential image generation | Template #4028 - 5 sequential HTTP nodes | Major - make dynamic, add DALL-E 3 config |
| Image analysis/validation | Not in context - need to build | Major - net-new component |
| Google Drive storage | Template #9191 - Google Drive nodes | Minor - adapt folder structure |
| Loop over slides | Template #4028 - Sequential chain / #9191 - splitInBatches | Moderate - combine both patterns |
| Merge collected images | Template #4028 - Merge node | Minor - make inputs dynamic |
| Error handling | Template #9191 - IF + error logging | Minor - adapt for image generation errors |
| Rate limit management | Not in either template | Moderate - add wait periods and retry logic |

---

## Reusable Components

### Component 1: AI Agent with Tool (Template #9191)

**Source**: Template #9191, nodes:
- AI Agent (6c19a117-9bac-4598-9618-432ca067a02f)
- OpenAI Chat Model (13743c5a-d649-49a3-8cd6-4c03494d9749)
- Simple Memory (9081f1d4-5dac-4350-b910-e17ad918208f)
- AI Image Generation Tool (c3becf95-359b-4a4a-8dc7-4e9faacf5b81)

**Purpose**: Orchestrate carousel generation intelligently

**Reuse Approach**: Copy exact structure, modify parameters

**Parameters to Change**:
- **System Prompt**:
  ```
  OLD: "You are an expert content writer..."
  NEW: "You are an expert carousel designer. Generate 5 compelling slide prompts for DALL-E 3 that tell a cohesive story. Each prompt should be detailed, visual, and build on the previous slide."
  ```
- **Tool Description**:
  ```
  OLD: "Generate an image for blog post"
  NEW: "Generate a carousel slide image using DALL-E 3. Provide detailed visual description."
  ```
- **Output Parser Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "slide_prompts": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "slide_number": { "type": "number" },
            "prompt": { "type": "string" },
            "style": { "type": "string" },
            "description": { "type": "string" }
          }
        }
      },
      "carousel_title": { "type": "string" },
      "carousel_description": { "type": "string" }
    }
  }
  ```

---

### Component 2: Sequential Image Generation Chain (Template #4028)

**Source**: Template #4028, nodes:
- OpenAI - Generate Image 1-5 (e2edf20b... through fa3c014c...)
- Separate Image Outputs 1-5 (004cb6dc... through 72fb090f...)
- Convert to File 1-5 (5f330301... through ed5689d2...)
- Change name to photo 1-5 (fef53966... through 596b16da...)

**Purpose**: Generate images sequentially and process outputs

**Reuse Approach**: Adapt structure, replace OpenAI API calls

**Parameters to Change**:

**HTTP Request (Image Generation)**:
- **OLD URL**: `https://api.openai.com/v1/images/generations`
- **NEW URL**: `https://api.openai.com/v1/images/generations` (same)
- **OLD Model**: `gpt-image-1`
- **NEW Model**: `dall-e-3`
- **OLD Prompt Source**: `{{ $json.promptN }}`
- **NEW Prompt Source**: `{{ $json.slide_prompts[N-1].prompt }}`
- **OLD Size**: `1024x1536`
- **NEW Size**: `1024x1024` (square for carousel)
- **NEW Parameters**:
  ```json
  {
    "model": "dall-e-3",
    "prompt": "{{ $json.slide_prompts[0].prompt }}",
    "size": "1024x1024",
    "quality": "hd",
    "style": "{{ $json.slide_prompts[0].style || 'vivid' }}",
    "response_format": "b64_json"
  }
  ```

**Code Node (Rename)**:
- **OLD**: `fileName: 'photo1.png'`
- **NEW**: `fileName: 'carousel_slide_1.png'`

---

### Component 3: Google Drive Upload + URL (Template #9191)

**Source**: Template #9191 sub-workflow, nodes:
- Convert Base64 to Binary (6756130b-2e51-4457-a28d-f810f9968fac)
- Upload to Google Drive (9830cce4-9d2f-450f-a61a-2937b3d9831c)
- Get Download Links (4c611c1f-8a67-482f-a8c2-3faccc234d84)
- Result (4828babb-1f1c-4e19-86a3-effc98f5e4f4)

**Purpose**: Store images and get public URLs

**Reuse Approach**: Copy exact, configure folder

**Parameters to Change**:

**Upload to Google Drive**:
- **Folder ID**: `<YOUR_CAROUSEL_FOLDER_ID>`
- **File Name**: Use dynamic expression
  ```
  {{ 'carousel_' + $now.format('YYYY-MM-DD_HHmmss') + '_slide_' + $json.slide_number + '.png' }}
  ```
- **Parents**: Ensure folder is set correctly

**Get Download Links**:
- **File ID**: Pass from upload result
- **Share Type**: `anyone` (public) or `domain` (organization)

---

### Component 4: Error Handling System (Template #9191)

**Source**: Template #9191, nodes:
- Check Success (4755da23-5ea0-4420-b5a2-7976e41411d1)
- Mark as Complete (a013bc1b-70af-4c27-9c88-c5df8a913bd1)
- Log Error (d833be28-654b-41f1-af4d-bcf18e8aa3ec)
- Save Error (632a7c39-687c-4ea9-95e0-dd57b302c191)
- Wait a few seconds (5f4abc50-4c29-4424-9668-b3eb1494fb66)

**Purpose**: Comprehensive error handling and logging

**Reuse Approach**: Copy pattern, adapt for image generation

**Parameters to Change**:

**Check Success (IF node)**:
- **OLD Condition**: `{{ $json.webflow_id !== undefined }}`
- **NEW Condition**: `{{ $json.image_url !== undefined && $json.quality_score >= 7 }}`

**Log Error (Code node)**:
- **OLD**:
  ```javascript
  return {
    keyword: $json.keyword,
    error: $json.error,
    timestamp: new Date().toISOString()
  };
  ```
- **NEW**:
  ```javascript
  return {
    carousel_id: $json.carousel_id,
    slide_number: $json.slide_number,
    error_type: $json.error_type,
    error_message: $json.error_message,
    prompt: $json.prompt,
    retry_count: $json.retry_count || 0,
    timestamp: new Date().toISOString()
  };
  ```

**Save Error (Google Sheets)**:
- **Sheet Name**: `carousel_error_logs`
- **Columns**: `carousel_id, slide_number, error_type, error_message, prompt, retry_count, timestamp, status`

---

### Component 5: Quality Validation Pattern (Template #9191)

**Source**: Template #9191, nodes:
- Content Quality Check (3403fae8-07ba-4faf-9db5-0ad221b1360e)
- Expand Content (457c8c37-c678-4299-8676-4ec41c2ba56d)
- Format Agent Output (6a7bc453-cf01-4bed-88a9-7b8d478793a2)

**Purpose**: Validate output quality and auto-fix if needed

**Reuse Approach**: Adapt pattern for image validation

**Parameters to Change**:

**Quality Check (IF node)**:
- **OLD Condition**: `{{ $json.word_count >= 600 }}`
- **NEW Condition**: `{{ $json.image_analysis.quality_score >= 7 && $json.image_analysis.subject_match >= 0.8 }}`

**Expand Content → Regenerate Image**:
- **Purpose**: If image fails validation, regenerate with modified prompt
- **Implementation**:
  ```javascript
  // Modify prompt to address quality issues
  const issues = $json.image_analysis.issues;
  let modifiedPrompt = $json.original_prompt;

  if (issues.includes('low_resolution')) {
    modifiedPrompt += ', highly detailed, sharp focus, 8k resolution';
  }
  if (issues.includes('poor_composition')) {
    modifiedPrompt += ', professional composition, rule of thirds';
  }
  if (issues.includes('wrong_subject')) {
    modifiedPrompt = 'IMPORTANT: ' + modifiedPrompt + '. Focus on: ' + $json.required_subject;
  }

  return {
    json: {
      modified_prompt: modifiedPrompt,
      retry_count: ($json.retry_count || 0) + 1,
      max_retries: 2
    }
  };
  ```

---

## Net-New Components Needed

### Net-New Component 1: Image Analysis Node

**Purpose**: Validate generated images for quality and relevance

**Build Approach**: Create custom HTTP Request node

**Implementation**:
```json
{
  "node_type": "n8n-nodes-base.httpRequest",
  "name": "Analyze Image Quality",
  "method": "POST",
  "url": "https://api.openai.com/v1/chat/completions",
  "authentication": "predefinedCredentialType",
  "nodeCredentialType": "openAiApi",
  "body": {
    "model": "gpt-4o",
    "messages": [
      {
        "role": "system",
        "content": "You are an expert image quality analyst. Analyze the provided image and return a structured quality assessment."
      },
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": "Analyze this carousel slide image. Expected subject: {{ $json.expected_subject }}. Rate quality 0-10, subject match 0-1, list any issues."
          },
          {
            "type": "image_url",
            "image_url": {
              "url": "data:image/png;base64,{{ $json.image_base64 }}"
            }
          }
        ]
      }
    ],
    "response_format": {
      "type": "json_schema",
      "json_schema": {
        "name": "image_analysis",
        "schema": {
          "type": "object",
          "properties": {
            "quality_score": { "type": "number" },
            "subject_match": { "type": "number" },
            "issues": {
              "type": "array",
              "items": { "type": "string" }
            },
            "recommendations": { "type": "string" }
          }
        }
      }
    }
  }
}
```

**Estimated Complexity**: Medium
**Dependencies**: OpenAI API with Vision capabilities
**Testing**: Test with known good/bad images first

---

### Net-New Component 2: Rate Limit Manager

**Purpose**: Prevent DALL-E API rate limit errors

**Build Approach**: Code node + Wait node combination

**Implementation**:

**Step 1: Track API Calls (Code Node)**
```javascript
// Initialize or update rate limit tracking
const now = Date.now();
const windowMs = 60 * 1000; // 1 minute window
const maxCallsPerMinute = 5; // DALL-E 3 limit (adjust based on tier)

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
      calls_in_window: tracking.calls.length
    }
  };
}

// Add current call
tracking.calls.push(now);
$workflow.staticData.rateLimit = tracking;

return {
  json: {
    can_proceed: true,
    wait_seconds: 0,
    calls_in_window: tracking.calls.length
  }
};
```

**Step 2: Conditional Wait (IF + Wait)**
```
Rate Limit Check (Code)
    ↓
IF can_proceed === false
    ├─ TRUE → Wait ({{ $json.wait_seconds }} seconds) → Loop back to Rate Limit Check
    └─ FALSE → Continue to Image Generation
```

**Estimated Complexity**: Medium
**Dependencies**: n8n workflow static data
**Testing**: Test with rapid-fire requests to validate throttling

---

### Net-New Component 3: Carousel Metadata Generator

**Purpose**: Create structured metadata for carousel

**Build Approach**: Add to AI Agent system prompt or separate AI call

**Implementation Option A: Include in Agent Prompt**
```
System Prompt Addition:
"After generating slide prompts, also create:
- carousel_title: Catchy title for entire carousel (5-8 words)
- carousel_description: Brief description (15-20 words)
- carousel_tags: 3-5 relevant tags
- slide_descriptions: Brief description for each slide (10-15 words)"
```

**Implementation Option B: Separate AI Call**
```json
{
  "node_type": "@n8n/n8n-nodes-langchain.chainLlm",
  "name": "Generate Carousel Metadata",
  "input": {
    "slide_prompts": "{{ $json.slide_prompts }}",
    "theme": "{{ $json.theme }}"
  },
  "prompt": "Based on these carousel slide prompts, generate comprehensive metadata...",
  "output_parser": "structured"
}
```

**Estimated Complexity**: Low
**Dependencies**: OpenAI API
**Testing**: Validate metadata quality and consistency

---

### Net-New Component 4: Progress Tracking

**Purpose**: Monitor carousel generation status

**Build Approach**: Google Sheet updates at key milestones

**Implementation**:

**Sheet Structure**:
| carousel_id | status | current_slide | total_slides | started_at | completed_at | error_count | image_urls |
|-------------|---------|---------------|--------------|------------|--------------|-------------|------------|

**Update Points**:
1. **Start**: `{ status: 'generating', current_slide: 0, started_at: NOW() }`
2. **After Each Slide**: `{ current_slide: N, image_urls: [url1, url2, ...] }`
3. **Completion**: `{ status: 'completed', completed_at: NOW() }`
4. **Error**: `{ status: 'failed', error_count: N }`

**Google Sheets Nodes**:
```json
{
  "operation": "update",
  "sheetName": "carousel_progress",
  "range": "A:H",
  "options": {
    "valueInputMode": "USER_ENTERED"
  }
}
```

**Estimated Complexity**: Low
**Dependencies**: Google Sheets API
**Testing**: Monitor sheet updates during test runs

---

## Integration Strategy

### Phase 1: Foundation (Templates #4028 + #9191 Core)

**Steps**:
1. Create new n8n workflow: `dev-carousel-generator`
2. Add Manual Trigger node
3. Copy AI Agent setup from Template #9191:
   - AI Agent node
   - OpenAI Chat Model
   - Simple Memory (Buffer Window)
4. Configure agent system prompt (see Component 1)
5. Test: Verify agent can generate text responses

**Validation**:
- ✅ Agent responds to manual trigger
- ✅ Agent system prompt is carousel-focused
- ✅ Memory persists conversation context

---

### Phase 2: Image Generation Tool (Adapted #9191 Sub-Workflow)

**Steps**:
1. Create sub-workflow: `lib-dalle3-image-generator`
2. Add Execute Workflow Trigger
3. Add Rate Limit Manager (Net-New Component 2)
4. Add DALL-E 3 HTTP Request (adapted from #4028)
5. Add Image Analysis (Net-New Component 1)
6. Add Quality Check (IF node)
7. Add Google Drive Upload (from #9191)
8. Add Result node
9. Test sub-workflow in isolation

**Validation**:
- ✅ Sub-workflow generates DALL-E 3 image
- ✅ Image analysis returns quality score
- ✅ Failed images trigger retry (max 2)
- ✅ Successful images upload to Google Drive
- ✅ Returns image URL to caller

---

### Phase 3: Tool Integration (Connect Agent + Sub-Workflow)

**Steps**:
1. In main workflow, add Tool Workflow node
2. Reference `lib-dalle3-image-generator` sub-workflow
3. Configure tool description for agent
4. Test: Agent calls tool with sample prompt
5. Verify tool returns image URL to agent

**Validation**:
- ✅ Agent can invoke image generation tool
- ✅ Tool receives parameters correctly
- ✅ Tool returns result in expected format
- ✅ Agent can use returned image URL

---

### Phase 4: Sequential Loop (Adapted #4028 Pattern)

**Steps**:
1. Add Structured Output Parser to agent
2. Configure schema for 5 slide prompts
3. Add Split Out node to separate slide prompts
4. Add Loop node (for each slide):
   - Call image generation tool
   - Store result
   - Continue to next
5. Add Merge node to collect all slide results

**Validation**:
- ✅ Agent generates 5 structured slide prompts
- ✅ Loop processes each prompt sequentially
- ✅ Each slide generates valid image + URL
- ✅ Merge collects all 5 image URLs

---

### Phase 5: Error Handling & Progress (Adapted #9191)

**Steps**:
1. Add Progress Tracking Google Sheet
2. Add initial status update (carousel started)
3. After each slide, update progress
4. Add error logging for failed slides
5. Add final completion status update
6. Test error scenarios (force API failure)

**Validation**:
- ✅ Progress sheet updates at each stage
- ✅ Errors are logged with context
- ✅ Workflow continues after recoverable errors
- ✅ Final status reflects actual completion state

---

### Phase 6: Final Assembly & Testing

**Steps**:
1. Add Carousel Metadata Generator (Net-New Component 3)
2. Create final data structure:
   ```json
   {
     "carousel_id": "...",
     "title": "...",
     "description": "...",
     "tags": [...],
     "slides": [
       {
         "slide_number": 1,
         "image_url": "...",
         "description": "...",
         "quality_score": 8.5
       },
       // ... 4 more slides
     ],
     "created_at": "...",
     "storage_folder": "..."
   }
   ```
3. Test full carousel generation end-to-end
4. Validate all images are accessible
5. Check error scenarios handled gracefully

**Validation**:
- ✅ Complete carousel data structure generated
- ✅ All 5 images stored in Google Drive
- ✅ All image URLs are accessible
- ✅ Metadata is accurate and useful
- ✅ Execution completes in <10 minutes
- ✅ Error handling prevents catastrophic failures

---

## Testing Plan

### Test 1: Single Image Generation
**Objective**: Validate basic image generation pipeline

**Steps**:
1. Manually trigger sub-workflow
2. Pass single slide prompt
3. Verify image generation
4. Verify quality analysis
5. Verify Google Drive upload
6. Check returned URL is accessible

**Expected Result**: Single image successfully generated and stored

---

### Test 2: AI Agent Tool Integration
**Objective**: Validate agent can call image generation tool

**Steps**:
1. Trigger main workflow
2. Agent generates 1 slide prompt
3. Agent calls tool with prompt
4. Verify tool executes
5. Verify agent receives URL back
6. Check agent can continue after tool call

**Expected Result**: Agent successfully orchestrates image generation

---

### Test 3: Multi-Slide Sequential Generation
**Objective**: Validate full carousel generation

**Steps**:
1. Trigger main workflow
2. Agent generates 5 slide prompts
3. Loop processes all 5 slides
4. Each slide generates image
5. Each image passes quality check
6. All images merge at end
7. Verify all 5 images in Google Drive

**Expected Result**: Complete 5-image carousel generated

---

### Test 4: Quality Rejection & Retry
**Objective**: Validate quality check and retry logic

**Steps**:
1. Force low-quality image (manipulate quality score)
2. Verify quality check fails
3. Verify retry with modified prompt
4. Verify max retry limit (2) enforced
5. Check workflow continues even if max retries exceeded

**Expected Result**: Failed images retry up to 2 times, then continue

---

### Test 5: Rate Limit Handling
**Objective**: Validate rate limit manager prevents API errors

**Steps**:
1. Trigger multiple workflow instances simultaneously
2. Monitor API call timing
3. Verify wait periods inserted when limit approached
4. Confirm no 429 errors from DALL-E API
5. Verify all instances complete successfully

**Expected Result**: Rate limit manager prevents API errors

---

### Test 6: Error Recovery
**Objective**: Validate workflow handles errors gracefully

**Test Scenarios**:
- **Scenario A**: DALL-E API returns 500 error
  - Expected: Retry 2 times, log error, continue
- **Scenario B**: Google Drive upload fails
  - Expected: Retry upload, log error, continue
- **Scenario C**: Agent generates malformed prompt
  - Expected: Catch error, regenerate prompt, continue
- **Scenario D**: Image analysis API timeout
  - Expected: Skip analysis, accept image, log warning

**Expected Result**: Workflow completes despite errors, logs all issues

---

### Test 7: Concurrent Execution
**Objective**: Validate multiple carousels can generate simultaneously

**Steps**:
1. Trigger 3 workflow instances at once
2. Monitor resource usage
3. Verify no race conditions (rate limit tracking)
4. Verify no cross-contamination of data
5. Confirm all 3 complete successfully

**Expected Result**: All instances complete independently without conflicts

---

## Success Criteria Checklist

**Implementation Complete When**:
- [ ] All components from templates successfully adapted
- [ ] All net-new components built and tested
- [ ] AI Agent generates 5 coherent slide prompts
- [ ] Image generation tool creates DALL-E 3 images
- [ ] Image analysis validates quality (score 0-10)
- [ ] Failed images retry with modified prompts (max 2)
- [ ] All images upload to Google Drive
- [ ] Public URLs generated for all images
- [ ] Rate limit manager prevents API errors
- [ ] Error logging captures all failures
- [ ] Progress tracking updates throughout execution
- [ ] Full carousel generation completes in <10 minutes
- [ ] Workflow validation passes (n8n built-in validator)
- [ ] All 7 test scenarios pass
- [ ] Error recovery handles failures gracefully
- [ ] Documentation updated with learnings

**Pattern Library Extraction Complete When**:
- [ ] Reusable patterns extracted to `.claude/workflow-examples/patterns/`
- [ ] Pattern JSON files created for key components
- [ ] Pattern documentation written
- [ ] Common mistakes documented
- [ ] Pattern index updated

---

## Timeline Estimate

**Phase 1 (Foundation)**: 30 minutes
**Phase 2 (Image Tool)**: 2 hours
**Phase 3 (Tool Integration)**: 1 hour
**Phase 4 (Sequential Loop)**: 1.5 hours
**Phase 5 (Error Handling)**: 1 hour
**Phase 6 (Final Assembly)**: 1 hour
**Testing**: 2 hours
**Documentation**: 1 hour

**Total Estimated Time**: 10 hours

**Complexity Breakdown**:
- Simple tasks (30%): Template copying, basic configuration
- Medium tasks (50%): Adapting patterns, tool integration
- Complex tasks (20%): Net-new components (image analysis, rate limit manager)

---

## Next Steps

1. **Immediate**: Start Phase 1 (Foundation) when ready to build
2. **Before Building**: Review API rate limits for current OpenAI tier
3. **Before Building**: Create Google Drive folder structure
4. **Before Building**: Set up Google Sheet for progress tracking
5. **During Building**: Document deviations from plan
6. **After Building**: Extract patterns to pattern library
7. **After Testing**: Update `agents-evolution.md` with outcomes

---

**Last Updated:** 2025-11-22
**Context Sources**: Template #4028, Template #9191
**Build Confidence**: High (85% coverage from proven templates)
