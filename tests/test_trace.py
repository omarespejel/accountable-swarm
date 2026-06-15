from unittest import TestCase

from accountable_swarm.trace.models import (
    DecisionEvent,
    PerceptionEvent,
    build_single_event_trace,
    canonical_json,
    reject_raw_floats,
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

    def test_trace_rejects_missing_summary(self) -> None:
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
        value["summary_sha"] = ""
        with self.assertRaises(ValueError):
            verify_trace(trace_from_dict(value))

    def test_trace_rejects_missing_event_hash(self) -> None:
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
        value["events"][0]["sha256"] = ""
        with self.assertRaises(ValueError):
            verify_trace(trace_from_dict(value))

    def test_trace_rejects_broken_hash_chain(self) -> None:
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
        value["events"][0]["prev_sha"] = "f" * 64
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

    def test_canonical_json_rejects_raw_float(self) -> None:
        with self.assertRaises(TypeError):
            canonical_json({"latency_seconds": 0.1})

    def test_decision_event_rejects_raw_float_in_command_before_hash(self) -> None:
        perception = _perception()
        with self.assertRaisesRegex(TypeError, r"\$\.command\.vx"):
            build_single_event_trace(
                run_id="trace-float-command",
                actor_id="agent-0",
                perception=perception,
                intent="move in fixed units",
                decision="MOVE",
                reason="test raw float rejection",
                command={"type": "move", "vx": 0.15},
            )

    def test_reject_raw_floats_allows_integer_units(self) -> None:
        reject_raw_floats({"latency_ms": 100, "confidence_ppm": 950000})


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
