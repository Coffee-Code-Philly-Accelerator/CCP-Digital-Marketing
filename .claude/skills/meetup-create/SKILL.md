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

## Optional Inputs

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `image_prompt` | string | auto-generated | Custom prompt for AI image generation |
| `tenant_id` | string | "default" | Tenant identifier for multi-tenant sessions |
| `resume` | boolean | false | Resume from checkpoint after auth/2FA |

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
        "event_description": "<description>",
        "image_prompt": "<optional custom prompt>",
        "tenant_id": "<tenant>",
        "resume": "<true/false>"
    }
)
```

## Output

The recipe returns:

```json
{
  "tenant_id": "default",
  "platform": "meetup",
  "status": "done|paused_2fa|needs_auth|failed",
  "event_url": "https://www.meetup.com/coffee-code-philly-accelerator/events/...",
  "image_url": "https://...",
  "error": null,
  "resume_token": "default:meetup:2fa",
  "resume_instructions": "..."
}
```

## Auth/2FA Resume Flow

If the recipe returns `status: "paused_2fa"` or `status: "needs_auth"`:

1. Inform the user that manual authentication is needed
2. Wait for the user to confirm they have logged in / completed 2FA in the browser
3. Re-run the recipe with `resume=true` to continue from the checkpoint

Example response to user:
> The Meetup session requires authentication. Please log in to Meetup in your browser.
> Once logged in, let me know and I'll resume the event creation.

## Platform Notes

- **Anti-Bot Delays**: Meetup has aggressive bot detection. The recipe uses 2.0s delays between all form actions, making it slower than other platforms.
- **Group URL**: Hardcoded to `https://www.meetup.com/coffee-code-philly-accelerator`
- **Create URL**: `{group_url}/events/create/`
- **Success URL Pattern**: `meetup.com` + `/events/` (not `/create`)
