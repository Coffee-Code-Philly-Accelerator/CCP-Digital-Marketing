# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CCP Digital Marketing automates event creation and social media promotion for Coffee Code Philly Accelerator using Rube MCP (Composio).

**Three-phase workflow:**
1. **Content Staging** - AI generates platform-specific descriptions + promotional image; user reviews/edits before publishing
2. **Event Creation** - Browser automation for Luma, Meetup, Partiful (no public APIs)
3. **Social Promotion** - Direct API integrations for Twitter, LinkedIn, Instagram, Facebook, Discord

## Development Commands

### Recipe Client (scripts/)

```bash
pip install -r scripts/requirements.txt
export COMPOSIO_API_KEY='your-key'

# Create event on all platforms (Luma, Meetup, Partiful)
python scripts/recipe_client.py create-event \
  --title "Event Name" --date "January 25, 2025" --time "6:00 PM EST" \
  --location "Venue" --description "Description" \
  --meetup-url "https://www.meetup.com/code-coffee-philly"

# Skip specific platforms
python scripts/recipe_client.py create-event \
  --title "Event Name" --date "January 25, 2025" --time "6:00 PM EST" \
  --location "Venue" --description "Description" \
  --skip "meetup,partiful"

# Promote on social media
python scripts/recipe_client.py promote \
  --title "Event Name" --date "January 25, 2025" --time "6:00 PM EST" \
  --location "Venue" --description "Description" \
  --event-url "https://lu.ma/abc123"

python scripts/recipe_client.py full-workflow [same args]

# Generic social post (not event-specific)
python scripts/recipe_client.py social-post \
  --topic "New Partnership" --content "We're partnering with TechHub!" \
  --url "https://example.com" --tone "excited"

python scripts/recipe_client.py info
```

### Tauri GUI (gui/)

```bash
# Build the desktop app
cd gui/src-tauri && cargo build

# Run the desktop app (requires COMPOSIO_API_KEY for recipe execution)
cd gui/src-tauri && cargo run

# Build release
cd gui/src-tauri && cargo build --release
```

## Architecture

**Rube MCP Recipes** (`recipes/`) - Self-contained Python scripts for Composio's Rube MCP runtime. These use `os.environ.get()` for inputs, `run_composio_tool()` for APIs, `invoke_llm()` for AI. Output is a bare variable (no return statement). Include mock implementations for local testing.

### Tauri GUI (`gui/`)

Desktop app providing both workflow telemetry viewing and recipe execution. Built with Tauri v2 (Rust backend + vanilla JS frontend).

> See `.claude/rules/architecture-reference.md` for full module reference, IPC commands, DB schema, and file inventory.

**Frontend** (`gui/src/`): 4-tab UI — Telemetry, Create Event, Social Post, Drafts. Real-time progress via Tauri event listener. Dark theme matching VS Code palette (#1e1e1e / #252526 / #4ec9b0).

**Draft interop:** Rust GUI and Python CLI use identical JSON schema for drafts in `drafts/`. Files created by either are readable by both.

## Recipe Code Pattern

Recipes in `recipes/` follow this pattern for Rube MCP runtime:
```python
"""RECIPE: Name  |  RECIPE ID: rcp_xxxxx"""
import os
event_title = os.environ.get("event_title")
result, error = run_composio_tool("TOOL_NAME", {args})
response, error = invoke_llm("prompt")
output = {...}  # bare variable, no return statement
output
```

## Key Recipes

| Recipe | ID | Purpose |
|--------|-----|---------|
| Create Event (Luma) | `rcp_mXyFyALaEsQF` | AI browser agent creates event on lu.ma |
| Create Event (Meetup) | `rcp_kHJoI1WmR3AR` | AI browser agent creates event on Meetup |
| Create Event (Partiful) | `rcp_bN7jRF5P_Kf0` | AI browser agent creates event on Partiful |
| Social Promotion | `rcp_X65IirgPhwh3` | Parallel API posting to 5 social platforms |
| Social Post | `rcp_3LheyoNQpiFK` | Generic social media post (non-event content) |
| Email Reply | `rcp_NLnlCNmIcIuN` | Three-pass review of email replies (clarity, grammar, tone); generate or review mode |

All event creation recipes default to Hyperbrowser (`HYPERBROWSER_START_BROWSER_USE_TASK`) with persistent auth profiles, falling back to Composio's `BROWSER_TOOL_CREATE_TASK` when configured. Both use a single AI browser agent call + polling pattern instead of the old multi-step state machine with sequential `NAVIGATE`/`PERFORM_WEB_TASK`/`FETCH_WEBPAGE` calls that exceeded the 4-minute Rube runtime timeout.

## Default Configuration

| Platform | URL |
|----------|-----|
| Meetup Group | `https://www.meetup.com/code-coffee-philly` |

**Note:** The Meetup group slug is `code-coffee-philly` (not `coffee-code-philly`).

## Composio Tool Reference

### Browser Automation (v3 - Hyperbrowser, Primary)
- `HYPERBROWSER_CREATE_PROFILE` - Create persistent browser profile (saves cookies/auth across sessions)
- `HYPERBROWSER_CREATE_SESSION` - Start browser session with profile, stealth mode, cookie acceptance
- `HYPERBROWSER_START_BROWSER_USE_TASK` - Launch AI browser agent with natural language task + session options
- `HYPERBROWSER_GET_BROWSER_USE_TASK_STATUS` - Poll task status (running/completed/failed)
- `HYPERBROWSER_GET_SESSION_DETAILS` - Get session liveUrl for real-time browser watching

> **Note:** Hyperbrowser provides persistent profiles that save login cookies across sessions, solving the auth expiry issue with Composio's ephemeral browser_tool sessions. All event creation recipes default to Hyperbrowser.

### Browser Automation (v2 - Composio browser_tool, Fallback)
- `BROWSER_TOOL_CREATE_TASK` - Launch AI browser agent with natural language task description + startUrl
- `BROWSER_TOOL_WATCH_TASK` - Poll task status (started/finished/stopped), returns current_url, is_success, output
- `BROWSER_TOOL_GET_SESSION` - Get liveUrl for real-time browser watching

### Browser Automation (v1 - Deprecated)
- `BROWSER_TOOL_NAVIGATE` - Navigate to URL, returns pageSnapshot
- `BROWSER_TOOL_PERFORM_WEB_TASK` - AI agent fills forms via natural language prompt
- `BROWSER_TOOL_FETCH_WEBPAGE` - Get current page state
- `BROWSER_TOOL_TAKE_SCREENSHOT` - Capture screenshot (debugging)

> **Note:** v1 tools require ~10 sequential calls for event creation, exceeding the 4-minute Rube runtime timeout. All recipes now use v2 (browser_tool) or v3 (Hyperbrowser).

### Social APIs
- `TWITTER_CREATION_OF_A_POST`
- `LINKEDIN_GET_MY_INFO` / `LINKEDIN_CREATE_LINKED_IN_POST`
- `INSTAGRAM_GET_USER_INFO` / `INSTAGRAM_CREATE_MEDIA_CONTAINER` / `INSTAGRAM_GET_POST_STATUS` / `INSTAGRAM_CREATE_POST`
- `FACEBOOK_CREATE_POST`
- `DISCORDBOT_CREATE_MESSAGE`

### Email APIs
- `GMAIL_GET_MESSAGE` - Read email by message ID (requires gmail.readonly scope)
- `OUTLOOK_GET_MESSAGE` - Read email by message ID (requires Mail.Read scope)

### AI
- `GEMINI_GENERATE_IMAGE` - Image generation (model: gemini-2.5-flash-image)
- `invoke_llm()` - LLM content generation (recipe runtime only)

## Platform-Specific Quirks

| Platform | Issue | Mitigation |
|----------|-------|------------|
| Luma | React date picker | Task instructions include explicit 2s waits after date selection |
| Meetup | Anti-bot detection | Task instructions include 2s waits between all form actions |
| Partiful | Share modal after creation | Task instructions dismiss modal before URL extraction |
| All | Session expiry | Browser task navigates to login page; recipe reports failure |
| All | Image upload via URL | Browser agent attempts URL import; gracefully skips if not available |

## Browser Provider Configuration

Event creation recipes support two browser providers, controlled by `CCP_BROWSER_PROVIDER`:

| Provider | Value | Description |
|----------|-------|-------------|
| Hyperbrowser | `hyperbrowser` (default) | Persistent profiles with saved auth. Requires one-time profile setup per platform. |
| Composio browser_tool | `browser_tool` | Ephemeral sessions (no auth persistence). Original provider, now fallback. |

### Auth Setup

Before using Hyperbrowser, set up persistent profiles for each platform:
1. Run the **auth-setup** skill for each platform (Luma, Meetup, Partiful)
2. Complete Google OAuth login in the browser window
3. Save the profile IDs to your `.env` file

### Re-Authentication

If a recipe returns `NEEDS_AUTH`, re-run auth-setup with the existing `profile_id` to re-login without creating a new profile.

## Common Patterns

### Nested Data Extraction
Composio responses often double-nest. In recipes:
```python
data = result.get("data", {})
if "data" in data:
    data = data["data"]
```

### Auth Detection
```python
AUTH_PATTERNS = ["sign in", "log in", "login", "verification code", "2fa"]
def check_needs_auth(page_content):
    return any(p in page_content.lower() for p in AUTH_PATTERNS)
```

### Skip Platforms
Recipes accept skip lists: `{"skip_platforms": "meetup,facebook"}`

### Duplicated Recipe Helpers
`sanitize_input()`, `extract_data()`, and `extract_json_from_text()` are duplicated across recipe files (required by Rube's self-contained runtime). Browser-automation recipes (luma, meetup, partiful) include apostrophe escaping (`'` → `\u2019`); non-browser recipes omit it. When updating these helpers, sync all copies and preserve this intentional divergence.

## Status Codes

| Status | Meaning | Action |
|--------|---------|--------|
| `PUBLISHED`/`DONE` | Success | None |
| `NEEDS_AUTH` | Browser session expired | Log in manually, re-run |
| `FAILED` | Error occurred | Check error message |
| `SKIPPED` | Intentionally skipped | Via skip_platforms param |
| `DRAFT_GENERATED` | Draft copies created (not posted) | Review, edit, approve, then publish |

## Draft Workflow (Social Promotion)

The social promotion recipe supports a two-phase draft workflow for human review before publishing.

### Recipe `mode` Parameter

| Mode | Image Gen | Copy Gen | Posting | Output |
|------|-----------|----------|---------|--------|
| `""` (default) | Yes | Yes | Yes | Current output (backwards compatible) |
| `generate_only` | Yes | Yes | Skip | `{"status": "DRAFT_GENERATED", "copies": {...}, "image_url": "..."}` |
| `publish_only` | Skip (uses `image_url`) | Skip (uses `pre_generated_copies`) | Yes | Posting results |

### Draft JSON Schema

Drafts are saved as JSON files in `drafts/` at the project root:

```json
{
  "version": 1,
  "status": "draft|approved|published|failed",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601",
  "event": {"title": "", "date": "", "time": "", "location": "", "description": "", "url": ""},
  "image_url": "https://...",
  "copies": {"twitter": "", "linkedin": "", "instagram": "", "facebook": "", "discord": ""},
  "platform_config": {"discord_channel_id": "", "facebook_page_id": "", "skip_platforms": ""},
  "publish_results": null
}
```

**Status lifecycle:** `draft` -> `approved` -> `published` (or `failed`)

### CLI Commands

```bash
# Generate event promotion drafts (calls recipe with mode=generate_only, saves to drafts/)
python scripts/recipe_client.py generate-drafts \
  --title "Event" --date "March 20, 2026" --time "6:00 PM EST" \
  --location "Philly" --description "Desc" --event-url "https://example.com"

# Generate social post drafts (non-event)
python scripts/recipe_client.py generate-social-post-draft \
  --topic "New Partnership" --content "We're partnering with TechHub!" \
  --url "https://example.com" --tone "excited"

# List all drafts
python scripts/recipe_client.py list-drafts

# Approve a draft
python scripts/recipe_client.py approve-draft --file drafts/<filename>.json

# Publish an approved draft
python scripts/recipe_client.py publish-draft --file drafts/<filename>.json
```

### Draft Store Module

`scripts/draft_store.py` provides pure functions (`slugify`, `build_draft`, `set_draft_status`, `validate_draft_for_publish`) and I/O boundary functions (`save_draft`, `load_draft`, `list_drafts`).

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `COMPOSIO_API_KEY` | Yes | - | Composio API authentication |
| `CCP_COMPOSIO_API_BASE` | No | `https://backend.composio.dev/api/v1` | Composio API base URL |
| `CCP_DISCORD_CHANNEL_ID` | No | (empty) | Default Discord channel ID |
| `CCP_FACEBOOK_PAGE_ID` | No | (empty) | Default Facebook page ID |
| `CCP_MEETUP_GROUP_URL` | No | `https://www.meetup.com/code-coffee-philly` | Default Meetup group URL |
| `CCP_LUMA_CREATE_URL` | No | `https://lu.ma/create` | Override Luma create page URL |
| `CCP_PARTIFUL_CREATE_URL` | No | `https://partiful.com/create` | Override Partiful create page URL |
| `CCP_BROWSER_PROVIDER` | No | `hyperbrowser` | Browser provider: "hyperbrowser" or "browser_tool" |
| `CCP_LUMA_PROFILE_ID` | No | (empty) | Hyperbrowser profile UUID for Luma |
| `CCP_MEETUP_PROFILE_ID` | No | (empty) | Hyperbrowser profile UUID for Meetup |
| `CCP_PARTIFUL_PROFILE_ID` | No | (empty) | Hyperbrowser profile UUID for Partiful |
| `CCP_HYPERBROWSER_LLM` | No | `claude-sonnet-4-20250514` | LLM for Hyperbrowser browser agent |
| `CCP_HYPERBROWSER_MAX_STEPS` | No | `25` | Max agent steps per browser task |
| `CCP_HYPERBROWSER_USE_STEALTH` | No | `true` | Stealth mode for anti-bot evasion |
| `CCP_CACHE_DB_PATH` | No | `~/.claude/cache/state.db` | SQLite database for telemetry cache (GUI) |
| `CCP_PROJECT_ROOT` | No | (auto-detected) | Project root for draft file resolution (GUI) |
| `CCP_DRAFTS_DIR` | No | `<project_root>/drafts` | Override drafts directory path (GUI) |

**Override Precedence:** Recipe input parameters > Environment variables > Defaults

## Via Rube MCP Tools

```python
RUBE_EXECUTE_RECIPE(
    recipe_id="rcp_mXyFyALaEsQF",
    input_data={"event_title": "...", "event_date": "...", ...}
)
```

## Claude Code Skills

Skills are defined in `.claude/skills/`. Each wraps a `RUBE_EXECUTE_RECIPE` call. Event creation recipes default to Hyperbrowser (single AI browser agent with persistent auth) and return a `live_url` for real-time watching.

| Skill | Directory | Recipe ID | Purpose |
|-------|-----------|-----------|---------|
| Luma Create | `luma-create/` | `rcp_mXyFyALaEsQF` | Create event on Luma via browser automation |
| Meetup Create | `meetup-create/` | `rcp_kHJoI1WmR3AR` | Create event on Meetup via browser automation |
| Partiful Create | `partiful-create/` | `rcp_bN7jRF5P_Kf0` | Create event on Partiful via browser automation |
| Social Promote | `social-promote/` | `rcp_X65IirgPhwh3` | Post event to Twitter, LinkedIn, Instagram, Facebook, Discord |
| Social Post | `social-post/` | `rcp_3LheyoNQpiFK` | Post generic content (non-event) to social media platforms |
| Email Reply | `email-reply/` | `rcp_NLnlCNmIcIuN` | Three-pass review of email replies (clarity, grammar, tone); generate from Gmail/Outlook or review drafts |
| Stage Event | `stage-event/` | N/A (Claude + GEMINI) | Generate platform-specific descriptions + image, preview for user review |
| Full Workflow | `full-workflow/` | All of the above | Orchestrate: stage content, create on all platforms, then promote on social media |
| Auth Setup | `auth-setup/` | N/A (direct tool calls) | Set up Hyperbrowser persistent auth profiles |

**Chaining:** The social-promote and full-workflow skills accept an optional `image_url` input. When provided (e.g., from a prior event creation), the social promotion recipe skips Gemini image generation and reuses the existing image.

---

## Claude Code Commands

Commands are defined in `.claude/commands/`. Each provides an interactive workflow invoked via `/command-name`.

| Command | Description |
|---------|-------------|
| `/code-review` | Multi-model consensus code review via PAL MCP |
| `/tdd` | Strict Red-Green-Refactor TDD workflow |
| `/test-coverage` | Coverage gap analysis and test generation |
| `/pr-check` | Run all 6 local CI checks with interactive fix loop |
| `/pr` | Create branch, commit, push, create PR, fix failing checks |
| `/push` | Push to origin remote with confirmation |
| `/log-fix` | Query SQLite telemetry DB, triage failures, interactive bug fixing |
| `/evaluate` | Recipe validation and design principle compliance checks |
| `/docs-update` | Review and update CLAUDE.md against recent git changes |
| `/deep-research` | Web search + multi-model consensus research reports |
| `/team-plan` | Decompose tasks into agent workstreams with PAL MCP consensus |

## Claude Code Rules

Rules in `.claude/rules/` are automatically loaded and provide persistent context:

| Rule | Purpose |
|------|---------|
| `architecture-reference.md` | Module reference, IPC commands, DB schema, file inventory |
| `logging.md` | SQLite telemetry architecture, progress events, query examples |

---

## CI/CD Pipeline

### Core CI (`.github/workflows/ci.yml`)

Runs on push to `main` and all PRs. All jobs must pass for merge (enforced by `ci-pass` gate job).

| Job | What it checks |
|-----|---------------|
| **Lint (Ruff)** | `ruff check scripts/ recipes/` |
| **Format (Ruff)** | `ruff format --check scripts/ recipes/` |
| **Recipe Validation** | `python scripts/validate_recipes.py` |
| **Security Scan** | `bandit -r scripts/ recipes/ -ll` + `pip-audit` |
| **Test** | `pytest tests/` across Python 3.10-3.13 matrix |
| **Cargo Check** | `cargo clippy -- -D warnings` + `cargo fmt -- --check` (Tauri/Rust) |
| **Design Principles** | Let It Crash compliance, KISS metrics, Pure Functions check |

### AI Code Review (3-phase)

| Phase | Workflow | Trigger | Purpose |
|-------|----------|---------|---------|
| Phase 1 | `claude-review-phase1.yml` | PR opened | Fast triage review |
| Phase 2 | `claude-review-phase2.yml` | PR opened | Deep review with PAL MCP consensus |
| Phase 3 | `claude-review-phase3.yml` | PR opened | Security-focused review with guardrails |
| Interactive | `claude-interactive.yml` | `@claude` comment | Answer questions, push fixes to PR |

All AI review workflows use **Bedrock (primary) + Anthropic API (fallback)** dual-provider pattern.

### Autonomous Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `issue-to-pr.yml` | Issue labeled `claude-fix` | Auto-generate fix PR from issue description |
| `nightly-code-review.yml` | Cron (4 AM UTC weekdays) | Scan recent changes, create improvement PRs |
| `autonomous-code-scanner.yml` | Scheduled | Automated formatting + security scanning |
| `nightly-docs-update.yml` | Scheduled | Keep CLAUDE.md in sync with code changes |

All autonomous workflows create **draft PRs only** with `ai-generated` + `needs-human-review` labels.

### Operational Workflows

| Workflow | Purpose |
|----------|---------|
| `commit-notifications.yml` | Slack notifications for commits via Composio |
| `release-notes.yml` | Auto-generate release notes |
| `ai-issue-triage.yml` | AI-powered issue labeling and routing |
| `ai-review-cost-monitor.yml` | Track AI review API costs |
| `pal-consensus-review.yml` | Multi-model consensus on PRs |

### Protected Paths

Centralized in `.github/config/protected-paths.json`. Autonomous workflows revert changes to these paths:
- `.github/workflows/*`, `.env*`, `recipes/`, `gui/src-tauri/src/`, `CLAUDE.md`, `Cargo.toml`, `tauri.conf.json`

### Required Secrets

| Secret | Purpose |
|--------|---------|
| `ANTHROPIC_API_KEY` | Claude Code API (fallback provider) |
| `AWS_BEARER_TOKEN_BEDROCK` | AWS Bedrock (primary provider) |
| `AWS_REGION` | Bedrock region (default: us-east-1) |
| `PAT_TOKEN` | PR creation (repo + workflow scopes) |
| `GEMINI_API_KEY` | PAL MCP consensus (Gemini model) |
| `OPENAI_API_KEY` | PAL MCP consensus (GPT model) |
| `RUBE_API_TOKEN` | Slack notifications via Composio |
| `SLACK_CONNECTED_ACCOUNT_ID` | Slack account for notifications |

### Setup

1. Install the Claude GitHub App: `github.com/apps/claude`
2. Configure secrets (run `.github/workflows/setup-claude-review.sh` for guided setup)
3. See `.github/workflows/CLAUDE_REVIEW_SETUP.md` for detailed instructions

---

# Design Philosophy

> **Instruction to Agent:** Consult the following principles before generating any new classes, functions, or error handling logic.

## Principle Priority (Conflict Resolution)

When principles conflict, follow this priority order:

1. **Let It Crash** (highest) - Visibility of errors trumps all
2. **KISS** - Simplicity over elegance
3. **Pure Functions** - Determinism over convenience
4. **SOLID** (lowest) - Architecture can flex for simplicity

**Example Conflicts:**
- **KISS vs Pure Functions**: If dependency injection adds excessive ceremony for a simple utility, prefer the simpler impure version with a comment.
- **SOLID vs KISS**: If an abstraction has only 1 use case, keep it inline even if it violates OCP.
- **Let It Crash vs KISS**: A visible crash is NEVER simplified away with a silent fallback.

---

## CRITICAL: Let It Crash (Primary Principle)

**CORE PRINCIPLE**: Embrace controlled failure. NO defensive programming. NO exponential backoffs. NO complex fallback chains. Let errors propagate and crash visibly.

**The Golden Rule: Do NOT write `try/except`. Period.** The default for every function is zero error handling. Errors propagate, crash visibly, and give a full stack trace.

**Use error-returning patterns instead.** This codebase uses `run_composio_tool()` returning `(result, error)` tuples. Check the error value explicitly -- no exceptions needed.

```python
# GOOD - Error values, not exceptions
result, error = run_composio_tool("TOOL_NAME", args)
if error:
    output = {"status": "FAILED", "error": error}
else:
    output = {"status": "DONE", "data": result}

# GOOD - Validate inputs up front, don't catch failures later
if not all([event_title, event_date, event_time]):
    raise ValueError("Missing required inputs")
# Now proceed knowing inputs are valid -- no defensive checks downstream
```

**FORBIDDEN patterns** (all of these hide root causes and delay fixes):
- `try/except Exception: pass` — silent swallowing
- `try/except: return None` — exception as control flow
- Retry/backoff loops wrapping try/except
- Nested try/except fallback chains
- Defensive null checks that obscure the real problem (validate once at boundary, trust downstream)

**The ONLY exception:** If a third-party library forces exception-based error handling, catch **one specific exception type** with a `# LET-IT-CRASH-EXCEPTION` annotation (e.g., `except ImportError` for optional imports). If you want more than this, **stop and redesign**.

**Code review rule:** Any `try/except` in a PR requires explicit justification. Default stance: remove it. Tests should also crash on unexpected errors -- never swallow exceptions to make tests pass.

---

## SOLID Principles

**CORE PRINCIPLE**: High cohesion, low coupling. Don't over-engineer -- for simple utilities, pragmatism > purity.

- **SRP** — Each function/module does ONE thing. Separate sanitization, payload construction, API calls, and formatting into distinct functions.
- **OCP** — Extend via configuration, not modification. Use dicts/maps to add new behavior without changing existing code.
- **LSP** — Implementations honor the base contract. Never strengthen preconditions, weaken postconditions, or throw unexpected errors. Return consistent shapes (e.g., `{"status": "SKIPPED"}` instead of raising).
- **ISP** — Keep interfaces minimal and focused. Functions take only what they need (explicit params, not god-objects). Traits/classes cover one concern.
- **DIP** — Depend on abstractions. Inject dependencies (API keys, clients) as parameters for testability. No `os.environ[]` deep in business logic.

```python
# BAD - Must modify function for new platforms
def create_event(platform: str, details: dict):
    if platform == "luma":
        return create_luma_event(details)
    elif platform == "meetup":
        return create_meetup_event(details)

# GOOD - Extensible via configuration (OCP)
PLATFORM_RECIPES = {
    "luma": "rcp_mXyFyALaEsQF",
    "meetup": "rcp_kHJoI1WmR3AR",
    "partiful": "rcp_bN7jRF5P_Kf0",
}

def create_event(platform: str, details: dict):
    recipe_id = PLATFORM_RECIPES[platform]
    return execute_recipe(recipe_id, details)
```

---

## KISS Principle (Keep It Simple, Stupid)

**CORE PRINCIPLE**: Simplicity is a key design goal. Unnecessary complexity is the enemy of reliability.

> Decision metric: "Can the next engineer accurately predict behavior and modify it safely?"

- **Readable over Clever** — Code any developer can understand beats elegant one-liners
- **Explicit over Implicit** — Clear intentions trump magic behavior
- **Avoid Premature Abstraction** — Wait for 3+ use cases before abstracting
- **Avoid Premature Optimization** — Simple first, optimize when proven necessary

| Metric | Threshold | Action |
|--------|-----------|--------|
| Function length | > 30 lines | Consider splitting |
| Cyclomatic complexity | > 15 | Refactor required |
| Nesting depth | > 3 levels | Flatten with early returns |
| Parameters | > 8 | Consider parameter object |
| File length | > 500 lines | Consider module split |

```python
# BAD - Clever but hard to understand
def process(d): return {k: v.strip().lower() for k, v in d.items() if v and isinstance(v, str) and not k.startswith('_')}

# GOOD - KISS approach
def normalize_data(data: dict[str, str]) -> dict[str, str]:
    result = {}
    for key, value in data.items():
        if key.startswith('_'):
            continue
        if not isinstance(value, str):
            continue
        result[key] = value.strip().lower()
    return result
```

---

## Pure Functions

**CORE PRINCIPLE**: Functions should be deterministic transformations with no side effects -- output depends ONLY on inputs.

1. **Deterministic**: Same inputs -> same output (always, every time)
2. **No Side Effects**: No mutation, no I/O, no external state modification

**What makes a function impure:** global state, mutating inputs, I/O (`print`, file, network), non-determinism (`datetime.now()`), external calls. Fix by passing as parameters and pushing I/O to boundaries.

**Default to pure** for business logic, validation, data formatting. Push I/O to boundaries. If purity adds excessive wiring, KISS wins -- prefer a small explicit side effect over complex parameter threading.

```python
# PURE CORE - Business logic as pure functions
def build_task_description(title: str, date: str, time: str, location: str, description: str) -> str:
    return f"""Create an event with these details:
    Title: {title}
    Date: {date}
    Time: {time}
    Location: {location}
    Description: {description}"""

def determine_primary_url(luma_url: str, meetup_url: str, partiful_url: str) -> str:
    return luma_url or meetup_url or partiful_url or ""

# IMPERATIVE SHELL - Side effects at boundaries only
def run_event_creation(event_details: dict) -> dict:
    result, error = run_composio_tool("BROWSER_TOOL_CREATE_TASK", {
        "task": build_task_description(**event_details),
    })
    primary_url = determine_primary_url(
        result.get("luma_url", ""), result.get("meetup_url", ""), result.get("partiful_url", ""),
    )
    return {"event_url": primary_url, "status": "done"}
```
