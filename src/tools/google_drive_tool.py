"""Google Drive document repository tool via Composio SDK.

Provides read-only access to Google Drive documents:
- list: List files in Drive folder
- search: Search documents in database
- get: Retrieve file content by file_id

Memory Offer Pattern:
When data is retrieved it is saved to short-term memory for cross-tool use.
The voice agent should prompt: "Would you like me to remember this for later?"
"""
import asyncio
import logging
import os
from typing import Any, Dict, Optional

import aiohttp
from livekit.agents import llm

from ..utils.short_term_memory import (
    store_tool_result,
    recall_by_category,
    recall_by_tool,
    ToolCategory,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Composio client (lazy-initialised, module-level singleton)
# ---------------------------------------------------------------------------

_composio_client = None


def _get_composio_client():
    global _composio_client
    if _composio_client is None:
        try:
            from composio import Composio
            _composio_client = Composio(api_key=os.getenv("COMPOSIO_API_KEY"))
        except Exception as e:
            logger.warning(f"Could not initialise Composio client: {e}")
    return _composio_client


async def _composio_execute(slug: str, arguments: dict) -> dict:
    """Run a Composio Drive tool in a thread (SDK is sync) and return data dict."""
    def _run():
        client = _get_composio_client()
        if client is None:
            raise RuntimeError("Composio client unavailable")
        user_id = os.getenv("COMPOSIO_USER_ID", "default")
        return client.tools.execute(
            slug,
            arguments,
            user_id=user_id,
            dangerously_skip_version_check=True,
        )

    result = await asyncio.to_thread(_run)
    return result.get("data", {}) if isinstance(result, dict) else {}


async def _composio_search(query: str, max_results: int) -> list:
    """Search Drive via Composio GOOGLEDRIVE_FIND_FILE."""
    try:
        data = await _composio_execute(
            "GOOGLEDRIVE_FIND_FILE",
            {
                "q": f"name contains '{query}' or fullText contains '{query}'",
                "pageSize": max_results,
            },
        )
        files = data.get("files", [])
        return [
            {
                "file_name": f.get("name", ""),
                "title": f.get("name", ""),
                "snippet": f.get("mimeType", ""),
                "id": f.get("id", ""),
            }
            for f in files
        ]
    except Exception as e:
        logger.error(f"Composio Drive search failed: {e}")
        return []


async def _composio_list(max_results: int) -> list:
    """List Drive files via Composio GOOGLEDRIVE_FIND_FILE."""
    try:
        data = await _composio_execute(
            "GOOGLEDRIVE_FIND_FILE",
            {"q": "trashed = false", "pageSize": max_results},
        )
        return data.get("files", [])
    except Exception as e:
        logger.error(f"Composio Drive list failed: {e}")
        return []


async def _composio_get(file_id: str) -> dict:
    """Get document content via Composio GOOGLEDRIVE_DOWNLOAD_FILE."""
    try:
        data = await _composio_execute(
            "GOOGLEDRIVE_DOWNLOAD_FILE",
            {"file_id": file_id, "mime_type": "text/plain"},
        )
        content_obj = data.get("downloaded_file_content", {})
        content = content_obj.get("content", "")
        s3url = content_obj.get("s3url", "")

        # Some file types return an S3 URL instead of inline content
        if not content and s3url:
            async with aiohttp.ClientSession() as session:
                async with session.get(s3url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    content = await resp.text()

        return {
            "extracted_text": content,
            "content": content,
            "title": data.get("name", "Document"),
        }
    except Exception as e:
        logger.error(f"Composio Drive get failed: {e}")
        return {}


# ---------------------------------------------------------------------------
# Short-term memory helpers
# ---------------------------------------------------------------------------

def _store_to_short_term_memory(
    operation: str,
    data: Any,
    summary: str,
    session_id: str = "livekit-agent"
) -> None:
    """Store retrieved data to short-term memory for cross-tool access."""
    store_tool_result(
        tool_name=f"google_drive_{operation}",
        operation=operation,
        data=data,
        summary=summary,
        session_id=session_id,
        suggested_uses=["email_summary", "vector_store", "reference", "analysis"],
    )


def get_short_term_memory(
    operation: Optional[str] = None,
    session_id: str = "livekit-agent"
) -> Optional[Dict[str, Any]]:
    """Retrieve data from short-term memory for cross-tool use.

    Args:
        operation: Specific operation to retrieve (list, search, get, analyze)
                   If None, returns most recent retrieval
        session_id: Session identifier

    Returns:
        Cached data or None if not found/expired
    """
    if operation:
        return recall_by_tool(f"google_drive_{operation}", operation, session_id)

    # Fall back to category-level recall
    return recall_by_category(ToolCategory.DRIVE, session_id)


# ---------------------------------------------------------------------------
# LLM-registered tools
# ---------------------------------------------------------------------------

@llm.function_tool(
    name="search_documents",
    description="""Search for documents in the shared Google Drive folder.
    Use this to find files, meeting notes, or reference documents.
    Returns matching documents with titles and snippets.
    After results are shown, offer to save them to short-term memory for later use.""",
)
async def search_documents_tool(
    query: str,
    max_results: int = 5,
    save_to_memory: bool = True,
) -> str:
    documents = await _composio_search(query, max_results)

    if not documents:
        return "No documents found matching your query."

    formatted = []
    for i, doc in enumerate(documents[:max_results], 1):
        title = doc.get("file_name", doc.get("title", doc.get("name", f"Document {i}")))
        snippet = doc.get("snippet", doc.get("extracted_text", ""))[:150]
        formatted.append(f"{i}. {title}: {snippet}")

    summary = f"Found {len(documents)} documents for '{query}'"
    if save_to_memory:
        _store_to_short_term_memory("search", documents, summary)

    return f"Found {len(documents)} documents:\n" + "\n".join(formatted)


@llm.function_tool(
    name="get_document",
    description="""Retrieve the full content of a specific document from Google Drive.
    Use this after searching to get the complete document text.
    Requires the file ID from a previous search.
    Auto-saves to short-term memory for use in other tools like email or vector store.""",
)
async def get_document_tool(
    file_id: str,
    save_to_memory: bool = True,
) -> str:
    data = await _composio_get(file_id)

    if not data:
        return f"Failed to retrieve document '{file_id}'."

    content = data.get("extracted_text", data.get("content", data.get("text", "")))
    title = data.get("file_name", data.get("title", data.get("name", "Document")))

    if not content:
        return f"Document '{title}' appears to be empty."

    summary = f"Retrieved document: {title}"
    if save_to_memory:
        _store_to_short_term_memory("get", {
            "file_id": file_id,
            "title": title,
            "content": content,
            "full_data": data,
        }, summary)

    display_content = content
    if len(content) > 2000:
        display_content = content[:2000] + "... [truncated for voice]"

    return f"Document: {title}\n\n{display_content}"


@llm.function_tool(
    name="list_drive_files",
    description="""List files in the shared Google Drive folder.
    Use this to see what documents are available.
    Returns file names and types.
    Auto-saves file list to short-term memory for reference.""",
)
async def list_drive_files_tool(
    max_results: int = 10,
    save_to_memory: bool = True,
) -> str:
    files = await _composio_list(max_results)

    if not files:
        return "No files found in Drive folder."

    summary = f"Found {len(files)} files in Drive"
    if save_to_memory:
        _store_to_short_term_memory("list", files, summary)

    formatted = []
    for i, f in enumerate(files[:max_results], 1):
        name = f.get("name", f.get("title", f"File {i}"))
        file_type = f.get("mimeType", f.get("type", "unknown"))
        formatted.append(f"{i}. {name} ({file_type})")

    return f"Found {len(files)} files:\n" + "\n".join(formatted)


@llm.function_tool(
    name="recall_drive_data",
    description="""Recall previously retrieved Drive data from short-term memory.
    Use this to access data from a recent search, file listing, or document retrieval
    without making another API call. Perfect for follow-up questions or cross-tool use.""",
)
async def recall_drive_data_tool(
    operation: Optional[str] = None,
) -> str:
    """Recall Drive data from short-term memory.

    Args:
        operation: Specific operation to recall (search, list, get, analyze)
                   If None, returns most recent retrieval

    Returns:
        Previously retrieved data or message if nothing found
    """
    memory = get_short_term_memory(operation)

    if not memory:
        if operation:
            return f"No recent {operation} data in memory. Try running the operation first."
        return "No recent Drive data in short-term memory. Try searching or listing files first."

    stored_op = memory.get("operation", "unknown")
    summary = memory.get("summary", "Data retrieved")
    data = memory.get("data")

    if stored_op == "search":
        docs = data if isinstance(data, list) else []
        doc_names = [d.get("file_name", d.get("title", "Unknown")) for d in docs[:5]]
        return f"From memory ({summary}): {', '.join(doc_names)}"

    elif stored_op == "list":
        files = data if isinstance(data, list) else []
        file_names = [f.get("name", f.get("title", "Unknown")) for f in files[:5]]
        return f"From memory ({summary}): {', '.join(file_names)}"

    elif stored_op == "get":
        if isinstance(data, dict):
            title = data.get("title", "Document")
            content = data.get("content", "")[:500]
            return f"From memory - {title}: {content}..."

    return f"From memory: {summary}"
