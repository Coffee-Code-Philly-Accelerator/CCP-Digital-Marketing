//! Tauri IPC commands for recipe execution
//!
//! Event creation commands require Rube MCP browser automation and are not
//! available via the v3 tool router API. Use the CLI or Claude Code skills.
//!
//! Social promotion and posting are available through the draft workflow
//! (generate draft -> approve -> publish).

use crate::composio::ComposioClient;
use crate::config::recipe_ids;
use serde_json::{json, Value};
use tauri::AppHandle;

/// Create an event on Luma, Meetup, and Partiful.
/// Requires Rube MCP browser automation — not available via v3 API.
#[tauri::command]
pub async fn create_event(
    _client: tauri::State<'_, ComposioClient>,
    _app: AppHandle,
    _title: String,
    _date: String,
    _time: String,
    _location: String,
    _description: String,
    _meetup_url: Option<String>,
    _skip_platforms: Option<String>,
    _provider: Option<String>,
) -> Result<Value, String> {
    Err(
        "Event creation requires Rube MCP browser automation, which is not available \
         through the GUI. Use the CLI (python scripts/recipe_client.py create-event) \
         or Claude Code skills (/luma-create, /meetup-create, /partiful-create)."
            .to_string(),
    )
}

/// Promote an event on social media platforms.
/// Use the draft workflow instead: generate_drafts -> approve -> publish.
#[tauri::command]
pub async fn promote_event(
    _client: tauri::State<'_, ComposioClient>,
    _app: AppHandle,
    _title: String,
    _date: String,
    _time: String,
    _location: String,
    _description: String,
    _event_url: String,
    _discord_channel_id: Option<String>,
    _facebook_page_id: Option<String>,
    _skip_platforms: Option<String>,
    _image_url: Option<String>,
) -> Result<Value, String> {
    Err(
        "Direct social promotion has been replaced by the draft workflow. \
         Use the Chat tab to generate a draft, then approve and publish it \
         from the Drafts tab."
            .to_string(),
    )
}

/// Post generic content to social media platforms.
/// Use the draft workflow instead: chat_generate_draft -> approve -> publish.
#[tauri::command]
pub async fn social_post(
    _client: tauri::State<'_, ComposioClient>,
    _app: AppHandle,
    _topic: String,
    _content: String,
    _url: Option<String>,
    _image_url: Option<String>,
    _image_prompt: Option<String>,
    _tone: Option<String>,
    _cta: Option<String>,
    _hashtags: Option<String>,
    _discord_channel_id: Option<String>,
    _facebook_page_id: Option<String>,
    _skip_platforms: Option<String>,
) -> Result<Value, String> {
    Err(
        "Direct social posting has been replaced by the draft workflow. \
         Use the Chat tab to generate a draft, then approve and publish it \
         from the Drafts tab."
            .to_string(),
    )
}

/// Full workflow: create events + promote on social media.
/// Requires Rube MCP browser automation — not available via v3 API.
#[tauri::command]
pub async fn full_workflow(
    _client: tauri::State<'_, ComposioClient>,
    _app: AppHandle,
    _title: String,
    _date: String,
    _time: String,
    _location: String,
    _description: String,
    _meetup_url: Option<String>,
    _discord_channel_id: Option<String>,
    _facebook_page_id: Option<String>,
    _skip_platforms: Option<String>,
    _provider: Option<String>,
) -> Result<Value, String> {
    Err(
        "Full workflow requires Rube MCP browser automation, which is not available \
         through the GUI. Use the CLI (python scripts/recipe_client.py full-workflow) \
         or Claude Code skills (/full-workflow)."
            .to_string(),
    )
}

/// Get recipe details for one or all recipes.
/// Returns static recipe metadata since v1 API is no longer available.
#[tauri::command]
pub async fn get_recipe_info(
    _client: tauri::State<'_, ComposioClient>,
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
        let platform_list: Vec<&str> = match *key {
            "luma_create" => vec!["luma"],
            "meetup_create" => vec!["meetup"],
            "partiful_create" => vec!["partiful"],
            "social_promotion" => vec!["twitter", "linkedin", "instagram", "facebook", "discord"],
            "social_post" => vec!["twitter", "linkedin", "instagram", "facebook", "discord"],
            _ => vec![],
        };
        results[*key] = json!({
            "recipe_id": recipe_id,
            "platforms": platform_list,
            "note": "Recipe details are managed via Rube MCP. Use Claude Code for full recipe info.",
        });
    }

    Ok(results)
}
