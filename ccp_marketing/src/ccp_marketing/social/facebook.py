"""Facebook social media poster."""

from typing import Any

from ccp_marketing.core.client import ComposioClient
from ccp_marketing.models.event import EventData
from ccp_marketing.models.results import SocialPostResult
from ccp_marketing.social.base import BaseSocialPoster


class FacebookPoster(BaseSocialPoster):
    """Poster for Facebook Pages.

    Notes:
        - Posts to Facebook Pages, not personal profiles
        - Requires page_id parameter
        - Requires page_manage_posts permission
        - Uses FACEBOOK_CREATE_PAGE_POST action
        - Character limit: 63,206 (effectively unlimited)
    """

    name = "facebook"
    max_length = 63206

    def post(
        self,
        content: str,
        event_data: EventData | None = None,
        image_url: str = "",
        event_url: str = "",
        page_id: str = "",
        **kwargs: Any,
    ) -> SocialPostResult:
        """Post to a Facebook Page.

        Args:
            content: Post text
            event_data: Optional event data
            image_url: Optional image URL (for reference in text)
            event_url: Optional event URL to append
            page_id: Required Facebook Page ID
            **kwargs: Additional arguments

        Returns:
            SocialPostResult with post status
        """
        # Page ID is required
        if not page_id:
            return self._skipped_result("No page ID provided")

        # Build post message
        message = content

        # Append event URL if provided
        if event_url:
            message = f"{message}\n\nRSVP: {event_url}"

        try:
            result = self.client.execute_action(
                "FACEBOOK_CREATE_PAGE_POST",
                {
                    "page_id": page_id,
                    "message": message,
                },
            )

            # Extract post info
            post_id = result.get("id", "")
            post_url = ""
            if post_id and "_" in post_id:
                # Facebook post IDs are in format: page_id_post_id
                post_url = f"https://facebook.com/{post_id.replace('_', '/posts/')}"

            return self._success_result(
                message="Posted to Facebook",
                post_id=str(post_id),
                post_url=post_url,
                data=result,
            )

        except Exception as e:
            return self._failed_result(str(e))
