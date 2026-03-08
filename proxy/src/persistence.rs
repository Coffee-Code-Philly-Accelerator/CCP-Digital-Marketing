//! SQLite persistence layer with async writes
//!
//! Implements CacheRepository trait from cache_db/repository.rs
//! Uses mpsc channel for non-blocking writes (Let It Crash: errors logged, not retried)

use sqlx::{sqlite::{SqlitePool, SqliteConnectOptions}, Row};
use std::str::FromStr;
use std::path::Path;
use tokio::sync::mpsc;
use tracing::{error, info};

// Re-declare types from cache_db/repository.rs for now
// In production, this would import from a shared crate
#[derive(Debug, Clone)]
pub struct ToolCall {
    pub id: Option<i64>,
    pub workflow_id: i64,
    pub phase_id: Option<i64>,
    pub tool_name: String,
    pub request_json: String,
    pub response_json: Option<String>,
    pub status: String,  // "pending", "success", "error"
    pub latency_ms: Option<i64>,
    pub created_at: i64,
}

/// SQLite cache repository with async writes
pub struct SqliteCacheRepository {
    pool: SqlitePool,
}

impl SqliteCacheRepository {
    /// Create new repository with database file path
    ///
    /// Initializes WAL mode and foreign keys
    pub async fn new(db_path: &Path) -> Result<Self, sqlx::Error> {
        // Create parent directory if it doesn't exist
        if let Some(parent) = db_path.parent() {
            tokio::fs::create_dir_all(parent).await?;
        }

        // Use SqliteConnectOptions to properly configure the connection
        let options = SqliteConnectOptions::from_str(&format!("sqlite:{}", db_path.display()))?
            .create_if_missing(true);
        let pool = SqlitePool::connect_with(options).await?;

        // Enable WAL mode and foreign keys
        sqlx::query("PRAGMA journal_mode=WAL")
            .execute(&pool)
            .await?;
        sqlx::query("PRAGMA foreign_keys=ON")
            .execute(&pool)
            .await?;

        // Run migrations (create schema if not exists)
        // Parse and execute each SQL statement separately
        let schema = include_str!("../../cache_db/schema.sql");
        let mut current_statement = String::new();

        for line in schema.lines() {
            let trimmed = line.trim();

            // Skip comments and PRAGMA statements (already handled above)
            if trimmed.starts_with("--") || trimmed.is_empty() {
                continue;
            }
            if trimmed.to_uppercase().starts_with("PRAGMA") {
                continue;
            }

            current_statement.push_str(line);
            current_statement.push('\n');

            // Execute when we hit a semicolon
            if trimmed.ends_with(';') {
                let stmt = current_statement.trim();
                if !stmt.is_empty() {
                    sqlx::query(stmt).execute(&pool).await?;
                }
                current_statement.clear();
            }
        }

        Ok(Self { pool })
    }

    /// Create a tool call record
    pub async fn create_tool_call(&self, call: &ToolCall) -> Result<i64, sqlx::Error> {
        let result = sqlx::query(
            r#"
            INSERT INTO tool_calls (workflow_id, phase_id, tool_name, request_json, response_json, status, latency_ms, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            "#
        )
        .bind(call.workflow_id)
        .bind(call.phase_id)
        .bind(&call.tool_name)
        .bind(&call.request_json)
        .bind(&call.response_json)
        .bind(&call.status)
        .bind(call.latency_ms)
        .bind(call.created_at)
        .execute(&self.pool)
        .await?;

        Ok(result.last_insert_rowid())
    }

    /// Get workflow count (for testing)
    pub async fn count_workflows(&self) -> Result<i64, sqlx::Error> {
        let row = sqlx::query("SELECT COUNT(*) as count FROM workflows")
            .fetch_one(&self.pool)
            .await?;
        Ok(row.get("count"))
    }

    /// Cleanup expired workflows (older than days)
    pub async fn cleanup_expired(&self, days: u32) -> Result<usize, sqlx::Error> {
        let cutoff = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs() as i64
            - (days as i64 * 86400);

        let result = sqlx::query("DELETE FROM workflows WHERE created_at < ?")
            .bind(cutoff)
            .execute(&self.pool)
            .await?;

        Ok(result.rows_affected() as usize)
    }

    /// Ensure default workflow exists (workflow_id=1)
    /// Creates it if missing, returns existing ID if present
    pub async fn ensure_default_workflow(&self) -> Result<i64, sqlx::Error> {
        // Check if workflow with id=1 exists
        let existing = sqlx::query("SELECT id FROM workflows WHERE id = 1")
            .fetch_optional(&self.pool)
            .await?;

        if existing.is_some() {
            return Ok(1);
        }

        // Create default workflow
        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs() as i64;

        sqlx::query(
            "INSERT INTO workflows (id, user_id, workflow_type, status, created_at, updated_at, input_params_json) VALUES (1, 'default', 'proxy-intercept', 'running', ?, ?, '{}')"
        )
        .bind(timestamp)
        .bind(timestamp)
        .execute(&self.pool)
        .await?;

        Ok(1)
    }
}

/// Message sent to persistence channel
#[derive(Debug)]
pub enum PersistenceMessage {
    ToolCall(ToolCall),
    Shutdown,
}

/// Spawn background writer task
///
/// Receives messages from mpsc channel and writes to SQLite
/// Let It Crash: Errors are logged but not retried
pub async fn spawn_persistence_writer(
    repo: SqliteCacheRepository,
    mut rx: mpsc::Receiver<PersistenceMessage>,
) {
    info!("Persistence writer started");

    // Ensure default workflow exists for hardcoded workflow_id=1 in interceptor
    if let Err(e) = repo.ensure_default_workflow().await {
        error!("Failed to create default workflow: {}", e);
    }

    while let Some(msg) = rx.recv().await {
        match msg {
            PersistenceMessage::ToolCall(call) => {
                match repo.create_tool_call(&call).await {
                    Ok(id) => {
                        info!("Persisted tool_call {} for tool {}", id, call.tool_name);
                    }
                    Err(e) => {
                        // Let It Crash: Log error but don't retry
                        error!("Failed to persist tool_call: {}", e);
                    }
                }
            }
            PersistenceMessage::Shutdown => {
                info!("Persistence writer shutting down");
                break;
            }
        }
    }
}

// Fixed tests with manual schema creation for in-memory DB

#[cfg(test)]
mod tests {
    use super::*;

    async fn create_test_repo() -> SqliteCacheRepository {
        let _db_path = std::path::PathBuf::from(":memory:");
        let pool = SqlitePool::connect("sqlite::memory:").await.unwrap();
        
        // Manually create schema for in-memory tests
        sqlx::query("PRAGMA journal_mode=WAL").execute(&pool).await.ok();
        sqlx::query("PRAGMA foreign_keys=ON").execute(&pool).await.ok();
        
        sqlx::query(r#"
            CREATE TABLE IF NOT EXISTS workflows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                workflow_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'running',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                input_params_json TEXT NOT NULL
            )
        "#).execute(&pool).await.unwrap();
        
        sqlx::query(r#"
            CREATE TABLE IF NOT EXISTS tool_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id INTEGER NOT NULL,
                phase_id INTEGER,
                tool_name TEXT NOT NULL,
                request_json TEXT NOT NULL,
                response_json TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                latency_ms INTEGER,
                created_at INTEGER NOT NULL,
                FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
            )
        "#).execute(&pool).await.unwrap();
        
        SqliteCacheRepository { pool }
    }

    #[tokio::test]
    async fn test_create_repository() {
        let repo = create_test_repo().await;
        assert_eq!(repo.count_workflows().await.unwrap(), 0);
    }

    #[tokio::test]
    async fn test_create_tool_call() {
        let repo = create_test_repo().await;

        // First create a workflow
        sqlx::query(
            "INSERT INTO workflows (user_id, workflow_type, status, created_at, updated_at, input_params_json) VALUES (?, ?, ?, ?, ?, ?)"
        )
        .bind("user123")
        .bind("test-workflow")
        .bind("running")
        .bind(1000000)
        .bind(1000000)
        .bind("{}")
        .execute(&repo.pool)
        .await
        .unwrap();

        let call = ToolCall {
            id: None,
            workflow_id: 1,
            phase_id: None,
            tool_name: "TEST_TOOL".to_string(),
            request_json: r#"{"arg": "value"}"#.to_string(),
            response_json: Some(r#"{"result": "success"}"#.to_string()),
            status: "success".to_string(),
            latency_ms: Some(42),
            created_at: 1000000,
        };

        let id = repo.create_tool_call(&call).await.unwrap();
        assert_eq!(id, 1);
    }
}
