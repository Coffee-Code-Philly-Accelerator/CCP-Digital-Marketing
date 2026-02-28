# stage-event

Generate platform-specific event descriptions and a promotional image, preview them for user review, then create events on all platforms with the approved content.

## Invocation

This skill is triggered when the user wants to:
- "Stage an event"
- "Preview event content"
- "Draft event descriptions"
- "Review event content before publishing"

## Required Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| `event_title` | string | Event name (max 200 chars) |
| `event_date` | string | Date in natural language, e.g., "March 15, 2025" |
| `event_time` | string | Time with timezone, e.g., "6:00 PM EST" |
| `event_location` | string | Venue name or address |

And ONE of:
| Parameter | Type | Description |
|-----------|------|-------------|
| `event_notes` | string | Rough notes/bullet points about the event (Claude generates full descriptions) |
| `event_description` | string | Pre-written description (Claude adapts formatting per platform, does not regenerate) |

## Optional Inputs

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `skip_event_platforms` | string | `""` | Comma-separated platforms to skip, e.g., "meetup,partiful" |
| `skip_image` | boolean | `false` | Skip Gemini image generation |

## Execution (Four Phases)

### Phase 1: Content Generation

**Generate 3 platform-specific descriptions** from the user's `event_notes` or `event_description`:

- **Luma**: Markdown formatting, professional tone, headers + bullets, 500-2000 chars
- **Meetup**: Plaintext only (NO markdown), community-focused, ALL CAPS section headers, 500-2000 chars
- **Partiful**: Casual, emoji-friendly, short paragraphs, 200-800 chars

If `event_description` is provided (not rough notes), adapt its formatting for each platform without regenerating the core content.

**Generate promotional image** (unless `skip_image` is true):

```
RUBE_MULTI_EXECUTE_TOOL(
    tool_slug="GEMINI_GENERATE_IMAGE",
    arguments={
        "model": "gemini-2.5-flash-image",
        "prompt": "Create a modern, eye-catching promotional image for a tech event called '<event_title>' on <event_date>. The event is about <brief summary from notes>. Style: clean, professional, vibrant colors, no text overlays.",
        "image_width": 1024,
        "image_height": 1024
    }
)
```

Extract the public URL using nested data pattern:
```python
data = result.get("data", {})
if "data" in data:
    data = data["data"]
image_url = data.get("publicUrl", "")
```

**Sanitize all descriptions**: Replace `'` with `\u2019` (curly apostrophe) to avoid Rube SyntaxError during recipe execution.

### Phase 2: Review Gate (INTERACTIVE)

Present a formatted preview to the user:

```
## Event Preview: <event_title>
**Date:** <event_date> at <event_time>
**Location:** <event_location>

### Luma Description (Markdown)
<luma_description>

### Meetup Description (Plaintext)
<meetup_description>

### Partiful Description (Casual)
<partiful_description>

### Promotional Image
<image_url>
```

**Wait for user response.** Handle these actions:
- **"Looks good" / "Approve"** -> Proceed to Phase 3
- **"Edit Luma/Meetup/Partiful description"** -> Update the specified platform's description, re-apply sanitization, re-present the preview
- **"Regenerate descriptions"** -> Re-generate all 3 descriptions from scratch
- **"Regenerate image"** -> Re-run GEMINI_GENERATE_IMAGE with a refined prompt
- **Specific edits** (e.g., "Make Meetup shorter", "Add pizza mention to Partiful") -> Apply the requested changes to the specified platform(s)

**Loop** until the user gives explicit approval.

### Phase 3: Create Events

After approval, chain to existing creation recipes. Pass each platform its specific approved description + shared image_url. Skip platforms in `skip_event_platforms`.

**Luma** (unless skipped):
```
RUBE_EXECUTE_RECIPE(
    recipe_id="rcp_mXyFyALaEsQF",
    input_data={
        "event_title": "<title>",
        "event_date": "<date>",
        "event_time": "<time>",
        "event_location": "<location>",
        "event_description": "<approved_luma_description>",
        "event_image_url": "<image_url>"
    }
)
```

**Meetup** (unless skipped):
```
RUBE_EXECUTE_RECIPE(
    recipe_id="rcp_kHJoI1WmR3AR",
    input_data={
        "event_title": "<title>",
        "event_date": "<date>",
        "event_time": "<time>",
        "event_location": "<location>",
        "event_description": "<approved_meetup_description>",
        "event_image_url": "<image_url>"
    }
)
```

**Partiful** (unless skipped):
```
RUBE_EXECUTE_RECIPE(
    recipe_id="rcp_bN7jRF5P_Kf0",
    input_data={
        "event_title": "<title>",
        "event_date": "<date>",
        "event_time": "<time>",
        "event_location": "<location>",
        "event_description": "<approved_partiful_description>",
        "event_image_url": "<image_url>"
    }
)
```

Each recipe returns immediately with `task_id` and `live_url`. Poll for completion using the same two-phase pattern as individual platform skills (see luma-create, meetup-create, partiful-create SKILL.md files).

### Phase 4: Results

Present platform results with event URLs:

```
## Event Creation Results
- Luma: done - https://lu.ma/abc123
- Meetup: done - https://www.meetup.com/.../events/...
- Partiful: done - https://partiful.com/e/abc123

Promotional image: <image_url>
Primary event URL: <luma_url or first successful>
```

Carry forward `image_url` and primary event URL for potential social promotion chaining (via social-promote or full-workflow skills).

## Output

The skill produces:
- 3 user-approved platform-specific descriptions
- 1 promotional image URL
- Event URLs from each platform (after creation)
- Primary event URL (Luma > Meetup > Partiful priority)

## Notes

- **No new Rube recipe needed** - Claude IS the LLM for content generation; only Gemini image generation uses RUBE_MULTI_EXECUTE_TOOL
- **Draft persistence** - Drafts exist in conversation context only (KISS - no external storage)
- **Sanitization** - Applied after every edit: `'` -> `\u2019` (curly apostrophe) to avoid Rube env var injection issues
- **Image URL lifetime** - Gemini publicUrl lives for hours; creation runs in minutes, so expiry is not a concern
- **Image upload failure** - Each platform recipe includes "skip if not available" fallback; text creation still succeeds
- **Social promotion chaining** - After event creation, the user can chain to social-promote skill with the staged image_url to skip redundant Gemini generation
