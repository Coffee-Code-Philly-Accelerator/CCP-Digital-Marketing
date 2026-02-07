"""AI image generation for promotional content."""

import logging
from dataclasses import dataclass
from typing import Any

from ccp_marketing.core.client import ComposioClient
from ccp_marketing.core.config import Config
from ccp_marketing.models.event import EventData

logger = logging.getLogger(__name__)


@dataclass
class ImageResult:
    """Result from image generation.

    Attributes:
        success: Whether generation succeeded
        url: Public URL of generated image
        error: Error message if failed
        data: Raw response data
    """

    success: bool
    url: str = ""
    error: str = ""
    data: dict[str, Any] | None = None


class ImageGenerator:
    """AI-powered promotional image generator.

    Uses Gemini's imagen model to generate promotional images for events.

    Example:
        >>> generator = ImageGenerator(client)
        >>> result = generator.generate_for_event(event_data)
        >>> if result.success:
        ...     print(f"Image: {result.url}")
    """

    DEFAULT_STYLE = "professional, vibrant colors, suitable for social media"

    def __init__(
        self,
        client: ComposioClient,
        config: Config | None = None,
    ) -> None:
        """Initialize the image generator.

        Args:
            client: Composio client for API calls
            config: Optional configuration
        """
        self.client = client
        self.config = config or Config.from_env()

    def generate(
        self,
        prompt: str,
        model: str | None = None,
    ) -> ImageResult:
        """Generate an image from a prompt.

        Args:
            prompt: Image generation prompt
            model: Optional model override

        Returns:
            ImageResult with URL or error
        """
        model = model or self.config.image_model

        try:
            result = self.client.execute_action(
                "GEMINI_GENERATE_IMAGE",
                {
                    "prompt": prompt,
                    "model": model,
                },
            )

            # Try multiple possible URL/path fields in the response
            url = (
                result.get("publicUrl")
                or result.get("url")
                or result.get("image")
                or result.get("imageUrl")
                or ""
            )
            if url:
                logger.info(f"Image generated: {url}")
                return ImageResult(success=True, url=url, data=result)
            else:
                return ImageResult(
                    success=False,
                    error="No URL in response",
                    data=result,
                )

        except Exception as e:
            logger.exception("Image generation failed")
            return ImageResult(success=False, error=str(e))

    def generate_for_event(
        self,
        event_data: EventData,
        style: str | None = None,
        include_location: bool = True,
    ) -> ImageResult:
        """Generate a promotional image for an event.

        Args:
            event_data: Event data to base image on
            style: Optional style override
            include_location: Whether to include location hints in prompt

        Returns:
            ImageResult with URL or error
        """
        style = style or self.DEFAULT_STYLE

        # Build the prompt
        prompt_parts = [
            "Create a modern, eye-catching event promotional graphic for:",
            event_data.title,
            f"Style: {style}",
        ]

        if include_location and event_data.location:
            prompt_parts.append(f"Include visual elements suggesting: {event_data.location}")

        # Important: no text in the image (text often looks bad in AI images)
        prompt_parts.append("Do not include any text in the image.")

        prompt = " ".join(prompt_parts)

        return self.generate(prompt)

    def generate_social_image(
        self,
        title: str,
        theme: str = "technology",
        aspect_ratio: str = "square",
    ) -> ImageResult:
        """Generate a social media optimized image.

        Args:
            title: Event or content title
            theme: Visual theme (technology, community, celebration, etc.)
            aspect_ratio: Image aspect ratio (square, landscape, portrait)

        Returns:
            ImageResult with URL or error
        """
        themes = {
            "technology": "digital, futuristic, clean lines, tech-inspired",
            "community": "warm, welcoming, diverse, inclusive",
            "celebration": "festive, colorful, energetic, exciting",
            "professional": "corporate, sleek, modern, business",
            "creative": "artistic, imaginative, unique, expressive",
        }

        theme_style = themes.get(theme, themes["technology"])

        prompts_by_ratio = {
            "square": "social media post",
            "landscape": "website banner or Twitter header",
            "portrait": "Instagram story or Pinterest pin",
        }

        format_hint = prompts_by_ratio.get(aspect_ratio, "social media post")

        prompt = (
            f"Create a {format_hint} graphic for: {title}. "
            f"Style: {theme_style}, visually striking, {self.DEFAULT_STYLE}. "
            "Do not include any text in the image."
        )

        return self.generate(prompt)
