//! Tauri IPC commands for draft management
//!
//! Draft generation uses Composio v3 tool router session:
//! - GEMINI_GENERATE_IMAGE for promotional images
//! - COMPOSIO_SEARCH_GROQ_CHAT (Llama 3.3 70B) for platform-specific copy
//!
//! Draft publishing uses Composio v2 actions API with connectedAccountId
//! for social platforms (LinkedIn, Instagram). AI tools stay on v3.

use crate::composio::{
    extract_data, extract_image_url, extract_json_from_text, extract_llm_content, ComposioClient,
};
use crate::draft::{
    self, build_draft, load_draft, save_draft, set_draft_status, set_publish_results,
    validate_draft_for_publish, validate_draft_path, Draft, DraftCopies, DraftEvent,
    DraftPlatformConfig,
};
use crate::progress::{emit_progress, RecipeProgressEvent};
use serde_json::{json, Value};
use tauri::AppHandle;

// ============================================================================
// Draft generation helpers (image + copy via v3 tool calls)
// ============================================================================

/// Generate a promotional image via GEMINI_GENERATE_IMAGE.
/// Returns the public URL, or empty string if generation fails (non-fatal).
async fn generate_image(
    client: &ComposioClient,
    app: &AppHandle,
    topic: &str,
    command: &str,
) -> String {
    let prompt = format!(
        "Create a modern, eye-catching social media graphic about: {}. \
         Style: vibrant colors, suitable for social media. Do not include any text in the image.",
        topic
    );

    let result = client
        .execute_tool(
            "GEMINI_GENERATE_IMAGE",
            &json!({
                "prompt": prompt,
                "model": "gemini-2.5-flash-image"
            }),
            app,
            command,
            "image_generation",
        )
        .await;

    match result {
        Ok(val) => extract_image_url(&val),
        Err(e) => {
            emit_progress(
                app,
                RecipeProgressEvent {
                    command: command.to_string(),
                    phase: "image_generation".to_string(),
                    status: "warning".to_string(),
                    elapsed_sec: 0,
                    message: format!("Image generation failed (non-fatal): {}", e),
                    result: None,
                },
            );
            String::new()
        }
    }
}

/// Generate platform-specific copies via COMPOSIO_SEARCH_GROQ_CHAT.
async fn generate_copies(
    client: &ComposioClient,
    app: &AppHandle,
    prompt: &str,
    command: &str,
) -> Result<Value, String> {
    let result = client
        .execute_tool(
            "COMPOSIO_SEARCH_GROQ_CHAT",
            &json!({
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a social media copywriter. Return ONLY a valid JSON object, no other text."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.7,
                "max_tokens": 2000
            }),
            app,
            command,
            "copy_generation",
        )
        .await?;

    let content =
        extract_llm_content(&result).ok_or_else(|| "LLM returned no content".to_string())?;

    let copies = extract_json_from_text(&content)
        .ok_or_else(|| format!("Failed to parse JSON from LLM response: {}", content))?;

    let required = ["twitter", "linkedin", "instagram", "facebook", "discord"];
    for key in &required {
        let val = copies.get(*key).and_then(|v| v.as_str()).unwrap_or("");
        if val.is_empty() {
            return Err(format!("Missing or empty '{}' in LLM response", key));
        }
    }

    Ok(copies)
}

/// Build a fallback copies object when LLM generation fails.
fn default_copies(topic: &str, content: &str, url: &str) -> Value {
    let base = if url.is_empty() {
        format!("{}\n\n{}", topic, content)
    } else {
        format!("{}\n\n{}\n\n{}", topic, content, url)
    };
    let twitter: String = base.chars().take(280).collect();
    json!({
        "twitter": twitter,
        "linkedin": base,
        "instagram": base,
        "facebook": base,
        "discord": format!("**{}**\n\n{}", topic, base),
    })
}

/// Extract DraftCopies from a JSON copies value.
fn copies_from_json(val: &Value) -> DraftCopies {
    DraftCopies {
        twitter: val
            .get("twitter")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string(),
        linkedin: val
            .get("linkedin")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string(),
        instagram: val
            .get("instagram")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string(),
        facebook: val
            .get("facebook")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string(),
        discord: val
            .get("discord")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string(),
    }
}

// ============================================================================
// Social platform posting helpers (for publish_draft)
// ============================================================================

/// Append a URL to text with double newline separator, or return text as-is.
fn with_url(text: &str, url: &str) -> String {
    if url.is_empty() {
        text.to_string()
    } else {
        format!("{}\n\n{}", text, url)
    }
}

/// Extract a string or numeric ID from a JSON value.
fn value_as_string_id(data: &Value, key: &str) -> String {
    data.get(key)
        .and_then(|v| match v {
            Value::String(s) => Some(s.clone()),
            Value::Number(n) => Some(n.to_string()),
            _ => None,
        })
        .unwrap_or_default()
}

async fn post_to_linkedin(client: &ComposioClient, app: &AppHandle, draft: &Draft) -> String {
    // LinkedIn uses v3 MCP endpoint (v2 API has expired LinkedIn API version 20241101)
    // Pre-check: ensure LinkedIn is connected to the session
    match client.initiate_connection("linkedin").await {
        Ok(url) if url != "already_connected" => {
            return format!(
                "needs_auth: LinkedIn not connected. Complete OAuth at: {}",
                url
            );
        }
        Err(e) => {
            return format!("failed: connection check - {}", e);
        }
        _ => {} // already_connected — proceed
    }

    let text = with_url(&draft.copies.linkedin, &draft.event.url);

    // First get user info to find author URN
    let profile_result = client
        .execute_tool_mcp(
            "LINKEDIN_GET_MY_INFO",
            &json!({}),
            app,
            "publish_draft",
            "linkedin",
        )
        .await;

    let profile_data = match profile_result {
        Ok(val) => extract_data(&val),
        Err(e) => return format!("failed: {}", e),
    };

    // MCP response may nest under response_dict or data.response_dict
    let inner = profile_data
        .get("response_dict")
        .or_else(|| {
            profile_data
                .get("data")
                .and_then(|d| d.get("response_dict"))
        })
        .unwrap_or(&profile_data);
    let author = inner
        .get("author_id")
        .or_else(|| inner.get("id"))
        .and_then(|v| v.as_str())
        .unwrap_or("");
    if author.is_empty() {
        return "failed: could not determine user ID".to_string();
    }

    let author = if author.starts_with("urn:li:") {
        author.to_string()
    } else {
        format!("urn:li:person:{}", author)
    };

    let post_result = client
        .execute_tool_mcp(
            "LINKEDIN_CREATE_LINKED_IN_POST",
            &json!({
                "author": author,
                "commentary": text,
                "visibility": "PUBLIC",
            }),
            app,
            "publish_draft",
            "linkedin",
        )
        .await;

    match post_result {
        Ok(_) => "success".to_string(),
        Err(e) => format!("failed: {}", e),
    }
}

/// Check if a signed URL has likely expired (contains X-Amz-Expires with short TTL).
fn is_signed_url_expired(url: &str) -> bool {
    if !url.contains("X-Amz-Date=") || !url.contains("X-Amz-Expires=") {
        return false;
    }
    // Parse X-Amz-Date (format: 20260320T163410Z) and X-Amz-Expires (seconds)
    let date_str = url
        .split("X-Amz-Date=")
        .nth(1)
        .and_then(|s| s.split('&').next())
        .unwrap_or("");
    let expires_str = url
        .split("X-Amz-Expires=")
        .nth(1)
        .and_then(|s| s.split('&').next())
        .unwrap_or("0");
    let expires_sec: i64 = expires_str.parse().unwrap_or(0);

    if let Ok(signed_at) = chrono::NaiveDateTime::parse_from_str(date_str, "%Y%m%dT%H%M%SZ") {
        let expiry = signed_at + chrono::Duration::seconds(expires_sec);
        let now = chrono::Utc::now().naive_utc();
        now > expiry
    } else {
        false
    }
}

async fn post_to_instagram(client: &ComposioClient, app: &AppHandle, draft: &Draft) -> String {
    if draft.image_url.is_empty() {
        return "skipped: no image available".to_string();
    }
    if is_signed_url_expired(&draft.image_url) {
        return "failed: image URL expired. Generate a new draft to get a fresh image.".to_string();
    }

    let account_id = &client.config.instagram_account_id;
    if account_id.is_empty() {
        return "skipped: CCP_INSTAGRAM_ACCOUNT_ID not set".to_string();
    }

    let user_result = client
        .execute_tool_v2(
            "INSTAGRAM_GET_USER_INFO",
            account_id,
            &json!({}),
            app,
            "publish_draft",
            "instagram",
        )
        .await;

    let user_data = match user_result {
        Ok(val) => extract_data(&val),
        Err(e) => return format!("failed: {}", e),
    };

    let ig_user_id = value_as_string_id(&user_data, "id");
    if ig_user_id.is_empty() {
        return "failed: could not determine user ID".to_string();
    }

    let container_result = client
        .execute_tool_v2(
            "INSTAGRAM_CREATE_MEDIA_CONTAINER",
            account_id,
            &json!({
                "ig_user_id": ig_user_id,
                "image_url": draft.image_url,
                "caption": draft.copies.instagram,
            }),
            app,
            "publish_draft",
            "instagram",
        )
        .await;

    let container_data = match container_result {
        Ok(val) => extract_data(&val),
        Err(e) => return format!("failed: container creation - {}", e),
    };

    let creation_id = value_as_string_id(&container_data, "id");
    if creation_id.is_empty() {
        return "failed: no container ID returned".to_string();
    }

    let publish_result = client
        .execute_tool_v2(
            "INSTAGRAM_CREATE_POST",
            account_id,
            &json!({
                "ig_user_id": ig_user_id,
                "creation_id": creation_id,
                "max_wait_seconds": 120,
            }),
            app,
            "publish_draft",
            "instagram",
        )
        .await;

    match publish_result {
        Ok(_) => "success".to_string(),
        Err(e) => format!("failed: publish - {}", e),
    }
}

async fn post_to_facebook(
    client: &ComposioClient,
    app: &AppHandle,
    draft: &Draft,
    page_id: &str,
) -> String {
    if page_id.is_empty() {
        return "skipped: no page ID configured".to_string();
    }

    let message = with_url(&draft.copies.facebook, &draft.event.url);

    let result = client
        .execute_tool(
            "FACEBOOK_CREATE_POST",
            &json!({
                "page_id": page_id,
                "message": message,
            }),
            app,
            "publish_draft",
            "facebook",
        )
        .await;

    match result {
        Ok(_) => "success".to_string(),
        Err(e) => format!("failed: {}", e),
    }
}

async fn post_to_discord(
    client: &ComposioClient,
    app: &AppHandle,
    draft: &Draft,
    channel_id: &str,
) -> String {
    if channel_id.is_empty() {
        return "skipped: no channel ID configured".to_string();
    }

    let content = with_url(&draft.copies.discord, &draft.event.url);

    let result = client
        .execute_tool(
            "DISCORDBOT_CREATE_MESSAGE",
            &json!({
                "channel_id": channel_id,
                "content": content,
            }),
            app,
            "publish_draft",
            "discord",
        )
        .await;

    match result {
        Ok(_) => "success".to_string(),
        Err(e) => format!("failed: {}", e),
    }
}

// ============================================================================
// Tauri IPC commands
// ============================================================================

/// Generate social media drafts for event promotion without posting.
#[allow(clippy::too_many_arguments)]
#[tauri::command]
pub async fn generate_drafts(
    client: tauri::State<'_, ComposioClient>,
    app: AppHandle,
    title: String,
    date: String,
    time: String,
    location: String,
    description: String,
    event_url: String,
    discord_channel_id: Option<String>,
    facebook_page_id: Option<String>,
    skip_platforms: Option<String>,
) -> Result<Value, String> {
    let discord = discord_channel_id.unwrap_or_else(|| client.config.discord_channel_id.clone());
    let facebook = facebook_page_id.unwrap_or_else(|| client.config.facebook_page_id.clone());
    let skip = skip_platforms.unwrap_or_default();

    // Build copy prompt before parallel section
    let copy_prompt = format!(
        "Generate 5 platform-specific social media posts to promote this event:\n\n\
         Title: {}\nDate: {}\nTime: {}\nLocation: {}\nDescription: {}\nEvent URL: {}\n\n\
         Return ONLY a JSON object with keys: twitter, linkedin, instagram, facebook, discord\n\n\
         Guidelines:\n\
         - Twitter: Concise, hashtags, under 280 chars, include event URL\n\
         - LinkedIn: Professional, detailed, industry-focused, include event URL\n\
         - Instagram: Engaging, emoji-friendly, hashtags, include event URL\n\
         - Facebook: Conversational, community-focused, include event URL\n\
         - Discord: Markdown formatting, casual tone, include event URL",
        title, date, time, location, description, event_url
    );

    // Run image generation and copy generation in parallel
    let (image_url, copies_result) = tokio::join!(
        generate_image(&client, &app, &title, "generate_drafts"),
        generate_copies(&client, &app, &copy_prompt, "generate_drafts"),
    );

    let copies_val = match copies_result {
        Ok(val) => val,
        Err(e) => {
            emit_progress(
                &app,
                RecipeProgressEvent {
                    command: "generate_drafts".to_string(),
                    phase: "copy_generation".to_string(),
                    status: "warning".to_string(),
                    elapsed_sec: 0,
                    message: format!("LLM copy generation failed, using defaults: {}", e),
                    result: None,
                },
            );
            default_copies(&title, &description, &event_url)
        }
    };

    // Build and save draft
    let event = DraftEvent {
        title,
        date,
        time,
        location,
        description,
        url: event_url,
    };
    let copies = copies_from_json(&copies_val);
    let platform_config = DraftPlatformConfig {
        discord_channel_id: discord,
        facebook_page_id: facebook,
        skip_platforms: skip,
    };

    let draft_obj = build_draft(
        "event_promotion",
        &event,
        &copies,
        &image_url,
        &platform_config,
    );
    let filepath = save_draft(&client.config.drafts_dir, &draft_obj)?;

    Ok(json!({
        "draft_filepath": filepath.display().to_string(),
        "copies": copies_val,
        "image_url": image_url,
    }))
}

/// List all drafts.
#[tauri::command]
pub async fn list_drafts_cmd(client: tauri::State<'_, ComposioClient>) -> Result<Value, String> {
    let drafts = draft::list_drafts(&client.config.drafts_dir)?;
    serde_json::to_value(drafts).map_err(|e| format!("Serialization error: {}", e))
}

/// Load a specific draft by filepath.
#[tauri::command]
pub async fn load_draft_cmd(
    client: tauri::State<'_, ComposioClient>,
    filepath: String,
) -> Result<Value, String> {
    let validated = validate_draft_path(&client.config.drafts_dir, &filepath)?;
    let draft = load_draft(&validated.display().to_string())?;
    serde_json::to_value(draft).map_err(|e| format!("Serialization error: {}", e))
}

/// Approve a draft (set status from "draft" to "approved").
#[tauri::command]
pub async fn approve_draft(
    client: tauri::State<'_, ComposioClient>,
    filepath: String,
) -> Result<Value, String> {
    let validated = validate_draft_path(&client.config.drafts_dir, &filepath)?;
    let draft = load_draft(&validated.display().to_string())?;
    if draft.status != "draft" {
        return Err(format!(
            "Draft status is '{}', expected 'draft'",
            draft.status
        ));
    }
    let draft = set_draft_status(draft, "approved");
    let saved = save_draft(&client.config.drafts_dir, &draft)?;
    Ok(json!({
        "status": "approved",
        "filepath": saved.display().to_string(),
    }))
}

/// Publish an approved draft by posting to social media platforms.
#[tauri::command]
pub async fn publish_draft(
    client: tauri::State<'_, ComposioClient>,
    app: AppHandle,
    filepath: String,
) -> Result<Value, String> {
    let validated = validate_draft_path(&client.config.drafts_dir, &filepath)?;
    let draft = load_draft(&validated.display().to_string())?;

    if let Some(error) = validate_draft_for_publish(&draft) {
        return Err(format!("Draft validation failed: {}", error));
    }

    let skip: Vec<&str> = draft
        .platform_config
        .skip_platforms
        .split(',')
        .map(|s| s.trim())
        .filter(|s| !s.is_empty())
        .collect();

    // Probe Instagram connection before publishing (LinkedIn uses MCP, checks at call time)
    let probe_toolkits = vec!["instagram"];
    let conn_status = client.check_connections(&probe_toolkits).await?;
    let results = conn_status.get("results").cloned().unwrap_or(json!({}));
    let mut needs_auth = Vec::new();
    if let Some(obj) = results.as_object() {
        for (toolkit, info) in obj {
            let status = info.get("status").and_then(|v| v.as_str()).unwrap_or("");
            if status == "needs_auth" && !skip.contains(&toolkit.as_str()) {
                needs_auth.push(toolkit.clone());
            }
        }
    }
    if !needs_auth.is_empty() {
        return Err(format!(
            "Cannot publish: these platforms need authentication: {}. \
             Use 'Check Connections' in the Drafts tab to connect your accounts.",
            needs_auth.join(", ")
        ));
    }

    let discord_id = if draft.platform_config.discord_channel_id.is_empty() {
        &client.config.discord_channel_id
    } else {
        &draft.platform_config.discord_channel_id
    };
    let facebook_id = if draft.platform_config.facebook_page_id.is_empty() {
        &client.config.facebook_page_id
    } else {
        &draft.platform_config.facebook_page_id
    };

    // Post to all platforms in parallel
    let (linkedin_result, instagram_result, facebook_result, discord_result) = tokio::join!(
        async {
            if skip.contains(&"linkedin") {
                "skipped".to_string()
            } else {
                post_to_linkedin(&client, &app, &draft).await
            }
        },
        async {
            if skip.contains(&"instagram") {
                "skipped".to_string()
            } else {
                post_to_instagram(&client, &app, &draft).await
            }
        },
        async {
            if skip.contains(&"facebook") {
                "skipped".to_string()
            } else {
                post_to_facebook(&client, &app, &draft, facebook_id).await
            }
        },
        async {
            if skip.contains(&"discord") {
                "skipped".to_string()
            } else {
                post_to_discord(&client, &app, &draft, discord_id).await
            }
        },
    );

    let mut results = json!({
        "twitter_posted": "skipped: connection not available",
        "linkedin_posted": linkedin_result,
        "instagram_posted": instagram_result,
        "facebook_posted": facebook_result,
        "discord_posted": discord_result,
        "image_url": draft.image_url,
    });

    let success_count = [
        &linkedin_result,
        &instagram_result,
        &facebook_result,
        &discord_result,
    ]
    .iter()
    .filter(|s| s.as_str() == "success")
    .count();
    results["summary"] = json!(format!("Posted to {}/5 platforms", success_count));

    let new_status = if success_count > 0 {
        "published"
    } else {
        "failed"
    };

    let draft = set_publish_results(draft, results.clone());
    let draft = set_draft_status(draft, new_status);
    save_draft(&client.config.drafts_dir, &draft)?;

    Ok(json!({
        "status": new_status,
        "result": results,
    }))
}

/// Generate a social post draft from a free-form chat message.
#[allow(clippy::too_many_arguments)]
#[tauri::command]
pub async fn chat_generate_draft(
    client: tauri::State<'_, ComposioClient>,
    app: AppHandle,
    message: String,
    url: Option<String>,
    tone: Option<String>,
    image_url: Option<String>,
    image_prompt: Option<String>,
    cta: Option<String>,
    hashtags: Option<String>,
    discord_channel_id: Option<String>,
    facebook_page_id: Option<String>,
    skip_platforms: Option<String>,
) -> Result<Value, String> {
    let message = message.trim().to_string();
    if message.is_empty() {
        return Err("Message cannot be empty".to_string());
    }

    let discord = discord_channel_id.unwrap_or_else(|| client.config.discord_channel_id.clone());
    let facebook = facebook_page_id.unwrap_or_else(|| client.config.facebook_page_id.clone());
    let skip = skip_platforms.unwrap_or_default();
    let url_str = url.as_deref().unwrap_or("");
    let tone_str = tone.as_deref().unwrap_or("engaging");

    // Build copy prompt before parallel section
    let mut copy_prompt = format!(
        "Generate 5 platform-specific social media posts about this topic:\n\n\
         Topic: {}\nContent: {}\n",
        message, message
    );
    if !url_str.is_empty() {
        copy_prompt.push_str(&format!("Link: {}\n", url_str));
    }
    if let Some(ref c) = cta {
        if !c.is_empty() {
            copy_prompt.push_str(&format!("Call to action: {}\n", c));
        }
    }
    if let Some(ref h) = hashtags {
        if !h.is_empty() {
            copy_prompt.push_str(&format!("Hashtags to include: {}\n", h));
        }
    }
    copy_prompt.push_str(&format!(
        "Tone: {}\n\n\
         Return ONLY a JSON object with keys: twitter, linkedin, instagram, facebook, discord\n\n\
         Guidelines:\n\
         - Twitter: Concise, hashtags, under 280 chars\n\
         - LinkedIn: Professional, detailed, industry-focused\n\
         - Instagram: Engaging, emoji-friendly, hashtags\n\
         - Facebook: Conversational, community-focused\n\
         - Discord: Markdown formatting, casual tone\n\
         - If a link was provided, include it naturally in each post\n\
         - If a call to action was provided, incorporate it",
        tone_str
    ));

    // Resolve image: use provided URL, custom prompt, or auto-generate
    let image_future = async {
        if let Some(ref provided) = image_url {
            if !provided.is_empty() {
                return provided.clone();
            }
        }
        if let Some(ref prompt) = image_prompt {
            if !prompt.is_empty() {
                let result = client
                    .execute_tool(
                        "GEMINI_GENERATE_IMAGE",
                        &json!({ "prompt": prompt, "model": "gemini-2.5-flash-image" }),
                        &app,
                        "chat_generate_draft",
                        "image_generation",
                    )
                    .await;
                return match result {
                    Ok(val) => extract_image_url(&val),
                    Err(_) => String::new(),
                };
            }
        }
        generate_image(&client, &app, &message, "chat_generate_draft").await
    };

    // Run image and copy generation in parallel
    let (result_image_url, copies_result) = tokio::join!(
        image_future,
        generate_copies(&client, &app, &copy_prompt, "chat_generate_draft"),
    );

    let copies_val = match copies_result {
        Ok(val) => val,
        Err(e) => {
            emit_progress(
                &app,
                RecipeProgressEvent {
                    command: "chat_generate_draft".to_string(),
                    phase: "copy_generation".to_string(),
                    status: "warning".to_string(),
                    elapsed_sec: 0,
                    message: format!("LLM copy generation failed, using defaults: {}", e),
                    result: None,
                },
            );
            default_copies(&message, &message, url_str)
        }
    };

    // Build and save draft
    let title: String = if message.chars().count() > 100 {
        let mut t: String = message.chars().take(97).collect();
        t.push_str("...");
        t
    } else {
        message.clone()
    };

    let event = DraftEvent {
        title,
        date: String::new(),
        time: String::new(),
        location: String::new(),
        description: message,
        url: url.unwrap_or_default(),
    };
    let copies = copies_from_json(&copies_val);
    let platform_config = DraftPlatformConfig {
        discord_channel_id: discord,
        facebook_page_id: facebook,
        skip_platforms: skip,
    };

    let draft_obj = build_draft(
        "social_post",
        &event,
        &copies,
        &result_image_url,
        &platform_config,
    );
    let filepath = save_draft(&client.config.drafts_dir, &draft_obj)?;

    Ok(json!({
        "draft_filepath": filepath.display().to_string(),
        "copies": copies_val,
        "image_url": result_image_url,
        "draft": serde_json::to_value(&draft_obj).map_err(|e| format!("Serialization error: {}", e))?,
    }))
}

/// Check or establish connections for social media toolkits.
/// Returns per-toolkit status with redirect URLs for any needing auth.
#[tauri::command]
pub async fn manage_connections(
    client: tauri::State<'_, ComposioClient>,
    toolkits: Option<Vec<String>>,
) -> Result<Value, String> {
    let default_toolkits = vec![
        "twitter".to_string(),
        "linkedin".to_string(),
        "instagram".to_string(),
        "facebook".to_string(),
        "discordbot".to_string(),
    ];
    let toolkits = toolkits.unwrap_or(default_toolkits);
    let toolkit_refs: Vec<&str> = toolkits.iter().map(|s| s.as_str()).collect();

    client.check_connections(&toolkit_refs).await
}

/// Initiate OAuth connection for a toolkit via v3 MCP endpoint.
/// Returns the redirect URL for the user to complete in their browser.
#[tauri::command]
pub async fn initiate_connection(
    client: tauri::State<'_, ComposioClient>,
    toolkit: String,
) -> Result<Value, String> {
    let url = client.initiate_connection(&toolkit).await?;
    if url == "already_connected" {
        Ok(json!({"status": "active", "toolkit": toolkit}))
    } else {
        Ok(json!({"status": "auth_required", "toolkit": toolkit, "redirect_url": url}))
    }
}
