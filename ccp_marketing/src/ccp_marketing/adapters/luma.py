"""Luma (lu.ma) platform adapter."""

from ccp_marketing.adapters.base import BasePlatformAdapter
from ccp_marketing.state_machine.states import EventState


class LumaAdapter(BasePlatformAdapter):
    """Adapter for Luma (lu.ma) event platform.

    Luma is a modern event platform with a clean React-based UI.

    Notes:
        - The date picker is a React component that needs extra wait time
        - URLs follow pattern: lu.ma/{event_slug}
        - Create page: lu.ma/create
    """

    name = "luma"
    create_url = "https://lu.ma/create"
    home_url = "https://lu.ma/home"
    inter_step_delay = 0.5

    form_indicators = [
        "event title",
        "create event",
        "what's your event",
        "add event",
    ]

    def success_url_check(self, url: str) -> bool:
        """Check if URL indicates successful Luma event creation.

        Success URL pattern: lu.ma/{slug} (not /create or /home)

        Args:
            url: Current page URL

        Returns:
            True if URL matches successful event pattern
        """
        return "lu.ma/" in url and "/create" not in url and "/home" not in url

    def get_prompt(self, state: EventState) -> str:
        """Get browser automation prompt for Luma.

        Args:
            state: Current state machine state

        Returns:
            Natural language prompt for the automation agent
        """
        prompts = {
            EventState.FILL_TITLE: (
                f"Click on the event title field (may say 'Event Title' or 'Untitled Event'), "
                f"clear any existing text, type exactly: {self.event_data.title}, "
                "then click outside the field to confirm"
            ),
            EventState.FILL_DATE: (
                f"Click on the date field or calendar icon, select the date: {self.event_data.date}. "
                "Wait for the calendar to respond before clicking."
            ),
            EventState.FILL_TIME: (
                f"Click on the time field, enter the time: {self.event_data.time}"
            ),
            EventState.FILL_LOCATION: (
                f"Click on the location or venue field, type: {self.event_data.location}, "
                "then select from the dropdown or press Enter"
            ),
            EventState.FILL_DESCRIPTION: (
                "Click on the description field (may say 'Add a description'), "
                f"clear any existing text, and type: {self.get_description()}"
            ),
            EventState.VERIFY_FORM: (
                "Review the form and make sure all fields are filled correctly. "
                "Do not click any buttons yet."
            ),
            EventState.SUBMIT: (
                "Click the 'Publish' or 'Create Event' button to publish the event. "
                "Wait for the page to navigate to the new event."
            ),
        }
        return prompts.get(state, "")

    def post_step_wait(self, state: EventState) -> float:
        """Get post-step wait time for Luma.

        The React date picker needs extra time to settle.

        Args:
            state: Current state

        Returns:
            Wait time in seconds
        """
        if state == EventState.FILL_DATE:
            return 1.5  # Extra wait for React date picker
        return self.inter_step_delay
