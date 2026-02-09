# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CCP Digital Marketing automates event creation and social media promotion for Coffee Code Philly Accelerator using Rube MCP (Composio).

**Two-phase workflow:**
1. **Event Creation** - Browser automation for Luma, Meetup, Partiful (no public APIs)
2. **Social Promotion** - Direct API integrations for Twitter, LinkedIn, Instagram, Facebook, Discord

## Development Commands

### Python Package (ccp_marketing/)

```bash
cd ccp_marketing

# Install with dev dependencies
pip install -e ".[dev]"

# Run all tests with coverage
pytest

# Run single test file
pytest tests/test_state_machine.py

# Run single test
pytest tests/test_state_machine.py::test_state_transitions -v

# Type checking
mypy src/ccp_marketing

# Linting
ruff check src/ccp_marketing
ruff check --fix src/ccp_marketing
```

Note: `pyproject.toml` configures pytest with `addopts = "-v --cov=src/ccp_marketing --cov-report=term-missing"`, so coverage runs automatically. The venv lives at `ccp_marketing/.venv/`.

### Recipe Client (scripts/)

```bash
pip install -r scripts/requirements.txt
export COMPOSIO_API_KEY='your-key'

python scripts/recipe_client.py create-event \
  --title "Event Name" --date "January 25, 2025" --time "6:00 PM EST" \
  --location "Venue" --description "Description" \
  --meetup-url "https://meetup.com/your-group"

python scripts/recipe_client.py promote \
  --title "Event Name" --date "January 25, 2025" --time "6:00 PM EST" \
  --location "Venue" --description "Description" \
  --event-url "https://lu.ma/abc123"

python scripts/recipe_client.py full-workflow [same args]
python scripts/recipe_client.py info rcp_xvediVZu8BzW
```

### CLI (after pip install)

```bash
ccp-marketing create-event --title "..." --date "..." --time "..." --location "..." --description "..."
ccp-marketing promote --title "..." --event-url "..." [same event args]
ccp-marketing full-workflow --title "..." [same event args]
ccp-marketing info
```

## Architecture

### Two-Layer Design

**Layer 1: Rube MCP Recipes** (`recipes/`) - Self-contained Python scripts for Composio's Rube MCP runtime. These use `os.environ.get()` for inputs, `run_composio_tool()` for APIs, `invoke_llm()` for AI. Output is a bare variable (no return statement). Include mock implementations for local testing.

**Layer 2: Python Package** (`ccp_marketing/src/ccp_marketing/`) - Full SDK-based implementation. Key modules:

- `core/` - `ComposioClient` (wraps Composio SDK with retry + nested data extraction), `Config` (dataclass, all values from env vars with `CCP_` prefix), custom exceptions
- `models/` - `EventData` (Pydantic), `PlatformResult`, `Status` enum, result types
- `state_machine/` - `EventState` enum (24 states), `StateConfig` (per-state retries/backoff), `EventCreationStateMachine` (drives browser automation through state transitions)
- `adapters/` - `BasePlatformAdapter` (ABC) with `LumaAdapter`, `MeetupAdapter`, `PartifulAdapter`. Each provides platform-specific URLs, form-fill prompts per state, success URL checks, and post-submit handling
- `social/` - `BaseSocialPoster` (ABC) with poster per platform. `SocialPromotionManager` coordinates parallel posting via `ThreadPoolExecutor`
- `ai/` - `ImageGenerator` (Gemini), `CopyGenerator` (LLM-based platform-specific copy)
- `workflows/` - `EventCreationWorkflow`, `SocialPromotionWorkflow`, `FullWorkflow` orchestrate the above
- `cli/` - Typer app with `create-event`, `promote`, `full-workflow`, `info`, `version` commands

### State Machine (Event Creation)

The core abstraction for browser automation. Each platform adapter provides prompts for each state, and the state machine drives transitions:

**v1 flow (14 states):** INIT -> CHECK_DUPLICATE -> NAVIGATE -> AUTH_CHECK -> FILL_TITLE -> FILL_DATE -> FILL_TIME -> FILL_LOCATION -> FILL_DESCRIPTION -> VERIFY_FORM -> SUBMIT -> POST_SUBMIT -> VERIFY_SUCCESS -> DONE

**v2 flow (19 states):** Adds UPLOAD_IMAGE, SET_TICKETS, ADD_COHOSTS, SET_RECURRING, SET_INTEGRATIONS between FILL_DESCRIPTION and VERIFY_FORM.

**Terminal states:** DONE, FAILED, NEEDS_AUTH, DUPLICATE, SKIPPED. **Pause state:** AWAIT_2FA (waiting for manual 2FA).

Each state has configurable `max_retries` (1-3) and exponential backoff with jitter. SUBMIT has only 1 retry to avoid duplicates.

### Key Design Decisions

- **Sequential event creation** (not parallel) for browser automation stability
- **Parallel social posting** via ThreadPoolExecutor with `max_workers` (default 5)
- `ComposioClient._extract_data()` handles Composio's double-nested `{data: {data: {...}}}` response pattern
- Adapters are responsible for all platform-specific logic; the state machine is platform-agnostic
- `MeetupAdapter.get_create_url()` dynamically builds URL from `group_url` (unlike Luma/Partiful which have static create URLs)

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
| Social Promotion | `rcp_zBzqs2LO-miP` | Parallel API posting to 5 social platforms |
| Create Event (legacy) | `rcp_xvediVZu8BzW` | Old state machine approach (deprecated - times out) |

All event creation recipes use `BROWSER_TOOL_CREATE_TASK` (single AI browser agent call + polling) instead of the old multi-step state machine with sequential `NAVIGATE`/`PERFORM_WEB_TASK`/`FETCH_WEBPAGE` calls that exceeded the 4-minute Rube runtime timeout.

## Composio Tool Reference

### Browser Automation (v2 - AI Agent)
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
- `LINKEDIN_GET_CURRENT_USER_PROFILE` / `LINKEDIN_CREATE_LINKED_IN_POST`
- `INSTAGRAM_USERS_GET_LOGGED_IN_USER_INFO` / `INSTAGRAM_MEDIA_POST_MEDIA`
- `FACEBOOK_CREATE_PAGE_POST`
- `DISCORD_SEND_MESSAGE`

### AI
- `GEMINI_GENERATE_IMAGE` - Image generation (model: gemini-2.5-flash-image)
- `invoke_llm()` - LLM content generation (recipe runtime only)

## Platform-Specific Quirks

| Platform | Issue | Mitigation |
|----------|-------|------------|
| Luma | React date picker | Extra 1.5s wait after date input (`post_step_wait`) |
| Meetup | Anti-bot detection | 2s `inter_step_delay` between all form actions |
| Partiful | Share modal after creation | `post_submit_action()` dismisses modal before URL extraction |
| All | Session expiry | State machine reports NEEDS_AUTH terminal state |

## Common Patterns

### Nested Data Extraction
Composio responses often double-nest. `ComposioClient._extract_data()` handles this, but in recipes:
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
Both CLI and recipes accept skip lists: `--skip "meetup,facebook"` or `{"skip_platforms": "meetup,facebook"}`

## Status Codes

| Status | Meaning | Action |
|--------|---------|--------|
| `PUBLISHED`/`DONE` | Success | None |
| `NEEDS_AUTH` | Browser session expired | Log in manually, re-run |
| `NEEDS_REVIEW` | Submit uncertain | Check platform manually |
| `FAILED` | Error occurred | Check error message |
| `SKIPPED` | Intentionally skipped | Via skip_platforms param |
| `DUPLICATE` | Event already exists | Verify or skip |
| `PAUSED_2FA` | Waiting for 2FA | Complete 2FA manually, resume with `resume=true` |

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `COMPOSIO_API_KEY` | Yes | - | Composio API authentication |
| `CCP_COMPOSIO_API_BASE` | No | `https://backend.composio.dev/api/v1` | Composio API base URL |
| `CCP_DISCORD_CHANNEL_ID` | No | (empty) | Default Discord channel ID |
| `CCP_FACEBOOK_PAGE_ID` | No | (empty) | Default Facebook page ID |
| `CCP_MEETUP_GROUP_URL` | No | (empty) | Default Meetup group URL |
| `CCP_LOG_LEVEL` | No | INFO | Logging level |
| `CCP_MAX_WORKERS` | No | 5 | Parallel social posting workers |
| `CCP_DEFAULT_TIMEOUT` | No | 60.0 | Default API timeout (seconds) |
| `CCP_MAX_RETRIES` | No | 3 | Max retry attempts |
| `CCP_BROWSER_ACTION_DELAY` | No | 0.5 | Delay between browser actions |
| `CCP_IMAGE_MODEL` | No | gemini-2.5-flash-image | AI image generation model |
| `CCP_REDACT_SENSITIVE` | No | true | Redact sensitive data in logs |

**Override Precedence:** CLI parameters > Environment variables > Defaults

## Via Rube MCP Tools

```python
RUBE_EXECUTE_RECIPE(
    recipe_id="rcp_xvediVZu8BzW",
    input_data={"event_title": "...", "event_date": "...", ...}
)
```

## Claude Code Skills

Skills are defined in `.claude/skills/`. Each wraps a `RUBE_EXECUTE_RECIPE` call. Event creation recipes use `BROWSER_TOOL_CREATE_TASK` (single AI browser agent) and return a `live_url` for real-time watching.

| Skill | Directory | Recipe ID | Purpose |
|-------|-----------|-----------|---------|
| Luma Create | `luma-create/` | `rcp_mXyFyALaEsQF` | Create event on Luma via browser automation |
| Meetup Create | `meetup-create/` | `rcp_kHJoI1WmR3AR` | Create event on Meetup via browser automation |
| Partiful Create | `partiful-create/` | `rcp_bN7jRF5P_Kf0` | Create event on Partiful via browser automation |
| Social Promote | `social-promote/` | `rcp_zBzqs2LO-miP` | Post event to Twitter, LinkedIn, Instagram, Facebook, Discord |
| Full Workflow | `full-workflow/` | All of the above | Orchestrate: create on all platforms, then promote on social media |

**Chaining:** The social-promote and full-workflow skills accept an optional `image_url` input. When provided (e.g., from a prior event creation), the social promotion recipe skips Gemini image generation and reuses the existing image.
