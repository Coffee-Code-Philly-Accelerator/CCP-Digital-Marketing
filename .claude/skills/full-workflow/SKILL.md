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
| `image_prompt` | string | auto-generated | Custom prompt for AI image generation |
| `tenant_id` | string | "default" | Tenant identifier for multi-tenant sessions |
| `discord_channel_id` | string | "" | Discord channel for social promotion |
| `facebook_page_id` | string | "" | Facebook page for social promotion |
| `skip_event_platforms` | string | "" | Comma-separated event platforms to skip, e.g., "meetup,partiful" |
| `skip_social_platforms` | string | "" | Comma-separated social platforms to skip, e.g., "facebook,discord" |

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
        "event_description": "<description>",
        "image_prompt": "<optional>",
        "tenant_id": "<tenant>"
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
        "event_description": "<description>",
        "image_prompt": "<optional>",
        "tenant_id": "<tenant>"
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
        "event_description": "<description>",
        "image_prompt": "<optional>",
        "tenant_id": "<tenant>"
    }
)
```

### Phase 1 Result Handling

After each recipe completes:

1. **If `status` is `"done"`**: Record the `event_url` and `image_url`. Continue to the next platform.
2. **If `status` is `"paused_2fa"` or `"needs_auth"`**: Inform the user which platform needs authentication. Wait for user confirmation, then re-run the same recipe with `resume=true`. After resume succeeds, continue.
3. **If `status` is `"failed"`**: Log the error and continue to the next platform. Do not abort the entire workflow.

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

## Auth/2FA Resume Flow

If any event creation recipe returns `status: "paused_2fa"` or `status: "needs_auth"`:

1. Inform the user which platform needs authentication
2. Wait for the user to confirm they have logged in / completed 2FA in the browser
3. Re-run that platform's recipe with `resume=true`
4. After resume, continue the workflow with the next platform

Example response to user:
> Luma event created successfully. Meetup requires authentication.
> Please log in to Meetup in your browser, then let me know to continue.

## Platform Notes

- **Event creation is sequential** - browser automation sessions cannot overlap
- **Social promotion runs in parallel internally** - the recipe handles parallelism via ThreadPoolExecutor
- **Image reuse** - the `image_url` from the first successful event creation is passed to social promotion, skipping redundant Gemini generation
- **Partial success is OK** - if one event platform fails, the workflow continues with remaining platforms and proceeds to social promotion with whatever URLs are available
