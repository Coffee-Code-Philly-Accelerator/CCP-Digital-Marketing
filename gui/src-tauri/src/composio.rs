//! HTTP client for Composio recipe execution
//!
//! Mirrors `ComposioRecipeClient` from `scripts/recipe_client.py`

use crate::config::AppConfig;
use crate::progress::{emit_progress, RecipeProgressEvent};
use reqwest::Client;
use serde_json::Value;
use std::time::Instant;
use tauri::AppHandle;

pub struct ComposioClient {
    http: Client,
    pub config: AppConfig,
}

impl ComposioClient {
    pub fn new(config: AppConfig) -> Self {
        Self {
            http: Client::new(),
            config,
        }
    }

    /// Execute a recipe and optionally poll until completion.
    /// Emits progress events to the frontend via `command` and `phase` labels.
    pub async fn execute_recipe(
        &self,
        recipe_id: &str,
        input_data: &Value,
        app: &AppHandle,
        command: &str,
        phase: &str,
    ) -> Result<Value, String> {
        if self.config.api_key.is_empty() {
            return Err(
                "COMPOSIO_API_KEY not set. Set it as an environment variable before launching the app."
                    .to_string(),
            );
        }

        let url = format!("{}/recipes/{}/execute", self.config.api_base, recipe_id);
        let body = serde_json::json!({ "input_data": input_data });
        let start = Instant::now();

        emit_progress(
            app,
            RecipeProgressEvent {
                command: command.to_string(),
                phase: phase.to_string(),
                status: "started".to_string(),
                elapsed_sec: 0,
                message: format!("Executing recipe {}", recipe_id),
                result: None,
            },
        );

        let response = self
            .http
            .post(&url)
            .header("Authorization", format!("Bearer {}", self.config.api_key))
            .header("Content-Type", "application/json")
            .header("Accept", "application/json")
            .json(&body)
            .send()
            .await
            .map_err(|e| format!("HTTP request failed: {}", e))?;

        let status_code = response.status();
        if !status_code.is_success() {
            let error_text = response
                .text()
                .await
                .unwrap_or_else(|_| "unknown error".to_string());
            let truncated = if error_text.len() > 500 {
                format!("{}...", &error_text[..500])
            } else {
                error_text
            };
            return Err(format!("HTTP {}: {}", status_code, truncated));
        }

        let result: Value = response
            .json()
            .await
            .map_err(|e| format!("Failed to parse response: {}", e))?;

        // If we got an execution_id, poll for completion
        if let Some(execution_id) = result.get("execution_id").and_then(|v| v.as_str()) {
            return self
                .poll_execution(execution_id, 300, app, command, phase, start)
                .await;
        }

        Ok(result)
    }

    /// Poll an execution until terminal status or timeout.
    async fn poll_execution(
        &self,
        execution_id: &str,
        timeout_secs: u64,
        app: &AppHandle,
        command: &str,
        phase: &str,
        start: Instant,
    ) -> Result<Value, String> {
        let url = format!("{}/executions/{}", self.config.api_base, execution_id);
        let terminal_statuses = ["completed", "success", "finished", "failed", "error"];

        loop {
            let elapsed = start.elapsed().as_secs();
            if elapsed >= timeout_secs {
                return Err(format!(
                    "Timeout after {}s waiting for execution {}",
                    timeout_secs, execution_id
                ));
            }

            let response = self
                .http
                .get(&url)
                .header("Authorization", format!("Bearer {}", self.config.api_key))
                .header("Accept", "application/json")
                .send()
                .await
                .map_err(|e| format!("Poll request failed: {}", e))?;

            let result: Value = response
                .json()
                .await
                .map_err(|e| format!("Failed to parse poll response: {}", e))?;

            let status = result
                .get("status")
                .and_then(|v| v.as_str())
                .unwrap_or("unknown");

            emit_progress(
                app,
                RecipeProgressEvent {
                    command: command.to_string(),
                    phase: phase.to_string(),
                    status: format!("polling:{}", status),
                    elapsed_sec: elapsed,
                    message: format!("Execution {} status: {}", execution_id, status),
                    result: None,
                },
            );

            if terminal_statuses.contains(&status) {
                let final_status = if status == "failed" || status == "error" {
                    "failed"
                } else {
                    "completed"
                };

                emit_progress(
                    app,
                    RecipeProgressEvent {
                        command: command.to_string(),
                        phase: phase.to_string(),
                        status: final_status.to_string(),
                        elapsed_sec: elapsed,
                        message: format!("Execution {} {}", execution_id, final_status),
                        result: Some(result.clone()),
                    },
                );

                return Ok(result);
            }

            tokio::time::sleep(std::time::Duration::from_secs(5)).await;
        }
    }

    /// Get recipe metadata/schema.
    pub async fn get_recipe_details(&self, recipe_id: &str) -> Result<Value, String> {
        if self.config.api_key.is_empty() {
            return Err("COMPOSIO_API_KEY not set.".to_string());
        }

        let url = format!("{}/recipes/{}", self.config.api_base, recipe_id);

        let response = self
            .http
            .get(&url)
            .header("Authorization", format!("Bearer {}", self.config.api_key))
            .header("Accept", "application/json")
            .send()
            .await
            .map_err(|e| format!("HTTP request failed: {}", e))?;

        let status_code = response.status();
        if !status_code.is_success() {
            let error_text = response
                .text()
                .await
                .unwrap_or_else(|_| "unknown error".to_string());
            return Err(format!("HTTP {}: {}", status_code, error_text));
        }

        response
            .json()
            .await
            .map_err(|e| format!("Failed to parse response: {}", e))
    }
}
