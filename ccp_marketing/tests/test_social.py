"""Tests for CCP Marketing social media posters."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import Future

from ccp_marketing.models.results import Status, SocialPostResult
from ccp_marketing.social.base import BaseSocialPoster
from ccp_marketing.social.twitter import TwitterPoster
from ccp_marketing.social.linkedin import LinkedInPoster
from ccp_marketing.social.instagram import InstagramPoster
from ccp_marketing.social.facebook import FacebookPoster
from ccp_marketing.social.discord import DiscordPoster
from ccp_marketing.social.manager import SocialPromotionManager


class TestBaseSocialPoster:
    """Tests for BaseSocialPoster base class."""

    def test_truncate_content_short(self, mock_client):
        """Test truncation of short content."""
        poster = TwitterPoster(mock_client)
        content = "Short content"

        result = poster.truncate_content(content)
        assert result == content

    def test_truncate_content_long(self, mock_client):
        """Test truncation of long content."""
        poster = TwitterPoster(mock_client)
        content = "A" * 500

        result = poster.truncate_content(content)
        assert len(result) <= 280
        assert result.endswith("...")

    def test_truncate_content_with_reserve(self, mock_client):
        """Test truncation with reserved characters."""
        poster = TwitterPoster(mock_client)
        content = "A" * 250

        result = poster.truncate_content(content, reserve=50)
        assert len(result) <= 280 - 50

    def test_truncate_at_word_boundary(self, mock_client):
        """Test truncation at word boundary."""
        poster = TwitterPoster(mock_client)
        content = "word " * 100

        result = poster.truncate_content(content)
        # Should end with ... after a space
        assert result.endswith("...")
        # Should not end with partial word
        assert "word..." in result or "word ..." in result

    def test_success_result(self, mock_client):
        """Test creating success result."""
        poster = TwitterPoster(mock_client)

        result = poster._success_result(
            message="Posted successfully",
            post_id="12345",
            post_url="https://twitter.com/user/status/12345",
        )

        assert result.status == Status.SUCCESS
        assert result.platform == "twitter"
        assert result.post_id == "12345"
        assert result.post_url == "https://twitter.com/user/status/12345"

    def test_failed_result(self, mock_client):
        """Test creating failed result."""
        poster = TwitterPoster(mock_client)

        result = poster._failed_result("API rate limit exceeded")

        assert result.status == Status.FAILED
        assert result.platform == "twitter"
        assert result.error == "API rate limit exceeded"

    def test_skipped_result(self, mock_client):
        """Test creating skipped result."""
        poster = TwitterPoster(mock_client)

        result = poster._skipped_result("Platform disabled")

        assert result.status == Status.SKIPPED
        assert result.platform == "twitter"
        assert result.message == "Platform disabled"


class TestTwitterPoster:
    """Tests for TwitterPoster."""

    def test_class_attributes(self):
        """Test Twitter class attributes."""
        assert TwitterPoster.name == "twitter"
        assert TwitterPoster.max_length == 280

    def test_post_success(self, mock_client):
        """Test successful tweet posting."""
        mock_client.execute_action.return_value = {
            "id": "12345678",
            "user": {"screen_name": "testuser"},
        }
        poster = TwitterPoster(mock_client)

        result = poster.post("Test tweet content")

        assert result.status == Status.SUCCESS
        assert result.post_id == "12345678"
        assert "twitter.com" in result.post_url
        mock_client.execute_action.assert_called_once_with(
            "TWITTER_CREATION_OF_A_POST",
            {"text": "Test tweet content"},
        )

    def test_post_with_image_url(self, mock_client, sample_event):
        """Test tweet with image URL."""
        mock_client.execute_action.return_value = {"id": "12345"}
        poster = TwitterPoster(mock_client)

        result = poster.post(
            "Test content",
            event_data=sample_event,
            image_url="https://example.com/image.png",
        )

        assert result.status == Status.SUCCESS
        call_args = mock_client.execute_action.call_args
        text = call_args[0][1]["text"]
        assert "https://example.com/image.png" in text

    def test_post_truncates_long_content(self, mock_client):
        """Test that long tweets are truncated."""
        mock_client.execute_action.return_value = {"id": "12345"}
        poster = TwitterPoster(mock_client)
        long_content = "A" * 500

        poster.post(long_content)

        call_args = mock_client.execute_action.call_args
        text = call_args[0][1]["text"]
        assert len(text) <= 280

    def test_post_failure(self, mock_client):
        """Test tweet posting failure."""
        mock_client.execute_action.side_effect = Exception("API error")
        poster = TwitterPoster(mock_client)

        result = poster.post("Test content")

        assert result.status == Status.FAILED
        assert "API error" in result.error


class TestLinkedInPoster:
    """Tests for LinkedInPoster."""

    def test_class_attributes(self):
        """Test LinkedIn class attributes."""
        assert LinkedInPoster.name == "linkedin"
        assert LinkedInPoster.max_length == 3000

    def test_post_success(self, mock_client):
        """Test successful LinkedIn posting."""
        mock_client.execute_action.side_effect = [
            {"sub": "abc123"},  # Profile response
            {"id": "post12345"},  # Post response
        ]
        poster = LinkedInPoster(mock_client)

        result = poster.post("Test LinkedIn post")

        assert result.status == Status.SUCCESS
        assert result.post_id == "post12345"
        # Verify profile was fetched first
        assert mock_client.execute_action.call_count == 2

    def test_post_with_event_url(self, mock_client, sample_event):
        """Test LinkedIn post with event URL."""
        mock_client.execute_action.side_effect = [
            {"sub": "abc123"},
            {"id": "post12345"},
        ]
        poster = LinkedInPoster(mock_client)

        result = poster.post(
            "Test content",
            event_data=sample_event,
            event_url="https://lu.ma/test",
        )

        assert result.status == Status.SUCCESS
        # Check that event URL was appended
        call_args = mock_client.execute_action.call_args_list[1]
        commentary = call_args[0][1]["commentary"]
        assert "https://lu.ma/test" in commentary

    def test_post_profile_error(self, mock_client):
        """Test LinkedIn posting when profile fetch fails."""
        mock_client.execute_action.side_effect = Exception("Profile error")
        poster = LinkedInPoster(mock_client)

        result = poster.post("Test content")

        assert result.status == Status.FAILED
        assert "Could not get profile" in result.error

    def test_post_missing_urn(self, mock_client):
        """Test LinkedIn posting when URN is missing."""
        mock_client.execute_action.return_value = {}  # No 'sub' field
        poster = LinkedInPoster(mock_client)

        result = poster.post("Test content")

        assert result.status == Status.FAILED
        assert "Could not determine user URN" in result.error

    def test_post_create_error(self, mock_client):
        """Test LinkedIn posting when post creation fails."""
        mock_client.execute_action.side_effect = [
            {"sub": "abc123"},  # Profile succeeds
            Exception("Post failed"),  # Post fails
        ]
        poster = LinkedInPoster(mock_client)

        result = poster.post("Test content")

        assert result.status == Status.FAILED


class TestFacebookPoster:
    """Tests for FacebookPoster."""

    def test_class_attributes(self):
        """Test Facebook class attributes."""
        assert FacebookPoster.name == "facebook"
        assert FacebookPoster.max_length == 63206

    def test_post_success(self, mock_client):
        """Test successful Facebook posting."""
        mock_client.execute_action.return_value = {
            "id": "page123_post456",
        }
        poster = FacebookPoster(mock_client)

        result = poster.post("Test Facebook post", page_id="page123")

        assert result.status == Status.SUCCESS
        assert "page123_post456" in result.post_id
        assert "facebook.com" in result.post_url
        mock_client.execute_action.assert_called_once_with(
            "FACEBOOK_CREATE_PAGE_POST",
            {"page_id": "page123", "message": "Test Facebook post"},
        )

    def test_post_no_page_id(self, mock_client):
        """Test Facebook posting without page ID."""
        poster = FacebookPoster(mock_client)

        result = poster.post("Test content")

        assert result.status == Status.SKIPPED
        assert "No page ID" in result.message

    def test_post_with_event_url(self, mock_client, sample_event):
        """Test Facebook post with event URL."""
        mock_client.execute_action.return_value = {"id": "page_post"}
        poster = FacebookPoster(mock_client)

        result = poster.post(
            "Test content",
            event_data=sample_event,
            event_url="https://lu.ma/test",
            page_id="page123",
        )

        assert result.status == Status.SUCCESS
        call_args = mock_client.execute_action.call_args
        message = call_args[0][1]["message"]
        assert "https://lu.ma/test" in message

    def test_post_failure(self, mock_client):
        """Test Facebook posting failure."""
        mock_client.execute_action.side_effect = Exception("API error")
        poster = FacebookPoster(mock_client)

        result = poster.post("Test content", page_id="page123")

        assert result.status == Status.FAILED
        assert "API error" in result.error


class TestDiscordPoster:
    """Tests for DiscordPoster."""

    def test_class_attributes(self):
        """Test Discord class attributes."""
        assert DiscordPoster.name == "discord"
        assert DiscordPoster.max_length == 2000

    def test_post_success(self, mock_client):
        """Test successful Discord posting."""
        mock_client.execute_action.return_value = {
            "id": "msg123",
            "guild_id": "guild456",
        }
        poster = DiscordPoster(mock_client)

        result = poster.post("Test Discord message", channel_id="chan789")

        assert result.status == Status.SUCCESS
        assert result.post_id == "msg123"
        assert "discord.com/channels" in result.post_url
        mock_client.execute_action.assert_called_once_with(
            "DISCORD_SEND_MESSAGE",
            {"channel_id": "chan789", "content": "Test Discord message"},
        )

    def test_post_no_channel_id(self, mock_client):
        """Test Discord posting without channel ID."""
        poster = DiscordPoster(mock_client)

        result = poster.post("Test content")

        assert result.status == Status.SKIPPED
        assert "No channel ID" in result.message

    def test_post_with_event_url(self, mock_client, sample_event):
        """Test Discord post with event URL."""
        mock_client.execute_action.return_value = {"id": "msg123"}
        poster = DiscordPoster(mock_client)

        result = poster.post(
            "Test content",
            event_data=sample_event,
            event_url="https://lu.ma/test",
            channel_id="chan789",
        )

        assert result.status == Status.SUCCESS
        call_args = mock_client.execute_action.call_args
        content = call_args[0][1]["content"]
        assert "https://lu.ma/test" in content

    def test_post_with_image_url(self, mock_client):
        """Test Discord post with image URL."""
        mock_client.execute_action.return_value = {"id": "msg123"}
        poster = DiscordPoster(mock_client)

        result = poster.post(
            "Test content",
            image_url="https://example.com/image.png",
            channel_id="chan789",
        )

        assert result.status == Status.SUCCESS
        call_args = mock_client.execute_action.call_args
        content = call_args[0][1]["content"]
        assert "https://example.com/image.png" in content

    def test_post_failure(self, mock_client):
        """Test Discord posting failure."""
        mock_client.execute_action.side_effect = Exception("API error")
        poster = DiscordPoster(mock_client)

        result = poster.post("Test content", channel_id="chan789")

        assert result.status == Status.FAILED
        assert "API error" in result.error

    def test_format_event_announcement(self, mock_client, sample_event):
        """Test Discord event announcement formatting."""
        poster = DiscordPoster(mock_client)

        formatted = poster.format_event_announcement(
            sample_event,
            event_url="https://lu.ma/test",
        )

        assert "AI Workshop" in formatted
        assert "January 25, 2025" in formatted
        assert "The Station, Philadelphia" in formatted
        assert "https://lu.ma/test" in formatted


class TestSocialPromotionManager:
    """Tests for SocialPromotionManager."""

    def test_initialization(self, mock_client):
        """Test manager initialization."""
        manager = SocialPromotionManager(mock_client)

        assert "twitter" in manager.posters
        assert "linkedin" in manager.posters
        assert "instagram" in manager.posters
        assert "facebook" in manager.posters
        assert "discord" in manager.posters

    def test_promote_all_success(self, mock_client, sample_event, platform_copies):
        """Test promoting to all platforms successfully."""
        mock_client.execute_action.return_value = {"id": "12345", "sub": "user123"}
        manager = SocialPromotionManager(mock_client)

        result = manager.promote(
            event_data=sample_event,
            copies=platform_copies,
            image_url="https://example.com/image.png",
            event_url="https://lu.ma/test",
            discord_channel_id="chan123",
            facebook_page_id="page123",
        )

        assert result.twitter is not None
        assert result.linkedin is not None
        assert result.discord is not None
        assert result.facebook is not None
        assert result.success_count >= 1  # Some should succeed

    def test_promote_with_skip(self, mock_client, sample_event, platform_copies):
        """Test promoting with skipped platforms."""
        mock_client.execute_action.return_value = {"id": "12345", "sub": "user123"}
        manager = SocialPromotionManager(mock_client)

        result = manager.promote(
            event_data=sample_event,
            copies=platform_copies,
            skip_platforms=["twitter", "facebook"],
        )

        assert result.twitter.status == Status.SKIPPED
        assert result.facebook.status == Status.SKIPPED

    def test_promote_missing_channel_id(self, mock_client, sample_event, platform_copies):
        """Test promoting without Discord channel ID."""
        mock_client.execute_action.return_value = {"id": "12345", "sub": "user123"}
        manager = SocialPromotionManager(mock_client)

        result = manager.promote(
            event_data=sample_event,
            copies=platform_copies,
            # No discord_channel_id
        )

        assert result.discord.status == Status.SKIPPED

    def test_promote_missing_page_id(self, mock_client, sample_event, platform_copies):
        """Test promoting without Facebook page ID."""
        mock_client.execute_action.return_value = {"id": "12345", "sub": "user123"}
        manager = SocialPromotionManager(mock_client)

        result = manager.promote(
            event_data=sample_event,
            copies=platform_copies,
            # No facebook_page_id
        )

        assert result.facebook.status == Status.SKIPPED

    def test_promote_partial_failure(self, mock_client, sample_event, platform_copies):
        """Test promoting when some platforms fail."""
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] % 2 == 0:
                raise Exception("Simulated failure")
            return {"id": "12345", "sub": "user123"}

        mock_client.execute_action.side_effect = side_effect
        manager = SocialPromotionManager(mock_client)

        result = manager.promote(
            event_data=sample_event,
            copies=platform_copies,
            discord_channel_id="chan123",
            facebook_page_id="page123",
        )

        # Should have a mix of success and failure
        all_results = result.all_results
        assert len(all_results) > 0

    def test_promote_uses_default_content(self, mock_client, sample_event):
        """Test promoting uses event description when copy not provided."""
        mock_client.execute_action.return_value = {"id": "12345"}
        manager = SocialPromotionManager(mock_client)

        result = manager.promote(
            event_data=sample_event,
            copies={},  # Empty copies
            skip_platforms=["linkedin", "instagram", "facebook", "discord"],
        )

        # Twitter should have been called with event description
        assert result.twitter is not None

    def test_post_to_single_success(self, mock_client, sample_event):
        """Test posting to a single platform."""
        mock_client.execute_action.return_value = {"id": "12345"}
        manager = SocialPromotionManager(mock_client)

        result = manager.post_to_single(
            platform="twitter",
            content="Single tweet",
            event_data=sample_event,
        )

        assert result.status == Status.SUCCESS

    def test_post_to_single_unknown_platform(self, mock_client, sample_event):
        """Test posting to unknown platform raises error."""
        manager = SocialPromotionManager(mock_client)

        with pytest.raises(ValueError, match="Unknown platform"):
            manager.post_to_single(
                platform="myspace",
                content="Test",
            )

    def test_post_to_single_case_insensitive(self, mock_client, sample_event):
        """Test platform name is case insensitive."""
        mock_client.execute_action.return_value = {"id": "12345"}
        manager = SocialPromotionManager(mock_client)

        result = manager.post_to_single(
            platform="TWITTER",
            content="Test",
        )

        assert result.platform == "twitter"


class TestPosterCommonBehavior:
    """Tests for behavior common to all posters."""

    @pytest.fixture(params=[
        TwitterPoster,
        LinkedInPoster,
        FacebookPoster,
        DiscordPoster,
    ])
    def poster_class(self, request):
        """Parametrized fixture for all poster classes."""
        return request.param

    def test_has_name(self, poster_class, mock_client):
        """Test all posters have a name."""
        poster = poster_class(mock_client)
        assert poster.name
        assert isinstance(poster.name, str)

    def test_has_max_length(self, poster_class, mock_client):
        """Test all posters have a max_length."""
        poster = poster_class(mock_client)
        assert poster.max_length > 0

    def test_truncate_content_method(self, poster_class, mock_client):
        """Test all posters have truncate_content method."""
        poster = poster_class(mock_client)
        result = poster.truncate_content("Test content")
        assert isinstance(result, str)

    def test_post_returns_social_post_result(self, poster_class, mock_client, sample_event):
        """Test all posters return SocialPostResult."""
        mock_client.execute_action.return_value = {"id": "123", "sub": "user"}
        poster = poster_class(mock_client)

        # Pass required args based on poster type
        kwargs = {}
        if poster_class == FacebookPoster:
            kwargs["page_id"] = "page123"
        elif poster_class == DiscordPoster:
            kwargs["channel_id"] = "chan123"

        result = poster.post("Test content", event_data=sample_event, **kwargs)

        assert isinstance(result, SocialPostResult)
        assert result.platform == poster.name


class TestInstagramPoster:
    """Tests for InstagramPoster - separate since it has unique requirements."""

    def test_class_attributes(self):
        """Test Instagram class attributes."""
        assert InstagramPoster.name == "instagram"
        assert InstagramPoster.max_length == 2200

    def test_post_requires_image_url(self, mock_client):
        """Test Instagram requires image URL."""
        poster = InstagramPoster(mock_client)

        result = poster.post("Test caption", image_url="")

        assert result.status == Status.SKIPPED
        assert "image" in result.message.lower()

    def test_post_success(self, mock_client, sample_event):
        """Test successful Instagram posting."""
        mock_client.execute_action.side_effect = [
            {"id": "user123"},  # User info response
            {"id": "post456", "permalink": "https://instagram.com/p/abc123"},  # Post response
        ]
        poster = InstagramPoster(mock_client)

        result = poster.post(
            "Test caption",
            event_data=sample_event,
            image_url="https://example.com/image.jpg",
        )

        assert result.status == Status.SUCCESS
        assert result.post_id == "post456"
        assert "instagram.com" in result.post_url

    def test_post_with_event_url(self, mock_client, sample_event):
        """Test Instagram post includes event URL in caption."""
        mock_client.execute_action.side_effect = [
            {"id": "user123"},
            {"id": "post456"},
        ]
        poster = InstagramPoster(mock_client)

        result = poster.post(
            "Test caption",
            event_data=sample_event,
            image_url="https://example.com/image.jpg",
            event_url="https://lu.ma/test",
        )

        assert result.status == Status.SUCCESS
        # Check caption was built with event URL
        call_args = mock_client.execute_action.call_args_list[1]
        caption = call_args[0][1]["caption"]
        assert "https://lu.ma/test" in caption

    def test_post_user_info_error(self, mock_client):
        """Test Instagram posting when user info fetch fails."""
        mock_client.execute_action.side_effect = Exception("User info error")
        poster = InstagramPoster(mock_client)

        result = poster.post(
            "Test caption",
            image_url="https://example.com/image.jpg",
        )

        assert result.status == Status.FAILED
        assert "Could not get user info" in result.error

    def test_post_missing_user_id(self, mock_client):
        """Test Instagram posting when user ID is missing."""
        mock_client.execute_action.return_value = {}  # No 'id' field
        poster = InstagramPoster(mock_client)

        result = poster.post(
            "Test caption",
            image_url="https://example.com/image.jpg",
        )

        assert result.status == Status.FAILED
        assert "Could not determine user ID" in result.error

    def test_post_media_error(self, mock_client):
        """Test Instagram posting when media post fails."""
        mock_client.execute_action.side_effect = [
            {"id": "user123"},  # User info succeeds
            Exception("Media post failed"),  # Post fails
        ]
        poster = InstagramPoster(mock_client)

        result = poster.post(
            "Test caption",
            image_url="https://example.com/image.jpg",
        )

        assert result.status == Status.FAILED
