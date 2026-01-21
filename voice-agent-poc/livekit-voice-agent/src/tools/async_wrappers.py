"""Async tool wrappers for AIO ecosystem.

Tools execute in background, returning instant acknowledgment.
The main agent handles all conversational aspects via system prompt.
Tool descriptions are minimal - conversation style lives in the agent prompt.
"""
from typing import Optional

from livekit.agents import llm

from ..utils.async_tool_worker import get_worker
from . import email_tool, database_tool, vector_store_tool, google_drive_tool, agent_context_tool


# =============================================================================
# EMAIL
# =============================================================================

@llm.function_tool(
    name="send_email",
    description="Send an email. Requires: to (email address), subject, body. Optional: cc.",
)
async def send_email_async(
    to: str,
    subject: str,
    body: str,
    cc: Optional[str] = None,
) -> str:
    """Dispatch email to background worker."""
    worker = get_worker()
    if not worker:
        return await email_tool.send_email_tool(to, subject, body, cc)

    task_id = await worker.dispatch(
        tool_name="send_email",
        tool_func=email_tool.send_email_tool,
        kwargs={"to": to, "subject": subject, "body": body, "cc": cc},
    )

    # Return human-speakable status for the agent
    recipient_name = to.split("@")[0].title()
    return f"Sending email to {recipient_name}..."


# =============================================================================
# KNOWLEDGE BASE SEARCH
# =============================================================================

@llm.function_tool(
    name="search_knowledge",
    description="Search the knowledge base. Requires: query (what to search for).",
)
async def query_database_async(query: str) -> str:
    """Dispatch database query to background worker."""
    worker = get_worker()
    if not worker:
        return await database_tool.query_database_tool(query)

    task_id = await worker.dispatch(
        tool_name="query_database",
        tool_func=database_tool.query_database_tool,
        kwargs={"query": query},
    )

    return "Searching the knowledge base..."


# =============================================================================
# KNOWLEDGE BASE STORE
# =============================================================================

@llm.function_tool(
    name="save_knowledge",
    description="Save information to knowledge base. Requires: content. Optional: type, source.",
)
async def store_knowledge_async(
    content: str,
    metadata_type: Optional[str] = None,
    metadata_source: Optional[str] = None,
) -> str:
    """Dispatch knowledge storage to background worker."""
    worker = get_worker()
    if not worker:
        return await vector_store_tool.store_knowledge_tool(
            content, metadata_type, metadata_source
        )

    task_id = await worker.dispatch(
        tool_name="store_knowledge",
        tool_func=vector_store_tool.store_knowledge_tool,
        kwargs={
            "content": content,
            "metadata_type": metadata_type,
            "metadata_source": metadata_source,
        },
    )

    return "Saving to knowledge base..."


# =============================================================================
# GOOGLE DRIVE - SEARCH
# =============================================================================

@llm.function_tool(
    name="search_documents",
    description="Search Google Drive for documents. Requires: query.",
)
async def search_documents_async(query: str) -> str:
    """Dispatch document search to background worker."""
    worker = get_worker()
    if not worker:
        return await google_drive_tool.search_documents_tool(query)

    task_id = await worker.dispatch(
        tool_name="search_documents",
        tool_func=google_drive_tool.search_documents_tool,
        kwargs={"query": query},
    )

    return "Searching your documents..."


# =============================================================================
# GOOGLE DRIVE - GET DOCUMENT
# =============================================================================

@llm.function_tool(
    name="get_document",
    description="Retrieve a specific document. Requires: file_id.",
)
async def get_document_async(file_id: str) -> str:
    """Dispatch document retrieval to background worker."""
    worker = get_worker()
    if not worker:
        return await google_drive_tool.get_document_tool(file_id)

    task_id = await worker.dispatch(
        tool_name="get_document",
        tool_func=google_drive_tool.get_document_tool,
        kwargs={"file_id": file_id},
    )

    return "Retrieving document..."


# =============================================================================
# GOOGLE DRIVE - LIST FILES
# =============================================================================

@llm.function_tool(
    name="list_files",
    description="List files in Google Drive. Optional: folder_name to filter.",
)
async def list_drive_files_async(folder_name: Optional[str] = None) -> str:
    """Dispatch file listing to background worker."""
    worker = get_worker()
    if not worker:
        return await google_drive_tool.list_drive_files_tool(folder_name)

    task_id = await worker.dispatch(
        tool_name="list_drive_files",
        tool_func=google_drive_tool.list_drive_files_tool,
        kwargs={"folder_name": folder_name},
    )

    return "Checking your files..."


# =============================================================================
# SESSION CONTEXT
# =============================================================================

@llm.function_tool(
    name="check_history",
    description="Check conversation history or session context. Requires: context_type. Optional: query.",
)
async def query_context_async(
    context_type: str,
    query: Optional[str] = None,
) -> str:
    """Dispatch context query to background worker."""
    worker = get_worker()
    if not worker:
        return await agent_context_tool.query_context_tool(context_type, query)

    task_id = await worker.dispatch(
        tool_name="query_context",
        tool_func=agent_context_tool.query_context_tool,
        kwargs={"context_type": context_type, "query": query},
    )

    return "Checking conversation history..."


# =============================================================================
# TOOL REGISTRY
# =============================================================================

ASYNC_TOOLS = [
    send_email_async,
    query_database_async,
    store_knowledge_async,
    search_documents_async,
    get_document_async,
    list_drive_files_async,
    query_context_async,
]
