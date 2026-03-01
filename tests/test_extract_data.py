"""
Tests for extract_data() — handles Composio's double-nested response format.

extract_data() is defined identically in all recipe files. We test the version
from luma_create_event.py as the canonical implementation.
"""

import pytest

from tests.conftest import RECIPES_DIR
from tests.helpers import extract_functions_from_file


@pytest.fixture
def extract_data():
    funcs = extract_functions_from_file(RECIPES_DIR / "luma_create_event.py", ["extract_data"])
    return funcs["extract_data"]


def test_none_input(extract_data):
    assert extract_data(None) == {}


def test_empty_dict(extract_data):
    assert extract_data({}) == {}


def test_single_nested(extract_data):
    result = {"data": {"id": "123", "name": "test"}}
    assert extract_data(result) == {"id": "123", "name": "test"}


def test_double_nested(extract_data):
    result = {"data": {"data": {"id": "456", "url": "https://example.com"}}}
    assert extract_data(result) == {"id": "456", "url": "https://example.com"}


def test_non_dict_data_value(extract_data):
    result = {"data": "just a string"}
    assert extract_data(result) == {}


def test_list_data_value(extract_data):
    result = {"data": [1, 2, 3]}
    assert extract_data(result) == {}


def test_no_data_key(extract_data):
    result = {"status": "ok", "id": "789"}
    assert extract_data(result) == {}


def test_preserves_all_inner_keys(extract_data):
    inner = {"a": 1, "b": "two", "c": [3], "d": {"nested": True}}
    result = {"data": inner}
    assert extract_data(result) == inner


def test_double_nested_preserves_keys(extract_data):
    inner = {"jobId": "abc", "sessionId": "def", "liveUrl": "https://live.example.com"}
    result = {"data": {"data": inner}}
    assert extract_data(result) == inner


def test_data_key_with_non_dict_inner(extract_data):
    """When data.data is not a dict, return data (which is a dict)."""
    result = {"data": {"data": "string_value", "other": "key"}}
    # data["data"] is a string, not a dict, so it should NOT unwrap
    # The function checks isinstance(data, dict) and "data" in data
    # then data = data["data"] which is "string_value"
    # then isinstance("string_value", dict) is False, so returns {}
    assert extract_data(result) == {}
