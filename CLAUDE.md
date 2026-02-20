# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CCP Digital Marketing automates event creation and social media promotion for Coffee Code Philly Accelerator using Rube MCP (Composio).

**Two-phase workflow:**
1. **Event Creation** - Browser automation for Luma, Meetup, Partiful (no public APIs)
2. **Social Promotion** - Direct API integrations for Twitter, LinkedIn, Instagram, Facebook, Discord

## Development Commands

### Recipe Client (scripts/)

```bash
pip install -r scripts/requirements.txt
export COMPOSIO_API_KEY='your-key'

# Create event on all platforms (Luma, Meetup, Partiful)
python scripts/recipe_client.py create-event \
  --title "Event Name" --date "January 25, 2025" --time "6:00 PM EST" \
  --location "Venue" --description "Description" \
  --meetup-url "https://www.meetup.com/code-coffee-philly"

# Skip specific platforms
python scripts/recipe_client.py create-event \
  --title "Event Name" --date "January 25, 2025" --time "6:00 PM EST" \
  --location "Venue" --description "Description" \
  --skip "meetup,partiful"

# Promote on social media
python scripts/recipe_client.py promote \
  --title "Event Name" --date "January 25, 2025" --time "6:00 PM EST" \
  --location "Venue" --description "Description" \
  --event-url "https://lu.ma/abc123"

python scripts/recipe_client.py full-workflow [same args]

# Generic social post (not event-specific)
python scripts/recipe_client.py social-post \
  --topic "New Partnership" --content "We're partnering with TechHub!" \
  --url "https://example.com" --tone "excited"

python scripts/recipe_client.py info
```

## Architecture

**Rube MCP Recipes** (`recipes/`) - Self-contained Python scripts for Composio's Rube MCP runtime. These use `os.environ.get()` for inputs, `run_composio_tool()` for APIs, `invoke_llm()` for AI. Output is a bare variable (no return statement). Include mock implementations for local testing.

## Recipe Code Pattern

Recipes in `recipes/` follow this pattern for Rube MCP runtime:
```python
"""RECIPE: Name  |  RECIPE ID: rcp_xxxxx"""
import os
event_title = os.environ.get("event_title")
result, error = run_composio_tool("TOOL_NAME", {args})
response, error = invoke_llm("prompt")
output = {...}  # bare variable, no return statement
output
```

## Key Recipes

| Recipe | ID | Purpose |
|--------|-----|---------|
| Create Event (Luma) | `rcp_mXyFyALaEsQF` | AI browser agent creates event on lu.ma |
| Create Event (Meetup) | `rcp_kHJoI1WmR3AR` | AI browser agent creates event on Meetup |
| Create Event (Partiful) | `rcp_bN7jRF5P_Kf0` | AI browser agent creates event on Partiful |
| Social Promotion | `rcp_X65IirgPhwh3` | Parallel API posting to 5 social platforms |
| Social Post | `rcp_3LheyoNQpiFK` | Generic social media post (non-event content) |

All event creation recipes default to Hyperbrowser (`HYPERBROWSER_START_BROWSER_USE_TASK`) with persistent auth profiles, falling back to Composio's `BROWSER_TOOL_CREATE_TASK` when configured. Both use a single AI browser agent call + polling pattern instead of the old multi-step state machine with sequential `NAVIGATE`/`PERFORM_WEB_TASK`/`FETCH_WEBPAGE` calls that exceeded the 4-minute Rube runtime timeout.

## Composio Tool Reference

### Browser Automation (v3 - Hyperbrowser, Primary)
- `HYPERBROWSER_CREATE_PROFILE` - Create persistent browser profile (saves cookies/auth across sessions)
- `HYPERBROWSER_CREATE_SESSION` - Start browser session with profile, stealth mode, cookie acceptance
- `HYPERBROWSER_START_BROWSER_USE_TASK` - Launch AI browser agent with natural language task + session options
- `HYPERBROWSER_GET_BROWSER_USE_TASK_STATUS` - Poll task status (running/completed/failed)
- `HYPERBROWSER_GET_SESSION_DETAILS` - Get session liveUrl for real-time browser watching

> **Note:** Hyperbrowser provides persistent profiles that save login cookies across sessions, solving the auth expiry issue with Composio's ephemeral browser_tool sessions. All event creation recipes default to Hyperbrowser.

### Browser Automation (v2 - Composio browser_tool, Fallback)
- `BROWSER_TOOL_CREATE_TASK` - Launch AI browser agent with natural language task description + startUrl
- `BROWSER_TOOL_WATCH_TASK` - Poll task status (started/finished/stopped), returns current_url, is_success, output
- `BROWSER_TOOL_GET_SESSION` - Get liveUrl for real-time browser watching

### Browser Automation (v1 - Deprecated)
- `BROWSER_TOOL_NAVIGATE` - Navigate to URL, returns pageSnapshot
- `BROWSER_TOOL_PERFORM_WEB_TASK` - AI agent fills forms via natural language prompt
- `BROWSER_TOOL_FETCH_WEBPAGE` - Get current page state
- `BROWSER_TOOL_TAKE_SCREENSHOT` - Capture screenshot (debugging)

> **Note:** v1 tools require ~10 sequential calls for event creation, exceeding the 4-minute Rube runtime timeout. All recipes now use v2.

### Social APIs
- `TWITTER_CREATION_OF_A_POST`
- `LINKEDIN_GET_MY_INFO` / `LINKEDIN_CREATE_LINKED_IN_POST`
- `INSTAGRAM_GET_USER_INFO` / `INSTAGRAM_CREATE_MEDIA_CONTAINER` / `INSTAGRAM_GET_POST_STATUS` / `INSTAGRAM_CREATE_POST`
- `FACEBOOK_CREATE_POST`
- `DISCORDBOT_CREATE_MESSAGE`

### AI
- `GEMINI_GENERATE_IMAGE` - Image generation (model: gemini-2.5-flash-image)
- `invoke_llm()` - LLM content generation (recipe runtime only)

## Platform-Specific Quirks

| Platform | Issue | Mitigation |
|----------|-------|------------|
| Luma | React date picker | Task instructions include explicit 2s waits after date selection |
| Meetup | Anti-bot detection | Task instructions include 2s waits between all form actions |
| Partiful | Share modal after creation | Task instructions dismiss modal before URL extraction |
| All | Session expiry | Browser task navigates to login page; recipe reports failure |

## Browser Provider Configuration

Event creation recipes support two browser providers, controlled by `CCP_BROWSER_PROVIDER`:

| Provider | Value | Description |
|----------|-------|-------------|
| Hyperbrowser | `hyperbrowser` (default) | Persistent profiles with saved auth. Requires one-time profile setup per platform. |
| Composio browser_tool | `browser_tool` | Ephemeral sessions (no auth persistence). Original provider, now fallback. |

### Auth Setup

Before using Hyperbrowser, set up persistent profiles for each platform:
1. Run the **auth-setup** skill for each platform (Luma, Meetup, Partiful)
2. Complete Google OAuth login in the browser window
3. Save the profile IDs to your `.env` file

### Re-Authentication

If a recipe returns `NEEDS_AUTH`, re-run auth-setup with the existing `profile_id` to re-login without creating a new profile.

## Common Patterns

### Nested Data Extraction
Composio responses often double-nest. In recipes:
```python
data = result.get("data", {})
if "data" in data:
    data = data["data"]
```

### Auth Detection
```python
AUTH_PATTERNS = ["sign in", "log in", "login", "verification code", "2fa"]
def check_needs_auth(page_content):
    return any(p in page_content.lower() for p in AUTH_PATTERNS)
```

### Skip Platforms
Recipes accept skip lists: `{"skip_platforms": "meetup,facebook"}`

## Status Codes

| Status | Meaning | Action |
|--------|---------|--------|
| `PUBLISHED`/`DONE` | Success | None |
| `NEEDS_AUTH` | Browser session expired | Log in manually, re-run |
| `FAILED` | Error occurred | Check error message |
| `SKIPPED` | Intentionally skipped | Via skip_platforms param |

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `COMPOSIO_API_KEY` | Yes | - | Composio API authentication |
| `CCP_COMPOSIO_API_BASE` | No | `https://backend.composio.dev/api/v1` | Composio API base URL |
| `CCP_DISCORD_CHANNEL_ID` | No | (empty) | Default Discord channel ID |
| `CCP_FACEBOOK_PAGE_ID` | No | (empty) | Default Facebook page ID |
| `CCP_MEETUP_GROUP_URL` | No | `https://www.meetup.com/code-coffee-philly` | Default Meetup group URL |
| `CCP_LUMA_CREATE_URL` | No | `https://lu.ma/create` | Override Luma create page URL |
| `CCP_PARTIFUL_CREATE_URL` | No | `https://partiful.com/create` | Override Partiful create page URL |
| `CCP_BROWSER_PROVIDER` | No | `hyperbrowser` | Browser provider: "hyperbrowser" or "browser_tool" |
| `CCP_LUMA_PROFILE_ID` | No | (empty) | Hyperbrowser profile UUID for Luma |
| `CCP_MEETUP_PROFILE_ID` | No | (empty) | Hyperbrowser profile UUID for Meetup |
| `CCP_PARTIFUL_PROFILE_ID` | No | (empty) | Hyperbrowser profile UUID for Partiful |
| `CCP_HYPERBROWSER_LLM` | No | `claude-sonnet-4-20250514` | LLM for Hyperbrowser browser agent |
| `CCP_HYPERBROWSER_MAX_STEPS` | No | `25` | Max agent steps per browser task |
| `CCP_HYPERBROWSER_USE_STEALTH` | No | `true` | Stealth mode for anti-bot evasion |

**Override Precedence:** Recipe input parameters > Environment variables > Defaults

## Via Rube MCP Tools

```python
RUBE_EXECUTE_RECIPE(
    recipe_id="rcp_mXyFyALaEsQF",
    input_data={"event_title": "...", "event_date": "...", ...}
)
```

## Claude Code Skills

Skills are defined in `.claude/skills/`. Each wraps a `RUBE_EXECUTE_RECIPE` call. Event creation recipes default to Hyperbrowser (single AI browser agent with persistent auth) and return a `live_url` for real-time watching.

| Skill | Directory | Recipe ID | Purpose |
|-------|-----------|-----------|---------|
| Luma Create | `luma-create/` | `rcp_mXyFyALaEsQF` | Create event on Luma via browser automation |
| Meetup Create | `meetup-create/` | `rcp_kHJoI1WmR3AR` | Create event on Meetup via browser automation |
| Partiful Create | `partiful-create/` | `rcp_bN7jRF5P_Kf0` | Create event on Partiful via browser automation |
| Social Promote | `social-promote/` | `rcp_X65IirgPhwh3` | Post event to Twitter, LinkedIn, Instagram, Facebook, Discord |
| Social Post | `social-post/` | `rcp_3LheyoNQpiFK` | Post generic content (non-event) to social media platforms |
| Full Workflow | `full-workflow/` | All of the above | Orchestrate: create on all platforms, then promote on social media |
| Auth Setup | `auth-setup/` | N/A (direct tool calls) | Set up Hyperbrowser persistent auth profiles |

**Chaining:** The social-promote and full-workflow skills accept an optional `image_url` input. When provided (e.g., from a prior event creation), the social promotion recipe skips Gemini image generation and reuses the existing image.

---

# Design Philosophy

> **Instruction to Agent:** Consult the following principles before generating any new classes, functions, or error handling logic.

## Principle Priority (Conflict Resolution)

When principles conflict, follow this priority order:

1. **Let It Crash** (highest) - Visibility of errors trumps all
2. **KISS** - Simplicity over elegance
3. **Pure Functions** - Determinism over convenience
4. **SOLID** (lowest) - Architecture can flex for simplicity

**Example Conflicts:**
- **KISS vs Pure Functions**: If dependency injection adds excessive ceremony for a simple utility, prefer the simpler impure version with a comment.
- **SOLID vs KISS**: If an abstraction has only 1 use case, keep it inline even if it violates OCP.
- **Let It Crash vs KISS**: A visible crash is NEVER simplified away with a silent fallback.

---

## CRITICAL: Let It Crash (Primary Principle)

**This is the most important design principle in this codebase. Read this section first before writing ANY error handling code.**

**CORE PRINCIPLE**: Embrace controlled failure. NO defensive programming. NO exponential backoffs. NO complex fallback chains. Let errors propagate and crash visibly.

### The Golden Rule

**Do NOT write `try/except`. Period.**

The default for every function is zero error handling. Errors propagate, crash visibly, and give a full stack trace. This is the correct behavior in virtually all cases.

### Why No try/except

| What try/except does | Why it's harmful |
|----------------------|------------------|
| Hides the root cause | Stack trace is lost or obscured |
| Creates silent failures | Bugs survive in production undetected |
| Adds code complexity | More branches, harder to reason about |
| Encourages defensive coding | Treats symptoms instead of fixing sources |
| Makes debugging harder | "It returned None" tells you nothing |

### What to Do Instead

**Use error-returning patterns.** This codebase already follows this: `run_composio_tool()` returns `(result, error)` tuples. Check the error value explicitly -- no exceptions needed.

```python
# GOOD - Error values, not exceptions
result, error = run_composio_tool("TOOL_NAME", args)
if error:
    print(f"Tool failed: {error}")
    output = {"status": "FAILED", "error": error}
else:
    output = {"status": "DONE", "data": result}

# GOOD - Let it crash for internal operations
def create_event_payload(title: str, date: str, time: str) -> dict:
    payload = {"event_title": title, "event_date": date, "event_time": time}
    return payload  # No error handling needed!

# GOOD - Validate inputs up front, don't catch failures later
if not all([event_title, event_date, event_time]):
    raise ValueError("Missing required inputs")
# Now proceed knowing inputs are valid -- no defensive checks downstream

# GOOD - Use conditional logic instead of exception control flow
response = invoke_llm(prompt)
if response is None or response == "":
    output = {"status": "FAILED", "error": "LLM returned empty response"}
else:
    output = {"status": "DONE", "content": response}
```

### FORBIDDEN Patterns

```python
# FORBIDDEN - Silent swallowing
try:
    do_something()
except Exception:
    pass

# FORBIDDEN - Exception as control flow
try:
    result = process_event(event)
except Exception:
    return None

# FORBIDDEN - Retry/backoff loops
for attempt in range(MAX_RETRIES):
    try:
        result = call_api()
        break
    except Exception:
        time.sleep(2 ** attempt)

# FORBIDDEN - Fallback chains
try:
    result = primary_method()
except Exception:
    try:
        result = fallback_method()
    except Exception:
        result = default_value
```

### The ONLY Exception (Literally)

If a third-party library forces exception-based error handling (no error-return alternative exists), you may catch **one specific exception type** with a `# LET-IT-CRASH-EXCEPTION` annotation. This should be rare -- most libraries used in this project (Composio tools, `invoke_llm`) already return error tuples.

```python
# LET-IT-CRASH-EXCEPTION: IMPORT_GUARD - module may not be installed
try:
    import optional_module
except ImportError:
    optional_module = None
```

If you find yourself wanting to write more than this, **stop and redesign**. The function signature or the calling pattern is wrong.

### Code Review Rule

**Any `try/except` block in a PR requires explicit justification in the PR description.** The default review stance is: remove it.

---

## SOLID Principles

**CORE PRINCIPLE**: Design systems with high cohesion and low coupling for maintainability, testability, and extensibility.

### 1. Single Responsibility Principle (SRP)

> "A module should have one, and only one, reason to change"

Each component/function/class should do ONE thing well. Separate concerns: state management != business logic != data fetching.

```python
# BAD - Function with multiple responsibilities
def process_event(title, date, time, location):
    sanitized = sanitize_all_inputs(title, date, time, location)  # Sanitization
    payload = build_payload(sanitized)                             # Payload construction
    result = call_browser_api(payload)                             # API call
    post_to_social(result["url"])                                  # Social posting
    return format_output(result)                                   # Formatting

# GOOD - Single responsibility per function
def sanitize_input(text: str, max_len: int = 2000) -> str:
    """Sanitize user input for safe inclusion in task descriptions."""
    if not text:
        return ""
    text = str(text)
    text = ''.join(char for char in text if char >= ' ' or char in '\n\t')
    return text[:max_len]
```

### 2. Open-Closed Principle (OCP)

> "Software entities should be open for extension, but closed for modification"

Add new features WITHOUT changing existing code. Use configuration and composition over modification.

```python
# BAD - Must modify function for new platforms
def create_event(platform: str, details: dict):
    if platform == "luma":
        return create_luma_event(details)
    elif platform == "meetup":
        return create_meetup_event(details)
    # New platform = code change every time

# GOOD - Extensible via configuration
PLATFORM_RECIPES = {
    "luma": "rcp_mXyFyALaEsQF",
    "meetup": "rcp_kHJoI1WmR3AR",
    "partiful": "rcp_bN7jRF5P_Kf0",
    # To add new platform: just extend this dict
}

def create_event(platform: str, details: dict):
    recipe_id = PLATFORM_RECIPES[platform]
    return execute_recipe(recipe_id, details)
```

### 3. Liskov Substitution Principle (LSP)

> "Subtypes must be substitutable for their base types without altering correctness"

Implementations must honor the contract of the base type. Consumers shouldn't need to know the specific implementation.

### 4. Interface Segregation Principle (ISP)

> "Clients should not be forced to depend on interfaces they don't use"

Many specific interfaces > one general-purpose interface. Avoid "fat" interfaces that force implementing unused methods.

### 5. Dependency Inversion Principle (DIP)

> "Depend on abstractions, not concretions"

High-level modules shouldn't depend on low-level implementation details. Enables testing and swapping implementations.

```python
# BAD - Depends on concrete implementation
class EventCreator:
    def __init__(self):
        self.api_key = os.environ["COMPOSIO_API_KEY"]  # Tight coupling!

# GOOD - Inject dependencies
class EventCreator:
    def __init__(self, api_key: str):
        self.api_key = api_key  # Testable, swappable
```

### Code Review Checklist

- [ ] Does this component have a single, clear purpose? (SRP)
- [ ] Can I add new behavior without modifying existing code? (OCP)
- [ ] Can I substitute different implementations without breaking consumers? (LSP)
- [ ] Are interfaces minimal and focused? (ISP)
- [ ] Am I depending on abstractions, not concrete types? (DIP)

**BALANCE**: Don't over-engineer. For simple utilities, pragmatism > purity.

---

## KISS Principle (Keep It Simple, Stupid)

**CORE PRINCIPLE**: Simplicity should be a key design goal; unnecessary complexity is the enemy of reliability and maintainability.

### Key Tenets

1. **Readable over Clever**: Code that any developer can understand beats elegant one-liners
2. **Explicit over Implicit**: Clear intentions trump magic behavior
3. **Do One Thing Well**: Avoid multi-purpose functions that try to handle every case
4. **Avoid Premature Abstraction**: Wait for 3+ use cases before abstracting
5. **Avoid Premature Optimization**: Simple first, optimize when proven necessary

### Decision Metric

> "Can the next engineer accurately predict behavior and modify it safely?"

### Objective KISS Metrics

| Metric | Threshold | Action |
|--------|-----------|--------|
| Function length | > 30 lines | Consider splitting |
| Cyclomatic complexity | > 15 | Refactor required |
| Nesting depth | > 3 levels | Flatten with early returns |
| Parameters | > 8 | Consider parameter object |
| File length | > 500 lines | Consider module split |

### Patterns

```python
# BAD - Clever but hard to understand
def process(d): return {k: v.strip().lower() for k, v in d.items() if v and isinstance(v, str) and not k.startswith('_')}

# GOOD - KISS approach
def normalize_data(data: dict[str, str]) -> dict[str, str]:
    """Normalize string values in data dict."""
    result = {}
    for key, value in data.items():
        if key.startswith('_'):
            continue
        if not isinstance(value, str):
            continue
        result[key] = value.strip().lower()
    return result
```

### Anti-Patterns to Avoid

```python
# BAD - Unnecessary abstraction for single use case
class SingletonConfigManagerFactoryProvider:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

# GOOD - Just use the value directly
CONFIG = {"browser_provider": "hyperbrowser", "max_steps": 25}

# BAD - Clever ternary chains
result = a if x else b if y else c if z else d

# GOOD - Clear conditionals
if x:
    result = a
elif y:
    result = b
elif z:
    result = c
else:
    result = d
```

---

## Pure Functions

**CORE PRINCIPLE**: Functions should be deterministic transformations with no side effects--output depends ONLY on inputs.

### Two Strict Requirements

1. **Deterministic**: Same inputs -> same output (always, every time)
2. **No Side Effects**: No mutation, no I/O, no external state modification

### What Makes a Function Impure

| Impurity | Example | How to Fix |
|----------|---------|------------|
| Global state | Reading/writing module-level variables | Pass as parameters |
| Mutation | Modifying input parameters | Return new objects |
| I/O operations | `print()`, file read/write, network | Push to boundaries |
| Non-determinism | `datetime.now()`, `random.random()` | Inject as parameters |
| External calls | Database queries, API calls | Push to boundaries |

### Pattern: Functional Core, Imperative Shell

```python
# PURE CORE - Business logic as pure functions
def build_task_description(title: str, date: str, time: str, location: str, description: str) -> str:
    """Pure: deterministic string construction from inputs."""
    return f"""Create an event with these details:
    Title: {title}
    Date: {date}
    Time: {time}
    Location: {location}
    Description: {description}"""

def determine_primary_url(luma_url: str, meetup_url: str, partiful_url: str) -> str:
    """Pure: deterministic URL priority selection."""
    return luma_url or meetup_url or partiful_url or ""

# IMPERATIVE SHELL - Side effects at boundaries
def run_event_creation(event_details: dict) -> dict:
    """Impure shell: I/O at boundaries, pure core for logic."""
    # Side effect: API call
    result, error = run_composio_tool("BROWSER_TOOL_CREATE_TASK", {
        "task": build_task_description(**event_details),  # Pure core
    })

    # Pure core
    primary_url = determine_primary_url(
        result.get("luma_url", ""),
        result.get("meetup_url", ""),
        result.get("partiful_url", ""),
    )

    # Side effect: logging
    print(f"Primary URL: {primary_url}")

    return {"event_url": primary_url, "status": "done"}
```

### Decision Rules

| Scenario | Recommendation |
|----------|----------------|
| Business logic / transformations | **Default to pure** |
| Validation rules | **Default to pure** |
| Data formatting / mapping | **Default to pure** |
| I/O operations (API calls, browser tools) | Push to boundaries |
| Logging / metrics | Push to boundaries |
| Making it pure adds excessive wiring | Consider contained side effect |

### KISS + Pure Functions Synergy

Pure functions ARE KISS applied to function design--they eliminate the complexity of tracking state changes and side effects.

> **KISS is the goal (minimize complexity); pure functions are one of the best tools to achieve it--so long as the purity itself doesn't add more complexity than it removes.**

When purity increases ceremony (excessive parameter threading, complex type gymnastics), KISS may prefer a small, explicit side effect.

### Code Review Checklist

- [ ] Can this function be pure? (no external state needed?)
- [ ] Are side effects pushed to boundaries?
- [ ] Would making this pure add more complexity than it removes?
- [ ] Is the simplest solution also the correct one?
- [ ] Can the next engineer predict behavior and modify safely?
