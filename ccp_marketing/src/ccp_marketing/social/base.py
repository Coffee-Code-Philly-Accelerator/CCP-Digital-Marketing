"""Base social media poster."""

from abc import ABC, abstractmethod
from typing import Any

from ccp_marketing.core.client import ComposioClient
from ccp_marketing.models.event import EventData
from ccp_marketing.models.results import SocialPostResult, Status


class BaseSocialPoster(ABC):
    """Base class for social media posting.

    Each social platform poster provides:
    - Platform-specific posting logic
    - Character limits and formatting
    - Error handling and status reporting

    Subclasses must implement:
    - post: Post content to the platform

    Example:
        >>> class MyPoster(BaseSocialPoster):
        ...     name = "myplatform"
        ...     max_length = 500
        ...
        ...     def post(self, content: str, ...) -> SocialPostResult:
        ...         # Platform-specific posting logic
        ...         return SocialPostResult(...)
    """

    name: str = "base"
    max_length: int = 2000  # Default character limit

    def __init__(self, client: ComposioClient) -> None:
        """Initialize the poster.

        Args:
            client: Composio client for API calls
        """
        self.client = client

    @abstractmethod
    def post(
        self,
        content: str,
        event_data: EventData | None = None,
        image_url: str = "",
        event_url: str = "",
        **kwargs: Any,
    ) -> SocialPostResult:
        """Post content to this social platform.

        Args:
            content: Text content to post
            event_data: Optional event data for context
            image_url: Optional promotional image URL
            event_url: Optional event RSVP URL
            **kwargs: Platform-specific arguments

        Returns:
            SocialPostResult with post status and details
        """
        raise NotImplementedError

    def truncate_content(self, content: str, reserve: int = 0) -> str:
        """Truncate content to platform's character limit.

        Args:
            content: Content to truncate
            reserve: Characters to reserve (e.g., for URL)

        Returns:
            Truncated content with ellipsis if needed
        """
        limit = self.max_length - reserve

        if len(content) <= limit:
            return content

        # Truncate at word boundary if possible
        truncated = content[: limit - 3]
        last_space = truncated.rfind(" ")

        if last_space > limit // 2:
            return truncated[:last_space] + "..."

        return truncated + "..."

    def _success_result(
        self,
        message: str = "",
        post_id: str = "",
        post_url: str = "",
        data: dict[str, Any] | None = None,
    ) -> SocialPostResult:
        """Create a successful result.

        Args:
            message: Success message
            post_id: ID of created post
            post_url: URL of created post
            data: Raw response data

        Returns:
            SocialPostResult with success status
        """
        return SocialPostResult(
            platform=self.name,
            status=Status.SUCCESS,
            post_id=post_id,
            post_url=post_url,
            message=message or f"Posted to {self.name.title()}",
            data=data or {},
        )

    def _failed_result(self, error: str, data: dict[str, Any] | None = None) -> SocialPostResult:
        """Create a failed result.

        Args:
            error: Error message
            data: Raw response data

        Returns:
            SocialPostResult with failed status
        """
        return SocialPostResult(
            platform=self.name,
            status=Status.FAILED,
            error=error,
            data=data or {},
        )

    def _skipped_result(self, reason: str = "") -> SocialPostResult:
        """Create a skipped result.

        Args:
            reason: Reason for skipping

        Returns:
            SocialPostResult with skipped status
        """
        return SocialPostResult(
            platform=self.name,
            status=Status.SKIPPED,
            message=reason or "Skipped",
        )
