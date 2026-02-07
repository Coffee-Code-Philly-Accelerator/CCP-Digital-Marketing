"""State machine for event creation workflows."""

from ccp_marketing.state_machine.checkpoint import (
    Checkpoint,
    CheckpointManager,
    CheckpointStorage,
)
from ccp_marketing.state_machine.machine import EventCreationStateMachine
from ccp_marketing.state_machine.states import (
    FEATURE_STATES,
    FILL_STATES,
    PAUSE_STATES,
    STATE_CONFIG,
    STATE_FLOW,
    STATE_FLOW_FULL,
    TERMINAL_STATES,
    EventState,
    StateConfig,
    get_next_state,
    get_state_config,
)

__all__ = [
    # Core state machine
    "EventState",
    "StateConfig",
    "STATE_CONFIG",
    "EventCreationStateMachine",
    # State sets
    "TERMINAL_STATES",
    "PAUSE_STATES",
    "FILL_STATES",
    "FEATURE_STATES",
    # State flows
    "STATE_FLOW",
    "STATE_FLOW_FULL",
    # Helpers
    "get_next_state",
    "get_state_config",
    # Checkpointing
    "Checkpoint",
    "CheckpointManager",
    "CheckpointStorage",
]
