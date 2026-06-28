import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread
from unittest import TestCase

from scripts import collect_ecs_smoke_report as collector


ROOT = Path(__file__).resolve().parents[1]
COMMIT = "a" * 40


class EcsSmokeReportCliTests(TestCase):
    def test_collects_go_report_from_public_ecs_metadata(self) -> None:
        report = collector.collect_report(
            base_url="http://8.8.8.8:8000",
            qwen_model="qwen-plus",
            deployed_commit=COMMIT,
            timeout_seconds=10,
            proof_mode="ecs-public",
            ecs_region="us-west-1",
            ecs_instance_id="i-accountable-swarm",
            ecs_public_ip="8.8.8.8",
            fetcher=_fake_fetcher(qwen_status="ok"),
        )

        self.assertEqual(report["schema_version"], "ecs-smoke-report.v1")
        self.assertEqual(report["outcome"], "GO")
        self.assertEqual(report["deployed_commit"], COMMIT)
        self.assertEqual(report["proof_mode"], "ecs-public")
        self.assertEqual(report["deployment"]["provider_asserted"], "Alibaba Cloud ECS")
        self.assertTrue(report["deployment"]["deployment_context_verified"])
        self.assertTrue(all(report["pass_conditions"].values()))
        self.assertEqual(len(report["checks"]), 6)

    def test_collects_go_report_from_bracketed_ipv6_public_metadata(self) -> None:
        report = collector.collect_report(
            base_url="http://[2001:4860:4860::8888]:8000",
            qwen_model="qwen-plus",
            deployed_commit=COMMIT,
            timeout_seconds=10,
            proof_mode="ecs-public",
            ecs_region="us-west-1",
            ecs_instance_id="i-accountable-swarm",
            ecs_public_ip="2001:4860:4860::8888",
            fetcher=_fake_fetcher(qwen_status="ok"),
        )

        self.assertEqual(report["outcome"], "GO")
        self.assertTrue(report["deployment"]["deployment_context_verified"])
        self.assertTrue(report["pass_conditions"]["base_url_matches_public_ip_when_ip_literal"])

    def test_localhost_smoke_is_narrow_claim_without_ecs_public_proof(self) -> None:
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
            self.assertEqual(result.returncode, 4)
            report = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(report["schema_version"], "ecs-smoke-report.v1")
            self.assertEqual(report["outcome"], "NARROW_CLAIM")
            self.assertEqual(report["deployed_commit"], COMMIT)
            self.assertEqual(report["proof_mode"], "local-smoke")
            self.assertFalse(report["pass_conditions"]["proof_mode_is_ecs_public"])
            self.assertFalse(report["pass_conditions"]["base_url_is_public_endpoint"])
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

    def test_fails_closed_when_qwen_content_is_unexpected(self) -> None:
        with _fake_ecs_server(qwen_status="bad_content") as base_url, TemporaryDirectory() as tmpdir:
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

    def test_fails_closed_when_commit_is_malformed(self) -> None:
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
                    "not-a-sha",
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
            self.assertFalse(report["pass_conditions"]["deployed_commit_recorded"])

    def test_fails_closed_when_swarm_summary_schema_is_wrong(self) -> None:
        with _fake_ecs_server(qwen_status="ok", summary_schema="wrong.v1") as base_url, TemporaryDirectory() as tmpdir:
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
            self.assertFalse(report["pass_conditions"]["swarm-demo_summary.json"])

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

    def test_ecs_public_mode_rejects_mismatched_ip_literal(self) -> None:
        report = collector.collect_report(
            base_url="http://8.8.4.4:8000",
            qwen_model="qwen-plus",
            deployed_commit=COMMIT,
            timeout_seconds=10,
            proof_mode="ecs-public",
            ecs_region="us-west-1",
            ecs_instance_id="i-accountable-swarm",
            ecs_public_ip="8.8.8.8",
            fetcher=_fake_fetcher(qwen_status="ok"),
        )

        self.assertEqual(report["outcome"], "NARROW_CLAIM")
        self.assertFalse(report["pass_conditions"]["base_url_matches_public_ip_when_ip_literal"])

    def test_rejects_base_url_control_characters_before_fetch(self) -> None:
        with self.assertRaises(ValueError):
            collector.collect_report(
                base_url="http://8.8.8.8:8000\ncurl",
                qwen_model="qwen-plus",
                deployed_commit=COMMIT,
                timeout_seconds=10,
                proof_mode="ecs-public",
                ecs_region="us-west-1",
                ecs_instance_id="i-accountable-swarm",
                ecs_public_ip="8.8.8.8",
                fetcher=_fake_fetcher(qwen_status="ok"),
            )

    def test_allow_narrow_claim_writes_invalid_input_report(self) -> None:
        with TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "ecs_report.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.collect_ecs_smoke_report",
                    "--base-url",
                    "http://8.8.8.8:8000\ncurl",
                    "--commit",
                    COMMIT,
                    "--out",
                    str(out),
                    "--proof-mode",
                    "ecs-public",
                    "--ecs-region",
                    "us-west-1",
                    "--ecs-instance-id",
                    "i-accountable-swarm",
                    "--ecs-public-ip",
                    "8.8.8.8",
                    "--allow-narrow-claim",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(out.read_text(encoding="utf-8"))

        self.assertEqual(report["outcome"], "NARROW_CLAIM")
        self.assertEqual(report["error"]["type"], "ValueError")
        self.assertFalse(report["pass_conditions"]["input_validation_passed"])
        self.assertNotIn("\n", report["base_url"])
        self.assertNotIn("\n", report["error"]["message"])


class _fake_ecs_server:
    def __init__(self, *, qwen_status: str, summary_schema: str = "swarm-demo-bundle-report.v1") -> None:
        self.qwen_status = qwen_status
        self.summary_schema = summary_schema

    def __enter__(self) -> str:
        qwen_status = self.qwen_status
        summary_schema = self.summary_schema

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
                            "has_alibaba_api_key": qwen_status in {"ok", "bad_content"},
                            "status": "ok",
                        },
                    )
                    return
                if self.path == "/camera-fixture":
                    _send_json(
                        self,
                        {
                            "decision": "VETO",
                            "schema_version": "decisiontrace.v2",
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
                            "schema_version": summary_schema,
                            "scenario_count": 5,
                        },
                    )
                    return
                if self.path == "/qwen-ping?model=qwen-plus":
                    if qwen_status == "ok":
                        _send_json(self, {"content_prefix": "OK.", "model": "qwen-plus", "status": "ok"})
                    elif qwen_status == "bad_content":
                        _send_json(self, {"content_prefix": "NOPE", "model": "qwen-plus", "status": "ok"})
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


def _fake_fetcher(*, qwen_status: str, summary_schema: str = "swarm-demo-bundle-report.v1"):
    def fetcher(*, base_url: str, path: str, timeout_seconds: int) -> dict[str, object]:
        del base_url, timeout_seconds
        if path == "/healthz":
            return _json_response({"service": "accountable-swarm", "status": "ok"})
        if path == "/readyz":
            return _json_response(
                {
                    "default_vl_model": "qwen3-vl-flash",
                    "has_alibaba_api_key": qwen_status in {"ok", "bad_content"},
                    "status": "ok",
                }
            )
        if path == "/camera-fixture":
            return _json_response(
                {
                    "decision": "VETO",
                    "schema_version": "decisiontrace.v2",
                    "status": "ok",
                    "trace_summary_sha": "b" * 64,
                }
            )
        if path == "/swarm-demo":
            return _text_response("<!doctype html><title>demo</title>", content_type="text/html; charset=utf-8")
        if path == "/swarm-demo/summary.json":
            return _json_response(
                {
                    "index_sha256": "c" * 64,
                    "outcome": "GO",
                    "schema_version": summary_schema,
                    "scenario_count": 5,
                }
            )
        if path == "/qwen-ping?model=qwen-plus":
            if qwen_status == "ok":
                return _json_response({"content_prefix": "OK.", "model": "qwen-plus", "status": "ok"})
            if qwen_status == "bad_content":
                return _json_response({"content_prefix": "NOPE", "model": "qwen-plus", "status": "ok"})
            return _json_response({"model": "qwen-plus", "status": qwen_status}, status=503)
        return _json_response({"error": "not_found"}, status=404)

    return fetcher


def _json_response(payload: dict[str, object], *, status: int = 200) -> dict[str, object]:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    return {
        "status_code": status,
        "content_type": "application/json",
        "body_sha256": "d" * 64,
        "byte_count": len(body),
        "json": payload,
    }


def _text_response(text: str, *, content_type: str, status: int = 200) -> dict[str, object]:
    body = text.encode("utf-8")
    return {
        "status_code": status,
        "content_type": content_type,
        "body_sha256": "e" * 64,
        "byte_count": len(body),
        "text_prefix": text[:128],
    }
