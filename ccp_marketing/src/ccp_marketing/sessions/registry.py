"""Multi-tenant session registry for browser automation."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from ccp_marketing.sessions.storage import MemorySessionStorage, SessionStorage

logger = logging.getLogger(__name__)


class SessionStatus(str, Enum):
    """Status of a browser session."""

    WARM = "warm"  # Active, authenticated, ready to use
    COLD = "cold"  # Never initialized or expired
    NEEDS_AUTH = "needs_auth"  # Authentication required (login page detected)
    PAUSED_2FA = "paused_2fa"  # Waiting for manual 2FA completion
    EXPIRED = "expired"  # Session timed out

    @property
    def is_usable(self) -> bool:
        """Check if session can be used for automation."""
        return self == SessionStatus.WARM


@dataclass
class TenantSession:
    """Browser session for a specific tenant and platform.

    Attributes:
        tenant_id: Unique identifier for the tenant/organization
        platform: Platform name (luma, meetup, partiful)
        session_id: Rube browser session ID (from BROWSER_TOOL_NAVIGATE)
        status: Current session status
        last_used: Timestamp of last successful use
        auth_expires: When authentication is expected to expire
        created_at: When the session was first created
        cookies: Cached authentication state (optional)
        last_url: Last known URL the browser was on
        error_message: Last error message (if status is error state)
        two_fa_prompt: Instructions for user if awaiting 2FA
    """

    tenant_id: str
    platform: str
    session_id: str | None = None
    status: SessionStatus = SessionStatus.COLD
    last_used: datetime | None = None
    auth_expires: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    cookies: dict[str, Any] | None = None
    last_url: str | None = None
    error_message: str | None = None
    two_fa_prompt: str | None = None

    @property
    def is_expired(self) -> bool:
        """Check if the session has expired based on auth_expires."""
        if self.auth_expires is None:
            return False
        return datetime.utcnow() > self.auth_expires

    @property
    def is_stale(self) -> bool:
        """Check if session hasn't been used recently (24 hours)."""
        if self.last_used is None:
            return True
        stale_threshold = datetime.utcnow() - timedelta(hours=24)
        return self.last_used < stale_threshold

    def mark_used(self) -> None:
        """Update last_used timestamp."""
        self.last_used = datetime.utcnow()

    def __str__(self) -> str:
        return f"TenantSession({self.tenant_id}:{self.platform}, status={self.status.value})"


class SessionRegistry:
    """Manages browser sessions across tenants and platforms.

    Provides session lifecycle management including:
    - Creating and warming sessions
    - Tracking authentication state
    - Handling 2FA pause/resume
    - Session expiration and cleanup

    Example:
        registry = SessionRegistry()

        # Get or create session
        session = registry.get_or_create_session("org-acme", "luma")

        # After successful login
        registry.mark_warm(session, session_id="browser-123")

        # When 2FA is detected
        registry.mark_paused_2fa(session, "Enter code from authenticator app")

        # After user completes 2FA
        session = registry.resume_after_2fa("org-acme", "luma")
    """

    # Default session expiry (1 week for warm sessions)
    DEFAULT_SESSION_TTL = timedelta(days=7)

    def __init__(self, storage: SessionStorage | None = None) -> None:
        """Initialize the session registry.

        Args:
            storage: Storage backend for session persistence.
                    Defaults to in-memory storage.
        """
        self._storage = storage or MemorySessionStorage()
        self._cache: dict[str, TenantSession] = {}

    def _make_key(self, tenant_id: str, platform: str) -> str:
        """Create cache key for tenant+platform."""
        return f"{tenant_id}:{platform}"

    def _load_session(self, tenant_id: str, platform: str) -> TenantSession | None:
        """Load session from storage, converting raw data to TenantSession."""
        data = self._storage.load(tenant_id, platform)
        if data is None:
            return None

        # Parse datetime fields
        for field_name in ["last_used", "auth_expires", "created_at"]:
            if data.get(field_name) and isinstance(data[field_name], str):
                try:
                    data[field_name] = datetime.fromisoformat(data[field_name])
                except ValueError:
                    data[field_name] = None

        # Parse status enum
        if isinstance(data.get("status"), str):
            try:
                data["status"] = SessionStatus(data["status"])
            except ValueError:
                data["status"] = SessionStatus.COLD

        return TenantSession(**data)

    def get_session(self, tenant_id: str, platform: str) -> TenantSession | None:
        """Get existing session for tenant+platform.

        Args:
            tenant_id: Tenant identifier
            platform: Platform name (luma, meetup, partiful)

        Returns:
            TenantSession if found, None otherwise
        """
        key = self._make_key(tenant_id, platform)

        # Check cache first
        if key in self._cache:
            return self._cache[key]

        # Load from storage
        session = self._load_session(tenant_id, platform)
        if session:
            self._cache[key] = session
        return session

    def get_or_create_session(
        self, tenant_id: str, platform: str
    ) -> TenantSession:
        """Get existing session or create a new cold session.

        Args:
            tenant_id: Tenant identifier
            platform: Platform name

        Returns:
            TenantSession (existing or newly created)
        """
        session = self.get_session(tenant_id, platform)
        if session is None:
            session = TenantSession(
                tenant_id=tenant_id,
                platform=platform,
                status=SessionStatus.COLD,
            )
            self._save_session(session)
            logger.info(f"Created new session: {session}")
        return session

    def _save_session(self, session: TenantSession) -> None:
        """Save session to both cache and storage."""
        key = self._make_key(session.tenant_id, session.platform)
        self._cache[key] = session
        self._storage.save(session)

    def mark_warm(
        self,
        session: TenantSession,
        session_id: str,
        auth_expires: datetime | None = None,
    ) -> TenantSession:
        """Mark session as warm (authenticated and ready).

        Args:
            session: The session to update
            session_id: Browser session ID from BROWSER_TOOL_NAVIGATE
            auth_expires: When auth is expected to expire (default: 7 days)

        Returns:
            Updated session
        """
        session.session_id = session_id
        session.status = SessionStatus.WARM
        session.mark_used()
        session.auth_expires = auth_expires or (
            datetime.utcnow() + self.DEFAULT_SESSION_TTL
        )
        session.error_message = None
        session.two_fa_prompt = None
        self._save_session(session)
        logger.info(f"Session marked warm: {session}")
        return session

    def mark_needs_auth(
        self, session: TenantSession, reason: str = "Login required"
    ) -> TenantSession:
        """Mark session as needing authentication.

        Args:
            session: The session to update
            reason: Human-readable reason for auth requirement

        Returns:
            Updated session
        """
        session.status = SessionStatus.NEEDS_AUTH
        session.error_message = reason
        self._save_session(session)
        logger.warning(f"Session needs auth: {session} - {reason}")
        return session

    def mark_paused_2fa(
        self, session: TenantSession, prompt: str
    ) -> TenantSession:
        """Pause session waiting for manual 2FA completion.

        Args:
            session: The session to update
            prompt: Instructions for user to complete 2FA

        Returns:
            Updated session
        """
        session.status = SessionStatus.PAUSED_2FA
        session.two_fa_prompt = prompt
        self._save_session(session)
        logger.info(f"Session paused for 2FA: {session}")
        return session

    def resume_after_2fa(
        self, tenant_id: str, platform: str
    ) -> TenantSession | None:
        """Resume session after user completes 2FA.

        The session status will be set to WARM if it was previously PAUSED_2FA.
        The workflow should re-verify authentication after calling this.

        Args:
            tenant_id: Tenant identifier
            platform: Platform name

        Returns:
            Updated session, or None if session not found
        """
        session = self.get_session(tenant_id, platform)
        if session is None:
            logger.error(f"Cannot resume - session not found: {tenant_id}:{platform}")
            return None

        if session.status != SessionStatus.PAUSED_2FA:
            logger.warning(
                f"Resume called on non-paused session: {session.status.value}"
            )

        # Don't automatically mark as WARM - let workflow verify auth first
        session.two_fa_prompt = None
        session.mark_used()
        self._save_session(session)
        logger.info(f"Session resumed after 2FA: {session}")
        return session

    def mark_expired(self, session: TenantSession) -> TenantSession:
        """Mark session as expired.

        Args:
            session: The session to update

        Returns:
            Updated session
        """
        session.status = SessionStatus.EXPIRED
        session.session_id = None
        self._save_session(session)
        logger.info(f"Session marked expired: {session}")
        return session

    def update_last_url(self, session: TenantSession, url: str) -> TenantSession:
        """Update the last known URL for the session.

        Args:
            session: The session to update
            url: Current browser URL

        Returns:
            Updated session
        """
        session.last_url = url
        session.mark_used()
        self._save_session(session)
        return session

    def delete_session(self, tenant_id: str, platform: str) -> None:
        """Delete a session completely.

        Args:
            tenant_id: Tenant identifier
            platform: Platform name
        """
        key = self._make_key(tenant_id, platform)
        if key in self._cache:
            del self._cache[key]
        self._storage.delete(tenant_id, platform)
        logger.info(f"Deleted session: {tenant_id}:{platform}")

    def list_sessions(
        self, tenant_id: str | None = None, status: SessionStatus | None = None
    ) -> list[TenantSession]:
        """List all sessions, optionally filtered.

        Args:
            tenant_id: Filter by tenant (None for all)
            status: Filter by status (None for all)

        Returns:
            List of matching sessions
        """
        sessions_data = self._storage.list_sessions(tenant_id)
        sessions = []

        for data in sessions_data:
            # Parse datetime fields
            for field_name in ["last_used", "auth_expires", "created_at"]:
                if data.get(field_name) and isinstance(data[field_name], str):
                    try:
                        data[field_name] = datetime.fromisoformat(data[field_name])
                    except ValueError:
                        data[field_name] = None

            # Parse status enum
            if isinstance(data.get("status"), str):
                try:
                    data["status"] = SessionStatus(data["status"])
                except ValueError:
                    data["status"] = SessionStatus.COLD

            session = TenantSession(**data)
            if status is None or session.status == status:
                sessions.append(session)

        return sessions

    def cleanup_expired_sessions(self) -> int:
        """Remove all expired sessions.

        Returns:
            Number of sessions removed
        """
        sessions = self.list_sessions()
        removed = 0

        for session in sessions:
            if session.is_expired or session.status == SessionStatus.EXPIRED:
                self.delete_session(session.tenant_id, session.platform)
                removed += 1

        if removed > 0:
            logger.info(f"Cleaned up {removed} expired sessions")
        return removed
