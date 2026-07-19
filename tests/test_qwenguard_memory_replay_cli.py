from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest import TestCase

from accountable_swarm.qwenguard.memory import verify_qwenguard_memory_replay
from accountable_swarm.trace.models import trace_from_dict


ROOT = Path(__file__).resolve().parents[1]
TEST_RUN_ROOT = ROOT / "runs" / "test-qwenguard-memory"


class QwenGuardMemoryReplayCliTests(TestCase):
    def setUp(self) -> None:
        TEST_RUN_ROOT.mkdir(parents=True, exist_ok=True)
        self.out_dir = Path(tempfile.mkdtemp(prefix="case-", dir=TEST_RUN_ROOT))
        self.trace_path = self.out_dir / "trace.json"
        self.report_path = self.out_dir / "report.json"

    def tearDown(self) -> None:
        shutil.rmtree(self.out_dir, ignore_errors=True)
        try:
            TEST_RUN_ROOT.rmdir()
        except OSError:
            pass

    def test_run_and_verify_clis_rebuild_exact_artifacts(self) -> None:
        run = _run_cli(
            "scripts.run_qwenguard_memory_replay",
            "--trace-out",
            str(self.trace_path.relative_to(ROOT)),
            "--report-out",
            str(self.report_path.relative_to(ROOT)),
        )
        self.assertEqual(run.returncode, 0, run.stderr)

        trace = trace_from_dict(json.loads(self.trace_path.read_text(encoding="utf-8")))
        report = json.loads(self.report_path.read_text(encoding="utf-8"))
        self.assertEqual(verify_qwenguard_memory_replay(trace), report["trace_summary_sha"])
        self.assertEqual(report["policy_sequence"], ["VERIFIED", "PROVISIONAL", "HOLD", "REVERIFY"])
        self.assertEqual(
            report["memory_state_sequence"],
            ["VERIFIED", "PROVISIONAL", "PROVISIONAL", "PROVISIONAL"],
        )
        self.assertFalse(report["motion_executed"])

        verify = _run_cli(
            "scripts.verify_qwenguard_memory_replay",
            "--trace",
            str(self.trace_path.relative_to(ROOT)),
            "--report",
            str(self.report_path.relative_to(ROOT)),
        )
        self.assertEqual(verify.returncode, 0, verify.stderr)
        self.assertIn("trace_summary_sha", verify.stdout)

    def test_run_rejects_absolute_and_parent_paths(self) -> None:
        absolute = _run_cli(
            "scripts.run_qwenguard_memory_replay",
            "--trace-out",
            str(self.trace_path),
            "--report-out",
            str(self.report_path.relative_to(ROOT)),
        )
        self.assertEqual(absolute.returncode, 2)
        self.assertIn("repository-relative", absolute.stderr)

        traversal = _run_cli(
            "scripts.run_qwenguard_memory_replay",
            "--trace-out",
            "../escape.json",
            "--report-out",
            str(self.report_path.relative_to(ROOT)),
        )
        self.assertEqual(traversal.returncode, 2)
        self.assertIn("escapes repository root", traversal.stderr)

        tracked = _run_cli(
            "scripts.run_qwenguard_memory_replay",
            "--trace-out",
            "README.md",
            "--report-out",
            str(self.report_path.relative_to(ROOT)),
        )
        self.assertEqual(tracked.returncode, 2)
        self.assertIn("must stay under runs/", tracked.stderr)

    def test_run_rejects_symlink_and_directory_outputs(self) -> None:
        target = self.out_dir / "target.json"
        target.write_text("{}", encoding="utf-8")
        link = self.out_dir / "trace-link.json"
        link.symlink_to(target)
        symlink = _run_cli(
            "scripts.run_qwenguard_memory_replay",
            "--trace-out",
            str(link.relative_to(ROOT)),
            "--report-out",
            str(self.report_path.relative_to(ROOT)),
        )
        self.assertEqual(symlink.returncode, 2)
        self.assertIn("must not use symlinks", symlink.stderr)

        directory = self.out_dir / "trace-dir"
        directory.mkdir()
        is_directory = _run_cli(
            "scripts.run_qwenguard_memory_replay",
            "--trace-out",
            str(directory.relative_to(ROOT)),
            "--report-out",
            str(self.report_path.relative_to(ROOT)),
        )
        self.assertEqual(is_directory.returncode, 2)
        self.assertIn("regular file", is_directory.stderr)

    def test_verifier_rejects_tampered_report(self) -> None:
        run = _run_cli(
            "scripts.run_qwenguard_memory_replay",
            "--trace-out",
            str(self.trace_path.relative_to(ROOT)),
            "--report-out",
            str(self.report_path.relative_to(ROOT)),
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        report = json.loads(self.report_path.read_text(encoding="utf-8"))
        report["motion_executed"] = True
        self.report_path.write_text(json.dumps(report), encoding="utf-8")

        verify = _run_cli(
            "scripts.verify_qwenguard_memory_replay",
            "--trace",
            str(self.trace_path.relative_to(ROOT)),
            "--report",
            str(self.report_path.relative_to(ROOT)),
        )
        self.assertEqual(verify.returncode, 2)
        self.assertIn("report does not match", verify.stderr)

    def test_verifier_rejects_duplicate_report_keys(self) -> None:
        run = _run_cli(
            "scripts.run_qwenguard_memory_replay",
            "--trace-out",
            str(self.trace_path.relative_to(ROOT)),
            "--report-out",
            str(self.report_path.relative_to(ROOT)),
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        text = self.report_path.read_text(encoding="utf-8")
        self.report_path.write_text(text.replace('{"event_receipts"', '{"outcome":"GO","event_receipts"'), encoding="utf-8")

        verify = _run_cli(
            "scripts.verify_qwenguard_memory_replay",
            "--trace",
            str(self.trace_path.relative_to(ROOT)),
            "--report",
            str(self.report_path.relative_to(ROOT)),
        )
        self.assertEqual(verify.returncode, 2)
        self.assertIn("duplicate JSON key: outcome", verify.stderr)


def _run_cli(module: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", module, *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
