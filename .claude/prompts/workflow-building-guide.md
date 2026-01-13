# N8N Workflow Building - Prompting Guide

**Purpose:** Guidelines for effectively prompting Claude to build, optimize, and maintain n8n workflows.

---

## Effective Prompting Principles

### 1. Be Specific About Requirements

**❌ Vague:**
"Build a workflow to process data"

**✅ Specific:**
"Build a workflow that:
- Receives webhook POST with JSON containing resume text
- Extracts candidate name, email, skills from JSON
- Sends resume text to OpenAI for scoring (0-100)
- Stores result in PostgreSQL table 'candidates'
- Returns JSON response with score and recommendation"

**Why it works:** Specific requirements allow Claude to select appropriate nodes and structure workflow correctly.

---

### 2. Specify Input/Output Data Structures

**❌ Generic:**
"Process user data and send to API"

**✅ With data structure:**
"Process user data with this structure:
```json
{
  "user": {
    "email": "user@example.com",
    "name": "John Doe",
    "company": "Acme Inc"
  },
  "action": "signup"
}
```
Transform to API format:
```json
{
  "email": "user@example.com",
  "full_name": "John Doe",
  "organization": "Acme Inc",
  "event_type": "user.signup"
}
```"

**Why it works:** Claude can create exact transformations using Set nodes instead of guessing.

---

### 3. Mention Error Scenarios

**❌ Happy path only:**
"Call the API and process the response"

**✅ Include error handling:**
"Call the API and process the response. Handle these errors:
- 401/403: Invalid API key → notify Slack channel #alerts
- 429: Rate limited → retry 3 times with exponential backoff
- 500: Server error → log to database and send email to ops@company.com
- Timeout: Retry once, then fail gracefully with error response"

**Why it works:** Claude includes error branches and retry logic from the start.

---

### 4. Specify Performance Requirements

**❌ No performance context:**
"Build workflow to generate images"

**✅ With performance requirements:**
"Build workflow to generate 5 carousel images. Requirements:
- Must complete in < 15 seconds total
- API calls should be parallelized if possible
- Expected volume: 50-100 generations per day
- Response must be returned to webhook caller immediately"

**Why it works:** Claude uses Split-Merge for parallelization and considers timeout limits.

---

### 5. Indicate Workflow Complexity

**❌ No complexity guidance:**
"Create workflow for customer onboarding"

**✅ With scope defined:**
"Create workflow for customer onboarding - this is a COMPLEX workflow that will:
- Handle 15+ steps from signup to activation
- Integrate with 5 external services
- Branch based on customer type (free/paid/enterprise)
- Run sub-workflows for different onboarding tracks

Consider breaking into:
- Main orchestration workflow
- Sub-workflows for each customer type
- Library workflows for common operations (send email, create records)"

**Why it works:** Claude structures workflow modularly instead of creating a monolith.

---

## Prompt Templates

### Template 1: New Workflow from Scratch

```
Build a new n8n workflow:

**Purpose:** {one-sentence description}

**Trigger:** {Webhook / Schedule / Manual / Other}

**Input Data:**
```json
{example input structure}
```

**Processing Steps:**
1. {step 1}
2. {step 2}
3. {step 3}

**Expected Output:**
```json
{example output structure}
```

**External Services:**
- {Service 1}: {purpose}
- {Service 2}: {purpose}

**Error Handling:**
- {Error scenario 1}: {how to handle}
- {Error scenario 2}: {how to handle}

**Performance:**
- Expected volume: {number} executions per {timeframe}
- Timeout requirements: {if any}

**Workflow Type:** {production / development / library / template}
```

### Template 2: Optimize Existing Workflow

```
Optimize the workflow: {workflow-name}

**Current Issues:**
- {Issue 1} - {impact}
- {Issue 2} - {impact}

**Optimization Goals:**
1. {Goal 1} - e.g., Reduce execution time from 30s to <10s
2. {Goal 2} - e.g., Replace Code nodes with native nodes
3. {Goal 3} - e.g., Add error handling for API failures

**Constraints:**
- {Constraint 1} - e.g., Must maintain backward compatibility with webhook callers
- {Constraint 2} - e.g., Cannot change database schema

**Current Execution Stats:**
- Average execution time: {duration}
- Success rate: {percentage}
- Error rate: {percentage}
- Most common error: {error type}

Please analyze and suggest optimizations using native n8n nodes where possible.
```

### Template 3: Debug Workflow Issue

```
Debug workflow execution failure:

**Workflow:** {workflow-name}
**Execution ID:** {if known}

**Error Symptoms:**
- {What's happening}
- {Error message if available}
- {When it started happening}

**Recent Changes:**
- {Change 1}
- {Change 2}

**Input Data that Failed:**
```json
{example of failing input}
```

**Input Data that Succeeded:**
```json
{example of successful input - if available}
```

**Expected Behavior:**
{What should happen}

**Actual Behavior:**
{What's actually happening}

Please analyze the issue and provide specific fix recommendations.
```

### Template 4: Add Feature to Existing Workflow

```
Add feature to workflow: {workflow-name}

**New Feature:**
{Description of what to add}

**Integration Point:**
{Where in existing workflow this should happen}

**Current Workflow Structure:**
{Brief description or list of main nodes}

**New Feature Requirements:**
- Input: {data structure}
- Processing: {what needs to happen}
- Output: {expected result}

**Impact Considerations:**
- Should not break existing functionality
- {Other considerations}

Please suggest where to integrate this and what nodes to add.
```

### Template 5: Convert Code Node to Native Nodes

```
Replace Code node with native n8n nodes:

**Workflow:** {workflow-name}
**Node Name:** {code node name}

**Current Code:**
```javascript
{paste code from Code node}
```

**What the code does:**
{Explain the logic}

**Input Data:**
```json
{example input to code node}
```

**Expected Output:**
```json
{example output from code node}
```

Please suggest native n8n nodes (Set, IF, Switch, etc.) that can replace this code.
```

---

## Prompt Patterns for Common Tasks

### Pattern: API Integration

```
Integrate {API name} API:

**API Documentation:** {URL or key details}
**Authentication:** {API key / OAuth / Basic Auth}
**Endpoint:** {URL}
**Method:** {GET / POST / PUT / DELETE}

**Request:**
- Headers: {required headers}
- Body: {request body structure}

**Response:**
- Success (200): {response structure}
- Error (4xx/5xx): {error structure}

**Use Case:**
{What you're using the API for}

**Error Handling:**
- Rate limits: {how to handle}
- Retries: {retry strategy}
```

### Pattern: Data Transformation

```
Transform data structure:

**From:**
```json
{source structure}
```

**To:**
```json
{target structure}
```

**Transformation Rules:**
1. {field mapping rule}
2. {calculation rule}
3. {conditional logic}

**Edge Cases:**
- Missing fields: {how to handle}
- Null values: {default values}
- Array handling: {map/filter/reduce logic}

Prefer Set node with expressions over Code node.
```

### Pattern: Workflow Orchestration

```
Build orchestration workflow:

**Main Process:**
{High-level description of business process}

**Sub-Processes:**
1. {Sub-process 1} - {trigger condition}
2. {Sub-process 2} - {trigger condition}
3. {Sub-process 3} - {trigger condition}

**Branching Logic:**
- If {condition}: Execute sub-process A
- Else if {condition}: Execute sub-process B
- Else: Execute sub-process C

**Data Flow:**
{How data flows between sub-processes}

**Error Strategy:**
{How errors in sub-processes should be handled}

Use Execute Workflow nodes for modularity.
```

---

## MCP Tool Usage in Prompts

### Explicit Tool Guidance

**When you want Claude to use specific MCP tools:**

```
Build a workflow for {purpose}.

Before building:
1. Search for similar templates using search_templates
2. Check if relevant nodes exist using search_nodes
3. Get documentation for {specific node} if needed

Then create the workflow using n8n_create_workflow.

After creation:
- Validate using n8n_validate_workflow
- Apply auto-fixes if validation finds issues
- Test by triggering with sample data
```

### Template Discovery

```
I need a workflow that {description}.

First, search n8n templates for similar workflows:
- Keywords: {relevant keywords}
- Show top 3 most relevant templates

If a good template exists, use it as a starting point.
If not, build from scratch.
```

### Node Discovery

```
I need to {task description}.

Search for n8n nodes that can handle:
- {Capability 1}
- {Capability 2}
- {Capability 3}

Prefer native nodes. Check AI tools list if AI processing is needed.
Show me the top 3 most relevant nodes before building.
```

---

## Anti-Patterns to Avoid

### ❌ Anti-Pattern: Assuming Claude Knows Your Data

**Bad:**
"Process the customer data"

**Why:** Claude doesn't know your data structure

**Good:**
"Process customer data with this structure: {JSON example}"

---

### ❌ Anti-Pattern: No Error Handling Mentioned

**Bad:**
"Call the API and save to database"

**Why:** Claude might not add error handling

**Good:**
"Call the API and save to database. Add error handling for API failures and database constraint violations."

---

### ❌ Anti-Pattern: Vague Performance Requirements

**Bad:**
"Make it fast"

**Why:** "Fast" is subjective

**Good:**
"Optimize to complete in under 5 seconds for 90% of executions"

---

### ❌ Anti-Pattern: No Context on Existing System

**Bad:**
"Add user creation to the workflow"

**Why:** Claude doesn't know existing workflow structure

**Good:**
"Add user creation after the 'Validate Input' node in the existing workflow. Current workflow has: Webhook → Validate → Process → Respond."

---

### ❌ Anti-Pattern: Missing Workflow Type

**Bad:**
"Build a workflow"

**Why:** Production workflows need different rigor than dev/test

**Good:**
"Build a PRODUCTION workflow (needs error handling, monitoring, proper naming)"

---

## Progressive Refinement Pattern

**Start broad, then refine:**

**Round 1:**
"I need a workflow to process resumes"

**Claude responds with clarifying questions**

**Round 2:**
"Process resumes received via webhook, extract skills using AI, score against job description, save to database"

**Claude provides workflow structure proposal**

**Round 3:**
"Looks good, but add:
- Retry logic for AI API (3 attempts)
- Email notification on processing failure
- Use PostgreSQL instead of MySQL"

**Claude refines the workflow**

**Why it works:** Iterative refinement allows you to start simple and add complexity.

---

## Validation Prompts

After Claude builds a workflow, validate:

```
Review the workflow you just built:

1. Does it follow naming conventions? (prod-/dev-/lib-/template-)
2. Are all API calls using native HTTP Request nodes?
3. Is error handling present on all external calls?
4. Are credentials using n8n credential system (not hardcoded)?
5. Is the workflow structure modular (sub-workflows if >20 nodes)?

Validate the workflow and suggest any improvements.
```

---

## Documentation Prompts

Request documentation:

```
Document this workflow:

Create a README that includes:
1. Purpose and business logic
2. Input/output data structures
3. Required credentials (with setup instructions)
4. Error scenarios and handling
5. Testing instructions
6. Monitoring/observability setup

Save to workflows/{category}/{workflow-name}/README.md
```

---

## Evolution Log Prompts

After solving a problem:

```
I just fixed {issue} in {workflow-name}.

The problem was: {anti-pattern description}
The solution was: {positive pattern description}
The result: {measurable improvement}

Document this in agents-evolution.md using the pattern template.
```

---

## Examples of Great Prompts

### Example 1: Complete Workflow Spec

```
Build a workflow: prod-marketing-carousel-generator

**Trigger:** Webhook POST to /api/generate-carousel

**Input:**
```json
{
  "topic": "AI in healthcare",
  "slides": 5,
  "style": "professional",
  "brand_colors": ["#FF6B6B", "#4ECDC4"]
}
```

**Processing:**
1. Generate text for each slide using Anthropic Claude
   - Prompt: "Create {slides} carousel slides about {topic} in {style} style"
   - Each slide: title (max 60 chars) + body (max 150 chars)

2. Generate images for each slide in PARALLEL
   - Use OpenAI DALL-E 3
   - Prompt: "Professional illustration for: {slide.title}, colors: {brand_colors}"
   - Size: 1024x1024

3. Combine text + images
   - Create carousel JSON structure
   - Include image URLs and text

**Output:**
```json
{
  "carousel_id": "uuid",
  "slides": [
    {
      "title": "...",
      "body": "...",
      "image_url": "..."
    }
  ],
  "created_at": "iso-timestamp"
}
```

**Error Handling:**
- Anthropic API failure: Retry 3x, then return error response
- DALL-E rate limit (429): Exponential backoff, max 5 attempts
- Invalid input: Return 400 with validation errors

**Performance:**
- MUST complete in < 30 seconds (Anthropic ~3s, images parallel ~10s)
- Expected load: 20-50 requests/day

**Credentials Needed:**
- Anthropic API key
- OpenAI API key

**Workflow Type:** Production

Build this using native n8n nodes. Use Split-Merge for parallel image generation.
```

### Example 2: Optimization Request

```
Optimize: prod-hr-resume-review

**Current Performance:**
- Execution time: 45 seconds average
- Bottleneck: Sequential API calls to resume parser (20s), AI analysis (15s), database save (5s)

**Goal:** Reduce to < 15 seconds

**Current Structure:**
Webhook → Parse Resume (HTTP) → Extract Text (Code) → AI Analysis (OpenAI) → Save (PostgreSQL) → Respond

**Issues I've Identified:**
1. Code node "Extract Text" does simple field extraction
2. AI Analysis waits for parse to complete (could start sooner)
3. No caching (same resume analyzed multiple times)

**Constraints:**
- Cannot change input/output contract (webhook format must stay same)
- Must continue using PostgreSQL (company standard)

Please analyze and propose optimizations. Prioritize native nodes over code.
```

---

## Quick Reference: Prompt Checklist

When asking Claude to build/modify a workflow, include:

- [ ] Workflow purpose (one sentence)
- [ ] Trigger type (webhook/schedule/manual)
- [ ] Input data structure (JSON example)
- [ ] Output data structure (JSON example)
- [ ] Processing steps (numbered list)
- [ ] External services (APIs, databases)
- [ ] Error scenarios and handling
- [ ] Performance requirements
- [ ] Workflow type (prod/dev/lib)
- [ ] Credentials needed

**The more specific your prompt, the better the workflow Claude will build.**

---

**Version:** 1.0.0
**Last Updated:** 2025-11-22
