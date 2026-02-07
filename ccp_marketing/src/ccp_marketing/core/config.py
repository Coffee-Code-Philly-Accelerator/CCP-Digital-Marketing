"""Configuration management for CCP Marketing."""

import os
from dataclasses import dataclass, field
from typing import Any

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


@dataclass
class PlatformConfig:
    """Configuration for a specific platform."""

    enabled: bool = True
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 1.0
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Config:
    """Global configuration for CCP Marketing.

    All values can be overridden via environment variables with CCP_ prefix.
    Example: CCP_MAX_WORKERS=10
    """

    # API Configuration
    composio_api_key: str = field(default_factory=lambda: os.environ.get("COMPOSIO_API_KEY", ""))

    # Execution Settings
    max_workers: int = field(
        default_factory=lambda: int(os.environ.get("CCP_MAX_WORKERS", "5"))
    )
    default_timeout: float = field(
        default_factory=lambda: float(os.environ.get("CCP_DEFAULT_TIMEOUT", "60.0"))
    )

    # Retry Settings
    max_retries: int = field(
        default_factory=lambda: int(os.environ.get("CCP_MAX_RETRIES", "3"))
    )
    retry_base_delay: float = field(
        default_factory=lambda: float(os.environ.get("CCP_RETRY_BASE_DELAY", "1.0"))
    )
    retry_max_delay: float = field(
        default_factory=lambda: float(os.environ.get("CCP_RETRY_MAX_DELAY", "30.0"))
    )
    retry_jitter: float = field(
        default_factory=lambda: float(os.environ.get("CCP_RETRY_JITTER", "0.1"))
    )

    # Browser Automation Settings
    browser_action_delay: float = field(
        default_factory=lambda: float(os.environ.get("CCP_BROWSER_ACTION_DELAY", "0.5"))
    )
    browser_page_load_timeout: float = field(
        default_factory=lambda: float(os.environ.get("CCP_BROWSER_PAGE_LOAD_TIMEOUT", "30.0"))
    )

    # Platform-specific configs
    luma: PlatformConfig = field(default_factory=PlatformConfig)
    meetup: PlatformConfig = field(default_factory=PlatformConfig)
    partiful: PlatformConfig = field(default_factory=PlatformConfig)
    twitter: PlatformConfig = field(default_factory=PlatformConfig)
    linkedin: PlatformConfig = field(default_factory=PlatformConfig)
    instagram: PlatformConfig = field(default_factory=PlatformConfig)
    facebook: PlatformConfig = field(default_factory=PlatformConfig)
    discord: PlatformConfig = field(default_factory=PlatformConfig)

    # AI Generation Settings
    image_model: str = field(
        default_factory=lambda: os.environ.get("CCP_IMAGE_MODEL", "gemini-2.5-flash-image")
    )

    # Logging
    log_level: str = field(
        default_factory=lambda: os.environ.get("CCP_LOG_LEVEL", "INFO")
    )
    redact_sensitive: bool = field(
        default_factory=lambda: os.environ.get("CCP_REDACT_SENSITIVE", "true").lower() == "true"
    )

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if not self.composio_api_key:
            # Don't raise immediately - allow library usage without API key for testing
            pass

    def validate(self) -> None:
        """Validate that all required configuration is present.

        Raises:
            ValueError: If required configuration is missing.
        """
        if not self.composio_api_key:
            raise ValueError(
                "COMPOSIO_API_KEY not found. Set it as an environment variable "
                "or pass it to the Config constructor."
            )

    def get_platform_config(self, platform: str) -> PlatformConfig:
        """Get configuration for a specific platform.

        Args:
            platform: Platform name (e.g., 'luma', 'twitter')

        Returns:
            PlatformConfig for the specified platform.

        Raises:
            ValueError: If platform is not recognized.
        """
        platform_lower = platform.lower()
        if hasattr(self, platform_lower):
            config = getattr(self, platform_lower)
            if isinstance(config, PlatformConfig):
                return config
        raise ValueError(f"Unknown platform: {platform}")

    @classmethod
    def from_env(cls) -> "Config":
        """Create a Config instance from environment variables.

        Returns:
            Config instance with values from environment.
        """
        return cls()
