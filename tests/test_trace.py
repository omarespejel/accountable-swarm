from unittest import TestCase

from accountable_swarm.trace.models import (
    DecisionEvent,
    PerceptionEvent,
    build_single_event_trace,
    canonical_json,
    trace_from_dict,
    verify_trace,
)


class DecisionTraceTests(TestCase):
    def test_single_event_trace_replays_deterministically(self) -> None:
        trace = build_single_event_trace(
            run_id="run",
            actor_id="physical-node-0",
            mode="fixture",
            perception=_perception(),
            intent="hold on hazard",
            decision="VETO",
            reason="hazard detected",
            command={"type": "hold", "duration_ticks": 1},
        )
        loaded = trace_from_dict(trace.to_dict())
        self.assertEqual(verify_trace(trace), verify_trace(loaded))
        self.assertEqual(canonical_json(trace.to_dict()), canonical_json(loaded.to_dict()))

    def test_trace_rejects_tampered_summary(self) -> None:
        trace = build_single_event_trace(
            run_id="run",
            actor_id="physical-node-0",
            mode="fixture",
            perception=_perception(),
            intent="hold on hazard",
            decision="VETO",
            reason="hazard detected",
            command={"type": "hold", "duration_ticks": 1},
        )
        value = trace.to_dict()
        value["summary_sha"] = "f" * 64
        with self.assertRaises(ValueError):
            verify_trace(trace_from_dict(value))

    def test_rejects_non_hex_prev_sha(self) -> None:
        with self.assertRaises(ValueError):
            DecisionEvent(
                tick=0,
                actor_id="physical-node-0",
                mode="fixture",
                intent="hold on hazard",
                decision="VETO",
                reason="hazard detected",
                command={"type": "hold"},
                perception=_perception(),
                prev_sha="z" * 64,
            )


def _perception() -> PerceptionEvent:
    return PerceptionEvent(
        event_id="perception-0000",
        source="image://hazard_marker.ppm",
        image_width=4,
        image_height=4,
        label="marked hazard",
        bbox_2d_norm_1000=(250, 250, 750, 750),
        bbox_2d_px=(1, 1, 3, 3),
        model="fixture-qwen3-vl-shape",
    )
