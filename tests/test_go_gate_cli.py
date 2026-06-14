import os
from pathlib import Path
import subprocess
import sys
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]


class GoGateCliTests(TestCase):
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
