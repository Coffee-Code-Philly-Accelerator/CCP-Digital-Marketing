"""
Tests for ComposioRecipeClient.get_recipe_details.
"""

import sys
from pathlib import Path

import pytest
import responses

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from recipe_client import COMPOSIO_API_BASE, ComposioRecipeClient


@pytest.fixture
def client(clean_env):
    return ComposioRecipeClient(api_key="test-key")


class TestGetRecipeDetails:
    @responses.activate
    def test_success(self, client):
        responses.add(
            responses.GET,
            f"{COMPOSIO_API_BASE}/recipes/rcp_test",
            json={"id": "rcp_test", "name": "Test Recipe", "inputs": []},
            status=200,
        )
        result = client.get_recipe_details("rcp_test")
        assert result["id"] == "rcp_test"
        assert result["name"] == "Test Recipe"

    @responses.activate
    def test_http_error(self, client):
        responses.add(
            responses.GET,
            f"{COMPOSIO_API_BASE}/recipes/rcp_bad",
            json={"message": "not found"},
            status=404,
        )
        result = client.get_recipe_details("rcp_bad")
        assert "error" in result

    @responses.activate
    def test_connection_error(self, client):
        import requests as req_lib

        responses.add(
            responses.GET,
            f"{COMPOSIO_API_BASE}/recipes/rcp_fail",
            body=req_lib.exceptions.ConnectionError("no connection"),
        )
        result = client.get_recipe_details("rcp_fail")
        assert "error" in result
