from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase

from accountable_swarm.swarm import scenario_names


ROOT = Path(__file__).resolve().parents[1]


class SwarmDemoBundleCliTests(TestCase):
    def test_bundle_generates_deterministic_reviewed_scenario_artifacts(self) -> None:
        with TemporaryDirectory() as first_tmp, TemporaryDirectory() as second_tmp:
            first_dir = Path(first_tmp) / "bundle"
            second_dir = Path(second_tmp) / "bundle"

            first = _run_bundle(first_dir)
            second = _run_bundle(second_dir)

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn("outcome GO", first.stdout)
            self.assertEqual(
                (first_dir / "index.html").read_text(encoding="utf-8"),
                (second_dir / "index.html").read_text(encoding="utf-8"),
            )
            first_summary = json.loads((first_dir / "summary.json").read_text(encoding="utf-8"))
            second_summary = json.loads((second_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(first_summary, second_summary)
            self.assertEqual(first_summary["schema_version"], "swarm-demo-bundle-report.v1")
            self.assertEqual(first_summary["outcome"], "GO")
            self.assertEqual(first_summary["scenario_count"], len(scenario_names()))
            self.assertEqual(first_summary["agent_count"], 4)
            self.assertEqual(first_summary["ticks"], 16)
            self.assertTrue(all(first_summary["pass_conditions"].values()))
            self.assertEqual(
                [case["scenario"] for case in first_summary["scenarios"]],
                list(scenario_names()),
            )

            index_html = (first_dir / "index.html").read_text(encoding="utf-8")
            self.assertNotIn(first_tmp, index_html)
            self.assertNotIn(first_tmp, json.dumps(first_summary, sort_keys=True))
            self.assertIn("Accountable Swarm Demo Bundle", index_html)
            self.assertIn("scenarios/center-block/replay.html", index_html)
            for case in first_summary["scenarios"]:
                self.assertEqual(case["sim_report"]["outcome"], "GO")
                self.assertEqual(case["render_summary"]["outcome"], "GO")
                self.assertTrue(all(case["pass_conditions"].values()))
                self.assertRegex(case["render_summary"]["html_sha256"], r"^[0-9a-f]{64}$")
                self.assertEqual(case["sim_report"]["same_cell_collision_count"], 0)
                self.assertEqual(case["sim_report"]["swap_collision_count"], 0)
                self.assertEqual(case["sim_report"]["obstacle_occupancy_violation_count"], 0)
                self.assertTrue((first_dir / case["files"]["sim_report"]).exists())
                self.assertTrue((first_dir / case["files"]["replay_html"]).exists())
                self.assertTrue((first_dir / case["files"]["replay_summary"]).exists())
                for trace_path in case["files"]["traces"].values():
                    self.assertTrue((first_dir / trace_path).exists())

    def test_bundle_surfaces_short_run_as_narrow_claim(self) -> None:
        with TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "bundle"

            result = _run_bundle(out_dir, "--scenario", "center-block", "--ticks", "1")

            self.assertEqual(result.returncode, 4)
            self.assertIn("outcome NARROW_CLAIM", result.stdout)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["outcome"], "NARROW_CLAIM")
            self.assertEqual(summary["scenario_count"], 1)
            self.assertFalse(summary["pass_conditions"]["all_reviewed_scenarios_included"])
            self.assertFalse(summary["pass_conditions"]["every_sim_report_go"])
            self.assertEqual(summary["scenarios"][0]["sim_report"]["outcome"], "NARROW_CLAIM")
            self.assertTrue((out_dir / "index.html").exists())


def _run_bundle(out_dir: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "scripts/build_swarm_demo_bundle.py",
            "--out-dir",
            str(out_dir),
            *extra_args,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
