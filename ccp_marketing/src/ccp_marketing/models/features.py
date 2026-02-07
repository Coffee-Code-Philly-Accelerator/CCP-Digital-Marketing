"""Feature configuration models for advanced event creation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TicketType(str, Enum):
    """Types of ticket configurations."""

    FREE = "free"
    PAID = "paid"
    DONATION = "donation"
    RSVP_ONLY = "rsvp_only"


class RecurringPattern(str, Enum):
    """Recurring event patterns."""

    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class EventVisibility(str, Enum):
    """Event visibility settings."""

    PUBLIC = "public"
    PRIVATE = "private"
    UNLISTED = "unlisted"


@dataclass
class TicketTier:
    """A single ticket tier configuration.

    Attributes:
        name: Tier name (e.g., "Early Bird", "General Admission")
        price: Ticket price (0 for free)
        currency: Currency code (USD, EUR, etc.)
        quantity: Number of tickets available (None for unlimited)
        description: Optional tier description
        sales_start: When sales begin (None for immediately)
        sales_end: When sales end (None for event start)
    """

    name: str = "General Admission"
    price: float = 0.0
    currency: str = "USD"
    quantity: int | None = None
    description: str = ""
    sales_start: datetime | None = None
    sales_end: datetime | None = None

    @property
    def is_free(self) -> bool:
        """Check if this tier is free."""
        return self.price == 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "price": self.price,
            "currency": self.currency,
            "quantity": self.quantity,
            "description": self.description,
            "sales_start": self.sales_start.isoformat() if self.sales_start else None,
            "sales_end": self.sales_end.isoformat() if self.sales_end else None,
        }


@dataclass
class TicketConfig:
    """Complete ticket/registration configuration.

    Attributes:
        ticket_type: Type of ticketing
        tiers: List of ticket tiers
        capacity: Total event capacity (None for unlimited)
        require_approval: Whether RSVPs need manual approval
        waitlist_enabled: Enable waitlist when capacity reached
        refund_policy: Refund policy description
    """

    ticket_type: TicketType = TicketType.FREE
    tiers: list[TicketTier] = field(default_factory=list)
    capacity: int | None = None
    require_approval: bool = False
    waitlist_enabled: bool = True
    refund_policy: str = ""

    def __post_init__(self) -> None:
        """Ensure at least one tier exists for paid events."""
        if self.ticket_type == TicketType.PAID and not self.tiers:
            self.tiers = [TicketTier(name="General Admission", price=10.0)]
        elif self.ticket_type == TicketType.FREE and not self.tiers:
            self.tiers = [TicketTier(name="Free Registration", price=0.0)]

    @property
    def is_free(self) -> bool:
        """Check if event is free (all tiers are free)."""
        if self.ticket_type == TicketType.FREE:
            return True
        return all(tier.is_free for tier in self.tiers)

    @property
    def min_price(self) -> float:
        """Get minimum ticket price."""
        if not self.tiers:
            return 0.0
        return min(tier.price for tier in self.tiers)

    @property
    def max_price(self) -> float:
        """Get maximum ticket price."""
        if not self.tiers:
            return 0.0
        return max(tier.price for tier in self.tiers)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "ticket_type": self.ticket_type.value,
            "tiers": [tier.to_dict() for tier in self.tiers],
            "capacity": self.capacity,
            "require_approval": self.require_approval,
            "waitlist_enabled": self.waitlist_enabled,
            "refund_policy": self.refund_policy,
            "is_free": self.is_free,
        }


@dataclass
class RecurringConfig:
    """Recurring event configuration.

    Attributes:
        pattern: Recurrence pattern
        end_date: When the series ends (None for no end)
        count: Number of occurrences (alternative to end_date)
        days_of_week: Days for weekly pattern (e.g., ["Monday", "Wednesday"])
        day_of_month: Day for monthly pattern (1-31)
        interval: Interval for pattern (e.g., 2 for "every 2 weeks")
        exceptions: Dates to skip
    """

    pattern: RecurringPattern = RecurringPattern.NONE
    end_date: str | None = None
    count: int | None = None
    days_of_week: list[str] = field(default_factory=list)
    day_of_month: int | None = None
    interval: int = 1
    exceptions: list[str] = field(default_factory=list)

    @property
    def is_recurring(self) -> bool:
        """Check if this is a recurring event."""
        return self.pattern != RecurringPattern.NONE

    def get_description(self) -> str:
        """Get human-readable description of recurrence."""
        if not self.is_recurring:
            return "One-time event"

        pattern_desc = {
            RecurringPattern.DAILY: "Daily",
            RecurringPattern.WEEKLY: "Weekly",
            RecurringPattern.BIWEEKLY: "Every 2 weeks",
            RecurringPattern.MONTHLY: "Monthly",
            RecurringPattern.CUSTOM: "Custom schedule",
        }

        desc = pattern_desc.get(self.pattern, "Recurring")

        if self.interval > 1 and self.pattern != RecurringPattern.BIWEEKLY:
            desc = f"Every {self.interval} {self.pattern.value}s"

        if self.days_of_week:
            days = ", ".join(self.days_of_week)
            desc += f" on {days}"

        if self.end_date:
            desc += f" until {self.end_date}"
        elif self.count:
            desc += f" ({self.count} occurrences)"

        return desc

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pattern": self.pattern.value,
            "end_date": self.end_date,
            "count": self.count,
            "days_of_week": self.days_of_week,
            "day_of_month": self.day_of_month,
            "interval": self.interval,
            "exceptions": self.exceptions,
            "is_recurring": self.is_recurring,
            "description": self.get_description(),
        }


@dataclass
class CoHostConfig:
    """Co-host configuration.

    Attributes:
        email: Co-host email address
        name: Co-host display name (optional)
        role: Role description (optional)
        can_edit: Whether co-host can edit event
        can_manage_guests: Whether co-host can manage guest list
    """

    email: str
    name: str = ""
    role: str = "Co-host"
    can_edit: bool = True
    can_manage_guests: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "email": self.email,
            "name": self.name,
            "role": self.role,
            "can_edit": self.can_edit,
            "can_manage_guests": self.can_manage_guests,
        }


@dataclass
class IntegrationConfig:
    """Integration settings for the event.

    Attributes:
        zoom: Enable Zoom meeting
        google_meet: Enable Google Meet
        calendar_sync: Sync to calendar
        zoom_meeting_id: Existing Zoom meeting ID (if not creating new)
        meet_link: Existing Google Meet link (if not creating new)
    """

    zoom: bool = False
    google_meet: bool = False
    calendar_sync: bool = True
    zoom_meeting_id: str | None = None
    meet_link: str | None = None

    @property
    def has_video_conferencing(self) -> bool:
        """Check if video conferencing is enabled."""
        return self.zoom or self.google_meet

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "zoom": self.zoom,
            "google_meet": self.google_meet,
            "calendar_sync": self.calendar_sync,
            "zoom_meeting_id": self.zoom_meeting_id,
            "meet_link": self.meet_link,
            "has_video_conferencing": self.has_video_conferencing,
        }


@dataclass
class AdvancedEventConfig:
    """Complete advanced configuration for event creation.

    Combines all feature configurations into a single object.
    """

    tickets: TicketConfig = field(default_factory=TicketConfig)
    recurring: RecurringConfig = field(default_factory=RecurringConfig)
    integrations: IntegrationConfig = field(default_factory=IntegrationConfig)
    cohosts: list[CoHostConfig] = field(default_factory=list)
    visibility: EventVisibility = EventVisibility.PUBLIC
    image_url: str = ""
    tags: list[str] = field(default_factory=list)
    custom_fields: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def basic(cls) -> AdvancedEventConfig:
        """Create a basic configuration (free, one-time, public)."""
        return cls()

    @classmethod
    def paid_event(
        cls,
        price: float,
        capacity: int | None = None,
        currency: str = "USD",
    ) -> AdvancedEventConfig:
        """Create configuration for a paid event."""
        return cls(
            tickets=TicketConfig(
                ticket_type=TicketType.PAID,
                tiers=[TicketTier(price=price, currency=currency)],
                capacity=capacity,
            )
        )

    @classmethod
    def recurring_event(
        cls,
        pattern: RecurringPattern,
        count: int | None = None,
        end_date: str | None = None,
    ) -> AdvancedEventConfig:
        """Create configuration for a recurring event."""
        return cls(
            recurring=RecurringConfig(
                pattern=pattern,
                count=count,
                end_date=end_date,
            )
        )

    def add_cohost(
        self, email: str, name: str = "", role: str = "Co-host"
    ) -> AdvancedEventConfig:
        """Add a co-host."""
        self.cohosts.append(CoHostConfig(email=email, name=name, role=role))
        return self

    def enable_zoom(self) -> AdvancedEventConfig:
        """Enable Zoom integration."""
        self.integrations.zoom = True
        return self

    def enable_google_meet(self) -> AdvancedEventConfig:
        """Enable Google Meet integration."""
        self.integrations.google_meet = True
        return self

    def set_image(self, url: str) -> AdvancedEventConfig:
        """Set promotional image URL."""
        self.image_url = url
        return self

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tickets": self.tickets.to_dict(),
            "recurring": self.recurring.to_dict(),
            "integrations": self.integrations.to_dict(),
            "cohosts": [c.to_dict() for c in self.cohosts],
            "visibility": self.visibility.value,
            "image_url": self.image_url,
            "tags": self.tags,
            "custom_fields": self.custom_fields,
        }
