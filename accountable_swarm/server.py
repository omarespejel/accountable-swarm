"""Small stdlib HTTP server for manual Alibaba ECS deployment proof."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urlparse

from accountable_swarm.images import image_size
from accountable_swarm.qwen.bbox import parse_qwen_bbox_response
from accountable_swarm.qwen.client import DashScopeQwenClient, DashScopeResponseError, MissingAlibabaApiKey
from accountable_swarm.trace.models import PerceptionEvent, build_single_event_trace, canonical_json, verify_trace


FIXTURE_RESPONSE = '[{"bbox_2d":[250,250,750,750],"label":"marked hazard"}]'
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SWARM_DEMO_BUNDLE_DIR = REPO_ROOT / "runs/demo/swarm"
DEFAULT_HAZARD_FORMATION_REPLAY_DIR = REPO_ROOT / "runs/hazard_formation/recording_x_replay"
SWARM_DEMO_BUILD_COMMAND = "python3 scripts/build_swarm_demo_bundle.py"
HAZARD_FORMATION_BUILD_COMMAND = "python3 scripts/prepare_demo_recording_pack.py"


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
        if parsed.path == "/qwen-ping":
            query = parse_qs(parsed.query)
            model = query.get("model", ["qwen-plus"])[0]
            self._handle_qwen_ping(model=model)
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

    def _send_json(self, payload: dict[str, Any], *, status: int = 200) -> None:
        data = canonical_json(payload).encode("utf-8") + b"\n"
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

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


def _has_swarm_demo_bundle_markers(root: Path) -> bool:
    return root.is_dir() and (root / "index.html").is_file() and (root / "summary.json").is_file()


def _has_hazard_formation_replay_markers(root: Path) -> bool:
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
