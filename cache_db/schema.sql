-- =============================================================================
-- CCP Digital Marketing - Telemetry Cache Schema
-- =============================================================================
-- Purpose: Tool-call level tracking for Claude skill automation workflows
-- Retention: 7-day TTL via background cleanup task
-- Concurrency: WAL mode for concurrent read/write access
-- Design: Three tables (workflows > phases > tool_calls) with TEXT JSON storage

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- =============================================================================
-- Table: workflows
-- =============================================================================
-- Top-level execution context for each automation run
-- Maps to user-initiated Claude skill invocations

CREATE TABLE IF NOT EXISTS workflows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,                  -- Claude user identifier
    workflow_type TEXT NOT NULL,            -- full-workflow, create-event, promote, social-post, email-reply
    status TEXT NOT NULL DEFAULT 'running', -- running, completed, failed, partial
    created_at INTEGER NOT NULL,            -- Unix timestamp (seconds)
    updated_at INTEGER NOT NULL,            -- Unix timestamp (seconds)
    input_params_json TEXT NOT NULL         -- JSON: all input parameters for the workflow
);

CREATE INDEX IF NOT EXISTS idx_workflows_user ON workflows(user_id);
CREATE INDEX IF NOT EXISTS idx_workflows_type ON workflows(workflow_type);
CREATE INDEX IF NOT EXISTS idx_workflows_status ON workflows(status);
CREATE INDEX IF NOT EXISTS idx_workflows_created ON workflows(created_at);

-- =============================================================================
-- Table: phases
-- =============================================================================
-- Logical phases within a workflow (staging, luma-create, meetup-create, etc.)
-- Captures phase-level inputs, outputs, and errors

CREATE TABLE IF NOT EXISTS phases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id INTEGER NOT NULL,
    phase_name TEXT NOT NULL,                -- staging, luma-create, meetup-create, partiful-create, social-promotion
    status TEXT NOT NULL DEFAULT 'running',  -- running, completed, failed, skipped
    phase_inputs_json TEXT,                  -- JSON: inputs specific to this phase (may differ from workflow inputs)
    phase_outputs_json TEXT,                 -- JSON: phase results (event_url, image_url, task_id, etc.)
    error_text TEXT,                         -- Error message if status=failed
    created_at INTEGER NOT NULL,             -- Unix timestamp (seconds)
    updated_at INTEGER NOT NULL,             -- Unix timestamp (seconds)
    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_phases_workflow ON phases(workflow_id);
CREATE INDEX IF NOT EXISTS idx_phases_name ON phases(phase_name);
CREATE INDEX IF NOT EXISTS idx_phases_status ON phases(status);
CREATE INDEX IF NOT EXISTS idx_phases_created ON phases(created_at);

-- =============================================================================
-- Table: tool_calls
-- =============================================================================
-- Individual Composio API tool invocations with full request/response
-- Granular debugging: every run_composio_tool() call is captured

CREATE TABLE IF NOT EXISTS tool_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id INTEGER NOT NULL,
    phase_id INTEGER,                        -- Nullable: some tool calls may not be in a phase
    tool_name TEXT NOT NULL,                 -- HYPERBROWSER_START_BROWSER_USE_TASK, LINKEDIN_CREATE_LINKED_IN_POST, etc.
    request_json TEXT NOT NULL,              -- JSON: tool arguments
    response_json TEXT,                      -- JSON: tool response (null if not yet complete)
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, success, error
    latency_ms INTEGER,                      -- API call duration in milliseconds
    created_at INTEGER NOT NULL,             -- Unix timestamp (seconds)
    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE,
    FOREIGN KEY (phase_id) REFERENCES phases(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tool_calls_workflow ON tool_calls(workflow_id);
CREATE INDEX IF NOT EXISTS idx_tool_calls_phase ON tool_calls(phase_id);
CREATE INDEX IF NOT EXISTS idx_tool_calls_tool_name ON tool_calls(tool_name);
CREATE INDEX IF NOT EXISTS idx_tool_calls_status ON tool_calls(status);
CREATE INDEX IF NOT EXISTS idx_tool_calls_created ON tool_calls(created_at);
