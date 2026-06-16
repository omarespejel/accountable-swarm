#!/usr/bin/env python3
"""Prepare a safe sensor-frame proof pack for the physical-node lane."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from accountable_swarm.images import image_size
from accountable_swarm.trace.models import canonical_json, trace_from_dict, verify_trace


PACK_SCHEMA_VERSION = "sensor-frame-proof-pack.v1"
DEFAULT_OUT_DIR = Path("runs/physical/sensor-frame-proof")
SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"Authorization:[ \t]*Bearer[ \t]+(?!<redacted>)\S+", re.IGNORECASE),
    re.compile(r"ALIBABA_API_KEY[ \t]*=[ \t]*\S+", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9._-]{6,}"),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--image", type=Path)
    source.add_argument("--capture-webcam", action="store_true")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--mode", choices=["fixture", "dashscope", "degraded"], default="fixture")
    parser.add_argument("--degraded-on-error", action="store_true")
    parser.add_argument("--target", default="marked hazard")
    parser.add_argument("--model", default="qwen3-vl-flash")
    parser.add_argument("--keep-captured-frame", action="store_true")
    args = parser.parse_args()

    try:
        repo_root = _find_repo_root(Path.cwd())
        out_dir = _repo_path(repo_root, args.out_dir)
    except ValueError as exc:
        print(f"sensor-frame proof pack failed: {exc}", file=sys.stderr)
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)
    trace_path = out_dir / "trace.json"
    report_path = out_dir / "report.json"
    source_frame_path = out_dir / "source_frame.png"
    command = [
        sys.executable,
        "-m",
        "scripts.run_camera_go_gate",
    ]
    display_command = [
        "python3",
        "-m",
        "scripts.run_camera_go_gate",
    ]
    if args.image is not None:
        command.extend(["--image", str(args.image)])
        display_command.extend(["--image", _display_or_placeholder(repo_root, args.image)])
        source_kind = "static_image"
        source_path = args.image
    else:
        command.extend(["--capture-webcam", _display_path(repo_root, source_frame_path)])
        display_command.extend(["--capture-webcam", _display_path(repo_root, source_frame_path)])
        source_kind = "webcam_capture"
        source_path = source_frame_path
    shared_tail = [
        "--mode",
        args.mode,
        "--trace-out",
        _display_path(repo_root, trace_path),
        "--report-out",
        _display_path(repo_root, report_path),
        "--target",
        args.target,
        "--model",
        args.model,
    ]
    command.extend(
        [
            "--mode",
            args.mode,
            "--trace-out",
            _display_path(repo_root, trace_path),
            "--report-out",
            _display_path(repo_root, report_path),
            "--target",
            args.target,
            "--model",
            args.model,
        ]
    )
    display_command.extend(shared_tail)
    if args.degraded_on_error:
        command.append("--degraded-on-error")
        display_command.append("--degraded-on-error")

    result = _run_command(command, cwd=repo_root)
    if result.returncode not in {0, 4}:
        print(result.stderr.strip() or result.stdout.strip() or "sensor-frame proof pack failed", file=sys.stderr)
        return result.returncode

    trace_payload = json.loads(trace_path.read_text(encoding="utf-8"))
    trace = trace_from_dict(trace_payload)
    trace_summary_sha = verify_trace(trace)
    report = json.loads(report_path.read_text(encoding="utf-8"))

    image_width, image_height = image_size(source_path)
    source_sha = _sha256_file(source_path)
    source_size = source_path.stat().st_size
    captured_frame_deleted = False
    if args.capture_webcam and not args.keep_captured_frame:
        source_path.unlink()
        captured_frame_deleted = True

    relative_source_path = None
    if not captured_frame_deleted and source_path.exists():
        relative_source_path = _display_path(repo_root, source_path)

    pass_conditions = {
        "camera_gate_completed": result.returncode in {0, 4},
        "trace_matches_report_summary_sha": trace_summary_sha == report["trace_summary_sha"],
        "manifest_contains_no_secret_material": False,
        "manifest_uses_only_relative_repo_paths": True,
        "captured_frame_deleted_by_default": (not args.capture_webcam) or args.keep_captured_frame or captured_frame_deleted,
    }
    pass_conditions.update(report["pass_conditions"])
    manifest: dict[str, Any] = {
        "schema_version": PACK_SCHEMA_VERSION,
        "outcome": report["outcome"],
        "camera_gate_outcome": report["outcome"],
        "mode": args.mode,
        "model": args.model,
        "source": {
            "kind": source_kind,
            "basename": source_path.name,
            "sha256": source_sha,
            "size_bytes": source_size,
            "image_width": image_width,
            "image_height": image_height,
            "retained_local": relative_source_path is not None,
            "relative_path": relative_source_path,
        },
        "artifacts": {
            "trace": _display_path(repo_root, trace_path),
            "report": _display_path(repo_root, report_path),
        },
        "trace_summary_sha": trace_summary_sha,
        "commands": {
            "camera_gate": _shell_join(display_command),
            "verify_trace": f"python3 -m scripts.verify_trace {_display_path(repo_root, trace_path)}",
        },
        "pass_conditions": pass_conditions,
        "non_claims": [
            "no physical motion",
            "no SO-101 connectivity",
            "no safety claim",
            "no latency or reliability claim",
            "no swarm behavior",
            "no physical robot behavior",
        ],
        "notes": {
            "captured_frame_default_policy": (
                "captured webcam frames are deleted after hashing unless --keep-captured-frame is set"
            ),
            "privacy_boundary": (
                "the manifest records only basename, dimensions, sha256, and relative paths under runs/"
            ),
        },
    }
    manifest_text = canonical_json(manifest)
    pass_conditions["manifest_contains_no_secret_material"] = not _contains_secret_material(manifest_text)
    pass_conditions["manifest_uses_only_relative_repo_paths"] = str(repo_root.resolve()) not in manifest_text
    manifest["pass_conditions"] = pass_conditions
    manifest["outcome"] = _manifest_outcome(report["outcome"], pass_conditions)

    manifest_path = out_dir / "manifest.json"
    manifest_text = canonical_json(manifest)
    manifest_path.write_text(manifest_text + "\n", encoding="utf-8")

    print(f"outcome {manifest['outcome']}")
    print(f"manifest {_display_path(repo_root, manifest_path)}")
    print(f"trace {_display_path(repo_root, trace_path)}")
    print(f"report {_display_path(repo_root, report_path)}")
    if relative_source_path is not None:
        print(f"source_frame {relative_source_path}")
    else:
        print("source_frame deleted_after_hash")
    return 0 if manifest["outcome"] in {"GO", "NARROW_CLAIM", "DEGRADED"} else 4


def _run_command(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)


def _find_repo_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "AGENTS.md").exists() and (candidate / "pyproject.toml").exists():
            return candidate
    raise ValueError("could not find repository root from current working directory")


def _repo_path(repo_root: Path, candidate: Path) -> Path:
    path = (repo_root / candidate).resolve()
    try:
        path.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ValueError(f"path escapes repository root: {candidate}") from exc
    return path


def _display_path(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.name


def _display_or_placeholder(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.name


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _contains_secret_material(text: str) -> bool:
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def _manifest_outcome(camera_gate_outcome: str, pass_conditions: dict[str, bool]) -> str:
    if not all(pass_conditions.values()):
        return "NARROW_CLAIM"
    if camera_gate_outcome == "GO":
        return "GO"
    if camera_gate_outcome == "DEGRADED":
        return "DEGRADED"
    return "NARROW_CLAIM"


def _shell_join(parts: list[str]) -> str:
    return " ".join(_shell_quote(part) for part in parts)


def _shell_quote(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_./:-]+", value):
        return value
    return "'" + value.replace("'", "'\"'\"'") + "'"


if __name__ == "__main__":
    raise SystemExit(main())
