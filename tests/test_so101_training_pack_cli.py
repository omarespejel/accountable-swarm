import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[1]


class SO101TrainingPackCliTests(TestCase):
    def test_training_pack_contains_no_secret_material(self) -> None:
        with TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "pack"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.prepare_so101_training_pack",
                    "--out-dir",
                    str(out_dir),
                ],
                text=True,
                capture_output=True,
                cwd=ROOT,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], "qwenguard-so101-training-pack.v1")
            self.assertEqual(manifest["lerobot_git_ref"], "1396b9fab7aecddd10006c33c47a487ffdcb54b4")
            self.assertEqual(manifest["opencv_python_version"], "4.13.0.92")
            joined = "\n".join(path.read_text(encoding="utf-8") for path in out_dir.iterdir() if path.is_file())
            self.assertNotIn("ALIBABA_API_KEY", joined)
            self.assertNotIn("ghp_", joined)
            self.assertIn("trial_id", (out_dir / "trial_template.csv").read_text(encoding="utf-8"))
            self.assertIn("lerobot[feetech] @ git+https://github.com/huggingface/lerobot.git@", joined)
            self.assertIn("opencv-python==${QWENGUARD_OPENCV_PYTHON_VERSION}", joined)
            self.assertIn("does **not** provide a programmatic interlock", joined)
            self.assertIn("require_motion_readiness", joined)
            self.assertIn("QWENGUARD_EMERGENCY_STOP_READY", joined)
            self.assertIn("QWENGUARD_LOW_SPEED_MODE", joined)
            self.assertIn("QWENGUARD_WORKSPACE_BOUNDS_SET", joined)
            self.assertIn("QWENGUARD_LEADER_DETACHED_OR_NONAUTHORITATIVE", joined)

    def test_training_pack_quotes_shell_unsafe_task(self) -> None:
        with TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "pack"
            task = "pick Bob's cube"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.prepare_so101_training_pack",
                    "--out-dir",
                    str(out_dir),
                    "--task",
                    task,
                ],
                text=True,
                capture_output=True,
                cwd=ROOT,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            script = out_dir / "operator_commands.sh"
            syntax = subprocess.run(
                ["bash", "-n", str(script)],
                text=True,
                capture_output=True,
                cwd=ROOT,
                check=False,
            )
            self.assertEqual(syntax.returncode, 0, syntax.stderr)
            self.assertEqual(json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))["task"], task)
            self.assertIn("Bob", script.read_text(encoding="utf-8"))
