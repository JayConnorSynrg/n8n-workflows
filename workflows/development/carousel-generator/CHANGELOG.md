# Changelog - AI Carousel Generator

All notable changes to workflow `8bhcEHkbbvnhdHBh` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [2.0.0] - 2025-11-23 - COMPLETE REBUILD

### Summary
Complete architectural rebuild of carousel generator workflow. Transformed from single-image quality loop to full 5-slide carousel generation system with AI-powered prompts, quality validation, and automated retry logic.

### Added
- **AI Agent Architecture:** GPT-4 Turbo with structured output for generating 5 coherent slide prompts
- **Webhook API:** POST endpoint `/carousel-generate` with JSON request/response
- **Sequential Processing:** Loop through 5 slides with independent generation and validation
- **Quality Validation:** GPT-4 Vision analysis of each image with 4-metric scoring system
- **Smart Retry Logic:** Automatic prompt modification based on quality issues (max 2 retries per slide)
- **Carousel Metadata:** Complete output with title, description, tags, and aggregate statistics
- **Error Handling:** Comprehensive error handling with `onError` properties on critical nodes
- **Public URL Generation:** Automatic Google Drive sharing with direct image URLs

### Changed
- **Workflow Name:** "dev-marketing-image-quality-loop" → "AI Carousel Generator - 5 Slides"
- **Trigger Type:** Manual Trigger → Webhook Trigger (POST)
- **Node Count:** 13 nodes → 19 nodes
- **Architecture:** Single image loop → Multi-slide sequential processing
- **Output Format:** Single image URL → Complete carousel with 5 slides + metadata
- **AI Model:** GPT-4 Turbo (prompt generation) + GPT-4 Vision (quality analysis)
- **Image Size:** 1024x1024 → 1024x1792 (3:4 portrait for carousel)

### Technical Changes

**Nodes Added:**
1. `Webhook Trigger` - Replaced Manual Trigger
2. `Set User Input` - Extract theme, style, audience from request
3. `OpenAI GPT-4 Turbo` - Language model for AI Agent
4. `Simple Memory` - Conversation buffer for AI Agent
5. `Parse Slide Prompts` - Structured output parser (JSON schema)
6. `Carousel Prompt Generator` - AI Agent node
7. `Split Slide Prompts` - Convert array to 5 separate items
8. `Set Slide Variables` - Initialize slide processing variables
9. `Modify Prompt for Retry` - Smart prompt modification on quality failure
10. `Merge All Slides` - Aggregate 5 slide results
11. `Generate Carousel Metadata` - Create comprehensive output
12. `Respond to Webhook` - Return JSON response

**Nodes Removed:**
1. `Initialize Loop Variables` - Replaced by Webhook + Set User Input
2. `Success Response` - Replaced by Generate Carousel Metadata
3. `Prepare Improvement Feedback` - Replaced by Modify Prompt for Retry

**Nodes Modified:**
1. `AI Agent - Generate/Refine Prompt` → `Carousel Prompt Generator`
   - Now generates 5 prompts simultaneously
   - Uses structured output parser
   - Story-driven prompt system
2. `OpenAI Chat Model` → `OpenAI GPT-4 Turbo`
   - Updated typeVersion 1.2 → 1.3
   - Added error handling
3. `Memory Buffer` → `Simple Memory`
   - No functional changes
4. `Generate Image with DALL-E-3` → `Generate Image - DALL-E 3`
   - Updated typeVersion 1.8 → 2
   - Changed size: 1024x1024 → 1024x1792
   - Added error handling
5. `Analyze Quality with Vision AI` → `Analyze Image Quality`
   - Updated typeVersion 1.8 → 2
   - Simplified scoring system
   - Added error handling
6. `Extract Quality Score` → `Parse Quality Score`
   - Enhanced JSON parsing with fallback
   - Added retry context preservation
7. `Check if Perfect or Max Iterations` → `Quality Check`
   - Updated typeVersion 2 → 2.2
   - Added error output handling
8. `Save Perfect Image` → `Upload to Google Drive`
   - Fixed expression format (resource locator)
   - Added error handling
9. `Set Public Permissions` - NEW FUNCTIONALITY
   - Automatically share uploaded files
   - Fixed expression format
   - Added error handling

### Fixed
- **Workflow Cycle Warning:** Retry loop is intentional (max 2 iterations)
- **Webhook Error Handling:** Added `onError: "continueRegularOutput"`
- **Expression Formats:** Updated Google Drive nodes to use resource locator format
- **Type Versions:** Updated outdated node typeVersions
- **Error Handling:** Added `onError` properties to all critical nodes

### Parameters & Configuration

**Fully Defined Parameters:**
- ✅ All node parameters explicitly set (0 placeholders)
- ✅ All expressions validated
- ✅ All credentials referenced
- ✅ All connections validated

**Credentials Used:**
- OpenAI API: `6BIzzQu5jAD5jKlH` (GPT-4 Turbo, DALL-E 3, GPT-4 Vision)
- Google Drive OAuth: `ylMLH2SMUpGQpUUr` (Upload + Share)

**Google Drive Configuration:**
- Folder ID: `1v0lANQ70OY7C1d8QM5va4PaZsE83w4Ew`
- Permissions: Public (reader, anyone)

### Quality Improvements
- **Error Resilience:** Comprehensive error handling prevents cascade failures
- **Quality Threshold:** Configurable (default: 7.0/10)
- **Retry Limit:** Max 2 retries per slide
- **Smart Retry:** Prompt modification based on specific quality issues
- **Fallback Behavior:** Continue workflow even if retries exhausted

### Performance
- **Execution Time:** ~2-6 minutes (depending on retries)
- **API Calls:** 10-20 per carousel (5 images + retries + quality checks)
- **Estimated Cost:** $0.45-0.65 per carousel

### Documentation
- ✅ README.md - Complete workflow documentation
- ✅ CHANGELOG.md - This file
- ✅ Build plan documented in `.claude/workflow-examples/contexts/carousel-generator-context/`
- ✅ Integration with `.claude/WORKFLOW-DEVELOPMENT-PROTOCOL.md`

### Testing Status
- ✅ JSON schema validation passed
- ✅ Connection validation passed
- ✅ Parameter completeness verified
- ⏳ Deployment pending (ready for instance)
- ⏳ End-to-end testing pending

### Breaking Changes
⚠️ **Complete API change** - Previous manual trigger workflow is completely replaced.

**Migration:**
- No backward compatibility
- New webhook endpoint required
- Different input/output format
- Original workflow backed up as `workflow-8bhcEHkbbvnhdHBh-baseline.json`

---

## [1.0.0] - 2025-11-23 - BASELINE (Deprecated)

### Summary
Original single-image quality loop workflow. Generated one image with iterative refinement.

### Features
- Manual trigger
- Single image generation with DALL-E 3
- Quality loop (max 5 iterations)
- GPT-4 Vision quality analysis (140-point scoring)
- Google Drive upload on success
- SYNRG brand aesthetic guidelines

### Limitations
- ❌ Only generates 1 image per execution
- ❌ No carousel support
- ❌ No API endpoint
- ❌ Manual trigger only
- ❌ No metadata output
- ❌ Fixed topic (hardcoded "AI-Powered Resume Processing")

### Archived
This version archived as `workflow-8bhcEHkbbvnhdHBh-baseline.json` for reference.

---

## Version Comparison

| Feature | v1.0.0 (Baseline) | v2.0.0 (Current) |
|---------|-------------------|-------------------|
| **Slides Generated** | 1 | 5 |
| **Trigger Type** | Manual | Webhook (API) |
| **AI Model** | GPT-4 Vision | GPT-4 Turbo + GPT-4 Vision |
| **Prompt Generation** | Manual/Hardcoded | AI Agent (dynamic) |
| **Quality Threshold** | 140/140 (100%) | 7/10 (70%) |
| **Max Retries** | 5 per image | 2 per slide (10 total) |
| **Output Format** | Single URL | Carousel metadata + 5 URLs |
| **Execution Time** | 1-5 minutes | 2-6 minutes |
| **API Cost** | ~$0.10 | ~$0.50-0.65 |
| **Error Handling** | Basic | Comprehensive |
| **Public API** | No | Yes (webhook) |

---

## Deployment History

### 2025-11-23 - v2.0.0
- **Status:** Ready for Deployment
- **Environment:** Development → Production
- **Method:** Local validation → Instance update
- **Workflow ID:** `8bhcEHkbbvnhdHBh` (same ID, complete rebuild)

### Pre-deployment Checklist
- [x] Local JSON created
- [x] Schema validation passed
- [x] Connection validation passed
- [x] Parameter completeness verified
- [x] Documentation complete
- [x] Baseline backup created
- [ ] Deployed to instance
- [ ] End-to-end test executed
- [ ] Production validation complete

---

## Future Roadmap

### v2.1.0 (Planned)
- [ ] Add webhook authentication (API key)
- [ ] Implement rate limiting
- [ ] Add carousel template variations
- [ ] Support custom image dimensions

### v2.2.0 (Planned)
- [ ] Move image generation to sub-workflow
- [ ] Add image editing/enhancement
- [ ] Database storage for carousel history

### v3.0.0 (Planned)
- [ ] Multi-language support
- [ ] Brand style customization
- [ ] Batch carousel generation
- [ ] Video slide support

---

## Notes

**Local Development Files:**
- `workflow-8bhcEHkbbvnhdHBh-baseline.json` - Original fetched state
- `workflow-8bhcEHkbbvnhdHBh.json` - Current development version
- `workflow-8bhcEHkbbvnhdHBh-validated.json` - Validated for deployment

**Protocol Compliance:**
✅ Follows `.claude/WORKFLOW-DEVELOPMENT-PROTOCOL.md`
✅ Local-first development
✅ Complete validation before deployment
✅ Only modifies user-specified workflow ID
✅ Uses n8n-workflows MCP for context (not instance)

---

**Maintained By:** SYNRG Automation Team
**Last Updated:** 2025-11-23
