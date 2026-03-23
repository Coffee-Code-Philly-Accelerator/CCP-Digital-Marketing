//! HTTP client for Composio API
//!
//! LinkedIn uses Rube MCP (Composio v2 has expired LinkedIn API version).
//! Instagram uses v2 actions API with connectedAccountId.
//! AI tools (Gemini, Groq) use v3 tool router session API.

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

    /// Probe a single tool via v2 actions API to test if its connection is active.
    /// Returns Ok on success, Err with the error text on failure.
    async fn probe_tool_v2(
        &self,
        tool_slug: &str,
        connected_account_id: &str,
    ) -> Result<(), String> {
        let url = format!(
            "{}/api/v2/actions/{}/execute",
            self.config.api_base, tool_slug
        );
        let body = json!({
            "connectedAccountId": connected_account_id,
            "input": {},
        });

        let response = self
            .http
            .post(&url)
            .header("x-api-key", &self.config.api_key)
            .header("Content-Type", "application/json")
            .json(&body)
            .send()
            .await
            .map_err(|e| format!("{} probe failed: {}", tool_slug, e))?;

        if response.status().is_success() {
            Ok(())
        } else {
            let text = response.text().await.unwrap_or_default();
            Err(truncate_str(&text, 500))
        }
    }

    /// Check connection status for requested toolkits.
    /// LinkedIn: checks via v3 MCP initiate_connection (returns needs_auth with redirect URL).
    /// Instagram: checks via v2 API probe with connectedAccountId.
    pub async fn check_connections(&self, toolkits: &[&str]) -> Result<Value, String> {
        let mut structured = serde_json::Map::new();
        let mut all_active = true;

        for toolkit in toolkits {
            match *toolkit {
                "linkedin" => {
                    // LinkedIn uses MCP path — try initiate_connection to check status
                    match self.initiate_connection("linkedin").await {
                        Ok(url) if url == "already_connected" => {
                            structured.insert(
                                toolkit.to_string(),
                                json!({"status": "active"}),
                            );
                        }
                        Ok(url) => {
                            all_active = false;
                            structured.insert(
                                toolkit.to_string(),
                                json!({"status": "needs_auth", "redirect_url": url}),
                            );
                        }
                        Err(e) => {
                            all_active = false;
                            structured.insert(
                                toolkit.to_string(),
                                json!({"status": "error", "error": truncate_str(&e, 200)}),
                            );
                        }
                    }
                }
                "instagram" => {
                    let account_id = self.config.instagram_account_id.as_str();
                    if account_id.is_empty() {
                        all_active = false;
                        structured.insert(
                            toolkit.to_string(),
                            json!({"status": "needs_config", "note": "Set CCP_INSTAGRAM_ACCOUNT_ID env var"}),
                        );
                    } else {
                        match self.probe_tool_v2("INSTAGRAM_GET_USER_INFO", account_id).await {
                            Ok(()) => {
                                structured.insert(
                                    toolkit.to_string(),
                                    json!({"status": "active"}),
                                );
                            }
                            Err(e) => {
                                all_active = false;
                                let status = if e.contains("NoActiveConnection") {
                                    "needs_auth"
                                } else {
                                    "error"
                                };
                                structured.insert(
                                    toolkit.to_string(),
                                    json!({"status": status, "error": truncate_str(&e, 200)}),
                                );
                            }
                        }
                    }
                }
                "twitter" => {
                    structured.insert(
                        toolkit.to_string(),
                        json!({"status": "not_available", "note": "Not yet implemented"}),
                    );
                }
                _ => {
                    structured.insert(
                        toolkit.to_string(),
                        json!({"status": "config_required"}),
                    );
                }
            }
        }

        Ok(json!({
            "all_active": all_active,
            "results": Value::Object(structured),
        }))
    }

    /// Execute a tool via the v2 actions API with a connected account ID.
    /// Used for social media tools (LinkedIn, Instagram, Facebook, Discord).
    pub async fn execute_tool_v2(
        &self,
        tool_slug: &str,
        connected_account_id: &str,
        input: &Value,
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
        if connected_account_id.is_empty() {
            return Err(format!(
                "No connected account ID for {}. Set the corresponding CCP_*_ACCOUNT_ID env var.",
                tool_slug
            ));
        }

        let start = Instant::now();

        emit_progress(
            app,
            RecipeProgressEvent {
                command: command.to_string(),
                phase: phase.to_string(),
                status: "started".to_string(),
                elapsed_sec: 0,
                message: format!("Executing {} (v2)", tool_slug),
                result: None,
            },
        );

        let url = format!(
            "{}/api/v2/actions/{}/execute",
            self.config.api_base, tool_slug
        );
        let body = json!({
            "connectedAccountId": connected_account_id,
            "input": input,
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

        // Composio v2 wraps errors in HTTP 200 with "successful": false
        let is_successful = result
            .get("successful")
            .and_then(|v| v.as_bool())
            .unwrap_or(true);
        if !is_successful {
            let error_msg = result
                .get("error")
                .and_then(|v| v.as_str())
                .or_else(|| {
                    result
                        .get("data")
                        .and_then(|d| d.get("message").or_else(|| d.get("error")))
                        .and_then(|v| v.as_str())
                })
                .unwrap_or("unknown error");
            return Err(format!("{}: {}", tool_slug, truncate_str(error_msg, 500)));
        }

        let elapsed = start.elapsed().as_secs();
        emit_progress(
            app,
            RecipeProgressEvent {
                command: command.to_string(),
                phase: phase.to_string(),
                status: "completed".to_string(),
                elapsed_sec: elapsed,
                message: format!("{} completed (v2)", tool_slug),
                result: Some(result.clone()),
            },
        );

        Ok(result)
    }

    /// Execute a tool via the v3 session MCP endpoint (JSON-RPC over SSE).
    /// Used for LinkedIn where the v2 API has an expired LinkedIn API version.
    /// Calls COMPOSIO_MULTI_EXECUTE_TOOL through the session's MCP endpoint.
    pub async fn execute_tool_mcp(
        &self,
        tool_slug: &str,
        arguments: &Value,
        app: &AppHandle,
        command: &str,
        phase: &str,
    ) -> Result<Value, String> {
        if self.config.api_key.is_empty() {
            return Err("COMPOSIO_API_KEY not set".to_string());
        }

        let start = Instant::now();
        emit_progress(
            app,
            RecipeProgressEvent {
                command: command.to_string(),
                phase: phase.to_string(),
                status: "started".to_string(),
                elapsed_sec: 0,
                message: format!("Executing {} (mcp)", tool_slug),
                result: None,
            },
        );

        let session_id = self.ensure_session().await?;
        let url = format!(
            "{}/tool_router/{}/mcp",
            self.config.api_base, session_id
        );

        let rpc_body = json!({
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 1,
            "params": {
                "name": "COMPOSIO_MULTI_EXECUTE_TOOL",
                "arguments": {
                    "tools": [{"tool_slug": tool_slug, "arguments": arguments}],
                    "sync_response_to_workbench": false,
                    "thought": format!("execute {}", tool_slug),
                    "current_step": "EXECUTING",
                    "memory": {}
                }
            }
        });

        let response = self
            .http
            .post(&url)
            .header("x-api-key", &self.config.api_key)
            .header("Content-Type", "application/json")
            .header("Accept", "application/json, text/event-stream")
            .json(&rpc_body)
            .send()
            .await
            .map_err(|e| format!("{} MCP request failed: {}", tool_slug, e))?;

        let body = response
            .text()
            .await
            .map_err(|e| format!("{} MCP response read failed: {}", tool_slug, e))?;

        // Parse SSE event stream — extract the JSON-RPC result from "data:" lines
        let json_str = body
            .lines()
            .find(|line| line.starts_with("data: "))
            .map(|line| &line[6..])
            .unwrap_or(&body);

        let rpc_result: Value = serde_json::from_str(json_str)
            .map_err(|e| format!("{} MCP parse error: {} (body: {})", tool_slug, e, truncate_str(&body, 200)))?;

        // Check for JSON-RPC error
        if let Some(err) = rpc_result.get("error") {
            return Err(format!("{} MCP error: {}", tool_slug, err));
        }

        // Extract tool result from: result.content[0].text (JSON string)
        let content_text = rpc_result
            .get("result")
            .and_then(|r| r.get("content"))
            .and_then(|c| c.get(0))
            .and_then(|c| c.get("text"))
            .and_then(|t| t.as_str())
            .unwrap_or("{}");

        let inner: Value = serde_json::from_str(content_text)
            .map_err(|e| format!("{} MCP inner parse error: {}", tool_slug, e))?;

        // Check Composio-level success
        let successful = inner.get("successful").and_then(|v| v.as_bool()).unwrap_or(false);
        if !successful {
            let err_msg = inner
                .get("error")
                .and_then(|v| v.as_str())
                .unwrap_or("unknown error");
            return Err(format!("{}: {}", tool_slug, truncate_str(err_msg, 500)));
        }

        // Extract actual tool result from data.results[0].response
        let result = inner
            .get("data")
            .and_then(|d| d.get("results"))
            .and_then(|r| r.get(0))
            .and_then(|r| r.get("response"))
            .cloned()
            .unwrap_or(inner.clone());

        let elapsed = start.elapsed().as_secs();
        emit_progress(
            app,
            RecipeProgressEvent {
                command: command.to_string(),
                phase: phase.to_string(),
                status: "completed".to_string(),
                elapsed_sec: elapsed,
                message: format!("{} completed (mcp)", tool_slug),
                result: Some(result.clone()),
            },
        );

        Ok(result)
    }

    /// Initiate a connection for a toolkit via v3 MCP endpoint.
    /// Returns the redirect URL for the user to complete OAuth.
    pub async fn initiate_connection(&self, toolkit: &str) -> Result<String, String> {
        let session_id = self.ensure_session().await?;
        let url = format!(
            "{}/tool_router/{}/mcp",
            self.config.api_base, session_id
        );

        let rpc_body = json!({
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 1,
            "params": {
                "name": "COMPOSIO_MANAGE_CONNECTIONS",
                "arguments": {
                    "toolkits": [toolkit],
                    "action": "check"
                }
            }
        });

        let response = self
            .http
            .post(&url)
            .header("x-api-key", &self.config.api_key)
            .header("Content-Type", "application/json")
            .header("Accept", "application/json, text/event-stream")
            .json(&rpc_body)
            .send()
            .await
            .map_err(|e| format!("Connection initiation failed: {}", e))?;

        let body = response.text().await.unwrap_or_default();
        let json_str = body
            .lines()
            .find(|line| line.starts_with("data: "))
            .map(|line| &line[6..])
            .unwrap_or(&body);

        let rpc_result: Value = serde_json::from_str(json_str)
            .map_err(|e| format!("Connection parse error: {}", e))?;

        let content_text = rpc_result
            .get("result")
            .and_then(|r| r.get("content"))
            .and_then(|c| c.get(0))
            .and_then(|c| c.get("text"))
            .and_then(|t| t.as_str())
            .unwrap_or("{}");

        let inner: Value = serde_json::from_str(content_text).unwrap_or(json!({}));

        // Extract redirect URL from results
        let redirect_url = inner
            .get("data")
            .and_then(|d| d.get("results"))
            .and_then(|r| r.get(toolkit))
            .and_then(|t| t.get("redirect_url"))
            .and_then(|v| v.as_str())
            .unwrap_or("");

        if redirect_url.is_empty() {
            // Check if already active
            let status = inner
                .get("data")
                .and_then(|d| d.get("results"))
                .and_then(|r| r.get(toolkit))
                .and_then(|t| t.get("status"))
                .and_then(|v| v.as_str())
                .unwrap_or("unknown");
            if status == "active" {
                return Ok("already_connected".to_string());
            }
            return Err(format!("No redirect URL returned for {}", toolkit));
        }

        Ok(redirect_url.to_string())
    }

    /// Execute a tool via the v3 tool router session API.
    /// Used for AI tools (Gemini, Groq) that don't need connected accounts.
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
