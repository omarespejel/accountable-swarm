from __future__ import annotations

import json
from pathlib import Path
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]


class CollectDimosRuntimeSmokeReportCliTests(TestCase):
    def test_missing_dimos_venv_yields_narrow_claim(self) -> None:
        with TemporaryDirectory(dir=ROOT / "runs") as tmpdir:
            tmp = Path(tmpdir)
            bridge_pack = tmp / "bridge-pack"
            checkout = tmp / "dimos-checkout"
            report_path = tmp / "report.json"
            _write_bridge_pack(bridge_pack)
            _write_checkout_source_files(checkout)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.collect_dimos_runtime_smoke_report",
                    "--bridge-pack",
                    str(bridge_pack.relative_to(ROOT)),
                    "--dimos-checkout",
                    str(checkout),
                    "--report-out",
                    str(report_path.relative_to(ROOT)),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 4)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["schema_version"], "dimos-runtime-smoke-report.v1")
            self.assertEqual(report["outcome"], "NARROW_CLAIM")
            self.assertFalse(report["pass_conditions"]["venv_python_present"])
            self.assertFalse(report["pass_conditions"]["dimos_cli_help_ok"])

    def test_fake_dimos_venv_can_produce_go_report(self) -> None:
        with TemporaryDirectory(dir=ROOT / "runs") as tmpdir:
            tmp = Path(tmpdir)
            bridge_pack = tmp / "bridge-pack"
            checkout = tmp / "dimos-checkout"
            report_path = tmp / "report.json"
            _write_bridge_pack(bridge_pack)
            _write_checkout_source_files(checkout)
            _write_fake_runtime_env(checkout)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.collect_dimos_runtime_smoke_report",
                    "--bridge-pack",
                    str(bridge_pack.relative_to(ROOT)),
                    "--dimos-checkout",
                    str(checkout),
                    "--report-out",
                    str(report_path.relative_to(ROOT)),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["outcome"], "GO")
            self.assertTrue(all(report["pass_conditions"].values()))
            self.assertEqual(report["dimos_runtime_probe"]["checkout_name"], "dimos-checkout")


def _write_bridge_pack(bridge_pack: Path) -> None:
    bridge_pack.mkdir(parents=True, exist_ok=True)
    timeline_lines = [
        json.dumps(
            {
                "agent_id": "agent-0",
                "decision": "MOVE",
                "dimos_stream_hint": "/accountable_swarm/demo/agent-0/grid_pose",
                "event_sha256": "a" * 64,
                "grid": {"height": 4, "width": 4},
                "position_cell": {"x": 1, "y": 1},
                "scenario": "demo",
                "schema_version": "dimos-swarm-replay-event.v1",
                "source": "accountable_swarm_decisiontrace",
                "tick": 0,
                "trace_summary_sha": "b" * 64,
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        json.dumps(
            {
                "agent_id": "agent-1",
                "decision": "HOLD",
                "dimos_stream_hint": "/accountable_swarm/demo/agent-1/grid_pose",
                "event_sha256": "c" * 64,
                "grid": {"height": 4, "width": 4},
                "position_cell": {"x": 2, "y": 1},
                "scenario": "demo",
                "schema_version": "dimos-swarm-replay-event.v1",
                "source": "accountable_swarm_decisiontrace",
                "tick": 0,
                "trace_summary_sha": "d" * 64,
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
    ]
    (bridge_pack / "timeline.ndjson").write_text("\n".join(timeline_lines) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": "dimos-bridge-pack-report.v1",
        "outcome": "GO",
        "bridge_outcome": "GO",
        "source_bundle": "runs/demo/source",
        "artifacts": {
            "manifest": bridge_pack.relative_to(ROOT).as_posix() + "/manifest.json",
            "timeline_ndjson": bridge_pack.relative_to(ROOT).as_posix() + "/timeline.ndjson",
        },
        "scenario_count": 1,
        "scenarios": ["demo"],
        "event_count": 2,
        "agent_count": 2,
        "dimos_probe": {
            "source": {"checkout_provided": False, "checkout_exists": False, "required_files_present": {}, "source_outcome": "NARROW_CLAIM", "source_name": None},
            "python_import_available": False,
            "cli_available": False,
            "runtime_outcome": "NARROW_CLAIM",
            "claim_boundary": "fixture",
        },
        "pass_conditions": {
            "source_bundle_outcome_go": True,
            "source_bundle_inside_repo": True,
            "out_dir_inside_repo": True,
            "timeline_has_events": True,
            "timeline_events_integer_only": True,
            "timeline_events_reference_verified_hashes": True,
            "manifest_paths_are_relative": True,
            "manifest_contains_no_key_material": True,
        },
        "non_claims": ["fixture"],
    }
    (bridge_pack / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _write_checkout_source_files(checkout: Path) -> None:
    for relative in (
        "AGENTS.md",
        "dimos/core/module.py",
        "dimos/core/stream.py",
        "dimos/core/coordination/blueprints.py",
        "dimos/visualization/rerun/bridge.py",
    ):
        path = checkout / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# fixture\n", encoding="utf-8")


def _write_fake_runtime_env(checkout: Path) -> None:
    bin_dir = checkout / ".venv" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    fake_python = bin_dir / "python"
    fake_python.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        "print(json.dumps({"
        "\"dimos_import_available\": True,"
        "\"rerun_import_available\": True,"
        "\"rerun_init_import_available\": True,"
        "\"timeline_event_count\": 2,"
        "\"timeline_scenarios\": [\"demo\"]"
        "}, sort_keys=True))\n",
        encoding="utf-8",
    )
    fake_python.chmod(fake_python.stat().st_mode | stat.S_IXUSR)
    fake_dimos = bin_dir / "dimos"
    fake_dimos.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    fake_dimos.chmod(fake_dimos.stat().st_mode | stat.S_IXUSR)
