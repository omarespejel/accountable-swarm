import json
from pathlib import Path
import subprocess
import sys
from unittest import TestCase

from accountable_swarm.world_model import verify_world_model_state, world_model_from_dict
from accountable_swarm.trace.models import trace_from_dict, verify_trace


ROOT = Path(__file__).resolve().parents[1]


class HazardFormationGateCliTests(TestCase):
    def test_fixture_hazard_forms_x_and_writes_replayable_traces(self) -> None:
        trace_dir = ROOT / "runs/hazard_formation/test_fixture_x"
        report_path = ROOT / "runs/hazard_formation/test_fixture_x_report.json"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.run_hazard_formation_gate",
                "--image",
                "fixtures/hazard_marker.ppm",
                "--mode",
                "fixture",
                "--formation",
                "x",
                "--trace-dir",
                str(trace_dir),
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

        self.assertEqual(report["outcome"], "GO")
        self.assertEqual(report["mode"], "fixture")
        self.assertEqual(report["hazard"]["cell"], {"x": 3, "y": 2})
        self.assertEqual(report["formation"], "x")
        self.assertTrue(report["pass_conditions"]["hazard_cell_quantized"])
        self.assertTrue(report["pass_conditions"]["formation_run_go"])
        self.assertIsNone(report["mission_choice"])
        self.assertEqual(report["sim_report"]["same_cell_collision_count"], 0)
        self.assertEqual(report["sim_report"]["swap_collision_count"], 0)
        self.assertEqual(report["sim_report"]["obstacle_occupancy_violation_count"], 0)
        self.assertTrue(report["pass_conditions"]["world_model_timeline_replay_deterministic"])
        self.assertEqual(report["world_model"]["state_count"], report["ticks"])
        self.assertEqual(report["world_model"]["predicted_conflict_count"], 0)
        self.assertEqual(len(report["world_model"]["first_world_model_sha"]), 64)
        self.assertEqual(len(report["world_model"]["last_world_model_sha"]), 64)
        self.assertEqual(len(report["world_model"]["export_trace_summary_sha"]), 64)
        self.assertFalse(Path(report["world_model"]["path"]).is_absolute())
        self.assertFalse(Path(report["world_model"]["export_trace_path"]).is_absolute())
        self.assertTrue((trace_dir / "hazard.json").is_file())
        self.assertTrue((trace_dir / "agents" / "sim-agent-0.json").is_file())
        self.assertTrue((trace_dir / "world_model_export.json").is_file())
        states = _load_world_model_timeline(trace_dir)
        self.assertEqual(len(states), report["ticks"])
        self.assertEqual(verify_world_model_state(states[0]), report["world_model"]["first_world_model_sha"])
        self.assertEqual(verify_world_model_state(states[-1]), report["world_model"]["last_world_model_sha"])
        self.assertEqual(states[0].observations[0].source, "fixture_bbox")
        self.assertEqual(states[0].hazards[0], states[0].observations[0].cell)
        self.assertEqual(len(states[0].agents), 4)
        self.assertEqual(len(states[0].reservations), 4)
        agent_trace = trace_from_dict(
            json.loads((trace_dir / "agents" / "sim-agent-0.json").read_text(encoding="utf-8"))
        )
        agent_state = next(agent for agent in states[0].agents if agent.agent_id == "sim-agent-0")
        self.assertEqual(agent_state.decision_event_sha, agent_trace.events[0].sha256)
        export_trace = trace_from_dict(
            json.loads((trace_dir / "world_model_export.json").read_text(encoding="utf-8"))
        )
        self.assertEqual(verify_trace(export_trace), report["world_model"]["export_trace_summary_sha"])
        self.assertEqual(export_trace.events[0].command["type"], "world_model_timeline_export")

    def test_fixture_hazard_can_emit_bounded_mission_choice_trace(self) -> None:
        trace_dir = ROOT / "runs/hazard_formation/test_fixture_x_mission"
        report_path = ROOT / "runs/hazard_formation/test_fixture_x_mission_report.json"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.run_hazard_formation_gate",
                "--image",
                "fixtures/hazard_marker.ppm",
                "--mode",
                "fixture",
                "--mission-source",
                "fixture",
                "--formation",
                "x",
                "--trace-dir",
                str(trace_dir),
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

        self.assertEqual(report["outcome"], "GO")
        self.assertEqual(report["mission_choice"]["source"], "fixture")
        self.assertEqual(report["mission_choice"]["choice"]["mission"], "surround_hazard")
        self.assertEqual(report["mission_choice"]["choice"]["risk"], "cautious")
        self.assertEqual(len(report["mission_choice"]["trace_summary_sha"]), 64)
        self.assertTrue(report["pass_conditions"]["mission_choice_validated"])
        self.assertTrue(report["pass_conditions"]["mission_trace_replay_deterministic"])
        self.assertTrue((trace_dir / "mission.json").is_file())

    def test_fixture_bounded_hold_position_keeps_agents_at_starts(self) -> None:
        trace_dir = ROOT / "runs/hazard_formation/test_fixture_hold_mission"
        report_path = ROOT / "runs/hazard_formation/test_fixture_hold_mission_report.json"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.run_hazard_formation_gate",
                "--image",
                "fixtures/hazard_marker.ppm",
                "--mode",
                "fixture",
                "--mission-source",
                "fixture",
                "--fixture-mission",
                "hold_position",
                "--fixture-risk",
                "balanced",
                "--formation",
                "x",
                "--trace-dir",
                str(trace_dir),
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

        self.assertEqual(report["outcome"], "GO")
        self.assertEqual(report["mission_choice"]["choice"], {"mission": "hold_position", "risk": "balanced"})
        self.assertIsNone(report["formation_plan"])
        self.assertEqual(report["ticks"], 1)
        self.assertEqual(report["sim_report"]["hold_count"], 4)
        self.assertTrue(report["pass_conditions"]["mission_choice_validated"])
        for agent_id, goal in report["assigned_goals"].items():
            agent_trace = trace_from_dict(
                json.loads((trace_dir / "agents" / f"{agent_id}.json").read_text(encoding="utf-8"))
            )
            command = agent_trace.events[0].command
            self.assertEqual(goal, {"x": command["from_x"], "y": command["from_y"]})
            self.assertEqual(agent_trace.events[0].decision, "HOLD")

    def test_degraded_mode_writes_hold_traces_without_model(self) -> None:
        trace_dir = ROOT / "runs/hazard_formation/test_degraded"
        report_path = ROOT / "runs/hazard_formation/test_degraded_report.json"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.run_hazard_formation_gate",
                "--image",
                "fixtures/hazard_marker.ppm",
                "--mode",
                "degraded",
                "--trace-dir",
                str(trace_dir),
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

        self.assertEqual(report["outcome"], "DEGRADED")
        self.assertIsNone(report["hazard"])
        self.assertTrue(report["pass_conditions"]["degraded_hold_selected"])
        self.assertTrue(report["pass_conditions"]["world_model_timeline_replay_deterministic"])
        self.assertEqual(report["world_model"]["state_count"], 1)
        self.assertEqual(report["sim_report"]["hold_count"], 4)
        self.assertEqual(report["sim_report"]["same_cell_collision_count"], 0)
        states = _load_world_model_timeline(trace_dir)
        self.assertEqual(states[0].observations[0].source, "degraded")
        self.assertEqual(states[0].hazards, ())

    def test_dashscope_missing_key_can_degrade_to_hold(self) -> None:
        trace_dir = ROOT / "runs/hazard_formation/test_missing_key"
        report_path = ROOT / "runs/hazard_formation/test_missing_key_report.json"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.run_hazard_formation_gate",
                "--image",
                "fixtures/hazard_marker.ppm",
                "--mode",
                "dashscope",
                "--degraded-on-error",
                "--trace-dir",
                str(trace_dir),
                "--report-out",
                str(report_path),
            ],
            cwd=ROOT,
            env={},
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(report["outcome"], "DEGRADED")
        self.assertIn("ALIBABA_API_KEY", report["model_error"])
        self.assertTrue(report["pass_conditions"]["degraded_hold_selected"])

    def test_dashscope_missing_key_fails_closed_without_degrade_flag(self) -> None:
        trace_dir = ROOT / "runs/hazard_formation/test_missing_key_fail"
        report_path = ROOT / "runs/hazard_formation/test_missing_key_fail_report.json"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.run_hazard_formation_gate",
                "--image",
                "fixtures/hazard_marker.ppm",
                "--mode",
                "dashscope",
                "--trace-dir",
                str(trace_dir),
                "--report-out",
                str(report_path),
            ],
            cwd=ROOT,
            env={},
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 3)
        self.assertIn("ALIBABA_API_KEY", result.stderr)


def _load_world_model_timeline(trace_dir: Path):
    timeline_path = trace_dir / "world_model_timeline.jsonl"
    return [
        world_model_from_dict(json.loads(line))
        for line in timeline_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
