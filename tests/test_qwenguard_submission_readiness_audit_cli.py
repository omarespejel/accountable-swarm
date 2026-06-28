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
            ecs_report = audit_root / "ecs_smoke_report.json"
            video_review = audit_root / "final_video_review.md"
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
            fixture_summary = json.loads(fixture_report.read_text(encoding="utf-8"))["trace_summary_sha"]
            trial_trace_dir.mkdir()
            (trial_trace_dir / "trial-001.json").write_text(fixture_trace.read_text(encoding="utf-8"), encoding="utf-8")
            camera_frame.write_bytes(b"synthetic-so101-frame")
            camera_report.write_text(canonical_json(_camera_go_report()) + "\n", encoding="utf-8")
            trial_csv.write_text(_trial_csv(fixture_summary), encoding="utf-8")
            ecs_report.write_text(canonical_json(_ecs_go_report()) + "\n", encoding="utf-8")
            video_review.write_text(_video_review(), encoding="utf-8")

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
                    "--ecs-report",
                    str(ecs_report.relative_to(ROOT)),
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
        trial_trace_check = next(check for check in report["checks"] if check["name"] == "measured_trial_traces_verify")
        trial_csv_check = next(check for check in report["checks"] if check["name"] == "measured_trial_csv_has_rows")
        self.assertEqual(trial_trace_check["evidence"]["verified_trace_count"], 1)
        self.assertEqual(trial_csv_check["evidence"]["valid_row_count"], 1)
        self.assertEqual(trial_csv_check["evidence"]["invalid_row_count"], 1)

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


def _run_ok(args: list[str]) -> None:
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise AssertionError(f"command failed: {args}\nstdout={result.stdout}\nstderr={result.stderr}")


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
        "deployed_commit": COMMIT,
        "deployment": {
            "provider_asserted": "Alibaba Cloud ECS",
            "deployment_context_verified": True,
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


def _video_review() -> str:
    return "\n".join(
        [
            "# Final Video Review",
            "",
            "Qwen never controls motors.",
            "SO-101 footage is labeled with the observed mode.",
            "Alibaba ECS proof is shown only if the public report is GO.",
            "Labels checked in captions: AUTONOMOUS, TELEOP, SCRIPTED.",
            "",
        ]
    )
