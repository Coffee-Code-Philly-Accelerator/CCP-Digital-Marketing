//! CCP Digital Marketing - Telemetry Cache Repository Trait
//!
//! SOLID Principles:
//! - Single Responsibility: Repository only handles data access, no business logic
//! - Open/Closed: New implementations can be added without modifying the trait
//! - Liskov Substitution: All implementations must honor the contract
//! - Interface Segregation: Focused interface for cache operations only
//! - Dependency Inversion: Consumers depend on this trait, not concrete SQLite

use std::time::{SystemTime, UNIX_EPOCH};

/// Workflow execution context
#[derive(Debug, Clone)]
pub struct Workflow {
    pub id: Option<i64>,             // None for new records, Some(id) for existing
    pub user_id: String,
    pub workflow_type: String,       // full-workflow, create-event, promote, etc.
    pub status: WorkflowStatus,
    pub created_at: i64,             // Unix timestamp (seconds)
    pub updated_at: i64,
    pub input_params_json: String,   // JSON string
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum WorkflowStatus {
    Running,
    Completed,
    Failed,
    Partial,
}

impl WorkflowStatus {
    pub fn as_str(&self) -> &str {
        match self {
            WorkflowStatus::Running => "running",
            WorkflowStatus::Completed => "completed",
            WorkflowStatus::Failed => "failed",
            WorkflowStatus::Partial => "partial",
        }
    }

    pub fn from_str(s: &str) -> Result<Self, Error> {
        match s {
            "running" => Ok(WorkflowStatus::Running),
            "completed" => Ok(WorkflowStatus::Completed),
            "failed" => Ok(WorkflowStatus::Failed),
            "partial" => Ok(WorkflowStatus::Partial),
            _ => Err(Error::InvalidStatus(s.to_string())),
        }
    }
}

/// Phase within a workflow
#[derive(Debug, Clone)]
pub struct Phase {
    pub id: Option<i64>,
    pub workflow_id: i64,
    pub phase_name: String,          // staging, luma-create, social-promotion, etc.
    pub status: PhaseStatus,
    pub phase_inputs_json: Option<String>,
    pub phase_outputs_json: Option<String>,
    pub error_text: Option<String>,
    pub created_at: i64,
    pub updated_at: i64,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PhaseStatus {
    Running,
    Completed,
    Failed,
    Skipped,
}

impl PhaseStatus {
    pub fn as_str(&self) -> &str {
        match self {
            PhaseStatus::Running => "running",
            PhaseStatus::Completed => "completed",
            PhaseStatus::Failed => "failed",
            PhaseStatus::Skipped => "skipped",
        }
    }

    pub fn from_str(s: &str) -> Result<Self, Error> {
        match s {
            "running" => Ok(PhaseStatus::Running),
            "completed" => Ok(PhaseStatus::Completed),
            "failed" => Ok(PhaseStatus::Failed),
            "skipped" => Ok(PhaseStatus::Skipped),
            _ => Err(Error::InvalidStatus(s.to_string())),
        }
    }
}

/// Individual tool call (Composio API invocation)
#[derive(Debug, Clone)]
pub struct ToolCall {
    pub id: Option<i64>,
    pub workflow_id: i64,
    pub phase_id: Option<i64>,       // Nullable: not all tool calls are in phases
    pub tool_name: String,           // HYPERBROWSER_START_BROWSER_USE_TASK, etc.
    pub request_json: String,
    pub response_json: Option<String>,
    pub status: ToolCallStatus,
    pub latency_ms: Option<i64>,
    pub created_at: i64,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ToolCallStatus {
    Pending,
    Success,
    Error,
}

impl ToolCallStatus {
    pub fn as_str(&self) -> &str {
        match self {
            ToolCallStatus::Pending => "pending",
            ToolCallStatus::Success => "success",
            ToolCallStatus::Error => "error",
        }
    }

    pub fn from_str(s: &str) -> Result<Self, Error> {
        match s {
            "pending" => Ok(ToolCallStatus::Pending),
            "success" => Ok(ToolCallStatus::Success),
            "error" => Ok(ToolCallStatus::Error),
            _ => Err(Error::InvalidStatus(s.to_string())),
        }
    }
}

/// Combined workflow with all phases and tool calls
#[derive(Debug, Clone)]
pub struct WorkflowDetails {
    pub workflow: Workflow,
    pub phases: Vec<PhaseDetails>,
}

#[derive(Debug, Clone)]
pub struct PhaseDetails {
    pub phase: Phase,
    pub tool_calls: Vec<ToolCall>,
}

/// Search filter for workflow queries
#[derive(Debug, Clone, Default)]
pub struct SearchFilter {
    pub user_id: Option<String>,
    pub workflow_type: Option<String>,
    pub status: Option<WorkflowStatus>,
    pub created_after: Option<i64>,   // Unix timestamp
    pub created_before: Option<i64>,
    pub limit: Option<usize>,
}

/// Repository error types
#[derive(Debug)]
pub enum Error {
    NotFound,
    InvalidStatus(String),
    DatabaseError(String),
    SerializationError(String),
}

impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Error::NotFound => write!(f, "Record not found"),
            Error::InvalidStatus(s) => write!(f, "Invalid status: {}", s),
            Error::DatabaseError(s) => write!(f, "Database error: {}", s),
            Error::SerializationError(s) => write!(f, "Serialization error: {}", s),
        }
    }
}

impl std::error::Error for Error {}

/// Telemetry cache repository trait
///
/// SOLID Compliance:
/// - Single Responsibility: Only handles data persistence operations
/// - Dependency Inversion: Business logic depends on this trait, not SQLite
/// - Interface Segregation: Focused interface for cache operations
///
/// Let It Crash:
/// - All methods return Result; no silent error swallowing
/// - Errors propagate to caller for visibility
/// - No retry logic or complex fallbacks
pub trait CacheRepository: Send + Sync {
    /// Create a new workflow record
    ///
    /// Returns the assigned workflow ID
    async fn create_workflow(&self, workflow: &Workflow) -> Result<i64, Error>;

    /// Update an existing workflow
    async fn update_workflow(&self, workflow: &Workflow) -> Result<(), Error>;

    /// Create a new phase record
    ///
    /// Returns the assigned phase ID
    async fn create_phase(&self, phase: &Phase) -> Result<i64, Error>;

    /// Update an existing phase
    async fn update_phase(&self, phase: &Phase) -> Result<(), Error>;

    /// Create a new tool call record
    ///
    /// Returns the assigned tool call ID
    async fn create_tool_call(&self, call: &ToolCall) -> Result<i64, Error>;

    /// Update an existing tool call (e.g., add response after polling)
    async fn update_tool_call(&self, call: &ToolCall) -> Result<(), Error>;

    /// Get workflow by ID (metadata only, no phases/tool_calls)
    async fn get_workflow(&self, id: i64) -> Result<Workflow, Error>;

    /// Get workflow with all phases and tool calls
    async fn get_workflow_with_details(&self, id: i64) -> Result<WorkflowDetails, Error>;

    /// Search workflows by filter criteria
    async fn search_workflows(&self, filter: &SearchFilter) -> Result<Vec<Workflow>, Error>;

    /// Search for tool calls containing a specific artifact in request or response
    ///
    /// Read-time correlation: SQL LIKE queries on JSON TEXT fields
    /// Example: Find all tool calls that reference a specific image_url
    async fn search_correlation(&self, artifact: &str) -> Result<Vec<ToolCall>, Error>;

    /// Delete workflows older than specified days (TTL cleanup)
    ///
    /// Returns number of workflows deleted
    /// Cascades to phases and tool_calls via foreign key constraints
    async fn cleanup_expired(&self, days: u32) -> Result<usize, Error>;
}

/// Pure helper function: Get current Unix timestamp
///
/// Pure function: Deterministic for testing (can be mocked), but note that
/// SystemTime::now() is inherently impure. In production, this should be injected
/// as a parameter for true purity.
pub fn current_timestamp() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("System time before UNIX epoch")
        .as_secs() as i64
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_workflow_status_roundtrip() {
        let statuses = vec![
            WorkflowStatus::Running,
            WorkflowStatus::Completed,
            WorkflowStatus::Failed,
            WorkflowStatus::Partial,
        ];

        for status in statuses {
            let s = status.as_str();
            let parsed = WorkflowStatus::from_str(s).unwrap();
            assert_eq!(status, parsed);
        }
    }

    #[test]
    fn test_phase_status_roundtrip() {
        let statuses = vec![
            PhaseStatus::Running,
            PhaseStatus::Completed,
            PhaseStatus::Failed,
            PhaseStatus::Skipped,
        ];

        for status in statuses {
            let s = status.as_str();
            let parsed = PhaseStatus::from_str(s).unwrap();
            assert_eq!(status, parsed);
        }
    }

    #[test]
    fn test_tool_call_status_roundtrip() {
        let statuses = vec![
            ToolCallStatus::Pending,
            ToolCallStatus::Success,
            ToolCallStatus::Error,
        ];

        for status in statuses {
            let s = status.as_str();
            let parsed = ToolCallStatus::from_str(s).unwrap();
            assert_eq!(status, parsed);
        }
    }

    #[test]
    fn test_current_timestamp() {
        let ts = current_timestamp();
        assert!(ts > 1700000000); // After 2023
        assert!(ts < 2000000000); // Before 2033
    }
}
