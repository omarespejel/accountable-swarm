#!/usr/bin/env python3
"""Prepare a non-secret operator pack for the SO-101 camera probe lane."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import stat
import subprocess
import sys
from typing import Any

from accountable_swarm.trace.models import canonical_json


PACK_SCHEMA_VERSION = "so101-operator-probe-pack.v1"
DEFAULT_OUT_DIR = Path("runs/physical/so101-operator-pack")
DEFAULT_CAMERA_NAME = "so101_overhead"
DEFAULT_CAMERA_ID = "0"
DOC_INSTALL_URL = "https://huggingface.co/docs/lerobot/installation"
DOC_CAMERAS_URL = "https://huggingface.co/docs/lerobot/en/cameras"
DOC_SO101_URL = "https://huggingface.co/docs/lerobot/so101"
SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"Authorization:[ \t]*Bearer[ \t]+(?!<redacted>)\S+", re.IGNORECASE),
    re.compile(r"ALIBABA_API_KEY[ \t]*=[ \t]*\S+", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9._-]{6,}"),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--camera-name", default=DEFAULT_CAMERA_NAME)
    parser.add_argument("--camera-id", default=DEFAULT_CAMERA_ID)
    args = parser.parse_args()

    if _has_control_chars(args.camera_name) or _has_control_chars(args.camera_id):
        print("camera values must not contain control characters", file=sys.stderr)
        return 2

    try:
        repo_root = _find_repo_root(Path.cwd())
        out_dir = _repo_path(repo_root, args.out_dir)
    except ValueError as exc:
        print(f"so101 operator pack failed: {exc}", file=sys.stderr)
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "runbook": out_dir / "README.md",
        "commands": out_dir / "operator_commands.sh",
        "manifest": out_dir / "manifest.json",
    }

    runbook = _render_runbook(repo_root=repo_root, files=files, camera_name=args.camera_name, camera_id=args.camera_id)
    commands = _render_commands(camera_name=args.camera_name, camera_id=args.camera_id)
    generated_text = "\n".join([runbook, commands])
    if _contains_secret_material(generated_text):
        print("generated SO-101 operator pack would contain secret material; aborting", file=sys.stderr)
        return 2

    files["runbook"].write_text(runbook, encoding="utf-8")
    files["commands"].write_text(commands, encoding="utf-8")
    files["commands"].chmod(files["commands"].stat().st_mode | stat.S_IXUSR)

    pass_conditions = {
        "runbook_written": files["runbook"].is_file(),
        "commands_script_written": files["commands"].is_file(),
        "manifest_contains_no_secret_material": False,
        "output_paths_are_repo_relative": True,
    }
    manifest: dict[str, Any] = {
        "schema_version": PACK_SCHEMA_VERSION,
        "outcome": "GO",
        "camera_name": args.camera_name,
        "camera_id": args.camera_id,
        "files": {name: _display_path(repo_root, path) for name, path in files.items()},
        "official_docs": {
            "installation": DOC_INSTALL_URL,
            "cameras": DOC_CAMERAS_URL,
            "so101": DOC_SO101_URL,
        },
        "operator_steps_required": [
            "Create or activate a Python 3.12 environment",
            "Install lerobot and the feetech extra",
            "Install opencv-python",
            "Run lerobot-find-cameras opencv",
            "Run capture-so101-camera-frame with the detected camera id",
            "Keep the path trace-only; do not enable motion",
        ],
        "non_claims": [
            "not SO-101 connectivity proof",
            "not SO-101 camera success until operator run completes",
            "not autonomous motion",
            "not ACT policy success",
            "not safety, latency, or reliability proof",
        ],
        "pass_conditions": pass_conditions,
    }
    manifest_text = canonical_json(manifest)
    pass_conditions["manifest_contains_no_secret_material"] = not _contains_secret_material(manifest_text)
    pass_conditions["output_paths_are_repo_relative"] = str(repo_root.resolve()) not in manifest_text
    manifest["outcome"] = "GO" if all(pass_conditions.values()) else "NARROW_CLAIM"
    files["manifest"].write_text(canonical_json(manifest) + "\n", encoding="utf-8")

    print(f"outcome {manifest['outcome']}")
    print(f"manifest {_display_path(repo_root, files['manifest'])}")
    print(f"runbook {_display_path(repo_root, files['runbook'])}")
    print(f"commands {_display_path(repo_root, files['commands'])}")
    return 0 if manifest["outcome"] == "GO" else 4


def _render_runbook(*, repo_root: Path, files: dict[str, Path], camera_name: str, camera_id: str) -> str:
    return "\n".join(
        [
            "# SO-101 Operator Probe Pack",
            "",
            "This pack is for the operator who has the SO-101 hardware and needs",
            "to run the trace-only camera probe without widening the motion boundary.",
            "",
            "## Official References",
            "",
            f"- Installation: {DOC_INSTALL_URL}",
            f"- Cameras: {DOC_CAMERAS_URL}",
            f"- SO-101: {DOC_SO101_URL}",
            "",
            "## Files",
            "",
            f"- Runbook: `{_display_path(repo_root, files['runbook'])}`",
            f"- Commands: `{_display_path(repo_root, files['commands'])}`",
            f"- Manifest: `{_display_path(repo_root, files['manifest'])}`",
            "",
            "## Intended Defaults",
            "",
            f"- Camera name: `{camera_name}`",
            f"- Initial camera id guess: `{camera_id}`",
            "- Motion boundary: trace-only",
            "",
            "## Operator Steps",
            "",
            "1. Create or activate a Python 3.12 environment.",
            "2. Install LeRobot from PyPI or source.",
            "3. Install the Feetech extra for SO-101 motor support.",
            "4. Install `opencv-python` for the OpenCV camera path.",
            "5. Run `lerobot-find-cameras opencv` and identify the correct camera id.",
            "6. Run `operator_commands.sh` from the repository root.",
            "7. Review `runs/physical/so101_capture_report.json` and only treat `GO` as camera success.",
            "",
            "## Non-Claims",
            "",
            "- This pack does not prove SO-101 connectivity by itself.",
            "- This pack does not authorize motion.",
            "- This pack does not prove ACT policy success or safety.",
            "",
        ]
    )


def _render_commands(*, camera_name: str, camera_id: str) -> str:
    q_name = _shell_quote(camera_name)
    q_id = _shell_quote(camera_id)
    return "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            "",
            'if ! command -v python3 >/dev/null 2>&1; then',
            '  echo "python3 is required" >&2',
            "  exit 2",
            "fi",
            "",
            'cat <<\'EOINFO\'',
            "If you are following the official LeRobot path, use a Python 3.12 environment.",
            "Official docs:",
            f"- {DOC_INSTALL_URL}",
            f"- {DOC_CAMERAS_URL}",
            f"- {DOC_SO101_URL}",
            "EOINFO",
            "",
            "python3 -m pip install --upgrade pip",
            "python3 -m pip install lerobot",
            "python3 -m pip install 'lerobot[feetech]'",
            "python3 -m pip install opencv-python",
            "",
            "echo 'Discover available OpenCV cameras:'",
            "lerobot-find-cameras opencv || true",
            "",
            "mkdir -p runs/physical",
            "python3 -m scripts.capture_so101_camera_frame \\",
            f"  --camera-name {q_name} \\",
            f"  --index-or-path {q_id} \\",
            "  --out runs/physical/so101_frame.png \\",
            "  --report-out runs/physical/so101_capture_report.json",
            "",
            "python3 -m json.tool runs/physical/so101_capture_report.json",
        ]
    )


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
        raise ValueError("output paths must stay inside the repository checkout") from exc
    return path


def _display_path(repo_root: Path, path: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def _contains_secret_material(text: str) -> bool:
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def _shell_quote(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_./:-]+", value):
        return value
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _has_control_chars(value: str) -> bool:
    return any(ord(ch) < 32 for ch in value)


if __name__ == "__main__":
    raise SystemExit(main())
