"""Validated low-rate mission specs for the deterministic swarm simulator."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any

from accountable_swarm.trace.models import (
    DecisionTrace,
    PerceptionEvent,
    build_single_event_trace,
    reject_raw_floats,
)

MISSION_SCHEMA_VERSION = "swarm-mission.v1"
MISSION_MODEL_FIXTURE_ID = "fixture-qwen-mission-shape"
SUPPORTED_MISSION_SCENARIOS = ("center-block",)
SUPPORTED_MISSION_AGENT_COUNTS = (4,)
MIN_MISSION_TICKS = 1
MAX_MISSION_TICKS = 32
MISSION_REQUIRED_KEYS = frozenset(
    {
        "schema_version",
        "mission_id",
        "scenario",
        "agent_count",
        "ticks",
        "objective",
    }
)


@dataclass(frozen=True)
class MissionSpec:
    """Bounded mission intent accepted from Qwen or a fixture."""

    schema_version: str
    mission_id: str
    scenario: str
    agent_count: int
    ticks: int
    objective: str

    def __post_init__(self) -> None:
        if not isinstance(self.schema_version, str):
            raise TypeError("schema_version must be a string")
        if self.schema_version != MISSION_SCHEMA_VERSION:
            raise ValueError(f"unsupported mission schema: {self.schema_version}")
        if not isinstance(self.mission_id, str):
            raise TypeError("mission_id must be a string")
        if not self.mission_id.strip():
            raise ValueError("mission_id must be non-empty")
        if not isinstance(self.scenario, str):
            raise TypeError("scenario must be a string")
        if self.scenario not in SUPPORTED_MISSION_SCENARIOS:
            raise ValueError(f"unsupported mission scenario: {self.scenario}")
        if isinstance(self.agent_count, bool) or not isinstance(self.agent_count, int):
            raise TypeError("agent_count must be an integer")
        if self.agent_count not in SUPPORTED_MISSION_AGENT_COUNTS:
            raise ValueError(f"unsupported mission agent_count: {self.agent_count}")
        if isinstance(self.ticks, bool) or not isinstance(self.ticks, int):
            raise TypeError("mission ticks must be an integer")
        if not MIN_MISSION_TICKS <= self.ticks <= MAX_MISSION_TICKS:
            raise ValueError(
                f"mission ticks must be between {MIN_MISSION_TICKS} and {MAX_MISSION_TICKS}"
            )
        if not isinstance(self.objective, str):
            raise TypeError("objective must be a string")
        if not self.objective.strip():
            raise ValueError("objective must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_mission_response(response_text: str) -> MissionSpec:
    """Parse a strict Qwen/fixture mission JSON object."""

    if not response_text.strip():
        raise ValueError("mission response must be non-empty")
    try:
        value = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise ValueError("mission response must be valid JSON") from exc
    reject_raw_floats(value)
    if not isinstance(value, dict):
        raise ValueError("mission response must be a JSON object")
    keys = frozenset(value)
    if keys != MISSION_REQUIRED_KEYS:
        missing = sorted(MISSION_REQUIRED_KEYS - keys)
        extra = sorted(keys - MISSION_REQUIRED_KEYS)
        raise ValueError(f"mission response keys mismatch; missing={missing}; extra={extra}")
    return MissionSpec(
        schema_version=_expect_str(value["schema_version"], "schema_version"),
        mission_id=_expect_str(value["mission_id"], "mission_id"),
        scenario=_expect_str(value["scenario"], "scenario"),
        agent_count=_expect_int(value["agent_count"], "agent_count"),
        ticks=_expect_int(value["ticks"], "ticks"),
        objective=_expect_str(value["objective"], "objective"),
    )


def build_mission_trace(*, spec: MissionSpec, mode: str, model: str) -> DecisionTrace:
    """Build a trace event for the validated low-rate mission decision."""

    if mode not in {"fixture", "dashscope"}:
        raise ValueError("mission trace mode must be fixture or dashscope")
    perception = PerceptionEvent(
        event_id=f"swarm-mission-{spec.mission_id}",
        source=f"{mode}_mission://{spec.mission_id}",
        image_width=1,
        image_height=1,
        label="validated_swarm_mission",
        bbox_2d_norm_1000=(0, 0, 1000, 1000),
        bbox_2d_px=(0, 0, 1, 1),
        model=model,
    )
    return build_single_event_trace(
        run_id=f"swarm-mission-{spec.mission_id}",
        actor_id="mission-validator-0",
        mode="cloud" if mode == "dashscope" else "fixture",
        perception=perception,
        intent="validate low-rate swarm mission before local planning",
        decision="MOVE",
        reason="mission JSON validated; local deterministic planner remains motion authority",
        command={
            "type": "swarm_mission",
            "schema_version": spec.schema_version,
            "mission_id": spec.mission_id,
            "scenario": spec.scenario,
            "agent_count": spec.agent_count,
            "ticks": spec.ticks,
            "objective": spec.objective,
        },
    )


def fixture_mission_response() -> str:
    return json.dumps(
        {
            "schema_version": MISSION_SCHEMA_VERSION,
            "mission_id": "center-block-n4",
            "scenario": "center-block",
            "agent_count": 4,
            "ticks": 16,
            "objective": "route all agents to their opposing goals without same-cell, swap, or obstacle occupancy violations",
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def qwen_mission_prompt() -> str:
    return (
        "Return ONLY a JSON object with exactly these keys: "
        "schema_version, mission_id, scenario, agent_count, ticks, objective. "
        f"schema_version must be {MISSION_SCHEMA_VERSION}. "
        "Choose scenario center-block, agent_count 4, ticks 16, mission_id center-block-n4. "
        "Objective: route all agents to their opposing goals without same-cell, swap, or obstacle occupancy violations. "
        "Do not include markdown, comments, prose, arrays, floats, or extra keys."
    )


def _expect_str(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    return value


def _expect_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    return value
