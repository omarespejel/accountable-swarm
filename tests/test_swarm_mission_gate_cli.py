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

    def test_dashscope_mission_response_uses_text_client(self) -> None:
        module = _load_mission_gate_module()
        calls = []

        class FakeClient:
            def __init__(self, *, model: str) -> None:
                calls.append(("init", model))

            def chat_text(self, *, prompt: str, max_tokens: int) -> str:
                calls.append(("chat_text", prompt, max_tokens))
                return fixture_mission_response()

        original = module.DashScopeQwenClient
        try:
            module.DashScopeQwenClient = FakeClient
            response = module._mission_response(mode="dashscope", model="fake-qwen")
        finally:
            module.DashScopeQwenClient = original

        self.assertEqual(response, fixture_mission_response())
        self.assertEqual(calls[0], ("init", "fake-qwen"))
        self.assertEqual(calls[1][0], "chat_text")
        self.assertIn("schema_version", calls[1][1])
        self.assertEqual(calls[1][2], 256)


def _load_mission_gate_module():
    spec = importlib.util.spec_from_file_location("mission_gate_for_test", MISSION_GATE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load mission gate script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
