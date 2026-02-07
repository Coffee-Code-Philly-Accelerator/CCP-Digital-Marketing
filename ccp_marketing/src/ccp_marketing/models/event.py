"""Event data models for CCP Marketing."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ccp_marketing.utils.sanitization import sanitize_input, sanitize_url


@dataclass
class EventData:
    """Data structure for event information.

    This is the primary input model for event creation and promotion workflows.

    Attributes:
        title: Event title (required)
        date: Event date as string (e.g., "January 25, 2025")
        time: Event time with timezone (e.g., "6:00 PM EST")
        location: Venue name and/or address
        description: Full event description
        url: Primary RSVP URL (if already created)
        meetup_group_url: Meetup group URL for Meetup events
        discord_channel_id: Discord channel ID for announcements
        facebook_page_id: Facebook page ID for posting
        tags: List of tags/categories for the event
        extra: Additional platform-specific data
    """

    title: str
    date: str
    time: str
    location: str
    description: str
    url: str = ""
    meetup_group_url: str = ""
    discord_channel_id: str = ""
    facebook_page_id: str = ""
    tags: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate and sanitize inputs after initialization."""
        # Sanitize text inputs
        self.title = sanitize_input(self.title, max_len=200)
        self.date = sanitize_input(self.date, max_len=100)
        self.time = sanitize_input(self.time, max_len=100)
        self.location = sanitize_input(self.location, max_len=500)
        self.description = sanitize_input(self.description, max_len=5000)

        # Sanitize URLs
        self.url = sanitize_url(self.url)
        self.meetup_group_url = sanitize_url(self.meetup_group_url)

    def validate(self) -> list[str]:
        """Validate event data and return list of validation errors.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if not self.title:
            errors.append("Event title is required")
        if not self.date:
            errors.append("Event date is required")
        if not self.time:
            errors.append("Event time is required")
        if not self.location:
            errors.append("Event location is required")
        if not self.description:
            errors.append("Event description is required")

        return errors

    def is_valid(self) -> bool:
        """Check if event data is valid.

        Returns:
            True if all required fields are present
        """
        return len(self.validate()) == 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API calls.

        Returns:
            Dictionary representation of event data
        """
        return {
            "event_title": self.title,
            "event_date": self.date,
            "event_time": self.time,
            "event_location": self.location,
            "event_description": self.description,
            "event_url": self.url,
            "meetup_group_url": self.meetup_group_url,
            "discord_channel_id": self.discord_channel_id,
            "facebook_page_id": self.facebook_page_id,
            "tags": self.tags,
            **self.extra,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EventData":
        """Create EventData from a dictionary.

        Args:
            data: Dictionary with event data (supports both prefixed and unprefixed keys)

        Returns:
            EventData instance
        """
        # Support both "title" and "event_title" formats
        def get_value(key: str) -> Any:
            return data.get(key) or data.get(f"event_{key}") or ""

        return cls(
            title=get_value("title"),
            date=get_value("date"),
            time=get_value("time"),
            location=get_value("location"),
            description=get_value("description"),
            url=get_value("url"),
            meetup_group_url=data.get("meetup_group_url", ""),
            discord_channel_id=data.get("discord_channel_id", ""),
            facebook_page_id=data.get("facebook_page_id", ""),
            tags=data.get("tags", []),
            extra={k: v for k, v in data.items() if not k.startswith("event_")},
        )

    def get_formatted_datetime(self) -> str:
        """Get formatted date and time string.

        Returns:
            Combined date and time string
        """
        return f"{self.date} at {self.time}"

    def get_short_description(self, max_len: int = 280) -> str:
        """Get truncated description for platforms with character limits.

        Args:
            max_len: Maximum length (default 280 for Twitter)

        Returns:
            Truncated description
        """
        if len(self.description) <= max_len:
            return self.description

        # Try to truncate at a sentence or word boundary
        truncated = self.description[: max_len - 3]
        last_period = truncated.rfind(".")
        last_space = truncated.rfind(" ")

        if last_period > max_len // 2:
            return self.description[: last_period + 1]
        if last_space > max_len // 2:
            return truncated[:last_space] + "..."

        return truncated + "..."
