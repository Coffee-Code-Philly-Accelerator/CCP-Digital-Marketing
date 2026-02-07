"""Discord social media poster."""

from typing import Any

from ccp_marketing.core.client import ComposioClient
from ccp_marketing.models.event import EventData
from ccp_marketing.models.results import SocialPostResult
from ccp_marketing.social.base import BaseSocialPoster


class DiscordPoster(BaseSocialPoster):
    """Poster for Discord channels.

    Notes:
        - Posts to a specific Discord channel
        - Requires channel_id parameter
        - Requires bot in server with send message permission
        - Supports markdown formatting
        - Uses DISCORD_SEND_MESSAGE action
        - Character limit: 2000
    """

    name = "discord"
    max_length = 2000

    def post(
        self,
        content: str,
        event_data: EventData | None = None,
        image_url: str = "",
        event_url: str = "",
        channel_id: str = "",
        **kwargs: Any,
    ) -> SocialPostResult:
        """Post to a Discord channel.

        Args:
            content: Message text (supports markdown)
            event_data: Optional event data
            image_url: Optional image URL (added to message)
            event_url: Optional event URL to append
            channel_id: Required Discord channel ID
            **kwargs: Additional arguments

        Returns:
            SocialPostResult with post status
        """
        # Channel ID is required
        if not channel_id:
            return self._skipped_result("No channel ID provided")

        # Build message (Discord supports markdown)
        message = content

        # Append event URL if provided
        if event_url:
            message = f"{message}\n\n**RSVP:** {event_url}"

        # Append image if available
        if image_url:
            message = f"{message}\n\n{image_url}"

        # Truncate if needed
        message = self.truncate_content(message)

        try:
            result = self.client.execute_action(
                "DISCORD_SEND_MESSAGE",
                {
                    "channel_id": channel_id,
                    "content": message,
                },
            )

            # Extract message info
            message_id = result.get("id", "")
            guild_id = result.get("guild_id", "")

            # Build message URL if we have IDs
            message_url = ""
            if guild_id and channel_id and message_id:
                message_url = f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"

            return self._success_result(
                message="Posted to Discord",
                post_id=str(message_id),
                post_url=message_url,
                data=result,
            )

        except Exception as e:
            return self._failed_result(str(e))

    def format_event_announcement(self, event_data: EventData, event_url: str = "") -> str:
        """Format an event as a Discord announcement with markdown.

        Args:
            event_data: Event data
            event_url: Optional event URL

        Returns:
            Formatted Discord message with markdown
        """
        lines = [
            f"# 📅 {event_data.title}",
            "",
            f"**When:** {event_data.date} at {event_data.time}",
            f"**Where:** {event_data.location}",
            "",
            event_data.get_short_description(500),
        ]

        if event_url:
            lines.extend(["", f"**RSVP:** {event_url}"])

        return "\n".join(lines)
