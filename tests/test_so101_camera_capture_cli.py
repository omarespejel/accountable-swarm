from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
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
        base = ROOT / "runs" / "physical"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            frame_path = Path(tmpdir) / "test_so101_frame.png"
            report_path = Path(tmpdir) / "test_so101_capture_report.json"
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
                    str(frame_path.relative_to(ROOT)),
                    "--report-out",
                    str(report_path.relative_to(ROOT)),
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

    def test_artifact_paths_must_be_repo_relative(self) -> None:
        base = ROOT / "runs" / "physical"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            frame_path = Path(tmpdir) / "frame.png"
            report_path = Path(tmpdir) / "absolute_report.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.capture_so101_camera_frame",
                    "--out",
                    str(frame_path.relative_to(ROOT)),
                    "--report-out",
                    str(report_path),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("repo-relative", result.stderr)
            self.assertFalse(report_path.exists())

    def test_artifact_paths_must_not_escape_repo(self) -> None:
        base = ROOT / "runs" / "physical"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            frame_path = Path(tmpdir) / "frame.png"
            report_path = Path(tmpdir) / "escape_report.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.capture_so101_camera_frame",
                    "--out",
                    str(frame_path.relative_to(ROOT)),
                    "--report-out",
                    "../escape_report.json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("stay inside", result.stderr)
            self.assertFalse(report_path.exists())

    def test_artifact_paths_must_name_files_not_directories(self) -> None:
        base = ROOT / "runs" / "physical"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            frame_path = Path(tmpdir) / "frame.png"
            report_dir = Path(tmpdir) / "reports"
            report_dir.mkdir()
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.capture_so101_camera_frame",
                    "--out",
                    str(frame_path.relative_to(ROOT)),
                    "--report-out",
                    str(report_dir.relative_to(ROOT)),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("must name files", result.stderr)

    def test_frame_and_report_must_be_colocated(self) -> None:
        base = ROOT / "runs" / "physical"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            session_dir = Path(tmpdir)
            frame_path = session_dir / "frames" / "so101_frame.png"
            report_path = session_dir / "reports" / "so101_report.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.capture_so101_camera_frame",
                    "--out",
                    str(frame_path.relative_to(ROOT)),
                    "--report-out",
                    str(report_path.relative_to(ROOT)),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("same directory", result.stderr)
            self.assertFalse(report_path.exists())
