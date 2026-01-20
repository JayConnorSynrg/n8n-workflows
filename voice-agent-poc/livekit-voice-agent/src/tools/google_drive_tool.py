"""Google Drive document repository tool via n8n webhook.

The n8n workflow provides read-only access to Google Drive documents:
- list: List files in Drive folder
- search: Search documents in database
- get: Retrieve file content by file_id
- analyze: AI analysis on documents
"""
import json
import uuid
from typing import Optional, Literal

import aiohttp
from livekit.agents import llm

from ..config import get_settings

settings = get_settings()


@llm.function_tool(
    name="search_documents",
    description="""Search for documents in the shared Google Drive folder.
    Use this to find files, meeting notes, or reference documents.
    Returns matching documents with titles and snippets.
    Takes about 5 to 15 seconds.""",
)
async def search_documents_tool(
    query: str,
    max_results: int = 5,
) -> str:
    """Search documents in Google Drive via n8n webhook.

    Args:
        query: Search query (searches titles and content)
        max_results: Maximum number of results to return

    Returns:
        Formatted list of matching documents or error message
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
                    documents = result.get("documents", result.get("results", []))
                    if not documents:
                        return "No documents found matching your query."

                    # Format results for voice
                    formatted = []
                    for i, doc in enumerate(documents[:max_results], 1):
                        title = doc.get("title", doc.get("name", f"Document {i}"))
                        snippet = doc.get("snippet", doc.get("content", ""))[:150]
                        formatted.append(f"{i}. {title}: {snippet}")

                    return f"Found {len(documents)} documents:\n" + "\n".join(formatted)
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
    Takes about 5 to 10 seconds.""",
)
async def get_document_tool(
    file_id: str,
) -> str:
    """Get full document content from Google Drive via n8n webhook.

    Args:
        file_id: The Google Drive file ID to retrieve

    Returns:
        Document content or error message
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
                    content = result.get("content", result.get("text", ""))
                    title = result.get("title", result.get("name", "Document"))

                    if not content:
                        return f"Document '{title}' appears to be empty."

                    # Truncate for voice response if too long
                    if len(content) > 2000:
                        content = content[:2000] + "... [truncated for voice]"

                    return f"Document: {title}\n\n{content}"
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
    Takes about 5 to 10 seconds.""",
)
async def list_drive_files_tool(
    max_results: int = 10,
) -> str:
    """List files in Google Drive via n8n webhook.

    Args:
        max_results: Maximum number of files to list

    Returns:
        Formatted list of files or error message
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
                    files = result.get("files", result.get("documents", []))
                    if not files:
                        return "No files found in Drive folder."

                    formatted = []
                    for i, f in enumerate(files[:max_results], 1):
                        name = f.get("name", f.get("title", f"File {i}"))
                        file_type = f.get("mimeType", f.get("type", "unknown"))
                        formatted.append(f"{i}. {name} ({file_type})")

                    return f"Found {len(files)} files:\n" + "\n".join(formatted)
                else:
                    error_msg = result.get("error", "Unknown error")
                    return f"Failed to list files: {error_msg}"

    except aiohttp.ClientError as e:
        return f"Network error listing files: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"
