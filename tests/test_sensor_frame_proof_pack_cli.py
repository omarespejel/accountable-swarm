from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]


class SensorFrameProofPackCliTests(TestCase):
    def test_fixture_image_writes_redacted_manifest(self) -> None:
        out_dir = ROOT / "runs" / "physical" / "test_sensor_frame_proof"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.prepare_sensor_frame_proof_pack",
                "--image",
                "fixtures/hazard_marker.ppm",
                "--mode",
                "fixture",
                "--out-dir",
                str(out_dir.relative_to(ROOT)),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
        report = json.loads((out_dir / "report.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["schema_version"], "sensor-frame-proof-pack.v1")
        self.assertEqual(manifest["outcome"], "NARROW_CLAIM")
        self.assertEqual(manifest["camera_gate_outcome"], "NARROW_CLAIM")
        self.assertEqual(manifest["source"]["kind"], "static_image")
        self.assertEqual(manifest["source"]["basename"], "hazard_marker.ppm")
        self.assertTrue(manifest["source"]["retained_local"])
        self.assertEqual(manifest["source"]["relative_path"], "fixtures/hazard_marker.ppm")
        self.assertEqual(manifest["trace_summary_sha"], report["trace_summary_sha"])
        self.assertTrue(manifest["pass_conditions"]["camera_gate_completed"])
        self.assertTrue(manifest["pass_conditions"]["trace_matches_report_summary_sha"])
        self.assertTrue(manifest["pass_conditions"]["manifest_contains_no_secret_material"])
        self.assertTrue(manifest["pass_conditions"]["manifest_uses_only_relative_repo_paths"])
        self.assertIn("scripts.run_camera_go_gate", manifest["commands"]["camera_gate"])
        self.assertIn("scripts.verify_trace", manifest["commands"]["verify_trace"])
        self.assertNotIn("ALIBABA_API_KEY", json.dumps(manifest, sort_keys=True))
        self.assertNotIn(str(ROOT), json.dumps(manifest, sort_keys=True))

    def test_out_dir_must_stay_under_repo(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.prepare_sensor_frame_proof_pack",
                "--image",
                "fixtures/hazard_marker.ppm",
                "--mode",
                "fixture",
                "--out-dir",
                "../escape",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("escapes repository root", result.stderr)
