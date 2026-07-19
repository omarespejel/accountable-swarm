from dataclasses import replace
import json
from pathlib import Path
from unittest import TestCase

from accountable_swarm.qwenguard.memory import (
    MEMORY_POLICY_SEQUENCE,
    MEMORY_STATE_SEQUENCE,
    build_memory_replay_report,
    build_qwenguard_memory_replay,
    memory_fixture_from_dict,
    parse_memory_evidence_manifest_json,
    parse_memory_fixture_json,
    verify_qwenguard_memory_replay,
)
from accountable_swarm.trace.models import DecisionEvent, DecisionTrace, verify_trace


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "fixtures/qwenguard_memory/observations.json"
MANIFEST_PATH = ROOT / "fixtures/qwenguard_memory/manifest.json"


class QwenGuardMemoryTests(TestCase):
    def test_exact_state_sequence_holds_without_motion(self) -> None:
        fixture, manifest, trace = _fixture_manifest_and_trace()
        report = build_memory_replay_report(
            fixture=fixture,
            evidence_manifest=manifest,
            trace=trace,
        )

        self.assertEqual(verify_qwenguard_memory_replay(trace), trace.summary_sha)
        self.assertEqual(
            [event.command["to_state"] for event in trace.events],
            list(MEMORY_STATE_SEQUENCE),
        )
        self.assertEqual(
            [event.command["policy_phase"] for event in trace.events],
            list(MEMORY_POLICY_SEQUENCE),
        )
        self.assertEqual([event.decision for event in trace.events], ["EVALUATE", "EVALUATE", "HOLD", "EVALUATE"])
        self.assertEqual(report["memory_state_sequence"], list(MEMORY_STATE_SEQUENCE))
        self.assertEqual(report["policy_sequence"], list(MEMORY_POLICY_SEQUENCE))
        self.assertEqual(report["execution_context"], "post_run_policy_simulation")
        self.assertFalse(report["robot_runtime_transitions"])
        self.assertIn("Gemini 2 fixed independent reference", report["semantic_frame_source"])
        self.assertIn("separate teleoperated context receipts", report["go2_capture_receipts_role"])
        self.assertEqual(report["retained_memory_state"], "PROVISIONAL")
        self.assertEqual(report["policy_action"], "HOLD")
        self.assertEqual(report["reverify_status"], "REQUESTED")
        self.assertTrue(all(event.command["motion_executed"] is False for event in trace.events))
        self.assertTrue(all(event.command["motor_authority"] == "none" for event in trace.events))

    def test_same_fixture_produces_identical_trace(self) -> None:
        _fixture, _manifest, first = _fixture_manifest_and_trace()
        _fixture, _manifest, second = _fixture_manifest_and_trace()

        self.assertEqual(first.summary_sha, second.summary_sha)
        self.assertEqual(first.to_canonical_json(), second.to_canonical_json())

    def test_baseline_and_conflict_hashes_must_differ(self) -> None:
        fixture = _fixture()
        conflict = replace(
            fixture.conflict,
            source_frame_sha256=fixture.baseline.source_frame_sha256,
        )

        with self.assertRaisesRegex(ValueError, "frames must differ"):
            build_qwenguard_memory_replay(
                run_id="same-frame",
                memory_id="target-001",
                baseline=fixture.baseline,
                conflict=conflict,
            )

    def test_semantically_skipped_transition_fails_after_valid_rehash(self) -> None:
        _fixture, _manifest, trace = _fixture_manifest_and_trace()
        commands = [dict(event.command) for event in trace.events]
        commands[1]["to_state"] = "HOLD"
        rehashed = _rehash_with_commands(trace, commands)

        self.assertEqual(verify_trace(rehashed), rehashed.summary_sha)
        with self.assertRaisesRegex(ValueError, "to_state"):
            verify_qwenguard_memory_replay(rehashed)

    def test_broken_hash_chain_fails_without_rehashing(self) -> None:
        _fixture, _manifest, trace = _fixture_manifest_and_trace()
        events = list(trace.events)
        events[1] = replace(events[1], prev_sha="0" * 64)
        tampered = replace(trace, events=tuple(events))

        with self.assertRaisesRegex(ValueError, "trace hash chain is broken"):
            verify_qwenguard_memory_replay(tampered)

    def test_extra_command_key_fails_after_valid_rehash(self) -> None:
        _fixture, _manifest, trace = _fixture_manifest_and_trace()
        commands = [dict(event.command) for event in trace.events]
        commands[2]["requested_action"] = "move"
        rehashed = _rehash_with_commands(trace, commands)

        self.assertEqual(verify_trace(rehashed), rehashed.summary_sha)
        with self.assertRaisesRegex(ValueError, "command keys"):
            verify_qwenguard_memory_replay(rehashed)

    def test_motor_authority_fails_after_valid_rehash(self) -> None:
        _fixture, _manifest, trace = _fixture_manifest_and_trace()
        commands = [dict(event.command) for event in trace.events]
        commands[2]["motor_authority"] = "granted"
        rehashed = _rehash_with_commands(trace, commands)

        self.assertEqual(verify_trace(rehashed), rehashed.summary_sha)
        with self.assertRaisesRegex(ValueError, "motor_authority"):
            verify_qwenguard_memory_replay(rehashed)

    def test_report_rejects_semantic_trace_with_unrelated_receipts(self) -> None:
        fixture, manifest, trace = _fixture_manifest_and_trace()
        commands = [dict(event.command) for event in trace.events]
        commands[0]["source_frame_sha256"] = "1" * 64
        commands[0]["observation_sha256"] = "2" * 64
        for command in commands[1:]:
            command["source_frame_sha256"] = "3" * 64
            command["observation_sha256"] = "4" * 64
        replacements = {}
        for index, (event, command) in enumerate(zip(trace.events, commands)):
            perception = replace(
                event.perception,
                source=f"sha256://{command['source_frame_sha256']}",
            )
            replacements[index] = replace(
                event,
                command=command,
                perception=perception,
                sha256="",
            )
        rehashed = _rehash_with_events(trace, replacements)

        self.assertEqual(verify_qwenguard_memory_replay(rehashed), rehashed.summary_sha)
        with self.assertRaisesRegex(ValueError, "does not match the checked fixture"):
            build_memory_replay_report(
                fixture=fixture,
                evidence_manifest=manifest,
                trace=rehashed,
            )

    def test_semantic_verifier_rejects_non_object_command_fail_closed(self) -> None:
        _fixture, _manifest, trace = _fixture_manifest_and_trace()
        malformed = replace(
            trace.events[0],
            command=["not", "an", "object"],  # type: ignore[arg-type]
            sha256="",
        )
        rehashed = _rehash_with_events(trace, {0: malformed})

        self.assertEqual(verify_trace(rehashed), rehashed.summary_sha)
        with self.assertRaisesRegex(TypeError, "command must be an object"):
            verify_qwenguard_memory_replay(rehashed)

    def test_observation_rejects_bool_scalars(self) -> None:
        fixture = _fixture()
        with self.assertRaisesRegex(TypeError, "reported_bbox"):
            replace(fixture.baseline, reported_bbox=(False, 1, 2, 3))
        with self.assertRaisesRegex(TypeError, "image_width"):
            replace(fixture.baseline, image_width=True)

    def test_semantic_verifier_rejects_bool_tick_after_valid_rehash(self) -> None:
        _fixture, _manifest, trace = _fixture_manifest_and_trace()
        first = replace(trace.events[0], tick=False, sha256="").with_computed_sha()
        events = [first]
        previous = first.sha256
        for event in trace.events[1:]:
            rebuilt = replace(event, prev_sha=previous, sha256="").with_computed_sha()
            events.append(rebuilt)
            previous = rebuilt.sha256
        rehashed = DecisionTrace(run_id=trace.run_id, events=tuple(events)).with_computed_summary()

        self.assertEqual(verify_trace(rehashed), rehashed.summary_sha)
        with self.assertRaisesRegex(ValueError, "ticks"):
            verify_qwenguard_memory_replay(rehashed)

    def test_fixture_rejects_raw_float_and_duplicate_keys(self) -> None:
        value = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        value["observations"][0]["detection"]["memory_confidence_milli"] = 0.5
        with self.assertRaisesRegex(TypeError, "memory_confidence_milli"):
            memory_fixture_from_dict(value)

        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            parse_memory_fixture_json('{"schema":"a","schema":"b"}')

    def test_fixture_rejects_private_or_unreviewed_public_text(self) -> None:
        for field, private_value, message in (
            ("fixture_id", "ALIBABA_API_KEY=private", "secret-like material"),
            ("measurement_caveat", "/Users/operator/private/frame.png", "absolute or host-specific path"),
            ("measurement_caveat", "/tmp/capture/frame.png", "absolute or host-specific path"),
            ("measurement_caveat", "/var/lib/receipt.json", "absolute or host-specific path"),
            ("measurement_caveat", "//host", "absolute or host-specific path"),
            ("measurement_caveat", "//host/share/frame.png", "absolute or host-specific path"),
            ("measurement_caveat", "///var/lib/receipt.json", "absolute or host-specific path"),
            ("measurement_caveat", "file:/var/lib/receipt.json", "absolute or host-specific path"),
            ("measurement_caveat", "~/capture/frame.png", "absolute or host-specific path"),
            ("measurement_caveat", r"C:\Users\operator\private\frame.png", "absolute or host-specific path"),
            ("measurement_caveat", r"\\workstation\capture\frame.png", "absolute or host-specific path"),
        ):
            with self.subTest(field=field):
                value = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
                if field == "fixture_id":
                    value[field] = private_value
                else:
                    value["observed_result"][field] = private_value
                with self.assertRaisesRegex(ValueError, message):
                    memory_fixture_from_dict(value)

    def test_fixture_rejects_unbound_object_label_bbox_and_displacement(self) -> None:
        mutations = (
            (
                lambda value: value["observed_result"].__setitem__("reported_displacement_model_units", 999),
                "reported displacement",
            ),
            (
                lambda value: value["observations"][1]["detection"].__setitem__("object_id", "other-999"),
                "same stable object_id",
            ),
            (
                lambda value: value["observations"][1]["detection"].__setitem__("label", "door"),
                "same label",
            ),
            (
                lambda value: value["observations"][1]["detection"].__setitem__("bbox", [271, 349, 99999, 999999]),
                "0-1000 domain",
            ),
        )
        for mutate, message in mutations:
            with self.subTest(message=message):
                value = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
                mutate(value)
                with self.assertRaisesRegex(ValueError, message):
                    memory_fixture_from_dict(value)

    def test_semantic_verifier_rejects_rehashed_metadata_tampering(self) -> None:
        _fixture, _manifest, trace = _fixture_manifest_and_trace()
        cases = (
            ("intent", "act on the scene", "intent"),
            ("reason", "trust me", "reason"),
        )
        for field, value, message in cases:
            with self.subTest(field=field):
                event = replace(trace.events[2], **{field: value}, sha256="")
                rehashed = _rehash_with_events(trace, {2: event})
                self.assertEqual(verify_trace(rehashed), rehashed.summary_sha)
                with self.assertRaisesRegex(ValueError, message):
                    verify_qwenguard_memory_replay(rehashed)

        for field, value, message in (
            ("label", "door_observation_receipt", "label"),
            ("model", "recorded:other-model", "model"),
            ("score_milli", 999, "confidence"),
        ):
            with self.subTest(perception_field=field):
                perception = replace(trace.events[1].perception, **{field: value})
                event = replace(trace.events[1], perception=perception, sha256="")
                rehashed = _rehash_with_events(trace, {1: event})
                self.assertEqual(verify_trace(rehashed), rehashed.summary_sha)
                with self.assertRaisesRegex(ValueError, message):
                    verify_qwenguard_memory_replay(rehashed)

    def test_evidence_manifest_is_bound_private_and_complete(self) -> None:
        fixture = _fixture()
        parsed = parse_memory_evidence_manifest_json(
            MANIFEST_PATH.read_text(encoding="utf-8"),
            fixture=fixture,
        )
        self.assertEqual(parsed.fixture_sha256, fixture.fixture_sha256)
        self.assertEqual(len(parsed.manifest_sha256), 64)

        mutations = (
            (
                lambda value: value.__setitem__("fixture_sha256", "0" * 64),
                "does not match",
            ),
            (
                lambda value: value["go2_capture_receipts"]["pass_after"]["recorded_rows"].__setitem__("lidar", 0),
                "must be positive",
            ),
            (
                lambda value: value.__setitem__("fixture", "/Users/operator/private.json"),
                "absolute or host-specific path",
            ),
            (
                lambda value: value["non_claims"].__setitem__(0, "ALIBABA_API_KEY=secret-value"),
                "secret-like material",
            ),
        )
        for mutate, message in mutations:
            with self.subTest(message=message):
                value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
                mutate(value)
                with self.assertRaisesRegex(ValueError, message):
                    parse_memory_evidence_manifest_json(json.dumps(value), fixture=fixture)

        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            parse_memory_evidence_manifest_json(
                '{"schema_version":"a","schema_version":"b"}',
                fixture=fixture,
            )

    def test_builder_rejects_cloud_source_mode(self) -> None:
        fixture = _fixture()
        with self.assertRaisesRegex(ValueError, "fixture source mode only"):
            build_qwenguard_memory_replay(
                run_id="cloud-replay",
                memory_id="target-001",
                baseline=fixture.baseline,
                conflict=fixture.conflict,
                source_mode="cloud",
            )

    def test_fixture_keeps_reported_bbox_out_of_calibrated_trace_bbox(self) -> None:
        fixture, _manifest, trace = _fixture_manifest_and_trace()

        self.assertEqual(fixture.baseline.reported_bbox, (396, 237, 466, 457))
        self.assertEqual(fixture.baseline.memory_confidence_milli, 500)
        self.assertEqual(fixture.conflict.memory_confidence_milli, 750)
        self.assertEqual(trace.events[0].perception.score_milli, 500)
        self.assertTrue(all(event.perception.score_milli == 750 for event in trace.events[1:]))
        self.assertTrue(all(event.perception.model == "recorded:memory2-belief" for event in trace.events))
        self.assertEqual(trace.events[0].perception.bbox_2d_norm_1000, (0, 0, 1000, 1000))
        self.assertEqual(
            trace.events[0].perception.bbox_2d_px,
            (0, 0, fixture.baseline.image_width, fixture.baseline.image_height),
        )


def _fixture():
    return parse_memory_fixture_json(FIXTURE_PATH.read_text(encoding="utf-8"))


def _fixture_manifest_and_trace():
    fixture = _fixture()
    manifest = parse_memory_evidence_manifest_json(
        MANIFEST_PATH.read_text(encoding="utf-8"),
        fixture=fixture,
    )
    trace = build_qwenguard_memory_replay(
        run_id="qwenguard-memory-replay-0001",
        memory_id="target-001",
        baseline=fixture.baseline,
        conflict=fixture.conflict,
    )
    return fixture, manifest, trace


def _rehash_with_commands(trace: DecisionTrace, commands: list[dict[str, object]]) -> DecisionTrace:
    previous = trace.genesis_sha
    events = []
    for event, command in zip(trace.events, commands):
        rebuilt = replace(event, command=command, prev_sha=previous, sha256="").with_computed_sha()
        events.append(rebuilt)
        previous = rebuilt.sha256
    return DecisionTrace(run_id=trace.run_id, events=tuple(events)).with_computed_summary()


def _rehash_with_events(
    trace: DecisionTrace,
    replacements: dict[int, DecisionEvent],
) -> DecisionTrace:
    previous = trace.genesis_sha
    events = []
    for index, original in enumerate(trace.events):
        event = replacements.get(index, original)
        rebuilt = replace(event, prev_sha=previous, sha256="").with_computed_sha()
        events.append(rebuilt)
        previous = rebuilt.sha256
    return DecisionTrace(run_id=trace.run_id, events=tuple(events)).with_computed_summary()
