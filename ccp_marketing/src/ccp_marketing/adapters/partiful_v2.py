"""Extended Partiful adapter with full feature support (v2)."""

from __future__ import annotations

from ccp_marketing.adapters.base_v2 import (
    BasePlatformAdapterV2,
    BrowserAction,
    FeatureSupport,
)
from ccp_marketing.browser.element_resolver import ElementTarget
from ccp_marketing.state_machine.states import EventState


class PartifulAdapterV2(BasePlatformAdapterV2):
    """Extended Partiful adapter with full feature support.

    Supports:
    - Image upload (cover images)
    - Tickets (free/paid)
    - Co-hosts
    - Integrations (calendar)

    Known quirks:
    - Shows share modal after creation - needs dismissal
    - Mobile-first design with emoji-friendly UI
    - Description supports rich formatting
    """

    name = "partiful"
    create_url = "https://partiful.com/create"
    home_url = "https://partiful.com/home"
    inter_step_delay = 0.5

    # Form indicators
    form_indicators = [
        "untitled event",
        "event title",
        "create party",
        "create event",
        "what's the occasion",
        "party name",
    ]

    # Feature support
    feature_support = FeatureSupport(
        image_upload=True,
        tickets=True,
        cohosts=True,
        recurring=False,  # Partiful doesn't support recurring natively
        integrations=True,
        capacity=True,
        visibility=True,
    )

    # Element targets
    element_targets = {
        "title": ElementTarget(
            name="event_title",
            css_selector="input[name='title'], input[placeholder*='title' i], [data-testid='event-title']",
            text_anchor="Untitled Event",
            ai_prompt="Click on the event title field (may say 'Untitled Event')",
            placeholder="Untitled Event",
            near_text="Title",
            wait_after_action=0.5,
        ),
        "date": ElementTarget(
            name="event_date",
            css_selector="[data-testid='date-picker'], input[type='date']",
            text_anchor="Date",
            ai_prompt="Click on the date field to open the date picker",
            near_text="When",
            wait_after_action=1.0,
        ),
        "time": ElementTarget(
            name="event_time",
            css_selector="[data-testid='time-picker'], input[type='time']",
            text_anchor="Time",
            ai_prompt="Click on the time field to set the start time",
            near_text="Time",
            wait_after_action=0.5,
        ),
        "location": ElementTarget(
            name="event_location",
            css_selector="input[placeholder*='location' i], input[placeholder*='address' i]",
            text_anchor="Location",
            ai_prompt="Click on the location field",
            placeholder="Add location",
            near_text="Where",
            wait_after_action=1.0,
        ),
        "description": ElementTarget(
            name="event_description",
            css_selector="textarea, [contenteditable='true'], [data-testid='description']",
            text_anchor="Description",
            ai_prompt="Click on the description field to add event details",
            near_text="Details",
            wait_after_action=0.5,
        ),
        "image_upload": ElementTarget(
            name="cover_image",
            css_selector="[data-testid='cover-upload'], .cover-image, .image-upload",
            text_anchor="Add cover",
            ai_prompt="Click on the cover image area or 'Add cover' to upload an image",
            near_text="Cover",
            wait_after_action=1.0,
        ),
        "tickets_button": ElementTarget(
            name="tickets_section",
            text_anchor="Tickets",
            ai_prompt="Click on the Tickets section to configure ticketing",
            wait_after_action=0.5,
        ),
        "add_cohost": ElementTarget(
            name="add_cohost_button",
            text_anchor="Add host",
            ai_prompt="Click on 'Add host' or the co-host section",
            wait_after_action=0.5,
        ),
        "visibility_toggle": ElementTarget(
            name="visibility_option",
            text_anchor="Private",
            ai_prompt="Click on the visibility setting (Private/Public)",
            wait_after_action=0.5,
        ),
        "publish_button": ElementTarget(
            name="publish_button",
            css_selector="button[type='submit'], button:has-text('Create'), button:has-text('Publish')",
            text_anchor="Create",
            ai_prompt="Click the Create or Publish button to create the event",
            wait_after_action=2.0,
        ),
    }

    def success_url_check(self, url: str) -> bool:
        """Check if URL indicates successful Partiful event creation.

        Success indicators:
        - URL matches partiful.com/e/{event_id}
        - NOT on /create page
        """
        url_lower = url.lower()
        if "partiful.com" not in url_lower:
            return False
        # Success URL pattern: partiful.com/e/xxxxx
        if "/e/" in url_lower:
            return True
        # Also check for event in URL without /e/
        if "/create" in url_lower:
            return False
        return False

    def get_prompt(self, state: EventState) -> str:
        """Get browser automation prompt for a state."""
        target = self.get_target_for_state(state)
        value = self.get_value_for_state(state)

        if not target:
            return ""

        if state in [
            EventState.FILL_TITLE,
            EventState.FILL_DATE,
            EventState.FILL_TIME,
            EventState.FILL_LOCATION,
            EventState.FILL_DESCRIPTION,
        ]:
            return f"{target.ai_prompt}. Clear existing text and type: {value}"

        if state == EventState.SUBMIT:
            return (
                f"{target.ai_prompt}. "
                "Wait for the event to be created and the page to redirect."
            )

        return target.ai_prompt or ""

    def post_step_wait(self, state: EventState) -> float:
        """Get additional wait time after a step."""
        # Extra wait for location autocomplete
        if state == EventState.FILL_LOCATION:
            return 1.0
        return self.inter_step_delay

    def post_submit_action(self) -> str | None:
        """Handle Partiful's share modal after creation."""
        return (
            "After event creation, a share/invite modal will likely appear. "
            "Dismiss it by clicking the X button, 'Skip', 'Maybe later', "
            "or clicking outside the modal. "
            "Make sure you can see the event page with the event details."
        )

    def get_image_upload_actions(self) -> list[BrowserAction]:
        """Get actions for uploading cover image on Partiful."""
        target = self.element_targets["image_upload"]
        return [
            BrowserAction(
                action="click",
                target=target,
                wait_after=1.0,
            ),
            BrowserAction(
                action="ai_task",
                prompt=(
                    f"Upload the cover image from URL: {self.image_url}. "
                    "Partiful may offer URL input or file upload. "
                    "Use whichever is available. "
                    "Wait for the image to upload and display as the cover."
                ),
                wait_after=3.0,
            ),
        ]

    def get_ticket_config_actions(self) -> list[BrowserAction]:
        """Get actions for configuring tickets on Partiful."""
        actions = [
            BrowserAction(
                action="click",
                target=self.element_targets["tickets_button"],
                wait_after=0.5,
            ),
        ]

        if self.ticket_config.is_free:
            actions.append(BrowserAction(
                action="ai_task",
                prompt="Ensure the event is set to Free or no ticket price",
                wait_after=0.5,
            ))
        else:
            actions.append(BrowserAction(
                action="ai_task",
                prompt=(
                    f"Set up paid tickets: "
                    f"Price ${self.ticket_config.price} {self.ticket_config.currency}. "
                    f"Ticket name: {self.ticket_config.ticket_name}"
                ),
                wait_after=1.0,
            ))

        if self.ticket_config.capacity:
            actions.append(BrowserAction(
                action="ai_task",
                prompt=f"Set guest limit or capacity to {self.ticket_config.capacity}",
                wait_after=0.5,
            ))

        return actions

    def get_cohost_actions(self) -> list[BrowserAction]:
        """Get actions for adding co-hosts on Partiful."""
        actions = [
            BrowserAction(
                action="click",
                target=self.element_targets["add_cohost"],
                wait_after=0.5,
            ),
        ]

        for cohost in self.cohosts:
            actions.append(BrowserAction(
                action="ai_task",
                prompt=(
                    f"Add co-host with email or phone: {cohost}. "
                    "Enter in the host invitation field and send invite."
                ),
                wait_after=1.0,
            ))

        return actions

    def get_recurring_actions(self) -> list[BrowserAction]:
        """Get actions for recurring events.

        Partiful doesn't natively support recurring events,
        so this returns empty list.
        """
        return []

    def get_integration_actions(self) -> list[BrowserAction]:
        """Get actions for setting up integrations on Partiful."""
        actions = []

        if self.integration_config.calendar_sync:
            actions.append(BrowserAction(
                action="ai_task",
                prompt=(
                    "Look for calendar integration or 'Add to Calendar' options. "
                    "Enable Google Calendar or Apple Calendar sync if available."
                ),
                wait_after=1.0,
            ))

        return actions
