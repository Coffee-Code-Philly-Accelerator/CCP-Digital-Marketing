"""Extended Luma adapter with full feature support (v2)."""

from __future__ import annotations

from ccp_marketing.adapters.base_v2 import (
    BasePlatformAdapterV2,
    BrowserAction,
    FeatureSupport,
)
from ccp_marketing.browser.element_resolver import ElementTarget
from ccp_marketing.state_machine.states import EventState


class LumaAdapterV2(BasePlatformAdapterV2):
    """Extended Luma adapter with full feature support.

    Supports:
    - Image upload (cover images)
    - Tickets (free and paid)
    - Co-hosts
    - Recurring events
    - Integrations (Zoom, Google Meet)

    Known quirks:
    - React date picker needs extra 1.5s wait
    - Image upload via URL or file
    - Share modal appears after creation
    """

    name = "luma"
    create_url = "https://lu.ma/create"
    home_url = "https://lu.ma/home"
    inter_step_delay = 0.5

    # Form indicators
    form_indicators = [
        "event title",
        "create event",
        "what's your event",
        "add event",
        "event name",
    ]

    # Feature support
    feature_support = FeatureSupport(
        image_upload=True,
        tickets=True,
        cohosts=True,
        recurring=True,
        integrations=True,
        capacity=True,
        visibility=True,
    )

    # Element targets for semantic UI targeting
    element_targets = {
        "title": ElementTarget(
            name="event_title",
            css_selector="input[name='title'], input[placeholder*='title' i]",
            text_anchor="Event Title",
            aria_label="event title",
            ai_prompt="Click on the event title field and clear any existing text",
            placeholder="Event Title",
            near_text="What's your event called?",
            wait_after_action=0.5,
        ),
        "date": ElementTarget(
            name="event_date",
            css_selector="[data-testid='date-picker'], .date-input, input[type='date']",
            text_anchor="Date",
            ai_prompt="Click on the date field or calendar icon to open the date picker",
            near_text="When",
            wait_after_action=1.5,  # Extra wait for React date picker
        ),
        "time": ElementTarget(
            name="event_time",
            css_selector="[data-testid='time-picker'], .time-input, input[type='time']",
            text_anchor="Start Time",
            ai_prompt="Click on the start time field",
            near_text="Time",
            wait_after_action=0.5,
        ),
        "location": ElementTarget(
            name="event_location",
            css_selector="input[placeholder*='location' i], input[placeholder*='venue' i]",
            text_anchor="Location",
            ai_prompt="Click on the location or venue field",
            placeholder="Add Location",
            near_text="Where",
            wait_after_action=1.0,  # Wait for autocomplete
        ),
        "description": ElementTarget(
            name="event_description",
            css_selector="[data-testid='description'], textarea, .ProseMirror, [contenteditable='true']",
            text_anchor="Description",
            aria_role="textbox",
            ai_prompt="Click on the description field or text area",
            near_text="About",
            wait_after_action=0.5,
        ),
        "image_upload": ElementTarget(
            name="cover_image",
            css_selector="[data-testid='cover-image'], .image-upload, .cover-upload",
            text_anchor="Add Cover",
            ai_prompt="Click on the cover image area or 'Add Cover' button to upload an image",
            near_text="Cover",
            wait_after_action=1.0,
        ),
        "tickets_button": ElementTarget(
            name="tickets_section",
            text_anchor="Tickets",
            ai_prompt="Click on the Tickets or Registration section to expand it",
            wait_after_action=0.5,
        ),
        "ticket_price": ElementTarget(
            name="ticket_price_input",
            css_selector="input[name='price'], input[type='number']",
            ai_prompt="Find the ticket price field and enter the price",
            near_text="Price",
            wait_after_action=0.5,
        ),
        "ticket_capacity": ElementTarget(
            name="capacity_input",
            css_selector="input[name='capacity'], input[placeholder*='capacity' i]",
            ai_prompt="Find the capacity or limit field",
            near_text="Capacity",
            wait_after_action=0.5,
        ),
        "add_cohost": ElementTarget(
            name="add_cohost_button",
            text_anchor="Add Host",
            ai_prompt="Click on 'Add Host' or 'Add Co-host' button",
            wait_after_action=0.5,
        ),
        "recurring_toggle": ElementTarget(
            name="recurring_option",
            text_anchor="Recurring",
            ai_prompt="Click on the Recurring event toggle or option",
            wait_after_action=0.5,
        ),
        "publish_button": ElementTarget(
            name="publish_button",
            css_selector="button[type='submit'], button:has-text('Publish')",
            text_anchor="Publish",
            ai_prompt="Click the Publish or Create Event button",
            wait_after_action=2.0,
        ),
    }

    def success_url_check(self, url: str) -> bool:
        """Check if URL indicates successful Luma event creation.

        Success indicators:
        - URL contains lu.ma/ but NOT /create or /home
        - Usually looks like lu.ma/abc123 (event page)
        """
        if "lu.ma/" not in url.lower():
            return False
        url_lower = url.lower()
        blocked_patterns = ["/create", "/home", "/login", "/signup"]
        return not any(pattern in url_lower for pattern in blocked_patterns)

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
            return f"{target.ai_prompt}. Clear any existing text. Type exactly: {value}"

        if state == EventState.SUBMIT:
            return target.ai_prompt or "Click the Publish or Create Event button"

        return target.ai_prompt or ""

    def post_step_wait(self, state: EventState) -> float:
        """Get additional wait time after a step."""
        # Extra wait for date picker (React component)
        if state == EventState.FILL_DATE:
            return 1.5
        # Extra wait for location autocomplete
        if state == EventState.FILL_LOCATION:
            return 1.0
        return self.inter_step_delay

    def post_submit_action(self) -> str | None:
        """Handle Luma's share modal after creation."""
        return (
            "If a share or invite modal appears, click the X button, "
            "'Skip', 'Maybe later', or click outside the modal to dismiss it. "
            "Wait for the event page to fully load."
        )

    def get_image_upload_actions(self) -> list[BrowserAction]:
        """Get actions for uploading cover image on Luma."""
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
                    f"Upload the image from URL: {self.image_url}. "
                    "If there's a URL input option, paste the URL. "
                    "If only file upload is available, download and upload the image. "
                    "Wait for the upload to complete and the image preview to appear."
                ),
                wait_after=3.0,
            ),
        ]

    def get_ticket_config_actions(self) -> list[BrowserAction]:
        """Get actions for configuring tickets on Luma."""
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
                prompt="Select 'Free' ticket type or ensure registration is free",
                wait_after=0.5,
            ))
        else:
            actions.append(BrowserAction(
                action="ai_task",
                prompt=(
                    f"Configure paid tickets: "
                    f"Set price to ${self.ticket_config.price} {self.ticket_config.currency}. "
                    f"Ticket name: {self.ticket_config.ticket_name}"
                ),
                wait_after=1.0,
            ))

        if self.ticket_config.capacity:
            actions.append(BrowserAction(
                action="ai_task",
                prompt=f"Set event capacity to {self.ticket_config.capacity} attendees",
                wait_after=0.5,
            ))

        return actions

    def get_cohost_actions(self) -> list[BrowserAction]:
        """Get actions for adding co-hosts on Luma."""
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
                    f"Add co-host with email: {cohost}. "
                    "Enter the email in the search/invite field and send the invitation."
                ),
                wait_after=1.0,
            ))

        return actions

    def get_recurring_actions(self) -> list[BrowserAction]:
        """Get actions for setting up recurring events on Luma."""
        pattern = self.recurring_config.pattern

        if pattern == "none":
            return []

        actions = [
            BrowserAction(
                action="click",
                target=self.element_targets["recurring_toggle"],
                wait_after=0.5,
            ),
        ]

        pattern_map = {
            "weekly": "Select 'Weekly' recurring pattern",
            "biweekly": "Select 'Every 2 weeks' or 'Biweekly' recurring pattern",
            "monthly": "Select 'Monthly' recurring pattern",
            "daily": "Select 'Daily' recurring pattern",
        }

        prompt = pattern_map.get(pattern, f"Select '{pattern}' recurring pattern")

        if self.recurring_config.end_date:
            prompt += f". Set end date to {self.recurring_config.end_date}"
        elif self.recurring_config.count:
            prompt += f". Set to repeat {self.recurring_config.count} times"

        actions.append(BrowserAction(
            action="ai_task",
            prompt=prompt,
            wait_after=1.0,
        ))

        return actions

    def get_integration_actions(self) -> list[BrowserAction]:
        """Get actions for setting up integrations on Luma."""
        actions = []

        if self.integration_config.zoom:
            actions.append(BrowserAction(
                action="ai_task",
                prompt=(
                    "Find the video conferencing or Zoom integration section. "
                    "Enable Zoom for this event. "
                    "If prompted to connect Zoom account, note that it needs authorization."
                ),
                wait_after=2.0,
            ))

        if self.integration_config.google_meet:
            actions.append(BrowserAction(
                action="ai_task",
                prompt=(
                    "Find the video conferencing section. "
                    "Enable Google Meet for this event."
                ),
                wait_after=2.0,
            ))

        return actions
