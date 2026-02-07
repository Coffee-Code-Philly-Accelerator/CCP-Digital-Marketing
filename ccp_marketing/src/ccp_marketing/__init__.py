"""CCP Digital Marketing - Event creation and social media promotion using Composio SDK.

This package provides both a library interface and CLI for:
- Creating events on Luma, Meetup, and Partiful
- Promoting events on Twitter, LinkedIn, Instagram, Facebook, and Discord
- AI-powered image and copy generation

Library Usage:
    >>> from ccp_marketing import ComposioClient, EventData, FullWorkflow
    >>>
    >>> client = ComposioClient()
    >>> event = EventData(
    ...     title="AI Workshop",
    ...     date="January 25, 2025",
    ...     time="6:00 PM EST",
    ...     location="Philadelphia",
    ...     description="Learn AI basics...",
    ... )
    >>>
    >>> workflow = FullWorkflow(client)
    >>> result = workflow.run(event)
    >>> print(result.primary_url)

CLI Usage:
    $ ccp-marketing create-event --title "AI Workshop" --date "Jan 25" ...
    $ ccp-marketing promote --title "AI Workshop" --event-url "https://..." ...
    $ ccp-marketing full-workflow --title "AI Workshop" ...
"""

__version__ = "0.1.0"

# Core
from ccp_marketing.core.client import ComposioClient
from ccp_marketing.core.config import Config
from ccp_marketing.core.exceptions import (
    CCPMarketingError,
    AuthenticationError,
    PlatformError,
    RateLimitError,
    ValidationError,
)

# Models
from ccp_marketing.models.event import EventData
from ccp_marketing.models.results import (
    PlatformResult,
    EventCreationResult,
    SocialPostResult,
    SocialPromotionResult,
    WorkflowResult,
    Status,
)

# Workflows
from ccp_marketing.workflows import (
    EventCreationWorkflow,
    SocialPromotionWorkflow,
    FullWorkflow,
)

# Adapters
from ccp_marketing.adapters import (
    BasePlatformAdapter,
    LumaAdapter,
    MeetupAdapter,
    PartifulAdapter,
)

# Social
from ccp_marketing.social import (
    BaseSocialPoster,
    SocialPromotionManager,
)

# AI
from ccp_marketing.ai import (
    ImageGenerator,
    CopyGenerator,
)

# State Machine
from ccp_marketing.state_machine import (
    EventState,
    EventCreationStateMachine,
)

__all__ = [
    # Version
    "__version__",
    # Core
    "ComposioClient",
    "Config",
    "CCPMarketingError",
    "AuthenticationError",
    "PlatformError",
    "RateLimitError",
    "ValidationError",
    # Models
    "EventData",
    "PlatformResult",
    "EventCreationResult",
    "SocialPostResult",
    "SocialPromotionResult",
    "WorkflowResult",
    "Status",
    # Workflows
    "EventCreationWorkflow",
    "SocialPromotionWorkflow",
    "FullWorkflow",
    # Adapters
    "BasePlatformAdapter",
    "LumaAdapter",
    "MeetupAdapter",
    "PartifulAdapter",
    # Social
    "BaseSocialPoster",
    "SocialPromotionManager",
    # AI
    "ImageGenerator",
    "CopyGenerator",
    # State Machine
    "EventState",
    "EventCreationStateMachine",
]
