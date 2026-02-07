"""Event creation state machine implementation."""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable

from ccp_marketing.core.client import ComposioClient
from ccp_marketing.state_machine.states import (
    EventState,
    StateConfig,
    TERMINAL_STATES,
    STATE_FLOW,
    get_state_config,
    get_next_state,
    DEFAULT_BASE_DELAY,
    DEFAULT_MAX_DELAY,
    BACKOFF_MULTIPLIER,
)
from ccp_marketing.utils.backoff import exponential_backoff

if TYPE_CHECKING:
    from ccp_marketing.adapters.base import BasePlatformAdapter

logger = logging.getLogger(__name__)


# Auth detection patterns
AUTH_PATTERNS = [
    "sign in",
    "log in",
    "login",
    "sign up",
    "create account",
    "enter your email",
    "enter your password",
    "verification code",
    "2fa",
    "two-factor",
    "authenticate",
    "verify your",
    "continue with google",
    "continue with apple",
    "continue with email",
]

# Validation error patterns
VALIDATION_ERROR_PATTERNS = [
    "required",
    "fix errors",
    "please enter",
    "invalid",
    "can't be blank",
    "must be",
    "is required",
    "please fill",
]


def check_needs_auth(content: str) -> bool:
    """Check if page content indicates authentication is needed.

    Args:
        content: Page content to check

    Returns:
        True if auth appears to be needed
    """
    content_lower = content.lower()
    return any(pattern in content_lower for pattern in AUTH_PATTERNS)


def check_validation_errors(content: str) -> bool:
    """Check if page content shows validation errors.

    Args:
        content: Page content to check

    Returns:
        True if validation errors are detected
    """
    content_lower = content.lower()
    return any(pattern in content_lower for pattern in VALIDATION_ERROR_PATTERNS)


@dataclass
class StateResult:
    """Result from executing a state.

    Attributes:
        success: Whether the state completed successfully
        next_state: Next state to transition to (if different from default)
        error: Error message if failed
    """

    success: bool
    next_state: EventState | None = None
    error: str = ""


@dataclass
class MachineResult:
    """Result from the state machine execution.

    Attributes:
        status: Final status string
        url: Event URL if created
        error: Error message if failed
        screenshot: Screenshot URL for debugging
        signals: Verification signals dictionary
        final_state: The terminal state reached
    """

    status: str
    url: str = ""
    error: str = ""
    screenshot: str = ""
    signals: dict[str, bool] = field(default_factory=dict)
    final_state: EventState = EventState.FAILED

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status,
            "url": self.url,
            "error": self.error,
            "screenshot": self.screenshot,
            "signals": self.signals,
        }


class EventCreationStateMachine:
    """State machine for creating events with atomic steps and verification.

    This state machine handles the complexity of creating events on various
    platforms through browser automation. It provides:

    - Atomic state transitions with retry logic
    - Exponential backoff on failures
    - Multi-signal verification for success
    - Screenshot capture on failures
    - Auth detection and graceful handling

    Example:
        >>> from ccp_marketing.adapters import LumaAdapter
        >>> adapter = LumaAdapter(event_data, descriptions, image_url)
        >>> machine = EventCreationStateMachine(client, adapter)
        >>> result = machine.run()
        >>> if result.status == "PUBLISHED":
        ...     print(f"Event created: {result.url}")
    """

    def __init__(
        self,
        client: ComposioClient,
        adapter: "BasePlatformAdapter",
    ) -> None:
        """Initialize the state machine.

        Args:
            client: Composio client for API calls
            adapter: Platform-specific adapter
        """
        self.client = client
        self.adapter = adapter
        self.platform = adapter.name
        self.state = EventState.INIT
        self.attempts: dict[EventState, int] = {}
        self.screenshot_url = ""
        self.event_url = ""
        self.error_message = ""
        self.verification_signals: dict[str, bool] = {}

    def run(self) -> MachineResult:
        """Execute the state machine until a terminal state is reached.

        Returns:
            MachineResult with final status and details
        """
        while self.state not in TERMINAL_STATES:
            self._log(f"Executing state...")

            try:
                result = self._execute_state()
            except Exception as e:
                logger.exception(f"Unexpected error in state {self.state}")
                result = StateResult(success=False, error=str(e))

            if result.success:
                # Move to next state
                next_state = result.next_state or self._next_state()
                self.state = next_state
                self.attempts[self.state] = 0
            else:
                # Handle failure with retry logic
                current_attempts = self.attempts.get(self.state, 0) + 1
                self.attempts[self.state] = current_attempts

                config = get_state_config(self.state)

                if current_attempts >= config.max_retries:
                    self._log(f"Max retries ({config.max_retries}) reached: {result.error}")
                    self.error_message = result.error or "Max retries exceeded"
                    self.screenshot_url = self._capture_screenshot(self.error_message)

                    # Use explicit next_state if provided (for terminal states)
                    if result.next_state and result.next_state.is_terminal:
                        self.state = result.next_state
                    else:
                        self.state = EventState.FAILED
                else:
                    delay = self._calculate_backoff(current_attempts, config)
                    self._log(
                        f"Retry {current_attempts}/{config.max_retries} "
                        f"after {delay:.2f}s: {result.error}"
                    )
                    time.sleep(delay)

        self._log(f"Terminal state reached. URL: {self.event_url}")
        return self._build_result()

    def _execute_state(self) -> StateResult:
        """Execute the current state.

        Returns:
            StateResult indicating success/failure and next state
        """
        handlers: dict[EventState, Callable[[], StateResult]] = {
            EventState.INIT: self._handle_init,
            EventState.CHECK_DUPLICATE: self._handle_check_duplicate,
            EventState.NAVIGATE: self._handle_navigate,
            EventState.AUTH_CHECK: self._handle_auth_check,
            EventState.FILL_TITLE: self._handle_fill_field,
            EventState.FILL_DATE: self._handle_fill_field,
            EventState.FILL_TIME: self._handle_fill_field,
            EventState.FILL_LOCATION: self._handle_fill_field,
            EventState.FILL_DESCRIPTION: self._handle_fill_field,
            EventState.VERIFY_FORM: self._handle_verify_form,
            EventState.SUBMIT: self._handle_submit,
            EventState.POST_SUBMIT: self._handle_post_submit,
            EventState.VERIFY_SUCCESS: self._handle_verify_success,
        }

        handler = handlers.get(self.state)
        if not handler:
            return StateResult(
                success=False,
                next_state=EventState.FAILED,
                error=f"No handler for state {self.state}",
            )

        return handler()

    def _next_state(self) -> EventState:
        """Get the next state in the standard flow.

        Returns:
            Next state or DONE if at end
        """
        next_state = get_next_state(self.state)
        if next_state is None:
            self._log(f"WARNING: State {self.state} not found in flow, jumping to DONE")
            return EventState.DONE
        return next_state

    def _calculate_backoff(self, attempt: int, config: StateConfig) -> float:
        """Calculate backoff delay for retry.

        Args:
            attempt: Current attempt number
            config: State configuration

        Returns:
            Delay in seconds
        """
        return exponential_backoff(
            attempt=attempt - 1,  # 0-indexed
            base_delay=config.base_delay,
            max_delay=config.max_delay,
            jitter=0.2,
        )

    def _handle_init(self) -> StateResult:
        """Initialize - validate and move to next state."""
        return StateResult(success=True)

    def _handle_check_duplicate(self) -> StateResult:
        """Check for existing event with same title."""
        home_url = self.adapter.get_home_url()
        if not home_url:
            return StateResult(success=True)

        try:
            data = self.client.browser_navigate(home_url)
            content = data.get("pageSnapshot", "")

            title_lower = self.adapter.event_data.title.lower()
            if title_lower in content.lower():
                self._log("Potential duplicate found")
                self.error_message = f"Event '{self.adapter.event_data.title}' may already exist"
                return StateResult(
                    success=False,
                    next_state=EventState.DUPLICATE,
                    error=self.error_message,
                )
        except Exception as e:
            # Non-critical, continue anyway
            self._log(f"Could not check duplicates: {e}")

        return StateResult(success=True)

    def _handle_navigate(self) -> StateResult:
        """Navigate to the event creation page."""
        create_url = self.adapter.get_create_url()
        if not create_url:
            self.error_message = f"No create URL for {self.platform}"
            return StateResult(
                success=False,
                next_state=EventState.SKIPPED,
                error=self.error_message,
            )

        try:
            self.client.browser_navigate(create_url)
            time.sleep(0.5)  # Let page settle
            return StateResult(success=True)
        except Exception as e:
            return StateResult(success=False, error=f"Navigation failed: {e}")

    def _handle_auth_check(self) -> StateResult:
        """Check if we're logged in and on the form page."""
        try:
            data = self.client.browser_get_page()
            content = data.get("content", data.get("pageSnapshot", ""))
            url = data.get("url", "")

            # Auth takes priority - if auth prompts detected, user needs to log in
            # (even if some form elements are visible)
            if check_needs_auth(content):
                self.error_message = (
                    f"Login required for {self.platform.title()} - "
                    "please log in via browser and retry"
                )
                return StateResult(
                    success=False,
                    next_state=EventState.NEEDS_AUTH,
                    error=self.error_message,
                )

            if not self.adapter.is_form_page(content):
                return StateResult(
                    success=False,
                    error="Not on form page - may need navigation",
                )

            return StateResult(success=True)
        except Exception as e:
            return StateResult(success=False, error=f"Could not fetch page: {e}")

    def _handle_fill_field(self) -> StateResult:
        """Handle atomic field filling with verification."""
        prompt = self.adapter.get_prompt(self.state)
        if not prompt:
            return StateResult(success=True)

        try:
            self.client.browser_perform_task(prompt)

            # Post-step wait (platform-specific)
            wait_time = self.adapter.post_step_wait(self.state)
            time.sleep(wait_time)

            # Verify field was filled (best-effort)
            try:
                data = self.client.browser_get_page()
                content = data.get("content", data.get("pageSnapshot", ""))

                if self.state == EventState.FILL_TITLE:
                    title = self.adapter.event_data.title
                    if title.lower() not in content.lower():
                        self._log("Title not found in page after fill")
            except Exception as e:
                self._log(f"Could not verify field: {e}")

            return StateResult(success=True)
        except Exception as e:
            return StateResult(success=False, error=f"Field fill failed: {e}")

    def _handle_verify_form(self) -> StateResult:
        """Verify form is complete before submission."""
        prompt = self.adapter.get_prompt(EventState.VERIFY_FORM)
        if prompt:
            try:
                self.client.browser_perform_task(prompt)
                time.sleep(0.5)
            except Exception:
                pass  # Non-critical

        try:
            data = self.client.browser_get_page()
            content = data.get("content", data.get("pageSnapshot", ""))

            if check_validation_errors(content):
                return StateResult(success=False, error="Form has validation errors")

            return StateResult(success=True)
        except Exception as e:
            return StateResult(success=False, error=f"Could not verify form: {e}")

    def _handle_submit(self) -> StateResult:
        """Submit the form."""
        prompt = self.adapter.get_prompt(EventState.SUBMIT)

        try:
            self.client.browser_perform_task(prompt)
            # Give time for navigation/processing
            time.sleep(2.0)
            return StateResult(success=True)
        except Exception as e:
            return StateResult(success=False, error=f"Submit failed: {e}")

    def _handle_post_submit(self) -> StateResult:
        """Handle post-submit actions (like dismissing modals)."""
        action = self.adapter.post_submit_action()
        if action:
            try:
                self.client.browser_perform_task(action)
                time.sleep(1.0)
            except Exception:
                pass  # Non-critical

        return StateResult(success=True)

    def _handle_verify_success(self) -> StateResult:
        """Verify event was created using multiple signals."""
        try:
            data = self.client.browser_get_page()
            content = data.get("content", data.get("pageSnapshot", ""))
            url = data.get("url", "")

            # Collect signals
            signals = {
                "url_success": self.adapter.success_url_check(url),
                "edit_button": any(
                    kw in content.lower() for kw in ["edit", "manage", "settings"]
                ),
                "title_visible": self.adapter.event_data.title.lower() in content.lower(),
                "no_create_form": not self.adapter.is_form_page(content),
            }

            self.verification_signals = signals
            signal_count = sum(signals.values())

            self._log(f"Signals: {signals} (count: {signal_count})")

            # Decision logic:
            # - URL check is primary signal
            # - Need URL + 1 secondary, OR 3 secondary signals
            if signals["url_success"] and signal_count >= 2:
                self.event_url = url
                return StateResult(success=True, next_state=EventState.DONE)
            elif signal_count >= 3:
                self.event_url = url
                return StateResult(success=True, next_state=EventState.DONE)
            else:
                return StateResult(
                    success=False,
                    error=f"Only {signal_count} success signals",
                )
        except Exception as e:
            return StateResult(success=False, error=f"Could not verify success: {e}")

    def _build_result(self) -> MachineResult:
        """Build the final result."""
        status_map = {
            EventState.DONE: "PUBLISHED",
            EventState.FAILED: "FAILED",
            EventState.NEEDS_AUTH: "NEEDS_AUTH",
            EventState.DUPLICATE: "DUPLICATE",
            EventState.SKIPPED: "SKIPPED",
        }

        status = status_map.get(self.state, "NEEDS_REVIEW")

        return MachineResult(
            status=status,
            url=self.event_url,
            error=self.error_message,
            screenshot=self.screenshot_url,
            signals=self.verification_signals,
            final_state=self.state,
        )

    def _capture_screenshot(self, error_msg: str = "") -> str:
        """Capture screenshot on failure for debugging.

        Args:
            error_msg: Error message to log with screenshot

        Returns:
            Screenshot URL or empty string
        """
        try:
            data = self.client.execute_action(
                "BROWSER_TOOL_TAKE_SCREENSHOT",
                {},
                retry=False,
            )
            url = data.get("url", data.get("screenshotUrl", ""))
            self._log(f"Screenshot captured: {url}")
            if error_msg:
                self._log(f"Failure reason: {error_msg}")
            return url
        except Exception as e:
            self._log(f"Screenshot failed: {e}")
            return ""

    def _log(self, message: str) -> None:
        """Log a message with platform and state context.

        Args:
            message: Message to log
        """
        ts = datetime.utcnow().isoformat()
        state_name = self.state.value if isinstance(self.state, EventState) else self.state
        log_msg = f"[{ts}] [{self.platform.upper()}] [{state_name}] {message}"
        logger.info(log_msg)
        print(log_msg)  # Also print for visibility
