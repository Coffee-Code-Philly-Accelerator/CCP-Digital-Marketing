// Fixed tests with manual schema creation for in-memory DB

#[cfg(test)]
mod tests {
    use super::*;

    async fn create_test_repo() -> SqliteCacheRepository {
        let db_path = std::path::PathBuf::from(":memory:");
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
