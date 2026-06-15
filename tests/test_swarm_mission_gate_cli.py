import json
import importlib.util
from pathlib import Path
import subprocess
import sys
from unittest import TestCase

from accountable_swarm.swarm import fixture_mission_response
from accountable_swarm.trace.models import trace_from_dict, verify_trace


ROOT = Path(__file__).resolve().parents[1]
MISSION_GATE_SCRIPT = ROOT / "scripts/run_swarm_mission_gate.py"


class SwarmMissionGateCliTests(TestCase):
    def test_fixture_mission_gate_writes_report_and_traces(self) -> None:
        trace_dir = ROOT / "runs/swarm/test-mission-fixture-n4"
        report_path = ROOT / "runs/swarm/test_mission_fixture_n4_report.json"
        result = subprocess.run(
            [
                sys.executable,
                "scripts/run_swarm_mission_gate.py",
                "--mode",
                "fixture",
                "--trace-dir",
                str(trace_dir),
                "--report-out",
                str(report_path),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["outcome"], "GO")
        self.assertEqual(report["mode"], "fixture")
        self.assertTrue(report["mission_validated"])
        self.assertEqual(report["mission"]["scenario"], "center-block")
        self.assertEqual(report["mission"]["agent_count"], 4)
        self.assertEqual(report["mission"]["ticks"], 16)
        self.assertEqual(report["sim_report"]["outcome"], "GO")
        self.assertEqual(report["sim_report"]["same_cell_collision_count"], 0)
        self.assertEqual(report["sim_report"]["swap_collision_count"], 0)
        self.assertEqual(report["sim_report"]["obstacle_occupancy_violation_count"], 0)
        self.assertEqual(len(report["mission_trace_summary_sha"]), 64)
        self.assertEqual(set(report["trace_summary_shas"]), {f"sim-agent-{index}" for index in range(4)})
        mission_trace = trace_from_dict(
            json.loads((trace_dir / "mission.json").read_text(encoding="utf-8"))
        )
        self.assertEqual(verify_trace(mission_trace), report["mission_trace_summary_sha"])
        self.assertTrue(report["pass_conditions"]["agent_traces_replay_deterministic"])
        for index in range(4):
            agent_id = f"sim-agent-{index}"
            agent_trace = trace_from_dict(
                json.loads((trace_dir / "agents" / f"{agent_id}.json").read_text(encoding="utf-8"))
            )
            self.assertEqual(verify_trace(agent_trace), report["trace_summary_shas"][agent_id])

    def test_fixture_mission_gate_accepts_registered_horizontal_slalom(self) -> None:
        trace_dir = ROOT / "runs/swarm/test-mission-horizontal-slalom-fixture-n4"
        report_path = ROOT / "runs/swarm/test_mission_horizontal_slalom_fixture_n4_report.json"
        result = subprocess.run(
            [
                sys.executable,
                "scripts/run_swarm_mission_gate.py",
                "--mode",
                "fixture",
                "--mission-scenario",
                "horizontal-slalom",
                "--trace-dir",
                str(trace_dir),
                "--report-out",
                str(report_path),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["outcome"], "GO")
        self.assertEqual(report["mode"], "fixture")
        self.assertEqual(report["mission"]["mission_id"], "horizontal-slalom-n4")
        self.assertEqual(report["mission"]["scenario"], "horizontal-slalom")
        self.assertEqual(report["mission"]["agent_count"], 4)
        self.assertEqual(report["mission"]["ticks"], 16)
        self.assertEqual(report["sim_report"]["outcome"], "GO")
        self.assertEqual(report["sim_report"]["scenario"], "horizontal-slalom")
        self.assertEqual(report["sim_report"]["obstacles"], [{"x": 2, "y": 2}, {"x": 4, "y": 2}])
        self.assertEqual(report["sim_report"]["same_cell_collision_count"], 0)
        self.assertEqual(report["sim_report"]["swap_collision_count"], 0)
        self.assertEqual(report["sim_report"]["obstacle_occupancy_violation_count"], 0)
        self.assertTrue(report["pass_conditions"]["mission_trace_replay_deterministic"])
        self.assertTrue(report["pass_conditions"]["agent_traces_replay_deterministic"])
        self.assertTrue(report["pass_conditions"]["agent_trace_replay_counts_zero"])

    def test_dashscope_mission_response_uses_text_client(self) -> None:
        module = _load_mission_gate_module()
        calls = []
        objective_response = '{"objective":"route agents through the selected fixed scenario"}'

        class FakeClient:
            def __init__(self, *, model: str) -> None:
                calls.append(("init", model))

            def chat_text(self, *, prompt: str, max_tokens: int) -> str:
                calls.append(("chat_text", prompt, max_tokens))
                return objective_response

        original = module.DashScopeQwenClient
        try:
            module.DashScopeQwenClient = FakeClient
            response = module._mission_response(
                mode="dashscope",
                model="fake-qwen",
                scenario="horizontal-slalom",
            )
        finally:
            module.DashScopeQwenClient = original

        self.assertEqual(response, objective_response)
        self.assertEqual(calls[0], ("init", "fake-qwen"))
        self.assertEqual(calls[1][0], "chat_text")
        self.assertIn("exactly one key: objective", calls[1][1])
        self.assertIn("horizontal-slalom", calls[1][1])
        self.assertIn("do not output scenario, mission_id, agent_count, ticks", calls[1][1])
        self.assertEqual(calls[1][2], 256)

    def test_dashscope_spec_binds_requested_scenario_from_intent_only(self) -> None:
        module = _load_mission_gate_module()
        spec = module._mission_spec_from_response(
            response_text='{"objective":"route agents through the selected fixed scenario"}',
            mode="dashscope",
            requested_scenario="horizontal-slalom",
        )

        self.assertEqual(spec.mission_id, "horizontal-slalom-n4")
        self.assertEqual(spec.scenario, "horizontal-slalom")
        self.assertEqual(spec.agent_count, 4)
        self.assertEqual(spec.ticks, 16)

    def test_dashscope_spec_rejects_hidden_control_metadata_inside_objective(self) -> None:
        module = _load_mission_gate_module()

        with self.assertRaisesRegex(ValueError, "numeric control metadata"):
            module._mission_spec_from_response(
                response_text='{"objective":"route 5 agents through the selected fixed layout"}',
                mode="dashscope",
                requested_scenario="horizontal-slalom",
            )

    def test_fixture_spec_rejects_mismatched_requested_scenario(self) -> None:
        module = _load_mission_gate_module()

        with self.assertRaisesRegex(ValueError, "mission scenario mismatch"):
            module._mission_spec_from_response(
                response_text=fixture_mission_response(scenario="center-block"),
                mode="fixture",
                requested_scenario="horizontal-slalom",
            )

    def test_fixture_spec_rejects_mismatched_mission_id(self) -> None:
        module = _load_mission_gate_module()
        value = json.loads(fixture_mission_response(scenario="horizontal-slalom"))
        value["mission_id"] = "wrong-id"

        with self.assertRaisesRegex(ValueError, "mission_id mismatch"):
            module._mission_spec_from_response(
                response_text=json.dumps(value),
                mode="fixture",
                requested_scenario="horizontal-slalom",
            )


def _load_mission_gate_module():
    spec = importlib.util.spec_from_file_location("mission_gate_for_test", MISSION_GATE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load mission gate script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
