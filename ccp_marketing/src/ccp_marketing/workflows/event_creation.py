"""Event creation workflow orchestrator."""

import logging
from datetime import datetime
from typing import Callable

from ccp_marketing.core.client import ComposioClient
from ccp_marketing.core.config import Config
from ccp_marketing.models.event import EventData
from ccp_marketing.models.results import EventCreationResult, PlatformResult, Status
from ccp_marketing.adapters import LumaAdapter, MeetupAdapter, PartifulAdapter
from ccp_marketing.ai.image_generator import ImageGenerator
from ccp_marketing.ai.copy_generator import CopyGenerator
from ccp_marketing.state_machine import EventCreationStateMachine

logger = logging.getLogger(__name__)


class EventCreationWorkflow:
    """Workflow orchestrator for creating events on multiple platforms.

    Handles the complete event creation process:
    1. Generate promotional image
    2. Generate platform-specific descriptions
    3. Create events on each platform using state machine

    Example:
        >>> workflow = EventCreationWorkflow(client)
        >>> result = workflow.run(
        ...     event_data=event,
        ...     platforms=["luma", "meetup", "partiful"],
        ... )
        >>> print(result.primary_url)
    """

    DEFAULT_PLATFORMS = ["luma", "meetup", "partiful"]

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

    def run(
        self,
        event_data: EventData,
        platforms: list[str] | None = None,
        skip_platforms: list[str] | None = None,
        meetup_group_url: str = "",
        generate_image: bool = True,
        generate_descriptions: bool = True,
    ) -> EventCreationResult:
        """Run the event creation workflow.

        Args:
            event_data: Event data
            platforms: Platforms to create events on
            skip_platforms: Platforms to skip
            meetup_group_url: Meetup group URL (required for Meetup)
            generate_image: Whether to generate promotional image
            generate_descriptions: Whether to generate platform descriptions

        Returns:
            EventCreationResult with results from all platforms
        """
        platforms = platforms or self.DEFAULT_PLATFORMS
        skip_platforms = skip_platforms or []
        skip_set = {p.lower() for p in skip_platforms}
        active_platforms = [p for p in platforms if p.lower() not in skip_set]

        self._log(f"Creating event on platforms: {active_platforms}")
        if skip_platforms:
            self._log(f"Skipping platforms: {skip_platforms}")

        # Step 1: Generate promotional image
        image_url = ""
        if generate_image:
            self._log("Generating promotional image...")
            image_result = self.image_generator.generate_for_event(event_data)
            if image_result.success:
                image_url = image_result.url
                self._log(f"Image generated: {image_url}")
            else:
                self._log(f"Image generation failed: {image_result.error}")

        # Step 2: Generate platform-specific descriptions
        descriptions: dict[str, str] = {}
        if generate_descriptions:
            self._log("Generating platform descriptions...")
            desc_result = self.copy_generator.generate_descriptions(
                event_data,
                platforms=["luma", "meetup", "partiful"],
            )
            if desc_result.success:
                descriptions = desc_result.copies
                self._log("Descriptions generated for all platforms")
            else:
                self._log(f"Description generation failed: {desc_result.error}")
                descriptions = self.copy_generator.get_fallback_copies(
                    event_data,
                    platforms=["luma", "meetup", "partiful"],
                )

        # Step 3: Create events using state machine
        results: dict[str, PlatformResult] = {}

        # Create adapters
        adapters = {
            "luma": LumaAdapter(event_data, descriptions, image_url),
            "meetup": MeetupAdapter(event_data, descriptions, image_url, meetup_group_url),
            "partiful": PartifulAdapter(event_data, descriptions, image_url),
        }

        # Execute for each platform (sequential for stability)
        for platform in active_platforms:
            if platform not in adapters:
                self._log(f"Unknown platform: {platform}")
                continue

            adapter = adapters[platform]
            self._log(f"Creating event on {platform.title()}...")

            machine = EventCreationStateMachine(self.client, adapter)
            machine_result = machine.run()

            results[platform] = PlatformResult(
                platform=platform,
                status=Status(machine_result.status) if machine_result.status in Status._value2member_map_ else Status.FAILED,
                url=machine_result.url,
                error=machine_result.error,
                data=machine_result.to_dict(),
            )

            self._log(f"{platform.title()}: {machine_result.status}")

        return EventCreationResult(
            luma=results.get("luma"),
            meetup=results.get("meetup"),
            partiful=results.get("partiful"),
        )

    def _log(self, message: str) -> None:
        """Log a message with timestamp."""
        ts = datetime.utcnow().isoformat()
        logger.info(f"[{ts}] {message}")
        print(f"[{ts}] {message}")
