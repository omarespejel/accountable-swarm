import json
from unittest import TestCase

from accountable_swarm.swarm import (
    FORMATION_MISSION_FIXTURE_MODEL_ID,
    FormationMissionChoice,
    GridPoint,
    build_formation_mission_trace,
    fixture_formation_mission_response,
    parse_formation_mission_response,
    qwen_formation_mission_prompt,
)
from accountable_swarm.trace.models import verify_trace


class FormationMissionChoiceTests(TestCase):
    def test_fixture_response_is_canonical(self) -> None:
        self.assertEqual(
            fixture_formation_mission_response(),
            '{"mission":"surround_hazard","risk":"cautious"}',
        )

    def test_parse_response_accepts_supported_enum(self) -> None:
        choice = parse_formation_mission_response(
            json.dumps({"mission": "hold_position", "risk": "balanced"})
        )

        self.assertEqual(choice, FormationMissionChoice(mission="hold_position", risk="balanced"))
        self.assertEqual(choice.fallback_formation(), "line")

    def test_parse_response_rejects_extra_keys(self) -> None:
        with self.assertRaisesRegex(ValueError, "keys mismatch"):
            parse_formation_mission_response(
                json.dumps({"mission": "surround_hazard", "risk": "cautious", "extra": "nope"})
            )

    def test_parse_response_rejects_malformed_json(self) -> None:
        with self.assertRaisesRegex(ValueError, "valid JSON"):
            parse_formation_mission_response('{"mission":"surround_hazard","risk":')

    def test_parse_response_rejects_duplicate_keys(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate key"):
            parse_formation_mission_response(
                '{"mission":"hold_position","mission":"surround_hazard","risk":"cautious"}'
            )

    def test_parse_response_rejects_invalid_enum(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported formation mission"):
            parse_formation_mission_response(
                json.dumps({"mission": "invent", "risk": "cautious"})
            )

        with self.assertRaisesRegex(ValueError, "unsupported mission risk"):
            parse_formation_mission_response(
                json.dumps({"mission": "surround_hazard", "risk": "reckless"})
            )

    def test_parse_response_rejects_float_payloads(self) -> None:
        with self.assertRaises(TypeError):
            parse_formation_mission_response(
                json.dumps({"mission": "surround_hazard", "risk": 0.5})
            )

    def test_prompt_mentions_json_and_allowed_values(self) -> None:
        prompt = qwen_formation_mission_prompt(
            hazard_cell=GridPoint(3, 2),
            grid_width=7,
            grid_height=5,
            requested_formation="x",
        )

        self.assertIn("json", prompt.casefold())
        self.assertIn("surround_hazard", prompt)
        self.assertIn("hold_position", prompt)
        self.assertIn("cautious", prompt)
        self.assertIn("balanced", prompt)
        self.assertIn("(3,2)", prompt)
        self.assertIn("x", prompt)

    def test_build_trace_binds_choice_into_command(self) -> None:
        trace = build_formation_mission_trace(
            choice=FormationMissionChoice(mission="surround_hazard", risk="cautious"),
            mode="fixture",
            model=FORMATION_MISSION_FIXTURE_MODEL_ID,
            hazard_cell=GridPoint(3, 2),
            grid_width=7,
            grid_height=5,
            requested_formation="x",
        )

        event = trace.events[0]
        self.assertEqual(event.command["type"], "formation_mission")
        self.assertEqual(event.command["mission"], "surround_hazard")
        self.assertEqual(event.command["risk"], "cautious")
        self.assertEqual(event.command["requested_formation"], "x")
        self.assertEqual(event.command["fallback_formation"], "x")
        self.assertEqual(len(verify_trace(trace)), 64)
