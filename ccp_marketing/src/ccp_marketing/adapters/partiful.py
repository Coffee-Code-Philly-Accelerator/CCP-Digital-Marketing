"""Partiful platform adapter."""

from ccp_marketing.adapters.base import BasePlatformAdapter
from ccp_marketing.state_machine.states import EventState


class PartifulAdapter(BasePlatformAdapter):
    """Adapter for Partiful event platform.

    Partiful is a casual event platform popular for social gatherings.

    Notes:
        - Shows a share/invite modal after creation that needs dismissal
        - Success URL pattern: partiful.com/e/{event_id}
        - Create page: partiful.com/create
    """

    name = "partiful"
    create_url = "https://partiful.com/create"
    home_url = "https://partiful.com/home"
    inter_step_delay = 0.6

    form_indicators = [
        "untitled event",
        "event title",
        "add event",
        "create party",
        "what's the occasion",
    ]

    def success_url_check(self, url: str) -> bool:
        """Check if URL indicates successful Partiful event creation.

        Success URL pattern: partiful.com/e/{event_id}

        Args:
            url: Current page URL

        Returns:
            True if URL matches successful event pattern
        """
        return "partiful.com/e/" in url

    def get_prompt(self, state: EventState) -> str:
        """Get browser automation prompt for Partiful.

        Args:
            state: Current state machine state

        Returns:
            Natural language prompt for the automation agent
        """
        prompts = {
            EventState.FILL_TITLE: (
                f"Click on the event title field (may say 'Untitled Event' or similar), "
                f"clear it, type exactly: {self.event_data.title}, click outside"
            ),
            EventState.FILL_DATE: (
                f"Click on the date field or 'When' section, select: {self.event_data.date}"
            ),
            EventState.FILL_TIME: (
                f"Click on the time field, enter: {self.event_data.time}"
            ),
            EventState.FILL_LOCATION: (
                f"Click on the location field or 'Where' section, "
                f"type: {self.event_data.location}, select from dropdown or press Enter"
            ),
            EventState.FILL_DESCRIPTION: (
                f"Click on the description or details field, type: {self.get_description()}"
            ),
            EventState.VERIFY_FORM: (
                "Check that all event details are filled in correctly. "
                "Do not publish yet."
            ),
            EventState.SUBMIT: (
                "Click 'Save', 'Publish', or 'Create' button to create the event. "
                "Wait for navigation."
            ),
        }
        return prompts.get(state, "")

    def post_submit_action(self) -> str | None:
        """Get post-submit action for Partiful.

        Partiful shows a share/invite modal after creation.

        Returns:
            Prompt to dismiss the share modal
        """
        return (
            "If a share, invite, or 'tell your friends' modal appears, "
            "click the X button, 'Skip', 'Maybe later', or click outside to dismiss it"
        )
