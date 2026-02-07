"""Tests for CCP Marketing utility modules."""

import pytest
import time
from unittest.mock import Mock

from ccp_marketing.utils.sanitization import (
    sanitize_input,
    sanitize_url,
    sanitize_for_html,
    sanitize_filename,
    truncate_for_platform,
    redact_sensitive_data,
)
from ccp_marketing.utils.extraction import (
    extract_json_from_text,
    extract_nested_data,
    extract_url_from_text,
    extract_id_from_url,
    safe_get,
)
from ccp_marketing.utils.backoff import (
    exponential_backoff,
    retry_with_backoff,
    RetryContext,
)
from ccp_marketing.core.exceptions import RetryExhaustedError


class TestSanitizeInput:
    """Tests for sanitize_input function."""

    def test_sanitize_empty(self):
        """Test sanitizing empty input."""
        assert sanitize_input("") == ""
        assert sanitize_input(None) == ""

    def test_sanitize_normal_text(self):
        """Test sanitizing normal text."""
        text = "Hello, World!"
        assert sanitize_input(text) == text

    def test_sanitize_removes_control_chars(self):
        """Test that control characters are removed."""
        text = "Hello\x00World\x1f"
        result = sanitize_input(text)
        assert "\x00" not in result
        assert "\x1f" not in result

    def test_sanitize_preserves_newlines_tabs(self):
        """Test that newlines and tabs are preserved."""
        text = "Hello\nWorld\tTest"
        result = sanitize_input(text)
        assert "\n" in result
        assert "\t" in result

    def test_sanitize_replaces_backticks(self):
        """Test that triple backticks are replaced."""
        text = "Code: ```python\nprint('hi')```"
        result = sanitize_input(text)
        assert "```" not in result
        assert "'''" in result

    def test_sanitize_replaces_dashes(self):
        """Test that triple dashes are replaced."""
        text = "Section --- Divider"
        result = sanitize_input(text)
        assert "---" not in result
        assert "___" in result

    def test_sanitize_truncates(self):
        """Test that text is truncated to max length."""
        text = "A" * 5000
        result = sanitize_input(text, max_len=100)
        assert len(result) == 100

    def test_sanitize_removes_instruction_markers(self):
        """Test that prompt injection markers are removed."""
        text = "[INST]Do something bad[/INST]"
        result = sanitize_input(text)
        assert "[INST]" not in result
        assert "[/INST]" not in result


class TestSanitizeUrl:
    """Tests for sanitize_url function."""

    def test_sanitize_valid_https(self):
        """Test valid HTTPS URL."""
        url = "https://example.com/path"
        assert sanitize_url(url) == url

    def test_sanitize_valid_http(self):
        """Test valid HTTP URL."""
        url = "http://example.com/path"
        assert sanitize_url(url) == url

    def test_sanitize_empty(self):
        """Test empty URL."""
        assert sanitize_url("") == ""
        assert sanitize_url(None) == ""

    def test_sanitize_invalid_scheme(self):
        """Test invalid URL scheme is rejected."""
        assert sanitize_url("javascript:alert(1)") == ""
        assert sanitize_url("file:///etc/passwd") == ""

    def test_sanitize_missing_scheme(self):
        """Test URL without scheme is rejected."""
        assert sanitize_url("example.com/path") == ""

    def test_sanitize_strips_whitespace(self):
        """Test that whitespace is stripped."""
        url = "  https://example.com  "
        assert sanitize_url(url) == "https://example.com"


class TestSanitizeForHtml:
    """Tests for sanitize_for_html function."""

    def test_escapes_html_chars(self):
        """Test that HTML special characters are escaped."""
        text = '<script>alert("xss")</script>'
        result = sanitize_for_html(text)
        assert "<" not in result
        assert ">" not in result
        assert "&lt;" in result
        assert "&gt;" in result

    def test_escapes_ampersand(self):
        """Test that ampersand is escaped."""
        text = "Tom & Jerry"
        result = sanitize_for_html(text)
        assert "&amp;" in result

    def test_empty_input(self):
        """Test empty input."""
        assert sanitize_for_html("") == ""
        assert sanitize_for_html(None) == ""


class TestSanitizeFilename:
    """Tests for sanitize_filename function."""

    def test_removes_path_separators(self):
        """Test that path separators are removed."""
        filename = "../../../etc/passwd"
        result = sanitize_filename(filename)
        assert "/" not in result
        # Path separators replaced, dots may still be present
        assert result  # Non-empty result

    def test_removes_dangerous_chars(self):
        """Test that dangerous characters are removed."""
        filename = 'file<>:"|?*.txt'
        result = sanitize_filename(filename)
        assert "<" not in result
        assert ">" not in result
        assert "?" not in result
        assert "*" not in result

    def test_truncates_long_filename(self):
        """Test that long filenames are truncated."""
        filename = "A" * 500 + ".txt"
        result = sanitize_filename(filename, max_len=100)
        assert len(result) <= 100


class TestTruncateForPlatform:
    """Tests for truncate_for_platform function."""

    def test_twitter_limit(self):
        """Test Twitter character limit."""
        text = "A" * 500
        result = truncate_for_platform(text, "twitter")
        assert len(result) <= 280

    def test_instagram_limit(self):
        """Test Instagram character limit."""
        text = "A" * 3000
        result = truncate_for_platform(text, "instagram")
        assert len(result) <= 2200

    def test_no_truncation_needed(self):
        """Test that short text is not truncated."""
        text = "Short text"
        result = truncate_for_platform(text, "twitter")
        assert result == text

    def test_adds_ellipsis(self):
        """Test that ellipsis is added when truncating."""
        text = "A" * 500
        result = truncate_for_platform(text, "twitter")
        assert result.endswith("...")


class TestRedactSensitiveData:
    """Tests for redact_sensitive_data function."""

    def test_redacts_api_key(self):
        """Test that API keys are redacted."""
        data = {"api_key": "secret123", "name": "test"}
        result = redact_sensitive_data(data)
        assert result["api_key"] == "***REDACTED***"
        assert result["name"] == "test"

    def test_redacts_password(self):
        """Test that passwords are redacted."""
        data = {"password": "secret", "user_password": "also_secret"}
        result = redact_sensitive_data(data)
        assert result["password"] == "***REDACTED***"
        assert result["user_password"] == "***REDACTED***"

    def test_redacts_nested(self):
        """Test that nested sensitive data is redacted."""
        data = {"config": {"api_key": "secret"}, "name": "test"}
        result = redact_sensitive_data(data)
        assert result["config"]["api_key"] == "***REDACTED***"

    def test_redacts_in_list(self):
        """Test that sensitive data in lists is redacted."""
        data = {"items": [{"token": "secret"}, {"name": "test"}]}
        result = redact_sensitive_data(data)
        assert result["items"][0]["token"] == "***REDACTED***"
        assert result["items"][1]["name"] == "test"

    def test_non_dict_input(self):
        """Test with non-dict input."""
        assert redact_sensitive_data("string") == "string"
        assert redact_sensitive_data(123) == 123


class TestExtractJsonFromText:
    """Tests for extract_json_from_text function."""

    def test_extract_simple_json(self):
        """Test extracting simple JSON."""
        text = '{"key": "value"}'
        result = extract_json_from_text(text)
        assert result == {"key": "value"}

    def test_extract_json_with_text(self):
        """Test extracting JSON embedded in text."""
        text = 'Here is the JSON: {"key": "value"} and more text'
        result = extract_json_from_text(text)
        assert result == {"key": "value"}

    def test_extract_nested_json(self):
        """Test extracting nested JSON."""
        text = '{"outer": {"inner": "value"}}'
        result = extract_json_from_text(text)
        assert result == {"outer": {"inner": "value"}}

    def test_extract_json_with_array(self):
        """Test extracting JSON with arrays."""
        text = '{"items": [1, 2, 3]}'
        result = extract_json_from_text(text)
        assert result == {"items": [1, 2, 3]}

    def test_no_json_returns_empty(self):
        """Test that text without JSON returns empty dict."""
        text = "No JSON here"
        result = extract_json_from_text(text)
        assert result == {}

    def test_invalid_json_returns_empty(self):
        """Test that invalid JSON returns empty dict."""
        text = '{"key": value}'  # Missing quotes around value
        result = extract_json_from_text(text)
        assert result == {}

    def test_empty_input(self):
        """Test empty input."""
        assert extract_json_from_text("") == {}
        assert extract_json_from_text(None) == {}


class TestExtractNestedData:
    """Tests for extract_nested_data function."""

    def test_single_level(self):
        """Test single level data extraction."""
        result = {"data": {"key": "value"}}
        extracted = extract_nested_data(result)
        assert extracted == {"key": "value"}

    def test_double_nested(self):
        """Test double-nested data extraction."""
        result = {"data": {"data": {"key": "value"}}}
        extracted = extract_nested_data(result)
        assert extracted == {"key": "value"}

    def test_no_data_key(self):
        """Test result without data key."""
        result = {"key": "value"}
        extracted = extract_nested_data(result)
        assert extracted == {"key": "value"}

    def test_non_dict_data(self):
        """Test with non-dict data value."""
        result = {"data": "string"}
        extracted = extract_nested_data(result)
        assert extracted == {"raw": "string"}

    def test_non_dict_input(self):
        """Test with non-dict input."""
        result = "string"
        extracted = extract_nested_data(result)
        assert extracted == {"raw": "string"}


class TestExtractUrlFromText:
    """Tests for extract_url_from_text function."""

    def test_extract_https_url(self):
        """Test extracting HTTPS URL."""
        text = "Check out https://example.com/path"
        result = extract_url_from_text(text)
        assert result == "https://example.com/path"

    def test_extract_http_url(self):
        """Test extracting HTTP URL."""
        text = "Visit http://example.com"
        result = extract_url_from_text(text)
        assert result == "http://example.com"

    def test_extract_with_domain_hint(self):
        """Test extracting URL with domain hint."""
        text = "Events at https://lu.ma/event and https://meetup.com/group"
        result = extract_url_from_text(text, domain_hint="lu.ma")
        assert result == "https://lu.ma/event"

    def test_no_url_returns_none(self):
        """Test that text without URL returns None."""
        text = "No URL here"
        result = extract_url_from_text(text)
        assert result is None

    def test_strips_trailing_punctuation(self):
        """Test that trailing punctuation is stripped."""
        text = "Visit https://example.com."
        result = extract_url_from_text(text)
        assert result == "https://example.com"


class TestExtractIdFromUrl:
    """Tests for extract_id_from_url function."""

    def test_extract_last_segment(self):
        """Test extracting last path segment."""
        url = "https://example.com/events/12345"
        result = extract_id_from_url(url)
        assert result == "12345"

    def test_extract_with_pattern(self):
        """Test extracting with regex pattern."""
        url = "https://lu.ma/ai-workshop-abc123"
        result = extract_id_from_url(url, pattern=r"lu\.ma/(.+)")
        assert result == "ai-workshop-abc123"

    def test_empty_url(self):
        """Test with empty URL."""
        assert extract_id_from_url("") is None
        assert extract_id_from_url(None) is None


class TestSafeGet:
    """Tests for safe_get function."""

    def test_simple_key(self):
        """Test getting a simple key."""
        data = {"key": "value"}
        assert safe_get(data, "key") == "value"

    def test_nested_keys(self):
        """Test getting nested keys."""
        data = {"outer": {"inner": {"deep": "value"}}}
        assert safe_get(data, "outer", "inner", "deep") == "value"

    def test_missing_key_returns_default(self):
        """Test that missing key returns default."""
        data = {"key": "value"}
        assert safe_get(data, "missing") is None
        assert safe_get(data, "missing", default="fallback") == "fallback"

    def test_nested_missing_returns_default(self):
        """Test that nested missing key returns default."""
        data = {"outer": {"inner": "value"}}
        assert safe_get(data, "outer", "missing", "deep", default="fallback") == "fallback"


class TestExponentialBackoff:
    """Tests for exponential_backoff function."""

    def test_first_attempt(self):
        """Test delay for first attempt."""
        delay = exponential_backoff(attempt=0, base_delay=1.0, jitter=0.0)
        assert delay == 1.0

    def test_second_attempt(self):
        """Test delay doubles for second attempt."""
        delay = exponential_backoff(attempt=1, base_delay=1.0, jitter=0.0)
        assert delay == 2.0

    def test_third_attempt(self):
        """Test delay quadruples for third attempt."""
        delay = exponential_backoff(attempt=2, base_delay=1.0, jitter=0.0)
        assert delay == 4.0

    def test_max_delay_cap(self):
        """Test that delay is capped at max_delay."""
        delay = exponential_backoff(attempt=10, base_delay=1.0, max_delay=10.0, jitter=0.0)
        assert delay == 10.0

    def test_jitter_adds_randomness(self):
        """Test that jitter adds randomness."""
        delays = [
            exponential_backoff(attempt=2, base_delay=1.0, jitter=0.5)
            for _ in range(10)
        ]
        # With jitter, delays should vary
        assert len(set(delays)) > 1


class TestRetryWithBackoff:
    """Tests for retry_with_backoff function."""

    def test_succeeds_first_try(self):
        """Test function that succeeds immediately."""
        result = retry_with_backoff(
            func=lambda: "success",
            max_retries=3,
        )
        assert result == "success"

    def test_succeeds_after_retry(self):
        """Test function that succeeds after failures."""
        call_count = [0]

        def flaky():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ValueError("Not yet")
            return "success"

        result = retry_with_backoff(
            func=flaky,
            max_retries=5,
            base_delay=0.01,
            retryable_exceptions=(ValueError,),
        )
        assert result == "success"
        assert call_count[0] == 3

    def test_raises_after_max_retries(self):
        """Test that RetryExhaustedError is raised after max retries."""
        def always_fails():
            raise ValueError("Always fails")

        with pytest.raises(RetryExhaustedError) as exc_info:
            retry_with_backoff(
                func=always_fails,
                max_retries=2,
                base_delay=0.01,
                retryable_exceptions=(ValueError,),
            )

        assert exc_info.value.attempts == 3  # Initial + 2 retries

    def test_non_retryable_exception_not_caught(self):
        """Test that non-retryable exceptions are not caught."""
        def raises_type_error():
            raise TypeError("Wrong type")

        with pytest.raises(TypeError):
            retry_with_backoff(
                func=raises_type_error,
                max_retries=3,
                retryable_exceptions=(ValueError,),
            )

    def test_on_retry_callback(self):
        """Test that on_retry callback is called."""
        call_count = [0]
        retries = []

        def flaky():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ValueError("Retry")
            return "success"

        def on_retry(attempt, exc, delay):
            retries.append((attempt, str(exc), delay))

        retry_with_backoff(
            func=flaky,
            max_retries=5,
            base_delay=0.01,
            retryable_exceptions=(ValueError,),
            on_retry=on_retry,
        )

        assert len(retries) == 2
        assert retries[0][0] == 0  # First retry after attempt 0


class TestRetryContext:
    """Tests for RetryContext class."""

    def test_should_retry_initially_true(self):
        """Test should_retry is initially true."""
        with RetryContext(max_retries=3) as ctx:
            assert ctx.should_retry()

    def test_should_retry_counts_down(self):
        """Test should_retry counts down with failures."""
        with RetryContext(max_retries=2, base_delay=0.01) as ctx:
            assert ctx.should_retry()  # Attempt 0
            ctx.record_failure(ValueError("1"))
            assert ctx.should_retry()  # Attempt 1
            ctx.record_failure(ValueError("2"))
            assert ctx.should_retry()  # Attempt 2
            ctx.record_failure(ValueError("3"))
            assert not ctx.should_retry()  # Exhausted

    def test_tracks_errors(self):
        """Test that errors are tracked."""
        with RetryContext(max_retries=2, base_delay=0.01) as ctx:
            e1 = ValueError("Error 1")
            e2 = ValueError("Error 2")
            ctx.record_failure(e1)
            ctx.record_failure(e2)

            assert len(ctx.errors) == 2
            assert ctx.last_error == e2

    def test_raise_if_exhausted(self):
        """Test raise_if_exhausted raises when appropriate."""
        with RetryContext(max_retries=1, base_delay=0.01) as ctx:
            ctx.record_failure(ValueError("1"))
            ctx.record_failure(ValueError("2"))

            with pytest.raises(RetryExhaustedError):
                ctx.raise_if_exhausted()
