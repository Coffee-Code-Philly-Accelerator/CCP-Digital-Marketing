# meetup-create

Create events on Meetup using browser automation.

## Invocation

This skill is triggered when the user wants to:
- "Create an event on Meetup"
- "Publish to Meetup"
- "Make a Meetup event"
- "Add event to Meetup.com"

## Required Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| `event_title` | string | Event name (max 200 chars) |
| `event_date` | string | Date in natural language, e.g., "January 25, 2025" |
| `event_time` | string | Time with timezone, e.g., "6:00 PM EST" |
| `event_location` | string | Venue name or address |
| `event_description` | string | Full event description (apostrophes are auto-converted to curly quotes) |

**Note**: The Meetup group URL defaults to `https://www.meetup.com/code-coffee-philly` but can be overridden via the `meetup_group_url` input parameter.

## Optional Inputs

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `meetup_group_url` | string | `https://www.meetup.com/code-coffee-philly` | Override the Meetup group URL |
| `event_image_url` | string | `""` | URL of image to upload as event featured photo |

## Execution (Two-Phase)

### Phase 1: Start the browser task

```
RUBE_EXECUTE_RECIPE(
    recipe_id="rcp_kHJoI1WmR3AR",
    input_data={
        "event_title": "<title>",
        "event_date": "<date>",
        "event_time": "<time>",
        "event_location": "<location>",
        "event_description": "<description>",
        "event_image_url": "<optional>"
    }
)
```

This returns immediately with `task_id`, `live_url`, `provider`, and `poll_tool`. Share the `live_url` with the user so they can watch the browser.

### Phase 2: Poll for completion

After the recipe returns, read the `provider` and `poll_tool` fields from the Phase 1 output to determine which polling tool and status values to use.

**If `provider` is `"hyperbrowser"`:**

```
RUBE_MULTI_EXECUTE_TOOL(
    tool_slug="HYPERBROWSER_GET_BROWSER_USE_TASK_STATUS",
    arguments={"task_id": "<task_id from Phase 1>"}
)
```

Check the response:
- `status: "completed"` → done, check result for event URL
- `status: "running"` → still running, poll again in 10-15 seconds
- `status: "failed"` → task failed, report error

**If `provider` is `"browser_tool"`:**

```
RUBE_MULTI_EXECUTE_TOOL(
    tool_slug="BROWSER_TOOL_WATCH_TASK",
    arguments={"taskId": "<task_id from Phase 1>"}
)
```

Check the response:
- `status: "finished"` → check `current_url` against success pattern
- `status: "started"` → still running, poll again in 10-15 seconds
- `status: "stopped"` → task was aborted, report failure

**Success URL pattern**: URL contains `meetup.com` and `/events/` but NOT `/create`

## Output (Phase 1)

```json
{
  "platform": "meetup",
  "status": "running",
  "task_id": "<use for polling>",
  "session_id": "<browser session>",
  "live_url": "https://...",
  "event_url": "",
  "error": null,
  "provider": "hyperbrowser",
  "poll_tool": "HYPERBROWSER_GET_BROWSER_USE_TASK_STATUS",
  "poll_args_key": "task_id",
  "success_url_pattern": "meetup.com/*/events/* (not /create)"
}
```

## Platform Notes

- **Architecture**: Fire-and-forget recipe + caller-side polling (avoids 4-min Rube timeout)
- **Browser Provider**: Defaults to Hyperbrowser with persistent profiles for saved auth. Falls back to Composio browser_tool if configured. Requires auth-setup skill to be run first for Hyperbrowser.
- **Image Upload**: When `event_image_url` is provided, the browser agent uploads it as a "Featured photo" before publishing (with 2s anti-bot waits). Gracefully skips if no URL import option is available.
- **Anti-Bot Delays**: Meetup has aggressive bot detection. Task instructions include 2s waits between each form action.
- **Group URL**: Defaults to `https://www.meetup.com/code-coffee-philly`. Override via `meetup_group_url` input.
- **Apostrophes**: Automatically converted to curly quotes (\u2019) to avoid Rube env var injection issues. No manual workaround needed.
- **Session Expiry**: If using Hyperbrowser, re-run auth-setup skill with existing profile_id. If using browser_tool, re-authenticate via Composio connected accounts.
