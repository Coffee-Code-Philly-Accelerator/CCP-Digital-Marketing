# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CCP Digital Marketing is an automated event creation and social media promotion system for Coffee Code Philly Accelerator. It uses Rube MCP (Composio) to orchestrate workflows across multiple platforms.

**Two-phase workflow:**
1. **Event Creation** - Creates events on Luma, Meetup, and Partiful using browser automation (these platforms lack public APIs)
2. **Social Promotion** - Posts to Twitter, LinkedIn, Instagram, Facebook, and Discord using direct API integrations

## Key Recipes

| Recipe | ID | Purpose |
|--------|-----|---------|
| Create Event | `rcp_xvediVZu8BzW` | Browser automation for Luma, Meetup, Partiful |
| Social Promotion | `rcp_zBzqs2LO-miP` | API-based posting to 5 social platforms |

## Architecture

### Recipe Code Structure

Recipe files in `recipes/` follow this pattern:
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

# All inputs via os.environ.get()
event_title = os.environ.get("event_title")

# Use run_composio_tool() for API calls
result, error = run_composio_tool("TOOL_NAME", {args})

# Use invoke_llm() for AI content generation
response, error = invoke_llm("prompt")

# Final output is just the variable name
output = {...}
output
```

### Browser Automation Tools

- `BROWSER_TOOL_NAVIGATE` - Navigate to URL, returns pageSnapshot
- `BROWSER_TOOL_PERFORM_WEB_TASK` - AI agent fills forms based on prompt
- `BROWSER_TOOL_FETCH_WEBPAGE` - Get current page state

### Social API Tools

- `TWITTER_CREATION_OF_A_POST`
- `LINKEDIN_GET_CURRENT_USER_PROFILE` / `LINKEDIN_CREATE_LINKED_IN_POST`
- `INSTAGRAM_USERS_GET_LOGGED_IN_USER_INFO` / `INSTAGRAM_MEDIA_POST_MEDIA`
- `FACEBOOK_CREATE_PAGE_POST`
- `DISCORD_SEND_MESSAGE`

### AI Tools

- `GEMINI_GENERATE_IMAGE` - Generates promotional images (model: imagen-3.0-generate-002)
- `invoke_llm()` - Generates platform-specific content

## Running Recipes

### Via Python Client

```bash
# Set API key
export COMPOSIO_API_KEY='your-key'

# Create event
python scripts/recipe_client.py create-event \
  --title "Event Name" \
  --date "January 25, 2025" \
  --time "6:00 PM EST" \
  --location "Venue" \
  --description "Description" \
  --meetup-url "https://meetup.com/your-group"

# Promote event
python scripts/recipe_client.py promote \
  --title "Event Name" \
  --date "January 25, 2025" \
  --time "6:00 PM EST" \
  --location "Venue" \
  --description "Description" \
  --event-url "https://lu.ma/abc123"

# Full workflow (create + promote)
python scripts/recipe_client.py full-workflow [same args as above]
```

### Via Rube MCP Tools

```python
RUBE_EXECUTE_RECIPE(
    recipe_id="rcp_xvediVZu8BzW",
    input_data={"event_title": "...", ...}
)
```

## Status Codes

| Status | Meaning | Action |
|--------|---------|--------|
| `PUBLISHED` | Success | None |
| `NEEDS_AUTH` | Browser session expired | Log in manually, re-run |
| `NEEDS_REVIEW` | Submit uncertain | Check platform manually |
| `FAILED` | Error occurred | Check error message |
| `SKIPPED` | Intentionally skipped | Via skip_platforms param |

## Common Patterns

### Auth Detection
```python
AUTH_PATTERNS = ["sign in", "log in", "login", "verification code", "2fa"]
def check_needs_auth(page_content):
    return any(p in page_content.lower() for p in AUTH_PATTERNS)
```

### Nested Data Extraction
Composio responses often double-nest data:
```python
data = result.get("data", {})
if "data" in data:
    data = data["data"]
```

### Skip Platforms
Use `skip_platforms` parameter to bypass problematic platforms:
```python
{"skip_platforms": "meetup,facebook"}
```

## Dependencies

- `requests` - Required for recipe_client.py
- `python-dotenv` - Optional for .env file support
