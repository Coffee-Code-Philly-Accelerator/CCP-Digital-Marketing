"""
Tests for ComposioRecipeClient.__init__.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from recipe_client import ComposioRecipeClient


class TestClientInit:
    def test_explicit_api_key(self, clean_env):
        client = ComposioRecipeClient(api_key="explicit-key-123")
        assert client.api_key == "explicit-key-123"

    def test_env_api_key(self, mock_composio_api_key):
        client = ComposioRecipeClient()
        assert client.api_key == "test-api-key-12345"

    def test_explicit_takes_precedence_over_env(self, mock_composio_api_key):
        client = ComposioRecipeClient(api_key="override-key")
        assert client.api_key == "override-key"

    def test_missing_key_raises_value_error(self, clean_env):
        with pytest.raises(ValueError, match="COMPOSIO_API_KEY"):
            ComposioRecipeClient()

    def test_session_headers(self, clean_env):
        client = ComposioRecipeClient(api_key="test-key")
        assert client.session.headers["Authorization"] == "Bearer test-key"
        assert client.session.headers["Content-Type"] == "application/json"
        assert client.session.headers["Accept"] == "application/json"

    def test_timestamp_format(self):
        ts = ComposioRecipeClient._timestamp()
        # Format: YYYY-MM-DD HH:MM:SS UTC
        assert ts.endswith(" UTC")
        parts = ts.replace(" UTC", "").split(" ")
        assert len(parts) == 2
        date_parts = parts[0].split("-")
        assert len(date_parts) == 3
