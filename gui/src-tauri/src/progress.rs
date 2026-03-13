//! Tauri event types for real-time recipe progress

use serde::Serialize;
use tauri::{AppHandle, Emitter};

#[derive(Serialize, Clone, Debug)]
pub struct RecipeProgressEvent {
    pub command: String,
    pub phase: String,
    pub status: String,
    pub elapsed_sec: u64,
    pub message: String,
    pub result: Option<serde_json::Value>,
}

pub fn emit_progress(app: &AppHandle, event: RecipeProgressEvent) {
    let _ = app.emit("recipe-progress", &event);
}
