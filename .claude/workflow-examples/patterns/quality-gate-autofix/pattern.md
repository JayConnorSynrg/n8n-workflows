# Pattern: Quality Gate with Auto-Fix

**Category:** Integration / Data Validation
**Quality Level:** 🧪 Tested
**Source:** n8n Template #9191
**Complexity:** Moderate

---

## Overview

Validate output quality against predefined criteria and automatically attempt to improve low-quality outputs before allowing them to continue through the workflow. Reduces manual intervention and ensures consistent quality standards.

---

## When to Use

✅ **Use this pattern when:**
- Quality standards must be met (content, images, data)
- Automated improvement is possible (AI refinement, retry, etc.)
- User shouldn't see low-quality outputs
- Manual review is too slow or expensive
- Quality can be measured objectively (scores, criteria)

❌ **Don't use when:**
- Quality is subjective and can't be measured
- Auto-fix isn't possible or reliable
- Performance is critical (adds latency)
- Validation criteria are unclear

---

## Pattern Structure

```
Generate Content/Data
    ↓
Validate Quality (AI or Rules)
    ↓
IF: Quality Score >= Threshold?
├─ PASS → Continue to next step
└─ FAIL → Enhance/Improve
              ↓
        Revalidate Quality
              ↓
        IF: Improved?
        ├─ Yes → Continue
        └─ No → Log issue + Continue with best attempt
```

---

## Key Components

### 1. Quality Validation Node
**Type:** `@n8n/n8n-nodes-langchain.openAi` (for AI-based validation)
**Purpose:** Analyze content and assign quality score

**Configuration (Image Quality Example):**
```json
{
  "resource": "image",
  "operation": "analyze",
  "modelId": "gpt-4o",
  "inputType": "base64",
  "binaryPropertyName": "data",
  "text": "Analyze this image quality. Rate from 0-10 based on: clarity (25%), subject relevance (25%), composition (25%), professional appearance (25%). Return JSON: {\"score\": X, \"issues\": [\"...\"], \"suggestions\": [\"...\"]}"
}
```

### 2. Quality Gate (IF Node)
**Type:** `n8n-nodes-base.if`
**Purpose:** Route based on quality score

**Configuration:**
```json
{
  "conditions": {
    "number": [
      {
        "value1": "={{ $json.score }}",
        "operation": "larger",
        "value2": 7
      }
    ]
  }
}
```

### 3. Enhancement Node
**Type:** `@n8n/n8n-nodes-langchain.agent` or HTTP Request
**Purpose:** Improve low-quality output

**Configuration (Image Regeneration Example):**
```json
{
  "promptType": "define",
  "text": "Original prompt: {{ $json.original_prompt }}\n\nQuality issues identified: {{ $json.issues.join(', ') }}\n\nSuggestions: {{ $json.suggestions.join(', ') }}\n\nGenerate an improved prompt that addresses these issues while maintaining the original intent.",
  "options": {
    "systemMessage": "You are an expert prompt engineer. Refine prompts to produce higher quality AI-generated images."
  }
}
```

### 4. Retry Counter
**Type:** `n8n-nodes-base.set`
**Purpose:** Track improvement attempts to prevent infinite loops

**Configuration:**
```json
{
  "values": {
    "number": [
      {
        "name": "retry_count",
        "value": "={{ $json.retry_count ? $json.retry_count + 1 : 1 }}"
      }
    ]
  },
  "options": {
    "keepOnlySet": false
  }
}
```

---

## Quality Criteria Examples

### Image Quality
```javascript
{
  "clarity": 0-10,      // Sharpness, resolution
  "relevance": 0-10,    // Matches prompt/intent
  "composition": 0-10,  // Framing, balance
  "professional": 0-10, // Polished appearance
  "overall": average    // Composite score
}
```

### Content Quality (Blog Posts)
```javascript
{
  "readability": 0-10,  // Clear, easy to understand
  "seo": 0-10,          // Keyword usage, structure
  "accuracy": 0-10,     // Factually correct
  "engagement": 0-10,   // Compelling, interesting
  "overall": average
}
```

### Data Quality
```javascript
{
  "completeness": 0-10, // All required fields present
  "validity": 0-10,     // Data format correct
  "accuracy": 0-10,     // Values make sense
  "consistency": 0-10,  // No contradictions
  "overall": average
}
```

---

## Auto-Fix Strategies

### For AI-Generated Content
1. **Prompt Refinement:** Improve prompt based on issues
2. **Parameter Adjustment:** Change temperature, model, etc.
3. **Alternative Model:** Try different AI model
4. **Few-Shot Examples:** Add examples to prompt

### For Data Quality
1. **Fill Missing Fields:** Use defaults or API lookups
2. **Format Correction:** Normalize phone numbers, emails, etc.
3. **Validation Rules:** Apply business logic fixes
4. **Enrichment:** Add data from external sources

### For Image Quality
1. **Regenerate:** New image with refined prompt
2. **Upscale:** Improve resolution with AI upscaler
3. **Style Transfer:** Apply professional styling
4. **Crop/Adjust:** Fix composition issues

---

## Best Practices

### Set Maximum Retry Limit
**Prevent infinite loops:**
```
IF: retry_count < 3 AND score < threshold
├─ True → Attempt auto-fix
└─ False → Continue with best attempt + log issue
```

### Log Quality Issues
**Track patterns for improvement:**
```json
{
  "timestamp": "2025-11-22T10:30:00Z",
  "item_id": "image_3",
  "initial_score": 6.2,
  "final_score": 8.1,
  "attempts": 2,
  "issues": ["low clarity", "poor composition"],
  "auto_fix_success": true
}
```

### Define Clear Thresholds
**Quality score guidelines:**
- **9-10:** Exceptional quality (publish immediately)
- **7-8:** Good quality (acceptable)
- **5-6:** Below standard (attempt auto-fix)
- **0-4:** Poor quality (auto-fix + manual review flag)

---

## Real-World Example

**Use Case:** AI Carousel Generator with quality assurance

**Workflow:**
1. Generate carousel slide image
2. Analyze quality (GPT-4 Vision)
3. IF score < 7:
   - Extract issues and suggestions
   - Refine prompt with AI
   - Regenerate image
   - Revalidate
4. IF still < 7 after 2 attempts:
   - Use best attempt
   - Flag for manual review
5. Continue to next slide

**Performance:**
- ~80% pass first validation (score >= 7)
- ~15% pass after 1 auto-fix attempt
- ~4% pass after 2 auto-fix attempts
- ~1% flagged for manual review

**Impact:**
- 95% success rate without manual intervention
- Average quality score: 8.2 (vs. 7.1 without auto-fix)

---

## Advantages

✅ **Consistent Quality:** Automated enforcement of standards
✅ **Reduced Manual Work:** Auto-fix handles most issues
✅ **Better Outputs:** Higher average quality
✅ **Learning Loop:** Logs reveal common issues to address
✅ **User Satisfaction:** Users receive higher quality results

---

## Disadvantages

❌ **Added Latency:** Validation + auto-fix adds time
❌ **Cost:** Additional AI API calls for validation/enhancement
❌ **Complexity:** More nodes and logic to maintain
❌ **False Positives:** May reject acceptable outputs
❌ **Diminishing Returns:** Multiple fixes may not improve quality

---

## Testing Checklist

Before deploying:
- [ ] Define clear quality criteria (measurable)
- [ ] Set appropriate threshold (not too strict)
- [ ] Test auto-fix with known low-quality examples
- [ ] Verify retry limit prevents infinite loops
- [ ] Check logging captures issues for analysis
- [ ] Validate performance impact is acceptable
- [ ] Test edge cases (validation fails, auto-fix fails)

---

## Related Patterns

- [Sequential Image Generation Chain](../sequential-image-chain/) - Add quality gates between images
- [AI Agent with Sub-Workflow Tool](../ai-agent-with-tool/) - Wrap quality check as tool
- [Comprehensive Error Handling](../comprehensive-error-handling/) - Handle validation failures

---

**Pattern Extracted:** 2025-11-22
**Last Validated:** 2025-11-22
**Production Usage:** Template #9191, recommended for AI-generated content workflows
