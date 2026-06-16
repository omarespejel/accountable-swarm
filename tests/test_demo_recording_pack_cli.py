from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "prepare_demo_recording_pack.py"


class DemoRecordingPackCliTests(TestCase):
    def test_prepare_recording_pack_writes_manifest_and_shotlist(self) -> None:
        module = _load_module()

        def fake_run_command(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
            self.assertEqual(cwd, ROOT)
            if "scripts/build_swarm_demo_bundle.py" in args:
                out_dir = ROOT / args[args.index("--out-dir") + 1]
                out_dir.mkdir(parents=True)
                (out_dir / "index.html").write_text("<!doctype html><title>swarm</title>", encoding="utf-8")
                (out_dir / "summary.json").write_text('{"outcome":"GO"}\n', encoding="utf-8")
                return subprocess.CompletedProcess(
                    args=args,
                    returncode=0,
                    stdout="outcome GO\nAuthorization: Bearer sk-testtoken123\n",
                    stderr="",
                )
            if "scripts.run_hazard_formation_gate" in args:
                trace_dir = ROOT / args[args.index("--trace-dir") + 1]
                report_path = ROOT / args[args.index("--report-out") + 1]
                trace_dir.mkdir(parents=True)
                (trace_dir / "hazard.json").write_text('{"trace":"placeholder"}\n', encoding="utf-8")
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report_path.write_text(
                    '{"outcome":"GO","grid":{"width":7,"height":5},"hazard":{"cell":{"x":3,"y":2}}}\n',
                    encoding="utf-8",
                )
                return subprocess.CompletedProcess(
                    args=args,
                    returncode=0,
                    stdout="outcome GO\n",
                    stderr="ALIBABA_API_KEY=sk-anothertesttoken\n",
                )
            if "scripts/render_swarm_trace_html.py" in args:
                self.assertIn("--obstacle", args)
                self.assertEqual(args[args.index("--obstacle") + 1], "3,2")
                html_path = ROOT / args[args.index("--html-out") + 1]
                summary_path = ROOT / args[args.index("--summary-out") + 1]
                html_path.parent.mkdir(parents=True, exist_ok=True)
                html_path.write_text("<!doctype html><title>hazard replay</title>", encoding="utf-8")
                summary_path.write_text('{"outcome":"GO"}\n', encoding="utf-8")
                return subprocess.CompletedProcess(
                    args=args,
                    returncode=0,
                    stdout="outcome GO\n",
                    stderr="",
                )
            raise AssertionError(f"unexpected command: {args}")

        test_root = ROOT / "runs" / "demo"
        test_root.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=test_root) as tmpdir:
            out_dir = Path(tmpdir) / "recording-pack"
            bundle_dir = Path(tmpdir) / "swarm"
            hazard_trace_dir = Path(tmpdir) / "hazard"
            hazard_report = Path(tmpdir) / "hazard_report.json"
            hazard_replay_dir = Path(tmpdir) / "hazard_replay"
            argv = [
                "prepare_demo_recording_pack.py",
                "--out-dir",
                str(out_dir.relative_to(ROOT)),
                "--bundle-dir",
                str(bundle_dir.relative_to(ROOT)),
                "--hazard-trace-dir",
                str(hazard_trace_dir.relative_to(ROOT)),
                "--hazard-report",
                str(hazard_report.relative_to(ROOT)),
                "--hazard-replay-dir",
                str(hazard_replay_dir.relative_to(ROOT)),
            ]
            with (
                patch.object(module, "_run_command", side_effect=fake_run_command),
                patch.object(sys, "argv", argv),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                returncode = module.main()

            self.assertEqual(returncode, 0)
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            shotlist = (out_dir / "shotlist.md").read_text(encoding="utf-8")

        self.assertEqual(manifest["schema_version"], "demo-recording-pack-report.v1")
        self.assertEqual(manifest["outcome"], "GO")
        self.assertTrue(all(manifest["pass_conditions"].values()))
        self.assertEqual(len(manifest["commands"]), 3)
        self.assertEqual(manifest["artifacts"]["bundle_index"], bundle_dir.relative_to(ROOT).as_posix() + "/index.html")
        self.assertEqual(
            manifest["artifacts"]["hazard_replay_html"],
            hazard_replay_dir.relative_to(ROOT).as_posix() + "/index.html",
        )
        self.assertIn("http://127.0.0.1:8000/swarm-demo", manifest["serve"]["urls"])
        self.assertIn("http://127.0.0.1:8000/hazard-formation", manifest["serve"]["urls"])
        self.assertEqual(manifest["key_material_redacted_count"], 2)
        self.assertTrue(manifest["pass_conditions"]["manifest_contains_no_key_material"])
        self.assertIn("Authorization: Bearer <redacted>", manifest["commands"][0]["stdout_tail"])
        self.assertIn("ALIBABA_API_KEY=<redacted>", manifest["commands"][1]["stderr_tail"])
        self.assertNotIn("sk-", json.dumps(manifest, sort_keys=True))
        self.assertFalse(module._contains_secret_material(json.dumps(manifest, sort_keys=True)))
        self.assertIn("no DimOS integration", shotlist)
        self.assertIn("Open the animated swarm replay", shotlist)

    def test_prepare_recording_pack_writes_narrow_manifest_when_children_fail(self) -> None:
        module = _load_module()

        def failed_run(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(args=args, returncode=9, stdout="", stderr="failed")

        test_root = ROOT / "runs" / "demo"
        test_root.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=test_root) as tmpdir:
            out_dir = Path(tmpdir) / "recording-pack"
            bundle_dir = Path(tmpdir) / "swarm"
            hazard_trace_dir = Path(tmpdir) / "hazard"
            hazard_report = Path(tmpdir) / "hazard_report.json"
            hazard_replay_dir = Path(tmpdir) / "hazard_replay"
            argv = [
                "prepare_demo_recording_pack.py",
                "--out-dir",
                str(out_dir.relative_to(ROOT)),
                "--bundle-dir",
                str(bundle_dir.relative_to(ROOT)),
                "--hazard-trace-dir",
                str(hazard_trace_dir.relative_to(ROOT)),
                "--hazard-report",
                str(hazard_report.relative_to(ROOT)),
                "--hazard-replay-dir",
                str(hazard_replay_dir.relative_to(ROOT)),
            ]
            with (
                patch.object(module, "_run_command", side_effect=failed_run),
                patch.object(sys, "argv", argv),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                returncode = module.main()

            self.assertEqual(returncode, 4)
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["outcome"], "NARROW_CLAIM")
        self.assertFalse(manifest["pass_conditions"]["bundle_command_succeeded"])
        self.assertFalse(manifest["pass_conditions"]["bundle_summary_go"])
        self.assertFalse(manifest["pass_conditions"]["hazard_command_succeeded"])
        self.assertFalse(manifest["pass_conditions"]["hazard_report_exists"])
        self.assertEqual(manifest["commands"][0]["stderr_tail"], ["failed"])

    def test_prepare_recording_pack_records_child_timeout_as_narrow_claim(self) -> None:
        module = _load_module()

        def timeout_result(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                args=args,
                returncode=124,
                stdout="partial stdout",
                stderr="partial stderr\ncommand timed out after 7s",
            )

        test_root = ROOT / "runs" / "demo"
        test_root.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=test_root) as tmpdir:
            out_dir = Path(tmpdir) / "recording-pack"
            bundle_dir = Path(tmpdir) / "swarm"
            hazard_trace_dir = Path(tmpdir) / "hazard"
            hazard_report = Path(tmpdir) / "hazard_report.json"
            hazard_replay_dir = Path(tmpdir) / "hazard_replay"
            argv = [
                "prepare_demo_recording_pack.py",
                "--out-dir",
                str(out_dir.relative_to(ROOT)),
                "--bundle-dir",
                str(bundle_dir.relative_to(ROOT)),
                "--hazard-trace-dir",
                str(hazard_trace_dir.relative_to(ROOT)),
                "--hazard-report",
                str(hazard_report.relative_to(ROOT)),
                "--hazard-replay-dir",
                str(hazard_replay_dir.relative_to(ROOT)),
            ]
            with (
                patch.object(module, "_run_command", side_effect=timeout_result),
                patch.object(sys, "argv", argv),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                returncode = module.main()

            self.assertEqual(returncode, 4)
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["outcome"], "NARROW_CLAIM")
        self.assertEqual(manifest["commands"][0]["returncode"], 124)
        self.assertFalse(manifest["pass_conditions"]["bundle_command_succeeded"])
        self.assertFalse(manifest["pass_conditions"]["hazard_command_succeeded"])
        self.assertIn("command timed out after 7s", manifest["commands"][0]["stderr_tail"])

    def test_prepare_recording_pack_treats_invalid_json_as_narrow_claim(self) -> None:
        module = _load_module()

        def invalid_json_run(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
            self.assertEqual(cwd, ROOT)
            if "scripts/build_swarm_demo_bundle.py" in args:
                out_dir = ROOT / args[args.index("--out-dir") + 1]
                out_dir.mkdir(parents=True)
                (out_dir / "index.html").write_text("<!doctype html><title>swarm</title>", encoding="utf-8")
                (out_dir / "summary.json").write_text("{not json", encoding="utf-8")
            if "scripts.run_hazard_formation_gate" in args:
                trace_dir = ROOT / args[args.index("--trace-dir") + 1]
                report_path = ROOT / args[args.index("--report-out") + 1]
                trace_dir.mkdir(parents=True)
                (trace_dir / "hazard.json").write_text('{"trace":"placeholder"}\n', encoding="utf-8")
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report_path.write_text("{not json", encoding="utf-8")
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        test_root = ROOT / "runs" / "demo"
        test_root.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=test_root) as tmpdir:
            out_dir = Path(tmpdir) / "recording-pack"
            bundle_dir = Path(tmpdir) / "swarm"
            hazard_trace_dir = Path(tmpdir) / "hazard"
            hazard_report = Path(tmpdir) / "hazard_report.json"
            hazard_replay_dir = Path(tmpdir) / "hazard_replay"
            argv = [
                "prepare_demo_recording_pack.py",
                "--out-dir",
                str(out_dir.relative_to(ROOT)),
                "--bundle-dir",
                str(bundle_dir.relative_to(ROOT)),
                "--hazard-trace-dir",
                str(hazard_trace_dir.relative_to(ROOT)),
                "--hazard-report",
                str(hazard_report.relative_to(ROOT)),
                "--hazard-replay-dir",
                str(hazard_replay_dir.relative_to(ROOT)),
            ]
            with (
                patch.object(module, "_run_command", side_effect=invalid_json_run),
                patch.object(sys, "argv", argv),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                returncode = module.main()

            self.assertEqual(returncode, 4)
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["outcome"], "NARROW_CLAIM")
        self.assertFalse(manifest["pass_conditions"]["bundle_summary_go"])
        self.assertFalse(manifest["pass_conditions"]["hazard_report_accepted_outcome"])
        self.assertTrue(manifest["pass_conditions"]["manifest_contains_no_key_material"])

    def test_prepare_recording_pack_treats_non_object_json_as_narrow_claim(self) -> None:
        module = _load_module()

        def array_json_run(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
            self.assertEqual(cwd, ROOT)
            if "scripts/build_swarm_demo_bundle.py" in args:
                out_dir = ROOT / args[args.index("--out-dir") + 1]
                out_dir.mkdir(parents=True)
                (out_dir / "index.html").write_text("<!doctype html><title>swarm</title>", encoding="utf-8")
                (out_dir / "summary.json").write_text("[]\n", encoding="utf-8")
            if "scripts.run_hazard_formation_gate" in args:
                trace_dir = ROOT / args[args.index("--trace-dir") + 1]
                report_path = ROOT / args[args.index("--report-out") + 1]
                trace_dir.mkdir(parents=True)
                (trace_dir / "hazard.json").write_text('{"trace":"placeholder"}\n', encoding="utf-8")
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report_path.write_text("[]\n", encoding="utf-8")
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        test_root = ROOT / "runs" / "demo"
        test_root.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=test_root) as tmpdir:
            out_dir = Path(tmpdir) / "recording-pack"
            bundle_dir = Path(tmpdir) / "swarm"
            hazard_trace_dir = Path(tmpdir) / "hazard"
            hazard_report = Path(tmpdir) / "hazard_report.json"
            hazard_replay_dir = Path(tmpdir) / "hazard_replay"
            argv = [
                "prepare_demo_recording_pack.py",
                "--out-dir",
                str(out_dir.relative_to(ROOT)),
                "--bundle-dir",
                str(bundle_dir.relative_to(ROOT)),
                "--hazard-trace-dir",
                str(hazard_trace_dir.relative_to(ROOT)),
                "--hazard-report",
                str(hazard_report.relative_to(ROOT)),
                "--hazard-replay-dir",
                str(hazard_replay_dir.relative_to(ROOT)),
            ]
            with (
                patch.object(module, "_run_command", side_effect=array_json_run),
                patch.object(sys, "argv", argv),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                returncode = module.main()

            self.assertEqual(returncode, 4)
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["outcome"], "NARROW_CLAIM")
        self.assertFalse(manifest["pass_conditions"]["bundle_summary_go"])
        self.assertFalse(manifest["pass_conditions"]["hazard_report_accepted_outcome"])

    def test_run_command_returns_completed_process_on_timeout(self) -> None:
        module = _load_module()

        def timeout_run(*args, **kwargs):
            raise subprocess.TimeoutExpired(
                cmd=args[0],
                timeout=kwargs["timeout"],
                output="partial stdout",
                stderr=b"partial stderr",
            )

        with patch.object(module.subprocess, "run", side_effect=timeout_run):
            result = module._run_command(["python3", "child.py"], cwd=ROOT, timeout_seconds=7)

        self.assertEqual(result.returncode, 124)
        self.assertEqual(result.stdout, "partial stdout")
        self.assertIn("partial stderr", result.stderr)
        self.assertIn("command timed out after 7s", result.stderr)

    def test_run_command_retries_retryable_spawn_error(self) -> None:
        module = _load_module()
        completed = subprocess.CompletedProcess(
            args=["python3", "child.py"],
            returncode=0,
            stdout="ok",
            stderr="",
        )
        calls = [
            BlockingIOError(35, "Resource temporarily unavailable"),
            completed,
        ]

        def flaky_run(*args, **kwargs):
            result = calls.pop(0)
            if isinstance(result, BaseException):
                raise result
            return result

        with (
            patch.object(module.subprocess, "run", side_effect=flaky_run),
            patch.object(module.time, "sleep"),
        ):
            result = module._run_command(["python3", "child.py"], cwd=ROOT, timeout_seconds=7)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "ok")
        self.assertFalse(calls)

    def test_run_command_returns_completed_process_on_persistent_spawn_error(self) -> None:
        module = _load_module()

        def failed_spawn(*args, **kwargs):
            raise BlockingIOError(35, "Resource temporarily unavailable")

        with (
            patch.object(module.subprocess, "run", side_effect=failed_spawn),
            patch.object(module.time, "sleep"),
        ):
            result = module._run_command(["python3", "child.py"], cwd=ROOT, timeout_seconds=7)

        self.assertEqual(result.returncode, 125)
        self.assertEqual(result.stdout, "")
        self.assertIn("spawn failed", result.stderr)
        self.assertIn("Resource temporarily unavailable", result.stderr)

    def test_installed_entrypoint_resolves_repo_from_current_working_tree(self) -> None:
        module = _load_module()
        self.assertEqual(module._find_repo_root(ROOT / "docs" / "submission"), ROOT)


def _load_module():
    spec = importlib.util.spec_from_file_location("prepare_demo_recording_pack_for_test", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load recording pack script")
    module = importlib.util.module_from_spec(spec)
    original_sys_path = list(sys.path)
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = original_sys_path
    return module
