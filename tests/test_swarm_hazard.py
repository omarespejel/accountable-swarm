from unittest import TestCase

from accountable_swarm.qwen.bbox import QwenGrounding
from accountable_swarm.swarm import GridPoint, hazard_cell_from_grounding
from accountable_swarm.trace.models import PerceptionEvent, canonical_json


class SwarmHazardTests(TestCase):
    def test_center_bbox_maps_to_center_grid_cell(self) -> None:
        grounding = QwenGrounding(
            label="hazard marker",
            bbox_2d_norm_1000=(450, 350, 550, 650),
            bbox_2d_px=(288, 126, 352, 234),
        )

        hazard = hazard_cell_from_grounding(grounding, grid_width=7, grid_height=5)

        self.assertEqual(hazard.cell, GridPoint(3, 2))
        self.assertEqual(hazard.source_label, "hazard marker")
        self.assertEqual(canonical_json(hazard.to_dict()), canonical_json(hazard.to_dict()))

    def test_edge_bbox_clamps_to_last_grid_cell(self) -> None:
        grounding = QwenGrounding(
            label="hazard marker",
            bbox_2d_norm_1000=(980, 900, 1000, 1000),
            bbox_2d_px=(627, 324, 640, 360),
        )

        hazard = hazard_cell_from_grounding(grounding, grid_width=7, grid_height=5)

        self.assertEqual(hazard.cell, GridPoint(6, 4))

    def test_invalid_bbox_is_rejected(self) -> None:
        grounding = QwenGrounding(
            label="hazard marker",
            bbox_2d_norm_1000=(500, 500, 500, 600),
            bbox_2d_px=(320, 180, 320, 216),
        )

        with self.assertRaisesRegex(ValueError, "positive area"):
            hazard_cell_from_grounding(grounding, grid_width=7, grid_height=5)

    def test_out_of_range_norm_bbox_is_rejected(self) -> None:
        grounding = QwenGrounding(
            label="hazard marker",
            bbox_2d_norm_1000=(900, 900, 1200, 1000),
            bbox_2d_px=(576, 324, 768, 360),
        )

        with self.assertRaisesRegex(ValueError, "0..1000"):
            hazard_cell_from_grounding(grounding, grid_width=7, grid_height=5)

    def test_bool_norm_bbox_is_rejected(self) -> None:
        grounding = QwenGrounding(
            label="hazard marker",
            bbox_2d_norm_1000=(False, 0, 250, 250),
            bbox_2d_px=(0, 0, 160, 90),
        )

        with self.assertRaisesRegex(ValueError, "must be integers"):
            hazard_cell_from_grounding(grounding, grid_width=7, grid_height=5)

    def test_perception_event_can_be_quantized_without_floats(self) -> None:
        perception = PerceptionEvent(
            event_id="perception-0001",
            source="image://frame.png",
            image_width=640,
            image_height=360,
            label="hazard",
            bbox_2d_norm_1000=(0, 0, 250, 250),
            bbox_2d_px=(0, 0, 160, 90),
            model="fixture",
        )

        from accountable_swarm.swarm import hazard_cell_from_perception

        hazard = hazard_cell_from_perception(perception, grid_width=7, grid_height=5)

        self.assertEqual(hazard.cell, GridPoint(0, 0))
