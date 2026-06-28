from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]


class QwenGuardSubmissionPackCliTests(TestCase):
    def test_prepare_pack_writes_claim_safe_submission_scaffold(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            out_dir = Path(tmpdir) / "qwenguard-pack"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.prepare_qwenguard_submission_pack",
                    "--out-dir",
                    str(out_dir.relative_to(ROOT)),
                    "--task",
                    "pick Bob's marked cube left of the green cube",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            evidence = json.loads((out_dir / "evidence_manifest.json").read_text(encoding="utf-8"))
            readme = (out_dir / "README.md").read_text(encoding="utf-8")
            architecture = (out_dir / "architecture.md").read_text(encoding="utf-8")
            demo_script = (out_dir / "demo_script.md").read_text(encoding="utf-8")

        self.assertEqual(manifest["schema_version"], "qwenguard-submission-pack.v1")
        self.assertEqual(manifest["outcome"], "GO")
        self.assertEqual(manifest["submission_readiness"], "NARROW_CLAIM")
        self.assertTrue(all(manifest["pass_conditions"].values()))
        self.assertEqual(evidence["submission_readiness"], "NARROW_CLAIM")
        self.assertEqual(evidence["task"], "pick Bob's marked cube left of the green cube")
        self.assertIn("Track 5", readme)
        self.assertIn("Qwen proposes; local code validates", demo_script)
        self.assertIn("Qwen selector", architecture)
        self.assertIn("ACT policy", architecture)
        self.assertIn("not physical success evidence", json.dumps(evidence, sort_keys=True))
        self.assertTrue(
            all(not Path(path).is_absolute() and ".." not in Path(path).parts for path in manifest["files"].values())
        )
        joined = "\n".join([json.dumps(manifest, sort_keys=True), json.dumps(evidence, sort_keys=True), readme])
        self.assertNotIn("ALIBABA_API_KEY=", joined)
        self.assertNotIn("ghp_", joined)
        self.assertNotIn("sk-", joined)

    def test_out_dir_must_stay_under_repo(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.prepare_qwenguard_submission_pack",
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
                "scripts.prepare_qwenguard_submission_pack",
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
