"""AI content/copy generation for social media posts."""

import logging
from dataclasses import dataclass
from typing import Any, Callable

from ccp_marketing.core.client import ComposioClient
from ccp_marketing.models.event import EventData
from ccp_marketing.utils.extraction import extract_json_from_text

logger = logging.getLogger(__name__)


@dataclass
class CopyResult:
    """Result from copy generation.

    Attributes:
        success: Whether generation succeeded
        copies: Dictionary of platform-specific content
        error: Error message if failed
        raw_response: Raw LLM response
    """

    success: bool
    copies: dict[str, str]
    error: str = ""
    raw_response: str = ""


class CopyGenerator:
    """AI-powered copy generator for social media posts.

    Generates platform-optimized content for events and promotions.

    Example:
        >>> generator = CopyGenerator(llm_func)
        >>> result = generator.generate_for_event(event_data)
        >>> if result.success:
        ...     print(result.copies["twitter"])
    """

    # Platform content guidelines
    PLATFORM_GUIDELINES = {
        "twitter": "Concise, hashtags, under 280 chars",
        "linkedin": "Professional, detailed, industry-focused",
        "instagram": "Engaging, emoji-friendly, hashtags",
        "facebook": "Conversational, community-focused",
        "discord": "Markdown formatting, casual tone",
        "luma": "Professional, concise",
        "meetup": "Community-focused, detailed",
        "partiful": "Fun, casual, emoji-friendly",
    }

    def __init__(
        self,
        llm_func: Callable[[str], tuple[str, str | None]] | None = None,
    ) -> None:
        """Initialize the copy generator.

        Args:
            llm_func: LLM invocation function that takes a prompt and returns
                      (response, error). If None, uses a mock implementation.
        """
        self._llm_func = llm_func or self._mock_llm

    def _mock_llm(self, prompt: str) -> tuple[str, str | None]:
        """Mock LLM for testing."""
        logger.warning("Using mock LLM - no actual content generation")
        return '{"twitter": "mock", "linkedin": "mock", "instagram": "mock", "facebook": "mock", "discord": "mock"}', None

    def generate(
        self,
        prompt: str,
        platforms: list[str] | None = None,
    ) -> CopyResult:
        """Generate platform-specific copy from a prompt.

        Args:
            prompt: Base prompt for content generation
            platforms: List of platforms to generate for

        Returns:
            CopyResult with generated content
        """
        platforms = platforms or list(self.PLATFORM_GUIDELINES.keys())

        # Build the generation prompt
        guidelines = "\n".join(
            f"- {platform.title()}: {self.PLATFORM_GUIDELINES.get(platform, 'General')}"
            for platform in platforms
        )

        full_prompt = f"""{prompt}

Generate content for these platforms:
{guidelines}

Return JSON with keys: {", ".join(platforms)}
Each value should be the complete post text optimized for that platform."""

        try:
            response, error = self._llm_func(full_prompt)

            if error:
                return CopyResult(
                    success=False,
                    copies={},
                    error=str(error),
                    raw_response=response or "",
                )

            # Parse the JSON response
            copies = extract_json_from_text(response)

            # Validate we have all platforms
            if not copies or not all(p in copies for p in platforms):
                logger.warning("Incomplete JSON response, using fallback")
                return CopyResult(
                    success=False,
                    copies=copies,
                    error="Incomplete response - missing some platforms",
                    raw_response=response,
                )

            return CopyResult(
                success=True,
                copies=copies,
                raw_response=response,
            )

        except Exception as e:
            logger.exception("Copy generation failed")
            return CopyResult(
                success=False,
                copies={},
                error=str(e),
            )

    def generate_for_event(
        self,
        event_data: EventData,
        platforms: list[str] | None = None,
    ) -> CopyResult:
        """Generate platform-specific copy for an event.

        Args:
            event_data: Event data
            platforms: List of platforms to generate for

        Returns:
            CopyResult with generated content
        """
        prompt = f"""Generate social media posts for this event:

Event: {event_data.title}
Date: {event_data.date} at {event_data.time}
Location: {event_data.location}
Description: {event_data.description}
RSVP Link: {event_data.url or "[link]"}"""

        return self.generate(prompt, platforms)

    def generate_descriptions(
        self,
        event_data: EventData,
        platforms: list[str] | None = None,
    ) -> CopyResult:
        """Generate platform-specific event descriptions.

        Similar to generate_for_event but optimized for event page descriptions
        rather than social posts.

        Args:
            event_data: Event data
            platforms: List of platforms (luma, meetup, partiful)

        Returns:
            CopyResult with generated descriptions
        """
        platforms = platforms or ["luma", "meetup", "partiful"]

        prompt = f"""Generate platform-specific event descriptions based on this info:

Title: {event_data.title}
Date: {event_data.date} at {event_data.time}
Location: {event_data.location}
Original Description: {event_data.description}

Each description should be optimized for that platform's audience and format."""

        return self.generate(prompt, platforms)

    def get_fallback_copies(
        self,
        event_data: EventData,
        platforms: list[str] | None = None,
    ) -> dict[str, str]:
        """Generate simple fallback copy without AI.

        Used when LLM generation fails.

        Args:
            event_data: Event data
            platforms: List of platforms

        Returns:
            Dictionary of basic copy per platform
        """
        platforms = platforms or list(self.PLATFORM_GUIDELINES.keys())

        # Basic template
        base = (
            f"{event_data.title}\n\n"
            f"{event_data.date} at {event_data.time}\n"
            f"{event_data.location}\n\n"
        )

        if event_data.url:
            base += f"RSVP: {event_data.url}"

        copies = {}
        for platform in platforms:
            if platform == "twitter":
                # Truncate for Twitter
                copies[platform] = event_data.get_short_description(280)
            elif platform == "discord":
                # Add markdown for Discord
                copies[platform] = f"**{event_data.title}**\n\n{base}"
            else:
                copies[platform] = base

        return copies
