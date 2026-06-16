from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]


class PrepareDimosRuntimeSmokePackCliTests(TestCase):
    def test_prepare_pack_writes_manifest_and_commands(self) -> None:
        base = ROOT / "runs"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            tmp = Path(tmpdir)
            bridge_pack = tmp / "bridge-pack"
            out_dir = tmp / "runtime-smoke-pack"
            _write_bridge_pack(bridge_pack)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.prepare_dimos_runtime_smoke_pack",
                    "--bridge-pack",
                    str(bridge_pack.relative_to(ROOT)),
                    "--out-dir",
                    str(out_dir.relative_to(ROOT)),
                    "--dimos-checkout-hint",
                    "../dimos",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            commands = (out_dir / "operator_commands.sh").read_text(encoding="utf-8")
            runbook = (out_dir / "README.md").read_text(encoding="utf-8")

        self.assertEqual(manifest["schema_version"], "dimos-runtime-smoke-pack.v1")
        self.assertEqual(manifest["outcome"], "GO")
        self.assertTrue(all(manifest["pass_conditions"].values()))
        self.assertIn("uv sync --frozen", commands)
        self.assertIn("scripts.run_dimos_replay_consumer", commands)
        self.assertIn("scripts.collect_dimos_runtime_smoke_report", commands)
        self.assertIn("DimOS Runtime Smoke Pack", runbook)
        self.assertNotIn(str(ROOT), commands)
        self.assertNotIn(str(ROOT), json.dumps(manifest, sort_keys=True))

    def test_out_dir_must_stay_under_repo(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.prepare_dimos_runtime_smoke_pack",
                "--bridge-pack",
                "runs/dimos/bridge-pack",
                "--out-dir",
                "../escape",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("path escapes repository root", result.stderr)


def _write_bridge_pack(bridge_pack: Path) -> None:
    bridge_pack.mkdir(parents=True, exist_ok=True)
    (bridge_pack / "timeline.ndjson").write_text("{\"fixture\":true}\n", encoding="utf-8")
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
