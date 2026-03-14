//! Tauri IPC commands for draft management
//!
//! Mirrors the draft CLI commands from `scripts/recipe_client.py`

use crate::composio::ComposioClient;
use crate::config::recipe_ids;
use crate::draft::{
    self, build_draft, load_draft, save_draft, set_draft_status, set_publish_results,
    validate_draft_for_publish, validate_draft_path, DraftCopies, DraftEvent, DraftPlatformConfig,
};
use serde_json::{json, Value};
use tauri::AppHandle;

/// Generate social media drafts without posting.
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
    let ids = recipe_ids();
    let recipe_id = ids["social_promotion"];

    let discord = discord_channel_id.unwrap_or_else(|| client.config.discord_channel_id.clone());
    let facebook = facebook_page_id.unwrap_or_else(|| client.config.facebook_page_id.clone());
    let skip = skip_platforms.unwrap_or_default();

    let input_data = json!({
        "event_title": title,
        "event_date": date,
        "event_time": time,
        "event_location": location,
        "event_description": description,
        "event_url": event_url,
        "discord_channel_id": discord,
        "facebook_page_id": facebook,
        "skip_platforms": skip,
        "mode": "generate_only",
    });

    let result = client
        .execute_recipe(
            recipe_id,
            &input_data,
            &app,
            "generate_drafts",
            "social_promotion",
        )
        .await?;

    // Extract copies from recipe result
    let copies_val = result.get("copies").cloned().unwrap_or(json!({}));
    let image_url = result
        .get("image_url")
        .and_then(|v| v.as_str())
        .unwrap_or("");

    // Check we actually got copies
    if copies_val.as_object().map(|m| m.is_empty()).unwrap_or(true) {
        return Ok(json!({
            "warning": "No copies returned from recipe",
            "recipe_result": result,
        }));
    }

    let event = DraftEvent {
        title,
        date,
        time,
        location,
        description,
        url: event_url,
    };
    let copies = DraftCopies {
        twitter: copies_val
            .get("twitter")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string(),
        linkedin: copies_val
            .get("linkedin")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string(),
        instagram: copies_val
            .get("instagram")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string(),
        facebook: copies_val
            .get("facebook")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string(),
        discord: copies_val
            .get("discord")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string(),
    };
    let platform_config = DraftPlatformConfig {
        discord_channel_id: discord,
        facebook_page_id: facebook,
        skip_platforms: skip,
    };

    let draft = build_draft("event_promotion", &event, &copies, image_url, &platform_config);
    let filepath = save_draft(&client.config.drafts_dir, &draft)?;

    Ok(json!({
        "draft_filepath": filepath.display().to_string(),
        "recipe_result": result,
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

/// Publish an approved draft.
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

    let ids = recipe_ids();

    let copies_json = serde_json::to_string(&draft.copies)
        .map_err(|e| format!("Failed to serialize copies: {}", e))?;

    let (recipe_id, input_data, recipe_label) = if draft.draft_type == "social_post" {
        let id = ids["social_post"];
        let data = json!({
            "topic": draft.event.title,
            "content": draft.event.description,
            "url": draft.event.url,
            "discord_channel_id": draft.platform_config.discord_channel_id,
            "facebook_page_id": draft.platform_config.facebook_page_id,
            "skip_platforms": draft.platform_config.skip_platforms,
            "image_url": draft.image_url,
            "mode": "publish_only",
            "pre_generated_copies": copies_json,
        });
        (id, data, "social_post")
    } else {
        let id = ids["social_promotion"];
        let data = json!({
            "event_title": draft.event.title,
            "event_date": draft.event.date,
            "event_time": draft.event.time,
            "event_location": draft.event.location,
            "event_description": draft.event.description,
            "event_url": draft.event.url,
            "discord_channel_id": draft.platform_config.discord_channel_id,
            "facebook_page_id": draft.platform_config.facebook_page_id,
            "skip_platforms": draft.platform_config.skip_platforms,
            "image_url": draft.image_url,
            "mode": "publish_only",
            "pre_generated_copies": copies_json,
        });
        (id, data, "social_promotion")
    };

    let result = client
        .execute_recipe(
            recipe_id,
            &input_data,
            &app,
            "publish_draft",
            recipe_label,
        )
        .await;

    let (new_status, result_val) = match result {
        Ok(val) => ("published", val),
        Err(e) => ("failed", json!({"error": e})),
    };

    let draft = set_publish_results(draft, result_val.clone());
    let draft = set_draft_status(draft, new_status);
    save_draft(&client.config.drafts_dir, &draft)?;

    Ok(json!({
        "status": new_status,
        "result": result_val,
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

    let ids = recipe_ids();
    let recipe_id = ids["social_post"];

    let discord = discord_channel_id.unwrap_or_else(|| client.config.discord_channel_id.clone());
    let facebook = facebook_page_id.unwrap_or_else(|| client.config.facebook_page_id.clone());
    let skip = skip_platforms.unwrap_or_default();

    let input_data = json!({
        "topic": message,
        "content": message,
        "url": url.as_deref().unwrap_or(""),
        "tone": tone.as_deref().unwrap_or(""),
        "image_url": image_url.as_deref().unwrap_or(""),
        "image_prompt": image_prompt.as_deref().unwrap_or(""),
        "cta": cta.as_deref().unwrap_or(""),
        "hashtags": hashtags.as_deref().unwrap_or(""),
        "discord_channel_id": discord,
        "facebook_page_id": facebook,
        "skip_platforms": skip,
        "mode": "generate_only",
    });

    let result = client
        .execute_recipe(
            recipe_id,
            &input_data,
            &app,
            "chat_generate_draft",
            "social_post",
        )
        .await?;

    let copies_val = result.get("copies").cloned().unwrap_or(json!({}));
    let result_image_url = result
        .get("image_url")
        .and_then(|v| v.as_str())
        .unwrap_or("");

    if copies_val.as_object().map(|m| m.is_empty()).unwrap_or(true) {
        return Ok(json!({
            "warning": "No copies returned from recipe",
            "recipe_result": result,
        }));
    }

    // Truncate message to 100 chars for title
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
    let copies = DraftCopies {
        twitter: copies_val
            .get("twitter")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string(),
        linkedin: copies_val
            .get("linkedin")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string(),
        instagram: copies_val
            .get("instagram")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string(),
        facebook: copies_val
            .get("facebook")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string(),
        discord: copies_val
            .get("discord")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string(),
    };
    let platform_config = DraftPlatformConfig {
        discord_channel_id: discord,
        facebook_page_id: facebook,
        skip_platforms: skip,
    };

    let draft = build_draft("social_post", &event, &copies, result_image_url, &platform_config);
    let filepath = save_draft(&client.config.drafts_dir, &draft)?;

    Ok(json!({
        "draft_filepath": filepath.display().to_string(),
        "copies": copies_val,
        "image_url": result_image_url,
        "draft": serde_json::to_value(&draft).map_err(|e| format!("Serialization error: {}", e))?,
    }))
}
