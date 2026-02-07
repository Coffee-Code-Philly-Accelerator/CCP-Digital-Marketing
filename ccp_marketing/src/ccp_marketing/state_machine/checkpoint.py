"""Checkpoint system for state machine resume capability."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ccp_marketing.state_machine.states import EventState

logger = logging.getLogger(__name__)


@dataclass
class Checkpoint:
    """Snapshot of state machine execution for resume capability.

    Stores all necessary state to resume a workflow from any point,
    enabling recovery from failures, 2FA pauses, or session interruptions.

    Attributes:
        tenant_id: Tenant/organization identifier
        platform: Platform being processed (luma, meetup, partiful)
        event_data: Original event creation input data
        current_state: State when checkpoint was created
        completed_states: States that have been successfully completed
        state_data: Data collected during execution (URLs, IDs, etc.)
        session_id: Browser session ID
        timestamp: When checkpoint was created
        checkpoint_id: Unique identifier for this checkpoint
        error_info: Error details if checkpoint was created due to failure
    """

    tenant_id: str
    platform: str
    event_data: dict[str, Any]
    current_state: EventState
    completed_states: list[EventState] = field(default_factory=list)
    state_data: dict[str, Any] = field(default_factory=dict)
    session_id: str | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    checkpoint_id: str = field(default_factory=lambda: "")
    error_info: str | None = None

    def __post_init__(self) -> None:
        """Generate checkpoint_id if not provided."""
        if not self.checkpoint_id:
            ts = self.timestamp.strftime("%Y%m%d_%H%M%S")
            self.checkpoint_id = f"{self.tenant_id}_{self.platform}_{ts}"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        # Convert enum values
        data["current_state"] = self.current_state.value
        data["completed_states"] = [s.value for s in self.completed_states]
        # Convert datetime
        data["timestamp"] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Checkpoint:
        """Create Checkpoint from dictionary."""
        # Parse state enums
        data["current_state"] = EventState(data["current_state"])
        data["completed_states"] = [
            EventState(s) for s in data.get("completed_states", [])
        ]
        # Parse timestamp
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)

    @property
    def can_resume(self) -> bool:
        """Check if this checkpoint can be resumed."""
        return not self.current_state.is_terminal

    @property
    def progress_percentage(self) -> float:
        """Calculate completion percentage based on completed states."""
        from ccp_marketing.state_machine.states import STATE_FLOW

        total_states = len([s for s in STATE_FLOW if not s.is_terminal])
        completed = len(self.completed_states)
        return (completed / total_states) * 100 if total_states > 0 else 0

    def __str__(self) -> str:
        return (
            f"Checkpoint({self.checkpoint_id}, "
            f"state={self.current_state.value}, "
            f"progress={self.progress_percentage:.0f}%)"
        )


class CheckpointStorage:
    """File-based checkpoint storage."""

    def __init__(self, storage_dir: Path | str) -> None:
        """Initialize checkpoint storage.

        Args:
            storage_dir: Directory for storing checkpoint files
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Using checkpoint storage at: {self.storage_dir}")

    def _get_path(self, tenant_id: str, platform: str) -> Path:
        """Get file path for a checkpoint."""
        safe_tenant = tenant_id.replace("/", "_").replace(":", "_")
        safe_platform = platform.replace("/", "_").replace(":", "_")
        return self.storage_dir / f"checkpoint_{safe_tenant}_{safe_platform}.json"

    def save(self, checkpoint: Checkpoint) -> None:
        """Save checkpoint to file."""
        path = self._get_path(checkpoint.tenant_id, checkpoint.platform)
        with open(path, "w") as f:
            json.dump(checkpoint.to_dict(), f, indent=2, default=str)
        logger.debug(f"Saved checkpoint: {checkpoint}")

    def load(self, tenant_id: str, platform: str) -> Checkpoint | None:
        """Load checkpoint from file."""
        path = self._get_path(tenant_id, platform)
        if not path.exists():
            return None
        try:
            with open(path) as f:
                data = json.load(f)
            checkpoint = Checkpoint.from_dict(data)
            logger.debug(f"Loaded checkpoint: {checkpoint}")
            return checkpoint
        except (json.JSONDecodeError, OSError, KeyError, ValueError) as e:
            logger.warning(f"Failed to load checkpoint from {path}: {e}")
            return None

    def delete(self, tenant_id: str, platform: str) -> None:
        """Delete checkpoint file."""
        path = self._get_path(tenant_id, platform)
        if path.exists():
            path.unlink()
            logger.debug(f"Deleted checkpoint: {tenant_id}:{platform}")

    def list_checkpoints(self, tenant_id: str | None = None) -> list[Checkpoint]:
        """List all checkpoints, optionally filtered by tenant."""
        checkpoints = []
        for path in self.storage_dir.glob("checkpoint_*.json"):
            try:
                with open(path) as f:
                    data = json.load(f)
                checkpoint = Checkpoint.from_dict(data)
                if tenant_id is None or checkpoint.tenant_id == tenant_id:
                    checkpoints.append(checkpoint)
            except (json.JSONDecodeError, OSError, KeyError, ValueError):
                continue
        return checkpoints


class CheckpointManager:
    """Manages checkpoints for state machine workflows.

    Provides high-level operations for saving, loading, and resuming
    from checkpoints during event creation workflows.

    Example:
        manager = CheckpointManager()

        # Save checkpoint during workflow
        checkpoint = manager.create_checkpoint(
            tenant_id="org-acme",
            platform="luma",
            event_data={"title": "Event"},
            current_state=EventState.FILL_DATE,
            completed_states=[EventState.INIT, EventState.NAVIGATE, EventState.FILL_TITLE],
            state_data={"title_filled": True},
            session_id="browser-123",
        )
        manager.save(checkpoint)

        # Later, resume from checkpoint
        checkpoint = manager.load("org-acme", "luma")
        if checkpoint and checkpoint.can_resume:
            # Reconstruct state machine and continue
            pass
    """

    def __init__(self, storage_dir: Path | str | None = None) -> None:
        """Initialize checkpoint manager.

        Args:
            storage_dir: Directory for checkpoint files.
                        Defaults to ~/.ccp_marketing/checkpoints
        """
        if storage_dir is None:
            storage_dir = Path.home() / ".ccp_marketing" / "checkpoints"
        self._storage = CheckpointStorage(storage_dir)

    def create_checkpoint(
        self,
        tenant_id: str,
        platform: str,
        event_data: dict[str, Any],
        current_state: EventState,
        completed_states: list[EventState] | None = None,
        state_data: dict[str, Any] | None = None,
        session_id: str | None = None,
        error_info: str | None = None,
    ) -> Checkpoint:
        """Create a new checkpoint.

        Args:
            tenant_id: Tenant/organization identifier
            platform: Platform name
            event_data: Original event creation input
            current_state: Current state when checkpoint is created
            completed_states: States successfully completed
            state_data: Additional data collected during execution
            session_id: Browser session ID
            error_info: Error details if applicable

        Returns:
            New Checkpoint instance
        """
        return Checkpoint(
            tenant_id=tenant_id,
            platform=platform,
            event_data=event_data,
            current_state=current_state,
            completed_states=completed_states or [],
            state_data=state_data or {},
            session_id=session_id,
            error_info=error_info,
        )

    def save(self, checkpoint: Checkpoint) -> None:
        """Save a checkpoint.

        Args:
            checkpoint: Checkpoint to save
        """
        self._storage.save(checkpoint)
        logger.info(f"Checkpoint saved: {checkpoint}")

    def load(self, tenant_id: str, platform: str) -> Checkpoint | None:
        """Load the most recent checkpoint for tenant+platform.

        Args:
            tenant_id: Tenant identifier
            platform: Platform name

        Returns:
            Checkpoint if found, None otherwise
        """
        return self._storage.load(tenant_id, platform)

    def clear(self, tenant_id: str, platform: str) -> None:
        """Clear checkpoint after successful completion.

        Args:
            tenant_id: Tenant identifier
            platform: Platform name
        """
        self._storage.delete(tenant_id, platform)
        logger.info(f"Checkpoint cleared: {tenant_id}:{platform}")

    def list_resumable(self, tenant_id: str | None = None) -> list[Checkpoint]:
        """List all checkpoints that can be resumed.

        Args:
            tenant_id: Filter by tenant (None for all)

        Returns:
            List of resumable checkpoints
        """
        all_checkpoints = self._storage.list_checkpoints(tenant_id)
        return [cp for cp in all_checkpoints if cp.can_resume]

    def get_resume_info(self, checkpoint: Checkpoint) -> dict[str, Any]:
        """Get human-readable resume information.

        Args:
            checkpoint: Checkpoint to describe

        Returns:
            Dictionary with resume information
        """
        return {
            "checkpoint_id": checkpoint.checkpoint_id,
            "tenant_id": checkpoint.tenant_id,
            "platform": checkpoint.platform,
            "current_state": checkpoint.current_state.value,
            "progress": f"{checkpoint.progress_percentage:.0f}%",
            "can_resume": checkpoint.can_resume,
            "timestamp": checkpoint.timestamp.isoformat(),
            "error_info": checkpoint.error_info,
            "event_title": checkpoint.event_data.get("title", "Unknown"),
        }
