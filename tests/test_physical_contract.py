from unittest import TestCase

from accountable_swarm.physical import PhysicalAction, PhysicalNodeSafety, TraceOnlyActionSink


class PhysicalContractTests(TestCase):
    def test_trace_only_sink_accepts_hold_without_arming(self) -> None:
        sink = TraceOnlyActionSink()
        action = PhysicalAction(action_type="hold", payload={"duration_ticks": 1})
        self.assertEqual(sink.apply(action), action)
        self.assertEqual(sink.actions, [action])

    def test_trace_only_sink_rejects_motion_without_operator_arming(self) -> None:
        sink = TraceOnlyActionSink()
        with self.assertRaises(RuntimeError):
            sink.apply(PhysicalAction(action_type="move", payload={"x": 1}))

    def test_safety_contract_requires_emergency_stop(self) -> None:
        safety = PhysicalNodeSafety(operator_armed=True, motion_enabled=True, emergency_stop_available=False)
        with self.assertRaises(RuntimeError):
            safety.assert_safe_for_motion()
