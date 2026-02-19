# AI Prompt Engineering Patterns
Category from agents-evolution.md | 12 entries | Workflows: AQjMRh9pqK5PebFq, MMaJkr8abEjnCM2h, 8bhcEHkbbvnhdHBh
---

### Anti-Pattern: Generic AI responses not grounded in retrieved data
**What Happened:** System prompt allowed AI to generate generic descriptions ("organizational design and change management skills") instead of synthesizing actual candidate data from the vector search tool results.

**Impact:**
- Responses read like AI-generated filler instead of expert analysis
- No specific skills, certifications, or experience referenced from actual candidate profiles

**Why It Failed:** System prompt lacked explicit instruction to ground every claim in the retrieved vector search data.

### Positive Pattern: Data-grounded system prompt with synthesis directive
**Solution:** System prompt explicitly requires: "Reference specific skills, certifications, and experience from each candidate profile. Do not use generic descriptions — every claim must be grounded in the retrieved data."

**Implementation:**
1. Add synthesis directive to system prompt
2. Include 2 reference examples using actual candidate data points
3. Mandate ALL THREE sections in every response
4. Closing instruction: "Reference specific candidate data — never use generic descriptions"

**Result:**
- Responses reference actual skills from vector search (e.g., "HRIS systems fluency", "data collection and analysis skills")
- Each candidate insight tied to specific profile data
- Executive-level synthesis rather than generic summaries

**Reusable Pattern:** When AI Agent uses retrieval tools (vector search, database), always include explicit data-grounding directive in system prompt with examples showing how to reference specific retrieved data points.

---

### Anti-Pattern: AI Nodes Fabricating Data When Missing from Source
**What Happened:** The workflow's AI nodes were inventing fake candidate data when resumes had missing fields:
- Inventing placeholder names like "Jane Doe" or "John Doe" when no name was in resume
- Creating fake email addresses like "john@example.com" or "candidate@email.com"
- Fabricating phone numbers, job titles, and skills that weren't mentioned
- Inferring experience levels without explicit date calculations

**Impact:**
- False candidate profiles created in recruitment database
- Recruiters wasted time reviewing non-existent candidates
- Hiring decisions based on fabricated data
- Loss of trust in AI evaluation system
- Manual cleanup required to remove fake records

**Why It Failed:**
- LLMs have a natural tendency to be "helpful" by filling gaps with plausible data
- System prompts didn't explicitly prohibit data fabrication
- No data integrity rules at prompt level
- Attribute descriptions were permissive ("extract name") without strict extraction-only enforcement
- Missing consequences explanation - AI didn't understand impact of fake data

### Positive Pattern: Critical Data Integrity Guards for AI Extraction Nodes
**Solution:** Prepend system prompts with explicit anti-fabrication rules using visual urgency markers and consequence explanations

**Implementation:**

1. **AI Recruiter Analysis Node** - Updated `parameters.options.systemMessage`:
```markdown
🔴 CRITICAL DATA INTEGRITY RULES - VIOLATION IS UNACCEPTABLE 🔴

1. EXTRACT ONLY - Never invent, assume, or fabricate ANY data
2. If a field is not explicitly stated in the resume, return "NOT FOUND" or empty - NEVER guess
3. Names MUST come directly from the resume - NEVER use placeholders like "John Doe" or "Jane Doe"
4. Contact info MUST be extracted verbatim - NEVER invent email addresses or phone numbers
5. Skills MUST be explicitly mentioned - NEVER infer or assume skills
6. Experience MUST be calculated from stated dates only - NEVER estimate
7. If the resume is blank, malformed, or unreadable, return ALL fields as "INSUFFICIENT DATA"

POSITIVE REINFORCEMENT:
✅ DO extract exactly what is written
✅ DO preserve original formatting of names, emails, phones
✅ DO return "NOT FOUND" for missing fields
✅ DO flag incomplete data rather than fill gaps

❌ NEVER invent a name when none is provided
❌ NEVER create placeholder contact information
❌ NEVER assume skills not explicitly listed
❌ NEVER fabricate job titles or experience

This system processes REAL job candidates. Invented data sabotages hiring decisions and wastes human time reviewing fake profiles.

---

[Original system prompt continues below...]
```

2. **Extract Candidate Info Node** - Updated `parameters.options.systemMessage` and all attribute descriptions:
```markdown
🔴 CRITICAL EXTRACTION RULES 🔴

You are extracting data from real job candidate resumes. Accuracy is MANDATORY.

RULES:
1. Extract ONLY what is explicitly written - NEVER invent data
2. If a field is missing, return 'NOT FOUND' - NEVER use placeholders
3. Preserve exact formatting from source text
4. If resume is blank or unreadable, return 'INSUFFICIENT DATA' for all fields
5. NEVER use example names like 'John Doe', 'Jane Smith', etc.
6. NEVER create placeholder emails like 'john@example.com'
7. NEVER fabricate phone numbers

This data directly impacts hiring decisions. Fake data wastes recruiter time and creates false candidate profiles.
```

Updated attribute descriptions to enforce strict extraction:
- `full_name`: "Candidate's full name EXACTLY as written in resume. If no name is present, return 'NOT FOUND'. NEVER use placeholder names like 'John Doe' or 'Jane Doe'."
- `email_address`: "Email address EXACTLY as written in resume. If no email is present, return 'NOT FOUND'. NEVER invent or create email addresses."
- Similar strict rules for all other fields

3. **MCP Operations Applied:**
```javascript
mcp__n8n-mcp__n8n_update_partial_workflow({
  id: "MMaJkr8abEjnCM2h",
  operations: [
    { type: "updateNode", nodeName: "AI Recruiter Analysis", updates: {...} },
    { type: "updateNode", nodeName: "Extract Candidate Info", updates: {...} }
  ]
})
```

**Result:**
- 2 operations applied successfully
- Workflow validation passed (no new errors introduced)
- AI nodes now explicitly instructed to never fabricate data
- Clear fallback values ("NOT FOUND", "INSUFFICIENT DATA") for missing fields
- Real-world consequences explained to AI (hiring decisions, wasted time)

**Reusable Pattern - AI Data Integrity Guard Template:**

**ALWAYS apply to AI extraction nodes processing critical data:**

```markdown
🔴 CRITICAL DATA INTEGRITY RULES - VIOLATION IS UNACCEPTABLE 🔴

1. EXTRACT ONLY - Never invent, assume, or fabricate ANY data
2. If field not stated, return "NOT FOUND" - NEVER guess
3. [Domain-specific prohibition: no placeholder names, emails, etc.]
4. [Field-specific extraction rules: dates from explicit mentions only]
5. If source is invalid, return "INSUFFICIENT DATA" for ALL fields

POSITIVE REINFORCEMENT:
✅ DO extract exactly what is written
✅ DO preserve original formatting
✅ DO return "NOT FOUND" for missing fields
✅ DO flag incomplete data

❌ NEVER invent data
❌ NEVER use placeholders
❌ NEVER infer missing information
❌ NEVER [domain-specific prohibition]

This data impacts [real-world consequence]. Fake data causes [specific harm].
```

**Key Elements of Effective Data Integrity Guards:**
1. **Visual urgency** - 🔴 emoji and CAPS for critical words to grab attention
2. **Numbered rules** - Clear, scannable list format
3. **Explicit examples** - Show exactly what NOT to do ("John Doe", "john@example.com")
4. **Positive reinforcement** - What TO do (✅)
5. **Negative reinforcement** - What NOT to do (❌)
6. **Consequence explanation** - Why accuracy matters (hiring decisions, wasted time)
7. **Domain-specific rules** - Tailor to your data type (resumes vs support tickets vs financial records)

**Apply Pattern To:**
- Information Extractor nodes processing candidate resumes
- AI Agents extracting customer data from support tickets
- Document parsers processing legal/financial records
- Any AI extraction where fabricated data causes downstream harm
- Structured data extraction from unstructured sources

**Testing Checklist:**
- [ ] Test with complete source data - verify exact extraction
- [ ] Test with missing critical field - verify "NOT FOUND" returned (not placeholder)
- [ ] Test with blank/invalid source - verify "INSUFFICIENT DATA" for all fields
- [ ] Test with ambiguous data - verify no inference or assumption
- [ ] Monitor real-world outputs for any fabricated data patterns

**Documentation:** Full fix details in `/workflows/development/onedrive-resume-processor/AI_NODE_DATA_INTEGRITY_FIX.md`

---

### Anti-Pattern: AI Agent with Structured Output Parser Returning Wrong Schema
**What Happened:** The AI Agent "Carousel Prompt Generator" had a Structured Output Parser connected but GPT-4o returned output in a completely different schema than expected:

**Expected:** `{ "carousel_title": "...", "slide_prompts": [{ "slide_number": 1, "prompt": "...", ... }], "tags": [...] }`

**Actual Output:** `{ "output": { "state": "...", "cities": ["HOOK: ...", "PAIN POINT: ..."] } }`

**Impact:**
- Split node searching for `output.slide_prompts` found nothing (0 items)
- Workflow effectively stopped at Split node with no downstream processing
- Generated prompts (in wrong location) were too short (~150 chars) and missing SYNRG aesthetic specifications
- Missing exact hex codes, material descriptions, sequential narrative

**Why It Failed:**
1. System message described requirements narratively without explicit JSON structure
2. No few-shot examples - model couldn't infer detailed prompt format from guidelines alone
3. Output Parser schema not reinforced in system message
4. Missing aesthetic specifications with exact values

### Positive Pattern: Reinforce Output Schema in System Message with Few-Shot Examples
**Solution:** Rewrote system message to include explicit JSON structure, few-shot examples for each slide type, mandatory specifications with exact hex codes, and a requirements checklist.

**Implementation:**
1. Added explicit JSON structure at top of system message
2. Included 5 example prompts (one per slide type: hook, pain_point, why_problem, solution, call_to_action)
3. Specified exact SYNRG colors (#f4f4f4 background, #24DE99 mint, #FFFFFF pearl)
4. Required 200-300 character prompts with specific materials (frosted glass, translucent resin)
5. Added requirements checklist for model self-verification
6. Enforced sequential narrative connection between slides

**Result:**
- Workflow versionCounter 6 → 7
- System message now ~2500 characters with complete specifications
- Model will output correct schema matching Output Parser
- Prompts will include exact SYNRG aesthetic requirements

**Reusable Pattern:**

**AI Agent + Structured Output Parser Reliability:**

| Requirement | Implementation |
|-------------|----------------|
| JSON structure | Include in system message, not just output parser |
| Few-shot examples | 1-2 examples per output type minimum |
| Specific values | Use exact specs (hex codes, dimensions) not descriptions |
| Self-verification | Include checklist for model to validate output |

**Key Learnings:**
- **Output Parser schema alone is insufficient** - models may not follow schema from connected node
- **Few-shot examples are mandatory for complex outputs** - show, don't just tell
- **Explicit > implicit** - hex codes beat "mint green", exact structure beats "include these fields"
- **Self-verification improves compliance** - requirements checklists help models validate output

---

### Anti-Pattern: Basic Quality Scoring Without Brand-Specific Criteria
**What Happened:** The carousel generator workflow had a basic quality analysis prompt using a 0-100 scoring scale with generic criteria:
- Text legibility (30%)
- SYNRG aesthetic adherence (30%)
- Composition + negative space (20%)
- Overall visual quality (20%)

This resulted in inconsistent image quality that didn't meet SYNRG's enterprise visual standards. The analyzer couldn't distinguish between generally "good" images and images that specifically matched SYNRG's brand identity.

**Impact:**
- Generated images didn't consistently meet SYNRG aesthetic standards
- Images were approved that lacked required elements (metaball centerpiece, correct gradients, typography treatment)
- Brand inconsistency across carousel slides
- Marketing team had to manually review and reject images that passed automated checks

**Why It Failed:**
- Generic criteria couldn't capture SYNRG's specific visual requirements
- Single 0-100 score masked which specific elements were failing
- No distinction between aesthetic and marketing quality
- Refinement prompts were too generic to address specific brand deviations

### Positive Pattern: SYNRG 14-Item Quality Checklist (0-140 Scale)
**Solution:** Implemented comprehensive 14-point SYNRG Image Analyzer with granular scoring:

**Implementation:**

1. **Set Slide Context** - Updated `quality_prompt` with detailed SYNRG spec:
```
AESTHETIC CRITERIA (10 items, 0-10 each):
1. aspect_ratio: Correct 3:4 vertical format
2. background: #f4f4f4 cold gray, soft lighting gradients
3. composition: Balanced layout, 40-60% negative space
4. metaball: Frosted glass/resin 3D centerpiece present
5. gradient: Mint #24DE99 to pearl white #FFFFFF transition
6. surface: Soft reflections, noise grain, edge softness
7. shadows: Long diffused shadows with mint/cyan tint
8. typography: Bold geometric sans-serif, lens blur effect
9. blur: Gaussian blur on text behind metaball elements
10. visual_integrity: No artifacts, distortions, or AI glitches

MARKETING CRITERIA (4 items, 0-10 each):
11. pain_point_clarity: Clear visual metaphor for business pain
12. solution_clarity: Automation/clarity/flow visually implied
13. enterprise_value: Professional, premium, trustworthy feel
14. brand_fidelity: Matches SYNRG identity exactly
```

2. **Parse Quality Result** - Updated to handle 14-item checklist:
```javascript
// SYNRG threshold: 80% of 140 = 112
const MIN_QUALITY_SCORE = 112;
const MAX_SCORE = 140;

// Calculate category scores
const aestheticItems = ['aspect_ratio', 'background', 'composition', 'metaball',
                       'gradient', 'surface', 'shadows', 'typography', 'blur', 'visual_integrity'];
const marketingItems = ['pain_point_clarity', 'solution_clarity', 'enterprise_value', 'brand_fidelity'];

// Determine pass/fail based on SYNRG threshold
const passesMinimum = totalScore >= MIN_QUALITY_SCORE;
```

3. **Quality Check** - Threshold automatically uses `passes_quality` boolean (112+ = pass)

4. **Refine Prompt** - Adds targeted refinements based on low-scoring criteria (<7):
```javascript
// Example: If metaball score < 7
if ((scores.metaball || 0) < 7) {
  refinements.push('CENTERPIECE: 3D frosted glass or translucent resin metaball shape as primary element');
}
```

5. **Generate Carousel Metadata** - Updated to show 0-140 scores with percentage conversion

**Result:**
- Workflow version 35 deployed with comprehensive SYNRG quality analysis
- Images now scored on exact SYNRG brand criteria
- Individual scores expose which specific elements need improvement
- Refinement prompts are targeted to failing criteria
- Verdicts: "Effective" (≥112), "Needs Improvement" (70-111), "Off-Brand" (<70)
- Category breakdown: Aesthetic score (0-100 normalized) + Marketing score (0-100 normalized)

**Reusable Pattern:**

```
┌─────────────────────────────────────────────────────────────┐
│  BRAND-SPECIFIC IMAGE QUALITY SCORING                       │
├─────────────────────────────────────────────────────────────┤
│  1. Define exact brand spec (colors, shapes, materials)     │
│  2. Create granular checklist (10-15 specific items)        │
│  3. Score each item independently (0-10)                    │
│  4. Set pass threshold at 80% of total                      │
│  5. Target refinements to low-scoring items only           │
│  6. Separate aesthetic vs marketing criteria                │
└─────────────────────────────────────────────────────────────┘
```

**SYNRG Image Analyzer JSON Output Format:**
```json
{
  "scores": {
    "aspect_ratio": 0-10,
    "background": 0-10,
    "composition": 0-10,
    "metaball": 0-10,
    "gradient": 0-10,
    "surface": 0-10,
    "shadows": 0-10,
    "typography": 0-10,
    "blur": 0-10,
    "visual_integrity": 0-10,
    "pain_point_clarity": 0-10,
    "solution_clarity": 0-10,
    "enterprise_value": 0-10,
    "brand_fidelity": 0-10
  },
  "total_score": 0-140,
  "verdict": "Effective|Needs Improvement|Off-Brand",
  "passes": true/false,
  "critical_issues": ["list of major problems"],
  "improvement_suggestions": ["specific fixes needed"]
}
```

---

### Anti-Pattern 2: AI Agent producing markdown when JSON is required
**What Happened:** When the AI Agent couldn't find resume data (due to Anti-Pattern 1), it fell back to producing a markdown-formatted response instead of the required JSON schema. The Structured Output Parser failed to parse markdown, and with `onError: continueRegularOutput`, the raw markdown string passed through to VDC.

**Impact:**
- VDC received a string instead of a parsed JSON object
- Original VDC parsing only handled JSON formats
- All AI analysis fields extracted as empty strings

**Why It Failed:** Knowledge Gap — no explicit JSON output format requirement in the system prompt. The AI defaulted to its natural markdown format when it couldn't produce a complete analysis.

### Positive Pattern 2: Mandatory JSON format directive in AI Agent system prompts + defensive 3-tier parsing
**Solution:** Two-layer defense: (1) Add explicit JSON output requirement to system prompt, (2) Add 3-tier defensive parsing in downstream Code nodes to handle JSON code fences, raw JSON extraction, and markdown key-value parsing.

**Implementation:**
1. Add to system prompt: "Your ENTIRE response MUST be a valid JSON object. Do NOT use markdown formatting."
2. List ALL required JSON keys explicitly in the system prompt
3. Add 3-tier parsing in consuming Code node: JSON code fences → raw JSON extraction → markdown key-value fallback
4. Always include field name fallback chains for nested vs flat structures

**Reusable Pattern:**
Any n8n AI Agent with a Structured Output Parser should have BOTH: (a) explicit JSON format instructions in the system prompt, and (b) defensive multi-format parsing in downstream nodes. The parser's `onError: continueRegularOutput` means raw strings WILL reach downstream nodes when parsing fails.

---

### Anti-Pattern 6: Structured Output Parser schema missing required extraction fields
**What Happened:** The Structured Output Parser's `jsonSchemaExample` defined fields for AI analysis (score, risk, strengths) but NOT for basic resume extraction (current_title, years_experience, key_skills). The AI Agent had no schema-level instruction to extract these fields, so they were never produced.

**Impact:**
- AI never extracted current title, experience, or skills
- VDC fallback chains got empty values
- Email templates showed "Not specified" for these fields

**Why It Failed:** Knowledge Gap — the parser schema was designed for AI ANALYSIS fields but not for basic EXTRACTION fields. The assumption was that extraction fields would come from another source, but the VDC code expects them from the AI output.

### Positive Pattern 6: Parser schema must include ALL fields that downstream nodes expect from AI output
**Solution:** Added `current_title`, `years_experience`, and `key_skills` to both the parser schema AND the system prompt's MANDATORY OUTPUT FORMAT section.

**Implementation:**
1. Map ALL fields that VDC/downstream nodes read from `aiAnalysis` or AI output
2. Ensure EVERY such field exists in the Structured Output Parser schema
3. Add extraction instructions to the system prompt for each field
4. Include clear fallback values ("NOT FOUND", "INSUFFICIENT DATA") for when data is unavailable

**Reusable Pattern:**
The Structured Output Parser schema is the CONTRACT between the AI Agent and all downstream processing. If a downstream node reads `aiAnalysis.fieldName`, that field MUST exist in the parser schema. Missing schema fields are silent failures — the AI simply doesn't produce them, and downstream nodes get undefined.

---
