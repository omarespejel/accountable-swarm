#!/usr/bin/env python3
"""Prepare a reproducible local recording pack for the judge demo."""

from __future__ import annotations

import argparse
import errno
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from accountable_swarm.trace.models import canonical_json


RECORDING_PACK_SCHEMA_VERSION = "demo-recording-pack-report.v1"
DEFAULT_OUT_DIR = Path("runs/demo/recording-pack")
DEFAULT_BUNDLE_DIR = Path("runs/demo/swarm")
DEFAULT_HAZARD_TRACE_DIR = Path("runs/hazard_formation/recording_x")
DEFAULT_HAZARD_REPORT = Path("runs/hazard_formation/recording_x_report.json")
DEFAULT_HAZARD_REPLAY_DIR = Path("runs/hazard_formation/recording_x_replay")
DEFAULT_HAZARD_IMAGE = Path("fixtures/hazard_marker.ppm")
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_COMMAND_TIMEOUT_SECONDS = 300
SUBPROCESS_SPAWN_ATTEMPTS = 5
SUBPROCESS_SPAWN_RETRY_DELAY_SECONDS = 0.5
SECRET_REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(Authorization:\s*Bearer\s+)(?!<redacted>)\S+", re.IGNORECASE), r"\1<redacted>"),
    (re.compile(r"(ALIBABA_API_KEY\s*=\s*)(?!<redacted>)\S+", re.IGNORECASE), r"\1<redacted>"),
    (re.compile(r"sk-[A-Za-z0-9._-]{6,}"), "<redacted>"),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--bundle-dir", type=Path, default=DEFAULT_BUNDLE_DIR)
    parser.add_argument("--hazard-image", type=Path, default=DEFAULT_HAZARD_IMAGE)
    parser.add_argument("--hazard-trace-dir", type=Path, default=DEFAULT_HAZARD_TRACE_DIR)
    parser.add_argument("--hazard-report", type=Path, default=DEFAULT_HAZARD_REPORT)
    parser.add_argument("--hazard-replay-dir", type=Path, default=DEFAULT_HAZARD_REPLAY_DIR)
    parser.add_argument("--hazard-mode", choices=["fixture", "dashscope", "degraded"], default="fixture")
    parser.add_argument("--hazard-model", default="qwen3-vl-flash")
    parser.add_argument("--formation", choices=["surround", "x", "line", "diamond"], default="x")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    try:
        repo_root = _find_repo_root(Path.cwd())
    except ValueError as exc:
        print(f"demo recording pack failed: {exc}", file=sys.stderr)
        return 2
    out_dir = _repo_path(repo_root, args.out_dir)
    bundle_dir = _repo_path(repo_root, args.bundle_dir)
    hazard_trace_dir = _repo_path(repo_root, args.hazard_trace_dir)
    hazard_report_path = _repo_path(repo_root, args.hazard_report)
    hazard_replay_dir = _repo_path(repo_root, args.hazard_replay_dir)
    hazard_image = _repo_path(repo_root, args.hazard_image)

    commands = []
    bundle_command = [
        sys.executable,
        "scripts/build_swarm_demo_bundle.py",
        "--out-dir",
        _display_path(repo_root, bundle_dir),
    ]
    hazard_command = [
        sys.executable,
        "-m",
        "scripts.run_hazard_formation_gate",
        "--image",
        _display_path(repo_root, hazard_image),
        "--mode",
        args.hazard_mode,
        "--model",
        args.hazard_model,
        "--formation",
        args.formation,
        "--trace-dir",
        _display_path(repo_root, hazard_trace_dir),
        "--report-out",
        _display_path(repo_root, hazard_report_path),
    ]

    bundle_result = _run_command(bundle_command, cwd=repo_root)
    commands.append(_command_report("build_swarm_demo_bundle", bundle_command, bundle_result))
    hazard_result = _run_command(hazard_command, cwd=repo_root)
    commands.append(_command_report("run_hazard_formation_gate", hazard_command, hazard_result))

    bundle_summary_path = bundle_dir / "summary.json"
    hazard_report = _load_json_if_exists(hazard_report_path)
    bundle_summary = _load_json_if_exists(bundle_summary_path)
    hazard_replay_html = hazard_replay_dir / "index.html"
    hazard_replay_summary_path = hazard_replay_dir / "summary.json"
    hazard_replay_command = _hazard_replay_command(
        repo_root=repo_root,
        hazard_trace_dir=hazard_trace_dir,
        hazard_report=hazard_report,
        hazard_replay_html=hazard_replay_html,
        hazard_replay_summary_path=hazard_replay_summary_path,
    )
    hazard_replay_result = _run_command(hazard_replay_command, cwd=repo_root)
    commands.append(_command_report("render_hazard_formation_replay", hazard_replay_command, hazard_replay_result))
    hazard_replay_summary = _load_json_if_exists(hazard_replay_summary_path)
    pass_conditions = {
        "bundle_command_succeeded": bundle_result.returncode == 0,
        "bundle_summary_go": bundle_summary.get("outcome") == "GO",
        "bundle_index_exists": (bundle_dir / "index.html").is_file(),
        "hazard_command_succeeded": hazard_result.returncode == 0,
        "hazard_report_exists": hazard_report_path.is_file(),
        "hazard_report_accepted_outcome": hazard_report.get("outcome") in {"GO", "DEGRADED"},
        "hazard_trace_exists": (hazard_trace_dir / "hazard.json").is_file(),
        "hazard_replay_command_succeeded": hazard_replay_result.returncode == 0,
        "hazard_replay_html_exists": hazard_replay_html.is_file(),
        "hazard_replay_summary_go": hazard_replay_summary.get("outcome") == "GO",
    }
    manifest = {
        "schema_version": RECORDING_PACK_SCHEMA_VERSION,
        "outcome": "PENDING",
        "commands": commands,
        "key_material_redacted_count": sum(
            command["key_material_redacted_count"] for command in commands
        ),
        "artifacts": {
            "bundle_index": _display_path(repo_root, bundle_dir / "index.html"),
            "bundle_summary": _display_path(repo_root, bundle_summary_path),
            "hazard_report": _display_path(repo_root, hazard_report_path),
            "hazard_trace": _display_path(repo_root, hazard_trace_dir / "hazard.json"),
            "hazard_replay_html": _display_path(repo_root, hazard_replay_html),
            "hazard_replay_summary": _display_path(repo_root, hazard_replay_summary_path),
        },
        "serve": {
            "command": f"python3 scripts/serve_demo.py --host {args.host} --port {args.port}",
            "urls": [
                f"http://{args.host}:{args.port}/healthz",
                f"http://{args.host}:{args.port}/readyz",
                f"http://{args.host}:{args.port}/swarm-demo",
                f"http://{args.host}:{args.port}/swarm-demo/summary.json",
                f"http://{args.host}:{args.port}/hazard-formation",
                f"http://{args.host}:{args.port}/hazard-formation/summary.json",
            ],
        },
        "recording_shotlist": [
            "Show repository root, LICENSE, README, and docs/submission/README.md.",
            "Show this recording manifest and the GO/NARROW_CLAIM outcome.",
            "Open the animated swarm replay from runs/demo/swarm/index.html.",
            "Open one replay scenario and show the moving agents plus static trace frames.",
            "Open the hazard-formation replay and show the bbox-derived hazard cell as the obstacle.",
            "Show the hazard-to-formation report with bbox, hazard cell, X formation, and trace hashes.",
            "State the boundary: Qwen keyframe perception or low-rate intent, deterministic local motion, hash-verifiable traces.",
            "State non-claims in frame: no DimOS, no physical SO-101, no 3D physics, no Qwen real-time control, no completed ECS proof unless separately recorded.",
        ],
        "pass_conditions": pass_conditions,
        "non_claims": [
            "no physical robot behavior",
            "no SO-101 operation",
            "no 3D physics simulation",
            "no DimOS integration",
            "no Qwen real-time control",
            "no Qwen onboard execution",
            "no Alibaba ECS deployment proof unless a separate ECS evidence doc exists",
            "no latency or reliability claim",
        ],
    }
    pass_conditions["manifest_contains_no_key_material"] = not _contains_secret_material(
        canonical_json(manifest)
    )
    outcome = "GO" if all(pass_conditions.values()) else "NARROW_CLAIM"
    manifest["outcome"] = outcome

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"
    shotlist_path = out_dir / "shotlist.md"
    manifest_path.write_text(canonical_json(manifest) + "\n", encoding="utf-8")
    shotlist_path.write_text(_render_shotlist(manifest), encoding="utf-8")

    print(f"outcome {outcome}")
    print(f"manifest {_display_path(repo_root, manifest_path)}")
    print(f"shotlist {_display_path(repo_root, shotlist_path)}")
    print(f"bundle_index {_display_path(repo_root, bundle_dir / 'index.html')}")
    print(f"hazard_report {_display_path(repo_root, hazard_report_path)}")
    print(f"hazard_replay {_display_path(repo_root, hazard_replay_html)}")
    return 0 if outcome == "GO" else 4


def _run_command(
    args: list[str],
    *,
    cwd: Path,
    timeout_seconds: int = DEFAULT_COMMAND_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    try:
        for attempt in range(SUBPROCESS_SPAWN_ATTEMPTS):
            try:
                return subprocess.run(
                    args,
                    cwd=cwd,
                    text=True,
                    capture_output=True,
                    check=False,
                    timeout=timeout_seconds,
                )
            except OSError as exc:
                if not _is_retryable_spawn_error(exc) or attempt + 1 >= SUBPROCESS_SPAWN_ATTEMPTS:
                    return subprocess.CompletedProcess(
                        args=args,
                        returncode=125,
                        stdout="",
                        stderr=f"spawn failed: {exc}",
                    )
                time.sleep(SUBPROCESS_SPAWN_RETRY_DELAY_SECONDS)
    except subprocess.TimeoutExpired as exc:
        stderr = _coerce_output_text(exc.stderr)
        timeout_message = f"command timed out after {timeout_seconds}s"
        return subprocess.CompletedProcess(
            args=args,
            returncode=124,
            stdout=_coerce_output_text(exc.stdout),
            stderr=f"{stderr}\n{timeout_message}".strip(),
        )
    raise RuntimeError("unreachable child command retry state")


def _is_retryable_spawn_error(exc: OSError) -> bool:
    return isinstance(exc, BlockingIOError) or exc.errno == errno.EAGAIN


def _command_report(
    label: str,
    args: list[str],
    result: subprocess.CompletedProcess[str],
) -> dict[str, Any]:
    argv, argv_count = _redact_values(args)
    stdout_tail, stdout_count = _safe_tail(result.stdout)
    stderr_tail, stderr_count = _safe_tail(result.stderr)
    return {
        "label": label,
        "argv": argv,
        "returncode": result.returncode,
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
        "key_material_redacted_count": argv_count + stdout_count + stderr_count,
    }


def _hazard_replay_command(
    *,
    repo_root: Path,
    hazard_trace_dir: Path,
    hazard_report: dict[str, Any],
    hazard_replay_html: Path,
    hazard_replay_summary_path: Path,
) -> list[str]:
    grid = hazard_report.get("grid")
    grid_width = _plain_int_or_default(grid.get("width") if isinstance(grid, dict) else None, 7)
    grid_height = _plain_int_or_default(grid.get("height") if isinstance(grid, dict) else None, 5)
    command = [
        sys.executable,
        "scripts/render_swarm_trace_html.py",
        "--trace-dir",
        _display_path(repo_root, hazard_trace_dir / "agents"),
        "--grid-width",
        str(grid_width),
        "--grid-height",
        str(grid_height),
        "--title",
        "Accountable Swarm Hazard Formation Replay",
        "--html-out",
        _display_path(repo_root, hazard_replay_html),
        "--summary-out",
        _display_path(repo_root, hazard_replay_summary_path),
    ]
    hazard_cell = _hazard_cell_from_report(hazard_report)
    if hazard_cell is not None:
        command.extend(["--obstacle", f"{hazard_cell[0]},{hazard_cell[1]}"])
    return command


def _plain_int_or_default(value: object, default: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return default
    return value


def _hazard_cell_from_report(report: dict[str, Any]) -> tuple[int, int] | None:
    hazard = report.get("hazard")
    if not isinstance(hazard, dict):
        return None
    cell = hazard.get("cell")
    if not isinstance(cell, dict):
        return None
    x = cell.get("x")
    y = cell.get("y")
    if isinstance(x, bool) or isinstance(y, bool) or not isinstance(x, int) or not isinstance(y, int):
        return None
    return (x, y)


def _safe_tail(text: str, *, max_lines: int = 12) -> tuple[list[str], int]:
    return _redact_values(text.splitlines()[-max_lines:])


def _redact_values(values: list[str]) -> tuple[list[str], int]:
    redacted = []
    count = 0
    for value in values:
        scrubbed, scrubbed_count = _redact_text(value)
        redacted.append(scrubbed)
        count += scrubbed_count
    return redacted, count


def _redact_text(value: str) -> tuple[str, int]:
    result = value
    count = 0
    for pattern, replacement in SECRET_REDACTIONS:
        result, replacements = pattern.subn(replacement, result)
        count += replacements
    return result, count


def _contains_secret_material(value: str) -> bool:
    return any(pattern.search(value) for pattern, _replacement in SECRET_REDACTIONS)


def _load_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _coerce_output_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (
            (candidate / "pyproject.toml").is_file()
            and (candidate / "scripts" / "prepare_demo_recording_pack.py").is_file()
            and (candidate / "fixtures" / "hazard_marker.ppm").is_file()
        ):
            return candidate
    raise ValueError(
        "run from an accountable-swarm checkout containing pyproject.toml and fixtures/hazard_marker.ppm"
    )


def _repo_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _display_path(repo_root: Path, path: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def _render_shotlist(manifest: dict[str, Any]) -> str:
    lines = [
        "# Accountable Swarm Demo Recording Shot List",
        "",
        f"Outcome: `{manifest['outcome']}`",
        "",
        "## Commands",
        "",
    ]
    for command in manifest["commands"]:
        lines.extend(
            [
                f"### {command['label']}",
                "",
                "```text",
                " ".join(command["argv"]),
                "```",
                "",
                f"Return code: `{command['returncode']}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Artifacts",
            "",
        ]
    )
    for label, path in manifest["artifacts"].items():
        lines.append(f"- `{label}`: `{path}`")
    lines.extend(
        [
            "",
            "## Serve Command",
            "",
            "```text",
            manifest["serve"]["command"],
            "```",
            "",
            "## Recording Beats",
            "",
        ]
    )
    for item in manifest["recording_shotlist"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Non-Claims",
            "",
        ]
    )
    for item in manifest["non_claims"]:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
