"""Core infrastructure for CCP Marketing."""

from ccp_marketing.core.client import ComposioClient
from ccp_marketing.core.config import Config
from ccp_marketing.core.exceptions import (
    CCPMarketingError,
    AuthenticationError,
    PlatformError,
    RateLimitError,
    ValidationError,
)

__all__ = [
    "ComposioClient",
    "Config",
    "CCPMarketingError",
    "AuthenticationError",
    "PlatformError",
    "RateLimitError",
    "ValidationError",
]
