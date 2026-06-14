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

    def test_swarm_demo_rejects_path_traversal(self) -> None:
        with TemporaryDirectory() as tmpdir:
            bundle_dir = Path(tmpdir) / "bundle"
            bundle_dir.mkdir()
            with patch.dict(os.environ, {"SWARM_DEMO_BUNDLE_DIR": str(bundle_dir)}), _test_server() as base_url:
                with self.assertRaises(HTTPError) as ctx:
                    _get_json(f"{base_url}/swarm-demo/%2e%2e/README.md")
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
