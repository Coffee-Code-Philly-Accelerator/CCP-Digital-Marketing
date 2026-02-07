"""Exponential backoff and retry utilities."""

import logging
import random
import time
from typing import Any, Callable, TypeVar

from ccp_marketing.core.exceptions import RetryExhaustedError

logger = logging.getLogger(__name__)

T = TypeVar("T")


def exponential_backoff(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    jitter: float = 0.1,
) -> float:
    """Calculate delay for exponential backoff with jitter.

    Args:
        attempt: Current attempt number (0-indexed)
        base_delay: Base delay in seconds
        max_delay: Maximum delay cap
        jitter: Jitter factor (0.0 to 1.0)

    Returns:
        Delay in seconds for this attempt
    """
    # Calculate exponential delay: base * 2^attempt
    delay = base_delay * (2**attempt)

    # Cap at maximum
    delay = min(delay, max_delay)

    # Add jitter to prevent thundering herd
    if jitter > 0:
        jitter_amount = delay * jitter
        delay = delay + random.uniform(-jitter_amount, jitter_amount)

    return max(0, delay)


def retry_with_backoff(
    func: Callable[[], T],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    jitter: float = 0.1,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
    on_retry: Callable[[int, Exception, float], None] | None = None,
) -> T:
    """Execute a function with retry and exponential backoff.

    Args:
        func: Function to execute
        max_retries: Maximum number of retry attempts
        base_delay: Base delay between retries
        max_delay: Maximum delay cap
        jitter: Jitter factor for randomization
        retryable_exceptions: Tuple of exception types to retry on
        on_retry: Optional callback called before each retry with (attempt, exception, delay)

    Returns:
        Result from successful function execution

    Raises:
        RetryExhaustedError: If all retry attempts fail
        Exception: If a non-retryable exception occurs
    """
    last_exception: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            return func()
        except retryable_exceptions as e:
            last_exception = e

            if attempt >= max_retries:
                logger.warning(f"All {max_retries} retry attempts exhausted")
                raise RetryExhaustedError(
                    message=f"All {max_retries} retry attempts exhausted",
                    attempts=attempt + 1,
                    last_error=e,
                    details={"last_error_type": type(e).__name__, "last_error_msg": str(e)},
                ) from e

            delay = exponential_backoff(attempt, base_delay, max_delay, jitter)
            logger.info(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.2f}s...")

            if on_retry:
                on_retry(attempt, e, delay)

            time.sleep(delay)

    # This should never be reached, but satisfy type checker
    raise RetryExhaustedError(
        message="Unexpected retry loop exit",
        attempts=max_retries + 1,
        last_error=last_exception,
    )


class RetryContext:
    """Context manager for retry operations with state tracking.

    Example:
        >>> with RetryContext(max_retries=3) as ctx:
        ...     while ctx.should_retry():
        ...         try:
        ...             result = do_something()
        ...             break
        ...         except SomeError as e:
        ...             ctx.record_failure(e)
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        jitter: float = 0.1,
    ) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter
        self.attempt = 0
        self.last_error: Exception | None = None
        self.errors: list[Exception] = []

    def __enter__(self) -> "RetryContext":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        return False  # Don't suppress exceptions

    def should_retry(self) -> bool:
        """Check if another retry attempt should be made.

        Returns:
            True if more retries are available
        """
        return self.attempt <= self.max_retries

    def record_failure(self, error: Exception) -> None:
        """Record a failed attempt and wait before next retry.

        Args:
            error: The exception that caused the failure
        """
        self.last_error = error
        self.errors.append(error)

        if self.attempt < self.max_retries:
            delay = exponential_backoff(
                self.attempt,
                self.base_delay,
                self.max_delay,
                self.jitter,
            )
            logger.info(f"Attempt {self.attempt + 1} failed. Retrying in {delay:.2f}s...")
            time.sleep(delay)

        self.attempt += 1

    def raise_if_exhausted(self) -> None:
        """Raise RetryExhaustedError if all attempts have been used.

        Raises:
            RetryExhaustedError: If max_retries has been exceeded
        """
        if self.attempt > self.max_retries:
            raise RetryExhaustedError(
                message=f"All {self.max_retries} retry attempts exhausted",
                attempts=self.attempt,
                last_error=self.last_error,
            )
