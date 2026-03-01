"""
Shared fixtures for CCP Digital Marketing test suite.
"""

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# =============================================================================
# Paths
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
RECIPES_DIR = PROJECT_ROOT / "recipes"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


@pytest.fixture
def project_root():
    return PROJECT_ROOT


@pytest.fixture
def recipes_dir():
    return RECIPES_DIR


@pytest.fixture
def scripts_dir():
    return SCRIPTS_DIR


# =============================================================================
# Sample Data
# =============================================================================


@pytest.fixture
def sample_event_inputs():
    return {
        "event_title": "AI Workshop",
        "event_date": "January 25, 2025",
        "event_time": "6:00 PM EST",
        "event_location": "The Station, Philadelphia",
        "event_description": "Join us for a hands-on AI workshop.",
    }


@pytest.fixture
def sample_social_inputs():
    return {
        "topic": "New Partnership",
        "content": "We're partnering with TechHub!",
        "url": "https://example.com",
        "tone": "excited",
    }


# =============================================================================
# Environment Helpers
# =============================================================================


@pytest.fixture
def mock_composio_api_key(monkeypatch):
    """Set a fake COMPOSIO_API_KEY for tests."""
    monkeypatch.setenv("COMPOSIO_API_KEY", "test-api-key-12345")
    return "test-api-key-12345"


@pytest.fixture
def clean_env(monkeypatch):
    """Remove all CCP_* env vars and COMPOSIO_API_KEY to ensure clean state."""
    for key in list(os.environ.keys()):
        if key.startswith("CCP_") or key == "COMPOSIO_API_KEY":
            monkeypatch.delenv(key, raising=False)


@pytest.fixture
def recipe_env(monkeypatch, sample_event_inputs):
    """Set up env vars as Rube runtime would for event recipes."""
    monkeypatch.setenv("event_title", sample_event_inputs["event_title"])
    monkeypatch.setenv("event_date", sample_event_inputs["event_date"])
    monkeypatch.setenv("event_time", sample_event_inputs["event_time"])
    monkeypatch.setenv("event_location", sample_event_inputs["event_location"])
    monkeypatch.setenv("event_description", sample_event_inputs["event_description"])
    monkeypatch.setenv("CCP_BROWSER_PROVIDER", "hyperbrowser")
    return sample_event_inputs


# =============================================================================
# Mock Helpers for Recipe Integration Tests
# =============================================================================


@pytest.fixture
def mock_run_composio_tool():
    """
    Create a configurable mock for run_composio_tool.

    Returns a MagicMock that can be configured with side_effect for different
    tool calls. Default returns ({"data": {}}, None).
    """
    mock = MagicMock(return_value=({"data": {}}, None))
    return mock


@pytest.fixture
def mock_invoke_llm():
    """
    Create a configurable mock for invoke_llm.

    Default returns a valid JSON string with all 5 platform keys.
    """
    default_response = (
        '{"twitter": "tweet", "linkedin": "post", "instagram": "caption", "facebook": "post", "discord": "message"}'
    )
    mock = MagicMock(return_value=(default_response, None))
    return mock
