# CCP Digital Marketing Automation

[![Rube MCP](https://img.shields.io/badge/Powered%20by-Rube%20MCP-blue)](https://rube.app)
[![Composio](https://img.shields.io/badge/Built%20with-Composio-green)](https://composio.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Automated event creation and social media promotion system for Coffee Code Philly Accelerator. Creates events across multiple platforms and promotes them on social media with AI-generated content. Also supports generic social media posts (community updates, tech news, sponsor shout-outs) that aren't tied to a specific event.

## Overview

This system automates the entire event lifecycle:
1. **Event Creation** - Sequentially creates events on Luma, Meetup, and Partiful via browser automation
2. **Content Generation** - AI generates promotional images and platform-optimized descriptions
3. **Social Promotion** - Posts to Twitter, LinkedIn, Instagram, Facebook, and Discord
4. **Generic Social Posts** - Post any content (not just events) to all social platforms

```mermaid
flowchart TB
    subgraph Input["User Input"]
        A[Event Details<br/>Title, Date, Time, Location, Description]
    end

    subgraph AI["AI Content Generation"]
        B[Gemini Image Generation]
        C[LLM Description Optimization]
    end

    subgraph Events["Event Platform Creation (Sequential)"]
        D[Luma<br/>rcp_mXyFyALaEsQF]
        E[Meetup<br/>rcp_kHJoI1WmR3AR]
        F[Partiful<br/>rcp_bN7jRF5P_Kf0]
    end

    subgraph Social["Social Media Promotion"]
        G[Twitter/X]
        H[LinkedIn]
        I[Instagram]
        J[Facebook]
        K[Discord]
    end

    subgraph Output["Results"]
        L[Event URLs]
        M[Post Confirmations]
    end

    A --> B
    A --> C
    B --> D & E & F
    C --> D & E & F
    D --> L
    E --> L
    F --> L
    L --> G & H & I & J & K
    B --> G & H & I & J & K
    G & H & I & J & K --> M
```

## Architecture

### System Components

```mermaid
flowchart LR
    subgraph Rube["Rube MCP Platform"]
        R1[Recipe: Luma Create<br/>rcp_mXyFyALaEsQF]
        R2[Recipe: Meetup Create<br/>rcp_kHJoI1WmR3AR]
        R3[Recipe: Partiful Create<br/>rcp_bN7jRF5P_Kf0]
        R4[Recipe: Social Promotion<br/>rcp_X65IirgPhwh3]
        R5[Recipe: Social Post<br/>rcp_PLACEHOLDER]
    end

    subgraph Browser["Browser Automation"]
        subgraph HB["Hyperbrowser (Primary)"]
            BA1[HYPERBROWSER_START_BROWSER_USE_TASK]
            BB1[HYPERBROWSER_GET_BROWSER_USE_TASK_STATUS]
            BC1[HYPERBROWSER_GET_SESSION_DETAILS]
        end
        subgraph BT["browser_tool (Fallback)"]
            BA2[BROWSER_TOOL_CREATE_TASK]
            BB2[BROWSER_TOOL_WATCH_TASK]
            BC2[BROWSER_TOOL_GET_SESSION]
        end
    end

    subgraph APIs["Direct API Integrations"]
        API1[Twitter API]
        API2[LinkedIn API]
        API3[Instagram Graph API]
        API4[Facebook Graph API]
        API5[Discord API]
    end

    subgraph AI["AI Services"]
        AI1[Gemini Imagen]
        AI2[LLM invoke_llm]
    end

    R1 & R2 & R3 --> Browser
    R1 & R2 & R3 --> AI
    R4 --> APIs
    R4 --> AI
    R5 --> APIs
    R5 --> AI
```

## Prerequisites

### Required Accounts
- [Composio Account](https://composio.dev) with Rube MCP access
- Event platform accounts: Luma, Meetup, Partiful
- Social media accounts: Twitter, LinkedIn, Instagram, Facebook Page, Discord Server

### Connected Apps in Composio

| App | Connection Type | Required For |
|-----|-----------------|--------------|
| `HYPERBROWSER` | API Key | Event creation (primary browser provider) |
| `BROWSER_TOOL` | Browser Session | Event creation (fallback browser provider) |
| `GEMINI` | API Key | Image generation |
| `TWITTER` | OAuth 2.0 | Social posting |
| `LINKEDIN` | OAuth 2.0 | Social posting |
| `INSTAGRAM` | OAuth 2.0 | Social posting |
| `FACEBOOK` | OAuth 2.0 | Page posting |
| `DISCORD` | Bot Token | Server announcements |

## Quick Start

### Option 1: Via Rube App (Recommended)

1. Open [Rube App](https://rube.app)
2. **Set up auth profiles first** (one-time): Run the auth-setup skill for each platform (Luma, Meetup, Partiful) to create Hyperbrowser persistent profiles with saved login cookies
3. Run per-platform event creation recipes:
   - Luma: `rcp_mXyFyALaEsQF`
   - Meetup: `rcp_kHJoI1WmR3AR`
   - Partiful: `rcp_bN7jRF5P_Kf0`
4. Fill in event details and run each recipe
5. Poll for completion using the provider-specific tool returned by the recipe (`HYPERBROWSER_GET_BROWSER_USE_TASK_STATUS` or `BROWSER_TOOL_WATCH_TASK`)
6. Copy event URLs from poll results
7. Run "Event Social Promotion" (`rcp_X65IirgPhwh3`) with the URLs

### Option 2: Via Claude Code with Rube MCP

```bash
# In Claude Code with Rube MCP connected
"Create an event titled 'AI Workshop' on January 25, 2025 at 6 PM
at The Station, Philadelphia. Then promote it on all social platforms."
```

## Recipes

### Recipe 1: Create Event on Luma

**Recipe ID:** `rcp_mXyFyALaEsQF`

Creates an event on Luma (lu.ma) using an AI browser agent. Defaults to Hyperbrowser with persistent auth profiles.

### Recipe 2: Create Event on Meetup

**Recipe ID:** `rcp_kHJoI1WmR3AR`

Creates an event on Meetup using an AI browser agent. Defaults to Hyperbrowser with persistent auth profiles.

### Recipe 3: Create Event on Partiful

**Recipe ID:** `rcp_bN7jRF5P_Kf0`

Creates an event on Partiful using an AI browser agent. Defaults to Hyperbrowser with persistent auth profiles.

#### Event Creation Sequence (all platforms)

```mermaid
sequenceDiagram
    participant U as User/Caller
    participant R as Recipe
    participant HB as Hyperbrowser / browser_tool
    participant P as Platform

    U->>R: Event Details
    alt Hyperbrowser (default)
        R->>HB: HYPERBROWSER_START_BROWSER_USE_TASK<br/>(task + profile + session options)
        HB-->>R: jobId + sessionId
        R->>HB: HYPERBROWSER_GET_SESSION_DETAILS
        HB-->>R: liveUrl
    else browser_tool (fallback)
        R->>HB: BROWSER_TOOL_CREATE_TASK<br/>(task description + startUrl)
        HB-->>R: watch_task_id + browser_session_id
        R->>HB: BROWSER_TOOL_GET_SESSION
        HB-->>R: liveUrl
    end
    R-->>U: {task_id, live_url, provider, status: "running"}

    loop Poll every 10-15s (caller-side)
        alt Hyperbrowser
            U->>HB: HYPERBROWSER_GET_BROWSER_USE_TASK_STATUS(task_id)
            HB-->>U: {status: "running"|"completed"|"failed"}
        else browser_tool
            U->>HB: BROWSER_TOOL_WATCH_TASK(taskId)
            HB-->>U: {status: "started"|"finished"|"stopped", current_url}
        end
    end

    Note over HB,P: Browser agent fills form and submits
    HB->>P: Submit event
    P-->>HB: Event page URL
```

#### Input Parameters (all event creation recipes)

| Parameter | Required | Description | Example |
|-----------|----------|-------------|---------|
| `event_title` | Yes | Name of the event | "AI Workshop: Building with Claude" |
| `event_date` | Yes | Date of event | "January 25, 2025" |
| `event_time` | Yes | Start time with timezone | "6:00 PM EST" |
| `event_location` | Yes | Venue or address | "The Station, 3rd Floor, Philadelphia" |
| `event_description` | Yes | Event description | "Join us for a hands-on workshop..." |

#### Output (Phase 1 - immediate return)

```json
{
  "platform": "luma|meetup|partiful",
  "status": "running",
  "task_id": "<use for polling>",
  "session_id": "<browser session>",
  "live_url": "https://...",
  "event_url": "",
  "provider": "hyperbrowser|browser_tool",
  "poll_tool": "HYPERBROWSER_GET_BROWSER_USE_TASK_STATUS|BROWSER_TOOL_WATCH_TASK",
  "poll_args_key": "task_id|taskId",
  "error": null
}
```

---

### Recipe 4: Event Social Promotion

**Recipe ID:** `rcp_X65IirgPhwh3`
**Recipe URL:** [View on Rube](https://rube.app)

Posts event announcements to 5 social platforms with AI-generated content.

```mermaid
sequenceDiagram
    participant U as User
    participant R as Recipe
    participant G as Gemini AI
    participant L as LLM
    participant T as Twitter
    participant Li as LinkedIn
    participant I as Instagram
    participant F as Facebook
    participant D as Discord

    U->>R: Event Details + URLs
    R->>G: Generate promotional image
    G-->>R: Image URL
    R->>L: Generate platform-specific copy
    L-->>R: 5 optimized posts

    par Parallel Posting
        R->>T: Post tweet with image
        T-->>R: Tweet ID
    and
        R->>Li: Post to LinkedIn
        Li-->>R: Post URN
    and
        R->>I: Post to Instagram
        I-->>R: Media ID
    and
        R->>F: Post to Page
        F-->>R: Post ID
    and
        R->>D: Send to channel
        D-->>R: Message ID
    end

    R-->>U: All post confirmations
```

#### Input Parameters

| Parameter | Required | Description | Example |
|-----------|----------|-------------|---------|
| `event_title` | Yes | Name of the event | "AI Workshop" |
| `event_date` | Yes | Date of event | "January 25, 2025" |
| `event_time` | Yes | Start time | "6:00 PM EST" |
| `event_location` | Yes | Venue | "The Station, Philadelphia" |
| `event_description` | Yes | Event description | "Join us for..." |
| `event_url` | Yes | Primary RSVP link | "https://lu.ma/abc123" |
| `discord_channel_id` | No | Discord channel ID | "1234567890" |
| `facebook_page_id` | No | Facebook page ID | "9876543210" |

#### Output

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

---

## Combined Workflow

For a complete event launch, run event creation recipes sequentially, then social promotion:

```mermaid
flowchart TD
    subgraph Phase1["Phase 1: Event Creation (Sequential)"]
        A[User provides event details] --> B[Luma Recipe<br/>rcp_mXyFyALaEsQF]
        B --> C[Poll until done]
        C --> D[Meetup Recipe<br/>rcp_kHJoI1WmR3AR]
        D --> E[Poll until done]
        E --> F[Partiful Recipe<br/>rcp_bN7jRF5P_Kf0]
        F --> G[Poll until done]
    end

    subgraph Phase2["Phase 2: Social Promotion"]
        G --> H[Recipe: Event Social Promotion<br/>rcp_X65IirgPhwh3]
        H --> I[Twitter Post]
        H --> J[LinkedIn Post]
        H --> K[Instagram Post]
        H --> L[Facebook Post]
        H --> M[Discord Message]
    end

    subgraph Results["Final Results"]
        I & J & K & L & M --> N[All URLs & Post IDs<br/>Stored for tracking]
    end
```

## Platform Connection Status

Current integration status for each platform:

| Platform | Type | Status | Notes |
|----------|------|--------|-------|
| **Luma** | Browser (Hyperbrowser) | Tested | Persistent profile with saved auth |
| **Meetup** | Browser (Hyperbrowser) | Tested | Persistent profile with saved auth |
| **Partiful** | Browser (Hyperbrowser) | Tested | Persistent profile with saved auth |
| **Twitter/X** | API | Working | OAuth connected |
| **LinkedIn** | API | Working | OAuth connected |
| **Instagram** | API | Working | Business account required |
| **Facebook** | API | Partial | Page permissions needed |
| **Discord** | API | Partial | Bot re-authorization needed |

## Authentication Flow

```mermaid
flowchart TD
    A[First-Time Setup] --> B[Run auth-setup skill per platform]
    B --> C[Hyperbrowser creates session with persistent profile]
    C --> D[User logs in via interactive live URL]
    D --> E[Cookies saved to profile]

    F[Event Creation] --> G{Profile has valid auth?}
    G -->|Yes| H[AI browser agent fills form]
    G -->|No / NEEDS_AUTH| I[Re-run auth-setup to re-login]
    I --> G
    H --> J[Submit/Publish]
    J --> K[Capture Event URL via polling]
```

## Browser Provider Configuration

Event creation recipes support two browser providers, controlled by `CCP_BROWSER_PROVIDER`:

| Provider | Value | Description |
|----------|-------|-------------|
| Hyperbrowser | `hyperbrowser` (default) | Persistent profiles with saved auth cookies. Requires one-time profile setup via auth-setup skill. |
| Composio browser_tool | `browser_tool` | Ephemeral sessions (no auth persistence). Fallback provider. |

### Auth Setup (One-Time)

Before creating events with Hyperbrowser, set up persistent profiles:

1. Run the **auth-setup** skill for each platform (Luma, Meetup, Partiful)
2. Open the interactive live URL provided
3. Complete login (Google OAuth or platform-specific)
4. Save the profile IDs to your `.env` file (`CCP_LUMA_PROFILE_ID`, `CCP_MEETUP_PROFILE_ID`, `CCP_PARTIFUL_PROFILE_ID`)

If a recipe returns `NEEDS_AUTH`, re-run auth-setup with the existing `profile_id` to re-login without creating a new profile.

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `COMPOSIO_API_KEY` | Yes | - | Composio API authentication |
| `CCP_BROWSER_PROVIDER` | No | `hyperbrowser` | Browser provider: `hyperbrowser` or `browser_tool` |
| `CCP_LUMA_PROFILE_ID` | No | - | Hyperbrowser profile UUID for Luma |
| `CCP_MEETUP_PROFILE_ID` | No | - | Hyperbrowser profile UUID for Meetup |
| `CCP_PARTIFUL_PROFILE_ID` | No | - | Hyperbrowser profile UUID for Partiful |
| `CCP_DISCORD_CHANNEL_ID` | No | - | Discord channel for social promotion |
| `CCP_FACEBOOK_PAGE_ID` | No | - | Facebook page for social promotion |
| `CCP_MEETUP_GROUP_URL` | No | `https://www.meetup.com/code-coffee-philly` | Default Meetup group URL |

See `scripts/.env.example` for the full list including optional overrides.

## Troubleshooting

See [docs/troubleshooting.md](docs/troubleshooting.md) for common issues:

- **NEEDS_AUTH status**: Browser session expired, re-login required
- **Form filling fails**: Platform UI changed, update prompts
- **Image upload fails**: Check image URL accessibility
- **Social post fails**: Re-authorize API connections in Composio

## File Structure

```
CCP-Digital-Marketing/
├── README.md                    # This file
├── CLAUDE.md                    # Claude Code guidance
├── docs/
│   ├── event-creation.md        # Detailed event creation docs
│   ├── social-promotion.md      # Detailed social promotion docs
│   ├── social-post.md           # Detailed generic social post docs
│   └── troubleshooting.md       # Common issues & solutions
├── recipes/
│   ├── luma_create_event.py     # Luma event creation recipe (Hyperbrowser + browser_tool)
│   ├── meetup_create_event.py   # Meetup event creation recipe (Hyperbrowser + browser_tool)
│   ├── partiful_create_event.py # Partiful event creation recipe (Hyperbrowser + browser_tool)
│   ├── social_promotion.py      # Social promotion recipe (event-specific)
│   ├── social_post.py           # Generic social post recipe
│   └── auth_setup.py            # Hyperbrowser auth profile setup
├── scripts/
│   ├── recipe_client.py         # CLI client for recipe execution
│   ├── requirements.txt         # Python dependencies
│   └── .env.example             # Environment variable template
├── .claude/skills/
│   ├── auth-setup/              # Hyperbrowser persistent auth profile setup
│   ├── luma-create/             # Luma event creation skill
│   ├── meetup-create/           # Meetup event creation skill
│   ├── partiful-create/         # Partiful event creation skill
│   ├── social-promote/          # Social promotion skill (event-specific)
│   ├── social-post/             # Generic social post skill
│   └── full-workflow/           # Full workflow orchestration skill
└── .gitignore
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/improvement`)
3. Commit your changes (`git commit -am 'Add new feature'`)
4. Push to the branch (`git push origin feature/improvement`)
5. Open a Pull Request

## License

MIT License - see LICENSE file for details.

## Support

- **Issues**: Open a GitHub issue
- **Composio**: [composio.dev/docs](https://composio.dev/docs)
- **Rube MCP**: [rube.app](https://rube.app)

---

Built with Rube MCP by Composio for Coffee Code Philly Accelerator
