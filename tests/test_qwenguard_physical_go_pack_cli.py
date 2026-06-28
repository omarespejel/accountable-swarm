from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]


class QwenGuardPhysicalGoPackCliTests(TestCase):
    def test_prepare_pack_writes_manifest_and_no_secret_material(self) -> None:
        base = ROOT / "runs" / "physical"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            out_dir = Path(tmpdir) / "physical-go-pack"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.prepare_qwenguard_physical_go_pack",
                    "--out-dir",
                    str(out_dir.relative_to(ROOT)),
                    "--task",
                    "pick Bob's marked cube",
                    "--camera-name",
                    "so101-main",
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
            evidence = json.loads((out_dir / "evidence_manifest_template.json").read_text(encoding="utf-8"))

            syntax = subprocess.run(
                ["bash", "-n", str(out_dir / "operator_commands.sh")],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(syntax.returncode, 0, syntax.stderr)
        self.assertEqual(manifest["schema_version"], "qwenguard-physical-go-pack.v1")
        self.assertEqual(manifest["outcome"], "GO")
        self.assertTrue(all(manifest["pass_conditions"].values()))
        self.assertIn("fixture", manifest["operator_phases"])
        self.assertIn("degraded", manifest["operator_phases"])
        self.assertIn("camera", manifest["operator_phases"])
        self.assertIn("training-pack", manifest["operator_phases"])
        self.assertIn("all-safe", manifest["operator_phases"])
        self.assertIn("run_qwenguard_no_motion_health_check", commands)
        self.assertIn("capture_so101_camera_frame", commands)
        self.assertIn("prepare_so101_training_pack", commands)
        self.assertIn("all-safe", commands)
        self.assertIn("Does not touch camera", commands)
        self.assertNotIn("lerobot.record", commands)
        self.assertIn("Qwen never controls motors", runbook)
        self.assertEqual(evidence["task"], "pick Bob's marked cube")
        joined = "\n".join([json.dumps(manifest, sort_keys=True), commands, runbook])
        self.assertNotIn("ALIBABA_API_KEY=", joined)
        self.assertNotIn("ghp_", joined)
        self.assertNotIn("sk-", joined)
        self.assertNotIn(str(ROOT), json.dumps(manifest, sort_keys=True))

    def test_all_safe_phase_runs_without_hardware(self) -> None:
        base = ROOT / "runs" / "physical"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            out_dir = Path(tmpdir) / "physical-go-pack"
            prep = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.prepare_qwenguard_physical_go_pack",
                    "--out-dir",
                    str(out_dir.relative_to(ROOT)),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(prep.returncode, 0, prep.stderr)
            result = subprocess.run(
                ["bash", str(out_dir / "operator_commands.sh"), "all-safe"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("verified runs/physical/qwenguard_physical_go/fixture_trace.json", result.stdout)
        self.assertIn("verified runs/physical/qwenguard_physical_go/degraded_trace.json", result.stdout)

    def test_out_dir_must_stay_under_repo(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.prepare_qwenguard_physical_go_pack",
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

    def test_control_characters_are_rejected(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.prepare_qwenguard_physical_go_pack",
                "--task",
                "bad\ntask",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("control characters", result.stderr)
