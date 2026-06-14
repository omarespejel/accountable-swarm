import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase

from accountable_swarm.swarm import SUPPORTED_MISSION_SCENARIOS


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
            self.assertEqual(report["case_count"], len(SUPPORTED_MISSION_SCENARIOS))
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
            self.assertTrue(report["pass_conditions"]["all_case_trace_paths_confined"])
            self.assertFalse(report["pass_conditions"]["all_cases_verified"])
            failing_cases = [case for case in report["cases"] if "error_type" in case]
            self.assertEqual(len(failing_cases), 1)
            self.assertEqual(failing_cases[0]["error_type"], "trace_artifact_invalid")
            self.assertEqual(failing_cases[0]["error_message"], "referenced trace artifact could not be verified")
            self.assertEqual(failing_cases[0]["error_classes"], ["ValueError"])
            self.assertEqual(failing_cases[0]["failed_trace_kinds"], ["agent:sim-agent-0"])
            self.assertNotIn(str(trace_root), json.dumps(report, sort_keys=True))
            self.assertNotIn(tampered_relative_path, json.dumps(failing_cases[0], sort_keys=True))

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
            self.assertFalse(report["pass_conditions"]["all_case_trace_paths_confined"])
            self.assertEqual(report["cases"][0]["error_type"], "trace_path_invalid")
            self.assertEqual(report["cases"][0]["error_class"], "ValueError")
            self.assertNotIn(str(trace_root), json.dumps(report, sort_keys=True))

    def test_verifier_rejects_symlink_escape_without_reading_outside_root(self) -> None:
        with TemporaryDirectory() as tmpdir:
            trace_root, suite_report = _write_suite(tmpdir)
            suite = json.loads(suite_report.read_text(encoding="utf-8"))
            case = suite["cases"][0]
            agent_id, relative_path = sorted(case["trace_files"]["agents"].items())[0]
            trace_path = trace_root / relative_path
            trace_path.unlink()
            outside_path = Path(tmpdir) / "outside.json"
            outside_path.write_text("not a trace\n", encoding="utf-8")
            trace_path.symlink_to(outside_path)
            verify_report = Path(tmpdir) / "verify_symlink_report.json"
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
            self.assertFalse(report["pass_conditions"]["all_case_trace_paths_confined"])
            failing_cases = [case for case in report["cases"] if "error_type" in case]
            self.assertEqual(len(failing_cases), 1)
            self.assertEqual(failing_cases[0]["error_type"], "trace_path_invalid")
            self.assertNotIn(str(outside_path), json.dumps(report, sort_keys=True))
            self.assertNotIn(f"{agent_id}:{relative_path}", json.dumps(report, sort_keys=True))

    def test_verifier_writes_narrow_report_for_invalid_suite_report(self) -> None:
        with TemporaryDirectory() as tmpdir:
            trace_root = Path(tmpdir) / "mission-suite"
            trace_root.mkdir()
            suite_report = Path(tmpdir) / "bad_suite_report.json"
            suite_report.write_text("[]\n", encoding="utf-8")
            verify_report = Path(tmpdir) / "verify_bad_suite_report.json"
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
            self.assertTrue(report["pass_conditions"]["suite_report_loaded"])
            self.assertFalse(report["pass_conditions"]["suite_report_valid"])
            self.assertFalse(report["pass_conditions"]["suite_cases_valid"])
            self.assertEqual(report["error_type"], "suite_report_invalid")
            self.assertEqual(report["cases"], [])

    def test_verifier_rejects_incompatible_suite_schema_version(self) -> None:
        with TemporaryDirectory() as tmpdir:
            trace_root, suite_report = _write_suite(tmpdir)
            suite = json.loads(suite_report.read_text(encoding="utf-8"))
            suite["schema_version"] = "swarm-mission-suite-report.v0"
            suite_report.write_text(json.dumps(suite, sort_keys=True) + "\n", encoding="utf-8")
            verify_report = Path(tmpdir) / "verify_bad_schema_report.json"
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
            self.assertEqual(report["suite_schema_version"], "swarm-mission-suite-report.v0")
            self.assertFalse(report["pass_conditions"]["suite_schema_version_valid"])
            self.assertFalse(report["pass_conditions"]["suite_cases_valid"])
            self.assertEqual(report["error_type"], "suite_schema_version_mismatch")
            self.assertEqual(report["cases"], [])

    def test_verifier_reports_summary_sha_mismatch_kind(self) -> None:
        with TemporaryDirectory() as tmpdir:
            trace_root, suite_report = _write_suite(tmpdir)
            suite = json.loads(suite_report.read_text(encoding="utf-8"))
            case = suite["cases"][0]
            agent_id = sorted(case["trace_summary_shas"])[0]
            case["trace_summary_shas"][agent_id] = "f" * 64
            suite_report.write_text(json.dumps(suite, sort_keys=True) + "\n", encoding="utf-8")
            verify_report = Path(tmpdir) / "verify_mismatch_report.json"
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
            failing_cases = [case for case in report["cases"] if "error_type" in case]
            self.assertEqual(len(failing_cases), 1)
            self.assertEqual(failing_cases[0]["error_type"], "trace_summary_sha_mismatch")
            self.assertEqual(failing_cases[0]["failed_trace_kinds"], [f"agent:{agent_id}"])
            self.assertEqual(failing_cases[0]["error_classes"], [])


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
