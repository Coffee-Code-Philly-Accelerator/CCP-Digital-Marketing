"""Composio client wrapper for CCP Marketing."""

import logging
from typing import Any, TYPE_CHECKING

# Lazy import to allow package usage without composio installed (for testing)
if TYPE_CHECKING:
    from composio import ComposioToolSet, Action

from ccp_marketing.core.config import Config
from ccp_marketing.core.exceptions import (
    AuthenticationError,
    CCPMarketingError,
    PlatformError,
    RateLimitError,
)
from ccp_marketing.utils.backoff import retry_with_backoff

logger = logging.getLogger(__name__)


class ComposioClient:
    """Wrapper around Composio SDK with retry logic and data extraction.

    This client provides a simplified interface to the Composio SDK with:
    - Automatic retry with exponential backoff
    - Nested data extraction (handles Composio's data.data pattern)
    - Error classification and custom exceptions
    - Logging with sensitive data redaction

    Example:
        >>> client = ComposioClient()
        >>> result = client.execute_action("TWITTER_CREATION_OF_A_POST", {"text": "Hello!"})
        >>> print(result)
    """

    def __init__(self, config: Config | None = None, api_key: str | None = None) -> None:
        """Initialize the Composio client.

        Args:
            config: Optional Config instance. If not provided, creates from environment.
            api_key: Optional API key override. If not provided, uses config value.
        """
        self.config = config or Config.from_env()
        self._api_key = api_key or self.config.composio_api_key

        if not self._api_key:
            raise AuthenticationError(
                "COMPOSIO_API_KEY not found. Set it as an environment variable "
                "or pass it to the constructor."
            )

        # Import composio at runtime - handle both old and new API
        try:
            from composio import Composio
            self._client = Composio(api_key=self._api_key)
            self._new_api = True
        except ImportError:
            try:
                from composio import ComposioToolSet
                self._client = ComposioToolSet(api_key=self._api_key)
                self._new_api = False
            except ImportError as e:
                raise ImportError(
                    "composio package not installed. Install with: pip install composio"
                ) from e

        logger.debug("ComposioClient initialized")

    def execute_action(
        self,
        action: str,
        params: dict[str, Any],
        retry: bool = True,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Execute a Composio action with retry logic.

        Args:
            action: The action name (e.g., "TWITTER_CREATION_OF_A_POST")
            params: Parameters for the action
            retry: Whether to retry on transient failures
            timeout: Optional timeout override

        Returns:
            Extracted data from the action response

        Raises:
            AuthenticationError: If authentication fails
            RateLimitError: If rate limits are exceeded
            PlatformError: If the action fails for other reasons
        """
        timeout = timeout or self.config.default_timeout

        if retry:
            return retry_with_backoff(
                func=lambda: self._execute_action_impl(action, params),
                max_retries=self.config.max_retries,
                base_delay=self.config.retry_base_delay,
                max_delay=self.config.retry_max_delay,
                jitter=self.config.retry_jitter,
                retryable_exceptions=(PlatformError,),
            )
        return self._execute_action_impl(action, params)

    def _execute_action_impl(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        """Internal implementation of action execution.

        Args:
            action: The action name
            params: Parameters for the action

        Returns:
            Extracted data from the response

        Raises:
            AuthenticationError: If authentication fails
            RateLimitError: If rate limits are exceeded
            PlatformError: If the action fails
        """
        logger.info(f"Executing action: {action}")
        logger.debug(f"Action params: {self._redact_params(params)}")

        try:
            if self._new_api:
                # New Composio API (v0.10+)
                response = self._client.tools.execute(
                    slug=action,
                    arguments=params,
                    user_id="default",
                    dangerously_skip_version_check=True,
                )
            else:
                # Old Composio API
                from composio import Action
                response = self._client.execute_action(
                    action=Action[action],
                    params=params,
                )

            # Check for errors in response
            if isinstance(response, dict):
                if response.get("error"):
                    self._handle_error(action, response)

            data = self._extract_data(response)
            logger.debug(f"Action {action} completed successfully")
            return data

        except KeyError as e:
            raise PlatformError(
                message=f"Unknown action: {action}",
                platform="composio",
                operation=action,
                details={"error": str(e)},
            ) from e
        except CCPMarketingError:
            raise
        except Exception as e:
            raise PlatformError(
                message=f"Action failed: {action}",
                platform="composio",
                operation=action,
                details={"error": str(e), "error_type": type(e).__name__},
            ) from e

    def _extract_data(self, result: dict[str, Any] | Any) -> dict[str, Any]:
        """Extract data from Composio's potentially nested response.

        Composio often returns responses in the format:
        {"data": {"data": {...actual_data...}}}

        This method handles the double-nesting and returns the actual data.

        Args:
            result: Raw response from Composio

        Returns:
            Extracted data dictionary
        """
        if not isinstance(result, dict):
            return {"raw": result}

        data = result.get("data", result)
        if isinstance(data, dict) and "data" in data:
            data = data["data"]

        return data if isinstance(data, dict) else {"raw": data}

    def _handle_error(self, action: str, response: dict[str, Any]) -> None:
        """Handle error responses from Composio.

        Args:
            action: The action that failed
            response: The error response

        Raises:
            AuthenticationError: For auth-related errors
            RateLimitError: For rate limit errors
            PlatformError: For other errors
        """
        error = response.get("error", "Unknown error")
        error_str = str(error).lower()

        # Classify the error
        if any(term in error_str for term in ["auth", "unauthorized", "forbidden", "401", "403"]):
            raise AuthenticationError(
                message=f"Authentication failed for {action}",
                platform=self._extract_platform(action),
                details={"error": error},
            )

        if any(term in error_str for term in ["rate limit", "too many requests", "429"]):
            raise RateLimitError(
                message=f"Rate limit exceeded for {action}",
                platform=self._extract_platform(action),
                details={"error": error},
            )

        raise PlatformError(
            message=f"Action failed: {action}",
            platform=self._extract_platform(action),
            operation=action,
            details={"error": error},
        )

    def _extract_platform(self, action: str) -> str:
        """Extract platform name from action string.

        Args:
            action: Action name (e.g., "TWITTER_CREATION_OF_A_POST")

        Returns:
            Platform name (e.g., "twitter")
        """
        parts = action.split("_")
        if parts:
            return parts[0].lower()
        return "unknown"

    def _redact_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Redact sensitive data from params for logging.

        Args:
            params: Parameters to redact

        Returns:
            Redacted parameters safe for logging
        """
        if not self.config.redact_sensitive:
            return params

        sensitive_keys = {"password", "token", "secret", "key", "credential", "auth"}
        redacted = {}

        for key, value in params.items():
            key_lower = key.lower()
            if any(sk in key_lower for sk in sensitive_keys):
                redacted[key] = "***REDACTED***"
            elif isinstance(value, dict):
                redacted[key] = self._redact_params(value)
            else:
                redacted[key] = value

        return redacted

    def browser_navigate(self, url: str) -> dict[str, Any]:
        """Navigate browser to a URL.

        Args:
            url: URL to navigate to

        Returns:
            Page snapshot data
        """
        return self.execute_action("BROWSER_TOOL_NAVIGATE", {"url": url})

    def browser_perform_task(self, task: str) -> dict[str, Any]:
        """Perform a browser automation task.

        Args:
            task: Natural language description of the task

        Returns:
            Task result data
        """
        return self.execute_action("BROWSER_TOOL_PERFORM_WEB_TASK", {"prompt": task})

    def browser_get_page(self) -> dict[str, Any]:
        """Get current browser page state.

        Returns:
            Current page data including URL and content
        """
        return self.execute_action("BROWSER_TOOL_FETCH_WEBPAGE", {})

    def generate_image(self, prompt: str, model: str | None = None) -> dict[str, Any]:
        """Generate an image using Gemini.

        Args:
            prompt: Image generation prompt
            model: Optional model override

        Returns:
            Image data including URL
        """
        return self.execute_action(
            "GEMINI_GENERATE_IMAGE",
            {
                "prompt": prompt,
                "model": model or self.config.image_model,
            },
        )
