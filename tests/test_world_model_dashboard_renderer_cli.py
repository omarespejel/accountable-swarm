from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]


class WorldModelDashboardRendererCliTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        (ROOT / "runs").mkdir(parents=True, exist_ok=True)
        cls._class_tmp = TemporaryDirectory(dir=ROOT / "runs")
        base = Path(cls._class_tmp.name)
        cls._base_pack_dir = base / "dashboard"
        trace_dir = base / "hazard_x"
        report_path = base / "hazard_x_report.json"
        dimos_manifest = base / "dimos_manifest.json"
        dimos_timeline = base / "dimos_timeline.ndjson"
        _run_hazard_gate(trace_dir=trace_dir, report_path=report_path)
        dimos_timeline.write_text(
            json.dumps(
                {
                    "schema_version": "dimos-swarm-replay-event.v1",
                    "scenario": "corridor",
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
        dimos_manifest.write_text(
            json.dumps(
                {
                    "schema_version": "dimos-bridge-pack-report.v1",
                    "outcome": "GO",
                    "bridge_outcome": "GO",
                    "event_count": 1,
                    "scenario_count": 1,
                    "scenarios": ["corridor"],
                    "artifacts": {
                        "manifest": dimos_manifest.relative_to(ROOT).as_posix(),
                        "timeline_ndjson": dimos_timeline.relative_to(ROOT).as_posix(),
                    },
                    "dimos_probe": {
                        "runtime_outcome": "NARROW_CLAIM",
                        "source": {"checkout_provided": False},
                    },
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
        _run_dashboard_pack(
            trace_dir=trace_dir,
            report_path=report_path,
            out_dir=cls._base_pack_dir,
            source_image=ROOT / "fixtures" / "hazard_marker.ppm",
            dimos_manifest=dimos_manifest,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._class_tmp.cleanup()

    def test_renderer_builds_interactive_html_from_verified_dashboard_pack(self) -> None:
        with TemporaryDirectory(dir=ROOT / "runs") as tmpdir:
            base = Path(tmpdir)
            pack_dir = base / "dashboard"
            shutil.copytree(self._base_pack_dir, pack_dir)
            html_path = pack_dir / "index.html"
            summary_path = pack_dir / "summary.json"

            result = _run_renderer(data_path=pack_dir / "data.json", html_path=html_path, summary_path=summary_path)

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            html_text = html_path.read_text(encoding="utf-8")

        self.assertEqual(summary["schema_version"], "world-model-dashboard-html-report.v1")
        self.assertEqual(summary["outcome"], "GO")
        self.assertTrue(all(summary["pass_conditions"].values()))
        self.assertEqual(summary["tick_count"], 8)
        self.assertEqual(summary["agent_count"], 4)
        self.assertEqual(len(summary["html_sha256"]), 64)
        self.assertFalse(Path(summary["html_path"]).is_absolute())
        self.assertFalse(Path(summary["data_path"]).is_absolute())
        self.assertIn("Accountable World Model Dashboard", html_text)
        self.assertIn("Qwen Source Frame", html_text)
        self.assertIn("Qwen evidence", html_text)
        self.assertIn("Deterministic local planner", html_text)
        self.assertIn("DecisionTrace", html_text)
        self.assertIn("DimOS-ready Export", html_text)
        self.assertIn("assets/hazard_marker.ppm", html_text)
        self.assertIn("No DimOS bridge manifest was packaged", html_text)  # script contains fallback string
        self.assertIn("renderDimosStatus", html_text)
        self.assertIn("world_model_sha", html_text)
        self.assertIn("no physical robot behavior", html_text)
        self.assertIn("no Qwen real-time control", html_text)
        self.assertNotIn("sk-", html_text)

    def test_renderer_rejects_unverified_schema(self) -> None:
        with TemporaryDirectory(dir=ROOT / "runs") as tmpdir:
            base = Path(tmpdir)
            pack_dir = base / "dashboard"
            shutil.copytree(self._base_pack_dir, pack_dir)
            data_path = pack_dir / "data.json"
            data = json.loads(data_path.read_text(encoding="utf-8"))
            data["schema_version"] = "other.v1"
            data_path.write_text(json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")

            result = _run_renderer(
                data_path=data_path,
                html_path=pack_dir / "index.html",
                summary_path=pack_dir / "summary.json",
            )

        self.assertEqual(result.returncode, 4)
        self.assertIn("unsupported schema", result.stderr)

    def test_renderer_rejects_absolute_source_path(self) -> None:
        with TemporaryDirectory(dir=ROOT / "runs") as tmpdir:
            base = Path(tmpdir)
            pack_dir = base / "dashboard"
            shutil.copytree(self._base_pack_dir, pack_dir)
            data_path = pack_dir / "data.json"
            data = json.loads(data_path.read_text(encoding="utf-8"))
            data["source"]["hazard_report"] = str((ROOT / "README.md").resolve())
            data_path.write_text(json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")

            result = _run_renderer(
                data_path=data_path,
                html_path=pack_dir / "index.html",
                summary_path=pack_dir / "summary.json",
            )

        self.assertEqual(result.returncode, 4)
        self.assertIn("absolute paths", result.stderr)

    def test_renderer_rejects_event_hash_drift(self) -> None:
        with TemporaryDirectory(dir=ROOT / "runs") as tmpdir:
            base = Path(tmpdir)
            pack_dir = base / "dashboard"
            shutil.copytree(self._base_pack_dir, pack_dir)
            data_path = pack_dir / "data.json"
            data = json.loads(data_path.read_text(encoding="utf-8"))
            data["timeline"][0]["agents"][0]["world_model_decision_event_sha"] = "0" * 64
            data_path.write_text(json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")

            result = _run_renderer(
                data_path=data_path,
                html_path=pack_dir / "index.html",
                summary_path=pack_dir / "summary.json",
            )

        self.assertEqual(result.returncode, 4)
        self.assertIn("world_model_decision_event_sha mismatch", result.stderr)

    def test_renderer_rejects_invalid_bbox_overlay_payload(self) -> None:
        with TemporaryDirectory(dir=ROOT / "runs") as tmpdir:
            base = Path(tmpdir)
            pack_dir = base / "dashboard"
            shutil.copytree(self._base_pack_dir, pack_dir)
            data_path = pack_dir / "data.json"
            data = json.loads(data_path.read_text(encoding="utf-8"))
            data["timeline"][0]["observations"][0]["bbox_2d_norm_1000"] = [0, 0, 1001, 1000]
            data_path.write_text(json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")

            result = _run_renderer(
                data_path=data_path,
                html_path=pack_dir / "index.html",
                summary_path=pack_dir / "summary.json",
            )

        self.assertEqual(result.returncode, 4)
        self.assertIn("bbox_2d_norm_1000 must be within 0..1000 with positive area", result.stderr)


def _run_hazard_gate(*, trace_dir: Path, report_path: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.run_hazard_formation_gate",
            "--image",
            "fixtures/hazard_marker.ppm",
            "--mode",
            "fixture",
            "--formation",
            "x",
            "--trace-dir",
            str(trace_dir.relative_to(ROOT)),
            "--report-out",
            str(report_path.relative_to(ROOT)),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return result


def _run_dashboard_pack(
    *,
    trace_dir: Path,
    report_path: Path,
    out_dir: Path,
    source_image: Path | None = None,
    dimos_manifest: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    args = [
        sys.executable,
        "-m",
        "scripts.prepare_world_model_dashboard_pack",
        "--trace-dir",
        str(trace_dir.relative_to(ROOT)),
        "--hazard-report",
        str(report_path.relative_to(ROOT)),
        "--out-dir",
        str(out_dir.relative_to(ROOT)),
    ]
    if source_image is not None:
        args.extend(["--source-image", str(source_image.relative_to(ROOT))])
    if dimos_manifest is not None:
        args.extend(["--dimos-bridge-manifest", str(dimos_manifest.relative_to(ROOT))])
    result = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return result


def _run_renderer(*, data_path: Path, html_path: Path, summary_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.render_world_model_dashboard_html",
            "--data",
            str(data_path.relative_to(ROOT)),
            "--html-out",
            str(html_path.relative_to(ROOT)),
            "--summary-out",
            str(summary_path.relative_to(ROOT)),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
