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
                    "--confirm-operator-attestation",
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
        self.assertEqual(report["issue"], "https://github.com/omarespejel/accountable-swarm/issues/103")
        self.assertEqual(report["umbrella_issue"], "https://github.com/omarespejel/accountable-swarm/issues/95")
        self.assertEqual(report["trace_summary_sha"], summary_sha)
        self.assertEqual(report["operator_attested"], "true")
        self.assertTrue(report["pass_conditions"]["operator_attestation_persisted"])
        self.assertEqual(rows[0]["trial_id"], "trial-001")
        self.assertEqual(rows[0]["trace_summary_sha"], summary_sha)
        self.assertEqual(rows[0]["operator_attested"], "true")
        self.assertEqual(rows[0]["outcome"], "success")
        self.assertEqual(rows[0]["policy"], "act")
        action_commands = [
            event["command"]
            for event in trace_payload["events"]
            if event["command"].get("type") == "physical_action_intent"
        ]
        self.assertEqual(action_commands[0]["control_label"], "AUTONOMOUS")
        self.assertIs(action_commands[0]["motion_executed"], True)
        self.assertIs(action_commands[0]["operator_attested"], True)

    def test_missing_operator_attestation_is_rejected_before_write(self) -> None:
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

            self.assertEqual(result.returncode, 2)
            self.assertIn("--confirm-operator-attestation", result.stderr)
            self.assertFalse(trace_dir.exists())
            self.assertFalse(csv_out.exists())
            self.assertFalse(report_out.exists())

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
                "--motion-executed",
                "true",
                "--confirm-operator-attestation",
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
                "--motion-executed",
                "true",
                "--confirm-operator-attestation",
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

    def test_cloud_hold_requires_degraded_hold_semantics(self) -> None:
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
                    "cloud_hold",
                    "--confirm-operator-attestation",
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

            self.assertEqual(result.returncode, 2)
            self.assertIn("outcome=cloud_hold requires cloud_mode=degraded", result.stderr)
            self.assertFalse(trace_dir.exists())
            self.assertFalse(csv_out.exists())

    def test_hold_decision_rejects_executed_motion(self) -> None:
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
                    "unsafe_hold",
                    "--gate-decision",
                    "HOLD",
                    "--risk-level",
                    "high",
                    "--motion-executed",
                    "true",
                    "--confirm-operator-attestation",
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

            self.assertEqual(result.returncode, 2)
            self.assertIn("gate_decision=HOLD requires motion_executed=false", result.stderr)
            self.assertFalse(trace_dir.exists())
            self.assertFalse(csv_out.exists())

    def test_success_requires_executed_motion_before_write(self) -> None:
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
                    "--confirm-operator-attestation",
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

            self.assertEqual(result.returncode, 2)
            self.assertIn("outcome=success requires motion_executed=true", result.stderr)
            self.assertFalse(trace_dir.exists())
            self.assertFalse(csv_out.exists())
            self.assertFalse(report_out.exists())

    def test_existing_report_path_rejects_before_trace_or_csv_write(self) -> None:
        base = ROOT / "runs" / "physical"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            trace_dir = Path(tmpdir) / "traces"
            csv_out = Path(tmpdir) / "trial_results.csv"
            report_out = Path(tmpdir) / "reports" / "trial-001.json"
            report_out.parent.mkdir(parents=True, exist_ok=True)
            report_out.write_text("existing-report\n", encoding="utf-8")
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
                    "--confirm-operator-attestation",
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

            self.assertEqual(result.returncode, 2)
            self.assertIn("report already exists", result.stderr)
            self.assertFalse(trace_dir.exists())
            self.assertFalse(csv_out.exists())
            self.assertEqual(report_out.read_text(encoding="utf-8"), "existing-report\n")

    def test_explicit_reference_ids_replace_default_and_validate_relation(self) -> None:
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
                    "--confirm-operator-attestation",
                    "--relation",
                    "between",
                    "--reference-mark-id",
                    "C",
                    "--reference-mark-id",
                    "D",
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
            trace_payload = json.loads((trace_dir / "trial-001.json").read_text(encoding="utf-8"))
            selector_commands = [
                event["command"]
                for event in trace_payload["events"]
                if event["command"].get("type") == "qwenguard_select_target"
            ]

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(selector_commands[0]["reference_mark_ids"], ["C", "D"])

    def test_between_relation_requires_two_distinct_references(self) -> None:
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
                    "--motion-executed",
                    "true",
                    "--confirm-operator-attestation",
                    "--relation",
                    "between",
                    "--reference-mark-id",
                    "C",
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
            self.assertIn("relation between requires exactly two distinct reference marks", result.stderr)
            self.assertFalse(trace_dir.exists())
            self.assertFalse(csv_out.exists())

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
                    "--confirm-operator-attestation",
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

    def test_data_url_notes_are_rejected_before_write(self) -> None:
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
                    "--motion-executed",
                    "true",
                    "--notes",
                    "data:image/png;base64," + ("A" * 100),
                    "--confirm-operator-attestation",
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
            self.assertIn("raw-frame-like material", result.stderr)
            self.assertFalse(trace_dir.exists())
            self.assertFalse(csv_out.exists())
