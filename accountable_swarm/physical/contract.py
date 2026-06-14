"""Safety-first physical-node contract.

The default physical path is trace-only. Nothing in this module moves hardware.
Future SO-101 or webcam adapters should implement this contract before adding
device-specific commands.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PhysicalNodeSafety:
    """Safety defaults for a physical edge node."""

    low_speed_mode: bool = True
    workspace_bounds_enabled: bool = True
    operator_armed: bool = False
    motion_enabled: bool = False
    emergency_stop_available: bool = True
    autonomous_setup_motion_allowed: bool = False

    def assert_safe_for_motion(self) -> None:
        if not self.low_speed_mode:
            raise RuntimeError("physical motion requires low_speed_mode")
        if not self.workspace_bounds_enabled:
            raise RuntimeError("physical motion requires workspace bounds")
        if not self.emergency_stop_available:
            raise RuntimeError("physical motion requires an emergency stop path")
        if self.autonomous_setup_motion_allowed:
            raise RuntimeError("autonomous setup motion must remain disabled")
        if not self.operator_armed or not self.motion_enabled:
            raise RuntimeError("physical motion requires explicit operator arming")


@dataclass(frozen=True)
class PhysicalAction:
    """Intent to apply to a physical device."""

    action_type: str
    payload: dict[str, Any]


class TraceOnlyActionSink:
    """Safe action sink that records intent but never moves hardware."""

    def __init__(self, safety: PhysicalNodeSafety | None = None) -> None:
        self.safety = safety or PhysicalNodeSafety()
        self.actions: list[PhysicalAction] = []

    def apply(self, action: PhysicalAction) -> PhysicalAction:
        if action.action_type != "hold":
            self.safety.assert_safe_for_motion()
        recorded = PhysicalAction(action_type=action.action_type, payload=deepcopy(action.payload))
        self.actions.append(recorded)
        return recorded
