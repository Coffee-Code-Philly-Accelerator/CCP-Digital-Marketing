"""Tests for CCP Marketing data models."""

import pytest
from datetime import datetime

from ccp_marketing.models.event import EventData
from ccp_marketing.models.results import (
    Status,
    PlatformResult,
    EventCreationResult,
    SocialPostResult,
    SocialPromotionResult,
    WorkflowResult,
)


class TestEventData:
    """Tests for EventData model."""

    def test_create_event_data(self, sample_event_data):
        """Test creating EventData with valid data."""
        event = EventData(**sample_event_data)

        assert event.title == sample_event_data["title"]
        assert event.date == sample_event_data["date"]
        assert event.time == sample_event_data["time"]
        assert event.location == sample_event_data["location"]
        assert event.description == sample_event_data["description"]

    def test_event_data_defaults(self):
        """Test EventData default values."""
        event = EventData(
            title="Test",
            date="Jan 1",
            time="6 PM",
            location="Here",
            description="Desc",
        )

        assert event.url == ""
        assert event.meetup_group_url == ""
        assert event.discord_channel_id == ""
        assert event.facebook_page_id == ""
        assert event.tags == []
        assert event.extra == {}

    def test_event_data_validation_valid(self, sample_event):
        """Test validation passes for valid event."""
        errors = sample_event.validate()
        assert errors == []
        assert sample_event.is_valid()

    def test_event_data_validation_missing_title(self, sample_event_data):
        """Test validation fails for missing title."""
        sample_event_data["title"] = ""
        event = EventData(**sample_event_data)

        errors = event.validate()
        assert "Event title is required" in errors
        assert not event.is_valid()

    def test_event_data_validation_missing_all(self):
        """Test validation fails for all missing fields."""
        event = EventData(
            title="",
            date="",
            time="",
            location="",
            description="",
        )

        errors = event.validate()
        assert len(errors) == 5
        assert not event.is_valid()

    def test_event_data_to_dict(self, sample_event):
        """Test conversion to dictionary."""
        result = sample_event.to_dict()

        assert result["event_title"] == sample_event.title
        assert result["event_date"] == sample_event.date
        assert result["event_time"] == sample_event.time
        assert result["event_location"] == sample_event.location
        assert result["event_description"] == sample_event.description

    def test_event_data_from_dict(self, sample_event_data):
        """Test creation from dictionary."""
        event = EventData.from_dict(sample_event_data)

        assert event.title == sample_event_data["title"]
        assert event.date == sample_event_data["date"]

    def test_event_data_from_dict_prefixed(self, sample_event_data):
        """Test creation from dictionary with event_ prefix."""
        prefixed = {f"event_{k}": v for k, v in sample_event_data.items()}
        event = EventData.from_dict(prefixed)

        assert event.title == sample_event_data["title"]
        assert event.date == sample_event_data["date"]

    def test_event_data_sanitization(self):
        """Test that inputs are sanitized."""
        event = EventData(
            title="Test ```code``` here",
            date="Jan 1 --- 2025",
            time="6 PM",
            location="Here",
            description="Normal description",
        )

        # Backticks replaced with single quotes
        assert "```" not in event.title
        assert "'''" in event.title

        # Dashes replaced with underscores
        assert "---" not in event.date
        assert "___" in event.date

    def test_event_data_truncation(self):
        """Test that inputs are truncated to max length."""
        long_title = "A" * 500
        event = EventData(
            title=long_title,
            date="Jan 1",
            time="6 PM",
            location="Here",
            description="Desc",
        )

        assert len(event.title) <= 200

    def test_get_formatted_datetime(self, sample_event):
        """Test formatted datetime string."""
        result = sample_event.get_formatted_datetime()
        assert "January 25, 2025" in result
        assert "6:00 PM EST" in result

    def test_get_short_description(self, sample_event):
        """Test truncated description."""
        short = sample_event.get_short_description(50)
        assert len(short) <= 50

    def test_get_short_description_with_ellipsis(self):
        """Test description truncation adds ellipsis."""
        event = EventData(
            title="Test",
            date="Jan 1",
            time="6 PM",
            location="Here",
            description="This is a very long description that should be truncated.",
        )

        short = event.get_short_description(30)
        assert short.endswith("...")


class TestStatus:
    """Tests for Status enum."""

    def test_status_values(self):
        """Test all status values exist."""
        assert Status.SUCCESS.value == "success"
        assert Status.PUBLISHED.value == "PUBLISHED"
        assert Status.FAILED.value == "failed"
        assert Status.SKIPPED.value == "skipped"
        assert Status.NEEDS_AUTH.value == "NEEDS_AUTH"
        assert Status.NEEDS_REVIEW.value == "NEEDS_REVIEW"
        assert Status.DUPLICATE.value == "DUPLICATE"
        assert Status.PENDING.value == "pending"
        assert Status.IN_PROGRESS.value == "in_progress"


class TestPlatformResult:
    """Tests for PlatformResult model."""

    def test_create_success_result(self):
        """Test creating a successful result."""
        result = PlatformResult(
            platform="luma",
            status=Status.PUBLISHED,
            url="https://lu.ma/test-event",
        )

        assert result.is_success
        assert not result.is_failure
        assert not result.is_skipped
        assert not result.needs_attention

    def test_create_failed_result(self):
        """Test creating a failed result."""
        result = PlatformResult(
            platform="luma",
            status=Status.FAILED,
            error="Connection timeout",
        )

        assert result.is_failure
        assert not result.is_success

    def test_create_skipped_result(self):
        """Test creating a skipped result."""
        result = PlatformResult(
            platform="meetup",
            status=Status.SKIPPED,
            message="Skipped by user",
        )

        assert result.is_skipped
        assert not result.is_success

    def test_needs_attention(self):
        """Test needs_attention property."""
        auth_result = PlatformResult(
            platform="luma",
            status=Status.NEEDS_AUTH,
        )
        review_result = PlatformResult(
            platform="meetup",
            status=Status.NEEDS_REVIEW,
        )

        assert auth_result.needs_attention
        assert review_result.needs_attention

    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = PlatformResult(
            platform="luma",
            status=Status.PUBLISHED,
            url="https://lu.ma/test",
        )

        d = result.to_dict()
        assert d["platform"] == "luma"
        assert d["status"] == "PUBLISHED"
        assert d["url"] == "https://lu.ma/test"
        assert "timestamp" in d


class TestEventCreationResult:
    """Tests for EventCreationResult model."""

    def test_create_with_results(self):
        """Test creating result with platform results."""
        luma = PlatformResult(
            platform="luma",
            status=Status.PUBLISHED,
            url="https://lu.ma/test",
        )
        meetup = PlatformResult(
            platform="meetup",
            status=Status.SKIPPED,
        )

        result = EventCreationResult(luma=luma, meetup=meetup)

        assert result.primary_url == "https://lu.ma/test"
        assert result.success_count == 1
        assert "1/" in result.summary

    def test_all_results(self):
        """Test all_results property."""
        luma = PlatformResult(platform="luma", status=Status.PUBLISHED)
        meetup = PlatformResult(platform="meetup", status=Status.FAILED)

        result = EventCreationResult(luma=luma, meetup=meetup)

        assert len(result.all_results) == 2

    def test_is_complete_success(self):
        """Test is_complete_success property."""
        luma = PlatformResult(platform="luma", status=Status.PUBLISHED)
        meetup = PlatformResult(platform="meetup", status=Status.PUBLISHED)

        result = EventCreationResult(luma=luma, meetup=meetup)
        assert result.is_complete_success

    def test_is_not_complete_success(self):
        """Test is_complete_success when some failed."""
        luma = PlatformResult(platform="luma", status=Status.PUBLISHED)
        meetup = PlatformResult(platform="meetup", status=Status.FAILED)

        result = EventCreationResult(luma=luma, meetup=meetup)
        assert not result.is_complete_success


class TestSocialPostResult:
    """Tests for SocialPostResult model."""

    def test_create_result(self):
        """Test creating a social post result."""
        result = SocialPostResult(
            platform="twitter",
            status=Status.SUCCESS,
            post_id="123456789",
            post_url="https://twitter.com/user/status/123456789",
        )

        assert result.is_success
        assert result.post_id == "123456789"

    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = SocialPostResult(
            platform="twitter",
            status=Status.SUCCESS,
            post_id="123",
        )

        d = result.to_dict()
        assert d["platform"] == "twitter"
        assert d["post_id"] == "123"


class TestSocialPromotionResult:
    """Tests for SocialPromotionResult model."""

    def test_create_with_results(self):
        """Test creating promotion result."""
        twitter = SocialPostResult(platform="twitter", status=Status.SUCCESS)
        linkedin = SocialPostResult(platform="linkedin", status=Status.SUCCESS)
        instagram = SocialPostResult(platform="instagram", status=Status.SKIPPED)

        result = SocialPromotionResult(
            twitter=twitter,
            linkedin=linkedin,
            instagram=instagram,
        )

        assert result.success_count == 2
        assert "2/5" in result.summary

    def test_all_results(self):
        """Test all_results property."""
        twitter = SocialPostResult(platform="twitter", status=Status.SUCCESS)

        result = SocialPromotionResult(twitter=twitter)
        assert len(result.all_results) == 1


class TestWorkflowResult:
    """Tests for WorkflowResult model."""

    def test_create_workflow_result(self):
        """Test creating a complete workflow result."""
        event_result = EventCreationResult(
            luma=PlatformResult(
                platform="luma",
                status=Status.PUBLISHED,
                url="https://lu.ma/test",
            )
        )
        social_result = SocialPromotionResult(
            twitter=SocialPostResult(platform="twitter", status=Status.SUCCESS)
        )

        result = WorkflowResult(
            event_creation=event_result,
            social_promotion=social_result,
            duration_seconds=45.5,
        )

        assert result.primary_url == "https://lu.ma/test"
        assert result.duration_seconds == 45.5
        assert "Events:" in result.summary
        assert "Social:" in result.summary

    def test_to_dict(self):
        """Test conversion to dictionary."""
        event_result = EventCreationResult()
        social_result = SocialPromotionResult()

        result = WorkflowResult(
            event_creation=event_result,
            social_promotion=social_result,
        )

        d = result.to_dict()
        assert "event_creation" in d
        assert "social_promotion" in d
        assert "duration_seconds" in d
