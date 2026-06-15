from unittest import TestCase

from accountable_swarm.swarm import (
    GridPoint,
    assign_formation_slots,
    build_agent_traces,
    compile_formation,
    default_agent_configs,
    points_to_dicts,
    replay_swarm_traces,
    run_swarm_custom,
)
from accountable_swarm.trace.models import canonical_json, verify_trace


class SwarmFormationTests(TestCase):
    def test_compile_x_formation_around_hazard(self) -> None:
        plan = compile_formation(
            formation="x",
            hazard_cell=GridPoint(3, 2),
            grid_width=7,
            grid_height=5,
        )

        self.assertEqual(plan.agent_count, 4)
        self.assertEqual(
            [slot.to_dict() for slot in plan.slots],
            [{"x": 2, "y": 1}, {"x": 4, "y": 1}, {"x": 2, "y": 3}, {"x": 4, "y": 3}],
        )
        self.assertNotIn(plan.hazard_cell, plan.slots)
        self.assertEqual(canonical_json(plan.to_dict()), canonical_json(plan.to_dict()))

    def test_compile_surround_and_diamond_use_cardinal_slots(self) -> None:
        surround = compile_formation(
            formation="surround",
            hazard_cell=GridPoint(3, 2),
            grid_width=7,
            grid_height=5,
        )
        diamond = compile_formation(
            formation="diamond",
            hazard_cell=GridPoint(3, 2),
            grid_width=7,
            grid_height=5,
        )

        expected = [{"x": 3, "y": 1}, {"x": 4, "y": 2}, {"x": 3, "y": 3}, {"x": 2, "y": 2}]
        self.assertEqual([slot.to_dict() for slot in surround.slots], expected)
        self.assertEqual([slot.to_dict() for slot in diamond.slots], expected)

    def test_compile_line_requires_in_bounds_slots(self) -> None:
        plan = compile_formation(
            formation="line",
            hazard_cell=GridPoint(3, 2),
            grid_width=7,
            grid_height=5,
        )
        self.assertEqual(
            [slot.to_dict() for slot in plan.slots],
            [{"x": 1, "y": 3}, {"x": 2, "y": 3}, {"x": 4, "y": 3}, {"x": 5, "y": 3}],
        )
        with self.assertRaisesRegex(ValueError, "formation slot must be inside"):
            compile_formation(
                formation="line",
                hazard_cell=GridPoint(1, 3),
                grid_width=7,
                grid_height=5,
            )

    def test_assignment_is_deterministic_and_minimizes_total_travel(self) -> None:
        starts = default_agent_configs(4, grid_width=7, grid_height=5)
        plan = compile_formation(
            formation="x",
            hazard_cell=GridPoint(3, 2),
            grid_width=7,
            grid_height=5,
        )

        assigned = assign_formation_slots(starts=starts, plan=plan)

        self.assertEqual([config.agent_id for config in assigned], [f"sim-agent-{index}" for index in range(4)])
        self.assertEqual(
            [config.goal.to_dict() for config in assigned],
            [{"x": 2, "y": 1}, {"x": 4, "y": 3}, {"x": 4, "y": 1}, {"x": 2, "y": 3}],
        )

    def test_custom_formation_run_reaches_slots_without_occupying_hazard(self) -> None:
        starts = default_agent_configs(4, grid_width=7, grid_height=5)
        hazard = GridPoint(3, 2)
        plan = compile_formation(
            formation="x",
            hazard_cell=hazard,
            grid_width=7,
            grid_height=5,
        )
        configs = assign_formation_slots(starts=starts, plan=plan)

        result = run_swarm_custom(
            configs=configs,
            obstacles=(hazard,),
            ticks=8,
            grid_width=7,
            grid_height=5,
            scenario="hazard-x-formation",
        )
        traces = build_agent_traces(result)
        trace_shas = {agent_id: verify_trace(trace) for agent_id, trace in traces.items()}
        report = result.report_dict(trace_shas)
        replay = replay_swarm_traces(traces, obstacles=result.obstacles)

        self.assertEqual(report["outcome"], "GO")
        self.assertTrue(report["all_goals_reached"])
        self.assertEqual(report["obstacle_occupancy_violation_count"], 0)
        self.assertEqual(replay.obstacle_occupancy_violation_count, 0)
        self.assertEqual(report["final_positions"], replay.to_dict()["final_positions"])

    def test_points_to_dicts_sorts_unordered_points(self) -> None:
        points = {GridPoint(4, 3), GridPoint(1, 2), GridPoint(1, 1)}

        self.assertEqual(
            points_to_dicts(points),
            [{"x": 1, "y": 1}, {"x": 1, "y": 2}, {"x": 4, "y": 3}],
        )
