"""
Tests for recipe wrapper functions: create_event, promote_event, full_workflow, post_to_social,
generate_social_post_drafts, publish_from_draft.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from recipe_client import (
    RECIPE_IDS,
    create_event,
    full_workflow,
    generate_social_post_drafts,
    post_to_social,
    promote_event,
    publish_from_draft,
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


# =============================================================================
# generate_social_post_drafts
# =============================================================================


class TestGenerateSocialPostDrafts:
    def test_calls_social_post_recipe_with_generate_only(self, mock_client, tmp_path):
        mock_client.execute_recipe.return_value = {
            "copies": {
                "twitter": "tweet",
                "linkedin": "post",
                "instagram": "caption",
                "facebook": "fb post",
                "discord": "msg",
            },
            "image_url": "https://img.example.com/photo.jpg",
        }
        with patch("scripts.draft_store.save_draft", return_value=str(tmp_path / "draft.json")) as mock_save:
            with patch("scripts.draft_store.build_draft") as mock_build:
                mock_build.return_value = {"event": {"title": "Topic"}, "copies": {}, "status": "draft"}
                generate_social_post_drafts(mock_client, "Topic", "Content")

        recipe_id = mock_client.execute_recipe.call_args.args[0]
        assert recipe_id == RECIPE_IDS["social_post"]
        input_data = mock_client.execute_recipe.call_args.args[1]
        assert input_data["mode"] == "generate_only"
        assert input_data["topic"] == "Topic"
        assert input_data["content"] == "Content"

    def test_builds_draft_with_social_post_type(self, mock_client, tmp_path):
        mock_client.execute_recipe.return_value = {
            "copies": {
                "twitter": "tweet",
                "linkedin": "post",
                "instagram": "caption",
                "facebook": "fb",
                "discord": "msg",
            },
            "image_url": "https://img.example.com/photo.jpg",
        }
        with patch("scripts.draft_store.save_draft", return_value=str(tmp_path / "draft.json")):
            with patch("scripts.draft_store.build_draft") as mock_build:
                mock_build.return_value = {"event": {"title": "Topic"}, "copies": {}, "status": "draft"}
                generate_social_post_drafts(
                    mock_client, "Topic", "Content", url="https://example.com"
                )

        mock_build.assert_called_once()
        args = mock_build.call_args
        assert args.args[0] == "social_post"
        event_dict = args.args[1]
        assert event_dict["title"] == "Topic"
        assert event_dict["description"] == "Content"
        assert event_dict["url"] == "https://example.com"
        assert event_dict["date"] == ""
        assert event_dict["time"] == ""

    def test_returns_result_when_no_copies(self, mock_client):
        mock_client.execute_recipe.return_value = {"status": "failed", "error": "API error"}
        result = generate_social_post_drafts(mock_client, "Topic", "Content")
        assert result == {"status": "failed", "error": "API error"}

    def test_passes_optional_fields(self, mock_client, tmp_path):
        mock_client.execute_recipe.return_value = {
            "copies": {
                "twitter": "t",
                "linkedin": "l",
                "instagram": "i",
                "facebook": "f",
                "discord": "d",
            },
            "image_url": "",
        }
        with patch("scripts.draft_store.save_draft", return_value=str(tmp_path / "d.json")):
            with patch("scripts.draft_store.build_draft") as mock_build:
                mock_build.return_value = {"event": {"title": ""}, "copies": {}, "status": "draft"}
                generate_social_post_drafts(
                    mock_client,
                    "Topic",
                    "Content",
                    tone="excited",
                    cta="Sign up!",
                    hashtags="#tech",
                    skip_platforms="twitter",
                )

        input_data = mock_client.execute_recipe.call_args.args[1]
        assert input_data["tone"] == "excited"
        assert input_data["cta"] == "Sign up!"
        assert input_data["hashtags"] == "#tech"
        assert input_data["skip_platforms"] == "twitter"


# =============================================================================
# publish_from_draft (social_post routing)
# =============================================================================


class TestPublishFromDraftSocialPost:
    def _make_social_post_draft(self, tmp_path):
        draft = {
            "version": 1,
            "draft_type": "social_post",
            "status": "approved",
            "created_at": "2026-03-16T00:00:00+00:00",
            "updated_at": "2026-03-16T00:00:00+00:00",
            "event": {
                "title": "New Partnership",
                "date": "",
                "time": "",
                "location": "",
                "description": "We are partnering with TechHub!",
                "url": "https://example.com",
            },
            "image_url": "https://img.example.com/photo.jpg",
            "copies": {
                "twitter": "tweet text",
                "linkedin": "linkedin text",
                "instagram": "insta text",
                "facebook": "fb text",
                "discord": "discord text",
            },
            "platform_config": {
                "discord_channel_id": "ch_123",
                "facebook_page_id": "pg_456",
                "skip_platforms": "",
            },
            "publish_results": None,
        }
        filepath = tmp_path / "draft.json"
        filepath.write_text(json.dumps(draft))
        return str(filepath)

    def test_routes_to_social_post_recipe(self, mock_client, tmp_path):
        filepath = self._make_social_post_draft(tmp_path)
        mock_client.execute_recipe.return_value = {"status": "completed"}
        publish_from_draft(mock_client, filepath)

        recipe_id = mock_client.execute_recipe.call_args.args[0]
        assert recipe_id == RECIPE_IDS["social_post"]

    def test_builds_input_with_topic_and_content(self, mock_client, tmp_path):
        filepath = self._make_social_post_draft(tmp_path)
        mock_client.execute_recipe.return_value = {"status": "completed"}
        publish_from_draft(mock_client, filepath)

        input_data = mock_client.execute_recipe.call_args.args[1]
        assert input_data["topic"] == "New Partnership"
        assert input_data["content"] == "We are partnering with TechHub!"
        assert input_data["url"] == "https://example.com"
        assert input_data["mode"] == "publish_only"
        assert input_data["discord_channel_id"] == "ch_123"
        assert "pre_generated_copies" in input_data
        # Should NOT have event-specific keys
        assert "event_title" not in input_data
        assert "event_date" not in input_data

    def test_updates_draft_status_on_success(self, mock_client, tmp_path):
        filepath = self._make_social_post_draft(tmp_path)
        mock_client.execute_recipe.return_value = {"status": "completed"}
        publish_from_draft(mock_client, filepath)

        # save_draft generates filename from title/created_at, find the new file
        original = Path(filepath)
        saved_files = [f for f in tmp_path.glob("*.json") if f != original]
        assert len(saved_files) == 1
        updated = json.loads(saved_files[0].read_text())
        assert updated["status"] == "published"


class TestPublishFromDraftEventPromotion:
    def _make_event_draft(self, tmp_path):
        draft = {
            "version": 1,
            "draft_type": "event_promotion",
            "status": "approved",
            "created_at": "2026-03-16T00:00:00+00:00",
            "updated_at": "2026-03-16T00:00:00+00:00",
            "event": {
                "title": "AI Workshop",
                "date": "March 20, 2026",
                "time": "6:00 PM EST",
                "location": "Philadelphia",
                "description": "A workshop",
                "url": "https://lu.ma/abc",
            },
            "image_url": "https://img.example.com/photo.jpg",
            "copies": {
                "twitter": "tweet",
                "linkedin": "post",
                "instagram": "caption",
                "facebook": "fb",
                "discord": "msg",
            },
            "platform_config": {
                "discord_channel_id": "",
                "facebook_page_id": "",
                "skip_platforms": "",
            },
            "publish_results": None,
        }
        filepath = tmp_path / "draft.json"
        filepath.write_text(json.dumps(draft))
        return str(filepath)

    def test_routes_to_social_promotion_recipe(self, mock_client, tmp_path):
        filepath = self._make_event_draft(tmp_path)
        mock_client.execute_recipe.return_value = {"status": "completed"}
        publish_from_draft(mock_client, filepath)

        recipe_id = mock_client.execute_recipe.call_args.args[0]
        assert recipe_id == RECIPE_IDS["social_promotion"]

    def test_builds_input_with_event_fields(self, mock_client, tmp_path):
        filepath = self._make_event_draft(tmp_path)
        mock_client.execute_recipe.return_value = {"status": "completed"}
        publish_from_draft(mock_client, filepath)

        input_data = mock_client.execute_recipe.call_args.args[1]
        assert input_data["event_title"] == "AI Workshop"
        assert input_data["event_date"] == "March 20, 2026"
        assert input_data["event_url"] == "https://lu.ma/abc"
        assert "topic" not in input_data
