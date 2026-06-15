from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]


class PackagingTests(TestCase):
    def test_pyproject_defines_zero_dependency_cli_entrypoints(self) -> None:
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('requires-python = ">=3.9"', text)
        self.assertIn("dependencies = []", text)
        self.assertIn('run-go-gate = "scripts.run_go_gate:main"', text)
        self.assertIn('run-camera-go-gate = "scripts.run_camera_go_gate:main"', text)
        self.assertIn('collect-ecs-smoke-report = "scripts.collect_ecs_smoke_report:main"', text)
        self.assertIn('verify-trace = "scripts.verify_trace:main"', text)
