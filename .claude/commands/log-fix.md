---
description: Query SQLite telemetry database and iteratively fix bugs based on workflow/tool call analysis
allowed-tools: AskUserQuestion, Bash, Read, Glob, Grep, Edit, Write
argument-hint: [--time <1h|1d|7d>] [--status <failed|all>] [--workflow-id <id>] [--tool <tool_name>]
---

# Log-Fix: Iterative Bug Fixing from Telemetry Analysis

Analyze the CCP telemetry SQLite database, identify failed workflows and tool calls, perform root cause analysis, and interactively fix issues with user approval.

> "Telemetry tells stories. This skill reads them and writes the fixes."

## Arguments

- `$ARGUMENTS` - Optional filters:
  - `--time <duration>` - Time range: `1h`, `1d`, `7d`, `30d` (default: `1d`)
  - `--status <status>` - Filter by status: `failed`, `all` (default: `failed`)
  - `--workflow-id <id>` - Trace specific workflow execution
  - `--tool <tool_name>` - Filter by Composio tool name (e.g., `TWITTER_CREATION_OF_A_POST`)

---

## CCP Telemetry Architecture

CCP stores telemetry in a SQLite database at `CCP_CACHE_DB_PATH` (default: `~/.claude/cache/state.db`). The GUI backend (`gui/src-tauri/src/db.rs`) manages this database.

### Database Schema

**`workflows` table:**
| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT PRIMARY KEY | Workflow UUID |
| `user_id` | TEXT | User identifier |
| `workflow_type` | TEXT | Type: `create_event`, `promote_event`, `social_post`, `full_workflow` |
| `status` | TEXT | Status: `pending`, `running`, `completed`, `failed` |
| `created_at` | TEXT | ISO-8601 timestamp |
| `updated_at` | TEXT | ISO-8601 timestamp |

**`tool_calls` table:**
| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT PRIMARY KEY | Tool call UUID |
| `workflow_id` | TEXT | Foreign key to workflows.id |
| `tool_name` | TEXT | Composio tool slug (e.g., `HYPERBROWSER_START_BROWSER_USE_TASK`) |
| `status` | TEXT | Status: `pending`, `running`, `completed`, `failed` |
| `latency_ms` | INTEGER | Execution time in milliseconds |
| `request_json` | TEXT | JSON request payload |
| `response_json` | TEXT | JSON response payload |
| `created_at` | TEXT | ISO-8601 timestamp |

### Progress Events

The Rust backend emits `recipe-progress` Tauri events via `gui/src-tauri/src/progress.rs`:
```rust
pub struct RecipeProgressEvent {
    pub command: String,      // IPC command name
    pub phase: String,        // "starting", "executing", "polling", "complete", "error"
    pub status: String,       // "in_progress", "success", "error"
    pub elapsed_sec: f64,     // Seconds since command start
    pub message: String,      // Human-readable status
    pub result: Option<Value> // Final result JSON (on completion)
}
```

---

## Philosophy: Ask Early, Ask Often

**This skill should liberally use `AskUserQuestion` at decision points.** Bug fixing involves judgment about severity, root causes, and fix strategies.

- **Before** analyzing -- confirm which data and time range to investigate
- **After** triage -- let the user choose which issues to dig into
- **Before** each fix -- present the proposed change for approval
- **When** root cause is uncertain -- present multiple hypotheses
- **After** fixes -- ask about next steps

## Phase 1: Database Discovery

### 1.1 Locate Database

```bash
DB_PATH="${CCP_CACHE_DB_PATH:-$HOME/.claude/cache/state.db}"
if [ -f "$DB_PATH" ]; then
  SIZE=$(du -h "$DB_PATH" | cut -f1)
  WORKFLOWS=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM workflows;")
  TOOL_CALLS=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM tool_calls;")
  echo "Database: $DB_PATH ($SIZE)"
  echo "Workflows: $WORKFLOWS, Tool calls: $TOOL_CALLS"
else
  echo "Database not found at $DB_PATH"
  echo "Set CCP_CACHE_DB_PATH or run the GUI app to create it"
fi
```

---

## Phase 2: Query Failed Workflows

### 2.1 Recent Failures

```bash
sqlite3 -header -column "$DB_PATH" "
  SELECT w.id, w.workflow_type, w.status, w.created_at,
         COUNT(tc.id) as tool_calls,
         SUM(CASE WHEN tc.status = 'failed' THEN 1 ELSE 0 END) as failed_calls
  FROM workflows w
  LEFT JOIN tool_calls tc ON tc.workflow_id = w.id
  WHERE w.status = 'failed'
    AND w.created_at >= datetime('now', '-${TIME_ARG:-1 day}')
  GROUP BY w.id
  ORDER BY w.created_at DESC
  LIMIT 20;
"
```

### 2.2 Failed Tool Calls with Error Details

```bash
sqlite3 -header -column "$DB_PATH" "
  SELECT tc.tool_name, tc.status, tc.latency_ms,
         substr(tc.response_json, 1, 200) as response_preview,
         tc.created_at
  FROM tool_calls tc
  WHERE tc.status = 'failed'
    AND tc.created_at >= datetime('now', '-${TIME_ARG:-1 day}')
  ORDER BY tc.created_at DESC
  LIMIT 20;
"
```

### 2.3 Tool Call Latency Analysis

```bash
sqlite3 -header -column "$DB_PATH" "
  SELECT tool_name,
         COUNT(*) as calls,
         AVG(latency_ms) as avg_ms,
         MAX(latency_ms) as max_ms,
         SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failures
  FROM tool_calls
  WHERE created_at >= datetime('now', '-${TIME_ARG:-1 day}')
  GROUP BY tool_name
  ORDER BY failures DESC, avg_ms DESC;
"
```

---

## Phase 3: Triage and Clustering

### 3.1 Incident Clustering

Group failures by:
1. Same tool name (e.g., all `HYPERBROWSER_START_BROWSER_USE_TASK` failures)
2. Same workflow type (e.g., all `create_event` failures)
3. Same error pattern in `response_json`
4. Same time window (errors within 5 minutes)

### 3.2 Severity Ranking

| Priority | Criteria |
|----------|----------|
| P0 | All workflows of a type failing (complete feature broken) |
| P1 | Specific tool consistently failing (partial feature broken) |
| P2 | Intermittent failures, high latency (performance degradation) |
| P3 | Single occurrence, low impact |

### 3.3 Common CCP Error Patterns

| Error Pattern | Likely Cause | Location |
|--------------|--------------|----------|
| `NEEDS_AUTH` in response | Browser session expired | Recipe auth setup |
| Tool call timeout (>240000ms) | Exceeded 4-min Rube runtime | Recipe task complexity |
| `401`/`403` in response | API key expired or invalid | `.env` / `config.rs` |
| `HYPERBROWSER` failure | Profile not set up | Auth setup needed |
| Empty `response_json` | Network/API connectivity | Composio backend |
| `anti-bot` / `captcha` in response | Platform detection | Add stealth/waits |

### 3.4 Display Triage Summary and Ask User

Present clustered issues and let the user choose which to investigate.

---

## Phase 4: Root Cause Analysis

### 4.1 Trace a Specific Workflow

```bash
WORKFLOW_ID="<id>"
sqlite3 -header -column "$DB_PATH" "
  SELECT tc.tool_name, tc.status, tc.latency_ms, tc.created_at,
         substr(tc.request_json, 1, 200) as request_preview,
         substr(tc.response_json, 1, 200) as response_preview
  FROM tool_calls tc
  WHERE tc.workflow_id = '$WORKFLOW_ID'
  ORDER BY tc.created_at ASC;
"
```

### 4.2 Inspect Full Request/Response

```bash
sqlite3 "$DB_PATH" "
  SELECT request_json FROM tool_calls
  WHERE id = '<tool_call_id>';
" | python3 -m json.tool
```

### 4.3 Map to Source Code

| Tool Call Pattern | Source File |
|-------------------|------------|
| `HYPERBROWSER_*` | `recipes/create_event_*.py` |
| `TWITTER_*`, `LINKEDIN_*`, etc. | `recipes/social_promotion.py` |
| `GEMINI_GENERATE_IMAGE` | `gui/src-tauri/src/draft_commands.rs` |
| `COMPOSIO_SEARCH_*` | `gui/src-tauri/src/draft_commands.rs` |
| Recipe execution | `gui/src-tauri/src/composio.rs` |
| Poll/status checks | `gui/src-tauri/src/composio.rs` |

### 4.4 Present Root Cause Hypotheses

When root cause is ambiguous, present hypotheses for user decision.

---

## Phase 5: Interactive Fix Loop

### 5.1 Fix Workflow

1. **Present** - Show error, root cause, affected files
2. **Show diff** - Display exact code changes
3. **Ask permission** - Get user approval via AskUserQuestion
4. **Apply if approved** - Use Edit tool
5. **Validate** - Run relevant tests or recipe validation
6. **Report** - Success/failure

### 5.2 Validation After Fix

| Fix Type | Validation Command |
|----------|-------------------|
| Recipe code | `python scripts/validate_recipes.py` |
| Python scripts | `pytest tests/ -v --tb=short` |
| Rust code | `cd gui/src-tauri && cargo clippy -- -D warnings` |
| Config/env | Manual verification |

---

## Phase 6: Summary Report

```markdown
## Log-Fix Session Summary

**Database**: <path>
**Time Range**: <range>
**Workflows Analyzed**: N
**Failed Tool Calls**: M

### Issues Addressed

| # | Workflow Type | Tool | Issue | Status | Action |
|---|--------------|------|-------|--------|--------|
| 1 | create_event | HYPERBROWSER_* | NEEDS_AUTH | FIXED | Re-auth profile |
| 2 | promote_event | TWITTER_* | 401 | SKIPPED | User skipped |

### Files Modified
- recipes/create_event_luma.py
- ...

### Validation Results
| File | Test | Result |
|------|------|--------|
| recipes/*.py | validate_recipes.py | PASSED |

### Remaining Issues
| Priority | Issue | Recommendation |
|----------|-------|----------------|
| P2 | High latency on Meetup | Add explicit waits |
```

---

## Useful Queries

```sql
-- Find workflows with the most failed tool calls
SELECT w.workflow_type, w.id, COUNT(*) as failed
FROM workflows w
JOIN tool_calls tc ON tc.workflow_id = w.id
WHERE tc.status = 'failed'
GROUP BY w.id ORDER BY failed DESC LIMIT 10;

-- Average latency by tool
SELECT tool_name, ROUND(AVG(latency_ms)) as avg_ms, COUNT(*) as total
FROM tool_calls GROUP BY tool_name ORDER BY avg_ms DESC;

-- Find NEEDS_AUTH errors
SELECT tc.tool_name, tc.created_at, substr(tc.response_json, 1, 300)
FROM tool_calls tc
WHERE tc.response_json LIKE '%NEEDS_AUTH%'
ORDER BY tc.created_at DESC LIMIT 10;

-- Workflow success rate by type
SELECT workflow_type,
  COUNT(*) as total,
  SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as succeeded,
  ROUND(100.0 * SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) / COUNT(*), 1) as success_pct
FROM workflows GROUP BY workflow_type;
```

## Example Usage

```
/log-fix
/log-fix --time 7d
/log-fix --workflow-id abc-123-def
/log-fix --tool HYPERBROWSER_START_BROWSER_USE_TASK
/log-fix --status all --time 30d
```

## Notes

- Requires sqlite3 CLI tool
- Database is created by the Tauri GUI app on first run
- If no database exists, suggest running the GUI app first
- Tool call request/response JSON can be large -- use `substr()` for previews
- Never auto-commit fixes -- always ask permission
- Suggest `/tdd` for bugs without test coverage
- Suggest `/pr-check` before committing fixes
