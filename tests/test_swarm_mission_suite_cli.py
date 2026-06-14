import contextlib
import io
import json
import importlib.util
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from accountable_swarm.swarm import MISSION_MODEL_FIXTURE_ID, SUPPORTED_MISSION_SCENARIOS
from accountable_swarm.trace.models import trace_from_dict, verify_trace


ROOT = Path(__file__).resolve().parents[1]
MISSION_SUITE_SCRIPT = ROOT / "scripts/run_swarm_mission_suite.py"


class SwarmMissionSuiteCliTests(TestCase):
    def test_mission_suite_writes_expected_fixture_cases(self) -> None:
        with TemporaryDirectory() as tmpdir:
            trace_root = Path(tmpdir) / "mission-suite"
            report_path = Path(tmpdir) / "mission_suite_report.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/run_swarm_mission_suite.py",
                    "--trace-root",
                    str(trace_root),
                    "--report-out",
                    str(report_path),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["schema_version"], "swarm-mission-suite-report.v2")
            self.assertEqual(report["outcome"], "GO")
            self.assertEqual(report["mode"], "fixture")
            self.assertEqual(report["model"], MISSION_MODEL_FIXTURE_ID)
            self.assertEqual(report["case_count"], len(SUPPORTED_MISSION_SCENARIOS))
            self.assertEqual(report["covered_mission_scenarios"], sorted(SUPPORTED_MISSION_SCENARIOS))
            self.assertTrue(all(report["pass_conditions"].values()))

            cases = {case["mission_scenario"]: case for case in report["cases"]}
            self.assertEqual(set(cases), set(SUPPORTED_MISSION_SCENARIOS))
            for scenario, case in sorted(cases.items()):
                self.assertNotIn("trace_dir", case)
                self.assertEqual(case["mode"], "fixture")
                self.assertEqual(case["model"], MISSION_MODEL_FIXTURE_ID)
                self.assertEqual(case["expected_outcome"], "GO")
                self.assertEqual(case["actual_outcome"], "GO")
                self.assertEqual(case["mission_gate_report"]["outcome"], "GO")
                self.assertEqual(case["mission_gate_report"]["mission"]["scenario"], scenario)
                self.assertTrue(all(case["pass_conditions"].values()))
                self.assertTrue(all(case["mission_gate_report"]["pass_conditions"].values()))

                mission_trace_path = trace_root / case["trace_files"]["mission"]
                mission_trace = trace_from_dict(json.loads(mission_trace_path.read_text(encoding="utf-8")))
                self.assertEqual(verify_trace(mission_trace), case["mission_trace_summary_sha"])

                agent_files = case["trace_files"]["agents"]
                self.assertEqual(set(agent_files), set(case["trace_summary_shas"]))
                for agent_id, relative_path in sorted(agent_files.items()):
                    agent_trace = trace_from_dict(
                        json.loads((trace_root / relative_path).read_text(encoding="utf-8"))
                    )
                    self.assertEqual(verify_trace(agent_trace), case["trace_summary_shas"][agent_id])

                sim_report = case["mission_gate_report"]["sim_report"]
                replay = sim_report["replay"]
                self.assertEqual(sim_report["outcome"], "GO")
                self.assertEqual(replay["same_cell_collision_count"], 0)
                self.assertEqual(replay["swap_collision_count"], 0)
                self.assertEqual(replay["obstacle_occupancy_violation_count"], 0)

    def test_mission_suite_builds_dashscope_cases_with_requested_model(self) -> None:
        module = _load_mission_suite_module()
        seen_cases = []

        def fake_run_case(*, case, trace_root, repo_root):
            seen_cases.append(case)
            scenario = case["mission_scenario"]
            return {
                "case_id": case["case_id"],
                "purpose": case["purpose"],
                "mode": case["mode"],
                "model": case["model"],
                "mission_scenario": scenario,
                "expected_outcome": "GO",
                "actual_outcome": "GO",
                "mission_id": f"{scenario}-n4",
                "mission_report_file": f"{case['case_id']}/mission_gate_report.json",
                "trace_files": {
                    "mission": f"{case['case_id']}/trace/mission.json",
                    "agents": {},
                },
                "mission_trace_summary_sha": "0" * 64,
                "trace_summary_shas": {},
                "pass_conditions": {
                    "mission_gate_command_succeeded": True,
                    "outcome_matches_expected": True,
                    "child_pass_conditions_true": True,
                    "mission_trace_replay_deterministic": True,
                    "agent_traces_replay_deterministic": True,
                    "sim_report_go": True,
                    "replay_violation_counts_zero": True,
                    "scenario_matches_case": True,
                    "child_mode_matches_requested": True,
                    "child_model_matches_requested": True,
                },
                "mission_gate_report": {
                    "outcome": "GO",
                    "mission": {"scenario": scenario},
                    "pass_conditions": {},
                    "sim_report": {"outcome": "GO", "replay": {}},
                },
            }

        with TemporaryDirectory() as tmpdir:
            trace_root = Path(tmpdir) / "mission-suite"
            report_path = Path(tmpdir) / "mission_suite_report.json"
            argv = [
                "run_swarm_mission_suite.py",
                "--mode",
                "dashscope",
                "--model",
                "qwen-plus",
                "--trace-root",
                str(trace_root),
                "--report-out",
                str(report_path),
            ]
            with (
                patch.object(module, "_run_case", side_effect=fake_run_case),
                patch.object(sys, "argv", argv),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                returncode = module.main()

            self.assertEqual(returncode, 0)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["outcome"], "GO")
            self.assertEqual(report["mode"], "dashscope")
            self.assertEqual(report["model"], "qwen-plus")
            self.assertEqual(report["covered_mission_scenarios"], sorted(SUPPORTED_MISSION_SCENARIOS))
            self.assertTrue(all(report["pass_conditions"].values()))
            self.assertEqual({case["mission_scenario"] for case in seen_cases}, set(SUPPORTED_MISSION_SCENARIOS))
            self.assertTrue(all(case["mode"] == "dashscope" for case in seen_cases))
            self.assertTrue(all(case["model"] == "qwen-plus" for case in seen_cases))
            self.assertTrue(all("-dashscope-qwen-plus-" in case["case_id"] for case in seen_cases))

    def test_run_case_passes_mode_and_model_to_child_gate(self) -> None:
        module = _load_mission_suite_module()
        case = {
            "case_id": "mission-corridor-dashscope-qwen-plus-n4-go",
            "mode": "dashscope",
            "model": "qwen-plus",
            "mission_scenario": "corridor",
            "expected_outcome": "GO",
            "purpose": "dashscope mission binding for reviewed scenario corridor",
        }

        def fake_run(args, **kwargs):
            self.assertEqual(args[args.index("--mode") + 1], "dashscope")
            self.assertEqual(args[args.index("--model") + 1], "qwen-plus")
            self.assertEqual(args[args.index("--mission-scenario") + 1], "corridor")
            return subprocess.CompletedProcess(args=args, returncode=7, stdout="", stderr="")

        with TemporaryDirectory() as tmpdir:
            with patch.object(module.subprocess, "run", side_effect=fake_run):
                result = module._run_case(
                    case=case,
                    trace_root=Path(tmpdir) / "mission-suite",
                    repo_root=ROOT,
                )

        self.assertEqual(result["actual_outcome"], "NARROW_CLAIM")
        self.assertEqual(result["mode"], "dashscope")
        self.assertEqual(result["model"], "qwen-plus")

    def test_run_case_rejects_child_mode_model_mismatch(self) -> None:
        module = _load_mission_suite_module()
        case = {
            "case_id": "mission-corridor-dashscope-qwen-plus-n4-go",
            "mode": "dashscope",
            "model": "qwen-plus",
            "mission_scenario": "corridor",
            "expected_outcome": "GO",
            "purpose": "dashscope mission binding for reviewed scenario corridor",
        }

        def fake_run(args, **kwargs):
            report_path = Path(args[args.index("--report-out") + 1])
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(
                json.dumps(
                    {
                        "outcome": "GO",
                        "mode": "fixture",
                        "model": MISSION_MODEL_FIXTURE_ID,
                        "mission": {
                            "mission_id": "corridor-n4",
                            "scenario": "corridor",
                        },
                        "mission_trace_summary_sha": "0" * 64,
                        "trace_summary_shas": {},
                        "pass_conditions": {
                            "mission_json_validated": True,
                            "mission_trace_replay_deterministic": True,
                            "agent_traces_replay_deterministic": True,
                            "sim_report_go": True,
                            "agent_trace_replay_counts_zero": True,
                        },
                        "sim_report": {
                            "outcome": "GO",
                            "replay": {
                                "same_cell_collision_count": 0,
                                "swap_collision_count": 0,
                                "obstacle_occupancy_violation_count": 0,
                            },
                        },
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        with TemporaryDirectory() as tmpdir:
            with (
                patch.object(module.subprocess, "run", side_effect=fake_run),
                patch.object(
                    module,
                    "_verify_case_traces",
                    return_value={
                        "mission_summary_sha": "0" * 64,
                        "agent_summary_shas": {},
                        "relative_files": {
                            "mission": "mission-corridor-dashscope-qwen-plus-n4-go/trace/mission.json",
                            "agents": {},
                        },
                    },
                ),
            ):
                result = module._run_case(
                    case=case,
                    trace_root=Path(tmpdir) / "mission-suite",
                    repo_root=ROOT,
                )

        self.assertEqual(result["actual_outcome"], "GO")
        self.assertFalse(result["pass_conditions"]["child_mode_matches_requested"])
        self.assertFalse(result["pass_conditions"]["child_model_matches_requested"])
        self.assertFalse(all(result["pass_conditions"].values()))

    def test_mission_suite_writes_narrow_report_when_child_gate_fails(self) -> None:
        module = _load_mission_suite_module()
        one_case = (
            {
                "case_id": "mission-corridor-fixture-n4-go",
                "mode": "fixture",
                "model": MISSION_MODEL_FIXTURE_ID,
                "mission_scenario": "corridor",
                "expected_outcome": "GO",
                "purpose": "fixture mission binding for reviewed scenario corridor",
            },
        )
        failed_result = subprocess.CompletedProcess(
            args=[],
            returncode=7,
            stdout="child stdout with /tmp/private/path\n",
            stderr="Traceback with /Users/private/path\n",
        )

        with TemporaryDirectory() as tmpdir:
            trace_root = Path(tmpdir) / "mission-suite"
            report_path = Path(tmpdir) / "mission_suite_report.json"
            argv = [
                "run_swarm_mission_suite.py",
                "--trace-root",
                str(trace_root),
                "--report-out",
                str(report_path),
            ]
            with (
                patch.object(module, "DEFAULT_CASES", one_case),
                patch.object(module.subprocess, "run", return_value=failed_result),
                patch.object(sys, "argv", argv),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                returncode = module.main()

            self.assertEqual(returncode, 4)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["outcome"], "NARROW_CLAIM")
            self.assertFalse(report["pass_conditions"]["all_mission_gate_commands_succeeded"])
            case = report["cases"][0]
            self.assertEqual(case["actual_outcome"], "NARROW_CLAIM")
            self.assertEqual(case["error_type"], "mission_gate_failed")
            self.assertEqual(case["error_message"], "child mission gate command failed")
            self.assertNotIn("stdout_excerpt", case)
            self.assertNotIn("stderr_excerpt", case)
            self.assertNotIn("/Users/private/path", json.dumps(report, sort_keys=True))
            self.assertFalse(case["pass_conditions"]["mission_gate_command_succeeded"])
            self.assertFalse(case["pass_conditions"]["mission_trace_replay_deterministic"])
            self.assertFalse(case["pass_conditions"]["child_mode_matches_requested"])
            self.assertFalse(case["pass_conditions"]["child_model_matches_requested"])

    def test_mission_suite_writes_narrow_report_when_child_gate_times_out(self) -> None:
        module = _load_mission_suite_module()
        one_case = (
            {
                "case_id": "mission-corridor-fixture-n4-go",
                "mode": "fixture",
                "model": MISSION_MODEL_FIXTURE_ID,
                "mission_scenario": "corridor",
                "expected_outcome": "GO",
                "purpose": "fixture mission binding for reviewed scenario corridor",
            },
        )

        def timeout_run(args, **kwargs):
            self.assertEqual(kwargs["timeout"], module.MISSION_GATE_TIMEOUT_SECONDS)
            raise subprocess.TimeoutExpired(cmd=args, timeout=kwargs["timeout"])

        with TemporaryDirectory() as tmpdir:
            trace_root = Path(tmpdir) / "mission-suite"
            report_path = Path(tmpdir) / "mission_suite_report.json"
            argv = [
                "run_swarm_mission_suite.py",
                "--trace-root",
                str(trace_root),
                "--report-out",
                str(report_path),
            ]
            with (
                patch.object(module, "DEFAULT_CASES", one_case),
                patch.object(module.subprocess, "run", side_effect=timeout_run),
                patch.object(sys, "argv", argv),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                returncode = module.main()

            self.assertEqual(returncode, 4)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["outcome"], "NARROW_CLAIM")
            case = report["cases"][0]
            self.assertEqual(case["actual_outcome"], "NARROW_CLAIM")
            self.assertEqual(case["mission_gate_returncode"], 124)
            self.assertEqual(case["error_type"], "mission_gate_timeout")
            self.assertEqual(case["error_message"], "child mission gate command timed out")
            self.assertFalse(case["pass_conditions"]["mission_gate_command_succeeded"])

    def test_mission_suite_writes_narrow_report_when_trace_artifact_is_invalid(self) -> None:
        module = _load_mission_suite_module()
        one_case = (
            {
                "case_id": "mission-corridor-fixture-n4-go",
                "mode": "fixture",
                "model": MISSION_MODEL_FIXTURE_ID,
                "mission_scenario": "corridor",
                "expected_outcome": "GO",
                "purpose": "fixture mission binding for reviewed scenario corridor",
            },
        )

        def fake_run(args, **kwargs):
            report_path = Path(args[args.index("--report-out") + 1])
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(
                json.dumps(
                    {
                        "outcome": "GO",
                        "mission": {
                            "mission_id": "corridor-n4",
                            "scenario": "corridor",
                        },
                        "mission_trace_summary_sha": "0" * 64,
                        "trace_summary_shas": {"sim-agent-0": "1" * 64},
                        "pass_conditions": {
                            "mission_json_validated": True,
                            "mission_trace_replay_deterministic": True,
                            "agent_traces_replay_deterministic": True,
                            "sim_report_go": True,
                            "agent_trace_replay_counts_zero": True,
                        },
                        "sim_report": {
                            "outcome": "GO",
                            "replay": {
                                "same_cell_collision_count": 0,
                                "swap_collision_count": 0,
                                "obstacle_occupancy_violation_count": 0,
                            },
                        },
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        with TemporaryDirectory() as tmpdir:
            trace_root = Path(tmpdir) / "mission-suite"
            report_path = Path(tmpdir) / "mission_suite_report.json"
            argv = [
                "run_swarm_mission_suite.py",
                "--trace-root",
                str(trace_root),
                "--report-out",
                str(report_path),
            ]
            with (
                patch.object(module, "DEFAULT_CASES", one_case),
                patch.object(module.subprocess, "run", side_effect=fake_run),
                patch.object(sys, "argv", argv),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                returncode = module.main()

            self.assertEqual(returncode, 4)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["outcome"], "NARROW_CLAIM")
            self.assertFalse(report["pass_conditions"]["all_mission_traces_replay_deterministic"])
            case = report["cases"][0]
            self.assertEqual(case["error_type"], "case_artifact_invalid")
            self.assertEqual(case["error_message"], "child mission gate artifact could not be verified")
            self.assertEqual(case["error_class"], "FileNotFoundError")
            self.assertNotIn("stdout_excerpt", case)
            self.assertNotIn("stderr_excerpt", case)
            self.assertFalse(case["pass_conditions"]["mission_trace_replay_deterministic"])
            self.assertFalse(case["pass_conditions"]["child_mode_matches_requested"])
            self.assertFalse(case["pass_conditions"]["child_model_matches_requested"])


def _load_mission_suite_module():
    spec = importlib.util.spec_from_file_location("mission_suite_for_test", MISSION_SUITE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load mission suite script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
