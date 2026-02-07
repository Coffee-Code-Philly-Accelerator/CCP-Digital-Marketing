"""Platform adapters for event creation."""

from ccp_marketing.adapters.base import BasePlatformAdapter
from ccp_marketing.adapters.luma import LumaAdapter
from ccp_marketing.adapters.meetup import MeetupAdapter
from ccp_marketing.adapters.partiful import PartifulAdapter

__all__ = [
    "BasePlatformAdapter",
    "LumaAdapter",
    "MeetupAdapter",
    "PartifulAdapter",
]
