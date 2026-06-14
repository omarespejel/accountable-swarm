import json
from pathlib import Path
import subprocess
import sys
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]


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
        self.assertTrue((trace_dir / "mission.json").exists())
        for index in range(4):
            self.assertTrue((trace_dir / "agents" / f"sim-agent-{index}.json").exists())
