"""Deterministic formation targets for reviewed integer-grid swarm runs."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations
from typing import Iterable

from accountable_swarm.swarm.sim import AgentConfig, GridPoint

FORMATION_SCHEMA_VERSION = "swarm-formation.v1"
SUPPORTED_FORMATIONS = ("surround", "x", "line", "diamond")


@dataclass(frozen=True)
class FormationPlan:
    """Bounded formation target slots around one hazard cell."""

    schema_version: str
    formation: str
    hazard_cell: GridPoint
    grid_width: int
    grid_height: int
    slots: tuple[GridPoint, ...]

    def __post_init__(self) -> None:
        if self.schema_version != FORMATION_SCHEMA_VERSION:
            raise ValueError(f"unsupported formation schema: {self.schema_version}")
        if self.formation not in SUPPORTED_FORMATIONS:
            raise ValueError(f"unsupported formation: {self.formation}")
        if self.grid_width <= 0 or self.grid_height <= 0:
            raise ValueError("grid dimensions must be positive")
        if not _in_bounds(self.hazard_cell, grid_width=self.grid_width, grid_height=self.grid_height):
            raise ValueError("hazard cell must be inside the grid")
        if not self.slots:
            raise ValueError("formation must contain at least one slot")
        if len(frozenset(self.slots)) != len(self.slots):
            raise ValueError("formation slots must be unique")
        for slot in self.slots:
            if not _in_bounds(slot, grid_width=self.grid_width, grid_height=self.grid_height):
                raise ValueError("formation slot must be inside the grid")
            if slot == self.hazard_cell:
                raise ValueError("formation slot must not occupy the hazard cell")

    @property
    def agent_count(self) -> int:
        return len(self.slots)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "formation": self.formation,
            "hazard_cell": self.hazard_cell.to_dict(),
            "grid": {"width": self.grid_width, "height": self.grid_height},
            "slots": [slot.to_dict() for slot in self.slots],
        }


def compile_formation(
    *,
    formation: str,
    hazard_cell: GridPoint,
    grid_width: int,
    grid_height: int,
    agent_count: int = 4,
) -> FormationPlan:
    """Compile a reviewed formation into deterministic grid target slots."""

    if formation not in SUPPORTED_FORMATIONS:
        raise ValueError(f"formation must be one of: {', '.join(SUPPORTED_FORMATIONS)}")
    if agent_count != 4:
        raise ValueError("current reviewed formations require exactly 4 agents")
    if not _in_bounds(hazard_cell, grid_width=grid_width, grid_height=grid_height):
        raise ValueError("hazard cell must be inside the grid")

    offsets = _formation_offsets(formation)
    slots = tuple(GridPoint(hazard_cell.x + dx, hazard_cell.y + dy) for dx, dy in offsets)
    return FormationPlan(
        schema_version=FORMATION_SCHEMA_VERSION,
        formation=formation,
        hazard_cell=hazard_cell,
        grid_width=grid_width,
        grid_height=grid_height,
        slots=slots,
    )


def assign_formation_slots(
    *,
    starts: tuple[AgentConfig, ...],
    plan: FormationPlan,
) -> tuple[AgentConfig, ...]:
    """Assign formation slots to agents with deterministic minimum travel cost."""

    if len(starts) != plan.agent_count:
        raise ValueError("agent count must match formation slots")
    agents = tuple(sorted(starts, key=lambda config: config.agent_id))
    best: tuple[int, tuple[tuple[int, int], ...], tuple[GridPoint, ...]] | None = None
    for candidate in permutations(plan.slots):
        cost = sum(_manhattan(config.start, slot) for config, slot in zip(agents, candidate))
        tie_break = tuple((slot.x, slot.y) for slot in candidate)
        key = (cost, tie_break, candidate)
        if best is None or key < best:
            best = key
    assert best is not None
    return tuple(
        AgentConfig(agent_id=config.agent_id, start=config.start, goal=slot)
        for config, slot in zip(agents, best[2])
    )


def _formation_offsets(formation: str) -> tuple[tuple[int, int], ...]:
    if formation == "x":
        return ((-1, -1), (1, -1), (-1, 1), (1, 1))
    if formation in {"surround", "diamond"}:
        return ((0, -1), (1, 0), (0, 1), (-1, 0))
    if formation == "line":
        return ((-2, 1), (-1, 1), (1, 1), (2, 1))
    raise ValueError(f"unsupported formation: {formation}")


def _manhattan(left: GridPoint, right: GridPoint) -> int:
    return abs(left.x - right.x) + abs(left.y - right.y)


def _in_bounds(point: GridPoint, *, grid_width: int, grid_height: int) -> bool:
    return 0 <= point.x < grid_width and 0 <= point.y < grid_height


def points_to_dicts(points: Iterable[GridPoint]) -> list[dict[str, int]]:
    """Return stable JSON-friendly point dictionaries."""

    return [point.to_dict() for point in sorted(points, key=lambda point: (point.x, point.y))]
