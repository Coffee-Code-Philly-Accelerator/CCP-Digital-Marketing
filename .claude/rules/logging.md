# CCP Telemetry & Logging

## Overview

CCP uses SQLite-based telemetry (not file-based logs) for tracking workflow executions and tool calls. The GUI backend manages the database; the frontend receives real-time progress via Tauri events.

## Telemetry Database

**Location**: `CCP_CACHE_DB_PATH` (default: `~/.claude/cache/state.db`)

**Manager**: `gui/src-tauri/src/db.rs`

### Tables

**`workflows`** -- Top-level execution records
```sql
CREATE TABLE workflows (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    workflow_type TEXT,  -- 'create_event', 'promote_event', 'social_post', 'full_workflow'
    status TEXT,         -- 'pending', 'running', 'completed', 'failed'
    created_at TEXT,     -- ISO-8601
    updated_at TEXT      -- ISO-8601
);
```

**`tool_calls`** -- Individual Composio tool invocations within a workflow
```sql
CREATE TABLE tool_calls (
    id TEXT PRIMARY KEY,
    workflow_id TEXT REFERENCES workflows(id),
    tool_name TEXT,      -- Composio tool slug (e.g., 'HYPERBROWSER_START_BROWSER_USE_TASK')
    status TEXT,         -- 'pending', 'running', 'completed', 'failed'
    latency_ms INTEGER,  -- Execution time
    request_json TEXT,   -- Full request payload
    response_json TEXT,  -- Full response payload
    created_at TEXT      -- ISO-8601
);
```

## Progress Events

**Source**: `gui/src-tauri/src/progress.rs`

The Rust backend emits `recipe-progress` Tauri events to the frontend for real-time status updates:

```rust
pub struct RecipeProgressEvent {
    pub command: String,      // IPC command name (e.g., "create_event")
    pub phase: String,        // "starting", "executing", "polling", "complete", "error"
    pub status: String,       // "in_progress", "success", "error"
    pub elapsed_sec: f64,     // Seconds since command start
    pub message: String,      // Human-readable status message
    pub result: Option<Value> // Final result JSON (on completion)
}
```

**Frontend listener**: `gui/src/progress.js` subscribes to these events and updates the UI.

## Viewing Telemetry

```bash
# Set the database path
DB_PATH="${CCP_CACHE_DB_PATH:-$HOME/.claude/cache/state.db}"

# List recent workflows
sqlite3 -header -column "$DB_PATH" \
  "SELECT id, workflow_type, status, created_at FROM workflows ORDER BY created_at DESC LIMIT 10;"

# View tool calls for a workflow
sqlite3 -header -column "$DB_PATH" \
  "SELECT tool_name, status, latency_ms, created_at FROM tool_calls WHERE workflow_id = '<id>' ORDER BY created_at;"

# Find failed tool calls
sqlite3 -header -column "$DB_PATH" \
  "SELECT tool_name, substr(response_json, 1, 200) as error_preview, created_at FROM tool_calls WHERE status = 'failed' ORDER BY created_at DESC LIMIT 10;"

# Average latency by tool
sqlite3 -header -column "$DB_PATH" \
  "SELECT tool_name, COUNT(*) as calls, ROUND(AVG(latency_ms)) as avg_ms FROM tool_calls GROUP BY tool_name ORDER BY avg_ms DESC;"

# Workflow success rate
sqlite3 -header -column "$DB_PATH" \
  "SELECT workflow_type, COUNT(*) as total, SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as ok, ROUND(100.0 * SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) / COUNT(*), 1) as pct FROM workflows GROUP BY workflow_type;"
```

## Debugging with Telemetry

1. **Trace a workflow**: Query `tool_calls` by `workflow_id` to see the full execution sequence
2. **Identify slow tools**: Sort by `latency_ms` to find bottlenecks
3. **Find auth issues**: Search `response_json` for `NEEDS_AUTH` patterns
4. **Track API errors**: Filter `tool_calls` by `status = 'failed'` and inspect `response_json`

## No File-Based Logs

CCP does not use file-based logging (no `logs/` directory). All observability comes from:
- **SQLite telemetry** (workflows + tool_calls tables)
- **Tauri progress events** (real-time, not persisted beyond the database)
- **stdout/stderr** from CLI scripts (recipe_client.py)

When debugging, always start with the SQLite database, not log files.
