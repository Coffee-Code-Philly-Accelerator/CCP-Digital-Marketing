"""Result models for CCP Marketing operations."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Status(str, Enum):
    """Status codes for platform operations."""

    SUCCESS = "success"
    PUBLISHED = "PUBLISHED"
    FAILED = "failed"
    SKIPPED = "skipped"
    NEEDS_AUTH = "NEEDS_AUTH"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    DUPLICATE = "DUPLICATE"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"


@dataclass
class PlatformResult:
    """Result from a single platform operation.

    Attributes:
        platform: Platform name (e.g., "luma", "twitter")
        status: Operation status
        url: URL of created resource (if applicable)
        message: Human-readable status message
        error: Error message if failed
        data: Raw response data
        timestamp: When the operation completed
    """

    platform: str
    status: Status
    url: str = ""
    message: str = ""
    error: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_success(self) -> bool:
        """Check if operation was successful."""
        return self.status in (Status.SUCCESS, Status.PUBLISHED)

    @property
    def is_failure(self) -> bool:
        """Check if operation failed."""
        return self.status == Status.FAILED

    @property
    def is_skipped(self) -> bool:
        """Check if operation was skipped."""
        return self.status == Status.SKIPPED

    @property
    def needs_attention(self) -> bool:
        """Check if operation needs manual attention."""
        return self.status in (Status.NEEDS_AUTH, Status.NEEDS_REVIEW)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "platform": self.platform,
            "status": self.status.value,
            "url": self.url,
            "message": self.message,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class EventCreationResult:
    """Result from event creation workflow.

    Attributes:
        luma: Result from Luma
        meetup: Result from Meetup
        partiful: Result from Partiful
        primary_url: Primary event URL for sharing
        summary: Human-readable summary
    """

    luma: PlatformResult | None = None
    meetup: PlatformResult | None = None
    partiful: PlatformResult | None = None
    primary_url: str = ""
    summary: str = ""

    def __post_init__(self) -> None:
        """Set primary URL and summary after initialization."""
        if not self.primary_url:
            self.primary_url = self._get_primary_url()
        if not self.summary:
            self.summary = self._generate_summary()

    def _get_primary_url(self) -> str:
        """Get the primary event URL (prefer Luma > Meetup > Partiful)."""
        for result in [self.luma, self.meetup, self.partiful]:
            if result and result.is_success and result.url:
                return result.url
        return ""

    def _generate_summary(self) -> str:
        """Generate a human-readable summary."""
        results = [
            ("Luma", self.luma),
            ("Meetup", self.meetup),
            ("Partiful", self.partiful),
        ]

        success_count = sum(1 for _, r in results if r and r.is_success)
        total = sum(1 for _, r in results if r and not r.is_skipped)

        return f"Created on {success_count}/{total} platforms"

    @property
    def all_results(self) -> list[PlatformResult]:
        """Get all non-None results."""
        return [r for r in [self.luma, self.meetup, self.partiful] if r]

    @property
    def success_count(self) -> int:
        """Count of successful platforms."""
        return sum(1 for r in self.all_results if r.is_success)

    @property
    def is_complete_success(self) -> bool:
        """Check if all attempted platforms succeeded."""
        attempted = [r for r in self.all_results if not r.is_skipped]
        return all(r.is_success for r in attempted) if attempted else False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "luma": self.luma.to_dict() if self.luma else None,
            "meetup": self.meetup.to_dict() if self.meetup else None,
            "partiful": self.partiful.to_dict() if self.partiful else None,
            "primary_url": self.primary_url,
            "summary": self.summary,
            "success_count": self.success_count,
        }


@dataclass
class SocialPostResult:
    """Result from posting to a single social platform.

    Extends PlatformResult with social-media-specific fields.
    """

    platform: str
    status: Status
    post_id: str = ""
    post_url: str = ""
    message: str = ""
    error: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_success(self) -> bool:
        return self.status == Status.SUCCESS

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "status": self.status.value,
            "post_id": self.post_id,
            "post_url": self.post_url,
            "message": self.message,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class SocialPromotionResult:
    """Result from social media promotion workflow.

    Attributes:
        twitter: Twitter post result
        linkedin: LinkedIn post result
        instagram: Instagram post result
        facebook: Facebook post result
        discord: Discord post result
        image_url: Generated promotional image URL
        summary: Human-readable summary
    """

    twitter: SocialPostResult | None = None
    linkedin: SocialPostResult | None = None
    instagram: SocialPostResult | None = None
    facebook: SocialPostResult | None = None
    discord: SocialPostResult | None = None
    image_url: str = ""
    summary: str = ""

    def __post_init__(self) -> None:
        if not self.summary:
            self.summary = self._generate_summary()

    def _generate_summary(self) -> str:
        results = [
            self.twitter,
            self.linkedin,
            self.instagram,
            self.facebook,
            self.discord,
        ]
        success_count = sum(1 for r in results if r and r.is_success)
        return f"Posted to {success_count}/5 platforms"

    @property
    def all_results(self) -> list[SocialPostResult]:
        return [
            r
            for r in [
                self.twitter,
                self.linkedin,
                self.instagram,
                self.facebook,
                self.discord,
            ]
            if r
        ]

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.all_results if r.is_success)

    def to_dict(self) -> dict[str, Any]:
        return {
            "twitter": self.twitter.to_dict() if self.twitter else None,
            "linkedin": self.linkedin.to_dict() if self.linkedin else None,
            "instagram": self.instagram.to_dict() if self.instagram else None,
            "facebook": self.facebook.to_dict() if self.facebook else None,
            "discord": self.discord.to_dict() if self.discord else None,
            "image_url": self.image_url,
            "summary": self.summary,
            "success_count": self.success_count,
        }


@dataclass
class WorkflowResult:
    """Result from the full workflow (event creation + promotion).

    Attributes:
        event_creation: Results from event creation phase
        social_promotion: Results from social promotion phase
        primary_url: Primary event URL
        summary: Overall summary
        duration_seconds: Total workflow duration
    """

    event_creation: EventCreationResult
    social_promotion: SocialPromotionResult
    primary_url: str = ""
    summary: str = ""
    duration_seconds: float = 0.0

    def __post_init__(self) -> None:
        if not self.primary_url:
            self.primary_url = self.event_creation.primary_url
        if not self.summary:
            self.summary = self._generate_summary()

    def _generate_summary(self) -> str:
        return (
            f"Events: {self.event_creation.summary}. "
            f"Social: {self.social_promotion.summary}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_creation": self.event_creation.to_dict(),
            "social_promotion": self.social_promotion.to_dict(),
            "primary_url": self.primary_url,
            "summary": self.summary,
            "duration_seconds": self.duration_seconds,
        }
