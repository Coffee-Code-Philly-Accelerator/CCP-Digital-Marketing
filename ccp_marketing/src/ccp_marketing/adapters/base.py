"""Base platform adapter for event creation."""

from abc import ABC, abstractmethod
from typing import Any

from ccp_marketing.models.event import EventData
from ccp_marketing.state_machine.states import EventState


class BasePlatformAdapter(ABC):
    """Base adapter with common functionality for event platforms.

    Each platform adapter provides:
    - Platform-specific URLs and configuration
    - Form field prompts for browser automation
    - Success verification logic
    - Post-submit handling (modal dismissal, etc.)

    Subclasses must implement:
    - success_url_check: Verify if URL indicates successful creation
    - get_prompt: Get the browser automation prompt for each state

    Example:
        >>> class MyPlatformAdapter(BasePlatformAdapter):
        ...     name = "myplatform"
        ...     create_url = "https://myplatform.com/create"
        ...
        ...     def success_url_check(self, url: str) -> bool:
        ...         return "myplatform.com/event/" in url
        ...
        ...     def get_prompt(self, state: EventState) -> str:
        ...         prompts = {...}
        ...         return prompts.get(state, "")
    """

    # Class attributes to be overridden
    name: str = "base"
    create_url: str = ""
    home_url: str = ""
    inter_step_delay: float = 0.4  # Default settle time after each action

    # Form field indicators to verify we're on the create page
    form_indicators: list[str] = []

    def __init__(
        self,
        event_data: EventData,
        descriptions: dict[str, str] | None = None,
        image_url: str = "",
    ) -> None:
        """Initialize the adapter.

        Args:
            event_data: Event data to use for form filling
            descriptions: Platform-specific descriptions (keyed by platform name)
            image_url: URL of promotional image (if available)
        """
        self.event_data = event_data
        self.descriptions = descriptions or {}
        self.image_url = image_url

    def get_description(self) -> str:
        """Get the description for this platform.

        Returns platform-specific description if available,
        otherwise falls back to the standard event description.

        Returns:
            Description text for this platform
        """
        return self.descriptions.get(self.name, self.event_data.description)

    def get_create_url(self) -> str:
        """Get the URL for creating events on this platform.

        Override this method for platforms that require dynamic URLs
        (e.g., Meetup which needs a group URL).

        Returns:
            URL to navigate to for event creation
        """
        return self.create_url

    def get_home_url(self) -> str:
        """Get the home/dashboard URL for this platform.

        Used for duplicate checking before creating events.

        Returns:
            Platform home URL
        """
        return self.home_url

    def is_form_page(self, content: str) -> bool:
        """Check if we're on the actual event creation form page.

        Args:
            content: Page content to check

        Returns:
            True if page appears to be the create form
        """
        content_lower = content.lower()
        return any(indicator in content_lower for indicator in self.form_indicators)

    @abstractmethod
    def success_url_check(self, url: str) -> bool:
        """Check if URL indicates successful event creation.

        Args:
            url: Current page URL

        Returns:
            True if URL indicates event was created successfully
        """
        raise NotImplementedError

    @abstractmethod
    def get_prompt(self, state: EventState) -> str:
        """Get the browser automation prompt for a given state.

        Args:
            state: Current state machine state

        Returns:
            Natural language prompt for browser automation agent
        """
        raise NotImplementedError

    def post_step_wait(self, state: EventState) -> float:
        """Get additional wait time after a specific step.

        Override to add extra delay for slow UI elements.

        Args:
            state: Current state

        Returns:
            Delay in seconds to wait after this step
        """
        return self.inter_step_delay

    def post_submit_action(self) -> str | None:
        """Get optional action to perform after submit.

        Used for things like dismissing share modals.

        Returns:
            Prompt for post-submit action, or None if not needed
        """
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert adapter info to dictionary.

        Returns:
            Dictionary with adapter configuration
        """
        return {
            "name": self.name,
            "create_url": self.get_create_url(),
            "home_url": self.get_home_url(),
            "inter_step_delay": self.inter_step_delay,
        }
