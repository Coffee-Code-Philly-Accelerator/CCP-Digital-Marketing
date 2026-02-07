"""Twitter/X social media poster."""

from typing import Any

from ccp_marketing.core.client import ComposioClient
from ccp_marketing.models.event import EventData
from ccp_marketing.models.results import SocialPostResult
from ccp_marketing.social.base import BaseSocialPoster


class TwitterPoster(BaseSocialPoster):
    """Poster for Twitter/X platform.

    Notes:
        - Character limit: 280
        - Can include image URL in tweet text
        - Uses TWITTER_CREATION_OF_A_POST action
    """

    name = "twitter"
    max_length = 280

    def post(
        self,
        content: str,
        event_data: EventData | None = None,
        image_url: str = "",
        event_url: str = "",
        **kwargs: Any,
    ) -> SocialPostResult:
        """Post a tweet.

        Args:
            content: Tweet text
            event_data: Optional event data
            image_url: Optional image URL to append
            event_url: Optional event URL (included in content)
            **kwargs: Additional arguments

        Returns:
            SocialPostResult with post status
        """
        # Build tweet text
        tweet_text = content

        # Append image URL if available (reserve space)
        if image_url:
            # Twitter auto-shortens URLs to ~23 chars
            url_reserve = 30
            tweet_text = self.truncate_content(content, reserve=url_reserve)
            tweet_text = f"{tweet_text}\n\n{image_url}"
        else:
            tweet_text = self.truncate_content(content)

        try:
            result = self.client.execute_action(
                "TWITTER_CREATION_OF_A_POST",
                {"text": tweet_text},
            )

            # Extract tweet info from response
            tweet_id = result.get("id", result.get("id_str", ""))
            tweet_url = ""
            if tweet_id:
                # Build tweet URL if we have the user info
                username = result.get("user", {}).get("screen_name", "")
                if username:
                    tweet_url = f"https://twitter.com/{username}/status/{tweet_id}"

            return self._success_result(
                message="Tweet posted",
                post_id=str(tweet_id),
                post_url=tweet_url,
                data=result,
            )

        except Exception as e:
            return self._failed_result(str(e))
