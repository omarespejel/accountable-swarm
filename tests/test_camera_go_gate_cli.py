import json
from pathlib import Path
import subprocess
import sys
from unittest import TestCase
from unittest.mock import patch

from scripts import run_camera_go_gate


ROOT = Path(__file__).resolve().parents[1]


class CameraGoGateCliTests(TestCase):
    def test_dashscope_retries_malformed_bbox_once(self) -> None:
        class FakeClient:
            calls = 0

            def __init__(self, *, model: str) -> None:
                self.model = model

            def detect_bbox(self, *, image_path: Path, target: str) -> str:
                FakeClient.calls += 1
                if FakeClient.calls == 1:
                    return '[["malformed"]]'
                return '[{"bbox_2d":[250,250,750,750],"label":"marked hazard"}]'

        with patch.object(run_camera_go_gate, "DashScopeQwenClient", FakeClient):
            _trace, conditions, model_error = run_camera_go_gate._build_trace(
                image_path=ROOT / "fixtures" / "hazard_marker.ppm",
                source_kind="static_image",
                mode="dashscope",
                target="marked hazard",
                model="fake-qwen",
            )

        self.assertEqual(FakeClient.calls, 2)
        self.assertTrue(conditions["json_validated"])
        self.assertEqual(model_error, "")

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

    def test_dashscope_without_key_returns_controlled_error(self) -> None:
        trace_path = ROOT / "runs/go_gate/test_camera_missing_key_trace.json"
        report_path = ROOT / "runs/go_gate/test_camera_missing_key_report.json"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.run_camera_go_gate",
                "--image",
                "fixtures/hazard_marker.ppm",
                "--mode",
                "dashscope",
                "--trace-out",
                str(trace_path),
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
        self.assertNotIn("NameError", result.stderr)
