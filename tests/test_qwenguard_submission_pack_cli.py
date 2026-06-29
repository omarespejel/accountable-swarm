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
        self.assertIn("Qwen proposes an object candidate", readme)
        self.assertIn(
            "local SO-101 policy is designed to act only when the gate allows it "
            "(physical execution pending operator proof)",
            readme.replace("\n> ", " "),
        )
        self.assertNotIn("physical execution succeeded", readme)
        self.assertNotIn("physical success", readme)
        self.assertNotIn("policy acts only when", readme)
        self.assertNotIn("Qwen identifies the right object", readme)
        self.assertIn("Qwen proposes; local code validates", demo_script)
        self.assertIn("Planned Local ACT Action", demo_script)
        self.assertIn("Record this segment only after a measured physical trace exists", demo_script)
        self.assertIn("recorded only after trial traces exist", demo_script)
        self.assertIn("Qwen selector", architecture)
        self.assertIn("ACT policy", architecture)
        self.assertIn("not physical success evidence", json.dumps(evidence, sort_keys=True))
        expected_paths = {
            item["name"]: item["expected_path"]
            for item in evidence["required_before_submit"]
        }
        self.assertEqual(
            expected_paths["qwenguard_no_motion_selector_gate_eval"],
            "runs/physical/qwenguard_physical_go/fixture_trace.json",
        )
        self.assertEqual(
            expected_paths["act_physical_trials"],
            "runs/physical/qwenguard_trials/trial_results.csv",
        )
        self.assertEqual(
            expected_paths["measured_trial_summary"],
            "runs/physical/qwenguard_trials/trial_summary.json",
        )
        self.assertNotIn("selector_trace.json", json.dumps(evidence, sort_keys=True))
        self.assertNotIn("evaluator_trace.json", json.dumps(evidence, sort_keys=True))
        self.assertIn("record-qwenguard-trial", readme)
        self.assertIn("trial_results.csv", json.dumps(evidence, sort_keys=True))
        self.assertIn("trial_summary.json", json.dumps(evidence, sort_keys=True))
        self.assertTrue(
            all(not Path(path).is_absolute() and ".." not in Path(path).parts for path in manifest["files"].values())
        )
        joined = "\n".join(
            [
                json.dumps(manifest, sort_keys=True),
                json.dumps(evidence, sort_keys=True),
                readme,
                architecture,
                demo_script,
            ]
        )
        self.assertNotIn("ALIBABA_API_KEY=", joined)
        self.assertNotIn("ghp_", joined)
        self.assertNotIn("github_pat_", joined)
        self.assertNotIn("gho_", joined)
        self.assertNotIn("ghu_", joined)
        self.assertNotIn("ghs_", joined)
        self.assertNotIn("ghr_", joined)
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

    def test_repo_url_control_characters_are_rejected(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.prepare_qwenguard_submission_pack",
                "--repo-url",
                "https://example.com/repo\nbad",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("control characters", result.stderr)

    def test_out_dir_control_characters_are_rejected(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.prepare_qwenguard_submission_pack",
                "--out-dir",
                "runs/submission/bad\npath",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("control characters", result.stderr)

    def test_generated_secret_like_repo_url_is_rejected(self) -> None:
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
                    "--repo-url",
                    "https://example.com/sk-testsecret",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("secret material", result.stderr)
            self.assertFalse(out_dir.exists())

    def test_secret_like_out_dir_is_rejected_before_write(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            out_dir = Path(tmpdir) / "sk-testsecret-pack"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.prepare_qwenguard_submission_pack",
                    "--out-dir",
                    str(out_dir.relative_to(ROOT)),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("output path contains secret-like material", result.stderr)
            self.assertFalse(out_dir.exists())

    def test_current_github_token_formats_are_rejected_before_write(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        token_like_urls = [
            "https://example.com/github_pat_ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            "https://example.com/gho_abcdefghijklmnop",
            "https://example.com/ghu_abcdefghijklmnop",
            "https://example.com/ghs_abcdefghijklmnop",
            "https://example.com/ghr_abcdefghijklmnop",
        ]
        for repo_url in token_like_urls:
            with self.subTest(repo_url=repo_url), TemporaryDirectory(dir=base) as tmpdir:
                out_dir = Path(tmpdir) / "qwenguard-pack"
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "scripts.prepare_qwenguard_submission_pack",
                        "--out-dir",
                        str(out_dir.relative_to(ROOT)),
                        "--repo-url",
                        repo_url,
                    ],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )

                self.assertEqual(result.returncode, 2)
                self.assertIn("secret material", result.stderr)
                self.assertFalse(out_dir.exists())
