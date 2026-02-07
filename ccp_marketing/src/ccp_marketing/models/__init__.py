"""Data models for CCP Marketing."""

from ccp_marketing.models.event import EventData
from ccp_marketing.models.features import (
    AdvancedEventConfig,
    CoHostConfig,
    EventVisibility,
    IntegrationConfig,
    RecurringConfig,
    RecurringPattern,
    TicketConfig,
    TicketTier,
    TicketType,
)
from ccp_marketing.models.results import (
    EventCreationResult,
    PlatformResult,
    SocialPostResult,
    SocialPromotionResult,
    WorkflowResult,
)

__all__ = [
    # Event data
    "EventData",
    # Feature configs
    "AdvancedEventConfig",
    "TicketConfig",
    "TicketTier",
    "TicketType",
    "RecurringConfig",
    "RecurringPattern",
    "CoHostConfig",
    "IntegrationConfig",
    "EventVisibility",
    # Results
    "PlatformResult",
    "EventCreationResult",
    "SocialPostResult",
    "SocialPromotionResult",
    "WorkflowResult",
]
