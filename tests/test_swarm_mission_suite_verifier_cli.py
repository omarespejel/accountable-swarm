import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]


class SwarmMissionSuiteVerifierCliTests(TestCase):
    def test_verifier_accepts_clean_mission_suite(self) -> None:
        with TemporaryDirectory() as tmpdir:
            trace_root, suite_report = _write_suite(tmpdir)
            verify_report = Path(tmpdir) / "verify_clean_report.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/verify_swarm_mission_suite.py",
                    "--trace-root",
                    str(trace_root),
                    "--report",
                    str(suite_report),
                    "--report-out",
                    str(verify_report),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(verify_report.read_text(encoding="utf-8"))
            self.assertEqual(report["schema_version"], "swarm-mission-suite-verify-report.v1")
            self.assertEqual(report["outcome"], "GO")
            self.assertEqual(report["suite_outcome"], "GO")
            self.assertEqual(report["case_count"], 4)
            self.assertTrue(all(report["pass_conditions"].values()))
            for case in report["cases"]:
                self.assertTrue(case["pass_conditions"]["case_verified"])
                self.assertNotIn("error_type", case)

    def test_verifier_rejects_tampered_agent_trace(self) -> None:
        with TemporaryDirectory() as tmpdir:
            trace_root, suite_report = _write_suite(tmpdir)
            tampered_relative_path = _tamper_first_agent_trace(trace_root, suite_report)
            verify_report = Path(tmpdir) / "verify_tampered_report.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/verify_swarm_mission_suite.py",
                    "--trace-root",
                    str(trace_root),
                    "--report",
                    str(suite_report),
                    "--report-out",
                    str(verify_report),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 4)
            report = json.loads(verify_report.read_text(encoding="utf-8"))
            self.assertEqual(report["outcome"], "NARROW_CLAIM")
            self.assertFalse(report["pass_conditions"]["all_agent_trace_shas_match"])
            self.assertTrue(report["pass_conditions"]["all_mission_trace_shas_match"])
            self.assertTrue(report["pass_conditions"]["all_case_trace_paths_relative"])
            self.assertFalse(report["pass_conditions"]["all_cases_verified"])
            failing_cases = [case for case in report["cases"] if "error_type" in case]
            self.assertEqual(len(failing_cases), 1)
            self.assertEqual(failing_cases[0]["error_type"], "trace_artifact_invalid")
            self.assertEqual(failing_cases[0]["error_message"], "referenced trace artifact could not be verified")
            self.assertEqual(failing_cases[0]["error_classes"], ["ValueError"])
            self.assertEqual(failing_cases[0]["failed_trace_kinds"], ["agent:sim-agent-0"])
            self.assertNotIn(str(trace_root), json.dumps(report, sort_keys=True))
            self.assertNotIn(tampered_relative_path, failing_cases[0])

    def test_verifier_rejects_absolute_trace_paths_without_leaking_path(self) -> None:
        with TemporaryDirectory() as tmpdir:
            trace_root, suite_report = _write_suite(tmpdir)
            suite = json.loads(suite_report.read_text(encoding="utf-8"))
            suite["cases"][0]["trace_files"]["mission"] = str(trace_root / "private" / "mission.json")
            suite_report.write_text(json.dumps(suite, sort_keys=True) + "\n", encoding="utf-8")
            verify_report = Path(tmpdir) / "verify_absolute_path_report.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/verify_swarm_mission_suite.py",
                    "--trace-root",
                    str(trace_root),
                    "--report",
                    str(suite_report),
                    "--report-out",
                    str(verify_report),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 4)
            report = json.loads(verify_report.read_text(encoding="utf-8"))
            self.assertEqual(report["outcome"], "NARROW_CLAIM")
            self.assertFalse(report["pass_conditions"]["all_case_trace_paths_relative"])
            self.assertEqual(report["cases"][0]["error_type"], "trace_path_invalid")
            self.assertEqual(report["cases"][0]["error_class"], "ValueError")
            self.assertNotIn(str(trace_root), json.dumps(report, sort_keys=True))


def _write_suite(tmpdir: str) -> tuple[Path, Path]:
    trace_root = Path(tmpdir) / "mission-suite"
    suite_report = Path(tmpdir) / "mission_suite_report.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_swarm_mission_suite.py",
            "--trace-root",
            str(trace_root),
            "--report-out",
            str(suite_report),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return trace_root, suite_report


def _tamper_first_agent_trace(trace_root: Path, suite_report: Path) -> str:
    suite = json.loads(suite_report.read_text(encoding="utf-8"))
    case = suite["cases"][0]
    agent_id, relative_path = sorted(case["trace_files"]["agents"].items())[0]
    trace_path = trace_root / relative_path
    value = json.loads(trace_path.read_text(encoding="utf-8"))
    value["events"][0]["command"]["accepted_x"] += 1
    trace_path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    return f"{agent_id}:{relative_path}"
