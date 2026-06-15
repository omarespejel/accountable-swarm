#!/usr/bin/env python3
"""Render verified swarm DecisionTrace files as deterministic HTML."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from accountable_swarm.swarm import GridPoint, replay_swarm_traces
from accountable_swarm.trace.models import DecisionTrace, canonical_json, trace_from_dict, verify_trace


REPORT_SCHEMA_VERSION = "swarm-trace-html-report.v1"
AGENT_COLORS = ("#2563eb", "#dc2626", "#16a34a", "#9333ea", "#d97706", "#0891b2")
CELL_SIZE = 40
CELL_GAP = 4
MARGIN = 24


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-dir", type=Path, required=True)
    parser.add_argument("--grid-width", type=int, required=True)
    parser.add_argument("--grid-height", type=int, required=True)
    parser.add_argument("--obstacle", action="append", default=[], help="Obstacle as x,y. Repeatable.")
    parser.add_argument("--title", default="Accountable Swarm Trace Replay")
    parser.add_argument("--html-out", type=Path, required=True)
    parser.add_argument("--summary-out", type=Path, required=True)
    args = parser.parse_args()

    try:
        traces = _load_traces(args.trace_dir)
        obstacles = tuple(_parse_obstacle(value) for value in args.obstacle)
        _validate_obstacles(
            obstacles=obstacles,
            grid_width=args.grid_width,
            grid_height=args.grid_height,
        )
        timeline = _timeline_from_traces(
            traces=traces,
            grid_width=args.grid_width,
            grid_height=args.grid_height,
        )
        replay = replay_swarm_traces(traces, obstacles=obstacles)
        trace_summary_shas = {
            agent_id: verify_trace(trace) for agent_id, trace in sorted(traces.items())
        }
        html_text = _render_html(
            title=args.title,
            grid_width=args.grid_width,
            grid_height=args.grid_height,
            obstacles=obstacles,
            timeline=timeline,
            trace_summary_shas=trace_summary_shas,
            replay=replay.to_dict(),
        )
        html_sha = hashlib.sha256(html_text.encode("utf-8")).hexdigest()
        summary = {
            "schema_version": REPORT_SCHEMA_VERSION,
            "outcome": "GO",
            "agent_count": len(traces),
            "tick_count": len(timeline),
            "grid": {"width": args.grid_width, "height": args.grid_height},
            "obstacles": [point.to_dict() for point in sorted(obstacles)],
            "final_positions": replay.to_dict()["final_positions"],
            "same_cell_collision_count": replay.same_cell_collision_count,
            "swap_collision_count": replay.swap_collision_count,
            "obstacle_occupancy_violation_count": replay.obstacle_occupancy_violation_count,
            "trace_summary_shas": trace_summary_shas,
            "html_sha256": html_sha,
            "non_claims": [
                "no physical robot behavior",
                "no SO-101 operation",
                "no 3D physics simulation",
                "no latency or reliability claim",
                "no DimOS integration",
                "no live Qwen claim",
                "no arbitrary-map or larger-swarm claim",
            ],
        }
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"swarm trace render failed: {exc}", file=sys.stderr)
        return 4

    args.html_out.parent.mkdir(parents=True, exist_ok=True)
    args.summary_out.parent.mkdir(parents=True, exist_ok=True)
    args.html_out.write_text(html_text, encoding="utf-8")
    args.summary_out.write_text(canonical_json(summary) + "\n", encoding="utf-8")

    print("outcome GO")
    print(f"agent_count {summary['agent_count']}")
    print(f"tick_count {summary['tick_count']}")
    print(f"html_sha256 {html_sha}")
    print(f"wrote {args.html_out}")
    print(f"wrote {args.summary_out}")
    return 0


def _load_traces(trace_dir: Path) -> dict[str, DecisionTrace]:
    if not trace_dir.is_dir():
        raise ValueError("trace-dir must be a directory")
    traces = {}
    for path in sorted(trace_dir.glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        trace = trace_from_dict(value)
        verify_trace(trace)
        actor_ids = {event.actor_id for event in trace.events}
        if len(actor_ids) != 1:
            raise ValueError(f"trace has multiple actor ids: {path.name}")
        agent_id = next(iter(actor_ids))
        if path.stem != agent_id:
            raise ValueError(f"trace filename {path.name} does not match actor {agent_id}")
        traces[agent_id] = trace
    if not traces:
        raise ValueError("trace-dir contains no agent trace JSON files")
    return dict(sorted(traces.items()))


def _parse_obstacle(value: str) -> GridPoint:
    parts = value.split(",")
    if len(parts) != 2:
        raise ValueError(f"obstacle must use x,y format: {value}")
    try:
        x = int(parts[0])
        y = int(parts[1])
    except ValueError as exc:
        raise ValueError(f"obstacle coordinates must be integers: {value}") from exc
    return GridPoint(x, y)


def _validate_obstacles(
    *,
    obstacles: tuple[GridPoint, ...],
    grid_width: int,
    grid_height: int,
) -> None:
    if grid_width <= 0 or grid_height <= 0:
        raise ValueError("grid dimensions must be positive")
    if len(set(obstacles)) != len(obstacles):
        raise ValueError("obstacles must be unique")
    for obstacle in obstacles:
        if not 0 <= obstacle.x < grid_width or not 0 <= obstacle.y < grid_height:
            raise ValueError("obstacle outside render grid")


def _timeline_from_traces(
    *,
    traces: dict[str, DecisionTrace],
    grid_width: int,
    grid_height: int,
) -> list[dict[str, Any]]:
    if grid_width <= 0 or grid_height <= 0:
        raise ValueError("grid dimensions must be positive")
    expected_ticks = None
    timeline: list[dict[str, Any]] = []
    for agent_id, trace in sorted(traces.items()):
        if expected_ticks is None:
            expected_ticks = len(trace.events)
            timeline = [{"tick": tick, "agents": {}} for tick in range(expected_ticks)]
        elif len(trace.events) != expected_ticks:
            raise ValueError("all traces must have the same event count")
        for event in trace.events:
            command = event.command
            if command.get("type") != "grid_step":
                raise ValueError("trace command type must be grid_step")
            if command.get("grid_width") != grid_width or command.get("grid_height") != grid_height:
                raise ValueError("trace grid dimensions do not match requested render grid")
            tick = event.tick
            if tick < 0 or expected_ticks is None or tick >= expected_ticks:
                raise ValueError("trace event tick outside timeline")
            position = GridPoint(command["accepted_x"], command["accepted_y"])
            if not 0 <= position.x < grid_width or not 0 <= position.y < grid_height:
                raise ValueError("accepted position outside render grid")
            timeline[tick]["agents"][agent_id] = {
                "x": position.x,
                "y": position.y,
                "decision": event.decision,
                "sha256": event.sha256,
            }
    for frame in timeline:
        if set(frame["agents"]) != set(traces):
            raise ValueError("timeline frame is missing one or more agents")
    return timeline


def _render_html(
    *,
    title: str,
    grid_width: int,
    grid_height: int,
    obstacles: tuple[GridPoint, ...],
    timeline: list[dict[str, Any]],
    trace_summary_shas: dict[str, str],
    replay: dict[str, Any],
) -> str:
    safe_title = html.escape(title)
    agent_ids = sorted(trace_summary_shas)
    obstacle_set = {(point.x, point.y) for point in obstacles}
    frames = "\n".join(
        _render_frame(
            frame=frame,
            grid_width=grid_width,
            grid_height=grid_height,
            obstacle_set=obstacle_set,
            agent_ids=agent_ids,
        )
        for frame in timeline
    )
    trace_rows = "\n".join(
        f"<tr><td>{html.escape(agent_id)}</td><td><code>{sha}</code></td></tr>"
        for agent_id, sha in sorted(trace_summary_shas.items())
    )
    final_rows = "\n".join(
        f"<tr><td>{html.escape(agent_id)}</td><td>({point['x']}, {point['y']})</td></tr>"
        for agent_id, point in sorted(replay["final_positions"].items())
    )
    return (
        "<!doctype html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\">\n"
        f"  <title>{safe_title}</title>\n"
        "  <style>\n"
        "    body{font-family:Arial,sans-serif;margin:24px;color:#111827;background:#f8fafc;}\n"
        "    h1{font-size:22px;margin:0 0 8px;}\n"
        "    h2{font-size:18px;margin:24px 0 8px;}\n"
        "    .meta{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:16px 0;}\n"
        "    .metric{background:white;border:1px solid #d1d5db;border-radius:6px;padding:10px;}\n"
        "    .stage{display:grid;grid-template-columns:minmax(0,1fr) 280px;gap:16px;align-items:start;background:#0f172a;color:#e5e7eb;border-radius:8px;padding:16px;margin-top:16px;}\n"
        "    .stage canvas{width:100%;height:auto;background:#111827;border:1px solid #334155;border-radius:6px;display:block;}\n"
        "    .panel{background:#111827;border:1px solid #334155;border-radius:6px;padding:12px;}\n"
        "    .panel h2{font-size:16px;margin:0 0 10px;color:#f8fafc;}\n"
        "    .panel button{border:1px solid #64748b;background:#f8fafc;color:#0f172a;border-radius:4px;padding:7px 10px;font-weight:700;}\n"
        "    .panel input{width:100%;margin:12px 0;}\n"
        "    .panel .readout{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px;}\n"
        "    .panel .readout div{background:#0f172a;border:1px solid #334155;border-radius:4px;padding:8px;}\n"
        "    .panel code{color:#bfdbfe;word-break:break-all;}\n"
        "    .agent-list{font-size:12px;line-height:1.5;margin-top:10px;}\n"
        "    .frames{display:flex;flex-wrap:wrap;gap:16px;align-items:flex-start;}\n"
        "    .frame{background:white;border:1px solid #d1d5db;border-radius:6px;padding:10px;}\n"
        "    .frame h3{font-size:14px;margin:0 0 8px;}\n"
        "    table{border-collapse:collapse;background:white;border:1px solid #d1d5db;}\n"
        "    td,th{border:1px solid #d1d5db;padding:6px 8px;text-align:left;}\n"
        "    code{font-size:12px;}\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        f"  <h1>{safe_title}</h1>\n"
        "  <p>Animated and static replay generated from verified DecisionTrace files. Qwen is not in this motion loop.</p>\n"
        "  <div class=\"meta\">\n"
        f"    <div class=\"metric\">Agents<br><strong>{len(agent_ids)}</strong></div>\n"
        f"    <div class=\"metric\">Ticks<br><strong>{len(timeline)}</strong></div>\n"
        f"    <div class=\"metric\">Replay violations<br><strong>{replay['same_cell_collision_count']} same-cell / {replay['swap_collision_count']} swap / {replay['obstacle_occupancy_violation_count']} obstacle</strong></div>\n"
        "  </div>\n"
        f"{_render_animation_panel(grid_width=grid_width, grid_height=grid_height, obstacles=obstacles, timeline=timeline, agent_ids=agent_ids, replay=replay)}"
        "  <h2>Timeline</h2>\n"
        f"  <div class=\"frames\">{frames}</div>\n"
        "  <h2>Trace Summary SHAs</h2>\n"
        f"  <table><thead><tr><th>Agent</th><th>Summary SHA</th></tr></thead><tbody>{trace_rows}</tbody></table>\n"
        "  <h2>Final Positions</h2>\n"
        f"  <table><thead><tr><th>Agent</th><th>Position</th></tr></thead><tbody>{final_rows}</tbody></table>\n"
        "</body>\n"
        "</html>\n"
    )


def _render_animation_panel(
    *,
    grid_width: int,
    grid_height: int,
    obstacles: tuple[GridPoint, ...],
    timeline: list[dict[str, Any]],
    agent_ids: list[str],
    replay: dict[str, Any],
) -> str:
    payload = {
        "agent_ids": agent_ids,
        "colors": {agent_id: AGENT_COLORS[index % len(AGENT_COLORS)] for index, agent_id in enumerate(agent_ids)},
        "grid": {"width": grid_width, "height": grid_height},
        "obstacles": [point.to_dict() for point in obstacles],
        "timeline": timeline,
    }
    payload_json = (
        json.dumps(payload, sort_keys=True, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    agent_rows = "".join(
        f"<div><span style=\"color:{AGENT_COLORS[index % len(AGENT_COLORS)]}\">&#9679;</span> {html.escape(agent_id)}</div>"
        for index, agent_id in enumerate(agent_ids)
    )
    return (
        "  <section class=\"stage\" aria-label=\"animated swarm replay\">\n"
        "    <canvas id=\"swarm-canvas\" width=\"1040\" height=\"620\"></canvas>\n"
        "    <aside class=\"panel\">\n"
        "      <h2>Replay</h2>\n"
        "      <button id=\"play-toggle\" type=\"button\">Play</button>\n"
        f"      <input id=\"tick-slider\" type=\"range\" min=\"0\" max=\"{len(timeline) - 1}\" value=\"0\" step=\"1\" aria-label=\"Replay tick\">\n"
        "      <div class=\"readout\">\n"
        "        <div>Tick<br><strong id=\"tick-label\">0</strong></div>\n"
        f"        <div>Agents<br><strong>{len(agent_ids)}</strong></div>\n"
        f"        <div>Same-cell<br><strong>{replay['same_cell_collision_count']}</strong></div>\n"
        f"        <div>Obstacle<br><strong>{replay['obstacle_occupancy_violation_count']}</strong></div>\n"
        "      </div>\n"
        f"      <div class=\"agent-list\">{agent_rows}</div>\n"
        "      <p><code>deterministic 2D trace replay; no DimOS or 3D physics claim</code></p>\n"
        "    </aside>\n"
        "  </section>\n"
        f"  <script id=\"swarm-data\" type=\"application/json\">{payload_json}</script>\n"
        "  <script>\n"
        "  (function(){\n"
        "    const data = JSON.parse(document.getElementById('swarm-data').textContent);\n"
        "    const canvas = document.getElementById('swarm-canvas');\n"
        "    const slider = document.getElementById('tick-slider');\n"
        "    const label = document.getElementById('tick-label');\n"
        "    const button = document.getElementById('play-toggle');\n"
        "    const ctx = canvas.getContext && canvas.getContext('2d');\n"
        "    if(!ctx){\n"
        "      const fallback = document.createElement('div');\n"
        "      fallback.className = 'panel';\n"
        "      fallback.textContent = 'Canvas not supported; use static frames below.';\n"
        "      canvas.replaceWith(fallback);\n"
        "      button.disabled = true;\n"
        "      slider.disabled = true;\n"
        "      return;\n"
        "    }\n"
        "    const obstacleSet = new Set(data.obstacles.map(p => p.x + ',' + p.y));\n"
        "    let tick = 0;\n"
        "    let playing = false;\n"
        "    let timer = null;\n"
        "    function cellRect(x,y){\n"
        "      const pad = 70;\n"
        "      const w = (canvas.width - pad*2) / data.grid.width;\n"
        "      const h = (canvas.height - pad*2) / data.grid.height;\n"
        "      return {x:pad+x*w,y:pad+y*h,w:w,h:h};\n"
        "    }\n"
        "    function cellPath(r){\n"
        "      ctx.beginPath();\n"
        "      if(typeof ctx.roundRect === 'function'){\n"
        "        ctx.roundRect(r.x+4,r.y+4,r.w-8,r.h-8,8);\n"
        "      } else {\n"
        "        ctx.rect(r.x+4,r.y+4,r.w-8,r.h-8);\n"
        "      }\n"
        "    }\n"
        "    function drawGrid(){\n"
        "      ctx.fillStyle = '#111827';\n"
        "      ctx.fillRect(0,0,canvas.width,canvas.height);\n"
        "      for(let y=0;y<data.grid.height;y++){\n"
        "        for(let x=0;x<data.grid.width;x++){\n"
        "          const r = cellRect(x,y);\n"
        "          ctx.fillStyle = obstacleSet.has(x+','+y) ? '#475569' : '#1f2937';\n"
        "          ctx.strokeStyle = '#334155';\n"
        "          ctx.lineWidth = 2;\n"
        "          cellPath(r);\n"
        "          ctx.fill();\n"
        "          ctx.stroke();\n"
        "        }\n"
        "      }\n"
        "    }\n"
        "    function drawAgents(frame){\n"
        "      data.agent_ids.forEach((id,index) => {\n"
        "        const state = frame.agents[id];\n"
        "        const r = cellRect(state.x,state.y);\n"
        "        const cx = r.x + r.w/2;\n"
        "        const cy = r.y + r.h/2;\n"
        "        ctx.fillStyle = 'rgba(0,0,0,0.35)';\n"
        "        ctx.beginPath();\n"
        "        ctx.ellipse(cx+8,cy+16,26,10,0,0,Math.PI*2);\n"
        "        ctx.fill();\n"
        "        ctx.fillStyle = data.colors[id];\n"
        "        ctx.beginPath();\n"
        "        ctx.arc(cx,cy,24,0,Math.PI*2);\n"
        "        ctx.fill();\n"
        "        ctx.strokeStyle = '#f8fafc';\n"
        "        ctx.lineWidth = 3;\n"
        "        ctx.stroke();\n"
        "        ctx.fillStyle = '#ffffff';\n"
        "        ctx.font = 'bold 15px Arial';\n"
        "        ctx.textAlign = 'center';\n"
        "        ctx.textBaseline = 'middle';\n"
        "        ctx.fillText(String(index),cx,cy);\n"
        "      });\n"
        "    }\n"
        "    function draw(){\n"
        "      const frame = data.timeline[tick];\n"
        "      drawGrid();\n"
        "      drawAgents(frame);\n"
        "      label.textContent = String(frame.tick);\n"
        "      slider.value = String(tick);\n"
        "    }\n"
        "    function step(){\n"
        "      tick = (tick + 1) % data.timeline.length;\n"
        "      draw();\n"
        "    }\n"
        "    button.addEventListener('click', () => {\n"
        "      playing = !playing;\n"
        "      button.textContent = playing ? 'Pause' : 'Play';\n"
        "      if(playing){ timer = setInterval(step, 420); }\n"
        "      else { clearInterval(timer); timer = null; }\n"
        "    });\n"
        "    slider.addEventListener('input', () => { tick = Number(slider.value); draw(); });\n"
        "    draw();\n"
        "  }());\n"
        "  </script>\n"
    )


def _render_frame(
    *,
    frame: dict[str, Any],
    grid_width: int,
    grid_height: int,
    obstacle_set: set[tuple[int, int]],
    agent_ids: list[str],
) -> str:
    svg_width = MARGIN * 2 + grid_width * (CELL_SIZE + CELL_GAP) - CELL_GAP
    svg_height = MARGIN * 2 + grid_height * (CELL_SIZE + CELL_GAP) - CELL_GAP
    cells = []
    for y in range(grid_height):
        for x in range(grid_width):
            fill = "#e5e7eb" if (x, y) in obstacle_set else "#ffffff"
            stroke = "#9ca3af"
            px = MARGIN + x * (CELL_SIZE + CELL_GAP)
            py = MARGIN + y * (CELL_SIZE + CELL_GAP)
            cells.append(
                f"<rect x=\"{px}\" y=\"{py}\" width=\"{CELL_SIZE}\" height=\"{CELL_SIZE}\" fill=\"{fill}\" stroke=\"{stroke}\"/>"
            )
    agents = []
    for index, agent_id in enumerate(agent_ids):
        state = frame["agents"][agent_id]
        color = AGENT_COLORS[index % len(AGENT_COLORS)]
        cx = MARGIN + state["x"] * (CELL_SIZE + CELL_GAP) + CELL_SIZE // 2
        cy = MARGIN + state["y"] * (CELL_SIZE + CELL_GAP) + CELL_SIZE // 2
        label = agent_id.rsplit("-", maxsplit=1)[-1]
        agents.append(
            f"<circle cx=\"{cx}\" cy=\"{cy}\" r=\"13\" fill=\"{color}\"/>"
            f"<text x=\"{cx}\" y=\"{cy + 4}\" text-anchor=\"middle\" font-size=\"11\" fill=\"white\">{html.escape(label)}</text>"
        )
    legend = " ".join(
        f"{html.escape(agent_id)}:{html.escape(frame['agents'][agent_id]['decision'])}"
        for agent_id in agent_ids
    )
    return (
        "<section class=\"frame\">"
        f"<h3>Tick {frame['tick']}</h3>"
        f"<svg width=\"{svg_width}\" height=\"{svg_height}\" viewBox=\"0 0 {svg_width} {svg_height}\" role=\"img\" aria-label=\"tick {frame['tick']} swarm grid\">"
        f"{''.join(cells)}{''.join(agents)}"
        "</svg>"
        f"<div><code>{legend}</code></div>"
        "</section>"
    )


if __name__ == "__main__":
    raise SystemExit(main())
