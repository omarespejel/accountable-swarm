#!/usr/bin/env python3
"""Prepare a non-secret Alibaba ECS operator proof pack."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from accountable_swarm.trace.models import canonical_json


PACK_SCHEMA_VERSION = "ecs-operator-proof-pack.v1"
DEFAULT_OUT_DIR = Path("runs/ecs/operator-pack")
DEFAULT_BASE_URL = "http://<ECS_PUBLIC_IP>:8000"
DEFAULT_REPO_URL = "https://github.com/omarespejel/accountable-swarm"
SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"Authorization:[ \t]*Bearer[ \t]+(?!<redacted>)\S+", re.IGNORECASE),
    re.compile(r"ALIBABA_API_KEY[ \t]*=[ \t]*\S+", re.IGNORECASE),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"gh(?:p|o|u|s|r)_[A-Za-z0-9_]{12,}"),
    re.compile(r"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9._-]{20,}"),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--repo-url", default=DEFAULT_REPO_URL)
    parser.add_argument("--commit", default=None)
    args = parser.parse_args()

    if _has_control_chars(args.base_url) or _has_control_chars(args.repo_url):
        print("base URL and repo URL must not contain control characters", file=sys.stderr)
        return 2
    if args.commit is not None and _has_control_chars(args.commit):
        print("commit must not contain control characters", file=sys.stderr)
        return 2
    for name, value in {
        "base URL": args.base_url,
        "repo URL": args.repo_url,
        "commit": args.commit or "",
    }.items():
        if _contains_secret_material(value):
            print(f"{name} must not contain secret-like material", file=sys.stderr)
            return 2

    try:
        repo_root = _find_repo_root(Path.cwd())
    except ValueError as exc:
        print(f"ecs operator pack failed: {exc}", file=sys.stderr)
        return 2

    commit = args.commit or _git_head(repo_root)
    try:
        out_dir = _repo_path(repo_root, args.out_dir)
    except ValueError as exc:
        print(f"ecs operator pack failed: {exc}", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "runbook": out_dir / "README.md",
        "commands": out_dir / "operator_commands.sh",
        "env_template": out_dir / ".env.template",
        "manifest": out_dir / "manifest.json",
    }
    runbook = _render_runbook(
        base_url=args.base_url,
        commit=commit,
        repo_url=args.repo_url,
        files=files,
        repo_root=repo_root,
    )
    commands = _render_commands(base_url=args.base_url, commit=commit)
    env_template = "\n".join(
        [
            "ALIBABA_API_KEY=",
            "QWEN_VL_MODEL=qwen3-vl-flash",
            "ECS_REGION=",
            "ECS_INSTANCE_ID=",
            "ECS_PUBLIC_IP=",
            "BASE_URL=",
            "",
        ]
    )

    generated_text = "\n".join([runbook, commands, env_template])
    if _contains_secret_material(generated_text):
        print("generated operator pack would contain secret material; aborting", file=sys.stderr)
        return 2

    files["runbook"].write_text(runbook, encoding="utf-8")
    files["commands"].write_text(commands, encoding="utf-8")
    files["commands"].chmod(files["commands"].stat().st_mode | stat.S_IXUSR)
    files["env_template"].write_text(env_template, encoding="utf-8")
    pass_conditions = {
        "deployed_commit_is_git_oid": _is_git_oid(commit),
        "runbook_written": files["runbook"].is_file(),
        "commands_script_written": files["commands"].is_file(),
        "env_template_written": files["env_template"].is_file(),
        "generated_text_contains_no_secret_material": not _contains_secret_material(generated_text),
    }
    manifest: dict[str, Any] = {
        "schema_version": PACK_SCHEMA_VERSION,
        "outcome": "PENDING",
        "base_url": args.base_url,
        "deployed_commit": commit,
        "files": {
            name: _display_path(repo_root, path)
            for name, path in files.items()
        },
        "code_file_links": _code_file_links(repo_url=args.repo_url, commit=commit),
        "operator_proof_required": [
            "ECS region and OS image",
            "ECS instance ID",
            "ECS public IP",
            "public endpoint base URL",
            "deployed commit SHA",
            "Docker build command",
            "Docker run command or service unit",
            "sanitized collect-ecs-smoke-report output",
            "runs/ecs/ecs_smoke_report.json with outcome GO and proof_mode ecs-public",
            "terminal screenshot or transcript showing execution against the Alibaba ECS public endpoint",
        ],
        "pass_conditions": pass_conditions,
        "non_claims": [
            "not an ECS deployment proof until run on Alibaba ECS",
            "not a production hosting claim",
            "not a public availability claim",
            "not a latency or reliability claim",
            "not physical robot behavior",
            "not SO-101 operation",
            "not Qwen onboard execution",
        ],
    }
    pass_conditions["manifest_contains_no_secret_material"] = not _contains_secret_material(
        canonical_json(manifest)
    )
    manifest["outcome"] = "GO" if all(pass_conditions.values()) else "NARROW_CLAIM"
    files["manifest"].write_text(canonical_json(manifest) + "\n", encoding="utf-8")

    print(f"outcome {manifest['outcome']}")
    print(f"manifest {_display_path(repo_root, files['manifest'])}")
    print(f"runbook {_display_path(repo_root, files['runbook'])}")
    print(f"commands {_display_path(repo_root, files['commands'])}")
    print(f"env_template {_display_path(repo_root, files['env_template'])}")
    return 0 if manifest["outcome"] == "GO" else 4


def _render_runbook(
    *,
    base_url: str,
    commit: str,
    repo_url: str,
    files: dict[str, Path],
    repo_root: Path,
) -> str:
    code_links = _code_file_links(repo_url=repo_url, commit=commit)
    return "\n".join(
        [
            "# Alibaba ECS Operator Proof Pack",
            "",
            "This pack is for the operator running the Alibaba ECS proof. It does",
            "not contain credentials and is not itself a deployment proof.",
            "",
            "## Pinned Inputs",
            "",
            f"- Commit: `{commit}`",
            f"- Expected ECS public base URL: `{base_url}`",
            "- Secrets: create `.env` from `.env.template` on the ECS host only.",
            "- Metadata: fill `ECS_REGION`, `ECS_INSTANCE_ID`, `ECS_PUBLIC_IP`,",
            "  and optionally `BASE_URL` in `.env` before running the command",
            "  script. If `BASE_URL` is blank, the script derives it from",
            "  `ECS_PUBLIC_IP`.",
            "",
            "## Files",
            "",
            f"- Runbook: `{_display_path(repo_root, files['runbook'])}`",
            f"- Commands: `{_display_path(repo_root, files['commands'])}`",
            f"- Non-secret env template: `{_display_path(repo_root, files['env_template'])}`",
            f"- Manifest: `{_display_path(repo_root, files['manifest'])}`",
            "",
            "## Operator Steps",
            "",
            "1. Provision an Alibaba ECS Linux host.",
            "2. Configure security groups so SSH and port 8000 are only available",
            "   to the operator IP during proof capture.",
            "3. Clone the repository and check out the pinned commit.",
            "4. Copy `.env.template` to `.env` on the ECS host and fill",
            "   `ALIBABA_API_KEY`, `ECS_REGION`, `ECS_INSTANCE_ID`, and",
            "   `ECS_PUBLIC_IP`. Leave `BASE_URL` blank to derive it from",
            "   `ECS_PUBLIC_IP`, or set it to the ECS public IP-literal URL.",
            "5. Run `operator_commands.sh` from the repository root. The collector",
            "   must run in `ecs-public` mode against `BASE_URL`, not localhost.",
            "6. Save `runs/ecs/ecs_smoke_report.json` only if it contains",
            "   `\"outcome\":\"GO\"` and `\"proof_mode\":\"ecs-public\"`.",
            "7. Record region, instance ID, public IP, OS image, deployed commit,",
            "   command transcript, and a terminal screenshot showing the proof",
            "   ran against the Alibaba ECS public endpoint.",
            "",
            "## Code File Links",
            "",
            f"- Dockerfile: {code_links['dockerfile']}",
            f"- Server: {code_links['server']}",
            f"- ECS collector: {code_links['ecs_collector']}",
            f"- DashScope client: {code_links['dashscope_client']}",
            "",
            "## Non-Claims",
            "",
            "- Not a deployment proof until these commands run on Alibaba ECS.",
            "- Not a production hosting, latency, reliability, safety, SO-101,",
            "  physical robot, or Qwen-onboard claim.",
            "",
        ]
    )


def _render_commands(*, base_url: str, commit: str) -> str:
    quoted_commit = _shell_single_quote(commit)
    quoted_base_url = _shell_single_quote(base_url)
    return "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            "",
            'PACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"',
            'if ! REPO_ROOT="$(git -C "${PACK_DIR}" rev-parse --show-toplevel 2>/dev/null)"; then',
            '  echo "could not find repository root from ${PACK_DIR}" >&2',
            "  exit 2",
            "fi",
            'ENV_FILE="${REPO_ROOT}/.env"',
            'cd "${REPO_ROOT}"',
            "",
            'if [ -z "${COMMIT:-}" ]; then',
            f"  COMMIT={quoted_commit}",
            "fi",
            f"PACK_DEFAULT_BASE_URL={quoted_base_url}",
            "",
            'if [ ! -f "${ENV_FILE}" ]; then',
            '  echo "missing .env; copy ${PACK_DIR}/.env.template to .env and fill it on the ECS host" >&2',
            "  exit 2",
            "fi",
            "",
            'env_value() {',
            '  awk -F= -v key="$1" \'$1 == key {sub(/^[^=]*=/, ""); print; exit}\' "${ENV_FILE}"',
            '}',
            "",
            "if ! awk -F= '$1 == \"ALIBABA_API_KEY\" && length($2) > 0 {found=1} END {exit found ? 0 : 1}' \"${ENV_FILE}\"; then",
            '  echo "ALIBABA_API_KEY is empty in .env" >&2',
            "  exit 2",
            "fi",
            "",
            'ECS_REGION="${ECS_REGION:-$(env_value ECS_REGION)}"',
            'ECS_INSTANCE_ID="${ECS_INSTANCE_ID:-$(env_value ECS_INSTANCE_ID)}"',
            'ECS_PUBLIC_IP="${ECS_PUBLIC_IP:-$(env_value ECS_PUBLIC_IP)}"',
            'BASE_URL="${BASE_URL:-$(env_value BASE_URL)}"',
            'if [ -z "${BASE_URL}" ]; then',
            '  BASE_URL="${PACK_DEFAULT_BASE_URL}"',
            "fi",
            'if [ "${BASE_URL}" = "http://<ECS_PUBLIC_IP>:8000" ] && [ -n "${ECS_PUBLIC_IP}" ]; then',
            '  if [[ "${ECS_PUBLIC_IP}" == *:* ]]; then',
            '    BASE_URL="http://[${ECS_PUBLIC_IP}]:8000"',
            "  else",
            '    BASE_URL="http://${ECS_PUBLIC_IP}:8000"',
            "  fi",
            "fi",
            'if printf "%s" "${BASE_URL}" | grep -Eiq "^https?://(localhost|127\\\\.|0\\\\.0\\\\.0\\\\.0|\\\\[?::1\\\\]?)(:|/|$)"; then',
            '  echo "BASE_URL must be the Alibaba ECS public IP/DNS for proof capture" >&2',
            "  exit 2",
            "fi",
            'if [ -z "${ECS_REGION}" ] || [ -z "${ECS_INSTANCE_ID}" ] || [ -z "${ECS_PUBLIC_IP}" ] || [ -z "${BASE_URL}" ]; then',
            '  echo "ECS_REGION, ECS_INSTANCE_ID, ECS_PUBLIC_IP, and BASE_URL must be set in .env or environment" >&2',
            "  exit 2",
            "fi",
            "",
            'echo "checking out ${COMMIT}"',
            'git fetch --all --tags --prune',
            'git checkout "${COMMIT}"',
            "",
            'echo "building accountable-swarm:ecs"',
            "docker build -t accountable-swarm:ecs .",
            "",
            'cat <<\'EONEXT\'',
            "Start the container in another terminal on the ECS host:",
            "",
            "docker run --rm --env-file .env -p 8000:8000 accountable-swarm:ecs",
            "",
            "Then return to this terminal and press Enter.",
            "EONEXT",
            "read -r _",
            "",
            'mkdir -p runs/ecs',
            'python3 -m scripts.collect_ecs_smoke_report \\',
            '  --base-url "${BASE_URL}" \\',
            '  --commit "${COMMIT}" \\',
            '  --proof-mode ecs-public \\',
            '  --ecs-region "${ECS_REGION}" \\',
            '  --ecs-instance-id "${ECS_INSTANCE_ID}" \\',
            '  --ecs-public-ip "${ECS_PUBLIC_IP}" \\',
            '  --out runs/ecs/ecs_smoke_report.json',
            'python3 -m json.tool runs/ecs/ecs_smoke_report.json',
            "",
        ]
    )


def _code_file_links(*, repo_url: str, commit: str) -> dict[str, str]:
    normalized = repo_url.rstrip("/")
    return {
        "dockerfile": f"{normalized}/blob/{commit}/Dockerfile",
        "server": f"{normalized}/blob/{commit}/scripts/serve_demo.py",
        "ecs_collector": f"{normalized}/blob/{commit}/scripts/collect_ecs_smoke_report.py",
        "dashscope_client": f"{normalized}/blob/{commit}/accountable_swarm/qwen/client.py",
    }


def _contains_secret_material(value: str) -> bool:
    return any(pattern.search(value) for pattern in SECRET_PATTERNS)


def _has_control_chars(value: str) -> bool:
    return any(ord(character) < 32 for character in value)


def _shell_single_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _repo_path(repo_root: Path, path: Path) -> Path:
    if path.is_absolute():
        raise ValueError("output paths must be repository-relative")
    repo_root_resolved = repo_root.resolve()
    resolved = (repo_root_resolved / path).resolve()
    try:
        resolved.relative_to(repo_root_resolved)
    except ValueError as exc:
        raise ValueError("output paths must stay inside the repository checkout") from exc
    return resolved


def _display_path(repo_root: Path, path: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def _find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (
            (candidate / "pyproject.toml").is_file()
            and (candidate / "Dockerfile").is_file()
            and (candidate / "scripts" / "collect_ecs_smoke_report.py").is_file()
        ):
            return candidate
    raise ValueError("run from an accountable-swarm checkout containing pyproject.toml and Dockerfile")


def _git_head(repo_root: Path) -> str:
    git = shutil.which("git")
    if git is None:
        return "unknown"
    try:
        result = subprocess.run(
            [git, "rev-parse", "HEAD"],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    head = result.stdout.strip()
    return head if result.returncode == 0 and _is_git_oid(head) else "unknown"


def _is_git_oid(value: str) -> bool:
    if len(value) not in {40, 64}:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
