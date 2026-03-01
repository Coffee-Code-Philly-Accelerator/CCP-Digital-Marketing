"""
Tests for ComposioRecipeClient.execute_recipe and _poll_execution.
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


class TestExecuteRecipe:
    @responses.activate
    def test_success_without_polling(self, client):
        """When response has no execution_id, returns immediately."""
        responses.add(
            responses.POST,
            f"{COMPOSIO_API_BASE}/recipes/rcp_test/execute",
            json={"status": "completed", "output": {"result": "ok"}},
            status=200,
        )
        result = client.execute_recipe("rcp_test", {"key": "value"})
        assert result["status"] == "completed"

    @responses.activate
    def test_polling_triggered_on_execution_id(self, client):
        """When response has execution_id and wait_for_completion=True, polls."""
        responses.add(
            responses.POST,
            f"{COMPOSIO_API_BASE}/recipes/rcp_test/execute",
            json={"execution_id": "exec_123"},
            status=200,
        )
        responses.add(
            responses.GET,
            f"{COMPOSIO_API_BASE}/executions/exec_123",
            json={"status": "completed", "output": {"data": "polled"}},
            status=200,
        )
        result = client.execute_recipe("rcp_test", {"key": "value"})
        assert result["status"] == "completed"
        assert result["output"]["data"] == "polled"

    @responses.activate
    def test_http_error_returns_error_dict(self, client):
        responses.add(
            responses.POST,
            f"{COMPOSIO_API_BASE}/recipes/rcp_test/execute",
            json={"message": "Not found"},
            status=404,
        )
        result = client.execute_recipe("rcp_test", {})
        assert "error" in result
        assert "HTTP" in result["error"]

    @responses.activate
    def test_connection_error_returns_error_dict(self, client):
        responses.add(
            responses.POST,
            f"{COMPOSIO_API_BASE}/recipes/rcp_test/execute",
            body=ConnectionError("Connection refused"),
        )
        result = client.execute_recipe("rcp_test", {})
        assert "error" in result

    @responses.activate
    def test_no_execution_id_returns_immediately(self, client):
        responses.add(
            responses.POST,
            f"{COMPOSIO_API_BASE}/recipes/rcp_test/execute",
            json={"status": "queued"},
            status=200,
        )
        result = client.execute_recipe("rcp_test", {})
        assert result["status"] == "queued"

    @responses.activate
    def test_wait_for_completion_false_skips_polling(self, client):
        responses.add(
            responses.POST,
            f"{COMPOSIO_API_BASE}/recipes/rcp_test/execute",
            json={"execution_id": "exec_456", "status": "started"},
            status=200,
        )
        result = client.execute_recipe("rcp_test", {}, wait_for_completion=False)
        assert result["execution_id"] == "exec_456"
        # Should NOT have made a GET request for polling
        assert len(responses.calls) == 1


class TestPollExecution:
    @responses.activate
    def test_returns_on_completed(self, client):
        responses.add(
            responses.GET,
            f"{COMPOSIO_API_BASE}/executions/exec_1",
            json={"status": "completed", "output": "done"},
            status=200,
        )
        result = client._poll_execution("exec_1", timeout=30)
        assert result["status"] == "completed"

    @responses.activate
    def test_returns_on_failed(self, client):
        responses.add(
            responses.GET,
            f"{COMPOSIO_API_BASE}/executions/exec_1",
            json={"status": "failed", "error": "something broke"},
            status=200,
        )
        result = client._poll_execution("exec_1", timeout=30)
        assert result["status"] == "failed"

    @responses.activate
    def test_returns_on_success(self, client):
        responses.add(
            responses.GET,
            f"{COMPOSIO_API_BASE}/executions/exec_1",
            json={"status": "success", "output": "ok"},
            status=200,
        )
        result = client._poll_execution("exec_1", timeout=30)
        assert result["status"] == "success"

    @responses.activate
    def test_returns_on_finished(self, client):
        responses.add(
            responses.GET,
            f"{COMPOSIO_API_BASE}/executions/exec_1",
            json={"status": "finished", "output": "ok"},
            status=200,
        )
        result = client._poll_execution("exec_1", timeout=30)
        assert result["status"] == "finished"

    @responses.activate
    def test_timeout_returns_error(self, client, mocker):
        """When polling exceeds timeout, return error dict."""
        responses.add(
            responses.GET,
            f"{COMPOSIO_API_BASE}/executions/exec_1",
            json={"status": "running"},
            status=200,
        )
        mocker.patch("time.sleep")
        # Use a very short timeout with mocked time
        call_count = [0]

        def fake_time():
            call_count[0] += 1
            # First call: start_time = 0
            # Second call: elapsed = 1000 (exceed timeout)
            return 0 if call_count[0] <= 1 else 1000

        mocker.patch("time.time", side_effect=fake_time)
        result = client._poll_execution("exec_1", timeout=5)
        assert "error" in result
        assert "Timeout" in result["error"]
