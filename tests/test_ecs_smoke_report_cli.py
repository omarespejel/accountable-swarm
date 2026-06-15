import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]
COMMIT = "a" * 64


class EcsSmokeReportCliTests(TestCase):
    def test_collects_go_report_from_expected_endpoints(self) -> None:
        with _fake_ecs_server(qwen_status="ok") as base_url, TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "ecs_report.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.collect_ecs_smoke_report",
                    "--base-url",
                    base_url,
                    "--commit",
                    COMMIT,
                    "--out",
                    str(out),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(report["schema_version"], "ecs-smoke-report.v1")
            self.assertEqual(report["outcome"], "GO")
            self.assertEqual(report["deployed_commit"], COMMIT)
            self.assertTrue(all(report["pass_conditions"].values()))
            self.assertEqual(len(report["checks"]), 6)

    def test_fails_closed_when_qwen_ping_is_not_ok(self) -> None:
        with _fake_ecs_server(qwen_status="missing_key") as base_url, TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "ecs_report.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.collect_ecs_smoke_report",
                    "--base-url",
                    base_url,
                    "--commit",
                    COMMIT,
                    "--out",
                    str(out),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 4)
            report = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(report["outcome"], "NARROW_CLAIM")
            self.assertFalse(report["pass_conditions"]["qwen-ping_model_qwen-plus"])

    def test_allow_narrow_claim_writes_report_with_zero_exit(self) -> None:
        with _fake_ecs_server(qwen_status="missing_key") as base_url, TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "ecs_report.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.collect_ecs_smoke_report",
                    "--base-url",
                    base_url,
                    "--commit",
                    COMMIT,
                    "--out",
                    str(out),
                    "--allow-narrow-claim",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["outcome"], "NARROW_CLAIM")


class _fake_ecs_server:
    def __init__(self, *, qwen_status: str) -> None:
        self.qwen_status = qwen_status

    def __enter__(self) -> str:
        qwen_status = self.qwen_status

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                if self.path == "/healthz":
                    _send_json(self, {"service": "accountable-swarm", "status": "ok"})
                    return
                if self.path == "/readyz":
                    _send_json(
                        self,
                        {
                            "default_vl_model": "qwen3-vl-flash",
                            "has_alibaba_api_key": qwen_status == "ok",
                            "status": "ok",
                        },
                    )
                    return
                if self.path == "/camera-fixture":
                    _send_json(
                        self,
                        {
                            "decision": "VETO",
                            "schema_version": "decisiontrace.v1",
                            "status": "ok",
                            "trace_summary_sha": "b" * 64,
                        },
                    )
                    return
                if self.path == "/swarm-demo":
                    _send_text(self, "<!doctype html><title>demo</title>", content_type="text/html; charset=utf-8")
                    return
                if self.path == "/swarm-demo/summary.json":
                    _send_json(
                        self,
                        {
                            "index_sha256": "c" * 64,
                            "outcome": "GO",
                            "scenario_count": 5,
                        },
                    )
                    return
                if self.path == "/qwen-ping?model=qwen-plus":
                    if qwen_status == "ok":
                        _send_json(self, {"content_prefix": "OK.", "model": "qwen-plus", "status": "ok"})
                    else:
                        _send_json(self, {"model": "qwen-plus", "status": qwen_status}, status=503)
                    return
                _send_json(self, {"error": "not_found"}, status=404)

            def log_message(self, format: str, *args: object) -> None:
                return

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.httpd.server_address
        return f"http://{host}:{port}"

    def __exit__(self, *args: object) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)


def _send_json(handler: BaseHTTPRequestHandler, payload: dict[str, object], *, status: int = 200) -> None:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _send_text(handler: BaseHTTPRequestHandler, text: str, *, content_type: str) -> None:
    data = text.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)
