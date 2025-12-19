# CCP Digital Marketing Automation

[![Rube MCP](https://img.shields.io/badge/Powered%20by-Rube%20MCP-blue)](https://rube.app)
[![Composio](https://img.shields.io/badge/Built%20with-Composio-green)](https://composio.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Automated event creation and social media promotion system for Coffee Code Philly Accelerator. Creates events across multiple platforms and promotes them on social media with AI-generated content.

## Overview

This system automates the entire event lifecycle:
1. **Event Creation** - Simultaneously creates events on Luma, Meetup, and Partiful
2. **Content Generation** - AI generates promotional images and platform-optimized descriptions
3. **Social Promotion** - Posts to Twitter, LinkedIn, Instagram, Facebook, and Discord

```mermaid
flowchart TB
    subgraph Input["User Input"]
        A[Event Details<br/>Title, Date, Time, Location, Description]
    end

    subgraph AI["AI Content Generation"]
        B[Gemini Image Generation]
        C[LLM Description Optimization]
    end

    subgraph Events["Event Platform Creation"]
        D[Luma<br/>lu.ma/create]
        E[Meetup<br/>meetup.com/.../events/create]
        F[Partiful<br/>partiful.com/create]
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
        R1[Recipe: Create Event<br/>rcp_xvediVZu8BzW]
        R2[Recipe: Social Promotion<br/>rcp_zBzqs2LO-miP]
    end

    subgraph Browser["Browser Automation"]
        BA[BROWSER_TOOL_NAVIGATE]
        BB[BROWSER_TOOL_PERFORM_WEB_TASK]
        BC[BROWSER_TOOL_SCREENSHOT]
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

    R1 --> Browser
    R1 --> AI
    R2 --> APIs
    R2 --> AI
```

## Prerequisites

### Required Accounts
- [Composio Account](https://composio.dev) with Rube MCP access
- Event platform accounts: Luma, Meetup, Partiful
- Social media accounts: Twitter, LinkedIn, Instagram, Facebook Page, Discord Server

### Connected Apps in Composio

| App | Connection Type | Required For |
|-----|-----------------|--------------|
| `BROWSER_TOOL` | Browser Session | Event creation |
| `GEMINI` | API Key | Image generation |
| `TWITTER` | OAuth 2.0 | Social posting |
| `LINKEDIN` | OAuth 2.0 | Social posting |
| `INSTAGRAM` | OAuth 2.0 | Social posting |
| `FACEBOOK` | OAuth 2.0 | Page posting |
| `DISCORD` | Bot Token | Server announcements |

## Quick Start

### Option 1: Via Rube App (Recommended)

1. Open [Rube App](https://rube.app)
2. Navigate to Recipes
3. Find "Create Event on All Platforms" (`rcp_xvediVZu8BzW`)
4. Fill in event details and run
5. Copy event URLs from output
6. Run "Event Social Promotion" (`rcp_zBzqs2LO-miP`) with the URLs

### Option 2: Via Claude Code with Rube MCP

```bash
# In Claude Code with Rube MCP connected
"Create an event titled 'AI Workshop' on January 25, 2025 at 6 PM
at The Station, Philadelphia. Then promote it on all social platforms."
```

## Recipes

### Recipe 1: Create Event on All Platforms

**Recipe ID:** `rcp_xvediVZu8BzW`
**Recipe URL:** [View on Rube](https://rube.app/recipes/fa1a7dd7-05d1-4155-803a-a2448f6fc1b2)

Creates events on Luma, Meetup, and Partiful using browser automation with AI-generated content.

```mermaid
sequenceDiagram
    participant U as User
    participant R as Recipe
    participant G as Gemini AI
    participant L as LLM
    participant B as Browser
    participant Lu as Luma
    participant Me as Meetup
    participant Pa as Partiful

    U->>R: Event Details
    R->>G: Generate promotional image
    G-->>R: Image URL
    R->>L: Generate platform descriptions
    L-->>R: Optimized descriptions

    rect rgb(240, 248, 255)
        Note over R,Lu: Luma Creation
        R->>B: Navigate to lu.ma/create
        B->>Lu: Check login status
        Lu-->>B: Page state
        R->>B: Fill form with AI agent
        B->>Lu: Submit event
        Lu-->>R: Event URL
    end

    rect rgb(255, 248, 240)
        Note over R,Me: Meetup Creation
        R->>B: Navigate to group/events/create
        B->>Me: Check login status
        Me-->>B: Page state
        R->>B: Fill form with AI agent
        B->>Me: Submit event
        Me-->>R: Event URL
    end

    rect rgb(240, 255, 240)
        Note over R,Pa: Partiful Creation
        R->>B: Navigate to partiful.com/create
        B->>Pa: Check login status
        Pa-->>B: Page state
        R->>B: Fill form with AI agent
        B->>Pa: Submit event
        Pa-->>R: Event URL
    end

    R-->>U: All Event URLs + Status
```

#### Input Parameters

| Parameter | Required | Description | Example |
|-----------|----------|-------------|---------|
| `event_title` | Yes | Name of the event | "AI Workshop: Building with Claude" |
| `event_date` | Yes | Date of event | "January 25, 2025" |
| `event_time` | Yes | Start time with timezone | "6:00 PM EST" |
| `event_location` | Yes | Venue or address | "The Station, 3rd Floor, Philadelphia" |
| `event_description` | Yes | Event description | "Join us for a hands-on workshop..." |
| `meetup_group_url` | Yes | Your Meetup group URL | "https://meetup.com/coffee-code-philly" |
| `platforms` | No | Platforms to create on | "luma,meetup,partiful" (default: all) |
| `skip_platforms` | No | Platforms to skip | "meetup" (if auth issues) |

#### Output

```json
{
  "luma_url": "https://lu.ma/abc123",
  "meetup_url": "https://meetup.com/coffee-code-philly/events/12345",
  "partiful_url": "https://partiful.com/e/xyz789",
  "image_url": "https://storage.googleapis.com/...",
  "status_summary": "Luma: PUBLISHED | Meetup: PUBLISHED | Partiful: PUBLISHED",
  "needs_auth": "none"
}
```

#### Status Codes

| Status | Meaning | Action Required |
|--------|---------|-----------------|
| `PUBLISHED` | Event created successfully | None |
| `NEEDS_AUTH` | Login or 2FA required | Log in manually, re-run |
| `NEEDS_REVIEW` | Uncertain if published | Check platform manually |
| `FAILED` | Error occurred | Check error message |
| `SKIPPED` | Platform skipped | Intentional (skip_platforms) |

---

### Recipe 2: Event Social Promotion

**Recipe ID:** `rcp_zBzqs2LO-miP`
**Recipe URL:** [View on Rube](https://rube.app/recipes/...)

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
  "twitter_posted": "success",
  "linkedin_posted": "success",
  "instagram_posted": "success",
  "facebook_posted": "success",
  "discord_posted": "success",
  "image_url": "https://storage.googleapis.com/...",
  "summary": "Posted to 5/5 platforms"
}
```

---

## Combined Workflow

For a complete event launch, run both recipes in sequence:

```mermaid
flowchart TD
    subgraph Phase1["Phase 1: Event Creation"]
        A[User provides event details] --> B[Recipe: Create Event on All Platforms]
        B --> C{Events Created?}
        C -->|Yes| D[Luma URL]
        C -->|Yes| E[Meetup URL]
        C -->|Yes| F[Partiful URL]
        C -->|Auth Required| G[Manual Login Required]
        G --> B
    end

    subgraph Phase2["Phase 2: Social Promotion"]
        D & E & F --> H[Recipe: Event Social Promotion]
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
| **Luma** | Browser | Tested | Session persists |
| **Meetup** | Browser | Tested | May need re-auth |
| **Partiful** | Browser | Tested | Session persists |
| **Twitter/X** | API | Working | OAuth connected |
| **LinkedIn** | API | Working | OAuth connected |
| **Instagram** | API | Working | Business account required |
| **Facebook** | API | Partial | Page permissions needed |
| **Discord** | API | Partial | Bot re-authorization needed |

## Authentication Flow

```mermaid
flowchart TD
    A[Navigate to Platform] --> B{Already Logged In?}
    B -->|Yes| C[Proceed to Form]
    B -->|No| D[Detect Login Page]
    D --> E{2FA Required?}
    E -->|No| F[Auto-login if credentials stored]
    E -->|Yes| G[PAUSE: Request 2FA Code]
    G --> H[User Enters Code]
    H --> I[Complete Login]
    F --> C
    I --> C
    C --> J[Fill Form with AI Agent]
    J --> K[Submit/Publish]
    K --> L[Capture Event URL]
```

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
├── docs/
│   ├── event-creation.md        # Detailed event creation docs
│   ├── social-promotion.md      # Detailed social promotion docs
│   └── troubleshooting.md       # Common issues & solutions
├── recipes/
│   ├── create_event.py          # Event creation recipe code
│   └── social_promotion.py      # Social promotion recipe code
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
