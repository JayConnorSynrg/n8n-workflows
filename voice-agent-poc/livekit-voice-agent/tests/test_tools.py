"""Tests for voice agent tools."""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

# Test the email tool
@pytest.mark.asyncio
async def test_send_email_success():
    """Test successful email sending."""
    with patch('aiohttp.ClientSession') as mock_session:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"status": "COMPLETED"})

        mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response

        # Import after patching
        from src.tools.email_tool import send_email_tool

        result = await send_email_tool(
            to="test@example.com",
            subject="Test Subject",
            body="Test body"
        )

        assert "successfully" in result.lower()


@pytest.mark.asyncio
async def test_send_email_failure():
    """Test email sending failure handling."""
    with patch('aiohttp.ClientSession') as mock_session:
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.json = AsyncMock(return_value={"error": "Server error"})

        mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response

        from src.tools.email_tool import send_email_tool

        result = await send_email_tool(
            to="test@example.com",
            subject="Test Subject",
            body="Test body"
        )

        assert "failed" in result.lower()


@pytest.mark.asyncio
async def test_query_database_success():
    """Test successful database query."""
    with patch('aiohttp.ClientSession') as mock_session:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "status": "COMPLETED",
            "results": [
                {"title": "Result 1", "snippet": "Content 1"},
                {"title": "Result 2", "snippet": "Content 2"}
            ]
        })

        mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response

        from src.tools.database_tool import query_database_tool

        result = await query_database_tool(query="test query")

        assert "Result 1" in result
        assert "Result 2" in result


@pytest.mark.asyncio
async def test_query_database_no_results():
    """Test database query with no results."""
    with patch('aiohttp.ClientSession') as mock_session:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "status": "COMPLETED",
            "results": []
        })

        mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response

        from src.tools.database_tool import query_database_tool

        result = await query_database_tool(query="test query")

        assert "no results" in result.lower()
