//! Tauri IPC commands for draft management
//!
//! Draft generation uses native Composio v3 tool calls:
//! - GEMINI_GENERATE_IMAGE for promotional images
//! - COMPOSIO_SEARCH_GROQ_CHAT (Llama 3.3 70B) for platform-specific copy
//!
//! Draft publishing calls individual social platform APIs via v3 session.

use crate::composio::{extract_data, extract_json_from_text, extract_llm_content, ComposioClient};
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
        Ok(val) => {
            let data = extract_data(&val);
            // v3: data.image.s3url; recipe/v1: data.publicUrl
            data.get("image")
                .and_then(|img| img.get("s3url").or_else(|| img.get("publicUrl")))
                .or_else(|| data.get("publicUrl"))
                .or_else(|| data.get("s3url"))
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string()
        }
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

    let content = extract_llm_content(&result)
        .ok_or_else(|| "LLM returned no content".to_string())?;

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

async fn post_to_linkedin(
    client: &ComposioClient,
    app: &AppHandle,
    draft: &Draft,
) -> String {
    let profile_result = client
        .execute_tool(
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

    let li_id = profile_data
        .get("id")
        .and_then(|v| v.as_str())
        .unwrap_or("");
    if li_id.is_empty() {
        return "failed: could not determine user ID".to_string();
    }

    let author = if li_id.starts_with("urn:li:") {
        li_id.to_string()
    } else {
        format!("urn:li:person:{}", li_id)
    };

    let mut text = draft.copies.linkedin.clone();
    if !draft.event.url.is_empty() {
        text = format!("{}\n\n{}", text, draft.event.url);
    }

    let post_result = client
        .execute_tool(
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

async fn post_to_instagram(
    client: &ComposioClient,
    app: &AppHandle,
    draft: &Draft,
) -> String {
    if draft.image_url.is_empty() {
        return "skipped: no image available".to_string();
    }

    let user_result = client
        .execute_tool(
            "INSTAGRAM_GET_USER_INFO",
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

    let ig_user_id = user_data
        .get("id")
        .and_then(|v| match v {
            Value::String(s) => Some(s.clone()),
            Value::Number(n) => Some(n.to_string()),
            _ => None,
        })
        .unwrap_or_default();
    if ig_user_id.is_empty() {
        return "failed: could not determine user ID".to_string();
    }

    let container_result = client
        .execute_tool(
            "INSTAGRAM_CREATE_MEDIA_CONTAINER",
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

    let creation_id = container_data
        .get("id")
        .and_then(|v| match v {
            Value::String(s) => Some(s.clone()),
            Value::Number(n) => Some(n.to_string()),
            _ => None,
        })
        .unwrap_or_default();
    if creation_id.is_empty() {
        return "failed: no container ID returned".to_string();
    }

    // Use the auto-waiting publish tool
    let publish_result = client
        .execute_tool(
            "INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH",
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

    let mut message = draft.copies.facebook.clone();
    if !draft.event.url.is_empty() {
        message = format!("{}\n\n{}", message, draft.event.url);
    }

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

    let mut content = draft.copies.discord.clone();
    if !draft.event.url.is_empty() {
        content = format!("{}\n\n{}", content, draft.event.url);
    }

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

    // Step 1: Generate promotional image
    let image_url = generate_image(&client, &app, &title, "generate_drafts").await;

    // Step 2: Generate platform-specific copies
    let prompt = format!(
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

    let copies_val = match generate_copies(&client, &app, &prompt, "generate_drafts").await {
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

    // Step 3: Build and save draft
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

    let draft_obj = build_draft("event_promotion", &event, &copies, &image_url, &platform_config);
    let filepath = save_draft(&client.config.drafts_dir, &draft_obj)?;

    Ok(json!({
        "draft_filepath": filepath.display().to_string(),
        "copies": copies_val,
        "image_url": image_url,
    }))
}

/// List all drafts.
#[tauri::command]
pub async fn list_drafts_cmd(
    client: tauri::State<'_, ComposioClient>,
) -> Result<Value, String> {
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

    let skip_platforms: Vec<String> = draft
        .platform_config
        .skip_platforms
        .split(',')
        .map(|s| s.trim().to_lowercase())
        .filter(|s| !s.is_empty())
        .collect();

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

    let mut results = json!({
        "twitter_posted": "skipped: connection not available",
        "linkedin_posted": "skipped",
        "instagram_posted": "skipped",
        "facebook_posted": "skipped",
        "discord_posted": "skipped",
        "image_url": draft.image_url,
    });

    // Post to each platform sequentially
    if !skip_platforms.contains(&"linkedin".to_string()) {
        results["linkedin_posted"] = json!(post_to_linkedin(&client, &app, &draft).await);
    }

    if !skip_platforms.contains(&"instagram".to_string()) {
        results["instagram_posted"] = json!(post_to_instagram(&client, &app, &draft).await);
    }

    if !skip_platforms.contains(&"facebook".to_string()) {
        results["facebook_posted"] = json!(post_to_facebook(&client, &app, &draft, facebook_id).await);
    }

    if !skip_platforms.contains(&"discord".to_string()) {
        results["discord_posted"] = json!(post_to_discord(&client, &app, &draft, discord_id).await);
    }

    // Count successes
    let success_count = ["twitter_posted", "linkedin_posted", "instagram_posted", "facebook_posted", "discord_posted"]
        .iter()
        .filter(|k| results[**k].as_str() == Some("success"))
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

    // Step 1: Generate image (use provided URL/prompt, or generate from topic)
    let result_image_url = if let Some(ref provided) = image_url {
        if !provided.is_empty() {
            provided.clone()
        } else {
            generate_image(&client, &app, &message, "chat_generate_draft").await
        }
    } else if let Some(ref prompt) = image_prompt {
        if !prompt.is_empty() {
            // Use custom image prompt
            let img_result = client
                .execute_tool(
                    "GEMINI_GENERATE_IMAGE",
                    &json!({
                        "prompt": prompt,
                        "model": "gemini-2.5-flash-image"
                    }),
                    &app,
                    "chat_generate_draft",
                    "image_generation",
                )
                .await;
            match img_result {
                Ok(val) => {
                    let data = extract_data(&val);
                    data.get("publicUrl")
                        .and_then(|v| v.as_str())
                        .unwrap_or("")
                        .to_string()
                }
                Err(_) => String::new(),
            }
        } else {
            generate_image(&client, &app, &message, "chat_generate_draft").await
        }
    } else {
        generate_image(&client, &app, &message, "chat_generate_draft").await
    };

    // Step 2: Generate platform-specific copies
    let mut prompt = format!(
        "Generate 5 platform-specific social media posts about this topic:\n\n\
         Topic: {}\nContent: {}\n",
        message, message
    );
    if !url_str.is_empty() {
        prompt.push_str(&format!("Link: {}\n", url_str));
    }
    if let Some(ref c) = cta {
        if !c.is_empty() {
            prompt.push_str(&format!("Call to action: {}\n", c));
        }
    }
    if let Some(ref h) = hashtags {
        if !h.is_empty() {
            prompt.push_str(&format!("Hashtags to include: {}\n", h));
        }
    }
    prompt.push_str(&format!(
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

    let copies_val =
        match generate_copies(&client, &app, &prompt, "chat_generate_draft").await {
            Ok(val) => val,
            Err(e) => {
                emit_progress(
                    &app,
                    RecipeProgressEvent {
                        command: "chat_generate_draft".to_string(),
                        phase: "copy_generation".to_string(),
                        status: "warning".to_string(),
                        elapsed_sec: 0,
                        message: format!(
                            "LLM copy generation failed, using defaults: {}",
                            e
                        ),
                        result: None,
                    },
                );
                default_copies(&message, &message, url_str)
            }
        };

    // Step 3: Build and save draft
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
