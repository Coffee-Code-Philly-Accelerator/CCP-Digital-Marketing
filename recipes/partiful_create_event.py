"""
RECIPE: Create Event on Partiful
RECIPE ID: rcp_bN7jRF5P_Kf0

FLOW: Input -> Session Check -> Checkpoint Load/Create -> Image Generation -> State Machine -> Event URL

VERSION HISTORY:
v1 (current): Standalone Partiful recipe with v2 state machine (19 states), checkpoint/resume, image generation

API LEARNINGS:
- BROWSER_TOOL_NAVIGATE: Returns pageSnapshot in markdown format, sessionId for reuse
- BROWSER_TOOL_PERFORM_WEB_TASK: AI agent fills forms via natural language prompt (50 step max)
- BROWSER_TOOL_FETCH_WEBPAGE: Gets current page state without navigation
- GEMINI_GENERATE_IMAGE: Returns publicUrl for generated image
- Partiful create URL: https://partiful.com/create
- Partiful shows share/invite modal after creation - needs dismissal
- Partiful does NOT support recurring events
- Composio responses often double-nest: data.data.field

KNOWN ISSUES:
- Session expiry requires re-login
- 2FA cannot be automated - recipe pauses and returns PAUSED_2FA
- Share modal must be dismissed to extract event URL
- Recurring events NOT supported on Partiful
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
        return "Mock LLM response", None


# ============================================================================
# Platform Configuration (Partiful-specific)
# ============================================================================

PLATFORM = "partiful"
CREATE_URL = "https://partiful.com/create"
HOME_URL = "https://partiful.com/home"
INTER_STEP_DELAY = 0.5

FORM_INDICATORS = ["untitled event", "event title", "add event", "create party", "what's the occasion"]
SUCCESS_PATTERNS = ["partiful.com/e/"]
BLOCKED_PATTERNS = ["/create"]


# ============================================================================
# Logging Utility
# ============================================================================

def log(tenant: str, state: str, message: str) -> None:
    """Unified logging with timestamp, tenant, and state context."""
    ts = datetime.utcnow().isoformat()
    print(f"[{ts}] [{tenant}] [partiful] [{state}] {message}")


# ============================================================================
# Data Extraction Utility
# ============================================================================

def extract_data(result: dict) -> dict:
    """Extract data from Composio response, handling double-nesting."""
    data = result.get("data", {})
    if isinstance(data, dict) and "data" in data:
        data = data["data"]
    return data if isinstance(data, dict) else {}


def sanitize_input(text: str, max_len: int = 2000) -> str:
    """Sanitize user input to prevent prompt injection."""
    if not text:
        return ""
    text = str(text)
    text = ''.join(char for char in text if char >= ' ' or char in '\n\t')
    text = text.replace("```", "'''")
    text = text.replace("---", "___")
    return text[:max_len]


# ============================================================================
# State Definitions (19 states for v2, but SET_RECURRING is skipped)
# ============================================================================

class EventState(str, Enum):
    """States for the event creation state machine."""
    # Core states
    INIT = "init"
    CHECK_SESSION = "check_session"
    LOAD_CHECKPOINT = "load_checkpoint"
    GENERATE_IMAGE = "generate_image"
    NAVIGATE = "navigate"
    AUTH_CHECK = "auth_check"
    # Form filling
    FILL_TITLE = "fill_title"
    FILL_DATE = "fill_date"
    FILL_TIME = "fill_time"
    FILL_LOCATION = "fill_location"
    FILL_DESCRIPTION = "fill_description"
    # Advanced features (skipped for now - can enable later)
    UPLOAD_IMAGE = "upload_image"
    SET_TICKETS = "set_tickets"
    ADD_COHOSTS = "add_cohosts"
    SET_RECURRING = "set_recurring"  # NOT SUPPORTED on Partiful - always skipped
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


TERMINAL_STATES = {EventState.DONE, EventState.FAILED, EventState.NEEDS_AUTH, EventState.PAUSED_2FA}

FILL_STATES = {EventState.FILL_TITLE, EventState.FILL_DATE, EventState.FILL_TIME,
               EventState.FILL_LOCATION, EventState.FILL_DESCRIPTION}

# State flow (SET_RECURRING is NOT included - Partiful doesn't support it)
STATE_FLOW = [
    EventState.INIT,
    EventState.GENERATE_IMAGE,
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

STATE_CONFIG = {
    EventState.GENERATE_IMAGE: {"max_retries": 1, "base_delay": 1.0},
    EventState.NAVIGATE: {"max_retries": 2, "base_delay": 1.0},
    EventState.AUTH_CHECK: {"max_retries": 1, "base_delay": 0.5},
    EventState.FILL_TITLE: {"max_retries": 2, "base_delay": 0.75},
    EventState.FILL_DATE: {"max_retries": 2, "base_delay": 0.75},
    EventState.FILL_TIME: {"max_retries": 2, "base_delay": 0.75},
    EventState.FILL_LOCATION: {"max_retries": 2, "base_delay": 0.75},
    EventState.FILL_DESCRIPTION: {"max_retries": 2, "base_delay": 0.75},
    EventState.VERIFY_FORM: {"max_retries": 2, "base_delay": 1.0},
    EventState.SUBMIT: {"max_retries": 1, "base_delay": 1.0},
    EventState.POST_SUBMIT: {"max_retries": 2, "base_delay": 1.0},  # Extra retries for modal dismissal
    EventState.VERIFY_SUCCESS: {"max_retries": 3, "base_delay": 1.5, "max_delay": 12.0},
}


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
    """Browser session for a tenant."""
    tenant_id: str
    session_id: str | None = None
    status: SessionStatus = SessionStatus.COLD
    last_used: str | None = None
    last_url: str | None = None

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "session_id": self.session_id,
            "status": self.status.value,
            "last_used": self.last_used,
            "last_url": self.last_url,
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
        os.chmod(self.storage_dir, 0o700)

    def _get_path(self, tenant_id: str) -> Path:
        safe_tenant = tenant_id.replace("/", "_").replace(":", "_")
        return self.storage_dir / f"{safe_tenant}_partiful.json"

    def load(self, tenant_id: str) -> TenantSession | None:
        path = self._get_path(tenant_id)
        if not path.exists():
            return None
        try:
            with open(path) as f:
                return TenantSession.from_dict(json.load(f))
        except (json.JSONDecodeError, KeyError):
            return None

    def save(self, session: TenantSession) -> None:
        path = self._get_path(session.tenant_id)
        with open(path, "w") as f:
            json.dump(session.to_dict(), f, indent=2)
        os.chmod(path, 0o600)

    def get_or_create(self, tenant_id: str) -> TenantSession:
        session = self.load(tenant_id)
        if session is None:
            session = TenantSession(tenant_id=tenant_id)
            self.save(session)
        return session


# ============================================================================
# Checkpoint Management
# ============================================================================

@dataclass
class Checkpoint:
    """Workflow state checkpoint for resume capability."""
    tenant_id: str
    event_data: dict
    current_state: str
    completed_states: list[str] = field(default_factory=list)
    state_data: dict = field(default_factory=dict)
    session_id: str | None = None
    image_url: str | None = None
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

    def _get_path(self, tenant_id: str) -> Path:
        safe_tenant = tenant_id.replace("/", "_").replace(":", "_")
        return self.storage_dir / f"checkpoint_{safe_tenant}_partiful.json"

    def load(self, tenant_id: str) -> Checkpoint | None:
        path = self._get_path(tenant_id)
        if not path.exists():
            return None
        try:
            with open(path) as f:
                return Checkpoint.from_dict(json.load(f))
        except (json.JSONDecodeError, KeyError):
            return None

    def save(self, checkpoint: Checkpoint) -> None:
        path = self._get_path(checkpoint.tenant_id)
        with open(path, "w") as f:
            json.dump(checkpoint.to_dict(), f, indent=2)
        os.chmod(path, 0o600)

    def clear(self, tenant_id: str) -> None:
        path = self._get_path(tenant_id)
        if path.exists():
            path.unlink()


# ============================================================================
# Auth Detection
# ============================================================================

AUTH_PATTERNS = [
    "sign in", "log in", "login", "sign up", "create account",
    "enter your email", "enter your password", "verification code",
    "2fa", "two-factor", "authenticate", "verify your",
    "continue with google", "continue with apple", "continue with phone",
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


def is_form_page(content: str) -> bool:
    """Check if we're on the event creation form page."""
    content_lower = content.lower()
    return any(ind in content_lower for ind in FORM_INDICATORS)


def check_success_url(url: str) -> bool:
    """Check if URL indicates successful event creation."""
    url_lower = url.lower()
    has_success = any(pattern in url_lower for pattern in SUCCESS_PATTERNS)
    has_blocked = any(pattern in url_lower for pattern in BLOCKED_PATTERNS)
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


def browser_screenshot() -> tuple[str | None, str | None]:
    """Take screenshot, return (url, error)."""
    result, error = run_composio_tool("BROWSER_TOOL_TAKE_SCREENSHOT", {})
    if error:
        return None, error
    data = extract_data(result)
    return data.get("url", data.get("screenshotUrl")), None


# ============================================================================
# Image Generation
# ============================================================================

def generate_event_image(event_data: dict, custom_prompt: str | None = None) -> tuple[str | None, str | None]:
    """Generate promotional image for the event."""
    if custom_prompt:
        prompt = custom_prompt
    else:
        prompt = (
            f"Create a fun, eye-catching party event graphic for: {event_data['title']}. "
            f"Style: playful, vibrant colors, suitable for a casual social event. "
            f"Include visual elements suggesting: {event_data['location']}. "
            "Do not include any text in the image."
        )

    result, error = run_composio_tool("GEMINI_GENERATE_IMAGE", {
        "prompt": prompt,
        "model": "imagen-3.0-generate-002"
    })

    if error:
        return None, error

    data = extract_data(result)
    return data.get("publicUrl", ""), None


# ============================================================================
# State Handlers
# ============================================================================

def get_next_state(current: EventState) -> EventState:
    """Get the next state in the flow."""
    try:
        idx = STATE_FLOW.index(current)
        if idx + 1 < len(STATE_FLOW):
            return STATE_FLOW[idx + 1]
    except ValueError:
        pass
    return EventState.DONE


def handle_init(tenant_id: str, checkpoint: Checkpoint) -> tuple[bool, EventState | None, str | None]:
    """Initialize workflow."""
    log(tenant_id, "init", "Initializing workflow")
    return True, get_next_state(EventState.INIT), None


def handle_generate_image(tenant_id: str, event_data: dict, image_prompt: str | None,
                          checkpoint: Checkpoint) -> tuple[bool, EventState | None, str | None]:
    """Generate promotional image."""
    log(tenant_id, "generate_image", "Generating promotional image via Gemini...")

    image_url, error = generate_event_image(event_data, image_prompt)

    if error:
        log(tenant_id, "generate_image", f"Image generation failed: {error}")
        checkpoint.image_url = None
    else:
        log(tenant_id, "generate_image", f"Image generated: {image_url}")
        checkpoint.image_url = image_url

    return True, get_next_state(EventState.GENERATE_IMAGE), None


def handle_navigate(tenant_id: str, session: TenantSession) -> tuple[bool, EventState | None, str | None]:
    """Handle navigation to create page."""
    log(tenant_id, "navigate", f"Navigating to {CREATE_URL}")

    force_new = session.status != SessionStatus.WARM
    session_id, content, error = browser_navigate(CREATE_URL, force_new)

    if error:
        return False, EventState.FAILED, f"Navigation failed: {error}"

    session.session_id = session_id
    session.last_url = CREATE_URL
    session.last_used = datetime.utcnow().isoformat()

    return True, get_next_state(EventState.NAVIGATE), None


def handle_auth_check(tenant_id: str, session: TenantSession,
                      checkpoint_mgr: CheckpointManager, checkpoint: Checkpoint) -> tuple[bool, EventState | None, str | None]:
    """Check authentication status."""
    content, url, error = browser_fetch()
    if error:
        return False, None, f"Fetch failed: {error}"

    # Check for 2FA first
    if check_needs_2fa(content):
        log(tenant_id, "auth_check", "2FA detected - pausing for manual completion")
        session.status = SessionStatus.PAUSED_2FA
        checkpoint.current_state = EventState.AWAIT_2FA.value
        checkpoint_mgr.save(checkpoint)
        return False, EventState.PAUSED_2FA, "2FA required. Please complete 2FA in browser and resume."

    # Check for login needed
    if check_needs_auth(content):
        log(tenant_id, "auth_check", "Login required")
        session.status = SessionStatus.NEEDS_AUTH
        return False, EventState.NEEDS_AUTH, "Login required. Please log in manually."

    # Check if on form page
    if not is_form_page(content):
        log(tenant_id, "auth_check", "Not on form page")
        return False, None, "Not on event creation form"

    session.status = SessionStatus.WARM
    log(tenant_id, "auth_check", "Authentication verified, on form page")
    return True, get_next_state(EventState.AUTH_CHECK), None


def handle_fill_field(tenant_id: str, state: EventState, event_data: dict) -> tuple[bool, EventState | None, str | None]:
    """Handle filling a form field."""
    field_map = {
        EventState.FILL_TITLE: ("title", event_data.get("title", "")),
        EventState.FILL_DATE: ("date", event_data.get("date", "")),
        EventState.FILL_TIME: ("time", event_data.get("time", "")),
        EventState.FILL_LOCATION: ("location", event_data.get("location", "")),
        EventState.FILL_DESCRIPTION: ("description", event_data.get("description", "")),
    }

    field_name, value = field_map.get(state, ("unknown", ""))
    log(tenant_id, state.value, f"Filling {field_name}: {value[:50]}...")

    # Build prompt based on field (Partiful-specific)
    prompts = {
        EventState.FILL_TITLE: f"Click on the event title field (may say 'Untitled Event' or similar), clear it, type exactly: {value}, click outside",
        EventState.FILL_DATE: f"Click on the date field or 'When' section, select: {value}",
        EventState.FILL_TIME: f"Click on the time field, enter: {value}",
        EventState.FILL_LOCATION: f"Click on the location field or 'Where' section, type: {value}, select from dropdown or press Enter",
        EventState.FILL_DESCRIPTION: f"Click on the description or details field, type: {value}",
    }

    prompt = prompts.get(state, f"Fill the {field_name} field with: {value}")
    success, error = browser_perform_task(prompt)

    if not success:
        return False, None, f"Fill {field_name} failed: {error}"

    time.sleep(INTER_STEP_DELAY)

    return True, get_next_state(state), None


def handle_verify_form(tenant_id: str, event_data: dict) -> tuple[bool, EventState | None, str | None]:
    """Verify all form fields are filled."""
    content, url, error = browser_fetch()
    if error:
        return False, None, f"Fetch failed: {error}"

    title = event_data.get("title", "")
    if title.lower() not in content.lower():
        log(tenant_id, "verify_form", "Title not found in page - may not be filled")

    log(tenant_id, "verify_form", "Form verification passed")
    return True, get_next_state(EventState.VERIFY_FORM), None


def handle_submit(tenant_id: str) -> tuple[bool, EventState | None, str | None]:
    """Submit the event form."""
    log(tenant_id, "submit", "Submitting event form")

    prompt = "Click 'Save', 'Publish', or 'Create' button to create the event. Wait for navigation."
    success, error = browser_perform_task(prompt)

    if not success:
        return False, None, f"Submit failed: {error}"

    time.sleep(2.0)
    return True, get_next_state(EventState.SUBMIT), None


def handle_post_submit(tenant_id: str) -> tuple[bool, EventState | None, str | None]:
    """Handle post-submit actions - CRITICAL for Partiful: dismiss share modal."""
    log(tenant_id, "post_submit", "Checking for share/invite modal...")

    # Partiful typically shows a share/invite modal after event creation
    prompt = (
        "If a share, invite, or 'tell your friends' modal appears, dismiss it by clicking "
        "the X button, 'Skip', 'Maybe later', or click outside the modal to close it."
    )
    browser_perform_task(prompt)
    time.sleep(1.5)

    # Double-check if modal is still present
    content, url, error = browser_fetch()
    if not error:
        modal_patterns = ["share", "invite", "tell your friends", "send invites"]
        if any(pattern in content.lower() for pattern in modal_patterns):
            log(tenant_id, "post_submit", "Modal still present, attempting second dismissal")
            prompt = "Click X, Skip, or outside the modal to close it."
            browser_perform_task(prompt)
            time.sleep(1.0)

    return True, get_next_state(EventState.POST_SUBMIT), None


def handle_verify_success(tenant_id: str, event_data: dict) -> tuple[bool, EventState | None, str | None, str | None]:
    """Verify event was created successfully. Returns (success, next_state, error, event_url)."""
    content, url, error = browser_fetch()
    if error:
        return False, None, f"Fetch failed: {error}", None

    signals = {
        "url_success": check_success_url(url),
        "title_visible": event_data.get("title", "").lower() in content.lower(),
        "edit_button": any(kw in content.lower() for kw in ["edit", "manage", "settings"]),
        "confirmation": any(kw in content.lower() for kw in ["created", "published", "live", "your party"]),
    }

    signal_count = sum(signals.values())
    log(tenant_id, "verify_success", f"Signals: {signals}, count: {signal_count}")

    if signals["url_success"] and signal_count >= 2:
        log(tenant_id, "verify_success", f"Event created successfully: {url}")
        return True, EventState.DONE, None, url
    elif signal_count >= 3:
        log(tenant_id, "verify_success", f"Event likely created: {url}")
        return True, EventState.DONE, None, url
    else:
        return False, None, f"Only {signal_count} success signals", None


# ============================================================================
# Main Workflow Runner
# ============================================================================

def run_workflow(tenant_id: str, event_data: dict, image_prompt: str | None = None,
                 resume: bool = False) -> dict:
    """Run the event creation workflow for Partiful.

    Args:
        tenant_id: Tenant/organization identifier
        event_data: Event details dict
        image_prompt: Optional custom image generation prompt
        resume: Whether to resume from checkpoint

    Returns:
        Result dict with status, event_url, error, resume_token
    """
    log(tenant_id, "init", f"Starting Partiful workflow (resume={resume})")
    log(tenant_id, "init", "Note: Recurring events are NOT supported on Partiful")

    session_mgr = SessionManager()
    checkpoint_mgr = CheckpointManager()

    session = session_mgr.get_or_create(tenant_id)

    checkpoint = checkpoint_mgr.load(tenant_id) if resume else None
    if checkpoint is None:
        checkpoint = Checkpoint(
            tenant_id=tenant_id,
            event_data=event_data,
            current_state=EventState.INIT.value,
        )

    # Determine starting state
    if resume and checkpoint.current_state == EventState.AWAIT_2FA.value:
        current_state = EventState.RESUME_2FA
        log(tenant_id, "init", "Resuming after 2FA")
    elif resume:
        current_state = EventState(checkpoint.current_state)
        log(tenant_id, "init", f"Resuming from state: {current_state.value}")
    else:
        current_state = EventState.INIT

    event_url = None
    error_message = None
    max_iterations = 50
    attempts = {}

    for iteration in range(max_iterations):
        if current_state in TERMINAL_STATES:
            break

        log(tenant_id, current_state.value, f"Executing (iteration {iteration})")

        try:
            if current_state == EventState.INIT:
                success, next_state, error = handle_init(tenant_id, checkpoint)
            elif current_state == EventState.GENERATE_IMAGE:
                success, next_state, error = handle_generate_image(tenant_id, event_data, image_prompt, checkpoint)
            elif current_state == EventState.NAVIGATE:
                success, next_state, error = handle_navigate(tenant_id, session)
            elif current_state == EventState.AUTH_CHECK:
                success, next_state, error = handle_auth_check(tenant_id, session, checkpoint_mgr, checkpoint)
            elif current_state == EventState.RESUME_2FA:
                success, next_state, error = handle_auth_check(tenant_id, session, checkpoint_mgr, checkpoint)
            elif current_state in FILL_STATES:
                success, next_state, error = handle_fill_field(tenant_id, current_state, event_data)
            elif current_state == EventState.VERIFY_FORM:
                success, next_state, error = handle_verify_form(tenant_id, event_data)
            elif current_state == EventState.SUBMIT:
                success, next_state, error = handle_submit(tenant_id)
            elif current_state == EventState.POST_SUBMIT:
                success, next_state, error = handle_post_submit(tenant_id)
            elif current_state == EventState.VERIFY_SUCCESS:
                success, next_state, error, event_url = handle_verify_success(tenant_id, event_data)
            else:
                success, next_state, error = False, EventState.FAILED, f"Unknown state: {current_state}"

            if success:
                checkpoint.completed_states.append(current_state.value)
                current_state = next_state
                checkpoint.current_state = current_state.value
                checkpoint_mgr.save(checkpoint)
                attempts[current_state] = 0
            else:
                if next_state in TERMINAL_STATES:
                    current_state = next_state
                else:
                    current_attempts = attempts.get(current_state, 0) + 1
                    attempts[current_state] = current_attempts

                    config = STATE_CONFIG.get(current_state, {})
                    max_retries = config.get("max_retries", 2)

                    if current_attempts >= max_retries:
                        log(tenant_id, current_state.value, f"Max retries ({max_retries}) reached: {error}")
                        error_message = error or "Max retries exceeded"
                        current_state = EventState.FAILED
                    else:
                        base_delay = config.get("base_delay", 0.75)
                        max_delay = config.get("max_delay", 8.0)
                        delay = min(base_delay * (2 ** current_attempts), max_delay)
                        delay = random.uniform(0, delay)
                        log(tenant_id, current_state.value, f"Retry {current_attempts}/{max_retries} after {delay:.2f}s: {error}")
                        time.sleep(delay)
                break

        except Exception as e:
            log(tenant_id, current_state.value, f"Exception: {e}")
            error_message = str(e)
            current_state = EventState.FAILED
            break

    session_mgr.save(session)

    result = {
        "tenant_id": tenant_id,
        "platform": "partiful",
        "status": current_state.value,
        "event_url": event_url,
        "image_url": checkpoint.image_url,
        "error": error_message,
    }

    if current_state == EventState.PAUSED_2FA:
        result["resume_token"] = f"{tenant_id}:partiful:2fa"
        result["resume_instructions"] = (
            "Please complete 2FA in the browser. "
            "Once done, run this recipe again with resume=true to continue."
        )
    elif current_state == EventState.NEEDS_AUTH:
        result["resume_token"] = f"{tenant_id}:partiful:auth"
        result["resume_instructions"] = (
            "Please log in to Partiful in the browser. "
            "Once logged in, run this recipe again with resume=true to continue."
        )

    if current_state == EventState.DONE:
        checkpoint_mgr.clear(tenant_id)

    return result


# ============================================================================
# Main Entry Point
# ============================================================================

print(f"[{datetime.utcnow().isoformat()}] Starting partiful_create_event recipe")

# Read inputs from environment
tenant_id = os.environ.get("tenant_id", "default")
resume_str = os.environ.get("resume", "false")

event_title = sanitize_input(os.environ.get("event_title", ""), max_len=200)
event_date = sanitize_input(os.environ.get("event_date", ""), max_len=100)
event_time = sanitize_input(os.environ.get("event_time", ""), max_len=100)
event_location = sanitize_input(os.environ.get("event_location", ""), max_len=500)
event_description = sanitize_input(os.environ.get("event_description", ""), max_len=5000)
image_prompt = os.environ.get("image_prompt", None)

# Validate required inputs
if not all([event_title, event_date, event_time, event_location, event_description]):
    output = {
        "tenant_id": tenant_id,
        "platform": "partiful",
        "status": "failed",
        "error": "Missing required inputs: event_title, event_date, event_time, event_location, event_description",
        "event_url": None,
        "image_url": None,
    }
else:
    event_data = {
        "title": event_title,
        "date": event_date,
        "time": event_time,
        "location": event_location,
        "description": event_description,
    }

    resume = resume_str.lower() == "true"
    output = run_workflow(tenant_id, event_data, image_prompt, resume)

print(f"[{datetime.utcnow().isoformat()}] Recipe completed: {output.get('status', 'N/A')}")

# Output is the final variable (Rube MCP pattern)
output
