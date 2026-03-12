"""
Draft storage module for social promotion drafts.

Provides pure functions for draft CRUD and I/O boundary functions
for file persistence. Drafts are stored as JSON files in the drafts/ directory.

Status lifecycle: draft -> approved -> published (or failed)
"""

import json
import os
import re
from datetime import datetime, timezone

# =============================================================================
# Pure Functions
# =============================================================================


def slugify(title: str) -> str:
    """Convert a title to a filename-safe slug."""
    text = title.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = text.strip("-")
    return text[:80] or "untitled"


def build_draft_filename(title: str, timestamp: str) -> str:
    """Build a draft filename from title and ISO timestamp."""
    slug = slugify(title)
    # Use compact timestamp for filename: 20260310T153022Z
    has_z = timestamp.endswith("Z")
    ts_clean = re.sub(r"[:\-]", "", timestamp)
    ts_clean = ts_clean.split(".")[0]  # drop microseconds
    if has_z and not ts_clean.endswith("Z"):
        ts_clean += "Z"
    return f"{slug}_{ts_clean}.json"


def build_draft(event: dict, copies: dict, image_url: str, platform_config: dict) -> dict:
    """Build a draft dict with all required fields."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "version": 1,
        "status": "draft",
        "created_at": now,
        "updated_at": now,
        "event": {
            "title": event.get("title", ""),
            "date": event.get("date", ""),
            "time": event.get("time", ""),
            "location": event.get("location", ""),
            "description": event.get("description", ""),
            "url": event.get("url", ""),
        },
        "image_url": image_url or "",
        "copies": {
            "twitter": copies.get("twitter", ""),
            "linkedin": copies.get("linkedin", ""),
            "instagram": copies.get("instagram", ""),
            "facebook": copies.get("facebook", ""),
            "discord": copies.get("discord", ""),
        },
        "platform_config": {
            "discord_channel_id": platform_config.get("discord_channel_id", ""),
            "facebook_page_id": platform_config.get("facebook_page_id", ""),
            "skip_platforms": platform_config.get("skip_platforms", ""),
        },
        "publish_results": None,
    }


def set_draft_status(draft: dict, new_status: str) -> dict:
    """Return a new draft dict with updated status and timestamp."""
    updated = dict(draft)
    updated["status"] = new_status
    updated["updated_at"] = datetime.now(timezone.utc).isoformat()
    return updated


def set_publish_results(draft: dict, results: dict) -> dict:
    """Return a new draft dict with publish results attached."""
    updated = dict(draft)
    updated["publish_results"] = results
    updated["updated_at"] = datetime.now(timezone.utc).isoformat()
    return updated


def validate_draft_for_publish(draft: dict) -> str | None:
    """Validate a draft is ready to publish. Returns error message or None."""
    if not draft:
        return "Draft is empty"
    if draft.get("status") != "approved":
        return f"Draft status is '{draft.get('status', 'unknown')}', must be 'approved'"
    if not draft.get("copies"):
        return "Draft has no copies"
    required_keys = ["twitter", "linkedin", "instagram", "facebook", "discord"]
    missing = [k for k in required_keys if not draft.get("copies", {}).get(k)]
    if missing:
        return f"Draft missing copies for: {', '.join(missing)}"
    return None


# =============================================================================
# I/O Boundary Functions
# =============================================================================


def save_draft(drafts_dir: str, draft: dict) -> str:
    """Save a draft to a JSON file. Returns the filepath."""
    os.makedirs(drafts_dir, exist_ok=True)
    filename = build_draft_filename(
        draft.get("event", {}).get("title", "untitled"),
        draft.get("created_at", datetime.now(timezone.utc).isoformat()),
    )
    filepath = os.path.join(drafts_dir, filename)
    with open(filepath, "w") as f:
        json.dump(draft, f, indent=2)
    return filepath


def load_draft(filepath: str) -> dict:
    """Load a draft from a JSON file."""
    with open(filepath) as f:
        return json.load(f)


def list_drafts(drafts_dir: str) -> list[dict]:
    """List all draft files with summary info. Returns list of dicts."""
    if not os.path.isdir(drafts_dir):
        return []
    results = []
    for filename in sorted(os.listdir(drafts_dir)):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(drafts_dir, filename)
        with open(filepath) as f:
            draft = json.load(f)
        results.append(
            {
                "filename": filename,
                "filepath": filepath,
                "status": draft.get("status", "unknown"),
                "title": draft.get("event", {}).get("title", ""),
                "date": draft.get("event", {}).get("date", ""),
                "created_at": draft.get("created_at", ""),
            }
        )
    return results
