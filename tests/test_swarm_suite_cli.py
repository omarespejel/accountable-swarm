import json
from pathlib import Path
import subprocess
import sys
from unittest import TestCase

from accountable_swarm.trace.models import trace_from_dict, verify_trace


ROOT = Path(__file__).resolve().parents[1]


class SwarmSuiteCliTests(TestCase):
    def test_swarm_suite_writes_expected_go_and_narrow_cases(self) -> None:
        trace_root = ROOT / "runs/swarm/test-suite"
        report_path = ROOT / "runs/swarm/test_suite_report.json"
        result = subprocess.run(
            [
                sys.executable,
                "scripts/run_swarm_suite.py",
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
        self.assertEqual(report["schema_version"], "swarm-suite-report.v1")
        self.assertEqual(report["outcome"], "GO")
        self.assertEqual(report["case_count"], 4)
        self.assertTrue(all(report["pass_conditions"].values()))

        cases = {case["case_id"]: case for case in report["cases"]}
        self.assertEqual(
            {case_id: case["actual_outcome"] for case_id, case in sorted(cases.items())},
            {
                "n2-center-block-go": "GO",
                "n2-corridor-go": "GO",
                "n4-center-block-go": "GO",
                "n4-center-block-short-narrow": "NARROW_CLAIM",
            },
        )
        self.assertTrue(cases["n4-center-block-short-narrow"]["pass_conditions"]["outcome_matches_expected"])
        for case in cases.values():
            self.assertEqual(set(case["trace_summary_shas"]), {f"sim-agent-{index}" for index in range(case["agent_count"])})
            for agent_id, expected_sha in case["trace_summary_shas"].items():
                trace_path = Path(case["trace_dir"]) / f"{agent_id}.json"
                trace = trace_from_dict(json.loads(trace_path.read_text(encoding="utf-8")))
                self.assertEqual(verify_trace(trace), expected_sha)
            replay = case["sim_report"]["replay"]
            self.assertEqual(replay["same_cell_collision_count"], 0)
            self.assertEqual(replay["swap_collision_count"], 0)
            self.assertEqual(replay["obstacle_occupancy_violation_count"], 0)
