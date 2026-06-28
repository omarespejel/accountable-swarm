#!/usr/bin/env python3
"""Prepare a claim-safe QwenGuard Track 5 submission pack."""

from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any

from accountable_swarm.trace.models import canonical_json


PACK_SCHEMA_VERSION = "qwenguard-submission-pack.v1"
DEFAULT_OUT_DIR = Path("runs/submission/qwenguard-pack")
DEFAULT_TASK = "pick the red cube left of the green cube and place it in the bin"
DEVPOST_URL = "https://qwencloud-hackathon.devpost.com/"
ISSUE_URL = "https://github.com/omarespejel/accountable-swarm/issues/95"
ECS_ISSUE_URL = "https://github.com/omarespejel/accountable-swarm/issues/91"
SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"Authorization:[ \t]*Bearer[ \t]+(?!<redacted>)\S+", re.IGNORECASE),
    re.compile(r"ALIBABA_API_KEY[ \t]*=[ \t]*\S+", re.IGNORECASE),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"gh(?:p|o|u|s|r)_[A-Za-z0-9_]{12,}"),
    re.compile(r"sk-[A-Za-z0-9._-]{6,}"),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--task", default=DEFAULT_TASK)
    parser.add_argument(
        "--repo-url",
        default="https://github.com/omarespejel/accountable-swarm",
        help="Public repository URL to place in the pack.",
    )
    args = parser.parse_args()

    for name, value in {
        "task": args.task,
        "repo_url": args.repo_url,
        "out_dir": str(args.out_dir),
    }.items():
        if _has_control_chars(value):
            print(f"{name} must not contain control characters", file=sys.stderr)
            return 2

    try:
        repo_root = _find_repo_root(Path.cwd())
        out_dir = _repo_path(repo_root, args.out_dir)
    except ValueError as exc:
        print(f"qwenguard submission pack failed: {exc}", file=sys.stderr)
        return 2
    if _contains_secret_material(_display_path(repo_root, out_dir)):
        print("qwenguard submission pack failed: output path contains secret-like material", file=sys.stderr)
        return 2

    files = {
        "readme": out_dir / "README.md",
        "architecture": out_dir / "architecture.md",
        "demo_script": out_dir / "demo_script.md",
        "evidence_manifest": out_dir / "evidence_manifest.json",
        "manifest": out_dir / "manifest.json",
    }
    readme = _render_readme(repo_root=repo_root, files=files, task=args.task, repo_url=args.repo_url)
    architecture = _render_architecture(task=args.task)
    demo_script = _render_demo_script(task=args.task)
    evidence_manifest = _evidence_manifest(task=args.task, repo_url=args.repo_url)

    generated_text = "\n".join([readme, architecture, demo_script, canonical_json(evidence_manifest)])
    if _contains_secret_material(generated_text):
        print("generated QwenGuard submission pack would contain secret material; aborting", file=sys.stderr)
        return 2

    pass_conditions = {
        "readme_written": True,
        "architecture_written": True,
        "demo_script_written": True,
        "evidence_manifest_written": True,
        "manifest_contains_no_secret_material": False,
        "output_paths_are_repo_relative": False,
        "readiness_is_not_overclaimed": evidence_manifest["submission_readiness"] == "NARROW_CLAIM",
    }
    manifest: dict[str, Any] = {
        "schema_version": PACK_SCHEMA_VERSION,
        "outcome": "GO",
        "submission_readiness": evidence_manifest["submission_readiness"],
        "issue": ISSUE_URL,
        "ecs_issue": ECS_ISSUE_URL,
        "devpost": DEVPOST_URL,
        "task": args.task,
        "files": {name: _display_path(repo_root, path) for name, path in files.items()},
        "required_before_submit": evidence_manifest["required_before_submit"],
        "pack_claim": (
            "claim-safe submission scaffold only; physical SO-101 and Alibaba ECS "
            "proofs remain operator gates"
        ),
        "non_claims": evidence_manifest["non_claims"],
        "pass_conditions": pass_conditions,
    }
    manifest_text = canonical_json(manifest)
    pass_conditions["manifest_contains_no_secret_material"] = not _contains_secret_material(manifest_text)
    pass_conditions["output_paths_are_repo_relative"] = _manifest_file_paths_are_repo_relative(manifest["files"])
    manifest["outcome"] = "GO" if all(pass_conditions.values()) else "NARROW_CLAIM"
    manifest_text = canonical_json(manifest)
    if _contains_secret_material(manifest_text):
        print("generated QwenGuard submission manifest would contain secret material; aborting", file=sys.stderr)
        return 2
    if manifest["outcome"] != "GO":
        print("generated QwenGuard submission manifest failed pass conditions; aborting", file=sys.stderr)
        return 4

    out_dir.mkdir(parents=True, exist_ok=True)
    files["readme"].write_text(readme, encoding="utf-8")
    files["architecture"].write_text(architecture, encoding="utf-8")
    files["demo_script"].write_text(demo_script, encoding="utf-8")
    files["evidence_manifest"].write_text(canonical_json(evidence_manifest) + "\n", encoding="utf-8")
    files["manifest"].write_text(canonical_json(manifest) + "\n", encoding="utf-8")

    print(f"outcome {manifest['outcome']}")
    print(f"submission_readiness {manifest['submission_readiness']}")
    print(f"manifest {_display_path(repo_root, files['manifest'])}")
    print(f"readme {_display_path(repo_root, files['readme'])}")
    print(f"architecture {_display_path(repo_root, files['architecture'])}")
    print(f"demo_script {_display_path(repo_root, files['demo_script'])}")
    return 0 if manifest["outcome"] == "GO" else 4


def _render_readme(*, repo_root: Path, files: dict[str, Path], task: str, repo_url: str) -> str:
    return "\n".join(
        [
            "# QwenGuard Track 5 Submission Pack",
            "",
            "This pack is a claim-safe operator/judge scaffold for the Qwen Cloud",
            "Hackathon Track 5 EdgeAgent submission. It is intentionally marked",
            "`NARROW_CLAIM` for submission readiness until the SO-101 physical",
            "run and Alibaba ECS proof are filled by the operator.",
            "",
            "## One-Sentence Pitch",
            "",
            "> Qwen proposes an object candidate from an edge camera frame, local",
            "> code validates and gates that proposal, a local SO-101 policy acts",
            "> only when the gate allows it, cloud failure causes HOLD, and every decision",
            "> is replayable as a hash-chained DecisionTrace.",
            "",
            "## Current Hero Task",
            "",
            f"`{task}`",
            "",
            "Use colored cubes, but make the instruction relational so Qwen is",
            "load-bearing and a color threshold is not enough.",
            "",
            "## Track 5 Fit",
            "",
            f"- Hackathon page: {DEVPOST_URL}",
            "- Edge sensor: SO-101 camera frame, pending operator proof.",
            "- Cloud reasoning: Qwen selector/evaluator, locally validated JSON.",
            "- Local action: ACT policy path, pending measured physical trials.",
            "- Offline degradation: local HOLD trace already exists in fixture mode.",
            "- Accountability: `decisiontrace.v2` verifier and trace hashes.",
            "- Alibaba deployment: tracked separately in issue #91.",
            "",
            "## Files",
            "",
            f"- README: `{_display_path(repo_root, files['readme'])}`",
            f"- Architecture: `{_display_path(repo_root, files['architecture'])}`",
            f"- Demo script: `{_display_path(repo_root, files['demo_script'])}`",
            f"- Evidence manifest: `{_display_path(repo_root, files['evidence_manifest'])}`",
            f"- Pack manifest: `{_display_path(repo_root, files['manifest'])}`",
            "",
            "## Exact Operator Commands",
            "",
            "Prepare the physical-session pack:",
            "",
            "```bash",
            "prepare-qwenguard-physical-go-pack \\",
            "  --out-dir runs/physical/qwenguard-physical-go-pack \\",
            "  --camera-name so101_overhead \\",
            "  --camera-id 0",
            "```",
            "",
            "Run the no-hardware safe path first:",
            "",
            "```bash",
            "bash runs/physical/qwenguard-physical-go-pack/operator_commands.sh all-safe",
            "```",
            "",
            "Then, only when the SO-101 is connected and supervised:",
            "",
            "```bash",
            "bash runs/physical/qwenguard-physical-go-pack/operator_commands.sh camera",
            "bash runs/physical/qwenguard-physical-go-pack/operator_commands.sh training-pack",
            "```",
            "",
            "Prepare the Alibaba ECS proof pack in parallel:",
            "",
            "```bash",
            "prepare-ecs-operator-pack --commit \"$(git rev-parse HEAD)\"",
            "```",
            "",
            "## Required Before Submission",
            "",
            "- SO-101 camera report with `outcome: GO`.",
            "- Qwen selector/evaluator traces over the real setup.",
            "- Measured physical trials as `N/10` with failure taxonomy.",
            "- Per-trial `decisiontrace.v2` JSON files under",
            "  `runs/physical/qwenguard_trials/traces/`, with CSV rows bound",
            "  to their `trace_summary_sha` values.",
            "- Trial rows recorded by `record-qwenguard-trial` into",
            "  `runs/physical/qwenguard_trials/trial_results.csv`.",
            "- Cloud-degraded HOLD take.",
            "- Alibaba ECS smoke report with `proof_mode: ecs-public` and `outcome: GO`.",
            "- Human-reviewed video captions with no overclaims.",
            "",
            "## Repo",
            "",
            repo_url,
            "",
        ]
    )


def _render_architecture(*, task: str) -> str:
    return "\n".join(
        [
            "# QwenGuard Architecture",
            "",
            "Issue: #95",
            "",
            "This diagram is for the planned physical Track 5 demo. It is not",
            "physical-success evidence until the operator fills the evidence",
            "manifest with real SO-101 and ECS artifacts.",
            "",
            "```mermaid",
            "flowchart LR",
            '  A["SO-101 camera frame"] --> B["Qwen selector (cloud)"]',
            '  B --> C["Local JSON validator"]',
            '  C --> D["Local outcome gate"]',
            '  D -->|ALLOW| E["Local ACT policy"]',
            '  D -->|HOLD| F["Local HOLD"]',
            '  E --> G["SO-101 pick/place attempt"]',
            '  G --> H["Qwen evaluator (before/after)"]',
            '  F --> I["DecisionTrace.v2"]',
            '  H --> I',
            '  D --> I',
            '  I --> J["Trace verifier"]',
            '  I --> K["DimOS-ready replay sidecar (no control claim)"]',
            '  L["Alibaba ECS proof (#91)"] -. "operator-run" .-> J',
            "```",
            "",
            "Task:",
            "",
            f"`{task}`",
            "",
            "Boundary:",
            "",
            "- Qwen proposes and evaluates; it never controls motors.",
            "- Local code validates, gates, acts, and records traces.",
            "- ACT remains a local policy claim only after measured physical trials.",
            "- DimOS is a replay sidecar unless a later issue proves runtime consumption.",
            "",
        ]
    )


def _render_demo_script(*, task: str) -> str:
    return "\n".join(
        [
            "# QwenGuard Demo Script",
            "",
            "Target duration: under 3 minutes.",
            "",
            "## 0:00-0:15 Setup",
            "",
            "- Show SO-101, cubes, bin, camera.",
            "- On-screen label: `REAL SO-101 SETUP - evidence pending until trace shown`.",
            "",
            "## 0:15-0:40 Qwen Selector",
            "",
            f"- Instruction: `{task}`",
            "- Show target mark id, relation, bbox evidence, confidence_milli.",
            "- Say: Qwen proposes; local code validates.",
            "",
            "## 0:40-1:00 Local Outcome Gate",
            "",
            "- Show predicted_success_milli, risk_level, gate_decision.",
            "- Say: the edge node can HOLD even when Qwen returns an answer.",
            "",
            "## 1:00-1:45 Local ACT Action",
            "",
            "- Label honestly: `AUTONOMOUS` only if ACT runs without teleop.",
            "- Keep leader arm detached in the autonomous segment.",
            "- Do not cut around a teleop correction without labeling it.",
            "",
            "## 1:45-2:10 Qwen Evaluator",
            "",
            "- Show before/after evaluation: success/failure/uncertain.",
            "- Show trace summary SHA and verifier command.",
            "",
            "## 2:10-2:35 Cloud-Degraded HOLD",
            "",
            "- Disable cloud/key/network for the selector path.",
            "- Show local HOLD and `cloud_unavailable` evidence.",
            "",
            "## 2:35-2:55 Evidence End Card",
            "",
            "- Measured `N/10` physical result.",
            "- Alibaba ECS proof status.",
            "- Non-claims: no Qwen motor control, not safety-certified, not SOTA.",
            "",
        ]
    )


def _evidence_manifest(*, task: str, repo_url: str) -> dict[str, Any]:
    return {
        "schema_version": "qwenguard-submission-evidence.v1",
        "issue": ISSUE_URL,
        "ecs_issue": ECS_ISSUE_URL,
        "devpost": DEVPOST_URL,
        "repo_url": repo_url,
        "submission_readiness": "NARROW_CLAIM",
        "task": task,
        "track5_alignment": {
            "edge_sensor": "SO-101 camera frame, pending operator proof",
            "cloud_reasoning": "Qwen selector/evaluator with local validation",
            "local_action": "ACT policy path, pending physical trials",
            "degraded_mode": "fixture HOLD path checked; physical/video take pending",
            "accountability": "decisiontrace.v2 hash-chain verifier",
            "alibaba_deploy": "pending issue #91 ECS public endpoint proof",
        },
        "required_before_submit": [
            {
                "name": "so101_camera_frame",
                "status": "pending",
                "expected_path": "runs/physical/qwenguard_physical_go/so101_capture_report.json",
            },
            {
                "name": "qwenguard_no_motion_selector_gate_eval",
                "status": "pending",
                "expected_path": "runs/physical/qwenguard_physical_go/fixture_trace.json",
                "note": "current physical-go pack writes one multi-stage no-motion trace, not separate selector/evaluator traces",
            },
            {
                "name": "act_physical_trials",
                "status": "pending",
                "expected_path": "runs/physical/qwenguard_trials/trial_results.csv",
                "note": (
                    "operator records measured trials with record-qwenguard-trial; "
                    "each promoted row binds to a verified trial trace summary"
                ),
            },
            {
                "name": "measured_trial_traces",
                "status": "pending",
                "expected_path": "runs/physical/qwenguard_trials/traces",
                "note": "operator stores one decisiontrace.v2 JSON file per promoted physical trial",
            },
            {
                "name": "cloud_degraded_hold_take",
                "status": "pending",
                "expected_path": "runs/physical/qwenguard_physical_go/degraded_trace.json",
            },
            {
                "name": "alibaba_ecs_public_endpoint",
                "status": "pending",
                "expected_path": "runs/ecs/ecs_smoke_report.json",
            },
            {
                "name": "human_reviewed_video",
                "status": "pending",
                "expected_path": "runs/submission/final_video_review.md",
            },
        ],
        "already_checked_locally": [
            "no-hardware QwenGuard selector/evaluator/gate software spine",
            "fixture no-motion ALLOW intent trace",
            "degraded no-motion HOLD trace",
            "operator physical GO pack generation",
            "interactive dashboard over deterministic planner",
        ],
        "non_claims": [
            "not SO-101 connectivity proof",
            "not physical success evidence",
            "not ACT policy success",
            "not Qwen motor control",
            "not Qwen onboard execution",
            "not validated 3D grasping",
            "not safety certified",
            "not a latency or reliability claim",
            "not Alibaba ECS deployment proof until issue #91 reaches GO",
            "not DimOS physical control",
            "not state of the art",
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


if __name__ == "__main__":
    raise SystemExit(main())
