"""Google Drive document repository tool via n8n webhook.

The n8n workflow provides read-only access to Google Drive documents:
- list: List files in Drive folder
- search: Search documents in database
- get: Retrieve file content by file_id
- analyze: AI analysis on documents

Memory Offer Pattern:
When data is retrieved, the workflow returns a memory_offer field that
indicates the data can be saved to short-term memory for cross-tool use.
The voice agent should prompt: "Would you like me to remember this for later?"
"""
import json
import logging
import uuid
from typing import Any, Dict, Optional, Literal

import aiohttp
from livekit.agents import llm

from ..config import get_settings
from ..utils.short_term_memory import (
    store_tool_result,
    recall_by_category,
    recall_by_tool,
    ToolCategory,
)

logger = logging.getLogger(__name__)
settings = get_settings()


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
    """Search documents in Google Drive via n8n webhook.

    Args:
        query: Search query (searches titles and content)
        max_results: Maximum number of results to return
        save_to_memory: Auto-save results to short-term memory (default True)

    Returns:
        Formatted list of matching documents with memory offer
    """
    webhook_url = f"{settings.n8n_webhook_base_url}/drive-document-repo"

    intent_id = f"lk_{uuid.uuid4().hex[:12]}"
    payload = {
        "intent_id": intent_id,
        "session_id": "livekit-agent",
        "operation": "search",
        "query": query,
        "limit": max_results,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                result = await response.json()

                if response.status == 200:
                    # Handle n8n response format: {result: {...}}
                    inner_result = result.get("result", result)
                    data = inner_result if isinstance(inner_result, dict) else result
                    documents = data.get("results", data.get("documents", data.get("files", [])))
                    memory_offer = result.get("memory_offer", {})

                    if not documents:
                        return "No documents found matching your query."

                    # Format results for voice
                    formatted = []
                    for i, doc in enumerate(documents[:max_results], 1):
                        title = doc.get("file_name", doc.get("title", doc.get("name", f"Document {i}")))
                        snippet = doc.get("snippet", doc.get("extracted_text", ""))[:150]
                        formatted.append(f"{i}. {title}: {snippet}")

                    # Auto-save to short-term memory if enabled
                    summary = memory_offer.get("summary", f"Found {len(documents)} documents")
                    if save_to_memory:
                        _store_to_short_term_memory("search", documents, summary)

                    response_text = f"Found {len(documents)} documents:\n" + "\n".join(formatted)

                    # Add memory offer hint for agent
                    if memory_offer.get("available"):
                        response_text += f"\n\n[Memory: {summary}. Available for vector store, email summary, or reference.]"

                    return response_text
                else:
                    error_msg = result.get("error", "Unknown error")
                    return f"Search failed: {error_msg}"

    except aiohttp.ClientError as e:
        return f"Network error searching documents: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"


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
    """Get full document content from Google Drive via n8n webhook.

    Args:
        file_id: The Google Drive file ID to retrieve
        save_to_memory: Auto-save content to short-term memory (default True)

    Returns:
        Document content with memory offer
    """
    webhook_url = f"{settings.n8n_webhook_base_url}/drive-document-repo"

    intent_id = f"lk_{uuid.uuid4().hex[:12]}"
    payload = {
        "intent_id": intent_id,
        "session_id": "livekit-agent",
        "operation": "get",
        "file_id": file_id,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                result = await response.json()

                if response.status == 200:
                    # Handle n8n response format: {result: {...}}
                    inner_result = result.get("result", result)
                    data = inner_result if isinstance(inner_result, dict) else result
                    memory_offer = result.get("memory_offer", {})

                    content = data.get("extracted_text", data.get("content", data.get("text", "")))
                    title = data.get("file_name", data.get("title", data.get("name", "Document")))

                    if not content:
                        return f"Document '{title}' appears to be empty."

                    # Auto-save full document to short-term memory
                    summary = memory_offer.get("summary", f"Retrieved document: {title}")
                    if save_to_memory:
                        _store_to_short_term_memory("get", {
                            "file_id": file_id,
                            "title": title,
                            "content": content,
                            "full_data": data,
                        }, summary)

                    # Truncate for voice response if too long
                    display_content = content
                    if len(content) > 2000:
                        display_content = content[:2000] + "... [truncated for voice]"

                    response_text = f"Document: {title}\n\n{display_content}"

                    # Add memory offer hint for agent
                    if memory_offer.get("available"):
                        suggested_uses = memory_offer.get("suggested_uses", [])
                        uses_str = ", ".join(suggested_uses) if suggested_uses else "vector store, email, analysis"
                        response_text += f"\n\n[Memory: Full document saved. Available for {uses_str}.]"

                    return response_text
                else:
                    error_msg = result.get("error", "Unknown error")
                    return f"Failed to retrieve document: {error_msg}"

    except aiohttp.ClientError as e:
        return f"Network error retrieving document: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"


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
    """List files in Google Drive via n8n webhook.

    Args:
        max_results: Maximum number of files to list
        save_to_memory: Auto-save file list to short-term memory (default True)

    Returns:
        Formatted list of files with memory offer
    """
    webhook_url = f"{settings.n8n_webhook_base_url}/drive-document-repo"

    intent_id = f"lk_{uuid.uuid4().hex[:12]}"
    payload = {
        "intent_id": intent_id,
        "session_id": "livekit-agent",
        "operation": "list",
        "limit": max_results,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                result = await response.json()

                if response.status == 200:
                    # Handle n8n response format: {result: {files: [...], count: N}}
                    # Also supports legacy format: {files: [...]}
                    inner_result = result.get("result", result)
                    data = inner_result if isinstance(inner_result, dict) else result
                    memory_offer = result.get("memory_offer", {})

                    files = data.get("files", data.get("documents", []))
                    file_count = data.get("count", len(files))

                    if not files:
                        return "No files found in Drive folder."

                    # Auto-save to short-term memory
                    summary = memory_offer.get("summary", f"Found {file_count} files in Drive")
                    if save_to_memory:
                        _store_to_short_term_memory("list", files, summary)

                    formatted = []
                    for i, f in enumerate(files[:max_results], 1):
                        name = f.get("name", f.get("title", f"File {i}"))
                        file_type = f.get("mimeType", f.get("type", "unknown"))
                        formatted.append(f"{i}. {name} ({file_type})")

                    response_text = f"Found {file_count} files:\n" + "\n".join(formatted)

                    # Add memory offer hint for agent
                    if memory_offer.get("available"):
                        response_text += f"\n\n[Memory: {summary}. Available for reference or email summary.]"

                    return response_text
                else:
                    error_msg = result.get("error", "Unknown error")
                    return f"Failed to list files: {error_msg}"

    except aiohttp.ClientError as e:
        return f"Network error listing files: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"


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

    # Format based on operation type
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
