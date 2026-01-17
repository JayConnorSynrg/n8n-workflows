"""Email tool for sending emails via n8n webhook.

The n8n workflow implements a gated execution pattern:
1. Voice agent confirms with user before calling
2. n8n workflow executes Gmail send
3. Success/failure returned for voice announcement

For the initial LiveKit deployment, we use simplified direct execution
without the callback gates (callback_url is set to a no-op endpoint).
"""
import json
import uuid
from typing import Optional

import aiohttp
from livekit.agents import llm

from ..config import get_settings

settings = get_settings()


@llm.function_tool(
    name="send_email",
    description="""Send an email to a recipient.
    ALWAYS confirm the recipient and subject with the user before calling this tool.
    After sending, announce the success to the user.""",
)
async def send_email_tool(
    to: str,
    subject: str,
    body: str,
    cc: Optional[str] = None,
) -> str:
    """Send an email via n8n webhook.

    Args:
        to: Recipient email address
        subject: Email subject line
        body: Email body content (plain text)
        cc: Optional CC recipient

    Returns:
        Success message or error description
    """
    webhook_url = f"{settings.n8n_webhook_base_url}/execute-gmail"

    # Build payload matching n8n workflow expected format
    intent_id = f"lk_{uuid.uuid4().hex[:12]}"
    payload = {
        "intent_id": intent_id,
        "session_id": "livekit-agent",
        # For initial deployment, use no-op callback (workflow will timeout but complete)
        # In production, set up a proper callback endpoint
        "callback_url": f"{settings.n8n_webhook_base_url}/callback-noop",
        "parameters": {
            "to": to,
            "subject": subject,
            "body": body,
        }
    }
    if cc:
        payload["parameters"]["cc"] = cc

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                # Increased timeout for gated workflow execution
                timeout=aiohttp.ClientTimeout(total=60),
            ) as response:
                result = await response.json()

                if response.status == 200:
                    status = result.get("status", "")
                    if status == "COMPLETED":
                        voice_response = result.get("voice_response", f"Email sent to {to}")
                        return voice_response
                    elif status == "CANCELLED":
                        return result.get("voice_response", "Email was cancelled")
                    else:
                        return f"Email sent successfully to {to}"
                else:
                    error_msg = result.get("error", result.get("voice_response", "Unknown error"))
                    return f"Failed to send email: {error_msg}"

    except aiohttp.ClientError as e:
        return f"Network error sending email: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"
