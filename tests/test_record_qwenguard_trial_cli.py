from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase

from accountable_swarm.trace.models import trace_from_dict, verify_trace


ROOT = Path(__file__).resolve().parents[1]


class RecordQwenGuardTrialCliTests(TestCase):
    def test_record_success_writes_verified_trace_and_bound_csv_row(self) -> None:
        base = ROOT / "runs" / "physical"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            trace_dir = Path(tmpdir) / "traces"
            csv_out = Path(tmpdir) / "trial_results.csv"
            report_out = Path(tmpdir) / "reports" / "trial-001.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.record_qwenguard_trial",
                    "--trial-id",
                    "trial-001",
                    "--outcome",
                    "success",
                    "--motion-executed",
                    "true",
                    "--control-label",
                    "AUTONOMOUS",
                    "--trace-dir",
                    str(trace_dir.relative_to(ROOT)),
                    "--csv-out",
                    str(csv_out.relative_to(ROOT)),
                    "--report-out",
                    str(report_out.relative_to(ROOT)),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            trace_path = trace_dir / "trial-001.json"
            trace_payload = json.loads(trace_path.read_text(encoding="utf-8"))
            summary_sha = verify_trace(trace_from_dict(trace_payload))
            report = json.loads(report_out.read_text(encoding="utf-8"))
            with csv_out.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(report["schema_version"], "qwenguard-trial-record-report.v1")
        self.assertEqual(report["outcome"], "GO")
        self.assertEqual(report["trace_summary_sha"], summary_sha)
        self.assertEqual(rows[0]["trial_id"], "trial-001")
        self.assertEqual(rows[0]["trace_summary_sha"], summary_sha)
        self.assertEqual(rows[0]["outcome"], "success")
        self.assertEqual(rows[0]["policy"], "act")
        action_commands = [
            event["command"]
            for event in trace_payload["events"]
            if event["command"].get("type") == "physical_action_intent"
        ]
        self.assertEqual(action_commands[0]["control_label"], "AUTONOMOUS")
        self.assertIs(action_commands[0]["motion_executed"], True)

    def test_duplicate_trial_id_is_rejected_without_overwrite(self) -> None:
        base = ROOT / "runs" / "physical"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            trace_dir = Path(tmpdir) / "traces"
            csv_out = Path(tmpdir) / "trial_results.csv"
            report_out = Path(tmpdir) / "reports" / "trial-001.json"
            common = [
                sys.executable,
                "-m",
                "scripts.record_qwenguard_trial",
                "--trial-id",
                "trial-001",
                "--outcome",
                "success",
                "--trace-dir",
                str(trace_dir.relative_to(ROOT)),
                "--csv-out",
                str(csv_out.relative_to(ROOT)),
                "--report-out",
                str(report_out.relative_to(ROOT)),
            ]
            first = subprocess.run(common, cwd=ROOT, text=True, capture_output=True, check=False)
            second = subprocess.run(common, cwd=ROOT, text=True, capture_output=True, check=False)

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 2)
        self.assertIn("trace already exists", second.stderr)

    def test_overwrite_replaces_existing_csv_row(self) -> None:
        base = ROOT / "runs" / "physical"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            trace_dir = Path(tmpdir) / "traces"
            csv_out = Path(tmpdir) / "trial_results.csv"
            report_out = Path(tmpdir) / "reports" / "trial-001.json"
            base_cmd = [
                sys.executable,
                "-m",
                "scripts.record_qwenguard_trial",
                "--trial-id",
                "trial-001",
                "--trace-dir",
                str(trace_dir.relative_to(ROOT)),
                "--csv-out",
                str(csv_out.relative_to(ROOT)),
                "--report-out",
                str(report_out.relative_to(ROOT)),
            ]
            first = subprocess.run(
                [*base_cmd, "--outcome", "success"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            second = subprocess.run(
                [*base_cmd, "--outcome", "missed_grasp", "--overwrite"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            with csv_out.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["outcome"], "missed_grasp")
        self.assertEqual(rows[0]["qwen_eval_label"], "failure:missed_grasp")

    def test_secret_like_notes_are_rejected_before_write(self) -> None:
        base = ROOT / "runs" / "physical"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            trace_dir = Path(tmpdir) / "traces"
            csv_out = Path(tmpdir) / "trial_results.csv"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.record_qwenguard_trial",
                    "--trial-id",
                    "trial-001",
                    "--outcome",
                    "success",
                    "--notes",
                    "sk-testsecret01234567890123456789",
                    "--trace-dir",
                    str(trace_dir.relative_to(ROOT)),
                    "--csv-out",
                    str(csv_out.relative_to(ROOT)),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("secret-like material", result.stderr)
            self.assertFalse(trace_dir.exists())
            self.assertFalse(csv_out.exists())
