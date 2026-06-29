#!/usr/bin/env python3
"""Prepare a non-secret SO-101 ACT training and evaluation operator pack."""

from __future__ import annotations

import argparse
from pathlib import Path
import shlex

from accountable_swarm.trace.models import canonical_json
from accountable_swarm.qwenguard.trial import trial_csv_header

REPORT_SCHEMA_VERSION = "qwenguard-so101-training-pack.v1"
DEFAULT_LEROBOT_GIT_REF = "1396b9fab7aecddd10006c33c47a487ffdcb54b4"  # v0.5.1 as checked on 2026-06-28
DEFAULT_OPENCV_PYTHON_VERSION = "4.13.0.92"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--task", default="pick the red cube left of the green cube and place it in the bin")
    parser.add_argument("--dataset-repo-id", default="YOUR_HF_USER/qwenguard-so101-cubes")
    parser.add_argument("--policy-out-dir", default="outputs/train/qwenguard_so101_act")
    parser.add_argument("--lerobot-git-ref", default=DEFAULT_LEROBOT_GIT_REF)
    parser.add_argument("--opencv-python-version", default=DEFAULT_OPENCV_PYTHON_VERSION)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    runbook = _runbook(
        task=args.task,
        dataset_repo_id=args.dataset_repo_id,
        policy_out_dir=args.policy_out_dir,
        lerobot_git_ref=args.lerobot_git_ref,
        opencv_python_version=args.opencv_python_version,
    )
    commands = _commands(
        task=args.task,
        dataset_repo_id=args.dataset_repo_id,
        policy_out_dir=args.policy_out_dir,
        lerobot_git_ref=args.lerobot_git_ref,
        opencv_python_version=args.opencv_python_version,
    )
    trial_template = ",".join(trial_csv_header()) + "\n"
    (args.out_dir / "README.md").write_text(runbook, encoding="utf-8")
    command_path = args.out_dir / "operator_commands.sh"
    command_path.write_text(commands, encoding="utf-8")
    command_path.chmod(0o755)
    (args.out_dir / "trial_template.csv").write_text(trial_template, encoding="utf-8")
    manifest = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "task": args.task,
        "dataset_repo_id": args.dataset_repo_id,
        "policy_out_dir": args.policy_out_dir,
        "lerobot_git_ref": args.lerobot_git_ref,
        "opencv_python_version": args.opencv_python_version,
        "files": ["README.md", "operator_commands.sh", "trial_template.csv"],
        "non_claims": [
            "not SO-101 connectivity proof",
            "not ACT policy success",
            "not autonomous physical success",
            "not a safety certification",
            "contains no secrets",
        ],
    }
    (args.out_dir / "manifest.json").write_text(canonical_json(manifest) + "\n", encoding="utf-8")
    print(f"wrote {args.out_dir}")
    return 0


def _runbook(
    *,
    task: str,
    dataset_repo_id: str,
    policy_out_dir: str,
    lerobot_git_ref: str,
    opencv_python_version: str,
) -> str:
    return f"""# QwenGuard SO-101 ACT Training Pack

This operator pack prepares tomorrow's physical SO-101 session. It is a runbook
only: it does not prove SO-101 connectivity, train a policy, or move hardware by
itself.

## Task

`{task}`

Use colored cubes and a bin/cup. Keep one stable camera view first. Label any
data-collection segment as `TELEOP`; label policy rollout as `AUTONOMOUS` only
after the leader arm is detached or clearly not controlling the follower.

## Critical claim boundaries

- Qwen selects/evaluates; Qwen never controls motors.
- ACT is the local motor policy.
- SmolVLA is stretch only, not the critical path.
- No blind community `.pt` weight loading. Prefer official LeRobot paths and
  inspect any external model before use.
- If async inference is used, bind it to localhost only.
- Record measured `N/10`; do not imply 100% success.
- This pack does **not** provide a programmatic interlock between a QwenGuard
  `ALLOW` decision and the LeRobot motion command. The shell checks below are
  manual operator acknowledgements only.

## Motion readiness checklist

Before running any LeRobot command that can move the SO-101:

1. Emergency stop path is reachable and tested.
2. Low-speed mode is selected.
3. Workspace bounds are physically marked and clear.
4. For autonomous policy rollout, the leader is detached or clearly
   non-authoritative.

The generated command script hard-fails unless the relevant acknowledgements
are exported before motion-capable LeRobot commands:

```bash
export QWENGUARD_EMERGENCY_STOP_READY=yes
export QWENGUARD_LOW_SPEED_MODE=yes
export QWENGUARD_WORKSPACE_BOUNDS_SET=yes
export QWENGUARD_LEADER_DETACHED_OR_NONAUTHORITATIVE=yes  # autonomous rollout only
```

The camera probe command remains trace-only and does not require these motion
acknowledgements.

## Suggested session order

1. Assemble SO-101, clear the workspace, verify emergency stop path.
2. Confirm one camera frame with `capture-so101-camera-frame`.
3. Record 50-100 clean demonstrations of the same constrained pick/place task.
4. Train ACT.
5. Run 10 autonomous evaluation trials.
6. Fill `trial_template.csv` with operator labels and trace hashes.

## References

- LeRobot SO-101 docs: https://huggingface.co/docs/lerobot/en/so101
- LeRobot ACT docs: https://huggingface.co/docs/lerobot/en/act

## Operator placeholders

- Dataset repo: `{dataset_repo_id}`
- Policy output: `{policy_out_dir}`
- LeRobot git ref: `{lerobot_git_ref}`
- OpenCV Python version: `{opencv_python_version}`
"""


def _commands(
    *,
    task: str,
    dataset_repo_id: str,
    policy_out_dir: str,
    lerobot_git_ref: str,
    opencv_python_version: str,
) -> str:
    return f"""#!/usr/bin/env bash
set -euo pipefail

# Run manually on the hardware machine. Fill robot/camera identifiers after
# following the official LeRobot SO-101 setup docs.

export QWENGUARD_TASK={shlex.quote(task)}
export QWENGUARD_DATASET_REPO_ID={shlex.quote(dataset_repo_id)}
export QWENGUARD_POLICY_OUT_DIR={shlex.quote(policy_out_dir)}
export QWENGUARD_LEROBOT_GIT_REF={shlex.quote(lerobot_git_ref)}
export QWENGUARD_OPENCV_PYTHON_VERSION={shlex.quote(opencv_python_version)}

require_yes() {{
  local name="$1"
  local detail="$2"
  if [[ "${{!name:-}}" != "yes" ]]; then
    echo "${{name}}=yes required before SO-101 motion: ${{detail}}" >&2
    exit 2
  fi
}}

require_motion_readiness() {{
  require_yes QWENGUARD_EMERGENCY_STOP_READY "emergency stop path reachable and tested"
  require_yes QWENGUARD_LOW_SPEED_MODE "low-speed mode selected"
  require_yes QWENGUARD_WORKSPACE_BOUNDS_SET "workspace bounds physically marked and clear"
}}

require_autonomous_readiness() {{
  require_motion_readiness
  require_yes QWENGUARD_LEADER_DETACHED_OR_NONAUTHORITATIVE "leader detached or non-authoritative for autonomous rollout"
}}

python -m pip install \\
  "lerobot[feetech] @ git+https://github.com/huggingface/lerobot.git@${{QWENGUARD_LEROBOT_GIT_REF}}" \\
  "opencv-python==${{QWENGUARD_OPENCV_PYTHON_VERSION}}"

# 1. Probe camera only, no motion.
capture-so101-camera-frame \\
  --camera-name so101-main \\
  --index-or-path 0 \\
  --out runs/physical/so101_probe/frame.png \\
  --report-out runs/physical/so101_probe/report.json

# 2. Record demonstrations.
# Replace robot.type/ports/camera IDs with values from your calibrated SO-101.
# This is manual teleoperation. It is guarded only by operator acknowledgements,
# not by a QwenGuard ALLOW-to-LeRobot actuation interlock.
require_motion_readiness
python -m lerobot.record \\
  --robot.type=so101_follower \\
  --teleop.type=so101_leader \\
  --dataset.repo_id="$QWENGUARD_DATASET_REPO_ID" \\
  --dataset.num_episodes=50 \\
  --dataset.single_task="$QWENGUARD_TASK"

# 3. Train ACT.
python -m lerobot.train \\
  --policy.type=act \\
  --dataset.repo_id="$QWENGUARD_DATASET_REPO_ID" \\
  --output_dir="$QWENGUARD_POLICY_OUT_DIR"

# 4. Evaluate ACT over 10 trials.
# Keep the leader detached/non-authoritative during autonomous rollout.
# This is manual operator execution of a local policy, not Qwen motor control.
require_autonomous_readiness
python -m lerobot.record \\
  --robot.type=so101_follower \\
  --policy.path="$QWENGUARD_POLICY_OUT_DIR/checkpoints/last/pretrained_model" \\
  --dataset.repo_id="${{QWENGUARD_DATASET_REPO_ID}}-eval" \\
  --dataset.num_episodes=10 \\
  --dataset.single_task="$QWENGUARD_TASK"
"""


if __name__ == "__main__":
    raise SystemExit(main())
