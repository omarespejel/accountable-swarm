from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase

from accountable_swarm.swarm import build_agent_traces, run_swarm_sim


ROOT = Path(__file__).resolve().parents[1]


class SwarmTraceHtmlCliTests(TestCase):
    def test_renderer_writes_deterministic_html_and_summary(self) -> None:
        with TemporaryDirectory() as tmpdir:
            trace_dir = Path(tmpdir) / "traces"
            html_path = Path(tmpdir) / "swarm.html"
            summary_path = Path(tmpdir) / "summary.json"
            rerender_path = Path(tmpdir) / "swarm-rerender.html"
            rerender_summary_path = Path(tmpdir) / "summary-rerender.json"
            _write_center_block_traces(trace_dir)

            first = _run_renderer(trace_dir, html_path, summary_path)
            second = _run_renderer(trace_dir, rerender_path, rerender_summary_path)

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            html_text = html_path.read_text(encoding="utf-8")
            self.assertEqual(html_text, rerender_path.read_text(encoding="utf-8"))
            self.assertIn("<canvas id=\"swarm-canvas\"", html_text)
            self.assertIn("<script id=\"swarm-data\" type=\"application/json\">", html_text)
            self.assertIn("deterministic 2D trace replay; no DimOS or 3D physics claim", html_text)
            self.assertIn("Canvas not supported; use static frames below.", html_text)
            self.assertIn("typeof ctx.roundRect === 'function'", html_text)
            self.assertIn("<svg", html_text)
            self.assertIn("Tick 0", html_text)
            self.assertIn("Trace Summary SHAs", html_text)
            self.assertNotIn(tmpdir, html_text)

            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            rerender_summary = json.loads(rerender_summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary, rerender_summary)
            self.assertEqual(summary["schema_version"], "swarm-trace-html-report.v1")
            self.assertEqual(summary["outcome"], "GO")
            self.assertEqual(summary["agent_count"], 4)
            self.assertEqual(summary["tick_count"], 16)
            self.assertEqual(summary["grid"], {"width": 7, "height": 5})
            self.assertEqual(summary["obstacles"], [{"x": 3, "y": 2}])
            self.assertEqual(summary["same_cell_collision_count"], 0)
            self.assertEqual(summary["swap_collision_count"], 0)
            self.assertEqual(summary["obstacle_occupancy_violation_count"], 0)
            self.assertRegex(summary["html_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(set(summary["trace_summary_shas"]), {f"sim-agent-{index}" for index in range(4)})

    def test_renderer_fails_closed_on_tampered_trace(self) -> None:
        with TemporaryDirectory() as tmpdir:
            trace_dir = Path(tmpdir) / "traces"
            html_path = Path(tmpdir) / "swarm.html"
            summary_path = Path(tmpdir) / "summary.json"
            _write_center_block_traces(trace_dir)

            trace_path = trace_dir / "sim-agent-0.json"
            value = json.loads(trace_path.read_text(encoding="utf-8"))
            value["events"][0]["command"]["accepted_x"] = 99
            trace_path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")

            result = _run_renderer(trace_dir, html_path, summary_path)

            self.assertEqual(result.returncode, 4)
            self.assertIn("swarm trace render failed", result.stderr)
            self.assertFalse(html_path.exists())
            self.assertFalse(summary_path.exists())

    def test_renderer_rejects_obstacle_outside_grid(self) -> None:
        with TemporaryDirectory() as tmpdir:
            trace_dir = Path(tmpdir) / "traces"
            html_path = Path(tmpdir) / "swarm.html"
            summary_path = Path(tmpdir) / "summary.json"
            _write_center_block_traces(trace_dir)

            result = _run_renderer(
                trace_dir,
                html_path,
                summary_path,
                extra_args=["--obstacle", "10,10"],
            )

            self.assertEqual(result.returncode, 4)
            self.assertIn("obstacle outside render grid", result.stderr)
            self.assertFalse(html_path.exists())
            self.assertFalse(summary_path.exists())


def _write_center_block_traces(trace_dir: Path) -> None:
    result = run_swarm_sim(agent_count=4, ticks=16, scenario="center-block")
    traces = build_agent_traces(result)
    trace_dir.mkdir(parents=True, exist_ok=True)
    for agent_id, trace in sorted(traces.items()):
        (trace_dir / f"{agent_id}.json").write_text(
            trace.to_canonical_json() + "\n",
            encoding="utf-8",
        )


def _run_renderer(
    trace_dir: Path,
    html_path: Path,
    summary_path: Path,
    *,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    obstacle_args = extra_args if extra_args is not None else ["--obstacle", "3,2"]
    return subprocess.run(
        [
            sys.executable,
            "scripts/render_swarm_trace_html.py",
            "--trace-dir",
            str(trace_dir),
            "--grid-width",
            "7",
            "--grid-height",
            "5",
            *obstacle_args,
            "--html-out",
            str(html_path),
            "--summary-out",
            str(summary_path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
