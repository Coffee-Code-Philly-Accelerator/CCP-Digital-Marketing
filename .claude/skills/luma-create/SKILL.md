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
| `event_description` | string | Full event description (max 5000 chars) |

## Execution

Use the Rube MCP tool to execute the Luma event creation recipe:

```
RUBE_EXECUTE_RECIPE(
    recipe_id="rcp_mXyFyALaEsQF",
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
  "platform": "luma",
  "status": "done|needs_review|failed",
  "event_url": "https://lu.ma/abc123",
  "image_url": "",
  "error": null,
  "live_url": "https://..."
}
```

## Status Handling

| Status | Meaning | Action |
|--------|---------|--------|
| `done` | Event created successfully | Report event_url to user |
| `needs_review` | Task finished but URL not confirmed | Ask user to check Luma manually |
| `failed` | Browser task error or timeout | Report error, suggest re-running |

## Live Browser Watching

The `live_url` field (when available) provides a real-time view of the browser automation. Share this with the user so they can watch the event being created.

## Platform Notes

- **Architecture**: Uses `BROWSER_TOOL_CREATE_TASK` - a single AI browser agent call that autonomously fills the form (replaces the old multi-step state machine)
- **Date Picker**: Luma uses a React date picker; task instructions include explicit 2s waits
- **Share Modal**: After publishing, Luma may show a share modal that the browser agent dismisses automatically
- **Create URL**: https://lu.ma/create
- **Success URL Pattern**: `lu.ma/` (not `/create` or `/home`)
- **Session Expiry**: If the Composio browser session is expired, re-authenticate via Composio connected accounts and re-run
