//! HTTP client for Composio v3 tool router session API
//!
//! Executes individual tools via session-based API, replacing the
//! deprecated v1 recipe execution endpoint.

use crate::config::AppConfig;
use crate::progress::{emit_progress, RecipeProgressEvent};
use reqwest::Client;
use serde_json::{json, Value};
use std::time::Instant;
use tauri::AppHandle;
use tokio::sync::RwLock;

pub struct ComposioClient {
    http: Client,
    pub config: AppConfig,
    session_id: RwLock<Option<String>>,
}

impl ComposioClient {
    pub fn new(config: AppConfig) -> Self {
        Self {
            http: Client::new(),
            config,
            session_id: RwLock::new(None),
        }
    }

    /// Ensure a v3 tool router session exists, creating one if needed.
    async fn ensure_session(&self) -> Result<String, String> {
        {
            let guard = self.session_id.read().await;
            if let Some(ref id) = *guard {
                return Ok(id.clone());
            }
        }

        let url = format!("{}/api/v3/tool_router/session", self.config.api_base);
        let body = json!({ "user_id": self.config.composio_user_id });

        let response = self
            .http
            .post(&url)
            .header("x-api-key", &self.config.api_key)
            .header("Content-Type", "application/json")
            .json(&body)
            .send()
            .await
            .map_err(|e| format!("Session creation failed: {}", e))?;

        let status = response.status();
        if !status.is_success() {
            let text = response.text().await.unwrap_or_default();
            return Err(format!(
                "Session creation HTTP {}: {}",
                status,
                truncate_str(&text, 500)
            ));
        }

        let result: Value = response
            .json()
            .await
            .map_err(|e| format!("Session parse error: {}", e))?;

        // Session ID can appear at various nesting levels
        let session_id = result
            .get("session_id")
            .or_else(|| result.get("sessionId"))
            .or_else(|| {
                result
                    .get("data")
                    .and_then(|d| d.get("session_id").or_else(|| d.get("sessionId")))
            })
            .and_then(|v| v.as_str())
            .ok_or_else(|| format!("No session_id in response: {}", result))?
            .to_string();

        let mut guard = self.session_id.write().await;
        *guard = Some(session_id.clone());

        Ok(session_id)
    }

    /// Invalidate the current session (e.g., on auth error).
    async fn invalidate_session(&self) {
        let mut guard = self.session_id.write().await;
        *guard = None;
    }

    /// Ensure connections are active for the given toolkits in this session.
    /// Returns Ok(()) if all active, or Err with redirect URLs for any that need auth.
    pub async fn ensure_connections(&self, toolkits: &[&str]) -> Result<(), String> {
        let session_id = self.ensure_session().await?;
        let url = format!(
            "{}/api/v3/tool_router/session/{}/execute",
            self.config.api_base, session_id
        );
        let body = serde_json::json!({
            "tool_slug": "COMPOSIO_MANAGE_CONNECTIONS",
            "arguments": {
                "toolkits": toolkits,
            },
        });

        let response = self
            .http
            .post(&url)
            .header("x-api-key", &self.config.api_key)
            .header("Content-Type", "application/json")
            .json(&body)
            .send()
            .await
            .map_err(|e| format!("Connection check failed: {}", e))?;

        let status_code = response.status();
        if !status_code.is_success() {
            let text = response.text().await.unwrap_or_default();
            return Err(format!(
                "COMPOSIO_MANAGE_CONNECTIONS HTTP {}: {}",
                status_code,
                truncate_str(&text, 500)
            ));
        }

        let result: Value = response
            .json()
            .await
            .map_err(|e| format!("Connection check parse error: {}", e))?;

        // Check if any toolkit needs authentication
        let data = extract_data(&result);
        let results = data.get("results").cloned().unwrap_or(Value::Object(serde_json::Map::new()));

        let mut needs_auth = Vec::new();
        if let Some(obj) = results.as_object() {
            for (toolkit, info) in obj {
                let status = info.get("status").and_then(|v| v.as_str()).unwrap_or("");
                if status != "active" {
                    let redirect = info
                        .get("redirect_url")
                        .and_then(|v| v.as_str())
                        .unwrap_or("(no URL)");
                    needs_auth.push(format!("{}: {}", toolkit, redirect));
                }
            }
        }

        if needs_auth.is_empty() {
            Ok(())
        } else {
            Err(format!(
                "These toolkits need authentication. Open these URLs to connect:\n{}",
                needs_auth.join("\n")
            ))
        }
    }

    /// Execute a tool via the v3 tool router session API.
    /// On 401/403, invalidates session and retries once.
    pub async fn execute_tool(
        &self,
        tool_slug: &str,
        arguments: &Value,
        app: &AppHandle,
        command: &str,
        phase: &str,
    ) -> Result<Value, String> {
        if self.config.api_key.is_empty() {
            return Err(
                "COMPOSIO_API_KEY not set. Set it as an environment variable before launching."
                    .to_string(),
            );
        }

        let start = Instant::now();

        emit_progress(
            app,
            RecipeProgressEvent {
                command: command.to_string(),
                phase: phase.to_string(),
                status: "started".to_string(),
                elapsed_sec: 0,
                message: format!("Executing {}", tool_slug),
                result: None,
            },
        );

        for attempt in 0..2u8 {
            let session_id = self.ensure_session().await?;
            let url = format!(
                "{}/api/v3/tool_router/session/{}/execute",
                self.config.api_base, session_id
            );
            let body = json!({
                "tool_slug": tool_slug,
                "arguments": arguments,
            });

            let response = self
                .http
                .post(&url)
                .header("x-api-key", &self.config.api_key)
                .header("Content-Type", "application/json")
                .json(&body)
                .send()
                .await
                .map_err(|e| format!("{} request failed: {}", tool_slug, e))?;

            let status_code = response.status();

            // Retry once with fresh session on auth errors
            if (status_code.as_u16() == 401 || status_code.as_u16() == 403) && attempt == 0 {
                self.invalidate_session().await;
                continue;
            }

            if !status_code.is_success() {
                let error_text = response.text().await.unwrap_or_default();
                return Err(format!(
                    "{} HTTP {}: {}",
                    tool_slug,
                    status_code,
                    truncate_str(&error_text, 500)
                ));
            }

            let result: Value = response
                .json()
                .await
                .map_err(|e| format!("Failed to parse {} response: {}", tool_slug, e))?;

            let elapsed = start.elapsed().as_secs();
            emit_progress(
                app,
                RecipeProgressEvent {
                    command: command.to_string(),
                    phase: phase.to_string(),
                    status: "completed".to_string(),
                    elapsed_sec: elapsed,
                    message: format!("{} completed", tool_slug),
                    result: Some(result.clone()),
                },
            );

            return Ok(result);
        }

        Err(format!("{}: auth retry exhausted", tool_slug))
    }
}

// ============================================================================
// Response extraction helpers
// ============================================================================

/// Extract nested data from Composio API response.
/// Handles both `{data: {...}}` and `{data: {data: {...}}}` patterns.
pub fn extract_data(result: &Value) -> Value {
    let data = result.get("data").unwrap_or(result);
    if let Some(inner) = data.get("data") {
        if inner.is_object() || inner.is_array() {
            return inner.clone();
        }
    }
    data.clone()
}

/// Extract the text content from an LLM chat completion response.
/// Handles OpenAI-compatible `choices[0].message.content` structure.
pub fn extract_llm_content(result: &Value) -> Option<String> {
    let data = extract_data(result);
    data.get("choices")
        .and_then(|c| c.get(0))
        .and_then(|c| c.get("message"))
        .and_then(|m| m.get("content"))
        .and_then(|v| v.as_str())
        .map(|s| s.to_string())
}

/// Extract image URL from a Composio tool response.
/// Handles v3 format (`data.image.s3url`) and recipe format (`data.publicUrl`).
pub fn extract_image_url(result: &Value) -> String {
    let data = extract_data(result);
    data.get("image")
        .and_then(|img| img.get("s3url").or_else(|| img.get("publicUrl")))
        .or_else(|| data.get("publicUrl"))
        .or_else(|| data.get("s3url"))
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string()
}

/// Extract the first JSON object from text that may contain surrounding prose.
/// Handles LLM responses wrapped in markdown code blocks or explanation text.
pub fn extract_json_from_text(text: &str) -> Option<Value> {
    if let Ok(val) = serde_json::from_str::<Value>(text) {
        return Some(val);
    }

    let bytes = text.as_bytes();
    let start = bytes.iter().position(|&b| b == b'{')?;
    let mut depth = 0i32;
    for (i, &b) in bytes[start..].iter().enumerate() {
        match b {
            b'{' => depth += 1,
            b'}' => {
                depth -= 1;
                if depth == 0 {
                    let slice = &text[start..start + i + 1];
                    return serde_json::from_str(slice).ok();
                }
            }
            _ => {}
        }
    }
    None
}

/// UTF-8 safe string truncation (single pass).
fn truncate_str(s: &str, max_chars: usize) -> String {
    let mut chars = s.chars();
    let truncated: String = (&mut chars).take(max_chars).collect();
    if chars.next().is_some() {
        format!("{}...", truncated)
    } else {
        truncated
    }
}
