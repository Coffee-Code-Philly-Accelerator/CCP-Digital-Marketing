//! Tauri IPC commands for recipe execution
//!
//! Mirrors the wrapper functions from `scripts/recipe_client.py`

use crate::composio::ComposioClient;
use crate::config::{recipe_ids, EVENT_PLATFORMS};
use crate::progress::{emit_progress, RecipeProgressEvent};
use serde_json::{json, Value};
use tauri::AppHandle;

/// Create an event on Luma, Meetup, and Partiful (sequentially, per-platform).
#[tauri::command]
pub async fn create_event(
    client: tauri::State<'_, ComposioClient>,
    app: AppHandle,
    title: String,
    date: String,
    time: String,
    location: String,
    description: String,
    meetup_url: Option<String>,
    skip_platforms: Option<String>,
    provider: Option<String>,
) -> Result<Value, String> {
    let ids = recipe_ids();
    let skip_set: Vec<String> = skip_platforms
        .unwrap_or_default()
        .split(',')
        .map(|s| s.trim().to_lowercase())
        .filter(|s| !s.is_empty())
        .collect();
    let provider = provider.unwrap_or_else(|| client.config.browser_provider.clone());

    let mut results = json!({});

    for platform in EVENT_PLATFORMS {
        if skip_set.contains(&platform.to_string()) {
            emit_progress(
                &app,
                RecipeProgressEvent {
                    command: "create_event".to_string(),
                    phase: platform.to_string(),
                    status: "skipped".to_string(),
                    elapsed_sec: 0,
                    message: format!("Skipping {} (user requested)", platform),
                    result: None,
                },
            );
            results[platform] = json!({"status": "skipped"});
            continue;
        }

        let recipe_key = format!("{}_create", platform);
        let recipe_id = ids
            .get(recipe_key.as_str())
            .ok_or_else(|| format!("Unknown recipe key: {}", recipe_key))?;

        let mut input_data = json!({
            "event_title": title,
            "event_date": date,
            "event_time": time,
            "event_location": location,
            "event_description": description,
            "CCP_BROWSER_PROVIDER": provider,
        });

        if platform == "meetup" {
            let meetup = meetup_url
                .as_deref()
                .filter(|s| !s.is_empty())
                .unwrap_or(&client.config.meetup_group_url);
            input_data["meetup_group_url"] = json!(meetup);
        }

        let result = client
            .execute_recipe(recipe_id, &input_data, &app, "create_event", platform)
            .await;

        match result {
            Ok(val) => results[platform] = val,
            Err(e) => results[platform] = json!({"status": "FAILED", "error": e}),
        }
    }

    Ok(results)
}

/// Promote an event on social media platforms.
#[tauri::command]
pub async fn promote_event(
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
    image_url: Option<String>,
) -> Result<Value, String> {
    let ids = recipe_ids();
    let recipe_id = ids["social_promotion"];

    let input_data = json!({
        "event_title": title,
        "event_date": date,
        "event_time": time,
        "event_location": location,
        "event_description": description,
        "event_url": event_url,
        "discord_channel_id": discord_channel_id.unwrap_or_else(|| client.config.discord_channel_id.clone()),
        "facebook_page_id": facebook_page_id.unwrap_or_else(|| client.config.facebook_page_id.clone()),
        "skip_platforms": skip_platforms.unwrap_or_default(),
        "image_url": image_url.unwrap_or_default(),
    });

    client
        .execute_recipe(recipe_id, &input_data, &app, "promote_event", "social_promotion")
        .await
}

/// Post generic content to social media platforms.
#[tauri::command]
pub async fn social_post(
    client: tauri::State<'_, ComposioClient>,
    app: AppHandle,
    topic: String,
    content: String,
    url: Option<String>,
    image_url: Option<String>,
    image_prompt: Option<String>,
    tone: Option<String>,
    cta: Option<String>,
    hashtags: Option<String>,
    discord_channel_id: Option<String>,
    facebook_page_id: Option<String>,
    skip_platforms: Option<String>,
) -> Result<Value, String> {
    let ids = recipe_ids();
    let recipe_id = ids["social_post"];

    let input_data = json!({
        "topic": topic,
        "content": content,
        "url": url.unwrap_or_default(),
        "image_url": image_url.unwrap_or_default(),
        "image_prompt": image_prompt.unwrap_or_default(),
        "tone": tone.unwrap_or_default(),
        "cta": cta.unwrap_or_default(),
        "hashtags": hashtags.unwrap_or_default(),
        "discord_channel_id": discord_channel_id.unwrap_or_else(|| client.config.discord_channel_id.clone()),
        "facebook_page_id": facebook_page_id.unwrap_or_else(|| client.config.facebook_page_id.clone()),
        "skip_platforms": skip_platforms.unwrap_or_default(),
    });

    client
        .execute_recipe(recipe_id, &input_data, &app, "social_post", "social_post")
        .await
}

/// Full workflow: create events on all platforms, then promote on social media.
#[tauri::command]
pub async fn full_workflow(
    client: tauri::State<'_, ComposioClient>,
    app: AppHandle,
    title: String,
    date: String,
    time: String,
    location: String,
    description: String,
    meetup_url: Option<String>,
    discord_channel_id: Option<String>,
    facebook_page_id: Option<String>,
    skip_platforms: Option<String>,
    provider: Option<String>,
) -> Result<Value, String> {
    // Phase 1: Create events
    let create_results = create_event(
        client.clone(),
        app.clone(),
        title.clone(),
        date.clone(),
        time.clone(),
        location.clone(),
        description.clone(),
        meetup_url,
        skip_platforms.clone(),
        provider,
    )
    .await?;

    // Extract primary event URL (prefer luma > meetup > partiful)
    let mut event_url = String::new();
    for platform in EVENT_PLATFORMS {
        if let Some(platform_result) = create_results.get(platform) {
            let url = platform_result
                .get("event_url")
                .or_else(|| platform_result.get(&format!("{}_url", platform)))
                .or_else(|| platform_result.get("url"))
                .and_then(|v| v.as_str())
                .unwrap_or("");
            if !url.is_empty() {
                event_url = url.to_string();
                break;
            }
        }
    }

    // Phase 2: Social promotion
    let promote_result = promote_event(
        client,
        app,
        title,
        date,
        time,
        location,
        description,
        event_url.clone(),
        discord_channel_id,
        facebook_page_id,
        skip_platforms,
        None,
    )
    .await?;

    Ok(json!({
        "event_creation": create_results,
        "social_promotion": promote_result,
        "primary_event_url": event_url,
    }))
}

/// Get recipe details for one or all recipes.
#[tauri::command]
pub async fn get_recipe_info(
    client: tauri::State<'_, ComposioClient>,
    recipe_name: Option<String>,
) -> Result<Value, String> {
    let ids = recipe_ids();

    let keys_to_fetch: Vec<&&str> = match recipe_name.as_deref() {
        Some("luma") => vec![&"luma_create"],
        Some("meetup") => vec![&"meetup_create"],
        Some("partiful") => vec![&"partiful_create"],
        Some("promote") => vec![&"social_promotion"],
        Some("social-post") | Some("social_post") => vec![&"social_post"],
        _ => ids.keys().collect(),
    };

    let mut results = json!({});
    for key in keys_to_fetch {
        let recipe_id = ids[*key];
        let detail = client.get_recipe_details(recipe_id).await;
        match detail {
            Ok(val) => results[*key] = val,
            Err(e) => results[*key] = json!({"error": e}),
        }
    }

    Ok(results)
}
