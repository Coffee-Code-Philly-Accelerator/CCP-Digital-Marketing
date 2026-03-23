//! Configuration and constants for CCP Digital Marketing GUI

use std::collections::HashMap;
use std::env;

#[allow(dead_code)]
pub struct AppConfig {
    pub api_base: String,
    pub api_key: String,
    pub composio_user_id: String,
    pub drafts_dir: String,
    pub discord_channel_id: String,
    pub facebook_page_id: String,
    pub linkedin_account_id: String,
    pub instagram_account_id: String,
}

impl AppConfig {
    pub fn from_env() -> Self {
        let project_root = env::var("CCP_PROJECT_ROOT").unwrap_or_else(|_| {
            // Exe is at gui/src-tauri/target/debug/ — 4 levels below project root
            let exe_dir = env::current_exe()
                .ok()
                .and_then(|p| p.parent().map(|p| p.to_path_buf()));
            exe_dir
                .map(|d| {
                    d.join("../../../..")
                        .canonicalize()
                        .unwrap_or_else(|_| d.to_path_buf())
                        .display()
                        .to_string()
                })
                .unwrap_or_else(|| ".".to_string())
        });

        Self {
            api_base: env::var("CCP_COMPOSIO_API_BASE")
                .unwrap_or_else(|_| "https://backend.composio.dev".to_string()),
            api_key: env::var("COMPOSIO_API_KEY").unwrap_or_default(),
            composio_user_id: env::var("CCP_COMPOSIO_USER_ID")
                .unwrap_or_else(|_| "default".to_string()),
            drafts_dir: env::var("CCP_DRAFTS_DIR").unwrap_or_else(|_| {
                std::path::Path::new(&project_root)
                    .join("drafts")
                    .display()
                    .to_string()
            }),
            discord_channel_id: env::var("CCP_DISCORD_CHANNEL_ID").unwrap_or_default(),
            facebook_page_id: env::var("CCP_FACEBOOK_PAGE_ID").unwrap_or_default(),
            linkedin_account_id: env::var("CCP_LINKEDIN_ACCOUNT_ID").unwrap_or_default(),
            instagram_account_id: env::var("CCP_INSTAGRAM_ACCOUNT_ID").unwrap_or_default(),
        }
    }
}

pub fn recipe_ids() -> HashMap<&'static str, &'static str> {
    HashMap::from([
        ("luma_create", "rcp_mXyFyALaEsQF"),
        ("meetup_create", "rcp_kHJoI1WmR3AR"),
        ("partiful_create", "rcp_bN7jRF5P_Kf0"),
        ("social_promotion", "rcp_X65IirgPhwh3"),
        ("social_post", "rcp_3LheyoNQpiFK"),
    ])
}
