import json
import os
from threading import Thread
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
