//! Database query functions for Tauri commands

use serde::{Deserialize, Serialize};
use sqlx::sqlite::{SqlitePool, SqliteRow};
use sqlx::Row;

#[derive(Debug, Serialize, Deserialize)]
pub struct WorkflowSummary {
    pub id: i64,
    pub user_id: String,
    pub workflow_type: String,
    pub status: String,
    pub created_at: i64,
    pub updated_at: i64,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ToolCallSummary {
    pub id: i64,
    pub tool_name: String,
    pub status: String,
    pub latency_ms: Option<i64>,
    pub created_at: i64,
}

/// List all workflows with optional filtering
#[tauri::command]
pub async fn list_workflows(
    pool: tauri::State<'_, SqlitePool>,
    workflow_type: Option<String>,
    status: Option<String>,
) -> Result<Vec<WorkflowSummary>, String> {
    let rows: Vec<SqliteRow> = sqlx::query(
        "SELECT id, user_id, workflow_type, status, created_at, updated_at FROM workflows WHERE (? IS NULL OR workflow_type = ?) AND (? IS NULL OR status = ?) ORDER BY created_at DESC LIMIT 100"
    )
    .bind(&workflow_type)
    .bind(&workflow_type)
    .bind(&status)
    .bind(&status)
    .fetch_all(pool.inner())
    .await
    .map_err(|e| format!("Database query failed: {}", e))?;

    let workflows = rows
        .iter()
        .map(|row| WorkflowSummary {
            id: row.get("id"),
            user_id: row.get("user_id"),
            workflow_type: row.get("workflow_type"),
            status: row.get("status"),
            created_at: row.get("created_at"),
            updated_at: row.get("updated_at"),
        })
        .collect();

    Ok(workflows)
}

/// Get tool calls for a specific workflow
#[tauri::command]
pub async fn get_workflow_tool_calls(
    pool: tauri::State<'_, SqlitePool>,
    workflow_id: i64,
) -> Result<Vec<ToolCallSummary>, String> {
    let rows: Vec<SqliteRow> = sqlx::query(
        "SELECT id, tool_name, status, latency_ms, created_at FROM tool_calls WHERE workflow_id = ? ORDER BY created_at ASC"
    )
    .bind(workflow_id)
    .fetch_all(pool.inner())
    .await
    .map_err(|e| format!("Database query failed: {}", e))?;

    let tool_calls = rows
        .iter()
        .map(|row| ToolCallSummary {
            id: row.get("id"),
            tool_name: row.get("tool_name"),
            status: row.get("status"),
            latency_ms: row.get("latency_ms"),
            created_at: row.get("created_at"),
        })
        .collect();

    Ok(tool_calls)
}

/// Search for workflows containing a specific artifact
#[tauri::command]
pub async fn search_correlation(
    pool: tauri::State<'_, SqlitePool>,
    artifact: String,
) -> Result<Vec<WorkflowSummary>, String> {
    let search_pattern = format!("%{}%", artifact);

    let rows: Vec<SqliteRow> = sqlx::query(
        r#"
        SELECT DISTINCT w.id, w.user_id, w.workflow_type, w.status, w.created_at, w.updated_at
        FROM workflows w
        JOIN tool_calls tc ON tc.workflow_id = w.id
        WHERE tc.request_json LIKE ? OR tc.response_json LIKE ?
        ORDER BY w.created_at DESC
        LIMIT 50
        "#,
    )
    .bind(&search_pattern)
    .bind(&search_pattern)
    .fetch_all(pool.inner())
    .await
    .map_err(|e| format!("Database query failed: {}", e))?;

    let workflows = rows
        .iter()
        .map(|row| WorkflowSummary {
            id: row.get("id"),
            user_id: row.get("user_id"),
            workflow_type: row.get("workflow_type"),
            status: row.get("status"),
            created_at: row.get("created_at"),
            updated_at: row.get("updated_at"),
        })
        .collect();

    Ok(workflows)
}

/// Cleanup expired workflows (older than days)
#[tauri::command]
pub async fn cleanup_expired(
    pool: tauri::State<'_, SqlitePool>,
    days: u32,
) -> Result<usize, String> {
    let cutoff = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_secs() as i64
        - (days as i64 * 86400);

    let result = sqlx::query("DELETE FROM workflows WHERE created_at < ?")
        .bind(cutoff)
        .execute(pool.inner())
        .await
        .map_err(|e| format!("Database query failed: {}", e))?;

    Ok(result.rows_affected() as usize)
}
