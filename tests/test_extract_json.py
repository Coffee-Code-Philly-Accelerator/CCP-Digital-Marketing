"""
Tests for extract_json_from_text() — parses JSON from LLM responses.

Defined in social_promotion.py and social_post.py (identical implementations).
Uses manual brace-depth counting to find the first valid JSON object.
"""

import pytest

from tests.conftest import RECIPES_DIR
from tests.helpers import extract_functions_with_imports


@pytest.fixture
def extract_json():
    funcs = extract_functions_with_imports(RECIPES_DIR / "social_promotion.py", ["extract_json_from_text"])
    return funcs["extract_json_from_text"]


def test_none_input(extract_json):
    assert extract_json(None) == {}


def test_empty_string(extract_json):
    assert extract_json("") == {}


def test_no_json(extract_json):
    assert extract_json("Just some plain text with no JSON") == {}


def test_clean_json(extract_json):
    text = '{"key": "value"}'
    assert extract_json(text) == {"key": "value"}


def test_json_with_surrounding_text(extract_json):
    text = 'Here is the JSON: {"name": "test"} and more text'
    assert extract_json(text) == {"name": "test"}


def test_markdown_code_block(extract_json):
    text = '```json\n{"twitter": "tweet", "linkedin": "post"}\n```'
    assert extract_json(text) == {"twitter": "tweet", "linkedin": "post"}


def test_nested_objects(extract_json):
    text = '{"outer": {"inner": "value"}}'
    result = extract_json(text)
    assert result == {"outer": {"inner": "value"}}


def test_invalid_json(extract_json):
    text = '{"key": broken}'
    assert extract_json(text) == {}


def test_malformed_json_missing_close(extract_json):
    text = '{"key": "value"'
    assert extract_json(text) == {}


def test_multiple_json_objects_returns_first(extract_json):
    text = '{"first": 1} and {"second": 2}'
    assert extract_json(text) == {"first": 1}


def test_full_llm_response_with_platform_keys(extract_json):
    text = """Here are the social media posts:

{"twitter": "Join us for AI Workshop! #AI #Philly", "linkedin": "We're hosting an AI Workshop in Philadelphia.", "instagram": "AI Workshop coming soon! Join us for hands-on learning.", "facebook": "Hey community! We're hosting an AI Workshop.", "discord": "**AI Workshop**\\nJoin us for a hands-on session."}

I hope these work for your promotion!"""
    result = extract_json(text)
    assert "twitter" in result
    assert "linkedin" in result
    assert "instagram" in result
    assert "facebook" in result
    assert "discord" in result


def test_json_with_special_characters(extract_json):
    text = '{"message": "Hello \\"world\\"!"}'
    result = extract_json(text)
    assert result == {"message": 'Hello "world"!'}
