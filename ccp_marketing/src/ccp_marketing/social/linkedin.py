"""LinkedIn social media poster."""

from typing import Any

from ccp_marketing.core.client import ComposioClient
from ccp_marketing.models.event import EventData
from ccp_marketing.models.results import SocialPostResult
from ccp_marketing.social.base import BaseSocialPoster


class LinkedInPoster(BaseSocialPoster):
    """Poster for LinkedIn platform.

    Notes:
        - Requires fetching user profile to get URN
        - Uses LINKEDIN_GET_CURRENT_USER_PROFILE for URN
        - Uses LINKEDIN_CREATE_LINKED_IN_POST for posting
        - Character limit: 3000
    """

    name = "linkedin"
    max_length = 3000

    def post(
        self,
        content: str,
        event_data: EventData | None = None,
        image_url: str = "",
        event_url: str = "",
        **kwargs: Any,
    ) -> SocialPostResult:
        """Post to LinkedIn.

        Args:
            content: Post text
            event_data: Optional event data
            image_url: Optional image URL (not directly supported)
            event_url: Optional event URL to append
            **kwargs: Additional arguments

        Returns:
            SocialPostResult with post status
        """
        # First, get the user profile to obtain the URN
        try:
            profile_data = self.client.execute_action(
                "LINKEDIN_GET_CURRENT_USER_PROFILE",
                {},
            )

            # Extract 'sub' field for URN
            sub = profile_data.get("sub", "")
            if not sub:
                return self._failed_result("Could not determine user URN from profile")

        except Exception as e:
            return self._failed_result(f"Could not get profile: {e}")

        # Build post text
        post_text = self.truncate_content(content)

        # Append event URL if provided
        if event_url:
            post_text = f"{post_text}\n\nRSVP: {event_url}"

        # Create the post
        try:
            result = self.client.execute_action(
                "LINKEDIN_CREATE_LINKED_IN_POST",
                {
                    "author": f"urn:li:person:{sub}",
                    "commentary": post_text,
                    "visibility": "PUBLIC",
                },
            )

            # Extract post ID if available
            post_id = result.get("id", "")

            return self._success_result(
                message="Posted to LinkedIn",
                post_id=str(post_id),
                data=result,
            )

        except Exception as e:
            return self._failed_result(str(e))
