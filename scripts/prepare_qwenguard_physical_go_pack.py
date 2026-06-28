#!/usr/bin/env python3
"""Prepare a non-secret operator pack for the QwenGuard physical GO session."""

from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import re
import shlex
import stat
import subprocess
import sys
from typing import Any

from accountable_swarm.qwenguard.trial import trial_csv_header
from accountable_swarm.trace.models import canonical_json


PACK_SCHEMA_VERSION = "qwenguard-physical-go-pack.v1"
DEFAULT_OUT_DIR = Path("runs/physical/qwenguard-physical-go-pack")
DEFAULT_TASK = "pick the red cube left of the green cube and place it in the bin"
DEFAULT_CAMERA_NAME = "so101_overhead"
DEFAULT_CAMERA_ID = "0"
DEFAULT_DATASET_REPO_ID = "YOUR_HF_USER/qwenguard-so101-cubes"
DEFAULT_POLICY_OUT_DIR = "outputs/train/qwenguard_so101_act"
DOC_SO101_URL = "https://huggingface.co/docs/lerobot/so101"
DOC_ACT_URL = "https://huggingface.co/docs/lerobot/en/act"
SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"Authorization:[ \t]*Bearer[ \t]+(?!<redacted>)\S+", re.IGNORECASE),
    re.compile(r"ALIBABA_API_KEY[ \t]*=[ \t]*\S+", re.IGNORECASE),
    re.compile(r"ghp_[A-Za-z0-9_]{12,}"),
    re.compile(r"sk-[A-Za-z0-9._-]{6,}"),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--task", default=DEFAULT_TASK)
    parser.add_argument("--camera-name", default=DEFAULT_CAMERA_NAME)
    parser.add_argument("--camera-id", default=DEFAULT_CAMERA_ID)
    parser.add_argument("--dataset-repo-id", default=DEFAULT_DATASET_REPO_ID)
    parser.add_argument("--policy-out-dir", default=DEFAULT_POLICY_OUT_DIR)
    args = parser.parse_args()

    for name, value in {
        "task": args.task,
        "camera_name": args.camera_name,
        "camera_id": args.camera_id,
        "dataset_repo_id": args.dataset_repo_id,
        "policy_out_dir": args.policy_out_dir,
    }.items():
        if _has_control_chars(value):
            print(f"{name} must not contain control characters", file=sys.stderr)
            return 2

    try:
        repo_root = _find_repo_root(Path.cwd())
        out_dir = _repo_path(repo_root, args.out_dir)
    except ValueError as exc:
        print(f"qwenguard physical GO pack failed: {exc}", file=sys.stderr)
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "runbook": out_dir / "README.md",
        "commands": out_dir / "operator_commands.sh",
        "trial_template": out_dir / "trial_template.csv",
        "evidence_template": out_dir / "evidence_manifest_template.json",
        "shotlist": out_dir / "demo_shotlist.md",
        "manifest": out_dir / "manifest.json",
    }

    runbook = _render_runbook(
        repo_root=repo_root,
        files=files,
        task=args.task,
        camera_name=args.camera_name,
        camera_id=args.camera_id,
        dataset_repo_id=args.dataset_repo_id,
        policy_out_dir=args.policy_out_dir,
    )
    commands = _render_commands(
        task=args.task,
        camera_name=args.camera_name,
        camera_id=args.camera_id,
        dataset_repo_id=args.dataset_repo_id,
        policy_out_dir=args.policy_out_dir,
    )
    trial_template = ",".join(trial_csv_header()) + "\n"
    evidence_template = canonical_json(_evidence_template(args.task)) + "\n"
    shotlist = _render_shotlist(args.task)

    generated_text = "\n".join([runbook, commands, trial_template, evidence_template, shotlist])
    if _contains_secret_material(generated_text):
        print("generated QwenGuard physical GO pack would contain secret material; aborting", file=sys.stderr)
        return 2

    files["runbook"].write_text(runbook, encoding="utf-8")
    files["commands"].write_text(commands, encoding="utf-8")
    files["commands"].chmod(files["commands"].stat().st_mode | stat.S_IXUSR)
    files["trial_template"].write_text(trial_template, encoding="utf-8")
    files["evidence_template"].write_text(evidence_template, encoding="utf-8")
    files["shotlist"].write_text(shotlist, encoding="utf-8")

    pass_conditions = {
        "runbook_written": files["runbook"].is_file(),
        "commands_script_written": files["commands"].is_file(),
        "commands_bash_syntax_valid": _bash_syntax_ok(files["commands"]),
        "trial_template_written": files["trial_template"].is_file() and "trace_summary_sha" in trial_template,
        "evidence_template_written": files["evidence_template"].is_file(),
        "shotlist_written": files["shotlist"].is_file(),
        "manifest_contains_no_secret_material": False,
        "output_paths_are_repo_relative": True,
    }
    manifest: dict[str, Any] = {
        "schema_version": PACK_SCHEMA_VERSION,
        "outcome": "GO",
        "issue": "https://github.com/omarespejel/accountable-swarm/issues/95",
        "task": args.task,
        "camera_name": args.camera_name,
        "camera_id": args.camera_id,
        "dataset_repo_id": args.dataset_repo_id,
        "policy_out_dir": args.policy_out_dir,
        "files": {name: _display_path(repo_root, path) for name, path in files.items()},
        "operator_phases": [
            "fixture",
            "degraded",
            "camera",
            "training-pack",
            "verify",
            "all-safe",
        ],
        "operator_proof_required": [
            "SO-101 camera frame captured through the controlled probe path",
            "fixture no-motion trace verifies",
            "degraded no-motion trace verifies and records HOLD",
            "training pack generated without secrets",
            "trial template filled by the operator after physical attempts",
            "raw private frames kept untracked unless explicitly reviewed",
        ],
        "non_claims": [
            "not SO-101 connectivity proof",
            "not SO-101 camera success until operator run completes",
            "not ACT policy training or success",
            "not autonomous physical motion",
            "not a safety, latency, or reliability claim",
            "not Qwen motor control",
            "not DimOS runtime control",
            "not Alibaba ECS deployment proof",
        ],
        "official_docs": {
            "lerobot_so101": DOC_SO101_URL,
            "lerobot_act": DOC_ACT_URL,
        },
        "pass_conditions": pass_conditions,
    }
    manifest_text = canonical_json(manifest)
    pass_conditions["manifest_contains_no_secret_material"] = not _contains_secret_material(manifest_text)
    pass_conditions["output_paths_are_repo_relative"] = _manifest_file_paths_are_repo_relative(manifest["files"])
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
    task: str,
    camera_name: str,
    camera_id: str,
    dataset_repo_id: str,
    policy_out_dir: str,
) -> str:
    return "\n".join(
        [
            "# QwenGuard Physical GO Operator Pack",
            "",
            "This pack prepares the SO-101 hardware session for issue #95. It",
            "does not move the robot by itself and does not prove physical success.",
            "",
            "## Hero Task",
            "",
            f"`{task}`",
            "",
            "Use colored cubes, preferably with at least one relational ambiguity",
            "that a color threshold alone cannot solve.",
            "",
            "## Files",
            "",
            f"- Runbook: `{_display_path(repo_root, files['runbook'])}`",
            f"- Commands: `{_display_path(repo_root, files['commands'])}`",
            f"- Trial template: `{_display_path(repo_root, files['trial_template'])}`",
            f"- Evidence template: `{_display_path(repo_root, files['evidence_template'])}`",
            f"- Demo shotlist: `{_display_path(repo_root, files['shotlist'])}`",
            f"- Manifest: `{_display_path(repo_root, files['manifest'])}`",
            "",
            "## Intended Defaults",
            "",
            f"- Camera name: `{camera_name}`",
            f"- Initial camera id guess: `{camera_id}`",
            f"- Dataset repo: `{dataset_repo_id}`",
            f"- Policy output: `{policy_out_dir}`",
            "- Motion boundary for this pack: no-motion unless the operator runs",
            "  the separate LeRobot collection or autonomous-eval commands generated",
            "  by the training pack.",
            "",
            "## Operator Phases",
            "",
            "Run from the repository root after reviewing this file:",
            "",
            "```bash",
            f"bash {_display_path(repo_root, files['commands'])} fixture",
            f"bash {_display_path(repo_root, files['commands'])} degraded",
            f"bash {_display_path(repo_root, files['commands'])} camera",
            f"bash {_display_path(repo_root, files['commands'])} training-pack",
            f"bash {_display_path(repo_root, files['commands'])} verify",
            "```",
            "",
            "The `camera` phase is the first phase that touches the SO-101 camera.",
            "The `training-pack` phase writes LeRobot ACT commands but does not run",
            "data collection, training, or autonomous rollout directly.",
            "",
            "## Safety And Claim Boundary",
            "",
            "- Qwen selects/evaluates. Qwen never controls motors.",
            "- ACT is the local policy path, and it remains unproven until the",
            "  operator runs measured physical trials.",
            "- Keep raw physical frames untracked unless privacy-reviewed.",
            "- Record trial results as measured `N/10`, not implied reliability.",
            "- Label clips `TELEOP`, `AUTONOMOUS`, or `SCRIPTED` honestly.",
            "",
            "## References",
            "",
            f"- LeRobot SO-101: {DOC_SO101_URL}",
            f"- LeRobot ACT: {DOC_ACT_URL}",
            "",
        ]
    )


def _render_commands(
    *,
    task: str,
    camera_name: str,
    camera_id: str,
    dataset_repo_id: str,
    policy_out_dir: str,
) -> str:
    q_task = shlex.quote(task)
    q_camera_name = shlex.quote(camera_name)
    q_camera_id = shlex.quote(camera_id)
    q_dataset_repo_id = shlex.quote(dataset_repo_id)
    q_policy_out_dir = shlex.quote(policy_out_dir)
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
            'RUN_DIR="${QWENGUARD_GO_RUN_DIR:-runs/physical/qwenguard_physical_go}"',
            'TRAINING_PACK_DIR="${QWENGUARD_TRAINING_PACK_DIR:-runs/physical/qwenguard_so101_training_pack}"',
            'case "${RUN_DIR}" in /*|..|../*|*/..|*/../*) echo "QWENGUARD_GO_RUN_DIR must be repo-relative and must not contain .." >&2; exit 2 ;; esac',
            'case "${TRAINING_PACK_DIR}" in /*|..|../*|*/..|*/../*) echo "QWENGUARD_TRAINING_PACK_DIR must be repo-relative and must not contain .." >&2; exit 2 ;; esac',
            "",
            f"export QWENGUARD_TASK={q_task}",
            f"export QWENGUARD_CAMERA_NAME={q_camera_name}",
            f"export QWENGUARD_CAMERA_ID={q_camera_id}",
            f"export QWENGUARD_DATASET_REPO_ID={q_dataset_repo_id}",
            f"export QWENGUARD_POLICY_OUT_DIR={q_policy_out_dir}",
            "",
            "usage() {",
            "  cat <<'EOUSAGE'",
            "Usage: operator_commands.sh PHASE",
            "",
            "Phases:",
            "  fixture        Run no-motion fixture selector/gate/evaluator trace.",
            "  degraded       Run no-motion degraded-cloud HOLD trace.",
            "  camera         Capture one SO-101 camera frame through the trace-only probe.",
            "  training-pack  Generate the LeRobot ACT operator training pack.",
            "  verify         Verify generated fixture/degraded traces when present.",
            "  all-safe       Run fixture, degraded, training-pack, and verify. Does not touch camera.",
            "",
            "No phase in this script moves the SO-101. The generated training pack",
            "contains the separate operator-reviewed LeRobot collection/eval commands.",
            "EOUSAGE",
            "}",
            "",
            "run_fixture() {",
            "  mkdir -p \"${RUN_DIR}\"",
            "  python3 -m scripts.run_qwenguard_no_motion_health_check \\",
            "    --image fixtures/hazard_marker.ppm \\",
            "    --mode fixture \\",
            "    --policy-available \\",
            "    --simulate-safe-motion-authority \\",
            "    --instruction \"${QWENGUARD_TASK}\" \\",
            "    --trace-out \"${RUN_DIR}/fixture_trace.json\" \\",
            "    --report-out \"${RUN_DIR}/fixture_report.json\"",
            "}",
            "",
            "run_degraded() {",
            "  mkdir -p \"${RUN_DIR}\"",
            "  python3 -m scripts.run_qwenguard_no_motion_health_check \\",
            "    --image fixtures/hazard_marker.ppm \\",
            "    --mode degraded \\",
            "    --policy-available \\",
            "    --simulate-safe-motion-authority \\",
            "    --instruction \"${QWENGUARD_TASK}\" \\",
            "    --trace-out \"${RUN_DIR}/degraded_trace.json\" \\",
            "    --report-out \"${RUN_DIR}/degraded_report.json\"",
            "}",
            "",
            "run_camera() {",
            "  mkdir -p \"${RUN_DIR}\"",
            "  python3 -m scripts.capture_so101_camera_frame \\",
            "    --camera-name \"${QWENGUARD_CAMERA_NAME}\" \\",
            "    --index-or-path \"${QWENGUARD_CAMERA_ID}\" \\",
            "    --out \"${RUN_DIR}/so101_frame.png\" \\",
            "    --report-out \"${RUN_DIR}/so101_capture_report.json\"",
            "}",
            "",
            "run_training_pack() {",
            "  python3 -m scripts.prepare_so101_training_pack \\",
            "    --out-dir \"${TRAINING_PACK_DIR}\" \\",
            "    --task \"${QWENGUARD_TASK}\" \\",
            "    --dataset-repo-id \"${QWENGUARD_DATASET_REPO_ID}\" \\",
            "    --policy-out-dir \"${QWENGUARD_POLICY_OUT_DIR}\"",
            "}",
            "",
            "run_verify() {",
            "  for trace in \"${RUN_DIR}/fixture_trace.json\" \"${RUN_DIR}/degraded_trace.json\"; do",
            "    if [[ -f \"${trace}\" ]]; then",
            "      python3 -m scripts.verify_trace \"${trace}\"",
            "    fi",
            "  done",
            "}",
            "",
            "case \"${PHASE}\" in",
            "  fixture) run_fixture ;;",
            "  degraded) run_degraded ;;",
            "  camera) run_camera ;;",
            "  training-pack) run_training_pack ;;",
            "  verify) run_verify ;;",
            "  all-safe) run_fixture; run_degraded; run_training_pack; run_verify ;;",
            "  help|-h|--help) usage ;;",
            "  *) usage; echo \"unknown phase: ${PHASE}\" >&2; exit 2 ;;",
            "esac",
            "",
        ]
    )


def _render_shotlist(task: str) -> str:
    return "\n".join(
        [
            "# QwenGuard Physical Demo Shotlist",
            "",
            "Keep the final video under three minutes and label every segment.",
            "",
            "1. Setup: SO-101, cubes, bin, one camera.",
            "2. Instruction overlay:",
            f"   `{task}`",
            "3. Qwen selector overlay: target id, relation, bbox evidence, confidence_milli.",
            "4. Local outcome gate overlay: predicted_success_milli, risk_level, gate_decision.",
            "5. Physical segment label: `AUTONOMOUS` only if the local ACT policy is",
            "   actually running without teleop; otherwise label `TELEOP` or `SCRIPTED`.",
            "6. Qwen evaluator overlay: success/failure/uncertain and failure_type.",
            "7. Cloud-degraded take: missing cloud response causes local HOLD.",
            "8. End card: measured N/10, trace verifier command, non-claims.",
            "",
            "Do not claim Qwen motor control, onboard Qwen, safety certification,",
            "DimOS physical control, or SO-101 success before checked evidence exists.",
            "",
        ]
    )


def _evidence_template(task: str) -> dict[str, Any]:
    return {
        "schema_version": "qwenguard-physical-go-evidence-template.v1",
        "issue": "https://github.com/omarespejel/accountable-swarm/issues/95",
        "task": task,
        "operator_fill_required": {
            "so101_camera_report": "runs/physical/qwenguard_physical_go/so101_capture_report.json",
            "fixture_trace": "runs/physical/qwenguard_physical_go/fixture_trace.json",
            "degraded_trace": "runs/physical/qwenguard_physical_go/degraded_trace.json",
            "training_pack_manifest": "runs/physical/qwenguard_so101_training_pack/manifest.json",
            "trial_trace_dir": "runs/physical/qwenguard_trials/traces",
            "trial_csv": "runs/physical/qwenguard_so101_training_pack/trial_template.csv",
            "raw_frame_policy": "keep untracked unless privacy-reviewed",
        },
        "required_before_public_claim": [
            "camera report outcome GO",
            "fixture trace verifies",
            "degraded trace verifies and records HOLD",
            "each promoted physical trial has a verified DecisionTrace under runs/physical/qwenguard_trials/traces",
            "trial CSV contains measured N/10 rows bound to those trial trace summary SHAs",
            "demo captions label TELEOP/AUTONOMOUS/SCRIPTED honestly",
            "no secrets or raw private imagery committed",
        ],
        "non_claims": [
            "not SO-101 success until operator evidence is filled",
            "not ACT policy success until measured physical trials exist",
            "not a safety or reliability claim",
        ],
    }


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


def _bash_syntax_ok(path: Path) -> bool:
    result = subprocess.run(["bash", "-n", str(path)], text=True, capture_output=True, check=False)
    return result.returncode == 0


if __name__ == "__main__":
    raise SystemExit(main())
