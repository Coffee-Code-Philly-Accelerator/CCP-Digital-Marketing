# full-workflow

Create an event on all platforms (Luma, Meetup, Partiful) and promote it on social media.

## Invocation

This skill is triggered when the user wants to:
- "Create and promote event"
- "Full event workflow"
- "Create event everywhere and share on social media"
- "Launch event on all platforms"

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
| `discord_channel_id` | string | "" | Discord channel for social promotion |
| `facebook_page_id` | string | "" | Facebook page for social promotion |
| `skip_event_platforms` | string | "" | Comma-separated event platforms to skip, e.g., "meetup,partiful" |
| `skip_social_platforms` | string | "" | Comma-separated social platforms to skip, e.g., "facebook,discord" |

## Prerequisites

Before running, ensure all platform profiles are set up via the **auth-setup** skill. Each platform (Luma, Meetup, Partiful) needs a Hyperbrowser persistent profile with saved login cookies.

## Execution

This is an orchestration skill. Execute the following 4 recipes **sequentially** (browser sessions cannot overlap). After all event creation is done, run social promotion.

### Phase 1: Event Creation (sequential)

Run each platform unless it appears in `skip_event_platforms`. Collect `event_url` and `image_url` from each successful result.

**Step 1 - Luma** (unless skipped):
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

**Step 2 - Meetup** (unless skipped):
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

**Step 3 - Partiful** (unless skipped):
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

### Phase 1 Result Handling

Each event creation recipe returns immediately with `status: "running"`, a `task_id`, and provider information (`provider`, `poll_tool`, `poll_args_key`). After each recipe returns:

1. **Poll for completion** using the provider-specific tool:

   **If `provider` is `"hyperbrowser"`:**
   ```
   RUBE_MULTI_EXECUTE_TOOL(
       tool_slug="HYPERBROWSER_GET_BROWSER_USE_TASK_STATUS",
       arguments={"task_id": "<task_id from recipe>"}
   )
   ```
   - `status: "completed"` → done, check result for event URL
   - `status: "running"` → still running, poll again in 10-15 seconds
   - `status: "failed"` → task failed, log error and continue

   **If `provider` is `"browser_tool"`:**
   ```
   RUBE_MULTI_EXECUTE_TOOL(
       tool_slug="BROWSER_TOOL_WATCH_TASK",
       arguments={"taskId": "<task_id from recipe>"}
   )
   ```
   - `status: "finished"` → check `current_url` against the platform's success URL pattern. Record as the event URL.
   - `status: "started"` → still running, poll again in 10-15 seconds
   - `status: "stopped"` → task was aborted, log error and continue

2. **If authentication is needed**: The browser task may navigate to a login page. Inform the user and wait for them to re-authenticate via the auth-setup skill (Hyperbrowser) or Composio connected accounts (browser_tool), then re-run.
3. Continue to the next platform regardless of success/failure.

### URL Priority

Select the **primary event URL** for social promotion using this priority order (matching `EventCreationResult.primary_url` logic):

1. Luma URL (if available)
2. Meetup URL (if available)
3. Partiful URL (if available)

Also reuse the `image_url` from the first successful platform to avoid redundant Gemini calls.

### Phase 2: Social Promotion

After all event creation steps complete, run social promotion with the primary URL and image:

**Step 4 - Social Promotion**:
```
RUBE_EXECUTE_RECIPE(
    recipe_id="rcp_zBzqs2LO-miP",
    input_data={
        "event_title": "<title>",
        "event_date": "<date>",
        "event_time": "<time>",
        "event_location": "<location>",
        "event_description": "<description>",
        "event_url": "<primary event URL from Phase 1>",
        "image_url": "<image URL from Phase 1>",
        "discord_channel_id": "<optional>",
        "facebook_page_id": "<optional>",
        "skip_platforms": "<skip_social_platforms value>"
    }
)
```

## Output

Present a combined summary to the user:

```
## Event Creation Results
- Luma: done - https://lu.ma/abc123
- Meetup: done - https://www.meetup.com/.../events/...
- Partiful: done - https://partiful.com/e/abc123

## Social Promotion Results
- Twitter: success
- LinkedIn: success
- Instagram: success
- Facebook: skipped: No page ID provided
- Discord: skipped: No channel ID provided

Primary event URL: https://lu.ma/abc123
```

## Platform Notes

- **Event creation is sequential** - browser automation sessions cannot overlap
- **Social promotion runs in parallel internally** - the recipe handles parallelism via ThreadPoolExecutor
- **Image reuse** - the `image_url` from the first successful event creation is passed to social promotion, skipping redundant Gemini generation
- **Partial success is OK** - if one event platform fails, the workflow continues with remaining platforms and proceeds to social promotion with whatever URLs are available
- **Browser provider** - defaults to Hyperbrowser with persistent profiles. Ensure auth-setup has been run for each platform before starting.
