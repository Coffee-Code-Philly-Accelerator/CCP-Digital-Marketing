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
| `linkedin_author_urn` | string | "" | LinkedIn author URN (auto-discovered if empty) |
| `ig_user_id` | string | "" | Instagram Business Account ID (auto-discovered if empty) |
| `discord_channel_id` | string | "" | Discord channel to post to (required for Discord) |
| `facebook_page_id` | string | "" | Facebook page to post to (required for Facebook) |

## Execution

Use the Rube MCP tool to execute the social promotion recipe:

```
RUBE_EXECUTE_RECIPE(
    recipe_id="rcp_zBzqs2LO-miP",
    input_data={
        "event_title": "<title>",
        "event_date": "<date>",
        "event_time": "<time>",
        "event_location": "<location>",
        "event_description": "<description>",
        "event_url": "<url>",
        "image_url": "<optional existing image URL>",
        "linkedin_author_urn": "<optional, auto-discovered if empty>",
        "ig_user_id": "<optional, auto-discovered if empty>",
        "discord_channel_id": "<optional>",
        "facebook_page_id": "<optional>"
    }
)
```

## Output

The recipe returns:

```json
{
  "twitter_status": "success|skipped|failed",
  "twitter_post_id": "...",
  "linkedin_status": "success|skipped: no URN|failed",
  "linkedin_post_id": "...",
  "instagram_status": "success|skipped: no user_id|skipped: no image|failed",
  "instagram_post_id": "...",
  "facebook_status": "success|skipped: no page_id|failed",
  "facebook_post_id": "...",
  "discord_status": "success|skipped: no channel_id|failed",
  "discord_message_id": "...",
  "generated_image_url": "https://...",
  "discovered_linkedin_urn": "urn:li:person:...",
  "discovered_ig_user_id": "...",
  "summary": "Posted: ['twitter', 'linkedin']. Skipped: ['facebook', 'discord']"
}
```

## Status Handling

| Status | Meaning |
|--------|---------|
| `success` | Posted successfully |
| `skipped: no URN` | LinkedIn skipped, URN not provided and auto-discovery failed |
| `skipped: no user_id` | Instagram skipped, user ID not provided and auto-discovery failed |
| `skipped: no image` | Instagram skipped because no image was generated or provided |
| `skipped: no page_id` | Facebook skipped because `facebook_page_id` was not set |
| `skipped: no channel_id` | Discord skipped because `discord_channel_id` was not set |
| `failed` | API error from the platform |

## Chaining from Event Creation

When chaining from a prior event creation skill (luma-create, meetup-create, or partiful-create), pass the `event_url` and `image_url` from the creation result:

```
# After luma-create returns:
#   event_url: "https://lu.ma/abc123"
#   image_url: "https://..."

RUBE_EXECUTE_RECIPE(
    recipe_id="rcp_zBzqs2LO-miP",
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
