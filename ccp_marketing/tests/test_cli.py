"""Tests for CCP Marketing CLI."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typer.testing import CliRunner

from ccp_marketing.cli.main import app, get_client, print_result
from ccp_marketing.models.results import (
    Status,
    PlatformResult,
    EventCreationResult,
    SocialPostResult,
    SocialPromotionResult,
    WorkflowResult,
)


runner = CliRunner()


class TestCLIHelp:
    """Tests for CLI help and info commands."""

    def test_help(self):
        """Test CLI shows help."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "ccp-marketing" in result.stdout or "CCP" in result.stdout

    def test_info_command(self):
        """Test info command shows workflow info."""
        result = runner.invoke(app, ["info"])
        assert result.exit_code == 0
        assert "create-event" in result.stdout
        assert "promote" in result.stdout

    def test_info_create_only(self):
        """Test info command with --recipe create."""
        result = runner.invoke(app, ["info", "--recipe", "create"])
        assert result.exit_code == 0
        assert "create-event" in result.stdout

    def test_info_promote_only(self):
        """Test info command with --recipe promote."""
        result = runner.invoke(app, ["info", "--recipe", "promote"])
        assert result.exit_code == 0
        assert "promote" in result.stdout

    def test_version_command(self):
        """Test version command."""
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "CCP Marketing" in result.stdout


class TestCreateEventCommand:
    """Tests for create-event command."""

    @pytest.fixture
    def mock_workflow(self):
        """Mock EventCreationWorkflow."""
        with patch("ccp_marketing.cli.main.EventCreationWorkflow") as mock:
            mock_result = EventCreationResult(
                luma=PlatformResult(
                    platform="luma",
                    status=Status.PUBLISHED,
                    url="https://lu.ma/test-event",
                ),
            )
            mock.return_value.run.return_value = mock_result
            yield mock

    @pytest.fixture
    def mock_client(self):
        """Mock get_client function."""
        with patch("ccp_marketing.cli.main.get_client") as mock:
            mock.return_value = Mock()
            yield mock

    def test_create_event_success(self, mock_client, mock_workflow):
        """Test successful event creation."""
        result = runner.invoke(app, [
            "create-event",
            "--title", "Test Event",
            "--date", "January 25, 2025",
            "--time", "6:00 PM EST",
            "--location", "Test Venue",
            "--description", "Test description",
        ])

        assert result.exit_code == 0
        mock_workflow.return_value.run.assert_called_once()

    def test_create_event_with_platforms(self, mock_client, mock_workflow):
        """Test event creation with platform selection."""
        result = runner.invoke(app, [
            "create-event",
            "--title", "Test Event",
            "--date", "January 25, 2025",
            "--time", "6:00 PM EST",
            "--location", "Test Venue",
            "--description", "Test description",
            "--platforms", "luma,meetup",
        ])

        assert result.exit_code == 0
        call_args = mock_workflow.return_value.run.call_args
        assert "luma" in call_args[1]["platforms"]
        assert "meetup" in call_args[1]["platforms"]

    def test_create_event_with_skip(self, mock_client, mock_workflow):
        """Test event creation with skipped platforms."""
        result = runner.invoke(app, [
            "create-event",
            "--title", "Test Event",
            "--date", "January 25, 2025",
            "--time", "6:00 PM EST",
            "--location", "Test Venue",
            "--description", "Test description",
            "--skip", "meetup,partiful",
        ])

        assert result.exit_code == 0
        call_args = mock_workflow.return_value.run.call_args
        assert "meetup" in call_args[1]["skip_platforms"]
        assert "partiful" in call_args[1]["skip_platforms"]

    def test_create_event_with_meetup_url(self, mock_client, mock_workflow):
        """Test event creation with Meetup URL."""
        result = runner.invoke(app, [
            "create-event",
            "--title", "Test Event",
            "--date", "January 25, 2025",
            "--time", "6:00 PM EST",
            "--location", "Test Venue",
            "--description", "Test description",
            "--meetup-url", "https://meetup.com/test-group",
        ])

        assert result.exit_code == 0
        call_args = mock_workflow.return_value.run.call_args
        assert call_args[1]["meetup_group_url"] == "https://meetup.com/test-group"

    def test_create_event_json_output(self, mock_client, mock_workflow):
        """Test event creation with JSON output."""
        result = runner.invoke(app, [
            "create-event",
            "--title", "Test Event",
            "--date", "January 25, 2025",
            "--time", "6:00 PM EST",
            "--location", "Test Venue",
            "--description", "Test description",
            "--json",
        ])

        assert result.exit_code == 0
        # JSON output should be present
        assert "{" in result.stdout

    def test_create_event_validation_error(self, mock_client, mock_workflow):
        """Test event creation with missing required fields."""
        result = runner.invoke(app, [
            "create-event",
            "--title", "",  # Empty title
            "--date", "January 25, 2025",
            "--time", "6:00 PM EST",
            "--location", "Test Venue",
            "--description", "Test description",
        ])

        assert result.exit_code == 1
        assert "Validation" in result.stdout or "required" in result.stdout.lower()


class TestPromoteCommand:
    """Tests for promote command."""

    @pytest.fixture
    def mock_workflow(self):
        """Mock SocialPromotionWorkflow."""
        with patch("ccp_marketing.cli.main.SocialPromotionWorkflow") as mock:
            mock_result = SocialPromotionResult(
                twitter=SocialPostResult(
                    platform="twitter",
                    status=Status.SUCCESS,
                    post_id="12345",
                ),
            )
            mock.return_value.run.return_value = mock_result
            yield mock

    @pytest.fixture
    def mock_client(self):
        """Mock get_client function."""
        with patch("ccp_marketing.cli.main.get_client") as mock:
            mock.return_value = Mock()
            yield mock

    def test_promote_success(self, mock_client, mock_workflow):
        """Test successful promotion."""
        result = runner.invoke(app, [
            "promote",
            "--title", "Test Event",
            "--date", "January 25, 2025",
            "--time", "6:00 PM EST",
            "--location", "Test Venue",
            "--description", "Test description",
            "--event-url", "https://lu.ma/test-event",
        ])

        assert result.exit_code == 0
        mock_workflow.return_value.run.assert_called_once()

    def test_promote_with_discord(self, mock_client, mock_workflow):
        """Test promotion with Discord channel."""
        result = runner.invoke(app, [
            "promote",
            "--title", "Test Event",
            "--date", "January 25, 2025",
            "--time", "6:00 PM EST",
            "--location", "Test Venue",
            "--description", "Test description",
            "--event-url", "https://lu.ma/test",
            "--discord-channel", "1234567890",
        ])

        assert result.exit_code == 0
        call_args = mock_workflow.return_value.run.call_args
        assert call_args[1]["discord_channel_id"] == "1234567890"

    def test_promote_with_facebook(self, mock_client, mock_workflow):
        """Test promotion with Facebook page."""
        result = runner.invoke(app, [
            "promote",
            "--title", "Test Event",
            "--date", "January 25, 2025",
            "--time", "6:00 PM EST",
            "--location", "Test Venue",
            "--description", "Test description",
            "--event-url", "https://lu.ma/test",
            "--facebook-page", "page123",
        ])

        assert result.exit_code == 0
        call_args = mock_workflow.return_value.run.call_args
        assert call_args[1]["facebook_page_id"] == "page123"

    def test_promote_with_skip(self, mock_client, mock_workflow):
        """Test promotion with skipped platforms."""
        result = runner.invoke(app, [
            "promote",
            "--title", "Test Event",
            "--date", "January 25, 2025",
            "--time", "6:00 PM EST",
            "--location", "Test Venue",
            "--description", "Test description",
            "--event-url", "https://lu.ma/test",
            "--skip", "twitter,linkedin",
        ])

        assert result.exit_code == 0
        call_args = mock_workflow.return_value.run.call_args
        assert "twitter" in call_args[1]["skip_platforms"]
        assert "linkedin" in call_args[1]["skip_platforms"]

    def test_promote_json_output(self, mock_client, mock_workflow):
        """Test promotion with JSON output."""
        result = runner.invoke(app, [
            "promote",
            "--title", "Test Event",
            "--date", "January 25, 2025",
            "--time", "6:00 PM EST",
            "--location", "Test Venue",
            "--description", "Test description",
            "--event-url", "https://lu.ma/test",
            "--json",
        ])

        assert result.exit_code == 0
        assert "{" in result.stdout


class TestFullWorkflowCommand:
    """Tests for full-workflow command."""

    @pytest.fixture
    def mock_workflow(self):
        """Mock FullWorkflow."""
        with patch("ccp_marketing.cli.main.FullWorkflow") as mock:
            event_result = EventCreationResult(
                luma=PlatformResult(
                    platform="luma",
                    status=Status.PUBLISHED,
                    url="https://lu.ma/test",
                ),
            )
            social_result = SocialPromotionResult(
                twitter=SocialPostResult(
                    platform="twitter",
                    status=Status.SUCCESS,
                ),
            )
            mock_result = WorkflowResult(
                event_creation=event_result,
                social_promotion=social_result,
                primary_url="https://lu.ma/test",
                duration_seconds=45.5,
            )
            mock.return_value.run.return_value = mock_result
            yield mock

    @pytest.fixture
    def mock_client(self):
        """Mock get_client function."""
        with patch("ccp_marketing.cli.main.get_client") as mock:
            mock.return_value = Mock()
            yield mock

    def test_full_workflow_success(self, mock_client, mock_workflow):
        """Test successful full workflow."""
        result = runner.invoke(app, [
            "full-workflow",
            "--title", "Test Event",
            "--date", "January 25, 2025",
            "--time", "6:00 PM EST",
            "--location", "Test Venue",
            "--description", "Test description",
        ])

        assert result.exit_code == 0
        mock_workflow.return_value.run.assert_called_once()

    def test_full_workflow_with_meetup(self, mock_client, mock_workflow):
        """Test full workflow with Meetup URL."""
        result = runner.invoke(app, [
            "full-workflow",
            "--title", "Test Event",
            "--date", "January 25, 2025",
            "--time", "6:00 PM EST",
            "--location", "Test Venue",
            "--description", "Test description",
            "--meetup-url", "https://meetup.com/test",
        ])

        assert result.exit_code == 0
        call_args = mock_workflow.return_value.run.call_args
        assert call_args[1]["meetup_group_url"] == "https://meetup.com/test"

    def test_full_workflow_with_all_options(self, mock_client, mock_workflow):
        """Test full workflow with all optional arguments."""
        result = runner.invoke(app, [
            "full-workflow",
            "--title", "Test Event",
            "--date", "January 25, 2025",
            "--time", "6:00 PM EST",
            "--location", "Test Venue",
            "--description", "Test description",
            "--meetup-url", "https://meetup.com/test",
            "--discord-channel", "chan123",
            "--facebook-page", "page123",
        ])

        assert result.exit_code == 0
        call_args = mock_workflow.return_value.run.call_args
        assert call_args[1]["meetup_group_url"] == "https://meetup.com/test"
        assert call_args[1]["discord_channel_id"] == "chan123"
        assert call_args[1]["facebook_page_id"] == "page123"

    def test_full_workflow_json_output(self, mock_client, mock_workflow):
        """Test full workflow with JSON output."""
        result = runner.invoke(app, [
            "full-workflow",
            "--title", "Test Event",
            "--date", "January 25, 2025",
            "--time", "6:00 PM EST",
            "--location", "Test Venue",
            "--description", "Test description",
            "--json",
        ])

        assert result.exit_code == 0
        assert "{" in result.stdout

    def test_full_workflow_validation_error(self, mock_client, mock_workflow):
        """Test full workflow with validation error."""
        result = runner.invoke(app, [
            "full-workflow",
            "--title", "",  # Empty title
            "--date", "January 25, 2025",
            "--time", "6:00 PM EST",
            "--location", "Test Venue",
            "--description", "Test description",
        ])

        assert result.exit_code == 1


class TestGetClient:
    """Tests for get_client function."""

    def test_get_client_with_valid_key(self):
        """Test get_client with valid API key."""
        with patch.dict("os.environ", {"COMPOSIO_API_KEY": "test-api-key"}):
            with patch("ccp_marketing.cli.main.ComposioClient") as mock_client:
                with patch("ccp_marketing.cli.main.Config.from_env") as mock_config:
                    mock_config_instance = Mock()
                    mock_config_instance.validate.return_value = None
                    mock_config.return_value = mock_config_instance

                    client = get_client()

                    mock_client.assert_called_once()

    def test_get_client_without_key(self):
        """Test get_client without API key raises exit."""
        with patch.dict("os.environ", {}, clear=True):
            with patch("ccp_marketing.cli.main.Config.from_env") as mock_config:
                mock_config.return_value.validate.side_effect = ValueError("API key required")

                # typer.Exit doesn't raise SystemExit in the same way
                import typer
                with pytest.raises(typer.Exit):
                    get_client()


class TestCLIErrorHandling:
    """Tests for CLI error handling."""

    @pytest.fixture
    def mock_client(self):
        """Mock get_client function."""
        with patch("ccp_marketing.cli.main.get_client") as mock:
            mock.return_value = Mock()
            yield mock

    def test_workflow_error_handling(self, mock_client):
        """Test CLI handles workflow errors gracefully."""
        with patch("ccp_marketing.cli.main.EventCreationWorkflow") as mock_workflow:
            from ccp_marketing.core.exceptions import CCPMarketingError
            mock_workflow.return_value.run.side_effect = CCPMarketingError("Test error")

            result = runner.invoke(app, [
                "create-event",
                "--title", "Test Event",
                "--date", "January 25, 2025",
                "--time", "6:00 PM EST",
                "--location", "Test Venue",
                "--description", "Test description",
            ])

            assert result.exit_code == 1
            assert "Error" in result.stdout


class TestCLIShortOptions:
    """Tests for CLI short option aliases."""

    @pytest.fixture
    def mock_workflow(self):
        """Mock EventCreationWorkflow."""
        with patch("ccp_marketing.cli.main.EventCreationWorkflow") as mock:
            mock_result = EventCreationResult()
            mock.return_value.run.return_value = mock_result
            yield mock

    @pytest.fixture
    def mock_client(self):
        """Mock get_client function."""
        with patch("ccp_marketing.cli.main.get_client") as mock:
            mock.return_value = Mock()
            yield mock

    def test_short_options(self, mock_client, mock_workflow):
        """Test using short option aliases."""
        result = runner.invoke(app, [
            "create-event",
            "-t", "Test Event",
            "-d", "January 25, 2025",
            "--time", "6:00 PM EST",
            "-l", "Test Venue",
            "--description", "Test description",
            "-p", "luma",
            "-s", "meetup",
        ])

        assert result.exit_code == 0
        call_args = mock_workflow.return_value.run.call_args
        assert call_args[1]["event_data"].title == "Test Event"
        assert "luma" in call_args[1]["platforms"]
        assert "meetup" in call_args[1]["skip_platforms"]
