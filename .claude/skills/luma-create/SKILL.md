# luma-create

Create events on Luma (lu.ma) using browser automation.

## Invocation

This skill is triggered when the user wants to:
- "Create an event on Luma"
- "Publish to lu.ma"
- "Make a Luma event"
- "Add event to Luma"

## Required Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| `event_title` | string | Event name (max 200 chars) |
| `event_date` | string | Date in natural language, e.g., "January 25, 2025" |
| `event_time` | string | Time with timezone, e.g., "6:00 PM EST" |
| `event_location` | string | Venue name or address |
| `event_description` | string | Full event description (apostrophes are auto-converted to curly quotes) |

## Optional Inputs

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `luma_create_url` | string | `https://lu.ma/create` | Override the Luma create page URL |
| `event_image_url` | string | `""` | URL of image to upload as event cover photo |

## Execution (Two-Phase)

### Phase 1: Start the browser task

```
RUBE_EXECUTE_RECIPE(
    recipe_id="rcp_mXyFyALaEsQF",
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

**Success URL pattern**: URL contains `lu.ma/` but NOT `/create` or `/home`

## Output (Phase 1)

```json
{
  "platform": "luma",
  "status": "running",
  "task_id": "<use for polling>",
  "session_id": "<browser session>",
  "live_url": "https://...",
  "event_url": "",
  "error": null,
  "provider": "hyperbrowser",
  "poll_tool": "HYPERBROWSER_GET_BROWSER_USE_TASK_STATUS",
  "poll_args_key": "task_id",
  "success_url_pattern": "lu.ma/ (not /create or /home)"
}
```

## Platform Notes

- **Architecture**: Fire-and-forget recipe + caller-side polling (avoids 4-min Rube timeout)
- **Browser Provider**: Defaults to Hyperbrowser with persistent profiles for saved auth. Falls back to Composio browser_tool if configured. Requires auth-setup skill to be run first for Hyperbrowser.
- **Image Upload**: When `event_image_url` is provided, the browser agent clicks the "Add cover" button and imports from URL before publishing. Gracefully skips if no URL import option is available.
- **Date Picker**: Luma uses a React date picker; task instructions include explicit 2s waits
- **Share Modal**: After publishing, Luma may show a share modal that the browser agent dismisses
- **Apostrophes**: Automatically converted to curly quotes (\u2019) to avoid Rube env var injection issues. No manual workaround needed.
- **Session Expiry**: If using Hyperbrowser, re-run auth-setup skill with existing profile_id. If using browser_tool, re-authenticate via Composio connected accounts.
