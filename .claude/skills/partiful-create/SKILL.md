# partiful-create

Create events on Partiful using browser automation.

## Invocation

This skill is triggered when the user wants to:
- "Create an event on Partiful"
- "Publish to Partiful"
- "Make a Partiful event"
- "Add event to Partiful.com"

## Required Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| `event_title` | string | Event name (max 200 chars) |
| `event_date` | string | Date in natural language, e.g., "January 25, 2025" |
| `event_time` | string | Time with timezone, e.g., "6:00 PM EST" |
| `event_location` | string | Venue name or address |
| `event_description` | string | Full event description (max 5000 chars) |

**Note**: Recurring events are NOT supported on Partiful.

## Execution

Use the Rube MCP tool to execute the Partiful event creation recipe:

```
RUBE_EXECUTE_RECIPE(
    recipe_id="rcp_bN7jRF5P_Kf0",
    input_data={
        "event_title": "<title>",
        "event_date": "<date>",
        "event_time": "<time>",
        "event_location": "<location>",
        "event_description": "<description>"
    }
)
```

## Output

The recipe returns:

```json
{
  "platform": "partiful",
  "status": "done|needs_review|failed",
  "event_url": "https://partiful.com/e/abc123",
  "image_url": "",
  "error": null,
  "live_url": "https://..."
}
```

## Status Handling

| Status | Meaning | Action |
|--------|---------|--------|
| `done` | Event created successfully | Report event_url to user |
| `needs_review` | Task finished but URL not confirmed | Ask user to check Partiful manually |
| `failed` | Browser task error or timeout | Report error, suggest re-running |

## Live Browser Watching

The `live_url` field (when available) provides a real-time view of the browser automation. Share this with the user so they can watch the event being created.

## Platform Notes

- **Architecture**: Uses `BROWSER_TOOL_CREATE_TASK` - a single AI browser agent call that autonomously fills the form (replaces the old multi-step state machine)
- **Share Modal**: Partiful shows a share/invite modal after event creation. The browser agent automatically dismisses it before extracting the event URL.
- **No Recurring Events**: Partiful does not support recurring events.
- **Create URL**: https://partiful.com/create
- **Success URL Pattern**: `partiful.com/e/`
- **Session Expiry**: If the Composio browser session is expired, re-authenticate via Composio connected accounts and re-run
