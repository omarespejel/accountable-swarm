import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread
from unittest import TestCase
from unittest.mock import patch

from scripts import collect_ecs_smoke_report as collector


ROOT = Path(__file__).resolve().parents[1]
COMMIT = collector._git_head()
ECS_IP = "47.88.8.8"
ECS_IPV6 = "2001:4860:4860::8888"


class EcsSmokeReportCliTests(TestCase):
    def test_collects_go_report_from_public_ecs_metadata(self) -> None:
        report = collector.collect_report(
            base_url=f"http://{ECS_IP}:8000",
            qwen_model="qwen3-vl-flash",
            deployed_commit=COMMIT,
            timeout_seconds=10,
            proof_mode="ecs-public",
            ecs_region="us-west-1",
            ecs_instance_id="i-accountable-swarm",
            ecs_public_ip=ECS_IP,
            fetcher=_fake_fetcher(qwen_status="ok"),
            metadata_fetcher=_fake_metadata_fetcher(region="us-west-1", instance_id="i-accountable-swarm"),
        )

        self.assertEqual(report["schema_version"], "ecs-smoke-report.v1")
        self.assertEqual(report["outcome"], "GO")
        self.assertEqual(report["deployed_commit"], COMMIT)
        self.assertEqual(report["proof_mode"], "ecs-public")
        self.assertEqual(report["deployment"]["provider_asserted"], "Alibaba Cloud ECS")
        self.assertTrue(report["deployment"]["deployment_context_verified"])
        self.assertTrue(all(report["pass_conditions"].values()))
        self.assertEqual(report["collector_head"], COMMIT)
        self.assertEqual(len(report["checks"]), 7)

    def test_collect_report_uses_one_cached_git_head(self) -> None:
        collector_head = "a" * 40
        with patch("scripts.collect_ecs_smoke_report._git_head", return_value=collector_head) as git_head:
            report = collector.collect_report(
                base_url=f"http://{ECS_IP}:8000",
                qwen_model="qwen3-vl-flash",
                deployed_commit=collector_head,
                timeout_seconds=10,
                proof_mode="ecs-public",
                ecs_region="us-west-1",
                ecs_instance_id="i-accountable-swarm",
                ecs_public_ip=ECS_IP,
                fetcher=_fake_fetcher(qwen_status="ok"),
                metadata_fetcher=_fake_metadata_fetcher(region="us-west-1", instance_id="i-accountable-swarm"),
            )

        self.assertEqual(git_head.call_count, 1)
        self.assertEqual(report["collector_head"], collector_head)
        self.assertTrue(report["pass_conditions"]["deployed_commit_matches_collector_head"])

        for field_name, updates in [
            ("ecs_region", {"ecs_region": ""}),
            ("ecs_instance_id", {"ecs_instance_id": ""}),
            ("ecs_public_ip", {"ecs_public_ip": ""}),
        ]:
            kwargs = {
                "base_url": f"http://{ECS_IP}:8000",
                "qwen_model": "qwen3-vl-flash",
                "deployed_commit": COMMIT,
                "timeout_seconds": 10,
                "proof_mode": "ecs-public",
                "ecs_region": "us-west-1",
                "ecs_instance_id": "i-accountable-swarm",
                "ecs_public_ip": ECS_IP,
                "fetcher": _fake_fetcher(qwen_status="ok"),
                "metadata_fetcher": _fake_metadata_fetcher(region="us-west-1", instance_id="i-accountable-swarm"),
            }
            kwargs.update(updates)
            narrowed = collector.collect_report(**kwargs)
            self.assertEqual(narrowed["outcome"], "NARROW_CLAIM", field_name)
            self.assertFalse(narrowed["deployment"]["deployment_context_verified"], field_name)

    def test_bracketed_ipv6_public_endpoint_is_narrow_without_public_ip_metadata_binding(self) -> None:
        report = collector.collect_report(
            base_url=f"http://[{ECS_IPV6}]:8000",
            qwen_model="qwen3-vl-flash",
            deployed_commit=COMMIT,
            timeout_seconds=10,
            proof_mode="ecs-public",
            ecs_region="us-west-1",
            ecs_instance_id="i-accountable-swarm",
            ecs_public_ip=ECS_IPV6,
            fetcher=_fake_fetcher(qwen_status="ok"),
            metadata_fetcher=_fake_metadata_fetcher(region="us-west-1", instance_id="i-accountable-swarm"),
        )

        self.assertEqual(report["outcome"], "NARROW_CLAIM")
        self.assertFalse(report["deployment"]["deployment_context_verified"])
        self.assertTrue(report["pass_conditions"]["base_url_matches_public_ip_when_ip_literal"])
        self.assertFalse(report["pass_conditions"]["ecs_metadata_public_ip_matches"])

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
            self.assertEqual(len(report["checks"]), 7)

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
            self.assertFalse(report["pass_conditions"]["qwen-ping_model_qwen3-vl-flash"])

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
            self.assertFalse(report["pass_conditions"]["qwen-ping_model_qwen3-vl-flash"])

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

    def test_fails_closed_when_deployed_commit_does_not_match_head(self) -> None:
        report = collector.collect_report(
            base_url=f"http://{ECS_IP}:8000",
            qwen_model="qwen3-vl-flash",
            deployed_commit="d" * 40,
            timeout_seconds=10,
            proof_mode="ecs-public",
            ecs_region="us-west-1",
            ecs_instance_id="i-accountable-swarm",
            ecs_public_ip=ECS_IP,
            fetcher=_fake_fetcher(qwen_status="ok"),
            metadata_fetcher=_fake_metadata_fetcher(region="us-west-1", instance_id="i-accountable-swarm"),
        )

        self.assertEqual(report["outcome"], "NARROW_CLAIM")
        self.assertFalse(report["pass_conditions"]["deployed_commit_matches_collector_head"])

    def test_fails_closed_when_ecs_metadata_is_absent_for_public_ip(self) -> None:
        report = collector.collect_report(
            base_url="http://8.8.8.8:8000",
            qwen_model="qwen3-vl-flash",
            deployed_commit=COMMIT,
            timeout_seconds=10,
            proof_mode="ecs-public",
            ecs_region="us-west-1",
            ecs_instance_id="i-accountable-swarm",
            ecs_public_ip="8.8.8.8",
            fetcher=_fake_fetcher(qwen_status="ok"),
            metadata_fetcher=_missing_metadata_fetcher,
        )

        self.assertEqual(report["outcome"], "NARROW_CLAIM")
        self.assertFalse(report["deployment"]["deployment_context_verified"])
        self.assertFalse(report["pass_conditions"]["ecs_metadata_identity_document_present"])

    def test_metadata_json_parses_when_content_type_is_plain_text(self) -> None:
        report = collector.collect_report(
            base_url=f"http://{ECS_IP}:8000",
            qwen_model="qwen3-vl-flash",
            deployed_commit=COMMIT,
            timeout_seconds=10,
            proof_mode="ecs-public",
            ecs_region="us-west-1",
            ecs_instance_id="i-accountable-swarm",
            ecs_public_ip=ECS_IP,
            fetcher=_fake_fetcher(qwen_status="ok"),
            metadata_fetcher=_fake_metadata_fetcher(
                region="us-west-1",
                instance_id="i-accountable-swarm",
                identity_content_type="text/plain",
            ),
        )

        self.assertEqual(report["outcome"], "GO")
        self.assertTrue(report["pass_conditions"]["ecs_metadata_identity_document_present"])

    def test_plain_text_metadata_survives_json_content_type_mismatch(self) -> None:
        response = collector._response_payload(
            status_code=200,
            content_type="application/json",
            body=f"{ECS_IP}\n".encode("utf-8"),
        )

        self.assertEqual(response["text_prefix"], f"{ECS_IP}\n")
        self.assertEqual(collector._metadata_text(response), ECS_IP)
        self.assertTrue(response["json_parse_error"])

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
            qwen_model="qwen3-vl-flash",
            deployed_commit=COMMIT,
            timeout_seconds=10,
            proof_mode="ecs-public",
            ecs_region="us-west-1",
            ecs_instance_id="i-accountable-swarm",
            ecs_public_ip="8.8.8.8",
            fetcher=_fake_fetcher(qwen_status="ok"),
            metadata_fetcher=_fake_metadata_fetcher(region="us-west-1", instance_id="i-accountable-swarm"),
        )

        self.assertEqual(report["outcome"], "NARROW_CLAIM")
        self.assertFalse(report["pass_conditions"]["base_url_matches_public_ip_when_ip_literal"])

    def test_ecs_public_mode_rejects_hostname_base_url(self) -> None:
        report = collector.collect_report(
            base_url="http://example.com:8000",
            qwen_model="qwen3-vl-flash",
            deployed_commit=COMMIT,
            timeout_seconds=10,
            proof_mode="ecs-public",
            ecs_region="us-west-1",
            ecs_instance_id="i-accountable-swarm",
            ecs_public_ip="8.8.8.8",
            fetcher=_fake_fetcher(qwen_status="ok"),
            metadata_fetcher=_fake_metadata_fetcher(region="us-west-1", instance_id="i-accountable-swarm"),
        )

        self.assertEqual(report["outcome"], "NARROW_CLAIM")
        self.assertFalse(report["pass_conditions"]["base_url_is_public_endpoint"])
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
                fetcher=_raising_fetcher,
            )

    def test_rejects_secret_like_inputs_before_fetch(self) -> None:
        with self.assertRaisesRegex(ValueError, "secret-like material"):
            collector.collect_report(
                base_url="http://8.8.8.8:8000/github_pat_ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                qwen_model="qwen-plus",
                deployed_commit=COMMIT,
                timeout_seconds=10,
                proof_mode="ecs-public",
                ecs_region="us-west-1",
                ecs_instance_id="i-accountable-swarm",
                ecs_public_ip="8.8.8.8",
                fetcher=_raising_fetcher,
            )

    def test_rejects_bearer_redaction_prefix_bypass_before_fetch(self) -> None:
        with self.assertRaisesRegex(ValueError, "secret-like material"):
            collector.collect_report(
                base_url="http://8.8.8.8:8000",
                qwen_model="Authorization: Bearer <redacted>gho_abcdefghijklmno",
                deployed_commit=COMMIT,
                timeout_seconds=10,
                proof_mode="ecs-public",
                ecs_region="us-west-1",
                ecs_instance_id="i-accountable-swarm",
                ecs_public_ip="8.8.8.8",
                fetcher=_raising_fetcher,
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
                    f"{COMMIT}\nbranch",
                    "--qwen-model",
                    "qwen-plus\nbad",
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
        self.assertNotIn("\n", report["deployed_commit"])
        self.assertNotIn("\n", report["qwen_model"])
        self.assertNotIn("\n", report["error"]["message"])

    def test_allow_narrow_claim_does_not_write_secret_like_input_report(self) -> None:
        with TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "ecs_report.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.collect_ecs_smoke_report",
                    "--base-url",
                    "http://8.8.8.8:8000/gho_abcdefghijklmno",
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

        self.assertEqual(result.returncode, 2)
        self.assertIn("secret-like material", result.stderr)
        self.assertFalse(out.exists())


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
                if self.path == "/qwen-ping?model=qwen3-vl-flash":
                    if qwen_status == "ok":
                        _send_json(self, {"content_prefix": "OK.", "model": "qwen3-vl-flash", "status": "ok"})
                    elif qwen_status == "bad_content":
                        _send_json(self, {"content_prefix": "NOPE", "model": "qwen3-vl-flash", "status": "ok"})
                    else:
                        _send_json(self, {"model": "qwen3-vl-flash", "status": qwen_status}, status=503)
                    return
                if self.path == "/qwen-vl-fixture?model=qwen3-vl-flash":
                    if qwen_status == "ok":
                        _send_json(
                            self,
                            {
                                "bbox_2d_norm_1000": [250, 250, 750, 750],
                                "decision": "VETO",
                                "label": "marked hazard",
                                "model": "qwen3-vl-flash",
                                "schema_version": "decisiontrace.v2",
                                "status": "ok",
                                "trace_summary_sha": "a" * 64,
                            },
                        )
                    else:
                        _send_json(self, {"model": "qwen3-vl-flash", "status": qwen_status}, status=503)
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
        if path == "/qwen-ping?model=qwen3-vl-flash":
            if qwen_status == "ok":
                return _json_response({"content_prefix": "OK.", "model": "qwen3-vl-flash", "status": "ok"})
            if qwen_status == "bad_content":
                return _json_response({"content_prefix": "NOPE", "model": "qwen3-vl-flash", "status": "ok"})
            return _json_response({"model": "qwen3-vl-flash", "status": qwen_status}, status=503)
        if path == "/qwen-vl-fixture?model=qwen3-vl-flash":
            if qwen_status == "ok":
                return _json_response(
                    {
                        "bbox_2d_norm_1000": [250, 250, 750, 750],
                        "decision": "VETO",
                        "label": "marked hazard",
                        "model": "qwen3-vl-flash",
                        "schema_version": "decisiontrace.v2",
                        "status": "ok",
                        "trace_summary_sha": "a" * 64,
                    }
                )
            return _json_response({"model": "qwen3-vl-flash", "status": qwen_status}, status=503)
        return _json_response({"error": "not_found"}, status=404)

    return fetcher


def _fake_metadata_fetcher(*, region: str, instance_id: str, identity_content_type: str = "application/json"):
    def fetcher(*, timeout_seconds: int) -> dict[str, object]:
        del timeout_seconds
        return {
            "token": _text_response("metadata-token", content_type="text/plain"),
            "identity": _json_response(
                {
                    "region-id": region,
                    "instance-id": instance_id,
                    "zone-id": f"{region}-a",
                    "image-id": "aliyun_3_x64_20G_alibase_20260201.vhd",
                },
                content_type=identity_content_type,
            ),
            "public_ipv4": _text_response(ECS_IP, content_type="text/plain"),
            "eipv4": _text_response("", content_type="text/plain"),
        }

    return fetcher


def _missing_metadata_fetcher(*, timeout_seconds: int) -> dict[str, object]:
    del timeout_seconds
    return {
        "status_code": 0,
        "content_type": "",
        "body_sha256": "",
        "byte_count": 0,
        "error": "URLError",
    }


def _raising_fetcher(*, base_url: str, path: str, timeout_seconds: int) -> dict[str, object]:
    raise AssertionError(f"fetcher should not be called for {base_url} {path} {timeout_seconds}")


def _json_response(
    payload: dict[str, object],
    *,
    status: int = 200,
    content_type: str = "application/json",
) -> dict[str, object]:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    response = {
        "status_code": status,
        "content_type": content_type,
        "body_sha256": "d" * 64,
        "byte_count": len(body),
    }
    if content_type == "application/json":
        response["json"] = payload
    else:
        response["text_prefix"] = body[:128].decode("utf-8", errors="replace")
        response["json"] = json.loads(body.decode("utf-8"))
    return response


def _text_response(text: str, *, content_type: str, status: int = 200) -> dict[str, object]:
    body = text.encode("utf-8")
    return {
        "status_code": status,
        "content_type": content_type,
        "body_sha256": "e" * 64,
        "byte_count": len(body),
        "text_prefix": text[:128],
    }
