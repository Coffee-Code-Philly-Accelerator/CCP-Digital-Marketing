"""Input sanitization utilities for CCP Marketing.

These utilities help prevent prompt injection attacks and ensure
input data is safe for use in LLM prompts and API calls.
"""

import re
from urllib.parse import urlparse


def sanitize_input(text: str | None, max_len: int = 2000) -> str:
    """Sanitize user input to prevent prompt injection attacks.

    Args:
        text: Input text to sanitize
        max_len: Maximum allowed length (default 2000)

    Returns:
        Sanitized string safe for inclusion in LLM prompts
    """
    if not text:
        return ""

    # Convert to string if needed
    text = str(text)

    # Remove control characters except newlines and tabs
    text = "".join(char for char in text if char >= " " or char in "\n\t")

    # Replace common prompt injection delimiters
    text = text.replace("```", "'''")
    text = text.replace("---", "___")

    # Remove potential instruction markers
    dangerous_patterns = [
        r"\[INST\]",
        r"\[/INST\]",
        r"<\|im_start\|>",
        r"<\|im_end\|>",
        r"<\|system\|>",
        r"<\|user\|>",
        r"<\|assistant\|>",
    ]
    for pattern in dangerous_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    # Truncate to max length
    return text[:max_len]


def sanitize_url(url: str | None) -> str:
    """Sanitize a URL for safe usage.

    Args:
        url: URL to sanitize

    Returns:
        Sanitized URL or empty string if invalid

    Note:
        Only allows http and https schemes.
    """
    if not url:
        return ""

    url = str(url).strip()

    # Parse and validate
    try:
        parsed = urlparse(url)

        # Only allow http and https
        if parsed.scheme not in ("http", "https"):
            return ""

        # Must have a netloc (domain)
        if not parsed.netloc:
            return ""

        # Reconstruct to ensure proper formatting
        return url

    except Exception:
        return ""


def sanitize_for_html(text: str | None) -> str:
    """Sanitize text for safe HTML output.

    Args:
        text: Text to sanitize

    Returns:
        HTML-safe string
    """
    if not text:
        return ""

    # Escape HTML special characters
    replacements = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#x27;",
    }

    for char, replacement in replacements.items():
        text = text.replace(char, replacement)

    return text


def sanitize_filename(filename: str | None, max_len: int = 255) -> str:
    """Sanitize a filename for safe filesystem usage.

    Args:
        filename: Filename to sanitize
        max_len: Maximum filename length

    Returns:
        Safe filename string
    """
    if not filename:
        return ""

    # Remove path separators and other dangerous characters
    dangerous_chars = r'[<>:"/\\|?*\x00-\x1f]'
    filename = re.sub(dangerous_chars, "_", filename)

    # Remove leading/trailing dots and spaces
    filename = filename.strip(". ")

    # Truncate
    return filename[:max_len]


def truncate_for_platform(text: str, platform: str) -> str:
    """Truncate text to platform-specific limits.

    Args:
        text: Text to truncate
        platform: Platform name (twitter, instagram, etc.)

    Returns:
        Truncated text with ellipsis if needed
    """
    limits = {
        "twitter": 280,
        "instagram": 2200,
        "facebook": 63206,
        "linkedin": 3000,
        "discord": 2000,
    }

    limit = limits.get(platform.lower(), 2000)

    if len(text) <= limit:
        return text

    # Leave room for ellipsis
    return text[: limit - 3] + "..."


def redact_sensitive_data(
    data: dict,
    sensitive_keys: set[str] | None = None,
) -> dict:
    """Redact sensitive values from a dictionary for safe logging.

    Args:
        data: Dictionary to redact
        sensitive_keys: Set of key substrings to redact. Defaults to common sensitive keys.

    Returns:
        New dictionary with sensitive values replaced with "***REDACTED***"
    """
    if sensitive_keys is None:
        sensitive_keys = {"api_key", "password", "secret", "token", "credential", "auth"}

    if not isinstance(data, dict):
        return data

    redacted = {}
    for key, value in data.items():
        key_lower = key.lower()
        if any(sk in key_lower for sk in sensitive_keys):
            redacted[key] = "***REDACTED***"
        elif isinstance(value, dict):
            redacted[key] = redact_sensitive_data(value, sensitive_keys)
        elif isinstance(value, list):
            redacted[key] = [
                redact_sensitive_data(item, sensitive_keys) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            redacted[key] = value

    return redacted
