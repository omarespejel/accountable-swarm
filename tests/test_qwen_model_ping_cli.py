import os
from pathlib import Path
import subprocess
import sys
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]


class QwenModelPingCliTests(TestCase):
    def test_missing_key_failure_is_clean(self) -> None:
        env = dict(os.environ)
        env.pop("ALIBABA_API_KEY", None)
        result = subprocess.run(
            [sys.executable, "scripts/qwen_model_ping.py", "--models", "qwen-plus"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 3)
        self.assertIn("ALIBABA_API_KEY is not set", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
