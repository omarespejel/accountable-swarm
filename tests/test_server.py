import json
import os
from pathlib import Path
from threading import Thread
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from urllib import request
from urllib.error import HTTPError

from accountable_swarm.server import AccountableSwarmHandler
from http.server import ThreadingHTTPServer


class ServerTests(TestCase):
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

            def flaky_open(path: Path, *args: object, **kwargs: object):
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
