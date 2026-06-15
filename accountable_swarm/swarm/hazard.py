"""Hazard-cell quantization from validated 2D perception."""

from __future__ import annotations

from dataclasses import dataclass

from accountable_swarm.qwen.bbox import QwenGrounding
from accountable_swarm.swarm.sim import GridPoint
from accountable_swarm.trace.models import PerceptionEvent

HAZARD_GRID_SCHEMA_VERSION = "hazard-grid.v1"


@dataclass(frozen=True)
class HazardCell:
    """Integer-grid hazard derived from a validated 2D bbox center."""

    schema_version: str
    cell: GridPoint
    grid_width: int
    grid_height: int
    source_label: str
    bbox_2d_norm_1000: tuple[int, int, int, int]
    bbox_2d_px: tuple[int, int, int, int]

    def __post_init__(self) -> None:
        if self.schema_version != HAZARD_GRID_SCHEMA_VERSION:
            raise ValueError(f"unsupported hazard grid schema: {self.schema_version}")
        if self.grid_width <= 0 or self.grid_height <= 0:
            raise ValueError("grid dimensions must be positive")
        if not 0 <= self.cell.x < self.grid_width or not 0 <= self.cell.y < self.grid_height:
            raise ValueError("hazard cell must be inside the grid")
        if not self.source_label.strip():
            raise ValueError("source_label must be non-empty")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "cell": self.cell.to_dict(),
            "grid": {"width": self.grid_width, "height": self.grid_height},
            "source_label": self.source_label,
            "bbox_2d_norm_1000": list(self.bbox_2d_norm_1000),
            "bbox_2d_px": list(self.bbox_2d_px),
        }


def hazard_cell_from_grounding(
    grounding: QwenGrounding,
    *,
    grid_width: int,
    grid_height: int,
) -> HazardCell:
    """Quantize a Qwen bbox center into a grid hazard cell."""

    return _hazard_cell_from_bbox(
        label=grounding.label,
        bbox_2d_norm_1000=grounding.bbox_2d_norm_1000,
        bbox_2d_px=grounding.bbox_2d_px,
        grid_width=grid_width,
        grid_height=grid_height,
    )


def hazard_cell_from_perception(
    perception: PerceptionEvent,
    *,
    grid_width: int,
    grid_height: int,
) -> HazardCell:
    """Quantize a persisted perception event into a grid hazard cell."""

    return _hazard_cell_from_bbox(
        label=perception.label,
        bbox_2d_norm_1000=perception.bbox_2d_norm_1000,
        bbox_2d_px=perception.bbox_2d_px,
        grid_width=grid_width,
        grid_height=grid_height,
    )


def _hazard_cell_from_bbox(
    *,
    label: str,
    bbox_2d_norm_1000: tuple[int, int, int, int],
    bbox_2d_px: tuple[int, int, int, int],
    grid_width: int,
    grid_height: int,
) -> HazardCell:
    if grid_width <= 0 or grid_height <= 0:
        raise ValueError("grid dimensions must be positive")
    _validate_norm_1000_bbox(bbox_2d_norm_1000)
    x1, y1, x2, y2 = bbox_2d_norm_1000
    if x1 >= x2 or y1 >= y2:
        raise ValueError("bbox must have positive area")
    center_x_norm = (x1 + x2) // 2
    center_y_norm = (y1 + y2) // 2
    cell = GridPoint(
        x=min(grid_width - 1, (center_x_norm * grid_width) // 1000),
        y=min(grid_height - 1, (center_y_norm * grid_height) // 1000),
    )
    return HazardCell(
        schema_version=HAZARD_GRID_SCHEMA_VERSION,
        cell=cell,
        grid_width=grid_width,
        grid_height=grid_height,
        source_label=label,
        bbox_2d_norm_1000=bbox_2d_norm_1000,
        bbox_2d_px=bbox_2d_px,
    )


def _validate_norm_1000_bbox(bbox_2d_norm_1000: tuple[int, int, int, int]) -> None:
    if len(bbox_2d_norm_1000) != 4:
        raise ValueError("bbox must contain four normalized coordinates")
    for value in bbox_2d_norm_1000:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("bbox normalized coordinates must be integers")
        if value < 0 or value > 1000:
            raise ValueError("bbox normalized coordinates must be in 0..1000")
