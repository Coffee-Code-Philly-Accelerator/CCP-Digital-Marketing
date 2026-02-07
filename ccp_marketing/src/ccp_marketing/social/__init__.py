"""Social media posting functionality."""

from ccp_marketing.social.base import BaseSocialPoster
from ccp_marketing.social.twitter import TwitterPoster
from ccp_marketing.social.linkedin import LinkedInPoster
from ccp_marketing.social.instagram import InstagramPoster
from ccp_marketing.social.facebook import FacebookPoster
from ccp_marketing.social.discord import DiscordPoster
from ccp_marketing.social.manager import SocialPromotionManager

__all__ = [
    "BaseSocialPoster",
    "TwitterPoster",
    "LinkedInPoster",
    "InstagramPoster",
    "FacebookPoster",
    "DiscordPoster",
    "SocialPromotionManager",
]
