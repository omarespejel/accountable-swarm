import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from accountable_swarm.trace.models import trace_from_dict, verify_trace

ROOT = Path(__file__).resolve().parents[1]


class QwenGuardHealthCheckCliTests(TestCase):
    def test_fixture_health_check_emits_verified_trace(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            trace_path = tmp_path / "trace.json"
            report_path = tmp_path / "report.json"

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.run_qwenguard_no_motion_health_check",
                    "--image",
                    "fixtures/hazard_marker.ppm",
                    "--mode",
                    "fixture",
                    "--policy-available",
                    "--simulate-safe-motion-authority",
                    "--trace-out",
                    str(trace_path),
                    "--report-out",
                    str(report_path),
                ],
                text=True,
                capture_output=True,
                cwd=ROOT,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            trace = trace_from_dict(json.loads(trace_path.read_text(encoding="utf-8")))
            self.assertEqual(verify_trace(trace), json.loads(report_path.read_text())["trace_summary_sha"])
            self.assertEqual([event.decision for event in trace.events], ["SELECT", "ALLOW", "ALLOW", "EVALUATE"])
            self.assertIs(trace.events[2].command["motion_executed"], False)

    def test_degraded_health_check_holds(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            trace_path = tmp_path / "trace.json"
            report_path = tmp_path / "report.json"

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.run_qwenguard_no_motion_health_check",
                    "--image",
                    "fixtures/hazard_marker.ppm",
                    "--mode",
                    "degraded",
                    "--policy-available",
                    "--simulate-safe-motion-authority",
                    "--trace-out",
                    str(trace_path),
                    "--report-out",
                    str(report_path),
                ],
                text=True,
                capture_output=True,
                cwd=ROOT,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["outcome"], "DEGRADED")
            self.assertEqual(report["gate"]["gate_decision"], "HOLD")
            self.assertTrue(report["pass_conditions"]["degraded_holds"])

    def test_blocked_fixture_health_check_is_not_go(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            trace_path = tmp_path / "trace.json"
            report_path = tmp_path / "report.json"

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.run_qwenguard_no_motion_health_check",
                    "--image",
                    "fixtures/hazard_marker.ppm",
                    "--mode",
                    "fixture",
                    "--trace-out",
                    str(trace_path),
                    "--report-out",
                    str(report_path),
                ],
                text=True,
                capture_output=True,
                cwd=ROOT,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["outcome"], "NARROW_CLAIM")
            self.assertEqual(report["gate"]["gate_decision"], "HOLD")
            self.assertFalse(report["pass_conditions"]["gate_allows_action"])

    def test_trace_mutation_is_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            trace_path = tmp_path / "trace.json"
            report_path = tmp_path / "report.json"
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.run_qwenguard_no_motion_health_check",
                    "--image",
                    "fixtures/hazard_marker.ppm",
                    "--mode",
                    "fixture",
                    "--policy-available",
                    "--simulate-safe-motion-authority",
                    "--trace-out",
                    str(trace_path),
                    "--report-out",
                    str(report_path),
                ],
                text=True,
                capture_output=True,
                cwd=ROOT,
                check=True,
            )

            value = json.loads(trace_path.read_text(encoding="utf-8"))
            value["events"][0]["command"]["target_mark_id"] = "C"

            with self.assertRaises(ValueError):
                verify_trace(trace_from_dict(value))
