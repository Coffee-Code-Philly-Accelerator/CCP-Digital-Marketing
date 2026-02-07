"""Multi-strategy element resolution for UI-change resilient targeting."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ResolutionMethod(str, Enum):
    """Method used to resolve an element."""

    CSS_SELECTOR = "css_selector"
    TEXT_ANCHOR = "text_anchor"
    ARIA = "aria"
    AI_ASSISTED = "ai_assisted"
    NONE = "none"


@dataclass
class ElementTarget:
    """Multi-strategy element targeting specification.

    Provides multiple strategies for finding an element, tried in order:
    1. CSS selector (most reliable if available)
    2. Text anchor (find by visible text)
    3. ARIA attributes (accessibility-based)
    4. AI-assisted fallback (PERFORM_WEB_TASK)

    Example:
        title_target = ElementTarget(
            name="event_title",
            css_selector="input[name='title']",
            text_anchor="Event Title",
            aria_label="event title",
            ai_prompt="Click on the event title input field",
            near_text="What's your event called?",
        )
    """

    name: str  # Human-readable name for logging
    css_selector: str | None = None  # Preferred CSS selector
    text_anchor: str | None = None  # Text content to find
    aria_label: str | None = None  # ARIA label attribute
    aria_role: str | None = None  # ARIA role attribute
    ai_prompt: str | None = None  # Fallback AI prompt for PERFORM_WEB_TASK
    near_text: str | None = None  # Text that appears near the element
    position_hint: str | None = None  # Spatial hint ("below title", "top right")
    placeholder: str | None = None  # Input placeholder text
    input_type: str | None = None  # Input type (text, email, date, etc.)
    is_required: bool = True  # Whether the element must be found
    wait_after_action: float = 0.5  # Seconds to wait after interacting

    def __str__(self) -> str:
        return f"ElementTarget({self.name})"


@dataclass
class ResolvedElement:
    """Result of element resolution.

    Attributes:
        found: Whether the element was successfully resolved
        method: Resolution method that succeeded
        selector: CSS selector to use for interaction
        confidence: Confidence level (0-1) in the resolution
        context: Additional context about the resolution
    """

    found: bool
    method: ResolutionMethod
    selector: str | None = None
    confidence: float = 0.0
    context: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        if self.found:
            return f"ResolvedElement(method={self.method.value}, selector={self.selector})"
        return "ResolvedElement(not found)"


class ElementResolver:
    """Resolves element targets using multiple strategies.

    Tries strategies in order until one succeeds:
    1. CSS selector (if provided)
    2. Text anchor (search for text in page content)
    3. ARIA attributes
    4. AI-assisted (returns prompt for PERFORM_WEB_TASK)

    Example:
        resolver = ElementResolver()

        # Resolve with page content
        page_content = "... Event Title ... Description ..."
        result = resolver.resolve(title_target, page_content)

        if result.found:
            if result.method == ResolutionMethod.AI_ASSISTED:
                # Use PERFORM_WEB_TASK with the AI prompt
                pass
            else:
                # Use MOUSE_CLICK with result.selector
                pass
    """

    def __init__(self) -> None:
        """Initialize the element resolver."""
        self._strategies = [
            self._try_css_selector,
            self._try_text_anchor,
            self._try_aria,
            self._try_placeholder,
            self._try_ai_assisted,
        ]

    def resolve(
        self,
        target: ElementTarget,
        page_content: str,
        page_html: str | None = None,
    ) -> ResolvedElement:
        """Resolve an element target using multiple strategies.

        Args:
            target: Element target specification
            page_content: Page content (markdown format from FETCH_WEBPAGE)
            page_html: Optional raw HTML for more precise matching

        Returns:
            ResolvedElement with resolution result
        """
        for strategy in self._strategies:
            result = strategy(target, page_content, page_html)
            if result.found:
                logger.debug(f"Resolved {target.name} via {result.method.value}")
                return result

        logger.warning(f"Failed to resolve element: {target.name}")
        return ResolvedElement(found=False, method=ResolutionMethod.NONE)

    def _try_css_selector(
        self,
        target: ElementTarget,
        page_content: str,
        page_html: str | None,
    ) -> ResolvedElement:
        """Try to use the provided CSS selector."""
        if not target.css_selector:
            return ResolvedElement(found=False, method=ResolutionMethod.CSS_SELECTOR)

        # If we have HTML, check if selector likely exists
        if page_html:
            # Simple heuristic: check if key parts of selector appear in HTML
            selector_parts = re.findall(r'[\w-]+', target.css_selector)
            matches = sum(1 for part in selector_parts if part in page_html)
            confidence = matches / len(selector_parts) if selector_parts else 0

            if confidence > 0.5:
                return ResolvedElement(
                    found=True,
                    method=ResolutionMethod.CSS_SELECTOR,
                    selector=target.css_selector,
                    confidence=confidence,
                )

        # Without HTML, assume selector is valid if provided
        return ResolvedElement(
            found=True,
            method=ResolutionMethod.CSS_SELECTOR,
            selector=target.css_selector,
            confidence=0.7,  # Lower confidence without HTML verification
        )

    def _try_text_anchor(
        self,
        target: ElementTarget,
        page_content: str,
        page_html: str | None,
    ) -> ResolvedElement:
        """Try to find element by text anchor."""
        if not target.text_anchor:
            return ResolvedElement(found=False, method=ResolutionMethod.TEXT_ANCHOR)

        content_lower = page_content.lower()
        anchor_lower = target.text_anchor.lower()

        if anchor_lower in content_lower:
            # Generate selector based on text content
            # This is a heuristic - actual selector may need refinement
            selector = f':has-text("{target.text_anchor}")'
            if target.input_type:
                selector = f'input[type="{target.input_type}"]{selector}'

            return ResolvedElement(
                found=True,
                method=ResolutionMethod.TEXT_ANCHOR,
                selector=selector,
                confidence=0.6,
                context={"text_found": target.text_anchor},
            )

        return ResolvedElement(found=False, method=ResolutionMethod.TEXT_ANCHOR)

    def _try_aria(
        self,
        target: ElementTarget,
        page_content: str,
        page_html: str | None,
    ) -> ResolvedElement:
        """Try to find element by ARIA attributes."""
        if not target.aria_label and not target.aria_role:
            return ResolvedElement(found=False, method=ResolutionMethod.ARIA)

        if page_html:
            # Check for aria-label in HTML
            if target.aria_label:
                aria_pattern = f'aria-label="{target.aria_label}"'
                if aria_pattern.lower() in page_html.lower():
                    selector = f'[aria-label="{target.aria_label}"]'
                    return ResolvedElement(
                        found=True,
                        method=ResolutionMethod.ARIA,
                        selector=selector,
                        confidence=0.8,
                    )

            # Check for role
            if target.aria_role:
                role_pattern = f'role="{target.aria_role}"'
                if role_pattern.lower() in page_html.lower():
                    selector = f'[role="{target.aria_role}"]'
                    if target.aria_label:
                        selector += f'[aria-label="{target.aria_label}"]'
                    return ResolvedElement(
                        found=True,
                        method=ResolutionMethod.ARIA,
                        selector=selector,
                        confidence=0.7,
                    )

        return ResolvedElement(found=False, method=ResolutionMethod.ARIA)

    def _try_placeholder(
        self,
        target: ElementTarget,
        page_content: str,
        page_html: str | None,
    ) -> ResolvedElement:
        """Try to find element by placeholder text."""
        if not target.placeholder:
            return ResolvedElement(found=False, method=ResolutionMethod.TEXT_ANCHOR)

        if page_html and target.placeholder.lower() in page_html.lower():
            selector = f'input[placeholder*="{target.placeholder}"]'
            return ResolvedElement(
                found=True,
                method=ResolutionMethod.TEXT_ANCHOR,
                selector=selector,
                confidence=0.75,
                context={"placeholder": target.placeholder},
            )

        return ResolvedElement(found=False, method=ResolutionMethod.TEXT_ANCHOR)

    def _try_ai_assisted(
        self,
        target: ElementTarget,
        page_content: str,
        page_html: str | None,
    ) -> ResolvedElement:
        """Fall back to AI-assisted resolution."""
        if not target.ai_prompt:
            return ResolvedElement(found=False, method=ResolutionMethod.AI_ASSISTED)

        # Always succeed for AI - it will attempt with PERFORM_WEB_TASK
        return ResolvedElement(
            found=True,
            method=ResolutionMethod.AI_ASSISTED,
            selector=None,  # No selector - use AI prompt instead
            confidence=0.5,
            context={"ai_prompt": target.ai_prompt},
        )

    def build_interaction_prompt(
        self,
        target: ElementTarget,
        action: str,
        value: str | None = None,
    ) -> str:
        """Build a prompt for AI-assisted interaction.

        Args:
            target: Element target
            action: Action to perform (click, type, select)
            value: Value to enter (for type action)

        Returns:
            Prompt for PERFORM_WEB_TASK
        """
        parts = []

        # Start with the AI prompt if available
        if target.ai_prompt:
            parts.append(target.ai_prompt)
        else:
            parts.append(f"Find the {target.name} field")

        # Add context hints
        if target.near_text:
            parts.append(f"It should be near text that says '{target.near_text}'")
        if target.position_hint:
            parts.append(f"It should be located {target.position_hint}")

        # Add action
        if action == "click":
            parts.append("Click on it")
        elif action == "type" and value:
            parts.append(f"Clear any existing text and type exactly: {value}")
        elif action == "select" and value:
            parts.append(f"Select the option: {value}")

        return ". ".join(parts) + "."
