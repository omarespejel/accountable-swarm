import json
from unittest import TestCase

from accountable_swarm.qwenguard.evaluator import degraded_evaluation, parse_evaluator_response


class QwenGuardEvaluatorTests(TestCase):
    def test_parses_success(self) -> None:
        result = parse_evaluator_response(
            json.dumps(
                {
                    "outcome": "success",
                    "failure_type": "none",
                    "confidence_milli": 880,
                    "evidence": "The cube is in the bin.",
                }
            )
        )

        self.assertEqual(result.outcome, "success")
        self.assertEqual(result.to_command()["failure_type"], "none")
        self.assertNotIn("The cube is in the bin", json.dumps(result.to_command()))
        self.assertIn("evidence_sha256", result.to_command())

    def test_rejects_success_with_failure_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "successful outcome"):
            parse_evaluator_response(
                json.dumps(
                    {
                        "outcome": "success",
                        "failure_type": "not_in_bin",
                        "confidence_milli": 880,
                        "evidence": "Contradictory.",
                    }
                )
            )

    def test_rejects_non_success_without_failure_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-success outcome"):
            parse_evaluator_response(
                json.dumps(
                    {
                        "outcome": "failure",
                        "failure_type": "none",
                        "confidence_milli": 880,
                        "evidence": "Contradictory.",
                    }
                )
            )

    def test_degraded_evaluation_uses_cloud_unavailable(self) -> None:
        result = degraded_evaluation("missing key")

        self.assertEqual(result.outcome, "uncertain")
        self.assertEqual(result.failure_type, "cloud_unavailable")
        self.assertEqual(result.confidence_milli, 0)

    def test_rejects_unbounded_evidence(self) -> None:
        with self.assertRaisesRegex(ValueError, "512 characters"):
            parse_evaluator_response(
                json.dumps(
                    {
                        "outcome": "failure",
                        "failure_type": "not_in_bin",
                        "confidence_milli": 880,
                        "evidence": "x" * 513,
                    }
                )
            )

    def test_rejects_non_object_json(self) -> None:
        with self.assertRaisesRegex(ValueError, "no valid JSON object"):
            parse_evaluator_response("[]")

    def test_rejects_missing_required_field(self) -> None:
        with self.assertRaisesRegex(ValueError, "failure_type"):
            parse_evaluator_response(
                json.dumps(
                    {
                        "outcome": "success",
                        "confidence_milli": 880,
                        "evidence": "The cube is in the bin.",
                    }
                )
            )

    def test_rejects_unexpected_key(self) -> None:
        with self.assertRaisesRegex(ValueError, "unexpected keys"):
            parse_evaluator_response(
                json.dumps(
                    {
                        "outcome": "success",
                        "failure_type": "none",
                        "confidence_milli": 880,
                        "evidence": "The cube is in the bin.",
                        "motor_command": "move",
                    }
                )
            )
