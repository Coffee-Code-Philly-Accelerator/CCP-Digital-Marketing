"""Meetup platform adapter."""

from ccp_marketing.adapters.base import BasePlatformAdapter
from ccp_marketing.models.event import EventData
from ccp_marketing.state_machine.states import EventState


class MeetupAdapter(BasePlatformAdapter):
    """Adapter for Meetup event platform.

    Meetup requires a group-specific URL for event creation.

    Notes:
        - Create URL is derived from group URL: {group_url}/events/create/
        - Has anti-bot detection, requires longer delays (2s)
        - Success URL pattern: meetup.com/*/events/{id}/
    """

    name = "meetup"
    home_url = "https://www.meetup.com/home"
    inter_step_delay = 2.0  # Anti-bot delay

    form_indicators = [
        "event details",
        "what's your event",
        "create event",
        "event title",
        "event name",
    ]

    def __init__(
        self,
        event_data: EventData,
        descriptions: dict[str, str] | None = None,
        image_url: str = "",
        group_url: str = "",
    ) -> None:
        """Initialize Meetup adapter.

        Args:
            event_data: Event data for form filling
            descriptions: Platform-specific descriptions
            image_url: Promotional image URL
            group_url: Meetup group URL (required for creating events)
        """
        super().__init__(event_data, descriptions, image_url)
        self.group_url = group_url

    def get_create_url(self) -> str:
        """Get Meetup event creation URL.

        The URL is derived from the group URL.

        Returns:
            Event creation URL, or empty string if no group URL
        """
        if not self.group_url:
            return ""
        return self.group_url.rstrip("/") + "/events/create/"

    def success_url_check(self, url: str) -> bool:
        """Check if URL indicates successful Meetup event creation.

        Success URL pattern: meetup.com/*/events/{id}/ (not /create)

        Args:
            url: Current page URL

        Returns:
            True if URL matches successful event pattern
        """
        return "meetup.com" in url and "/events/" in url and "/create" not in url

    def get_prompt(self, state: EventState) -> str:
        """Get browser automation prompt for Meetup.

        Args:
            state: Current state machine state

        Returns:
            Natural language prompt for the automation agent
        """
        prompts = {
            EventState.FILL_TITLE: (
                f"Find the event title or event name field, click on it, "
                f"clear any existing text, type exactly: {self.event_data.title}, "
                "then click outside"
            ),
            EventState.FILL_DATE: (
                f"Find and click the date field or date picker, select: {self.event_data.date}. "
                "May need to navigate the calendar."
            ),
            EventState.FILL_TIME: (
                f"Find the start time field, click it, and enter: {self.event_data.time}"
            ),
            EventState.FILL_LOCATION: (
                f"Find the venue or location field, click it, type: {self.event_data.location}, "
                "and select from suggestions or press Enter"
            ),
            EventState.FILL_DESCRIPTION: (
                "Find the description or 'about this event' field, click it, "
                f"and type: {self.get_description()}"
            ),
            EventState.VERIFY_FORM: (
                "Scroll through the form and verify all required fields are filled. "
                "Do not submit yet."
            ),
            EventState.SUBMIT: (
                "Click the 'Publish' or 'Schedule Event' or 'Create Event' button. "
                "Wait for confirmation."
            ),
        }
        return prompts.get(state, "")
