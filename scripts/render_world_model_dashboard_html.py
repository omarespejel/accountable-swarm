#!/usr/bin/env python3
"""Render verified world-model dashboard data as deterministic HTML."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import sys
from typing import Any

from accountable_swarm.trace.models import canonical_json


REPORT_SCHEMA_VERSION = "world-model-dashboard-html-report.v1"
DATA_SCHEMA_VERSION = "world-model-dashboard-data.v1"
DEFAULT_DATA_PATH = Path("runs/dashboard/world_model_x/data.json")
DEFAULT_HTML_OUT = Path("runs/dashboard/world_model_x/index.html")
DEFAULT_SUMMARY_OUT = Path("runs/dashboard/world_model_x/summary.json")
SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"Authorization:\s*Bearer\s+\S+", re.IGNORECASE),
    re.compile(r"ALIBABA_API_KEY\s*=\s*\S+", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9._-]{6,}"),
)
AGENT_COLORS = ("#0f766e", "#7c3aed", "#dc2626", "#2563eb", "#d97706", "#0891b2")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument("--html-out", type=Path, default=DEFAULT_HTML_OUT)
    parser.add_argument("--summary-out", type=Path, default=DEFAULT_SUMMARY_OUT)
    args = parser.parse_args()

    try:
        repo_root = _find_repo_root(Path.cwd())
        data_path = _repo_path(repo_root, args.data)
        html_out = _repo_path(repo_root, args.html_out)
        summary_out = _repo_path(repo_root, args.summary_out)
        _require_inside_repo(repo_root, data_path, "data")
        _require_inside_repo(repo_root, html_out, "html-out")
        _require_inside_repo(repo_root, summary_out, "summary-out")

        data = _read_data(data_path)
        summary = _build_summary(repo_root=repo_root, data=data, data_path=data_path, html_out=html_out)
        html_text = _render_html(data=data, summary=summary)
        html_sha = hashlib.sha256(html_text.encode("utf-8")).hexdigest()
        summary["html_sha256"] = html_sha
        summary["pass_conditions"]["html_sha256_recorded"] = _is_hex_64(html_sha)
        summary["outcome"] = "GO" if all(summary["pass_conditions"].values()) else "NARROW_CLAIM"
        summary_text = canonical_json(summary)
        if _contains_secret_material(html_text) or _contains_secret_material(summary_text):
            raise ValueError("rendered dashboard would contain secret material")
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"world-model dashboard render failed: {exc}", file=sys.stderr)
        return 4

    html_out.parent.mkdir(parents=True, exist_ok=True)
    summary_out.parent.mkdir(parents=True, exist_ok=True)
    html_out.write_text(html_text, encoding="utf-8")
    summary_out.write_text(summary_text + "\n", encoding="utf-8")

    print(f"outcome {summary['outcome']}")
    print(f"html {_display_path(repo_root, html_out)}")
    print(f"summary {_display_path(repo_root, summary_out)}")
    print(f"html_sha256 {summary['html_sha256']}")
    return 0 if summary["outcome"] == "GO" else 4


def _read_data(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError("dashboard data file is required")
    text = path.read_text(encoding="utf-8")
    if _contains_secret_material(text):
        raise ValueError("dashboard data contains secret material")
    payload = json.loads(text)
    data = _require_dict(payload, "dashboard data")
    if data.get("schema_version") != DATA_SCHEMA_VERSION:
        raise ValueError("dashboard data uses an unsupported schema")
    if canonical_json(data) != text.rstrip("\n"):
        raise ValueError("dashboard data must be canonical JSON")
    if _contains_raw_float(data):
        raise ValueError("dashboard data must not contain raw floats")
    if _contains_absolute_path(data):
        raise ValueError("dashboard data must not contain absolute paths")
    _validate_data(data)
    return data


def _validate_data(data: dict[str, Any]) -> None:
    grid = _require_dict(data.get("grid"), "grid")
    width = _require_positive_int(grid, "width")
    height = _require_positive_int(grid, "height")
    _validate_image(data.get("image"))
    _validate_dimos_export(data.get("dimos_export"))
    timeline = _require_list(data.get("timeline"), "timeline")
    if not timeline:
        raise ValueError("timeline must contain at least one frame")
    world_model = _require_dict(data.get("world_model"), "world_model")
    if _require_positive_int(world_model, "state_count") != len(timeline):
        raise ValueError("world_model state_count must match timeline length")
    if not _is_hex_64(world_model.get("first_world_model_sha")):
        raise ValueError("first_world_model_sha must be a 64-character lowercase hex string")
    if not _is_hex_64(world_model.get("last_world_model_sha")):
        raise ValueError("last_world_model_sha must be a 64-character lowercase hex string")
    if not _is_hex_64(world_model.get("export_trace_summary_sha")):
        raise ValueError("export_trace_summary_sha must be a 64-character lowercase hex string")
    agent_trace_shas = _require_dict(data.get("agent_trace_summary_shas"), "agent_trace_summary_shas")
    if not agent_trace_shas:
        raise ValueError("agent_trace_summary_shas must not be empty")
    for agent_id, trace_sha in agent_trace_shas.items():
        if not isinstance(agent_id, str) or not agent_id:
            raise ValueError("agent ids must be non-empty strings")
        if not _is_hex_64(trace_sha):
            raise ValueError(f"agent trace summary SHA is invalid for {agent_id}")
    hazard_trace_sha = data.get("hazard_trace_summary_sha")
    if not _is_hex_64(hazard_trace_sha):
        raise ValueError("hazard_trace_summary_sha must be a 64-character lowercase hex string")
    _validate_hazard(data.get("hazard"), width=width, height=height)
    expected_agents: set[str] | None = None
    for index, frame_value in enumerate(timeline):
        frame = _require_dict(frame_value, f"timeline[{index}]")
        if _require_int(frame, "tick") != index:
            raise ValueError("timeline ticks must be contiguous from zero")
        if not _is_hex_64(frame.get("world_model_sha")):
            raise ValueError("timeline world_model_sha must be a 64-character lowercase hex string")
        if index == 0 and frame["world_model_sha"] != world_model["first_world_model_sha"]:
            raise ValueError("first timeline world_model_sha does not match world_model summary")
        if index == len(timeline) - 1 and frame["world_model_sha"] != world_model["last_world_model_sha"]:
            raise ValueError("last timeline world_model_sha does not match world_model summary")
        _validate_observations(frame.get("observations"), hazard_trace_sha=hazard_trace_sha, width=width, height=height)
        _validate_hazards(frame.get("hazards"), width=width, height=height)
        agents = _require_list(frame.get("agents"), "timeline agents")
        if not agents:
            raise ValueError("timeline frame must contain at least one agent")
        frame_agents: set[str] = set()
        for agent_value in agents:
            agent = _require_dict(agent_value, "timeline agent")
            agent_id = _require_string(agent, "agent_id")
            if agent_id in frame_agents:
                raise ValueError(f"duplicate timeline agent: {agent_id}")
            frame_agents.add(agent_id)
            if agent_id not in agent_trace_shas:
                raise ValueError(f"timeline references unknown agent trace: {agent_id}")
            if agent.get("trace_summary_sha") != agent_trace_shas[agent_id]:
                raise ValueError(f"timeline agent trace_summary_sha mismatch for {agent_id}")
            if not _is_hex_64(agent.get("event_sha256")):
                raise ValueError(f"event_sha256 is invalid for {agent_id}")
            if agent.get("world_model_decision_event_sha") != agent["event_sha256"]:
                raise ValueError(f"world_model_decision_event_sha mismatch for {agent_id}")
            _validate_cell(agent.get("cell"), width=width, height=height, name=f"{agent_id} cell")
            _validate_cell(agent.get("goal"), width=width, height=height, name=f"{agent_id} goal")
            _validate_command(agent.get("command"), width=width, height=height, agent_id=agent_id)
        if expected_agents is None:
            expected_agents = frame_agents
        elif frame_agents != expected_agents:
            raise ValueError("timeline agent set must stay stable")
        _validate_reservations(frame.get("reservations"), agents=agents)
        _require_list(frame.get("predicted_conflicts"), "predicted_conflicts")


def _validate_image(value: Any) -> None:
    image = _require_dict(value, "image")
    if "asset_path" in image:
        asset_path = image["asset_path"]
        if not isinstance(asset_path, str) or not asset_path:
            raise ValueError("image asset_path must be a non-empty string")
        if Path(asset_path).is_absolute():
            raise ValueError("image asset_path must be relative")


def _validate_dimos_export(value: Any) -> None:
    if value is None:
        return
    export = _require_dict(value, "dimos_export")
    schema = export.get("bridge_manifest_schema")
    if not isinstance(schema, str) or not schema:
        raise ValueError("dimos_export bridge_manifest_schema must be a non-empty string")
    for key in ("bridge_outcome", "overall_outcome", "runtime_outcome", "timeline_path", "manifest_path"):
        if not isinstance(export.get(key), str) or not export[key]:
            raise ValueError(f"dimos_export {key} must be a non-empty string")
    for key in ("event_count", "scenario_count"):
        item = export.get(key)
        if isinstance(item, bool) or not isinstance(item, int):
            raise ValueError(f"dimos_export {key} must be an integer")


def _validate_observations(value: Any, *, hazard_trace_sha: str, width: int, height: int) -> None:
    observations = _require_list(value, "observations")
    if not observations:
        raise ValueError("timeline frame must contain at least one observation")
    for observation_value in observations:
        observation = _require_dict(observation_value, "observation")
        if observation.get("source_trace_sha") != hazard_trace_sha:
            raise ValueError("observation source_trace_sha must match hazard trace summary")
        _require_string(observation, "observation_id")
        _require_string(observation, "source")
        _require_string(observation, "label")
        _validate_cell(observation.get("cell"), width=width, height=height, name="observation cell")
        score_milli = _require_int(observation, "score_milli")
        if not 0 <= score_milli <= 1000:
            raise ValueError("observation score_milli must be between 0 and 1000")
        bbox = observation.get("bbox_2d_norm_1000")
        if bbox is not None:
            _validate_bbox_2d_norm_1000(bbox)


def _validate_bbox_2d_norm_1000(value: Any) -> None:
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError("bbox_2d_norm_1000 must contain four integers")
    x0, y0, x1, y1 = (_require_nonbool_int(item, "bbox_2d_norm_1000 value") for item in value)
    if not 0 <= x0 < x1 <= 1000 or not 0 <= y0 < y1 <= 1000:
        raise ValueError("bbox_2d_norm_1000 must be within 0..1000 with positive area")


def _validate_hazards(value: Any, *, width: int, height: int) -> None:
    for hazard in _require_list(value, "hazards"):
        _validate_cell(hazard, width=width, height=height, name="hazard")


def _validate_hazard(value: Any, *, width: int, height: int) -> None:
    if value is None:
        return
    hazard = _require_dict(value, "hazard")
    _validate_cell(hazard.get("cell"), width=width, height=height, name="hazard cell")


def _validate_reservations(value: Any, *, agents: list[Any]) -> None:
    reservations = _require_list(value, "reservations")
    agent_cells = {
        agent["agent_id"]: agent["cell"]
        for agent in (_require_dict(agent, "reservation agent") for agent in agents)
    }
    for reservation_value in reservations:
        reservation = _require_dict(reservation_value, "reservation")
        agent_id = _require_string(reservation, "agent_id")
        if agent_id not in agent_cells:
            raise ValueError(f"reservation references unknown agent: {agent_id}")
        if reservation.get("cell") != agent_cells[agent_id]:
            raise ValueError(f"reservation cell mismatch for {agent_id}")


def _validate_cell(value: Any, *, width: int, height: int, name: str) -> None:
    cell = _require_dict(value, name)
    x = _require_int(cell, "x")
    y = _require_int(cell, "y")
    if not 0 <= x < width or not 0 <= y < height:
        raise ValueError(f"{name} outside grid")


def _validate_command(value: Any, *, width: int, height: int, agent_id: str) -> None:
    command = _require_dict(value, f"{agent_id} command")
    for key in ("from_x", "from_y", "proposed_x", "proposed_y", "accepted_x", "accepted_y", "goal_x", "goal_y"):
        _require_int(command, key)
    for prefix in ("from", "proposed", "accepted", "goal"):
        x = command[f"{prefix}_x"]
        y = command[f"{prefix}_y"]
        if not 0 <= x < width or not 0 <= y < height:
            raise ValueError(f"{agent_id} {prefix} command cell outside grid")


def _build_summary(*, repo_root: Path, data: dict[str, Any], data_path: Path, html_out: Path) -> dict[str, Any]:
    timeline = _require_list(data.get("timeline"), "timeline")
    agent_count = len(_require_list(timeline[0].get("agents"), "timeline agents"))
    pass_conditions = {
        "data_schema_valid": data.get("schema_version") == DATA_SCHEMA_VERSION,
        "timeline_nonempty": bool(timeline),
        "world_model_hashes_present": all(_is_hex_64(frame.get("world_model_sha")) for frame in timeline),
        "event_hashes_bound": all(
            agent.get("event_sha256") == agent.get("world_model_decision_event_sha")
            for frame in timeline
            for agent in _require_list(frame.get("agents"), "timeline agents")
        ),
        "qwen_evidence_present": bool(data.get("hazard_trace_summary_sha")),
        "planner_metrics_present": isinstance(data.get("planner_metrics"), dict),
        "non_claims_present": "no Qwen real-time control" in data.get("non_claims", ()),
        "html_sha256_recorded": False,
    }
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "outcome": "NARROW_CLAIM",
        "data_path": _display_path(repo_root, data_path),
        "html_path": _display_path(repo_root, html_out),
        "tick_count": len(timeline),
        "agent_count": agent_count,
        "first_world_model_sha": data["world_model"]["first_world_model_sha"],
        "last_world_model_sha": data["world_model"]["last_world_model_sha"],
        "hazard_trace_summary_sha": data["hazard_trace_summary_sha"],
        "planner_metrics": data.get("planner_metrics", {}),
        "html_sha256": "",
        "pass_conditions": pass_conditions,
        "non_claims": data.get("non_claims", []),
    }


def _render_html(*, data: dict[str, Any], summary: dict[str, Any]) -> str:
    data_json = _safe_json(data)
    title = "Accountable World Model Dashboard"
    grid = data["grid"]
    model = data.get("model") or "fixture"
    mode = data.get("mode") or "unknown"
    hazard_cell = _hazard_cell_label(data.get("hazard"))
    source_image = _require_dict(data.get("image"), "image")
    source_image_asset = source_image.get("asset_path")
    return (
        "<!doctype html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\">\n"
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"  <title>{html.escape(title)}</title>\n"
        "  <style>\n"
        "    :root{color-scheme:light;--ink:#172033;--muted:#5f6b7a;--line:#d8dee8;--panel:#ffffff;--wash:#eef3f7;--teal:#0f766e;--violet:#7c3aed;--amber:#b45309;--red:#dc2626;}\n"
        "    *{box-sizing:border-box;}\n"
        "    body{margin:0;background:#f7f9fb;color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,\"Segoe UI\",sans-serif;}\n"
        "    header{padding:24px 28px 16px;border-bottom:1px solid var(--line);background:#ffffff;}\n"
        "    h1{margin:0;font-size:28px;line-height:1.1;font-weight:760;letter-spacing:0;}\n"
        "    .subtitle{margin:8px 0 0;color:var(--muted);max-width:980px;font-size:15px;line-height:1.45;}\n"
        "    main{display:grid;grid-template-columns:minmax(520px,1.45fr) minmax(360px,.9fr);gap:18px;padding:18px 28px 28px;align-items:start;}\n"
        "    section,.panel{background:var(--panel);border:1px solid var(--line);border-radius:8px;}\n"
        "    .stage{padding:14px;}\n"
        "    .stage-grid{display:grid;grid-template-columns:minmax(280px,.72fr) minmax(420px,1fr);gap:12px;align-items:start;}\n"
        "    .toolbar{display:flex;align-items:center;gap:10px;margin-bottom:12px;}\n"
        "    button{appearance:none;border:1px solid #8aa0b5;background:#fff;border-radius:6px;padding:8px 12px;font-weight:700;color:var(--ink);cursor:pointer;}\n"
        "    input[type=range]{width:100%;min-width:160px;accent-color:var(--teal);}\n"
        "    canvas{width:100%;height:auto;display:block;background:#152032;border-radius:6px;border:1px solid #334155;}\n"
        "    .source-frame{border:1px solid var(--line);border-radius:6px;background:#fbfcfe;padding:10px;}\n"
        "    .source-frame h2{margin:0 0 8px;font-size:14px;line-height:1.2;}\n"
        "    .source-frame p{margin:0 0 8px;font-size:12px;color:var(--muted);line-height:1.4;}\n"
        "    .frame-wrap{position:relative;background:#0f172a;border-radius:6px;overflow:hidden;border:1px solid #334155;aspect-ratio:1 / 1;}\n"
        "    .frame-wrap img{display:block;width:100%;height:100%;object-fit:contain;background:#0f172a;}\n"
        "    .bbox{position:absolute;border:3px solid #c4b5fd;box-shadow:0 0 0 9999px rgba(124,58,237,0.08) inset;pointer-events:none;}\n"
        "    .source-fallback{display:flex;align-items:center;justify-content:center;min-height:260px;color:#cbd5e1;font-size:13px;padding:12px;text-align:center;}\n"
        "    .side{display:grid;gap:12px;}\n"
        "    .panel{padding:14px;}\n"
        "    .panel h2{margin:0 0 10px;font-size:15px;line-height:1.2;letter-spacing:0;color:#101828;}\n"
        "    .metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;}\n"
        "    .metric{border:1px solid var(--line);border-radius:6px;padding:9px;background:#fbfcfe;min-width:0;}\n"
        "    .metric span{display:block;color:var(--muted);font-size:12px;margin-bottom:3px;}\n"
        "    .metric strong{font-size:15px;word-break:break-word;}\n"
        "    .lane{display:grid;grid-template-columns:28px 1fr;gap:9px;align-items:start;margin:8px 0;}\n"
        "    .dot{width:18px;height:18px;border-radius:50%;margin-top:2px;}\n"
        "    .dot.qwen{background:var(--violet);} .dot.local{background:var(--teal);} .dot.trace{background:var(--amber);}\n"
        "    code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:11px;word-break:break-all;color:#243b53;}\n"
        "    .hash-list{display:grid;gap:8px;font-size:12px;}\n"
        "    .agent-row{display:grid;grid-template-columns:78px 74px 1fr;gap:8px;align-items:center;border-top:1px solid var(--line);padding:7px 0;font-size:12px;}\n"
        "    .agent-row button{all:unset;display:grid;grid-template-columns:78px 74px 1fr;gap:8px;align-items:center;width:100%;cursor:pointer;border-top:1px solid var(--line);padding:7px 0;font-size:12px;}\n"
        "    .agent-row button[data-selected=\"true\"]{background:#f5f8fc;border-radius:6px;padding-left:6px;padding-right:6px;}\n"
        "    .agent-chip{display:inline-flex;align-items:center;gap:6px;font-weight:700;}\n"
        "    .agent-swatch{width:10px;height:10px;border-radius:50%;display:inline-block;}\n"
        "    .notice{border-left:4px solid var(--amber);background:#fff7ed;padding:10px 12px;color:#663c00;font-size:13px;line-height:1.4;}\n"
        "    .nonclaims{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px;}\n"
        "    .pill{border:1px solid #cbd5e1;border-radius:999px;padding:4px 8px;background:#fff;font-size:11px;color:#475569;}\n"
        "    .legend{display:flex;gap:10px;flex-wrap:wrap;margin-top:10px;font-size:12px;color:#d9e5ef;}\n"
        "    .legend span{display:inline-flex;gap:5px;align-items:center;}\n"
        "    .legend i{width:10px;height:10px;border-radius:2px;display:inline-block;}\n"
        "    .detail-grid{display:grid;gap:8px;font-size:12px;}\n"
        "    .detail-grid code{font-size:11px;}\n"
        "    .detail-row{border-top:1px solid var(--line);padding-top:8px;}\n"
        "    .status-stack{display:grid;gap:8px;font-size:12px;}\n"
        "    .status-stack strong{font-size:13px;}\n"
        "    @media(max-width:1180px){.stage-grid{grid-template-columns:1fr;}}\n"
        "    @media(max-width:980px){main{grid-template-columns:1fr;padding:14px;}header{padding:18px 14px 12px;}h1{font-size:24px;}.metrics{grid-template-columns:1fr 1fr;}}\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "  <header>\n"
        f"    <h1>{title}</h1>\n"
        "    <p class=\"subtitle\">Qwen supplies bounded keyframe evidence. A deterministic local planner updates the world model and emits hash-bound DecisionTrace events. This page is a verified 2D replay artifact, not a physics or hardware claim.</p>\n"
        "  </header>\n"
        "  <main>\n"
        "    <section class=\"stage\" aria-label=\"world model replay stage\">\n"
        "      <div class=\"toolbar\">\n"
        "        <button id=\"play-toggle\" type=\"button\">Play</button>\n"
        f"        <input id=\"tick-slider\" type=\"range\" min=\"0\" max=\"{len(data['timeline']) - 1}\" value=\"0\" step=\"1\" aria-label=\"Replay tick\">\n"
        "      </div>\n"
        "      <div class=\"stage-grid\">\n"
        "        <div class=\"source-frame\">\n"
        "          <h2>Qwen Source Frame</h2>\n"
        "          <p>Bounded keyframe evidence only. The bbox is displayed exactly as persisted in the verified observation payload.</p>\n"
        "          <div class=\"frame-wrap\" id=\"frame-wrap\">\n"
        + (
            f"            <img id=\"source-image\" alt=\"Qwen source frame\" src=\"{html.escape(str(source_image_asset))}\">\n"
            if isinstance(source_image_asset, str) and source_image_asset
            else "            <div class=\"source-fallback\">No source-frame asset was packaged for this run.</div>\n"
        )
        + "            <div class=\"bbox\" id=\"bbox-overlay\" hidden></div>\n"
        "          </div>\n"
        "        </div>\n"
        "        <canvas id=\"world-canvas\" width=\"1120\" height=\"760\"></canvas>\n"
        "      </div>\n"
        "      <div class=\"legend\"><span><i style=\"background:#7c3aed\"></i>Qwen hazard evidence</span><span><i style=\"background:#0f766e\"></i>local planner agents</span><span><i style=\"background:#f59e0b\"></i>formation targets</span><span><i style=\"background:#ef4444\"></i>predicted conflict</span></div>\n"
        "    </section>\n"
        "    <aside class=\"side\">\n"
        "      <section class=\"panel\">\n"
        "        <h2>Run Summary</h2>\n"
        "        <div class=\"metrics\">\n"
        f"          <div class=\"metric\"><span>Mode</span><strong>{html.escape(str(mode))}</strong></div>\n"
        f"          <div class=\"metric\"><span>Model</span><strong>{html.escape(str(model))}</strong></div>\n"
        f"          <div class=\"metric\"><span>Grid</span><strong>{grid['width']} x {grid['height']}</strong></div>\n"
        f"          <div class=\"metric\"><span>Ticks</span><strong>{len(data['timeline'])}</strong></div>\n"
        f"          <div class=\"metric\"><span>Agents</span><strong>{summary['agent_count']}</strong></div>\n"
        f"          <div class=\"metric\"><span>Hazard</span><strong>{html.escape(hazard_cell)}</strong></div>\n"
        "        </div>\n"
        "      </section>\n"
        "      <section class=\"panel\">\n"
        "        <h2>Accountability Pipeline</h2>\n"
        "        <div class=\"lane\"><span class=\"dot qwen\"></span><div><strong>Qwen evidence</strong><br><code id=\"hazard-sha\"></code></div></div>\n"
        "        <div class=\"lane\"><span class=\"dot local\"></span><div><strong>Deterministic local planner</strong><br><span id=\"planner-readout\"></span></div></div>\n"
        "        <div class=\"lane\"><span class=\"dot trace\"></span><div><strong>World model hash</strong><br><code id=\"world-model-sha\"></code></div></div>\n"
        "      </section>\n"
        "      <section class=\"panel\">\n"
        "        <h2>Current Tick Decisions</h2>\n"
        "        <div id=\"agent-list\"></div>\n"
        "      </section>\n"
        "      <section class=\"panel\">\n"
        "        <h2>DecisionTrace Inspector</h2>\n"
        "        <div class=\"detail-grid\" id=\"trace-inspector\"></div>\n"
        "      </section>\n"
        "      <section class=\"panel\">\n"
        "        <h2>DimOS-ready Export</h2>\n"
        "        <div class=\"status-stack\" id=\"dimos-status\"></div>\n"
        "      </section>\n"
        "      <section class=\"panel\">\n"
        "        <h2>Verifier Notes</h2>\n"
        "        <div class=\"notice\">The rendered payload comes from <code>world-model-dashboard-data.v1</code>. Agent event hashes are checked against the world-model event hashes before this HTML is produced.</div>\n"
        "        <div class=\"nonclaims\" id=\"nonclaims\"></div>\n"
        "      </section>\n"
        "    </aside>\n"
        "  </main>\n"
        f"  <script id=\"dashboard-data\" type=\"application/json\">{data_json}</script>\n"
        "  <script>\n"
        "  (function(){\n"
        "    const data = JSON.parse(document.getElementById('dashboard-data').textContent);\n"
        "    const canvas = document.getElementById('world-canvas');\n"
        "    const ctx = canvas.getContext && canvas.getContext('2d');\n"
        "    const slider = document.getElementById('tick-slider');\n"
        "    const button = document.getElementById('play-toggle');\n"
        "    const worldModelSha = document.getElementById('world-model-sha');\n"
        "    const hazardSha = document.getElementById('hazard-sha');\n"
        "    const plannerReadout = document.getElementById('planner-readout');\n"
        "    const agentList = document.getElementById('agent-list');\n"
        "    const traceInspector = document.getElementById('trace-inspector');\n"
        "    const dimosStatus = document.getElementById('dimos-status');\n"
        "    const bboxOverlay = document.getElementById('bbox-overlay');\n"
        "    const sourceImage = document.getElementById('source-image');\n"
        "    const nonclaims = document.getElementById('nonclaims');\n"
        "    const colors = {\"sim-agent-0\":\"#0f766e\",\"sim-agent-1\":\"#7c3aed\",\"sim-agent-2\":\"#dc2626\",\"sim-agent-3\":\"#2563eb\",\"sim-agent-4\":\"#d97706\",\"sim-agent-5\":\"#0891b2\"};\n"
        "    let tick = 0;\n"
        "    let selectedAgentId = null;\n"
        "    let timer = null;\n"
        "    hazardSha.textContent = data.hazard_trace_summary_sha;\n"
        "    plannerReadout.textContent = `${data.planner_metrics.outcome || 'unknown'} / same-cell ${data.planner_metrics.same_cell_collision_count} / swap ${data.planner_metrics.swap_collision_count}`;\n"
        "    data.non_claims.forEach((claim) => { const span = document.createElement('span'); span.className = 'pill'; span.textContent = claim; nonclaims.appendChild(span); });\n"
        "    function appendDetailRow(container, label, value){\n"
        "      const row = document.createElement('div');\n"
        "      row.className = 'detail-row';\n"
        "      const strong = document.createElement('strong');\n"
        "      strong.textContent = label;\n"
        "      row.appendChild(strong);\n"
        "      row.appendChild(document.createElement('br'));\n"
        "      const code = document.createElement('code');\n"
        "      code.textContent = String(value);\n"
        "      row.appendChild(code);\n"
        "      container.appendChild(row);\n"
        "    }\n"
        "    function renderDimosStatus(){\n"
        "      dimosStatus.replaceChildren();\n"
        "      if(!data.dimos_export){ const empty = document.createElement('div'); empty.textContent = 'No DimOS bridge manifest was packaged for this run.'; dimosStatus.appendChild(empty); return; }\n"
        "      const rows = [\n"
        "        ['Bridge outcome', data.dimos_export.bridge_outcome],\n"
        "        ['Runtime outcome', data.dimos_export.runtime_outcome],\n"
        "        ['Overall outcome', data.dimos_export.overall_outcome],\n"
        "        ['Events', String(data.dimos_export.event_count)],\n"
        "        ['Scenarios', String(data.dimos_export.scenario_count)],\n"
        "      ];\n"
        "      rows.forEach(([label, value]) => appendDetailRow(dimosStatus, label, value));\n"
        "      const foot = document.createElement('div'); foot.className = 'notice'; foot.textContent = 'This panel proves replay/export status only. It does not claim DimOS executed, visualized, or controlled the swarm.'; dimosStatus.appendChild(foot);\n"
        "    }\n"
        "    function renderSourceFrame(frame){\n"
        "      if(!bboxOverlay || !sourceImage){ return; }\n"
        "      const observation = frame.observations && frame.observations[0];\n"
        "      if(!observation || !Array.isArray(observation.bbox_2d_norm_1000) || observation.bbox_2d_norm_1000.length !== 4 || !sourceImage.complete || !sourceImage.naturalWidth || !sourceImage.naturalHeight){ bboxOverlay.hidden = true; return; }\n"
        "      const [x0,y0,x1,y1] = observation.bbox_2d_norm_1000;\n"
        "      const wrap = sourceImage.parentElement;\n"
        "      if(!wrap){ bboxOverlay.hidden = true; return; }\n"
        "      const wrapWidth = wrap.clientWidth;\n"
        "      const wrapHeight = wrap.clientHeight;\n"
        "      const scale = Math.min(wrapWidth / sourceImage.naturalWidth, wrapHeight / sourceImage.naturalHeight);\n"
        "      const renderWidth = sourceImage.naturalWidth * scale;\n"
        "      const renderHeight = sourceImage.naturalHeight * scale;\n"
        "      const offsetX = (wrapWidth - renderWidth) / 2;\n"
        "      const offsetY = (wrapHeight - renderHeight) / 2;\n"
        "      bboxOverlay.hidden = false;\n"
        "      bboxOverlay.style.left = `${offsetX + renderWidth * (x0 / 1000)}px`;\n"
        "      bboxOverlay.style.top = `${offsetY + renderHeight * (y0 / 1000)}px`;\n"
        "      bboxOverlay.style.width = `${renderWidth * ((x1 - x0) / 1000)}px`;\n"
        "      bboxOverlay.style.height = `${renderHeight * ((y1 - y0) / 1000)}px`;\n"
        "    }\n"
        "    function draw(){\n"
        "      const frame = data.timeline[tick];\n"
        "      worldModelSha.textContent = frame.world_model_sha;\n"
        "      slider.value = String(tick);\n"
        "      renderSourceFrame(frame);\n"
        "      if(!ctx){ return; }\n"
        "      ctx.clearRect(0,0,canvas.width,canvas.height);\n"
        "      ctx.fillStyle = '#152032'; ctx.fillRect(0,0,canvas.width,canvas.height);\n"
        "      const pad = 74;\n"
        "      const cell = Math.min((canvas.width - pad * 2) / data.grid.width, (canvas.height - pad * 2) / data.grid.height);\n"
        "      const boardW = cell * data.grid.width;\n"
        "      const boardH = cell * data.grid.height;\n"
        "      const ox = (canvas.width - boardW) / 2;\n"
        "      const oy = (canvas.height - boardH) / 2;\n"
        "      function rectFor(point){ return {x: ox + point.x * cell, y: oy + point.y * cell, w: cell, h: cell}; }\n"
        "      for(let y=0;y<data.grid.height;y++){\n"
        "        for(let x=0;x<data.grid.width;x++){\n"
        "          const r = rectFor({x,y});\n"
        "          ctx.fillStyle = '#1e2b40'; ctx.fillRect(r.x+2,r.y+2,r.w-4,r.h-4);\n"
        "          ctx.strokeStyle = '#334155'; ctx.strokeRect(r.x+2,r.y+2,r.w-4,r.h-4);\n"
        "        }\n"
        "      }\n"
        "      if(data.hazard && data.hazard.cell){\n"
        "        const r = rectFor(data.hazard.cell);\n"
        "        ctx.fillStyle = 'rgba(124,58,237,0.32)'; ctx.fillRect(r.x+4,r.y+4,r.w-8,r.h-8);\n"
        "        ctx.strokeStyle = '#c4b5fd'; ctx.lineWidth = 4; ctx.strokeRect(r.x+6,r.y+6,r.w-12,r.h-12);\n"
        "      }\n"
        "      const goals = data.assigned_goals || {};\n"
        "      Object.entries(goals).forEach(([agentId, goal]) => {\n"
        "        const r = rectFor(goal);\n"
        "        ctx.strokeStyle = '#f59e0b'; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(r.x+10,r.y+10); ctx.lineTo(r.x+r.w-10,r.y+r.h-10); ctx.moveTo(r.x+r.w-10,r.y+10); ctx.lineTo(r.x+10,r.y+r.h-10); ctx.stroke();\n"
        "      });\n"
        "      frame.reservations.forEach((res) => { const r = rectFor(res.cell); ctx.fillStyle = 'rgba(20,184,166,0.16)'; ctx.fillRect(r.x+8,r.y+8,r.w-16,r.h-16); });\n"
        "      frame.predicted_conflicts.forEach((conflict) => { const r = rectFor(conflict.cell); ctx.strokeStyle = '#ef4444'; ctx.lineWidth = 5; ctx.strokeRect(r.x+12,r.y+12,r.w-24,r.h-24); });\n"
        "      frame.agents.forEach((agent) => {\n"
        "        const r = rectFor(agent.cell); const color = colors[agent.agent_id] || '#0891b2';\n"
        "        ctx.fillStyle = color; ctx.beginPath(); ctx.arc(r.x + r.w/2, r.y + r.h/2, Math.max(12, cell * 0.24), 0, Math.PI*2); ctx.fill();\n"
        "        ctx.fillStyle = '#ffffff'; ctx.font = '700 15px system-ui'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(agent.agent_id.replace('sim-agent-','A'), r.x+r.w/2, r.y+r.h/2);\n"
        "      });\n"
        "      ctx.fillStyle = '#dbeafe'; ctx.font = '700 18px system-ui'; ctx.textAlign = 'left'; ctx.fillText(`tick ${tick}`, 24, 34);\n"
        "    }\n"
        "    function renderRows(){\n"
        "      const frame = data.timeline[tick]; agentList.innerHTML = '';\n"
        "      if(!selectedAgentId && frame.agents.length){ selectedAgentId = frame.agents[0].agent_id; }\n"
        "      frame.agents.forEach((agent) => {\n"
        "        const row = document.createElement('div'); row.className = 'agent-row';\n"
        "        const button = document.createElement('button'); button.type = 'button'; button.dataset.selected = String(agent.agent_id === selectedAgentId);\n"
        "        const chip = document.createElement('span'); chip.className = 'agent-chip';\n"
        "        const swatch = document.createElement('span'); swatch.className = 'agent-swatch'; swatch.style.background = colors[agent.agent_id] || '#0891b2'; chip.appendChild(swatch); chip.append(agent.agent_id.replace('sim-agent-','A'));\n"
        "        const cell = document.createElement('span'); cell.textContent = `(${agent.cell.x},${agent.cell.y}) -> (${agent.goal.x},${agent.goal.y})`;\n"
        "        const code = document.createElement('code'); code.textContent = `${agent.decision} ${agent.event_sha256}`;\n"
        "        button.append(chip, cell, code); button.addEventListener('click', () => { selectedAgentId = agent.agent_id; renderRows(); renderInspector(); }); row.appendChild(button); agentList.appendChild(row);\n"
        "      });\n"
        "    }\n"
        "    function renderInspector(){\n"
        "      const frame = data.timeline[tick];\n"
        "      const agent = frame.agents.find((entry) => entry.agent_id === selectedAgentId) || frame.agents[0];\n"
        "      if(!agent){ traceInspector.replaceChildren(); return; }\n"
        "      selectedAgentId = agent.agent_id;\n"
        "      const conflictCells = (frame.predicted_conflicts || []).map((conflict) => `(${conflict.cell.x},${conflict.cell.y})`).join(', ') || 'none';\n"
        "      const reservationCells = (frame.reservations || []).map((reservation) => `${reservation.agent_id}:${reservation.cell.x},${reservation.cell.y}`).join(' | ') || 'none';\n"
        "      traceInspector.replaceChildren();\n"
        "      const rows = [\n"
        "        ['Agent', agent.agent_id],\n"
        "        ['Decision', agent.decision],\n"
        "        ['Reason', agent.reason],\n"
        "        ['Event SHA', agent.event_sha256],\n"
        "        ['Proposed', `(${agent.command.proposed_x},${agent.command.proposed_y})`],\n"
        "        ['Accepted', `(${agent.command.accepted_x},${agent.command.accepted_y})`],\n"
        "        ['Goal', `(${agent.command.goal_x},${agent.command.goal_y})`],\n"
        "        ['Reservations', reservationCells],\n"
        "        ['Predicted conflicts', conflictCells],\n"
        "      ];\n"
        "      rows.forEach(([label, value]) => appendDetailRow(traceInspector, label, value));\n"
        "    }\n"
        "    function update(){ draw(); renderRows(); renderInspector(); }\n"
        "    slider.addEventListener('input', () => { tick = Number(slider.value); update(); });\n"
        "    button.addEventListener('click', () => {\n"
        "      if(timer){ clearInterval(timer); timer = null; button.textContent = 'Play'; return; }\n"
        "      button.textContent = 'Pause'; timer = setInterval(() => { tick = (tick + 1) % data.timeline.length; update(); }, 650);\n"
        "    });\n"
        "    if(sourceImage){ sourceImage.addEventListener('load', update); }\n"
        "    window.addEventListener('resize', update);\n"
        "    renderDimosStatus();\n"
        "    update();\n"
        "  })();\n"
        "  </script>\n"
        "</body>\n"
        "</html>\n"
    )


def _hazard_cell_label(value: Any) -> str:
    if value is None:
        return "none"
    if isinstance(value, dict) and isinstance(value.get("cell"), dict):
        cell = value["cell"]
        return f"({cell.get('x')}, {cell.get('y')})"
    return "unknown"


def _safe_json(value: Any) -> str:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def _find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (
            (candidate / "pyproject.toml").is_file()
            and (candidate / "scripts" / "prepare_world_model_dashboard_pack.py").is_file()
            and (candidate / "fixtures" / "hazard_marker.ppm").is_file()
        ):
            return candidate
    raise ValueError("run from an accountable-swarm checkout")


def _repo_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _require_inside_repo(repo_root: Path, path: Path, name: str) -> None:
    resolved_root = repo_root.resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"{name} must be inside the repository") from exc


def _display_path(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _require_dict(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _require_list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be an array")
    return value


def _require_string(value: dict[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise ValueError(f"{key} must be a non-empty string")
    return item


def _require_int(value: dict[str, Any], key: str) -> int:
    item = value.get(key)
    if isinstance(item, bool) or not isinstance(item, int):
        raise ValueError(f"{key} must be an integer")
    return item


def _require_nonbool_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


def _require_positive_int(value: dict[str, Any], key: str) -> int:
    item = _require_int(value, key)
    if item <= 0:
        raise ValueError(f"{key} must be positive")
    return item


def _is_hex_64(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _contains_raw_float(value: Any) -> bool:
    if isinstance(value, float):
        return True
    if isinstance(value, dict):
        return any(_contains_raw_float(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_raw_float(item) for item in value)
    return False


def _contains_secret_material(value: str) -> bool:
    return any(pattern.search(value) for pattern in SECRET_PATTERNS)


def _contains_absolute_path(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_absolute_path(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_absolute_path(item) for item in value)
    if isinstance(value, str):
        return Path(value).is_absolute() or bool(re.match(r"^[A-Za-z]:[\\/]", value))
    return False


if __name__ == "__main__":
    raise SystemExit(main())
