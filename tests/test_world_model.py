import json
from unittest import TestCase

from accountable_swarm.swarm.sim import GridPoint
from accountable_swarm.trace.models import GENESIS_SHA, canonical_json
from accountable_swarm.world_model import (
    PredictedConflict,
    WorldAgentState,
    WorldModelState,
    WorldObservation,
    WorldReservation,
    verify_world_model_state,
    world_model_from_dict,
)


class WorldModelTests(TestCase):
    def test_world_model_hash_replays_deterministically(self) -> None:
        state = _state().with_computed_sha()
        loaded = world_model_from_dict(json.loads(state.to_canonical_json()))

        self.assertEqual(verify_world_model_state(state), verify_world_model_state(loaded))
        self.assertEqual(canonical_json(state.to_dict()), canonical_json(loaded.to_dict()))

    def test_world_model_hash_ignores_input_ordering(self) -> None:
        left = _state().with_computed_sha()
        right = WorldModelState(
            tick=1,
            grid_width=7,
            grid_height=5,
            observations=tuple(reversed(left.observations)),
            hazards=tuple(reversed(left.hazards)),
            agents=tuple(reversed(left.agents)),
            reservations=tuple(reversed(left.reservations)),
            predicted_conflicts=tuple(reversed(left.predicted_conflicts)),
        ).with_computed_sha()

        self.assertEqual(left.world_model_sha, right.world_model_sha)

    def test_world_model_rejects_tampered_hash(self) -> None:
        state = _state().with_computed_sha()
        value = state.to_dict()
        value["world_model_sha"] = "f" * 64

        with self.assertRaisesRegex(ValueError, "world_model_sha mismatch"):
            verify_world_model_state(world_model_from_dict(value))

    def test_world_model_requires_summary_hash_before_verification(self) -> None:
        with self.assertRaisesRegex(ValueError, "world_model_sha missing"):
            verify_world_model_state(_state())

    def test_world_model_rejects_raw_float(self) -> None:
        with self.assertRaisesRegex(TypeError, "raw float"):
            WorldModelState(
                tick=0,
                grid_width=7.0,  # type: ignore[arg-type]
                grid_height=5,
                observations=(_observation(),),
            )

    def test_world_model_rejects_raw_bool_in_hashed_payload(self) -> None:
        with self.assertRaisesRegex(TypeError, "raw bool"):
            WorldModelState(
                tick=True,  # type: ignore[arg-type]
                grid_width=7,
                grid_height=5,
                observations=(_observation(),),
            )

    def test_world_model_rejects_bool_bbox_values(self) -> None:
        with self.assertRaisesRegex(TypeError, "bbox_2d_norm_1000 values must be integers"):
            WorldObservation(
                observation_id="obs-bool-bbox",
                source="qwen_bbox",
                label="hazard",
                cell=GridPoint(3, 2),
                source_trace_sha=GENESIS_SHA,
                bbox_2d_norm_1000=(True, 100, 900, 900),  # type: ignore[arg-type]
            )

    def test_world_model_rejects_duplicate_agents(self) -> None:
        agent = _agent("sim-agent-0", GridPoint(0, 0), GridPoint(1, 0), "MOVE")

        with self.assertRaisesRegex(ValueError, "unique agent_id"):
            WorldModelState(
                tick=0,
                grid_width=7,
                grid_height=5,
                agents=(agent, agent),
            )

    def test_world_model_rejects_duplicate_reservations(self) -> None:
        reservation = WorldReservation(tick=1, agent_id="sim-agent-0", cell=GridPoint(1, 0))

        with self.assertRaisesRegex(ValueError, "unique tick/agent_id"):
            WorldModelState(
                tick=0,
                grid_width=7,
                grid_height=5,
                reservations=(reservation, reservation),
            )

    def test_world_model_rejects_out_of_bounds_cells(self) -> None:
        with self.assertRaisesRegex(ValueError, "hazard outside world model grid"):
            WorldModelState(
                tick=0,
                grid_width=7,
                grid_height=5,
                hazards=(GridPoint(7, 0),),
            )

    def test_world_model_rejects_unsupported_observation_source(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported observation source"):
            WorldObservation(
                observation_id="obs-bad-source",
                source="llm_control",
                label="hazard",
                cell=GridPoint(3, 2),
                source_trace_sha=GENESIS_SHA,
            )

    def test_world_model_rejects_invalid_conflict(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported conflict_type"):
            PredictedConflict(
                tick=1,
                conflict_type="fake_conflict",
                agent_ids=("sim-agent-0",),
                cell=GridPoint(1, 0),
                reason="bad type",
            )


def _state() -> WorldModelState:
    return WorldModelState(
        tick=1,
        grid_width=7,
        grid_height=5,
        observations=(_observation(),),
        hazards=(GridPoint(3, 2),),
        agents=(
            _agent("sim-agent-1", GridPoint(6, 2), GridPoint(4, 3), "REROUTE"),
            _agent("sim-agent-0", GridPoint(0, 2), GridPoint(2, 1), "MOVE"),
        ),
        reservations=(
            WorldReservation(tick=2, agent_id="sim-agent-1", cell=GridPoint(5, 2)),
            WorldReservation(tick=2, agent_id="sim-agent-0", cell=GridPoint(1, 2)),
        ),
        predicted_conflicts=(
            PredictedConflict(
                tick=2,
                conflict_type="reservation",
                agent_ids=("sim-agent-0", "sim-agent-1"),
                cell=GridPoint(3, 2),
                reason="hazard cell is reserved as blocked",
            ),
        ),
    )


def _observation() -> WorldObservation:
    return WorldObservation(
        observation_id="obs-0000",
        source="qwen_bbox",
        label="hazard",
        cell=GridPoint(3, 2),
        source_trace_sha=GENESIS_SHA,
        bbox_2d_norm_1000=(241, 238, 756, 759),
        score_milli=1000,
    )


def _agent(agent_id: str, cell: GridPoint, goal: GridPoint, decision: str) -> WorldAgentState:
    return WorldAgentState(
        agent_id=agent_id,
        cell=cell,
        goal=goal,
        decision_trace_sha=GENESIS_SHA,
        last_decision=decision,
    )
