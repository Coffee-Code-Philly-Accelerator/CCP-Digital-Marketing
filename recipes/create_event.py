"""
RECIPE: Create Event on All Platforms
RECIPE ID: rcp_xvediVZu8BzW
RECIPE URL: https://rube.app/recipes/fa1a7dd7-05d1-4155-803a-a2448f6fc1b2

FLOW: Input → Gemini Image → LLM Descriptions → State Machine Browser Automation (Luma, Meetup, Partiful) → Event URLs

VERSION HISTORY:
v3 (current): State machine architecture with atomic steps, multi-signal verification, platform adapters
v2: Added 2FA detection, skip_platforms option, better auth state checking
v1: Initial version - sequential browser automation for 3 platforms

API LEARNINGS:
- BROWSER_TOOL_NAVIGATE: Returns pageSnapshot in markdown format
- BROWSER_TOOL_PERFORM_WEB_TASK: AI agent fills forms based on natural language prompt
- BROWSER_TOOL_FETCH_WEBPAGE: Gets current page state without navigation
- BROWSER_TOOL_TAKE_SCREENSHOT: Captures screenshot, returns URL
- GEMINI_GENERATE_IMAGE: Returns publicUrl for generated image
- Luma create URL: https://lu.ma/create
- Partiful create URL: https://partiful.com/create
- Meetup requires group-specific URL: {group_url}/events/create/
- Composio responses often double-nest: data.data.field

KNOWN ISSUES:
- Session expiry may require re-login
- 2FA interrupts require manual intervention - recipe reports NEEDS_AUTH
- UI changes may break form filling prompts
- Luma React date picker needs extra wait time (1.5s)
- Meetup has anti-bot detection - requires 2s delays between actions
- Partiful shows share modal after creation - needs dismissal
"""

import os
import re
import json
import time
import random
from datetime import datetime
from enum import Enum

print(f"[{datetime.utcnow().isoformat()}] Starting unified event creation workflow v3")


# ============================================================================
# SECTION 1: State Machine Definition
# ============================================================================

class EventState(Enum):
    """States for the event creation state machine"""
    INIT = "init"
    CHECK_DUPLICATE = "check_duplicate"
    NAVIGATE = "navigate"
    AUTH_CHECK = "auth_check"
    FILL_TITLE = "fill_title"
    FILL_DATE = "fill_date"
    FILL_TIME = "fill_time"
    FILL_LOCATION = "fill_location"
    FILL_DESCRIPTION = "fill_description"
    VERIFY_FORM = "verify_form"
    SUBMIT = "submit"
    POST_SUBMIT = "post_submit"
    VERIFY_SUCCESS = "verify_success"
    DONE = "done"
    FAILED = "failed"
    NEEDS_AUTH = "needs_auth"
    DUPLICATE = "duplicate"
    SKIPPED = "skipped"


# State configuration: max retries and backoff settings per state
STATE_CONFIG = {
    EventState.CHECK_DUPLICATE: {"max_retries": 1, "base_delay": 0.5},
    EventState.NAVIGATE: {"max_retries": 2, "base_delay": 1.0},
    EventState.AUTH_CHECK: {"max_retries": 1, "base_delay": 0.5},
    EventState.FILL_TITLE: {"max_retries": 2, "base_delay": 0.75},
    EventState.FILL_DATE: {"max_retries": 2, "base_delay": 0.75},
    EventState.FILL_TIME: {"max_retries": 2, "base_delay": 0.75},
    EventState.FILL_LOCATION: {"max_retries": 2, "base_delay": 0.75},
    EventState.FILL_DESCRIPTION: {"max_retries": 2, "base_delay": 0.75},
    EventState.VERIFY_FORM: {"max_retries": 2, "base_delay": 1.0},
    EventState.SUBMIT: {"max_retries": 1, "base_delay": 1.0},  # Only 1 retry to avoid duplicates
    EventState.POST_SUBMIT: {"max_retries": 1, "base_delay": 1.0},
    EventState.VERIFY_SUCCESS: {"max_retries": 3, "base_delay": 1.5, "max_delay": 12.0},
}

# Backoff defaults
DEFAULT_BASE_DELAY = 0.75
DEFAULT_MAX_DELAY = 8.0
BACKOFF_MULTIPLIER = 2.0


# ============================================================================
# SECTION 2: Helper Functions
# ============================================================================

def extract_data(result):
    """Extract data from Composio's double-nested response format"""
    if not result:
        return {}
    data = result.get("data", {})
    if isinstance(data, dict) and "data" in data:
        data = data["data"]
    return data if isinstance(data, dict) else {}


def backoff_delay(attempt, base_delay=DEFAULT_BASE_DELAY, max_delay=DEFAULT_MAX_DELAY):
    """Calculate exponential backoff with full jitter"""
    delay = min(base_delay * (BACKOFF_MULTIPLIER ** attempt), max_delay)
    jittered = random.uniform(0, delay)
    return jittered


def log(platform, state, message):
    """Consistent logging format"""
    ts = datetime.utcnow().isoformat()
    state_name = state.value if isinstance(state, EventState) else state
    print(f"[{ts}] [{platform.upper()}] [{state_name}] {message}")


def capture_screenshot(platform, state, error_msg=""):
    """Capture screenshot on failure for debugging"""
    try:
        result, error = run_composio_tool("BROWSER_TOOL_TAKE_SCREENSHOT", {})
        if error:
            log(platform, state, f"Screenshot failed: {error}")
            return ""
        data = extract_data(result)
        url = data.get("url", data.get("screenshotUrl", ""))
        log(platform, state, f"Screenshot captured: {url}")
        if error_msg:
            log(platform, state, f"Failure reason: {error_msg}")
        return url
    except Exception as e:
        log(platform, state, f"Screenshot exception: {e}")
        return ""


def fetch_page_content():
    """Fetch current page content for verification"""
    result, error = run_composio_tool("BROWSER_TOOL_FETCH_WEBPAGE", {
        "format": "markdown",
        "wait": 1500
    })
    if error:
        return "", "", error
    data = extract_data(result)
    content = data.get("content", data.get("pageSnapshot", ""))
    url = data.get("url", "")
    return content, url, None


# Auth detection patterns
AUTH_PATTERNS = [
    "sign in", "log in", "login", "sign up", "create account",
    "enter your email", "enter your password", "verification code",
    "2fa", "two-factor", "authenticate", "verify your", "continue with google",
    "continue with apple", "continue with email"
]

# Validation error patterns
VALIDATION_ERROR_PATTERNS = [
    "required", "fix errors", "please enter", "invalid", "can't be blank",
    "must be", "is required", "please fill"
]


def check_needs_auth(content):
    """Check if page indicates auth is needed"""
    content_lower = content.lower()
    return any(pattern in content_lower for pattern in AUTH_PATTERNS)


def check_validation_errors(content):
    """Check if page shows validation errors"""
    content_lower = content.lower()
    return any(pattern in content_lower for pattern in VALIDATION_ERROR_PATTERNS)


# ============================================================================
# SECTION 3: Platform Adapters
# ============================================================================

class BasePlatformAdapter:
    """Base adapter with common functionality"""

    name = "base"
    create_url = ""
    home_url = ""
    inter_step_delay = 0.4  # Default settle time after each action

    # Form field indicators to verify we're on the create page
    form_indicators = []

    def __init__(self, event_data, descriptions, image_url):
        self.event = event_data
        self.descriptions = descriptions
        self.image_url = image_url

    def get_description(self):
        return self.descriptions.get(self.name, self.event["description"])

    def get_create_url(self):
        return self.create_url

    def get_home_url(self):
        return self.home_url

    def is_form_page(self, content):
        """Check if we're on the actual form page"""
        content_lower = content.lower()
        return any(indicator in content_lower for indicator in self.form_indicators)

    def success_url_check(self, url):
        """Check if URL indicates successful event creation"""
        raise NotImplementedError

    def get_prompt(self, state):
        """Get the atomic prompt for a given state"""
        raise NotImplementedError

    def post_step_wait(self, state):
        """Get additional wait time after a specific step"""
        return self.inter_step_delay

    def post_submit_action(self):
        """Optional action after submit (e.g., dismiss modals)"""
        return None


class LumaAdapter(BasePlatformAdapter):
    """Adapter for Luma (lu.ma)"""

    name = "luma"
    create_url = "https://lu.ma/create"
    home_url = "https://lu.ma/home"
    inter_step_delay = 0.5
    form_indicators = ["event title", "create event", "what's your event", "add event"]

    def success_url_check(self, url):
        return "lu.ma/" in url and "/create" not in url and "/home" not in url

    def get_prompt(self, state):
        prompts = {
            EventState.FILL_TITLE: f"Click on the event title field (may say 'Event Title' or 'Untitled Event'), clear any existing text, type exactly: {self.event['title']}, then click outside the field to confirm",
            EventState.FILL_DATE: f"Click on the date field or calendar icon, select the date: {self.event['date']}. Wait for the calendar to respond before clicking.",
            EventState.FILL_TIME: f"Click on the time field, enter the time: {self.event['time']}",
            EventState.FILL_LOCATION: f"Click on the location or venue field, type: {self.event['location']}, then select from the dropdown or press Enter",
            EventState.FILL_DESCRIPTION: f"Click on the description field (may say 'Add a description'), clear any existing text, and type: {self.get_description()}",
            EventState.VERIFY_FORM: "Review the form and make sure all fields are filled correctly. Do not click any buttons yet.",
            EventState.SUBMIT: "Click the 'Publish' or 'Create Event' button to publish the event. Wait for the page to navigate to the new event.",
        }
        return prompts.get(state, "")

    def post_step_wait(self, state):
        if state == EventState.FILL_DATE:
            return 1.5  # Extra wait for React date picker
        return self.inter_step_delay


class MeetupAdapter(BasePlatformAdapter):
    """Adapter for Meetup"""

    name = "meetup"
    home_url = "https://www.meetup.com/home"
    inter_step_delay = 2.0  # Anti-bot delay
    form_indicators = ["event details", "what's your event", "create event", "event title", "event name"]

    def __init__(self, event_data, descriptions, image_url, group_url):
        super().__init__(event_data, descriptions, image_url)
        self.group_url = group_url

    def get_create_url(self):
        if not self.group_url:
            return ""
        return self.group_url.rstrip("/") + "/events/create/"

    def success_url_check(self, url):
        return "meetup.com" in url and "/events/" in url and "/create" not in url

    def get_prompt(self, state):
        prompts = {
            EventState.FILL_TITLE: f"Find the event title or event name field, click on it, clear any existing text, type exactly: {self.event['title']}, then click outside",
            EventState.FILL_DATE: f"Find and click the date field or date picker, select: {self.event['date']}. May need to navigate the calendar.",
            EventState.FILL_TIME: f"Find the start time field, click it, and enter: {self.event['time']}",
            EventState.FILL_LOCATION: f"Find the venue or location field, click it, type: {self.event['location']}, and select from suggestions or press Enter",
            EventState.FILL_DESCRIPTION: f"Find the description or 'about this event' field, click it, and type: {self.get_description()}",
            EventState.VERIFY_FORM: "Scroll through the form and verify all required fields are filled. Do not submit yet.",
            EventState.SUBMIT: "Click the 'Publish' or 'Schedule Event' or 'Create Event' button. Wait for confirmation.",
        }
        return prompts.get(state, "")


class PartifulAdapter(BasePlatformAdapter):
    """Adapter for Partiful"""

    name = "partiful"
    create_url = "https://partiful.com/create"
    home_url = "https://partiful.com/home"
    inter_step_delay = 0.6
    form_indicators = ["untitled event", "event title", "add event", "create party", "what's the occasion"]

    def success_url_check(self, url):
        return "partiful.com/e/" in url

    def get_prompt(self, state):
        prompts = {
            EventState.FILL_TITLE: f"Click on the event title field (may say 'Untitled Event' or similar), clear it, type exactly: {self.event['title']}, click outside",
            EventState.FILL_DATE: f"Click on the date field or 'When' section, select: {self.event['date']}",
            EventState.FILL_TIME: f"Click on the time field, enter: {self.event['time']}",
            EventState.FILL_LOCATION: f"Click on the location field or 'Where' section, type: {self.event['location']}, select from dropdown or press Enter",
            EventState.FILL_DESCRIPTION: f"Click on the description or details field, type: {self.get_description()}",
            EventState.VERIFY_FORM: "Check that all event details are filled in correctly. Do not publish yet.",
            EventState.SUBMIT: "Click 'Save', 'Publish', or 'Create' button to create the event. Wait for navigation.",
        }
        return prompts.get(state, "")

    def post_submit_action(self):
        """Dismiss share/invite modal that appears after creation"""
        return "If a share, invite, or 'tell your friends' modal appears, click the X button, 'Skip', 'Maybe later', or click outside to dismiss it"


# ============================================================================
# SECTION 4: State Machine Implementation
# ============================================================================

class EventCreationStateMachine:
    """State machine for creating events with atomic steps and verification"""

    # Define state transitions
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

    def __init__(self, adapter):
        self.adapter = adapter
        self.platform = adapter.name
        self.state = EventState.INIT
        self.attempts = {}  # Track attempts per state
        self.screenshot_url = ""
        self.event_url = ""
        self.error_message = ""
        self.verification_signals = {}

    def run(self):
        """Execute the state machine until terminal state"""
        terminal_states = {EventState.DONE, EventState.FAILED, EventState.NEEDS_AUTH,
                          EventState.DUPLICATE, EventState.SKIPPED}

        while self.state not in terminal_states:
            log(self.platform, self.state, "Executing...")

            try:
                success, next_state, error = self._execute_state()
            except Exception as e:
                success, next_state, error = False, None, str(e)

            if success:
                self.state = next_state
                self.attempts[self.state] = 0
            else:
                current_attempts = self.attempts.get(self.state, 0) + 1
                self.attempts[self.state] = current_attempts

                config = STATE_CONFIG.get(self.state, {})
                max_retries = config.get("max_retries", 2)

                if current_attempts >= max_retries:
                    log(self.platform, self.state, f"Max retries ({max_retries}) reached: {error}")
                    self.error_message = error or "Max retries exceeded"
                    self.screenshot_url = capture_screenshot(self.platform, self.state, self.error_message)
                    self.state = EventState.FAILED
                else:
                    base_delay = config.get("base_delay", DEFAULT_BASE_DELAY)
                    max_delay = config.get("max_delay", DEFAULT_MAX_DELAY)
                    delay = backoff_delay(current_attempts, base_delay, max_delay)
                    log(self.platform, self.state, f"Retry {current_attempts}/{max_retries} after {delay:.2f}s: {error}")
                    time.sleep(delay)

        log(self.platform, self.state, f"Terminal state reached. URL: {self.event_url}")
        return self._build_result()

    def _execute_state(self):
        """Execute current state and return (success, next_state, error)"""
        handlers = {
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
            return False, EventState.FAILED, f"No handler for state {self.state}"

        return handler()

    def _next_state(self):
        """Get the next state in the flow"""
        try:
            idx = self.STATE_FLOW.index(self.state)
            if idx + 1 < len(self.STATE_FLOW):
                return self.STATE_FLOW[idx + 1]
        except ValueError:
            pass
        return EventState.DONE

    def _handle_init(self):
        """Initialize - just move to next state"""
        return True, self._next_state(), None

    def _handle_check_duplicate(self):
        """Check for existing event with same title"""
        home_url = self.adapter.get_home_url()
        if not home_url:
            return True, self._next_state(), None

        result, error = run_composio_tool("BROWSER_TOOL_NAVIGATE", {"url": home_url})
        if error:
            # Non-critical, continue anyway
            log(self.platform, self.state, f"Could not check duplicates: {error}")
            return True, self._next_state(), None

        data = extract_data(result)
        content = data.get("pageSnapshot", "")

        title_lower = self.adapter.event["title"].lower()
        if title_lower in content.lower():
            log(self.platform, self.state, "Potential duplicate found")
            self.error_message = f"Event '{self.adapter.event['title']}' may already exist"
            return False, EventState.DUPLICATE, self.error_message

        return True, self._next_state(), None

    def _handle_navigate(self):
        """Navigate to the event creation page"""
        create_url = self.adapter.get_create_url()
        if not create_url:
            self.error_message = f"No create URL for {self.platform}"
            return False, EventState.SKIPPED, self.error_message

        result, error = run_composio_tool("BROWSER_TOOL_NAVIGATE", {"url": create_url})
        if error:
            return False, None, f"Navigation failed: {error}"

        time.sleep(0.5)  # Let page settle
        return True, self._next_state(), None

    def _handle_auth_check(self):
        """Check if we're logged in and on the form page"""
        content, url, error = fetch_page_content()
        if error:
            return False, None, f"Could not fetch page: {error}"

        if check_needs_auth(content) and not self.adapter.is_form_page(content):
            self.error_message = f"Login required for {self.platform.title()} - please log in via browser and retry"
            return False, EventState.NEEDS_AUTH, self.error_message

        if not self.adapter.is_form_page(content):
            return False, None, "Not on form page - may need navigation"

        return True, self._next_state(), None

    def _handle_fill_field(self):
        """Handle atomic field filling with verification"""
        prompt = self.adapter.get_prompt(self.state)
        if not prompt:
            return True, self._next_state(), None

        result, error = run_composio_tool("BROWSER_TOOL_PERFORM_WEB_TASK", {"prompt": prompt})
        if error:
            return False, None, f"Field fill failed: {error}"

        # Post-step wait (platform-specific)
        wait_time = self.adapter.post_step_wait(self.state)
        time.sleep(wait_time)

        # Verify field was filled (basic check)
        content, _, fetch_error = fetch_page_content()
        if fetch_error:
            log(self.platform, self.state, f"Could not verify field: {fetch_error}")
            # Continue anyway - verification is best-effort
        else:
            # For title, do a simple check
            if self.state == EventState.FILL_TITLE:
                title = self.adapter.event["title"]
                if title.lower() not in content.lower():
                    log(self.platform, self.state, "Title not found in page after fill")
                    # Don't fail - might be in an input that's not rendered in snapshot

        return True, self._next_state(), None

    def _handle_verify_form(self):
        """Verify form is complete before submission"""
        prompt = self.adapter.get_prompt(EventState.VERIFY_FORM)
        if prompt:
            run_composio_tool("BROWSER_TOOL_PERFORM_WEB_TASK", {"prompt": prompt})
            time.sleep(0.5)

        content, _, error = fetch_page_content()
        if error:
            return False, None, f"Could not verify form: {error}"

        if check_validation_errors(content):
            return False, None, "Form has validation errors"

        return True, self._next_state(), None

    def _handle_submit(self):
        """Submit the form"""
        prompt = self.adapter.get_prompt(EventState.SUBMIT)

        result, error = run_composio_tool("BROWSER_TOOL_PERFORM_WEB_TASK", {"prompt": prompt})
        if error:
            return False, None, f"Submit failed: {error}"

        # Give time for navigation/processing
        time.sleep(2.0)
        return True, self._next_state(), None

    def _handle_post_submit(self):
        """Handle post-submit actions (like dismissing modals)"""
        action = self.adapter.post_submit_action()
        if action:
            run_composio_tool("BROWSER_TOOL_PERFORM_WEB_TASK", {"prompt": action})
            time.sleep(1.0)

        return True, self._next_state(), None

    def _handle_verify_success(self):
        """Verify event was created using multiple signals"""
        content, url, error = fetch_page_content()
        if error:
            return False, None, f"Could not verify success: {error}"

        # Collect signals
        signals = {
            "url_success": self.adapter.success_url_check(url),
            "edit_button": any(kw in content.lower() for kw in ["edit", "manage", "settings"]),
            "title_visible": self.adapter.event["title"].lower() in content.lower(),
            "no_create_form": not self.adapter.is_form_page(content),
        }

        self.verification_signals = signals
        signal_count = sum(signals.values())

        log(self.platform, self.state, f"Signals: {signals} (count: {signal_count})")

        # Decision logic:
        # - URL check is primary signal
        # - Need URL + 1 secondary, OR 3 secondary signals
        if signals["url_success"] and signal_count >= 2:
            self.event_url = url
            return True, EventState.DONE, None
        elif signal_count >= 3:
            self.event_url = url
            return True, EventState.DONE, None
        else:
            return False, None, f"Only {signal_count} success signals"

    def _build_result(self):
        """Build the result dictionary"""
        status_map = {
            EventState.DONE: "PUBLISHED",
            EventState.FAILED: "FAILED",
            EventState.NEEDS_AUTH: "NEEDS_AUTH",
            EventState.DUPLICATE: "DUPLICATE",
            EventState.SKIPPED: "SKIPPED",
        }

        status = status_map.get(self.state, "NEEDS_REVIEW")

        return {
            "status": status,
            "url": self.event_url,
            "error": self.error_message,
            "screenshot": self.screenshot_url,
            "signals": self.verification_signals,
        }


# ============================================================================
# SECTION 5: Main Workflow
# ============================================================================

# Get inputs
event_title = os.environ.get("event_title")
event_date = os.environ.get("event_date")
event_time = os.environ.get("event_time")
event_location = os.environ.get("event_location")
event_description = os.environ.get("event_description")
meetup_group_url = os.environ.get("meetup_group_url", "")
platforms_str = os.environ.get("platforms", "luma,meetup,partiful")
skip_platforms_str = os.environ.get("skip_platforms", "")

# Validate required inputs
if not all([event_title, event_date, event_time, event_location, event_description]):
    raise ValueError("Missing required inputs: event_title, event_date, event_time, event_location, event_description")

event_data = {
    "title": event_title,
    "date": event_date,
    "time": event_time,
    "location": event_location,
    "description": event_description,
}

platforms = [p.strip().lower() for p in platforms_str.split(",") if p.strip()]
skip_platforms = [p.strip().lower() for p in skip_platforms_str.split(",") if p.strip()]
active_platforms = [p for p in platforms if p not in skip_platforms]

print(f"[{datetime.utcnow().isoformat()}] Creating event on platforms: {active_platforms}")
if skip_platforms:
    print(f"[{datetime.utcnow().isoformat()}] Skipping platforms: {skip_platforms}")

# Step 1: Generate promotional image
print(f"[{datetime.utcnow().isoformat()}] Generating promotional image via Gemini...")
image_prompt = f"Create a modern, eye-catching event promotional graphic for: {event_title}. Style: professional, vibrant colors, suitable for social media. Include visual elements suggesting: {event_location}. Do not include any text in the image."

image_result, image_error = run_composio_tool("GEMINI_GENERATE_IMAGE", {
    "prompt": image_prompt,
    "model": "imagen-3.0-generate-002"
})

if image_error:
    print(f"[{datetime.utcnow().isoformat()}] Image generation failed: {image_error}")
    image_url = ""
else:
    image_data = extract_data(image_result)
    image_url = image_data.get("publicUrl", "")
    print(f"[{datetime.utcnow().isoformat()}] Image generated: {image_url}")

# Step 2: Generate platform-specific descriptions
print(f"[{datetime.utcnow().isoformat()}] Generating platform-optimized descriptions...")
desc_prompt = f"""Generate 3 platform-specific event descriptions based on this info:
Title: {event_title}
Date: {event_date} at {event_time}
Location: {event_location}
Original Description: {event_description}

Return JSON with keys: luma, meetup, partiful
Each should be optimized for that platform's audience and format.
Luma: Professional, concise
Meetup: Community-focused, detailed
Partiful: Fun, casual, emoji-friendly"""

desc_response, desc_error = invoke_llm(desc_prompt)
if desc_error:
    print(f"[{datetime.utcnow().isoformat()}] Description generation failed, using original")
    descriptions = {"luma": event_description, "meetup": event_description, "partiful": event_description}
else:
    try:
        json_match = re.search(r'\{[^{}]*\}', desc_response, re.DOTALL)
        if json_match:
            descriptions = json.loads(json_match.group())
        else:
            descriptions = {"luma": event_description, "meetup": event_description, "partiful": event_description}
    except:
        descriptions = {"luma": event_description, "meetup": event_description, "partiful": event_description}

print(f"[{datetime.utcnow().isoformat()}] Descriptions ready for all platforms")

# Step 3: Create events using state machine
results = {
    "luma_url": "",
    "meetup_url": "",
    "partiful_url": "",
    "image_url": image_url,
    "statuses": {},
    "needs_auth_platforms": [],
    "screenshots": {},
}

# Execute for each platform (sequential for stability)
if "luma" in active_platforms:
    adapter = LumaAdapter(event_data, descriptions, image_url)
    sm = EventCreationStateMachine(adapter)
    result = sm.run()
    results["luma_url"] = result.get("url", "")
    results["statuses"]["luma"] = result
    if result["status"] == "NEEDS_AUTH":
        results["needs_auth_platforms"].append("luma")
    if result.get("screenshot"):
        results["screenshots"]["luma"] = result["screenshot"]
    print(f"[{datetime.utcnow().isoformat()}] Luma: {result['status']}")

if "meetup" in active_platforms:
    adapter = MeetupAdapter(event_data, descriptions, image_url, meetup_group_url)
    sm = EventCreationStateMachine(adapter)
    result = sm.run()
    results["meetup_url"] = result.get("url", "")
    results["statuses"]["meetup"] = result
    if result["status"] == "NEEDS_AUTH":
        results["needs_auth_platforms"].append("meetup")
    if result.get("screenshot"):
        results["screenshots"]["meetup"] = result["screenshot"]
    print(f"[{datetime.utcnow().isoformat()}] Meetup: {result['status']}")

if "partiful" in active_platforms:
    adapter = PartifulAdapter(event_data, descriptions, image_url)
    sm = EventCreationStateMachine(adapter)
    result = sm.run()
    results["partiful_url"] = result.get("url", "")
    results["statuses"]["partiful"] = result
    if result["status"] == "NEEDS_AUTH":
        results["needs_auth_platforms"].append("partiful")
    if result.get("screenshot"):
        results["screenshots"]["partiful"] = result["screenshot"]
    print(f"[{datetime.utcnow().isoformat()}] Partiful: {result['status']}")

# Build summary
status_parts = []
for platform, status_info in results.get("statuses", {}).items():
    status_parts.append(f"{platform.title()}: {status_info.get('status', 'UNKNOWN')}")

results["status_summary"] = " | ".join(status_parts)
needs_auth_str = ",".join(results["needs_auth_platforms"]) if results["needs_auth_platforms"] else "none"

print(f"[{datetime.utcnow().isoformat()}] Workflow complete: {results['status_summary']}")
if results["needs_auth_platforms"]:
    print(f"[{datetime.utcnow().isoformat()}] ACTION REQUIRED: Log in to these platforms and re-run: {needs_auth_str}")

output = {
    "luma_url": results["luma_url"],
    "meetup_url": results["meetup_url"],
    "partiful_url": results["partiful_url"],
    "image_url": results["image_url"],
    "status_summary": results["status_summary"],
    "needs_auth": needs_auth_str
}
output
