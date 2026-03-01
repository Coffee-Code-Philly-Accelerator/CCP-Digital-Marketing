"""
Tests for sanitize_input() — extracted from recipe files via AST.

Two variants exist:
- Event recipes (luma, meetup, partiful): replaces apostrophes with curly quotes
- Social recipes (social_promotion, social_post): no apostrophe replacement
"""

import pytest

from tests.conftest import RECIPES_DIR
from tests.helpers import extract_functions_from_file


@pytest.fixture
def event_sanitize():
    """sanitize_input from luma recipe (apostrophe → curly quote)."""
    funcs = extract_functions_from_file(RECIPES_DIR / "luma_create_event.py", ["sanitize_input"])
    return funcs["sanitize_input"]


@pytest.fixture
def social_sanitize():
    """sanitize_input from social_promotion recipe (no apostrophe change)."""
    funcs = extract_functions_from_file(RECIPES_DIR / "social_promotion.py", ["sanitize_input"])
    return funcs["sanitize_input"]


# ---- Shared behavior (both variants) ----


class TestSanitizeInputCommon:
    """Tests that apply to both event and social variants."""

    @pytest.fixture(params=["event", "social"])
    def sanitize(self, request, event_sanitize, social_sanitize):
        return event_sanitize if request.param == "event" else social_sanitize

    def test_empty_string(self, sanitize):
        assert sanitize("") == ""

    def test_none_input(self, sanitize):
        assert sanitize(None) == ""

    def test_normal_text(self, sanitize):
        assert sanitize("Hello world") == "Hello world"

    def test_truncation_default(self, sanitize):
        long_text = "a" * 2500
        result = sanitize(long_text)
        assert len(result) == 2000

    def test_truncation_custom_max_len(self, sanitize):
        result = sanitize("Hello world", max_len=5)
        assert result == "Hello"

    def test_backtick_replacement(self, sanitize):
        result = sanitize("code ```block``` here")
        assert "```" not in result

    def test_triple_dash_replacement(self, sanitize):
        result = sanitize("section --- divider")
        assert "---" not in result
        assert "___" in result

    def test_control_char_stripped(self, sanitize):
        result = sanitize("hello\x00world\x07test")
        assert "\x00" not in result
        assert "\x07" not in result
        assert "helloworld" in result

    def test_newline_preserved(self, sanitize):
        result = sanitize("line1\nline2")
        assert "\n" in result

    def test_tab_preserved(self, sanitize):
        result = sanitize("col1\tcol2")
        assert "\t" in result

    def test_non_string_conversion(self, sanitize):
        result = sanitize(12345)
        assert result == "12345"

    def test_zero_falsy_input(self, sanitize):
        """0 is falsy, so sanitize_input returns empty string."""
        result = sanitize(0)
        assert result == ""


# ---- Event-specific behavior (apostrophe → curly) ----


class TestSanitizeInputEvent:
    def test_apostrophe_replaced(self, event_sanitize):
        result = event_sanitize("it's a test")
        assert "'" not in result
        assert "\u2019" in result

    def test_multiple_apostrophes(self, event_sanitize):
        result = event_sanitize("it's John's party")
        assert result.count("\u2019") == 2
        assert "'" not in result


# ---- Social-specific behavior (no apostrophe change) ----


class TestSanitizeInputSocial:
    def test_apostrophe_preserved(self, social_sanitize):
        result = social_sanitize("it's a test")
        assert "'" in result
