import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase

from accountable_swarm.world_model import world_model_from_dict


ROOT = Path(__file__).resolve().parents[1]


class WorldModelDashboardPackCliTests(TestCase):
    def test_dashboard_pack_verifies_fixture_hazard_world_model_timeline(self) -> None:
        (ROOT / "runs").mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=ROOT / "runs") as tmpdir:
            base = Path(tmpdir)
            trace_dir = base / "hazard_x"
            report_path = base / "hazard_x_report.json"
            out_dir = base / "dashboard"
            _run_hazard_gate(trace_dir=trace_dir, report_path=report_path)

            result = _run_dashboard_pack(trace_dir=trace_dir, report_path=report_path, out_dir=out_dir)

            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            data = json.loads((out_dir / "data.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["schema_version"], "world-model-dashboard-pack-report.v1")
        self.assertEqual(manifest["outcome"], "GO")
        self.assertTrue(all(manifest["pass_conditions"].values()))
        self.assertEqual(manifest["state_count"], 8)
        self.assertEqual(manifest["agent_count"], 4)
        self.assertEqual(data["schema_version"], "world-model-dashboard-data.v1")
        self.assertEqual(data["mode"], "fixture")
        self.assertEqual(data["hazard"]["cell"], {"x": 3, "y": 2})
        self.assertEqual(data["formation"], "x")
        self.assertEqual(len(data["timeline"]), 8)
        self.assertEqual(len(data["timeline"][0]["agents"]), 4)
        self.assertEqual(data["timeline"][0]["observations"][0]["source"], "fixture_bbox")
        self.assertEqual(data["timeline"][0]["hazards"], [{"x": 3, "y": 2}])
        self.assertFalse(Path(manifest["data_path"]).is_absolute())
        self.assertFalse(any(Path(path).is_absolute() for path in manifest["source"].values()))
        self.assertNotIn("sk-", json.dumps(manifest, sort_keys=True))
        self.assertNotIn("sk-", json.dumps(data, sort_keys=True))
        self.assertIn("no learned world model", data["non_claims"])

    def test_dashboard_pack_rejects_world_model_trace_drift_even_when_rehashed(self) -> None:
        (ROOT / "runs").mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=ROOT / "runs") as tmpdir:
            base = Path(tmpdir)
            trace_dir = base / "hazard_x"
            report_path = base / "hazard_x_report.json"
            out_dir = base / "dashboard"
            _run_hazard_gate(trace_dir=trace_dir, report_path=report_path)
            drifted_sha = _rewrite_first_state_with_drift(trace_dir / "world_model_timeline.jsonl")
            _rewrite_report_first_world_model_sha(report_path, drifted_sha)

            result = _run_dashboard_pack(trace_dir=trace_dir, report_path=report_path, out_dir=out_dir)

        self.assertEqual(result.returncode, 4)
        self.assertIn("world model agent cell does not match trace command", result.stderr)

    def test_dashboard_pack_accepts_degraded_hold_world_model_timeline(self) -> None:
        (ROOT / "runs").mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=ROOT / "runs") as tmpdir:
            base = Path(tmpdir)
            trace_dir = base / "degraded"
            report_path = base / "degraded_report.json"
            out_dir = base / "dashboard"
            _run_hazard_gate(trace_dir=trace_dir, report_path=report_path, mode="degraded")

            result = _run_dashboard_pack(trace_dir=trace_dir, report_path=report_path, out_dir=out_dir)

            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            data = json.loads((out_dir / "data.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["outcome"], "GO")
        self.assertEqual(data["mode"], "degraded")
        self.assertIsNone(data["hazard"])
        self.assertEqual(data["world_model"]["state_count"], 1)
        self.assertEqual(data["timeline"][0]["observations"][0]["source"], "degraded")
        self.assertEqual(data["timeline"][0]["hazards"], [])
        self.assertEqual(data["planner_metrics"]["hold_count"], 4)


def _run_hazard_gate(
    *,
    trace_dir: Path,
    report_path: Path,
    mode: str = "fixture",
) -> subprocess.CompletedProcess[str]:
    args = [
        sys.executable,
        "-m",
        "scripts.run_hazard_formation_gate",
        "--image",
        "fixtures/hazard_marker.ppm",
        "--mode",
        mode,
        "--formation",
        "x",
        "--trace-dir",
        str(trace_dir.relative_to(ROOT)),
        "--report-out",
        str(report_path.relative_to(ROOT)),
    ]
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return result


def _run_dashboard_pack(
    *,
    trace_dir: Path,
    report_path: Path,
    out_dir: Path,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.prepare_world_model_dashboard_pack",
            "--trace-dir",
            str(trace_dir.relative_to(ROOT)),
            "--hazard-report",
            str(report_path.relative_to(ROOT)),
            "--out-dir",
            str(out_dir.relative_to(ROOT)),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _rewrite_first_state_with_drift(timeline_path: Path) -> str:
    lines = timeline_path.read_text(encoding="utf-8").splitlines()
    payload = json.loads(lines[0])
    agent = payload["agents"][0]
    width = payload["grid"]["width"]
    agent["cell"]["x"] = (agent["cell"]["x"] + 1) % width
    state = world_model_from_dict(payload).with_computed_sha()
    lines[0] = state.to_canonical_json()
    timeline_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return state.world_model_sha


def _rewrite_report_first_world_model_sha(report_path: Path, first_world_model_sha: str) -> None:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["world_model"]["first_world_model_sha"] = first_world_model_sha
    report_path.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
