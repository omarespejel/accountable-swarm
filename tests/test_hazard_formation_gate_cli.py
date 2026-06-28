from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase

from accountable_swarm.trace.models import trace_from_dict, verify_trace
from accountable_swarm.world_model import verify_world_model_state, world_model_from_dict


ROOT = Path(__file__).resolve().parents[1]


class HazardFormationGateCliTests(TestCase):
    def test_fixture_hazard_forms_x_and_writes_replayable_traces(self) -> None:
        with _temp_run_paths("fixture_x") as (trace_dir, report_path):
            result = _run_gate("--mode", "fixture", "--formation", "x", trace_dir=trace_dir, report_path=report_path)
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
            agent_trace = trace_from_dict(
                json.loads((trace_dir / "agents" / "sim-agent-0.json").read_text(encoding="utf-8"))
            )
            export_trace = trace_from_dict(
                json.loads((trace_dir / "world_model_export.json").read_text(encoding="utf-8"))
            )

        self.assertEqual(len(states), report["ticks"])
        self.assertEqual(verify_world_model_state(states[0]), report["world_model"]["first_world_model_sha"])
        self.assertEqual(verify_world_model_state(states[-1]), report["world_model"]["last_world_model_sha"])
        self.assertEqual(states[0].observations[0].source, "fixture_bbox")
        self.assertEqual(states[0].hazards[0], states[0].observations[0].cell)
        self.assertEqual(len(states[0].agents), 4)
        self.assertEqual(len(states[0].reservations), 4)
        agent_state = next(agent for agent in states[0].agents if agent.agent_id == "sim-agent-0")
        self.assertEqual(agent_state.decision_event_sha, agent_trace.events[0].sha256)
        self.assertEqual(verify_trace(export_trace), report["world_model"]["export_trace_summary_sha"])
        self.assertEqual(export_trace.events[0].command["type"], "world_model_timeline_export")

    def test_fixture_hazard_can_emit_bounded_mission_choice_trace(self) -> None:
        with _temp_run_paths("fixture_x_mission") as (trace_dir, report_path):
            result = _run_gate(
                "--mode",
                "fixture",
                "--mission-source",
                "fixture",
                "--formation",
                "x",
                trace_dir=trace_dir,
                report_path=report_path,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            mission_trace_exists = (trace_dir / "mission.json").is_file()

        self.assertEqual(report["outcome"], "GO")
        self.assertEqual(report["mission_choice"]["source"], "fixture")
        self.assertEqual(report["mission_choice"]["choice"]["mission"], "surround_hazard")
        self.assertEqual(report["mission_choice"]["choice"]["risk"], "cautious")
        self.assertEqual(len(report["mission_choice"]["trace_summary_sha"]), 64)
        self.assertTrue(report["pass_conditions"]["mission_choice_validated"])
        self.assertTrue(report["pass_conditions"]["mission_trace_replay_deterministic"])
        self.assertTrue(mission_trace_exists)

    def test_fixture_bounded_hold_position_keeps_agents_at_starts(self) -> None:
        with _temp_run_paths("fixture_hold_mission") as (trace_dir, report_path):
            result = _run_gate(
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
                trace_dir=trace_dir,
                report_path=report_path,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            agent_traces = {
                agent_id: trace_from_dict(
                    json.loads((trace_dir / "agents" / f"{agent_id}.json").read_text(encoding="utf-8"))
                )
                for agent_id in report["assigned_goals"]
            }

        self.assertEqual(report["outcome"], "GO")
        self.assertEqual(report["mission_choice"]["choice"], {"mission": "hold_position", "risk": "balanced"})
        self.assertIsNone(report["formation_plan"])
        self.assertEqual(report["ticks"], 1)
        self.assertEqual(report["sim_report"]["hold_count"], 4)
        self.assertTrue(report["pass_conditions"]["mission_choice_validated"])
        for agent_id, goal in report["assigned_goals"].items():
            command = agent_traces[agent_id].events[0].command
            self.assertEqual(goal, {"x": command["from_x"], "y": command["from_y"]})
            self.assertEqual(agent_traces[agent_id].events[0].decision, "HOLD")

    def test_degraded_mode_writes_hold_traces_without_model(self) -> None:
        with _temp_run_paths("degraded") as (trace_dir, report_path):
            result = _run_gate("--mode", "degraded", trace_dir=trace_dir, report_path=report_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            states = _load_world_model_timeline(trace_dir)

        self.assertEqual(report["outcome"], "DEGRADED")
        self.assertIsNone(report["hazard"])
        self.assertTrue(report["pass_conditions"]["degraded_hold_selected"])
        self.assertTrue(report["pass_conditions"]["world_model_timeline_replay_deterministic"])
        self.assertEqual(report["world_model"]["state_count"], 1)
        self.assertEqual(report["sim_report"]["hold_count"], 4)
        self.assertEqual(report["sim_report"]["same_cell_collision_count"], 0)
        self.assertEqual(states[0].observations[0].source, "degraded")
        self.assertEqual(states[0].hazards, ())

    def test_dashscope_missing_key_can_degrade_to_hold(self) -> None:
        with _temp_run_paths("missing_key") as (trace_dir, report_path):
            result = _run_gate(
                "--mode",
                "dashscope",
                "--degraded-on-error",
                trace_dir=trace_dir,
                report_path=report_path,
                env={},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(report["outcome"], "DEGRADED")
        self.assertIn("ALIBABA_API_KEY", report["model_error"])
        self.assertTrue(report["pass_conditions"]["degraded_hold_selected"])

    def test_dashscope_missing_key_fails_closed_without_degrade_flag(self) -> None:
        with _temp_run_paths("missing_key_fail") as (trace_dir, report_path):
            result = _run_gate("--mode", "dashscope", trace_dir=trace_dir, report_path=report_path, env={})

        self.assertEqual(result.returncode, 3)
        self.assertIn("ALIBABA_API_KEY", result.stderr)


def _run_gate(
    *args: str,
    trace_dir: Path,
    report_path: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.run_hazard_formation_gate",
            "--image",
            "fixtures/hazard_marker.ppm",
            "--trace-dir",
            str(trace_dir),
            "--report-out",
            str(report_path),
            *args,
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _load_world_model_timeline(trace_dir: Path):
    timeline_path = trace_dir / "world_model_timeline.jsonl"
    return [
        world_model_from_dict(json.loads(line))
        for line in timeline_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class _temp_run_paths:
    def __init__(self, name: str) -> None:
        self.name = name

    def __enter__(self) -> tuple[Path, Path]:
        (ROOT / "runs").mkdir(parents=True, exist_ok=True)
        self._tmp = TemporaryDirectory(dir=ROOT / "runs")
        base = Path(self._tmp.name)
        return base / self.name, base / f"{self.name}_report.json"

    def __exit__(self, *args: object) -> None:
        self._tmp.cleanup()
