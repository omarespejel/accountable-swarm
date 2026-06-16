from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from unittest import TestCase

from accountable_swarm.physical.so101 import parse_index_or_path


ROOT = Path(__file__).resolve().parents[1]


class So101CaptureHelpersTests(TestCase):
    def test_parse_index_or_path_converts_plain_integer(self) -> None:
        self.assertEqual(parse_index_or_path("0"), 0)
        self.assertEqual(parse_index_or_path(" 12 "), 12)
        self.assertEqual(parse_index_or_path("/dev/video2"), "/dev/video2")


class So101CameraCaptureCliTests(TestCase):
    def test_missing_optional_dependencies_yields_controlled_no_go_report(self) -> None:
        frame_path = ROOT / "runs" / "physical" / "test_so101_frame.png"
        report_path = ROOT / "runs" / "physical" / "test_so101_capture_report.json"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.capture_so101_camera_frame",
                "--camera-name",
                "so101_overhead",
                "--index-or-path",
                "0",
                "--out",
                str(frame_path),
                "--report-out",
                str(report_path),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 4)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["schema_version"], "so101-camera-capture-report.v1")
        self.assertEqual(report["outcome"], "NO_GO")
        self.assertFalse(report["pass_conditions"]["dependencies_available"])
        self.assertFalse(report["pass_conditions"]["frame_captured"])
        self.assertTrue(report["pass_conditions"]["trace_only_motion_boundary_preserved"])
        self.assertIn("lerobot", report["detail"])
