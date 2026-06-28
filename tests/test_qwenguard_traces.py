import json
from unittest import TestCase

from accountable_swarm.qwenguard.evaluator import EvaluationResult
from accountable_swarm.qwenguard.outcome_gate import GateDecision
from accountable_swarm.qwenguard.selector import fixture_cube_candidates, parse_selector_response
from accountable_swarm.qwenguard.traces import build_qwenguard_trace
from accountable_swarm.trace.models import verify_trace


class QwenGuardTraceTests(TestCase):
    def test_retry_gate_is_preserved_in_action_event(self) -> None:
        selector = parse_selector_response(
            json.dumps(
                {
                    "target_mark_id": "A",
                    "relation": "left_of",
                    "reference_mark_ids": ["B"],
                    "confidence_milli": 910,
                    "evidence": "A is left of B.",
                }
            ),
            candidates=fixture_cube_candidates(),
        )
        trace = build_qwenguard_trace(
            run_id="retry-run",
            source="image://fixture.ppm",
            image_width=4,
            image_height=4,
            model="fixture",
            selector=selector,
            gate=GateDecision(
                gate_decision="RETRY",
                candidate_action="retry_pick_place",
                predicted_success_milli=700,
                risk_level="medium",
                reasons=("bounded_retry_available",),
            ),
            evaluation=EvaluationResult(
                outcome="uncertain",
                failure_type="uncertain_view",
                confidence_milli=500,
                evidence="Retry fixture was not physically executed.",
            ),
            mode="fixture",
        )

        self.assertEqual(verify_trace(trace), trace.summary_sha)
        self.assertEqual(trace.events[2].decision, "RETRY")
        self.assertEqual(trace.events[2].mode, "edge")
        self.assertEqual(trace.events[2].command["requested_action"], "retry_pick_place")
