# AI Carousel Generator Workflow

**Workflow ID:** `8bhcEHkbbvnhdHBh`
**Type:** AI-Powered Content Generation
**Status:** Active Development → Ready for Deployment
**Version:** 2.0.0 (Complete Rebuild)

---

## Overview

Generates high-quality 5-slide carousels using AI:
- **AI Agent** generates coherent, story-driven slide prompts
- **DALL-E 3** creates high-definition images for each slide
- **GPT-4 Vision** validates quality with automatic retry logic
- **Google Drive** stores images with public URLs
- **Webhook API** provides complete carousel metadata

---

## Architecture

### Flow Diagram

```
Webhook Trigger (POST /carousel-generate)
    ↓
Set User Input (theme, style, audience)
    ↓
AI Agent (Generate 5 Slide Prompts)
├─ OpenAI GPT-4 Turbo (language model)
├─ Memory Buffer (conversation context)
└─ Structured Output Parser (JSON schema)
    ↓
Split Slide Prompts (5 items)
    ↓
FOR EACH SLIDE:
    ↓
    Set Slide Variables (prompt, style, description, retry_count)
    ↓
    Generate Image - DALL-E 3 (1024x1792, HD quality)
    ↓
    Analyze Image Quality (GPT-4 Vision)
    ↓
    Parse Quality Score (extract JSON, calculate average)
    ↓
    Quality Check (score >= 7 OR max retries?)
    ├─ TRUE → Upload to Google Drive
    │           ↓
    │       Set Public Permissions
    │           ↓
    │       Format Slide Result
    │
    └─ FALSE → Modify Prompt for Retry
                   ↓
               Loop back to Set Slide Variables
    ↓
Merge All Slides (aggregate 5 results)
    ↓
Generate Carousel Metadata
    ↓
Respond to Webhook (JSON response)
```

### Node Count
- **Total Nodes:** 19
- **AI Nodes:** 4 (GPT-4 Turbo, AI Agent, DALL-E 3, GPT-4 Vision)
- **Logic Nodes:** 7 (Set, IF, Code, Split, Merge)
- **Integration Nodes:** 3 (Google Drive upload, share, webhook response)

---

## API Usage

### Webhook Endpoint

**URL:** `https://[your-n8n-instance].n8n.cloud/webhook/carousel-generate`
**Method:** `POST`
**Content-Type:** `application/json`

### Request Body

```json
{
  "theme": "AI automation benefits for small businesses",
  "style": "vivid",
  "audience": "business owners"
}
```

**Parameters:**
- `theme` (string, optional): Carousel topic/theme
  - Default: "AI automation benefits for small businesses"
- `style` (string, optional): Image style - "vivid" or "natural"
  - Default: "vivid"
- `audience` (string, optional): Target audience description
  - Default: "business owners"

### Response

```json
{
  "carousel_id": "car_1700000000000",
  "title": "AI Transforms Small Business",
  "description": "Discover how AI automation saves time, reduces costs, and scales your business effortlessly",
  "tags": ["AI", "automation", "business", "productivity", "technology"],
  "slide_count": 5,
  "slides": [
    {
      "slide_number": 1,
      "image_url": "https://drive.google.com/uc?export=view&id=XXXXX",
      "file_id": "XXXXX",
      "file_name": "carousel_2025-11-23_120000_slide_1.png",
      "description": "The problem: Manual work overload",
      "quality_score": 8.5,
      "retry_count": 0
    },
    // ... 4 more slides
  ],
  "created_at": "2025-11-23T12:00:00.000Z",
  "average_quality_score": 8.3,
  "total_retries": 2,
  "status": "completed"
}
```

---

## Features

### 1. AI-Powered Slide Generation
- **AI Agent** with GPT-4 Turbo creates narrative-driven prompts
- **Structured Output** ensures consistent 5-slide format
- **Story Arc:** Hook → Context → Core → Support → CTA

### 2. Quality Validation & Auto-Retry
- **GPT-4 Vision** analyzes each image (0-10 scoring)
- **4 Quality Metrics:**
  - Overall quality
  - Subject relevance
  - Visual clarity
  - Professional appearance
- **Retry Logic:** Max 2 retries per slide
- **Smart Prompt Modification:** Adds specific improvements based on issues

### 3. Error Handling
- **Webhook:** Continue on error, always send response
- **OpenAI Nodes:** Continue on error (retry handled separately)
- **Google Drive:** Continue on error (graceful degradation)
- **Quality Check:** Error output for retry loop

### 4. Google Drive Integration
- **Auto-upload** all generated images
- **Public permissions** set automatically
- **Direct URLs** for immediate use
- **Organized naming:** `carousel_[timestamp]_slide_[num].png`

---

## Configuration

### Prerequisites
1. **OpenAI API Key** (configured in n8n credentials)
   - GPT-4 Turbo access
   - DALL-E 3 access
   - GPT-4 Vision access
2. **Google Drive OAuth** (configured in n8n credentials)
   - Drive write permission
   - Public sharing permission
3. **Google Drive Folder ID:** `1v0lANQ70OY7C1d8QM5va4PaZsE83w4Ew`
   - Update in nodes: "Upload to Google Drive" and "Set Public Permissions"

### Credential IDs
- **OpenAI API:** `6BIzzQu5jAD5jKlH` ("OpenAi account")
- **Google Drive OAuth:** `ylMLH2SMUpGQpUUr` ("Google Drive account")

### Customizable Parameters

**In "Set Slide Variables" node:**
- `max_retries`: Default 2 (increase for stricter quality requirements)

**In "Quality Check" node:**
- Quality threshold: Default 7.0 (adjust between 0-10)

**In "Generate Image - DALL-E 3" node:**
- `size`: Default "1024x1792" (3:4 portrait)
- `quality`: Default "hd"
- `style`: Dynamic (from user input)

---

## Performance

### Expected Timeline
- **AI Agent (prompt generation):** ~10-15 seconds
- **Image 1 generation:** ~15-20 seconds
- **Images 2-5 generation:** ~15-20 seconds each
- **Quality analysis:** ~5 seconds per image
- **Total (no retries):** ~2-3 minutes
- **Total (with retries):** ~4-6 minutes

### API Costs (Estimated)
- **GPT-4 Turbo:** $0.01-0.03 per carousel (prompt generation)
- **DALL-E 3 (HD, 1024x1792):** $0.08 × 5 = $0.40 per carousel
- **GPT-4 Vision:** $0.01 × 5 = $0.05 per carousel
- **Total per carousel:** ~$0.45-0.50 (without retries)
- **With retries (avg 2):** ~$0.55-0.65

---

## Troubleshooting

### Issue: Images fail quality check repeatedly
**Solution:**
1. Lower quality threshold from 7.0 to 6.0 in "Quality Check" node
2. Increase `max_retries` to 3 in "Set Slide Variables"
3. Review prompt modification logic in "Modify Prompt for Retry"

### Issue: DALL-E 3 generation timeout
**Solution:**
1. Check OpenAI API status
2. Verify API key has DALL-E 3 access
3. Reduce image size to "1024x1024" for faster generation

### Issue: Google Drive upload fails
**Solution:**
1. Verify folder ID is correct
2. Check Google Drive credentials are valid
3. Ensure folder has write permissions
4. Check Google Drive API quota

### Issue: Workflow takes too long
**Solution:**
1. Reduce quality threshold (fewer retries)
2. Use "natural" style instead of "vivid" (faster generation)
3. Check rate limiting is not causing delays

---

## Testing

### Manual Test
```bash
curl -X POST https://[your-n8n-instance].n8n.cloud/webhook/carousel-generate \
  -H "Content-Type: application/json" \
  -d '{
    "theme": "Benefits of automation",
    "style": "vivid",
    "audience": "entrepreneurs"
  }'
```

### Expected Outcomes
- ✅ All 5 slides generate successfully
- ✅ All image URLs are accessible
- ✅ Average quality score >= 7.5
- ✅ Execution completes in < 10 minutes
- ✅ No critical errors

---

## Monitoring

### Key Metrics to Track
1. **Success Rate:** % of carousels generated successfully
2. **Average Quality Score:** Should be >= 7.5
3. **Average Retries:** Should be < 3 per carousel
4. **Execution Time:** Should be < 10 minutes
5. **API Costs:** Track OpenAI spending

### Error Logging
- Webhook errors automatically continue with error response
- API failures logged in n8n execution logs
- Quality issues trigger retry (not considered errors)

---

## Future Improvements

### Phase 1 (Short-term)
- [ ] Add webhook authentication
- [ ] Implement rate limiting
- [ ] Add carousel template variations
- [ ] Support custom image dimensions

### Phase 2 (Medium-term)
- [ ] Move image generation to sub-workflow
- [ ] Add image editing/enhancement
- [ ] Support video slide generation
- [ ] Add database storage for carousel history

### Phase 3 (Long-term)
- [ ] Multi-language support
- [ ] Brand style customization
- [ ] Batch carousel generation
- [ ] Integration with CMS platforms

---

## Version History

See [CHANGELOG.md](./CHANGELOG.md) for detailed version history.

---

## Support & Resources

**Internal Documentation:**
- [Workflow Development Protocol](.claude/WORKFLOW-DEVELOPMENT-PROTOCOL.md)
- [Build Plan](.claude/workflow-examples/contexts/carousel-generator-context/build-plan.md)
- [Pattern Library](.claude/workflow-examples/patterns/)

**n8n Resources:**
- [n8n Docs](https://docs.n8n.io)
- [AI Nodes](https://docs.n8n.io/integrations/builtin/cluster-nodes/root-nodes/n8n-nodes-langchain/)
- [Workflow Best Practices](https://docs.n8n.io/workflows/best-practices/)

---

**Last Updated:** 2025-11-23
**Maintained By:** SYNRG Automation Team
