from unittest import TestCase

from accountable_swarm.qwenguard.trial import TrialRecord, trial_csv_header


class QwenGuardTrialTests(TestCase):
    def test_trial_record_validates(self) -> None:
        record = TrialRecord(
            trial_id="trial-001",
            task_instruction="pick the red cube left of the green cube",
            object_layout_id="layout-a",
            selector_mode="qwen",
            gate_mode="on",
            policy="act",
            cloud_mode="online",
            outcome="success",
            operator_label="success",
            qwen_eval_label="success",
            operator_attested="true",
            trace_summary_sha="a" * 64,
        )

        self.assertEqual(record.to_dict()["policy"], "act")
        self.assertEqual(record.to_dict()["operator_attested"], "true")
        self.assertIn("trial_id", trial_csv_header())
        self.assertIn("operator_attested", trial_csv_header())

    def test_trial_record_rejects_bad_sha(self) -> None:
        with self.assertRaisesRegex(ValueError, "trace_summary_sha"):
            TrialRecord(
                trial_id="trial-001",
                task_instruction="pick the red cube left of the green cube",
                object_layout_id="layout-a",
                selector_mode="qwen",
                gate_mode="on",
                policy="act",
                cloud_mode="online",
                outcome="success",
                operator_label="success",
                qwen_eval_label="success",
                operator_attested="true",
                trace_summary_sha="not-a-sha",
            )

    def test_trial_record_rejects_unattested_row(self) -> None:
        with self.assertRaisesRegex(ValueError, "operator_attested"):
            TrialRecord(
                trial_id="trial-001",
                task_instruction="pick the red cube left of the green cube",
                object_layout_id="layout-a",
                selector_mode="qwen",
                gate_mode="on",
                policy="act",
                cloud_mode="online",
                outcome="success",
                operator_label="success",
                qwen_eval_label="success",
                operator_attested="false",
                trace_summary_sha="a" * 64,
            )

    def test_trial_record_rejects_bad_selector_mode_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "selector_mode"):
            TrialRecord(
                trial_id="trial-001",
                task_instruction="pick the red cube left of the green cube",
                object_layout_id="layout-a",
                selector_mode=[],  # type: ignore[arg-type]
                gate_mode="on",
                policy="act",
                cloud_mode="online",
                outcome="success",
                operator_label="success",
                qwen_eval_label="success",
                operator_attested="true",
                trace_summary_sha="a" * 64,
            )

    def test_trial_record_rejects_unsupported_outcome(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported outcome"):
            TrialRecord(
                trial_id="trial-001",
                task_instruction="pick the red cube left of the green cube",
                object_layout_id="layout-a",
                selector_mode="qwen",
                gate_mode="on",
                policy="act",
                cloud_mode="online",
                outcome="magic",
                operator_label="success",
                qwen_eval_label="success",
                operator_attested="true",
                trace_summary_sha="a" * 64,
            )
