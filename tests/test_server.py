from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Thread
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from urllib import request
from urllib.error import HTTPError

from accountable_swarm.qwen.client import DEFAULT_DASHSCOPE_BASE_URL, DashScopeQwenClient
from accountable_swarm.qwenguard.memory import verify_qwenguard_memory_replay
from accountable_swarm.server import AccountableSwarmHandler, _is_loopback_host
from accountable_swarm.trace.models import trace_from_dict
from http.server import ThreadingHTTPServer


class ServerTests(TestCase):
    def test_is_loopback_host(self) -> None:
        self.assertTrue(_is_loopback_host("127.0.0.1"))
        self.assertTrue(_is_loopback_host("::1"))
        self.assertTrue(_is_loopback_host("localhost"))
        self.assertFalse(_is_loopback_host("10.0.0.5"))
        self.assertFalse(_is_loopback_host("example.com"))

    def test_health_ready_and_fixture_endpoints(self) -> None:
        with _test_server() as base_url:
            health = _get_json(f"{base_url}/healthz")
            self.assertEqual(health["status"], "ok")

            ready = _get_json(f"{base_url}/readyz")
            self.assertEqual(ready["status"], "ok")
            self.assertIn("has_alibaba_api_key", ready)

            fixture = _get_json(f"{base_url}/camera-fixture")
            self.assertEqual(fixture["status"], "ok")
            self.assertEqual(fixture["decision"], "VETO")
            self.assertEqual(len(fixture["trace_summary_sha"]), 64)

    def test_qwen_ping_without_key_returns_503(self) -> None:
        with patch.dict(os.environ, {"ALIBABA_API_KEY": ""}), _test_server() as base_url:
            with self.assertRaises(HTTPError) as ctx:
                _get_json(f"{base_url}/qwen-ping?model=qwen-plus")
            self.assertEqual(ctx.exception.code, 503)

    def test_qwenguard_memory_fixture_returns_semantically_verified_trace(self) -> None:
        with _test_server() as base_url:
            payload = _get_json(f"{base_url}/qwenguard-memory-fixture")

        trace = trace_from_dict(payload["trace"])
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["execution_context"], "post_run_policy_simulation")
        self.assertFalse(payload["robot_runtime_transitions"])
        self.assertIn("Gemini 2 fixed independent reference", payload["semantic_frame_source"])
        self.assertIn("separate teleoperated context receipts", payload["go2_capture_receipts_role"])
        self.assertEqual(payload["policy_sequence"], ["VERIFIED", "PROVISIONAL", "HOLD", "REVERIFY"])
        self.assertEqual(
            payload["memory_state_sequence"],
            ["VERIFIED", "PROVISIONAL", "PROVISIONAL", "PROVISIONAL"],
        )
        self.assertEqual(payload["retained_memory_state"], "PROVISIONAL")
        self.assertEqual(payload["policy_action"], "HOLD")
        self.assertEqual(payload["reverify_status"], "REQUESTED")
        self.assertFalse(payload["motion_executed"])
        self.assertEqual(verify_qwenguard_memory_replay(trace), payload["trace_summary_sha"])
        self.assertEqual(payload["event_receipts"], [event.sha256 for event in trace.events])

    def test_qwenguard_memory_fixture_failure_does_not_leak_host_path(self) -> None:
        private_path = Path("/Users/operator/private/missing-observations.json")
        with (
            patch("accountable_swarm.server.DEFAULT_QWENGUARD_MEMORY_FIXTURE", private_path),
            _test_server() as base_url,
        ):
            with self.assertRaises(HTTPError) as ctx:
                _get_json(f"{base_url}/qwenguard-memory-fixture")
            self.assertEqual(ctx.exception.code, 500)
            body = ctx.exception.read().decode("utf-8")
            payload = json.loads(body)

        self.assertEqual(payload, {"status": "failed", "error": "memory_fixture_unavailable"})
        self.assertNotIn(str(private_path), body)
        self.assertNotIn("/Users/", body)

    def test_qwenguard_memory_fixture_malformed_input_returns_sanitized_failure(self) -> None:
        with TemporaryDirectory() as tmpdir:
            malformed_fixture = Path(tmpdir) / "observations.json"
            malformed_fixture.write_text('{"schema":"qwenguard.observation-fixture.v1"}', encoding="utf-8")
            with (
                patch("accountable_swarm.server.DEFAULT_QWENGUARD_MEMORY_FIXTURE", malformed_fixture),
                _test_server() as base_url,
            ):
                with self.assertRaises(HTTPError) as ctx:
                    _get_json(f"{base_url}/qwenguard-memory-fixture")
                self.assertEqual(ctx.exception.code, 500)
                body = ctx.exception.read().decode("utf-8")
                payload = json.loads(body)

        self.assertEqual(payload, {"status": "failed", "error": "memory_fixture_unavailable"})
        self.assertNotIn(str(malformed_fixture), body)
        self.assertNotIn(tmpdir, body)

    def test_qwen_ping_rejects_unexpected_content(self) -> None:
        class FakeClient:
            def __init__(self, *, model: str) -> None:
                self.model = model

            def chat_text(self, *, prompt: str, max_tokens: int) -> str:
                return "NOPE"

        with (
            patch.dict(os.environ, {"ALIBABA_API_KEY": "test-key"}),
            patch("accountable_swarm.server.DashScopeQwenClient", FakeClient),
            _test_server() as base_url,
        ):
            with self.assertRaises(HTTPError) as ctx:
                _get_json(f"{base_url}/qwen-ping?model=qwen-plus")
            self.assertEqual(ctx.exception.code, 502)
            payload = json.loads(ctx.exception.read().decode("utf-8"))
            self.assertEqual(payload["status"], "failed")

    def test_qwen_vl_fixture_calls_detector_and_returns_trace(self) -> None:
        calls: dict[str, str] = {}

        class FakeClient:
            def __init__(self, *, model: str) -> None:
                self.model = model

            def detect_bbox(self, *, image_path: Path, target: str) -> str:
                calls["target"] = target
                calls["image_name"] = image_path.name
                return '[{"bbox_2d":[250,250,750,750],"label":"marked hazard"}]'

        with (
            patch.dict(os.environ, {"ALIBABA_API_KEY": "test-key"}),
            patch("accountable_swarm.server.DashScopeQwenClient", FakeClient),
            _test_server() as base_url,
        ):
            payload = _get_json(f"{base_url}/qwen-vl-fixture?model=qwen3-vl-flash")

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(calls, {"target": "marked hazard", "image_name": "hazard_marker.png"})
        self.assertEqual(payload["model"], "qwen3-vl-flash")
        self.assertEqual(payload["decision"], "VETO")
        self.assertEqual(payload["schema_version"], "decisiontrace.v2")
        self.assertEqual(payload["bbox_2d_norm_1000"], [250, 250, 750, 750])
        self.assertEqual(len(payload["trace_summary_sha"]), 64)

    def test_qwen_vl_fixture_uses_dashscope_supported_image(self) -> None:
        response = {
            "choices": [
                {
                    "message": {
                        "content": '[{"bbox_2d":[250,250,750,750],"label":"marked hazard"}]'
                    }
                }
            ]
        }

        with (
            patch.dict(
                os.environ,
                {
                    "ALIBABA_API_KEY": "test-key",
                    "DASHSCOPE_BASE_URL": DEFAULT_DASHSCOPE_BASE_URL,
                },
            ),
            patch.object(DashScopeQwenClient, "_post_chat_completion", return_value=response),
            _test_server() as base_url,
        ):
            payload = _get_json(f"{base_url}/qwen-vl-fixture?model=qwen3-vl-flash")

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["model"], "qwen3-vl-flash")

    def test_fixture_endpoints_do_not_depend_on_process_cwd(self) -> None:
        response = {
            "choices": [
                {
                    "message": {
                        "content": '[{"bbox_2d":[250,250,750,750],"label":"marked hazard"}]'
                    }
                }
            ]
        }

        old_cwd = Path.cwd()
        with TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            try:
                with (
                    patch.dict(
                        os.environ,
                        {
                            "ALIBABA_API_KEY": "test-key",
                            "DASHSCOPE_BASE_URL": DEFAULT_DASHSCOPE_BASE_URL,
                        },
                    ),
                    patch.object(DashScopeQwenClient, "_post_chat_completion", return_value=response),
                    _test_server() as base_url,
                ):
                    camera = _get_json(f"{base_url}/camera-fixture")
                    qwen_vl = _get_json(f"{base_url}/qwen-vl-fixture?model=qwen3-vl-flash")
            finally:
                os.chdir(old_cwd)

        self.assertEqual(camera["status"], "ok")
        self.assertEqual(qwen_vl["status"], "ok")

    def test_qwen_vl_fixture_rejects_malformed_bbox_payloads(self) -> None:
        malformed_responses = (
            "not json",
            '[["wrong shape"]]',
            '[{"label":"marked hazard"}]',
            '[{"bbox_2d":[0,0,1001,1000],"label":"marked hazard"}]',
        )

        for response_text in malformed_responses:
            with self.subTest(response_text=response_text):
                class FakeClient:
                    def __init__(self, *, model: str) -> None:
                        self.model = model

                    def detect_bbox(self, *, image_path: Path, target: str) -> str:
                        return response_text

                with (
                    patch.dict(os.environ, {"ALIBABA_API_KEY": "test-key"}),
                    patch("accountable_swarm.server.DashScopeQwenClient", FakeClient),
                    _test_server() as base_url,
                ):
                    with self.assertRaises(HTTPError) as ctx:
                        _get_json(f"{base_url}/qwen-vl-fixture?model=qwen3-vl-flash")

                self.assertEqual(ctx.exception.code, 502)
                payload = json.loads(ctx.exception.read().decode("utf-8"))
                self.assertEqual(payload["status"], "failed")
                self.assertEqual(payload["model"], "qwen3-vl-flash")

    def test_qwen_vl_fixture_accepts_full_normalized_bbox(self) -> None:
        class FakeClient:
            def __init__(self, *, model: str) -> None:
                self.model = model

            def detect_bbox(self, *, image_path: Path, target: str) -> str:
                return '[{"bbox_2d":[0,0,1000,1000],"label":"marked hazard"}]'

        with (
            patch.dict(os.environ, {"ALIBABA_API_KEY": "test-key"}),
            patch("accountable_swarm.server.DashScopeQwenClient", FakeClient),
            _test_server() as base_url,
        ):
            payload = _get_json(f"{base_url}/qwen-vl-fixture?model=qwen3-vl-flash")

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["bbox_2d_norm_1000"], [0, 0, 1000, 1000])

    def test_qwen_vl_fixture_without_key_returns_503(self) -> None:
        with patch.dict(os.environ, {"ALIBABA_API_KEY": ""}), _test_server() as base_url:
            with self.assertRaises(HTTPError) as ctx:
                _get_json(f"{base_url}/qwen-vl-fixture?model=qwen3-vl-flash")
            self.assertEqual(ctx.exception.code, 503)

    def test_qwen_vl_fixture_read_failure_returns_json_error(self) -> None:
        with (
            patch.dict(os.environ, {"ALIBABA_API_KEY": "test-key"}),
            patch("accountable_swarm.server.image_size", side_effect=OSError("missing fixture")),
            _test_server() as base_url,
        ):
            with self.assertRaises(HTTPError) as ctx:
                _get_json(f"{base_url}/qwen-vl-fixture?model=qwen3-vl-flash")
            self.assertEqual(ctx.exception.code, 502)
            payload = json.loads(ctx.exception.read().decode("utf-8"))

        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["model"], "qwen3-vl-flash")
        self.assertEqual(payload["error"], "fixture_read_failed")
        self.assertEqual(payload["image"], "hazard_marker.png")

    def test_swarm_demo_bundle_files_are_served_from_configured_root(self) -> None:
        with TemporaryDirectory() as tmpdir:
            bundle_dir = Path(tmpdir) / "bundle"
            replay_dir = bundle_dir / "scenarios" / "corridor"
            replay_dir.mkdir(parents=True)
            (bundle_dir / "index.html").write_text("<!doctype html><title>bundle</title>", encoding="utf-8")
            (bundle_dir / "summary.json").write_text('{"outcome":"GO"}\n', encoding="utf-8")
            (replay_dir / "replay.html").write_text("<!doctype html><title>replay</title>", encoding="utf-8")

            with patch.dict(os.environ, {"SWARM_DEMO_BUNDLE_DIR": str(bundle_dir)}), _test_server() as base_url:
                self.assertIn("bundle", _get_text(f"{base_url}/swarm-demo"))
                self.assertEqual(_get_json(f"{base_url}/swarm-demo/summary.json")["outcome"], "GO")
                self.assertIn("replay", _get_text(f"{base_url}/swarm-demo/scenarios/corridor/replay.html"))

    def test_swarm_demo_missing_bundle_returns_build_command(self) -> None:
        with TemporaryDirectory() as tmpdir:
            missing_dir = Path(tmpdir) / "missing"
            with patch.dict(os.environ, {"SWARM_DEMO_BUNDLE_DIR": str(missing_dir)}), _test_server() as base_url:
                with self.assertRaises(HTTPError) as ctx:
                    _get_json(f"{base_url}/swarm-demo")
                self.assertEqual(ctx.exception.code, 404)
                payload = json.loads(ctx.exception.read().decode("utf-8"))
                self.assertEqual(payload["status"], "missing_bundle")
                self.assertEqual(payload["build_command"], "python3 scripts/build_swarm_demo_bundle.py")

    def test_swarm_demo_empty_bundle_dir_does_not_serve_cwd(self) -> None:
        with TemporaryDirectory() as tmpdir:
            old_cwd = Path.cwd()
            tmp_path = Path(tmpdir)
            (tmp_path / "cwd-only.txt").write_text("must not be served", encoding="utf-8")
            try:
                os.chdir(tmp_path)
                with patch.dict(os.environ, {"SWARM_DEMO_BUNDLE_DIR": ""}), _test_server() as base_url:
                    with self.assertRaises(HTTPError) as ctx:
                        _get_text(f"{base_url}/swarm-demo/cwd-only.txt")
                    self.assertEqual(ctx.exception.code, 404)
                    payload = json.loads(ctx.exception.read().decode("utf-8"))
                    self.assertEqual(payload["status"], "missing_bundle")
            finally:
                os.chdir(old_cwd)

    def test_swarm_demo_root_without_bundle_markers_fails_closed(self) -> None:
        with TemporaryDirectory() as tmpdir:
            bundle_dir = Path(tmpdir) / "bundle"
            bundle_dir.mkdir()
            (bundle_dir / "unexpected.txt").write_text("not a bundle", encoding="utf-8")
            with patch.dict(os.environ, {"SWARM_DEMO_BUNDLE_DIR": str(bundle_dir)}), _test_server() as base_url:
                with self.assertRaises(HTTPError) as ctx:
                    _get_text(f"{base_url}/swarm-demo/unexpected.txt")
                self.assertEqual(ctx.exception.code, 404)
                payload = json.loads(ctx.exception.read().decode("utf-8"))
                self.assertEqual(payload["status"], "missing_bundle")

    def test_swarm_demo_rejects_path_traversal(self) -> None:
        with TemporaryDirectory() as tmpdir:
            bundle_dir = Path(tmpdir) / "bundle"
            bundle_dir.mkdir()
            (bundle_dir / "index.html").write_text("<!doctype html><title>bundle</title>", encoding="utf-8")
            (bundle_dir / "summary.json").write_text('{"outcome":"GO"}\n', encoding="utf-8")
            with patch.dict(os.environ, {"SWARM_DEMO_BUNDLE_DIR": str(bundle_dir)}), _test_server() as base_url:
                with self.assertRaises(HTTPError) as ctx:
                    _get_json(f"{base_url}/swarm-demo/%2e%2e/README.md")
                self.assertEqual(ctx.exception.code, 400)
                payload = json.loads(ctx.exception.read().decode("utf-8"))
                self.assertEqual(payload["status"], "rejected")
                self.assertIn("swarm demo", payload["error"])

    def test_hazard_formation_replay_files_are_served_from_configured_root(self) -> None:
        with TemporaryDirectory() as tmpdir:
            replay_dir = Path(tmpdir) / "hazard-replay"
            replay_dir.mkdir()
            (replay_dir / "index.html").write_text(
                "<!doctype html><title>hazard replay</title>",
                encoding="utf-8",
            )
            (replay_dir / "summary.json").write_text('{"outcome":"GO"}\n', encoding="utf-8")

            with patch.dict(os.environ, {"HAZARD_FORMATION_REPLAY_DIR": str(replay_dir)}), _test_server() as base_url:
                self.assertIn("hazard replay", _get_text(f"{base_url}/hazard-formation"))
                self.assertEqual(_get_json(f"{base_url}/hazard-formation/summary.json")["outcome"], "GO")

    def test_hazard_formation_missing_replay_returns_build_command(self) -> None:
        with TemporaryDirectory() as tmpdir:
            missing_dir = Path(tmpdir) / "missing"
            with patch.dict(os.environ, {"HAZARD_FORMATION_REPLAY_DIR": str(missing_dir)}), _test_server() as base_url:
                with self.assertRaises(HTTPError) as ctx:
                    _get_json(f"{base_url}/hazard-formation")
                self.assertEqual(ctx.exception.code, 404)
                payload = json.loads(ctx.exception.read().decode("utf-8"))
                self.assertEqual(payload["status"], "missing_hazard_formation_replay")
                self.assertEqual(payload["build_command"], "python3 scripts/prepare_demo_recording_pack.py")

    def test_hazard_formation_empty_replay_dir_does_not_serve_cwd(self) -> None:
        with TemporaryDirectory() as tmpdir:
            old_cwd = Path.cwd()
            tmp_path = Path(tmpdir)
            default_replay_dir = tmp_path / "default-hazard-replay"
            (tmp_path / "cwd-only.txt").write_text("must not be served", encoding="utf-8")
            try:
                os.chdir(tmp_path)
                with (
                    patch.dict(os.environ, {"HAZARD_FORMATION_REPLAY_DIR": ""}),
                    patch("accountable_swarm.server.DEFAULT_HAZARD_FORMATION_REPLAY_DIR", default_replay_dir),
                    _test_server() as base_url,
                ):
                    with self.assertRaises(HTTPError) as ctx:
                        _get_text(f"{base_url}/hazard-formation/cwd-only.txt")
                    self.assertEqual(ctx.exception.code, 404)
                    payload = json.loads(ctx.exception.read().decode("utf-8"))
                    self.assertEqual(payload["status"], "missing_hazard_formation_replay")
            finally:
                os.chdir(old_cwd)

    def test_hazard_formation_root_without_replay_markers_fails_closed(self) -> None:
        with TemporaryDirectory() as tmpdir:
            replay_dir = Path(tmpdir) / "hazard-replay"
            replay_dir.mkdir()
            (replay_dir / "unexpected.txt").write_text("not a replay", encoding="utf-8")
            with patch.dict(os.environ, {"HAZARD_FORMATION_REPLAY_DIR": str(replay_dir)}), _test_server() as base_url:
                with self.assertRaises(HTTPError) as ctx:
                    _get_text(f"{base_url}/hazard-formation/unexpected.txt")
                self.assertEqual(ctx.exception.code, 404)
                payload = json.loads(ctx.exception.read().decode("utf-8"))
                self.assertEqual(payload["status"], "missing_hazard_formation_replay")

    def test_hazard_formation_read_time_missing_file_returns_hazard_payload(self) -> None:
        with TemporaryDirectory() as tmpdir:
            replay_dir = Path(tmpdir) / "hazard-replay"
            index_path = (replay_dir / "index.html").resolve()
            replay_dir.mkdir()
            index_path.write_text("<!doctype html><title>hazard replay</title>", encoding="utf-8")
            (replay_dir / "summary.json").write_text('{"outcome":"GO"}\n', encoding="utf-8")
            original_open = Path.open

            def flaky_open(path: Path, *args: object, **kwargs: object) -> object:
                if path == index_path:
                    raise FileNotFoundError(index_path)
                return original_open(path, *args, **kwargs)

            with (
                patch.dict(os.environ, {"HAZARD_FORMATION_REPLAY_DIR": str(replay_dir)}),
                patch.object(Path, "open", flaky_open),
                _test_server() as base_url,
            ):
                with self.assertRaises(HTTPError) as ctx:
                    _get_json(f"{base_url}/hazard-formation")
                self.assertEqual(ctx.exception.code, 404)
                payload = json.loads(ctx.exception.read().decode("utf-8"))
                self.assertEqual(payload["status"], "missing_hazard_formation_replay")
                self.assertEqual(payload["build_command"], "python3 scripts/prepare_demo_recording_pack.py")

    def test_hazard_formation_rejects_path_traversal(self) -> None:
        with TemporaryDirectory() as tmpdir:
            replay_dir = Path(tmpdir) / "hazard-replay"
            replay_dir.mkdir()
            (replay_dir / "index.html").write_text(
                "<!doctype html><title>hazard replay</title>",
                encoding="utf-8",
            )
            (replay_dir / "summary.json").write_text('{"outcome":"GO"}\n', encoding="utf-8")
            with patch.dict(os.environ, {"HAZARD_FORMATION_REPLAY_DIR": str(replay_dir)}), _test_server() as base_url:
                with self.assertRaises(HTTPError) as ctx:
                    _get_json(f"{base_url}/hazard-formation/%2e%2e/README.md")
                self.assertEqual(ctx.exception.code, 400)
                payload = json.loads(ctx.exception.read().decode("utf-8"))
                self.assertEqual(payload["status"], "rejected")
                self.assertIn("hazard formation replay", payload["error"])

    def test_world_model_dashboard_files_are_served_from_configured_root(self) -> None:
        with TemporaryDirectory() as tmpdir:
            dashboard_dir = Path(tmpdir) / "dashboard"
            dashboard_dir.mkdir()
            (dashboard_dir / "index.html").write_text(
                "<!doctype html><title>Accountable World Model Dashboard</title>",
                encoding="utf-8",
            )
            (dashboard_dir / "summary.json").write_text('{"outcome":"GO"}\n', encoding="utf-8")

            with patch.dict(os.environ, {"WORLD_MODEL_DASHBOARD_DIR": str(dashboard_dir)}), _test_server() as base_url:
                self.assertIn("Accountable World Model Dashboard", _get_text(f"{base_url}/world-model-dashboard"))
                self.assertEqual(_get_json(f"{base_url}/world-model-dashboard/summary.json")["outcome"], "GO")

    def test_world_model_dashboard_missing_returns_build_command(self) -> None:
        with TemporaryDirectory() as tmpdir:
            missing_dir = Path(tmpdir) / "missing"
            with patch.dict(os.environ, {"WORLD_MODEL_DASHBOARD_DIR": str(missing_dir)}), _test_server() as base_url:
                with self.assertRaises(HTTPError) as ctx:
                    _get_json(f"{base_url}/world-model-dashboard")
                self.assertEqual(ctx.exception.code, 404)
                payload = json.loads(ctx.exception.read().decode("utf-8"))
                self.assertEqual(payload["status"], "missing_world_model_dashboard")
                self.assertEqual(payload["build_command"], "python3 scripts/prepare_demo_recording_pack.py")

    def test_world_model_dashboard_rejects_path_traversal(self) -> None:
        with TemporaryDirectory() as tmpdir:
            dashboard_dir = Path(tmpdir) / "dashboard"
            dashboard_dir.mkdir()
            (dashboard_dir / "index.html").write_text("<!doctype html><title>dashboard</title>", encoding="utf-8")
            (dashboard_dir / "summary.json").write_text('{"outcome":"GO"}\n', encoding="utf-8")
            with patch.dict(os.environ, {"WORLD_MODEL_DASHBOARD_DIR": str(dashboard_dir)}), _test_server() as base_url:
                with self.assertRaises(HTTPError) as ctx:
                    _get_json(f"{base_url}/world-model-dashboard/%2e%2e/README.md")
                self.assertEqual(ctx.exception.code, 400)
                payload = json.loads(ctx.exception.read().decode("utf-8"))
                self.assertEqual(payload["status"], "rejected")
                self.assertIn("world model dashboard", payload["error"])

    def test_replan_endpoint_is_deterministic_for_identical_request(self) -> None:
        with _test_server() as base_url:
            request_body = {
                "grid": {"w": 7, "h": 5},
                "agents": [
                    {"id": "sim-agent-0", "cell": [0, 2]},
                    {"id": "sim-agent-1", "cell": [6, 2]},
                    {"id": "sim-agent-2", "cell": [3, 0]},
                    {"id": "sim-agent-3", "cell": [3, 4]},
                ],
                "hazard": [3, 2],
                "obstacles": [[1, 2]],
                "formation": "x",
                "ticks": 8,
            }
            first = _post_json_bytes(f"{base_url}/replan", request_body)
            second = _post_json_bytes(f"{base_url}/replan", request_body)
            payload = json.loads(first.decode("utf-8"))

        self.assertEqual(first, second)
        self.assertEqual(payload["schema_version"], "interactive-replan-response.v1")
        self.assertEqual(payload["outcome"], "GO")
        self.assertEqual(payload["formation"], "x")
        self.assertEqual(payload["hazard"]["cell"], {"x": 3, "y": 2})
        self.assertEqual(payload["obstacles"], [{"x": 1, "y": 2}])
        self.assertTrue(any(agent["decision"] == "REROUTE" for agent in payload["timeline"][0]["agents"]))

    def test_replan_endpoint_rejects_duplicate_json_keys(self) -> None:
        body = (
            '{"grid":{"w":7,"h":5},'
            '"agents":[{"id":"sim-agent-0","cell":[0,2]},'
            '{"id":"sim-agent-1","cell":[6,2]},'
            '{"id":"sim-agent-2","cell":[3,0]},'
            '{"id":"sim-agent-3","cell":[3,4]}],'
            '"hazard":[3,2],'
            '"obstacles":[],'
            '"formation":"x",'
            '"ticks":8,'
            '"ticks":9}'
        ).encode("utf-8")
        with _test_server() as base_url:
            with self.assertRaises(HTTPError) as ctx:
                _post_raw_bytes(f"{base_url}/replan", body)

        self.assertEqual(ctx.exception.code, 400)
        payload = json.loads(ctx.exception.read().decode("utf-8"))
        self.assertEqual(payload["status"], "rejected")
        self.assertIn("duplicate JSON key: ticks", payload["error"])

    def test_replan_world_model_hash_binds_observations(self) -> None:
        first_request = _valid_replan_request()
        first_request["observations"] = [_sample_observation(label="marked hazard")]
        second_request = _valid_replan_request()
        second_request["observations"] = [_sample_observation(label="changed hazard")]

        with _test_server() as base_url:
            first = json.loads(_post_json_bytes(f"{base_url}/replan", first_request).decode("utf-8"))
            second = json.loads(_post_json_bytes(f"{base_url}/replan", second_request).decode("utf-8"))

        first_frame = first["timeline"][0]
        second_frame = second["timeline"][0]
        self.assertEqual(first_frame["observations"][0]["label"], "marked hazard")
        self.assertEqual(second_frame["observations"][0]["label"], "changed hazard")
        self.assertNotEqual(first_frame["world_model_sha"], second_frame["world_model_sha"])
        self.assertEqual(first["world_model"]["first_world_model_sha"], first_frame["world_model_sha"])

    def test_replan_endpoint_rejects_obstacle_on_hazard(self) -> None:
        with _test_server() as base_url:
            request_body = {
                "grid": {"w": 7, "h": 5},
                "agents": [
                    {"id": "sim-agent-0", "cell": [0, 2]},
                    {"id": "sim-agent-1", "cell": [6, 2]},
                    {"id": "sim-agent-2", "cell": [3, 0]},
                    {"id": "sim-agent-3", "cell": [3, 4]},
                ],
                "hazard": [3, 2],
                "obstacles": [[3, 2]],
                "formation": "x",
            }
            with self.assertRaises(HTTPError) as ctx:
                _post_json_bytes(f"{base_url}/replan", request_body)

        self.assertEqual(ctx.exception.code, 400)
        payload = json.loads(ctx.exception.read().decode("utf-8"))
        self.assertEqual(payload["status"], "rejected")
        self.assertIn("obstacle must not overlap the hazard cell", payload["error"])

    def test_replan_endpoint_rejects_non_loopback_origin(self) -> None:
        with _test_server() as base_url:
            request_body = _valid_replan_request()
            with self.assertRaises(HTTPError) as ctx:
                _post_json_bytes(
                    f"{base_url}/replan",
                    request_body,
                    headers={"Origin": "https://example.com"},
                )

        self.assertEqual(ctx.exception.code, 403)
        payload = json.loads(ctx.exception.read().decode("utf-8"))
        self.assertEqual(payload["status"], "rejected")
        self.assertIn("loopback Origin", payload["error"])

    def test_replan_endpoint_rejects_non_loopback_host(self) -> None:
        with _test_server() as base_url:
            with self.assertRaises(HTTPError) as ctx:
                _post_json_bytes(
                    f"{base_url}/replan",
                    _valid_replan_request(),
                    headers={"Host": "example.com"},
                )

        self.assertEqual(ctx.exception.code, 403)
        payload = json.loads(ctx.exception.read().decode("utf-8"))
        self.assertEqual(payload["status"], "rejected")
        self.assertIn("loopback Host", payload["error"])

    def test_replan_endpoint_rejects_malformed_json_body(self) -> None:
        with _test_server() as base_url:
            with self.assertRaises(HTTPError) as ctx:
                _post_raw_bytes(f"{base_url}/replan", b'{"grid":{"w":7')

        self.assertEqual(ctx.exception.code, 400)
        payload = json.loads(ctx.exception.read().decode("utf-8"))
        self.assertEqual(payload["status"], "rejected")
        self.assertIn("valid UTF-8 JSON", payload["error"])

    def test_replan_endpoint_rejects_unbounded_request_shape(self) -> None:
        with _test_server() as base_url:
            request_body = _valid_replan_request()
            request_body["grid"] = {"w": 64, "h": 64}
            with self.assertRaises(HTTPError) as grid_ctx:
                _post_json_bytes(f"{base_url}/replan", request_body)

            request_body = _valid_replan_request()
            request_body["ticks"] = 64
            with self.assertRaises(HTTPError) as ticks_ctx:
                _post_json_bytes(f"{base_url}/replan", request_body)

            request_body = _valid_replan_request()
            request_body["obstacles"] = [[x % 7, (x // 7) % 5] for x in range(25)]
            with self.assertRaises(HTTPError) as obstacles_ctx:
                _post_json_bytes(f"{base_url}/replan", request_body)

        self.assertEqual(grid_ctx.exception.code, 400)
        self.assertIn("grid.w must be between", grid_ctx.exception.read().decode("utf-8"))
        self.assertEqual(ticks_ctx.exception.code, 400)
        self.assertIn("ticks must be at most", ticks_ctx.exception.read().decode("utf-8"))
        self.assertEqual(obstacles_ctx.exception.code, 400)
        self.assertIn("obstacles must contain at most", obstacles_ctx.exception.read().decode("utf-8"))


class _test_server:
    def __enter__(self) -> str:
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), AccountableSwarmHandler)
        self.thread = Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.httpd.server_address
        return f"http://{host}:{port}"

    def __exit__(self, *args: object) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)


def _get_json(url: str) -> dict[str, object]:
    with request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_text(url: str) -> str:
    with request.urlopen(url, timeout=5) as resp:
        return resp.read().decode("utf-8")


def _valid_replan_request() -> dict[str, object]:
    return {
        "grid": {"w": 7, "h": 5},
        "agents": [
            {"id": "sim-agent-0", "cell": [0, 2]},
            {"id": "sim-agent-1", "cell": [6, 2]},
            {"id": "sim-agent-2", "cell": [3, 0]},
            {"id": "sim-agent-3", "cell": [3, 4]},
        ],
        "hazard": [3, 2],
        "obstacles": [[1, 2]],
        "formation": "x",
        "ticks": 8,
    }


def _sample_observation(*, label: str) -> dict[str, object]:
    return {
        "observation_id": "obs-hazard",
        "source": "fixture_bbox",
        "label": label,
        "cell": {"x": 3, "y": 2},
        "source_trace_sha": "a" * 64,
        "bbox_2d_norm_1000": [250, 250, 750, 750],
        "score_milli": 1000,
    }


def _post_json_bytes(
    url: str,
    payload: dict[str, object],
    *,
    headers: dict[str, str] | None = None,
) -> bytes:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    request_headers = {"Content-Type": "application/json", "Content-Length": str(len(body))}
    if headers:
        request_headers.update(headers)
    req = request.Request(
        url,
        data=body,
        method="POST",
        headers=request_headers,
    )
    with request.urlopen(req, timeout=5) as resp:
        return resp.read()


def _post_raw_bytes(
    url: str,
    body: bytes,
    *,
    headers: dict[str, str] | None = None,
) -> bytes:
    request_headers = {"Content-Type": "application/json", "Content-Length": str(len(body))}
    if headers:
        request_headers.update(headers)
    req = request.Request(
        url,
        data=body,
        method="POST",
        headers=request_headers,
    )
    with request.urlopen(req, timeout=5) as resp:
        return resp.read()
