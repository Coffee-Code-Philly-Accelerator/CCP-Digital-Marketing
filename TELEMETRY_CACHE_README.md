# CCP Telemetry Cache - Rust State Cache for Claude Skills

## Overview

A transparent Rust-based telemetry cache that captures every Composio API call during Claude skill automation workflows. Provides tool-call level observability with SQLite storage, HTTP proxy interception, and a Tauri desktop GUI.

## Architecture

### Components

1. **Data Layer** (`cache_db/`) - SQLite schema and Repository trait
2. **Proxy Service** (`proxy/`) - HTTP interceptor with async persistence
3. **Tauri GUI** (`gui/`) - Desktop app with timeline visualization

### Design Principles

All code follows `CLAUDE.md` principles:
- **Let It Crash**: Errors propagate visibly, no silent failures
- **KISS**: Simple solutions, plain TEXT for JSON, no over-engineering
- **Pure Functions**: Deterministic transformations with no side effects
- **SOLID**: Repository trait abstraction, single responsibility

## Quick Start

### Prerequisites

- Rust 1.70+ (`rustup install stable`)
- SQLite 3.x
- For GUI: System dependencies for Tauri (see [Tauri Prerequisites](https://tauri.app/start/prerequisites/))

### Build & Run Proxy

```bash
cd proxy
cargo build --release

# Run proxy (intercepts Composio API calls)
CCP_PROXY_PORT=8765 \
CCP_COMPOSIO_API_BASE=https://backend.composio.dev/api/v1 \
CCP_CACHE_DB_PATH=~/.claude/cache/state.db \
cargo run --release
```

### Configure recipe_client.py

Set environment variable to route through proxy:

```bash
export COMPOSIO_API_BASE=http://localhost:8765
python scripts/recipe_client.py info  # Test - this call will be captured
```

### Build & Run GUI

```bash
cd gui
cargo tauri build  # Or `cargo tauri dev` for development

# Run GUI
./src-tauri/target/release/ccp-cache-gui
```

## Database Schema

### Three-Table Design

```
workflows (1) --< (N) phases (1) --< (N) tool_calls
```

**workflows**: Top-level execution context (user_id, workflow_type, status, input_params_json)
**phases**: Logical groupings (staging, luma-create, social-promotion)
**tool_calls**: Individual API calls (tool_name, request_json, response_json, latency_ms)

### Key Features

- **TEXT JSON storage**: Simple, portable, no extensions
- **WAL mode**: Concurrent reads during writes
- **7-day TTL**: Automatic cleanup via `cleanup_expired()`
- **Read-time correlation**: SQL LIKE queries on JSON

## Proxy Service

### How It Works

1. Listens on `0.0.0.0:8765` (configurable via `CCP_PROXY_PORT`)
2. Client (recipe_client.py) sends HTTP request to proxy
3. Proxy forwards to Composio API as HTTPS
4. Captures request/response with timing (target <10ms overhead)
5. Masks PII (api_key, auth_token, password fields)
6. Sends to async SQLite writer via mpsc channel (non-blocking)
7. Returns response to client

### Architecture

```
Client → HTTP (8765) → Proxy → HTTPS → Composio API
                          ↓
                    mpsc channel
                          ↓
                   SQLite Writer (async)
```

### PII Masking

Automatically redacts:
- `api_key`
- `auth_token`
- `password`
- `access_token`
- `Authorization` headers

Replacement: `"[REDACTED]"`

## GUI Features

### Workflow List

- Filter by workflow type (full-workflow, create-event, promote, etc.)
- Filter by status (running, completed, failed, partial)
- Sort by creation time
- Click row to view timeline

### Timeline Visualization

- Gantt-style view of tool calls
- Color-coded by status (green=success, red=error, yellow=pending)
- Shows latency per tool call
- Displays relative timing within workflow

### Correlation Search

- Search for artifacts across workflows (e.g., `image_url`, `event_url`)
- SQL LIKE queries on JSON TEXT fields
- Shows all workflows that reference the artifact

### TTL Cleanup

- Manual cleanup button: delete workflows older than 7 days
- Background task (future): hourly automated cleanup

## File Structure

```
cache_db/
├── schema.sql              # SQLite schema (3 tables)
├── repository.rs           # Repository trait definition
└── migrations/
    └── 001_initial.sql     # Idempotent migration

proxy/
├── Cargo.toml
└── src/
    ├── lib.rs              # Module exports
    ├── main.rs             # Proxy server entry
    ├── interceptor.rs      # HTTP interception logic
    ├── persistence.rs      # SQLite writer with mpsc channel
    └── pii_mask.rs         # Pure function PII masking

gui/
├── src-tauri/
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   ├── build.rs
│   └── src/
│       ├── main.rs         # Tauri app entry
│       └── db.rs           # SQLite query commands
└── src/
    ├── index.html          # Main UI
    ├── timeline.js         # Timeline visualization
    └── search.js           # Correlation search
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CCP_PROXY_PORT` | `8765` | Proxy listen port |
| `CCP_COMPOSIO_API_BASE` | `https://backend.composio.dev/api/v1` | Upstream Composio API |
| `CCP_CACHE_DB_PATH` | `~/.claude/cache/state.db` | SQLite database file |
| `COMPOSIO_API_BASE` | (set to `http://localhost:8765`) | Route client through proxy |

## Testing

### Unit Tests

```bash
# Test persistence layer
cd proxy
cargo test

# Test PII masking
cargo test pii_mask
```

### Integration Test

```bash
# Terminal 1: Start proxy
cd proxy
cargo run --release

# Terminal 2: Run recipe client through proxy
export COMPOSIO_API_BASE=http://localhost:8765
cd ..
python scripts/recipe_client.py info

# Terminal 3: Check cache
sqlite3 ~/.claude/cache/state.db "SELECT COUNT(*) FROM tool_calls;"
```

### Performance Benchmark

Target: <10ms proxy latency overhead

```bash
# TODO: Create benchmark suite
cd proxy
cargo bench
```

## Implementation Notes

### Let It Crash Patterns

- SQLite write failures are logged but not retried
- Proxy forwards responses even if persistence fails
- No exponential backoffs or complex retry chains
- Errors always propagate with full context

### KISS Decisions

- Plain TEXT for JSON (not JSON1 extension)
- SQL LIKE for correlation (not graph structure)
- Single binary for GUI (proxy embedded in background thread)
- No complex state machines or event sourcing

### SOLID Compliance

- **Repository trait**: Abstracts SQLite implementation
- **Dependency injection**: Pool/channel passed to functions
- **Pure functions**: `pii_mask::mask_pii()` has no side effects
- **Single responsibility**: Modules focused on one concern

## Known Limitations

1. **Workflow ID hardcoded**: Proxy currently uses `workflow_id=1` for all tool calls. Future: Extract from request headers or API key.

2. **Tool name extraction**: Parsed from URL path (`/actions/TOOL_NAME/execute`). May not work for all endpoints.

3. **No auth persistence**: Proxy doesn't handle session cookies. Future: Add cookie jar support.

4. **GUI proxy integration**: Currently GUI and proxy are separate binaries. Future: Single binary with proxy in background thread.

5. **No real-time updates**: GUI doesn't auto-refresh. Future: WebSocket or polling for live updates.

## Future Enhancements

- [ ] Extract workflow_id from request context
- [ ] Compression for large response_json (>100KB)
- [ ] Archival to S3 before TTL deletion
- [ ] Performance metrics aggregation
- [ ] Real-time GUI updates (WebSocket)
- [ ] Full-text search (SQLite FTS5)
- [ ] Export to CSV/JSON for analysis

## References

- [ARCHITECTURE.md](./ARCHITECTURE.md) - Detailed design decisions
- [CLAUDE.md](./CLAUDE.md) - Project design principles
- [SQLite WAL Mode](https://www.sqlite.org/wal.html)
- [Tauri Documentation](https://tauri.app/)

## License

See [LICENSE](./LICENSE) file.

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.
