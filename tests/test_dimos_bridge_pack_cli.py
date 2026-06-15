from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from accountable_swarm.swarm import build_agent_traces, run_swarm_sim
from accountable_swarm.trace.models import canonical_json, sha256_canonical, verify_trace


ROOT = Path(__file__).resolve().parents[1]


class DimosBridgePackCliTests(TestCase):
    def test_prepare_dimos_bridge_pack_exports_verified_timeline(self) -> None:
        module = _load_module()
        test_root = ROOT / "runs" / "dimos"
        test_root.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=test_root) as tmpdir:
            work_dir = Path(tmpdir)
            bundle_dir = _write_minimal_bundle(work_dir / "bundle")
            out_dir = work_dir / "bridge"
            dimos_checkout = _write_fake_dimos_checkout(work_dir / "dimos")
            argv = [
                "prepare_dimos_bridge_pack.py",
                "--source-bundle",
                str(bundle_dir.relative_to(ROOT)),
                "--out-dir",
                str(out_dir.relative_to(ROOT)),
                "--dimos-checkout",
                str(dimos_checkout),
            ]

            with patch.object(sys, "argv", argv):
                returncode = module.main()

            self.assertEqual(returncode, 0)
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            events = [
                json.loads(line)
                for line in (out_dir / "timeline.ndjson").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(manifest["schema_version"], "dimos-bridge-pack-report.v1")
            self.assertEqual(manifest["outcome"], "GO")
            self.assertEqual(manifest["bridge_outcome"], "GO")
            self.assertEqual(manifest["scenario_count"], 1)
            self.assertEqual(manifest["scenarios"], ["corridor"])
            self.assertEqual(manifest["event_count"], len(events))
            self.assertTrue(manifest["dimos_probe"]["source"]["checkout_exists"])
            self.assertEqual(manifest["dimos_probe"]["source"]["source_outcome"], "GO")
            self.assertNotIn(str(dimos_checkout), canonical_json(manifest))
            self.assertTrue(all(manifest["pass_conditions"].values()))
            self.assertTrue(events)
            self.assertTrue(
                all(event["schema_version"] == "dimos-swarm-replay-event.v1" for event in events)
            )
            self.assertTrue(
                all(isinstance(event["position_cell"]["x"], int) for event in events)
            )
            self.assertTrue(
                all(isinstance(event["position_cell"]["y"], int) for event in events)
            )

    def test_prepare_dimos_bridge_pack_rejects_tampered_trace(self) -> None:
        module = _load_module()
        test_root = ROOT / "runs" / "dimos"
        test_root.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=test_root) as tmpdir:
            work_dir = Path(tmpdir)
            bundle_dir = _write_minimal_bundle(work_dir / "bundle")
            out_dir = work_dir / "bridge"
            trace_path = next((bundle_dir / "scenarios" / "corridor" / "traces").glob("*.json"))
            payload = json.loads(trace_path.read_text(encoding="utf-8"))
            payload["events"][0]["command"]["accepted_x"] = 99
            trace_path.write_text(canonical_json(payload) + "\n", encoding="utf-8")
            argv = [
                "prepare_dimos_bridge_pack.py",
                "--source-bundle",
                str(bundle_dir.relative_to(ROOT)),
                "--out-dir",
                str(out_dir.relative_to(ROOT)),
            ]

            with patch.object(sys, "argv", argv):
                returncode = module.main()

            self.assertEqual(returncode, 4)
            self.assertFalse((out_dir / "manifest.json").exists())
            self.assertFalse((out_dir / "timeline.ndjson").exists())

    def test_prepare_dimos_bridge_pack_rejects_trace_path_escape(self) -> None:
        module = _load_module()
        test_root = ROOT / "runs" / "dimos"
        test_root.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=test_root) as tmpdir:
            work_dir = Path(tmpdir)
            bundle_dir = _write_minimal_bundle(work_dir / "bundle")
            out_dir = work_dir / "bridge"
            trace_path = next((bundle_dir / "scenarios" / "corridor" / "traces").glob("*.json"))
            outside_trace = work_dir / "outside.json"
            outside_trace.write_text(trace_path.read_text(encoding="utf-8"), encoding="utf-8")
            summary_path = bundle_dir / "summary.json"
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            traces = summary["scenarios"][0]["files"]["traces"]
            first_agent = sorted(traces)[0]
            traces[first_agent] = "../outside.json"
            summary_path.write_text(canonical_json(summary) + "\n", encoding="utf-8")
            argv = [
                "prepare_dimos_bridge_pack.py",
                "--source-bundle",
                str(bundle_dir.relative_to(ROOT)),
                "--out-dir",
                str(out_dir.relative_to(ROOT)),
            ]

            with patch.object(sys, "argv", argv):
                returncode = module.main()

            self.assertEqual(returncode, 4)
            self.assertFalse((out_dir / "manifest.json").exists())
            self.assertFalse((out_dir / "timeline.ndjson").exists())

    def test_prepare_dimos_bridge_pack_rejects_hash_valid_bool_tick(self) -> None:
        module = _load_module()
        test_root = ROOT / "runs" / "dimos"
        test_root.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=test_root) as tmpdir:
            work_dir = Path(tmpdir)
            bundle_dir = _write_minimal_bundle(work_dir / "bundle")
            out_dir = work_dir / "bridge"
            trace_path = next((bundle_dir / "scenarios" / "corridor" / "traces").glob("*.json"))
            payload = json.loads(trace_path.read_text(encoding="utf-8"))
            payload["events"][0]["tick"] = True
            first_event_body = dict(payload["events"][0])
            first_event_body.pop("sha256")
            payload["events"][0]["sha256"] = sha256_canonical(first_event_body)
            for index in range(1, len(payload["events"])):
                payload["events"][index]["prev_sha"] = payload["events"][index - 1]["sha256"]
                event_body = dict(payload["events"][index])
                event_body.pop("sha256")
                payload["events"][index]["sha256"] = sha256_canonical(event_body)
            payload["summary_sha"] = sha256_canonical(
                {
                    "events": payload["events"],
                    "genesis_sha": payload["genesis_sha"],
                    "run_id": payload["run_id"],
                    "schema_version": payload["schema_version"],
                }
            )
            trace_path.write_text(canonical_json(payload) + "\n", encoding="utf-8")
            argv = [
                "prepare_dimos_bridge_pack.py",
                "--source-bundle",
                str(bundle_dir.relative_to(ROOT)),
                "--out-dir",
                str(out_dir.relative_to(ROOT)),
            ]

            with patch.object(sys, "argv", argv):
                returncode = module.main()

            self.assertEqual(returncode, 4)
            self.assertFalse((out_dir / "manifest.json").exists())
            self.assertFalse((out_dir / "timeline.ndjson").exists())

    def test_prepare_dimos_bridge_pack_rejects_hash_valid_bool_grid_dimensions(self) -> None:
        module = _load_module()
        test_root = ROOT / "runs" / "dimos"
        test_root.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=test_root) as tmpdir:
            work_dir = Path(tmpdir)
            bundle_dir = _write_minimal_bundle(work_dir / "bundle")
            out_dir = work_dir / "bridge"
            trace_path = next((bundle_dir / "scenarios" / "corridor" / "traces").glob("*.json"))
            payload = json.loads(trace_path.read_text(encoding="utf-8"))
            payload["events"] = [payload["events"][0]]
            payload["events"][0]["command"]["accepted_x"] = 0
            payload["events"][0]["command"]["accepted_y"] = 0
            payload["events"][0]["command"]["grid_width"] = True
            payload["events"][0]["command"]["grid_height"] = True
            payload["events"][0]["prev_sha"] = "0" * 64
            first_event_body = dict(payload["events"][0])
            first_event_body.pop("sha256")
            payload["events"][0]["sha256"] = sha256_canonical(first_event_body)
            payload["summary_sha"] = sha256_canonical(
                {
                    "events": payload["events"],
                    "genesis_sha": payload["genesis_sha"],
                    "run_id": payload["run_id"],
                    "schema_version": payload["schema_version"],
                }
            )
            trace_path.write_text(canonical_json(payload) + "\n", encoding="utf-8")
            summary_path = bundle_dir / "summary.json"
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summary["scenarios"][0]["grid"] = {"width": 1, "height": 1}
            summary_path.write_text(canonical_json(summary) + "\n", encoding="utf-8")
            argv = [
                "prepare_dimos_bridge_pack.py",
                "--source-bundle",
                str(bundle_dir.relative_to(ROOT)),
                "--out-dir",
                str(out_dir.relative_to(ROOT)),
            ]

            with patch.object(sys, "argv", argv):
                returncode = module.main()

            self.assertEqual(returncode, 4)
            self.assertFalse((out_dir / "manifest.json").exists())
            self.assertFalse((out_dir / "timeline.ndjson").exists())

    def test_prepare_dimos_bridge_pack_rejects_malformed_command_shape(self) -> None:
        module = _load_module()
        test_root = ROOT / "runs" / "dimos"
        test_root.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=test_root) as tmpdir:
            work_dir = Path(tmpdir)
            bundle_dir = _write_minimal_bundle(work_dir / "bundle")
            out_dir = work_dir / "bridge"
            trace_path = next((bundle_dir / "scenarios" / "corridor" / "traces").glob("*.json"))
            payload = json.loads(trace_path.read_text(encoding="utf-8"))
            payload["events"][0]["command"] = "not-a-command-object"
            first_event_body = dict(payload["events"][0])
            first_event_body.pop("sha256")
            payload["events"][0]["sha256"] = sha256_canonical(first_event_body)
            for index in range(1, len(payload["events"])):
                payload["events"][index]["prev_sha"] = payload["events"][index - 1]["sha256"]
                event_body = dict(payload["events"][index])
                event_body.pop("sha256")
                payload["events"][index]["sha256"] = sha256_canonical(event_body)
            payload["summary_sha"] = sha256_canonical(
                {
                    "events": payload["events"],
                    "genesis_sha": payload["genesis_sha"],
                    "run_id": payload["run_id"],
                    "schema_version": payload["schema_version"],
                }
            )
            trace_path.write_text(canonical_json(payload) + "\n", encoding="utf-8")
            argv = [
                "prepare_dimos_bridge_pack.py",
                "--source-bundle",
                str(bundle_dir.relative_to(ROOT)),
                "--out-dir",
                str(out_dir.relative_to(ROOT)),
            ]

            with patch.object(sys, "argv", argv):
                returncode = module.main()

            self.assertEqual(returncode, 4)
            self.assertFalse((out_dir / "manifest.json").exists())
            self.assertFalse((out_dir / "timeline.ndjson").exists())

    def test_repo_path_rejects_escaped_paths(self) -> None:
        module = _load_module()
        with self.assertRaises(ValueError):
            module._repo_path(ROOT, Path("../outside"))
        with self.assertRaises(ValueError):
            module._repo_path(ROOT, ROOT.parent / "outside")


def _write_minimal_bundle(bundle_dir: Path) -> Path:
    result = run_swarm_sim(agent_count=2, scenario="corridor", ticks=16)
    traces = build_agent_traces(result)
    trace_dir = bundle_dir / "scenarios" / "corridor" / "traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_paths = {}
    trace_summary_shas = {}
    for agent_id, trace in sorted(traces.items()):
        trace_summary_shas[agent_id] = verify_trace(trace)
        trace_path = trace_dir / f"{agent_id}.json"
        trace_path.write_text(trace.to_canonical_json() + "\n", encoding="utf-8")
        trace_paths[agent_id] = trace_path.relative_to(bundle_dir).as_posix()
    sim_report = result.report_dict(trace_summary_shas)
    summary = {
        "schema_version": "swarm-demo-bundle-report.v1",
        "outcome": "GO",
        "scenario_count": 1,
        "agent_count": 2,
        "ticks": 16,
        "scenarios": [
            {
                "scenario": "corridor",
                "agent_count": 2,
                "ticks": 16,
                "grid": {"width": result.grid_width, "height": result.grid_height},
                "obstacles": [],
                "sim_report": sim_report,
                "render_summary": {"outcome": "GO"},
                "files": {
                    "sim_report": "scenarios/corridor/sim_report.json",
                    "replay_html": "scenarios/corridor/replay.html",
                    "replay_summary": "scenarios/corridor/replay_summary.json",
                    "traces": trace_paths,
                },
            }
        ],
        "pass_conditions": {
            "all_reviewed_scenarios_included": False,
            "every_sim_report_go": True,
            "every_render_report_go": True,
            "every_trace_replay_clean": True,
            "no_absolute_paths": True,
        },
        "non_claims": ["no DimOS integration"],
    }
    (bundle_dir / "summary.json").write_text(canonical_json(summary) + "\n", encoding="utf-8")
    return bundle_dir


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
        target.write_text("# fake DimOS file for bridge probe tests\n", encoding="utf-8")
    return path


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "prepare_dimos_bridge_pack_under_test",
        ROOT / "scripts" / "prepare_dimos_bridge_pack.py",
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
