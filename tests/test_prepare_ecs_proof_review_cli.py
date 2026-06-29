from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from accountable_swarm.trace.models import canonical_json
from scripts import prepare_ecs_proof_review as review_helper


ROOT = Path(__file__).resolve().parents[1]
COMMIT = "d" * 40


class PrepareEcsProofReviewCliTests(TestCase):
    def test_writes_review_note_for_go_report_and_terminal_artifact(self) -> None:
        base = ROOT / "runs" / "ecs"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            report = audit_root / "ecs_smoke_report.json"
            terminal = audit_root / "terminal-proof.txt"
            review = audit_root / "ecs_proof_review.md"
            report.write_text(canonical_json(_ecs_go_report()) + "\n", encoding="utf-8")
            terminal.write_text(
                "Alibaba ECS region us-west-1 instance i-accountable-swarm public endpoint checked.\n",
                encoding="utf-8",
            )

            result = _run_review_cli(
                "--out",
                str(review.relative_to(ROOT)),
                "--ecs-report",
                str(report.relative_to(ROOT)),
                "--terminal-artifact",
                str(terminal.relative_to(ROOT)),
                "--reviewed-by",
                "human-reviewer",
                "--review-date",
                "2026-06-29",
                "--confirm-report-go",
                "--confirm-alibaba-context",
                "--confirm-public-endpoint",
                "--confirm-deployed-commit",
                "--confirm-security-group",
                "--confirm-secrets",
                "--notes",
                "Terminal transcript reviewed after ECS public smoke collection.",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            text = review.read_text(encoding="utf-8")

        self.assertIn("outcome GO", result.stdout)
        self.assertIn("ECS-report-GO-reviewed: yes", text)
        self.assertIn("Alibaba-context-reviewed: yes", text)
        self.assertIn("Terminal-artifact-exists: true", text)
        self.assertIn("proof_mode ecs-public", text)

    def test_missing_confirmation_refuses_to_write(self) -> None:
        base = ROOT / "runs" / "ecs"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            report = audit_root / "ecs_smoke_report.json"
            terminal = audit_root / "terminal-proof.txt"
            review = audit_root / "ecs_proof_review.md"
            report.write_text(canonical_json(_ecs_go_report()) + "\n", encoding="utf-8")
            terminal.write_text("Alibaba ECS public endpoint checked.\n", encoding="utf-8")

            result = _run_review_cli(
                "--out",
                str(review.relative_to(ROOT)),
                "--ecs-report",
                str(report.relative_to(ROOT)),
                "--terminal-artifact",
                str(terminal.relative_to(ROOT)),
                "--reviewed-by",
                "human-reviewer",
                "--review-date",
                "2026-06-29",
                "--confirm-report-go",
                "--confirm-alibaba-context",
                "--confirm-public-endpoint",
                "--confirm-deployed-commit",
                "--confirm-security-group",
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("Secrets-reviewed", result.stderr)
            self.assertFalse(review.exists())

    def test_minimal_forged_go_report_refuses_to_write_review(self) -> None:
        base = ROOT / "runs" / "ecs"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            report = audit_root / "ecs_smoke_report.json"
            terminal = audit_root / "terminal-proof.txt"
            review = audit_root / "ecs_proof_review.md"
            report.write_text(
                canonical_json(
                    {
                        "schema_version": "ecs-smoke-report.v1",
                        "outcome": "GO",
                        "proof_mode": "ecs-public",
                        "deployment": {
                            "provider_asserted": "Alibaba Cloud ECS",
                            "deployment_context_verified": True,
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            terminal.write_text("Alibaba ECS public endpoint checked.\n", encoding="utf-8")

            result = _run_review_cli(
                "--out",
                str(review.relative_to(ROOT)),
                "--ecs-report",
                str(report.relative_to(ROOT)),
                "--terminal-artifact",
                str(terminal.relative_to(ROOT)),
                "--reviewed-by",
                "human-reviewer",
                "--review-date",
                "2026-06-29",
                "--confirm-report-go",
                "--confirm-alibaba-context",
                "--confirm-public-endpoint",
                "--confirm-deployed-commit",
                "--confirm-security-group",
                "--confirm-secrets",
            )

            self.assertEqual(result.returncode, 4)
            self.assertIn("missing required ECS public proof evidence", result.stderr)
            self.assertFalse(review.exists())

    def test_narrow_ecs_report_refuses_to_write_review(self) -> None:
        base = ROOT / "runs" / "ecs"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            report = audit_root / "ecs_smoke_report.json"
            terminal = audit_root / "terminal-proof.txt"
            review = audit_root / "ecs_proof_review.md"
            payload = _ecs_go_report()
            payload["outcome"] = "NARROW_CLAIM"
            report.write_text(canonical_json(payload) + "\n", encoding="utf-8")
            terminal.write_text("Alibaba ECS public endpoint checked.\n", encoding="utf-8")

            result = _run_review_cli(
                "--out",
                str(review.relative_to(ROOT)),
                "--ecs-report",
                str(report.relative_to(ROOT)),
                "--terminal-artifact",
                str(terminal.relative_to(ROOT)),
                "--reviewed-by",
                "human-reviewer",
                "--review-date",
                "2026-06-29",
                "--confirm-report-go",
                "--confirm-alibaba-context",
                "--confirm-public-endpoint",
                "--confirm-deployed-commit",
                "--confirm-security-group",
                "--confirm-secrets",
            )

            self.assertEqual(result.returncode, 4)
            self.assertIn("not GO ecs-public proof", result.stderr)
            self.assertFalse(review.exists())

    def test_colon_lines_in_notes_do_not_break_header_validation(self) -> None:
        base = ROOT / "runs" / "ecs"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            report = audit_root / "ecs_smoke_report.json"
            terminal = audit_root / "terminal-proof.txt"
            review = audit_root / "ecs_proof_review.md"
            report.write_text(canonical_json(_ecs_go_report()) + "\n", encoding="utf-8")
            terminal.write_text("Alibaba ECS public endpoint checked.\n", encoding="utf-8")

            result = _run_review_cli(
                "--out",
                str(review.relative_to(ROOT)),
                "--ecs-report",
                str(report.relative_to(ROOT)),
                "--terminal-artifact",
                str(terminal.relative_to(ROOT)),
                "--reviewed-by",
                "human-reviewer",
                "--review-date",
                "2026-06-29",
                "--confirm-report-go",
                "--confirm-alibaba-context",
                "--confirm-public-endpoint",
                "--confirm-deployed-commit",
                "--confirm-security-group",
                "--confirm-secrets",
                "--notes",
                "Security group: operator IP only.\nReviewed-by: duplicate note text ignored.",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            text = review.read_text(encoding="utf-8")

        self.assertIn("Security group: operator IP only.", text)
        self.assertIn("Reviewed-by: human-reviewer", text)

    def test_missing_terminal_artifact_refuses_to_write_review(self) -> None:
        base = ROOT / "runs" / "ecs"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            report = audit_root / "ecs_smoke_report.json"
            missing_terminal = audit_root / "missing-terminal.txt"
            review = audit_root / "ecs_proof_review.md"
            report.write_text(canonical_json(_ecs_go_report()) + "\n", encoding="utf-8")

            result = _run_review_cli(
                "--out",
                str(review.relative_to(ROOT)),
                "--ecs-report",
                str(report.relative_to(ROOT)),
                "--terminal-artifact",
                str(missing_terminal.relative_to(ROOT)),
                "--reviewed-by",
                "human-reviewer",
                "--review-date",
                "2026-06-29",
                "--confirm-report-go",
                "--confirm-alibaba-context",
                "--confirm-public-endpoint",
                "--confirm-deployed-commit",
                "--confirm-security-group",
                "--confirm-secrets",
            )

            self.assertEqual(result.returncode, 4)
            self.assertIn("terminal artifact file is missing", result.stderr)
            self.assertFalse(review.exists())

    def test_json_terminal_artifact_is_rejected(self) -> None:
        base = ROOT / "runs" / "ecs"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            report = audit_root / "ecs_smoke_report.json"
            review = audit_root / "ecs_proof_review.md"
            report.write_text(canonical_json(_ecs_go_report()) + "\n", encoding="utf-8")

            result = _run_review_cli(
                "--out",
                str(review.relative_to(ROOT)),
                "--ecs-report",
                str(report.relative_to(ROOT)),
                "--terminal-artifact",
                str(report.relative_to(ROOT)),
                "--reviewed-by",
                "human-reviewer",
                "--review-date",
                "2026-06-29",
                "--confirm-report-go",
                "--confirm-alibaba-context",
                "--confirm-public-endpoint",
                "--confirm-deployed-commit",
                "--confirm-security-group",
                "--confirm-secrets",
            )

            self.assertEqual(result.returncode, 4)
            self.assertIn("terminal artifact must be a transcript, screenshot, or video file", result.stderr)
            self.assertFalse(review.exists())

    def test_unreadable_text_artifact_returns_refusal(self) -> None:
        base = ROOT / "runs" / "ecs"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            artifact = Path(tmpdir) / "terminal-proof.txt"
            artifact.write_text("Alibaba ECS public endpoint checked.\n", encoding="utf-8")
            with patch.object(Path, "read_text", side_effect=OSError("boom")):
                error = review_helper._validate_terminal_artifact(ROOT, str(artifact.relative_to(ROOT)))

        self.assertEqual(error, "text terminal artifact could not be read")

    def test_secret_like_terminal_transcript_refuses_to_write_review(self) -> None:
        base = ROOT / "runs" / "ecs"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            report = audit_root / "ecs_smoke_report.json"
            terminal = audit_root / "terminal-proof.txt"
            review = audit_root / "ecs_proof_review.md"
            report.write_text(canonical_json(_ecs_go_report()) + "\n", encoding="utf-8")
            terminal.write_text("ALIBABA_API_KEY=plain_secret_marker\n", encoding="utf-8")

            result = _run_review_cli(
                "--out",
                str(review.relative_to(ROOT)),
                "--ecs-report",
                str(report.relative_to(ROOT)),
                "--terminal-artifact",
                str(terminal.relative_to(ROOT)),
                "--reviewed-by",
                "human-reviewer",
                "--review-date",
                "2026-06-29",
                "--confirm-report-go",
                "--confirm-alibaba-context",
                "--confirm-public-endpoint",
                "--confirm-deployed-commit",
                "--confirm-security-group",
                "--confirm-secrets",
            )

            self.assertEqual(result.returncode, 4)
            self.assertIn("terminal artifact file contains secret-like material", result.stderr)
            self.assertFalse(review.exists())

    def test_https_terminal_artifact_is_allowed(self) -> None:
        base = ROOT / "runs" / "ecs"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            report = audit_root / "ecs_smoke_report.json"
            review = audit_root / "ecs_proof_review.md"
            report.write_text(canonical_json(_ecs_go_report()) + "\n", encoding="utf-8")

            result = _run_review_cli(
                "--out",
                str(review.relative_to(ROOT)),
                "--ecs-report",
                str(report.relative_to(ROOT)),
                "--terminal-artifact",
                "https://accountable-swarm.invalid/ecs-proof-terminal.png",
                "--reviewed-by",
                "human-reviewer",
                "--review-date",
                "2026-06-29",
                "--confirm-report-go",
                "--confirm-alibaba-context",
                "--confirm-public-endpoint",
                "--confirm-deployed-commit",
                "--confirm-security-group",
                "--confirm-secrets",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            text = review.read_text(encoding="utf-8")

        self.assertIn("Terminal-artifact-kind: https", text)
        self.assertIn("Terminal-artifact-exists: not checked", text)


def _run_review_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.prepare_ecs_proof_review",
            *args,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _ecs_go_report() -> dict[str, object]:
    return {
        "schema_version": "ecs-smoke-report.v1",
        "outcome": "GO",
        "base_url": "http://8.8.8.8:8000",
        "deployed_commit": COMMIT,
        "proof_mode": "ecs-public",
        "deployment": {
            "provider_asserted": "Alibaba Cloud ECS",
            "deployment_context_verified": True,
            "ecs_region": "us-west-1",
            "ecs_instance_id": "i-accountable-swarm",
            "ecs_public_ip": "8.8.8.8",
            "base_url_is_public_endpoint": True,
            "base_url_matches_public_ip_when_ip_literal": True,
        },
        "qwen_model": "qwen-plus",
        "checks": [
            {"name": "healthz", "ok": True},
            {"name": "readyz", "ok": True},
            {"name": "camera-fixture", "ok": True},
            {"name": "swarm-demo", "ok": True},
            {"name": "swarm-demo_summary.json", "ok": True},
            {"name": "qwen-ping_model_qwen-plus", "ok": True},
        ],
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
        "non_claims": ["not a production hosting claim"],
    }
