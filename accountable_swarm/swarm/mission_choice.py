"""Bounded Qwen mission choice for the hazard-to-formation demo path."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from accountable_swarm.trace.models import (
    DecisionTrace,
    PerceptionEvent,
    build_single_event_trace,
    reject_raw_floats,
)
from accountable_swarm.swarm.formations import SUPPORTED_FORMATIONS
from accountable_swarm.swarm.sim import GridPoint


FORMATION_MISSION_SCHEMA_VERSION = "formation-mission.v1"
FORMATION_MISSION_FIXTURE_MODEL_ID = "fixture-qwen-mission-choice"
SUPPORTED_FORMATION_MISSIONS = ("surround_hazard", "hold_position")
SUPPORTED_MISSION_RISKS = ("cautious", "balanced")
MISSION_RESPONSE_REQUIRED_KEYS = frozenset({"mission", "risk"})
MISSION_TO_FORMATION_FALLBACK = {
    "surround_hazard": "x",
    "hold_position": "line",
}


@dataclass(frozen=True)
class FormationMissionChoice:
    """Validated low-rate mission choice accepted from Qwen or a fixture."""

    mission: str
    risk: str

    def __post_init__(self) -> None:
        if not isinstance(self.mission, str):
            raise TypeError("mission must be a string")
        if self.mission not in SUPPORTED_FORMATION_MISSIONS:
            raise ValueError(f"unsupported formation mission: {self.mission}")
        if not isinstance(self.risk, str):
            raise TypeError("risk must be a string")
        if self.risk not in SUPPORTED_MISSION_RISKS:
            raise ValueError(f"unsupported mission risk: {self.risk}")

    def to_dict(self) -> dict[str, str]:
        return {"mission": self.mission, "risk": self.risk}

    def fallback_formation(self) -> str:
        return MISSION_TO_FORMATION_FALLBACK[self.mission]


def parse_formation_mission_response(response_text: str) -> FormationMissionChoice:
    """Parse a strict JSON mission choice response."""

    if not response_text.strip():
        raise ValueError("formation mission response must be non-empty")
    try:
        value = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise ValueError("formation mission response must be valid JSON") from exc
    reject_raw_floats(value)
    if not isinstance(value, dict):
        raise ValueError("formation mission response must be a JSON object")
    keys = frozenset(value)
    if keys != MISSION_RESPONSE_REQUIRED_KEYS:
        missing = sorted(MISSION_RESPONSE_REQUIRED_KEYS - keys)
        extra = sorted(keys - MISSION_RESPONSE_REQUIRED_KEYS)
        raise ValueError(
            f"formation mission response keys mismatch; missing={missing}; extra={extra}"
        )
    return FormationMissionChoice(
        mission=_expect_str(value["mission"], "mission"),
        risk=_expect_str(value["risk"], "risk"),
    )


def fixture_formation_mission_response(
    *,
    mission: str = "surround_hazard",
    risk: str = "cautious",
) -> str:
    choice = FormationMissionChoice(mission=mission, risk=risk)
    return json.dumps(choice.to_dict(), sort_keys=True, separators=(",", ":"))


def qwen_formation_mission_prompt(
    *,
    hazard_cell: GridPoint,
    grid_width: int,
    grid_height: int,
    requested_formation: str,
) -> str:
    if requested_formation not in SUPPORTED_FORMATIONS:
        raise ValueError(f"unsupported requested formation: {requested_formation}")
    return (
        "Return ONLY json. Use exactly two keys: mission and risk. "
        "mission must be one of: surround_hazard, hold_position. "
        "risk must be one of: cautious, balanced. "
        f"The hazard is at grid cell ({hazard_cell.x},{hazard_cell.y}) on a {grid_width}x{grid_height} grid. "
        f"The local reviewed formation fallback is {requested_formation}. "
        "Choose surround_hazard when the agents should continue the reviewed containment demo. "
        "Choose hold_position when the safest bounded response is to hold locally. "
        "Do not include prose, markdown, comments, or additional keys."
    )


def build_formation_mission_trace(
    *,
    choice: FormationMissionChoice,
    mode: str,
    model: str,
    hazard_cell: GridPoint,
    grid_width: int,
    grid_height: int,
    requested_formation: str,
) -> DecisionTrace:
    """Record the validated low-rate mission choice before local planning."""

    if mode not in {"fixture", "dashscope"}:
        raise ValueError("formation mission trace mode must be fixture or dashscope")
    if requested_formation not in SUPPORTED_FORMATIONS:
        raise ValueError(f"unsupported requested formation: {requested_formation}")
    perception = PerceptionEvent(
        event_id=f"formation-mission-{choice.mission}-{choice.risk}",
        source=f"{mode}_mission://{choice.mission}",
        image_width=1,
        image_height=1,
        label="validated_formation_mission",
        bbox_2d_norm_1000=(0, 0, 1000, 1000),
        bbox_2d_px=(0, 0, 1, 1),
        model=model,
    )
    return build_single_event_trace(
        run_id=f"formation-mission-{choice.mission}-{choice.risk}",
        actor_id="mission-validator-0",
        mode="cloud" if mode == "dashscope" else "fixture",
        perception=perception,
        intent="validate low-rate mission choice before deterministic local planning",
        decision="MOVE",
        reason="mission enum validated; local deterministic planner remains motion authority",
        command={
            "type": "formation_mission",
            "schema_version": FORMATION_MISSION_SCHEMA_VERSION,
            "mission": choice.mission,
            "risk": choice.risk,
            "requested_formation": requested_formation,
            "fallback_formation": choice.fallback_formation(),
            "grid_width": grid_width,
            "grid_height": grid_height,
            "hazard_x": hazard_cell.x,
            "hazard_y": hazard_cell.y,
        },
    )


def _expect_str(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must be non-empty")
    return value
