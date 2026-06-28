from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "prepare_ecs_operator_pack.py"
COMMIT = "c" * 40


class EcsOperatorPackCliTests(TestCase):
    def test_prepare_ecs_operator_pack_writes_non_secret_manifest(self) -> None:
        module = _load_module()
        test_root = ROOT / "runs" / "ecs"
        test_root.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=test_root) as tmpdir:
            out_dir = Path(tmpdir) / "operator-pack"
            argv = [
                "prepare_ecs_operator_pack.py",
                "--out-dir",
                str(out_dir.relative_to(ROOT)),
                "--base-url",
                "http://127.0.0.1:8000",
                "--commit",
                COMMIT,
            ]
            with patch.object(sys, "argv", argv):
                returncode = module.main()

            self.assertEqual(returncode, 0)
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            runbook = (out_dir / "README.md").read_text(encoding="utf-8")
            commands = (out_dir / "operator_commands.sh").read_text(encoding="utf-8")
            env_template = (out_dir / ".env.template").read_text(encoding="utf-8")

        self.assertEqual(manifest["schema_version"], "ecs-operator-proof-pack.v1")
        self.assertEqual(manifest["outcome"], "GO")
        self.assertTrue(all(manifest["pass_conditions"].values()))
        self.assertEqual(manifest["deployed_commit"], COMMIT)
        self.assertIn(f"/blob/{COMMIT}/Dockerfile", manifest["code_file_links"]["dockerfile"])
        self.assertIn("runs/ecs/ecs_smoke_report.json", runbook)
        self.assertIn('"proof_mode":"ecs-public"', runbook)
        self.assertIn("collect_ecs_smoke_report", commands)
        self.assertIn("--proof-mode ecs-public", commands)
        self.assertIn("--ecs-region", commands)
        self.assertIn("--ecs-instance-id", commands)
        self.assertIn("--ecs-public-ip", commands)
        self.assertIn('REPO_ROOT="$(git -C "${PACK_DIR}" rev-parse --show-toplevel', commands)
        self.assertIn('ENV_FILE="${REPO_ROOT}/.env"', commands)
        self.assertIn('cd "${REPO_ROOT}"', commands)
        self.assertIn("PACK_DEFAULT_BASE_URL=", commands)
        self.assertIn('if [ "${BASE_URL}" = "http://<ECS_PUBLIC_IP>:8000" ]', commands)
        self.assertIn('if [[ "${ECS_PUBLIC_IP}" == *:* ]]; then', commands)
        self.assertIn('BASE_URL="http://[${ECS_PUBLIC_IP}]:8000"', commands)
        self.assertIn('BASE_URL="http://${ECS_PUBLIC_IP}:8000"', commands)
        self.assertIn("BASE_URL must be the Alibaba ECS public IP/DNS for proof capture", commands)
        self.assertIn('PACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"', commands)
        self.assertIn("${PACK_DIR}/.env.template", commands)
        self.assertIn("${ENV_FILE}", commands)
        self.assertNotIn("copy runs/ecs/operator-pack/.env.template", commands)
        self.assertEqual(
            env_template,
            "ALIBABA_API_KEY=\n"
            "QWEN_VL_MODEL=qwen3-vl-flash\n"
            "ECS_REGION=\n"
            "ECS_INSTANCE_ID=\n"
            "ECS_PUBLIC_IP=\n"
            "BASE_URL=\n",
        )
        combined = json.dumps(manifest, sort_keys=True) + runbook + commands + env_template
        self.assertFalse(module._contains_secret_material(combined))

    def test_prepare_ecs_operator_pack_narrows_for_malformed_commit(self) -> None:
        module = _load_module()
        test_root = ROOT / "runs" / "ecs"
        test_root.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=test_root) as tmpdir:
            out_dir = Path(tmpdir) / "operator-pack"
            argv = [
                "prepare_ecs_operator_pack.py",
                "--out-dir",
                str(out_dir.relative_to(ROOT)),
                "--commit",
                "not-a-commit",
            ]
            with patch.object(sys, "argv", argv):
                returncode = module.main()

            self.assertEqual(returncode, 4)
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["outcome"], "NARROW_CLAIM")
        self.assertFalse(manifest["pass_conditions"]["deployed_commit_is_git_oid"])

    def test_prepare_ecs_operator_pack_rejects_control_chars_before_writing(self) -> None:
        module = _load_module()
        test_root = ROOT / "runs" / "ecs"
        test_root.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=test_root) as tmpdir:
            out_dir = Path(tmpdir) / "operator-pack"
            argv = [
                "prepare_ecs_operator_pack.py",
                "--out-dir",
                str(out_dir.relative_to(ROOT)),
                "--commit",
                COMMIT,
                "--base-url",
                "http://127.0.0.1:8000\nuname",
            ]
            with patch.object(sys, "argv", argv):
                returncode = module.main()

            self.assertEqual(returncode, 2)
            self.assertFalse((out_dir / "manifest.json").exists())

    def test_prepare_ecs_operator_pack_rejects_output_path_escape(self) -> None:
        module = _load_module()
        test_root = ROOT / "runs" / "ecs"
        test_root.mkdir(parents=True, exist_ok=True)
        argv = [
            "prepare_ecs_operator_pack.py",
            "--out-dir",
            "../outside-accountable-swarm",
            "--commit",
            COMMIT,
        ]
        with patch.object(sys, "argv", argv):
            returncode = module.main()

        self.assertEqual(returncode, 2)

    def test_prepare_ecs_operator_pack_rejects_secret_patterns_before_writing(self) -> None:
        module = _load_module()
        test_root = ROOT / "runs" / "ecs"
        test_root.mkdir(parents=True, exist_ok=True)
        secret_cases = {
            "sk": "https://example.com/sk-secret-token-01234567890123456789",
            "github_pat": "https://example.com/github_pat_ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            "gho": "https://example.com/gho_abcdefghijklmno",
        }
        for label, repo_url in secret_cases.items():
            with self.subTest(label=label):
                with TemporaryDirectory(dir=test_root) as tmpdir:
                    out_dir = Path(tmpdir) / "operator-pack"
                    argv = [
                        "prepare_ecs_operator_pack.py",
                        "--out-dir",
                        str(out_dir.relative_to(ROOT)),
                        "--commit",
                        COMMIT,
                        "--repo-url",
                        repo_url,
                    ]
                    with patch.object(sys, "argv", argv):
                        returncode = module.main()

                    self.assertEqual(returncode, 2)
                    self.assertFalse((out_dir / "README.md").exists())
                    self.assertFalse((out_dir / "operator_commands.sh").exists())
                    self.assertFalse((out_dir / ".env.template").exists())
                    self.assertFalse((out_dir / "manifest.json").exists())

    def test_prepare_ecs_operator_pack_rejects_secret_like_out_dir_before_writing(self) -> None:
        module = _load_module()
        test_root = ROOT / "runs" / "ecs"
        test_root.mkdir(parents=True, exist_ok=True)
        out_dir = test_root / "operator-pack-gho_abcdefghijklmno"
        argv = [
            "prepare_ecs_operator_pack.py",
            "--out-dir",
            str(out_dir.relative_to(ROOT)),
            "--commit",
            COMMIT,
        ]
        with patch.object(sys, "argv", argv):
            returncode = module.main()

        self.assertEqual(returncode, 2)
        self.assertFalse((out_dir / "README.md").exists())
        self.assertFalse((out_dir / "operator_commands.sh").exists())
        self.assertFalse((out_dir / ".env.template").exists())
        self.assertFalse((out_dir / "manifest.json").exists())

    def test_prepare_ecs_operator_pack_rejects_bearer_redaction_prefix_bypass(self) -> None:
        module = _load_module()
        test_root = ROOT / "runs" / "ecs"
        test_root.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=test_root) as tmpdir:
            out_dir = Path(tmpdir) / "operator-pack"
            argv = [
                "prepare_ecs_operator_pack.py",
                "--out-dir",
                str(out_dir.relative_to(ROOT)),
                "--commit",
                COMMIT,
                "--repo-url",
                "https://example.com/Authorization: Bearer <redacted>gho_abcdefghijklmno",
            ]
            with patch.object(sys, "argv", argv):
                returncode = module.main()

            self.assertEqual(returncode, 2)
            self.assertFalse((out_dir / "README.md").exists())
            self.assertFalse((out_dir / "operator_commands.sh").exists())
            self.assertFalse((out_dir / ".env.template").exists())
            self.assertFalse((out_dir / "manifest.json").exists())

    def test_repo_path_rejects_absolute_paths(self) -> None:
        module = _load_module()
        with self.assertRaises(ValueError):
            module._repo_path(ROOT, ROOT / "runs" / "ecs" / "absolute-out")

    def test_shell_single_quote_escapes_embedded_quotes(self) -> None:
        module = _load_module()
        self.assertEqual(module._shell_single_quote("abc'def"), "'abc'\"'\"'def'")

    def test_find_repo_root_resolves_from_subdirectory(self) -> None:
        module = _load_module()
        self.assertEqual(module._find_repo_root(ROOT / "docs" / "engineering"), ROOT)


def _load_module():
    spec = importlib.util.spec_from_file_location("prepare_ecs_operator_pack_for_test", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load ECS operator pack script")
    module = importlib.util.module_from_spec(spec)
    original_sys_path = list(sys.path)
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = original_sys_path
    return module
