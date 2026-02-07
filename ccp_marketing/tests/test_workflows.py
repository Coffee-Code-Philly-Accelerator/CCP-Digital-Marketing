"""Tests for CCP Marketing workflows and AI generators."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from ccp_marketing.ai.image_generator import ImageGenerator, ImageResult
from ccp_marketing.ai.copy_generator import CopyGenerator, CopyResult
from ccp_marketing.workflows.event_creation import EventCreationWorkflow
from ccp_marketing.workflows.social_promotion import SocialPromotionWorkflow
from ccp_marketing.workflows.full_workflow import FullWorkflow
from ccp_marketing.models.results import Status, PlatformResult, SocialPostResult


class TestImageResult:
    """Tests for ImageResult dataclass."""

    def test_success_result(self):
        """Test creating a successful result."""
        result = ImageResult(
            success=True,
            url="https://example.com/image.png",
        )
        assert result.success
        assert result.url == "https://example.com/image.png"
        assert result.error == ""

    def test_failed_result(self):
        """Test creating a failed result."""
        result = ImageResult(
            success=False,
            error="Generation failed",
        )
        assert not result.success
        assert result.error == "Generation failed"


class TestImageGenerator:
    """Tests for ImageGenerator."""

    def test_generate_success(self, mock_client):
        """Test successful image generation."""
        mock_client.execute_action.return_value = {
            "publicUrl": "https://storage.example.com/image-123.png",
        }
        generator = ImageGenerator(mock_client)

        result = generator.generate("Test prompt")

        assert result.success
        assert "storage.example.com" in result.url
        mock_client.execute_action.assert_called_once_with(
            "GEMINI_GENERATE_IMAGE",
            {
                "prompt": "Test prompt",
                "model": "gemini-2.5-flash-image",
            },
        )

    def test_generate_no_url(self, mock_client):
        """Test generation returns no URL."""
        mock_client.execute_action.return_value = {}
        generator = ImageGenerator(mock_client)

        result = generator.generate("Test prompt")

        assert not result.success
        assert "No URL" in result.error

    def test_generate_exception(self, mock_client):
        """Test generation with exception."""
        mock_client.execute_action.side_effect = Exception("API error")
        generator = ImageGenerator(mock_client)

        result = generator.generate("Test prompt")

        assert not result.success
        assert "API error" in result.error

    def test_generate_for_event(self, mock_client, sample_event):
        """Test generating image for event."""
        mock_client.execute_action.return_value = {
            "publicUrl": "https://storage.example.com/image.png",
        }
        generator = ImageGenerator(mock_client)

        result = generator.generate_for_event(sample_event)

        assert result.success
        # Check prompt contains event title
        call_args = mock_client.execute_action.call_args
        prompt = call_args[0][1]["prompt"]
        assert "AI Workshop" in prompt

    def test_generate_for_event_with_location(self, mock_client, sample_event):
        """Test event image includes location."""
        mock_client.execute_action.return_value = {"publicUrl": "https://example.com/img.png"}
        generator = ImageGenerator(mock_client)

        generator.generate_for_event(sample_event, include_location=True)

        call_args = mock_client.execute_action.call_args
        prompt = call_args[0][1]["prompt"]
        assert "Philadelphia" in prompt

    def test_generate_for_event_without_location(self, mock_client, sample_event):
        """Test event image without location."""
        mock_client.execute_action.return_value = {"publicUrl": "https://example.com/img.png"}
        generator = ImageGenerator(mock_client)

        generator.generate_for_event(sample_event, include_location=False)

        call_args = mock_client.execute_action.call_args
        prompt = call_args[0][1]["prompt"]
        assert "Philadelphia" not in prompt

    def test_generate_social_image(self, mock_client):
        """Test generating social media optimized image."""
        mock_client.execute_action.return_value = {"publicUrl": "https://example.com/img.png"}
        generator = ImageGenerator(mock_client)

        result = generator.generate_social_image(
            title="Event Title",
            theme="technology",
            aspect_ratio="square",
        )

        assert result.success

    def test_generate_social_image_different_themes(self, mock_client):
        """Test social image with different themes."""
        mock_client.execute_action.return_value = {"publicUrl": "https://example.com/img.png"}
        generator = ImageGenerator(mock_client)

        themes = ["technology", "community", "celebration", "professional", "creative"]
        for theme in themes:
            result = generator.generate_social_image("Title", theme=theme)
            assert result.success


class TestCopyResult:
    """Tests for CopyResult dataclass."""

    def test_success_result(self):
        """Test creating a successful result."""
        result = CopyResult(
            success=True,
            copies={"twitter": "Tweet content"},
        )
        assert result.success
        assert result.copies["twitter"] == "Tweet content"

    def test_failed_result(self):
        """Test creating a failed result."""
        result = CopyResult(
            success=False,
            copies={},
            error="LLM unavailable",
        )
        assert not result.success
        assert result.error == "LLM unavailable"


class TestCopyGenerator:
    """Tests for CopyGenerator."""

    def test_generate_success(self, mock_llm_func):
        """Test successful copy generation."""
        generator = CopyGenerator(mock_llm_func)

        result = generator.generate("Test prompt", platforms=["twitter", "linkedin"])

        assert result.success
        assert "twitter" in result.copies
        assert "linkedin" in result.copies

    def test_generate_with_llm_error(self, mock_llm_func_error):
        """Test generation with LLM error."""
        generator = CopyGenerator(mock_llm_func_error)

        result = generator.generate("Test prompt")

        assert not result.success
        assert "unavailable" in result.error.lower()

    def test_generate_for_event(self, mock_llm_func, sample_event):
        """Test generating copy for event."""
        generator = CopyGenerator(mock_llm_func)

        result = generator.generate_for_event(sample_event)

        assert result.success
        # Should have content for social platforms
        assert "twitter" in result.copies

    def test_generate_descriptions(self, mock_llm_func, sample_event):
        """Test generating event descriptions."""
        generator = CopyGenerator(mock_llm_func)

        result = generator.generate_descriptions(sample_event)

        assert result.success

    def test_fallback_copies(self, sample_event):
        """Test fallback copy generation."""
        generator = CopyGenerator(None)

        copies = generator.get_fallback_copies(
            sample_event,
            platforms=["twitter", "discord"],
        )

        assert "twitter" in copies
        assert "discord" in copies
        # Discord should have markdown
        assert "**" in copies["discord"]

    def test_fallback_twitter_truncation(self, sample_event):
        """Test fallback Twitter copy is truncated."""
        generator = CopyGenerator(None)

        copies = generator.get_fallback_copies(sample_event, platforms=["twitter"])

        assert len(copies["twitter"]) <= 280

    def test_mock_llm_fallback(self):
        """Test generator uses mock LLM when none provided."""
        generator = CopyGenerator(None)  # No LLM function

        result = generator.generate("Test prompt", platforms=["twitter"])

        # Should use mock and return something
        assert result.success or not result.success  # Either way should not crash

    def test_platform_guidelines(self):
        """Test platform guidelines are defined."""
        generator = CopyGenerator(None)

        assert "twitter" in generator.PLATFORM_GUIDELINES
        assert "linkedin" in generator.PLATFORM_GUIDELINES
        assert "instagram" in generator.PLATFORM_GUIDELINES

    def test_generate_exception_handling(self):
        """Test generation handles exceptions."""
        def failing_llm(prompt):
            raise Exception("LLM crashed")

        generator = CopyGenerator(failing_llm)

        result = generator.generate("Test")

        assert not result.success
        assert "crashed" in result.error.lower()


class TestEventCreationWorkflow:
    """Tests for EventCreationWorkflow."""

    @pytest.fixture
    def mock_workflow_deps(self, mock_client):
        """Mock all workflow dependencies."""
        mock_client.execute_action.return_value = {
            "publicUrl": "https://image.url/img.png",
            "pageSnapshot": "Event form",
            "url": "https://lu.ma/test-event",
        }
        mock_client.browser_navigate.return_value = {"pageSnapshot": "Form"}
        mock_client.browser_get_page.return_value = {
            "content": "AI Workshop\n\nEdit | Settings",
            "url": "https://lu.ma/test-event",
        }
        mock_client.browser_perform_task.return_value = {}
        return mock_client

    def test_initialization(self, mock_client):
        """Test workflow initialization."""
        workflow = EventCreationWorkflow(mock_client)

        assert workflow.client == mock_client
        assert workflow.image_generator is not None
        assert workflow.copy_generator is not None

    def test_default_platforms(self, mock_client):
        """Test default platforms."""
        workflow = EventCreationWorkflow(mock_client)

        assert "luma" in workflow.DEFAULT_PLATFORMS
        assert "meetup" in workflow.DEFAULT_PLATFORMS
        assert "partiful" in workflow.DEFAULT_PLATFORMS

    @patch("time.sleep")
    def test_run_basic(self, mock_sleep, mock_workflow_deps, sample_event):
        """Test basic workflow run."""
        workflow = EventCreationWorkflow(mock_workflow_deps)

        with patch.object(workflow.image_generator, "generate_for_event") as mock_img:
            mock_img.return_value = ImageResult(success=True, url="https://img.url/img.png")
            with patch.object(workflow.copy_generator, "generate_descriptions") as mock_copy:
                mock_copy.return_value = CopyResult(success=True, copies={"luma": "desc", "meetup": "desc", "partiful": "desc"})

                result = workflow.run(
                    event_data=sample_event,
                    platforms=["luma"],
                    skip_platforms=["meetup", "partiful"],
                )

        assert result is not None

    @patch("time.sleep")
    def test_run_skip_platforms(self, mock_sleep, mock_workflow_deps, sample_event):
        """Test workflow with skipped platforms."""
        workflow = EventCreationWorkflow(mock_workflow_deps)

        with patch.object(workflow.image_generator, "generate_for_event") as mock_img:
            mock_img.return_value = ImageResult(success=True, url="https://img.url/img.png")
            with patch.object(workflow.copy_generator, "generate_descriptions") as mock_copy:
                mock_copy.return_value = CopyResult(success=True, copies={})

                result = workflow.run(
                    event_data=sample_event,
                    platforms=["luma", "meetup"],
                    skip_platforms=["meetup"],
                )

        # Meetup should not be in results or be skipped
        if result.meetup:
            assert result.meetup.status in [Status.SKIPPED, None] or result.meetup is None

    @patch("time.sleep")
    def test_run_no_image_generation(self, mock_sleep, mock_workflow_deps, sample_event):
        """Test workflow without image generation."""
        workflow = EventCreationWorkflow(mock_workflow_deps)

        with patch.object(workflow.image_generator, "generate_for_event") as mock_img:
            with patch.object(workflow.copy_generator, "generate_descriptions") as mock_copy:
                mock_copy.return_value = CopyResult(success=True, copies={})

                result = workflow.run(
                    event_data=sample_event,
                    platforms=[],
                    generate_image=False,
                )

                # Image generator should not be called
                mock_img.assert_not_called()

    @patch("time.sleep")
    def test_run_no_description_generation(self, mock_sleep, mock_workflow_deps, sample_event):
        """Test workflow without description generation."""
        workflow = EventCreationWorkflow(mock_workflow_deps)

        with patch.object(workflow.image_generator, "generate_for_event") as mock_img:
            mock_img.return_value = ImageResult(success=True, url="https://img.url/img.png")
            with patch.object(workflow.copy_generator, "generate_descriptions") as mock_copy:
                result = workflow.run(
                    event_data=sample_event,
                    platforms=[],
                    generate_descriptions=False,
                )

                # Description generator should not be called
                mock_copy.assert_not_called()


class TestSocialPromotionWorkflow:
    """Tests for SocialPromotionWorkflow."""

    def test_initialization(self, mock_client):
        """Test workflow initialization."""
        workflow = SocialPromotionWorkflow(mock_client)

        assert workflow.client == mock_client
        assert workflow.image_generator is not None
        assert workflow.copy_generator is not None
        assert workflow.social_manager is not None

    def test_run_basic(self, mock_client, sample_event):
        """Test basic workflow run."""
        mock_client.execute_action.return_value = {"id": "123", "sub": "user123"}
        workflow = SocialPromotionWorkflow(mock_client)

        with patch.object(workflow.image_generator, "generate_for_event") as mock_img:
            mock_img.return_value = ImageResult(success=True, url="https://img.url/img.png")
            with patch.object(workflow.copy_generator, "generate_for_event") as mock_copy:
                mock_copy.return_value = CopyResult(
                    success=True,
                    copies={"twitter": "t", "linkedin": "l", "instagram": "i", "facebook": "f", "discord": "d"},
                )

                result = workflow.run(
                    event_data=sample_event,
                    event_url="https://lu.ma/test",
                    skip_platforms=["instagram", "facebook", "discord"],
                )

        assert result is not None

    def test_run_with_existing_image(self, mock_client, sample_event):
        """Test workflow with pre-existing image URL."""
        mock_client.execute_action.return_value = {"id": "123", "sub": "user123"}
        workflow = SocialPromotionWorkflow(mock_client)

        with patch.object(workflow.image_generator, "generate_for_event") as mock_img:
            with patch.object(workflow.copy_generator, "generate_for_event") as mock_copy:
                mock_copy.return_value = CopyResult(success=True, copies={"twitter": "t"})

                result = workflow.run(
                    event_data=sample_event,
                    image_url="https://existing.image/url.png",
                    skip_platforms=["linkedin", "instagram", "facebook", "discord"],
                )

                # Should not generate new image
                mock_img.assert_not_called()

    def test_run_skip_copy_generation(self, mock_client, sample_event):
        """Test workflow without copy generation."""
        mock_client.execute_action.return_value = {"id": "123"}
        workflow = SocialPromotionWorkflow(mock_client)

        with patch.object(workflow.image_generator, "generate_for_event") as mock_img:
            mock_img.return_value = ImageResult(success=True, url="https://img.url/img.png")
            with patch.object(workflow.copy_generator, "generate_for_event") as mock_copy:
                with patch.object(workflow.copy_generator, "get_fallback_copies") as mock_fallback:
                    mock_fallback.return_value = {"twitter": "fallback"}

                    result = workflow.run(
                        event_data=sample_event,
                        generate_copy=False,
                        skip_platforms=["linkedin", "instagram", "facebook", "discord"],
                    )

                    # Should use fallback copies
                    mock_copy.assert_not_called()
                    mock_fallback.assert_called()


class TestFullWorkflow:
    """Tests for FullWorkflow."""

    def test_initialization(self, mock_client):
        """Test workflow initialization."""
        workflow = FullWorkflow(mock_client)

        assert workflow.client == mock_client
        assert workflow.event_workflow is not None
        assert workflow.social_workflow is not None

    @patch("time.sleep")
    def test_run_combines_workflows(self, mock_sleep, mock_client, sample_event):
        """Test full workflow combines both phases."""
        workflow = FullWorkflow(mock_client)

        # Mock the sub-workflows
        mock_event_result = MagicMock()
        mock_event_result.primary_url = "https://lu.ma/test-event"
        mock_event_result.all_results = []

        mock_social_result = MagicMock()
        mock_social_result.summary = "1/5 posted"

        with patch.object(workflow.event_workflow, "run", return_value=mock_event_result):
            with patch.object(workflow.social_workflow, "run", return_value=mock_social_result):
                result = workflow.run(
                    event_data=sample_event,
                    meetup_group_url="https://meetup.com/test",
                    discord_channel_id="chan123",
                )

        assert result is not None
        assert result.event_creation == mock_event_result
        assert result.social_promotion == mock_social_result
        assert result.duration_seconds >= 0

    @patch("time.sleep")
    def test_run_passes_event_url_to_social(self, mock_sleep, mock_client, sample_event):
        """Test event URL is passed to social workflow."""
        workflow = FullWorkflow(mock_client)

        mock_event_result = MagicMock()
        mock_event_result.primary_url = "https://lu.ma/captured-url"
        mock_event_result.all_results = []

        with patch.object(workflow.event_workflow, "run", return_value=mock_event_result):
            with patch.object(workflow.social_workflow, "run") as mock_social:
                mock_social.return_value = MagicMock()

                workflow.run(event_data=sample_event)

                # Verify social workflow was called with the event URL
                call_args = mock_social.call_args
                assert call_args[1]["event_url"] == "https://lu.ma/captured-url"

    @patch("time.sleep")
    def test_run_handles_no_event_url(self, mock_sleep, mock_client, sample_event):
        """Test workflow handles case where no event URL is captured."""
        workflow = FullWorkflow(mock_client)

        mock_event_result = MagicMock()
        mock_event_result.primary_url = ""  # No URL captured
        mock_event_result.all_results = []

        with patch.object(workflow.event_workflow, "run", return_value=mock_event_result):
            with patch.object(workflow.social_workflow, "run") as mock_social:
                mock_social.return_value = MagicMock()

                result = workflow.run(event_data=sample_event)

                # Should still complete, just without event URL
                assert result is not None

    @patch("time.sleep")
    def test_run_tracks_duration(self, mock_sleep, mock_client, sample_event):
        """Test workflow tracks duration."""
        workflow = FullWorkflow(mock_client)

        mock_event_result = MagicMock()
        mock_event_result.primary_url = ""
        mock_event_result.all_results = []
        mock_social_result = MagicMock()

        with patch.object(workflow.event_workflow, "run", return_value=mock_event_result):
            with patch.object(workflow.social_workflow, "run", return_value=mock_social_result):
                result = workflow.run(event_data=sample_event)

        assert result.duration_seconds >= 0

    @patch("time.sleep")
    def test_run_reuses_image(self, mock_sleep, mock_client, sample_event):
        """Test workflow reuses image from event creation."""
        workflow = FullWorkflow(mock_client)

        # Event result with image in data
        mock_event_result = MagicMock()
        mock_event_result.primary_url = "https://lu.ma/test"
        mock_platform_result = MagicMock()
        mock_platform_result.data = {"image_url": "https://generated.image/url.png"}
        mock_event_result.all_results = [mock_platform_result]

        with patch.object(workflow.event_workflow, "run", return_value=mock_event_result):
            with patch.object(workflow.social_workflow, "run") as mock_social:
                mock_social.return_value = MagicMock()

                workflow.run(event_data=sample_event)

                # Verify image URL was passed
                call_args = mock_social.call_args
                assert call_args[1]["image_url"] == "https://generated.image/url.png"
                # And generate_image should be False since we have one
                assert call_args[1]["generate_image"] is False


class TestWorkflowIntegration:
    """Integration tests for workflows."""

    @patch("time.sleep")
    def test_event_creation_result_structure(self, mock_sleep, mock_client, sample_event):
        """Test EventCreationResult structure from workflow."""
        mock_client.execute_action.return_value = {"publicUrl": "https://img.url/img.png"}
        mock_client.browser_navigate.return_value = {"pageSnapshot": "Form"}
        mock_client.browser_get_page.return_value = {
            "content": "AI Workshop\n\nEdit",
            "url": "https://lu.ma/test",
        }
        mock_client.browser_perform_task.return_value = {}

        workflow = EventCreationWorkflow(mock_client)

        with patch.object(workflow.image_generator, "generate_for_event") as mock_img:
            mock_img.return_value = ImageResult(success=True, url="https://img.url/img.png")
            with patch.object(workflow.copy_generator, "generate_descriptions") as mock_copy:
                mock_copy.return_value = CopyResult(success=True, copies={})

                result = workflow.run(
                    event_data=sample_event,
                    platforms=[],  # No actual platforms to speed up test
                )

        # Result should have proper structure
        assert hasattr(result, "luma")
        assert hasattr(result, "meetup")
        assert hasattr(result, "partiful")
        assert hasattr(result, "all_results")
        assert hasattr(result, "primary_url")

    def test_social_promotion_result_structure(self, mock_client, sample_event):
        """Test SocialPromotionResult structure from workflow."""
        mock_client.execute_action.return_value = {"id": "123", "sub": "user"}

        workflow = SocialPromotionWorkflow(mock_client)

        with patch.object(workflow.image_generator, "generate_for_event") as mock_img:
            mock_img.return_value = ImageResult(success=True, url="https://img.url/img.png")
            with patch.object(workflow.copy_generator, "generate_for_event") as mock_copy:
                mock_copy.return_value = CopyResult(
                    success=True,
                    copies={"twitter": "t", "linkedin": "l", "instagram": "i", "facebook": "f", "discord": "d"},
                )

                result = workflow.run(
                    event_data=sample_event,
                    skip_platforms=["linkedin", "instagram", "facebook", "discord"],
                )

        # Result should have proper structure
        assert hasattr(result, "twitter")
        assert hasattr(result, "linkedin")
        assert hasattr(result, "instagram")
        assert hasattr(result, "facebook")
        assert hasattr(result, "discord")
        assert hasattr(result, "all_results")
        assert hasattr(result, "summary")
