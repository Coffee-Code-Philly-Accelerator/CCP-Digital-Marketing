"""Social media promotion workflow orchestrator."""

import logging
from datetime import datetime
from typing import Callable

from ccp_marketing.core.client import ComposioClient
from ccp_marketing.core.config import Config
from ccp_marketing.models.event import EventData
from ccp_marketing.models.results import SocialPromotionResult
from ccp_marketing.ai.image_generator import ImageGenerator
from ccp_marketing.ai.copy_generator import CopyGenerator
from ccp_marketing.social.manager import SocialPromotionManager

logger = logging.getLogger(__name__)


class SocialPromotionWorkflow:
    """Workflow orchestrator for social media promotion.

    Handles the complete social promotion process:
    1. Generate promotional image (if not provided)
    2. Generate platform-specific copy
    3. Post to all social platforms in parallel

    Example:
        >>> workflow = SocialPromotionWorkflow(client)
        >>> result = workflow.run(
        ...     event_data=event,
        ...     event_url="https://lu.ma/myevent",
        ... )
        >>> print(result.summary)
    """

    def __init__(
        self,
        client: ComposioClient,
        config: Config | None = None,
        llm_func: Callable[[str], tuple[str, str | None]] | None = None,
    ) -> None:
        """Initialize the workflow.

        Args:
            client: Composio client for API calls
            config: Optional configuration
            llm_func: Optional LLM function for content generation
        """
        self.client = client
        self.config = config or Config.from_env()
        self.image_generator = ImageGenerator(client, config)
        self.copy_generator = CopyGenerator(llm_func)
        self.social_manager = SocialPromotionManager(client, config)

    def run(
        self,
        event_data: EventData,
        event_url: str = "",
        image_url: str = "",
        skip_platforms: list[str] | None = None,
        discord_channel_id: str = "",
        facebook_page_id: str = "",
        generate_image: bool = True,
        generate_copy: bool = True,
    ) -> SocialPromotionResult:
        """Run the social promotion workflow.

        Args:
            event_data: Event data
            event_url: Event RSVP URL
            image_url: Pre-existing image URL (skips generation if provided)
            skip_platforms: Platforms to skip
            discord_channel_id: Discord channel ID
            facebook_page_id: Facebook page ID
            generate_image: Whether to generate image (if not provided)
            generate_copy: Whether to generate copy

        Returns:
            SocialPromotionResult with results from all platforms
        """
        self._log("Starting social media promotion workflow")

        # Step 1: Get or generate promotional image
        if not image_url and generate_image:
            self._log("Generating promotional image...")
            image_result = self.image_generator.generate_for_event(event_data)
            if image_result.success:
                image_url = image_result.url
                self._log(f"Image generated: {image_url}")
            else:
                self._log(f"Image generation failed: {image_result.error}")

        # Step 2: Generate platform-specific copy
        copies: dict[str, str] = {}
        social_platforms = ["twitter", "linkedin", "instagram", "facebook", "discord"]

        if generate_copy:
            self._log("Generating platform-specific copy...")
            copy_result = self.copy_generator.generate_for_event(
                event_data,
                platforms=social_platforms,
            )
            if copy_result.success:
                copies = copy_result.copies
                self._log("Copy generated for all platforms")
            else:
                self._log(f"Copy generation failed: {copy_result.error}")
                copies = self.copy_generator.get_fallback_copies(
                    event_data,
                    platforms=social_platforms,
                )
        else:
            copies = self.copy_generator.get_fallback_copies(
                event_data,
                platforms=social_platforms,
            )

        # Step 3: Post to social platforms
        self._log("Posting to social platforms...")
        result = self.social_manager.promote(
            event_data=event_data,
            copies=copies,
            image_url=image_url,
            event_url=event_url,
            skip_platforms=skip_platforms,
            discord_channel_id=discord_channel_id,
            facebook_page_id=facebook_page_id,
        )

        # Update image_url in result if we generated one
        if image_url:
            result.image_url = image_url

        self._log(f"Workflow complete: {result.summary}")
        self._log_platform_results(result)

        return result

    def _log(self, message: str) -> None:
        """Log a message with timestamp."""
        ts = datetime.utcnow().isoformat()
        logger.info(f"[{ts}] {message}")
        print(f"[{ts}] {message}")

    def _log_platform_results(self, result: SocialPromotionResult) -> None:
        """Log individual platform results."""
        platforms = [
            ("Twitter", result.twitter),
            ("LinkedIn", result.linkedin),
            ("Instagram", result.instagram),
            ("Facebook", result.facebook),
            ("Discord", result.discord),
        ]

        for name, r in platforms:
            if r:
                status = r.status.value
                error = f" - {r.error}" if r.error else ""
                print(f"{name}: {status}{error}")
