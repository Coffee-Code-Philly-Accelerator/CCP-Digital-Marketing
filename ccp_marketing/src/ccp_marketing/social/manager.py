"""Social promotion manager for coordinating posts across platforms."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from ccp_marketing.core.client import ComposioClient
from ccp_marketing.core.config import Config
from ccp_marketing.models.event import EventData
from ccp_marketing.models.results import SocialPostResult, SocialPromotionResult, Status
from ccp_marketing.social.twitter import TwitterPoster
from ccp_marketing.social.linkedin import LinkedInPoster
from ccp_marketing.social.instagram import InstagramPoster
from ccp_marketing.social.facebook import FacebookPoster
from ccp_marketing.social.discord import DiscordPoster

logger = logging.getLogger(__name__)


class SocialPromotionManager:
    """Manager for coordinating social media promotion across platforms.

    Handles parallel posting to multiple social platforms with:
    - Platform-specific content formatting
    - Parallel execution for speed
    - Graceful handling of individual platform failures
    - Skip platform support

    Example:
        >>> manager = SocialPromotionManager(client)
        >>> copies = {"twitter": "...", "linkedin": "...", ...}
        >>> result = manager.promote(
        ...     event_data=event,
        ...     copies=copies,
        ...     image_url="https://...",
        ...     event_url="https://lu.ma/...",
        ... )
        >>> print(result.summary)
    """

    def __init__(
        self,
        client: ComposioClient,
        config: Config | None = None,
    ) -> None:
        """Initialize the social promotion manager.

        Args:
            client: Composio client for API calls
            config: Optional configuration
        """
        self.client = client
        self.config = config or Config.from_env()

        # Initialize posters
        self.posters = {
            "twitter": TwitterPoster(client),
            "linkedin": LinkedInPoster(client),
            "instagram": InstagramPoster(client),
            "facebook": FacebookPoster(client),
            "discord": DiscordPoster(client),
        }

    def promote(
        self,
        event_data: EventData,
        copies: dict[str, str],
        image_url: str = "",
        event_url: str = "",
        skip_platforms: list[str] | None = None,
        discord_channel_id: str = "",
        facebook_page_id: str = "",
        **kwargs: Any,
    ) -> SocialPromotionResult:
        """Promote an event across social media platforms.

        Args:
            event_data: Event data
            copies: Platform-specific content (keyed by platform name)
            image_url: Promotional image URL
            event_url: Event RSVP URL
            skip_platforms: List of platforms to skip
            discord_channel_id: Discord channel ID for posting
            facebook_page_id: Facebook page ID for posting
            **kwargs: Additional platform-specific arguments

        Returns:
            SocialPromotionResult with results from all platforms
        """
        skip_platforms = skip_platforms or []
        skip_set = {p.lower() for p in skip_platforms}

        # Build platform arguments
        platform_args = {
            "twitter": {},
            "linkedin": {},
            "instagram": {},
            "facebook": {"page_id": facebook_page_id},
            "discord": {"channel_id": discord_channel_id},
        }

        results: dict[str, SocialPostResult] = {}

        # Execute posts in parallel
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            futures = {}

            for platform, poster in self.posters.items():
                if platform in skip_set:
                    results[platform] = SocialPostResult(
                        platform=platform,
                        status=Status.SKIPPED,
                        message="Skipped by user",
                    )
                    continue

                content = copies.get(platform, event_data.description)
                args = platform_args.get(platform, {})

                future = executor.submit(
                    poster.post,
                    content=content,
                    event_data=event_data,
                    image_url=image_url,
                    event_url=event_url,
                    **args,
                )
                futures[future] = platform

            # Collect results
            for future in as_completed(futures):
                platform = futures[future]
                try:
                    results[platform] = future.result()
                except Exception as e:
                    logger.exception(f"Error posting to {platform}")
                    results[platform] = SocialPostResult(
                        platform=platform,
                        status=Status.FAILED,
                        error=str(e),
                    )

        return SocialPromotionResult(
            twitter=results.get("twitter"),
            linkedin=results.get("linkedin"),
            instagram=results.get("instagram"),
            facebook=results.get("facebook"),
            discord=results.get("discord"),
            image_url=image_url,
        )

    def post_to_single(
        self,
        platform: str,
        content: str,
        event_data: EventData | None = None,
        image_url: str = "",
        event_url: str = "",
        **kwargs: Any,
    ) -> SocialPostResult:
        """Post to a single platform.

        Args:
            platform: Platform name
            content: Content to post
            event_data: Optional event data
            image_url: Optional image URL
            event_url: Optional event URL
            **kwargs: Platform-specific arguments

        Returns:
            SocialPostResult for the platform

        Raises:
            ValueError: If platform is not recognized
        """
        platform_lower = platform.lower()
        poster = self.posters.get(platform_lower)

        if not poster:
            raise ValueError(f"Unknown platform: {platform}")

        return poster.post(
            content=content,
            event_data=event_data,
            image_url=image_url,
            event_url=event_url,
            **kwargs,
        )
