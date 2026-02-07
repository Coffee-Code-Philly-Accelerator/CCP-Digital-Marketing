"""State definitions for the event creation state machine."""

from dataclasses import dataclass
from enum import Enum


class EventState(str, Enum):
    """States for the event creation state machine.

    The state machine progresses through these states to create an event:
    1. INIT - Initialize the state machine
    2. CHECK_DUPLICATE - Check for existing events with same title
    3. NAVIGATE - Navigate to the event creation page
    4. AUTH_CHECK - Verify user is logged in
    5. FILL_TITLE - Fill the title field
    6. FILL_DATE - Fill the date field
    7. FILL_TIME - Fill the time field
    8. FILL_LOCATION - Fill the location field
    9. FILL_DESCRIPTION - Fill the description field
    10. UPLOAD_IMAGE - Upload cover/promotional image (v2)
    11. SET_TICKETS - Configure ticketing options (v2)
    12. ADD_COHOSTS - Add co-hosts/organizers (v2)
    13. SET_RECURRING - Configure recurring schedule (v2)
    14. SET_INTEGRATIONS - Set up integrations like Zoom (v2)
    15. VERIFY_FORM - Verify all fields are filled correctly
    16. SUBMIT - Submit the form
    17. POST_SUBMIT - Handle post-submit actions (modals, etc.)
    18. VERIFY_SUCCESS - Verify the event was created successfully

    Auth states (v2):
    - AWAIT_2FA - Paused waiting for manual 2FA completion
    - RESUME_2FA - Resuming after 2FA completed

    Terminal states:
    - DONE - Event created successfully
    - FAILED - Event creation failed
    - NEEDS_AUTH - Login required
    - DUPLICATE - Event already exists
    - SKIPPED - Platform was skipped
    """

    # Progression states
    INIT = "init"
    CHECK_DUPLICATE = "check_duplicate"
    NAVIGATE = "navigate"
    AUTH_CHECK = "auth_check"
    FILL_TITLE = "fill_title"
    FILL_DATE = "fill_date"
    FILL_TIME = "fill_time"
    FILL_LOCATION = "fill_location"
    FILL_DESCRIPTION = "fill_description"

    # Advanced feature states (v2)
    UPLOAD_IMAGE = "upload_image"
    SET_TICKETS = "set_tickets"
    ADD_COHOSTS = "add_cohosts"
    SET_RECURRING = "set_recurring"
    SET_INTEGRATIONS = "set_integrations"

    # Finalization states
    VERIFY_FORM = "verify_form"
    SUBMIT = "submit"
    POST_SUBMIT = "post_submit"
    VERIFY_SUCCESS = "verify_success"

    # Auth states (v2)
    AWAIT_2FA = "await_2fa"
    RESUME_2FA = "resume_2fa"

    # Terminal states
    DONE = "done"
    FAILED = "failed"
    NEEDS_AUTH = "needs_auth"
    DUPLICATE = "duplicate"
    SKIPPED = "skipped"

    @property
    def is_terminal(self) -> bool:
        """Check if this is a terminal state."""
        return self in TERMINAL_STATES

    @property
    def is_fill_state(self) -> bool:
        """Check if this is a form-filling state."""
        return self in FILL_STATES


# Terminal states - state machine stops when reaching these
TERMINAL_STATES = frozenset({
    EventState.DONE,
    EventState.FAILED,
    EventState.NEEDS_AUTH,
    EventState.DUPLICATE,
    EventState.SKIPPED,
})

# Pause states - waiting for external action (e.g., user 2FA)
PAUSE_STATES = frozenset({
    EventState.AWAIT_2FA,
})

# Form-filling states
FILL_STATES = frozenset({
    EventState.FILL_TITLE,
    EventState.FILL_DATE,
    EventState.FILL_TIME,
    EventState.FILL_LOCATION,
    EventState.FILL_DESCRIPTION,
})

# Advanced feature states (v2)
FEATURE_STATES = frozenset({
    EventState.UPLOAD_IMAGE,
    EventState.SET_TICKETS,
    EventState.ADD_COHOSTS,
    EventState.SET_RECURRING,
    EventState.SET_INTEGRATIONS,
})

# Standard state flow order (basic events)
STATE_FLOW = [
    EventState.INIT,
    EventState.CHECK_DUPLICATE,
    EventState.NAVIGATE,
    EventState.AUTH_CHECK,
    EventState.FILL_TITLE,
    EventState.FILL_DATE,
    EventState.FILL_TIME,
    EventState.FILL_LOCATION,
    EventState.FILL_DESCRIPTION,
    EventState.VERIFY_FORM,
    EventState.SUBMIT,
    EventState.POST_SUBMIT,
    EventState.VERIFY_SUCCESS,
    EventState.DONE,
]

# Full-featured state flow (v2 with images, tickets, cohosts, etc.)
STATE_FLOW_FULL = [
    EventState.INIT,
    EventState.CHECK_DUPLICATE,
    EventState.NAVIGATE,
    EventState.AUTH_CHECK,
    EventState.FILL_TITLE,
    EventState.FILL_DATE,
    EventState.FILL_TIME,
    EventState.FILL_LOCATION,
    EventState.FILL_DESCRIPTION,
    EventState.UPLOAD_IMAGE,
    EventState.SET_TICKETS,
    EventState.ADD_COHOSTS,
    EventState.SET_RECURRING,
    EventState.SET_INTEGRATIONS,
    EventState.VERIFY_FORM,
    EventState.SUBMIT,
    EventState.POST_SUBMIT,
    EventState.VERIFY_SUCCESS,
    EventState.DONE,
]


@dataclass
class StateConfig:
    """Configuration for a specific state.

    Attributes:
        max_retries: Maximum retry attempts for this state
        base_delay: Base delay in seconds for exponential backoff
        max_delay: Maximum delay cap for backoff
    """

    max_retries: int = 2
    base_delay: float = 0.75
    max_delay: float = 8.0


# Default backoff configuration
DEFAULT_BASE_DELAY = 0.75
DEFAULT_MAX_DELAY = 8.0
BACKOFF_MULTIPLIER = 2.0


# Per-state configuration
STATE_CONFIG: dict[EventState, StateConfig] = {
    EventState.CHECK_DUPLICATE: StateConfig(max_retries=1, base_delay=0.5),
    EventState.NAVIGATE: StateConfig(max_retries=2, base_delay=1.0),
    EventState.AUTH_CHECK: StateConfig(max_retries=1, base_delay=0.5),
    EventState.FILL_TITLE: StateConfig(max_retries=2, base_delay=0.75),
    EventState.FILL_DATE: StateConfig(max_retries=2, base_delay=0.75),
    EventState.FILL_TIME: StateConfig(max_retries=2, base_delay=0.75),
    EventState.FILL_LOCATION: StateConfig(max_retries=2, base_delay=0.75),
    EventState.FILL_DESCRIPTION: StateConfig(max_retries=2, base_delay=0.75),
    # Advanced feature states (v2)
    EventState.UPLOAD_IMAGE: StateConfig(max_retries=2, base_delay=1.5, max_delay=10.0),
    EventState.SET_TICKETS: StateConfig(max_retries=2, base_delay=1.0),
    EventState.ADD_COHOSTS: StateConfig(max_retries=2, base_delay=1.0),
    EventState.SET_RECURRING: StateConfig(max_retries=2, base_delay=1.0),
    EventState.SET_INTEGRATIONS: StateConfig(max_retries=2, base_delay=1.0),
    # Finalization
    EventState.VERIFY_FORM: StateConfig(max_retries=2, base_delay=1.0),
    # Only 1 retry for submit to avoid creating duplicate events
    EventState.SUBMIT: StateConfig(max_retries=1, base_delay=1.0),
    EventState.POST_SUBMIT: StateConfig(max_retries=1, base_delay=1.0),
    EventState.VERIFY_SUCCESS: StateConfig(max_retries=3, base_delay=1.5, max_delay=12.0),
    # Auth states
    EventState.AWAIT_2FA: StateConfig(max_retries=0, base_delay=0),  # No retry, waits for user
    EventState.RESUME_2FA: StateConfig(max_retries=1, base_delay=1.0),
}


def get_state_config(state: EventState) -> StateConfig:
    """Get configuration for a specific state.

    Args:
        state: The state to get configuration for

    Returns:
        StateConfig for the state (defaults if not explicitly configured)
    """
    return STATE_CONFIG.get(state, StateConfig())


def get_next_state(current: EventState) -> EventState | None:
    """Get the next state in the standard flow.

    Args:
        current: Current state

    Returns:
        Next state in flow, or None if at end or not in flow
    """
    try:
        idx = STATE_FLOW.index(current)
        if idx + 1 < len(STATE_FLOW):
            return STATE_FLOW[idx + 1]
    except ValueError:
        pass
    return None
