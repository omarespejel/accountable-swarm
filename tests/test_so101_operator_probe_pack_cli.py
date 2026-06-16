from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]


class So101OperatorProbePackCliTests(TestCase):
    def test_prepare_pack_writes_manifest_and_no_secret_material(self) -> None:
        base = ROOT / "runs" / "physical"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            out_dir = Path(tmpdir) / "operator-pack"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.prepare_so101_operator_probe_pack",
                    "--out-dir",
                    str(out_dir.relative_to(ROOT)),
                    "--camera-name",
                    "so101_overhead",
                    "--camera-id",
                    "0",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            commands = (out_dir / "operator_commands.sh").read_text(encoding="utf-8")
            runbook = (out_dir / "README.md").read_text(encoding="utf-8")

        self.assertEqual(manifest["schema_version"], "so101-operator-probe-pack.v1")
        self.assertEqual(manifest["outcome"], "GO")
        self.assertTrue(all(manifest["pass_conditions"].values()))
        self.assertIn("pip install lerobot", commands)
        self.assertIn("pip install 'lerobot[feetech]'", commands)
        self.assertIn("pip install opencv-python", commands)
        self.assertIn("lerobot-find-cameras opencv", commands)
        self.assertIn("capture_so101_camera_frame", commands)
        self.assertIn("huggingface.co/docs/lerobot/installation", runbook)
        self.assertNotIn("ALIBABA_API_KEY", json.dumps(manifest, sort_keys=True))
        self.assertNotIn(str(ROOT), json.dumps(manifest, sort_keys=True))

    def test_out_dir_must_stay_under_repo(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.prepare_so101_operator_probe_pack",
                "--out-dir",
                "../escape",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("inside the repository checkout", result.stderr)
