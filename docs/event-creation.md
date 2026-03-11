# Event Creation Recipes - Detailed Documentation

## Per-Platform Recipes

| Platform | Recipe ID | Create URL |
|----------|-----------|------------|
| Luma | `rcp_mXyFyALaEsQF` | `https://lu.ma/create` |
| Meetup | `rcp_kHJoI1WmR3AR` | `https://www.meetup.com/<group>/events/create/` |
| Partiful | `rcp_bN7jRF5P_Kf0` | `https://partiful.com/create` |

## Overview

Each recipe creates an event on a single platform using browser automation. Recipes are designed to be run sequentially (one platform at a time) since browser automation sessions cannot overlap. Each recipe uses the fire-and-forget pattern: it starts an AI browser agent and returns immediately with a `task_id` for caller-side polling.

Recipes default to **Hyperbrowser** (`HYPERBROWSER_START_BROWSER_USE_TASK`) with persistent auth profiles, falling back to Composio's `BROWSER_TOOL_CREATE_TASK` when `CCP_BROWSER_PROVIDER=browser_tool` is set. Both providers use the same single-call + polling pattern.

## Why Browser Automation?

| Platform | Public API | Event Creation API | Our Approach |
|----------|------------|-------------------|--------------|
| Luma | None | None | Browser automation |
| Partiful | None | None | Browser automation |
| Meetup | GraphQL | Available | Browser for consistency |

Luma and Partiful have no public APIs, so browser automation is the only programmatic option.

## Architecture

```mermaid
flowchart TB
    subgraph Input["Step 1: Input Validation"]
        A[event_title]
        B[event_date]
        C[event_time]
        D[event_location]
        E[event_description]
    end

    subgraph Browser["Step 2: Fire-and-Forget Browser Task"]
        direction TB
        F{CCP_BROWSER_PROVIDER?}
        F -->|hyperbrowser default| G1[HYPERBROWSER_START_BROWSER_USE_TASK<br/>+ persistent profile]
        F -->|browser_tool| G2[BROWSER_TOOL_CREATE_TASK<br/>+ startUrl]
        G1 --> H1[HYPERBROWSER_GET_SESSION_DETAILS<br/>Gets live_url]
        G2 --> H2[BROWSER_TOOL_GET_SESSION<br/>Gets live_url]
    end

    subgraph Polling["Step 3: Caller-Side Polling (every 10-15s)"]
        direction TB
        I{provider?}
        I -->|hyperbrowser| J1[HYPERBROWSER_GET_BROWSER_USE_TASK_STATUS]
        I -->|browser_tool| J2[BROWSER_TOOL_WATCH_TASK]
        J1 --> K1{status?}
        K1 -->|running| J1
        K1 -->|completed| L[Done - extract event URL]
        K1 -->|failed| M[Error]
        J2 --> K2{status?}
        K2 -->|started| J2
        K2 -->|finished| L
        K2 -->|stopped| M
    end

    A & B & C & D & E --> F
    H1 & H2 --> I
```

## Input Parameters

### Required Parameters (all platforms)

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `event_title` | string | The name/title of your event | "AI Workshop: Building with Claude" |
| `event_date` | string | Date in natural language | "January 25, 2025" or "Next Saturday" |
| `event_time` | string | Time with timezone | "6:00 PM EST" or "18:00 Eastern" |
| `event_location` | string | Venue name or full address | "The Station, 3rd Floor, 1500 Sansom St, Philadelphia, PA" |
| `event_description` | string | Full event description (apostrophes auto-converted to curly quotes) | "Join us for a hands-on workshop where we'll explore..." |

### Optional Parameters (platform-specific)

| Parameter | Platform | Default | Description |
|-----------|----------|---------|-------------|
| `luma_create_url` | Luma | `https://lu.ma/create` | Override the Luma create page URL |
| `meetup_group_url` | Meetup | `https://www.meetup.com/code-coffee-philly` | Override the Meetup group URL |
| `partiful_create_url` | Partiful | `https://partiful.com/create` | Override the Partiful create page URL |

## Output Format

Each recipe returns immediately with:

```json
{
  "platform": "luma|meetup|partiful",
  "status": "running",
  "task_id": "<use for polling>",
  "session_id": "<browser session>",
  "live_url": "https://...",
  "event_url": "",
  "provider": "hyperbrowser|browser_tool",
  "poll_tool": "HYPERBROWSER_GET_BROWSER_USE_TASK_STATUS|BROWSER_TOOL_WATCH_TASK",
  "poll_args_key": "task_id|taskId",
  "error": null,
  "success_url_pattern": "<platform-specific pattern>"
}
```

### Polling Response

Use the `poll_tool` and `poll_args_key` from the recipe output to determine which tool to call.

**Hyperbrowser** (`HYPERBROWSER_GET_BROWSER_USE_TASK_STATUS`):

| Field | Description |
|-------|-------------|
| `status` | `"running"` (still running), `"completed"` (done), `"failed"` (error) |

**browser_tool** (`BROWSER_TOOL_WATCH_TASK`):

| Field | Description |
|-------|-------------|
| `status` | `"started"` (still running), `"finished"` (done), `"stopped"` (aborted) |
| `current_url` | The browser's current URL - check against success pattern |
| `is_success` | Boolean indicating if task completed successfully |
| `output` | Task output text |

### Success URL Patterns

| Platform | Success Pattern |
|----------|----------------|
| Luma | URL contains `lu.ma/` but NOT `/create` or `/home` |
| Meetup | URL contains `meetup.com` and `/events/` but NOT `/create` |
| Partiful | URL contains `partiful.com/e/` |

## Example Usage

### Create Event on Luma

```python
# Phase 1: Start the task
RUBE_EXECUTE_RECIPE(
    recipe_id="rcp_mXyFyALaEsQF",
    input_data={
        "event_title": "AI Workshop: Building with Claude",
        "event_date": "January 25, 2025",
        "event_time": "6:00 PM EST",
        "event_location": "The Station, Philadelphia",
        "event_description": "Join us for a hands-on workshop..."
    }
)
# Returns: {task_id, live_url, status: "running"}

# Phase 2: Poll for completion (use poll_tool from Phase 1 output)
# Hyperbrowser (default):
RUBE_MULTI_EXECUTE_TOOL(
    tool_slug="HYPERBROWSER_GET_BROWSER_USE_TASK_STATUS",
    arguments={"task_id": "<task_id from Phase 1>"}
)
# Returns: {status: "running"|"completed"|"failed"}

# browser_tool (fallback):
RUBE_MULTI_EXECUTE_TOOL(
    tool_slug="BROWSER_TOOL_WATCH_TASK",
    arguments={"taskId": "<task_id from Phase 1>"}
)
# Returns: {status: "started"|"finished"|"stopped", current_url: "..."}
```

### Create Event on Meetup

```python
RUBE_EXECUTE_RECIPE(
    recipe_id="rcp_kHJoI1WmR3AR",
    input_data={
        "event_title": "AI Workshop: Building with Claude",
        "event_date": "January 25, 2025",
        "event_time": "6:00 PM EST",
        "event_location": "The Station, Philadelphia",
        "event_description": "Join us for a hands-on workshop...",
        "meetup_group_url": "https://www.meetup.com/code-coffee-philly"
    }
)
```

### Create Event on Partiful

```python
RUBE_EXECUTE_RECIPE(
    recipe_id="rcp_bN7jRF5P_Kf0",
    input_data={
        "event_title": "AI Workshop: Building with Claude",
        "event_date": "January 25, 2025",
        "event_time": "6:00 PM EST",
        "event_location": "The Station, Philadelphia",
        "event_description": "Join us for a hands-on workshop..."
    }
)
```

## Platform-Specific Details

### Luma (lu.ma)

**Create URL:** `https://lu.ma/create`

**Login Methods:**
- Google SSO
- Email/Password
- Magic Link

**Form Fields Filled:**
- Event Title
- Date/Time Picker
- Location (with Google Places autocomplete)
- Description (rich text)
- Cover Image (optional)

**Known Quirks:**
- React-based UI with dynamic elements
- Date picker requires specific interaction pattern - task instructions include explicit 2s waits
- Cover image upload needs URL (not file upload)

### Meetup

**Create URL:** `https://www.meetup.com/<group>/events/create/`

**Login Methods:**
- Email/Password
- Google SSO
- Facebook SSO
- Apple SSO

**Form Fields Filled:**
- Event Title
- Date and Time
- Venue/Location (with venue search)
- Description (rich text editor)
- Event Type
- Photo (optional)

**Known Quirks:**
- Complex multi-step form
- Aggressive anti-bot detection - task instructions include 2s waits between form actions
- Venue search can be slow
- Rich text editor has specific formatting
- Must be an organizer of the group
- Group URL defaults to `https://www.meetup.com/code-coffee-philly`, overridable via `meetup_group_url`

### Partiful

**Create URL:** `https://partiful.com/create`

**Login Methods:**
- Phone Number + SMS
- Google SSO

**Form Fields Filled:**
- Event Title
- Date/Time
- Location
- Description
- Cover Image
- RSVP Options

**Known Quirks:**
- Mobile-first design
- Emoji-friendly platform
- Theme/Effect customization available
- Guest capacity settings
- Share modal after creation - browser agent dismisses it before URL extraction
- Recurring events NOT supported

## Session Management

### Hyperbrowser (Default)

Hyperbrowser uses persistent profiles that save login cookies across sessions. One-time setup per platform:

1. **Initial Setup:** Run the **auth-setup** skill for each platform (Luma, Meetup, Partiful)
2. **Login:** Open the live URL provided and complete Google OAuth login
3. **Save Profile:** Add the profile ID to your `.env` file (`CCP_LUMA_PROFILE_ID`, etc.)
4. **Sessions Persist:** Subsequent recipe runs reuse the saved profile with cookies
5. **Re-Auth:** If a recipe returns `NEEDS_AUTH`, re-run auth-setup with the existing `profile_id` to re-login

```mermaid
stateDiagram-v2
    [*] --> NoProfile
    NoProfile --> ProfileCreated: auth-setup skill (creates profile)
    ProfileCreated --> LoggedIn: User logs in via liveUrl
    LoggedIn --> SessionActive: Cookies saved to profile
    SessionActive --> SessionActive: Multiple recipe runs
    SessionActive --> SessionExpired: Cookies expire
    SessionExpired --> LoggedIn: Re-run auth-setup (same profile_id)
```

### browser_tool (Fallback)

When `CCP_BROWSER_PROVIDER=browser_tool`, sessions are ephemeral (no auth persistence):

1. **Initial Login:** Log in via Composio connected accounts
2. **Session Persists:** Within the same browser session
3. **Session Expires:** Re-authenticate via Composio dashboard

## Best Practices

1. **Test Login First:** Before running for real events, verify you're logged into all platforms
2. **Use skip_platforms:** If one platform has issues, skip it rather than failing entirely
3. **Poll patiently:** Browser tasks can take 30-90 seconds to complete
4. **Watch the live_url:** Share with user so they can observe the browser in real time
5. **Run During Low Traffic:** Platform UIs respond better during off-peak hours
