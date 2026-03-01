"""
Tests for CLI argument parsing and main() dispatch.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from recipe_client import main


class TestCLIParsing:
    def test_no_command_exits(self, mock_composio_api_key):
        with patch("sys.argv", ["recipe_client.py"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    @patch("recipe_client.create_event")
    @patch("recipe_client.ComposioRecipeClient")
    def test_create_event_command(self, mock_cls, mock_fn, mock_composio_api_key):
        mock_fn.return_value = {"status": "ok"}
        with patch(
            "sys.argv",
            [
                "recipe_client.py",
                "create-event",
                "--title",
                "Test",
                "--date",
                "Jan 1",
                "--time",
                "6pm",
                "--location",
                "Philly",
                "--description",
                "Desc",
                "--meetup-url",
                "https://meetup.com/test",
                "--skip",
                "partiful",
                "--provider",
                "browser_tool",
            ],
        ):
            main()
        mock_fn.assert_called_once()
        kwargs = mock_fn.call_args
        assert kwargs.kwargs["title"] == "Test"
        assert kwargs.kwargs["meetup_group_url"] == "https://meetup.com/test"
        assert kwargs.kwargs["skip_platforms"] == "partiful"
        assert kwargs.kwargs["provider"] == "browser_tool"

    @patch("recipe_client.promote_event")
    @patch("recipe_client.ComposioRecipeClient")
    def test_promote_command(self, mock_cls, mock_fn, mock_composio_api_key):
        mock_fn.return_value = {"status": "ok"}
        with patch(
            "sys.argv",
            [
                "recipe_client.py",
                "promote",
                "--title",
                "Test",
                "--date",
                "Jan 1",
                "--time",
                "6pm",
                "--location",
                "Philly",
                "--description",
                "Desc",
                "--event-url",
                "https://lu.ma/abc",
            ],
        ):
            main()
        mock_fn.assert_called_once()
        assert mock_fn.call_args.kwargs["event_url"] == "https://lu.ma/abc"

    @patch("recipe_client.full_workflow")
    @patch("recipe_client.ComposioRecipeClient")
    def test_full_workflow_command(self, mock_cls, mock_fn, mock_composio_api_key):
        mock_fn.return_value = {"status": "ok"}
        with patch(
            "sys.argv",
            [
                "recipe_client.py",
                "full-workflow",
                "--title",
                "Test",
                "--date",
                "Jan 1",
                "--time",
                "6pm",
                "--location",
                "Philly",
                "--description",
                "Desc",
            ],
        ):
            main()
        mock_fn.assert_called_once()

    @patch("recipe_client.post_to_social")
    @patch("recipe_client.ComposioRecipeClient")
    def test_social_post_command(self, mock_cls, mock_fn, mock_composio_api_key):
        mock_fn.return_value = {"status": "ok"}
        with patch(
            "sys.argv",
            [
                "recipe_client.py",
                "social-post",
                "--topic",
                "News",
                "--content",
                "Big announcement!",
                "--tone",
                "excited",
            ],
        ):
            main()
        mock_fn.assert_called_once()
        assert mock_fn.call_args.kwargs["topic"] == "News"
        assert mock_fn.call_args.kwargs["tone"] == "excited"

    @patch("recipe_client.ComposioRecipeClient")
    def test_info_command(self, mock_cls, mock_composio_api_key):
        mock_instance = MagicMock()
        mock_instance.get_recipe_details.return_value = {"id": "rcp_test"}
        mock_cls.return_value = mock_instance
        with patch("sys.argv", ["recipe_client.py", "info", "--recipe", "luma"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
        mock_instance.get_recipe_details.assert_called_once()

    @patch("recipe_client.ComposioRecipeClient")
    def test_info_all_recipes(self, mock_cls, mock_composio_api_key):
        mock_instance = MagicMock()
        mock_instance.get_recipe_details.return_value = {"id": "rcp_test"}
        mock_cls.return_value = mock_instance
        with patch("sys.argv", ["recipe_client.py", "info", "--recipe", "all"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
        assert mock_instance.get_recipe_details.call_count == 5

    def test_missing_api_key_exits(self, clean_env):
        with patch(
            "sys.argv",
            [
                "recipe_client.py",
                "create-event",
                "--title",
                "Test",
                "--date",
                "Jan 1",
                "--time",
                "6pm",
                "--location",
                "Philly",
                "--description",
                "Desc",
            ],
        ):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
