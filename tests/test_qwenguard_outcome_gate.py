import json
from unittest import TestCase

from accountable_swarm.physical.contract import PhysicalNodeSafety
from accountable_swarm.qwenguard.outcome_gate import OutcomeGateInput, evaluate_outcome_gate
from accountable_swarm.qwenguard.selector import fixture_cube_candidates, parse_selector_response


class QwenGuardOutcomeGateTests(TestCase):
    def test_allows_when_selector_policy_workspace_and_safety_pass(self) -> None:
        decision = evaluate_outcome_gate(
            OutcomeGateInput(
                selector=_selector(),
                safety=_safe_motion(),
                policy_available=True,
                cloud_available=True,
                workspace_ok=True,
            )
        )

        self.assertEqual(decision.gate_decision, "ALLOW")
        self.assertEqual(decision.candidate_action, "pick_place")

    def test_holds_when_cloud_unavailable(self) -> None:
        decision = evaluate_outcome_gate(
            OutcomeGateInput(
                selector=_selector(),
                safety=_safe_motion(),
                policy_available=True,
                cloud_available=False,
                workspace_ok=True,
            )
        )

        self.assertEqual(decision.gate_decision, "HOLD")
        self.assertIn("cloud_unavailable", decision.reasons)

    def test_default_physical_safety_holds(self) -> None:
        decision = evaluate_outcome_gate(
            OutcomeGateInput(
                selector=_selector(),
                safety=PhysicalNodeSafety(),
                policy_available=True,
                cloud_available=True,
                workspace_ok=True,
            )
        )

        self.assertEqual(decision.gate_decision, "HOLD")
        self.assertTrue(any(reason.startswith("safety_rejected:") for reason in decision.reasons))

    def test_holds_when_policy_missing(self) -> None:
        decision = evaluate_outcome_gate(
            OutcomeGateInput(
                selector=_selector(),
                safety=_safe_motion(),
                policy_available=False,
                cloud_available=True,
                workspace_ok=True,
            )
        )

        self.assertEqual(decision.gate_decision, "HOLD")
        self.assertIn("policy_unavailable", decision.reasons)

    def test_holds_when_confidence_below_threshold_even_if_above_old_allow_cutoff(self) -> None:
        decision = evaluate_outcome_gate(
            OutcomeGateInput(
                selector=_selector(confidence_milli=690),
                safety=_safe_motion(),
                policy_available=True,
                cloud_available=True,
                workspace_ok=True,
                min_confidence_milli=700,
            )
        )

        self.assertEqual(decision.gate_decision, "HOLD")
        self.assertIn("selector_confidence_below_threshold", decision.reasons)


def _selector(*, confidence_milli: int = 910):
    return parse_selector_response(
        json.dumps(
            {
                "target_mark_id": "A",
                "relation": "left_of",
                "reference_mark_ids": ["B"],
                "confidence_milli": confidence_milli,
                "evidence": "A is left of B.",
            }
        ),
        candidates=fixture_cube_candidates(),
    )


def _safe_motion() -> PhysicalNodeSafety:
    return PhysicalNodeSafety(
        low_speed_mode=True,
        workspace_bounds_enabled=True,
        operator_armed=True,
        motion_enabled=True,
        emergency_stop_available=True,
        autonomous_setup_motion_allowed=False,
    )
