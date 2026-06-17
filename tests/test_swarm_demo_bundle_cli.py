from __future__ import annotations

import importlib.util
import errno
import json
from pathlib import Path
import subprocess
import sys
import time
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from accountable_swarm.swarm import scenario_names


ROOT = Path(__file__).resolve().parents[1]


class SwarmDemoBundleCliTests(TestCase):
    def test_bundle_generates_deterministic_reviewed_scenario_artifacts(self) -> None:
        with TemporaryDirectory(dir="/tmp") as first_tmp, TemporaryDirectory(dir="/tmp") as second_tmp:
            first_dir = Path(first_tmp) / "bundle"
            second_dir = Path(second_tmp) / "bundle"

            first = _run_bundle(first_dir)
            second = _run_bundle(second_dir)

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn("outcome GO", first.stdout)
            self.assertEqual(
                (first_dir / "index.html").read_text(encoding="utf-8"),
                (second_dir / "index.html").read_text(encoding="utf-8"),
            )
            first_summary = json.loads((first_dir / "summary.json").read_text(encoding="utf-8"))
            second_summary = json.loads((second_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(first_summary, second_summary)
            self.assertEqual(first_summary["schema_version"], "swarm-demo-bundle-report.v1")
            self.assertEqual(first_summary["outcome"], "GO")
            self.assertEqual(first_summary["scenario_count"], len(scenario_names()))
            self.assertEqual(first_summary["agent_count"], 4)
            self.assertEqual(first_summary["ticks"], 17)
            self.assertTrue(all(first_summary["pass_conditions"].values()))
            self.assertEqual(
                [case["scenario"] for case in first_summary["scenarios"]],
                list(scenario_names()),
            )

            index_html = (first_dir / "index.html").read_text(encoding="utf-8")
            self.assertNotIn(first_tmp, index_html)
            self.assertNotIn(first_tmp, json.dumps(first_summary, sort_keys=True))
            self.assertIn("Accountable Swarm Demo Bundle", index_html)
            self.assertIn("scenarios/center-block/replay.html", index_html)
            for case in first_summary["scenarios"]:
                self.assertEqual(case["sim_report"]["outcome"], "GO")
                self.assertEqual(case["render_summary"]["outcome"], "GO")
                self.assertTrue(all(case["pass_conditions"].values()))
                self.assertRegex(case["render_summary"]["html_sha256"], r"^[0-9a-f]{64}$")
                self.assertEqual(case["sim_report"]["same_cell_collision_count"], 0)
                self.assertEqual(case["sim_report"]["swap_collision_count"], 0)
                self.assertEqual(case["sim_report"]["obstacle_occupancy_violation_count"], 0)
                self.assertTrue((first_dir / case["files"]["sim_report"]).exists())
                self.assertTrue((first_dir / case["files"]["replay_html"]).exists())
                self.assertTrue((first_dir / case["files"]["replay_summary"]).exists())
                for trace_path in case["files"]["traces"].values():
                    self.assertTrue((first_dir / trace_path).exists())

            stale_trace = first_dir / "scenarios" / "center-block" / "traces" / "stale.json"
            stale_trace.write_text("{}", encoding="utf-8")
            rerun = _run_bundle(first_dir)
            self.assertEqual(rerun.returncode, 0, rerun.stderr)
            self.assertFalse(stale_trace.exists())
            self.assertEqual(
                first_summary,
                json.loads((first_dir / "summary.json").read_text(encoding="utf-8")),
            )

    def test_bundle_defaults_to_runs_demo_swarm(self) -> None:
        with TemporaryDirectory(dir="/tmp") as tmpdir:
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/build_swarm_demo_bundle.py"),
                ],
                cwd=tmpdir,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            out_dir = Path(tmpdir) / "runs/demo/swarm"
            self.assertTrue((out_dir / "index.html").exists())
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertIn("wrote runs/demo/swarm/index.html", result.stdout)

    def test_bundle_canonicalizes_reversed_reviewed_scenarios(self) -> None:
        with TemporaryDirectory(dir="/tmp") as tmpdir:
            out_dir = Path(tmpdir) / "bundle"
            args = []
            for scenario in reversed(scenario_names()):
                args.extend(["--scenario", scenario])

            result = _run_bundle(out_dir, *args)

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["outcome"], "GO")
            self.assertTrue(summary["pass_conditions"]["all_reviewed_scenarios_included"])
            self.assertEqual(
                [case["scenario"] for case in summary["scenarios"]],
                list(scenario_names()),
            )

    def test_bundle_surfaces_short_run_as_narrow_claim(self) -> None:
        with TemporaryDirectory(dir="/tmp") as tmpdir:
            out_dir = Path(tmpdir) / "bundle"

            result = _run_bundle(out_dir, "--scenario", "center-block", "--ticks", "1")

            self.assertEqual(result.returncode, 4)
            self.assertIn("outcome NARROW_CLAIM", result.stdout)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["outcome"], "NARROW_CLAIM")
            self.assertEqual(summary["scenario_count"], 1)
            self.assertFalse(summary["pass_conditions"]["all_reviewed_scenarios_included"])
            self.assertFalse(summary["pass_conditions"]["every_sim_report_go"])
            self.assertEqual(summary["scenarios"][0]["sim_report"]["outcome"], "NARROW_CLAIM")
            self.assertTrue((out_dir / "index.html").exists())

    def test_child_renderer_command_retries_transient_spawn_error(self) -> None:
        module = _load_bundle_module()
        calls = []

        def fake_run(*args, **kwargs):
            calls.append((args, kwargs))
            if len(calls) == 1:
                raise BlockingIOError(35, "Resource temporarily unavailable")
            return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="", stderr="")

        with (
            patch.object(module.subprocess, "run", side_effect=fake_run),
            patch.object(module.time, "sleep"),
        ):
            result = module._run_child_command(
                ["python3", "scripts/render_swarm_trace_html.py"],
                cwd=ROOT,
                timeout=1,
            )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(calls), 2)

    def test_child_renderer_command_does_not_retry_non_retryable_spawn_error(self) -> None:
        module = _load_bundle_module()
        calls = []

        def fake_run(*args, **kwargs):
            calls.append((args, kwargs))
            raise OSError(2, "No such file or directory")

        with (
            patch.object(module.subprocess, "run", side_effect=fake_run),
            patch.object(module.time, "sleep"),
        ):
            with self.assertRaises(OSError):
                module._run_child_command(
                    ["python3", "scripts/render_swarm_trace_html.py"],
                    cwd=ROOT,
                    timeout=1,
                )

        self.assertEqual(len(calls), 1)

    def test_child_renderer_command_raises_after_retry_budget(self) -> None:
        module = _load_bundle_module()
        calls = []

        def fake_run(*args, **kwargs):
            calls.append((args, kwargs))
            raise BlockingIOError(35, "Resource temporarily unavailable")

        with (
            patch.object(module.subprocess, "run", side_effect=fake_run),
            patch.object(module.time, "sleep"),
        ):
            with self.assertRaises(BlockingIOError):
                module._run_child_command(
                    ["python3", "scripts/render_swarm_trace_html.py"],
                    cwd=ROOT,
                    timeout=1,
                )

        self.assertEqual(len(calls), module.SUBPROCESS_SPAWN_ATTEMPTS)


def _run_bundle(out_dir: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
    args = [
        sys.executable,
        "scripts/build_swarm_demo_bundle.py",
        "--out-dir",
        str(out_dir),
        *extra_args,
    ]
    for attempt in range(5):
        try:
            result = subprocess.run(
                args,
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            if (
                result.returncode == 4
                and f"Errno {errno.EAGAIN}" in result.stderr
                and "Resource temporarily unavailable" in result.stderr
                and attempt < 4
            ):
                time.sleep(0.5)
                continue
            return result
        except OSError as exc:
            if not _is_retryable_spawn_error(exc) or attempt == 4:
                raise
            time.sleep(0.5)
    raise RuntimeError("unreachable bundle retry state")


def _is_retryable_spawn_error(exc: OSError) -> bool:
    return isinstance(exc, BlockingIOError) or exc.errno == errno.EAGAIN


def _load_bundle_module():
    spec = importlib.util.spec_from_file_location(
        "build_swarm_demo_bundle_under_test",
        ROOT / "scripts" / "build_swarm_demo_bundle.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    original_sys_path = list(sys.path)
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = original_sys_path
    return module
