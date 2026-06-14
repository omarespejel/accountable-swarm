from unittest import TestCase

from accountable_swarm.swarm import (
    GridPoint,
    build_agent_traces,
    replay_swarm_traces,
    run_swarm_sim,
    scenario_names,
    scenario_spec,
)
from accountable_swarm.trace.models import canonical_json, trace_from_dict, verify_trace
from accountable_swarm.swarm.sim import AgentConfig, _choose_tick_steps


class SwarmSimTests(TestCase):
    def test_scenario_registry_centralizes_current_layouts(self) -> None:
        self.assertEqual(
            scenario_names(),
            ("corridor", "center-block", "vertical-slalom", "horizontal-slalom", "double-chicane"),
        )
        self.assertFalse(scenario_spec("corridor").use_reservation_planner)
        self.assertTrue(scenario_spec("center-block").use_reservation_planner)
        self.assertTrue(scenario_spec("vertical-slalom").use_reservation_planner)
        self.assertTrue(scenario_spec("horizontal-slalom").use_reservation_planner)
        self.assertTrue(scenario_spec("double-chicane").use_reservation_planner)
        self.assertEqual(scenario_spec("vertical-slalom").fixed_grid, (7, 5))
        self.assertEqual(scenario_spec("horizontal-slalom").fixed_grid, (7, 5))
        self.assertEqual(scenario_spec("double-chicane").fixed_grid, (7, 5))
        self.assertEqual(scenario_spec("center-block").default_ticks, 16)
        self.assertEqual(scenario_spec("double-chicane").default_ticks, 17)
        self.assertEqual(
            tuple((point.x, point.y) for point in scenario_spec("vertical-slalom").fixed_obstacles),
            ((3, 1), (3, 3)),
        )
        self.assertEqual(
            tuple((point.x, point.y) for point in scenario_spec("horizontal-slalom").fixed_obstacles),
            ((2, 2), (4, 2)),
        )
        self.assertEqual(
            tuple((point.x, point.y) for point in scenario_spec("double-chicane").fixed_obstacles),
            ((2, 1), (3, 1), (4, 2), (3, 3), (2, 3)),
        )
        self.assertEqual(scenario_spec("corridor").obstacles(grid_width=7, grid_height=5), frozenset())
        self.assertEqual(
            scenario_spec("center-block").obstacles(grid_width=7, grid_height=5),
            frozenset({GridPoint(3, 2)}),
        )
        self.assertEqual(
            scenario_spec("horizontal-slalom").obstacles(grid_width=7, grid_height=5),
            frozenset({GridPoint(2, 2), GridPoint(4, 2)}),
        )
        self.assertEqual(
            scenario_spec("double-chicane").obstacles(grid_width=7, grid_height=5),
            frozenset(
                {
                    GridPoint(2, 1),
                    GridPoint(3, 1),
                    GridPoint(4, 2),
                    GridPoint(3, 3),
                    GridPoint(2, 3),
                }
            ),
        )

    def test_n2_corridor_reaches_goals_without_collisions(self) -> None:
        result = run_swarm_sim(agent_count=2, ticks=8)
        traces = build_agent_traces(result)
        report = result.report_dict({agent_id: verify_trace(trace) for agent_id, trace in traces.items()})

        self.assertEqual(report["outcome"], "GO")
        self.assertTrue(report["all_goals_reached"])
        self.assertEqual(report["same_cell_collision_count"], 0)
        self.assertEqual(report["swap_collision_count"], 0)
        self.assertEqual(report["obstacle_occupancy_violation_count"], 0)
        self.assertGreaterEqual(report["reroute_count"], 1)

    def test_n2_traces_replay_deterministically(self) -> None:
        result = run_swarm_sim(agent_count=2, ticks=8)
        traces = build_agent_traces(result)

        self.assertEqual(sorted(traces), ["sim-agent-0", "sim-agent-1"])
        for trace in traces.values():
            self.assertEqual(verify_trace(trace), trace.summary_sha)
            self.assertEqual(len(trace.events), 8)

        replay = replay_swarm_traces(traces, obstacles=())
        self.assertEqual(replay.same_cell_collision_count, 0)
        self.assertEqual(replay.swap_collision_count, 0)
        self.assertEqual(replay.obstacle_occupancy_violation_count, 0)
        self.assertEqual(replay.final_positions["sim-agent-0"].to_dict(), {"x": 6, "y": 2})
        self.assertEqual(replay.final_positions["sim-agent-1"].to_dict(), {"x": 0, "y": 2})

    def test_n2_report_is_deterministic_and_float_free(self) -> None:
        left = run_swarm_sim(agent_count=2, ticks=8)
        right = run_swarm_sim(agent_count=2, ticks=8)
        left_traces = build_agent_traces(left)
        right_traces = build_agent_traces(right)

        left_report = left.report_dict(
            {agent_id: verify_trace(trace) for agent_id, trace in left_traces.items()}
        )
        right_report = right.report_dict(
            {agent_id: verify_trace(trace) for agent_id, trace in right_traces.items()}
        )
        self.assertEqual(canonical_json(left_report), canonical_json(right_report))

    def test_report_requires_trace_for_every_agent(self) -> None:
        result = run_swarm_sim(agent_count=2, ticks=8)
        traces = build_agent_traces(result)
        partial_report = result.report_dict({"sim-agent-0": verify_trace(traces["sim-agent-0"])})
        wrong_key_report = result.report_dict(
            {
                "sim-agent-0": verify_trace(traces["sim-agent-0"]),
                "not-an-agent": verify_trace(traces["sim-agent-1"]),
            }
        )
        bad_sha_report = result.report_dict(
            {"sim-agent-0": verify_trace(traces["sim-agent-0"]), "sim-agent-1": "not-a-sha"}
        )

        self.assertEqual(partial_report["outcome"], "NARROW_CLAIM")
        self.assertEqual(wrong_key_report["outcome"], "NARROW_CLAIM")
        self.assertEqual(bad_sha_report["outcome"], "NARROW_CLAIM")

    def test_center_block_n2_reaches_goals_without_obstacle_occupancy(self) -> None:
        result = run_swarm_sim(agent_count=2, ticks=9, scenario="center-block")
        traces = build_agent_traces(result)
        report = result.report_dict({agent_id: verify_trace(trace) for agent_id, trace in traces.items()})
        replay = replay_swarm_traces(traces, obstacles=result.obstacles)

        self.assertEqual(report["outcome"], "GO")
        self.assertEqual(report["scenario"], "center-block")
        self.assertEqual(report["obstacles"], [{"x": 3, "y": 2}])
        self.assertEqual(report["same_cell_collision_count"], 0)
        self.assertEqual(report["swap_collision_count"], 0)
        self.assertEqual(report["obstacle_occupancy_violation_count"], 0)
        self.assertGreaterEqual(report["reroute_count"], 2)
        self.assertEqual(replay.same_cell_collision_count, 0)
        self.assertEqual(replay.swap_collision_count, 0)
        self.assertEqual(replay.obstacle_occupancy_violation_count, 0)

    def test_center_block_n4_reservation_planner_reaches_goals(self) -> None:
        result = run_swarm_sim(agent_count=4, ticks=16, scenario="center-block")
        traces = build_agent_traces(result)
        report = result.report_dict({agent_id: verify_trace(trace) for agent_id, trace in traces.items()})
        replay = replay_swarm_traces(traces, obstacles=result.obstacles)

        self.assertEqual(report["outcome"], "GO")
        self.assertTrue(report["all_goals_reached"])
        self.assertEqual(report["agent_count"], 4)
        self.assertEqual(report["same_cell_collision_count"], 0)
        self.assertEqual(report["swap_collision_count"], 0)
        self.assertEqual(report["obstacle_occupancy_violation_count"], 0)
        self.assertEqual(replay.same_cell_collision_count, 0)
        self.assertEqual(replay.swap_collision_count, 0)
        self.assertEqual(replay.obstacle_occupancy_violation_count, 0)
        self.assertEqual(report["final_positions"], replay.to_dict()["final_positions"])
        self.assertEqual(set(report["trace_summary_shas"]), {f"sim-agent-{index}" for index in range(4)})
        for summary_sha in report["trace_summary_shas"].values():
            self.assertEqual(len(summary_sha), 64)

    def test_vertical_slalom_n4_reservation_planner_reaches_goals(self) -> None:
        result = run_swarm_sim(agent_count=4, ticks=16, scenario="vertical-slalom")
        traces = build_agent_traces(result)
        report = result.report_dict({agent_id: verify_trace(trace) for agent_id, trace in traces.items()})
        replay = replay_swarm_traces(traces, obstacles=result.obstacles)

        self.assertEqual(report["outcome"], "GO")
        self.assertTrue(report["all_goals_reached"])
        self.assertEqual(report["agent_count"], 4)
        self.assertEqual(report["scenario"], "vertical-slalom")
        self.assertEqual(report["obstacles"], [{"x": 3, "y": 1}, {"x": 3, "y": 3}])
        self.assertEqual(report["same_cell_collision_count"], 0)
        self.assertEqual(report["swap_collision_count"], 0)
        self.assertEqual(report["obstacle_occupancy_violation_count"], 0)
        self.assertEqual(replay.same_cell_collision_count, 0)
        self.assertEqual(replay.swap_collision_count, 0)
        self.assertEqual(replay.obstacle_occupancy_violation_count, 0)
        self.assertEqual(report["final_positions"], replay.to_dict()["final_positions"])

    def test_horizontal_slalom_n4_reservation_planner_reaches_goals(self) -> None:
        result = run_swarm_sim(agent_count=4, ticks=16, scenario="horizontal-slalom")
        traces = build_agent_traces(result)
        report = result.report_dict({agent_id: verify_trace(trace) for agent_id, trace in traces.items()})
        replay = replay_swarm_traces(traces, obstacles=result.obstacles)

        self.assertEqual(report["outcome"], "GO")
        self.assertTrue(report["all_goals_reached"])
        self.assertEqual(report["agent_count"], 4)
        self.assertEqual(report["scenario"], "horizontal-slalom")
        self.assertEqual(report["obstacles"], [{"x": 2, "y": 2}, {"x": 4, "y": 2}])
        self.assertEqual(report["same_cell_collision_count"], 0)
        self.assertEqual(report["swap_collision_count"], 0)
        self.assertEqual(report["obstacle_occupancy_violation_count"], 0)
        self.assertEqual(replay.same_cell_collision_count, 0)
        self.assertEqual(replay.swap_collision_count, 0)
        self.assertEqual(replay.obstacle_occupancy_violation_count, 0)
        self.assertEqual(report["final_positions"], replay.to_dict()["final_positions"])

    def test_double_chicane_n4_reservation_planner_reaches_goals_at_boundary(self) -> None:
        result = run_swarm_sim(agent_count=4, ticks=17, scenario="double-chicane")
        traces = build_agent_traces(result)
        report = result.report_dict({agent_id: verify_trace(trace) for agent_id, trace in traces.items()})
        replay = replay_swarm_traces(traces, obstacles=result.obstacles)

        self.assertEqual(report["outcome"], "GO")
        self.assertTrue(report["all_goals_reached"])
        self.assertEqual(report["agent_count"], 4)
        self.assertEqual(report["scenario"], "double-chicane")
        self.assertEqual(
            report["obstacles"],
            [{"x": 2, "y": 1}, {"x": 2, "y": 3}, {"x": 3, "y": 1}, {"x": 3, "y": 3}, {"x": 4, "y": 2}],
        )
        self.assertEqual(report["same_cell_collision_count"], 0)
        self.assertEqual(report["swap_collision_count"], 0)
        self.assertEqual(report["obstacle_occupancy_violation_count"], 0)
        self.assertEqual(replay.same_cell_collision_count, 0)
        self.assertEqual(replay.swap_collision_count, 0)
        self.assertEqual(replay.obstacle_occupancy_violation_count, 0)
        self.assertEqual(report["final_positions"], replay.to_dict()["final_positions"])
        self.assertGreaterEqual(report["reroute_count"], 20)

    def test_double_chicane_n4_one_tick_short_stays_narrow_claim(self) -> None:
        result = run_swarm_sim(agent_count=4, ticks=16, scenario="double-chicane")
        traces = build_agent_traces(result)
        report = result.report_dict({agent_id: verify_trace(trace) for agent_id, trace in traces.items()})

        self.assertEqual(report["outcome"], "NARROW_CLAIM")
        self.assertFalse(report["all_goals_reached"])
        self.assertEqual(report["same_cell_collision_count"], 0)
        self.assertEqual(report["swap_collision_count"], 0)
        self.assertEqual(report["obstacle_occupancy_violation_count"], 0)

    def test_vertical_slalom_rejects_non_fixed_grid(self) -> None:
        with self.assertRaisesRegex(ValueError, "fixed 7x5 grid"):
            run_swarm_sim(agent_count=4, ticks=16, scenario="vertical-slalom", grid_width=9)

    def test_vertical_slalom_obstacles_reject_non_fixed_grid(self) -> None:
        with self.assertRaisesRegex(ValueError, "fixed 7x5 grid"):
            scenario_spec("vertical-slalom").obstacles(grid_width=9, grid_height=5)

    def test_horizontal_slalom_rejects_non_fixed_grid(self) -> None:
        with self.assertRaisesRegex(ValueError, "fixed 7x5 grid"):
            run_swarm_sim(agent_count=4, ticks=16, scenario="horizontal-slalom", grid_width=9)

    def test_horizontal_slalom_obstacles_reject_non_fixed_grid(self) -> None:
        with self.assertRaisesRegex(ValueError, "fixed 7x5 grid"):
            scenario_spec("horizontal-slalom").obstacles(grid_width=9, grid_height=5)

    def test_double_chicane_rejects_non_fixed_grid(self) -> None:
        with self.assertRaisesRegex(ValueError, "fixed 7x5 grid"):
            run_swarm_sim(agent_count=4, ticks=17, scenario="double-chicane", grid_width=9)

    def test_double_chicane_obstacles_reject_non_fixed_grid(self) -> None:
        with self.assertRaisesRegex(ValueError, "fixed 7x5 grid"):
            scenario_spec("double-chicane").obstacles(grid_width=9, grid_height=5)

    def test_center_block_n4_short_run_stays_narrow_claim(self) -> None:
        result = run_swarm_sim(agent_count=4, ticks=2, scenario="center-block")
        traces = build_agent_traces(result)
        report = result.report_dict({agent_id: verify_trace(trace) for agent_id, trace in traces.items()})

        self.assertEqual(report["outcome"], "NARROW_CLAIM")
        self.assertFalse(report["all_goals_reached"])
        self.assertEqual(report["same_cell_collision_count"], 0)
        self.assertEqual(report["swap_collision_count"], 0)
        self.assertEqual(report["obstacle_occupancy_violation_count"], 0)

    def test_center_block_n4_planner_budget_exhaustion_stays_narrow_claim(self) -> None:
        result = run_swarm_sim(
            agent_count=4,
            ticks=16,
            scenario="center-block",
            planner_max_expansions=0,
        )
        traces = build_agent_traces(result)
        report = result.report_dict({agent_id: verify_trace(trace) for agent_id, trace in traces.items()})

        self.assertEqual(report["outcome"], "NARROW_CLAIM")
        self.assertEqual(report["same_cell_collision_count"], 0)
        self.assertEqual(report["swap_collision_count"], 0)
        self.assertEqual(report["obstacle_occupancy_violation_count"], 0)

    def test_negative_planner_budget_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            run_swarm_sim(agent_count=4, ticks=16, scenario="center-block", planner_max_expansions=-1)

    def test_replay_reports_obstacle_occupancy_when_supplied(self) -> None:
        result = run_swarm_sim(agent_count=2, ticks=8)
        traces = build_agent_traces(result)
        replay = replay_swarm_traces(traces, obstacles=(GridPoint(1, 2),))
        replay_from_dict = replay_swarm_traces(traces, obstacles=({"x": 1, "y": 2},))

        self.assertGreaterEqual(replay.obstacle_occupancy_violation_count, 1)
        self.assertEqual(replay.obstacle_occupancy_violation_count, replay_from_dict.obstacle_occupancy_violation_count)

    def test_replay_rejects_inconsistent_from_position(self) -> None:
        result = run_swarm_sim(agent_count=2, ticks=8)
        trace = build_agent_traces(result)["sim-agent-0"]
        value = trace.to_dict()
        value["events"][1]["command"]["from_x"] = 99
        tampered = trace_from_dict(value)

        with self.assertRaises(ValueError):
            replay_swarm_traces({"sim-agent-0": tampered}, obstacles=())

    def test_replay_rejects_missing_summary_sha(self) -> None:
        result = run_swarm_sim(agent_count=2, ticks=8)
        trace = build_agent_traces(result)["sim-agent-0"]
        value = trace.to_dict()
        value["summary_sha"] = ""
        unsigned = trace_from_dict(value)

        with self.assertRaises(ValueError):
            replay_swarm_traces({"sim-agent-0": unsigned}, obstacles=())

    def test_unsupported_scenario_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            run_swarm_sim(agent_count=2, ticks=8, scenario="unknown")

    def test_step_guard_does_not_reserve_unprocessed_agent_current_cell(self) -> None:
        configs = (
            AgentConfig("sim-agent-0", GridPoint(0, 0), GridPoint(2, 0)),
            AgentConfig("sim-agent-1", GridPoint(1, 0), GridPoint(0, 0)),
        )
        positions = {config.agent_id: config.start for config in configs}
        steps = _choose_tick_steps(
            tick=0,
            configs=configs,
            positions=positions,
            grid_width=3,
            grid_height=3,
            obstacles=frozenset(),
        )

        self.assertNotEqual(steps[0].accepted, positions["sim-agent-1"])

    def test_n4_exploratory_probe_reaches_goals_without_collisions(self) -> None:
        result = run_swarm_sim(agent_count=4, ticks=10)
        traces = build_agent_traces(result)
        report = result.report_dict({agent_id: verify_trace(trace) for agent_id, trace in traces.items()})

        self.assertEqual(report["outcome"], "GO")
        self.assertEqual(report["agent_count"], 4)
        self.assertEqual(report["same_cell_collision_count"], 0)
        self.assertEqual(report["swap_collision_count"], 0)
        self.assertGreaterEqual(report["reroute_count"], 1)

    def test_unsupported_agent_count_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            run_swarm_sim(agent_count=3, ticks=8)
