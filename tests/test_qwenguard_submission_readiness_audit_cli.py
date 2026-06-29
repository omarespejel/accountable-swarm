from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase

from accountable_swarm.qwenguard.trial import trial_csv_header
from accountable_swarm.trace.models import canonical_json


ROOT = Path(__file__).resolve().parents[1]
COMMIT = "a" * 40


class QwenGuardSubmissionReadinessAuditCliTests(TestCase):
    def test_missing_operator_artifacts_remain_narrow_claim(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            out = audit_root / "readiness.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.audit_qwenguard_submission_readiness",
                    "--out",
                    str(out.relative_to(ROOT)),
                    "--submission-manifest",
                    str((audit_root / "missing_submission.json").relative_to(ROOT)),
                    "--so101-camera-report",
                    str((audit_root / "missing_camera.json").relative_to(ROOT)),
                    "--fixture-trace",
                    str((audit_root / "missing_fixture.json").relative_to(ROOT)),
                    "--degraded-trace",
                    str((audit_root / "missing_degraded.json").relative_to(ROOT)),
                    "--trial-csv",
                    str((audit_root / "missing_trials.csv").relative_to(ROOT)),
                    "--ecs-report",
                    str((audit_root / "missing_ecs.json").relative_to(ROOT)),
                    "--video-review",
                    str((audit_root / "missing_video.md").relative_to(ROOT)),
                    "--allow-narrow-claim",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(out.read_text(encoding="utf-8"))

        self.assertEqual(report["schema_version"], "qwenguard-submission-readiness-report.v1")
        self.assertEqual(report["outcome"], "NARROW_CLAIM")
        self.assertEqual(report["submission_readiness"], "NARROW_CLAIM")
        self.assertFalse(any(report["pass_conditions"].values()))
        self.assertIn("checks:", result.stdout)
        self.assertIn("MISS so101_camera_report_go - file is missing", result.stdout)
        self.assertIn("MISS human_video_review_present - final video review note is missing", result.stdout)

    def test_without_allow_narrow_claim_missing_artifacts_exit_nonzero(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            out = Path(tmpdir) / "readiness.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.audit_qwenguard_submission_readiness",
                    "--out",
                    str(out.relative_to(ROOT)),
                    "--submission-manifest",
                    str((Path(tmpdir) / "missing_submission.json").relative_to(ROOT)),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 4)
            report = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(report["outcome"], "NARROW_CLAIM")

    def test_stdout_checklist_uses_stable_reason_for_csv_parse_errors(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            out = audit_root / "readiness.json"
            bad_csv = audit_root / "bad_trials.csv"
            bad_csv.write_bytes(b"trial_id,trace_summary_sha\n\xff\n")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.audit_qwenguard_submission_readiness",
                    "--out",
                    str(out.relative_to(ROOT)),
                    "--trial-csv",
                    str(bad_csv.relative_to(ROOT)),
                    "--allow-narrow-claim",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(out.read_text(encoding="utf-8"))

        csv_check = next(check for check in report["checks"] if check["name"] == "measured_trial_csv_has_rows")
        self.assertEqual(csv_check["reason"], "trial CSV could not be parsed")
        self.assertEqual(csv_check["evidence"]["error_type"], "UnicodeDecodeError")
        self.assertIn("MISS measured_trial_csv_has_rows - trial CSV could not be parsed", result.stdout)
        self.assertNotIn("UnicodeDecodeError", result.stdout)
        self.assertNotIn("codec", result.stdout)

    def test_complete_synthetic_evidence_set_is_ready(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            pack_dir = audit_root / "pack"
            fixture_trace = audit_root / "fixture_trace.json"
            fixture_report = audit_root / "fixture_report.json"
            degraded_trace = audit_root / "degraded_trace.json"
            degraded_report = audit_root / "degraded_report.json"
            camera_report = audit_root / "so101_capture_report.json"
            camera_frame = audit_root / "so101_frame.png"
            trial_trace_dir = audit_root / "trial_traces"
            trial_csv = audit_root / "trial_results.csv"
            trial_summary = audit_root / "trial_summary.json"
            trial_report = audit_root / "trial-001-report.json"
            ecs_report = audit_root / "ecs_smoke_report.json"
            ecs_review = audit_root / "ecs_proof_review.md"
            ecs_terminal_artifact = audit_root / "ecs-terminal-proof.txt"
            video_review = audit_root / "final_video_review.md"
            video_file = audit_root / "qwenguard-final-demo.mp4"
            out = audit_root / "readiness.json"

            _run_ok(
                [
                    sys.executable,
                    "-m",
                    "scripts.prepare_qwenguard_submission_pack",
                    "--out-dir",
                    str(pack_dir.relative_to(ROOT)),
                ]
            )
            _run_ok(
                [
                    sys.executable,
                    "-m",
                    "scripts.run_qwenguard_no_motion_health_check",
                    "--trace-out",
                    str(fixture_trace.relative_to(ROOT)),
                    "--report-out",
                    str(fixture_report.relative_to(ROOT)),
                    "--mode",
                    "fixture",
                    "--policy-available",
                    "--simulate-safe-motion-authority",
                    "--fixture-outcome",
                    "success",
                ]
            )
            _run_ok(
                [
                    sys.executable,
                    "-m",
                    "scripts.run_qwenguard_no_motion_health_check",
                    "--trace-out",
                    str(degraded_trace.relative_to(ROOT)),
                    "--report-out",
                    str(degraded_report.relative_to(ROOT)),
                    "--mode",
                    "degraded",
                ]
            )
            camera_frame.write_bytes(b"synthetic-so101-frame")
            camera_report.write_text(canonical_json(_camera_go_report()) + "\n", encoding="utf-8")
            _run_ok(
                [
                    sys.executable,
                    "-m",
                    "scripts.record_qwenguard_trial",
                    "--trial-id",
                    "trial-001",
                    "--outcome",
                    "success",
                    "--motion-executed",
                    "true",
                    "--control-label",
                    "AUTONOMOUS",
                    "--trace-dir",
                    str(trial_trace_dir.relative_to(ROOT)),
                    "--csv-out",
                    str(trial_csv.relative_to(ROOT)),
                    "--report-out",
                    str(trial_report.relative_to(ROOT)),
                ]
            )
            _run_ok(
                [
                    sys.executable,
                    "-m",
                    "scripts.summarize_qwenguard_trials",
                    "--trial-csv",
                    str(trial_csv.relative_to(ROOT)),
                    "--trial-trace-dir",
                    str(trial_trace_dir.relative_to(ROOT)),
                    "--out",
                    str(trial_summary.relative_to(ROOT)),
                ]
            )
            ecs_report.write_text(canonical_json(_ecs_go_report()) + "\n", encoding="utf-8")
            ecs_terminal_artifact.write_text("Alibaba ECS instance i-accountable-swarm served public endpoint.\n", encoding="utf-8")
            ecs_review.write_text(
                _ecs_proof_review(
                    ecs_report=ecs_report.relative_to(ROOT),
                    terminal_artifact=ecs_terminal_artifact.relative_to(ROOT),
                ),
                encoding="utf-8",
            )
            video_file.write_bytes(b"synthetic-video-artifact")
            video_review.write_text(_video_review(str(video_file.relative_to(ROOT))), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.audit_qwenguard_submission_readiness",
                    "--out",
                    str(out.relative_to(ROOT)),
                    "--submission-manifest",
                    str((pack_dir / "manifest.json").relative_to(ROOT)),
                    "--so101-camera-report",
                    str(camera_report.relative_to(ROOT)),
                    "--fixture-trace",
                    str(fixture_trace.relative_to(ROOT)),
                    "--degraded-trace",
                    str(degraded_trace.relative_to(ROOT)),
                    "--trial-csv",
                    str(trial_csv.relative_to(ROOT)),
                    "--trial-trace-dir",
                    str(trial_trace_dir.relative_to(ROOT)),
                    "--trial-summary",
                    str(trial_summary.relative_to(ROOT)),
                    "--ecs-report",
                    str(ecs_report.relative_to(ROOT)),
                    "--ecs-proof-review",
                    str(ecs_review.relative_to(ROOT)),
                    "--video-review",
                    str(video_review.relative_to(ROOT)),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(out.read_text(encoding="utf-8"))

        self.assertEqual(report["outcome"], "GO")
        self.assertEqual(report["submission_readiness"], "READY")
        self.assertTrue(all(report["pass_conditions"].values()))
        self.assertIn("checks:", result.stdout)
        self.assertIn(
            "OK submission_pack_manifest_go - submission pack generated and still claim-safe",
            result.stdout,
        )
        self.assertIn(
            "OK human_video_review_present - human video review records explicit reviewer, artifact, and claim checks",
            result.stdout,
        )
        trial_trace_check = next(check for check in report["checks"] if check["name"] == "measured_trial_traces_verify")
        trial_csv_check = next(check for check in report["checks"] if check["name"] == "measured_trial_csv_has_rows")
        trial_summary_check = next(check for check in report["checks"] if check["name"] == "measured_trial_summary_go")
        self.assertEqual(trial_trace_check["evidence"]["verified_trace_count"], 1)
        self.assertEqual(trial_csv_check["evidence"]["valid_row_count"], 1)
        self.assertEqual(trial_csv_check["evidence"]["invalid_row_count"], 0)
        self.assertEqual(trial_summary_check["evidence"]["total_trials"], 1)
        ecs_review_check = next(check for check in report["checks"] if check["name"] == "ecs_proof_review_present")
        self.assertTrue(ecs_review_check["ok"])

    def test_ecs_smoke_report_requires_human_proof_review_note(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            ecs_report = audit_root / "ecs_smoke_report.json"
            out = audit_root / "readiness.json"
            ecs_report.write_text(canonical_json(_ecs_go_report()) + "\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.audit_qwenguard_submission_readiness",
                    "--out",
                    str(out.relative_to(ROOT)),
                    "--ecs-report",
                    str(ecs_report.relative_to(ROOT)),
                    "--ecs-proof-review",
                    str((audit_root / "missing-ecs-review.md").relative_to(ROOT)),
                    "--allow-narrow-claim",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(out.read_text(encoding="utf-8"))

        ecs_report_check = next(check for check in report["checks"] if check["name"] == "ecs_report_is_public_go")
        ecs_review_check = next(check for check in report["checks"] if check["name"] == "ecs_proof_review_present")
        self.assertTrue(ecs_report_check["ok"])
        self.assertFalse(ecs_review_check["ok"])
        self.assertEqual(ecs_review_check["reason"], "ECS proof review note is missing")

    def test_ecs_proof_review_must_bind_to_audited_ecs_report(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            ecs_report = audit_root / "ecs_smoke_report.json"
            other_report = audit_root / "other_ecs_smoke_report.json"
            ecs_review = audit_root / "ecs_proof_review.md"
            terminal_artifact = audit_root / "ecs-terminal-proof.txt"
            out = audit_root / "readiness.json"
            ecs_report.write_text(canonical_json(_ecs_go_report()) + "\n", encoding="utf-8")
            terminal_artifact.write_text("Alibaba ECS public endpoint proof.\n", encoding="utf-8")
            ecs_review.write_text(
                _ecs_proof_review(
                    ecs_report=other_report.relative_to(ROOT),
                    terminal_artifact=terminal_artifact.relative_to(ROOT),
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.audit_qwenguard_submission_readiness",
                    "--out",
                    str(out.relative_to(ROOT)),
                    "--ecs-report",
                    str(ecs_report.relative_to(ROOT)),
                    "--ecs-proof-review",
                    str(ecs_review.relative_to(ROOT)),
                    "--allow-narrow-claim",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(out.read_text(encoding="utf-8"))

        ecs_review_check = next(check for check in report["checks"] if check["name"] == "ecs_proof_review_present")
        self.assertFalse(ecs_review_check["ok"])
        self.assertIn(
            "ECS-report field does not match audited ECS smoke report",
            ecs_review_check["evidence"]["invalid_reasons"],
        )

    def test_ecs_proof_review_symlink_terminal_artifact_fails_without_crash(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir, TemporaryDirectory() as outside_tmpdir:
            audit_root = Path(tmpdir)
            outside_file = Path(outside_tmpdir) / "outside-terminal.txt"
            outside_file.write_text("outside repo terminal proof\n", encoding="utf-8")
            ecs_report = audit_root / "ecs_smoke_report.json"
            ecs_review = audit_root / "ecs_proof_review.md"
            terminal_link = audit_root / "terminal-link.txt"
            out = audit_root / "readiness.json"
            try:
                terminal_link.symlink_to(outside_file)
            except OSError as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")
            ecs_report.write_text(canonical_json(_ecs_go_report()) + "\n", encoding="utf-8")
            ecs_review.write_text(
                _ecs_proof_review(
                    ecs_report=ecs_report.relative_to(ROOT),
                    terminal_artifact=terminal_link.relative_to(ROOT),
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.audit_qwenguard_submission_readiness",
                    "--out",
                    str(out.relative_to(ROOT)),
                    "--ecs-report",
                    str(ecs_report.relative_to(ROOT)),
                    "--ecs-proof-review",
                    str(ecs_review.relative_to(ROOT)),
                    "--allow-narrow-claim",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(out.read_text(encoding="utf-8"))

        ecs_review_check = next(check for check in report["checks"] if check["name"] == "ecs_proof_review_present")
        self.assertFalse(ecs_review_check["ok"])
        self.assertIn("Terminal-artifact local path must stay inside repository", ecs_review_check["evidence"]["invalid_reasons"])
        self.assertEqual(ecs_review_check["evidence"]["terminal_artifact"]["kind"], "invalid-path")

    def test_ecs_proof_review_large_terminal_artifact_fails_without_reading_all(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            ecs_report = audit_root / "ecs_smoke_report.json"
            ecs_review = audit_root / "ecs_proof_review.md"
            terminal_artifact = audit_root / "large-terminal-proof.txt"
            out = audit_root / "readiness.json"
            ecs_report.write_text(canonical_json(_ecs_go_report()) + "\n", encoding="utf-8")
            terminal_artifact.write_text("x" * (1024 * 1024 + 1), encoding="utf-8")
            ecs_review.write_text(
                _ecs_proof_review(
                    ecs_report=ecs_report.relative_to(ROOT),
                    terminal_artifact=terminal_artifact.relative_to(ROOT),
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.audit_qwenguard_submission_readiness",
                    "--out",
                    str(out.relative_to(ROOT)),
                    "--ecs-report",
                    str(ecs_report.relative_to(ROOT)),
                    "--ecs-proof-review",
                    str(ecs_review.relative_to(ROOT)),
                    "--allow-narrow-claim",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(out.read_text(encoding="utf-8"))

        ecs_review_check = next(check for check in report["checks"] if check["name"] == "ecs_proof_review_present")
        self.assertFalse(ecs_review_check["ok"])
        self.assertIn(
            "Terminal-artifact local text is too large; provide a sanitized excerpt",
            ecs_review_check["evidence"]["invalid_reasons"],
        )

    def test_tampered_trace_keeps_readiness_narrow(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            fixture_trace = audit_root / "fixture_trace.json"
            fixture_report = audit_root / "fixture_report.json"
            out = audit_root / "readiness.json"
            _run_ok(
                [
                    sys.executable,
                    "-m",
                    "scripts.run_qwenguard_no_motion_health_check",
                    "--trace-out",
                    str(fixture_trace.relative_to(ROOT)),
                    "--report-out",
                    str(fixture_report.relative_to(ROOT)),
                    "--mode",
                    "fixture",
                    "--policy-available",
                    "--simulate-safe-motion-authority",
                    "--fixture-outcome",
                    "success",
                ]
            )
            payload = json.loads(fixture_trace.read_text(encoding="utf-8"))
            payload["events"][1]["command"]["gate_decision"] = "HOLD"
            fixture_trace.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.audit_qwenguard_submission_readiness",
                    "--out",
                    str(out.relative_to(ROOT)),
                    "--fixture-trace",
                    str(fixture_trace.relative_to(ROOT)),
                    "--allow-narrow-claim",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(out.read_text(encoding="utf-8"))

        self.assertEqual(report["outcome"], "NARROW_CLAIM")
        fixture_check = next(check for check in report["checks"] if check["name"] == "fixture_decisiontrace_verifies")
        self.assertFalse(fixture_check["ok"])

    def test_malformed_trace_missing_keys_does_not_crash_audit(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            fixture_trace = audit_root / "malformed_trace.json"
            out = audit_root / "readiness.json"
            fixture_trace.write_text('{"schema_version":"decisiontrace.v2"}\n', encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.audit_qwenguard_submission_readiness",
                    "--out",
                    str(out.relative_to(ROOT)),
                    "--fixture-trace",
                    str(fixture_trace.relative_to(ROOT)),
                    "--allow-narrow-claim",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(out.read_text(encoding="utf-8"))

        fixture_check = next(check for check in report["checks"] if check["name"] == "fixture_decisiontrace_verifies")
        self.assertFalse(fixture_check["ok"])
        self.assertEqual(fixture_check["reason"], "trace verification failed")
        self.assertEqual(fixture_check["evidence"]["error_type"], "KeyError")

    def test_trial_summary_is_required_even_when_trial_rows_verify(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            trial_trace_dir = audit_root / "trial_traces"
            trial_csv = audit_root / "trial_results.csv"
            trial_report = audit_root / "trial-001-report.json"
            out = audit_root / "readiness.json"
            _run_ok(
                [
                    sys.executable,
                    "-m",
                    "scripts.record_qwenguard_trial",
                    "--trial-id",
                    "trial-001",
                    "--outcome",
                    "success",
                    "--motion-executed",
                    "true",
                    "--trace-dir",
                    str(trial_trace_dir.relative_to(ROOT)),
                    "--csv-out",
                    str(trial_csv.relative_to(ROOT)),
                    "--report-out",
                    str(trial_report.relative_to(ROOT)),
                ]
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.audit_qwenguard_submission_readiness",
                    "--out",
                    str(out.relative_to(ROOT)),
                    "--trial-csv",
                    str(trial_csv.relative_to(ROOT)),
                    "--trial-trace-dir",
                    str(trial_trace_dir.relative_to(ROOT)),
                    "--trial-summary",
                    str((audit_root / "missing-summary.json").relative_to(ROOT)),
                    "--allow-narrow-claim",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(out.read_text(encoding="utf-8"))

        trial_csv_check = next(check for check in report["checks"] if check["name"] == "measured_trial_csv_has_rows")
        trial_summary_check = next(check for check in report["checks"] if check["name"] == "measured_trial_summary_go")
        self.assertEqual(report["outcome"], "NARROW_CLAIM")
        self.assertTrue(trial_csv_check["ok"])
        self.assertFalse(trial_summary_check["ok"])
        self.assertEqual(trial_summary_check["reason"], "file is missing")

    def test_trial_summary_empty_checks_are_rejected(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            trial_trace_dir = audit_root / "trial_traces"
            trial_csv = audit_root / "trial_results.csv"
            trial_summary = audit_root / "trial_summary.json"
            out = audit_root / "readiness.json"
            _write_valid_trial_summary(
                audit_root=audit_root,
                trial_trace_dir=trial_trace_dir,
                trial_csv=trial_csv,
                trial_summary=trial_summary,
            )
            payload = json.loads(trial_summary.read_text(encoding="utf-8"))
            payload["checks"] = {}
            trial_summary.write_text(canonical_json(payload) + "\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.audit_qwenguard_submission_readiness",
                    "--out",
                    str(out.relative_to(ROOT)),
                    "--trial-csv",
                    str(trial_csv.relative_to(ROOT)),
                    "--trial-trace-dir",
                    str(trial_trace_dir.relative_to(ROOT)),
                    "--trial-summary",
                    str(trial_summary.relative_to(ROOT)),
                    "--allow-narrow-claim",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(out.read_text(encoding="utf-8"))

        trial_summary_check = next(check for check in report["checks"] if check["name"] == "measured_trial_summary_go")
        self.assertFalse(trial_summary_check["ok"])
        self.assertFalse(trial_summary_check["evidence"]["summary_checks_ok"])
        self.assertIn("trial_csv_present", trial_summary_check["evidence"]["missing_summary_checks"])

    def test_trial_summary_binding_must_match_audited_trace(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            trial_trace_dir = audit_root / "trial_traces"
            trial_csv = audit_root / "trial_results.csv"
            trial_summary = audit_root / "trial_summary.json"
            out = audit_root / "readiness.json"
            _write_valid_trial_summary(
                audit_root=audit_root,
                trial_trace_dir=trial_trace_dir,
                trial_csv=trial_csv,
                trial_summary=trial_summary,
            )
            payload = json.loads(trial_summary.read_text(encoding="utf-8"))
            payload["trial_bindings"][0]["trace_summary_sha"] = "f" * 64
            trial_summary.write_text(canonical_json(payload) + "\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.audit_qwenguard_submission_readiness",
                    "--out",
                    str(out.relative_to(ROOT)),
                    "--trial-csv",
                    str(trial_csv.relative_to(ROOT)),
                    "--trial-trace-dir",
                    str(trial_trace_dir.relative_to(ROOT)),
                    "--trial-summary",
                    str(trial_summary.relative_to(ROOT)),
                    "--allow-narrow-claim",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(out.read_text(encoding="utf-8"))

        trial_summary_check = next(check for check in report["checks"] if check["name"] == "measured_trial_summary_go")
        self.assertFalse(trial_summary_check["ok"])
        self.assertEqual(trial_summary_check["evidence"]["binding_error_count"], 2)
        self.assertIn("trace_summary_sha not verified by audit", " ".join(trial_summary_check["evidence"]["binding_errors"]))

    def test_forged_ecs_report_with_empty_pass_conditions_is_rejected(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            ecs_report = audit_root / "forged_ecs_report.json"
            out = audit_root / "readiness.json"
            forged = _ecs_go_report()
            forged["pass_conditions"] = {}
            ecs_report.write_text(canonical_json(forged) + "\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.audit_qwenguard_submission_readiness",
                    "--out",
                    str(out.relative_to(ROOT)),
                    "--ecs-report",
                    str(ecs_report.relative_to(ROOT)),
                    "--allow-narrow-claim",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(out.read_text(encoding="utf-8"))

        ecs_check = next(check for check in report["checks"] if check["name"] == "ecs_report_is_public_go")
        self.assertFalse(ecs_check["ok"])
        self.assertIn("healthz", ecs_check["evidence"]["missing_pass_conditions"])
        self.assertFalse(ecs_check["evidence"]["qwen_ping_condition_present"])

    def test_malformed_json_records_parse_reason(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            manifest = audit_root / "manifest.json"
            out = audit_root / "readiness.json"
            manifest.write_text("{not-json}\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.audit_qwenguard_submission_readiness",
                    "--out",
                    str(out.relative_to(ROOT)),
                    "--submission-manifest",
                    str(manifest.relative_to(ROOT)),
                    "--allow-narrow-claim",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(out.read_text(encoding="utf-8"))

        manifest_check = next(check for check in report["checks"] if check["name"] == "submission_pack_manifest_go")
        self.assertFalse(manifest_check["ok"])
        self.assertEqual(manifest_check["reason"], "file is not valid JSON")

    def test_video_review_keywords_without_signoff_fields_are_rejected(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            video_review = audit_root / "final_video_review.md"
            out = audit_root / "readiness.json"
            video_review.write_text(
                "\n".join(
                    [
                        "# Final Video Review",
                        "",
                        "Qwen never controls motors.",
                        "SO-101 footage is labeled with the observed mode.",
                        "Alibaba ECS proof is shown only if the public report is GO.",
                        "Labels checked in captions: AUTONOMOUS, TELEOP, SCRIPTED.",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.audit_qwenguard_submission_readiness",
                    "--out",
                    str(out.relative_to(ROOT)),
                    "--video-review",
                    str(video_review.relative_to(ROOT)),
                    "--allow-narrow-claim",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(out.read_text(encoding="utf-8"))

        video_check = next(check for check in report["checks"] if check["name"] == "human_video_review_present")
        self.assertFalse(video_check["ok"])
        self.assertIn("Reviewed-by", video_check["evidence"]["missing_fields"])
        self.assertFalse(video_check["evidence"]["missing_phrases"])

    def test_video_review_placeholder_signoff_fields_are_rejected(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            video_review = audit_root / "final_video_review.md"
            out = audit_root / "readiness.json"
            video_review.write_text(
                _video_review()
                .replace("Reviewed-by: human-reviewer", "Reviewed-by: <your name>")
                .replace("Video-artifact: runs/submission/qwenguard-final-demo.mp4", "Video-artifact: TODO.mp4"),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.audit_qwenguard_submission_readiness",
                    "--out",
                    str(out.relative_to(ROOT)),
                    "--video-review",
                    str(video_review.relative_to(ROOT)),
                    "--allow-narrow-claim",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(out.read_text(encoding="utf-8"))

        video_check = next(check for check in report["checks"] if check["name"] == "human_video_review_present")
        self.assertFalse(video_check["ok"])
        self.assertEqual(video_check["evidence"]["invalid_fields"]["Reviewed-by"], "placeholder value")
        self.assertEqual(video_check["evidence"]["invalid_fields"]["Video-artifact"], "placeholder value")

    def test_video_review_missing_local_artifact_is_rejected(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            video_review = audit_root / "final_video_review.md"
            out = audit_root / "readiness.json"
            missing_video = audit_root / "missing-demo.mp4"
            video_review.write_text(_video_review(str(missing_video.relative_to(ROOT))), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.audit_qwenguard_submission_readiness",
                    "--out",
                    str(out.relative_to(ROOT)),
                    "--video-review",
                    str(video_review.relative_to(ROOT)),
                    "--allow-narrow-claim",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(out.read_text(encoding="utf-8"))

        video_check = next(check for check in report["checks"] if check["name"] == "human_video_review_present")
        self.assertFalse(video_check["ok"])
        self.assertEqual(video_check["evidence"]["invalid_fields"]["Video-artifact"], "video artifact file is missing")
        self.assertEqual(video_check["evidence"]["video_artifact"]["exists"], "false")

    def test_video_review_secret_like_text_is_rejected(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            video_review = audit_root / "final_video_review.md"
            video_file = audit_root / "qwenguard-final-demo.mp4"
            out = audit_root / "readiness.json"
            video_file.write_bytes(b"synthetic-video-artifact")
            video_review.write_text(
                _video_review(str(video_file.relative_to(ROOT)))
                + "\nOperator note: ALIBABA_API_KEY=sk-testsecret01234567890123456789\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.audit_qwenguard_submission_readiness",
                    "--out",
                    str(out.relative_to(ROOT)),
                    "--video-review",
                    str(video_review.relative_to(ROOT)),
                    "--allow-narrow-claim",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(out.read_text(encoding="utf-8"))

        video_check = next(check for check in report["checks"] if check["name"] == "human_video_review_present")
        self.assertFalse(video_check["ok"])
        self.assertEqual(
            video_check["evidence"]["invalid_fields"]["Secrets-reviewed"],
            "review note contains secret-like material",
        )

    def test_video_review_non_yes_signoff_values_are_rejected(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            video_review = audit_root / "final_video_review.md"
            out = audit_root / "readiness.json"
            video_review.write_text(
                _video_review()
                .replace("Privacy-reviewed: yes", "Privacy-reviewed: no")
                .replace("Mode-labels-reviewed: yes", "Mode-labels-reviewed: maybe"),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.audit_qwenguard_submission_readiness",
                    "--out",
                    str(out.relative_to(ROOT)),
                    "--video-review",
                    str(video_review.relative_to(ROOT)),
                    "--allow-narrow-claim",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(out.read_text(encoding="utf-8"))

        video_check = next(check for check in report["checks"] if check["name"] == "human_video_review_present")
        self.assertFalse(video_check["ok"])
        self.assertEqual(video_check["evidence"]["invalid_fields"]["Privacy-reviewed"], "must be yes/reviewed")
        self.assertEqual(video_check["evidence"]["invalid_fields"]["Mode-labels-reviewed"], "must be yes/reviewed")

    def test_video_review_duplicate_required_fields_are_rejected(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            video_review = audit_root / "final_video_review.md"
            out = audit_root / "readiness.json"
            video_review.write_text(_video_review() + "Reviewed-by: second-reviewer\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.audit_qwenguard_submission_readiness",
                    "--out",
                    str(out.relative_to(ROOT)),
                    "--video-review",
                    str(video_review.relative_to(ROOT)),
                    "--allow-narrow-claim",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(out.read_text(encoding="utf-8"))

        video_check = next(check for check in report["checks"] if check["name"] == "human_video_review_present")
        self.assertFalse(video_check["ok"])
        self.assertEqual(video_check["evidence"]["invalid_fields"]["Reviewed-by"], "duplicate field")
        self.assertEqual(video_check["evidence"]["duplicate_fields"]["reviewed-by"], 2)

    def test_video_review_remote_artifact_must_use_https(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            video_review = audit_root / "final_video_review.md"
            out = audit_root / "readiness.json"
            video_review.write_text(_video_review("http://qwenguard.invalid/qwenguard-final-demo.mp4"), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.audit_qwenguard_submission_readiness",
                    "--out",
                    str(out.relative_to(ROOT)),
                    "--video-review",
                    str(video_review.relative_to(ROOT)),
                    "--allow-narrow-claim",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(out.read_text(encoding="utf-8"))

        video_check = next(check for check in report["checks"] if check["name"] == "human_video_review_present")
        self.assertFalse(video_check["ok"])
        self.assertEqual(
            video_check["evidence"]["invalid_fields"]["Video-artifact"],
            "remote video artifact URL must use https",
        )

    def test_video_review_date_must_be_literal_yyyy_mm_dd(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            video_review = audit_root / "final_video_review.md"
            out = audit_root / "readiness.json"
            video_review.write_text(
                _video_review().replace("Review-date: 2026-06-29", "Review-date: 20260629"),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.audit_qwenguard_submission_readiness",
                    "--out",
                    str(out.relative_to(ROOT)),
                    "--video-review",
                    str(video_review.relative_to(ROOT)),
                    "--allow-narrow-claim",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(out.read_text(encoding="utf-8"))

        video_check = next(check for check in report["checks"] if check["name"] == "human_video_review_present")
        self.assertFalse(video_check["ok"])
        self.assertEqual(video_check["evidence"]["invalid_fields"]["Review-date"], "must be YYYY-MM-DD")

    def test_repo_escape_path_rejected_before_report_write(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            out = Path(tmpdir) / "readiness.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.audit_qwenguard_submission_readiness",
                    "--out",
                    str(out.relative_to(ROOT)),
                    "--fixture-trace",
                    "../escape.json",
                    "--allow-narrow-claim",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertFalse(out.exists())
            self.assertIn("path must stay inside the repository checkout", result.stderr)

    def test_camera_report_rejects_escaped_frame_artifact(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            camera_report = audit_root / "so101_capture_report.json"
            out = audit_root / "readiness.json"
            payload = _camera_go_report()
            payload["output_path"] = "../../../../frame.png"
            payload["capture"] = {"output_path": "../../../../frame.png"}
            camera_report.write_text(canonical_json(payload) + "\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.audit_qwenguard_submission_readiness",
                    "--out",
                    str(out.relative_to(ROOT)),
                    "--so101-camera-report",
                    str(camera_report.relative_to(ROOT)),
                    "--allow-narrow-claim",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(out.read_text(encoding="utf-8"))

        camera_check = next(check for check in report["checks"] if check["name"] == "so101_camera_report_go")
        self.assertFalse(camera_check["ok"])
        self.assertEqual(
            camera_check["reason"],
            "camera frame artifact path must stay inside the repository checkout",
        )

    def test_trial_csv_row_must_bind_to_measured_trial_trace(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            fixture_trace = audit_root / "fixture_trace.json"
            fixture_report = audit_root / "fixture_report.json"
            trial_csv = audit_root / "trial_results.csv"
            trial_trace_dir = audit_root / "trial_traces"
            out = audit_root / "readiness.json"
            _run_ok(
                [
                    sys.executable,
                    "-m",
                    "scripts.run_qwenguard_no_motion_health_check",
                    "--trace-out",
                    str(fixture_trace.relative_to(ROOT)),
                    "--report-out",
                    str(fixture_report.relative_to(ROOT)),
                    "--mode",
                    "fixture",
                    "--policy-available",
                    "--simulate-safe-motion-authority",
                    "--fixture-outcome",
                    "success",
                ]
            )
            fixture_summary = json.loads(fixture_report.read_text(encoding="utf-8"))["trace_summary_sha"]
            trial_trace_dir.mkdir()
            trial_csv.write_text(_trial_csv(fixture_summary), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.audit_qwenguard_submission_readiness",
                    "--out",
                    str(out.relative_to(ROOT)),
                    "--fixture-trace",
                    str(fixture_trace.relative_to(ROOT)),
                    "--trial-csv",
                    str(trial_csv.relative_to(ROOT)),
                    "--trial-trace-dir",
                    str(trial_trace_dir.relative_to(ROOT)),
                    "--allow-narrow-claim",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(out.read_text(encoding="utf-8"))

        trace_check = next(check for check in report["checks"] if check["name"] == "measured_trial_traces_verify")
        csv_check = next(check for check in report["checks"] if check["name"] == "measured_trial_csv_has_rows")
        self.assertFalse(trace_check["ok"])
        self.assertEqual(trace_check["reason"], "measured trial trace directory has no JSON traces")
        self.assertFalse(csv_check["ok"])
        self.assertIn("trace_summary_sha is not bound to an audited trace", csv_check["evidence"]["invalid_reasons"][0])

    def test_trial_csv_cannot_pass_when_trace_directory_has_invalid_trace(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            fixture_trace = audit_root / "fixture_trace.json"
            fixture_report = audit_root / "fixture_report.json"
            trial_csv = audit_root / "trial_results.csv"
            trial_trace_dir = audit_root / "trial_traces"
            out = audit_root / "readiness.json"
            _run_ok(
                [
                    sys.executable,
                    "-m",
                    "scripts.run_qwenguard_no_motion_health_check",
                    "--trace-out",
                    str(fixture_trace.relative_to(ROOT)),
                    "--report-out",
                    str(fixture_report.relative_to(ROOT)),
                    "--mode",
                    "fixture",
                    "--policy-available",
                    "--simulate-safe-motion-authority",
                    "--fixture-outcome",
                    "success",
                ]
            )
            fixture_summary = json.loads(fixture_report.read_text(encoding="utf-8"))["trace_summary_sha"]
            trial_trace_dir.mkdir()
            (trial_trace_dir / "trial-001.json").write_text(fixture_trace.read_text(encoding="utf-8"), encoding="utf-8")
            (trial_trace_dir / "trial-corrupt.json").write_text("{not-json}\n", encoding="utf-8")
            trial_csv.write_text(_trial_csv(fixture_summary), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.audit_qwenguard_submission_readiness",
                    "--out",
                    str(out.relative_to(ROOT)),
                    "--fixture-trace",
                    str(fixture_trace.relative_to(ROOT)),
                    "--trial-csv",
                    str(trial_csv.relative_to(ROOT)),
                    "--trial-trace-dir",
                    str(trial_trace_dir.relative_to(ROOT)),
                    "--allow-narrow-claim",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(out.read_text(encoding="utf-8"))

        trace_check = next(check for check in report["checks"] if check["name"] == "measured_trial_traces_verify")
        csv_check = next(check for check in report["checks"] if check["name"] == "measured_trial_csv_has_rows")
        self.assertFalse(trace_check["ok"])
        self.assertEqual(trace_check["evidence"]["verified_trace_count"], 1)
        self.assertEqual(trace_check["evidence"]["invalid_reason_count"], 1)
        self.assertFalse(csv_check["ok"])
        self.assertFalse(csv_check["evidence"]["trace_dependency_satisfied"])


def _run_ok(args: list[str]) -> None:
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise AssertionError(f"command failed: {args}\nstdout={result.stdout}\nstderr={result.stderr}")


def _write_valid_trial_summary(
    *,
    audit_root: Path,
    trial_trace_dir: Path,
    trial_csv: Path,
    trial_summary: Path,
) -> None:
    trial_report = audit_root / "trial-001-report.json"
    _run_ok(
        [
            sys.executable,
            "-m",
            "scripts.record_qwenguard_trial",
            "--trial-id",
            "trial-001",
            "--outcome",
            "success",
            "--motion-executed",
            "true",
            "--control-label",
            "AUTONOMOUS",
            "--trace-dir",
            str(trial_trace_dir.relative_to(ROOT)),
            "--csv-out",
            str(trial_csv.relative_to(ROOT)),
            "--report-out",
            str(trial_report.relative_to(ROOT)),
        ]
    )
    _run_ok(
        [
            sys.executable,
            "-m",
            "scripts.summarize_qwenguard_trials",
            "--trial-csv",
            str(trial_csv.relative_to(ROOT)),
            "--trial-trace-dir",
            str(trial_trace_dir.relative_to(ROOT)),
            "--out",
            str(trial_summary.relative_to(ROOT)),
        ]
    )


def _camera_go_report() -> dict[str, object]:
    return {
        "schema_version": "so101-camera-capture-report.v1",
        "outcome": "GO",
        "camera_name": "so101_overhead",
        "index_or_path": 0,
        "output_path": "so101_frame.png",
        "pass_conditions": {
            "dependencies_available": True,
            "frame_captured": True,
            "trace_only_motion_boundary_preserved": True,
        },
        "capture": {
            "path": "so101_frame.png",
            "width": 640,
            "height": 480,
            "sha256": "b" * 64,
        },
    }


def _trial_csv(trace_summary_sha: str) -> str:
    row = {
        "trial_id": "trial-001",
        "task_instruction": "pick the red cube left of the green cube",
        "object_layout_id": "layout-a",
        "selector_mode": "qwen",
        "gate_mode": "on",
        "policy": "act",
        "cloud_mode": "online",
        "outcome": "success",
        "operator_label": "success",
        "qwen_eval_label": "success",
        "trace_summary_sha": trace_summary_sha,
        "notes": "synthetic readiness fixture",
    }
    header = trial_csv_header()
    invalid_row = {
        **row,
        "trial_id": "trial-invalid",
        "trace_summary_sha": "not-a-sha",
    }
    return (
        ",".join(header)
        + "\n"
        + ",".join(row[name] for name in header)
        + "\n"
        + "\n"
        + ",".join(invalid_row[name] for name in header)
        + "\n"
    )


def _ecs_go_report() -> dict[str, object]:
    checks = [
        {"name": "healthz", "ok": True},
        {"name": "readyz", "ok": True},
        {"name": "camera-fixture", "ok": True},
        {"name": "swarm-demo", "ok": True},
        {"name": "swarm-demo_summary.json", "ok": True},
        {"name": "qwen-ping_model_qwen-plus", "ok": True},
    ]
    return {
        "schema_version": "ecs-smoke-report.v1",
        "outcome": "GO",
        "proof_mode": "ecs-public",
        "base_url": "http://8.8.8.8:8000",
        "deployed_commit": COMMIT,
        "deployment": {
            "provider_asserted": "Alibaba Cloud ECS",
            "deployment_context_verified": True,
            "ecs_region": "us-west-1",
            "ecs_instance_id": "i-accountable-swarm",
            "ecs_public_ip": "8.8.8.8",
            "base_url_is_public_endpoint": True,
            "base_url_matches_public_ip_when_ip_literal": True,
        },
        "checks": checks,
        "pass_conditions": {
            "healthz": True,
            "readyz": True,
            "camera-fixture": True,
            "swarm-demo": True,
            "swarm-demo_summary.json": True,
            "qwen-ping_model_qwen-plus": True,
            "deployed_commit_recorded": True,
            "proof_mode_is_ecs_public": True,
            "ecs_region_recorded": True,
            "ecs_instance_id_recorded": True,
            "ecs_public_ip_is_global": True,
            "base_url_is_public_endpoint": True,
            "base_url_matches_public_ip_when_ip_literal": True,
        },
    }


def _ecs_proof_review(*, ecs_report: Path, terminal_artifact: Path) -> str:
    return "\n".join(
        [
            "# Alibaba ECS Proof Review",
            "",
            "Reviewed-by: human-reviewer",
            "Review-date: 2026-06-29",
            f"ECS-report: {ecs_report.as_posix()}",
            f"Terminal-artifact: {terminal_artifact.as_posix()}",
            "Terminal-artifact-kind: local",
            "Terminal-artifact-exists: true",
            "ECS-region: us-west-1",
            "ECS-instance-id: i-accountable-swarm",
            "ECS-public-ip: 8.8.8.8",
            "Base-url: http://8.8.8.8:8000",
            f"Deployed-commit: {COMMIT}",
            "ECS-report-GO-reviewed: yes",
            "Alibaba-context-reviewed: yes",
            "Public-endpoint-reviewed: yes",
            "Deployed-commit-reviewed: yes",
            "Security-group-reviewed: yes",
            "Secrets-reviewed: yes",
            "",
            "Alibaba ECS proof is claimed only because the checked ECS smoke report is GO with proof_mode ecs-public.",
            "The terminal or screenshot artifact was reviewed for Alibaba ECS context and secret exposure.",
            "This note does not claim production hosting, availability, latency, reliability, SO-101 operation, or Qwen onboard execution.",
            "",
            "## Reviewer Notes",
            "",
            "Synthetic test review.",
            "",
        ]
    )


def _video_review(video_artifact: str = "https://example.com/qwenguard-final-demo.mp4") -> str:
    return "\n".join(
        [
            "# Final Video Review",
            "",
            "Reviewed-by: human-reviewer",
            "Review-date: 2026-06-29",
            f"Video-artifact: {video_artifact}",
            "Privacy-reviewed: yes",
            "Claim-boundary-reviewed: yes",
            "Mode-labels-reviewed: yes",
            "ECS-proof-reviewed: yes",
            "SO-101-footage-reviewed: yes",
            "Secrets-reviewed: yes",
            "",
            "Qwen never controls motors.",
            "SO-101 footage is labeled with the observed mode.",
            "Alibaba ECS proof is shown only if the public report is GO.",
            "Labels checked in captions: AUTONOMOUS, TELEOP, SCRIPTED.",
            "",
        ]
    )
