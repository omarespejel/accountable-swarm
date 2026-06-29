from __future__ import annotations

import ast
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from accountable_swarm.physical.so101 import SO101CameraSpec, capture_frame, parse_index_or_path


ROOT = Path(__file__).resolve().parents[1]


class So101CaptureHelpersTests(TestCase):
    def test_parse_index_or_path_converts_plain_integer(self) -> None:
        self.assertEqual(parse_index_or_path("0"), 0)
        self.assertEqual(parse_index_or_path(" 12 "), 12)
        self.assertEqual(parse_index_or_path("/dev/video2"), "/dev/video2")

    def test_capture_frame_uses_camera_read_path_without_actuation(self) -> None:
        calls: list[str] = []

        class FakeFrame:
            shape = (480, 640, 3)

        class FakeConfig:
            def __init__(
                self,
                camera_index: int | str | None = None,
                width: int | None = None,
                height: int | None = None,
                fps: int | None = None,
                name: str | None = None,
            ) -> None:
                self.camera_index = camera_index
                self.width = width
                self.height = height
                self.fps = fps
                self.name = name

        class FakeCamera:
            def __init__(self, config: FakeConfig) -> None:
                self.config = config
                calls.append("construct_camera")

            def connect(self) -> None:
                calls.append("connect")

            def async_read(self) -> FakeFrame:
                calls.append("async_read")
                return FakeFrame()

            def disconnect(self) -> None:
                calls.append("disconnect")

            def close(self) -> None:
                calls.append("close")

            def send_action(self, *_args: object, **_kwargs: object) -> None:
                raise AssertionError("camera probe must not send actions")

            def set_goal_position(self, *_args: object, **_kwargs: object) -> None:
                raise AssertionError("camera probe must not set goal positions")

            def set_position(self, *_args: object, **_kwargs: object) -> None:
                raise AssertionError("camera probe must not set positions")

            def write_torque(self, *_args: object, **_kwargs: object) -> None:
                raise AssertionError("camera probe must not write torque")

        cv2_module = ModuleType("cv2")

        def imwrite(path: str, _frame: FakeFrame) -> bool:
            calls.append("imwrite")
            Path(path).write_bytes(b"fake-png")
            return True

        cv2_module.imwrite = imwrite  # type: ignore[attr-defined]
        camera_module = ModuleType("lerobot.cameras.opencv.camera_opencv")
        camera_module.OpenCVCamera = FakeCamera  # type: ignore[attr-defined]
        config_module = ModuleType("lerobot.cameras.opencv.configuration_opencv")
        config_module.OpenCVCameraConfig = FakeConfig  # type: ignore[attr-defined]
        fake_modules = {
            "cv2": cv2_module,
            "lerobot": ModuleType("lerobot"),
            "lerobot.cameras": ModuleType("lerobot.cameras"),
            "lerobot.cameras.opencv": ModuleType("lerobot.cameras.opencv"),
            "lerobot.cameras.opencv.camera_opencv": camera_module,
            "lerobot.cameras.opencv.configuration_opencv": config_module,
        }

        with TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "frame.png"
            with patch.dict(sys.modules, fake_modules):
                capture = capture_frame(SO101CameraSpec("so101-main", 0), out_path)

        self.assertEqual(calls, ["construct_camera", "connect", "async_read", "imwrite", "disconnect", "close"])
        self.assertEqual(capture["width"], 640)
        self.assertEqual(capture["height"], 480)
        self.assertEqual(capture["output_path"], "frame.png")

    def test_so101_camera_module_does_not_import_or_call_actuation_surfaces(self) -> None:
        source = (ROOT / "accountable_swarm" / "physical" / "so101.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        forbidden_imports = {"lerobot.record", "lerobot.robots", "lerobot.teleoperators"}
        forbidden_symbols = {
            "send_action",
            "set_goal_position",
            "goal_position",
            "set_position",
            "write_torque",
            "so101_follower",
            "so101_leader",
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn(alias.name, forbidden_imports)
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                self.assertNotIn(module, forbidden_imports)
            if isinstance(node, ast.Attribute):
                self.assertNotIn(node.attr, forbidden_symbols)
            if isinstance(node, ast.Name):
                self.assertNotIn(node.id, forbidden_symbols)
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                self.assertNotIn(node.value, forbidden_symbols)


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
