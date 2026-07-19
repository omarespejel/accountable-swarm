"""Small stdlib HTTP server for manual Alibaba ECS deployment proof."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import os
from pathlib import Path
import shutil
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urlparse

from accountable_swarm.images import image_size
from accountable_swarm.qwen.bbox import parse_qwen_bbox_response
from accountable_swarm.qwen.client import DashScopeQwenClient, DashScopeResponseError, MissingAlibabaApiKey
from accountable_swarm.qwenguard.memory import (
    build_memory_replay_response,
    build_qwenguard_memory_replay,
    parse_memory_evidence_manifest_json,
    parse_memory_fixture_json,
)
from accountable_swarm.swarm import (
    AgentConfig,
    GridPoint,
    SUPPORTED_FORMATIONS,
    assign_formation_slots,
    build_agent_traces,
    compile_formation,
    run_swarm_custom,
)
from accountable_swarm.trace.models import PerceptionEvent, build_single_event_trace, canonical_json, verify_trace
from accountable_swarm.world_model import WorldAgentState, WorldModelState, WorldObservation, WorldReservation


FIXTURE_RESPONSE = '[{"bbox_2d":[250,250,750,750],"label":"marked hazard"}]'
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SWARM_DEMO_BUNDLE_DIR = REPO_ROOT / "runs/demo/swarm"
DEFAULT_HAZARD_FORMATION_REPLAY_DIR = REPO_ROOT / "runs/hazard_formation/recording_x_replay"
DEFAULT_WORLD_MODEL_DASHBOARD_DIR = REPO_ROOT / "runs/dashboard/recording_x"
DEFAULT_QWENGUARD_MEMORY_FIXTURE = REPO_ROOT / "fixtures/qwenguard_memory/observations.json"
DEFAULT_QWENGUARD_MEMORY_MANIFEST = REPO_ROOT / "fixtures/qwenguard_memory/manifest.json"
SWARM_DEMO_BUILD_COMMAND = "python3 scripts/build_swarm_demo_bundle.py"
HAZARD_FORMATION_BUILD_COMMAND = "python3 scripts/prepare_demo_recording_pack.py"
WORLD_MODEL_DASHBOARD_BUILD_COMMAND = "python3 scripts/prepare_demo_recording_pack.py"
INTERACTIVE_REPLAN_SCHEMA_VERSION = "interactive-replan-response.v1"
INTERACTIVE_MIN_GRID_SIZE = 5
INTERACTIVE_MAX_GRID_SIZE = 12
INTERACTIVE_MAX_TICKS = 32
INTERACTIVE_MAX_OBSTACLES = 24
INTERACTIVE_MAX_OBSERVATIONS = 4


class AccountableSwarmHandler(BaseHTTPRequestHandler):
    server_version = "AccountableSwarmHTTP/0.1"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            self._send_json({"status": "ok", "service": "accountable-swarm"})
            return
        if parsed.path == "/readyz":
            self._send_json(
                {
                    "status": "ok",
                    "has_alibaba_api_key": bool(os.getenv("ALIBABA_API_KEY")),
                    "default_vl_model": os.getenv("QWEN_VL_MODEL", "qwen3-vl-flash"),
                }
            )
            return
        if parsed.path == "/camera-fixture":
            self._handle_camera_fixture()
            return
        if parsed.path == "/qwenguard-memory-fixture":
            self._handle_qwenguard_memory_fixture()
            return
        if parsed.path == "/qwen-vl-fixture":
            query = parse_qs(parsed.query)
            model = query.get("model", [os.getenv("QWEN_VL_MODEL", "qwen3-vl-flash")])[0]
            self._handle_qwen_vl_fixture(model=model)
            return
        if parsed.path == "/swarm-demo":
            self._handle_swarm_demo_file("index.html")
            return
        if parsed.path.startswith("/swarm-demo/"):
            rel_path = parsed.path.removeprefix("/swarm-demo/") or "index.html"
            self._handle_swarm_demo_file(rel_path)
            return
        if parsed.path == "/hazard-formation":
            self._handle_hazard_formation_file("index.html")
            return
        if parsed.path.startswith("/hazard-formation/"):
            rel_path = parsed.path.removeprefix("/hazard-formation/") or "index.html"
            self._handle_hazard_formation_file(rel_path)
            return
        if parsed.path == "/world-model-dashboard":
            self._handle_world_model_dashboard_file("index.html")
            return
        if parsed.path.startswith("/world-model-dashboard/"):
            rel_path = parsed.path.removeprefix("/world-model-dashboard/") or "index.html"
            self._handle_world_model_dashboard_file(rel_path)
            return
        if parsed.path == "/qwen-ping":
            query = parse_qs(parsed.query)
            model = query.get("model", ["qwen-plus"])[0]
            self._handle_qwen_ping(model=model)
            return
        self._send_json({"error": "not_found"}, status=404)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/replan":
            self._handle_replan()
            return
        self._send_json({"error": "not_found"}, status=404)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _handle_camera_fixture(self) -> None:
        image_path = Path("fixtures/hazard_marker.ppm")
        width, height = image_size(image_path)
        grounding = parse_qwen_bbox_response(FIXTURE_RESPONSE, image_width=width, image_height=height)
        perception = PerceptionEvent(
            event_id="ecs-fixture-perception-0000",
            source=f"fixture://{image_path.name}",
            image_width=width,
            image_height=height,
            label=grounding.label,
            bbox_2d_norm_1000=grounding.bbox_2d_norm_1000,
            bbox_2d_px=grounding.bbox_2d_px,
            model="fixture-qwen3-vl-shape",
            score_milli=grounding.score_milli,
        )
        trace = build_single_event_trace(
            run_id="ecs-fixture-go-gate-0000",
            actor_id="ecs-edge-node-0",
            mode="fixture",
            perception=perception,
            intent="hold if marked hazard is visible",
            decision="VETO",
            reason="hazard label detected in keyframe",
            command={"type": "hold", "duration_ticks": 1},
        )
        summary_sha = verify_trace(trace)
        self._send_json(
            {
                "status": "ok",
                "trace_summary_sha": summary_sha,
                "schema_version": trace.schema_version,
                "decision": trace.events[0].decision,
            }
        )

    def _handle_qwen_vl_fixture(self, *, model: str) -> None:
        image_path = Path("fixtures/hazard_marker.ppm")
        try:
            width, height = image_size(image_path)
            response_text = DashScopeQwenClient(model=model).detect_bbox(image_path=image_path, target="marked hazard")
            grounding = parse_qwen_bbox_response(response_text, image_width=width, image_height=height)
        except MissingAlibabaApiKey:
            self._send_json({"status": "missing_key", "model": model}, status=503)
            return
        except OSError:
            self._send_json(
                {"status": "failed", "model": model, "error": "fixture_read_failed", "image": image_path.name},
                status=502,
            )
            return
        except (DashScopeResponseError, ValueError) as exc:
            self._send_json({"status": "failed", "model": model, "error": str(exc)}, status=502)
            return
        perception = PerceptionEvent(
            event_id="ecs-qwen-vl-perception-0000",
            source=f"qwen-vl-fixture://{image_path.name}",
            image_width=width,
            image_height=height,
            label=grounding.label,
            bbox_2d_norm_1000=grounding.bbox_2d_norm_1000,
            bbox_2d_px=grounding.bbox_2d_px,
            model=model,
            score_milli=grounding.score_milli,
        )
        trace = build_single_event_trace(
            run_id="ecs-qwen-vl-fixture-0000",
            actor_id="ecs-edge-node-0",
            mode="cloud",
            perception=perception,
            intent="hold if Qwen3-VL sees marked hazard in deployed fixture",
            decision="VETO",
            reason="Qwen3-VL bbox detection returned a marked hazard",
            command={"type": "hold", "duration_ticks": 1},
        )
        summary_sha = verify_trace(trace)
        self._send_json(
            {
                "status": "ok",
                "model": model,
                "label": grounding.label,
                "bbox_2d_norm_1000": list(grounding.bbox_2d_norm_1000),
                "trace_summary_sha": summary_sha,
                "schema_version": trace.schema_version,
                "decision": trace.events[0].decision,
            }
        )

    def _handle_qwenguard_memory_fixture(self) -> None:
        try:
            self._send_json(_qwenguard_memory_fixture_response())
        except (OSError, TypeError, ValueError):
            self._send_json(
                {"status": "failed", "error": "memory_fixture_unavailable"},
                status=500,
            )

    def _handle_qwen_ping(self, *, model: str) -> None:
        try:
            content = DashScopeQwenClient(model=model).chat_text(prompt="Return exactly OK.", max_tokens=8)
        except MissingAlibabaApiKey:
            self._send_json({"status": "missing_key", "model": model}, status=503)
            return
        except (DashScopeResponseError, ValueError) as exc:
            self._send_json({"status": "failed", "model": model, "error": str(exc)}, status=502)
            return
        content_prefix = content.strip()[:16]
        if not content_prefix.startswith("OK"):
            self._send_json({"status": "failed", "model": model, "content_prefix": content_prefix}, status=502)
            return
        self._send_json({"status": "ok", "model": model, "content_prefix": content_prefix})

    def _handle_replan(self) -> None:
        if not _is_loopback_host(self.client_address[0]):
            self._send_json({"status": "rejected", "error": "replan endpoint is localhost-only"}, status=403)
            return
        if not _is_loopback_authority(self.headers.get("Host", "")):
            self._send_json({"status": "rejected", "error": "replan endpoint requires a loopback Host header"}, status=403)
            return
        origin = self.headers.get("Origin")
        if origin and not _is_loopback_origin(origin):
            self._send_json({"status": "rejected", "error": "replan endpoint requires a loopback Origin"}, status=403)
            return
        try:
            payload = self._read_json_body()
            response = _interactive_replan_response(payload)
        except ValueError as exc:
            self._send_json({"status": "rejected", "error": str(exc)}, status=400)
            return
        self._send_json(response)

    def _handle_swarm_demo_file(self, rel_url_path: str) -> None:
        root = _swarm_demo_bundle_root()
        if not _has_swarm_demo_bundle_markers(root):
            self._send_missing_swarm_demo_bundle()
            return
        try:
            target = _safe_bundle_path(root=root, rel_url_path=rel_url_path, label="swarm demo")
        except ValueError as exc:
            self._send_json({"status": "rejected", "error": str(exc)}, status=400)
            return
        if not target.is_file():
            self._send_missing_swarm_demo_bundle()
            return
        self._send_file(
            target,
            on_missing=self._send_missing_swarm_demo_bundle,
            read_error_label="swarm demo",
        )

    def _handle_hazard_formation_file(self, rel_url_path: str) -> None:
        root = _hazard_formation_replay_root()
        if not _has_hazard_formation_replay_markers(root):
            self._send_missing_hazard_formation_replay()
            return
        try:
            target = _safe_bundle_path(root=root, rel_url_path=rel_url_path, label="hazard formation replay")
        except ValueError as exc:
            self._send_json({"status": "rejected", "error": str(exc)}, status=400)
            return
        if not target.is_file():
            self._send_missing_hazard_formation_replay()
            return
        self._send_file(
            target,
            on_missing=self._send_missing_hazard_formation_replay,
            read_error_label="hazard formation replay",
        )

    def _handle_world_model_dashboard_file(self, rel_url_path: str) -> None:
        root = _world_model_dashboard_root()
        if not _has_world_model_dashboard_markers(root):
            self._send_missing_world_model_dashboard()
            return
        try:
            target = _safe_bundle_path(root=root, rel_url_path=rel_url_path, label="world model dashboard")
        except ValueError as exc:
            self._send_json({"status": "rejected", "error": str(exc)}, status=400)
            return
        if not target.is_file():
            self._send_missing_world_model_dashboard()
            return
        self._send_file(
            target,
            on_missing=self._send_missing_world_model_dashboard,
            read_error_label="world model dashboard",
        )

    def _send_missing_swarm_demo_bundle(self) -> None:
        self._send_json(
            {
                "status": "missing_bundle",
                "error": "swarm demo bundle file not found",
                "build_command": SWARM_DEMO_BUILD_COMMAND,
            },
            status=404,
        )

    def _send_missing_hazard_formation_replay(self) -> None:
        self._send_json(
            {
                "status": "missing_hazard_formation_replay",
                "error": "hazard formation replay file not found",
                "build_command": HAZARD_FORMATION_BUILD_COMMAND,
            },
            status=404,
        )

    def _send_missing_world_model_dashboard(self) -> None:
        self._send_json(
            {
                "status": "missing_world_model_dashboard",
                "error": "world model dashboard file not found",
                "build_command": WORLD_MODEL_DASHBOARD_BUILD_COMMAND,
            },
            status=404,
        )

    def _send_json(self, payload: dict[str, Any], *, status: int = 200) -> None:
        data = canonical_json(payload).encode("utf-8") + b"\n"
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json_body(self) -> dict[str, Any]:
        length_header = self.headers.get("Content-Length")
        if length_header is None:
            raise ValueError("Content-Length header required")
        try:
            length = int(length_header)
        except ValueError as exc:
            raise ValueError("Content-Length must be an integer") from exc
        if length <= 0:
            raise ValueError("request body must be non-empty")
        if length > 64_000:
            raise ValueError("request body too large")
        body = self.rfile.read(length)
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("request body must be valid UTF-8 JSON") from exc
        try:
            parsed = json.loads(text, object_pairs_hook=_reject_duplicate_json_keys)
        except json.JSONDecodeError as exc:
            raise ValueError("request body must be valid UTF-8 JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError("request body must be a JSON object")
        return parsed

    def _send_file(
        self,
        path: Path,
        *,
        on_missing: Callable[[], None],
        read_error_label: str,
    ) -> None:
        try:
            size = path.stat().st_size
            source = path.open("rb")
        except FileNotFoundError:
            on_missing()
            return
        except OSError as exc:
            self._send_json({"status": "failed", "error": f"could not read {read_error_label} file: {exc}"}, status=500)
            return

        self.send_response(200)
        self.send_header("Content-Type", _content_type(path))
        self.send_header("Content-Length", str(size))
        self.end_headers()
        try:
            with source:
                shutil.copyfileobj(source, self.wfile)
        except OSError:
            return


def _qwenguard_memory_fixture_response() -> dict[str, Any]:
    fixture = parse_memory_fixture_json(DEFAULT_QWENGUARD_MEMORY_FIXTURE.read_text(encoding="utf-8"))
    evidence_manifest = parse_memory_evidence_manifest_json(
        DEFAULT_QWENGUARD_MEMORY_MANIFEST.read_text(encoding="utf-8"),
        fixture=fixture,
    )
    trace = build_qwenguard_memory_replay(
        run_id="qwenguard-memory-replay-0001",
        memory_id="target-001",
        baseline=fixture.baseline,
        conflict=fixture.conflict,
    )
    return build_memory_replay_response(
        fixture=fixture,
        evidence_manifest=evidence_manifest,
        trace=trace,
    )


def _interactive_replan_response(payload: dict[str, Any]) -> dict[str, Any]:
    grid = _require_dict(payload.get("grid"), "grid")
    grid_width = _require_positive_int(grid.get("w"), "grid.w")
    grid_height = _require_positive_int(grid.get("h"), "grid.h")
    if not (INTERACTIVE_MIN_GRID_SIZE <= grid_width <= INTERACTIVE_MAX_GRID_SIZE):
        raise ValueError(f"grid.w must be between {INTERACTIVE_MIN_GRID_SIZE} and {INTERACTIVE_MAX_GRID_SIZE}")
    if not (INTERACTIVE_MIN_GRID_SIZE <= grid_height <= INTERACTIVE_MAX_GRID_SIZE):
        raise ValueError(f"grid.h must be between {INTERACTIVE_MIN_GRID_SIZE} and {INTERACTIVE_MAX_GRID_SIZE}")

    formation = payload.get("formation")
    if not isinstance(formation, str) or formation not in SUPPORTED_FORMATIONS:
        raise ValueError(f"formation must be one of: {', '.join(SUPPORTED_FORMATIONS)}")

    hazard = _grid_point_from_pair(payload.get("hazard"), "hazard")
    _validate_point_in_grid(hazard, grid_width=grid_width, grid_height=grid_height, name="hazard")
    observations = _observations_from_request(
        payload.get("observations", []),
        grid_width=grid_width,
        grid_height=grid_height,
    )

    obstacles = tuple(sorted(_grid_points_from_pairs(payload.get("obstacles", []), "obstacles")))
    if len(obstacles) > INTERACTIVE_MAX_OBSTACLES:
        raise ValueError(f"obstacles must contain at most {INTERACTIVE_MAX_OBSTACLES} items")
    for obstacle in obstacles:
        _validate_point_in_grid(obstacle, grid_width=grid_width, grid_height=grid_height, name="obstacle")
        if obstacle == hazard:
            raise ValueError("obstacle must not overlap the hazard cell")

    agent_positions = _agent_positions_from_request(payload.get("agents"), grid_width=grid_width, grid_height=grid_height)
    starts = tuple(
        AgentConfig(agent_id=agent_id, start=cell, goal=cell)
        for agent_id, cell in sorted(agent_positions.items())
    )
    plan = compile_formation(
        formation=formation,
        hazard_cell=hazard,
        grid_width=grid_width,
        grid_height=grid_height,
        agent_count=len(starts),
    )
    configs = assign_formation_slots(starts=starts, plan=plan)
    ticks = _require_optional_positive_int(payload.get("ticks"), "ticks", default=8)
    if ticks > INTERACTIVE_MAX_TICKS:
        raise ValueError(f"ticks must be at most {INTERACTIVE_MAX_TICKS}")
    planner_obstacles = tuple(sorted({*obstacles, hazard}))
    result = run_swarm_custom(
        configs=configs,
        obstacles=planner_obstacles,
        ticks=ticks,
        grid_width=grid_width,
        grid_height=grid_height,
        scenario=f"interactive-{formation}-replan",
        run_id=f"interactive-{formation}-n{len(configs)}",
    )
    traces = build_agent_traces(result)
    trace_summary_shas = {
        agent_id: verify_trace(trace)
        for agent_id, trace in sorted(traces.items())
    }
    sim_report = result.report_dict(trace_summary_shas)
    goals = {config.agent_id: config.goal for config in result.configs}
    decision_event_shas = {
        agent_id: {event.tick: event.sha256 for event in trace.events}
        for agent_id, trace in sorted(traces.items())
    }
    states = tuple(
        _interactive_world_state_for_tick(
            result=result,
            tick=tick_record,
            hazard=hazard,
            observations=observations,
            trace_summary_shas=trace_summary_shas,
            decision_event_shas=decision_event_shas,
        ).with_computed_sha()
        for tick_record in result.ticks
    )
    replay = {
        "same_cell_collision_count": result.same_cell_collision_count,
        "swap_collision_count": result.swap_collision_count,
        "obstacle_occupancy_violation_count": result.obstacle_occupancy_violation_count,
        "all_goals_reached": result.all_goals_reached,
    }
    return {
        "schema_version": INTERACTIVE_REPLAN_SCHEMA_VERSION,
        "outcome": sim_report["outcome"],
        "formation": formation,
        "grid": {"width": grid_width, "height": grid_height},
        "hazard": {"cell": hazard.to_dict()},
        "obstacles": [point.to_dict() for point in obstacles],
        "assigned_goals": {
            config.agent_id: config.goal.to_dict()
            for config in sorted(configs, key=lambda item: item.agent_id)
        },
        "agent_trace_summary_shas": trace_summary_shas,
        "traces": {
            agent_id: trace.to_dict()
            for agent_id, trace in sorted(traces.items())
        },
        "planner_metrics": {
            "outcome": sim_report["outcome"],
            "same_cell_collision_count": result.same_cell_collision_count,
            "swap_collision_count": result.swap_collision_count,
            "obstacle_occupancy_violation_count": result.obstacle_occupancy_violation_count,
            "all_goals_reached": result.all_goals_reached,
            "reroute_count": result.reroute_count,
            "hold_count": result.hold_count,
        },
        "reservation_table": [
            {"tick": reservation.tick, "agent_id": reservation.agent_id, "cell": reservation.cell.to_dict()}
            for state in states
            for reservation in state.reservations
        ],
        "world_model": {
            "state_count": len(states),
            "first_world_model_sha": states[0].world_model_sha if states else "",
            "last_world_model_sha": states[-1].world_model_sha if states else "",
            "predicted_conflict_count": sum(len(state.predicted_conflicts) for state in states),
        },
        "timeline": [
            {
                "tick": tick_record.tick,
                "agents": [
                    {
                        "agent_id": step.agent_id,
                        "cell": step.accepted.to_dict(),
                        "goal": goals[step.agent_id].to_dict(),
                        "decision": step.decision,
                        "reason": step.reason,
                        "event_sha256": decision_event_shas[step.agent_id][step.tick],
                        "trace_summary_sha": trace_summary_shas[step.agent_id],
                        "world_model_decision_event_sha": decision_event_shas[step.agent_id][step.tick],
                        "command": step.command_dict(grid_width=grid_width, grid_height=grid_height),
                    }
                    for step in tick_record.steps
                ],
                "reservations": [
                    {"tick": reservation.tick, "agent_id": reservation.agent_id, "cell": reservation.cell.to_dict()}
                    for reservation in states[tick_record.tick].reservations
                ],
                "predicted_conflicts": [
                    {
                        "tick": conflict.tick,
                        "conflict_type": conflict.conflict_type,
                        "agent_ids": list(conflict.agent_ids),
                        "cell": conflict.cell.to_dict(),
                        "reason": conflict.reason,
                    }
                    for conflict in states[tick_record.tick].predicted_conflicts
                ],
                "observations": states[tick_record.tick].to_dict()["observations"],
                "world_model_sha": states[tick_record.tick].world_model_sha,
            }
            for tick_record in result.ticks
        ],
        "replay": replay,
        "non_claims": [
            "no physical robot behavior",
            "no live Qwen control",
            "no DimOS execution",
            "no safety, latency, or reliability claim",
            "no learned world model",
        ],
    }


def _interactive_world_state_for_tick(
    *,
    result: Any,
    tick: Any,
    hazard: GridPoint,
    observations: tuple[WorldObservation, ...],
    trace_summary_shas: dict[str, str],
    decision_event_shas: dict[str, dict[int, str]],
) -> WorldModelState:
    goals = {config.agent_id: config.goal for config in result.configs}
    agents = tuple(
        WorldAgentState(
            agent_id=step.agent_id,
            cell=step.accepted,
            goal=goals[step.agent_id],
            decision_trace_sha=trace_summary_shas[step.agent_id],
            last_decision=step.decision,
            decision_event_sha=decision_event_shas[step.agent_id][step.tick],
        )
        for step in tick.steps
    )
    reservations = tuple(
        WorldReservation(tick=step.tick, agent_id=step.agent_id, cell=step.accepted)
        for step in tick.steps
    )
    return WorldModelState(
        tick=tick.tick,
        grid_width=result.grid_width,
        grid_height=result.grid_height,
        observations=observations,
        hazards=(hazard,),
        agents=agents,
        reservations=reservations,
        predicted_conflicts=(),
    )


def _observations_from_request(
    value: Any,
    *,
    grid_width: int,
    grid_height: int,
) -> tuple[WorldObservation, ...]:
    items = _require_list(value, "observations")
    if len(items) > INTERACTIVE_MAX_OBSERVATIONS:
        raise ValueError(f"observations must contain at most {INTERACTIVE_MAX_OBSERVATIONS} items")
    observations: list[WorldObservation] = []
    for item in items:
        observation = _require_dict(item, "observation")
        cell = _grid_point_from_dict(_require_dict(observation.get("cell"), "observation cell"), "observation cell")
        _validate_point_in_grid(cell, grid_width=grid_width, grid_height=grid_height, name="observation cell")
        bbox_value = observation.get("bbox_2d_norm_1000")
        bbox = _norm_bbox_from_request(bbox_value) if bbox_value is not None else None
        score_milli = _require_optional_int(observation.get("score_milli"), "observation score_milli", default=1000)
        observations.append(
            WorldObservation(
                observation_id=_require_string(observation.get("observation_id"), "observation_id"),
                source=_require_string(observation.get("source"), "observation source"),
                label=_require_string(observation.get("label"), "observation label"),
                cell=cell,
                source_trace_sha=_require_string(observation.get("source_trace_sha"), "observation source_trace_sha"),
                bbox_2d_norm_1000=bbox,
                score_milli=score_milli,
            )
        )
    return tuple(sorted(observations, key=lambda item: item.observation_id))


def _agent_positions_from_request(value: Any, *, grid_width: int, grid_height: int) -> dict[str, GridPoint]:
    items = _require_list(value, "agents")
    if len(items) != 4:
        raise ValueError("agents must contain exactly 4 items")
    positions: dict[str, GridPoint] = {}
    for item in items:
        agent = _require_dict(item, "agent")
        agent_id = agent.get("id")
        if not isinstance(agent_id, str) or not agent_id.strip():
            raise ValueError("agent id must be a non-empty string")
        if agent_id in positions:
            raise ValueError("agent ids must be unique")
        point = _grid_point_from_pair(agent.get("cell"), f"agent {agent_id} cell")
        _validate_point_in_grid(point, grid_width=grid_width, grid_height=grid_height, name=f"agent {agent_id} cell")
        positions[agent_id] = point
    if len(set(positions.values())) != len(positions):
        raise ValueError("agent cells must be unique")
    return positions


def _grid_points_from_pairs(value: Any, name: str) -> tuple[GridPoint, ...]:
    items = _require_list(value, name)
    points = tuple(_grid_point_from_pair(item, f"{name} item") for item in items)
    if len(set(points)) != len(points):
        raise ValueError(f"{name} must be unique")
    return points


def _grid_point_from_pair(value: Any, name: str) -> GridPoint:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{name} must be a two-item array")
    x = _require_int(value[0], f"{name}[0]")
    y = _require_int(value[1], f"{name}[1]")
    return GridPoint(x=x, y=y)


def _grid_point_from_dict(value: dict[str, Any], name: str) -> GridPoint:
    x = _require_int(value.get("x"), f"{name}.x")
    y = _require_int(value.get("y"), f"{name}.y")
    return GridPoint(x=x, y=y)


def _norm_bbox_from_request(value: Any) -> tuple[int, int, int, int]:
    items = _require_list(value, "observation bbox_2d_norm_1000")
    if len(items) != 4:
        raise ValueError("observation bbox_2d_norm_1000 must contain four values")
    return tuple(
        _require_int(item, f"observation bbox_2d_norm_1000[{index}]")
        for index, item in enumerate(items)
    )


def _require_positive_int(value: Any, name: str) -> int:
    integer = _require_int(value, name)
    if integer <= 0:
        raise ValueError(f"{name} must be positive")
    return integer


def _require_optional_int(value: Any, name: str, *, default: int) -> int:
    if value is None:
        return default
    return _require_int(value, name)


def _require_optional_positive_int(value: Any, name: str, *, default: int) -> int:
    if value is None:
        return default
    return _require_positive_int(value, name)


def _require_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


def _require_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _validate_point_in_grid(point: GridPoint, *, grid_width: int, grid_height: int, name: str) -> None:
    if not (0 <= point.x < grid_width and 0 <= point.y < grid_height):
        raise ValueError(f"{name} must stay inside the {grid_width}x{grid_height} grid")


def _require_dict(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _require_list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be an array")
    return value


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, item in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = item
    return result


def _is_loopback_host(value: str) -> bool:
    if value == "localhost":
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def _is_loopback_origin(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        return False
    return _is_loopback_host(parsed.hostname or "")


def _is_loopback_authority(value: str) -> bool:
    host = _authority_host(value)
    return _is_loopback_host(host)


def _authority_host(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if "://" in value:
        return urlparse(value).hostname or ""
    if value.startswith("["):
        end = value.find("]")
        return value[1:end] if end > 1 else ""
    if "@" in value:
        value = value.rsplit("@", 1)[1]
    if ":" in value:
        host, port = value.rsplit(":", 1)
        if port.isdigit():
            return host
    return value


def _swarm_demo_bundle_root() -> Path:
    configured = os.getenv("SWARM_DEMO_BUNDLE_DIR")
    if configured is None or configured.strip() in {"", "."}:
        return DEFAULT_SWARM_DEMO_BUNDLE_DIR.resolve()
    return Path(configured).resolve()


def _hazard_formation_replay_root() -> Path:
    configured = os.getenv("HAZARD_FORMATION_REPLAY_DIR")
    if configured is None or configured.strip() in {"", "."}:
        return DEFAULT_HAZARD_FORMATION_REPLAY_DIR.resolve()
    return Path(configured).resolve()


def _world_model_dashboard_root() -> Path:
    configured = os.getenv("WORLD_MODEL_DASHBOARD_DIR")
    if configured is None or configured.strip() in {"", "."}:
        return DEFAULT_WORLD_MODEL_DASHBOARD_DIR.resolve()
    return Path(configured).resolve()


def _has_swarm_demo_bundle_markers(root: Path) -> bool:
    return root.is_dir() and (root / "index.html").is_file() and (root / "summary.json").is_file()


def _has_hazard_formation_replay_markers(root: Path) -> bool:
    return root.is_dir() and (root / "index.html").is_file() and (root / "summary.json").is_file()


def _has_world_model_dashboard_markers(root: Path) -> bool:
    return root.is_dir() and (root / "index.html").is_file() and (root / "summary.json").is_file()


def _safe_bundle_path(*, root: Path, rel_url_path: str, label: str) -> Path:
    rel_path = Path(unquote(rel_url_path))
    if rel_path.is_absolute() or ".." in rel_path.parts:
        raise ValueError(f"{label} path must stay inside root")
    target = (root / rel_path).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} path must stay inside root") from exc
    return target


def _content_type(path: Path) -> str:
    if path.suffix == ".html":
        return "text/html; charset=utf-8"
    if path.suffix == ".json":
        return "application/json"
    return "application/octet-stream"


def run_server(*, host: str, port: int) -> None:
    httpd = ThreadingHTTPServer((host, port), AccountableSwarmHandler)
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
