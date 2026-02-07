"""Storage backends for session persistence."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ccp_marketing.sessions.registry import TenantSession

logger = logging.getLogger(__name__)


class SessionStorage(ABC):
    """Abstract base for session storage backends."""

    @abstractmethod
    def save(self, session: TenantSession) -> None:
        """Persist a session."""

    @abstractmethod
    def load(self, tenant_id: str, platform: str) -> dict[str, Any] | None:
        """Load session data. Returns None if not found."""

    @abstractmethod
    def delete(self, tenant_id: str, platform: str) -> None:
        """Delete a session."""

    @abstractmethod
    def list_sessions(self, tenant_id: str | None = None) -> list[dict[str, Any]]:
        """List all sessions, optionally filtered by tenant."""

    def _make_key(self, tenant_id: str, platform: str) -> str:
        """Create a unique key for tenant+platform."""
        return f"{tenant_id}:{platform}"


class MemorySessionStorage(SessionStorage):
    """In-memory session storage (for testing/single-instance use)."""

    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}

    def save(self, session: TenantSession) -> None:
        """Save session to memory."""
        key = self._make_key(session.tenant_id, session.platform)
        data = asdict(session)
        # Convert datetime to ISO string for consistency
        for field in ["last_used", "auth_expires", "created_at"]:
            if data.get(field) and isinstance(data[field], datetime):
                data[field] = data[field].isoformat()
        # Convert enum to string
        if hasattr(data.get("status"), "value"):
            data["status"] = data["status"].value
        self._sessions[key] = data
        logger.debug(f"Saved session to memory: {key}")

    def load(self, tenant_id: str, platform: str) -> dict[str, Any] | None:
        """Load session from memory."""
        key = self._make_key(tenant_id, platform)
        data = self._sessions.get(key)
        if data:
            logger.debug(f"Loaded session from memory: {key}")
        return data

    def delete(self, tenant_id: str, platform: str) -> None:
        """Delete session from memory."""
        key = self._make_key(tenant_id, platform)
        if key in self._sessions:
            del self._sessions[key]
            logger.debug(f"Deleted session from memory: {key}")

    def list_sessions(self, tenant_id: str | None = None) -> list[dict[str, Any]]:
        """List sessions in memory."""
        sessions = list(self._sessions.values())
        if tenant_id:
            sessions = [s for s in sessions if s.get("tenant_id") == tenant_id]
        return sessions


class FileSessionStorage(SessionStorage):
    """File-based session storage (JSON files per session)."""

    def __init__(self, storage_dir: Path | str) -> None:
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Using file session storage at: {self.storage_dir}")

    def _get_path(self, tenant_id: str, platform: str) -> Path:
        """Get file path for a session."""
        safe_tenant = tenant_id.replace("/", "_").replace(":", "_")
        safe_platform = platform.replace("/", "_").replace(":", "_")
        return self.storage_dir / f"{safe_tenant}_{safe_platform}.json"

    def save(self, session: TenantSession) -> None:
        """Save session to file."""
        path = self._get_path(session.tenant_id, session.platform)
        data = asdict(session)
        # Convert datetime to ISO string
        for field in ["last_used", "auth_expires", "created_at"]:
            if data.get(field) and isinstance(data[field], datetime):
                data[field] = data[field].isoformat()
        # Convert enum to string
        if hasattr(data.get("status"), "value"):
            data["status"] = data["status"].value
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        logger.debug(f"Saved session to file: {path}")

    def load(self, tenant_id: str, platform: str) -> dict[str, Any] | None:
        """Load session from file."""
        path = self._get_path(tenant_id, platform)
        if not path.exists():
            return None
        try:
            with open(path) as f:
                data = json.load(f)
            logger.debug(f"Loaded session from file: {path}")
            return data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load session from {path}: {e}")
            return None

    def delete(self, tenant_id: str, platform: str) -> None:
        """Delete session file."""
        path = self._get_path(tenant_id, platform)
        if path.exists():
            path.unlink()
            logger.debug(f"Deleted session file: {path}")

    def list_sessions(self, tenant_id: str | None = None) -> list[dict[str, Any]]:
        """List all session files."""
        sessions = []
        for path in self.storage_dir.glob("*.json"):
            try:
                with open(path) as f:
                    data = json.load(f)
                if tenant_id is None or data.get("tenant_id") == tenant_id:
                    sessions.append(data)
            except (json.JSONDecodeError, OSError):
                continue
        return sessions
