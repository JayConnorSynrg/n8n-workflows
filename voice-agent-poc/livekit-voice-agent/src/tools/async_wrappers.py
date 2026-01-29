"""AIO Ecosystem Tool Wrappers - Executive Assistant Edition

Architecture:
- Tools return natural language summaries, never JSON
- Descriptions guide LLM behavior for executive UX
- Background execution with conversational result announcements
"""
from typing import Optional

from livekit.agents import llm

from ..utils.async_tool_worker import get_worker
from ..utils.short_term_memory import (
    recall_by_category,
    recall_by_tool,
    recall_most_recent,
    get_memory_summary,
    ToolCategory,
)
from . import email_tool, database_tool, vector_store_tool, google_drive_tool, agent_context_tool


# =============================================================================
# EMAIL - WRITE OPERATION (REQUIRES CONFIRMATION)
# =============================================================================

@llm.function_tool(
    name="send_email",
    description="""Send an email. WRITE OPERATION - requires user confirmation.
    Before calling: Confirm recipient, subject, and message with user.
    After calling: Report sent status briefly.""",
)
async def send_email_async(
    to: str,
    subject: str,
    body: str,
    cc: Optional[str] = None,
) -> str:
    """Send email after confirmation."""
    worker = get_worker()
    if not worker:
        await email_tool.send_email_tool(to, subject, body, cc)
        return f"Email sent to {to.split('@')[0].replace('.', ' ').title()}"

    await worker.dispatch(
        tool_name="send_email",
        tool_func=email_tool.send_email_tool,
        kwargs={"to": to, "subject": subject, "body": body, "cc": cc},
    )
    return f"Sending email to {to.split('@')[0].replace('.', ' ').title()}"


# =============================================================================
# GOOGLE DRIVE - READ OPERATIONS (IMMEDIATE EXECUTION)
# =============================================================================

@llm.function_tool(
    name="search_drive",
    description="""Search Google Drive for documents. READ OPERATION - execute immediately.
    Before calling: Say "Searching Drive" or similar acknowledgment.
    After result: Summarize findings naturally - file names and count only.""",
)
async def search_documents_async(
    query: str,
    max_results: int = 5,
) -> str:
    """Search Drive documents."""
    worker = get_worker()
    if not worker:
        return await google_drive_tool.search_documents_tool(query, max_results)

    await worker.dispatch(
        tool_name="search_documents",
        tool_func=google_drive_tool.search_documents_tool,
        kwargs={"query": query, "max_results": max_results},
    )
    return "Searching Drive"


@llm.function_tool(
    name="get_file",
    description="""Retrieve a specific file from Google Drive. READ OPERATION.
    Requires file_id from a previous search.
    After result: Summarize document content briefly.""",
)
async def get_document_async(file_id: str) -> str:
    """Get document content."""
    worker = get_worker()
    if not worker:
        return await google_drive_tool.get_document_tool(file_id)

    await worker.dispatch(
        tool_name="get_document",
        tool_func=google_drive_tool.get_document_tool,
        kwargs={"file_id": file_id},
    )
    return "Retrieving document"


@llm.function_tool(
    name="list_files",
    description="""List files in Google Drive. READ OPERATION - execute immediately.
    Before calling: Say "Checking your files" or similar.
    After result: Read the file names naturally. Example: "You have 5 files: quarterly report, budget draft, meeting notes, project plan, and status update".""",
)
async def list_drive_files_async(max_results: int = 10) -> str:
    """List Drive files."""
    worker = get_worker()
    if not worker:
        return await google_drive_tool.list_drive_files_tool(max_results)

    await worker.dispatch(
        tool_name="list_drive_files",
        tool_func=google_drive_tool.list_drive_files_tool,
        kwargs={"max_results": max_results},
    )
    return "Checking your files"


# =============================================================================
# KNOWLEDGE BASE - MIXED OPERATIONS
# =============================================================================

@llm.function_tool(
    name="knowledge_base",
    description="""Search or store in knowledge base.
    For action="search": READ - execute immediately, summarize findings.
    For action="store": WRITE - requires user confirmation first.""",
)
async def vector_store_async(
    action: str,
    content: str,
    category: Optional[str] = None,
) -> str:
    """Knowledge base operations."""
    worker = get_worker()

    if action.lower() in ["search", "find", "query"]:
        if not worker:
            return await database_tool.query_database_tool(content)
        await worker.dispatch(
            tool_name="query_database",
            tool_func=database_tool.query_database_tool,
            kwargs={"query": content},
        )
        return "Searching knowledge base"
    else:
        if not worker:
            return await vector_store_tool.store_knowledge_tool(content, category or "general", None)
        await worker.dispatch(
            tool_name="store_knowledge",
            tool_func=vector_store_tool.store_knowledge_tool,
            kwargs={"content": content, "category": category or "general", "source": None},
        )
        return "Storing to knowledge base"


# =============================================================================
# DATABASE - READ OPERATION
# =============================================================================

@llm.function_tool(
    name="query_db",
    description="""Query the database. READ OPERATION - execute immediately.
    Summarize results conversationally.""",
)
async def database_query_async(query: str) -> str:
    """Query database."""
    worker = get_worker()
    if not worker:
        return await database_tool.query_database_tool(query)

    await worker.dispatch(
        tool_name="query_database",
        tool_func=database_tool.query_database_tool,
        kwargs={"query": query},
    )
    return "Querying database"


# =============================================================================
# SESSION CONTEXT - READ OPERATION
# =============================================================================

@llm.function_tool(
    name="check_context",
    description="""Check conversation context or history. READ OPERATION.
    Use to recall what was discussed earlier.""",
)
async def query_context_async(
    context_type: str,
    query: Optional[str] = None,
) -> str:
    """Query session context."""
    worker = get_worker()
    if not worker:
        return await agent_context_tool.query_context_tool(context_type, query)

    await worker.dispatch(
        tool_name="query_context",
        tool_func=agent_context_tool.query_context_tool,
        kwargs={"context_type": context_type, "query": query},
    )
    return "Checking context"


# =============================================================================
# MEMORY RECALL - READ OPERATIONS
# =============================================================================

@llm.function_tool(
    name="recall",
    description="""Recall previously retrieved data from session memory. READ OPERATION.
    Use to reference earlier search results, file listings, or document content
    without making another API call.""",
)
async def recall_data_async(
    category: Optional[str] = None,
    tool_name: Optional[str] = None,
    show_all: bool = False,
) -> str:
    """Recall from memory."""
    if show_all:
        return get_memory_summary()

    if tool_name:
        result = recall_by_tool(tool_name)
        if result:
            return _format_recall(result)
        return f"No recent {tool_name} data in memory"

    if category:
        try:
            cat = ToolCategory(category.lower())
            result = recall_by_category(cat)
            if result:
                return _format_recall(result)
        except ValueError:
            pass
        return f"No recent {category} data in memory"

    result = recall_most_recent()
    if result:
        return _format_recall(result)
    return "No data in memory yet"


def _format_recall(result: dict) -> str:
    """Format recalled data for voice output."""
    data = result.get("data")
    summary = result.get("summary", "Data found")

    if isinstance(data, list) and data:
        names = []
        for item in data[:5]:
            if isinstance(item, dict):
                name = item.get("name", item.get("title", item.get("file_name", "")))
                if name:
                    names.append(str(name))
        if names:
            return f"{summary}: {', '.join(names)}"

    if isinstance(data, dict):
        title = data.get("title", data.get("name", ""))
        if title:
            return f"{summary}: {title}"

    return summary


@llm.function_tool(
    name="memory_status",
    description="""Get overview of data currently stored in session memory.""",
)
async def memory_summary_async() -> str:
    """Memory summary."""
    return get_memory_summary()


@llm.function_tool(
    name="recall_drive",
    description="""Recall previous Drive operation results from memory.
    Use after list_files or search_drive to reference those results.""",
)
async def recall_drive_data_async(operation: Optional[str] = None) -> str:
    """Recall Drive data from memory."""
    return await google_drive_tool.recall_drive_data_tool(operation)


# =============================================================================
# TOOL REGISTRY
# =============================================================================

ASYNC_TOOLS = [
    send_email_async,
    search_documents_async,
    get_document_async,
    list_drive_files_async,
    recall_data_async,
    recall_drive_data_async,
    memory_summary_async,
    vector_store_async,
    database_query_async,
    query_context_async,
]
