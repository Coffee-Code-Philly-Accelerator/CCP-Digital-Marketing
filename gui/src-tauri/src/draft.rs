//! Draft types and pure functions for social promotion drafts.
//!
//! Mirrors `scripts/draft_store.py` with identical JSON schema for interop.
//! Status lifecycle: draft -> approved -> published (or failed)

use chrono::Utc;
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::LazyLock;

// =============================================================================
// Types
// =============================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Draft {
    pub version: u32,
    pub status: String,
    pub created_at: String,
    pub updated_at: String,
    pub event: DraftEvent,
    pub image_url: String,
    pub copies: DraftCopies,
    pub platform_config: DraftPlatformConfig,
    pub publish_results: Option<serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DraftEvent {
    pub title: String,
    pub date: String,
    pub time: String,
    pub location: String,
    pub description: String,
    pub url: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DraftCopies {
    pub twitter: String,
    pub linkedin: String,
    pub instagram: String,
    pub facebook: String,
    pub discord: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DraftPlatformConfig {
    pub discord_channel_id: String,
    pub facebook_page_id: String,
    pub skip_platforms: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DraftSummary {
    pub filename: String,
    pub filepath: String,
    pub status: String,
    pub title: String,
    pub date: String,
    pub created_at: String,
}

// =============================================================================
// Pure Functions
// =============================================================================

static RE_NONWORD: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"[^\w\s-]").unwrap());
static RE_SEP: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"[\s_-]+").unwrap());

pub fn slugify(title: &str) -> String {
    let text = title.to_lowercase();
    let text = text.trim();
    let text = RE_NONWORD.replace_all(text, "");
    let text = RE_SEP.replace_all(&text, "-");
    let text = text.trim_matches('-');
    let text = if text.len() > 80 { &text[..80] } else { text };
    if text.is_empty() {
        "untitled".to_string()
    } else {
        text.to_string()
    }
}

pub fn build_draft_filename(title: &str, timestamp: &str) -> String {
    let slug = slugify(title);
    let has_z = timestamp.ends_with('Z');
    // Compact timestamp: remove colons and hyphens
    let ts_clean: String = timestamp.chars().filter(|c| *c != ':' && *c != '-').collect();
    // Drop microseconds (everything after '.')
    let ts_clean = ts_clean.split('.').next().unwrap_or(&ts_clean);
    let ts_clean = if has_z && !ts_clean.ends_with('Z') {
        format!("{}Z", ts_clean)
    } else {
        ts_clean.to_string()
    };
    format!("{}_{}.json", slug, ts_clean)
}

pub fn build_draft(
    event: &DraftEvent,
    copies: &DraftCopies,
    image_url: &str,
    platform_config: &DraftPlatformConfig,
) -> Draft {
    let now = Utc::now().to_rfc3339();
    Draft {
        version: 1,
        status: "draft".to_string(),
        created_at: now.clone(),
        updated_at: now,
        event: event.clone(),
        image_url: image_url.to_string(),
        copies: copies.clone(),
        platform_config: platform_config.clone(),
        publish_results: None,
    }
}

pub fn set_draft_status(mut draft: Draft, new_status: &str) -> Draft {
    draft.status = new_status.to_string();
    draft.updated_at = Utc::now().to_rfc3339();
    draft
}

pub fn set_publish_results(mut draft: Draft, results: serde_json::Value) -> Draft {
    draft.publish_results = Some(results);
    draft.updated_at = Utc::now().to_rfc3339();
    draft
}

pub fn validate_draft_for_publish(draft: &Draft) -> Option<String> {
    if draft.status != "approved" {
        return Some(format!(
            "Draft status is '{}', must be 'approved'",
            draft.status
        ));
    }
    let copies = &draft.copies;
    let mut missing = Vec::new();
    if copies.twitter.is_empty() {
        missing.push("twitter");
    }
    if copies.linkedin.is_empty() {
        missing.push("linkedin");
    }
    if copies.instagram.is_empty() {
        missing.push("instagram");
    }
    if copies.facebook.is_empty() {
        missing.push("facebook");
    }
    if copies.discord.is_empty() {
        missing.push("discord");
    }
    if !missing.is_empty() {
        return Some(format!("Draft missing copies for: {}", missing.join(", ")));
    }
    None
}

// =============================================================================
// I/O Boundary Functions
// =============================================================================

pub fn save_draft(drafts_dir: &str, draft: &Draft) -> Result<PathBuf, String> {
    fs::create_dir_all(drafts_dir).map_err(|e| format!("Failed to create drafts dir: {}", e))?;

    let filename = build_draft_filename(&draft.event.title, &draft.created_at);
    let filepath = Path::new(drafts_dir).join(&filename);

    let json =
        serde_json::to_string_pretty(draft).map_err(|e| format!("Failed to serialize: {}", e))?;
    fs::write(&filepath, json).map_err(|e| format!("Failed to write draft: {}", e))?;

    Ok(filepath)
}

pub fn load_draft(filepath: &str) -> Result<Draft, String> {
    let contents =
        fs::read_to_string(filepath).map_err(|e| format!("Failed to read draft: {}", e))?;
    serde_json::from_str(&contents).map_err(|e| format!("Failed to parse draft: {}", e))
}

pub fn list_drafts(drafts_dir: &str) -> Result<Vec<DraftSummary>, String> {
    let dir = Path::new(drafts_dir);
    if !dir.is_dir() {
        return Ok(Vec::new());
    }

    let mut entries: Vec<_> = fs::read_dir(dir)
        .map_err(|e| format!("Failed to read drafts dir: {}", e))?
        .filter_map(|entry| entry.ok())
        .filter(|entry| {
            entry
                .path()
                .extension()
                .map(|ext| ext == "json")
                .unwrap_or(false)
        })
        .collect();

    entries.sort_by_key(|e| e.file_name());

    let mut results = Vec::new();
    for entry in entries {
        let filepath = entry.path();
        let contents = fs::read_to_string(&filepath)
            .map_err(|e| format!("Failed to read {}: {}", filepath.display(), e))?;
        let draft: Draft = serde_json::from_str(&contents)
            .map_err(|e| format!("Failed to parse {}: {}", filepath.display(), e))?;

        results.push(DraftSummary {
            filename: entry.file_name().to_string_lossy().to_string(),
            filepath: filepath.display().to_string(),
            status: draft.status,
            title: draft.event.title,
            date: draft.event.date,
            created_at: draft.created_at,
        });
    }

    Ok(results)
}
