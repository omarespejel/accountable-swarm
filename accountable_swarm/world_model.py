"""Explicit accountable world model for swarm replay.

The world model is not a learned simulator. It is a deterministic belief-state
artifact that records what local code believes about observations, hazards,
agents, reservations, and predicted conflicts before a rendered replay or
planner handoff.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from accountable_swarm.swarm.sim import GridPoint
from accountable_swarm.trace.models import canonical_json, sha256_canonical

WORLD_MODEL_SCHEMA_VERSION = "world-model.v1"
WORLD_MODEL_ID = "explicit-accountable-world-model-v1"
SUPPORTED_OBSERVATION_SOURCES = ("fixture_bbox", "qwen_bbox", "trace_replay", "degraded")
SUPPORTED_CONFLICT_TYPES = ("same_cell", "swap", "obstacle", "reservation")


@dataclass(frozen=True)
class WorldObservation:
    """Validated semantic observation that can update the explicit world state."""

    observation_id: str
    source: str
    label: str
    cell: GridPoint
    source_trace_sha: str
    bbox_2d_norm_1000: tuple[int, int, int, int] | None = None
    score_milli: int = 1000

    def __post_init__(self) -> None:
        if not self.observation_id.strip():
            raise ValueError("observation_id must be non-empty")
        if self.source not in SUPPORTED_OBSERVATION_SOURCES:
            raise ValueError(f"unsupported observation source: {self.source}")
        if not self.label.strip():
            raise ValueError("observation label must be non-empty")
        _require_hex_64(self.source_trace_sha, "source_trace_sha")
        _require_milli(self.score_milli, "score_milli")
        if self.bbox_2d_norm_1000 is not None:
            _validate_norm_bbox(self.bbox_2d_norm_1000)

    def to_dict(self) -> dict[str, Any]:
        return _freeze_tuples(asdict(self))


@dataclass(frozen=True)
class WorldAgentState:
    """Agent cell and goal inside the accountable world model."""

    agent_id: str
    cell: GridPoint
    goal: GridPoint
    decision_trace_sha: str
    last_decision: str = "HOLD"
    decision_event_sha: str = ""

    def __post_init__(self) -> None:
        if not self.agent_id.strip():
            raise ValueError("agent_id must be non-empty")
        _require_hex_64(self.decision_trace_sha, "decision_trace_sha")
        if self.decision_event_sha:
            _require_hex_64(self.decision_event_sha, "decision_event_sha")
        if self.last_decision not in {"MOVE", "VETO", "HOLD", "REROUTE"}:
            raise ValueError(f"unsupported last_decision: {self.last_decision}")

    def to_dict(self) -> dict[str, Any]:
        return _freeze_tuples(asdict(self))


@dataclass(frozen=True)
class WorldReservation:
    """One reserved future cell for one agent at one tick."""

    tick: int
    agent_id: str
    cell: GridPoint

    def __post_init__(self) -> None:
        if self.tick < 0:
            raise ValueError("reservation tick must be non-negative")
        if not self.agent_id.strip():
            raise ValueError("reservation agent_id must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        return _freeze_tuples(asdict(self))


@dataclass(frozen=True)
class PredictedConflict:
    """Predicted conflict before execution, derived from reservations or paths."""

    tick: int
    conflict_type: str
    agent_ids: tuple[str, ...]
    cell: GridPoint
    reason: str

    def __post_init__(self) -> None:
        _require_nonbool_int(self.tick, "conflict tick")
        if self.tick < 0:
            raise ValueError("conflict tick must be non-negative")
        if self.conflict_type not in SUPPORTED_CONFLICT_TYPES:
            raise ValueError(f"unsupported conflict_type: {self.conflict_type}")
        if len(self.agent_ids) < 1:
            raise ValueError("conflict must include at least one agent")
        if len(set(self.agent_ids)) != len(self.agent_ids):
            raise ValueError("conflict agent_ids must be unique")
        for agent_id in self.agent_ids:
            if not isinstance(agent_id, str) or not agent_id.strip():
                raise ValueError("conflict agent_id must be non-empty")
        if not self.reason.strip():
            raise ValueError("conflict reason must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        return _freeze_tuples(asdict(self))


@dataclass(frozen=True)
class WorldModelState:
    """Hash-stable explicit world model state for one replay tick."""

    tick: int
    grid_width: int
    grid_height: int
    observations: tuple[WorldObservation, ...] = ()
    hazards: tuple[GridPoint, ...] = ()
    agents: tuple[WorldAgentState, ...] = ()
    reservations: tuple[WorldReservation, ...] = ()
    predicted_conflicts: tuple[PredictedConflict, ...] = ()
    model_id: str = WORLD_MODEL_ID
    schema_version: str = WORLD_MODEL_SCHEMA_VERSION
    world_model_sha: str = field(default="")

    def __post_init__(self) -> None:
        if self.schema_version != WORLD_MODEL_SCHEMA_VERSION:
            raise ValueError(f"unsupported world model schema: {self.schema_version}")
        if self.model_id != WORLD_MODEL_ID:
            raise ValueError(f"unsupported world model id: {self.model_id}")
        _require_nonbool_int(self.tick, "world model tick")
        _require_nonbool_int(self.grid_width, "world model grid_width")
        _require_nonbool_int(self.grid_height, "world model grid_height")
        if self.tick < 0:
            raise ValueError("world model tick must be non-negative")
        if self.grid_width <= 0 or self.grid_height <= 0:
            raise ValueError("world model grid dimensions must be positive")
        _validate_unique_observations(self.observations)
        _validate_unique_agents(self.agents)
        _validate_unique_reservations(self.reservations)
        for point in self.hazards:
            _validate_cell(point, grid_width=self.grid_width, grid_height=self.grid_height, name="hazard")
        for observation in self.observations:
            _validate_cell(
                observation.cell,
                grid_width=self.grid_width,
                grid_height=self.grid_height,
                name="observation cell",
            )
        for agent in self.agents:
            _validate_cell(agent.cell, grid_width=self.grid_width, grid_height=self.grid_height, name="agent cell")
            _validate_cell(agent.goal, grid_width=self.grid_width, grid_height=self.grid_height, name="agent goal")
        for reservation in self.reservations:
            _validate_cell(
                reservation.cell,
                grid_width=self.grid_width,
                grid_height=self.grid_height,
                name="reservation cell",
            )
        for conflict in self.predicted_conflicts:
            _validate_cell(
                conflict.cell,
                grid_width=self.grid_width,
                grid_height=self.grid_height,
                name="conflict cell",
            )
        if self.world_model_sha:
            _require_hex_64(self.world_model_sha, "world_model_sha")
        _reject_raw_float_or_bool(self.body_for_hash(), "$")

    def body_for_hash(self) -> dict[str, Any]:
        body = self.to_dict()
        body.pop("world_model_sha", None)
        return body

    def compute_sha(self) -> str:
        return sha256_canonical(self.body_for_hash())

    def with_computed_sha(self) -> "WorldModelState":
        return WorldModelState(
            tick=self.tick,
            grid_width=self.grid_width,
            grid_height=self.grid_height,
            observations=self.observations,
            hazards=self.hazards,
            agents=self.agents,
            reservations=self.reservations,
            predicted_conflicts=self.predicted_conflicts,
            model_id=self.model_id,
            schema_version=self.schema_version,
            world_model_sha=self.compute_sha(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "model_id": self.model_id,
            "tick": self.tick,
            "grid": {"width": self.grid_width, "height": self.grid_height},
            "observations": [
                observation.to_dict()
                for observation in sorted(self.observations, key=lambda item: item.observation_id)
            ],
            "hazards": [point.to_dict() for point in sorted(self.hazards, key=lambda point: (point.x, point.y))],
            "agents": [agent.to_dict() for agent in sorted(self.agents, key=lambda item: item.agent_id)],
            "reservations": [
                reservation.to_dict()
                for reservation in sorted(
                    self.reservations,
                    key=lambda item: (item.tick, item.agent_id, item.cell.x, item.cell.y),
                )
            ],
            "predicted_conflicts": [
                conflict.to_dict()
                for conflict in sorted(
                    self.predicted_conflicts,
                    key=lambda item: (item.tick, item.conflict_type, item.agent_ids, item.cell.x, item.cell.y),
                )
            ],
            "world_model_sha": self.world_model_sha,
        }

    def to_canonical_json(self) -> str:
        return canonical_json(self.to_dict())


def verify_world_model_state(state: WorldModelState) -> str:
    """Verify and return the deterministic world-model hash."""

    if not state.world_model_sha:
        raise ValueError("world_model_sha missing")
    recomputed = state.with_computed_sha()
    if state.world_model_sha != recomputed.world_model_sha:
        raise ValueError("world_model_sha mismatch")
    return recomputed.world_model_sha


def world_model_from_dict(value: dict[str, Any]) -> WorldModelState:
    """Load a world model state from JSON-compatible data."""

    value = _require_dict(value, "world model")
    schema_version = value.get("schema_version")
    if schema_version != WORLD_MODEL_SCHEMA_VERSION:
        raise ValueError(f"unsupported world model schema: {schema_version}")
    grid = _require_dict(value.get("grid"), "grid")
    observations = tuple(
        WorldObservation(
            observation_id=item["observation_id"],
            source=item["source"],
            label=item["label"],
            cell=GridPoint.from_dict(_require_dict(item["cell"], "observation cell")),
            source_trace_sha=item["source_trace_sha"],
            bbox_2d_norm_1000=tuple(item["bbox_2d_norm_1000"])
            if item.get("bbox_2d_norm_1000") is not None
            else None,
            score_milli=item.get("score_milli", 1000),
        )
        for item in _require_list(value.get("observations", []), "observations")
        for item in (_require_dict(item, "observation"),)
    )
    hazards = tuple(
        GridPoint.from_dict(_require_dict(item, "hazard"))
        for item in _require_list(value.get("hazards", []), "hazards")
    )
    agents = tuple(
        WorldAgentState(
            agent_id=item["agent_id"],
            cell=GridPoint.from_dict(_require_dict(item["cell"], "agent cell")),
            goal=GridPoint.from_dict(_require_dict(item["goal"], "agent goal")),
            decision_trace_sha=item["decision_trace_sha"],
            last_decision=item.get("last_decision", "HOLD"),
            decision_event_sha=item.get("decision_event_sha", ""),
        )
        for item in _require_list(value.get("agents", []), "agents")
        for item in (_require_dict(item, "agent"),)
    )
    reservations = tuple(
        WorldReservation(
            tick=item["tick"],
            agent_id=item["agent_id"],
            cell=GridPoint.from_dict(_require_dict(item["cell"], "reservation cell")),
        )
        for item in _require_list(value.get("reservations", []), "reservations")
        for item in (_require_dict(item, "reservation"),)
    )
    conflicts = tuple(
        PredictedConflict(
            tick=item["tick"],
            conflict_type=item["conflict_type"],
            agent_ids=_require_agent_ids(item["agent_ids"]),
            cell=GridPoint.from_dict(_require_dict(item["cell"], "conflict cell")),
            reason=item["reason"],
        )
        for item in _require_list(value.get("predicted_conflicts", []), "predicted_conflicts")
        for item in (_require_dict(item, "predicted conflict"),)
    )
    return WorldModelState(
        tick=value["tick"],
        grid_width=grid["width"],
        grid_height=grid["height"],
        observations=observations,
        hazards=hazards,
        agents=agents,
        reservations=reservations,
        predicted_conflicts=conflicts,
        model_id=value.get("model_id", WORLD_MODEL_ID),
        schema_version=schema_version,
        world_model_sha=value.get("world_model_sha", ""),
    )


def _validate_unique_observations(observations: tuple[WorldObservation, ...]) -> None:
    ids = [observation.observation_id for observation in observations]
    if len(set(ids)) != len(ids):
        raise ValueError("world observations must have unique observation_id values")


def _validate_unique_agents(agents: tuple[WorldAgentState, ...]) -> None:
    ids = [agent.agent_id for agent in agents]
    if len(set(ids)) != len(ids):
        raise ValueError("world agents must have unique agent_id values")


def _validate_unique_reservations(reservations: tuple[WorldReservation, ...]) -> None:
    keys = [(reservation.tick, reservation.agent_id) for reservation in reservations]
    if len(set(keys)) != len(keys):
        raise ValueError("world reservations must have unique tick/agent_id pairs")


def _validate_cell(point: GridPoint, *, grid_width: int, grid_height: int, name: str) -> None:
    if not 0 <= point.x < grid_width or not 0 <= point.y < grid_height:
        raise ValueError(f"{name} outside world model grid")


def _validate_norm_bbox(bbox: tuple[int, int, int, int]) -> None:
    if len(bbox) != 4:
        raise ValueError("bbox_2d_norm_1000 must contain four values")
    x1, y1, x2, y2 = bbox
    values = (x1, y1, x2, y2)
    if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
        raise TypeError("bbox_2d_norm_1000 values must be integers")
    if any(value < 0 or value > 1000 for value in values):
        raise ValueError("bbox_2d_norm_1000 values must be in 0..1000")
    if x1 >= x2 or y1 >= y2:
        raise ValueError("bbox_2d_norm_1000 must have positive area")


def _require_milli(value: int, name: str) -> None:
    _require_nonbool_int(value, name)
    if value < 0 or value > 1000:
        raise ValueError(f"{name} must be within 0..1000")


def _require_nonbool_int(value: Any, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")


def _require_hex_64(value: str, name: str) -> None:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{name} must be a 64-character hex string")
    if any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{name} must be lowercase hex")


def _require_dict(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _require_list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be an array")
    return value


def _require_agent_ids(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError("conflict agent_ids must be an array")
    agent_ids = tuple(value)
    for agent_id in agent_ids:
        if not isinstance(agent_id, str) or not agent_id.strip():
            raise ValueError("conflict agent_ids must contain non-empty strings")
    return agent_ids


def _reject_raw_float_or_bool(value: Any, path: str) -> None:
    if isinstance(value, bool):
        raise TypeError(f"raw bool not allowed in world model canonical JSON at {path}")
    if isinstance(value, float):
        raise TypeError(f"raw float not allowed in world model canonical JSON at {path}")
    if isinstance(value, dict):
        for key, item in value.items():
            _reject_raw_float_or_bool(item, f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_raw_float_or_bool(item, f"{path}[{index}]")


def _freeze_tuples(value: Any) -> Any:
    if isinstance(value, GridPoint):
        return value.to_dict()
    if isinstance(value, tuple):
        return [_freeze_tuples(item) for item in value]
    if isinstance(value, list):
        return [_freeze_tuples(item) for item in value]
    if isinstance(value, dict):
        return {key: _freeze_tuples(item) for key, item in value.items()}
    return value
