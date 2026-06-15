import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from accountable_swarm.trace.models import trace_from_dict, verify_trace
from scripts import run_go_gate


ROOT = Path(__file__).resolve().parents[1]


class GoGateCliTests(TestCase):
    def test_fixture_hazard_frame_emits_veto_trace(self) -> None:
        with TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "hazard.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/run_go_gate.py",
                    "--image",
                    "fixtures/hazard_marker.ppm",
                    "--mode",
                    "fixture",
                    "--out",
                    str(out),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("decision VETO", result.stdout)
            trace = trace_from_dict(json.loads(out.read_text(encoding="utf-8")))
            self.assertEqual(trace.events[0].decision, "VETO")
            self.assertEqual(trace.events[0].command["type"], "hold")
            verify_trace(trace)

    def test_fixture_clear_frame_emits_move_trace(self) -> None:
        with TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "clear.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/run_go_gate.py",
                    "--image",
                    "fixtures/clear_frame.ppm",
                    "--mode",
                    "fixture",
                    "--out",
                    str(out),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("decision MOVE", result.stdout)
            trace = trace_from_dict(json.loads(out.read_text(encoding="utf-8")))
            self.assertEqual(trace.events[0].decision, "MOVE")
            self.assertEqual(trace.events[0].command["type"], "move")
            self.assertEqual(trace.events[0].perception.label, "clear frame")
            verify_trace(trace)

    def test_dashscope_grounding_retries_once_after_malformed_bbox(self) -> None:
        class FakeClient:
            calls = 0

            def __init__(self, *, model: str) -> None:
                self.model = model

            def detect_bbox(self, *, image_path: Path, target: str) -> str:
                FakeClient.calls += 1
                if FakeClient.calls == 1:
                    return "not json"
                return '[{"bbox_2d":[250,250,750,750],"label":"marked hazard"}]'

        with patch.object(run_go_gate, "DashScopeQwenClient", FakeClient):
            grounding = run_go_gate._get_grounding(
                "dashscope",
                image_path=ROOT / "fixtures" / "hazard_marker.ppm",
                target="marked hazard",
                model="fake-qwen",
                image_width=4,
                image_height=4,
            )

        self.assertIsNotNone(grounding)
        self.assertEqual(FakeClient.calls, 2)
        self.assertEqual(grounding.label, "marked hazard")

    def test_dashscope_grounding_fails_after_one_retry(self) -> None:
        class BadClient:
            calls = 0

            def __init__(self, *, model: str) -> None:
                self.model = model

            def detect_bbox(self, *, image_path: Path, target: str) -> str:
                BadClient.calls += 1
                return "not json"

        with patch.object(run_go_gate, "DashScopeQwenClient", BadClient):
            with self.assertRaises(ValueError):
                run_go_gate._get_grounding(
                    "dashscope",
                    image_path=ROOT / "fixtures" / "hazard_marker.ppm",
                    target="marked hazard",
                    model="fake-qwen",
                    image_width=4,
                    image_height=4,
                )

        self.assertEqual(BadClient.calls, 2)

    def test_directory_image_path_fails_cleanly(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "scripts/run_go_gate.py",
                "--image",
                "fixtures",
                "--mode",
                "fixture",
                "--out",
                "runs/go_gate/should_not_exist.json",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("image is not a file", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_dashscope_ppm_failure_is_clean(self) -> None:
        env = dict(os.environ)
        env["ALIBABA_API_KEY"] = "test-key"
        result = subprocess.run(
            [
                sys.executable,
                "scripts/run_go_gate.py",
                "--image",
                "fixtures/hazard_marker.ppm",
                "--mode",
                "dashscope",
                "--out",
                "runs/go_gate/should_not_exist.json",
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 4)
        self.assertIn("go-gate input/API validation failed", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
