import json
from unittest import TestCase

from accountable_swarm.swarm import (
    DEFAULT_MISSION_SCENARIO,
    MISSION_MODEL_FIXTURE_ID,
    MISSION_SCHEMA_VERSION,
    MissionSpec,
    SUPPORTED_MISSION_SCENARIOS,
    build_mission_trace,
    fixture_mission_response,
    mission_id_for_scenario,
    mission_spec_for_scenario,
    parse_mission_intent_response,
    parse_mission_response,
    qwen_mission_prompt,
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

    def test_default_fixture_mission_response_stays_canonical(self) -> None:
        self.assertEqual(
            fixture_mission_response(),
            (
                '{"agent_count":4,"mission_id":"center-block-n4",'
                '"objective":"route all agents to their opposing goals without same-cell, swap, or obstacle occupancy violations",'
                '"scenario":"center-block","schema_version":"swarm-mission.v1","ticks":16}'
            ),
        )

    def test_supported_mission_scenarios_follow_registry(self) -> None:
        self.assertEqual(DEFAULT_MISSION_SCENARIO, "center-block")
        self.assertIn("center-block", SUPPORTED_MISSION_SCENARIOS)
        self.assertIn("vertical-slalom", SUPPORTED_MISSION_SCENARIOS)
        self.assertIn("horizontal-slalom", SUPPORTED_MISSION_SCENARIOS)
        self.assertIn("double-chicane", SUPPORTED_MISSION_SCENARIOS)

    def test_fixture_mission_can_select_horizontal_slalom(self) -> None:
        spec = parse_mission_response(fixture_mission_response(scenario="horizontal-slalom"))
        trace = build_mission_trace(spec=spec, mode="fixture", model=MISSION_MODEL_FIXTURE_ID)

        self.assertEqual(spec.mission_id, "horizontal-slalom-n4")
        self.assertEqual(spec.scenario, "horizontal-slalom")
        self.assertEqual(spec.agent_count, 4)
        self.assertEqual(spec.ticks, 16)
        self.assertEqual(trace.events[0].perception.event_id, "swarm-mission-horizontal-slalom-n4")
        self.assertEqual(len(verify_trace(trace)), 64)

    def test_fixture_mission_can_select_double_chicane_with_reviewed_tick_budget(self) -> None:
        spec = parse_mission_response(fixture_mission_response(scenario="double-chicane"))
        trace = build_mission_trace(spec=spec, mode="fixture", model=MISSION_MODEL_FIXTURE_ID)

        self.assertEqual(spec.mission_id, "double-chicane-n4")
        self.assertEqual(spec.scenario, "double-chicane")
        self.assertEqual(spec.agent_count, 4)
        self.assertEqual(spec.ticks, 17)
        self.assertEqual(trace.events[0].perception.event_id, "swarm-mission-double-chicane-n4")
        self.assertEqual(len(verify_trace(trace)), 64)

    def test_dashscope_intent_response_only_accepts_objective(self) -> None:
        objective = "route agents through the selected fixed scenario"
        parsed = parse_mission_intent_response(json.dumps({"objective": objective}))

        self.assertEqual(parsed, objective)

    def test_dashscope_intent_response_rejects_control_metadata(self) -> None:
        with self.assertRaises(ValueError):
            parse_mission_intent_response(
                json.dumps(
                    {
                        "objective": "route agents",
                        "scenario": "horizontal-slalom",
                        "agent_count": 4,
                    }
                )
            )

    def test_dashscope_intent_response_rejects_control_metadata_inside_objective(self) -> None:
        bad_objectives = (
            "route 5 agents through the selected fixed layout",
            "route agents in scenario double-chicane",
            "route sim-agent-0 to x=3 y=2",
            "route agents through waypoints [1,2]",
            "set velocity to fast and thrust to high",
            "use mission_id center-block-n4",
        )

        for objective in bad_objectives:
            with self.subTest(objective=objective):
                with self.assertRaises(ValueError):
                    parse_mission_intent_response(json.dumps({"objective": objective}))

    def test_qwen_mission_prompt_requests_intent_only(self) -> None:
        prompt = qwen_mission_prompt(scenario="horizontal-slalom")

        self.assertIn("exactly one key: objective", prompt)
        self.assertIn("horizontal-slalom", prompt)
        self.assertIn("do not output scenario, mission_id, agent_count, ticks", prompt)
        self.assertIn("Do not include markdown, comments, digits", prompt)
        self.assertNotIn("schema_version must", prompt)
        self.assertNotIn("Choose scenario", prompt)

    def test_mission_spec_for_scenario_binds_deterministic_fields(self) -> None:
        spec = mission_spec_for_scenario(
            scenario="horizontal-slalom",
            objective="route agents through the selected fixed scenario",
        )

        self.assertEqual(spec.mission_id, "horizontal-slalom-n4")
        self.assertEqual(mission_id_for_scenario(scenario="horizontal-slalom"), "horizontal-slalom-n4")
        self.assertEqual(spec.scenario, "horizontal-slalom")
        self.assertEqual(spec.agent_count, 4)
        self.assertEqual(spec.ticks, 16)

    def test_mission_spec_for_scenario_uses_reviewed_scenario_tick_budget(self) -> None:
        spec = mission_spec_for_scenario(
            scenario="double-chicane",
            objective="route agents through the selected fixed scenario",
        )

        self.assertEqual(spec.mission_id, "double-chicane-n4")
        self.assertEqual(spec.scenario, "double-chicane")
        self.assertEqual(spec.agent_count, 4)
        self.assertEqual(spec.ticks, 17)

    def test_fixture_mission_rejects_unregistered_scenario(self) -> None:
        with self.assertRaises(ValueError):
            fixture_mission_response(scenario="unknown")

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

    def test_full_mission_response_rejects_objective_with_hidden_control_metadata(self) -> None:
        value = json.loads(fixture_mission_response())
        value["objective"] = "route agents through coordinates (1,2)"

        with self.assertRaisesRegex(ValueError, "control metadata"):
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
