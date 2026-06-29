#!/usr/bin/env python3
"""Prepare one non-secret operator pack for the final QwenGuard readiness gates."""

from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import re
import shlex
import stat
import subprocess
import sys
from typing import Any

from accountable_swarm.trace.models import canonical_json


PACK_SCHEMA_VERSION = "qwenguard-readiness-operator-pack.v1"
DEFAULT_OUT_DIR = Path("runs/submission/qwenguard-readiness-operator-pack")
DEFAULT_TASK = "pick the red cube left of the green cube and place it in the bin"
DEFAULT_CAMERA_NAME = "so101_overhead"
DEFAULT_CAMERA_ID = "0"
DEFAULT_VIDEO_ARTIFACT = "runs/submission/qwenguard-final-demo.mp4"
DEFAULT_REPO_URL = "https://github.com/omarespejel/accountable-swarm"
ISSUE_URL = "https://github.com/omarespejel/accountable-swarm/issues/106"
ECS_ISSUE_URL = "https://github.com/omarespejel/accountable-swarm/issues/91"

SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"Authorization:[ \t]*Bearer[ \t]+(?!<redacted>(?:$|[ \t]))\S+", re.IGNORECASE),
    re.compile(r"ALIBABA_API_KEY[ \t]*=[ \t]*\S+", re.IGNORECASE),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"gh(?:p|o|u|s|r)_[A-Za-z0-9_]{12,}"),
    re.compile(r"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9._-]{20,}"),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--task", default=DEFAULT_TASK)
    parser.add_argument("--camera-name", default=DEFAULT_CAMERA_NAME)
    parser.add_argument("--camera-id", default=DEFAULT_CAMERA_ID)
    parser.add_argument("--video-artifact", default=DEFAULT_VIDEO_ARTIFACT)
    parser.add_argument("--repo-url", default=DEFAULT_REPO_URL)
    parser.add_argument("--commit", default=None)
    args = parser.parse_args()

    for name, value in {
        "out-dir": str(args.out_dir),
        "task": args.task,
        "camera-name": args.camera_name,
        "camera-id": args.camera_id,
        "video-artifact": args.video_artifact,
        "repo-url": args.repo_url,
        "commit": args.commit or "",
    }.items():
        if _has_control_chars(value):
            print(f"{name} must not contain control characters", file=sys.stderr)
            return 2
        if _contains_secret_material(value):
            print(f"{name} must not contain secret-like material", file=sys.stderr)
            return 2

    try:
        repo_root = _find_repo_root(Path.cwd())
        out_dir = _repo_path(repo_root, args.out_dir)
    except ValueError as exc:
        print(f"qwenguard readiness operator pack failed: {exc}", file=sys.stderr)
        return 2

    try:
        commit = _resolve_commit(repo_root, args.commit)
    except ValueError as exc:
        print(f"qwenguard readiness operator pack failed: {exc}", file=sys.stderr)
        return 2
    files = {
        "runbook": out_dir / "README.md",
        "commands": out_dir / "operator_commands.sh",
        "manifest": out_dir / "manifest.json",
    }

    runbook = _render_runbook(
        repo_root=repo_root,
        files=files,
        task=args.task,
        camera_name=args.camera_name,
        camera_id=args.camera_id,
        video_artifact=args.video_artifact,
        repo_url=args.repo_url,
        commit=commit,
    )
    commands = _render_commands(
        task=args.task,
        camera_name=args.camera_name,
        camera_id=args.camera_id,
        video_artifact=args.video_artifact,
        repo_url=args.repo_url,
        commit=commit,
    )
    generated_text = "\n".join([runbook, commands])
    if _contains_secret_material(generated_text):
        print("generated QwenGuard readiness operator pack would contain secret material; aborting", file=sys.stderr)
        return 2

    pass_conditions = {
        "deployed_commit_is_git_oid": _is_git_oid(commit),
        "runbook_rendered": bool(runbook.strip()),
        "commands_script_rendered": bool(commands.strip()),
        "commands_bash_syntax_valid": _bash_syntax_text_ok(commands),
        "generated_text_contains_no_secret_material": not _contains_secret_material(generated_text),
        "output_paths_are_repo_relative": True,
        "readiness_is_not_overclaimed": True,
    }
    manifest: dict[str, Any] = {
        "schema_version": PACK_SCHEMA_VERSION,
        "outcome": "GO",
        "submission_readiness": "NARROW_CLAIM",
        "issue": ISSUE_URL,
        "ecs_issue": ECS_ISSUE_URL,
        "repo_url": args.repo_url,
        "commit": commit,
        "task": args.task,
        "camera_name": args.camera_name,
        "camera_id": args.camera_id,
        "video_artifact": args.video_artifact,
        "files": {name: _display_path(repo_root, path) for name, path in files.items()},
        "operator_phases": [
            "bootstrap",
            "safe-software",
            "so101-camera",
            "record-success",
            "record-failure",
            "record-cloud-hold",
            "summarize-trials",
            "ecs-pack",
            "submission-pack",
            "video-review",
            "audit-narrow",
            "audit-final",
            "all-preflight",
        ],
        "remaining_go_gates": [
            "SO-101 camera report with outcome GO",
            "measured physical trial traces bound to trial_results.csv rows",
            "trial_summary.json generated from verified measured trial rows",
            "Alibaba ECS public endpoint report from issue #91",
            "human-reviewed final video note with explicit signoffs",
            "final readiness audit exits GO without --allow-narrow-claim",
        ],
        "pack_claim": (
            "operator runbook and command pack for final readiness gates; "
            "not itself SO-101, ECS, ACT, or submission-readiness evidence"
        ),
        "non_claims": [
            "not SO-101 connectivity proof",
            "not SO-101 camera success",
            "not physical trial success",
            "not ACT policy success",
            "not Alibaba ECS deployment proof",
            "not final submission readiness",
            "not Qwen motor control",
            "not Qwen onboard execution",
            "not DimOS runtime control",
            "not safety, latency, reliability, or production hosting",
        ],
        "pass_conditions": pass_conditions,
    }
    pass_conditions["manifest_contains_no_secret_material"] = not _contains_secret_material(canonical_json(manifest))
    pass_conditions["output_paths_are_repo_relative"] = _manifest_file_paths_are_repo_relative(manifest["files"])
    manifest["outcome"] = "GO" if all(pass_conditions.values()) else "NARROW_CLAIM"
    manifest_text = canonical_json(manifest)
    if _contains_secret_material(manifest_text):
        print("generated QwenGuard readiness manifest would contain secret material; aborting", file=sys.stderr)
        return 2
    if manifest["outcome"] != "GO":
        print("generated QwenGuard readiness manifest failed pass conditions; aborting", file=sys.stderr)
        return 4

    out_dir.mkdir(parents=True, exist_ok=True)
    files["runbook"].write_text(runbook, encoding="utf-8")
    files["commands"].write_text(commands, encoding="utf-8")
    files["commands"].chmod(files["commands"].stat().st_mode | stat.S_IXUSR)
    files["manifest"].write_text(manifest_text + "\n", encoding="utf-8")

    print(f"outcome {manifest['outcome']}")
    print(f"submission_readiness {manifest['submission_readiness']}")
    print(f"manifest {_display_path(repo_root, files['manifest'])}")
    print(f"runbook {_display_path(repo_root, files['runbook'])}")
    print(f"commands {_display_path(repo_root, files['commands'])}")
    return 0 if manifest["outcome"] == "GO" else 4


def _render_runbook(
    *,
    repo_root: Path,
    files: dict[str, Path],
    task: str,
    camera_name: str,
    camera_id: str,
    video_artifact: str,
    repo_url: str,
    commit: str,
) -> str:
    return "\n".join(
        [
            "# QwenGuard Final Readiness Operator Pack",
            "",
            "This pack is the final operator checklist for issue #106. It stitches",
            "together the remaining SO-101, ECS, video-review, and readiness-audit",
            "gates without creating the evidence itself.",
            "",
            "## Claim Boundary",
            "",
            "- This pack is `GO` only as command/runbook plumbing.",
            "- Submission readiness stays `NARROW_CLAIM` until the final audit",
            "  passes without `--allow-narrow-claim`.",
            "- No phase here proves SO-101 success, ACT success, ECS deployment,",
            "  Qwen motor control, Qwen onboard execution, DimOS control, safety,",
            "  latency, reliability, or production hosting.",
            "",
            "## Pinned Inputs",
            "",
            f"- Commit: `{commit}`",
            f"- Repo: {repo_url}",
            f"- Task: `{task}`",
            f"- Camera name: `{camera_name}`",
            f"- Camera id: `{camera_id}`",
            f"- Expected final video artifact: `{video_artifact}`",
            "",
            "## Files",
            "",
            f"- Runbook: `{_display_path(repo_root, files['runbook'])}`",
            f"- Commands: `{_display_path(repo_root, files['commands'])}`",
            f"- Manifest: `{_display_path(repo_root, files['manifest'])}`",
            "",
            "## Phase Order",
            "",
            "Run from the repository root:",
            "",
            "```bash",
            f"bash {_display_path(repo_root, files['commands'])} all-preflight",
            "```",
            "",
            "That phase is the locally test-covered no-camera/no-ECS-host",
            "preflight. It does not invoke camera capture or ECS proof collection;",
            "it generates the physical, ECS, and submission packs, runs the",
            "existing physical-pack `all-safe` phase, and confirms the current",
            "audit remains `NARROW_CLAIM` for missing operator evidence.",
            "",
            "When hardware is connected and supervised:",
            "",
            "```bash",
            f"bash {_display_path(repo_root, files['commands'])} so101-camera",
            f"QWENGUARD_TRIAL_ID=trial-001 bash {_display_path(repo_root, files['commands'])} record-success",
            f"QWENGUARD_TRIAL_ID=trial-cloud-hold-001 bash {_display_path(repo_root, files['commands'])} record-cloud-hold",
            f"bash {_display_path(repo_root, files['commands'])} summarize-trials",
            "```",
            "",
            "When Alibaba ECS proof has been captured on the ECS host, copy the",
            "sanitized `runs/ecs/ecs_smoke_report.json` back into this checkout.",
            "Then create the final video review only after a human has watched the",
            "actual final cut:",
            "",
            "```bash",
            "QWENGUARD_REVIEWED_BY=\"REPLACE_WITH_HUMAN_REVIEWER\" \\",
            "QWENGUARD_REVIEW_DATE=\"2026-06-29\" \\",
            f"QWENGUARD_VIDEO_ARTIFACT={shlex.quote(video_artifact)} \\",
            f"bash {_display_path(repo_root, files['commands'])} video-review",
            f"bash {_display_path(repo_root, files['commands'])} audit-final",
            "```",
            "",
            "## Remaining GO Evidence",
            "",
            "- SO-101 camera report:",
            "  `runs/physical/qwenguard_physical_go/so101_capture_report.json`",
            "  with `outcome: GO`.",
            "- `runs/physical/qwenguard_trials/traces/*.json` verified as",
            "  `decisiontrace.v2`.",
            "- `runs/physical/qwenguard_trials/trial_results.csv` rows bound to",
            "  those trace summaries.",
            "- `runs/physical/qwenguard_trials/trial_summary.json` with measured",
            "  N/10 counts and failure taxonomy from verified trace bindings.",
            "- `runs/ecs/ecs_smoke_report.json` with `outcome: GO` and",
            "  `proof_mode: ecs-public`.",
            "- `runs/submission/final_video_review.md` with explicit privacy,",
            "  claim-boundary, mode-label, ECS, SO-101, and secrets signoffs.",
            "",
            "## Issue Links",
            "",
            f"- Final readiness: {ISSUE_URL}",
            f"- ECS public endpoint proof: {ECS_ISSUE_URL}",
            "",
        ]
    )


def _render_commands(
    *,
    task: str,
    camera_name: str,
    camera_id: str,
    video_artifact: str,
    repo_url: str,
    commit: str,
) -> str:
    q_task = shlex.quote(task)
    q_camera_name = shlex.quote(camera_name)
    q_camera_id = shlex.quote(camera_id)
    q_video_artifact = shlex.quote(video_artifact)
    q_repo_url = shlex.quote(repo_url)
    q_commit = shlex.quote(commit)
    return "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            "",
            'PHASE="${1:-help}"',
            'PACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"',
            'if [[ -z "${REPO_ROOT:-}" ]]; then',
            '  if REPO_ROOT="$(git -C "${PACK_DIR}" rev-parse --show-toplevel 2>/dev/null)"; then',
            "    :",
            "  else",
            '    echo "could not locate repository root; set REPO_ROOT or run this pack inside the git checkout" >&2',
            "    exit 2",
            "  fi",
            "fi",
            'if [[ ! -f "${REPO_ROOT}/pyproject.toml" || ! -d "${REPO_ROOT}/scripts" ]]; then',
            '  echo "REPO_ROOT does not look like the accountable-swarm checkout: ${REPO_ROOT}" >&2',
            "  exit 2",
            "fi",
            'cd "${REPO_ROOT}"',
            "",
            f"export QWENGUARD_TASK={q_task}",
            f"export QWENGUARD_CAMERA_NAME={q_camera_name}",
            f"export QWENGUARD_CAMERA_ID={q_camera_id}",
            f"export QWENGUARD_VIDEO_ARTIFACT_DEFAULT={q_video_artifact}",
            f"export QWENGUARD_REPO_URL={q_repo_url}",
            f"export QWENGUARD_COMMIT={q_commit}",
            'PHYSICAL_PACK_DIR="${QWENGUARD_PHYSICAL_PACK_DIR:-runs/physical/qwenguard-physical-go-pack}"',
            'ECS_PACK_DIR="${QWENGUARD_ECS_PACK_DIR:-runs/ecs/operator-pack}"',
            'SUBMISSION_PACK_DIR="${QWENGUARD_SUBMISSION_PACK_DIR:-runs/submission/qwenguard-pack}"',
            'READINESS_REPORT="${QWENGUARD_READINESS_REPORT:-runs/submission/qwenguard-readiness-current.json}"',
            'FINAL_VIDEO_REVIEW="${QWENGUARD_FINAL_VIDEO_REVIEW:-runs/submission/final_video_review.md}"',
            'TRIAL_CSV="${QWENGUARD_TRIAL_CSV:-runs/physical/qwenguard_trials/trial_results.csv}"',
            'TRIAL_TRACE_DIR="${QWENGUARD_TRIAL_TRACE_DIR:-runs/physical/qwenguard_trials/traces}"',
            'TRIAL_SUMMARY="${QWENGUARD_TRIAL_SUMMARY:-runs/physical/qwenguard_trials/trial_summary.json}"',
            'VIDEO_ARTIFACT="${QWENGUARD_VIDEO_ARTIFACT:-${QWENGUARD_VIDEO_ARTIFACT_DEFAULT}}"',
            "",
            "repo_relative_guard() {",
            "  case \"$1\" in /*|..|../*|*/..|*/../*) echo \"$2 must be repo-relative and must not contain ..\" >&2; exit 2 ;; esac",
            "}",
            "require_env() {",
            "  local name=\"$1\"",
            "  if [[ -z \"${!name:-}\" ]]; then",
            "    echo \"missing required environment variable: ${name}\" >&2",
            "    exit 2",
            "  fi",
            "}",
            "repo_relative_guard \"${PHYSICAL_PACK_DIR}\" QWENGUARD_PHYSICAL_PACK_DIR",
            "repo_relative_guard \"${ECS_PACK_DIR}\" QWENGUARD_ECS_PACK_DIR",
            "repo_relative_guard \"${SUBMISSION_PACK_DIR}\" QWENGUARD_SUBMISSION_PACK_DIR",
            "repo_relative_guard \"${READINESS_REPORT}\" QWENGUARD_READINESS_REPORT",
            "repo_relative_guard \"${FINAL_VIDEO_REVIEW}\" QWENGUARD_FINAL_VIDEO_REVIEW",
            "repo_relative_guard \"${TRIAL_CSV}\" QWENGUARD_TRIAL_CSV",
            "repo_relative_guard \"${TRIAL_TRACE_DIR}\" QWENGUARD_TRIAL_TRACE_DIR",
            "repo_relative_guard \"${TRIAL_SUMMARY}\" QWENGUARD_TRIAL_SUMMARY",
            "case \"${VIDEO_ARTIFACT}\" in",
            "  https://*) : ;;",
            "  *) repo_relative_guard \"${VIDEO_ARTIFACT}\" QWENGUARD_VIDEO_ARTIFACT ;;",
            "esac",
            "",
            "usage() {",
            "  cat <<'EOUSAGE'",
            "Usage: operator_commands.sh PHASE",
            "",
            "Phases:",
            "  bootstrap         Generate physical, ECS, and submission packs.",
            "  safe-software     Run fixture/degraded no-motion path through the physical pack.",
            "  so101-camera      Capture one SO-101 camera frame through trace-only probe.",
            "  record-success    Record one operator-attested successful physical trial.",
            "  record-failure    Record one operator-attested failed physical trial.",
            "  record-cloud-hold Record one degraded-cloud HOLD physical/video trial.",
            "  summarize-trials  Summarize measured trial rows into N/10 counts and taxonomy.",
            "  ecs-pack          Generate the Alibaba ECS proof pack for issue #91.",
            "  submission-pack   Generate the claim-safe submission scaffold.",
            "  video-review      Write the human final-video review note after explicit env vars.",
            "  audit-narrow      Run final readiness audit with --allow-narrow-claim.",
            "  audit-final       Run final readiness audit without --allow-narrow-claim.",
            "  all-preflight     bootstrap + safe-software + audit-narrow. No camera or ECS host.",
            "",
            "No phase in this script enters raw secrets. ECS credentials belong only",
            "on the ECS host .env created from the generated ECS operator pack.",
            "EOUSAGE",
            "}",
            "",
            "run_physical_pack() {",
            "  python3 -m scripts.prepare_qwenguard_physical_go_pack \\",
            "    --out-dir \"${PHYSICAL_PACK_DIR}\" \\",
            "    --task \"${QWENGUARD_TASK}\" \\",
            "    --camera-name \"${QWENGUARD_CAMERA_NAME}\" \\",
            "    --camera-id \"${QWENGUARD_CAMERA_ID}\"",
            "}",
            "run_ecs_pack() {",
            "  python3 -m scripts.prepare_ecs_operator_pack \\",
            "    --out-dir \"${ECS_PACK_DIR}\" \\",
            "    --repo-url \"${QWENGUARD_REPO_URL}\" \\",
            "    --commit \"${QWENGUARD_COMMIT}\"",
            "}",
            "run_submission_pack() {",
            "  python3 -m scripts.prepare_qwenguard_submission_pack \\",
            "    --out-dir \"${SUBMISSION_PACK_DIR}\" \\",
            "    --task \"${QWENGUARD_TASK}\" \\",
            "    --repo-url \"${QWENGUARD_REPO_URL}\"",
            "}",
            "run_bootstrap() {",
            "  run_physical_pack",
            "  run_ecs_pack",
            "  run_submission_pack",
            "}",
            "run_safe_software() {",
            "  run_physical_pack",
            "  bash \"${PHYSICAL_PACK_DIR}/operator_commands.sh\" all-safe",
            "}",
            "run_so101_camera() {",
            "  run_physical_pack",
            "  bash \"${PHYSICAL_PACK_DIR}/operator_commands.sh\" camera",
            "}",
            "run_record_success() {",
            "  run_physical_pack",
            "  bash \"${PHYSICAL_PACK_DIR}/operator_commands.sh\" record-success",
            "}",
            "run_record_failure() {",
            "  run_physical_pack",
            "  bash \"${PHYSICAL_PACK_DIR}/operator_commands.sh\" record-failure",
            "}",
            "run_record_cloud_hold() {",
            "  run_physical_pack",
            "  bash \"${PHYSICAL_PACK_DIR}/operator_commands.sh\" record-cloud-hold",
            "}",
            "run_summarize_trials() {",
            "  python3 -m scripts.summarize_qwenguard_trials \\",
            "    --trial-csv \"${TRIAL_CSV}\" \\",
            "    --trial-trace-dir \"${TRIAL_TRACE_DIR}\" \\",
            "    --out \"${TRIAL_SUMMARY}\"",
            "}",
            "run_video_review() {",
            "  require_env QWENGUARD_REVIEWED_BY",
            "  require_env QWENGUARD_REVIEW_DATE",
            "  python3 -m scripts.prepare_qwenguard_final_video_review \\",
            "    --out \"${FINAL_VIDEO_REVIEW}\" \\",
            "    --reviewed-by \"${QWENGUARD_REVIEWED_BY}\" \\",
            "    --review-date \"${QWENGUARD_REVIEW_DATE}\" \\",
            "    --video-artifact \"${VIDEO_ARTIFACT}\" \\",
            "    --confirm-privacy \\",
            "    --confirm-claim-boundary \\",
            "    --confirm-mode-labels \\",
            "    --confirm-ecs-proof \\",
            "    --confirm-so101-footage \\",
            "    --confirm-secrets \\",
            "    ${QWENGUARD_FINAL_VIDEO_REVIEW_OVERWRITE:+--allow-overwrite}",
            "}",
            "run_audit() {",
            "  local allow_flag=\"${1:-}\"",
            "  run_submission_pack",
            "  python3 -m scripts.audit_qwenguard_submission_readiness \\",
            "    --submission-manifest \"${SUBMISSION_PACK_DIR}/manifest.json\" \\",
            "    --trial-csv \"${TRIAL_CSV}\" \\",
            "    --trial-trace-dir \"${TRIAL_TRACE_DIR}\" \\",
            "    --trial-summary \"${TRIAL_SUMMARY}\" \\",
            "    --out \"${READINESS_REPORT}\" \\",
            "    ${allow_flag}",
            "}",
            "",
            "case \"${PHASE}\" in",
            "  bootstrap) run_bootstrap ;;",
            "  safe-software) run_safe_software ;;",
            "  so101-camera) run_so101_camera ;;",
            "  record-success) run_record_success ;;",
            "  record-failure) run_record_failure ;;",
            "  record-cloud-hold) run_record_cloud_hold ;;",
            "  summarize-trials) run_summarize_trials ;;",
            "  ecs-pack) run_ecs_pack ;;",
            "  submission-pack) run_submission_pack ;;",
            "  video-review) run_video_review ;;",
            "  audit-narrow) run_audit --allow-narrow-claim ;;",
            "  audit-final) run_audit ;;",
            "  all-preflight) run_bootstrap; run_safe_software; run_audit --allow-narrow-claim ;;",
            "  help|-h|--help) usage ;;",
            "  *) usage; echo \"unknown phase: ${PHASE}\" >&2; exit 2 ;;",
            "esac",
            "",
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


def _manifest_file_paths_are_repo_relative(files: object) -> bool:
    if not isinstance(files, dict):
        return False
    for value in files.values():
        if not isinstance(value, str) or not value:
            return False
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts:
            return False
    return True


def _has_control_chars(value: str) -> bool:
    return any(ord(ch) < 32 for ch in value)


def _resolve_commit(repo_root: Path, supplied: str | None) -> str:
    if supplied is None:
        return _git_rev_parse(repo_root, "HEAD")
    if not _is_git_oid(supplied):
        raise ValueError("commit must be a full 40-character git object id")
    return _git_rev_parse(repo_root, supplied)


def _git_rev_parse(repo_root: Path, revision: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", f"{revision}^{{commit}}"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError("commit must resolve to a commit in this checkout")
    commit = result.stdout.strip()
    if not _is_git_oid(commit):
        raise ValueError("resolved commit is not a full 40-character git object id")
    return commit


def _is_git_oid(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{40}", value))


def _bash_syntax_text_ok(script: str) -> bool:
    result = subprocess.run(["bash", "-n"], input=script, text=True, capture_output=True, check=False)
    return result.returncode == 0


if __name__ == "__main__":
    raise SystemExit(main())
