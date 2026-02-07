"""Pytest configuration and fixtures for CCP Marketing tests."""

import pytest
from unittest.mock import Mock, MagicMock
from typing import Any

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture
def sample_event_data() -> dict[str, str]:
    """Sample event data for testing."""
    return {
        "title": "AI Workshop",
        "date": "January 25, 2025",
        "time": "6:00 PM EST",
        "location": "The Station, Philadelphia",
        "description": "Join us for a hands-on workshop exploring the latest AI tools and techniques.",
    }


@pytest.fixture
def sample_event(sample_event_data):
    """Sample EventData instance."""
    from ccp_marketing.models.event import EventData
    return EventData(**sample_event_data)


@pytest.fixture
def mock_composio_response() -> dict[str, Any]:
    """Mock successful Composio API response."""
    return {
        "data": {
            "data": {
                "id": "12345",
                "url": "https://example.com/event/12345",
                "status": "success",
            }
        }
    }


@pytest.fixture
def mock_composio_error_response() -> dict[str, Any]:
    """Mock error Composio API response."""
    return {
        "error": "Rate limit exceeded",
        "data": {},
    }


@pytest.fixture
def mock_browser_navigate_response() -> dict[str, Any]:
    """Mock browser navigate response."""
    return {
        "data": {
            "pageSnapshot": "# Event Creation Page\n\nEvent Title: \nDate: \nTime: \nLocation: \n",
            "url": "https://lu.ma/create",
        }
    }


@pytest.fixture
def mock_browser_success_response() -> dict[str, Any]:
    """Mock browser response after successful event creation."""
    return {
        "data": {
            "pageSnapshot": "# AI Workshop\n\nEdit Event | Manage RSVPs | Settings\n\nJanuary 25, 2025",
            "url": "https://lu.ma/ai-workshop-abc123",
        }
    }


@pytest.fixture
def mock_client():
    """Create a mock ComposioClient."""
    client = Mock()
    client.config = Mock()
    client.config.max_retries = 3
    client.config.retry_base_delay = 0.1
    client.config.retry_max_delay = 1.0
    client.config.retry_jitter = 0.0
    client.config.default_timeout = 30.0
    client.config.redact_sensitive = True
    client.config.image_model = "gemini-2.5-flash-image"
    client.config.max_workers = 5
    return client


@pytest.fixture
def mock_llm_func():
    """Create a mock LLM function."""
    def llm(prompt: str) -> tuple[str, str | None]:
        return (
            '{"twitter": "Check out AI Workshop!", '
            '"linkedin": "Excited to announce AI Workshop...", '
            '"instagram": "🤖 AI Workshop coming soon!", '
            '"facebook": "Join us for AI Workshop!", '
            '"discord": "**AI Workshop** - Don\'t miss it!", '
            '"luma": "Professional AI Workshop description", '
            '"meetup": "Community AI Workshop", '
            '"partiful": "🎉 AI Workshop Party!"}',
            None,
        )
    return llm


@pytest.fixture
def mock_llm_func_error():
    """Create a mock LLM function that returns an error."""
    def llm(prompt: str) -> tuple[str, str | None]:
        return "", "LLM service unavailable"
    return llm


@pytest.fixture
def mock_image_result() -> dict[str, Any]:
    """Mock image generation result."""
    return {
        "publicUrl": "https://storage.example.com/generated-image-123.png",
    }


@pytest.fixture
def platform_copies() -> dict[str, str]:
    """Sample platform-specific copies."""
    return {
        "twitter": "🚀 AI Workshop this Saturday! Learn the latest AI tools. RSVP now! #AI #Tech",
        "linkedin": "Excited to announce our upcoming AI Workshop. Join industry professionals for a hands-on session exploring cutting-edge AI technologies.",
        "instagram": "🤖✨ AI Workshop coming up! Don't miss this chance to level up your skills! 💡 #AIWorkshop #TechEvent #Philadelphia",
        "facebook": "Hey everyone! We're hosting an AI Workshop this Saturday. Come learn with us and connect with fellow tech enthusiasts!",
        "discord": "**🎯 AI Workshop**\n\nJoin us for hands-on AI exploration!\n\n📅 Saturday\n📍 The Station",
    }


class MockComposioToolSet:
    """Mock ComposioToolSet for testing."""

    def __init__(self, api_key: str = "test-key"):
        self.api_key = api_key
        self._responses: dict[str, Any] = {}

    def set_response(self, action: str, response: dict[str, Any]) -> None:
        """Set a mock response for an action."""
        self._responses[action] = response

    def execute_action(self, action: Any, params: dict[str, Any]) -> dict[str, Any]:
        """Execute a mock action."""
        action_name = str(action) if not isinstance(action, str) else action
        if action_name in self._responses:
            return self._responses[action_name]
        return {"data": {"mock": True, "action": action_name}}


@pytest.fixture
def mock_toolset():
    """Create a mock ComposioToolSet."""
    return MockComposioToolSet()
