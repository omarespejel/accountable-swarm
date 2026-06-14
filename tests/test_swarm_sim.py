from unittest import TestCase

from accountable_swarm.swarm import build_agent_traces, replay_swarm_traces, run_swarm_sim
from accountable_swarm.trace.models import canonical_json, trace_from_dict, verify_trace


class SwarmSimTests(TestCase):
    def test_n2_corridor_reaches_goals_without_collisions(self) -> None:
        result = run_swarm_sim(agent_count=2, ticks=8)
        traces = build_agent_traces(result)
        report = result.report_dict({agent_id: verify_trace(trace) for agent_id, trace in traces.items()})

        self.assertEqual(report["outcome"], "GO")
        self.assertTrue(report["all_goals_reached"])
        self.assertEqual(report["same_cell_collision_count"], 0)
        self.assertEqual(report["swap_collision_count"], 0)
        self.assertGreaterEqual(report["reroute_count"], 1)

    def test_n2_traces_replay_deterministically(self) -> None:
        result = run_swarm_sim(agent_count=2, ticks=8)
        traces = build_agent_traces(result)

        self.assertEqual(sorted(traces), ["sim-agent-0", "sim-agent-1"])
        for trace in traces.values():
            self.assertEqual(verify_trace(trace), trace.summary_sha)
            self.assertEqual(len(trace.events), 8)

        replay = replay_swarm_traces(traces)
        self.assertEqual(replay.same_cell_collision_count, 0)
        self.assertEqual(replay.swap_collision_count, 0)
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

    def test_replay_rejects_inconsistent_from_position(self) -> None:
        result = run_swarm_sim(agent_count=2, ticks=8)
        trace = build_agent_traces(result)["sim-agent-0"]
        value = trace.to_dict()
        value["events"][1]["command"]["from_x"] = 99
        tampered = trace_from_dict(value)

        with self.assertRaises(ValueError):
            replay_swarm_traces({"sim-agent-0": tampered})

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
