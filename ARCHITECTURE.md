# CCP Digital Marketing - Telemetry Cache Architecture

## Overview

SQLite telemetry cache for capturing tool-call level granularity in Claude skill automation workflows. Supports debugging, observability, and workflow correlation with 7-day retention.

## Design Principles

All decisions follow `CLAUDE.md` principles:

1. **Let It Crash** - Errors propagate visibly; no silent failures
2. **KISS** - Simple schema, plain TEXT for JSON, no over-engineering
3. **Pure Functions** - Repository methods have no side effects beyond database operations
4. **SOLID** - Repository trait for abstraction, single responsibility per component

## Schema Design

### Three-Table Normalized Design

```
workflows (1) --< (N) phases (1) --< (N) tool_calls
```

**Rationale:**
- **Separation of concerns**: Workflow context, phase grouping, and tool-level detail
- **Efficient queries**: Indexes on foreign keys enable fast JOINs
- **Cascade deletes**: TTL cleanup on workflows automatically removes phases and tool_calls
- **Nullable phase_id**: Not all tool calls belong to a phase

### Why TEXT for JSON Storage

**Decision:** Use plain TEXT columns for JSON data instead of SQLite's JSON1 extension.

**Rationale:**
1. **Simplicity** (KISS): No extension dependencies
2. **Portability**: Compatible with any SQLite version
3. **Read-time correlation**: SQL LIKE queries sufficient for 7-day retention
4. **Consensus feedback**: Avoid complex JSONB extension

**Example correlation query:**
```sql
SELECT * FROM tool_calls
WHERE response_json LIKE '%"image_url": "https://storage.googleapis.com/abc123"%'
ORDER BY created_at DESC;
```

## TTL Cleanup Strategy

### Background Task Approach

**Implementation:** Hourly task executes:

```sql
DELETE FROM workflows WHERE created_at < (strftime('%s', 'now') - 604800);
```

**Rationale:**
1. **Let It Crash**: Simple DELETE query; errors propagate if database is locked
2. **KISS**: No complex archival logic, no soft deletes
3. **Cascade behavior**: Foreign keys automatically delete phases and tool_calls

### WAL Mode Configuration

**Enable at initialization:**
```sql
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
```

**Benefits:**
- Concurrent access: Readers don't block writers
- Performance: Writes batched to WAL file
- Crash recovery: Automatic recovery after unclean shutdown

**Trade-offs:**
- Creates `.db-wal` and `.db-shm` files
- Slightly more complex backups (copy all 3 files)

## Read-Time Correlation

### Why Not Write-Time Graph?

**Decision:** Implement correlation via SQL queries at read time, not as a graph at write time.

**Rationale:**
1. **KISS**: No separate edge table, graph traversal logic, or complex schema
2. **Sufficient performance**: For 7-day retention, LIKE queries fast enough
3. **Flexibility**: Any JSON field can be correlated without schema changes

### Correlation Query Patterns

**Find all tool calls referencing an artifact:**
```sql
SELECT tc.*, w.workflow_type, p.phase_name
FROM tool_calls tc
JOIN workflows w ON tc.workflow_id = w.id
LEFT JOIN phases p ON tc.phase_id = p.id
WHERE tc.request_json LIKE '%"image_url": "https://storage.googleapis.com/abc123"%'
   OR tc.response_json LIKE '%"image_url": "https://storage.googleapis.com/abc123"%'
ORDER BY tc.created_at;
```

## Index Strategy

### Critical Indexes

**created_at indexes** (all tables):
- **Purpose**: Efficient TTL cleanup
- **Query**: `DELETE FROM workflows WHERE created_at < X`

**Foreign key indexes:**
- `idx_phases_workflow` on `phases(workflow_id)`
- `idx_tool_calls_workflow` on `tool_calls(workflow_id)`
- `idx_tool_calls_phase` on `tool_calls(phase_id)`
- **Purpose**: Fast JOINs for workflow details queries

**Filter indexes:**
- `idx_workflows_type`, `idx_workflows_status`, `idx_tool_calls_tool_name`, `idx_tool_calls_status`

### EXPLAIN QUERY PLAN Example

```sql
EXPLAIN QUERY PLAN
DELETE FROM workflows WHERE created_at < 1234567890;

-- Expected: SEARCH workflows USING INDEX idx_workflows_created (created_at<?)
```

## Implementation Sequence

1. **Phase 1: Schema and Repository** - Define data layer (cache_db/)
2. **Phase 2: Proxy Service** - HTTP interceptor with async persistence (proxy/)
3. **Phase 3: Tauri GUI** - Desktop app with timeline visualization (gui/)
4. **Phase 4: Integration** - E2E tests, benchmarks, documentation

## Testing Strategy

- **Unit Tests**: In-memory SQLite, test CRUD operations
- **Integration Tests**: Real SQLite, full workflow invocation
- **Performance Tests**: 10K workflows, verify index usage, TTL cleanup time

## References

- [SQLite WAL Mode](https://www.sqlite.org/wal.html)
- [SQLite Foreign Keys](https://www.sqlite.org/foreignkeys.html)
- `CLAUDE.md` - Project design principles
