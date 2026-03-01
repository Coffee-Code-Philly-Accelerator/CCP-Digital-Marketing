"""
Tests for recipe wrapper functions: create_event, promote_event, full_workflow, post_to_social.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from recipe_client import (
    RECIPE_IDS,
    create_event,
    full_workflow,
    post_to_social,
    promote_event,
)


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.execute_recipe.return_value = {"status": "completed"}
    return client


# =============================================================================
# create_event
# =============================================================================


class TestCreateEvent:
    def test_calls_all_three_platforms(self, mock_client):
        result = create_event(mock_client, "Title", "Jan 1", "6pm", "Venue", "Desc")
        assert mock_client.execute_recipe.call_count == 3
        assert "luma" in result
        assert "meetup" in result
        assert "partiful" in result

    def test_correct_recipe_ids(self, mock_client):
        create_event(mock_client, "Title", "Jan 1", "6pm", "Venue", "Desc")
        called_ids = [call.args[0] for call in mock_client.execute_recipe.call_args_list]
        assert RECIPE_IDS["luma_create"] in called_ids
        assert RECIPE_IDS["meetup_create"] in called_ids
        assert RECIPE_IDS["partiful_create"] in called_ids

    def test_skip_platforms(self, mock_client):
        result = create_event(mock_client, "Title", "Jan 1", "6pm", "Venue", "Desc", skip_platforms="meetup,partiful")
        assert mock_client.execute_recipe.call_count == 1
        assert result["meetup"]["status"] == "skipped"
        assert result["partiful"]["status"] == "skipped"

    def test_meetup_group_url_only_for_meetup(self, mock_client):
        create_event(mock_client, "Title", "Jan 1", "6pm", "Venue", "Desc", meetup_group_url="https://meetup.com/test")
        for call in mock_client.execute_recipe.call_args_list:
            recipe_id = call.args[0]
            input_data = call.args[1]
            if recipe_id == RECIPE_IDS["meetup_create"]:
                assert "meetup_group_url" in input_data
            else:
                assert "meetup_group_url" not in input_data

    def test_provider_passed_in_input(self, mock_client):
        create_event(mock_client, "Title", "Jan 1", "6pm", "Venue", "Desc", provider="browser_tool")
        for call in mock_client.execute_recipe.call_args_list:
            input_data = call.args[1]
            assert input_data["CCP_BROWSER_PROVIDER"] == "browser_tool"


# =============================================================================
# promote_event
# =============================================================================


class TestPromoteEvent:
    def test_calls_social_promotion_recipe(self, mock_client):
        promote_event(mock_client, "Title", "Jan 1", "6pm", "Venue", "Desc", event_url="https://lu.ma/test")
        mock_client.execute_recipe.assert_called_once()
        recipe_id = mock_client.execute_recipe.call_args.args[0]
        assert recipe_id == RECIPE_IDS["social_promotion"]

    def test_passes_all_fields(self, mock_client):
        promote_event(
            mock_client,
            "Title",
            "Jan 1",
            "6pm",
            "Venue",
            "Desc",
            event_url="https://lu.ma/test",
            discord_channel_id="ch_123",
            facebook_page_id="pg_456",
            skip_platforms="twitter",
        )
        input_data = mock_client.execute_recipe.call_args.args[1]
        assert input_data["event_url"] == "https://lu.ma/test"
        assert input_data["discord_channel_id"] == "ch_123"
        assert input_data["facebook_page_id"] == "pg_456"
        assert input_data["skip_platforms"] == "twitter"


# =============================================================================
# full_workflow
# =============================================================================


class TestFullWorkflow:
    def test_calls_create_then_promote(self, mock_client):
        """full_workflow should call create (3 platforms) + promote (1) = 4 calls."""
        mock_client.execute_recipe.return_value = {"status": "completed"}
        result = full_workflow(mock_client, "Title", "Jan 1", "6pm", "Venue", "Desc")
        assert mock_client.execute_recipe.call_count == 4
        assert "event_creation" in result
        assert "social_promotion" in result
        assert "primary_event_url" in result

    def test_extracts_event_url_from_create_results(self, mock_client):
        def side_effect(recipe_id, input_data, **kwargs):
            if recipe_id == RECIPE_IDS["luma_create"]:
                return {"status": "completed", "event_url": "https://lu.ma/abc123"}
            return {"status": "completed"}

        mock_client.execute_recipe.side_effect = side_effect
        result = full_workflow(mock_client, "Title", "Jan 1", "6pm", "Venue", "Desc")
        assert result["primary_event_url"] == "https://lu.ma/abc123"

    def test_no_event_url_still_promotes(self, mock_client):
        mock_client.execute_recipe.return_value = {"status": "completed"}
        result = full_workflow(mock_client, "Title", "Jan 1", "6pm", "Venue", "Desc")
        assert result["primary_event_url"] == ""
        # Should still have called promote (4th call)
        assert mock_client.execute_recipe.call_count == 4

    def test_skip_platforms_passed_to_both(self, mock_client):
        mock_client.execute_recipe.return_value = {"status": "completed"}
        full_workflow(mock_client, "Title", "Jan 1", "6pm", "Venue", "Desc", skip_platforms="meetup,twitter")
        # Luma + partiful + promote = 3 calls (meetup skipped)
        assert mock_client.execute_recipe.call_count == 3


# =============================================================================
# post_to_social
# =============================================================================


class TestPostToSocial:
    def test_calls_social_post_recipe(self, mock_client):
        post_to_social(mock_client, "Topic", "Content")
        recipe_id = mock_client.execute_recipe.call_args.args[0]
        assert recipe_id == RECIPE_IDS["social_post"]

    def test_passes_all_optional_fields(self, mock_client):
        post_to_social(
            mock_client,
            "Topic",
            "Content",
            url="https://example.com",
            image_url="https://img.example.com/photo.jpg",
            image_prompt="Custom prompt",
            tone="excited",
            cta="Sign up now!",
            hashtags="#tech #AI",
            discord_channel_id="ch_789",
            facebook_page_id="pg_101",
            skip_platforms="instagram",
        )
        input_data = mock_client.execute_recipe.call_args.args[1]
        assert input_data["topic"] == "Topic"
        assert input_data["content"] == "Content"
        assert input_data["url"] == "https://example.com"
        assert input_data["image_url"] == "https://img.example.com/photo.jpg"
        assert input_data["image_prompt"] == "Custom prompt"
        assert input_data["tone"] == "excited"
        assert input_data["cta"] == "Sign up now!"
        assert input_data["hashtags"] == "#tech #AI"
        assert input_data["discord_channel_id"] == "ch_789"
        assert input_data["facebook_page_id"] == "pg_101"
        assert input_data["skip_platforms"] == "instagram"

    def test_defaults_empty_strings(self, mock_client):
        post_to_social(mock_client, "Topic", "Content")
        input_data = mock_client.execute_recipe.call_args.args[1]
        assert input_data["url"] == ""
        assert input_data["image_url"] == ""
        assert input_data["tone"] == ""
        assert input_data["skip_platforms"] == ""
