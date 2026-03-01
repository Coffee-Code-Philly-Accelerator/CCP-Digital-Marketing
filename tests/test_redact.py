"""
Tests for redact_sensitive_data() from scripts/recipe_client.py.

This function is a module-level pure function that can be imported directly.
"""

import sys
from pathlib import Path

# Add scripts/ to sys.path so we can import recipe_client
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from recipe_client import redact_sensitive_data


class TestRedactSensitiveData:
    def test_api_key_redacted(self):
        data = {"api_key": "secret123"}
        result = redact_sensitive_data(data)
        assert result["api_key"] == "***REDACTED***"

    def test_password_redacted(self):
        data = {"password": "hunter2"}
        result = redact_sensitive_data(data)
        assert result["password"] == "***REDACTED***"

    def test_secret_redacted(self):
        data = {"client_secret": "abc"}
        result = redact_sensitive_data(data)
        assert result["client_secret"] == "***REDACTED***"

    def test_token_redacted(self):
        data = {"access_token": "tok_123"}
        result = redact_sensitive_data(data)
        assert result["access_token"] == "***REDACTED***"

    def test_credential_redacted(self):
        data = {"user_credential": "cred"}
        result = redact_sensitive_data(data)
        assert result["user_credential"] == "***REDACTED***"

    def test_auth_redacted(self):
        data = {"auth_header": "Bearer xyz"}
        result = redact_sensitive_data(data)
        assert result["auth_header"] == "***REDACTED***"

    def test_case_insensitive(self):
        data = {"API_KEY": "secret", "Password": "hunter2", "ACCESS_TOKEN": "tok"}
        result = redact_sensitive_data(data)
        assert result["API_KEY"] == "***REDACTED***"
        assert result["Password"] == "***REDACTED***"
        assert result["ACCESS_TOKEN"] == "***REDACTED***"

    def test_substring_matching(self):
        """Keys containing sensitive substrings are redacted."""
        data = {"my_api_key_value": "secret"}
        result = redact_sensitive_data(data)
        assert result["my_api_key_value"] == "***REDACTED***"

    def test_nested_dicts_redacted(self):
        data = {"outer": {"api_key": "nested_secret", "safe": "visible"}}
        result = redact_sensitive_data(data)
        assert result["outer"]["api_key"] == "***REDACTED***"
        assert result["outer"]["safe"] == "visible"

    def test_non_dict_passthrough(self):
        assert redact_sensitive_data("string") == "string"
        assert redact_sensitive_data(42) == 42
        assert redact_sensitive_data(None) is None
        assert redact_sensitive_data([1, 2]) == [1, 2]

    def test_empty_dict(self):
        assert redact_sensitive_data({}) == {}

    def test_safe_keys_preserved(self):
        data = {"title": "AI Workshop", "date": "Jan 25", "location": "Philly"}
        result = redact_sensitive_data(data)
        assert result == data

    def test_original_not_mutated(self):
        data = {"api_key": "secret", "title": "test"}
        original_value = data["api_key"]
        redact_sensitive_data(data)
        assert data["api_key"] == original_value

    def test_custom_sensitive_keys(self):
        data = {"ssn": "123-45-6789", "name": "John"}
        result = redact_sensitive_data(data, sensitive_keys={"ssn"})
        assert result["ssn"] == "***REDACTED***"
        assert result["name"] == "John"
