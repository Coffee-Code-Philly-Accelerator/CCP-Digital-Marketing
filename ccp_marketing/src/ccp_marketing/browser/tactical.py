"""Tactical execution layer for hybrid explicit/AI browser automation."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable

from ccp_marketing.browser.element_resolver import (
    ElementResolver,
    ElementTarget,
    ResolvedElement,
    ResolutionMethod,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ExecutionStrategy(str, Enum):
    """Strategy for executing browser actions."""

    EXPLICIT_ONLY = "explicit_only"  # Only use MOUSE_CLICK + TYPE_TEXT
    AI_ONLY = "ai_only"  # Only use PERFORM_WEB_TASK
    HYBRID = "hybrid"  # Try explicit first, fall back to AI
    ADAPTIVE = "adaptive"  # Choose based on element complexity


@dataclass
class TacticalResult:
    """Result of a tactical execution attempt.

    Attributes:
        success: Whether the action succeeded
        method: Method used (explicit or ai_assisted)
        verified: Whether success was verified
        error: Error message if failed
        data: Additional data from the action
        page_content: Page content after action (for verification)
    """

    success: bool
    method: str
    verified: bool = False
    error: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    page_content: str | None = None

    def __str__(self) -> str:
        status = "success" if self.success else "failed"
        return f"TacticalResult({status}, method={self.method})"


# Type alias for browser tool executor function
BrowserToolExecutor = Callable[[str, dict[str, Any]], tuple[dict[str, Any], str | None]]


class TacticalExecutor:
    """Executes browser actions with hybrid explicit/AI strategy.

    Provides a unified interface for browser interactions that:
    1. Tries explicit actions (MOUSE_CLICK + TYPE_TEXT) first for reliability
    2. Falls back to AI-assisted (PERFORM_WEB_TASK) for complex interactions
    3. Verifies actions succeeded using FETCH_WEBPAGE

    Example:
        def execute_tool(tool_name, args):
            # Call RUBE_MULTI_EXECUTE_TOOL
            return result, error

        executor = TacticalExecutor(execute_tool)

        result = executor.fill_field(
            target=ElementTarget(name="title", css_selector="input#title"),
            value="My Event",
            strategy=ExecutionStrategy.HYBRID,
        )
    """

    def __init__(
        self,
        tool_executor: BrowserToolExecutor,
        resolver: ElementResolver | None = None,
    ) -> None:
        """Initialize the tactical executor.

        Args:
            tool_executor: Function to execute browser tools.
                          Signature: (tool_name, args) -> (result, error)
            resolver: Element resolver instance (created if not provided)
        """
        self._execute_tool = tool_executor
        self._resolver = resolver or ElementResolver()
        self._last_page_content: str | None = None
        self._last_page_html: str | None = None

    def fetch_page(self, format: str = "markdown") -> tuple[str, str | None]:
        """Fetch current page content.

        Args:
            format: Output format ("markdown" or "html")

        Returns:
            Tuple of (content, error)
        """
        result, error = self._execute_tool(
            "BROWSER_TOOL_FETCH_WEBPAGE",
            {"format": format, "wait": 1000},
        )
        if error:
            return "", error

        content = self._extract_content(result)
        if format == "markdown":
            self._last_page_content = content
        else:
            self._last_page_html = content
        return content, None

    def _extract_content(self, result: dict[str, Any]) -> str:
        """Extract content from tool result, handling nested data."""
        data = result.get("data", {})
        if isinstance(data, dict) and "data" in data:
            data = data["data"]
        if isinstance(data, dict):
            return data.get("content", data.get("pageSnapshot", ""))
        return str(data) if data else ""

    def click(
        self,
        target: ElementTarget,
        strategy: ExecutionStrategy = ExecutionStrategy.HYBRID,
    ) -> TacticalResult:
        """Click on an element.

        Args:
            target: Element to click
            strategy: Execution strategy

        Returns:
            TacticalResult
        """
        logger.info(f"Clicking: {target.name}")

        if strategy == ExecutionStrategy.HYBRID:
            result = self._try_explicit_click(target)
            if result.success:
                return result
            logger.debug(f"Explicit click failed, trying AI: {result.error}")
            return self._try_ai_click(target)
        elif strategy == ExecutionStrategy.EXPLICIT_ONLY:
            return self._try_explicit_click(target)
        elif strategy == ExecutionStrategy.AI_ONLY:
            return self._try_ai_click(target)
        else:  # ADAPTIVE
            return self._adaptive_click(target)

    def _try_explicit_click(self, target: ElementTarget) -> TacticalResult:
        """Try to click using explicit MOUSE_CLICK."""
        # Get page content for resolution
        if not self._last_page_content:
            self.fetch_page("markdown")
        if not self._last_page_html:
            self.fetch_page("html")

        # Resolve element
        resolved = self._resolver.resolve(
            target,
            self._last_page_content or "",
            self._last_page_html,
        )

        if not resolved.found or resolved.method == ResolutionMethod.AI_ASSISTED:
            return TacticalResult(
                success=False,
                method="explicit",
                error="Could not resolve element selector",
            )

        # Execute click
        result, error = self._execute_tool(
            "BROWSER_TOOL_MOUSE_CLICK",
            {"selector": resolved.selector},
        )

        if error:
            return TacticalResult(success=False, method="explicit", error=error)

        # Wait after action
        time.sleep(target.wait_after_action)

        return TacticalResult(
            success=True,
            method="explicit",
            data={"selector": resolved.selector, "resolution": resolved.method.value},
        )

    def _try_ai_click(self, target: ElementTarget) -> TacticalResult:
        """Try to click using AI-assisted PERFORM_WEB_TASK."""
        prompt = self._resolver.build_interaction_prompt(target, "click")

        result, error = self._execute_tool(
            "BROWSER_TOOL_PERFORM_WEB_TASK",
            {"prompt": prompt},
        )

        if error:
            return TacticalResult(success=False, method="ai_assisted", error=error)

        # Wait after action
        time.sleep(target.wait_after_action)

        return TacticalResult(
            success=True,
            method="ai_assisted",
            data={"prompt": prompt},
        )

    def _adaptive_click(self, target: ElementTarget) -> TacticalResult:
        """Choose click strategy based on target complexity."""
        # Use explicit if we have a selector, AI for complex targets
        if target.css_selector:
            return self._try_explicit_click(target)
        return self._try_ai_click(target)

    def fill_field(
        self,
        target: ElementTarget,
        value: str,
        strategy: ExecutionStrategy = ExecutionStrategy.HYBRID,
        clear_first: bool = True,
    ) -> TacticalResult:
        """Fill a form field with a value.

        Args:
            target: Element target
            value: Value to enter
            strategy: Execution strategy
            clear_first: Whether to clear existing content first

        Returns:
            TacticalResult
        """
        logger.info(f"Filling field: {target.name} = {value[:50]}...")

        if strategy == ExecutionStrategy.HYBRID:
            result = self._try_explicit_fill(target, value, clear_first)
            if result.success:
                return result
            logger.debug(f"Explicit fill failed, trying AI: {result.error}")
            return self._try_ai_fill(target, value)
        elif strategy == ExecutionStrategy.EXPLICIT_ONLY:
            return self._try_explicit_fill(target, value, clear_first)
        elif strategy == ExecutionStrategy.AI_ONLY:
            return self._try_ai_fill(target, value)
        else:  # ADAPTIVE
            return self._adaptive_fill(target, value, clear_first)

    def _try_explicit_fill(
        self, target: ElementTarget, value: str, clear_first: bool
    ) -> TacticalResult:
        """Try to fill using explicit MOUSE_CLICK + TYPE_TEXT."""
        # First click to focus
        click_result = self._try_explicit_click(target)
        if not click_result.success:
            return TacticalResult(
                success=False,
                method="explicit",
                error=f"Failed to click field: {click_result.error}",
            )

        # Clear existing content if requested
        if clear_first:
            self._execute_tool(
                "BROWSER_TOOL_KEYBOARD_SHORTCUT",
                {"keys": ["Control", "a"]},
            )
            time.sleep(0.1)

        # Type the value
        result, error = self._execute_tool(
            "BROWSER_TOOL_TYPE_TEXT",
            {"text": value, "delay": 10},  # Small delay for natural typing
        )

        if error:
            return TacticalResult(success=False, method="explicit", error=error)

        # Wait after action
        time.sleep(target.wait_after_action)

        return TacticalResult(
            success=True,
            method="explicit",
            data={"value": value, "cleared": clear_first},
        )

    def _try_ai_fill(self, target: ElementTarget, value: str) -> TacticalResult:
        """Try to fill using AI-assisted PERFORM_WEB_TASK."""
        prompt = self._resolver.build_interaction_prompt(target, "type", value)

        result, error = self._execute_tool(
            "BROWSER_TOOL_PERFORM_WEB_TASK",
            {"prompt": prompt},
        )

        if error:
            return TacticalResult(success=False, method="ai_assisted", error=error)

        # Wait after action
        time.sleep(target.wait_after_action)

        return TacticalResult(
            success=True,
            method="ai_assisted",
            data={"prompt": prompt, "value": value},
        )

    def _adaptive_fill(
        self, target: ElementTarget, value: str, clear_first: bool
    ) -> TacticalResult:
        """Choose fill strategy based on target and value complexity."""
        # Use AI for complex widgets (date pickers, rich text editors)
        complex_keywords = ["date", "time", "calendar", "picker", "editor", "rich"]
        is_complex = any(
            kw in target.name.lower() or kw in (target.ai_prompt or "").lower()
            for kw in complex_keywords
        )

        if is_complex or not target.css_selector:
            return self._try_ai_fill(target, value)
        return self._try_explicit_fill(target, value, clear_first)

    def navigate(self, url: str, force_new_session: bool = False) -> TacticalResult:
        """Navigate to a URL.

        Args:
            url: URL to navigate to
            force_new_session: Whether to force a new browser session

        Returns:
            TacticalResult
        """
        logger.info(f"Navigating to: {url}")

        result, error = self._execute_tool(
            "BROWSER_TOOL_NAVIGATE",
            {"url": url, "forceNewSession": force_new_session},
        )

        if error:
            return TacticalResult(success=False, method="navigate", error=error)

        # Extract session info
        data = result.get("data", {})
        if isinstance(data, dict) and "data" in data:
            data = data["data"]

        session_id = data.get("sessionId") if isinstance(data, dict) else None
        page_url = data.get("navigatedUrl", url) if isinstance(data, dict) else url

        # Clear cached page content
        self._last_page_content = None
        self._last_page_html = None

        return TacticalResult(
            success=True,
            method="navigate",
            data={"session_id": session_id, "url": page_url},
        )

    def take_screenshot(self) -> TacticalResult:
        """Take a screenshot of the current page.

        Note: This must be called alone, not with other tools.

        Returns:
            TacticalResult with screenshot URL in data
        """
        logger.info("Taking screenshot")

        result, error = self._execute_tool("BROWSER_TOOL_TAKE_SCREENSHOT", {})

        if error:
            return TacticalResult(success=False, method="screenshot", error=error)

        data = result.get("data", {})
        if isinstance(data, dict) and "data" in data:
            data = data["data"]

        screenshot_url = None
        if isinstance(data, dict):
            screenshot_url = data.get("url", data.get("screenshotUrl"))

        return TacticalResult(
            success=True,
            method="screenshot",
            data={"screenshot_url": screenshot_url},
        )

    def scroll(self, direction: str = "down", amount: int = 400) -> TacticalResult:
        """Scroll the page.

        Args:
            direction: "up" or "down"
            amount: Pixels to scroll

        Returns:
            TacticalResult
        """
        delta_y = amount if direction == "down" else -amount

        result, error = self._execute_tool(
            "BROWSER_TOOL_SCROLL",
            {"deltaY": delta_y, "x": 640, "y": 360},
        )

        if error:
            return TacticalResult(success=False, method="scroll", error=error)

        return TacticalResult(success=True, method="scroll")

    def keyboard_shortcut(self, keys: list[str]) -> TacticalResult:
        """Execute a keyboard shortcut.

        Args:
            keys: List of keys (e.g., ["Control", "a"] for Ctrl+A)

        Returns:
            TacticalResult
        """
        result, error = self._execute_tool(
            "BROWSER_TOOL_KEYBOARD_SHORTCUT",
            {"keys": keys},
        )

        if error:
            return TacticalResult(success=False, method="keyboard", error=error)

        return TacticalResult(success=True, method="keyboard", data={"keys": keys})

    def perform_task(self, prompt: str, max_steps: int = 50) -> TacticalResult:
        """Perform a complex task using AI-assisted automation.

        Args:
            prompt: Natural language task description
            max_steps: Maximum steps for the AI agent

        Returns:
            TacticalResult
        """
        logger.info(f"AI task: {prompt[:100]}...")

        result, error = self._execute_tool(
            "BROWSER_TOOL_PERFORM_WEB_TASK",
            {"prompt": prompt},
        )

        if error:
            return TacticalResult(success=False, method="ai_task", error=error)

        return TacticalResult(
            success=True,
            method="ai_task",
            data={"prompt": prompt},
        )

    def verify_field_value(
        self, target: ElementTarget, expected_value: str
    ) -> TacticalResult:
        """Verify a field contains the expected value.

        Args:
            target: Element target
            expected_value: Value to verify

        Returns:
            TacticalResult with verified=True if value matches
        """
        content, error = self.fetch_page("markdown")
        if error:
            return TacticalResult(
                success=False, method="verify", error=error, verified=False
            )

        # Check if value appears in page content
        value_found = expected_value.lower() in content.lower()

        return TacticalResult(
            success=True,
            method="verify",
            verified=value_found,
            page_content=content,
            data={"expected": expected_value, "found": value_found},
        )
