"""
Integration tests for the Meetup event creation recipe.
"""

import builtins
import runpy

import pytest

from tests.conftest import RECIPES_DIR

RECIPE_FILE = str(RECIPES_DIR / "meetup_create_event.py")


def _run_recipe(monkeypatch, env_vars, tool_responses=None):
    for key, val in env_vars.items():
        monkeypatch.setenv(key, val)

    if tool_responses is None:
        tool_responses = {}

    default_responses = {
        "HYPERBROWSER_START_BROWSER_USE_TASK": ({"data": {"jobId": "hb_job_1", "sessionId": "hb_sess_1"}}, None),
        "HYPERBROWSER_GET_SESSION_DETAILS": ({"data": {"liveUrl": "https://live.example.com/hb"}}, None),
        "BROWSER_TOOL_CREATE_TASK": ({"data": {"watch_task_id": "bt_task_1", "browser_session_id": "bt_sess_1"}}, None),
        "BROWSER_TOOL_GET_SESSION": ({"data": {"liveUrl": "https://live.example.com/bt"}}, None),
    }
    default_responses.update(tool_responses)

    def mock_tool(tool_name, arguments):
        if tool_name in default_responses:
            return default_responses[tool_name]
        return ({"data": {}}, None)

    monkeypatch.setattr(builtins, "run_composio_tool", mock_tool, raising=False)
    namespace = runpy.run_path(RECIPE_FILE)
    return namespace["output"]


@pytest.fixture
def base_env():
    return {
        "event_title": "AI Workshop",
        "event_date": "January 25, 2025",
        "event_time": "6:00 PM EST",
        "event_location": "The Station Philadelphia",
        "event_description": "Hands-on AI workshop",
        "CCP_BROWSER_PROVIDER": "hyperbrowser",
    }


class TestMeetupHyperbrowser:
    def test_output_has_required_keys(self, monkeypatch, base_env):
        output = _run_recipe(monkeypatch, base_env)
        assert output["platform"] == "meetup"
        assert output["status"] == "running"
        assert output["task_id"] == "hb_job_1"
        assert output["provider"] == "hyperbrowser"
        assert output["poll_tool"] == "HYPERBROWSER_GET_BROWSER_USE_TASK_STATUS"

    def test_custom_meetup_group_url(self, monkeypatch, base_env):
        base_env["meetup_group_url"] = "https://www.meetup.com/custom-group"
        tool_calls = []

        def mock_tool(tool_name, arguments):
            tool_calls.append((tool_name, arguments))
            if tool_name == "HYPERBROWSER_START_BROWSER_USE_TASK":
                return ({"data": {"jobId": "hb_job_1", "sessionId": "hb_sess_1"}}, None)
            if tool_name == "HYPERBROWSER_GET_SESSION_DETAILS":
                return ({"data": {"liveUrl": "https://live.example.com"}}, None)
            return ({"data": {}}, None)

        monkeypatch.setattr(builtins, "run_composio_tool", mock_tool, raising=False)
        for key, val in base_env.items():
            monkeypatch.setenv(key, val)

        runpy.run_path(RECIPE_FILE)
        # Verify the custom URL was used in the task description
        start_call = next(c for c in tool_calls if c[0] == "HYPERBROWSER_START_BROWSER_USE_TASK")
        assert "custom-group" in start_call[1]["task"]

    def test_with_profile_id(self, monkeypatch, base_env):
        base_env["CCP_MEETUP_PROFILE_ID"] = "meetup_profile_abc"
        tool_calls = []

        def mock_tool(tool_name, arguments):
            tool_calls.append((tool_name, arguments))
            if tool_name == "HYPERBROWSER_START_BROWSER_USE_TASK":
                return ({"data": {"jobId": "hb_job_2", "sessionId": "hb_sess_2"}}, None)
            if tool_name == "HYPERBROWSER_GET_SESSION_DETAILS":
                return ({"data": {"liveUrl": "https://live.example.com"}}, None)
            return ({"data": {}}, None)

        monkeypatch.setattr(builtins, "run_composio_tool", mock_tool, raising=False)
        for key, val in base_env.items():
            monkeypatch.setenv(key, val)

        runpy.run_path(RECIPE_FILE)
        start_call = next(c for c in tool_calls if c[0] == "HYPERBROWSER_START_BROWSER_USE_TASK")
        assert start_call[1]["sessionOptions"]["profile"]["id"] == "meetup_profile_abc"


class TestMeetupBrowserTool:
    def test_browser_tool_fallback(self, monkeypatch, base_env):
        base_env["CCP_BROWSER_PROVIDER"] = "browser_tool"
        output = _run_recipe(monkeypatch, base_env)
        assert output["provider"] == "browser_tool"
        assert output["task_id"] == "bt_task_1"
        assert output["poll_tool"] == "BROWSER_TOOL_WATCH_TASK"


class TestMeetupEdgeCases:
    def test_missing_required_inputs(self, monkeypatch):
        monkeypatch.setattr(builtins, "run_composio_tool", lambda *a: ({"data": {}}, None), raising=False)
        monkeypatch.setenv("event_title", "Test")
        with pytest.raises(ValueError, match="Missing required inputs"):
            runpy.run_path(RECIPE_FILE)

    def test_tool_error_raises(self, monkeypatch, base_env):
        for key, val in base_env.items():
            monkeypatch.setenv(key, val)

        def mock_tool(tool_name, arguments):
            return (None, "Service down")

        monkeypatch.setattr(builtins, "run_composio_tool", mock_tool, raising=False)
        with pytest.raises(Exception, match="Failed to create browser task"):
            runpy.run_path(RECIPE_FILE)

    def test_success_url_pattern_in_output(self, monkeypatch, base_env):
        output = _run_recipe(monkeypatch, base_env)
        assert "meetup.com" in output["success_url_pattern"]
