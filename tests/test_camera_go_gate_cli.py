import json
from pathlib import Path
import subprocess
import sys
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]


class CameraGoGateCliTests(TestCase):
    def test_fixture_static_frame_writes_trace_and_report(self) -> None:
        trace_path = ROOT / "runs/go_gate/test_camera_trace.json"
        report_path = ROOT / "runs/go_gate/test_camera_report.json"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.run_camera_go_gate",
                "--image",
                "fixtures/hazard_marker.ppm",
                "--mode",
                "fixture",
                "--trace-out",
                str(trace_path),
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
        self.assertEqual(report["outcome"], "NARROW_CLAIM")
        self.assertFalse(report["pass_conditions"]["model_responded"])
        self.assertTrue(report["pass_conditions"]["json_validated"])
        self.assertTrue(report["pass_conditions"]["bbox_rescaled"])
        self.assertTrue(report["pass_conditions"]["trace_replay_deterministic"])
        self.assertTrue(report["pass_conditions"]["frame_emits_decisiontrace_schema"])

    def test_degraded_static_frame_writes_safe_hold_trace(self) -> None:
        trace_path = ROOT / "runs/go_gate/test_camera_degraded_trace.json"
        report_path = ROOT / "runs/go_gate/test_camera_degraded_report.json"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.run_camera_go_gate",
                "--image",
                "fixtures/hazard_marker.ppm",
                "--mode",
                "degraded",
                "--trace-out",
                str(trace_path),
                "--report-out",
                str(report_path),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["outcome"], "DEGRADED")
        self.assertEqual(trace["events"][0]["decision"], "HOLD")
        self.assertFalse(report["pass_conditions"]["model_responded"])
