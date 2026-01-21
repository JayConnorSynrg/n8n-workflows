"""AIO Ecosystem Tool Wrappers - Enterprise Edition

Tool Architecture:
1. Enterprise descriptions explain PURPOSE (not mechanics)
2. User-gated flow - always confirm before executing
3. Background execution with conversational results

Flow Pattern:
  User: "Send an email to John"
  AIO: "I can send that email for you. Who should I address it to and what should it say?"
  User: "Tell him the meeting is moved to 3pm"
  AIO: "Got it. Send an email to John about the meeting moving to 3pm. Should I send it?"
  User: "Yes"
  AIO: "Sending now" [tool executes] "Done, email sent to John"
"""
from typing import Optional

from livekit.agents import llm

from ..utils.async_tool_worker import get_worker
from . import email_tool, database_tool, vector_store_tool, google_drive_tool, agent_context_tool


# =============================================================================
# EMAIL COMMUNICATION TOOL
# =============================================================================

@llm.function_tool(
    name="email_tool",
    description="""Email Communication Tool: For sending emails to contacts and team members.
    Use this when the user wants to send a message to someone via email.

    GATING REQUIRED - This is a WRITE operation that sends real emails.
    You MUST confirm with the user before executing:
    1. Confirm the recipient email address
    2. Confirm the subject line
    3. Confirm the message content
    4. Ask "should I send this email" and wait for yes/confirmation

    Required: to (email address), subject, body. Optional: cc.""",
)
async def send_email_async(
    to: str,
    subject: str,
    body: str,
    cc: Optional[str] = None,
) -> str:
    """Execute email send after user confirmation."""
    worker = get_worker()
    if not worker:
        result = await email_tool.send_email_tool(to, subject, body, cc)
        return f"Email sent to {to.split('@')[0].title()}"

    await worker.dispatch(
        tool_name="send_email",
        tool_func=email_tool.send_email_tool,
        kwargs={"to": to, "subject": subject, "body": body, "cc": cc},
    )

    recipient_name = to.split("@")[0].replace(".", " ").title()
    return f"Email is being sent to {recipient_name}"


# =============================================================================
# GOOGLE DRIVE TOOL
# =============================================================================

@llm.function_tool(
    name="google_drive_tool",
    description="""Google Drive Tool: For searching the Google Drive document repository.
    Use this when the user wants to find documents, files, or stored information in Drive.
    Can search by keywords, file names, or content.
    This is a read-only search operation that does not require user confirmation.
    Required: query (what to search for). Optional: max_results (default 5).""",
)
async def search_documents_async(query: str, max_results: int = 5) -> str:
    """Execute Drive search - read-only, no confirmation needed."""
    worker = get_worker()
    if not worker:
        return await google_drive_tool.search_documents_tool(query, max_results)

    await worker.dispatch(
        tool_name="search_documents",
        tool_func=google_drive_tool.search_documents_tool,
        kwargs={"query": query, "max_results": max_results},
    )

    return f"Searching Drive for {query}"


@llm.function_tool(
    name="drive_file_retrieval",
    description="""Drive File Retrieval: For getting a specific document from Google Drive.
    Use when the user wants to open or read a particular file.
    This is a read-only operation that does not require user confirmation.
    Required: file_id (the document identifier from a previous search).""",
)
async def get_document_async(file_id: str) -> str:
    """Execute document retrieval - read-only, no confirmation needed."""
    worker = get_worker()
    if not worker:
        return await google_drive_tool.get_document_tool(file_id)

    await worker.dispatch(
        tool_name="get_document",
        tool_func=google_drive_tool.get_document_tool,
        kwargs={"file_id": file_id},
    )

    return "Retrieving the document"


@llm.function_tool(
    name="drive_file_listing",
    description="""Drive File Listing: For listing files in Google Drive.
    Use when the user wants to see what files are available in Drive.
    This is a read-only operation that does not require user confirmation.
    Optional: max_results (default 10).""",
)
async def list_drive_files_async(max_results: int = 10) -> str:
    """Execute file listing - read-only, no confirmation needed."""
    worker = get_worker()
    if not worker:
        return await google_drive_tool.list_drive_files_tool(max_results)

    await worker.dispatch(
        tool_name="list_drive_files",
        tool_func=google_drive_tool.list_drive_files_tool,
        kwargs={"max_results": max_results},
    )

    return "Listing files in Drive"


# =============================================================================
# VECTOR DATABASE TOOL
# =============================================================================

@llm.function_tool(
    name="vector_database_tool",
    description="""Vector Database Tool: For storing and retrieving semantic data.
    Use this for saving important information that needs to be recalled later,
    or for searching through stored knowledge using natural language queries.

    For SEARCH operations (action=search/find/query/retrieve):
    - This is read-only and does NOT require user confirmation
    - Required: action, content (the search query)

    For STORE operations (action=store/save/add):
    - This WRITES data and REQUIRES user confirmation before executing
    - Confirm what content will be stored and ask "should I save this"
    - Required: action, content (what to save)
    - Optional: category (meeting_notes, reference, or general)""",
)
async def vector_store_async(
    action: str,
    content: str,
    category: Optional[str] = None,
) -> str:
    """Execute vector database operation with proper gating."""
    worker = get_worker()

    if action.lower() in ["search", "find", "query", "retrieve"]:
        # READ operation - no confirmation needed
        if not worker:
            return await database_tool.query_database_tool(content)

        await worker.dispatch(
            tool_name="query_database",
            tool_func=database_tool.query_database_tool,
            kwargs={"query": content},
        )
        return f"Searching knowledge base for {content[:50]}"

    else:  # store/save - WRITE operation, should have been confirmed by user
        if not worker:
            return await vector_store_tool.store_knowledge_tool(content, category or "general", None)

        await worker.dispatch(
            tool_name="store_knowledge",
            tool_func=vector_store_tool.store_knowledge_tool,
            kwargs={"content": content, "category": category or "general", "source": None},
        )
        return "Saving to knowledge base"


# =============================================================================
# CENTRALIZED DATABASE TOOL
# =============================================================================

@llm.function_tool(
    name="database_query_tool",
    description="""Centralized Database Query Tool: For retrieving data from the centralized database.
    Use this for structured data operations and records lookup.
    Supports natural language queries that get translated to database operations.

    This is a READ-ONLY search operation that does NOT require user confirmation.
    Simply execute the query when the user asks for information.

    Required: query (what to find).""",
)
async def database_query_async(query: str) -> str:
    """Execute database query - read-only, no confirmation needed."""
    worker = get_worker()
    if not worker:
        return await database_tool.query_database_tool(query)

    await worker.dispatch(
        tool_name="query_database",
        tool_func=database_tool.query_database_tool,
        kwargs={"query": query},
    )

    return f"Querying database for {query[:50]}"


# =============================================================================
# SESSION CONTEXT TOOL
# =============================================================================

@llm.function_tool(
    name="session_history_tool",
    description="""Session History Tool: For checking conversation context and previous interactions.
    Use this to recall what was discussed earlier in the session or to maintain continuity.

    This is a READ-ONLY operation that does NOT require user confirmation.
    Use it to check context before responding to user questions.

    Required: context_type (session_context, tool_history, global_context, search_history, custom_query).
    Optional: query (for search_history or custom_query types).""",
)
async def query_context_async(
    context_type: str,
    query: Optional[str] = None,
) -> str:
    """Execute context query - read-only, no confirmation needed."""
    worker = get_worker()
    if not worker:
        return await agent_context_tool.query_context_tool(context_type, query)

    await worker.dispatch(
        tool_name="query_context",
        tool_func=agent_context_tool.query_context_tool,
        kwargs={"context_type": context_type, "query": query},
    )

    return "Checking session history"


# =============================================================================
# TOOL REGISTRY
# =============================================================================

ASYNC_TOOLS = [
    send_email_async,
    search_documents_async,
    get_document_async,
    list_drive_files_async,
    vector_store_async,
    database_query_async,
    query_context_async,
]
