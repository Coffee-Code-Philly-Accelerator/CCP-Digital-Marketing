"""Extended base platform adapter with full feature support (v2)."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ccp_marketing.adapters.base import BasePlatformAdapter
from ccp_marketing.browser.element_resolver import ElementTarget
from ccp_marketing.state_machine.states import EventState

if TYPE_CHECKING:
    from ccp_marketing.models.event import EventData


@dataclass
class FeatureSupport:
    """Feature support flags for a platform."""

    image_upload: bool = False
    tickets: bool = False
    cohosts: bool = False
    recurring: bool = False
    integrations: bool = False
    capacity: bool = False
    tags: bool = False
    visibility: bool = False  # Public/private toggle


@dataclass
class BrowserAction:
    """A browser action to perform.

    Attributes:
        action: Type of action (click, type, ai_task, wait)
        target: ElementTarget for the action (if applicable)
        value: Value to enter (for type action)
        prompt: AI prompt (for ai_task action)
        wait_after: Seconds to wait after action
    """

    action: str  # click, type, ai_task, wait, scroll
    target: ElementTarget | None = None
    value: str | None = None
    prompt: str | None = None
    wait_after: float = 0.5


@dataclass
class TicketConfig:
    """Ticket configuration for an event."""

    is_free: bool = True
    price: float | None = None
    currency: str = "USD"
    capacity: int | None = None
    ticket_name: str = "General Admission"
    early_bird_price: float | None = None
    early_bird_deadline: str | None = None


@dataclass
class RecurringConfig:
    """Recurring event configuration."""

    pattern: str = "none"  # none, daily, weekly, biweekly, monthly
    end_date: str | None = None
    count: int | None = None  # Number of occurrences
    days_of_week: list[str] = field(default_factory=list)  # For weekly


@dataclass
class IntegrationConfig:
    """Integration configuration."""

    zoom: bool = False
    google_meet: bool = False
    calendar_sync: bool = True


class BasePlatformAdapterV2(BasePlatformAdapter):
    """Extended platform adapter with full feature support.

    Extends the base adapter with:
    - Element targets for semantic UI targeting
    - Feature support flags
    - Advanced feature flows (images, tickets, cohosts, recurring)
    - Multi-strategy element resolution

    Subclasses should define:
    - element_targets: Dict of ElementTarget for each field
    - feature_support: FeatureSupport flags
    - Feature-specific flow methods
    """

    # Element targets for semantic UI targeting
    element_targets: dict[str, ElementTarget] = {}

    # Feature support flags
    feature_support: FeatureSupport = FeatureSupport()

    def __init__(
        self,
        event_data: EventData,
        descriptions: dict[str, str] | None = None,
        image_url: str = "",
        ticket_config: TicketConfig | None = None,
        recurring_config: RecurringConfig | None = None,
        integration_config: IntegrationConfig | None = None,
        cohosts: list[str] | None = None,
    ) -> None:
        """Initialize the extended adapter.

        Args:
            event_data: Event data for form filling
            descriptions: Platform-specific descriptions
            image_url: Promotional image URL
            ticket_config: Ticket/registration configuration
            recurring_config: Recurring event configuration
            integration_config: Integration settings
            cohosts: List of co-host emails
        """
        super().__init__(event_data, descriptions, image_url)
        self.ticket_config = ticket_config or TicketConfig()
        self.recurring_config = recurring_config or RecurringConfig()
        self.integration_config = integration_config or IntegrationConfig()
        self.cohosts = cohosts or []

    def get_element_target(self, element_name: str) -> ElementTarget | None:
        """Get the element target for a specific field.

        Args:
            element_name: Name of the element (e.g., "title", "date")

        Returns:
            ElementTarget if defined, None otherwise
        """
        return self.element_targets.get(element_name)

    def get_required_targets(self) -> list[str]:
        """Get list of required element target names.

        Returns:
            List of element names that must be filled
        """
        return ["title", "date", "time", "location", "description"]

    def get_optional_targets(self) -> list[str]:
        """Get list of optional element target names.

        Returns:
            List of optional element names
        """
        targets = []
        if self.feature_support.image_upload and self.image_url:
            targets.append("image_upload")
        if self.feature_support.tickets and not self.ticket_config.is_free:
            targets.extend(["tickets_button", "ticket_price", "ticket_capacity"])
        if self.feature_support.cohosts and self.cohosts:
            targets.append("add_cohost")
        if self.feature_support.recurring and self.recurring_config.pattern != "none":
            targets.append("recurring_toggle")
        return targets

    def should_skip_feature(self, state: EventState) -> bool:
        """Check if a feature state should be skipped.

        Args:
            state: Current state

        Returns:
            True if this feature state should be skipped
        """
        skip_map = {
            EventState.UPLOAD_IMAGE: not (
                self.feature_support.image_upload and self.image_url
            ),
            EventState.SET_TICKETS: not (
                self.feature_support.tickets
                and (not self.ticket_config.is_free or self.ticket_config.capacity)
            ),
            EventState.ADD_COHOSTS: not (
                self.feature_support.cohosts and self.cohosts
            ),
            EventState.SET_RECURRING: not (
                self.feature_support.recurring
                and self.recurring_config.pattern != "none"
            ),
            EventState.SET_INTEGRATIONS: not (
                self.feature_support.integrations
                and (
                    self.integration_config.zoom
                    or self.integration_config.google_meet
                )
            ),
        }
        return skip_map.get(state, False)

    @abstractmethod
    def get_image_upload_actions(self) -> list[BrowserAction]:
        """Get actions for uploading a cover image.

        Returns:
            List of BrowserAction to perform
        """
        raise NotImplementedError

    @abstractmethod
    def get_ticket_config_actions(self) -> list[BrowserAction]:
        """Get actions for configuring tickets.

        Returns:
            List of BrowserAction to perform
        """
        raise NotImplementedError

    @abstractmethod
    def get_cohost_actions(self) -> list[BrowserAction]:
        """Get actions for adding co-hosts.

        Returns:
            List of BrowserAction to perform
        """
        raise NotImplementedError

    @abstractmethod
    def get_recurring_actions(self) -> list[BrowserAction]:
        """Get actions for setting up recurring events.

        Returns:
            List of BrowserAction to perform
        """
        raise NotImplementedError

    def get_integration_actions(self) -> list[BrowserAction]:
        """Get actions for setting up integrations.

        Default implementation - override for platform-specific logic.

        Returns:
            List of BrowserAction to perform
        """
        actions = []
        if self.integration_config.zoom:
            actions.append(BrowserAction(
                action="ai_task",
                prompt="Find and enable Zoom integration for this event",
                wait_after=2.0,
            ))
        if self.integration_config.google_meet:
            actions.append(BrowserAction(
                action="ai_task",
                prompt="Find and enable Google Meet integration for this event",
                wait_after=2.0,
            ))
        return actions

    def get_state_actions(self, state: EventState) -> list[BrowserAction]:
        """Get browser actions for a specific state.

        Args:
            state: Current state

        Returns:
            List of BrowserAction to perform
        """
        if state == EventState.UPLOAD_IMAGE:
            return self.get_image_upload_actions()
        elif state == EventState.SET_TICKETS:
            return self.get_ticket_config_actions()
        elif state == EventState.ADD_COHOSTS:
            return self.get_cohost_actions()
        elif state == EventState.SET_RECURRING:
            return self.get_recurring_actions()
        elif state == EventState.SET_INTEGRATIONS:
            return self.get_integration_actions()
        return []

    def get_target_for_state(self, state: EventState) -> ElementTarget | None:
        """Get the element target for a state.

        Args:
            state: Current state

        Returns:
            ElementTarget for the state's primary element
        """
        state_to_target = {
            EventState.FILL_TITLE: "title",
            EventState.FILL_DATE: "date",
            EventState.FILL_TIME: "time",
            EventState.FILL_LOCATION: "location",
            EventState.FILL_DESCRIPTION: "description",
            EventState.SUBMIT: "publish_button",
        }
        target_name = state_to_target.get(state)
        if target_name:
            return self.get_element_target(target_name)
        return None

    def get_value_for_state(self, state: EventState) -> str | None:
        """Get the value to enter for a state.

        Args:
            state: Current state

        Returns:
            Value string to enter
        """
        state_to_value = {
            EventState.FILL_TITLE: self.event_data.title,
            EventState.FILL_DATE: self.event_data.date,
            EventState.FILL_TIME: self.event_data.time,
            EventState.FILL_LOCATION: self.event_data.location,
            EventState.FILL_DESCRIPTION: self.get_description(),
        }
        return state_to_value.get(state)

    def to_dict(self) -> dict[str, Any]:
        """Convert adapter info to dictionary.

        Returns:
            Dictionary with extended adapter configuration
        """
        base = super().to_dict()
        base.update({
            "feature_support": {
                "image_upload": self.feature_support.image_upload,
                "tickets": self.feature_support.tickets,
                "cohosts": self.feature_support.cohosts,
                "recurring": self.feature_support.recurring,
                "integrations": self.feature_support.integrations,
            },
            "has_image": bool(self.image_url),
            "ticket_config": {
                "is_free": self.ticket_config.is_free,
                "price": self.ticket_config.price,
                "capacity": self.ticket_config.capacity,
            },
            "recurring": self.recurring_config.pattern,
            "cohost_count": len(self.cohosts),
        })
        return base
