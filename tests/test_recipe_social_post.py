"""
Integration tests for the generic social post recipe.
"""

import builtins
import json
import runpy

import pytest

from tests.conftest import RECIPES_DIR

RECIPE_FILE = str(RECIPES_DIR / "social_post.py")


def _run_recipe(monkeypatch, env_vars, tool_fn=None, llm_fn=None):
    for key, val in env_vars.items():
        monkeypatch.setenv(key, val)

    if tool_fn is None:

        def tool_fn(tool_name, arguments):
            if tool_name == "GEMINI_GENERATE_IMAGE":
                return ({"data": {"publicUrl": "https://img.example.com/generated.jpg"}}, None)
            if tool_name == "LINKEDIN_GET_MY_INFO":
                return ({"data": {"data": {"id": "li_user_123"}}}, None)
            if tool_name == "LINKEDIN_CREATE_LINKED_IN_POST":
                return ({"data": {"id": "post_123"}}, None)
            if tool_name == "INSTAGRAM_GET_USER_INFO":
                return ({"data": {"data": {"id": "ig_user_456"}}}, None)
            if tool_name == "INSTAGRAM_CREATE_MEDIA_CONTAINER":
                return ({"data": {"data": {"id": "container_789"}}}, None)
            if tool_name == "INSTAGRAM_GET_POST_STATUS":
                return ({"data": {"data": {"status_code": "FINISHED"}}}, None)
            if tool_name == "INSTAGRAM_CREATE_POST":
                return ({"data": {"id": "ig_post_123"}}, None)
            if tool_name == "FACEBOOK_CREATE_POST":
                return ({"data": {"id": "fb_post_123"}}, None)
            if tool_name == "DISCORDBOT_CREATE_MESSAGE":
                return ({"data": {"id": "dc_msg_123"}}, None)
            return ({"data": {}}, None)

    if llm_fn is None:
        copies = {
            "twitter": "Tweet about partnership",
            "linkedin": "Professional partnership post",
            "instagram": "Partnership caption",
            "facebook": "Community partnership post",
            "discord": "**Partnership** discord message",
        }

        def llm_fn(prompt):
            return (json.dumps(copies), None)

    monkeypatch.setattr(builtins, "run_composio_tool", tool_fn, raising=False)
    monkeypatch.setattr(builtins, "invoke_llm", llm_fn, raising=False)
    monkeypatch.setattr("time.sleep", lambda x: None)

    namespace = runpy.run_path(RECIPE_FILE)
    return namespace["output"]


@pytest.fixture
def base_env():
    return {
        "topic": "New Partnership",
        "content": "We are partnering with TechHub for amazing things!",
        "url": "https://example.com/partnership",
        "tone": "excited",
        "discord_channel_id": "ch_123",
        "facebook_page_id": "pg_456",
    }


class TestSocialPostFullFlow:
    def test_all_platforms_success(self, monkeypatch, base_env):
        output = _run_recipe(monkeypatch, base_env)
        assert output["linkedin_posted"] == "success"
        assert output["instagram_posted"] == "success"
        assert output["facebook_posted"] == "success"
        assert output["discord_posted"] == "success"
        assert output["image_url"] == "https://img.example.com/generated.jpg"

    def test_existing_image_url_skips_gemini(self, monkeypatch, base_env):
        base_env["image_url"] = "https://existing.example.com/photo.jpg"
        tool_calls = []

        def tool_fn(tool_name, arguments):
            tool_calls.append(tool_name)
            if tool_name == "LINKEDIN_GET_MY_INFO":
                return ({"data": {"data": {"id": "li_123"}}}, None)
            if tool_name == "LINKEDIN_CREATE_LINKED_IN_POST":
                return ({"data": {}}, None)
            if tool_name == "INSTAGRAM_GET_USER_INFO":
                return ({"data": {"data": {"id": "ig_456"}}}, None)
            if tool_name == "INSTAGRAM_CREATE_MEDIA_CONTAINER":
                return ({"data": {"data": {"id": "c_789"}}}, None)
            if tool_name == "INSTAGRAM_GET_POST_STATUS":
                return ({"data": {"data": {"status_code": "FINISHED"}}}, None)
            if tool_name == "INSTAGRAM_CREATE_POST":
                return ({"data": {}}, None)
            if tool_name == "FACEBOOK_CREATE_POST":
                return ({"data": {}}, None)
            if tool_name == "DISCORDBOT_CREATE_MESSAGE":
                return ({"data": {}}, None)
            return ({"data": {}}, None)

        output = _run_recipe(monkeypatch, base_env, tool_fn=tool_fn)
        assert "GEMINI_GENERATE_IMAGE" not in tool_calls
        assert output["image_url"] == "https://existing.example.com/photo.jpg"

    def test_custom_image_prompt(self, monkeypatch, base_env):
        base_env["image_prompt"] = "A futuristic handshake between robots"
        tool_calls = []

        def tool_fn(tool_name, arguments):
            tool_calls.append((tool_name, arguments))
            if tool_name == "GEMINI_GENERATE_IMAGE":
                assert "futuristic handshake" in arguments["prompt"]
                return ({"data": {"publicUrl": "https://img.example.com/custom.jpg"}}, None)
            if tool_name == "LINKEDIN_GET_MY_INFO":
                return ({"data": {"data": {"id": "li_123"}}}, None)
            if tool_name == "LINKEDIN_CREATE_LINKED_IN_POST":
                return ({"data": {}}, None)
            if tool_name == "INSTAGRAM_GET_USER_INFO":
                return ({"data": {"data": {"id": "ig_456"}}}, None)
            if tool_name == "INSTAGRAM_CREATE_MEDIA_CONTAINER":
                return ({"data": {"data": {"id": "c_789"}}}, None)
            if tool_name == "INSTAGRAM_GET_POST_STATUS":
                return ({"data": {"data": {"status_code": "FINISHED"}}}, None)
            if tool_name == "INSTAGRAM_CREATE_POST":
                return ({"data": {}}, None)
            if tool_name == "FACEBOOK_CREATE_POST":
                return ({"data": {}}, None)
            if tool_name == "DISCORDBOT_CREATE_MESSAGE":
                return ({"data": {}}, None)
            return ({"data": {}}, None)

        output = _run_recipe(monkeypatch, base_env, tool_fn=tool_fn)
        assert output["image_url"] == "https://img.example.com/custom.jpg"


class TestSocialPostLLMFailure:
    def test_llm_error_uses_default_copy(self, monkeypatch, base_env):
        def llm_fn(prompt):
            return (None, "LLM unavailable")

        output = _run_recipe(monkeypatch, base_env, llm_fn=llm_fn)
        assert output["linkedin_posted"] == "success"


class TestSocialPostSkipping:
    def test_skip_platforms(self, monkeypatch, base_env):
        base_env["skip_platforms"] = "instagram,facebook"
        output = _run_recipe(monkeypatch, base_env)
        assert output["instagram_posted"] == "skipped"
        assert output["facebook_posted"] == "skipped"
        assert output["linkedin_posted"] == "success"
        assert output["discord_posted"] == "success"


class TestSocialPostValidation:
    def test_missing_required_inputs(self, monkeypatch):
        monkeypatch.setattr(builtins, "run_composio_tool", lambda *a: ({"data": {}}, None), raising=False)
        monkeypatch.setattr(builtins, "invoke_llm", lambda *a: ("{}", None), raising=False)
        monkeypatch.setenv("topic", "Test")
        # Missing content
        with pytest.raises(ValueError, match="Missing required inputs"):
            runpy.run_path(RECIPE_FILE)

    def test_missing_both_inputs(self, monkeypatch):
        monkeypatch.setattr(builtins, "run_composio_tool", lambda *a: ({"data": {}}, None), raising=False)
        monkeypatch.setattr(builtins, "invoke_llm", lambda *a: ("{}", None), raising=False)
        with pytest.raises(ValueError, match="Missing required inputs"):
            runpy.run_path(RECIPE_FILE)
