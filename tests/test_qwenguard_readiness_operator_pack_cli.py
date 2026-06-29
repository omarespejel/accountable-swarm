from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]


class QwenGuardReadinessOperatorPackCliTests(TestCase):
    def test_prepare_pack_writes_claim_safe_operator_commands(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            out_dir = Path(tmpdir) / "readiness-pack"
            result = _run_pack_cli(
                "--out-dir",
                str(out_dir.relative_to(ROOT)),
                "--task",
                "pick Bob's marked cube left of the green cube",
                "--camera-name",
                "so101-main",
                "--camera-id",
                "0",
                "--video-artifact",
                "runs/submission/qwenguard-final-demo.mp4",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            commands = (out_dir / "operator_commands.sh").read_text(encoding="utf-8")
            runbook = (out_dir / "README.md").read_text(encoding="utf-8")

            syntax = subprocess.run(
                ["bash", "-n", str(out_dir / "operator_commands.sh")],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(syntax.returncode, 0, syntax.stderr)
        self.assertEqual(manifest["schema_version"], "qwenguard-readiness-operator-pack.v1")
        self.assertEqual(manifest["outcome"], "GO")
        self.assertEqual(manifest["submission_readiness"], "NARROW_CLAIM")
        self.assertTrue(all(manifest["pass_conditions"].values()))
        self.assertIn("all-preflight", manifest["operator_phases"])
        self.assertIn("so101-camera", manifest["operator_phases"])
        self.assertIn("summarize-trials", manifest["operator_phases"])
        self.assertIn("ecs-pack", manifest["operator_phases"])
        self.assertIn("ecs-review", manifest["operator_phases"])
        self.assertIn("video-review", manifest["operator_phases"])
        self.assertIn("next-steps", manifest["operator_phases"])
        self.assertIn("audit-final", manifest["operator_phases"])
        self.assertIn("prepare_qwenguard_physical_go_pack", commands)
        self.assertIn("prepare_ecs_operator_pack", commands)
        self.assertIn("prepare_qwenguard_submission_pack", commands)
        self.assertIn("summarize_qwenguard_trials", commands)
        self.assertIn("--trial-summary \"${TRIAL_SUMMARY}\"", commands)
        self.assertIn("prepare_ecs_proof_review", commands)
        self.assertIn("--ecs-proof-review \"${ECS_PROOF_REVIEW}\"", commands)
        self.assertIn("prepare_qwenguard_final_video_review", commands)
        self.assertIn("audit_qwenguard_submission_readiness", commands)
        self.assertIn("--ecs-report \"${ECS_REPORT}\"", commands)
        self.assertIn("print_next_steps", commands)
        self.assertIn("Next operator sequence", commands)
        self.assertIn("No phase in this script enters raw secrets", commands)
        self.assertIn("Submission readiness stays `NARROW_CLAIM`", runbook)
        self.assertIn("next-steps", runbook)
        self.assertIn("`next-steps` only prints", runbook)
        self.assertIn("`all-preflight` is the locally", runbook)
        self.assertIn("test-covered no-camera/no-ECS-host preflight", runbook)
        self.assertIn("It does not invoke", runbook)
        self.assertIn("camera capture or ECS proof collection", runbook)
        self.assertIn("existing physical-pack", runbook)
        self.assertIn("`all-safe` phase", runbook)
        self.assertNotIn("safe to run before hardware", runbook)
        self.assertNotIn("no-hardware fixture/degraded traces", runbook)
        self.assertIn("SO-101 camera report", runbook)
        self.assertIn("trial_summary.json", runbook)
        self.assertIn("ecs_proof_review.md", runbook)
        self.assertIn('QWENGUARD_ECS_REVIEW_DATE="YYYY-MM-DD"', runbook)
        self.assertIn('QWENGUARD_REVIEW_DATE="YYYY-MM-DD"', runbook)
        self.assertIn("runs/ecs/ecs_terminal_proof.txt", runbook)
        self.assertNotIn("runs/ecs/ecs-terminal-proof.txt", runbook)
        self.assertNotIn("ALIBABA_API_KEY=", "\n".join([commands, runbook, json.dumps(manifest)]))
        self.assertNotIn("ghp_", "\n".join([commands, runbook, json.dumps(manifest)]))
        self.assertTrue(
            all(not Path(path).is_absolute() and ".." not in Path(path).parts for path in manifest["files"].values())
        )

    def test_all_preflight_runs_without_camera_or_ecs_host(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            out_dir = Path(tmpdir) / "readiness-pack"
            prep = _run_pack_cli(
                "--out-dir",
                str(out_dir.relative_to(ROOT)),
                "--commit",
                _git_head(),
            )
            self.assertEqual(prep.returncode, 0, prep.stderr)
            env = {
                **os.environ,
                "QWENGUARD_PHYSICAL_PACK_DIR": str((Path(tmpdir) / "physical-pack").relative_to(ROOT)),
                "QWENGUARD_ECS_PACK_DIR": str((Path(tmpdir) / "ecs-pack").relative_to(ROOT)),
                "QWENGUARD_SUBMISSION_PACK_DIR": str((Path(tmpdir) / "submission-pack").relative_to(ROOT)),
                "QWENGUARD_READINESS_REPORT": str((Path(tmpdir) / "readiness.json").relative_to(ROOT)),
                "QWENGUARD_FINAL_VIDEO_REVIEW": str((Path(tmpdir) / "final_video_review.md").relative_to(ROOT)),
            }

            result = subprocess.run(
                ["bash", str(out_dir / "operator_commands.sh"), "all-preflight"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            readiness = json.loads((Path(tmpdir) / "readiness.json").read_text(encoding="utf-8"))
            self.assertEqual(readiness["outcome"], "NARROW_CLAIM")
            self.assertTrue((Path(tmpdir) / "physical-pack" / "manifest.json").is_file())
            self.assertTrue((Path(tmpdir) / "ecs-pack" / "manifest.json").is_file())
            self.assertTrue((Path(tmpdir) / "submission-pack" / "manifest.json").is_file())
            self.assertFalse((Path(tmpdir) / "final_video_review.md").exists())

    def test_next_steps_phase_prints_operator_sequence_without_evidence(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            out_dir = Path(tmpdir) / "readiness-pack"
            prep = _run_pack_cli("--out-dir", str(out_dir.relative_to(ROOT)))
            self.assertEqual(prep.returncode, 0, prep.stderr)

            result = subprocess.run(
                ["bash", str(out_dir / "operator_commands.sh"), "next-steps"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Next operator sequence:", result.stdout)
        self.assertIn("so101-camera", result.stdout)
        self.assertIn("record-success", result.stdout)
        self.assertIn("record-cloud-hold", result.stdout)
        self.assertIn("ecs-review", result.stdout)
        self.assertIn("video-review", result.stdout)
        self.assertIn("audit-final", result.stdout)
        self.assertIn("runs/physical/qwenguard_trials/trial_results.csv", result.stdout)
        self.assertIn("runs/ecs/ecs_terminal_proof.txt", result.stdout)
        self.assertNotIn("runs/ecs/ecs-terminal-proof.txt", result.stdout)
        self.assertIn(str((out_dir / "operator_commands.sh").relative_to(ROOT)), result.stdout)
        self.assertNotIn("ALIBABA_API_KEY=", result.stdout)

    def test_next_steps_phase_uses_operator_overrides(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            out_dir = Path(tmpdir) / "readiness-pack"
            prep = _run_pack_cli("--out-dir", str(out_dir.relative_to(ROOT)))
            self.assertEqual(prep.returncode, 0, prep.stderr)
            env = {
                **os.environ,
                "QWENGUARD_GO_RUN_DIR": "runs/custom/physical-go",
                "QWENGUARD_TRIAL_CSV": "runs/custom/trials.csv",
                "QWENGUARD_TRIAL_TRACE_DIR": "runs/custom/traces",
                "QWENGUARD_TRIAL_SUMMARY": "runs/custom/summary.json",
                "QWENGUARD_ECS_REPORT": "runs/custom/ecs.json",
                "QWENGUARD_ECS_PROOF_REVIEW": "runs/custom/ecs_review.md",
                "QWENGUARD_ECS_TERMINAL_ARTIFACT": "runs/custom/terminal.txt",
                "QWENGUARD_FINAL_VIDEO_REVIEW": "runs/custom/video_review.md",
                "QWENGUARD_VIDEO_ARTIFACT": "runs/custom/final.mp4",
            }

            result = subprocess.run(
                ["bash", str(out_dir / "operator_commands.sh"), "next-steps"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("runs/custom/physical-go/so101_capture_report.json", result.stdout)
        self.assertIn("runs/custom/trials.csv", result.stdout)
        self.assertIn("runs/custom/traces/*.json", result.stdout)
        self.assertIn("runs/custom/summary.json", result.stdout)
        self.assertIn("runs/custom/ecs.json", result.stdout)
        self.assertIn("runs/custom/ecs_review.md", result.stdout)
        self.assertIn("runs/custom/terminal.txt", result.stdout)
        self.assertIn("QWENGUARD_VIDEO_ARTIFACT=runs/custom/final.mp4", result.stdout)
        self.assertIn("runs/custom/video_review.md", result.stdout)

    def test_next_steps_rejects_secret_like_artifact_overrides(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            out_dir = Path(tmpdir) / "readiness-pack"
            prep = _run_pack_cli("--out-dir", str(out_dir.relative_to(ROOT)))
            self.assertEqual(prep.returncode, 0, prep.stderr)
            cases = {
                "QWENGUARD_ECS_TERMINAL_ARTIFACT": "runs/ecs/sk-testsecret01234567890123456789.txt",
                "QWENGUARD_VIDEO_ARTIFACT": "https://example.com/sk-testsecret01234567890123456789/final.mp4",
            }

            for env_name, env_value in cases.items():
                with self.subTest(env_name=env_name):
                    env = {**os.environ, env_name: env_value}
                    result = subprocess.run(
                        ["bash", str(out_dir / "operator_commands.sh"), "next-steps"],
                        cwd=ROOT,
                        env=env,
                        text=True,
                        capture_output=True,
                        check=False,
                    )

                    self.assertEqual(result.returncode, 2)
                    self.assertIn(env_name, result.stderr)
                    self.assertNotIn(env_value, result.stdout)
                    self.assertNotIn(env_value, result.stderr)

    def test_next_steps_rejects_escaping_so101_run_dir_override(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            out_dir = Path(tmpdir) / "readiness-pack"
            prep = _run_pack_cli("--out-dir", str(out_dir.relative_to(ROOT)))
            self.assertEqual(prep.returncode, 0, prep.stderr)
            env = {**os.environ, "QWENGUARD_GO_RUN_DIR": "../escape"}

            result = subprocess.run(
                ["bash", str(out_dir / "operator_commands.sh"), "next-steps"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("QWENGUARD_GO_RUN_DIR", result.stderr)

    def test_video_review_phase_requires_human_metadata(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            out_dir = Path(tmpdir) / "readiness-pack"
            prep = _run_pack_cli("--out-dir", str(out_dir.relative_to(ROOT)))
            self.assertEqual(prep.returncode, 0, prep.stderr)

            result = subprocess.run(
                ["bash", str(out_dir / "operator_commands.sh"), "video-review"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("QWENGUARD_REVIEWED_BY", result.stderr)

    def test_ecs_review_phase_requires_human_metadata(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            out_dir = Path(tmpdir) / "readiness-pack"
            prep = _run_pack_cli("--out-dir", str(out_dir.relative_to(ROOT)))
            self.assertEqual(prep.returncode, 0, prep.stderr)

            result = subprocess.run(
                ["bash", str(out_dir / "operator_commands.sh"), "ecs-review"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("QWENGUARD_ECS_REVIEWED_BY", result.stderr)

    def test_out_dir_must_stay_under_repo(self) -> None:
        result = _run_pack_cli("--out-dir", "../escape")

        self.assertEqual(result.returncode, 2)
        self.assertIn("inside the repository checkout", result.stderr)

    def test_control_characters_are_rejected(self) -> None:
        result = _run_pack_cli("--task", "bad\ntask")

        self.assertEqual(result.returncode, 2)
        self.assertIn("control characters", result.stderr)

    def test_secret_like_task_is_rejected_before_write(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            out_dir = Path(tmpdir) / "readiness-pack"
            result = _run_pack_cli(
                "--out-dir",
                str(out_dir.relative_to(ROOT)),
                "--task",
                "pick cube using sk-redactedsecret01234567890123456789",
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("secret-like material", result.stderr)
            self.assertFalse(out_dir.exists())

    def test_invalid_commit_is_rejected_before_write(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            out_dir = Path(tmpdir) / "readiness-pack"
            result = _run_pack_cli(
                "--out-dir",
                str(out_dir.relative_to(ROOT)),
                "--commit",
                "ffffffffffffffffffffffffffffffffffffffff",
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("commit must resolve", result.stderr)
            self.assertFalse(out_dir.exists())

    def test_generated_runner_rejects_escaping_output_override(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            out_dir = Path(tmpdir) / "readiness-pack"
            prep = _run_pack_cli("--out-dir", str(out_dir.relative_to(ROOT)))
            self.assertEqual(prep.returncode, 0, prep.stderr)
            env = {**os.environ, "QWENGUARD_SUBMISSION_PACK_DIR": "../escape"}

            result = subprocess.run(
                ["bash", str(out_dir / "operator_commands.sh"), "bootstrap"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("QWENGUARD_SUBMISSION_PACK_DIR", result.stderr)

    def test_generated_runner_rejects_escaping_video_artifact_override(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            out_dir = Path(tmpdir) / "readiness-pack"
            prep = _run_pack_cli("--out-dir", str(out_dir.relative_to(ROOT)))
            self.assertEqual(prep.returncode, 0, prep.stderr)
            env = {**os.environ, "QWENGUARD_VIDEO_ARTIFACT": "../escape.mp4"}

            result = subprocess.run(
                ["bash", str(out_dir / "operator_commands.sh"), "video-review"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("QWENGUARD_VIDEO_ARTIFACT", result.stderr)

    def test_generated_runner_rejects_escaping_trial_summary_override(self) -> None:
        self._assert_summarize_trials_rejects_path_escape(
            env_name="QWENGUARD_TRIAL_SUMMARY",
            env_value="../escape.json",
        )

    def test_generated_runner_rejects_escaping_trial_csv_override(self) -> None:
        self._assert_summarize_trials_rejects_path_escape(
            env_name="QWENGUARD_TRIAL_CSV",
            env_value="../escape.csv",
        )

    def test_generated_runner_rejects_escaping_trial_trace_dir_override(self) -> None:
        self._assert_summarize_trials_rejects_path_escape(
            env_name="QWENGUARD_TRIAL_TRACE_DIR",
            env_value="../escape-traces",
        )

    def test_generated_runner_rejects_escaping_ecs_review_override(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            out_dir = Path(tmpdir) / "readiness-pack"
            prep = _run_pack_cli("--out-dir", str(out_dir.relative_to(ROOT)))
            self.assertEqual(prep.returncode, 0, prep.stderr)
            env = {**os.environ, "QWENGUARD_ECS_PROOF_REVIEW": "../escape.md"}

            result = subprocess.run(
                ["bash", str(out_dir / "operator_commands.sh"), "audit-narrow"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("QWENGUARD_ECS_PROOF_REVIEW", result.stderr)

    def test_generated_runner_rejects_escaping_ecs_report_override(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            out_dir = Path(tmpdir) / "readiness-pack"
            prep = _run_pack_cli("--out-dir", str(out_dir.relative_to(ROOT)))
            self.assertEqual(prep.returncode, 0, prep.stderr)
            env = {**os.environ, "QWENGUARD_ECS_REPORT": "../escape.json"}

            result = subprocess.run(
                ["bash", str(out_dir / "operator_commands.sh"), "audit-narrow"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("QWENGUARD_ECS_REPORT", result.stderr)

    def _assert_summarize_trials_rejects_path_escape(self, *, env_name: str, env_value: str) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            out_dir = Path(tmpdir) / "readiness-pack"
            prep = _run_pack_cli("--out-dir", str(out_dir.relative_to(ROOT)))
            self.assertEqual(prep.returncode, 0, prep.stderr)
            env = {**os.environ, env_name: env_value}

            result = subprocess.run(
                ["bash", str(out_dir / "operator_commands.sh"), "summarize-trials"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn(env_name, result.stderr)


def _run_pack_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.prepare_qwenguard_readiness_operator_pack",
            *args,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()
