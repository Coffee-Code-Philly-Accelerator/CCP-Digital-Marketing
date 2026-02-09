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
| Social Promotion | `rcp_zBzqs2LO-miP` | Parallel API posting to 5 social platforms |

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
| Social Promote | `social-promote/` | `rcp_zBzqs2LO-miP` | Post event to Twitter, LinkedIn, Instagram, Facebook, Discord |
| Full Workflow | `full-workflow/` | All of the above | Orchestrate: create on all platforms, then promote on social media |
| Auth Setup | `auth-setup/` | N/A (direct tool calls) | Set up Hyperbrowser persistent auth profiles |

**Chaining:** The social-promote and full-workflow skills accept an optional `image_url` input. When provided (e.g., from a prior event creation), the social promotion recipe skips Gemini image generation and reuses the existing image.
