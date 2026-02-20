# social-post

Post generic content (not event-specific) across social media platforms (Twitter, LinkedIn, Instagram, Facebook, Discord).

## Invocation

This skill is triggered when the user wants to:
- "Post to social media about..."
- "Share on social media"
- "Create a social media post about..."
- "Post this to all platforms"
- "Share this on LinkedIn, Instagram, etc."

**Note:** If the user is promoting a specific **event** (with date, time, location), use the `social-promote` skill instead. This skill is for general-purpose social posts: community updates, tech news, sponsor shout-outs, recaps, announcements, etc.

## Required Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| `topic` | string | What the post is about (max 200 chars) |
| `content` | string | Main message/body text (max 5000 chars) |

## Optional Inputs

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | string | "" | Link to include in posts |
| `cta` | string | "" | Call-to-action, e.g. "Join us", "Read more", "Check it out" |
| `image_url` | string | "" | Reuse an existing image URL (skips Gemini generation) |
| `image_prompt` | string | "" | Custom Gemini prompt for image generation |
| `tone` | string | "engaging" | Style: "engaging", "professional", "casual", "excited", "informative" |
| `hashtags` | string | "" | Custom hashtags to include |
| `discord_channel_id` | string | "" | Discord channel to post to (required for Discord) |
| `facebook_page_id` | string | "" | Facebook page to post to (required for Facebook) |
| `skip_platforms` | string | "" | Platforms to skip (comma-separated) |

**Note**: `discord_channel_id` and `facebook_page_id` also fall back to `CCP_DISCORD_CHANNEL_ID` and `CCP_FACEBOOK_PAGE_ID` environment variables if not provided as recipe inputs.

## Execution

Use the Rube MCP tool to execute the generic social post recipe:

```
RUBE_EXECUTE_RECIPE(
    recipe_id="rcp_3LheyoNQpiFK",
    input_data={
        "topic": "<topic>",
        "content": "<content>",
        "url": "<optional link>",
        "cta": "<optional call to action>",
        "image_url": "<optional existing image URL>",
        "image_prompt": "<optional custom image prompt>",
        "tone": "<optional tone>",
        "hashtags": "<optional hashtags>",
        "discord_channel_id": "<optional>",
        "facebook_page_id": "<optional>",
        "skip_platforms": "<optional>"
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

## Examples

### Community Update
```
RUBE_EXECUTE_RECIPE(
    recipe_id="rcp_3LheyoNQpiFK",
    input_data={
        "topic": "New Community Partnership",
        "content": "We're excited to announce our partnership with TechHub Philly! This collaboration brings new resources and networking opportunities to our community.",
        "url": "https://example.com/partnership",
        "cta": "Learn more",
        "tone": "excited"
    }
)
```

### Tech News Share
```
RUBE_EXECUTE_RECIPE(
    recipe_id="rcp_3LheyoNQpiFK",
    input_data={
        "topic": "Claude 4 Release",
        "content": "Anthropic just released Claude 4 with groundbreaking reasoning capabilities. Here's what it means for developers building AI applications.",
        "url": "https://anthropic.com/news",
        "tone": "informative",
        "hashtags": "#AI #Claude #Anthropic #MachineLearning"
    }
)
```

## Platform Notes

- **Twitter**: Posts text with hashtags. Truncated to 280 chars.
- **LinkedIn**: Auto-discovers user URN via `LINKEDIN_GET_MY_INFO`. Posts as personal update.
- **Instagram**: 3-step process (create container, poll status, publish). Requires Business/Creator account. Skipped if no image is available.
- **Facebook**: Requires `facebook_page_id` and page publish permissions.
- **Discord**: Requires `discord_channel_id` and bot with SEND_MESSAGES permission in target channel.
