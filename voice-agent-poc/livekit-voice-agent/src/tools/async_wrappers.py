"""Async tool wrappers that dispatch to background worker.

These tools return immediately with an acknowledgment,
while the actual work happens in the background.

Pattern:
1. User: "Send an email to John"
2. Agent: "I'm sending the email now. I'll let you know when it's done."
3. (Background: email is sent)
4. Agent: "Done! The email was sent successfully."
"""
from typing import Optional

from livekit.agents import llm

from ..utils.async_tool_worker import get_worker
from . import email_tool, database_tool, vector_store_tool, google_drive_tool, agent_context_tool


# =============================================================================
# EMAIL TOOL (Async)
# =============================================================================

@llm.function_tool(
    name="send_email_async",
    description="""Send an email in the background. Returns immediately - you'll be notified when complete.
    ALWAYS confirm recipient and subject with user before calling.
    After calling, say "I'm sending that email now, I'll let you know when it's done."
    DO NOT wait silently - keep the conversation going.""",
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
        # Fallback to sync if worker not available
        return await email_tool.send_email_tool(to, subject, body, cc)

    # Dispatch to background
    task_id = await worker.dispatch(
        tool_name="send_email",
        tool_func=email_tool.send_email_tool,
        kwargs={"to": to, "subject": subject, "body": body, "cc": cc},
    )

    return f"ASYNC_TASK:{task_id}:Email to {to} is being sent. I'll notify you when complete."


# =============================================================================
# DATABASE TOOL (Async)
# =============================================================================

@llm.function_tool(
    name="query_database_async",
    description="""Search the knowledge base in the background.
    After calling, say "I'm searching for that now."
    Continue the conversation - results will arrive shortly.""",
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

    return f"ASYNC_TASK:{task_id}:Searching the knowledge base. Results coming shortly."


# =============================================================================
# VECTOR STORE TOOL (Async)
# =============================================================================

@llm.function_tool(
    name="store_knowledge_async",
    description="""Save information to the knowledge base in the background.
    After calling, say "I'm saving that information now."
    Continue the conversation.""",
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

    return f"ASYNC_TASK:{task_id}:Saving that information. I'll confirm when done."


# =============================================================================
# GOOGLE DRIVE TOOLS (Async)
# =============================================================================

@llm.function_tool(
    name="search_documents_async",
    description="""Search Google Drive documents in the background.
    After calling, say "I'm searching your documents now."
    Continue the conversation - results will arrive shortly.""",
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

    return f"ASYNC_TASK:{task_id}:Searching your Google Drive. Results coming shortly."


@llm.function_tool(
    name="get_document_async",
    description="""Retrieve a document from Google Drive in the background.
    After calling, say "I'm retrieving that document now."
    Continue the conversation.""",
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

    return f"ASYNC_TASK:{task_id}:Retrieving the document. One moment."


@llm.function_tool(
    name="list_drive_files_async",
    description="""List files in Google Drive in the background.
    After calling, say "I'm checking your Drive files now."
    Continue the conversation.""",
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

    return f"ASYNC_TASK:{task_id}:Checking your Drive files. One moment."


# =============================================================================
# CONTEXT TOOLS (Async)
# =============================================================================

@llm.function_tool(
    name="query_context_async",
    description="""Query session context in the background.
    This is usually fast, but runs async for consistency.
    After calling, continue the conversation naturally.""",
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

    return f"ASYNC_TASK:{task_id}:Checking the context. One moment."


# =============================================================================
# EXPORT ALL ASYNC TOOLS
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
