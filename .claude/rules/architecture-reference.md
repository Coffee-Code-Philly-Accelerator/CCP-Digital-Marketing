# Architecture Reference

## Rust Backend Modules (`gui/src-tauri/src/`)

| Module | Purpose |
|--------|---------|
| `main.rs` | Tauri app setup, plugin registration, IPC command registration |
| `config.rs` | `AppConfig` struct, recipe IDs, platform constants (reads `COMPOSIO_API_KEY` + `CCP_*` env vars) |
| `composio.rs` | `ComposioClient` -- HTTP client for Composio v3 tool router session API (execute_tool, poll, get details) |
| `recipe_commands.rs` | 5 IPC commands: `create_event`, `promote_event`, `social_post`, `full_workflow`, `get_recipe_info` |
| `draft_commands.rs` | 5 IPC commands: `generate_drafts`, `list_drafts_cmd`, `load_draft_cmd`, `approve_draft`, `publish_draft` |
| `draft.rs` | Draft types + pure functions (slugify, build, validate) + file I/O -- mirrors `scripts/draft_store.py` |
| `progress.rs` | `RecipeProgressEvent` struct + `emit_progress()` -- emits `recipe-progress` Tauri events to frontend |
| `db.rs` | Telemetry SQLite queries: `list_workflows`, `get_workflow_tool_calls`, `search_correlation`, `cleanup_expired` |

## Tauri IPC Commands

| Command | Module | Description |
|---------|--------|-------------|
| `create_event` | recipe_commands.rs | Create event on platforms (Luma, Meetup, Partiful) |
| `promote_event` | recipe_commands.rs | Post event to social media platforms |
| `social_post` | recipe_commands.rs | Generic social media post |
| `full_workflow` | recipe_commands.rs | Create event + promote (full pipeline) |
| `get_recipe_info` | recipe_commands.rs | Get recipe configuration info |
| `generate_drafts` | draft_commands.rs | Generate draft copies + image via v3 API |
| `list_drafts_cmd` | draft_commands.rs | List all draft JSON files |
| `load_draft_cmd` | draft_commands.rs | Load a specific draft by filename |
| `approve_draft` | draft_commands.rs | Set draft status to approved |
| `publish_draft` | draft_commands.rs | Publish approved draft to social platforms |

## Frontend Files (`gui/src/`)

| File | Purpose |
|------|---------|
| `index.html` | Main HTML shell with 4-tab layout |
| `app.js` | Shared utilities, tab switching, Tauri API bridge |
| `progress.js` | Real-time recipe progress listener (Tauri events) |
| `timeline.js` | Telemetry timeline visualization |
| `search.js` | Telemetry search and correlation |
| `event-form.js` | Create Event tab form logic |
| `social-post-form.js` | Social Post tab form logic |
| `drafts-view.js` | Drafts tab -- list, preview, approve, publish |

## Python Scripts (`scripts/`)

| File | Purpose |
|------|---------|
| `recipe_client.py` | CLI client for executing Composio recipes (create-event, promote, social-post, etc.) |
| `draft_store.py` | Draft CRUD operations -- pure functions + file I/O boundary |
| `validate_recipes.py` | AST-based structural validation of recipe files |

## Recipes (`recipes/`)

| File | Recipe ID | Purpose |
|------|-----------|---------|
| `create_event_luma.py` | `rcp_mXyFyALaEsQF` | Create event on Luma via browser automation |
| `create_event_meetup.py` | `rcp_kHJoI1WmR3AR` | Create event on Meetup via browser automation |
| `create_event_partiful.py` | `rcp_bN7jRF5P_Kf0` | Create event on Partiful via browser automation |
| `social_promotion.py` | `rcp_X65IirgPhwh3` | Post event to 5 social platforms |
| `social_post.py` | `rcp_3LheyoNQpiFK` | Generic social media post |
| `email_reply.py` | `rcp_NLnlCNmIcIuN` | Three-pass email reply review |
| `auth_setup.py` | N/A | Standalone Hyperbrowser auth profile setup |

## Database Schema (`db.rs`)

**`workflows` table:**
- `id` TEXT PRIMARY KEY
- `user_id` TEXT
- `workflow_type` TEXT (`create_event`, `promote_event`, `social_post`, `full_workflow`)
- `status` TEXT (`pending`, `running`, `completed`, `failed`)
- `created_at` TEXT (ISO-8601)
- `updated_at` TEXT (ISO-8601)

**`tool_calls` table:**
- `id` TEXT PRIMARY KEY
- `workflow_id` TEXT (FK -> workflows.id)
- `tool_name` TEXT (Composio tool slug)
- `status` TEXT (`pending`, `running`, `completed`, `failed`)
- `latency_ms` INTEGER
- `request_json` TEXT
- `response_json` TEXT
- `created_at` TEXT (ISO-8601)

## Key Query Functions (`db.rs`)

| Function | Purpose |
|----------|---------|
| `list_workflows(limit, offset)` | Paginated workflow list with tool call counts |
| `get_workflow_tool_calls(workflow_id)` | All tool calls for a specific workflow |
| `search_correlation(query)` | Full-text search across workflows and tool calls |
| `cleanup_expired(days)` | Delete workflows older than N days |

## Config Environment Variables (`config.rs`)

All prefixed with `CCP_` (except `COMPOSIO_API_KEY`). See CLAUDE.md Environment Variables table for full list. Key ones:

- `COMPOSIO_API_KEY` -- Required for all recipe execution
- `CCP_BROWSER_PROVIDER` -- `hyperbrowser` (default) or `browser_tool`
- `CCP_CACHE_DB_PATH` -- SQLite telemetry database path
- `CCP_COMPOSIO_USER_ID` -- Composio user ID for v3 sessions (default: "default")
