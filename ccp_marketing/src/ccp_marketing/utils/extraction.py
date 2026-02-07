"""Data extraction utilities for CCP Marketing."""

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def extract_json_from_text(text: str | None) -> dict[str, Any]:
    """Robustly extract JSON object from text that may contain non-JSON content.

    Handles cases where JSON is embedded in explanatory text, has nested
    structures, or spans multiple lines.

    Args:
        text: String that may contain a JSON object

    Returns:
        Parsed dict if found, empty dict otherwise
    """
    if not text:
        return {}

    # First, try to parse the entire text as JSON
    try:
        result = json.loads(text.strip())
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # Find JSON by matching outermost braces with depth tracking
    start = text.find("{")
    if start == -1:
        return {}

    depth = 0
    in_string = False
    escape_next = False

    for i, char in enumerate(text[start:], start):
        if escape_next:
            escape_next = False
            continue

        if char == "\\":
            escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    # Try to find another JSON object
                    next_start = text.find("{", start + 1)
                    if next_start != -1:
                        return extract_json_from_text(text[next_start:])
                    return {}

    return {}


def extract_nested_data(result: dict[str, Any] | Any) -> dict[str, Any]:
    """Extract data from Composio's potentially double-nested response format.

    Composio often returns responses like: {"data": {"data": {...actual_data...}}}
    This function handles that pattern and returns the innermost data.

    Args:
        result: Raw response from Composio API

    Returns:
        Extracted data dictionary
    """
    if not isinstance(result, dict):
        return {"raw": result}

    data = result.get("data", result)

    # Handle double nesting
    if isinstance(data, dict) and "data" in data:
        data = data["data"]

    return data if isinstance(data, dict) else {"raw": data}


def extract_url_from_text(text: str | None, domain_hint: str | None = None) -> str | None:
    """Extract a URL from text, optionally filtering by domain.

    Args:
        text: Text that may contain URLs
        domain_hint: Optional domain to filter for (e.g., "lu.ma")

    Returns:
        First matching URL or None
    """
    if not text:
        return None

    # URL pattern that matches common URL formats
    url_pattern = r"https?://[^\s<>\"'{}|\\^`\[\]]+"

    urls = re.findall(url_pattern, text)

    if not urls:
        return None

    if domain_hint:
        for url in urls:
            if domain_hint.lower() in url.lower():
                return url.rstrip(".,;:!?)")

    return urls[0].rstrip(".,;:!?)") if urls else None


def extract_id_from_url(url: str, pattern: str | None = None) -> str | None:
    """Extract an ID from a URL using a pattern.

    Args:
        url: URL to extract ID from
        pattern: Regex pattern with a capture group for the ID.
                 If None, returns the last path segment.

    Returns:
        Extracted ID or None
    """
    if not url:
        return None

    if pattern:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
        return None

    # Default: return last path segment
    parts = url.rstrip("/").split("/")
    return parts[-1] if parts else None


def safe_get(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Safely get a nested value from a dictionary.

    Args:
        data: Dictionary to traverse
        *keys: Keys to follow in order
        default: Default value if path doesn't exist

    Returns:
        Value at the nested path or default
    """
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
        if current is default:
            return default
    return current
