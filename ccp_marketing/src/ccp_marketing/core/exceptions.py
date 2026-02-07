"""Custom exceptions for CCP Marketing."""

from typing import Any


class CCPMarketingError(Exception):
    """Base exception for all CCP Marketing errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} - Details: {self.details}"
        return self.message


class AuthenticationError(CCPMarketingError):
    """Raised when authentication fails or session expires."""

    def __init__(
        self,
        message: str = "Authentication required",
        platform: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)
        self.platform = platform


class PlatformError(CCPMarketingError):
    """Raised when a platform-specific operation fails."""

    def __init__(
        self,
        message: str,
        platform: str,
        operation: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)
        self.platform = platform
        self.operation = operation


class RateLimitError(CCPMarketingError):
    """Raised when API rate limits are exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        platform: str | None = None,
        retry_after: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)
        self.platform = platform
        self.retry_after = retry_after


class ValidationError(CCPMarketingError):
    """Raised when input validation fails."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)
        self.field = field
        self.value = value


class StateTransitionError(CCPMarketingError):
    """Raised when an invalid state transition is attempted."""

    def __init__(
        self,
        message: str,
        current_state: str,
        attempted_state: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)
        self.current_state = current_state
        self.attempted_state = attempted_state


class RetryExhaustedError(CCPMarketingError):
    """Raised when all retry attempts have been exhausted."""

    def __init__(
        self,
        message: str = "All retry attempts exhausted",
        attempts: int = 0,
        last_error: Exception | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)
        self.attempts = attempts
        self.last_error = last_error
