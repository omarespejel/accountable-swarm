from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from accountable_swarm.trace.models import canonical_json


ROOT = Path(__file__).resolve().parents[1]


class DimosReplayConsumerCliTests(TestCase):
    def test_replay_consumer_writes_deterministic_report(self) -> None:
        module = _load_module()
        test_root = ROOT / "runs" / "dimos"
        test_root.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=test_root) as tmpdir:
            work_dir = Path(tmpdir)
            bridge_pack = _write_bridge_pack(work_dir / "bridge")
            report_out = work_dir / "report.json"
            dimos_checkout = _write_fake_dimos_checkout(work_dir / "dimos")
            argv = [
                "run_dimos_replay_consumer.py",
                "--bridge-pack",
                str(bridge_pack.relative_to(ROOT)),
                "--report-out",
                str(report_out.relative_to(ROOT)),
                "--dimos-checkout",
                str(dimos_checkout),
            ]

            with (
                patch.object(module, "_probe_dimos", return_value=_runtime_probe(source_outcome="GO")),
                patch.object(sys, "argv", argv),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                returncode = module.main()

            self.assertEqual(returncode, 0)
            report = json.loads(report_out.read_text(encoding="utf-8"))

        self.assertEqual(report["schema_version"], "dimos-replay-consumer-report.v1")
        self.assertEqual(report["consumer_outcome"], "GO")
        self.assertEqual(report["outcome"], "NARROW_CLAIM")
        self.assertEqual(report["scenario_count"], 1)
        self.assertEqual(report["scenarios"], ["corridor"])
        self.assertEqual(report["event_count"], 3)
        self.assertEqual(report["stream_count"], 2)
        self.assertEqual(report["first_tick"], 0)
        self.assertEqual(report["last_tick"], 1)
        self.assertTrue(report["dimos_runtime"]["source"]["checkout_exists"])
        self.assertEqual(report["dimos_runtime"]["source"]["source_outcome"], "GO")
        self.assertEqual(report["dimos_runtime"]["runtime_outcome"], "NARROW_CLAIM")
        self.assertNotIn(str(dimos_checkout), canonical_json(report))
        self.assertTrue(all(report["pass_conditions"].values()))
        self.assertEqual(report["streams"][0]["stream_hint"], "/accountable_swarm/corridor/agent-0/grid_pose")
        self.assertEqual(report["streams"][0]["first_position_cell"], {"x": 0, "y": 0})
        self.assertEqual(report["streams"][0]["last_position_cell"], {"x": 1, "y": 0})

    def test_replay_consumer_requires_runtime_when_requested(self) -> None:
        module = _load_module()
        test_root = ROOT / "runs" / "dimos"
        test_root.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=test_root) as tmpdir:
            work_dir = Path(tmpdir)
            bridge_pack = _write_bridge_pack(work_dir / "bridge")
            report_out = work_dir / "report.json"
            argv = [
                "run_dimos_replay_consumer.py",
                "--bridge-pack",
                str(bridge_pack.relative_to(ROOT)),
                "--report-out",
                str(report_out.relative_to(ROOT)),
                "--require-dimos-runtime",
            ]

            with (
                patch.object(module, "_probe_dimos", return_value=_runtime_probe()),
                patch.object(sys, "argv", argv),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                returncode = module.main()

            self.assertEqual(returncode, 4)
            report = json.loads(report_out.read_text(encoding="utf-8"))

        self.assertEqual(report["consumer_outcome"], "GO")
        self.assertEqual(report["outcome"], "NARROW_CLAIM")
        self.assertTrue(report["require_dimos_runtime"])
        self.assertEqual(report["dimos_runtime"]["runtime_outcome"], "NARROW_CLAIM")

    def test_replay_consumer_rejects_raw_float_in_timeline(self) -> None:
        module = _load_module()
        test_root = ROOT / "runs" / "dimos"
        test_root.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=test_root) as tmpdir:
            work_dir = Path(tmpdir)
            bridge_pack = _write_bridge_pack(work_dir / "bridge")
            report_out = work_dir / "report.json"
            event = _base_event(agent_id="agent-0", tick=0, x=0, y=0)
            event["position_cell"]["x"] = 0.25
            (bridge_pack / "timeline.ndjson").write_text(json.dumps(event, sort_keys=True) + "\n", encoding="utf-8")
            argv = [
                "run_dimos_replay_consumer.py",
                "--bridge-pack",
                str(bridge_pack.relative_to(ROOT)),
                "--report-out",
                str(report_out.relative_to(ROOT)),
            ]

            with (
                patch.object(sys, "argv", argv),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                returncode = module.main()

            self.assertEqual(returncode, 4)
            self.assertFalse(report_out.exists())

    def test_replay_consumer_rejects_manifest_timeline_mismatch(self) -> None:
        module = _load_module()
        test_root = ROOT / "runs" / "dimos"
        test_root.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=test_root) as tmpdir:
            work_dir = Path(tmpdir)
            bridge_pack = _write_bridge_pack(work_dir / "bridge")
            report_out = work_dir / "report.json"
            manifest_path = bridge_pack / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["event_count"] = 99
            manifest_path.write_text(canonical_json(manifest) + "\n", encoding="utf-8")
            argv = [
                "run_dimos_replay_consumer.py",
                "--bridge-pack",
                str(bridge_pack.relative_to(ROOT)),
                "--report-out",
                str(report_out.relative_to(ROOT)),
            ]

            with (
                patch.object(module, "_probe_dimos", return_value=_runtime_probe()),
                patch.object(sys, "argv", argv),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                returncode = module.main()

            self.assertEqual(returncode, 4)
            self.assertFalse(report_out.exists())

    def test_replay_consumer_rejects_out_of_order_stream_ticks(self) -> None:
        module = _load_module()
        test_root = ROOT / "runs" / "dimos"
        test_root.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=test_root) as tmpdir:
            work_dir = Path(tmpdir)
            bridge_pack = _write_bridge_pack(work_dir / "bridge")
            report_out = work_dir / "report.json"
            events = [
                _base_event(agent_id="agent-0", tick=1, x=1, y=0),
                _base_event(agent_id="agent-0", tick=0, x=0, y=0),
            ]
            (bridge_pack / "timeline.ndjson").write_text(
                "\n".join(canonical_json(event) for event in events) + "\n",
                encoding="utf-8",
            )
            argv = [
                "run_dimos_replay_consumer.py",
                "--bridge-pack",
                str(bridge_pack.relative_to(ROOT)),
                "--report-out",
                str(report_out.relative_to(ROOT)),
            ]

            with (
                patch.object(sys, "argv", argv),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                returncode = module.main()

            self.assertEqual(returncode, 4)
            self.assertFalse(report_out.exists())

    def test_replay_consumer_rejects_escaped_paths(self) -> None:
        module = _load_module()
        with self.assertRaises(ValueError):
            module._repo_path(ROOT, Path("../outside"))
        with self.assertRaises(ValueError):
            module._repo_path(ROOT, ROOT.parent / "outside")


def _write_bridge_pack(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    events = [
        _base_event(agent_id="agent-0", tick=0, x=0, y=0),
        _base_event(agent_id="agent-0", tick=1, x=1, y=0),
        _base_event(agent_id="agent-1", tick=0, x=4, y=2),
    ]
    manifest = {
        "schema_version": "dimos-bridge-pack-report.v1",
        "outcome": "GO",
        "bridge_outcome": "GO",
        "source_bundle": "runs/demo/test",
        "artifacts": {
            "manifest": path.relative_to(ROOT).as_posix() + "/manifest.json",
            "timeline_ndjson": path.relative_to(ROOT).as_posix() + "/timeline.ndjson",
        },
        "scenario_count": 1,
        "scenarios": ["corridor"],
        "event_count": len(events),
        "agent_count": 2,
        "dimos_probe": {"runtime_outcome": "NARROW_CLAIM"},
        "pass_conditions": {"test_bridge": True},
        "non_claims": ["no DimOS execution"],
    }
    (path / "manifest.json").write_text(canonical_json(manifest) + "\n", encoding="utf-8")
    (path / "timeline.ndjson").write_text(
        "\n".join(canonical_json(event) for event in events) + "\n",
        encoding="utf-8",
    )
    return path


def _base_event(*, agent_id: str, tick: int, x: int, y: int) -> dict[str, object]:
    return {
        "schema_version": "dimos-swarm-replay-event.v1",
        "source": "accountable_swarm_decisiontrace",
        "scenario": "corridor",
        "tick": tick,
        "agent_id": agent_id,
        "position_cell": {"x": x, "y": y},
        "grid": {"width": 5, "height": 3},
        "decision": "MOVE",
        "event_sha256": "a" * 64,
        "trace_summary_sha": "b" * 64,
        "dimos_stream_hint": f"/accountable_swarm/corridor/{agent_id}/grid_pose",
    }


def _write_fake_dimos_checkout(path: Path) -> Path:
    required = [
        "AGENTS.md",
        "dimos/core/module.py",
        "dimos/core/stream.py",
        "dimos/core/coordination/blueprints.py",
        "dimos/visualization/rerun/bridge.py",
    ]
    for relative in required:
        target = path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# fake DimOS file for replay consumer tests\n", encoding="utf-8")
    return path


def _runtime_probe(*, source_outcome: str = "NARROW_CLAIM") -> dict[str, object]:
    return {
        "source": {
            "checkout_provided": source_outcome == "GO",
            "checkout_exists": source_outcome == "GO",
            "source_name": "dimos" if source_outcome == "GO" else None,
            "required_files_present": {},
            "source_outcome": source_outcome,
        },
        "python_import_available": False,
        "cli_available": False,
        "rerun_import_available": False,
        "runtime_outcome": "NARROW_CLAIM",
        "claim_boundary": "test runtime probe",
    }


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "run_dimos_replay_consumer_under_test",
        ROOT / "scripts" / "run_dimos_replay_consumer.py",
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
