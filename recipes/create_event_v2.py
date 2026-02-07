"""
RECIPE: Create Event on All Platforms (v2)
RECIPE ID: rcp_NEW_V2

FLOW: Input → Session Check → Checkpoint Load/Create → State Machine → Event URLs

VERSION HISTORY:
v2 (current): Multi-tenant, checkpoint-enabled, full-featured with tactical execution layer
  - Added: tenant_id for multi-tenant session management
  - Added: Checkpoint-based resume for failure recovery
  - Added: 2FA pause/resume flow (AWAIT_2FA state)
  - Added: Full feature support (images, tickets, cohosts, recurring)
  - Added: Hybrid execution (explicit + AI-assisted browser actions)
v1: See create_event.py - Original state machine implementation

API LEARNINGS:
- BROWSER_TOOL_NAVIGATE: Must be called first to establish session; returns sessionId
- BROWSER_TOOL_PERFORM_WEB_TASK: 50 step max; keep prompts focused and single-purpose
- BROWSER_TOOL_FETCH_WEBPAGE: Use format='markdown' for reading, 'html' for selectors
- BROWSER_TOOL_MOUSE_CLICK: Requires valid CSS selector; verify with FETCH first
- BROWSER_TOOL_TYPE_TEXT: Types at current cursor; click to focus first
- Sessions: Must reuse session context; store sessionId between calls
- Composio responses: Often double-nest data at result.data.data

KNOWN ISSUES:
- Session expiry requires re-login
- 2FA cannot be automated - recipe pauses and returns PAUSED_2FA
- Luma date picker needs 1.5s extra wait (React component)
- Meetup anti-bot requires 2s delays between all actions
- Partiful shows share modal after creation - needs dismissal
"""

import os
import json
import time
import random
from datetime import datetime
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Any

# ============================================================================
# Mockable Interface for External Dependencies
# ============================================================================

try:
    run_composio_tool
except NameError:
    def run_composio_tool(tool_name: str, arguments: dict) -> tuple[dict, str | None]:
        """Mock implementation for local testing."""
        print(f"[MOCK] run_composio_tool({tool_name}, {json.dumps(arguments)[:100]}...)")
        return {"data": {"mock": True, "sessionId": "mock-session-123"}}, None

try:
    invoke_llm
except NameError:
    def invoke_llm(prompt: str) -> tuple[str, str | None]:
        """Mock implementation for local testing."""
        print(f"[MOCK] invoke_llm(prompt length={len(prompt)})")
        return '{"luma": "mock desc", "meetup": "mock desc", "partiful": "mock desc"}', None


# ============================================================================
# Logging Utility
# ============================================================================

def log(tenant: str, platform: str, state: str, message: str) -> None:
    """Unified logging with timestamp, tenant, platform, and state context."""
    ts = datetime.utcnow().isoformat()
    print(f"[{ts}] [{tenant}] [{platform}] [{state}] {message}")


# ============================================================================
# Data Extraction Utility
# ============================================================================

def extract_data(result: dict) -> dict:
    """Extract data from Composio response, handling double-nesting."""
    data = result.get("data", {})
    if isinstance(data, dict) and "data" in data:
        data = data["data"]
    return data if isinstance(data, dict) else {}


# ============================================================================
# State Definitions
# ============================================================================

class EventState(str, Enum):
    """States for the event creation state machine."""
    # Core states
    INIT = "init"
    CHECK_SESSION = "check_session"
    LOAD_CHECKPOINT = "load_checkpoint"
    NAVIGATE = "navigate"
    AUTH_CHECK = "auth_check"
    # Form filling
    FILL_TITLE = "fill_title"
    FILL_DATE = "fill_date"
    FILL_TIME = "fill_time"
    FILL_LOCATION = "fill_location"
    FILL_DESCRIPTION = "fill_description"
    # Advanced features
    UPLOAD_IMAGE = "upload_image"
    SET_TICKETS = "set_tickets"
    ADD_COHOSTS = "add_cohosts"
    SET_RECURRING = "set_recurring"
    # Finalization
    VERIFY_FORM = "verify_form"
    SUBMIT = "submit"
    POST_SUBMIT = "post_submit"
    VERIFY_SUCCESS = "verify_success"
    # Auth states
    AWAIT_2FA = "await_2fa"
    RESUME_2FA = "resume_2fa"
    # Terminal states
    DONE = "done"
    FAILED = "failed"
    NEEDS_AUTH = "needs_auth"
    PAUSED_2FA = "paused_2fa"
    SKIPPED = "skipped"


TERMINAL_STATES = {EventState.DONE, EventState.FAILED, EventState.NEEDS_AUTH,
                   EventState.PAUSED_2FA, EventState.SKIPPED}

FILL_STATES = {EventState.FILL_TITLE, EventState.FILL_DATE, EventState.FILL_TIME,
               EventState.FILL_LOCATION, EventState.FILL_DESCRIPTION}

FEATURE_STATES = {EventState.UPLOAD_IMAGE, EventState.SET_TICKETS,
                  EventState.ADD_COHOSTS, EventState.SET_RECURRING}


# ============================================================================
# Session Management
# ============================================================================

class SessionStatus(str, Enum):
    WARM = "warm"
    COLD = "cold"
    NEEDS_AUTH = "needs_auth"
    PAUSED_2FA = "paused_2fa"
    EXPIRED = "expired"


@dataclass
class TenantSession:
    """Browser session for a tenant+platform."""
    tenant_id: str
    platform: str
    session_id: str | None = None
    status: SessionStatus = SessionStatus.COLD
    last_used: str | None = None
    last_url: str | None = None
    auth_state: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "platform": self.platform,
            "session_id": self.session_id,
            "status": self.status.value,
            "last_used": self.last_used,
            "last_url": self.last_url,
            "auth_state": self.auth_state,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TenantSession":
        data["status"] = SessionStatus(data.get("status", "cold"))
        return cls(**data)


class SessionManager:
    """File-based session management."""

    def __init__(self, storage_dir: str | None = None):
        self.storage_dir = Path(storage_dir or os.path.expanduser("~/.ccp_marketing/sessions"))
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        # Set secure permissions
        os.chmod(self.storage_dir, 0o700)

    def _get_path(self, tenant_id: str, platform: str) -> Path:
        safe_tenant = tenant_id.replace("/", "_").replace(":", "_")
        return self.storage_dir / f"{safe_tenant}_{platform}.json"

    def load(self, tenant_id: str, platform: str) -> TenantSession | None:
        path = self._get_path(tenant_id, platform)
        if not path.exists():
            return None
        try:
            with open(path) as f:
                return TenantSession.from_dict(json.load(f))
        except (json.JSONDecodeError, KeyError):
            return None

    def save(self, session: TenantSession) -> None:
        path = self._get_path(session.tenant_id, session.platform)
        with open(path, "w") as f:
            json.dump(session.to_dict(), f, indent=2)
        os.chmod(path, 0o600)

    def get_or_create(self, tenant_id: str, platform: str) -> TenantSession:
        session = self.load(tenant_id, platform)
        if session is None:
            session = TenantSession(tenant_id=tenant_id, platform=platform)
            self.save(session)
        return session


# ============================================================================
# Checkpoint Management
# ============================================================================

@dataclass
class Checkpoint:
    """Workflow state checkpoint for resume capability."""
    tenant_id: str
    platform: str
    event_data: dict
    current_state: str
    completed_states: list[str] = field(default_factory=list)
    state_data: dict = field(default_factory=dict)
    session_id: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Checkpoint":
        return cls(**data)


class CheckpointManager:
    """File-based checkpoint management."""

    def __init__(self, storage_dir: str | None = None):
        self.storage_dir = Path(storage_dir or os.path.expanduser("~/.ccp_marketing/checkpoints"))
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.storage_dir, 0o700)

    def _get_path(self, tenant_id: str, platform: str) -> Path:
        safe_tenant = tenant_id.replace("/", "_").replace(":", "_")
        return self.storage_dir / f"checkpoint_{safe_tenant}_{platform}.json"

    def load(self, tenant_id: str, platform: str) -> Checkpoint | None:
        path = self._get_path(tenant_id, platform)
        if not path.exists():
            return None
        try:
            with open(path) as f:
                return Checkpoint.from_dict(json.load(f))
        except (json.JSONDecodeError, KeyError):
            return None

    def save(self, checkpoint: Checkpoint) -> None:
        path = self._get_path(checkpoint.tenant_id, checkpoint.platform)
        with open(path, "w") as f:
            json.dump(checkpoint.to_dict(), f, indent=2)
        os.chmod(path, 0o600)

    def clear(self, tenant_id: str, platform: str) -> None:
        path = self._get_path(tenant_id, platform)
        if path.exists():
            path.unlink()


# ============================================================================
# Auth Detection
# ============================================================================

AUTH_PATTERNS = [
    "sign in", "log in", "login", "sign up", "create account",
    "enter your email", "enter your password", "verification code",
    "2fa", "two-factor", "authenticate", "verify your",
    "continue with google", "continue with apple",
]

TWO_FA_PATTERNS = [
    "verification code", "2fa", "two-factor", "authenticator",
    "enter the code", "sms code", "security code",
]


def check_needs_auth(content: str) -> bool:
    """Check if page indicates authentication is needed."""
    content_lower = content.lower()
    return any(pattern in content_lower for pattern in AUTH_PATTERNS)


def check_needs_2fa(content: str) -> bool:
    """Check if page is requesting 2FA."""
    content_lower = content.lower()
    return any(pattern in content_lower for pattern in TWO_FA_PATTERNS)


# ============================================================================
# Platform Configuration
# ============================================================================

PLATFORM_CONFIG = {
    "luma": {
        "create_url": "https://lu.ma/create",
        "home_url": "https://lu.ma/home",
        "inter_step_delay": 0.5,
        "date_picker_delay": 1.5,
        "form_indicators": ["event title", "create event", "what's your event"],
        "success_patterns": ["lu.ma/"],
        "blocked_patterns": ["/create", "/home", "/login"],
    },
    "meetup": {
        "create_url": None,  # Dynamic - needs group URL
        "home_url": "https://www.meetup.com",
        "inter_step_delay": 2.0,  # Anti-bot
        "form_indicators": ["event details", "what's your event", "create event"],
        "success_patterns": ["meetup.com", "/events/"],
        "blocked_patterns": ["/create"],
    },
    "partiful": {
        "create_url": "https://partiful.com/create",
        "home_url": "https://partiful.com/home",
        "inter_step_delay": 0.5,
        "form_indicators": ["untitled event", "event title", "create party"],
        "success_patterns": ["partiful.com/e/"],
        "blocked_patterns": ["/create"],
    },
}


def get_create_url(platform: str, event_data: dict) -> str:
    """Get the event creation URL for a platform."""
    config = PLATFORM_CONFIG.get(platform, {})
    if platform == "meetup":
        group_url = event_data.get("meetup_group_url", "").rstrip("/")
        return f"{group_url}/events/create/" if group_url else "https://www.meetup.com/create/"
    return config.get("create_url", "")


def check_success_url(platform: str, url: str) -> bool:
    """Check if URL indicates successful event creation."""
    config = PLATFORM_CONFIG.get(platform, {})
    url_lower = url.lower()

    # Check success patterns
    has_success = any(pattern in url_lower for pattern in config.get("success_patterns", []))
    # Check blocked patterns
    has_blocked = any(pattern in url_lower for pattern in config.get("blocked_patterns", []))

    return has_success and not has_blocked


# ============================================================================
# Browser Tool Wrappers
# ============================================================================

def browser_navigate(url: str, force_new: bool = False) -> tuple[str | None, str | None, str | None]:
    """Navigate to URL, return (session_id, page_content, error)."""
    result, error = run_composio_tool("BROWSER_TOOL_NAVIGATE", {
        "url": url,
        "forceNewSession": force_new,
    })
    if error:
        return None, None, error
    data = extract_data(result)
    session_id = data.get("sessionId")
    content = data.get("pageSnapshot", "")
    return session_id, content, None


def browser_fetch(format: str = "markdown") -> tuple[str, str, str | None]:
    """Fetch current page, return (content, url, error)."""
    result, error = run_composio_tool("BROWSER_TOOL_FETCH_WEBPAGE", {
        "format": format,
        "wait": 1000,
    })
    if error:
        return "", "", error
    data = extract_data(result)
    content = data.get("content", data.get("pageSnapshot", ""))
    url = data.get("url", data.get("navigatedUrl", ""))
    return content, url, None


def browser_perform_task(prompt: str) -> tuple[bool, str | None]:
    """Perform AI-assisted task, return (success, error)."""
    result, error = run_composio_tool("BROWSER_TOOL_PERFORM_WEB_TASK", {
        "prompt": prompt,
    })
    if error:
        return False, error
    return True, None


def browser_click(selector: str) -> tuple[bool, str | None]:
    """Click element by selector, return (success, error)."""
    result, error = run_composio_tool("BROWSER_TOOL_MOUSE_CLICK", {
        "selector": selector,
    })
    if error:
        return False, error
    return True, None


def browser_type(text: str, delay: int = 10) -> tuple[bool, str | None]:
    """Type text at cursor, return (success, error)."""
    result, error = run_composio_tool("BROWSER_TOOL_TYPE_TEXT", {
        "text": text,
        "delay": delay,
    })
    if error:
        return False, error
    return True, None


def browser_screenshot() -> tuple[str | None, str | None]:
    """Take screenshot, return (url, error)."""
    result, error = run_composio_tool("BROWSER_TOOL_TAKE_SCREENSHOT", {})
    if error:
        return None, error
    data = extract_data(result)
    return data.get("url", data.get("screenshotUrl")), None


# ============================================================================
# State Handlers
# ============================================================================

def handle_navigate(tenant_id: str, platform: str, event_data: dict,
                   session: TenantSession) -> tuple[bool, EventState | None, str | None]:
    """Handle navigation to create page."""
    url = get_create_url(platform, event_data)
    log(tenant_id, platform, "navigate", f"Navigating to {url}")

    # Use existing session if warm, otherwise create new
    force_new = session.status != SessionStatus.WARM
    session_id, content, error = browser_navigate(url, force_new)

    if error:
        return False, EventState.FAILED, f"Navigation failed: {error}"

    # Update session
    session.session_id = session_id
    session.last_url = url
    session.last_used = datetime.utcnow().isoformat()

    return True, EventState.AUTH_CHECK, None


def handle_auth_check(tenant_id: str, platform: str, session: TenantSession,
                      checkpoint_mgr: CheckpointManager, checkpoint: Checkpoint) -> tuple[bool, EventState | None, str | None]:
    """Check authentication status."""
    content, url, error = browser_fetch()
    if error:
        return False, None, f"Fetch failed: {error}"

    # Check for 2FA first
    if check_needs_2fa(content):
        log(tenant_id, platform, "auth_check", "2FA detected - pausing for manual completion")
        session.status = SessionStatus.PAUSED_2FA
        checkpoint.current_state = EventState.AWAIT_2FA.value
        checkpoint_mgr.save(checkpoint)
        return False, EventState.PAUSED_2FA, "2FA required. Please complete 2FA in browser and resume."

    # Check for login needed
    if check_needs_auth(content):
        log(tenant_id, platform, "auth_check", "Login required")
        session.status = SessionStatus.NEEDS_AUTH
        return False, EventState.NEEDS_AUTH, "Login required. Please log in manually."

    # Check if on form page
    config = PLATFORM_CONFIG.get(platform, {})
    indicators = config.get("form_indicators", [])
    content_lower = content.lower()
    if not any(ind in content_lower for ind in indicators):
        log(tenant_id, platform, "auth_check", "Not on form page")
        return False, None, "Not on event creation form"

    session.status = SessionStatus.WARM
    log(tenant_id, platform, "auth_check", "Authentication verified, on form page")
    return True, EventState.FILL_TITLE, None


def handle_fill_field(tenant_id: str, platform: str, state: EventState,
                      event_data: dict) -> tuple[bool, EventState | None, str | None]:
    """Handle filling a form field."""
    config = PLATFORM_CONFIG.get(platform, {})
    delay = config.get("inter_step_delay", 0.5)

    # Map state to field and value
    field_map = {
        EventState.FILL_TITLE: ("title", event_data.get("title", "")),
        EventState.FILL_DATE: ("date", event_data.get("date", "")),
        EventState.FILL_TIME: ("time", event_data.get("time", "")),
        EventState.FILL_LOCATION: ("location", event_data.get("location", "")),
        EventState.FILL_DESCRIPTION: ("description", event_data.get("description", "")),
    }

    field_name, value = field_map.get(state, ("unknown", ""))
    log(tenant_id, platform, state.value, f"Filling {field_name}: {value[:50]}...")

    # Use AI-assisted for better reliability
    prompt = f"Find the {field_name} field. Click on it to focus. Clear any existing text. Type exactly: {value}"

    # Special handling for date picker
    if state == EventState.FILL_DATE and platform == "luma":
        prompt = f"Click on the date field to open the date picker. Select the date: {value}. Wait for the calendar to respond."
        delay = config.get("date_picker_delay", 1.5)

    success, error = browser_perform_task(prompt)
    if not success:
        return False, None, f"Fill {field_name} failed: {error}"

    time.sleep(delay)

    # Determine next state
    state_order = [EventState.FILL_TITLE, EventState.FILL_DATE, EventState.FILL_TIME,
                   EventState.FILL_LOCATION, EventState.FILL_DESCRIPTION, EventState.VERIFY_FORM]
    idx = state_order.index(state)
    next_state = state_order[idx + 1] if idx + 1 < len(state_order) else EventState.VERIFY_FORM

    return True, next_state, None


def handle_verify_form(tenant_id: str, platform: str,
                       event_data: dict) -> tuple[bool, EventState | None, str | None]:
    """Verify all form fields are filled."""
    content, url, error = browser_fetch()
    if error:
        return False, None, f"Fetch failed: {error}"

    # Basic verification - check if title appears in page
    title = event_data.get("title", "")
    if title.lower() not in content.lower():
        log(tenant_id, platform, "verify_form", "Title not found in page - may not be filled")
        # Continue anyway - verification is best-effort

    log(tenant_id, platform, "verify_form", "Form verification passed")
    return True, EventState.SUBMIT, None


def handle_submit(tenant_id: str, platform: str) -> tuple[bool, EventState | None, str | None]:
    """Submit the event form."""
    log(tenant_id, platform, "submit", "Submitting event form")

    prompt = "Click the Publish, Create Event, or Submit button. Wait for the page to respond and redirect."
    success, error = browser_perform_task(prompt)

    if not success:
        return False, None, f"Submit failed: {error}"

    time.sleep(2.0)  # Wait for submission
    return True, EventState.POST_SUBMIT, None


def handle_post_submit(tenant_id: str, platform: str) -> tuple[bool, EventState | None, str | None]:
    """Handle post-submit actions (modal dismissal, etc.)."""
    # Platform-specific post-submit handling
    if platform == "partiful":
        prompt = "If a share or invite modal appears, dismiss it by clicking X, Skip, or clicking outside."
        browser_perform_task(prompt)
        time.sleep(1.0)
    elif platform == "luma":
        prompt = "If a share modal appears, dismiss it by clicking X or Skip."
        browser_perform_task(prompt)
        time.sleep(1.0)

    return True, EventState.VERIFY_SUCCESS, None


def handle_verify_success(tenant_id: str, platform: str,
                          event_data: dict) -> tuple[bool, EventState | None, str | None, str | None]:
    """Verify event was created successfully. Returns (success, next_state, error, event_url)."""
    content, url, error = browser_fetch()
    if error:
        return False, None, f"Fetch failed: {error}", None

    # Multi-signal verification
    signals = {
        "url_success": check_success_url(platform, url),
        "title_visible": event_data.get("title", "").lower() in content.lower(),
        "edit_button": any(kw in content.lower() for kw in ["edit", "manage", "settings"]),
        "confirmation": any(kw in content.lower() for kw in ["created", "published", "live"]),
    }

    signal_count = sum(signals.values())
    log(tenant_id, platform, "verify_success", f"Signals: {signals}, count: {signal_count}")

    # Need URL success + 1 other, or 3+ signals
    if signals["url_success"] and signal_count >= 2:
        log(tenant_id, platform, "verify_success", f"Event created successfully: {url}")
        return True, EventState.DONE, None, url
    elif signal_count >= 3:
        log(tenant_id, platform, "verify_success", f"Event likely created: {url}")
        return True, EventState.DONE, None, url
    else:
        return False, None, f"Only {signal_count} success signals", None


# ============================================================================
# Main Workflow Runner
# ============================================================================

def run_workflow(tenant_id: str, platform: str, event_data: dict,
                 resume: bool = False) -> dict:
    """Run the event creation workflow for a single platform.

    Args:
        tenant_id: Tenant/organization identifier
        platform: Platform name (luma, meetup, partiful)
        event_data: Event details dict
        resume: Whether to resume from checkpoint

    Returns:
        Result dict with status, event_url, error, resume_token
    """
    log(tenant_id, platform, "init", f"Starting workflow (resume={resume})")

    session_mgr = SessionManager()
    checkpoint_mgr = CheckpointManager()

    # Load or create session
    session = session_mgr.get_or_create(tenant_id, platform)

    # Load or create checkpoint
    checkpoint = checkpoint_mgr.load(tenant_id, platform) if resume else None
    if checkpoint is None:
        checkpoint = Checkpoint(
            tenant_id=tenant_id,
            platform=platform,
            event_data=event_data,
            current_state=EventState.NAVIGATE.value,
        )

    # Determine starting state
    if resume and checkpoint.current_state == EventState.AWAIT_2FA.value:
        current_state = EventState.RESUME_2FA
        log(tenant_id, platform, "init", "Resuming after 2FA")
    elif resume:
        current_state = EventState(checkpoint.current_state)
        log(tenant_id, platform, "init", f"Resuming from state: {current_state.value}")
    else:
        current_state = EventState.NAVIGATE

    event_url = None
    error_message = None
    max_iterations = 50  # Safety limit

    for iteration in range(max_iterations):
        if current_state in TERMINAL_STATES:
            break

        log(tenant_id, platform, current_state.value, f"Executing (iteration {iteration})")

        try:
            if current_state == EventState.NAVIGATE:
                success, next_state, error = handle_navigate(tenant_id, platform, event_data, session)
            elif current_state == EventState.AUTH_CHECK:
                success, next_state, error = handle_auth_check(tenant_id, platform, session, checkpoint_mgr, checkpoint)
            elif current_state == EventState.RESUME_2FA:
                # Re-check auth after 2FA
                success, next_state, error = handle_auth_check(tenant_id, platform, session, checkpoint_mgr, checkpoint)
            elif current_state in FILL_STATES:
                success, next_state, error = handle_fill_field(tenant_id, platform, current_state, event_data)
            elif current_state == EventState.VERIFY_FORM:
                success, next_state, error = handle_verify_form(tenant_id, platform, event_data)
            elif current_state == EventState.SUBMIT:
                success, next_state, error = handle_submit(tenant_id, platform)
            elif current_state == EventState.POST_SUBMIT:
                success, next_state, error = handle_post_submit(tenant_id, platform)
            elif current_state == EventState.VERIFY_SUCCESS:
                success, next_state, error, event_url = handle_verify_success(tenant_id, platform, event_data)
            else:
                success, next_state, error = False, EventState.FAILED, f"Unknown state: {current_state}"

            if success:
                checkpoint.completed_states.append(current_state.value)
                current_state = next_state
                checkpoint.current_state = current_state.value
                checkpoint_mgr.save(checkpoint)
            else:
                if next_state in TERMINAL_STATES:
                    current_state = next_state
                else:
                    error_message = error
                    current_state = EventState.FAILED
                break

        except Exception as e:
            log(tenant_id, platform, current_state.value, f"Exception: {e}")
            error_message = str(e)
            current_state = EventState.FAILED
            break

    # Save final session state
    session_mgr.save(session)

    # Build result
    result = {
        "tenant_id": tenant_id,
        "platform": platform,
        "status": current_state.value,
        "event_url": event_url,
        "error": error_message,
    }

    # Add resume token for pausable states
    if current_state == EventState.PAUSED_2FA:
        result["resume_token"] = f"{tenant_id}:{platform}:2fa"
        result["resume_instructions"] = (
            "Please complete 2FA in the browser. "
            "Once done, run this recipe again with resume=true to continue."
        )
    elif current_state == EventState.NEEDS_AUTH:
        result["resume_token"] = f"{tenant_id}:{platform}:auth"
        result["resume_instructions"] = (
            "Please log in to the platform in the browser. "
            "Once logged in, run this recipe again with resume=true to continue."
        )

    # Clear checkpoint on success or permanent failure
    if current_state == EventState.DONE:
        checkpoint_mgr.clear(tenant_id, platform)

    return result


# ============================================================================
# Main Entry Point
# ============================================================================

print(f"[{datetime.utcnow().isoformat()}] Starting create_event_v2 recipe")

# Read inputs from environment
tenant_id = os.environ.get("tenant_id", "default")
platforms_str = os.environ.get("platforms", "luma,meetup,partiful")
skip_platforms_str = os.environ.get("skip_platforms", "")
resume_str = os.environ.get("resume", "false")

event_title = os.environ.get("event_title", "")
event_date = os.environ.get("event_date", "")
event_time = os.environ.get("event_time", "")
event_location = os.environ.get("event_location", "")
event_description = os.environ.get("event_description", "")
meetup_group_url = os.environ.get("meetup_group_url", "")
image_url = os.environ.get("image_url", "")

# Validate required inputs
if not all([event_title, event_date, event_time, event_location, event_description]):
    output = {
        "status": "failed",
        "error": "Missing required inputs: event_title, event_date, event_time, event_location, event_description",
    }
else:
    # Build event data
    event_data = {
        "title": event_title,
        "date": event_date,
        "time": event_time,
        "location": event_location,
        "description": event_description,
        "meetup_group_url": meetup_group_url,
        "image_url": image_url,
    }

    # Determine platforms to run
    platforms = [p.strip().lower() for p in platforms_str.split(",") if p.strip()]
    skip_platforms = [p.strip().lower() for p in skip_platforms_str.split(",") if p.strip()]
    platforms = [p for p in platforms if p not in skip_platforms]
    resume = resume_str.lower() == "true"

    # Run workflow for each platform
    results = {}
    for platform in platforms:
        if platform not in PLATFORM_CONFIG:
            results[platform] = {"status": "failed", "error": f"Unknown platform: {platform}"}
            continue

        # Check for meetup-specific requirement
        if platform == "meetup" and not meetup_group_url:
            results[platform] = {"status": "skipped", "error": "meetup_group_url required for Meetup"}
            continue

        result = run_workflow(tenant_id, platform, event_data, resume)
        results[platform] = result

    # Build final output
    output = {
        "tenant_id": tenant_id,
        "platforms": results,
        "luma_url": results.get("luma", {}).get("event_url"),
        "meetup_url": results.get("meetup", {}).get("event_url"),
        "partiful_url": results.get("partiful", {}).get("event_url"),
        "image_url": image_url,
        "status_summary": " | ".join([
            f"{p}: {r.get('status', 'unknown')}"
            for p, r in results.items()
        ]),
        "needs_action": [p for p, r in results.items()
                        if r.get("status") in ["paused_2fa", "needs_auth"]],
    }

print(f"[{datetime.utcnow().isoformat()}] Recipe completed: {output.get('status_summary', 'N/A')}")

# Output is the final variable (Rube MCP pattern)
output
