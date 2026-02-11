# social-promote

Promote events across social media platforms (Twitter, LinkedIn, Instagram, Facebook, Discord).

## Invocation

This skill is triggered when the user wants to:
- "Promote event on social media"
- "Share event across platforms"
- "Post event to social media"
- "Mass share this event"

## Required Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| `event_title` | string | Event name (max 200 chars) |
| `event_date` | string | Date in natural language, e.g., "January 25, 2025" |
| `event_time` | string | Time with timezone, e.g., "6:00 PM EST" |
| `event_location` | string | Venue name or address |
| `event_description` | string | Full event description (1-2 sentences) |
| `event_url` | string | RSVP/registration link for the event |

## Optional Inputs

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `image_url` | string | "" | Reuse an existing image URL (skips Gemini generation) |
| `discord_channel_id` | string | "" | Discord channel to post to (required for Discord) |
| `facebook_page_id` | string | "" | Facebook page to post to (required for Facebook) |

**Note**: `discord_channel_id` and `facebook_page_id` also fall back to `CCP_DISCORD_CHANNEL_ID` and `CCP_FACEBOOK_PAGE_ID` environment variables if not provided as recipe inputs.

## Execution

Use the Rube MCP tool to execute the social promotion recipe:

```
RUBE_EXECUTE_RECIPE(
    recipe_id="rcp_X65IirgPhwh3",
    input_data={
        "event_title": "<title>",
        "event_date": "<date>",
        "event_time": "<time>",
        "event_location": "<location>",
        "event_description": "<description>",
        "event_url": "<url>",
        "image_url": "<optional existing image URL>",
        "discord_channel_id": "<optional>",
        "facebook_page_id": "<optional>"
    }
)
```

## Output

The recipe returns:

```json
{
  "twitter_posted": "success|skipped|failed: <error>",
  "linkedin_posted": "success|skipped|failed: <error>",
  "instagram_posted": "success|skipped: No image available|failed: <error>",
  "facebook_posted": "success|skipped: No page ID provided|failed: <error>",
  "discord_posted": "success|skipped: No channel ID provided|failed: <error>",
  "image_url": "https://...",
  "summary": "Posted to N/5 platforms"
}
```

## Status Handling

| Status | Meaning |
|--------|---------|
| `success` | Posted successfully |
| `skipped` | Platform intentionally skipped via `skip_platforms` |
| `skipped: No image available` | Instagram skipped because no image was generated or provided |
| `skipped: No page ID provided` | Facebook skipped because `facebook_page_id` was not set |
| `skipped: No channel ID provided` | Discord skipped because `discord_channel_id` was not set |
| `failed: <error>` | API error from the platform (error message included) |

## Chaining from Event Creation

When chaining from a prior event creation skill (luma-create, meetup-create, or partiful-create), pass the `event_url` and `image_url` from the creation result:

```
# After luma-create returns:
#   event_url: "https://lu.ma/abc123"
#   image_url: "https://..."

RUBE_EXECUTE_RECIPE(
    recipe_id="rcp_X65IirgPhwh3",
    input_data={
        ...event details...,
        "event_url": "<event_url from creation result>",
        "image_url": "<image_url from creation result>"
    }
)
```

This avoids redundant Gemini image generation when an image was already created during event creation.

## Platform Notes

- **Twitter**: Posts text with hashtags. Truncated to 280 chars.
- **LinkedIn**: Auto-discovers user URN via `LINKEDIN_GET_MY_INFO` if not provided. Posts as personal update.
- **Instagram**: 3-step process (create container, poll status, publish). Requires Business/Creator account. Skipped if no image is available.
- **Facebook**: Requires `facebook_page_id` and page publish permissions.
- **Discord**: Requires `discord_channel_id` and bot with SEND_MESSAGES permission in target channel.
