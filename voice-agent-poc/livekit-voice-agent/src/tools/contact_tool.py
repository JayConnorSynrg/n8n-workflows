"""Contact management tool for managing contacts via n8n webhook.

The n8n workflow implements multi-gate confirmation for add_contact:
1. Gate 1: Confirm name spelling (phonetic)
2. Gate 2: Confirm email spelling (character-by-character)
3. Gate 3: Save to database

Read operations (get_contact, search_contacts) execute immediately.
"""
import json
import uuid
from typing import Optional, Dict, Any

import aiohttp
from livekit.agents import llm

from ..config import get_settings

settings = get_settings()


async def _call_contact_webhook(
    operation: str,
    session_id: str = "livekit-agent",
    **kwargs,
) -> Dict[str, Any]:
    """Call the contact management webhook.

    Args:
        operation: One of add_contact, get_contact, search_contacts
        session_id: Session identifier
        **kwargs: Additional parameters for the operation

    Returns:
        Response dictionary from the webhook
    """
    webhook_url = f"{settings.n8n_webhook_base_url}/manage-contacts"

    payload = {
        "operation": operation,
        "session_id": session_id,
        **kwargs,
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
                return result
    except aiohttp.ClientError as e:
        return {"success": False, "error": str(e), "voice_response": f"Network error: {str(e)}"}
    except Exception as e:
        return {"success": False, "error": str(e), "voice_response": f"Error: {str(e)}"}


@llm.function_tool(
    name="add_contact",
    description="""Add a new contact. WRITE OPERATION with multi-gate confirmation.
    This tool uses a multi-step process:
    1. First call: Returns name spelled phonetically for confirmation
    2. Second call (with name_confirmed=True): Returns email spelled out for confirmation
    3. Third call (with email_confirmed=True): Saves the contact

    IMPORTANT: You MUST spell back the name and email to the user and get their
    explicit confirmation before proceeding to the next gate.

    Parameters for each gate:
    - Gate 1: name, email (optional: phone, company, notes)
    - Gate 2: name, name_confirmed=True, email, phone, company
    - Gate 3: name, name_confirmed=True, email, email_confirmed=True, phone, company""",
)
async def add_contact_tool(
    name: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    company: Optional[str] = None,
    notes: Optional[str] = None,
    gate: int = 1,
    name_confirmed: bool = False,
    email_confirmed: bool = False,
) -> str:
    """Add a new contact with multi-gate confirmation.

    Args:
        name: Contact's full name
        email: Email address
        phone: Phone number (optional)
        company: Company name (optional)
        notes: Additional notes (optional)
        gate: Current gate number (1, 2, or 3)
        name_confirmed: Set True after user confirms name spelling
        email_confirmed: Set True after user confirms email spelling

    Returns:
        Voice response with confirmation request or success message
    """
    result = await _call_contact_webhook(
        operation="add_contact",
        name=name,
        email=email,
        phone=phone,
        company=company,
        notes=notes,
        gate=gate,
        name_confirmed=name_confirmed,
        email_confirmed=email_confirmed,
    )

    if result.get("requires_confirmation"):
        # Return confirmation prompt with phonetic spelling
        return result.get("voice_response", "Please confirm the spelling.")

    if result.get("success"):
        return result.get("voice_response", f"Contact {name} saved successfully.")

    return result.get("voice_response", f"Failed to save contact: {result.get('error', 'Unknown error')}")


@llm.function_tool(
    name="get_contact",
    description="""Look up a specific contact by name, email, or ID. READ OPERATION.
    Execute immediately and announce the contact details to the user.
    Returns contact information including name, email, phone, company.""",
)
async def get_contact_tool(
    query: Optional[str] = None,
    name: Optional[str] = None,
    email: Optional[str] = None,
    contact_id: Optional[str] = None,
) -> str:
    """Get a specific contact's information.

    Args:
        query: Search term (name, email, or partial match)
        name: Exact or partial name to search
        email: Email address to search
        contact_id: UUID of the contact

    Returns:
        Contact information or not found message
    """
    result = await _call_contact_webhook(
        operation="get_contact",
        query=query or name,
        name=name,
        email=email,
        contact_id=contact_id,
    )

    if result.get("found"):
        contact = result.get("contact", {})
        return result.get("voice_response", f"Found {contact.get('name')}")

    return result.get("voice_response", "Contact not found.")


@llm.function_tool(
    name="search_contacts",
    description="""Search for contacts by name, email, or company. READ OPERATION.
    Execute immediately and summarize the matching contacts for the user.
    Returns a list of matching contacts.""",
)
async def search_contacts_tool(
    query: str,
) -> str:
    """Search for contacts matching a query.

    Args:
        query: Search term to match against name, email, or company

    Returns:
        List of matching contacts or no results message
    """
    result = await _call_contact_webhook(
        operation="search_contacts",
        query=query,
    )

    if result.get("found"):
        count = result.get("count", 0)
        contacts = result.get("contacts", [])
        return result.get("voice_response", f"Found {count} contacts")

    return result.get("voice_response", "No contacts found matching your search.")


# Helper for voice to get contact email for sending
async def get_contact_email(name: str) -> Optional[str]:
    """Get email address for a contact by name.

    Utility function for other tools that need to look up email addresses.

    Args:
        name: Contact name to search

    Returns:
        Email address if found, None otherwise
    """
    result = await _call_contact_webhook(
        operation="get_contact",
        query=name,
    )

    if result.get("found"):
        contact = result.get("contact", {})
        return contact.get("email")

    return None
