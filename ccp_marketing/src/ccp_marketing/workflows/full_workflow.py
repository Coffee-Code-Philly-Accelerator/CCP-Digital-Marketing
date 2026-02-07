"""Full workflow orchestrator combining event creation and promotion."""

import logging
import time
from datetime import datetime
from typing import Callable

from ccp_marketing.core.client import ComposioClient
from ccp_marketing.core.config import Config
from ccp_marketing.models.event import EventData
from ccp_marketing.models.results import WorkflowResult
from ccp_marketing.workflows.event_creation import EventCreationWorkflow
from ccp_marketing.workflows.social_promotion import SocialPromotionWorkflow

logger = logging.getLogger(__name__)


class FullWorkflow:
    """Complete workflow orchestrator for event creation and promotion.

    Combines:
    1. Event creation on Luma, Meetup, Partiful
    2. Social media promotion on Twitter, LinkedIn, Instagram, Facebook, Discord

    Example:
        >>> workflow = FullWorkflow(client)
        >>> result = workflow.run(
        ...     event_data=event,
        ...     meetup_group_url="https://meetup.com/mygroup",
        ...     discord_channel_id="1234567890",
        ... )
        >>> print(result.summary)
    """

    def __init__(
        self,
        client: ComposioClient,
        config: Config | None = None,
        llm_func: Callable[[str], tuple[str, str | None]] | None = None,
    ) -> None:
        """Initialize the full workflow.

        Args:
            client: Composio client for API calls
            config: Optional configuration
            llm_func: Optional LLM function for content generation
        """
        self.client = client
        self.config = config or Config.from_env()
        self.event_workflow = EventCreationWorkflow(client, config, llm_func)
        self.social_workflow = SocialPromotionWorkflow(client, config, llm_func)

    def run(
        self,
        event_data: EventData,
        meetup_group_url: str = "",
        discord_channel_id: str = "",
        facebook_page_id: str = "",
        event_platforms: list[str] | None = None,
        social_platforms: list[str] | None = None,
        skip_event_platforms: list[str] | None = None,
        skip_social_platforms: list[str] | None = None,
    ) -> WorkflowResult:
        """Run the complete workflow.

        Phase 1: Create events on event platforms
        Phase 2: Promote on social media platforms

        Args:
            event_data: Event data
            meetup_group_url: Meetup group URL
            discord_channel_id: Discord channel ID
            facebook_page_id: Facebook page ID
            event_platforms: Event platforms to use
            social_platforms: Social platforms to use
            skip_event_platforms: Event platforms to skip
            skip_social_platforms: Social platforms to skip

        Returns:
            WorkflowResult with results from both phases
        """
        start_time = time.time()

        self._log_phase_header("PHASE 1: Creating Events")

        # Run event creation workflow
        event_result = self.event_workflow.run(
            event_data=event_data,
            platforms=event_platforms,
            skip_platforms=skip_event_platforms,
            meetup_group_url=meetup_group_url,
            generate_image=True,
            generate_descriptions=True,
        )

        # Get the primary event URL for promotion
        event_url = event_result.primary_url

        if not event_url:
            self._log("Warning: No event URL captured. Promotion will proceed without link.")

        self._log_phase_header("PHASE 2: Social Media Promotion")

        # Get image URL from event creation if available
        image_url = ""
        for r in event_result.all_results:
            if r and r.data and r.data.get("image_url"):
                image_url = r.data["image_url"]
                break

        # Run social promotion workflow
        social_result = self.social_workflow.run(
            event_data=event_data,
            event_url=event_url,
            image_url=image_url,
            skip_platforms=skip_social_platforms,
            discord_channel_id=discord_channel_id,
            facebook_page_id=facebook_page_id,
            generate_image=not bool(image_url),  # Only generate if we don't have one
            generate_copy=True,
        )

        duration = time.time() - start_time

        result = WorkflowResult(
            event_creation=event_result,
            social_promotion=social_result,
            primary_url=event_url,
            duration_seconds=duration,
        )

        self._log_phase_header("WORKFLOW COMPLETE")
        self._log(result.summary)
        self._log(f"Duration: {duration:.1f} seconds")
        self._log(f"Primary URL: {event_url}")

        return result

    def _log(self, message: str) -> None:
        """Log a message with timestamp."""
        ts = datetime.utcnow().isoformat()
        logger.info(f"[{ts}] {message}")
        print(f"[{ts}] {message}")

    def _log_phase_header(self, title: str) -> None:
        """Log a phase header."""
        separator = "=" * 60
        print(f"\n{separator}")
        print(title)
        print(f"{separator}\n")
