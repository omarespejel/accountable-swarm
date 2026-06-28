#!/usr/bin/env python3
"""Prepare the human-signed QwenGuard final video review note."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from scripts.audit_qwenguard_submission_readiness import (
    DEFAULT_VIDEO_REVIEW,
    _display_path,
    _find_repo_root,
    _repo_path,
    check_video_review_text,
)


CONFIRMATION_FLAGS = {
    "privacy": "Privacy-reviewed",
    "claim_boundary": "Claim-boundary-reviewed",
    "mode_labels": "Mode-labels-reviewed",
    "ecs_proof": "ECS-proof-reviewed",
    "so101_footage": "SO-101-footage-reviewed",
    "secrets": "Secrets-reviewed",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_VIDEO_REVIEW)
    parser.add_argument("--reviewed-by", required=True)
    parser.add_argument("--review-date", required=True, help="Literal YYYY-MM-DD review date.")
    parser.add_argument("--video-artifact", required=True, help="HTTPS URL or repo-relative video path.")
    parser.add_argument("--notes", default="")
    parser.add_argument("--allow-overwrite", action="store_true")
    for flag_name, field_name in CONFIRMATION_FLAGS.items():
        parser.add_argument(
            f"--confirm-{flag_name.replace('_', '-')}",
            action="store_true",
            help=f"Confirm final video review field `{field_name}: yes`.",
        )
    args = parser.parse_args()

    missing = [
        field_name
        for flag_name, field_name in CONFIRMATION_FLAGS.items()
        if not getattr(args, f"confirm_{flag_name}")
    ]
    if missing:
        print(
            "final video review note not written; missing explicit confirmations: "
            + ", ".join(missing),
            file=sys.stderr,
        )
        return 2

    try:
        repo_root = _find_repo_root(Path.cwd())
        out = _repo_path(repo_root, args.out)
    except ValueError as exc:
        print(f"final video review note failed: {exc}", file=sys.stderr)
        return 2
    if out.exists() and not args.allow_overwrite:
        print(f"final video review note failed: output already exists: {_display_path(repo_root, out)}", file=sys.stderr)
        return 2
    if out.exists() and out.is_dir():
        print(f"final video review note failed: output path is a directory: {_display_path(repo_root, out)}", file=sys.stderr)
        return 2
    if out.suffix != ".md":
        print("final video review note failed: output path must end in .md", file=sys.stderr)
        return 2
    if out.parent.exists() and not out.parent.is_dir():
        print(f"final video review note failed: output parent is not a directory: {out.parent}", file=sys.stderr)
        return 2

    note = _render_review_note(
        reviewed_by=args.reviewed_by,
        review_date=args.review_date,
        video_artifact=args.video_artifact,
        notes=args.notes,
    )
    check = check_video_review_text(repo_root=repo_root, path=out, text=note)
    if not check["ok"]:
        print(f"final video review note failed: {check['reason']}", file=sys.stderr)
        evidence = check.get("evidence", {})
        for key in ("missing_phrases", "missing_fields", "invalid_fields"):
            value = evidence.get(key)
            if value:
                print(f"{key}: {value}", file=sys.stderr)
        return 4

    tmp = out.with_name(out.name + ".tmp")
    success = False
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(note, encoding="utf-8")
        tmp.replace(out)
        success = True
    except OSError as exc:
        print(f"final video review note failed: {exc}", file=sys.stderr)
        return 2
    finally:
        if not success:
            tmp.unlink(missing_ok=True)

    print("outcome GO")
    print(f"review {_display_path(repo_root, out)}")
    return 0


def _render_review_note(*, reviewed_by: str, review_date: str, video_artifact: str, notes: str) -> str:
    lines = [
        "# Final Video Review",
        "",
        f"Reviewed-by: {reviewed_by}",
        f"Review-date: {review_date}",
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
        "## Reviewer Notes",
        "",
        notes.strip() or "No additional notes.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
