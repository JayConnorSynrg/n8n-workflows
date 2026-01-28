"""AIO Ecosystem Tool Wrappers - Enterprise Edition

Tool Architecture:
1. Enterprise descriptions explain PURPOSE (not mechanics)
2. User-gated flow - always confirm before executing
3. Background execution with conversational results
4. Universal short-term memory - ALL tool results stored for cross-tool use

Flow Pattern:
  User: "Send an email to John"
  AIO: "I can send that email for you. Who should I address it to and what should it say?"
  User: "Tell him the meeting is moved to 3pm"
  AIO: "Got it. Send an email to John about the meeting moving to 3pm. Should I send it?"
  User: "Yes"
  AIO: "Sending now" [tool executes] "Done, email sent to John"

Cross-Tool Memory Pattern:
  User: "Search Drive for the budget report"
  AIO: "Found 3 documents. I have saved these to memory for later use."
  User: "Email a summary to Sarah"
  AIO: [Uses recalled Drive data] "I will email Sarah a summary. Should I send it?"
"""
from typing import Optional

from livekit.agents import llm

from ..utils.async_tool_worker import get_worker
from ..utils.short_term_memory import (
    store_tool_result,
    recall_by_category,
    recall_by_tool,
    recall_all,
    recall_most_recent,
    get_memory_summary,
    suggest_uses_for_category,
    ToolCategory,
)
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
# UNIVERSAL SHORT-TERM MEMORY TOOLS
# =============================================================================

@llm.function_tool(
    name="recall_data",
    description="""Universal Recall Tool: Access ANY previously retrieved data from short-term memory.
    Use this to reference recent results from Drive searches, database queries, vector store lookups,
    or any other tool without making another API call.

    This is the primary tool for cross-tool data reuse:
    - After a Drive search, recall that data to summarize in an email
    - After a database query, use results for vector store input
    - Recall the most recent action for follow-up questions

    This is a read-only operation that does NOT require user confirmation.

    Parameters:
    - category: Optional filter by source (drive, database, vector, email, context)
    - tool_name: Optional specific tool to recall from
    - show_all: Set to true to see summary of ALL available memory""",
)
async def recall_data_async(
    category: Optional[str] = None,
    tool_name: Optional[str] = None,
    show_all: bool = False,
) -> str:
    """Universal recall from short-term memory."""
    if show_all:
        return get_memory_summary()

    # Try specific tool first
    if tool_name:
        result = recall_by_tool(tool_name)
        if result:
            summary = result.get("summary", "Data found")
            data = result.get("data")
            suggested = result.get("suggested_uses", [])
            return f"From memory ({summary}): {_format_data_preview(data)}. Can be used for: {', '.join(suggested) if suggested else 'reference'}"
        return f"No recent data from {tool_name} in memory"

    # Try category
    if category:
        try:
            cat = ToolCategory(category.lower())
        except ValueError:
            cat = None

        if cat:
            result = recall_by_category(cat)
            if result:
                summary = result.get("summary", "Data found")
                data = result.get("data")
                suggested = result.get("suggested_uses", [])
                return f"From {category} memory ({summary}): {_format_data_preview(data)}. Can be used for: {', '.join(suggested) if suggested else 'reference'}"
            return f"No recent {category} data in memory"

    # Fall back to most recent
    result = recall_most_recent()
    if result:
        category = result.get("category", "unknown")
        summary = result.get("summary", "Data found")
        data = result.get("data")
        suggested = result.get("suggested_uses", [])
        return f"Most recent ({category}): {summary}. {_format_data_preview(data)}. Can be used for: {', '.join(suggested) if suggested else 'reference'}"

    return "No data in short-term memory. Try searching Drive, querying database, or using another tool first."


def _format_data_preview(data) -> str:
    """Format data for voice-friendly preview."""
    if data is None:
        return "No data"

    if isinstance(data, str):
        return data[:200] + "..." if len(data) > 200 else data

    if isinstance(data, list):
        if not data:
            return "Empty list"
        # Get first few items
        previews = []
        for item in data[:3]:
            if isinstance(item, dict):
                name = item.get("name", item.get("title", item.get("file_name", str(item)[:50])))
                previews.append(str(name))
            else:
                previews.append(str(item)[:50])
        suffix = f" and {len(data) - 3} more" if len(data) > 3 else ""
        return ", ".join(previews) + suffix

    if isinstance(data, dict):
        # Get key fields
        for key in ["title", "name", "summary", "content", "message"]:
            if key in data:
                val = str(data[key])
                return val[:200] + "..." if len(val) > 200 else val
        return str(data)[:200]

    return str(data)[:200]


@llm.function_tool(
    name="memory_summary",
    description="""Memory Summary Tool: Get a quick overview of all data currently in short-term memory.
    Use this to understand what context is available for follow-up actions.
    This is a read-only operation that does NOT require user confirmation.""",
)
async def memory_summary_async() -> str:
    """Get summary of all short-term memory."""
    return get_memory_summary()


# Legacy Drive-specific recall (for backwards compatibility)
@llm.function_tool(
    name="recall_drive_data",
    description="""Recall Drive Data: For accessing previously retrieved Drive data from short-term memory.
    Use this when you want to reference data from a recent search, file listing, or document retrieval.
    Consider using the more general 'recall_data' tool for cross-tool memory access.
    This is a read-only operation that does NOT require user confirmation.
    Optional: operation (search, list, get, analyze) to recall specific type.""",
)
async def recall_drive_data_async(
    operation: Optional[str] = None,
) -> str:
    """Recall Drive data from short-term memory - no API call needed."""
    return await google_drive_tool.recall_drive_data_tool(operation)


# =============================================================================
# TOOL REGISTRY
# =============================================================================

ASYNC_TOOLS = [
    send_email_async,
    search_documents_async,
    get_document_async,
    list_drive_files_async,
    recall_data_async,           # Universal recall (primary)
    recall_drive_data_async,     # Legacy Drive-specific recall
    memory_summary_async,        # Memory overview
    vector_store_async,
    database_query_async,
    query_context_async,
]
