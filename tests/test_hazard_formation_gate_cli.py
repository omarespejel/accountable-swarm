import json
from pathlib import Path
import subprocess
import sys
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]


class HazardFormationGateCliTests(TestCase):
    def test_fixture_hazard_forms_x_and_writes_replayable_traces(self) -> None:
        trace_dir = ROOT / "runs/hazard_formation/test_fixture_x"
        report_path = ROOT / "runs/hazard_formation/test_fixture_x_report.json"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.run_hazard_formation_gate",
                "--image",
                "fixtures/hazard_marker.ppm",
                "--mode",
                "fixture",
                "--formation",
                "x",
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
        self.assertEqual(report["hazard"]["cell"], {"x": 3, "y": 2})
        self.assertEqual(report["formation"], "x")
        self.assertTrue(report["pass_conditions"]["hazard_cell_quantized"])
        self.assertTrue(report["pass_conditions"]["formation_run_go"])
        self.assertEqual(report["sim_report"]["same_cell_collision_count"], 0)
        self.assertEqual(report["sim_report"]["swap_collision_count"], 0)
        self.assertEqual(report["sim_report"]["obstacle_occupancy_violation_count"], 0)
        self.assertTrue((trace_dir / "hazard.json").is_file())
        self.assertTrue((trace_dir / "agents" / "sim-agent-0.json").is_file())

    def test_degraded_mode_writes_hold_traces_without_model(self) -> None:
        trace_dir = ROOT / "runs/hazard_formation/test_degraded"
        report_path = ROOT / "runs/hazard_formation/test_degraded_report.json"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.run_hazard_formation_gate",
                "--image",
                "fixtures/hazard_marker.ppm",
                "--mode",
                "degraded",
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

        self.assertEqual(report["outcome"], "DEGRADED")
        self.assertIsNone(report["hazard"])
        self.assertTrue(report["pass_conditions"]["degraded_hold_selected"])
        self.assertEqual(report["sim_report"]["hold_count"], 4)
        self.assertEqual(report["sim_report"]["same_cell_collision_count"], 0)

    def test_dashscope_missing_key_can_degrade_to_hold(self) -> None:
        trace_dir = ROOT / "runs/hazard_formation/test_missing_key"
        report_path = ROOT / "runs/hazard_formation/test_missing_key_report.json"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.run_hazard_formation_gate",
                "--image",
                "fixtures/hazard_marker.ppm",
                "--mode",
                "dashscope",
                "--degraded-on-error",
                "--trace-dir",
                str(trace_dir),
                "--report-out",
                str(report_path),
            ],
            cwd=ROOT,
            env={},
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(report["outcome"], "DEGRADED")
        self.assertIn("ALIBABA_API_KEY", report["model_error"])
        self.assertTrue(report["pass_conditions"]["degraded_hold_selected"])

    def test_dashscope_missing_key_fails_closed_without_degrade_flag(self) -> None:
        trace_dir = ROOT / "runs/hazard_formation/test_missing_key_fail"
        report_path = ROOT / "runs/hazard_formation/test_missing_key_fail_report.json"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.run_hazard_formation_gate",
                "--image",
                "fixtures/hazard_marker.ppm",
                "--mode",
                "dashscope",
                "--trace-dir",
                str(trace_dir),
                "--report-out",
                str(report_path),
            ],
            cwd=ROOT,
            env={},
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 3)
        self.assertIn("ALIBABA_API_KEY", result.stderr)
