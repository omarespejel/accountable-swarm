from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]


class PrepareQwenGuardFinalVideoReviewCliTests(TestCase):
    def test_writes_review_note_that_readiness_audit_accepts(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            video = audit_root / "qwenguard-final-demo.mp4"
            review = audit_root / "final_video_review.md"
            readiness = audit_root / "readiness.json"
            video.write_bytes(b"synthetic final demo video")

            result = _run_review_cli(
                "--out",
                str(review.relative_to(ROOT)),
                "--reviewed-by",
                "human-reviewer",
                "--review-date",
                "2026-06-29",
                "--video-artifact",
                str(video.relative_to(ROOT)),
                "--confirm-privacy",
                "--confirm-claim-boundary",
                "--confirm-mode-labels",
                "--confirm-ecs-proof",
                "--confirm-so101-footage",
                "--confirm-secrets",
                "--notes",
                "Human reviewed the final cut and confirmed claim labels.",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("outcome GO", result.stdout)
            self.assertTrue(review.is_file())

            audit = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.audit_qwenguard_submission_readiness",
                    "--out",
                    str(readiness.relative_to(ROOT)),
                    "--video-review",
                    str(review.relative_to(ROOT)),
                    "--allow-narrow-claim",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(audit.returncode, 0, audit.stderr)
            report = json.loads(readiness.read_text(encoding="utf-8"))

        video_check = next(check for check in report["checks"] if check["name"] == "human_video_review_present")
        self.assertTrue(video_check["ok"])
        self.assertEqual(video_check["evidence"]["video_artifact"]["exists"], "true")

    def test_missing_confirmation_refuses_to_write(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            video = audit_root / "qwenguard-final-demo.mp4"
            review = audit_root / "final_video_review.md"
            video.write_bytes(b"synthetic final demo video")

            result = _run_review_cli(
                "--out",
                str(review.relative_to(ROOT)),
                "--reviewed-by",
                "human-reviewer",
                "--review-date",
                "2026-06-29",
                "--video-artifact",
                str(video.relative_to(ROOT)),
                "--confirm-privacy",
                "--confirm-claim-boundary",
                "--confirm-mode-labels",
                "--confirm-ecs-proof",
                "--confirm-so101-footage",
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("Secrets-reviewed", result.stderr)
            self.assertFalse(review.exists())

    def test_missing_local_video_refuses_to_write_review(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            review = audit_root / "final_video_review.md"
            missing_video = audit_root / "missing-demo.mp4"

            result = _run_review_cli(
                "--out",
                str(review.relative_to(ROOT)),
                "--reviewed-by",
                "human-reviewer",
                "--review-date",
                "2026-06-29",
                "--video-artifact",
                str(missing_video.relative_to(ROOT)),
                "--confirm-privacy",
                "--confirm-claim-boundary",
                "--confirm-mode-labels",
                "--confirm-ecs-proof",
                "--confirm-so101-footage",
                "--confirm-secrets",
            )

            self.assertEqual(result.returncode, 4)
            self.assertIn("video artifact file is missing", result.stderr)
            self.assertFalse(review.exists())
            self.assertFalse((audit_root / "final_video_review.md.tmp").exists())

    def test_secret_like_notes_refuse_to_write_review(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            video = audit_root / "qwenguard-final-demo.mp4"
            review = audit_root / "final_video_review.md"
            video.write_bytes(b"synthetic final demo video")

            result = _run_review_cli(
                "--out",
                str(review.relative_to(ROOT)),
                "--reviewed-by",
                "human-reviewer",
                "--review-date",
                "2026-06-29",
                "--video-artifact",
                str(video.relative_to(ROOT)),
                "--confirm-privacy",
                "--confirm-claim-boundary",
                "--confirm-mode-labels",
                "--confirm-ecs-proof",
                "--confirm-so101-footage",
                "--confirm-secrets",
                "--notes",
                "ALIBABA_API_KEY=<redacted>",
            )

            self.assertEqual(result.returncode, 4)
            self.assertIn("review note contains secret-like material", result.stderr)
            self.assertFalse(review.exists())
            self.assertFalse((audit_root / "final_video_review.md.tmp").exists())

    def test_existing_directory_output_is_rejected_before_write(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            video = audit_root / "qwenguard-final-demo.mp4"
            review_dir = audit_root / "final_video_review.md"
            video.write_bytes(b"synthetic final demo video")
            review_dir.mkdir()

            result = _run_review_cli(
                "--out",
                str(review_dir.relative_to(ROOT)),
                "--reviewed-by",
                "human-reviewer",
                "--review-date",
                "2026-06-29",
                "--video-artifact",
                str(video.relative_to(ROOT)),
                "--confirm-privacy",
                "--confirm-claim-boundary",
                "--confirm-mode-labels",
                "--confirm-ecs-proof",
                "--confirm-so101-footage",
                "--confirm-secrets",
                "--allow-overwrite",
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("output path is a directory", result.stderr)
            self.assertFalse((audit_root / "final_video_review.md.tmp").exists())

    def test_non_markdown_output_is_rejected_before_write(self) -> None:
        base = ROOT / "runs" / "submission"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            audit_root = Path(tmpdir)
            video = audit_root / "qwenguard-final-demo.mp4"
            review = audit_root / "final_video_review.txt"
            video.write_bytes(b"synthetic final demo video")

            result = _run_review_cli(
                "--out",
                str(review.relative_to(ROOT)),
                "--reviewed-by",
                "human-reviewer",
                "--review-date",
                "2026-06-29",
                "--video-artifact",
                str(video.relative_to(ROOT)),
                "--confirm-privacy",
                "--confirm-claim-boundary",
                "--confirm-mode-labels",
                "--confirm-ecs-proof",
                "--confirm-so101-footage",
                "--confirm-secrets",
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("output path must end in .md", result.stderr)
            self.assertFalse(review.exists())


def _run_review_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.prepare_qwenguard_final_video_review",
            *args,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
