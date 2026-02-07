"""Page state verification utilities."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Common patterns indicating authentication is required
AUTH_PATTERNS = [
    "sign in",
    "log in",
    "login",
    "sign up",
    "create account",
    "enter your email",
    "enter your password",
    "verification code",
    "2fa",
    "two-factor",
    "authenticate",
    "verify your",
    "continue with google",
    "continue with apple",
    "continue with email",
]

# Patterns indicating 2FA specifically
TWO_FA_PATTERNS = [
    "verification code",
    "2fa",
    "two-factor",
    "authenticator",
    "enter the code",
    "sms code",
    "security code",
]

# Patterns indicating validation errors
VALIDATION_ERROR_PATTERNS = [
    "required",
    "fix errors",
    "please enter",
    "invalid",
    "can't be blank",
    "must be",
    "is required",
    "please fill",
    "error:",
]


@dataclass
class VerificationResult:
    """Result of a page verification check.

    Attributes:
        passed: Whether the verification passed
        signals: Dictionary of individual signal results
        signal_count: Number of positive signals
        confidence: Overall confidence (0-1)
        details: Additional details about the verification
    """

    passed: bool
    signals: dict[str, bool] = field(default_factory=dict)
    signal_count: int = 0
    confidence: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        status = "passed" if self.passed else "failed"
        return f"VerificationResult({status}, signals={self.signal_count})"


class PageVerifier:
    """Verifies page state for browser automation.

    Provides utilities to check:
    - Authentication status
    - Form page detection
    - Validation errors
    - Success/confirmation pages
    - Multi-signal verification for event creation

    Example:
        verifier = PageVerifier()

        # Check if auth is needed
        if verifier.needs_auth(page_content):
            if verifier.needs_2fa(page_content):
                # Pause for manual 2FA
                pass
            else:
                # Login required
                pass

        # Verify event creation success
        result = verifier.verify_event_created(
            page_content,
            current_url,
            event_title,
            success_url_check=lambda url: "lu.ma/" in url,
        )
    """

    def __init__(self) -> None:
        """Initialize the page verifier."""
        self._auth_patterns = AUTH_PATTERNS
        self._two_fa_patterns = TWO_FA_PATTERNS
        self._validation_patterns = VALIDATION_ERROR_PATTERNS

    def needs_auth(self, page_content: str) -> bool:
        """Check if the page indicates authentication is needed.

        Args:
            page_content: Page content (markdown)

        Returns:
            True if auth appears to be required
        """
        content_lower = page_content.lower()
        return any(pattern in content_lower for pattern in self._auth_patterns)

    def needs_2fa(self, page_content: str) -> bool:
        """Check if the page is requesting 2FA.

        Args:
            page_content: Page content (markdown)

        Returns:
            True if 2FA appears to be required
        """
        content_lower = page_content.lower()
        return any(pattern in content_lower for pattern in self._two_fa_patterns)

    def has_validation_errors(self, page_content: str) -> bool:
        """Check if the page shows validation errors.

        Args:
            page_content: Page content (markdown)

        Returns:
            True if validation errors are present
        """
        content_lower = page_content.lower()
        return any(pattern in content_lower for pattern in self._validation_patterns)

    def is_form_page(
        self, page_content: str, form_indicators: list[str]
    ) -> bool:
        """Check if the current page is a form page.

        Args:
            page_content: Page content (markdown)
            form_indicators: Platform-specific indicators of form presence

        Returns:
            True if form indicators are found
        """
        content_lower = page_content.lower()
        return any(indicator.lower() in content_lower for indicator in form_indicators)

    def verify_event_created(
        self,
        page_content: str,
        current_url: str,
        event_title: str,
        success_url_check: Callable[[str], bool],
        form_indicators: list[str] | None = None,
    ) -> VerificationResult:
        """Verify event creation using multi-signal approach.

        Uses multiple signals to determine success:
        1. URL matches success pattern
        2. Event title visible on page
        3. Edit/manage buttons present
        4. Form is no longer visible
        5. Confirmation text present

        Args:
            page_content: Current page content
            current_url: Current browser URL
            event_title: Title of the created event
            success_url_check: Function to check if URL indicates success
            form_indicators: Indicators of form page (to check form is gone)

        Returns:
            VerificationResult with detailed signal analysis
        """
        content_lower = page_content.lower()
        title_lower = event_title.lower()

        signals = {
            "url_success": success_url_check(current_url),
            "title_visible": title_lower in content_lower,
            "edit_button": any(
                kw in content_lower for kw in ["edit", "manage", "settings"]
            ),
            "share_button": any(
                kw in content_lower for kw in ["share", "invite", "copy link"]
            ),
            "confirmation_text": any(
                kw in content_lower
                for kw in ["created", "published", "live", "success"]
            ),
            "no_form": not self.is_form_page(page_content, form_indicators or []),
        }

        signal_count = sum(signals.values())

        # Decision logic:
        # - URL success + 1 secondary = pass
        # - 3+ secondary signals = pass (without URL)
        passed = False
        confidence = signal_count / len(signals)

        if signals["url_success"] and signal_count >= 2:
            passed = True
            confidence = min(confidence + 0.2, 1.0)
        elif signal_count >= 3:
            passed = True

        return VerificationResult(
            passed=passed,
            signals=signals,
            signal_count=signal_count,
            confidence=confidence,
            details={"url": current_url, "title": event_title},
        )

    def verify_field_filled(
        self,
        page_content: str,
        field_name: str,
        expected_value: str,
    ) -> VerificationResult:
        """Verify a form field was filled correctly.

        Args:
            page_content: Current page content
            field_name: Name of the field
            expected_value: Value that should be present

        Returns:
            VerificationResult
        """
        content_lower = page_content.lower()
        value_lower = expected_value.lower()

        # Check if value appears in content
        value_found = value_lower in content_lower

        # Check for validation errors near the field
        has_error = self.has_validation_errors(page_content)

        signals = {
            "value_visible": value_found,
            "no_validation_error": not has_error,
        }

        passed = value_found and not has_error
        signal_count = sum(signals.values())

        return VerificationResult(
            passed=passed,
            signals=signals,
            signal_count=signal_count,
            confidence=0.7 if passed else 0.3,
            details={"field": field_name, "expected": expected_value},
        )

    def extract_url_from_page(
        self, page_content: str, pattern: str
    ) -> str | None:
        """Extract a URL matching a pattern from page content.

        Args:
            page_content: Page content (markdown)
            pattern: Regex pattern for the URL

        Returns:
            Matched URL or None
        """
        try:
            match = re.search(pattern, page_content)
            if match:
                return match.group(0)
        except re.error as e:
            logger.warning(f"Invalid URL pattern: {e}")
        return None

    def get_auth_prompt(self, page_content: str) -> str:
        """Generate a user-friendly auth prompt based on page content.

        Args:
            page_content: Page content showing auth requirement

        Returns:
            Human-readable prompt for the user
        """
        if self.needs_2fa(page_content):
            return (
                "Two-factor authentication required. "
                "Please complete 2FA in the browser and let me know when done."
            )
        return (
            "Login required. "
            "Please log in to the platform in the browser and let me know when done."
        )
