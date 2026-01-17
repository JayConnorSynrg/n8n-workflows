"""Tool implementations for the voice agent."""
from .email_tool import send_email_tool
from .database_tool import query_database_tool

__all__ = ["send_email_tool", "query_database_tool"]
