//! CCP Digital Marketing - Telemetry Cache GUI
//!
//! Tauri desktop app for viewing workflow telemetry with timeline visualization

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod db;

use sqlx::sqlite::SqlitePool;
use std::path::PathBuf;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Database path
    let db_path = std::env::var("CCP_CACHE_DB_PATH").unwrap_or_else(|_| {
        dirs::home_dir()
            .unwrap_or_else(|| PathBuf::from("."))
            .join(".claude/cache/state.db")
            .display()
            .to_string()
    });

    println!("CCP Cache GUI - Database: {}", db_path);

    // Initialize SQLite pool
    let pool = SqlitePool::connect(&format!("sqlite:{}", db_path)).await?;

    // Enable WAL mode and foreign keys
    sqlx::query("PRAGMA journal_mode=WAL")
        .execute(&pool)
        .await?;
    sqlx::query("PRAGMA foreign_keys=ON")
        .execute(&pool)
        .await?;

    println!("SQLite connection established (WAL mode)");

    // TODO: Optionally spawn proxy server in background
    // This would require feature flag or config option
    // tokio::spawn(async { ccp_cache_proxy::start_proxy().await });

    // Build and run Tauri app
    tauri::Builder::default()
        .manage(pool)
        .invoke_handler(tauri::generate_handler![
            db::list_workflows,
            db::get_workflow_tool_calls,
            db::search_correlation,
            db::cleanup_expired,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");

    Ok(())
}
