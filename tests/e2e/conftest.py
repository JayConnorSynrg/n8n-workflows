"""Shared fixtures for AIO E2E test suite."""
import os
import sys
import json
import asyncio
import uuid
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
from typing import Generator, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path bootstrap — allow imports from src/
# ---------------------------------------------------------------------------
SRC_ROOT = Path(__file__).parent.parent.parent / "src"
REPO_ROOT = Path(__file__).parent.parent.parent

def _load_module(name: str, rel_path: str):
    """Load a src/ module by path and register in sys.modules."""
    if name in sys.modules:
        return sys.modules[name]
    path = SRC_ROOT / rel_path
    spec = spec_from_file_location(name, path)
    mod = module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Pytest hooks
# ---------------------------------------------------------------------------

def pytest_addoption(parser):
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests that call live Railway, DB, and Composio APIs",
    )


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-integration"):
        skip_integration = pytest.mark.skip(reason="Pass --run-integration to run")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def postgres_url() -> str:
    """Railway PostgreSQL URL from environment."""
    url = os.environ.get("POSTGRES_URL", "")
    return url


@pytest.fixture
def mock_session_id() -> str:
    """Generate a unique test session ID."""
    return f"test-session-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def mock_user_id() -> str:
    return "test-user-e2e"


@pytest.fixture
def mock_composio_execute():
    """Mock Composio SDK execute call returning a successful response."""
    def _make_response(data: dict = None, successful: bool = True, error: str = ""):
        return {
            "successful": successful,
            "data": data or {},
            "error": error,
            "log_id": "test-log-id",
        }
    return _make_response


@pytest.fixture
def mock_settings():
    """Mock AIO settings object."""
    settings = MagicMock()
    settings.composio_api_key = "test-composio-key"
    settings.composio_user_id = "pg-test-49ecc67f-362b-4475-b0cc-92804c604d1c"
    settings.n8n_webhook_base_url = "https://jayconnorexe.app.n8n.cloud"
    settings.n8n_webhook_secret = "test-secret-64chars-" + "x" * 44
    settings.postgres_url = os.environ.get("POSTGRES_URL", "")
    settings.pgvector_url = ""
    settings.memory_dir = "/tmp/aio-test-memory"
    settings.max_tool_steps = 20
    return settings


@pytest.fixture
def gate_sentinel_prefix() -> str:
    return "__GATE__:"


@pytest.fixture
def slug_overrides_expected() -> dict:
    """Expected _SLUG_OVERRIDES entries — test that all 8 are present."""
    return {
        "GOOGLEDRIVE_FIND_FOLDER": "GOOGLEDRIVE_FIND_FILE",
        "GOOGLEDRIVE_LIST_FILES_IN_FOLDER": "GOOGLEDRIVE_FIND_FILE",
        "GOOGLEDRIVE_LIST_FOLDERS": "GOOGLEDRIVE_FIND_FILE",
        "GOOGLEDRIVE_SEARCH_FILES": "GOOGLEDRIVE_FIND_FILE",
        "GOOGLEDRIVE_GET_FILE": "GOOGLEDRIVE_GET_FILE_METADATA",
        "GOOGLEDRIVE_GET_FILE_BY_ID": "GOOGLEDRIVE_GET_FILE_METADATA",
        "MICROSOFT_TEAMS_LIST_MESSAGES": "MICROSOFT_TEAMS_TEAMS_LIST_CHANNEL_MESSAGES",
    }
