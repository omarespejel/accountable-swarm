from __future__ import annotations

import json
import os
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
                    f"pick Bob's marked cube near {ROOT}",
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
        self.assertIn("could not locate repository root", commands)
        self.assertIn("QWENGUARD_GO_RUN_DIR", commands)
        self.assertNotIn("lerobot.record", commands)
        self.assertIn("Qwen never controls motors", runbook)
        self.assertEqual(evidence["task"], f"pick Bob's marked cube near {ROOT}")
        joined = "\n".join([json.dumps(manifest, sort_keys=True), commands, runbook])
        self.assertNotIn("ALIBABA_API_KEY=", joined)
        self.assertNotIn("ghp_", joined)
        self.assertNotIn("sk-", joined)
        self.assertTrue(
            all(not Path(path).is_absolute() and ".." not in Path(path).parts for path in manifest["files"].values())
        )

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
            go_run_dir = Path(tmpdir) / "go-run"
            training_dir = Path(tmpdir) / "training-pack"
            env = {
                **os.environ,
                "QWENGUARD_GO_RUN_DIR": str(go_run_dir.relative_to(ROOT)),
                "QWENGUARD_TRAINING_PACK_DIR": str(training_dir.relative_to(ROOT)),
            }
            result = subprocess.run(
                ["bash", str(out_dir / "operator_commands.sh"), "all-safe"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f"verified {go_run_dir.relative_to(ROOT)}/fixture_trace.json", result.stdout)
            self.assertIn(f"verified {go_run_dir.relative_to(ROOT)}/degraded_trace.json", result.stdout)
            self.assertTrue((go_run_dir / "fixture_trace.json").is_file())
            self.assertTrue((training_dir / "manifest.json").is_file())

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

    def test_generated_runner_rejects_escaping_output_override(self) -> None:
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
                ["bash", str(out_dir / "operator_commands.sh"), "fixture"],
                cwd=ROOT,
                env={**os.environ, "QWENGUARD_GO_RUN_DIR": "../escape"},
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("QWENGUARD_GO_RUN_DIR must be repo-relative", result.stderr)
