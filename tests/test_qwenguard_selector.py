import json
from unittest import TestCase

from accountable_swarm.qwenguard.selector import CandidateMark, fixture_cube_candidates, parse_selector_response


class QwenGuardSelectorTests(TestCase):
    def test_parses_marked_relational_selection(self) -> None:
        result = parse_selector_response(
            json.dumps(
                {
                    "target_mark_id": "A",
                    "target_label": "red cube left of green cube",
                    "relation": "left_of",
                    "reference_mark_ids": ["B"],
                    "confidence_milli": 900,
                    "evidence": "A is left of B.",
                }
            ),
            candidates=fixture_cube_candidates(),
        )

        self.assertEqual(result.target_mark_id, "A")
        self.assertEqual(result.reference_mark_ids, ("B",))
        self.assertEqual(result.to_command()["confidence_milli"], 900)
        self.assertNotIn("A is left", json.dumps(result.to_command()))
        self.assertIn("evidence_sha256", result.to_command())

    def test_rejects_unknown_target_mark(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown target_mark_id"):
            parse_selector_response(
                json.dumps(
                    {
                        "target_mark_id": "Z",
                        "relation": "left_of",
                        "reference_mark_ids": ["B"],
                        "confidence_milli": 900,
                        "evidence": "Z is left of B.",
                    }
                ),
                candidates=fixture_cube_candidates(),
            )

    def test_rejects_relation_without_reference(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires at least one reference"):
            parse_selector_response(
                json.dumps(
                    {
                        "target_mark_id": "A",
                        "relation": "left_of",
                        "confidence_milli": 900,
                        "evidence": "A is left.",
                    }
                ),
                candidates=fixture_cube_candidates(),
            )

    def test_rejects_unsupported_relation(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported relation"):
            parse_selector_response(
                json.dumps(
                    {
                        "target_mark_id": "A",
                        "relation": "fly_to",
                        "reference_mark_ids": ["B"],
                        "confidence_milli": 900,
                        "evidence": "A is selected.",
                    }
                ),
                candidates=fixture_cube_candidates(),
            )

    def test_rejects_target_label_that_disagrees_with_candidate(self) -> None:
        with self.assertRaisesRegex(ValueError, "target_label"):
            parse_selector_response(
                json.dumps(
                    {
                        "target_mark_id": "A",
                        "target_label": "green cube",
                        "relation": "left_of",
                        "reference_mark_ids": ["B"],
                        "confidence_milli": 900,
                        "evidence": "A is left of B.",
                    }
                ),
                candidates=fixture_cube_candidates(),
            )

    def test_rejects_between_with_wrong_reference_count(self) -> None:
        with self.assertRaisesRegex(ValueError, "exactly two distinct"):
            parse_selector_response(
                json.dumps(
                    {
                        "target_mark_id": "A",
                        "relation": "between",
                        "reference_mark_ids": ["B"],
                        "confidence_milli": 900,
                        "evidence": "A is between B.",
                    }
                ),
                candidates=fixture_cube_candidates(),
            )

    def test_rejects_float_confidence(self) -> None:
        with self.assertRaisesRegex(ValueError, "confidence_milli must be an integer"):
            parse_selector_response(
                json.dumps(
                    {
                        "target_mark_id": "A",
                        "relation": "left_of",
                        "reference_mark_ids": ["B"],
                        "confidence_milli": 0.9,
                        "evidence": "A is left of B.",
                    }
                ),
                candidates=fixture_cube_candidates(),
            )

    def test_rejects_bool_bbox_coordinates(self) -> None:
        with self.assertRaisesRegex(TypeError, "coordinates must be integers"):
            CandidateMark(
                mark_id="A",
                label="bad cube",
                bbox_2d_norm_1000=(True, 0, 100, 100),  # type: ignore[arg-type]
            )

    def test_rejects_unbounded_evidence(self) -> None:
        with self.assertRaisesRegex(ValueError, "512 characters"):
            parse_selector_response(
                json.dumps(
                    {
                        "target_mark_id": "A",
                        "relation": "left_of",
                        "reference_mark_ids": ["B"],
                        "confidence_milli": 900,
                        "evidence": "x" * 513,
                    }
                ),
                candidates=fixture_cube_candidates(),
            )
