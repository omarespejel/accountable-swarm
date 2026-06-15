"""Validated low-rate mission specs for the deterministic swarm simulator."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from typing import Any

from accountable_swarm.trace.models import (
    DecisionTrace,
    PerceptionEvent,
    build_single_event_trace,
    reject_raw_floats,
)
from accountable_swarm.swarm.sim import scenario_default_ticks, scenario_names

MISSION_SCHEMA_VERSION = "swarm-mission.v1"
MISSION_MODEL_FIXTURE_ID = "fixture-qwen-mission-shape"
DEFAULT_MISSION_SCENARIO = "center-block"
DEFAULT_MISSION_AGENT_COUNT = 4
SUPPORTED_MISSION_SCENARIOS = scenario_names()
SUPPORTED_MISSION_AGENT_COUNTS = (DEFAULT_MISSION_AGENT_COUNT,)
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
MISSION_INTENT_REQUIRED_KEYS = frozenset({"objective"})
MISSION_OBJECTIVE_FORBIDDEN_WORD_TERMS = (
    "agent_count",
    "command",
    "commands",
    "control",
    "coordinate",
    "coordinates",
    "mission_id",
    "motor",
    "motors",
    "schema_version",
    "setpoint",
    "setpoints",
    "thrust",
    "tick",
    "ticks",
    "velocity",
    "velocities",
    "waypoint",
    "waypoints",
)
MISSION_OBJECTIVE_FORBIDDEN_CHARACTERS = frozenset("{}[]")
MISSION_OBJECTIVE_NUMBER_WORDS = (
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
)
MISSION_OBJECTIVE_COUNT_TARGETS = ("agent", "agents", "tick", "ticks")
MISSION_OBJECTIVE_COUNT_WORD_RE = re.compile(
    r"\b("
    + "|".join(re.escape(word) for word in MISSION_OBJECTIVE_NUMBER_WORDS)
    + r")\s+("
    + "|".join(re.escape(target) for target in MISSION_OBJECTIVE_COUNT_TARGETS)
    + r")\b"
)
MISSION_OBJECTIVE_SPECIAL_CONTROL_PATTERNS = (
    re.compile(r"\bsim[-_\s]+agent\b"),
    re.compile(r"\b[xyz]\s*[:=]"),
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
        validate_mission_objective_text(self.objective)

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


def parse_mission_intent_response(response_text: str) -> str:
    """Parse a strict DashScope mission-intent JSON object."""

    if not response_text.strip():
        raise ValueError("mission intent response must be non-empty")
    try:
        value = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise ValueError("mission intent response must be valid JSON") from exc
    reject_raw_floats(value)
    if not isinstance(value, dict):
        raise ValueError("mission intent response must be a JSON object")
    keys = frozenset(value)
    if keys != MISSION_INTENT_REQUIRED_KEYS:
        missing = sorted(MISSION_INTENT_REQUIRED_KEYS - keys)
        extra = sorted(keys - MISSION_INTENT_REQUIRED_KEYS)
        raise ValueError(f"mission intent keys mismatch; missing={missing}; extra={extra}")
    objective = _expect_str(value["objective"], "objective")
    if not objective.strip():
        raise ValueError("objective must be non-empty")
    validate_mission_objective_text(objective)
    return objective


def validate_mission_objective_text(objective: str) -> None:
    """Reject obvious control metadata hidden inside mission objective prose."""

    if any(character.isdigit() for character in objective):
        raise ValueError("mission objective must not contain numeric control metadata")
    if any(character in MISSION_OBJECTIVE_FORBIDDEN_CHARACTERS for character in objective):
        raise ValueError("mission objective must not contain structured control metadata")
    lowered = objective.casefold()
    if MISSION_OBJECTIVE_COUNT_WORD_RE.search(lowered):
        raise ValueError("mission objective must not contain numeric control metadata")
    scenario_hits = [
        scenario
        for scenario in SUPPORTED_MISSION_SCENARIOS
        if re.search(_mission_objective_scenario_re(scenario), lowered)
    ]
    if scenario_hits:
        raise ValueError(
            "mission objective must not select a scenario; local code binds scenario"
        )
    term_hits = [
        term
        for term in MISSION_OBJECTIVE_FORBIDDEN_WORD_TERMS
        if re.search(rf"\b{re.escape(term)}\b", lowered)
    ]
    if term_hits:
        raise ValueError("mission objective must not contain control metadata terms")
    if any(pattern.search(lowered) for pattern in MISSION_OBJECTIVE_SPECIAL_CONTROL_PATTERNS):
        raise ValueError("mission objective must not contain control metadata terms")


def _mission_objective_scenario_re(scenario: str) -> str:
    parts = [re.escape(part) for part in scenario.split("-")]
    return r"\b" + r"[-_\s]+".join(parts) + r"\b"


def mission_spec_for_scenario(*, scenario: str, objective: str) -> MissionSpec:
    """Build the deterministic mission envelope for a reviewed scenario."""

    _validate_mission_scenario(scenario)
    return MissionSpec(
        schema_version=MISSION_SCHEMA_VERSION,
        mission_id=mission_id_for_scenario(scenario=scenario),
        scenario=scenario,
        agent_count=DEFAULT_MISSION_AGENT_COUNT,
        ticks=scenario_default_ticks(scenario),
        objective=objective,
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


def fixture_mission_response(*, scenario: str = DEFAULT_MISSION_SCENARIO) -> str:
    spec = mission_spec_for_scenario(
        scenario=scenario,
        objective="route all agents to their opposing goals without same-cell, swap, or obstacle occupancy violations",
    )
    return json.dumps(
        spec.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
    )


def qwen_mission_prompt(*, scenario: str = DEFAULT_MISSION_SCENARIO) -> str:
    _validate_mission_scenario(scenario)
    return (
        "Return ONLY a JSON object with exactly one key: objective. "
        f"The deterministic local runner has already selected scenario {scenario}; "
        "do not output scenario, mission_id, agent_count, ticks, commands, coordinates, arrays, or control parameters. "
        "The objective must describe the mission intent: route all agents to their opposing goals without same-cell, swap, or obstacle occupancy violations. "
        "Do not include markdown, comments, digits, arrays, floats, coordinates, or extra keys."
    )


def _expect_str(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    return value


def _expect_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    return value


def mission_id_for_scenario(*, scenario: str, agent_count: int = DEFAULT_MISSION_AGENT_COUNT) -> str:
    _validate_mission_scenario(scenario)
    if agent_count not in SUPPORTED_MISSION_AGENT_COUNTS:
        raise ValueError(f"unsupported mission agent_count: {agent_count}")
    return f"{scenario}-n{agent_count}"


def _validate_mission_scenario(scenario: str) -> None:
    if scenario not in SUPPORTED_MISSION_SCENARIOS:
        raise ValueError(f"unsupported mission scenario: {scenario}")
