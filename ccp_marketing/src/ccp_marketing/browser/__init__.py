"""Browser tactical execution layer for hybrid automation."""

from ccp_marketing.browser.element_resolver import (
    ElementResolver,
    ElementTarget,
    ResolvedElement,
    ResolutionMethod,
)
from ccp_marketing.browser.tactical import (
    ExecutionStrategy,
    TacticalExecutor,
    TacticalResult,
)
from ccp_marketing.browser.verification import (
    PageVerifier,
    VerificationResult,
)

__all__ = [
    # Element targeting
    "ElementTarget",
    "ElementResolver",
    "ResolvedElement",
    "ResolutionMethod",
    # Tactical execution
    "TacticalExecutor",
    "TacticalResult",
    "ExecutionStrategy",
    # Verification
    "PageVerifier",
    "VerificationResult",
]
