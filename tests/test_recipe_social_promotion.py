"""
Integration tests for the social promotion recipe.
"""

import builtins
import json
import runpy

import pytest

from tests.conftest import RECIPES_DIR

RECIPE_FILE = str(RECIPES_DIR / "social_promotion.py")


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
            "twitter": "Join us! #AI",
            "linkedin": "Professional post about AI Workshop",
            "instagram": "AI Workshop caption",
            "facebook": "Community AI Workshop post",
            "discord": "**AI Workshop** discord post",
        }

        def llm_fn(prompt):
            return (json.dumps(copies), None)

    monkeypatch.setattr(builtins, "run_composio_tool", tool_fn, raising=False)
    monkeypatch.setattr(builtins, "invoke_llm", llm_fn, raising=False)

    # Mock time.sleep to avoid slow tests
    monkeypatch.setattr("time.sleep", lambda x: None)

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
        "event_url": "https://lu.ma/test123",
        "discord_channel_id": "ch_123",
        "facebook_page_id": "pg_456",
    }


class TestSocialPromotionFullFlow:
    def test_all_platforms_success(self, monkeypatch, base_env):
        output = _run_recipe(monkeypatch, base_env)
        assert output["linkedin_posted"] == "success"
        assert output["instagram_posted"] == "success"
        assert output["facebook_posted"] == "success"
        assert output["discord_posted"] == "success"
        assert output["image_url"] == "https://img.example.com/generated.jpg"
        assert "4/5" in output["summary"]  # Twitter always skipped

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


class TestSocialPromotionLLMFailure:
    def test_llm_error_uses_default_copy(self, monkeypatch, base_env):
        def llm_fn(prompt):
            return (None, "LLM service unavailable")

        output = _run_recipe(monkeypatch, base_env, llm_fn=llm_fn)
        # Should still post (with default copy)
        assert output["linkedin_posted"] == "success"


class TestSocialPromotionPlatformSkipping:
    def test_skip_linkedin_and_discord(self, monkeypatch, base_env):
        base_env["skip_platforms"] = "linkedin,discord"
        output = _run_recipe(monkeypatch, base_env)
        assert output["linkedin_posted"] == "skipped"
        assert output["discord_posted"] == "skipped"
        assert output["instagram_posted"] == "success"
        assert output["facebook_posted"] == "success"

    def test_skip_all_platforms(self, monkeypatch, base_env):
        base_env["skip_platforms"] = "linkedin,instagram,facebook,discord"
        output = _run_recipe(monkeypatch, base_env)
        assert output["linkedin_posted"] == "skipped"
        assert output["instagram_posted"] == "skipped"
        assert output["facebook_posted"] == "skipped"
        assert output["discord_posted"] == "skipped"
        assert "0/5" in output["summary"]


class TestSocialPromotionPlatformFailures:
    def test_linkedin_profile_error(self, monkeypatch, base_env):
        def tool_fn(tool_name, arguments):
            if tool_name == "GEMINI_GENERATE_IMAGE":
                return ({"data": {"publicUrl": "https://img.example.com/photo.jpg"}}, None)
            if tool_name == "LINKEDIN_GET_MY_INFO":
                return (None, "Auth expired")
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
        assert "failed" in output["linkedin_posted"]
        assert output["instagram_posted"] == "success"

    def test_no_facebook_page_id(self, monkeypatch, base_env):
        del base_env["facebook_page_id"]
        output = _run_recipe(monkeypatch, base_env)
        assert "skipped" in output["facebook_posted"]

    def test_no_discord_channel_id(self, monkeypatch, base_env):
        del base_env["discord_channel_id"]
        output = _run_recipe(monkeypatch, base_env)
        assert "skipped" in output["discord_posted"]


class TestSocialPromotionValidation:
    def test_missing_required_inputs(self, monkeypatch):
        monkeypatch.setattr(builtins, "run_composio_tool", lambda *a: ({"data": {}}, None), raising=False)
        monkeypatch.setattr(builtins, "invoke_llm", lambda *a: ("{}", None), raising=False)
        monkeypatch.setenv("event_title", "Test")
        with pytest.raises(ValueError, match="Missing required inputs"):
            runpy.run_path(RECIPE_FILE)
