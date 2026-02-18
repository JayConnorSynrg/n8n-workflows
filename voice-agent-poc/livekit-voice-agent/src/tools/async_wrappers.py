"""AIO Ecosystem Tool Wrappers - Executive Assistant Edition

Architecture:
- Tools return natural language summaries, never JSON
- Descriptions guide LLM behavior for executive UX
- Background execution with conversational result announcements
- Tool names use camelCase (no underscores) to prevent TTS saying "underscore"
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
from . import email_tool, database_tool, vector_store_tool, google_drive_tool, agent_context_tool, contact_tool


# =============================================================================
# EMAIL - WRITE OPERATION (REQUIRES CONFIRMATION)
# =============================================================================

@llm.function_tool(
    name="sendEmail",
    description="Send an email. Confirm recipient subject and message with user first.",
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
        tool_name="sendEmail",
        tool_func=email_tool.send_email_tool,
        kwargs={"to": to, "subject": subject, "body": body, "cc": cc},
    )
    return f"Sending email to {to.split('@')[0].replace('.', ' ').title()}"


# =============================================================================
# GOOGLE DRIVE - READ OPERATIONS (IMMEDIATE EXECUTION)
# =============================================================================

@llm.function_tool(
    name="searchDrive",
    description="Search Google Drive for documents by keyword or topic. Summarize findings for the user.",
)
async def search_documents_async(
    query: str,
    max_results: int = 5,
) -> str:
    """Search Drive documents - runs synchronously for immediate results."""
    return await google_drive_tool.search_documents_tool(query, max_results)


@llm.function_tool(
    name="getFile",
    description="Retrieve a specific file from Google Drive by file ID from a previous search.",
)
async def get_document_async(file_id: str) -> str:
    """Get document content - runs synchronously for immediate results."""
    return await google_drive_tool.get_document_tool(file_id)


@llm.function_tool(
    name="listFiles",
    description="List recent files in Google Drive. Summarize results naturally.",
)
async def list_drive_files_async(max_results: int = 10) -> str:
    """List Drive files - runs synchronously for immediate results."""
    return await google_drive_tool.list_drive_files_tool(max_results)


# =============================================================================
# KNOWLEDGE BASE - MIXED OPERATIONS
# =============================================================================

@llm.function_tool(
    name="knowledgeBase",
    description="Search or store in the knowledge base. For search execute immediately. For store confirm with user first.",
)
async def vector_store_async(
    action: str,
    content: str,
    category: Optional[str] = None,
) -> str:
    """Knowledge base operations."""
    if action.lower() in ["search", "find", "query"]:
        return await database_tool.query_database_tool(content)
    else:
        worker = get_worker()
        if not worker:
            return await vector_store_tool.store_knowledge_tool(content, category or "general", None)
        await worker.dispatch(
            tool_name="storeKnowledge",
            tool_func=vector_store_tool.store_knowledge_tool,
            kwargs={"content": content, "category": category or "general", "source": None},
        )
        return "Storing to knowledge base"


# =============================================================================
# DATABASE - READ OPERATION
# =============================================================================

@llm.function_tool(
    name="queryDatabase",
    description="Query the database for records analytics or lookups. Returns results immediately.",
)
async def database_query_async(query: str) -> str:
    """Query database - runs synchronously for immediate results."""
    return await database_tool.query_database_tool(query)


# =============================================================================
# SESSION CONTEXT - READ OPERATION
# =============================================================================

@llm.function_tool(
    name="checkContext",
    description="Check conversation context or session history to recall what was discussed earlier.",
)
async def query_context_async(
    context_type: str,
    query: Optional[str] = None,
) -> str:
    """Query session context - runs synchronously for immediate results."""
    return await agent_context_tool.query_context_tool(context_type, query)


# =============================================================================
# MEMORY RECALL - READ OPERATIONS
# =============================================================================

@llm.function_tool(
    name="recall",
    description="Recall previously retrieved data from session memory without making another call.",
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
    name="memoryStatus",
    description="Get overview of data currently stored in session memory.",
)
async def memory_summary_async() -> str:
    """Memory summary."""
    return get_memory_summary()


@llm.function_tool(
    name="recallDrive",
    description="Recall previous Drive search or listing results from memory.",
)
async def recall_drive_data_async(operation: Optional[str] = None) -> str:
    """Recall Drive data from memory."""
    return await google_drive_tool.recall_drive_data_tool(operation)


# =============================================================================
# CONTACTS - MIXED OPERATIONS
# =============================================================================

@llm.function_tool(
    name="addContact",
    description="Add a new contact. Uses 3 step confirmation: spell name then confirm, spell email then confirm, then save.",
)
async def add_contact_async(
    name: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    company: Optional[str] = None,
    notes: Optional[str] = None,
    gate: int = 1,
    name_confirmed: bool = False,
    email_confirmed: bool = False,
) -> str:
    """Add contact with multi-gate confirmation - runs synchronously for immediate gate response."""
    return await contact_tool.add_contact_tool(
        name=name,
        email=email,
        phone=phone,
        company=company,
        notes=notes,
        gate=gate,
        name_confirmed=name_confirmed,
        email_confirmed=email_confirmed,
    )


@llm.function_tool(
    name="getContact",
    description="Look up a contact by name email or ID. Returns contact details immediately.",
)
async def get_contact_async(
    query: Optional[str] = None,
    name: Optional[str] = None,
    email: Optional[str] = None,
    contact_id: Optional[str] = None,
) -> str:
    """Get contact - runs synchronously for immediate results."""
    return await contact_tool.get_contact_tool(
        query=query,
        name=name,
        email=email,
        contact_id=contact_id,
    )


@llm.function_tool(
    name="searchContacts",
    description="Search contacts by name email or company. Returns matching contacts immediately.",
)
async def search_contacts_async(query: str) -> str:
    """Search contacts - runs synchronously for immediate results."""
    return await contact_tool.search_contacts_tool(query)


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
    # Contacts
    add_contact_async,
    get_contact_async,
    search_contacts_async,
]
