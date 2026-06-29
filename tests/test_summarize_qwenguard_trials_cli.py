from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase

from accountable_swarm.qwenguard.trial import trial_csv_header
from scripts.summarize_qwenguard_trials import _contains_secret_like_material


ROOT = Path(__file__).resolve().parents[1]


class SummarizeQwenGuardTrialsCliTests(TestCase):
    def test_summarizes_verified_trials_with_integer_rates(self) -> None:
        base = ROOT / "runs" / "physical"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            root = Path(tmpdir)
            trace_dir = root / "traces"
            csv_out = root / "trial_results.csv"
            summary_out = root / "trial_summary.json"
            _record_trial(
                trial_id="trial-success",
                outcome="success",
                trace_dir=trace_dir,
                csv_out=csv_out,
                extra=["--motion-executed", "true", "--control-label", "AUTONOMOUS"],
            )
            _record_trial(
                trial_id="trial-missed",
                outcome="missed_grasp",
                trace_dir=trace_dir,
                csv_out=csv_out,
                extra=["--motion-executed", "true", "--control-label", "AUTONOMOUS"],
            )
            _record_trial(
                trial_id="trial-cloud-hold",
                outcome="cloud_hold",
                trace_dir=trace_dir,
                csv_out=csv_out,
                extra=[
                    "--cloud-mode",
                    "degraded",
                    "--gate-decision",
                    "HOLD",
                    "--predicted-success-milli",
                    "0",
                    "--risk-level",
                    "high",
                ],
            )
            result = _run_summary(csv_out=csv_out, trace_dir=trace_dir, out=summary_out)
            report = json.loads(summary_out.read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["schema_version"], "qwenguard-trial-summary.v1")
        self.assertEqual(report["outcome"], "GO")
        self.assertEqual(report["trial_readiness"], "READY")
        self.assertEqual(report["aggregate"]["total_trials"], 3)
        self.assertEqual(report["aggregate"]["attempted_trials"], 2)
        self.assertEqual(report["aggregate"]["success_count"], 1)
        self.assertEqual(report["aggregate"]["failure_count"], 2)
        self.assertEqual(report["aggregate"]["no_motion_count"], 1)
        self.assertEqual(report["aggregate"]["cloud_hold_count"], 1)
        self.assertEqual(report["aggregate"]["success_rate_all_trials_milli"], 333)
        self.assertEqual(report["aggregate"]["success_rate_attempted_milli"], 500)
        self.assertEqual(report["aggregate"]["failure_taxonomy_counts"]["missed_grasp"], 1)
        self.assertEqual(report["aggregate"]["failure_taxonomy_counts"]["cloud_hold"], 1)
        self.assertEqual(len(report["trial_bindings"]), 3)
        self.assertTrue(all(binding["verified"] for binding in report["trial_bindings"]))
        self.assertNotIn(".333", json.dumps(report, sort_keys=True))

    def test_missing_trials_remain_narrow_claim_with_allow_flag(self) -> None:
        base = ROOT / "runs" / "physical"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            root = Path(tmpdir)
            out = root / "trial_summary.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.summarize_qwenguard_trials",
                    "--trial-csv",
                    str((root / "missing.csv").relative_to(ROOT)),
                    "--trial-trace-dir",
                    str((root / "missing_traces").relative_to(ROOT)),
                    "--out",
                    str(out.relative_to(ROOT)),
                    "--allow-narrow-claim",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            report = json.loads(out.read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["outcome"], "NARROW_CLAIM")
        self.assertEqual(report["trial_readiness"], "NARROW_CLAIM")
        self.assertFalse(report["checks"]["trial_csv_present"])
        self.assertFalse(report["checks"]["trial_trace_dir_present"])
        self.assertEqual(report["aggregate"]["total_trials"], 0)

    def test_missing_trials_exit_nonzero_without_allow_flag(self) -> None:
        base = ROOT / "runs" / "physical"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            root = Path(tmpdir)
            out = root / "trial_summary.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.summarize_qwenguard_trials",
                    "--trial-csv",
                    str((root / "missing.csv").relative_to(ROOT)),
                    "--out",
                    str(out.relative_to(ROOT)),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            report = json.loads(out.read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 4)
        self.assertEqual(report["outcome"], "NARROW_CLAIM")

    def test_trace_summary_mismatch_is_narrow_claim(self) -> None:
        base = ROOT / "runs" / "physical"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            root = Path(tmpdir)
            trace_dir = root / "traces"
            csv_out = root / "trial_results.csv"
            summary_out = root / "trial_summary.json"
            _record_trial(
                trial_id="trial-success",
                outcome="success",
                trace_dir=trace_dir,
                csv_out=csv_out,
                extra=["--motion-executed", "true"],
            )
            rows = _read_csv(csv_out)
            rows[0]["trace_summary_sha"] = "f" * 64
            _write_csv(csv_out, rows)
            result = _run_summary(
                csv_out=csv_out,
                trace_dir=trace_dir,
                out=summary_out,
                allow_narrow=True,
            )
            report = json.loads(summary_out.read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["outcome"], "NARROW_CLAIM")
        self.assertFalse(report["checks"]["trial_bindings_verify"])
        self.assertIn("trace summary does not match CSV row", " ".join(report["invalid_reasons"]))

    def test_csv_outcome_tamper_with_valid_sha_is_narrow_claim(self) -> None:
        base = ROOT / "runs" / "physical"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            root = Path(tmpdir)
            trace_dir = root / "traces"
            csv_out = root / "trial_results.csv"
            summary_out = root / "trial_summary.json"
            _record_trial(
                trial_id="trial-success",
                outcome="success",
                trace_dir=trace_dir,
                csv_out=csv_out,
                extra=["--motion-executed", "true"],
            )
            rows = _read_csv(csv_out)
            rows[0]["outcome"] = "missed_grasp"
            _write_csv(csv_out, rows)
            result = _run_summary(
                csv_out=csv_out,
                trace_dir=trace_dir,
                out=summary_out,
                allow_narrow=True,
            )
            report = json.loads(summary_out.read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["outcome"], "NARROW_CLAIM")
        self.assertFalse(report["checks"]["trial_bindings_verify"])
        self.assertIn("outcome does not match trace evaluator metadata", " ".join(report["invalid_reasons"]))

    def test_mutated_trace_hash_chain_is_narrow_claim(self) -> None:
        base = ROOT / "runs" / "physical"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            root = Path(tmpdir)
            trace_dir = root / "traces"
            csv_out = root / "trial_results.csv"
            summary_out = root / "trial_summary.json"
            _record_trial(
                trial_id="trial-success",
                outcome="success",
                trace_dir=trace_dir,
                csv_out=csv_out,
                extra=["--motion-executed", "true"],
            )
            trace_path = trace_dir / "trial-success.json"
            payload = json.loads(trace_path.read_text(encoding="utf-8"))
            payload["events"][1]["command"]["risk_level"] = "high"
            trace_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
            result = _run_summary(
                csv_out=csv_out,
                trace_dir=trace_dir,
                out=summary_out,
                allow_narrow=True,
            )
            report = json.loads(summary_out.read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["outcome"], "NARROW_CLAIM")
        self.assertFalse(report["checks"]["trial_bindings_verify"])
        self.assertIn("trace verification failed", " ".join(report["invalid_reasons"]))

    def test_unsupported_trace_schema_is_narrow_claim(self) -> None:
        base = ROOT / "runs" / "physical"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            root = Path(tmpdir)
            trace_dir = root / "traces"
            csv_out = root / "trial_results.csv"
            summary_out = root / "trial_summary.json"
            _record_trial(
                trial_id="trial-success",
                outcome="success",
                trace_dir=trace_dir,
                csv_out=csv_out,
                extra=["--motion-executed", "true"],
            )
            trace_path = trace_dir / "trial-success.json"
            payload = json.loads(trace_path.read_text(encoding="utf-8"))
            payload["schema_version"] = "decisiontrace.v1"
            trace_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
            result = _run_summary(
                csv_out=csv_out,
                trace_dir=trace_dir,
                out=summary_out,
                allow_narrow=True,
            )
            report = json.loads(summary_out.read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["outcome"], "NARROW_CLAIM")
        self.assertFalse(report["checks"]["trial_bindings_verify"])
        self.assertIn("trace verification failed", " ".join(report["invalid_reasons"]))

    def test_trial_id_path_traversal_is_narrow_claim(self) -> None:
        base = ROOT / "runs" / "physical"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            root = Path(tmpdir)
            trace_dir = root / "traces"
            trace_dir.mkdir(parents=True)
            csv_out = root / "trial_results.csv"
            summary_out = root / "trial_summary.json"
            row = _base_trial_row()
            row["trial_id"] = "../escape"
            _write_csv(csv_out, [row])
            result = _run_summary(
                csv_out=csv_out,
                trace_dir=trace_dir,
                out=summary_out,
                allow_narrow=True,
            )
            report = json.loads(summary_out.read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["outcome"], "NARROW_CLAIM")
        self.assertFalse(report["checks"]["trial_bindings_verify"])
        self.assertIn("trial_id is not a simple trace filename identifier", " ".join(report["invalid_reasons"]))

    def test_secret_like_csv_material_is_narrow_claim(self) -> None:
        base = ROOT / "runs" / "physical"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            root = Path(tmpdir)
            trace_dir = root / "traces"
            csv_out = root / "trial_results.csv"
            summary_out = root / "trial_summary.json"
            _record_trial(
                trial_id="trial-success",
                outcome="success",
                trace_dir=trace_dir,
                csv_out=csv_out,
                extra=["--motion-executed", "true"],
            )
            rows = _read_csv(csv_out)
            rows[0]["notes"] = "operator note contains sk-testsecret01234567890123456789"
            _write_csv(csv_out, rows)
            result = _run_summary(
                csv_out=csv_out,
                trace_dir=trace_dir,
                out=summary_out,
                allow_narrow=True,
            )
            report = json.loads(summary_out.read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["outcome"], "NARROW_CLAIM")
        self.assertFalse(report["checks"]["secret_material_absent"])
        self.assertIn("secret-like", " ".join(report["invalid_reasons"]))

    def test_output_path_inside_trace_directory_is_rejected(self) -> None:
        base = ROOT / "runs" / "physical"
        base.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=base) as tmpdir:
            root = Path(tmpdir)
            trace_dir = root / "traces"
            csv_out = root / "trial_results.csv"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.summarize_qwenguard_trials",
                    "--trial-csv",
                    str(csv_out.relative_to(ROOT)),
                    "--trial-trace-dir",
                    str(trace_dir.relative_to(ROOT)),
                    "--out",
                    str((trace_dir / "trial_summary.json").relative_to(ROOT)),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("must not be written inside the trace directory", result.stderr)

    def test_redacted_bearer_token_is_not_flagged_as_secret(self) -> None:
        self.assertFalse(_contains_secret_like_material("Authorization: Bearer <redacted>"))
        self.assertFalse(_contains_secret_like_material('{"auth":"Authorization: Bearer <redacted>"}'))
        self.assertFalse(_contains_secret_like_material("Authorization: Bearer <redacted>\n"))

    def test_redacted_prefix_plus_token_is_still_flagged(self) -> None:
        self.assertTrue(_contains_secret_like_material("Authorization: Bearer <redacted>gho_abcdefghijklmnop"))
        self.assertTrue(_contains_secret_like_material('{"auth":"Authorization: Bearer <redacted>gho_abcdefghijklmnop"}'))


def _record_trial(*, trial_id: str, outcome: str, trace_dir: Path, csv_out: Path, extra: list[str]) -> None:
    report_out = trace_dir.parent / "reports" / f"{trial_id}.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.record_qwenguard_trial",
            "--trial-id",
            trial_id,
            "--outcome",
            outcome,
            "--trace-dir",
            str(trace_dir.relative_to(ROOT)),
            "--csv-out",
            str(csv_out.relative_to(ROOT)),
            "--report-out",
            str(report_out.relative_to(ROOT)),
            *extra,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr)


def _run_summary(*, csv_out: Path, trace_dir: Path, out: Path, allow_narrow: bool = False) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        "-m",
        "scripts.summarize_qwenguard_trials",
        "--trial-csv",
        str(csv_out.relative_to(ROOT)),
        "--trial-trace-dir",
        str(trace_dir.relative_to(ROOT)),
        "--out",
        str(out.relative_to(ROOT)),
    ]
    if allow_narrow:
        command.append("--allow-narrow-claim")
    return subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(trial_csv_header()))
        writer.writeheader()
        writer.writerows(rows)


def _base_trial_row() -> dict[str, str]:
    return {
        "trial_id": "trial-001",
        "task_instruction": "pick the red cube left of the green cube and place it in the bin",
        "object_layout_id": "qwenguard-cubes-layout-001",
        "selector_mode": "qwen",
        "gate_mode": "on",
        "policy": "act",
        "cloud_mode": "online",
        "outcome": "success",
        "operator_label": "success",
        "qwen_eval_label": "success",
        "trace_summary_sha": "a" * 64,
        "notes": "",
    }
