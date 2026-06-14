import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase

from accountable_swarm.swarm import SUPPORTED_MISSION_SCENARIOS
from accountable_swarm.trace.models import trace_from_dict, verify_trace


ROOT = Path(__file__).resolve().parents[1]


class SwarmMissionSuiteCliTests(TestCase):
    def test_mission_suite_writes_expected_fixture_cases(self) -> None:
        with TemporaryDirectory() as tmpdir:
            trace_root = Path(tmpdir) / "mission-suite"
            report_path = Path(tmpdir) / "mission_suite_report.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/run_swarm_mission_suite.py",
                    "--trace-root",
                    str(trace_root),
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
            self.assertEqual(report["schema_version"], "swarm-mission-suite-report.v1")
            self.assertEqual(report["outcome"], "GO")
            self.assertEqual(report["case_count"], len(SUPPORTED_MISSION_SCENARIOS))
            self.assertEqual(report["covered_mission_scenarios"], sorted(SUPPORTED_MISSION_SCENARIOS))
            self.assertTrue(all(report["pass_conditions"].values()))

            cases = {case["mission_scenario"]: case for case in report["cases"]}
            self.assertEqual(set(cases), set(SUPPORTED_MISSION_SCENARIOS))
            for scenario, case in sorted(cases.items()):
                self.assertNotIn("trace_dir", case)
                self.assertEqual(case["mode"], "fixture")
                self.assertEqual(case["expected_outcome"], "GO")
                self.assertEqual(case["actual_outcome"], "GO")
                self.assertEqual(case["mission_gate_report"]["outcome"], "GO")
                self.assertEqual(case["mission_gate_report"]["mission"]["scenario"], scenario)
                self.assertTrue(all(case["pass_conditions"].values()))
                self.assertTrue(all(case["mission_gate_report"]["pass_conditions"].values()))

                mission_trace_path = trace_root / case["trace_files"]["mission"]
                mission_trace = trace_from_dict(json.loads(mission_trace_path.read_text(encoding="utf-8")))
                self.assertEqual(verify_trace(mission_trace), case["mission_trace_summary_sha"])

                agent_files = case["trace_files"]["agents"]
                self.assertEqual(set(agent_files), set(case["trace_summary_shas"]))
                for agent_id, relative_path in sorted(agent_files.items()):
                    agent_trace = trace_from_dict(
                        json.loads((trace_root / relative_path).read_text(encoding="utf-8"))
                    )
                    self.assertEqual(verify_trace(agent_trace), case["trace_summary_shas"][agent_id])

                sim_report = case["mission_gate_report"]["sim_report"]
                replay = sim_report["replay"]
                self.assertEqual(sim_report["outcome"], "GO")
                self.assertEqual(replay["same_cell_collision_count"], 0)
                self.assertEqual(replay["swap_collision_count"], 0)
                self.assertEqual(replay["obstacle_occupancy_violation_count"], 0)
