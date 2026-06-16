#!/usr/bin/env python3
"""Prepare a non-secret operator pack for a DimOS runtime smoke session."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import stat
import subprocess
import sys
from typing import Any

from accountable_swarm.trace.models import canonical_json


PACK_SCHEMA_VERSION = "dimos-runtime-smoke-pack.v1"
BRIDGE_SCHEMA_VERSION = "dimos-bridge-pack-report.v1"
DEFAULT_OUT_DIR = Path("runs/dimos/runtime-smoke-pack")
DEFAULT_BRIDGE_PACK = Path("runs/dimos/bridge-pack")
DEFAULT_DIMOS_CHECKOUT_HINT = "../dimos"
DIMOS_REPO_URL = "https://github.com/dimensionalOS/dimos"
SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"Authorization:[ \t]*Bearer[ \t]+(?!<redacted>)\S+", re.IGNORECASE),
    re.compile(r"ALIBABA_API_KEY[ \t]*=[ \t]*\S+", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9._-]{6,}"),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--bridge-pack", type=Path, default=DEFAULT_BRIDGE_PACK)
    parser.add_argument("--dimos-checkout-hint", default=DEFAULT_DIMOS_CHECKOUT_HINT)
    parser.add_argument("--commit", default=None)
    args = parser.parse_args()

    if _has_control_chars(args.dimos_checkout_hint):
        print("dimos checkout hint must not contain control characters", file=sys.stderr)
        return 2

    try:
        repo_root = _find_repo_root(Path.cwd())
        out_dir = _repo_path(repo_root, args.out_dir)
        bridge_pack = _repo_path(repo_root, args.bridge_pack)
        bridge_manifest = _read_bridge_manifest(repo_root=repo_root, bridge_pack=bridge_pack)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"dimos runtime smoke pack failed: {exc}", file=sys.stderr)
        return 2

    commit = args.commit or _git_head(repo_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "runbook": out_dir / "README.md",
        "commands": out_dir / "operator_commands.sh",
        "manifest": out_dir / "manifest.json",
    }

    runbook = _render_runbook(
        repo_root=repo_root,
        files=files,
        bridge_pack=bridge_pack,
        bridge_manifest=bridge_manifest,
        dimos_checkout_hint=args.dimos_checkout_hint,
        commit=commit,
    )
    commands = _render_commands(
        bridge_pack=_display_path(repo_root, bridge_pack),
        dimos_checkout_hint=args.dimos_checkout_hint,
    )
    generated_text = "\n".join([runbook, commands])
    if _contains_secret_material(generated_text):
        print("generated DimOS runtime smoke pack would contain secret material; aborting", file=sys.stderr)
        return 2

    files["runbook"].write_text(runbook, encoding="utf-8")
    files["commands"].write_text(commands, encoding="utf-8")
    files["commands"].chmod(files["commands"].stat().st_mode | stat.S_IXUSR)

    pass_conditions = {
        "runbook_written": files["runbook"].is_file(),
        "commands_script_written": files["commands"].is_file(),
        "bridge_pack_schema_valid": bridge_manifest.get("schema_version") == BRIDGE_SCHEMA_VERSION,
        "bridge_pack_outcome_go": bridge_manifest.get("bridge_outcome") == "GO",
        "bridge_paths_are_repo_relative": True,
        "generated_paths_are_repo_relative": str(repo_root.resolve()) not in generated_text,
        "generated_text_contains_no_secret_material": not _contains_secret_material(generated_text),
    }
    manifest: dict[str, Any] = {
        "schema_version": PACK_SCHEMA_VERSION,
        "outcome": "PENDING",
        "deployed_commit": commit,
        "bridge_pack": _display_path(repo_root, bridge_pack),
        "bridge_manifest": {
            "scenario_count": _require_int(bridge_manifest, "scenario_count"),
            "scenarios": bridge_manifest["scenarios"],
            "event_count": _require_int(bridge_manifest, "event_count"),
            "agent_count": _require_int(bridge_manifest, "agent_count"),
        },
        "dimos_checkout_hint": args.dimos_checkout_hint,
        "files": {name: _display_path(repo_root, path) for name, path in files.items()},
        "operator_steps_required": [
            "Ensure uv is installed on the operator machine",
            "Set DIMOS_CHECKOUT to a local DimOS checkout or use the reviewed hint",
            "Run uv sync inside the DimOS checkout",
            "Run the replay consumer precheck against the verified bridge pack",
            "Run collect-dimos-runtime-smoke-report and inspect the resulting report",
            "Treat only outcome GO as DimOS runtime smoke success",
        ],
        "references": {
            "dimos_repo": DIMOS_REPO_URL,
            "local_dimos_guide": "docs/engineering/dimos-runtime-smoke-pack-2026-06-17.md",
        },
        "pass_conditions": pass_conditions,
        "non_claims": [
            "no DimOS swarm control claim",
            "no DimOS 3D simulation claim",
            "no Rerun recording proof",
            "no physical robot behavior",
            "no SO-101 operation",
            "no latency or reliability claim",
        ],
    }
    pass_conditions["manifest_contains_no_secret_material"] = not _contains_secret_material(canonical_json(manifest))
    manifest["outcome"] = "GO" if all(pass_conditions.values()) else "NARROW_CLAIM"
    files["manifest"].write_text(canonical_json(manifest) + "\n", encoding="utf-8")

    print(f"outcome {manifest['outcome']}")
    print(f"manifest {_display_path(repo_root, files['manifest'])}")
    print(f"runbook {_display_path(repo_root, files['runbook'])}")
    print(f"commands {_display_path(repo_root, files['commands'])}")
    return 0 if manifest["outcome"] == "GO" else 4


def _render_runbook(
    *,
    repo_root: Path,
    files: dict[str, Path],
    bridge_pack: Path,
    bridge_manifest: dict[str, Any],
    dimos_checkout_hint: str,
    commit: str,
) -> str:
    return "\n".join(
        [
            "# DimOS Runtime Smoke Pack",
            "",
            "This pack is for a claim-safe operator-run attempt to bring up a local",
            "DimOS environment against the verified Accountable Swarm replay export.",
            "It does not prove DimOS swarm control or 3D simulation by itself.",
            "",
            "## Pinned Inputs",
            "",
            f"- Accountable Swarm commit: `{commit}`",
            f"- Verified bridge pack: `{_display_path(repo_root, bridge_pack)}`",
            f"- Bridge scenarios: `{', '.join(bridge_manifest['scenarios'])}`",
            f"- Bridge event count: `{bridge_manifest['event_count']}`",
            f"- Reviewed DimOS checkout hint: `{dimos_checkout_hint}`",
            "",
            "## Files",
            "",
            f"- Runbook: `{_display_path(repo_root, files['runbook'])}`",
            f"- Commands: `{_display_path(repo_root, files['commands'])}`",
            f"- Manifest: `{_display_path(repo_root, files['manifest'])}`",
            "",
            "## Operator Steps",
            "",
            "1. Confirm a local DimOS checkout is available.",
            "2. Set `DIMOS_CHECKOUT` if it differs from the reviewed hint.",
            "3. Run `operator_commands.sh` from the Accountable Swarm repository root.",
            "4. Inspect `runs/dimos/runtime-smoke-precheck.json` and",
            "   `runs/dimos/runtime-smoke-report.json`.",
            "5. Treat only `\"outcome\":\"GO\"` in the runtime smoke report as a",
            "   successful smoke result.",
            "",
            "## Non-Claims",
            "",
            "- This pack does not prove DimOS controlled the swarm.",
            "- This pack does not prove Rerun recorded the replay.",
            "- This pack does not prove a physical robot path, SO-101 path, or latency claim.",
            "",
        ]
    )


def _render_commands(*, bridge_pack: str, dimos_checkout_hint: str) -> str:
    quoted_hint = _shell_quote(dimos_checkout_hint)
    return "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            "",
            'if [ ! -f "AGENTS.md" ] || [ ! -f "pyproject.toml" ]; then',
            '  echo "run this command from the accountable-swarm repository root" >&2',
            "  exit 2",
            "fi",
            "",
            'if ! command -v uv >/dev/null 2>&1; then',
            '  echo "uv is required for the DimOS runtime smoke path" >&2',
            "  exit 2",
            "fi",
            "",
            'DIMOS_CHECKOUT="${DIMOS_CHECKOUT:-' + quoted_hint + '}"',
            'if [ ! -d "${DIMOS_CHECKOUT}" ]; then',
            '  echo "DimOS checkout not found: ${DIMOS_CHECKOUT}" >&2',
            "  exit 2",
            "fi",
            "",
            'echo "syncing reviewed DimOS environment at ${DIMOS_CHECKOUT}"',
            '(cd "${DIMOS_CHECKOUT}" && uv sync --frozen)',
            "",
            "mkdir -p runs/dimos",
            "python3 -m scripts.run_dimos_replay_consumer \\",
            f"  --bridge-pack {bridge_pack} \\",
            '  --dimos-checkout "${DIMOS_CHECKOUT}" \\',
            "  --report-out runs/dimos/runtime-smoke-precheck.json",
            "",
            "python3 -m scripts.collect_dimos_runtime_smoke_report \\",
            f"  --bridge-pack {bridge_pack} \\",
            '  --dimos-checkout "${DIMOS_CHECKOUT}" \\',
            "  --report-out runs/dimos/runtime-smoke-report.json",
            "",
            "python3 -m json.tool runs/dimos/runtime-smoke-report.json",
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
        raise ValueError(f"path escapes repository root: {candidate}") from exc
    return path


def _display_path(repo_root: Path, path: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def _read_bridge_manifest(*, repo_root: Path, bridge_pack: Path) -> dict[str, Any]:
    manifest_path = bridge_pack / "manifest.json"
    timeline_path = bridge_pack / "timeline.ndjson"
    if not manifest_path.is_file():
        raise ValueError("bridge pack manifest.json is required")
    if not timeline_path.is_file():
        raise ValueError("bridge pack timeline.ndjson is required")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != BRIDGE_SCHEMA_VERSION:
        raise ValueError("bridge pack manifest uses an unsupported schema")
    if manifest.get("bridge_outcome") != "GO":
        raise ValueError("bridge pack must have bridge_outcome GO")
    artifacts = _require_dict(manifest, "artifacts")
    expected_manifest = _display_path(repo_root, manifest_path)
    expected_timeline = _display_path(repo_root, timeline_path)
    if artifacts.get("manifest") != expected_manifest:
        raise ValueError("bridge pack manifest artifact path mismatch")
    if artifacts.get("timeline_ndjson") != expected_timeline:
        raise ValueError("bridge pack timeline artifact path mismatch")
    return manifest


def _require_dict(payload: dict[str, Any], field: str) -> dict[str, Any]:
    value = payload.get(field)
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return value


def _require_int(payload: dict[str, Any], field: str) -> int:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    return value


def _git_head(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(result.stderr.strip() or "failed to read git HEAD")
    return result.stdout.strip()


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
