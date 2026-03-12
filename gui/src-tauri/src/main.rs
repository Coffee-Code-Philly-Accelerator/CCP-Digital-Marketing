//! CCP Digital Marketing - Tauri GUI
//!
//! Desktop app for viewing workflow telemetry and executing Composio recipes
//! (event creation, social promotion, draft management).

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod composio;
mod config;
mod db;
mod draft;
mod draft_commands;
mod progress;
mod recipe_commands;

use composio::ComposioClient;
use config::AppConfig;
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

    println!("CCP Digital Marketing - Database: {}", db_path);

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

    // Initialize Composio client
    let app_config = AppConfig::from_env();
    if app_config.api_key.is_empty() {
        println!("Warning: COMPOSIO_API_KEY not set. Recipe execution will be unavailable.");
    } else {
        println!("Composio client initialized (API base: {})", app_config.api_base);
    }
    println!("Drafts directory: {}", app_config.drafts_dir);
    let composio_client = ComposioClient::new(app_config);

    // Build and run Tauri app
    tauri::Builder::default()
        .manage(pool)
        .manage(composio_client)
        .invoke_handler(tauri::generate_handler![
            // Existing telemetry commands
            db::list_workflows,
            db::get_workflow_tool_calls,
            db::search_correlation,
            db::cleanup_expired,
            // Recipe commands
            recipe_commands::create_event,
            recipe_commands::promote_event,
            recipe_commands::social_post,
            recipe_commands::full_workflow,
            recipe_commands::get_recipe_info,
            // Draft commands
            draft_commands::generate_drafts,
            draft_commands::list_drafts_cmd,
            draft_commands::load_draft_cmd,
            draft_commands::approve_draft,
            draft_commands::publish_draft,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");

    Ok(())
}
