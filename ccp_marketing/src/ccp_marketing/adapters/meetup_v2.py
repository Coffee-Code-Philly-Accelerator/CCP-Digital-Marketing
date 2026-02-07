"""Extended Meetup adapter with full feature support (v2)."""

from __future__ import annotations

from ccp_marketing.adapters.base_v2 import (
    BasePlatformAdapterV2,
    BrowserAction,
    FeatureSupport,
)
from ccp_marketing.browser.element_resolver import ElementTarget
from ccp_marketing.state_machine.states import EventState


class MeetupAdapterV2(BasePlatformAdapterV2):
    """Extended Meetup adapter with full feature support.

    Supports:
    - Image upload (feature images)
    - Tickets (RSVP limits)
    - Co-hosts (event hosts)
    - Recurring events (series)

    Known quirks:
    - Anti-bot detection requires 2s delays between actions
    - Requires group-specific URL for event creation
    - Rich text editor for description
    - Location autocomplete with Google Maps
    """

    name = "meetup"
    create_url = ""  # Dynamic - set from meetup_group_url
    home_url = "https://www.meetup.com"
    inter_step_delay = 2.0  # Longer delay for anti-bot

    # Form indicators
    form_indicators = [
        "event details",
        "what's your event",
        "create event",
        "event title",
        "schedule your event",
        "event name",
    ]

    # Feature support
    feature_support = FeatureSupport(
        image_upload=True,
        tickets=False,  # Meetup uses RSVP limits instead
        cohosts=True,
        recurring=True,
        integrations=False,  # Limited integration options
        capacity=True,
        visibility=True,
    )

    # Element targets
    element_targets = {
        "title": ElementTarget(
            name="event_title",
            css_selector="input[name='name'], input[id='event-name'], input[data-testid='event-title']",
            text_anchor="Event Title",
            ai_prompt="Click on the event title or name field",
            placeholder="Event name",
            near_text="Title",
            wait_after_action=2.0,
        ),
        "date": ElementTarget(
            name="event_date",
            css_selector="input[type='date'], [data-testid='date-input']",
            text_anchor="Date",
            ai_prompt="Click on the date field to open the date picker",
            near_text="When",
            wait_after_action=2.0,
        ),
        "time": ElementTarget(
            name="event_time",
            css_selector="input[type='time'], [data-testid='time-input']",
            text_anchor="Start time",
            ai_prompt="Click on the start time field",
            near_text="Time",
            wait_after_action=2.0,
        ),
        "location": ElementTarget(
            name="event_location",
            css_selector="input[name='venue'], input[placeholder*='location' i], input[placeholder*='venue' i]",
            text_anchor="Location",
            ai_prompt="Click on the venue or location field. This may have autocomplete.",
            placeholder="Search for a venue",
            near_text="Where",
            wait_after_action=2.5,  # Extra for autocomplete
        ),
        "description": ElementTarget(
            name="event_description",
            css_selector="[data-testid='description-editor'], .ql-editor, [contenteditable='true'], textarea",
            text_anchor="Description",
            ai_prompt="Click on the description editor or text area",
            near_text="Details",
            wait_after_action=2.0,
        ),
        "image_upload": ElementTarget(
            name="feature_image",
            css_selector="[data-testid='image-upload'], .image-upload-button",
            text_anchor="Add featured photo",
            ai_prompt="Click on 'Add featured photo' or the image upload area",
            near_text="Featured photo",
            wait_after_action=2.0,
        ),
        "capacity_input": ElementTarget(
            name="rsvp_limit",
            css_selector="input[name='rsvpLimit'], input[type='number']",
            ai_prompt="Find the RSVP limit or attendee limit field",
            near_text="RSVP limit",
            wait_after_action=2.0,
        ),
        "add_cohost": ElementTarget(
            name="add_host_button",
            text_anchor="Add event host",
            ai_prompt="Click on 'Add event host' or 'Add organizer' button",
            wait_after_action=2.0,
        ),
        "recurring_toggle": ElementTarget(
            name="recurring_option",
            text_anchor="Repeat",
            ai_prompt="Click on the 'Repeat' or 'Make this a recurring event' option",
            wait_after_action=2.0,
        ),
        "publish_button": ElementTarget(
            name="publish_button",
            css_selector="button[type='submit'], button:has-text('Publish'), button:has-text('Create')",
            text_anchor="Publish",
            ai_prompt="Click the Publish event or Create event button",
            wait_after_action=3.0,  # Longer wait for submit
        ),
    }

    def get_create_url(self) -> str:
        """Get the Meetup event creation URL.

        Meetup requires a group-specific URL for event creation.
        """
        group_url = getattr(self.event_data, 'meetup_group_url', '')
        if group_url:
            # Ensure URL doesn't have trailing slash
            group_url = group_url.rstrip('/')
            return f"{group_url}/events/create/"
        return "https://www.meetup.com/create/"  # Fallback

    def success_url_check(self, url: str) -> bool:
        """Check if URL indicates successful Meetup event creation.

        Success indicators:
        - URL contains meetup.com and /events/
        - URL does NOT contain /create
        - Usually looks like meetup.com/group-name/events/12345/
        """
        url_lower = url.lower()
        if "meetup.com" not in url_lower:
            return False
        if "/events/" not in url_lower:
            return False
        if "/create" in url_lower:
            return False
        return True

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
            prompt = f"{target.ai_prompt}. Wait 2 seconds for the page to respond. "
            prompt += f"Clear any existing text and type: {value}"
            if state == EventState.FILL_LOCATION:
                prompt += ". Select the first matching result from the autocomplete dropdown."
            return prompt

        if state == EventState.SUBMIT:
            return (
                f"{target.ai_prompt}. "
                "Wait for the page to fully submit and redirect to the event page."
            )

        return target.ai_prompt or ""

    def post_step_wait(self, state: EventState) -> float:
        """Get additional wait time - Meetup needs longer delays."""
        # All states get the anti-bot delay
        return self.inter_step_delay

    def post_submit_action(self) -> str | None:
        """Handle any post-submit actions on Meetup."""
        return (
            "If a confirmation dialog or share modal appears, "
            "dismiss it by clicking 'Done', 'Skip', or the X button. "
            "Wait for the event page to fully load."
        )

    def get_image_upload_actions(self) -> list[BrowserAction]:
        """Get actions for uploading feature image on Meetup."""
        target = self.element_targets["image_upload"]
        return [
            BrowserAction(
                action="click",
                target=target,
                wait_after=2.0,
            ),
            BrowserAction(
                action="ai_task",
                prompt=(
                    f"Upload the image from URL: {self.image_url}. "
                    "Meetup may require downloading the image first. "
                    "If there's a URL option, use it. Otherwise, note that file upload is needed. "
                    "Wait for the upload to complete and a preview to appear."
                ),
                wait_after=4.0,
            ),
        ]

    def get_ticket_config_actions(self) -> list[BrowserAction]:
        """Get actions for configuring RSVP limits on Meetup.

        Meetup doesn't have traditional tickets - uses RSVP limits instead.
        """
        if not self.ticket_config.capacity:
            return []

        return [
            BrowserAction(
                action="ai_task",
                prompt=(
                    f"Find the RSVP limit or attendee limit setting. "
                    f"Set the maximum number of attendees to {self.ticket_config.capacity}. "
                    "This may be under 'Event settings' or 'RSVP settings'."
                ),
                wait_after=2.0,
            ),
        ]

    def get_cohost_actions(self) -> list[BrowserAction]:
        """Get actions for adding event hosts on Meetup."""
        actions = [
            BrowserAction(
                action="click",
                target=self.element_targets["add_cohost"],
                wait_after=2.0,
            ),
        ]

        for cohost in self.cohosts:
            actions.append(BrowserAction(
                action="ai_task",
                prompt=(
                    f"Search for and add event host with email or name: {cohost}. "
                    "They must be an existing member of the Meetup group."
                ),
                wait_after=2.0,
            ))

        return actions

    def get_recurring_actions(self) -> list[BrowserAction]:
        """Get actions for setting up recurring events on Meetup."""
        pattern = self.recurring_config.pattern

        if pattern == "none":
            return []

        actions = [
            BrowserAction(
                action="click",
                target=self.element_targets["recurring_toggle"],
                wait_after=2.0,
            ),
        ]

        pattern_map = {
            "weekly": "Weekly",
            "biweekly": "Every 2 weeks",
            "monthly": "Monthly",
        }

        meetup_pattern = pattern_map.get(pattern, pattern)
        prompt = f"Select '{meetup_pattern}' as the repeat frequency."

        if self.recurring_config.days_of_week:
            days = ", ".join(self.recurring_config.days_of_week)
            prompt += f" Select days: {days}."

        if self.recurring_config.end_date:
            prompt += f" Set the series to end on {self.recurring_config.end_date}."
        elif self.recurring_config.count:
            prompt += f" Set the series to have {self.recurring_config.count} occurrences."

        actions.append(BrowserAction(
            action="ai_task",
            prompt=prompt,
            wait_after=2.0,
        ))

        return actions
