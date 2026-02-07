# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CCP Digital Marketing automates event creation and social media promotion for Coffee Code Philly Accelerator using Rube MCP (Composio).

**Two-phase workflow:**
1. **Event Creation** - Browser automation for Luma, Meetup, Partiful (no public APIs)
2. **Social Promotion** - Direct API integrations for Twitter, LinkedIn, Instagram, Facebook, Discord

## Key Recipes

| Recipe | ID | Purpose |
|--------|-----|---------|
| Create Event | `rcp_xvediVZu8BzW` | State machine browser automation for 3 event platforms |
| Create Event v2 | (pending upload) | Multi-tenant, checkpoint-enabled with full features |
| Social Promotion | `rcp_zBzqs2LO-miP` | Parallel API posting to 5 social platforms |

## Architecture

### Two-Layer Design

**Layer 1: Rube MCP Recipes** (`recipes/`)
- Self-contained Python scripts for Composio's Rube MCP runtime
- Use `os.environ.get()` for inputs, `run_composio_tool()` for APIs, `invoke_llm()` for AI
- Include mock implementations for local testing
- Output as bare variable (no return statement)

**Layer 2: Python Package** (`ccp_marketing/`)
- Full SDK-based implementation with modular architecture
- Adapters for each platform, state machine for event creation
- CLI via Typer, tests via pytest

### State Machine (Event Creation)

**Basic flow (v1 - 14 states):**
```
INIT → CHECK_DUPLICATE → NAVIGATE → AUTH_CHECK → FILL_TITLE → FILL_DATE →
FILL_TIME → FILL_LOCATION → FILL_DESCRIPTION → VERIFY_FORM → SUBMIT →
POST_SUBMIT → VERIFY_SUCCESS → DONE
```

**Extended flow (v2 - 19 states):**
```
INIT → CHECK_DUPLICATE → NAVIGATE → AUTH_CHECK →
FILL_TITLE → FILL_DATE → FILL_TIME → FILL_LOCATION → FILL_DESCRIPTION →
UPLOAD_IMAGE → SET_TICKETS → ADD_COHOSTS → SET_RECURRING → SET_INTEGRATIONS →
VERIFY_FORM → SUBMIT → POST_SUBMIT → VERIFY_SUCCESS → DONE
```

**Terminal States:** DONE, FAILED, NEEDS_AUTH, DUPLICATE, SKIPPED, AWAIT_2FA

Each state has configurable retries (1-2) and exponential backoff with jitter.

## Development Commands

### Python Package (ccp_marketing/)

```bash
cd ccp_marketing

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests with coverage
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

### Recipe Client (scripts/)

```bash
# Install dependencies
pip install -r scripts/requirements.txt

# Set API key
export COMPOSIO_API_KEY='your-key'

# Create event
python scripts/recipe_client.py create-event \
  --title "Event Name" --date "January 25, 2025" --time "6:00 PM EST" \
  --location "Venue" --description "Description" \
  --meetup-url "https://meetup.com/your-group"

# Promote event
python scripts/recipe_client.py promote \
  --title "Event Name" --date "January 25, 2025" --time "6:00 PM EST" \
  --location "Venue" --description "Description" \
  --event-url "https://lu.ma/abc123"

# Full workflow
python scripts/recipe_client.py full-workflow [same args]

# Get recipe info
python scripts/recipe_client.py info rcp_xvediVZu8BzW
```

## Recipe Code Pattern

```python
"""
RECIPE: Name
RECIPE ID: rcp_xxxxx

VERSION HISTORY:
API LEARNINGS:
KNOWN ISSUES:
"""

import os
from datetime import datetime

# Inputs via environment
event_title = os.environ.get("event_title")

# API calls
result, error = run_composio_tool("TOOL_NAME", {args})

# AI content
response, error = invoke_llm("prompt")

# Output (bare variable, no return)
output = {...}
output
```

## Composio Tool Reference

### Browser Automation
- `BROWSER_TOOL_NAVIGATE` - Navigate to URL, returns pageSnapshot
- `BROWSER_TOOL_PERFORM_WEB_TASK` - AI agent fills forms via natural language prompt
- `BROWSER_TOOL_FETCH_WEBPAGE` - Get current page state
- `BROWSER_TOOL_TAKE_SCREENSHOT` - Capture screenshot (useful for debugging)

### Social APIs
- `TWITTER_CREATION_OF_A_POST`
- `LINKEDIN_GET_CURRENT_USER_PROFILE` / `LINKEDIN_CREATE_LINKED_IN_POST`
- `INSTAGRAM_USERS_GET_LOGGED_IN_USER_INFO` / `INSTAGRAM_MEDIA_POST_MEDIA`
- `FACEBOOK_CREATE_PAGE_POST`
- `DISCORD_SEND_MESSAGE`

### AI
- `GEMINI_GENERATE_IMAGE` - Generates images (model: imagen-3.0-generate-002)
- `invoke_llm()` - LLM content generation (available in recipe runtime)

## Platform-Specific Quirks

| Platform | Issue | Mitigation |
|----------|-------|------------|
| Luma | React date picker | Extra 1.5s wait after date input |
| Meetup | Anti-bot detection | 2s delays between form actions |
| Partiful | Share modal after creation | Dismiss modal before extracting URL |
| All | Session expiry | Reports NEEDS_AUTH status |

## Common Patterns

### Nested Data Extraction
Composio responses often double-nest:
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
```python
{"skip_platforms": "meetup,facebook"}
```

## Status Codes

| Status | Meaning | Action |
|--------|---------|--------|
| `PUBLISHED` | Success | None |
| `NEEDS_AUTH` | Browser session expired | Log in manually, re-run |
| `NEEDS_REVIEW` | Submit uncertain | Check platform manually |
| `FAILED` | Error occurred | Check error message |
| `SKIPPED` | Intentionally skipped | Via skip_platforms param |
| `DUPLICATE` | Event already exists | Verify or skip |

## Via Rube MCP Tools

```python
RUBE_EXECUTE_RECIPE(
    recipe_id="rcp_xvediVZu8BzW",
    input_data={"event_title": "...", ...}
)
```

## V2 Architecture (Multi-Tenant)

The v2 system adds multi-tenant support, checkpoint-based resume, and full event features.

### Package Structure (ccp_marketing/src/ccp_marketing/)

```
sessions/           # Multi-tenant session management
├── registry.py     # SessionRegistry - per-tenant, per-platform sessions
└── storage.py      # File/memory storage backends (~/.ccp_marketing/sessions/)

state_machine/
├── states.py       # 19 states including feature states (UPLOAD_IMAGE, etc.)
└── checkpoint.py   # Checkpoint save/load for resume capability

browser/
├── element_resolver.py  # Multi-strategy element targeting (CSS, text, ARIA, AI)
├── tactical.py          # Hybrid execution (explicit + AI-assisted fallback)
└── verification.py      # Auth detection, 2FA detection, success verification

adapters/
├── base_v2.py      # Extended base adapter with feature support
├── luma_v2.py      # Luma with 12 element targets, 1.5s date picker delay
├── meetup_v2.py    # Meetup with 2s anti-bot delays, group-specific URL
└── partiful_v2.py  # Partiful with share modal dismissal

models/
└── features.py     # TicketConfig, RecurringConfig, CoHostConfig, IntegrationConfig
```

### Session States

| Status | Meaning |
|--------|---------|
| `WARM` | Active, authenticated, ready |
| `COLD` | Never initialized |
| `NEEDS_AUTH` | Login required |
| `PAUSED_2FA` | Waiting for manual 2FA |
| `EXPIRED` | Session timed out |

### 2FA Pause/Resume Flow

1. Automation detects 2FA prompt → returns `PAUSED_2FA` with `resume_token`
2. User completes 2FA manually in browser
3. User resumes with: `resume_token=<token>` parameter
4. Workflow continues from checkpoint

### Feature Support by Platform

| Feature | Luma | Meetup | Partiful |
|---------|------|--------|----------|
| Image upload | Yes | Yes | Yes |
| Tickets | Yes | RSVP only | Yes |
| Co-hosts | Yes | Yes | Yes |
| Recurring | Yes | Yes | No |
| Integrations | Yes (Zoom, Meet) | No | Calendar only |
