"""
Unit tests for the draft_store module.
"""

import os

from scripts.draft_store import (
    build_draft,
    build_draft_filename,
    list_drafts,
    load_draft,
    save_draft,
    set_draft_status,
    set_publish_results,
    slugify,
    validate_draft_for_publish,
)


class TestSlugify:
    def test_basic_title(self):
        assert slugify("AI Workshop") == "ai-workshop"

    def test_special_characters(self):
        assert slugify("Hello, World! #2026") == "hello-world-2026"

    def test_extra_whitespace(self):
        assert slugify("  multiple   spaces  ") == "multiple-spaces"

    def test_empty_string(self):
        assert slugify("") == "untitled"

    def test_truncates_long_title(self):
        long_title = "a" * 100
        assert len(slugify(long_title)) <= 80


class TestBuildDraftFilename:
    def test_basic(self):
        filename = build_draft_filename("AI Workshop", "2026-03-10T15:30:22Z")
        assert filename == "ai-workshop_20260310T153022Z.json"

    def test_with_microseconds(self):
        filename = build_draft_filename("Test", "2026-03-10T15:30:22.123456Z")
        assert filename == "test_20260310T153022Z.json"


class TestBuildDraft:
    def test_correct_schema(self):
        event = {
            "title": "AI Workshop",
            "date": "March 20, 2026",
            "time": "6:00 PM EST",
            "location": "Philly",
            "description": "Test event",
            "url": "https://example.com",
        }
        copies = {
            "twitter": "tweet",
            "linkedin": "li post",
            "instagram": "ig caption",
            "facebook": "fb post",
            "discord": "dc msg",
        }
        platform_config = {
            "discord_channel_id": "ch_123",
            "facebook_page_id": "pg_456",
            "skip_platforms": "",
        }

        draft = build_draft("event_promotion", event, copies, "https://img.example.com/photo.jpg", platform_config)

        assert draft["version"] == 1
        assert draft["status"] == "draft"
        assert draft["draft_type"] == "event_promotion"
        assert draft["event"]["title"] == "AI Workshop"
        assert draft["copies"]["twitter"] == "tweet"
        assert draft["image_url"] == "https://img.example.com/photo.jpg"
        assert draft["platform_config"]["discord_channel_id"] == "ch_123"
        assert draft["publish_results"] is None
        assert "created_at" in draft
        assert "updated_at" in draft

    def test_missing_optional_fields(self):
        draft = build_draft("social_post", {}, {}, "", {})
        assert draft["event"]["title"] == ""
        assert draft["copies"]["twitter"] == ""
        assert draft["image_url"] == ""


class TestSetDraftStatus:
    def test_draft_to_approved(self):
        draft = {"status": "draft", "updated_at": "old"}
        updated = set_draft_status(draft, "approved")
        assert updated["status"] == "approved"
        assert updated["updated_at"] != "old"

    def test_does_not_mutate_original(self):
        draft = {"status": "draft", "updated_at": "old"}
        set_draft_status(draft, "approved")
        assert draft["status"] == "draft"


class TestSetPublishResults:
    def test_attaches_results(self):
        draft = {"status": "approved", "updated_at": "old", "publish_results": None}
        results = {"linkedin_posted": "success"}
        updated = set_publish_results(draft, results)
        assert updated["publish_results"] == results
        assert updated["updated_at"] != "old"

    def test_does_not_mutate_original(self):
        draft = {"status": "approved", "updated_at": "old", "publish_results": None}
        set_publish_results(draft, {"linkedin_posted": "success"})
        assert draft["publish_results"] is None


class TestValidateDraftForPublish:
    def test_rejects_non_approved(self):
        draft = {
            "status": "draft",
            "copies": {"twitter": "t", "linkedin": "l", "instagram": "i", "facebook": "f", "discord": "d"},
        }
        error = validate_draft_for_publish(draft)
        assert error is not None
        assert "approved" in error

    def test_accepts_approved(self):
        draft = {
            "status": "approved",
            "copies": {"twitter": "t", "linkedin": "l", "instagram": "i", "facebook": "f", "discord": "d"},
        }
        assert validate_draft_for_publish(draft) is None

    def test_rejects_empty_draft(self):
        assert validate_draft_for_publish({}) is not None

    def test_rejects_missing_copies(self):
        draft = {"status": "approved", "copies": {"twitter": "t"}}
        error = validate_draft_for_publish(draft)
        assert error is not None
        assert "missing" in error.lower()


class TestSaveAndLoadDraft:
    def test_round_trip(self, tmp_path):
        event = {
            "title": "Test Event",
            "date": "March 20, 2026",
            "time": "6 PM",
            "location": "Philly",
            "description": "Desc",
            "url": "https://example.com",
        }
        copies = {"twitter": "t", "linkedin": "l", "instagram": "i", "facebook": "f", "discord": "d"}
        draft = build_draft("event_promotion", event, copies, "https://img.example.com/photo.jpg", {})

        filepath = save_draft(str(tmp_path), draft)
        loaded = load_draft(filepath)

        assert loaded["event"]["title"] == "Test Event"
        assert loaded["copies"]["twitter"] == "t"
        assert loaded["image_url"] == "https://img.example.com/photo.jpg"
        assert loaded["status"] == "draft"

    def test_creates_directory(self, tmp_path):
        nested_dir = str(tmp_path / "nested" / "drafts")
        draft = build_draft("event_promotion", {"title": "Test"}, {}, "", {})
        filepath = save_draft(nested_dir, draft)
        assert os.path.exists(filepath)


class TestListDrafts:
    def test_multiple_files(self, tmp_path):
        for i in range(3):
            event = {
                "title": f"Event {i}",
                "date": f"March {20 + i}, 2026",
                "time": "6 PM",
                "location": "Philly",
                "description": "Desc",
                "url": "",
            }
            copies = {"twitter": "t", "linkedin": "l", "instagram": "i", "facebook": "f", "discord": "d"}
            draft = build_draft("event_promotion", event, copies, "", {})
            save_draft(str(tmp_path), draft)

        results = list_drafts(str(tmp_path))
        assert len(results) == 3
        assert all("filename" in r for r in results)
        assert all("status" in r for r in results)
        assert all("title" in r for r in results)

    def test_empty_directory(self, tmp_path):
        assert list_drafts(str(tmp_path)) == []

    def test_nonexistent_directory(self):
        assert list_drafts("/nonexistent/path") == []

    def test_ignores_non_json_files(self, tmp_path):
        (tmp_path / ".gitkeep").write_text("")
        (tmp_path / "notes.txt").write_text("hello")
        draft = build_draft(
            "event_promotion",
            {"title": "Real Draft"},
            {"twitter": "t", "linkedin": "l", "instagram": "i", "facebook": "f", "discord": "d"},
            "",
            {},
        )
        save_draft(str(tmp_path), draft)

        results = list_drafts(str(tmp_path))
        assert len(results) == 1
