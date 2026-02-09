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
| `event_description` | string | Full event description (max 5000 chars) |

**Note**: The Meetup group URL is pre-configured in the recipe (Coffee Code Philly Accelerator). It is not a user-provided parameter.

## Execution

Use the Rube MCP tool to execute the Meetup event creation recipe:

```
RUBE_EXECUTE_RECIPE(
    recipe_id="rcp_kHJoI1WmR3AR",
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
  "platform": "meetup",
  "status": "done|needs_review|failed",
  "event_url": "https://www.meetup.com/coffee-code-philly-accelerator/events/...",
  "image_url": "",
  "error": null,
  "live_url": "https://..."
}
```

## Status Handling

| Status | Meaning | Action |
|--------|---------|--------|
| `done` | Event created successfully | Report event_url to user |
| `needs_review` | Task finished but URL not confirmed | Ask user to check Meetup manually |
| `failed` | Browser task error or timeout | Report error, suggest re-running |

## Live Browser Watching

The `live_url` field (when available) provides a real-time view of the browser automation. Share this with the user so they can watch the event being created.

## Platform Notes

- **Architecture**: Uses `BROWSER_TOOL_CREATE_TASK` - a single AI browser agent call that autonomously fills the form (replaces the old multi-step state machine)
- **Anti-Bot Delays**: Meetup has aggressive bot detection. Task instructions include 2s waits between each form action.
- **Group URL**: Hardcoded to `https://www.meetup.com/coffee-code-philly-accelerator`
- **Create URL**: `{group_url}/events/create/`
- **Success URL Pattern**: `meetup.com` + `/events/` (not `/create`)
- **Session Expiry**: If the Composio browser session is expired, re-authenticate via Composio connected accounts and re-run
