"""Deterministic integer-grid swarm simulator.

This module is deliberately not a physics simulator. It is the smallest
swarm-shaped experiment for the repo thesis: local deterministic guards choose
MOVE/REROUTE/HOLD decisions, and every choice is replayable as a DecisionTrace.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from accountable_swarm.trace.models import (
    GENESIS_SHA,
    DecisionEvent,
    DecisionTrace,
    PerceptionEvent,
)

SWARM_REPORT_SCHEMA_VERSION = "swarm-sim-report.v1"
SWARM_MODEL_ID = "deterministic-grid-swarm-v1"


@dataclass(frozen=True, order=True)
class GridPoint:
    """Integer grid coordinate."""

    x: int
    y: int

    def __post_init__(self) -> None:
        if not isinstance(self.x, int) or not isinstance(self.y, int):
            raise TypeError("grid coordinates must be integers")

    def to_dict(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y}


@dataclass(frozen=True)
class AgentConfig:
    """Static start/goal configuration for one simulated agent."""

    agent_id: str
    start: GridPoint
    goal: GridPoint

    def __post_init__(self) -> None:
        if not self.agent_id.strip():
            raise ValueError("agent_id must be non-empty")


@dataclass(frozen=True)
class AgentStep:
    """One accepted local decision for one agent at one tick."""

    tick: int
    agent_id: str
    before: GridPoint
    goal: GridPoint
    proposed: GridPoint
    accepted: GridPoint
    decision: str
    reason: str

    def command_dict(self, *, grid_width: int, grid_height: int) -> dict[str, Any]:
        return {
            "type": "grid_step",
            "grid_width": grid_width,
            "grid_height": grid_height,
            "from_x": self.before.x,
            "from_y": self.before.y,
            "goal_x": self.goal.x,
            "goal_y": self.goal.y,
            "proposed_x": self.proposed.x,
            "proposed_y": self.proposed.y,
            "accepted_x": self.accepted.x,
            "accepted_y": self.accepted.y,
            "delta_x": self.accepted.x - self.before.x,
            "delta_y": self.accepted.y - self.before.y,
            "collision_guard_checked": 1,
            "swap_guard_checked": 1,
        }


@dataclass(frozen=True)
class TickRecord:
    """Aggregate state transition for one simulated tick."""

    tick: int
    steps: tuple[AgentStep, ...]
    same_cell_collisions: int
    swap_collisions: int


@dataclass(frozen=True)
class SwarmSimulationResult:
    """Full deterministic swarm run."""

    run_id: str
    grid_width: int
    grid_height: int
    configs: tuple[AgentConfig, ...]
    ticks: tuple[TickRecord, ...]
    final_positions: dict[str, GridPoint]

    @property
    def agent_count(self) -> int:
        return len(self.configs)

    @property
    def same_cell_collision_count(self) -> int:
        return sum(tick.same_cell_collisions for tick in self.ticks)

    @property
    def swap_collision_count(self) -> int:
        return sum(tick.swap_collisions for tick in self.ticks)

    @property
    def reroute_count(self) -> int:
        return sum(1 for tick in self.ticks for step in tick.steps if step.decision == "REROUTE")

    @property
    def hold_count(self) -> int:
        return sum(1 for tick in self.ticks for step in tick.steps if step.decision == "HOLD")

    @property
    def all_goals_reached(self) -> bool:
        goals = {config.agent_id: config.goal for config in self.configs}
        return all(self.final_positions[agent_id] == goal for agent_id, goal in goals.items())

    def report_dict(self, trace_summary_shas: dict[str, str]) -> dict[str, Any]:
        expected_agent_ids = {config.agent_id for config in self.configs}
        trace_summary_complete = set(trace_summary_shas) == expected_agent_ids and all(
            _is_hex_64(summary_sha) for summary_sha in trace_summary_shas.values()
        )
        outcome = (
            "GO"
            if self.all_goals_reached
            and self.same_cell_collision_count == 0
            and self.swap_collision_count == 0
            and trace_summary_complete
            else "NARROW_CLAIM"
        )
        return {
            "schema_version": SWARM_REPORT_SCHEMA_VERSION,
            "run_id": self.run_id,
            "outcome": outcome,
            "agent_count": self.agent_count,
            "grid": {"width": self.grid_width, "height": self.grid_height},
            "ticks_executed": len(self.ticks),
            "all_goals_reached": self.all_goals_reached,
            "same_cell_collision_count": self.same_cell_collision_count,
            "swap_collision_count": self.swap_collision_count,
            "reroute_count": self.reroute_count,
            "hold_count": self.hold_count,
            "final_positions": {
                agent_id: point.to_dict() for agent_id, point in sorted(self.final_positions.items())
            },
            "trace_summary_shas": dict(sorted(trace_summary_shas.items())),
            "non_claims": [
                "no physical robot behavior",
                "no SO-101 operation",
                "no real-time latency or reliability claim",
                "no 3D physics simulation",
                "no DimOS integration",
                "no Alibaba deployment proof",
                "no claim that larger swarms succeed",
            ],
        }


@dataclass(frozen=True)
class SwarmReplayReport:
    """Trace-derived replay report with no simulator-side implicit state."""

    agent_count: int
    ticks_replayed: int
    final_positions: dict[str, GridPoint]
    same_cell_collision_count: int
    swap_collision_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_count": self.agent_count,
            "ticks_replayed": self.ticks_replayed,
            "final_positions": {
                agent_id: point.to_dict() for agent_id, point in sorted(self.final_positions.items())
            },
            "same_cell_collision_count": self.same_cell_collision_count,
            "swap_collision_count": self.swap_collision_count,
        }


def run_swarm_sim(
    *,
    agent_count: int = 2,
    ticks: int = 8,
    grid_width: int = 7,
    grid_height: int = 5,
    run_id: str | None = None,
) -> SwarmSimulationResult:
    """Run the deterministic simulated swarm."""

    if ticks <= 0:
        raise ValueError("ticks must be positive")
    configs = _default_configs(agent_count, grid_width=grid_width, grid_height=grid_height)
    positions = {config.agent_id: config.start for config in configs}
    records: list[TickRecord] = []
    for tick in range(ticks):
        before = dict(positions)
        steps = _choose_tick_steps(
            tick=tick,
            configs=configs,
            positions=before,
            grid_width=grid_width,
            grid_height=grid_height,
        )
        positions = {step.agent_id: step.accepted for step in steps}
        same_cell, swap = _collision_counts(before, positions)
        records.append(
            TickRecord(
                tick=tick,
                steps=tuple(steps),
                same_cell_collisions=same_cell,
                swap_collisions=swap,
            )
        )
    return SwarmSimulationResult(
        run_id=run_id or f"swarm-sim-n{agent_count}",
        grid_width=grid_width,
        grid_height=grid_height,
        configs=configs,
        ticks=tuple(records),
        final_positions=positions,
    )


def build_agent_traces(result: SwarmSimulationResult) -> dict[str, DecisionTrace]:
    """Build one hash-chained DecisionTrace per simulated agent."""

    traces: dict[str, DecisionTrace] = {}
    for config in result.configs:
        prev_sha = GENESIS_SHA
        events: list[DecisionEvent] = []
        for tick in result.ticks:
            step = _step_for_agent(tick, config.agent_id)
            event = DecisionEvent(
                tick=step.tick,
                actor_id=config.agent_id,
                mode="edge",
                intent="move toward integer-grid goal while preserving local collision guards",
                decision=step.decision,
                reason=step.reason,
                command=step.command_dict(grid_width=result.grid_width, grid_height=result.grid_height),
                perception=_synthetic_perception(result=result, tick=step.tick, agent_id=config.agent_id),
                prev_sha=prev_sha,
            ).with_computed_sha()
            events.append(event)
            prev_sha = event.sha256
        traces[config.agent_id] = DecisionTrace(
            run_id=f"{result.run_id}-{config.agent_id}",
            events=tuple(events),
        ).with_computed_summary()
    return traces


def replay_swarm_traces(traces: dict[str, DecisionTrace]) -> SwarmReplayReport:
    """Replay per-agent traces into final positions and collision counts."""

    if not traces:
        raise ValueError("at least one trace is required")
    agent_ids = sorted(traces)
    events_by_agent: dict[str, tuple[DecisionEvent, ...]] = {}
    expected_ticks: int | None = None
    for agent_id in agent_ids:
        trace = traces[agent_id]
        trace.with_computed_summary()
        if expected_ticks is None:
            expected_ticks = len(trace.events)
        elif len(trace.events) != expected_ticks:
            raise ValueError("all swarm traces must have the same event count")
        events_by_agent[agent_id] = trace.events
    assert expected_ticks is not None

    previous_positions: dict[str, GridPoint] | None = None
    final_positions: dict[str, GridPoint] = {}
    same_cell_collision_count = 0
    swap_collision_count = 0
    for tick in range(expected_ticks):
        before: dict[str, GridPoint] = {}
        after: dict[str, GridPoint] = {}
        for agent_id in agent_ids:
            event = events_by_agent[agent_id][tick]
            if event.actor_id != agent_id:
                raise ValueError("trace actor_id does not match trace map key")
            command = _grid_step_command(event.command)
            event_before = GridPoint(command["from_x"], command["from_y"])
            event_after = GridPoint(command["accepted_x"], command["accepted_y"])
            if previous_positions is not None and event_before != previous_positions[agent_id]:
                raise ValueError("trace from-position does not match previous accepted position")
            if command["delta_x"] != event_after.x - event_before.x:
                raise ValueError("trace delta_x does not match accepted movement")
            if command["delta_y"] != event_after.y - event_before.y:
                raise ValueError("trace delta_y does not match accepted movement")
            _validate_decision_matches_command(event, command, event_before, event_after)
            before[agent_id] = event_before
            after[agent_id] = event_after
        same_cell, swap = _collision_counts(before, after)
        same_cell_collision_count += same_cell
        swap_collision_count += swap
        previous_positions = after
        final_positions = after
    return SwarmReplayReport(
        agent_count=len(agent_ids),
        ticks_replayed=expected_ticks,
        final_positions=final_positions,
        same_cell_collision_count=same_cell_collision_count,
        swap_collision_count=swap_collision_count,
    )


def _choose_tick_steps(
    *,
    tick: int,
    configs: tuple[AgentConfig, ...],
    positions: dict[str, GridPoint],
    grid_width: int,
    grid_height: int,
) -> list[AgentStep]:
    accepted: dict[str, GridPoint] = {}
    steps: list[AgentStep] = []
    for config in sorted(configs, key=lambda item: item.agent_id):
        before = positions[config.agent_id]
        candidates = _candidate_positions(config, before)
        proposed = candidates[0]
        accepted_point = before
        decision = "HOLD"
        reason = "no safe candidate available"
        for index, candidate in enumerate(candidates):
            if not _in_bounds(candidate, grid_width=grid_width, grid_height=grid_height):
                continue
            if candidate in accepted.values():
                continue
            if _would_swap(config.agent_id, before, candidate, positions, accepted):
                continue
            accepted_point = candidate
            decision, reason = _decision_for_candidate(index=index, before=before, candidate=candidate)
            break
        steps.append(
            AgentStep(
                tick=tick,
                agent_id=config.agent_id,
                before=before,
                goal=config.goal,
                proposed=proposed,
                accepted=accepted_point,
                decision=decision,
                reason=reason,
            )
        )
        accepted[config.agent_id] = accepted_point
    return steps


def _candidate_positions(config: AgentConfig, before: GridPoint) -> list[GridPoint]:
    if before == config.goal:
        return [before]
    direct = _step_toward(before, config.goal)
    candidates = [direct]
    if direct.x != before.x:
        offsets = (-1, 1) if _agent_index(config.agent_id) % 2 == 0 else (1, -1)
        candidates.extend(GridPoint(before.x, before.y + offset) for offset in offsets)
    else:
        offsets = (-1, 1) if _agent_index(config.agent_id) % 2 == 0 else (1, -1)
        candidates.extend(GridPoint(before.x + offset, before.y) for offset in offsets)
    alternate = _alternate_axis_step(before, config.goal, direct)
    if alternate not in candidates:
        candidates.append(alternate)
    candidates.append(before)
    return _dedupe_points(candidates)


def _step_toward(before: GridPoint, goal: GridPoint) -> GridPoint:
    if before.x < goal.x:
        return GridPoint(before.x + 1, before.y)
    if before.x > goal.x:
        return GridPoint(before.x - 1, before.y)
    if before.y < goal.y:
        return GridPoint(before.x, before.y + 1)
    if before.y > goal.y:
        return GridPoint(before.x, before.y - 1)
    return before


def _alternate_axis_step(before: GridPoint, goal: GridPoint, direct: GridPoint) -> GridPoint:
    if direct.x != before.x and before.y != goal.y:
        return GridPoint(before.x, before.y + (1 if before.y < goal.y else -1))
    if direct.y != before.y and before.x != goal.x:
        return GridPoint(before.x + (1 if before.x < goal.x else -1), before.y)
    return before


def _decision_for_candidate(*, index: int, before: GridPoint, candidate: GridPoint) -> tuple[str, str]:
    if candidate == before:
        return "HOLD", "already at goal or all movement candidates were blocked"
    if index == 0:
        return "MOVE", "direct grid step accepted"
    return "REROUTE", "direct step blocked by local collision guard"


def _would_swap(
    agent_id: str,
    before: GridPoint,
    candidate: GridPoint,
    positions: dict[str, GridPoint],
    accepted: dict[str, GridPoint],
) -> bool:
    for other_id, other_target in accepted.items():
        if other_id == agent_id:
            continue
        if candidate == positions[other_id] and other_target == before:
            return True
    return False


def _collision_counts(before: dict[str, GridPoint], after: dict[str, GridPoint]) -> tuple[int, int]:
    target_counts: dict[GridPoint, int] = {}
    for point in after.values():
        target_counts[point] = target_counts.get(point, 0) + 1
    same_cell = sum(count - 1 for count in target_counts.values() if count > 1)
    swap = 0
    agent_ids = sorted(after)
    for left_index, left_id in enumerate(agent_ids):
        for right_id in agent_ids[left_index + 1 :]:
            if after[left_id] == before[right_id] and after[right_id] == before[left_id]:
                swap += 1
    return same_cell, swap


def _synthetic_perception(*, result: SwarmSimulationResult, tick: int, agent_id: str) -> PerceptionEvent:
    return PerceptionEvent(
        event_id=f"swarm-{agent_id}-tick-{tick:04d}",
        source=f"swarm_sim://{result.run_id}/tick-{tick:04d}",
        image_width=result.grid_width,
        image_height=result.grid_height,
        label="simulated_swarm_state",
        bbox_2d_norm_1000=(0, 0, 1000, 1000),
        bbox_2d_px=(0, 0, result.grid_width, result.grid_height),
        model=SWARM_MODEL_ID,
    )


def _default_configs(agent_count: int, *, grid_width: int, grid_height: int) -> tuple[AgentConfig, ...]:
    if grid_width < 5 or grid_height < 5:
        raise ValueError("default swarm scenarios require grid_width >= 5 and grid_height >= 5")
    configs = (
        AgentConfig("sim-agent-0", GridPoint(0, grid_height // 2), GridPoint(grid_width - 1, grid_height // 2)),
        AgentConfig("sim-agent-1", GridPoint(grid_width - 1, grid_height // 2), GridPoint(0, grid_height // 2)),
        AgentConfig("sim-agent-2", GridPoint(grid_width // 2, 0), GridPoint(grid_width // 2, grid_height - 1)),
        AgentConfig("sim-agent-3", GridPoint(grid_width // 2, grid_height - 1), GridPoint(grid_width // 2, 0)),
    )
    if agent_count not in {2, 4}:
        raise ValueError("agent_count must be 2 or 4 for the current checked scenarios")
    return configs[:agent_count]


def _step_for_agent(tick: TickRecord, agent_id: str) -> AgentStep:
    for step in tick.steps:
        if step.agent_id == agent_id:
            return step
    raise ValueError(f"missing step for {agent_id}")


def _in_bounds(point: GridPoint, *, grid_width: int, grid_height: int) -> bool:
    return 0 <= point.x < grid_width and 0 <= point.y < grid_height


def _agent_index(agent_id: str) -> int:
    suffix = agent_id.rsplit("-", 1)[-1]
    return int(suffix) if suffix.isdigit() else 0


def _dedupe_points(points: list[GridPoint]) -> list[GridPoint]:
    deduped: list[GridPoint] = []
    for point in points:
        if point not in deduped:
            deduped.append(point)
    return deduped


def _grid_step_command(command: dict[str, Any]) -> dict[str, int]:
    required_keys = (
        "from_x",
        "from_y",
        "proposed_x",
        "proposed_y",
        "accepted_x",
        "accepted_y",
        "delta_x",
        "delta_y",
    )
    if command.get("type") != "grid_step":
        raise ValueError("trace command is not a grid_step")
    checked: dict[str, int] = {}
    for key in required_keys:
        value = command.get(key)
        if not isinstance(value, int):
            raise ValueError(f"trace command {key} must be an integer")
        checked[key] = value
    return checked


def _validate_decision_matches_command(
    event: DecisionEvent, command: dict[str, int], before: GridPoint, accepted: GridPoint
) -> None:
    proposed = GridPoint(command["proposed_x"], command["proposed_y"])
    if accepted == before:
        if event.decision != "HOLD":
            raise ValueError("stationary grid step must be a HOLD decision")
        return
    if accepted == proposed:
        if event.decision != "MOVE":
            raise ValueError("direct accepted grid step must be a MOVE decision")
        return
    if event.decision != "REROUTE":
        raise ValueError("non-direct accepted grid step must be a REROUTE decision")


def _is_hex_64(value: str) -> bool:
    if len(value) != 64:
        return False
    return all(char in "0123456789abcdef" for char in value)
