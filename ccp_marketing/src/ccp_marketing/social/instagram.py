"""Instagram social media poster."""

from typing import Any

from ccp_marketing.core.client import ComposioClient
from ccp_marketing.models.event import EventData
from ccp_marketing.models.results import SocialPostResult
from ccp_marketing.social.base import BaseSocialPoster


class InstagramPoster(BaseSocialPoster):
    """Poster for Instagram platform.

    Notes:
        - Requires a Business or Creator account
        - Requires fetching user info to get user_id
        - Requires an image URL (posts cannot be text-only)
        - Uses INSTAGRAM_USERS_GET_LOGGED_IN_USER_INFO for user_id
        - Uses INSTAGRAM_MEDIA_POST_MEDIA for posting
        - Character limit: 2200
    """

    name = "instagram"
    max_length = 2200

    def post(
        self,
        content: str,
        event_data: EventData | None = None,
        image_url: str = "",
        event_url: str = "",
        **kwargs: Any,
    ) -> SocialPostResult:
        """Post to Instagram.

        Args:
            content: Caption text
            event_data: Optional event data
            image_url: Required image URL for the post
            event_url: Optional event URL (added to caption)
            **kwargs: Additional arguments

        Returns:
            SocialPostResult with post status
        """
        # Instagram requires an image
        if not image_url:
            return self._skipped_result("No image available - Instagram requires an image")

        # First, get the user info to obtain user_id
        try:
            user_data = self.client.execute_action(
                "INSTAGRAM_USERS_GET_LOGGED_IN_USER_INFO",
                {},
            )

            user_id = user_data.get("id", "")
            if not user_id:
                return self._failed_result("Could not determine user ID")

        except Exception as e:
            return self._failed_result(f"Could not get user info: {e}")

        # Build caption
        caption = self.truncate_content(content)

        # Instagram doesn't support clickable links in captions, but we can include it
        if event_url:
            caption = f"{caption}\n\n🔗 Link in bio or: {event_url}"

        # Post the image
        try:
            result = self.client.execute_action(
                "INSTAGRAM_MEDIA_POST_MEDIA",
                {
                    "user_id": user_id,
                    "image_url": image_url,
                    "caption": caption,
                    "media_type": "IMAGE",
                },
            )

            # Extract post info
            post_id = result.get("id", "")
            permalink = result.get("permalink", "")

            return self._success_result(
                message="Posted to Instagram",
                post_id=str(post_id),
                post_url=permalink,
                data=result,
            )

        except Exception as e:
            return self._failed_result(str(e))
