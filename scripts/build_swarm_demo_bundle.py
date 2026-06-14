#!/usr/bin/env python3
"""Build a deterministic local swarm demo bundle."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from accountable_swarm.swarm import build_agent_traces, replay_swarm_traces, run_swarm_sim, scenario_names
from accountable_swarm.trace.models import canonical_json, verify_trace


BUNDLE_SCHEMA_VERSION = "swarm-demo-bundle-report.v1"
DEFAULT_AGENT_COUNT = 4
DEFAULT_TICKS = 16


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--agents", type=int, default=DEFAULT_AGENT_COUNT)
    parser.add_argument("--ticks", type=int, default=DEFAULT_TICKS)
    parser.add_argument(
        "--scenario",
        action="append",
        choices=scenario_names(),
        help="Scenario to include. Repeatable. Defaults to every reviewed scenario.",
    )
    args = parser.parse_args()

    scenarios = tuple(args.scenario or scenario_names())
    try:
        report = _build_bundle(
            out_dir=args.out_dir,
            scenarios=scenarios,
            agent_count=args.agents,
            ticks=args.ticks,
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"swarm demo bundle failed: {exc}", file=sys.stderr)
        return 4

    print(f"outcome {report['outcome']}")
    print(f"scenario_count {report['scenario_count']}")
    print(f"index_sha256 {report['index_sha256']}")
    print(f"wrote {args.out_dir / 'index.html'}")
    print(f"wrote {args.out_dir / 'summary.json'}")
    return 0 if report["outcome"] == "GO" else 4


def _build_bundle(
    *,
    out_dir: Path,
    scenarios: tuple[str, ...],
    agent_count: int,
    ticks: int,
) -> dict[str, Any]:
    if not scenarios:
        raise ValueError("at least one scenario is required")
    if len(set(scenarios)) != len(scenarios):
        raise ValueError("scenarios must be unique")
    out_dir.mkdir(parents=True, exist_ok=True)

    cases = []
    for scenario in scenarios:
        case = _build_scenario_case(
            out_dir=out_dir,
            scenario=scenario,
            agent_count=agent_count,
            ticks=ticks,
        )
        cases.append(case)

    pass_conditions = {
        "all_reviewed_scenarios_included": tuple(scenarios) == scenario_names(),
        "every_sim_report_go": all(case["sim_report"]["outcome"] == "GO" for case in cases),
        "every_render_report_go": all(case["render_summary"]["outcome"] == "GO" for case in cases),
        "every_trace_replay_clean": all(
            case["sim_report"]["same_cell_collision_count"] == 0
            and case["sim_report"]["swap_collision_count"] == 0
            and case["sim_report"]["obstacle_occupancy_violation_count"] == 0
            and case["sim_report"]["replay"]["same_cell_collision_count"] == 0
            and case["sim_report"]["replay"]["swap_collision_count"] == 0
            and case["sim_report"]["replay"]["obstacle_occupancy_violation_count"] == 0
            for case in cases
        ),
        "no_absolute_paths": all(_case_has_relative_paths(case) for case in cases),
    }
    outcome = "GO" if all(pass_conditions.values()) else "NARROW_CLAIM"
    index_html = _render_index_html(cases=cases, outcome=outcome)
    index_sha = hashlib.sha256(index_html.encode("utf-8")).hexdigest()
    summary = {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "outcome": outcome,
        "scenario_count": len(cases),
        "agent_count": agent_count,
        "ticks": ticks,
        "scenarios": cases,
        "pass_conditions": pass_conditions,
        "index_sha256": index_sha,
        "non_claims": [
            "no physical robot behavior",
            "no SO-101 operation",
            "no 3D physics simulation",
            "no live Qwen claim",
            "no latency or reliability claim",
            "no DimOS integration",
            "no arbitrary-map or larger-swarm claim",
        ],
    }

    index_path = out_dir / "index.html"
    summary_path = out_dir / "summary.json"
    index_path.write_text(index_html, encoding="utf-8")
    summary_path.write_text(canonical_json(summary) + "\n", encoding="utf-8")
    return summary


def _build_scenario_case(
    *,
    out_dir: Path,
    scenario: str,
    agent_count: int,
    ticks: int,
) -> dict[str, Any]:
    scenario_dir = out_dir / "scenarios" / scenario
    trace_dir = scenario_dir / "traces"
    report_path = scenario_dir / "sim_report.json"
    render_path = scenario_dir / "replay.html"
    render_summary_path = scenario_dir / "replay_summary.json"
    scenario_dir.mkdir(parents=True, exist_ok=True)

    result = run_swarm_sim(
        agent_count=agent_count,
        ticks=ticks,
        scenario=scenario,
    )
    traces = build_agent_traces(result)
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_summary_shas: dict[str, str] = {}
    for agent_id, trace in sorted(traces.items()):
        trace_summary_shas[agent_id] = verify_trace(trace)
        (trace_dir / f"{agent_id}.json").write_text(
            trace.to_canonical_json() + "\n",
            encoding="utf-8",
        )

    replay_report = replay_swarm_traces(traces, obstacles=result.obstacles)
    sim_report = result.report_dict(trace_summary_shas)
    sim_report["replay"] = replay_report.to_dict()
    report_path.write_text(canonical_json(sim_report) + "\n", encoding="utf-8")

    render_args = [
        sys.executable,
        str(Path(__file__).resolve().parent / "render_swarm_trace_html.py"),
        "--trace-dir",
        str(trace_dir),
        "--grid-width",
        str(result.grid_width),
        "--grid-height",
        str(result.grid_height),
        "--title",
        f"Accountable Swarm Replay: {scenario}",
        "--html-out",
        str(render_path),
        "--summary-out",
        str(render_summary_path),
    ]
    for obstacle in result.obstacles:
        render_args.extend(["--obstacle", f"{obstacle.x},{obstacle.y}"])
    render_result = subprocess.run(
        render_args,
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )
    if render_result.returncode != 0:
        raise ValueError(f"trace renderer failed for {scenario}: {render_result.stderr.strip()}")
    render_summary = json.loads(render_summary_path.read_text(encoding="utf-8"))

    return {
        "scenario": scenario,
        "agent_count": agent_count,
        "ticks": ticks,
        "grid": {"width": result.grid_width, "height": result.grid_height},
        "obstacles": [point.to_dict() for point in result.obstacles],
        "sim_report": sim_report,
        "render_summary": render_summary,
        "files": {
            "sim_report": _relative_posix(report_path, out_dir),
            "replay_html": _relative_posix(render_path, out_dir),
            "replay_summary": _relative_posix(render_summary_path, out_dir),
            "traces": {
                agent_id: _relative_posix(trace_dir / f"{agent_id}.json", out_dir)
                for agent_id in sorted(trace_summary_shas)
            },
        },
        "pass_conditions": {
            "sim_report_go": sim_report["outcome"] == "GO",
            "render_report_go": render_summary["outcome"] == "GO",
            "trace_replay_clean": (
                sim_report["same_cell_collision_count"] == 0
                and sim_report["swap_collision_count"] == 0
                and sim_report["obstacle_occupancy_violation_count"] == 0
                and sim_report["replay"]["same_cell_collision_count"] == 0
                and sim_report["replay"]["swap_collision_count"] == 0
                and sim_report["replay"]["obstacle_occupancy_violation_count"] == 0
            ),
        },
    }


def _relative_posix(path: Path, base: Path) -> str:
    return path.relative_to(base).as_posix()


def _case_has_relative_paths(case: dict[str, Any]) -> bool:
    files = case["files"]
    paths = [
        files["sim_report"],
        files["replay_html"],
        files["replay_summary"],
        *files["traces"].values(),
    ]
    return all(not Path(path).is_absolute() for path in paths)


def _render_index_html(*, cases: list[dict[str, Any]], outcome: str) -> str:
    rows = "\n".join(
        _render_index_row(case)
        for case in cases
    )
    return (
        "<!doctype html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\">\n"
        "  <title>Accountable Swarm Demo Bundle</title>\n"
        "  <style>\n"
        "    body{font-family:Arial,sans-serif;margin:24px;color:#111827;background:#f8fafc;}\n"
        "    h1{font-size:22px;margin:0 0 8px;}\n"
        "    table{border-collapse:collapse;background:white;border:1px solid #d1d5db;margin-top:16px;}\n"
        "    td,th{border:1px solid #d1d5db;padding:6px 8px;text-align:left;vertical-align:top;}\n"
        "    code{font-size:12px;}\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "  <h1>Accountable Swarm Demo Bundle</h1>\n"
        f"  <p>Outcome: <strong>{html.escape(outcome)}</strong>. Static bundle generated from deterministic integer-grid traces. Qwen is not in this motion loop.</p>\n"
        "  <table>\n"
        "    <thead><tr><th>Scenario</th><th>Outcome</th><th>Replay</th><th>HTML SHA</th><th>Violations</th></tr></thead>\n"
        f"    <tbody>{rows}</tbody>\n"
        "  </table>\n"
        "</body>\n"
        "</html>\n"
    )


def _render_index_row(case: dict[str, Any]) -> str:
    scenario = html.escape(case["scenario"])
    sim_report = case["sim_report"]
    render_summary = case["render_summary"]
    replay_href = html.escape(case["files"]["replay_html"])
    sha = html.escape(render_summary["html_sha256"])
    violations = (
        f"{sim_report['same_cell_collision_count']} same-cell / "
        f"{sim_report['swap_collision_count']} swap / "
        f"{sim_report['obstacle_occupancy_violation_count']} obstacle"
    )
    return (
        "<tr>"
        f"<td>{scenario}</td>"
        f"<td>{html.escape(sim_report['outcome'])}</td>"
        f"<td><a href=\"{replay_href}\">replay</a></td>"
        f"<td><code>{sha}</code></td>"
        f"<td>{html.escape(violations)}</td>"
        "</tr>"
    )


if __name__ == "__main__":
    raise SystemExit(main())
