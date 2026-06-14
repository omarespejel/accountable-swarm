import json
from unittest import TestCase

from accountable_swarm.swarm import (
    MISSION_MODEL_FIXTURE_ID,
    MISSION_SCHEMA_VERSION,
    MissionSpec,
    build_mission_trace,
    fixture_mission_response,
    parse_mission_response,
)
from accountable_swarm.trace.models import verify_trace


class SwarmMissionTests(TestCase):
    def test_fixture_mission_parses_and_traces(self) -> None:
        spec = parse_mission_response(fixture_mission_response())
        trace = build_mission_trace(spec=spec, mode="fixture", model=MISSION_MODEL_FIXTURE_ID)

        self.assertEqual(spec.schema_version, MISSION_SCHEMA_VERSION)
        self.assertEqual(spec.mission_id, "center-block-n4")
        self.assertEqual(spec.scenario, "center-block")
        self.assertEqual(spec.agent_count, 4)
        self.assertEqual(spec.ticks, 16)
        self.assertEqual(trace.events[0].perception.event_id, "swarm-mission-center-block-n4")
        self.assertEqual(len(verify_trace(trace)), 64)

    def test_mission_trace_rejects_unsupported_mode(self) -> None:
        spec = parse_mission_response(fixture_mission_response())

        with self.assertRaises(ValueError):
            build_mission_trace(spec=spec, mode="edge", model=MISSION_MODEL_FIXTURE_ID)

    def test_malformed_json_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            parse_mission_response("not json")

    def test_extra_key_is_rejected(self) -> None:
        value = json.loads(fixture_mission_response())
        value["extra"] = "not allowed"

        with self.assertRaises(ValueError):
            parse_mission_response(json.dumps(value))

    def test_unsupported_scenario_is_rejected(self) -> None:
        value = json.loads(fixture_mission_response())
        value["scenario"] = "unknown"

        with self.assertRaises(ValueError):
            parse_mission_response(json.dumps(value))

    def test_unsupported_agent_count_is_rejected(self) -> None:
        value = json.loads(fixture_mission_response())
        value["agent_count"] = 2

        with self.assertRaises(ValueError):
            parse_mission_response(json.dumps(value))

    def test_unsafe_ticks_are_rejected(self) -> None:
        low = json.loads(fixture_mission_response())
        high = json.loads(fixture_mission_response())
        low["ticks"] = 0
        high["ticks"] = 33

        with self.assertRaises(ValueError):
            parse_mission_response(json.dumps(low))
        with self.assertRaises(ValueError):
            parse_mission_response(json.dumps(high))

    def test_float_and_bool_mission_fields_are_rejected(self) -> None:
        float_ticks = json.loads(fixture_mission_response())
        bool_count = json.loads(fixture_mission_response())
        float_ticks["ticks"] = 16.5
        bool_count["agent_count"] = True

        with self.assertRaises(TypeError):
            parse_mission_response(json.dumps(float_ticks))
        with self.assertRaises(TypeError):
            parse_mission_response(json.dumps(bool_count))

    def test_direct_mission_spec_rejects_bool_agent_count(self) -> None:
        with self.assertRaises(TypeError):
            MissionSpec(
                schema_version=MISSION_SCHEMA_VERSION,
                mission_id="bad",
                scenario="center-block",
                agent_count=True,
                ticks=16,
                objective="invalid bool count",
            )
