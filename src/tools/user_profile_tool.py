"""
AIO Voice System — User Profile Tool

Writes user profile data (name, role, company) to the user's USER.md file
for cross-session identity recognition. Called by the LLM after onboarding.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_user_mem_dir: Optional[str] = None


def set_user_mem_dir(path: str) -> None:
    """Set the active user's memory directory. Called from agent.py at session start."""
    global _user_mem_dir
    _user_mem_dir = path


async def update_user_profile_tool(
    name: str = "",
    role: str = "",
    company: str = "",
    timezone: str = "",
    notes: str = "",
) -> str:
    """
    Update the user's persistent profile (USER.md) with their name, role, and company.
    This enables cross-session recognition — call this after learning who the user is.
    """
    if not _user_mem_dir:
        return "User profile storage not initialized — cannot save profile."

    user_md = os.path.join(_user_mem_dir, "USER.md")

    try:
        # Read existing content to preserve non-Identity sections
        existing_sections = ""
        if os.path.exists(user_md):
            with open(user_md, "r", encoding="utf-8") as f:
                current = f.read()
            # Preserve Work Context and later sections if they have real content
            if "## Work Context" in current:
                idx = current.find("## Work Context")
                existing_sections = "\n\n" + current[idx:].strip()

        # Build updated file
        lines = [
            "# USER.md — User Profile",
            "",
            "AIO learns about the user over time. This file is read at every session start.",
            "",
            "## Identity",
        ]
        if name:
            lines.append(f"- Name: {name}")
        if role:
            lines.append(f"- Role: {role}")
        if company:
            lines.append(f"- Company: {company}")
        if timezone:
            lines.append(f"- Timezone: {timezone}")
        if notes:
            lines.append(f"- Notes: {notes}")

        new_content = "\n".join(lines)
        if existing_sections:
            new_content += existing_sections

        with open(user_md, "w", encoding="utf-8") as f:
            f.write(new_content + "\n")

        logger.info("[UserProfile] Updated USER.md at %s: name=%r role=%r company=%r",
                    _user_mem_dir, name, role, company)

        saved_fields = [f for f in [name, role, company] if f]
        return (
            f"Profile saved: {', '.join(saved_fields)}. "
            "I'll recognize you at the start of future sessions."
        )

    except Exception as exc:
        logger.error("[UserProfile] Failed to update USER.md: %s", exc)
        return "I had trouble saving your profile this time — I'll try again next session."
