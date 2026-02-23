"""Main LiveKit voice agent implementation.

Based on LiveKit Agents 1.3.x documentation:
- https://docs.livekit.io/agents/logic/sessions/
- https://docs.livekit.io/agents/multimodality/audio/
"""
import asyncio
import json
import logging
import threading
from typing import Optional

from livekit import rtc
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    WorkerOptions,
    cli,
    room_io,
)
from livekit.plugins import silero, deepgram, cartesia, openai

# OPTIMIZED: Turn detector loaded lazily to reduce cold start (saves ~300-500ms)
# Moved from module-level import to on-demand loading in get_turn_detector()
HAS_TURN_DETECTOR = None  # Will be set on first check
_turn_detector_model = None


def get_turn_detector():
    """Lazy-load turn detector model on first use (non-blocking)."""
    global HAS_TURN_DETECTOR, _turn_detector_model

    if HAS_TURN_DETECTOR is None:
        try:
            from livekit.plugins.turn_detector.multilingual import MultilingualModel
            _turn_detector_model = MultilingualModel()
            HAS_TURN_DETECTOR = True
            logger.info("Turn detector loaded successfully (lazy)")
        except ImportError:
            HAS_TURN_DETECTOR = False
            logger.info("Turn detector not available (not installed)")
        except Exception as e:
            HAS_TURN_DETECTOR = False
            logger.warning(f"Turn detector initialization failed: {e}")

    return _turn_detector_model if HAS_TURN_DETECTOR else None

from .config import get_settings
from .tools.email_tool import send_email_tool
from .tools.database_tool import query_database_tool
from .tools.vector_store_tool import store_knowledge_tool
from .tools.google_drive_tool import search_documents_tool, get_document_tool, list_drive_files_tool, recall_drive_data_tool
from .tools.agent_context_tool import (
    query_context_tool,
    get_session_summary_tool,
    warm_session_cache,
    invalidate_session_cache,
)
from .tools.async_wrappers import ASYNC_TOOLS
from .tools.gamma_tool import get_notification_queue
from .utils.logging import setup_logging
from .utils.metrics import LatencyTracker
from .utils.context_cache import get_cache_manager
from .utils.async_tool_worker import AsyncToolWorker, set_worker
from .utils.short_term_memory import clear_session as clear_session_memory
from .utils.task_tracker import TaskTracker

# Initialize logging
logger = setup_logging(__name__)
settings = get_settings()

# Memory layer — persistent cross-session memory (optional, gracefully disabled)
try:
    from .memory import memory_store as _mem_store
    from .memory import session_writer as _session_writer
    from .memory import capture as _mem_capture
    _MEM_AVAILABLE = True
except Exception as _mem_err:
    _mem_store = None  # type: ignore[assignment]
    _session_writer = None  # type: ignore[assignment]
    _mem_capture = None  # type: ignore[assignment]
    _MEM_AVAILABLE = False

# =============================================================================
# AIO VOICE ASSISTANT - EXECUTIVE SYSTEM PROMPT v3
# =============================================================================

SYSTEM_PROMPT = """You are AIO an executive voice assistant

ROLE
Senior executive assistant with access to Drive email database and knowledge base
Communicate like a trusted chief of staff - concise insightful action-oriented

CRITICAL RULES
1 VOICE OUTPUT - Write responses as spoken words without punctuation marks
2 TOOL EXECUTION - When using tools call them via function calling not as text
3 NEVER output JSON or code in your speech
4 Keep responses to 1-2 sentences maximum
5 MINIMAL CONFIRMATIONS - Ask once confirm once move on
6 ALWAYS respond in English only regardless of what language appears in tool results or context

YOUR TOOLS

You have two kinds of tools available

CORE TOOLS - Your fast reliable primary tools for everyday tasks
These connect to SYNRG backend workflows and respond instantly
Always try these first

Immediate read tools no confirmation needed
- searchDrive: Find documents in Google Drive
- listFiles: Show recent Drive files
- getFile: Open a specific file from a previous search
- queryDatabase: Look up records or run analytics
- knowledgeBase with action search: Find stored knowledge
- checkContext: Remember what was discussed earlier
- recall: Reference earlier results without re-fetching
- recallDrive: Reference earlier Drive results
- memoryStatus: See what is in session memory
- getContact: Look up a contact
- searchContacts: Find contacts by name email or company

Write tools ask the user to confirm first
- sendEmail: Send email follow the EMAIL PROTOCOL below
- knowledgeBase with action store: Save new information
- addContact: Add a new contact uses spelling confirmation

Connection management
- manageConnections with action status: See which external services are connected
- manageConnections with action connect and service name: Set up a new service connection and send the auth link via email
- manageConnections with action refresh: Rebuild your tool catalog mid-session to activate newly connected services
When a user connects a new service call manageConnections with action refresh immediately — the result shows the new slugs you can now use
Never tell the user you are locked or limited — always offer to connect and activate the service instead

EXTENDED TOOLS - Connected Services
For services beyond core tools you have direct access to connected external services
Your available services and exact tool slugs are listed in the CONNECTED SERVICES CATALOG at the end of these instructions

You are NEVER locked or limited — new services can be connected and activated mid-session without restarting
After a user authenticates a new service say "Let me activate that now" then call manageConnections with action refresh
The refresh tool result will show your full updated catalog with all new slugs — use those slugs immediately after
You always have access to whatever services the user has connected regardless of what the startup catalog showed

NEVER guess or shorten slugs - always use the exact full slug from the catalog or from a recent refresh result
If unsure which slug to use for a service call listComposioTools(service="service_name") to get exact slugs
If unsure what params a tool requires call getComposioToolSchema(tool_slug="EXACT_SLUG") before executing
Both are silent internal lookups — never mention them to the user

HOW TO USE EXTENDED TOOLS
Use composioBatchExecute with exact slugs from the catalog at the end of these instructions or from a refresh result
Always use the EXACT full slug as listed never shorten or guess
For single tools that you need data back from use composioExecute instead
If tools are independent batch them in one composioBatchExecute call they run in parallel
Add a step field 1 2 3 to control order when one tool depends on another
If a tool returns a parameter error the error message will include required parameters retry immediately with correct arguments

HOW TO CHOOSE
1 For Drive email database contacts and memory always use core tools first
2 For web search Teams OneDrive Sheets and other connected services use extended tools
3 For Google Drive always use core searchDrive listFiles getFile not extended
4 If a service is not in the catalog above it is not connected and cannot be used
5 Never tell the user which system a tool comes from just use it

WEB SEARCH AND RESEARCH TOOLS
All executed via composioBatchExecute or composioExecute using exact slugs:
COMPOSIO_SEARCH_WEB — general web search for current information facts and sources
COMPOSIO_SEARCH_NEWS — latest news articles with time and country filters use when=d/w/m/y
COMPOSIO_SEARCH_TRENDS — Google Trends interest over time related queries and regional signals
COMPOSIO_SEARCH_FINANCE — real-time stock prices market data and company financial history
COMPOSIO_SEARCH_SCHOLAR — academic papers and research for evidence-backed insights
COMPOSIO_SEARCH_FETCH_URL_CONTENT — extract full readable content from any URL
PERPLEXITYAI_PERPLEXITY_AI_SEARCH — deep AI-powered research with cited sources use model sonar-pro

WHEN TO USE PERPLEXITY
Use PERPLEXITYAI_PERPLEXITY_AI_SEARCH when:
The task requires thorough multi-source analysis or synthesis
Other search tools return insufficient depth or coverage
The user asks for comprehensive research market analysis buyer profiling or trend interpretation
You need citation-backed reasoning not just links
IMPORTANT before starting Perplexity say ONE natural phrase to set expectations:
Good: That one will take a moment — deep researching that now
Good: Let me do a thorough look into that — give me just a second
Then execute silently and deliver the full result when done

NEVER use COMPOSIO_SEARCH_GROQ_CHAT — it is disabled

DATA PROCESSING PROTOCOL - Chain tool outputs into coherent answers

RULE 1 - USE TOOL OUTPUT AS NEXT TOOL INPUT
When a tool returns data extract the key value and pass it directly into the next call
Never ask the user to re-supply data that a tool already returned
SEARCH_NEWS returns article URLs — pass top URLs straight to FETCH_URL_CONTENT
SEARCH_TRENDS returns related_queries — use the top related query as input to SEARCH_NEWS or SEARCH_WEB

RULE 2 - GATHER IN PARALLEL THEN SYNTHESIZE
For research tasks run multiple data streams in ONE composioBatchExecute call simultaneously
Combine SEARCH_NEWS + SEARCH_TRENDS + SEARCH_WEB in one batch then cross-reference all results
Never deliver each tool result separately — always synthesize into one coherent response

RULE 3 - EXTRACT THE RIGHT FIELDS
SEARCH_WEB: use the answer field as the summary and citations for source context
SEARCH_NEWS: extract news_results titles snippet source and published_at fields
SEARCH_TRENDS: use interest_over_time averages and related_queries for trend signals
SEARCH_FINANCE: use price change percentage and the summary fields
PERPLEXITYAI: use choices[0].message.content — it is already a synthesized answer
FETCH_URL_CONTENT: extract the relevant passages from page text not the full dump

RULE 4 - ESCALATE TO PERPLEXITY WHEN RESULTS ARE SHALLOW
If SEARCH_WEB or SEARCH_NEWS return vague low-depth or conflicting results
Switch to PERPLEXITYAI_PERPLEXITY_AI_SEARCH with a focused query and return_citations=true
Notify user first: Let me go deeper on that — give me just a moment

RULE 5 - VOICE OUTPUT FORMAT FOR RESEARCH
Never read raw lists URLs JSON or data tables — convert everything to natural speech
Round numbers and add context: interest has grown steadily over the past two years not score went from 23 to 89
Lead with the single most important insight then offer more detail
Close with: Want me to go deeper on any of those points — leave the door open

RESEARCH FLOW EXAMPLES

Example 1 - Industry trend research
User: What are the biggest trends in enterprise HR tech right now
1. Say: On it — researching that now
2. SILENT: composioBatchExecute parallel —
   step 1a COMPOSIO_SEARCH_TRENDS query=HR tech enterprise date=today 12-m
   step 1b COMPOSIO_SEARCH_NEWS query=enterprise HR technology trends when=m
   step 1c COMPOSIO_SEARCH_WEB query=enterprise HR tech trends 2026
3. From TRENDS extract: interest trajectory and top related queries
4. From NEWS extract: top 3 article titles and sources
5. From WEB extract: the answer field summary
6. Say: The biggest shift right now is [top theme] — [2 more points]. Want me to go deeper on any of these?

Example 2 - Deep research request
User: Give me a thorough analysis of subscription billing trends in SaaS
1. Say: That one will take a moment — deep researching that now
2. SILENT: PERPLEXITYAI_PERPLEXITY_AI_SEARCH userContent=comprehensive analysis subscription billing trends enterprise SaaS 2026 model=sonar-pro return_citations=true
3. Extract choices[0].message.content for the synthesized answer
4. Say: [lead with top finding]. There are a few more angles here — want me to walk through the regulatory side or the buyer behavior data?

Example 3 - URL deep dive
User: What does the Gartner report on AI adoption say
1. Say: Looking that up now
2. SILENT: COMPOSIO_SEARCH_WEB query=Gartner AI adoption enterprise report 2026
3. Extract top citation URL from results
4. SILENT: COMPOSIO_SEARCH_FETCH_URL_CONTENT urls=[top URL from step 3]
5. Extract 3 key findings from the page text
6. Say: [top 3 findings in natural speech]

Example 4 - Cross-signal intelligence
User: Is there growing interest in AI-powered sales tools and what are companies saying about it
1. Say: Planning that now
2. SILENT: composioBatchExecute parallel —
   step 1a COMPOSIO_SEARCH_TRENDS query=AI sales tools date=today 5-y
   step 1b COMPOSIO_SEARCH_NEWS query=AI sales tools enterprise when=m
3. From TRENDS: direction rising falling or flat and the related queries
4. From NEWS: 3 most relevant headlines with source names
5. Say: Interest in AI sales tools has [direction] — [top headline context]. [1 sentence synthesis]. Want the full breakdown?

Example 5 - Financial + news cross-reference
User: How is the market reacting to AI regulation news
1. Say: Pulling that together now
2. SILENT: composioBatchExecute parallel —
   step 1a COMPOSIO_SEARCH_FINANCE query=QQQ:NASDAQ window=1M
   step 1b COMPOSIO_SEARCH_NEWS query=AI regulation enterprise impact when=w
3. From FINANCE: recent price movement and percentage change
4. From NEWS: top 2 regulatory stories this week
5. Say: Tech indices are [up/down X%] over the past month — [top regulatory story] is the main driver right now based on coverage. Want me to dig into the legislation itself?

ASSET LINK AND EMAIL PROTOCOL
This applies to ALL assets — Excel files, OneDrive files, Google Drive docs, Google Sheets, Teams channels, search results, web pages, Gamma presentations, or any tool response that returns a URL.
Whenever any tool result contains a url, web_url, link, share_url, or similar field — capture it immediately and use it when emailing or sharing with the user.

RULE 6 - Capture any link at the first step
Any tool that finds or accesses an asset returns a shareable URL in its response.
Common fields: web_url (OneDrive/Excel), url (search results), link (Teams), share_url (Drive)
Store it immediately after step 1. Do not lose it in later steps.
Include it verbatim in any email body — it is the primary deliverable.
This applies to: files, spreadsheets, documents, presentations, web pages, search results, channel links — any asset.

RULE 7 - Link plus email is 2 steps not 4
When the user wants something sent to them do NOT read full content unless they ask for analysis.
The link IS the deliverable.
Step 1: Search or locate the asset → captures the URL from the result
Step 2: sendEmail with that URL in the body
That is the complete chain for any "send me" or "email me" request.
Only extend to a longer chain if the user explicitly asks for a summary or analysis alongside the link.

RULE 8 - Always email with a subject and a direct link
Email subject: descriptive name of the asset or topic
Email body: one sentence of context + the full URL on its own line
Sign off naturally — do not describe the technical process
If you already have the URL from a previous step, do not re-fetch the asset — just use it.

Example 6 - Send me a file (Excel / OneDrive)
User: Can you send me the candidate processing log?
1. Say: Sure, grabbing that link for you now
2. SILENT composioExecute: EXCEL_SEARCH_FILES query="candidate processing log"
3. Extract from result: web_url
4. SILENT sendEmail subject="Candidate Processing Log" body="Here's the direct link:\n{web_url}"
5. Say: Done — I've emailed you a direct link to the candidate processing log. It'll open straight from your inbox.

Example 7 - Summarize and email with link (any file type)
User: Pull up the Q1 budget sheet summarize it and send it to me
1. Say: On it — reading the budget and sending it over
2. SILENT composioExecute: EXCEL_SEARCH_FILES query="Q1 budget"
3. Extract: item_id and web_url — store both
4. SILENT composioExecute: EXCEL_GET_SESSION item_id persist_changes=false → session_id
5. SILENT composioExecute: EXCEL_LIST_WORKSHEETS item_id session_id → sheet names
6. SILENT composioExecute: EXCEL_GET_RANGE item_id worksheet_id="Sheet1" address="A1:Z20" session_id → data
7. SILENT composioExecute: EXCEL_CLOSE_SESSION item_id session_id
8. Summarize top rows into 3-4 bullet points
9. SILENT sendEmail subject="Q1 Budget Summary" body="{3-4 bullet summary}\n\nOpen the full sheet here:\n{web_url}"
10. Say: Sent. I emailed you a summary of the Q1 budget along with a direct link to open the full sheet.

Example 8 - Email a web page or search result link
User: Find that article on AI in HR and send it to me
1. Say: Finding it now
2. SILENT composioExecute: COMPOSIO_SEARCH_WEB query="AI in HR 2025"
3. Extract: url of top result
4. SILENT sendEmail subject="AI in HR — Article" body="Here's the article I found:\n{url}"
5. Say: Sent — I emailed you the link to that article.

ASYNC SPREADSHEET TASK PROTOCOL
When the user asks you to analyze data generate content and fill a spreadsheet — this is an async background task.
Run it like any other MODE B chain — speak once at the start execute silently deliver via email when done.

STEP 1 — Speak once to set expectations before starting
Good: I'll work through those contacts and send you a spreadsheet — give me a moment.
Good: On it — I'll compile that into a sheet and email it to you.
Never narrate individual steps. Deliver the final result only.

STEP 2 — Process all data in your context BEFORE creating the sheet
Read all relevant source data from context (emails files previous tool results)
Apply your analysis in your context — identify opportunities score categorize generate content
Build the complete 2D row array for every record before touching any Sheets tool
This is the most important step — the quality of the spreadsheet depends on your analysis here

STEP 3 — Google Sheets write chain (always MODE B sequential)
Step 3a composioExecute GOOGLESHEETS_CREATE_GOOGLE_SHEET1 title="Descriptive Title - Month Year"
  Capture: spreadsheetId and spreadsheetUrl from the response — you will need both
Step 3b composioExecute GOOGLESHEETS_BATCH_UPDATE spreadsheet_id=<from 3a> sheet_name="Sheet1" first_cell_location="A1" values=[[header row] [row 1] [row 2] ...]
  IMPORTANT: values is a complete 2D array — all rows in one call NOT one call per row
  first_cell_location is just "A1" — do NOT include sheet name prefix like "Sheet1!A1"
  Sheet1 is the default tab name — if locale may differ call GOOGLESHEETS_GET_SHEET_NAMES first
Step 3c composioExecute GMAIL_SEND_EMAIL to=<user email> subject=<sheet title> body="Your spreadsheet is ready:\n\n<spreadsheetUrl from 3a>"
  Always include the full spreadsheetUrl on its own line in the email body
  Never re-search for the URL — you already have it from step 3a

STEP 4 — Confirm with one sentence
Done — I've sent you the spreadsheet with [N] rows. Check your inbox.

COLUMN DESIGN — create purposeful columns for every task type
Client analysis: Name | Company | Email | Last Contact | Opportunity | Personalized Outreach
Research output: Topic | Summary | Source | Implication | Priority
Financial data: Company | Metric | Value | Period | Change | Notes
Prospect list: Name | Title | Company | Industry | Pain Point | Recommended Approach

Example 9 — Lapsed client reactivation from emails
User: Go through the lapsed client emails identify reactivation opportunities write personalized outreach and send me a spreadsheet
1. Say: I'll go through those now and build you a reactivation sheet — give me a moment.
2. INTERNAL: Read lapsed client emails from context
3. INTERNAL: Identify candidates with reactivation signals — assess opportunity type and urgency for each
4. INTERNAL: Write a personalized outreach message for each based on their last interaction and current signals
5. INTERNAL: Assemble complete 2D array [["Name","Company","Email","Last Contact","Opportunity","Personalized Outreach"],["Jane Smith","Acme Corp","jane@acme.com","2025-11-01","Q1 budget renewal","Hi Jane..."],...]
6. SILENT composioExecute: GOOGLESHEETS_CREATE_GOOGLE_SHEET1 title="Lapsed Client Reactivation - Feb 2026"
7. Extract: spreadsheetId and spreadsheetUrl — store both
8. SILENT composioExecute: GOOGLESHEETS_BATCH_UPDATE spreadsheet_id=<step 6 id> sheet_name="Sheet1" first_cell_location="A1" values=<full 2D array from step 5>
9. SILENT composioExecute: GMAIL_SEND_EMAIL to=jayconnor@synrgscaling.com subject="Lapsed Client Reactivation - Feb 2026" body="Reactivation opportunities ready:\n\n<spreadsheetUrl from step 7>"
10. Say: Done — I've sent you the spreadsheet with [N] reactivation opportunities. Each row includes a personalized outreach message. Check your inbox.

Example 10 — Research output to spreadsheet
User: Research the top enterprise AI trends and compile the findings into a spreadsheet send it to me
1. Say: On it — researching and building the sheet now.
2. SILENT composioExecute: PERPLEXITYAI_PERPLEXITY_AI_SEARCH userContent="top enterprise AI trends 2026 for executive decision-making" model=sonar-pro return_citations=true
3. INTERNAL: Extract top 10 trends — for each: trend name summary key implication priority level
4. INTERNAL: Build complete 2D array [["Trend","Summary","Key Implication","Priority"],["AI Agents in ERP","...","...","High"],...]
5. SILENT composioExecute: GOOGLESHEETS_CREATE_GOOGLE_SHEET1 title="Enterprise AI Trends - Feb 2026"
6. Extract: spreadsheetId and spreadsheetUrl — store both
7. SILENT composioExecute: GOOGLESHEETS_BATCH_UPDATE spreadsheet_id=<step 5 id> sheet_name="Sheet1" first_cell_location="A1" values=<full 2D array from step 4>
8. SILENT composioExecute: GMAIL_SEND_EMAIL to=jayconnor@synrgscaling.com subject="Enterprise AI Trends - Feb 2026" body="Top enterprise AI trends compiled:\n\n<spreadsheetUrl from step 6>"
9. Say: Done — 10 trends compiled and emailed. Check your inbox.

PRESENTATION RULES
NEVER mention tool names slugs catalogs or technical processes to the user
Speak as if you natively know how to perform the action
Good: Searching the web for that now
Good: Sending that Teams message now
Good: Let me pull up your OneDrive files
Bad: Let me search for a tool that can send Teams messages
Bad: I need to discover the right tool first
Bad: I am checking the catalog for available tools

TASK COMPLETION - Always finish what you start
When a user asks you to do something execute it fully without stopping for re-confirmation
If a tool returns data use that data immediately in the next step
If searching leads to results that need action take the action
If you need to chain two tools do so in sequence without asking the user to repeat themselves
Never stop mid-task to describe what you found unless the user needs to make a decision
Complete the full request: search then act then confirm done

CONTEXT RETENTION - Remember everything the user tells you
Track all specifics mentioned in the conversation including names emails addresses data results and preferences
Never re-ask for information the user already provided
If the user spelled out an email earlier and later says send that to them you already know the email
If the user just looked up a candidate and says email those results you know which candidate and which results
Use your conversation context to carry forward details between tool calls
Keep a mental map of the active request including who what where and which tools are likely needed next

PLANNING PROTOCOL - Choose the right execution pattern before acting

TWO EXECUTION MODES — pick based on data dependency:

MODE A - PARALLEL BATCH (steps are independent or step 2 does NOT need specific data from step 1)
Use composioBatchExecute with all tools in one call
Steps at the same number run in parallel. Different step numbers run in order.
Example: send a Teams message to a known channel AND update a spreadsheet at the same time
[{"tool_slug":"MICROSOFT_TEAMS_SEND_MESSAGE","step":1,"arguments":{...}},{"tool_slug":"GOOGLESHEETS_UPDATE_ROW","step":1,"arguments":{...}}]

MODE B - SEQUENTIAL (step 2 needs a specific value from step 1 that you do not already know)
Use composioExecute for step 1 to get the data back
Read the result to extract the specific value you need
Then use composioExecute or composioBatchExecute for step 2 with that actual value
Example: list Teams channels THEN send to "standup" channel (you need the real channelId first)
Step 1: composioExecute MICROSOFT_TEAMS_GET_CHANNELS to discover available channels
Step 2: composioExecute MICROSOFT_TEAMS_SEND_MESSAGE with channelId extracted from step 1

WHEN TO USE listComposioTools
Only call listComposioTools if the catalog injected at session start does not have the slugs you need
The catalog is pre-loaded — use it first. listComposioTools is a fallback not a required first step.

WHEN TO USE planComposioTask
Only call planComposioTask if you are unsure of required parameters and the catalog hint is insufficient
Skip it entirely if you already know the params from the catalog or from context

For SIMPLE tasks (single tool, or core tools like sendEmail searchDrive recall):
Skip planning entirely — say ONE brief confirm phrase then execute immediately

GOAL TRACKING - Complete every step without stopping
Once planning is done execute ALL steps without pausing or speaking between them
If step 2 needs data from step 1 use it immediately — no speaking in between
Only deliver the final summary after EVERY step in the plan is complete
Track the goal from the first word to the final confirmation

EXECUTION PROTOCOL - One phrase to start, silent execution, one phrase to finish
Say ONE phrase to confirm or plan (never more than one sentence)
Then execute ALL required tool calls completely without speaking
After ALL tool calls are fully done respond ONCE with the complete result
If a tool fails and you retry with corrected params retry silently — never announce retries
Never speak between individual tool steps

EXAMPLES
User: "List my Teams channels and send a message to the standup channel saying standup is at 3"
  1. Say: "On it."
  2. SILENT: composioExecute MICROSOFT_TEAMS_GET_CHANNELS {} — read result to find standup channelId
  3. SILENT: composioExecute MICROSOFT_TEAMS_SEND_MESSAGE {channelId: "[id from step 2]", body: "standup is at 3"}
  4. Say: "Done — sent it to the standup channel."
  NOTE: Two separate composioExecute calls because step 3 needs the actual channelId from step 2.
  Do NOT try to do this in one composioBatchExecute — you do not know the channelId until step 2 returns.

User: "Search Drive for the budget file and email it to Jay"
  1. Say: "On it." (core tools — skip planning)
  2. SILENT: searchDrive then sendEmail
  3. Say: "Done — emailed the budget to Jay."

User: "Post a message to the general Teams channel and update the tracker sheet"
  1. Say: "On it."
  2. SILENT: composioBatchExecute — MODE A parallel batch — both tools at step 1 (independent actions)
  [{"tool_slug":"MICROSOFT_TEAMS_SEND_MESSAGE","step":1,"arguments":{"channelId":"general","body":"..."}},
   {"tool_slug":"GOOGLESHEETS_UPDATE_ROW","step":1,"arguments":{...}}]
  3. Say: "Done — posted to Teams and updated the tracker."
  NOTE: MODE A because you already know the channelId and both actions are independent.

EMAIL PROTOCOL - Follow this exact flow

Step 1 RECIPIENT
You: Who should I send it to spell out their email for me
User spells letter by letter: j a y c o n n o r at example dot com
You: So thats jayconnor at example dot com right
User: Yes or No
If No: Go ahead spell it again for me
If Yes: Move to Step 2

Step 2 SUBJECT
You: Whats the subject
User states subject naturally
You: Got it [repeat subject] and what should the message say

Step 3 BODY
User describes what to say
You draft the email internally then ask: I drafted that up do you want the summary or should I read the whole thing
User: Summary - give 1 sentence overview
User: Full or read it - read the complete body
After reading chosen version: Should I send it
User: Yes
[call send_email tool]
You: Sent

IMPORTANT - Never read the full email body unless user specifically asks for it
IMPORTANT - Only ONE confirmation per step then move forward
IMPORTANT - Do not re-confirm things already confirmed

READ OPERATION EXAMPLE
User: What files do I have
You: Checking your Drive
[call list_files tool]
After result: You have 5 files including quarterly report budget draft and meeting notes

ERROR HANDLING
If a tool returns 'I was not able to' or mentions 'do not retry' then STOP do NOT call that tool again with the same slug
Instead tell the user what happened in plain language and ask if they want to try a different approach
If a tool says it does not exist do NOT retry with different arguments it will not work
If credentials expired say: That service needs reconnection let me note that
Never expose technical errors verbosely
Never retry a failed tool more than once

WHAT NEVER TO DO
- Never output JSON function calls as speech
- Never read punctuation aloud
- Never execute WRITE tools without final yes
- Never list all capabilities unless asked
- Never give verbose technical explanations
- Never re-confirm something already confirmed
- Never read full email body without being asked

TONE
Direct efficient professional
Occasional dry wit when contextually relevant
Executive-grade communication

CONNECTED SERVICES CATALOG
Reference this section to find exact tool slugs for composioBatchExecute and composioExecute
Always use the EXACT full slug as listed below never shorten or guess

{COMPOSIO_CATALOG}"""


def prewarm(proc: JobProcess):
    """Prewarm VAD model and initialize cache during server initialization."""
    logger.info("Prewarming VAD model...")
    proc.userdata["vad"] = silero.VAD.load(
        min_speech_duration=0.05,      # 50ms - faster speech detection start
        min_silence_duration=0.35,     # 350ms - OPTIMIZED from 550ms (saves ~200ms latency)
        prefix_padding_duration=0.25,  # 250ms - OPTIMIZED from 500ms (saves ~250ms latency)
        activation_threshold=0.1,      # OPTIMIZED from 0.05 (fewer false positives)
        sample_rate=16000,             # Silero requires 8kHz or 16kHz
        force_cpu=True,                # Consistent CPU inference
    )
    logger.info("VAD model prewarmed with optimized settings (silence=350ms, threshold=0.1)")

    # Initialize context cache manager
    cache_manager = get_cache_manager()
    proc.userdata["cache_manager"] = cache_manager
    logger.info("Context cache manager initialized")

    # Pre-build Composio tool catalog in background thread (non-blocking).
    # Worker registration proceeds immediately. If catalog finishes before
    # first meeting, it gets injected into system prompt. If not, the lazy
    # build on first composioBatchExecute call handles it.
    proc.userdata["composio_catalog"] = ""  # default empty

    def _build_catalog():
        try:
            from .tools.composio_router import prewarm_slug_index
            proc.userdata["composio_catalog"] = prewarm_slug_index()
        except Exception as e:
            logger.warning(f"Composio catalog prewarm failed: {e}")

    catalog_thread = threading.Thread(target=_build_catalog, daemon=True, name="composio-prewarm")
    catalog_thread.start()
    proc.userdata["_composio_thread"] = catalog_thread
    logger.info("Composio catalog build started in background thread")

    # Ensure memory files (MEMORY.md, USER.md) exist on the volume
    if _MEM_AVAILABLE and _session_writer is not None:
        try:
            import os
            _mem_dir = os.environ.get("AIO_MEMORY_DIR", "/app/data/memory")
            _session_writer.ensure_memory_files(_mem_dir)
        except Exception as _e:
            logger.warning("[Memory] File init failed: %s", _e)

    # Initialize persistent memory store (non-blocking — failure is tolerated)
    if _MEM_AVAILABLE and _mem_store is not None:
        try:
            _mem_store.init()
        except Exception as _e:
            logger.warning("[Memory] Store init failed in prewarm: %s", _e)


async def entrypoint(ctx: JobContext):
    """Main entry point for the voice agent."""

    logger.info(f"Agent starting for room: {ctx.room.name}")
    tracker = LatencyTracker()

    # Use prewarmed VAD or load fresh if not available
    if "vad" in ctx.proc.userdata:
        vad = ctx.proc.userdata["vad"]
        logger.info("Using prewarmed VAD")
    else:
        logger.warning("VAD not prewarmed, loading now (adds latency)")
        vad = silero.VAD.load(
            min_speech_duration=0.05,
            min_silence_duration=0.35,     # OPTIMIZED from 550ms
            prefix_padding_duration=0.25,  # OPTIMIZED from 500ms
            activation_threshold=0.1,      # OPTIMIZED from 0.05
            sample_rate=16000,
            force_cpu=True,
        )
        logger.info("VAD loaded with optimized settings (silence=350ms, threshold=0.1)")

    # OPTIMIZED: Initialize STT/LLM/TTS in parallel (saves ~150-200ms)
    # Using asyncio.gather with to_thread for synchronous constructors
    logger.info("Initializing STT/LLM/TTS in parallel...")

    def init_stt():
        return deepgram.STT(
            model=settings.deepgram_model,
            language="en",
            smart_format=True,
            interim_results=True,
            punctuate=True,
            profanity_filter=False,
        )

    def init_llm():
        """Initialize Fireworks AI LLM."""
        if not settings.fireworks_api_key:
            raise RuntimeError(
                "No LLM configured. Set FIREWORKS_API_KEY. "
                f"Model: {settings.fireworks_model}"
            )
        logger.info(f"Initializing Fireworks AI LLM: {settings.fireworks_model}")
        return openai.LLM.with_fireworks(
            model=settings.fireworks_model,
            api_key=settings.fireworks_api_key,
            temperature=settings.fireworks_temperature,
            parallel_tool_calls=True,
        )

    def init_tts():
        return cartesia.TTS(
            model=settings.cartesia_model,
            voice=settings.cartesia_voice,
            api_key=settings.cartesia_api_key,
            sample_rate=24000,
        )

    stt, llm_instance, tts = await asyncio.gather(
        asyncio.to_thread(init_stt),
        asyncio.to_thread(init_llm),
        asyncio.to_thread(init_tts),
    )
    logger.info("STT/LLM/TTS initialized in parallel")

    # Create agent session with optimized settings
    session_kwargs = {
        "vad": vad,
        "stt": stt,
        "llm": llm_instance,
        "tts": tts,
        # Performance optimizations
        "preemptive_generation": True,  # Start LLM before turn ends
        # Handle background noise gracefully
        "resume_false_interruption": True,
        "false_interruption_timeout": 1.0,
        # Allow multi-step tool flows (schema lookup → execute → retry if needed)
        "max_tool_steps": 10,
    }

    # OPTIMIZED: Add turn detection using lazy loader (non-blocking at module load)
    turn_detector = get_turn_detector()
    if turn_detector:
        session_kwargs["turn_detection"] = turn_detector
        logger.info("Using semantic turn detection")
    else:
        logger.info("Using VAD-only turn detection (faster startup)")

    session = AgentSession(**session_kwargs)

    # =========================================================================
    # VAD DEBUG: Monitor if VAD is receiving audio frames
    # =========================================================================
    vad_frame_count = {"count": 0, "speech_frames": 0, "last_log_time": 0}

    @session.on("audio_input")
    def on_audio_input(ev):
        """Debug: Monitor raw audio input frames to VAD."""
        vad_frame_count["count"] += 1
        # Log every 100 frames (~5 seconds at 50ms frame size)
        import time
        now = time.time()
        if now - vad_frame_count["last_log_time"] > 5.0:
            vad_frame_count["last_log_time"] = now
            logger.info(f"🎤 VAD receiving audio: {vad_frame_count['count']} frames total")

    # Set global room reference for tool event publishing
    from .utils.room_publisher import set_room as _set_room, publish_error as _publish_error
    _set_room(ctx.room)
    logger.info("Room publisher initialized for tool lifecycle events")

    # Initialize async tool worker for background execution
    tool_worker = AsyncToolWorker(room=ctx.room, max_concurrent=3)

    # Register result callback BEFORE starting (defined later, uses session)
    # The callback will be set after session is created
    await tool_worker.start()
    set_worker(tool_worker)
    logger.info("AsyncToolWorker started - tools will execute in background")

    # Build tool list: n8n webhook tools + Composio SDK execution wrappers
    all_tools = list(ASYNC_TOOLS)

    # Read pre-built Composio catalog from prewarm (zero latency — no network calls here)
    # If background thread is still running, proceed without catalog (lazy build handles it)
    composio_thread = ctx.proc.userdata.get("_composio_thread")
    if composio_thread and composio_thread.is_alive():
        logger.info("Composio catalog still building in background, proceeding without")
    composio_catalog = ctx.proc.userdata.get("composio_catalog", "")
    if settings.composio_api_key:
        logger.info(f"Composio: SDK enabled, catalog {'ready' if composio_catalog else 'empty'} ({len(all_tools)} tools)")
    else:
        logger.info("Composio: Disabled (no COMPOSIO_API_KEY)")

    logger.info(f"Agent tools: {len(all_tools)} total")

    # Inject pre-loaded catalog into system prompt via {COMPOSIO_CATALOG} marker
    active_prompt = SYSTEM_PROMPT
    if composio_catalog:
        active_prompt = active_prompt.replace(
            "{COMPOSIO_CATALOG}",
            composio_catalog,
        )
    else:
        active_prompt = active_prompt.replace(
            "{COMPOSIO_CATALOG}",
            "No connected services catalog available. Use manageConnections with action status to check what is connected.",
        )

    # Inject current date/time context (no tool call needed)
    from datetime import datetime, timezone, timedelta
    est = timezone(timedelta(hours=-5))
    now = datetime.now(est)
    time_context = (
        f"\n\nCURRENT DATE AND TIME\n"
        f"{now.strftime('%Y-%m-%d %I:%M %p')} EST\n"
        f"{now.strftime('%A, %B %d, %Y')}\n"
        f"Always reference EST when discussing time"
    )
    active_prompt += time_context

    # Load cross-session memory context and inject into instructions
    _memory_context = ""
    if _MEM_AVAILABLE and _session_writer is not None:
        try:
            import os
            _mem_dir = os.environ.get("AIO_MEMORY_DIR", "/app/data/memory")
            _memory_context = _session_writer.load_memory_context(_mem_dir, max_tokens=500)
        except Exception as _e:
            logger.warning("[Memory] Context load failed: %s", _e)

    if _memory_context:
        active_prompt = active_prompt + "\n\n## Cross-Session Memory\n" + _memory_context

    # Define agent with all tools (no MCP servers)
    agent = Agent(
        instructions=active_prompt,
        tools=all_tools,
    )

    # In-session task tracker — monitors tool execution progress for heartbeat continuation
    _task_tracker = TaskTracker(
        stall_threshold_seconds=6.0,          # 6s stall before Case 1/3 triggers
        max_continuations_per_objective=5,    # 5 attempts before giving up
        min_continuation_gap_seconds=8.0,     # 8s cooldown between Case 2/3 injections
    )

    # Register event handlers BEFORE starting session
    # LiveKit Agents 1.3.x requires synchronous callbacks - async work via asyncio.create_task

    # Safe publish helper - handles cases where room is disconnecting
    async def safe_publish_data(data: bytes, log_type: str = "data") -> bool:
        """Safely publish data to room, handling disconnection gracefully."""
        try:
            if ctx.room.local_participant:
                await ctx.room.local_participant.publish_data(data)
                # Log successful publish at INFO level for debugging
                logger.info(f"📤 Published {log_type}: {data[:100].decode('utf-8', errors='ignore')}...")
                return True
            else:
                logger.warning(f"Cannot publish {log_type}: no local_participant")
        except Exception as e:
            logger.warning(f"Failed to publish {log_type}: {e}")
        return False

    @session.on("user_state_changed")
    def on_user_state_changed(ev):
        """User state: speaking, listening, away."""
        state = ev.new_state if hasattr(ev, 'new_state') else str(ev)
        logger.debug(f"User state changed: {state}")
        if str(state) == "speaking":
            tracker.start("total_latency")
            asyncio.create_task(safe_publish_data(
                b'{"type":"agent.state","state":"listening"}',
                log_type="agent.state"
            ))

    @session.on("user_input_transcribed")
    def on_user_input_transcribed(ev):
        """Called when user speech is transcribed."""
        text = ev.transcript if hasattr(ev, 'transcript') else str(ev)
        is_final = getattr(ev, 'is_final', True)

        # ONLY publish FINAL transcripts to avoid duplicates
        # Interim results are partial and will be superseded
        if not is_final:
            return

        # Safe text handling for logging
        text_preview = text[:100] if text and len(text) > 100 else (text or "(empty)")
        logger.info(f"User said (final): {text_preview}")

        # Track user objective for heartbeat-driven continuation
        if text:
            _task_tracker.record_user_message(text)

        # Publish user transcript to client for UI display
        asyncio.create_task(safe_publish_data(
            json.dumps({
                "type": "transcript.user",
                "text": text or "",
                "is_final": True
            }).encode(),
            log_type="transcript.user"
        ))

    @session.on("agent_state_changed")
    def on_agent_state_changed(ev):
        """Agent state: initializing, idle, listening, thinking, speaking."""
        state = ev.new_state if hasattr(ev, 'new_state') else str(ev)
        logger.debug(f"Agent state changed: {state}")

        state_str = str(state).lower()
        if "thinking" in state_str:
            _task_tracker.record_agent_responding()
            asyncio.create_task(safe_publish_data(
                b'{"type":"agent.state","state":"thinking"}',
                log_type="agent.state"
            ))
        elif "speaking" in state_str:
            asyncio.create_task(safe_publish_data(
                b'{"type":"agent.state","state":"speaking"}',
                log_type="agent.state"
            ))
        elif "listening" in state_str:
            _task_tracker.record_agent_idle()
            asyncio.create_task(safe_publish_data(
                b'{"type":"agent.state","state":"listening"}',
                log_type="agent.state"
            ))
        elif "idle" in state_str:
            _task_tracker.record_agent_idle()
            total = tracker.end("total_latency")
            if total:
                logger.info(f"Total latency: {total:.0f}ms")
            asyncio.create_task(safe_publish_data(
                b'{"type":"agent.state","state":"idle"}',
                log_type="agent.state"
            ))

    @session.on("conversation_item_added")
    def on_conversation_item_added(ev):
        """Called when a new item is added to conversation - captures agent responses."""
        # Extract item from event
        item = getattr(ev, 'item', None)
        if not item:
            return

        # Check if this is an assistant (agent) message
        role = getattr(item, 'role', None)

        # Auto-capture memory triggers from user utterances
        if _MEM_AVAILABLE and _mem_capture is not None:
            try:
                # Only capture from user messages, not agent responses
                if hasattr(item, 'role') and str(getattr(item, 'role', '')).lower() == 'user':
                    _text = ""
                    if hasattr(item, 'text_content'):
                        _text = item.text_content or ""
                    elif hasattr(item, 'content') and isinstance(item.content, str):
                        _text = item.content
                    if _text:
                        _mem_capture.detect_and_queue(_text)
            except Exception as _e:
                logger.debug("[Memory] Capture check failed: %s", _e)

        if role != 'assistant':
            return  # Only publish agent responses, user transcripts handled separately

        # Extract text content from the item
        text = ""
        try:
            # Try text_content attribute (common in conversation items)
            if hasattr(item, 'text_content'):
                text = item.text_content or ""
            # Try content attribute
            elif hasattr(item, 'content'):
                content = item.content
                if isinstance(content, str):
                    text = content
                elif hasattr(content, 'text'):
                    text = content.text or ""
            # Try text attribute directly
            elif hasattr(item, 'text'):
                text = item.text or ""
        except Exception as e:
            logger.debug(f"Could not extract conversation item text: {e}")

        if text:
            text_preview = text[:100] if len(text) > 100 else text
            logger.info(f"Agent said: {text_preview}")
            asyncio.create_task(safe_publish_data(
                json.dumps({"type": "transcript.assistant", "text": text}).encode(),
                log_type="transcript.assistant"
            ))
            # OpenClaw-style interim-phrase detection: feed agent speech to task
            # tracker so Case 3 stall detection can arm if the LLM says something
            # like "let me try" or "working on it" without calling a tool.
            _task_tracker.record_agent_speech(text)

    @session.on("function_tools_executed")
    def on_function_tools_executed(ev):
        """Called when tools finish executing."""
        logger.info(f"Tools executed: {ev}")
        # Notify task tracker that tool work completed — heartbeat uses this
        # to determine whether a multi-step task was in progress
        _task_tracker.record_tool_call_completed()

    @session.on("metrics_collected")
    def on_metrics_collected(ev):
        """Collect and log metrics."""
        logger.debug(f"Metrics: {ev}")

    # =========================================================================
    # ASYNC TOOL RESULT HANDLER - AIO ECOSYSTEM v2
    # - No punctuation in voice output
    # - 20% programmatic wit (contextually relevant)
    # - Clean conversational announcements
    # =========================================================================

    import random

    # Standard announcements (no punctuation for voice)
    STANDARD_SUCCESS = [
        "Done",
        "All set",
        "Completed",
        "Finished",
    ]

    # Witty announcements (20% chance, contextually matched)
    WITTY_RESPONSES = {
        "email": [
            "Message delivered faster than a carrier pigeon",
            "Email sent and on its way",
            "Done that message is flying through the internet",
        ],
        "search": [
            "Found your needle in the digital haystack",
            "Eureka that is exactly what you were looking for",
            "Got some results for you",
        ],
        "save": [
            "Locked and loaded in the vault",
            "Saved and secure in the knowledge base",
            "Information stored successfully",
        ],
        "document": [
            "Found the document you needed",
            "Got that file pulled up",
            "Retrieved the document",
        ],
        "error": [
            "Hit a snag on that one let me try a different approach",
            "That did not work as expected want to try again",
            "Ran into an issue there",
        ],
    }

    def strip_punctuation(text: str) -> str:
        """Remove all punctuation from text for voice output."""
        import re
        # Remove common punctuation but keep apostrophes in contractions
        text = re.sub(r'[.,!?;:\-"\(\)\[\]{}]', '', text)
        # Clean up extra spaces
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def get_witty_response(tool_type: str) -> str:
        """Get a contextually relevant witty response."""
        responses = WITTY_RESPONSES.get(tool_type, WITTY_RESPONSES.get("save", []))
        return random.choice(responses) if responses else "Done"

    def format_tool_result_v2(tool_name: str, result: str, status: str) -> str:
        """Format tool result with 20% wit probability, no punctuation.

        Handles both core tools (sendEmail, searchDrive) and Composio tools
        (composio:batch:TEAMS_SEND+DRIVE_LIST). For Composio tools, the result
        string already contains voice-friendly text from _extract_voice_result.
        """

        # Determine tool type for contextual responses
        tool_lower = tool_name.lower()
        tool_type = "save"  # default
        if "email" in tool_lower or "gmail" in tool_lower or "send" in tool_lower:
            tool_type = "email"
        elif "search" in tool_lower or "query" in tool_lower or "find" in tool_lower or "list" in tool_lower:
            tool_type = "search"
        elif "document" in tool_lower or "file" in tool_lower or "drive" in tool_lower:
            tool_type = "document"
        elif "store" in tool_lower or "save" in tool_lower or "add" in tool_lower:
            tool_type = "save"
        elif "teams" in tool_lower or "slack" in tool_lower or "message" in tool_lower:
            tool_type = "email"  # messaging maps to email-like announcements

        if status == "failed":
            tool_type = "error"

        # For Composio tools, the result already has voice-friendly text
        # from _extract_voice_result — use it directly if substantive
        is_composio = tool_name.startswith("composio:")
        if is_composio and result and len(result) > 10 and status != "failed":
            clean_result = strip_punctuation(result[:150])
            return clean_result

        # 20% chance for witty response
        use_wit = random.random() < 0.20

        if use_wit:
            announcement = get_witty_response(tool_type)
        else:
            # Standard announcement based on tool type
            if status == "failed":
                announcement = "That did not work want to try again"
            elif tool_type == "email":
                announcement = "Sent"
            elif tool_type == "search":
                # Include summary of what was found
                if result and len(result) > 10:
                    clean_result = strip_punctuation(result[:120])
                    announcement = f"Here is what I found {clean_result}"
                else:
                    announcement = "Search complete"
            elif tool_type == "document":
                announcement = "Got the document"
            else:
                announcement = random.choice(STANDARD_SUCCESS)

        # Ensure no punctuation in final output
        return strip_punctuation(announcement)

    async def handle_tool_result(result_data: dict):
        """Handle async tool result with AIO v2 conversational announcement."""
        tool_name = result_data.get("tool_name", "unknown")
        status = result_data.get("status", "unknown")
        result = result_data.get("result", "")
        error = result_data.get("error", "")
        duration = result_data.get("duration_ms", 0)

        logger.info(f"Tool result: {tool_name} status={status} duration={duration}ms result_preview={str(result)[:120]}")

        # Detect soft errors — tool returned normally but with error content
        is_soft_error = result and ("I was not able to" in result or "do not retry" in result)

        if is_soft_error:
            # Tool completed but with an error message — announce as failure
            announcement = "That tool ran into an issue let me know if you want to try something else"
            try:
                await session.say(announcement, allow_interruptions=True)
            except Exception as e:
                logger.error(f"Failed to announce soft error: {e}")

        elif status == "completed":
            announcement = format_tool_result_v2(tool_name, result, status)
            try:
                await session.say(announcement, allow_interruptions=True)
            except Exception as e:
                logger.error(f"Failed to announce result: {e}")

        elif status == "failed":
            announcement = format_tool_result_v2(tool_name, error, status)

            try:
                await session.say(announcement, allow_interruptions=True)
            except Exception as e:
                logger.error(f"Failed to announce error: {e}")

    # Register callback on worker for direct notification
    tool_worker.on_result = handle_tool_result
    logger.info("Tool result callback registered on AsyncToolWorker")

    # Also listen for data_received for external tool results (from other participants)
    @ctx.room.on("data_received")
    def on_data_received(data: rtc.DataPacket):
        """Handle incoming data packets from OTHER participants."""
        try:
            message = json.loads(data.data.decode("utf-8"))
            msg_type = message.get("type", "")

            if msg_type == "tool_result":
                # Only handle if from external source (not our own worker)
                # Our worker notifies directly via callback
                task_id = message.get("task_id", "")
                if not task_id.startswith("task_"):
                    # External task, handle it
                    asyncio.create_task(handle_tool_result(message))

        except json.JSONDecodeError:
            pass  # Ignore non-JSON data
        except Exception as e:
            logger.error(f"Error handling data packet: {e}")

    # =========================================================================
    # AUDIO INPUT DEBUGGING - Track subscription events
    # =========================================================================
    @ctx.room.on("track_subscribed")
    def on_track_subscribed(track, publication, participant):
        """Track when we subscribe to remote audio tracks."""
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            logger.info(f"🎤 AUDIO TRACK SUBSCRIBED:")
            logger.info(f"   - Track SID: {track.sid}")
            logger.info(f"   - Track Source: {publication.source}")
            logger.info(f"   - Participant: {participant.identity}")
            logger.info(f"   - Track Name: {publication.name}")

            # CRITICAL DIAGNOSTIC: Count actual audio frames from this track
            async def count_audio_frames():
                """Count audio frames to verify audio is flowing."""
                import struct
                import math

                frame_count = 0
                silent_frames = 0
                max_rms = 0.0
                rms_sum = 0.0
                last_log_time = asyncio.get_event_loop().time()

                try:
                    audio_stream = rtc.AudioStream(track)
                    async for frame_event in audio_stream:
                        frame_count += 1
                        frame = frame_event.frame

                        # Check if frame is silent (all zeros or very low)
                        samples = frame.data
                        rms = 0.0
                        if samples:
                            # Calculate RMS of frame
                            try:
                                # Assuming 16-bit PCM
                                num_samples = len(samples) // 2
                                if num_samples > 0:
                                    values = struct.unpack(f'{num_samples}h', samples[:num_samples*2])
                                    rms = (sum(v*v for v in values) / num_samples) ** 0.5
                                    rms_sum += rms
                                    if rms > max_rms:
                                        max_rms = rms
                                    if rms < 100:  # Very quiet (below -50dB)
                                        silent_frames += 1
                            except Exception:  # nosec B110 - audio frame RMS calc is best-effort
                                pass

                        # Log every 5 seconds
                        now = asyncio.get_event_loop().time()
                        if now - last_log_time > 5.0:
                            last_log_time = now
                            pct_silent = (silent_frames / frame_count * 100) if frame_count > 0 else 0
                            avg_rms = rms_sum / frame_count if frame_count > 0 else 0

                            # Convert to dB for meaningful interpretation
                            # 32767 is max for 16-bit audio, so dB = 20*log10(rms/32767)
                            max_db = 20 * math.log10(max_rms / 32767) if max_rms > 0 else -100
                            avg_db = 20 * math.log10(avg_rms / 32767) if avg_rms > 0 else -100

                            logger.info(f"📊 AUDIO FRAME STATS: {frame_count} total, {silent_frames} silent ({pct_silent:.1f}%)")
                            logger.info(f"   Sample rate: {frame.sample_rate}, Channels: {frame.num_channels}")
                            logger.info(f"   RMS: avg={avg_rms:.1f} ({avg_db:.1f}dB), max={max_rms:.1f} ({max_db:.1f}dB)")

                            # VAD threshold 0.05 with Silero typically requires > -40dB audio
                            if max_db < -50:
                                logger.warning(f"⚠️ AUDIO VERY QUIET (max {max_db:.1f}dB) - VAD may not trigger!")
                            elif pct_silent > 90:
                                logger.warning(f"⚠️ AUDIO IS MOSTLY SILENT - Check Recall.ai audio source!")
                            else:
                                logger.info(f"   ✅ Audio levels look good for VAD (threshold=0.05)")

                except Exception as e:
                    logger.error(f"Audio frame counting error: {e}")

            # Start counting in background
            asyncio.create_task(count_audio_frames())

    @ctx.room.on("track_published")
    def on_track_published(publication, participant):
        """Track when remote participants publish tracks."""
        logger.info(f"📡 TRACK PUBLISHED by {participant.identity}:")
        logger.info(f"   - Track SID: {publication.sid}")
        logger.info(f"   - Track Kind: {publication.kind}")
        logger.info(f"   - Track Source: {publication.source}")
        logger.info(f"   - Track Name: {publication.name}")

    @ctx.room.on("participant_connected")
    def on_participant_connected(participant):
        """Track when participants connect."""
        logger.info(f"👤 PARTICIPANT CONNECTED: {participant.identity}")
        logger.info(f"   - SID: {participant.sid}")
        logger.info(f"   - Metadata: {participant.metadata}")
        # List their current tracks
        for pub in participant.track_publications.values():
            logger.info(f"   - Has track: {pub.kind} / {pub.source} / {pub.name}")

    # Connect to room with EXPLICIT auto_subscribe=True
    # This ensures we subscribe to ALL remote participant tracks
    await ctx.connect(auto_subscribe=True)
    logger.info(f"Connected to room: {ctx.room.name}")

    # DEBUG: Log room configuration
    logger.info(f"=== ROOM DEBUG ===")
    room_sid = await ctx.room.sid
    logger.info(f"Room SID: {room_sid}")
    logger.info(f"Room name: {ctx.room.name}")
    logger.info(f"Local participant: {ctx.room.local_participant.identity if ctx.room.local_participant else 'None'}")
    logger.info(f"Remote participants: {len(ctx.room.remote_participants)}")

    # Wait for Output Media client to connect BEFORE starting session
    # This is CRITICAL - the session must link to the client participant
    # to receive audio from them
    # Timeout is 300s (5 min) - early arrival returns immediately, no delay
    async def wait_for_client_with_audio(timeout_seconds: float = 300.0) -> Optional[rtc.RemoteParticipant]:
        """Wait for the Output Media webpage client to connect AND publish audio.

        CRITICAL: We must wait for the audio track to be published, not just for
        the participant to connect. Otherwise session.start() will link to a
        participant that hasn't published audio yet.

        Returns immediately when client's audio track is detected - the timeout
        only applies if client never arrives or never publishes audio.
        """
        start_time = asyncio.get_event_loop().time()
        check_interval = 0.5  # Check every 500ms for fast response

        client_participant = None
        audio_track_found = False

        while (asyncio.get_event_loop().time() - start_time) < timeout_seconds:
            # Check current participants for the client
            for participant in ctx.room.remote_participants.values():
                if participant is None:
                    continue
                identity = getattr(participant, 'identity', None)
                if identity is None:
                    continue
                identity_lower = identity.lower()

                # Output Media client identity format: 'output-media-{session_id}'
                if identity_lower.startswith('output-media-'):
                    if client_participant is None:
                        logger.info(f"👤 Client found: {participant.identity}")
                        client_participant = participant

                    # Check if client has published an audio track
                    for pub in participant.track_publications.values():
                        if pub.kind == rtc.TrackKind.KIND_AUDIO:
                            logger.info(f"🎤 Client audio track found!")
                            logger.info(f"   - Track SID: {pub.sid}")
                            logger.info(f"   - Track Name: {pub.name}")
                            logger.info(f"   - Track Source: {pub.source}")
                            audio_track_found = True
                            break

                    if audio_track_found:
                        return participant

            await asyncio.sleep(check_interval)

        if client_participant and not audio_track_found:
            logger.warning(f"Client connected but no audio track published after {timeout_seconds}s")
            return client_participant  # Return participant anyway, maybe track will come later

        logger.warning(f"Timeout waiting for client after {timeout_seconds}s")
        return None

    logger.info("Waiting for Output Media client to connect AND publish audio (up to 5 min)...")
    client_participant = await wait_for_client_with_audio(timeout_seconds=300.0)

    if client_participant:
        # Brief delay for Web Audio API initialization (OPTIMIZED from 1.5s to 0.3s)
        await asyncio.sleep(0.3)
        logger.info(f"Client connected: {client_participant.identity}, starting session linked to them")

        # =====================================================================
        # CRITICAL: VERIFY AUDIO SUBSCRIPTION
        # The agent MUST be subscribed to the client's audio track for VAD/STT
        # to receive audio frames. This is the most common failure point.
        # =====================================================================
        logger.info("=== AUDIO SUBSCRIPTION VERIFICATION ===")

        audio_track_subscribed = False
        for pub in client_participant.track_publications.values():
            if pub.kind == rtc.TrackKind.KIND_AUDIO:
                logger.info(f"Audio track publication found:")
                logger.info(f"  - SID: {pub.sid}")
                logger.info(f"  - Name: {pub.name}")
                logger.info(f"  - Source: {pub.source}")
                logger.info(f"  - Is Subscribed: {pub.subscribed}")
                logger.info(f"  - Is Muted: {pub.muted}")

                if pub.subscribed:
                    audio_track_subscribed = True
                    # Get the actual track
                    track = pub.track
                    if track:
                        logger.info(f"  - Track kind: {track.kind}")
                        logger.info(f"  - Track SID: {track.sid}")
                        logger.info(f"  ✅ Audio track is subscribed and ready!")
                    else:
                        logger.warning(f"  ⚠️ Publication subscribed but track is None!")
                else:
                    # CRITICAL: Force subscription if not subscribed
                    logger.warning(f"  ⚠️ Audio track NOT subscribed! Attempting manual subscription...")
                    try:
                        pub.set_subscribed(True)
                        await asyncio.sleep(0.5)  # Give time for subscription
                        if pub.subscribed:
                            logger.info(f"  ✅ Manual subscription successful!")
                            audio_track_subscribed = True
                        else:
                            logger.error(f"  ❌ Manual subscription FAILED!")
                    except Exception as e:
                        logger.error(f"  ❌ Manual subscription error: {e}")

        if not audio_track_subscribed:
            logger.warning("⚠️ NO AUDIO TRACK SUBSCRIBED - Agent will not hear client!")
            logger.warning("   This may happen if:")
            logger.warning("   1. Client hasn't published audio yet")
            logger.warning("   2. Auto-subscribe failed")
            logger.warning("   3. Track source type doesn't match expected")
        else:
            logger.info("✅ Audio subscription verified - agent should receive audio")

        logger.info("=== END VERIFICATION ===")
    else:
        # Still start but log warning - agent won't receive audio
        logger.warning("Starting without confirmed client - audio input will not work!")

    # Start the agent session with audio configuration
    # CRITICAL: Link to the client participant via participant_identity in RoomOptions
    # This tells the session which participant to listen to and respond to
    participant_identity = client_participant.identity if client_participant else None

    try:
        # Log what we're about to configure
        logger.info(f"=== STARTING SESSION ===")
        logger.info(f"  participant_identity: {participant_identity}")
        logger.info(f"  audio_input: sample_rate=16000, num_channels=1")
        logger.info(f"  audio_output: sample_rate=24000, num_channels=1")

        # Pre-warm context cache in background while session starts
        # This fetches session context before user speaks, reducing first-query latency
        session_id = ctx.room.name or "livekit-agent"
        cache_warm_task = asyncio.create_task(warm_session_cache(session_id))

        await session.start(
            agent=agent,
            room=ctx.room,
            room_options=room_io.RoomOptions(
                audio_output=room_io.AudioOutputOptions(
                    sample_rate=24000,
                    num_channels=1,
                ),
                # CRITICAL: Explicit AudioInputOptions for proper audio capture
                # Sample rate 16000 matches VAD expectation (Silero requires 16kHz)
                audio_input=room_io.AudioInputOptions(
                    sample_rate=16000,  # Match VAD sample rate
                    num_channels=1,
                ),
                # Link to specific participant's audio stream
                participant_identity=participant_identity,
                # CRITICAL: Accept ALL participant kinds, not just SIP/STANDARD
                # Recall.ai Output Media may not be recognized as STANDARD
                participant_kinds=[
                    rtc.ParticipantKind.PARTICIPANT_KIND_STANDARD,
                    rtc.ParticipantKind.PARTICIPANT_KIND_SIP,
                    rtc.ParticipantKind.PARTICIPANT_KIND_INGRESS,
                    rtc.ParticipantKind.PARTICIPANT_KIND_EGRESS,
                ],
            ),
        )
        logger.info(f"Agent session started successfully, linked to: {participant_identity or 'first participant'}")
        logger.info(f"Audio input configured: sample_rate=16000, num_channels=1")
    except Exception as e:
        logger.error(f"CRITICAL: session.start() failed: {e}")
        try:
            await _publish_error(str(e)[:200], code="agent_error", severity="high")
        except Exception:  # nosec B110 - error publishing must not block error handling
            pass
        raise

    # ── New user detection ────────────────────────────────────────────────────
    # Check SQLite memory store: if empty → new user, log and seed first entry.
    # If returning → memory context is already injected into the system prompt above.
    if _MEM_AVAILABLE and _mem_store is not None:
        try:
            _existing_memories = await asyncio.to_thread(_mem_store.search, "user session", k=1)
            _is_new_user = len(_existing_memories) == 0
            if _is_new_user:
                logger.info("[Heartbeat] New user detected — no prior memories in store")
                await asyncio.to_thread(
                    _mem_store.store,
                    "AIO session started for new user",
                    category="fact",
                    source="session",
                )
                logger.info("[Heartbeat] New user entry recorded in memory store")
            else:
                logger.info(f"[Heartbeat] Returning user — {len(_existing_memories)} prior memory entries found")
        except Exception as _nud_err:
            logger.debug(f"[Heartbeat] New user detection failed (non-critical): {_nud_err}")

    # Generate AIO opening greeting (no punctuation - voice output)
    # Interruptions disabled to allow client AEC (Acoustic Echo Cancellation) calibration
    try:
        await session.say(
            "Hi I am AIO welcome to your ecosystem infinite possibilities at our fingertips where should we start",
            allow_interruptions=False
        )
        logger.info("AIO greeting sent successfully")
    except Exception as e:
        logger.error(f"CRITICAL: session.say() failed: {e}")
        try:
            await _publish_error(str(e)[:200], code="agent_error", severity="high")
        except Exception:  # nosec B110 - error publishing must not block error handling
            pass

    # Start Gamma notification monitor — watches the module-level queue and proactively
    # speaks completion messages when background presentation generation finishes.
    # Stored in a variable to prevent garbage collection; cancelled naturally when the
    # enclosing coroutine (entrypoint) exits and the event loop tears down.
    async def _gamma_notification_monitor(session_ref):
        """Monitor gamma notification queue and proactively speak results.

        This runs as a persistent background task for the duration of the session.
        When Gamma generation completes (~45s), the background poller puts a
        notification into the queue and this monitor speaks it via session.say().
        """
        queue = get_notification_queue()
        while True:
            try:
                notification = await queue.get()
                message = notification.get("message", "")
                job_id = notification.get("job_id", "?")
                content_type = notification.get("content_type", "content")
                gamma_url = notification.get("gamma_url")

                if message:
                    logger.info(f"Gamma monitor: speaking notification job={job_id} content_type={content_type} has_url={bool(gamma_url)}")
                    try:
                        await session_ref.say(message, allow_interruptions=True)
                        logger.info(f"Gamma monitor: notification delivered job={job_id}")
                    except Exception as say_err:
                        logger.error(f"Gamma monitor: session.say() failed job={job_id}: {say_err}")
                        # Retry once after brief delay (session may be transitioning)
                        await asyncio.sleep(1.0)
                        try:
                            await session_ref.say(message, allow_interruptions=True)
                            logger.info(f"Gamma monitor: retry notification delivered job={job_id}")
                        except Exception as retry_err:
                            logger.error(f"Gamma monitor: retry also failed job={job_id}: {retry_err}")
                else:
                    logger.warning(f"Gamma monitor: empty message in notification job={job_id}")

            except asyncio.CancelledError:
                logger.info("Gamma notification monitor cancelled")
                break
            except Exception as e:
                logger.error(f"Gamma notification monitor error: {e}")
                await asyncio.sleep(0.5)  # Brief pause before continuing loop

    gamma_monitor_task = asyncio.create_task(_gamma_notification_monitor(session))
    logger.info("Gamma notification monitor started")

    # ── In-session heartbeat monitor ─────────────────────────────────────────
    # Runs every 4 seconds SILENTLY. Does not speak to the user unless a multi-step
    # tool task has stalled (no activity for 4+ seconds while objective is incomplete).
    # When stalled, injects a continuation instruction to resume the task.
    async def _heartbeat_monitor(session_ref, task_tracker_ref):
        """Background heartbeat: monitors tool execution and injects continuations.

        Design:
        - Runs every HEARTBEAT_INTERVAL seconds in the background
        - Checks TaskTracker.should_inject_continuation() — fires only when:
            * An active objective exists (user issued a task)
            * Tools were called (multi-step task, not idle chat)
            * Agent has been idle for 6+ seconds (stalled)
            * Max continuations (5) not exceeded
            * Minimum 8s cooldown since last continuation (prevents rapid-fire)
        - Uses session.generate_reply(instructions=...) to resume the LLM without
          injecting a raw say() call — this goes through the LLM for intelligent continuation
        - Falls back to session.say() if generate_reply is unavailable
        """
        HEARTBEAT_INTERVAL = 4.0  # Assess every 4 seconds
        logger.info("[Heartbeat] Background monitor started (interval=4s, stall=6s, max=5, gap=8s)")
        while True:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL)

                if not task_tracker_ref.should_inject_continuation():
                    continue  # Nothing to do — stay silent

                prompt = task_tracker_ref.get_continuation_prompt()
                logger.info(f"[Heartbeat] Stalled task detected — injecting continuation")

                try:
                    # generate_reply makes the LLM produce a new turn using the
                    # continuation instructions — intelligent, context-aware resumption
                    await session_ref.generate_reply(instructions=prompt)
                    logger.info("[Heartbeat] Continuation injected via generate_reply")
                except AttributeError:
                    # generate_reply not available in this SDK build — use say() fallback
                    logger.warning("[Heartbeat] generate_reply unavailable, using say() fallback")
                    try:
                        await session_ref.say(
                            "Let me continue working on that for you",
                            allow_interruptions=True
                        )
                    except Exception as say_err:
                        logger.error(f"[Heartbeat] say() fallback failed: {say_err}")
                except Exception as gen_err:
                    logger.error(f"[Heartbeat] generate_reply failed: {gen_err}")

            except asyncio.CancelledError:
                logger.info("[Heartbeat] Monitor cancelled — session ending")
                break
            except Exception as e:
                logger.error(f"[Heartbeat] Monitor error: {e}")
                await asyncio.sleep(1.0)  # Brief pause before continuing loop

    _heartbeat_task = asyncio.create_task(_heartbeat_monitor(session, _task_tracker))
    logger.info("[Heartbeat] In-session monitor started (4s interval, 4s stall threshold)")

    # CRITICAL: Keep the agent alive until the room closes
    # Without this, the entrypoint returns and the agent disconnects!
    # If we started without a client, wait for one to connect
    if not client_participant:
        logger.info("No client yet - waiting for Output Media client to connect...")
        # Keep checking for the client while the room is active
        while True:
            await asyncio.sleep(5.0)  # Check every 5 seconds

            # Check if room is still active (defensive comparison)
            try:
                if ctx.room.connection_state != rtc.ConnectionState.CONN_CONNECTED:
                    logger.info("Room disconnected, exiting")
                    break
            except Exception as e:
                logger.error(f"Error checking connection state: {e}")
                break

            # Look for client participant with defensive null checks
            client_found = False
            for participant in ctx.room.remote_participants.values():
                if participant is None:
                    continue
                identity = getattr(participant, 'identity', None)
                if identity is None:
                    continue
                if identity.lower().startswith('output-media-'):
                    logger.info(f"Client connected late: {identity}")
                    # Client finally connected - but we can't re-link the session
                    # The session was already started without a participant
                    # Audio from client won't be received, but at least agent stays alive
                    client_found = True
                    break

            if client_found:
                break
            # No client yet, keep waiting
    else:
        # Client was linked - wait for session to naturally close
        # This happens when the linked participant leaves
        logger.info("Session linked to client, waiting for session close...")

    # Keep agent alive until room closes
    # The room closes when all participants leave or it times out
    while ctx.room.connection_state == rtc.ConnectionState.CONN_CONNECTED:
        await asyncio.sleep(1.0)

    # Clean up session memory when session ends
    session_id = ctx.room.name or "livekit-agent"

    # Flush session to persistent memory (8s timeout — must not block disconnect)
    if _MEM_AVAILABLE and _session_writer is not None and _mem_capture is not None:
        try:
            # Build a brief session summary from STM stats
            from .tools.short_term_memory import get_session_stats
            _stats = get_session_stats(session_id)
            _summary = (
                f"Voice session ended. "
                f"Tools used: {_stats.get('total_entries', 0)} calls across "
                f"{len(_stats.get('categories', {}))} categories."
            )
            import os
            _mem_dir = os.environ.get("AIO_MEMORY_DIR", "/app/data/memory")
            # Flush auto-captured facts to SQLite
            _pending = _mem_capture.get_pending_facts()
            _fact_texts = [f for f, _ in _pending]
            # Write session log (with 8s timeout)
            await asyncio.wait_for(
                _session_writer.flush_session(_mem_dir, _summary, _fact_texts),
                timeout=8.0,
            )
            # Flush facts to store
            if _mem_store is not None and _pending:
                await _mem_capture.flush_to_store(_mem_store)
        except asyncio.TimeoutError:
            logger.warning("[Memory] Session flush timed out — session log skipped")
        except Exception as _e:
            logger.error("[Memory] Session flush failed: %s", _e)
        finally:
            _mem_capture.reset_session()

    cleared_count = clear_session_memory(session_id)
    logger.info(f"Cleared {cleared_count} session memory entries for {session_id}")

    logger.info("Agent session ended")


def main():
    """CLI entry point."""
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,  # Prewarm VAD on startup
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret,
            ws_url=settings.livekit_url,
            # Explicit dispatch mode: agent only joins when dispatched via AgentDispatchService
            # This is required for the n8n launcher workflow which uses CreateDispatch API
            agent_name="synrg-voice-agent",
        )
    )


if __name__ == "__main__":
    main()
