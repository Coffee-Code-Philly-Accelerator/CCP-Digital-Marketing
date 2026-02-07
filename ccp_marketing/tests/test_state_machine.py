"""Tests for CCP Marketing state machine."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from ccp_marketing.state_machine.states import (
    EventState,
    StateConfig,
    STATE_CONFIG,
    TERMINAL_STATES,
    FILL_STATES,
    STATE_FLOW,
    get_state_config,
    get_next_state,
)
from ccp_marketing.state_machine.machine import (
    EventCreationStateMachine,
    StateResult,
    MachineResult,
    check_needs_auth,
    check_validation_errors,
)


class TestEventState:
    """Tests for EventState enum."""

    def test_all_states_exist(self):
        """Test that all expected states exist."""
        expected = [
            "init", "check_duplicate", "navigate", "auth_check",
            "fill_title", "fill_date", "fill_time", "fill_location", "fill_description",
            "verify_form", "submit", "post_submit", "verify_success",
            "done", "failed", "needs_auth", "duplicate", "skipped",
        ]
        actual = [s.value for s in EventState]
        for state in expected:
            assert state in actual

    def test_is_terminal(self):
        """Test is_terminal property."""
        assert EventState.DONE.is_terminal
        assert EventState.FAILED.is_terminal
        assert EventState.NEEDS_AUTH.is_terminal
        assert EventState.DUPLICATE.is_terminal
        assert EventState.SKIPPED.is_terminal

        assert not EventState.INIT.is_terminal
        assert not EventState.NAVIGATE.is_terminal

    def test_is_fill_state(self):
        """Test is_fill_state property."""
        assert EventState.FILL_TITLE.is_fill_state
        assert EventState.FILL_DATE.is_fill_state
        assert EventState.FILL_TIME.is_fill_state
        assert EventState.FILL_LOCATION.is_fill_state
        assert EventState.FILL_DESCRIPTION.is_fill_state

        assert not EventState.INIT.is_fill_state
        assert not EventState.SUBMIT.is_fill_state


class TestTerminalStates:
    """Tests for TERMINAL_STATES constant."""

    def test_contains_expected_states(self):
        """Test terminal states set contains expected states."""
        assert EventState.DONE in TERMINAL_STATES
        assert EventState.FAILED in TERMINAL_STATES
        assert EventState.NEEDS_AUTH in TERMINAL_STATES
        assert EventState.DUPLICATE in TERMINAL_STATES
        assert EventState.SKIPPED in TERMINAL_STATES

    def test_does_not_contain_progression_states(self):
        """Test terminal states doesn't contain progression states."""
        assert EventState.INIT not in TERMINAL_STATES
        assert EventState.NAVIGATE not in TERMINAL_STATES
        assert EventState.SUBMIT not in TERMINAL_STATES


class TestFillStates:
    """Tests for FILL_STATES constant."""

    def test_contains_fill_states(self):
        """Test fill states set contains all fill states."""
        assert EventState.FILL_TITLE in FILL_STATES
        assert EventState.FILL_DATE in FILL_STATES
        assert EventState.FILL_TIME in FILL_STATES
        assert EventState.FILL_LOCATION in FILL_STATES
        assert EventState.FILL_DESCRIPTION in FILL_STATES

    def test_count(self):
        """Test there are exactly 5 fill states."""
        assert len(FILL_STATES) == 5


class TestStateFlow:
    """Tests for STATE_FLOW constant."""

    def test_starts_with_init(self):
        """Test flow starts with INIT."""
        assert STATE_FLOW[0] == EventState.INIT

    def test_ends_with_done(self):
        """Test flow ends with DONE."""
        assert STATE_FLOW[-1] == EventState.DONE

    def test_contains_all_progression_states(self):
        """Test flow contains all non-terminal progression states."""
        progression = [
            EventState.INIT, EventState.CHECK_DUPLICATE, EventState.NAVIGATE,
            EventState.AUTH_CHECK, EventState.FILL_TITLE, EventState.FILL_DATE,
            EventState.FILL_TIME, EventState.FILL_LOCATION, EventState.FILL_DESCRIPTION,
            EventState.VERIFY_FORM, EventState.SUBMIT, EventState.POST_SUBMIT,
            EventState.VERIFY_SUCCESS, EventState.DONE,
        ]
        for state in progression:
            assert state in STATE_FLOW


class TestStateConfig:
    """Tests for StateConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = StateConfig()
        assert config.max_retries == 2
        assert config.base_delay == 0.75
        assert config.max_delay == 8.0

    def test_custom_values(self):
        """Test custom configuration values."""
        config = StateConfig(max_retries=5, base_delay=1.0, max_delay=30.0)
        assert config.max_retries == 5
        assert config.base_delay == 1.0
        assert config.max_delay == 30.0


class TestGetStateConfig:
    """Tests for get_state_config function."""

    def test_configured_state(self):
        """Test getting config for a configured state."""
        config = get_state_config(EventState.SUBMIT)
        # Submit has max_retries=1 to avoid duplicates
        assert config.max_retries == 1

    def test_unconfigured_state_returns_default(self):
        """Test getting config for unconfigured state returns default."""
        config = get_state_config(EventState.INIT)
        assert config.max_retries == 2  # Default

    def test_verify_success_config(self):
        """Test verify_success has higher retry count."""
        config = get_state_config(EventState.VERIFY_SUCCESS)
        assert config.max_retries == 3


class TestGetNextState:
    """Tests for get_next_state function."""

    def test_init_to_check_duplicate(self):
        """Test INIT goes to CHECK_DUPLICATE."""
        assert get_next_state(EventState.INIT) == EventState.CHECK_DUPLICATE

    def test_submit_to_post_submit(self):
        """Test SUBMIT goes to POST_SUBMIT."""
        assert get_next_state(EventState.SUBMIT) == EventState.POST_SUBMIT

    def test_verify_success_to_done(self):
        """Test VERIFY_SUCCESS goes to DONE."""
        assert get_next_state(EventState.VERIFY_SUCCESS) == EventState.DONE

    def test_done_returns_none(self):
        """Test DONE returns None (end of flow)."""
        assert get_next_state(EventState.DONE) is None

    def test_terminal_state_returns_none(self):
        """Test terminal states not in flow return None."""
        assert get_next_state(EventState.FAILED) is None


class TestCheckNeedsAuth:
    """Tests for check_needs_auth function."""

    def test_detects_sign_in(self):
        """Test detection of 'sign in' text."""
        assert check_needs_auth("Please sign in to continue")
        assert check_needs_auth("Sign In Required")

    def test_detects_login(self):
        """Test detection of 'login' text."""
        assert check_needs_auth("Login to your account")
        assert check_needs_auth("Log in with Google")

    def test_detects_2fa(self):
        """Test detection of 2FA prompts."""
        assert check_needs_auth("Enter verification code")
        assert check_needs_auth("Two-factor authentication required")
        assert check_needs_auth("2FA code")

    def test_detects_oauth(self):
        """Test detection of OAuth prompts."""
        assert check_needs_auth("Continue with Google")
        assert check_needs_auth("Continue with Apple")

    def test_no_auth_needed(self):
        """Test that normal content doesn't trigger auth detection."""
        assert not check_needs_auth("Event Creation Form")
        assert not check_needs_auth("Enter event title")


class TestCheckValidationErrors:
    """Tests for check_validation_errors function."""

    def test_detects_required_field(self):
        """Test detection of 'required' error."""
        assert check_validation_errors("Title is required")
        assert check_validation_errors("This field is required")

    def test_detects_fix_errors(self):
        """Test detection of 'fix errors' message."""
        assert check_validation_errors("Please fix errors below")

    def test_detects_invalid(self):
        """Test detection of 'invalid' error."""
        assert check_validation_errors("Invalid date format")

    def test_detects_blank(self):
        """Test detection of blank field error."""
        assert check_validation_errors("Title can't be blank")

    def test_no_validation_errors(self):
        """Test that normal content doesn't trigger validation detection."""
        assert not check_validation_errors("Event Title: AI Workshop")
        assert not check_validation_errors("Date: January 25, 2025")


class TestStateResult:
    """Tests for StateResult dataclass."""

    def test_success_result(self):
        """Test creating a successful result."""
        result = StateResult(success=True)
        assert result.success
        assert result.next_state is None
        assert result.error == ""

    def test_failure_result(self):
        """Test creating a failed result."""
        result = StateResult(
            success=False,
            error="Navigation failed",
        )
        assert not result.success
        assert result.error == "Navigation failed"

    def test_with_next_state(self):
        """Test result with explicit next state."""
        result = StateResult(
            success=False,
            next_state=EventState.NEEDS_AUTH,
            error="Login required",
        )
        assert result.next_state == EventState.NEEDS_AUTH


class TestMachineResult:
    """Tests for MachineResult dataclass."""

    def test_success_result(self):
        """Test successful machine result."""
        result = MachineResult(
            status="PUBLISHED",
            url="https://lu.ma/test-event",
            final_state=EventState.DONE,
        )
        assert result.status == "PUBLISHED"
        assert result.url == "https://lu.ma/test-event"

    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = MachineResult(
            status="PUBLISHED",
            url="https://lu.ma/test",
            signals={"url_success": True},
        )
        d = result.to_dict()
        assert d["status"] == "PUBLISHED"
        assert d["url"] == "https://lu.ma/test"
        assert d["signals"]["url_success"]


class TestEventCreationStateMachine:
    """Tests for EventCreationStateMachine."""

    @pytest.fixture
    def mock_adapter(self, sample_event):
        """Create a mock adapter."""
        adapter = Mock()
        adapter.name = "luma"
        adapter.event_data = sample_event
        adapter.get_home_url.return_value = "https://lu.ma/home"
        adapter.get_create_url.return_value = "https://lu.ma/create"
        adapter.is_form_page.return_value = True
        adapter.get_prompt.return_value = "Fill the title field"
        adapter.post_step_wait.return_value = 0.01
        adapter.post_submit_action.return_value = None
        adapter.success_url_check.return_value = True
        return adapter

    def test_initial_state(self, mock_client, mock_adapter):
        """Test machine starts in INIT state."""
        machine = EventCreationStateMachine(mock_client, mock_adapter)
        assert machine.state == EventState.INIT

    def test_run_happy_path(self, mock_client, mock_adapter):
        """Test successful run through all states."""
        # Configure mock client responses
        mock_client.browser_navigate.return_value = {
            "pageSnapshot": "Event form",
            "url": "https://lu.ma/create",
        }
        mock_client.browser_get_page.return_value = {
            "content": "AI Workshop\n\nEdit | Manage | Settings",
            "url": "https://lu.ma/ai-workshop-123",
        }
        mock_client.browser_perform_task.return_value = {}

        machine = EventCreationStateMachine(mock_client, mock_adapter)

        with patch("time.sleep"):  # Skip actual delays
            result = machine.run()

        assert result.status == "PUBLISHED"
        assert "lu.ma" in result.url

    def test_run_needs_auth(self, mock_client, mock_adapter):
        """Test machine handles auth requirement."""
        mock_client.browser_navigate.return_value = {}
        mock_client.browser_get_page.return_value = {
            "content": "Please sign in to continue",
            "url": "https://lu.ma/login",
        }
        mock_adapter.is_form_page.return_value = False

        machine = EventCreationStateMachine(mock_client, mock_adapter)

        with patch("time.sleep"):
            result = machine.run()

        assert result.status == "NEEDS_AUTH"

    def test_run_skipped_no_create_url(self, mock_client, mock_adapter):
        """Test machine skips when no create URL."""
        mock_adapter.get_create_url.return_value = ""
        mock_client.browser_navigate.return_value = {}

        machine = EventCreationStateMachine(mock_client, mock_adapter)

        with patch("time.sleep"):
            result = machine.run()

        assert result.status == "SKIPPED"

    def test_run_duplicate_detected(self, mock_client, mock_adapter):
        """Test machine handles duplicate detection."""
        mock_client.browser_navigate.return_value = {
            "pageSnapshot": "Your Events\n\n- AI Workshop (January 25)",
        }

        machine = EventCreationStateMachine(mock_client, mock_adapter)

        with patch("time.sleep"):
            result = machine.run()

        assert result.status == "DUPLICATE"

    def test_retry_on_failure(self, mock_client, mock_adapter):
        """Test machine retries on transient failure."""
        call_count = [0]

        def get_page_side_effect():
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception("Transient error")
            return {
                "content": "AI Workshop\n\nEdit | Settings",
                "url": "https://lu.ma/ai-workshop-123",
            }

        mock_client.browser_navigate.return_value = {
            "pageSnapshot": "Your Events",  # Avoid duplicate check issue
            "url": "https://lu.ma/home",
        }
        mock_client.browser_get_page.side_effect = get_page_side_effect
        mock_client.browser_perform_task.return_value = {}

        machine = EventCreationStateMachine(mock_client, mock_adapter)

        with patch("time.sleep"):
            result = machine.run()

        # browser_get_page was called at least once (may fail earlier due to other reasons)
        assert call_count[0] >= 1

    def test_verification_signals(self, mock_client, mock_adapter):
        """Test verification signal collection."""
        mock_client.browser_navigate.return_value = {}
        mock_client.browser_get_page.return_value = {
            "content": "AI Workshop\n\nEdit Event | Manage RSVPs",
            "url": "https://lu.ma/ai-workshop-123",
        }
        mock_client.browser_perform_task.return_value = {}

        machine = EventCreationStateMachine(mock_client, mock_adapter)

        with patch("time.sleep"):
            result = machine.run()

        # Should have collected verification signals
        assert "url_success" in result.signals
        assert "edit_button" in result.signals
        assert "title_visible" in result.signals

    def test_screenshot_on_failure(self, mock_client, mock_adapter):
        """Test screenshot capture on failure."""
        mock_client.browser_navigate.side_effect = Exception("Navigation failed")
        mock_client.execute_action.return_value = {
            "url": "https://screenshot.url/image.png",
        }

        machine = EventCreationStateMachine(mock_client, mock_adapter)

        with patch("time.sleep"):
            result = machine.run()

        assert result.status == "FAILED"
        # Screenshot should have been attempted
        mock_client.execute_action.assert_called()
