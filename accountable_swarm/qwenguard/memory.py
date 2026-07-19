"""Deterministic, no-motion memory replay for recorded Qwen observations."""

from __future__ import annotations

from dataclasses import dataclass
import json
from math import isqrt
from pathlib import PurePosixPath
import re
from typing import Any

from accountable_swarm.trace.models import (
    GENESIS_SHA,
    DecisionEvent,
    DecisionTrace,
    PerceptionEvent,
    canonical_json,
    sha256_canonical,
    verify_trace,
)


MEMORY_INITIAL_STATE = "UNSEEN"
MEMORY_POLICY_SEQUENCE = ("VERIFIED", "PROVISIONAL", "HOLD", "REVERIFY")
MEMORY_STATE_SEQUENCE = ("VERIFIED", "PROVISIONAL", "PROVISIONAL", "PROVISIONAL")
MEMORY_REPORT_SCHEMA_VERSION = "qwenguard-memory-replay-report.v1"
MEMORY_FIXTURE_SCHEMA_VERSION = "qwenguard.observation-fixture.v1"
MEMORY_EVIDENCE_MANIFEST_SCHEMA_VERSION = "qwenguard-memory-evidence-manifest.v1"
MEMORY_COORDINATE_SPACE = "model_reported_integer_bbox_unscaled"
MEMORY_FIXTURE_ID = "fixed-camera-two-pass-change-001"
MEMORY_TARGET_OBJECT_ID = "target-001"
MEMORY_TARGET_LABEL = "suitcase"
MEMORY_RECORDED_MODEL = "recorded:memory2-belief"
MEMORY_RECORDED_CONFIDENCE_BY_PASS = {"pass_before": 500, "pass_after": 750}
MEMORY_RECORDED_IMAGE_SIZE = (1920, 1080)
MEMORY_FIXTURE_RELATIVE_PATH = "fixtures/qwenguard_memory/observations.json"
MEMORY_CONFIDENCE_SEMANTICS = (
    "Internal Memory2 belief confidence from the recorded events; not Qwen detection confidence."
)
MEMORY_MEASUREMENT_CAVEAT = (
    "Model coordinates were stored without rescaling; displacement is reported in those "
    "model-coordinate units, not calibrated image pixels."
)
MEMORY_COMMAND_KEYS = frozenset(
    {
        "type",
        "memory_id",
        "from_state",
        "to_state",
        "policy_phase",
        "trigger",
        "source_frame_sha256",
        "observation_sha256",
        "motor_authority",
        "motion_executed",
    }
)
_TRANSITIONS = (
    ("UNSEEN", "VERIFIED", "VERIFIED", "baseline_confirmed", "EVALUATE"),
    ("VERIFIED", "PROVISIONAL", "PROVISIONAL", "conflicting_observation", "EVALUATE"),
    ("PROVISIONAL", "PROVISIONAL", "HOLD", "trust_policy_hold", "HOLD"),
    ("PROVISIONAL", "PROVISIONAL", "REVERIFY", "reverification_requested", "EVALUATE"),
)
_MEMORY_INTENT = "retain uncertain scene changes until re-verification"
_SECRET_PATTERN = re.compile(
    r"(?:ALIBABA_API_KEY\s*=|github_pat_|gh[pousr]_|(?<![A-Za-z0-9_-])sk-[A-Za-z0-9._-]{20,})",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class MemoryObservation:
    """Privacy-safe receipt for one recorded semantic observation."""

    observation_id: str
    object_id: str
    source_frame_sha256: str
    observation_sha256: str
    image_width: int
    image_height: int
    label: str
    reported_bbox: tuple[int, int, int, int]
    coordinate_space: str
    memory_confidence_milli: int
    model: str

    def __post_init__(self) -> None:
        _require_nonempty_string(self.observation_id, "observation_id")
        _require_nonempty_string(self.object_id, "object_id")
        _require_sha256(self.source_frame_sha256, "source_frame_sha256")
        _require_sha256(self.observation_sha256, "observation_sha256")
        _require_positive_int(self.image_width, "image_width")
        _require_positive_int(self.image_height, "image_height")
        _require_nonempty_string(self.label, "label")
        _validate_reported_bbox(self.reported_bbox)
        if self.coordinate_space != MEMORY_COORDINATE_SPACE:
            raise ValueError(f"unsupported coordinate space: {self.coordinate_space}")
        _require_int(self.memory_confidence_milli, "memory_confidence_milli")
        if self.memory_confidence_milli < 0 or self.memory_confidence_milli > 1000:
            raise ValueError("memory_confidence_milli must be within 0-1000")
        _require_nonempty_string(self.model, "model")

    def to_perception(self, *, event_id: str) -> PerceptionEvent:
        """Represent the source receipt without treating its bbox as calibrated."""

        return PerceptionEvent(
            event_id=event_id,
            source=f"sha256://{self.source_frame_sha256}",
            image_width=self.image_width,
            image_height=self.image_height,
            label=f"{self.label}_observation_receipt",
            bbox_2d_norm_1000=(0, 0, 1000, 1000),
            bbox_2d_px=(0, 0, self.image_width, self.image_height),
            model=self.model,
            score_milli=self.memory_confidence_milli,
        )


@dataclass(frozen=True)
class MemoryFixture:
    """Validated two-pass fixture plus its privacy and provenance boundary."""

    fixture_id: str
    fixture_sha256: str
    baseline: MemoryObservation
    conflict: MemoryObservation
    reported_change: str
    reported_displacement: int
    ambiguous: bool
    measurement_caveat: str
    retained_memory_state: str
    policy_action: str
    reverify_required: bool
    motion_executed: bool
    provenance: dict[str, str]


@dataclass(frozen=True)
class MemoryEvidenceManifest:
    """Validated public evidence manifest bound to one observation fixture."""

    manifest_sha256: str
    fixture_sha256: str


def parse_memory_fixture_json(text: str) -> MemoryFixture:
    """Parse fixture JSON while rejecting duplicate object keys."""

    try:
        value = json.loads(text, object_pairs_hook=_reject_duplicate_json_keys)
    except json.JSONDecodeError as exc:
        raise ValueError("memory fixture must be valid JSON") from exc
    if not isinstance(value, dict):
        raise TypeError("memory fixture must be a JSON object")
    return memory_fixture_from_dict(value)


def parse_memory_evidence_manifest_json(
    text: str,
    *,
    fixture: MemoryFixture,
) -> MemoryEvidenceManifest:
    """Validate the public capture receipts and bind them to the fixture."""

    try:
        value = json.loads(text, object_pairs_hook=_reject_duplicate_json_keys)
    except json.JSONDecodeError as exc:
        raise ValueError("memory evidence manifest must be valid JSON") from exc
    manifest = _require_dict(value, "memory evidence manifest")
    _require_exact_keys(
        manifest,
        {
            "schema_version",
            "fixture",
            "fixture_sha256",
            "capture_control",
            "fixed_reference_camera",
            "go2_capture_receipts",
            "privacy",
            "public_labels",
            "non_claims",
        },
        "memory evidence manifest",
    )
    if manifest["schema_version"] != MEMORY_EVIDENCE_MANIFEST_SCHEMA_VERSION:
        raise ValueError(f"unsupported evidence manifest schema: {manifest['schema_version']}")
    fixture_path = _require_nonempty_string(manifest["fixture"], "manifest.fixture")
    if fixture_path != MEMORY_FIXTURE_RELATIVE_PATH or PurePosixPath(fixture_path).is_absolute() or ".." in PurePosixPath(fixture_path).parts:
        raise ValueError("manifest fixture must be the checked repository-relative fixture")
    fixture_sha = _require_sha256(manifest["fixture_sha256"], "manifest.fixture_sha256")
    if fixture_sha != fixture.fixture_sha256:
        raise ValueError("manifest fixture_sha256 does not match the checked fixture")
    if manifest["capture_control"] != "TELEOP":
        raise ValueError("manifest capture_control must be TELEOP")
    if manifest["fixed_reference_camera"] != "Gemini 2 independent reference, not mounted on Go2":
        raise ValueError("unexpected fixed reference camera label")

    receipts = _require_dict(manifest["go2_capture_receipts"], "go2_capture_receipts")
    _require_exact_keys(receipts, {"pass_before", "pass_after"}, "go2_capture_receipts")
    parsed_receipts = {
        pass_id: _validate_capture_receipt(receipts[pass_id], name=f"go2_capture_receipts.{pass_id}")
        for pass_id in ("pass_before", "pass_after")
    }
    for field in ("raw_database_sha256", "replay_database_sha256", "highlight_database_sha256"):
        if parsed_receipts["pass_before"][field] == parsed_receipts["pass_after"][field]:
            raise ValueError(f"before and after {field} receipts must differ")

    privacy = _require_dict(manifest["privacy"], "manifest.privacy")
    _require_exact_keys(
        privacy,
        {"raw_images_included", "raw_databases_included", "absolute_paths_included"},
        "manifest.privacy",
    )
    if privacy != {
        "raw_images_included": False,
        "raw_databases_included": False,
        "absolute_paths_included": False,
    }:
        raise ValueError("evidence manifest must exclude raw private artifacts and absolute paths")
    public_labels = _require_string_list(manifest["public_labels"], "public_labels")
    if public_labels != [
        "POST-RUN POLICY SIMULATION — built from recorded receipts; these were not robot-runtime transitions",
        "RECORDED GO2 ONBOARD-SLAM POINT CLOUD, shown in post-run replay — not raw L1 LiDAR",
        "SEMANTIC FRAMES — Gemini 2 fixed independent reference, separate from Go2 capture receipts",
    ]:
        raise ValueError("evidence manifest public labels do not match the reviewed boundary")
    non_claims = _require_string_list(manifest["non_claims"], "non_claims")
    required_non_claims = {
        "database hashes are receipts, not public raw-data verification",
        "no sensor calibration or hardware synchronization proof",
        "no autonomous Go2 control",
        "no independently verified Qwen accuracy",
    }
    if set(non_claims) != required_non_claims or len(non_claims) != len(required_non_claims):
        raise ValueError("evidence manifest non-claims do not match the reviewed boundary")
    _reject_private_text(canonical_json(manifest), label="evidence manifest")
    return MemoryEvidenceManifest(
        manifest_sha256=sha256_canonical(manifest),
        fixture_sha256=fixture_sha,
    )


def memory_fixture_from_dict(value: dict[str, Any]) -> MemoryFixture:
    """Parse the checked fixture without accepting extra or host-specific data."""

    _require_exact_keys(
        value,
        {
            "schema",
            "fixture_id",
            "privacy",
            "coordinate_space",
            "observations",
            "observed_result",
            "expected_policy",
            "provenance",
        },
        "fixture",
    )
    if value["schema"] != MEMORY_FIXTURE_SCHEMA_VERSION:
        raise ValueError(f"unsupported fixture schema: {value['schema']}")
    fixture_id = _require_nonempty_string(value["fixture_id"], "fixture_id")
    if fixture_id != MEMORY_FIXTURE_ID:
        raise ValueError("unexpected fixture_id")
    privacy = _require_dict(value["privacy"], "privacy")
    _require_exact_keys(
        privacy,
        {"raw_images_included", "absolute_paths_included", "people_or_room_identifiers_included"},
        "privacy",
    )
    if privacy != {
        "raw_images_included": False,
        "absolute_paths_included": False,
        "people_or_room_identifiers_included": False,
    }:
        raise ValueError("fixture must contain only privacy-safe receipts")
    coordinate_space = value["coordinate_space"]
    if coordinate_space != MEMORY_COORDINATE_SPACE:
        raise ValueError(f"unsupported coordinate space: {coordinate_space}")

    observed_result = _require_dict(value["observed_result"], "observed_result")
    _require_exact_keys(
        observed_result,
        {
            "change",
            "reported_displacement_model_units",
            "ambiguous",
            "confidence_semantics",
            "measurement_caveat",
        },
        "observed_result",
    )
    if observed_result["change"] != "moved":
        raise ValueError("fixture change must be moved")
    reported_displacement = _require_nonnegative_int(
        observed_result["reported_displacement_model_units"],
        "reported_displacement_model_units",
    )
    if observed_result["ambiguous"] is not True:
        raise ValueError("fixture must preserve the recorded ambiguity")
    confidence_semantics = _require_nonempty_string(
        observed_result["confidence_semantics"],
        "confidence_semantics",
    )
    if confidence_semantics != MEMORY_CONFIDENCE_SEMANTICS:
        raise ValueError("unexpected memory confidence semantics")
    measurement_caveat = _require_nonempty_string(
        observed_result["measurement_caveat"],
        "measurement_caveat",
    )
    if measurement_caveat != MEMORY_MEASUREMENT_CAVEAT:
        raise ValueError("unexpected measurement caveat")

    expected_policy = _require_dict(value["expected_policy"], "expected_policy")
    _require_exact_keys(
        expected_policy,
        {"memory_state", "action", "reverify_required", "motion_executed"},
        "expected_policy",
    )
    if expected_policy != {
        "memory_state": "PROVISIONAL",
        "action": "HOLD",
        "reverify_required": True,
        "motion_executed": False,
    }:
        raise ValueError("fixture policy must retain PROVISIONAL, HOLD, and request re-verification")

    provenance_value = _require_dict(value["provenance"], "provenance")
    provenance_keys = {
        "proposer_recorded",
        "tier_recorded",
        "trust_label_recorded",
        "memory_events_sha256",
        "memory_snapshot_sha256",
        "event_chain_head",
    }
    _require_exact_keys(provenance_value, provenance_keys, "provenance")
    if provenance_value["proposer_recorded"] != "cloud:qwen3-vl-flash":
        raise ValueError("unexpected recorded proposer")
    if provenance_value["tier_recorded"] != "cloud":
        raise ValueError("unexpected recorded tier")
    if provenance_value["trust_label_recorded"] != "verified":
        raise ValueError("unexpected recorded trust label")
    provenance: dict[str, str] = {}
    for key in sorted(provenance_keys):
        item = _require_nonempty_string(provenance_value[key], f"provenance.{key}")
        if key.endswith("sha256") or key == "event_chain_head":
            _require_sha256(item, f"provenance.{key}")
        provenance[key] = item

    observations = value["observations"]
    if not isinstance(observations, list) or len(observations) != 2:
        raise ValueError("observations must contain exactly two items")
    baseline = _observation_from_fixture_item(
        observations[0],
        expected_pass_id="pass_before",
        coordinate_space=coordinate_space,
        model=MEMORY_RECORDED_MODEL,
    )
    conflict = _observation_from_fixture_item(
        observations[1],
        expected_pass_id="pass_after",
        coordinate_space=coordinate_space,
        model=MEMORY_RECORDED_MODEL,
    )
    if baseline.source_frame_sha256 == conflict.source_frame_sha256:
        raise ValueError("baseline and conflicting frames must differ")
    if baseline.observation_sha256 == conflict.observation_sha256:
        raise ValueError("baseline and conflicting observations must differ")
    if baseline.object_id != conflict.object_id:
        raise ValueError("baseline and conflicting observations must use the same stable object_id")
    if baseline.label != conflict.label:
        raise ValueError("baseline and conflicting observations must use the same label")
    _validate_checked_observation(baseline)
    _validate_checked_observation(conflict)
    computed_displacement = _reported_displacement(baseline.reported_bbox, conflict.reported_bbox)
    if reported_displacement != computed_displacement:
        raise ValueError("reported displacement does not match the two model-coordinate boxes")
    _reject_private_text(canonical_json(value), label="memory fixture")

    return MemoryFixture(
        fixture_id=fixture_id,
        fixture_sha256=sha256_canonical(value),
        baseline=baseline,
        conflict=conflict,
        reported_change="moved",
        reported_displacement=reported_displacement,
        ambiguous=True,
        measurement_caveat=measurement_caveat,
        retained_memory_state="PROVISIONAL",
        policy_action="HOLD",
        reverify_required=True,
        motion_executed=False,
        provenance=provenance,
    )


def build_qwenguard_memory_replay(
    *,
    run_id: str,
    memory_id: str,
    baseline: MemoryObservation,
    conflict: MemoryObservation,
    source_mode: str = "fixture",
) -> DecisionTrace:
    """Build the reviewed four-step memory policy trace."""

    _require_nonempty_string(run_id, "run_id")
    _require_nonempty_string(memory_id, "memory_id")
    if source_mode != "fixture":
        raise ValueError("this checked replay supports fixture source mode only")
    if baseline.source_frame_sha256 == conflict.source_frame_sha256:
        raise ValueError("baseline and conflicting frames must differ")
    if baseline.observation_sha256 == conflict.observation_sha256:
        raise ValueError("baseline and conflicting observations must differ")
    if baseline.object_id != conflict.object_id or baseline.object_id != memory_id:
        raise ValueError("memory_id must match the stable object_id in both observations")
    if baseline.label != conflict.label:
        raise ValueError("baseline and conflicting observations must use the same label")
    _validate_checked_observation(baseline)
    _validate_checked_observation(conflict)

    events: list[DecisionEvent] = []
    prev_sha = GENESIS_SHA
    for tick, (from_state, to_state, policy_phase, trigger, decision) in enumerate(_TRANSITIONS):
        observation = baseline if tick == 0 else conflict
        mode = "degraded" if policy_phase == "HOLD" else source_mode
        event = DecisionEvent(
            tick=tick,
            actor_id="edge-memory-policy",
            mode=mode,
            intent=_MEMORY_INTENT,
            decision=decision,
            reason=_reason_for_phase(policy_phase),
            command={
                "type": "qwenguard_memory_transition",
                "memory_id": memory_id,
                "from_state": from_state,
                "to_state": to_state,
                "policy_phase": policy_phase,
                "trigger": trigger,
                "source_frame_sha256": observation.source_frame_sha256,
                "observation_sha256": observation.observation_sha256,
                "motor_authority": "none",
                "motion_executed": False,
            },
            perception=observation.to_perception(event_id=f"memory-observation-{tick:04d}"),
            prev_sha=prev_sha,
        ).with_computed_sha()
        events.append(event)
        prev_sha = event.sha256
    trace = DecisionTrace(run_id=run_id, events=tuple(events)).with_computed_summary()
    verify_qwenguard_memory_replay(trace)
    return trace


def verify_qwenguard_memory_replay(trace: DecisionTrace) -> str:
    """Verify both the hash chain and the memory-policy semantics."""

    summary_sha = verify_trace(trace)
    if len(trace.events) != 4:
        raise ValueError("memory replay must contain exactly four events")
    if any(not isinstance(event.command, dict) for event in trace.events):
        raise TypeError("memory replay command must be an object")
    source_mode = trace.events[0].mode
    if source_mode != "fixture":
        raise ValueError("memory replay source mode must be fixture")
    expected_modes = (source_mode, source_mode, "degraded", source_mode)
    memory_id = trace.events[0].command.get("memory_id")
    _require_nonempty_string(memory_id, "memory_id")
    for tick, (event, transition, expected_mode) in enumerate(
        zip(trace.events, _TRANSITIONS, expected_modes)
    ):
        from_state, to_state, policy_phase, trigger, decision = transition
        if isinstance(event.tick, bool) or event.tick != tick:
            raise ValueError("memory replay ticks must be 0 through 3")
        if event.actor_id != "edge-memory-policy":
            raise ValueError("unexpected memory replay actor")
        if event.intent != _MEMORY_INTENT:
            raise ValueError("unexpected memory replay intent")
        if event.reason != _reason_for_phase(policy_phase):
            raise ValueError("unexpected memory replay reason")
        if event.mode != expected_mode:
            raise ValueError("unexpected memory replay mode sequence")
        if event.decision != decision:
            raise ValueError("unexpected memory replay decision sequence")
        if set(event.command) != MEMORY_COMMAND_KEYS:
            raise ValueError("memory transition command keys do not match the reviewed contract")
        expected_values = {
            "type": "qwenguard_memory_transition",
            "memory_id": memory_id,
            "from_state": from_state,
            "to_state": to_state,
            "policy_phase": policy_phase,
            "trigger": trigger,
            "motor_authority": "none",
            "motion_executed": False,
        }
        for key, expected in expected_values.items():
            if event.command.get(key) != expected:
                raise ValueError(f"unexpected memory transition value for {key}")
        source_frame_sha = event.command["source_frame_sha256"]
        observation_sha = event.command["observation_sha256"]
        _require_sha256(source_frame_sha, "source_frame_sha256")
        _require_sha256(observation_sha, "observation_sha256")
        if event.perception.source != f"sha256://{source_frame_sha}":
            raise ValueError("perception source does not match its frame receipt")
        if event.perception.event_id != f"memory-observation-{tick:04d}":
            raise ValueError("unexpected memory perception event id")
        if event.perception.label != f"{MEMORY_TARGET_LABEL}_observation_receipt":
            raise ValueError("unexpected memory perception label")
        if event.perception.model != MEMORY_RECORDED_MODEL:
            raise ValueError("unexpected memory perception model")
        expected_memory_confidence = 500 if tick == 0 else 750
        if event.perception.score_milli != expected_memory_confidence:
            raise ValueError("unexpected recorded Memory2 belief confidence")
        if (event.perception.image_width, event.perception.image_height) != MEMORY_RECORDED_IMAGE_SIZE:
            raise ValueError("unexpected memory perception dimensions")
        if isinstance(event.perception.image_width, bool) or isinstance(event.perception.image_height, bool):
            raise TypeError("memory perception dimensions must be integers, not booleans")
        if any(isinstance(value, bool) for value in event.perception.bbox_2d_norm_1000):
            raise TypeError("memory normalized bbox values must not be booleans")
        if any(isinstance(value, bool) for value in event.perception.bbox_2d_px):
            raise TypeError("memory pixel bbox values must not be booleans")
        if event.perception.bbox_2d_norm_1000 != (0, 0, 1000, 1000):
            raise ValueError("memory replay must not claim a calibrated object bbox")
        if event.perception.bbox_2d_px != (0, 0, event.perception.image_width, event.perception.image_height):
            raise ValueError("memory replay perception must cover the source frame")
        if event.command["motion_executed"] is not False:
            raise ValueError("memory replay must not execute motion")
        if event.command["motor_authority"] != "none":
            raise ValueError("memory replay must not have motor authority")
        if event.command["type"] == "physical_action_intent":
            raise ValueError("physical action intents are forbidden in memory replay")

    baseline = trace.events[0].command
    conflict = trace.events[1].command
    if baseline["source_frame_sha256"] == conflict["source_frame_sha256"]:
        raise ValueError("baseline and conflicting frames must differ")
    if baseline["observation_sha256"] == conflict["observation_sha256"]:
        raise ValueError("baseline and conflicting observations must differ")
    for event in trace.events[2:]:
        if event.command["source_frame_sha256"] != conflict["source_frame_sha256"]:
            raise ValueError("HOLD and REVERIFY must retain the conflicting frame receipt")
        if event.command["observation_sha256"] != conflict["observation_sha256"]:
            raise ValueError("HOLD and REVERIFY must retain the conflicting observation receipt")
    canonical_json(trace.to_dict())
    return summary_sha


def build_memory_replay_report(
    *,
    fixture: MemoryFixture,
    evidence_manifest: MemoryEvidenceManifest,
    trace: DecisionTrace,
) -> dict[str, Any]:
    """Build the deterministic judge-facing report for a verified replay."""

    summary_sha = verify_qwenguard_memory_replay(trace)
    _verify_trace_fixture_binding(trace=trace, fixture=fixture)
    memory_state_sequence = [event.command["to_state"] for event in trace.events]
    policy_sequence = [event.command["policy_phase"] for event in trace.events]
    retained_memory_state = memory_state_sequence[-1]
    if retained_memory_state != fixture.retained_memory_state:
        raise ValueError("trace final memory state does not match the fixture policy")
    if policy_sequence != list(MEMORY_POLICY_SEQUENCE):
        raise ValueError("trace policy sequence does not match the reviewed fixture policy")
    if evidence_manifest.fixture_sha256 != fixture.fixture_sha256:
        raise ValueError("evidence manifest does not bind to the fixture")
    return {
        "schema_version": MEMORY_REPORT_SCHEMA_VERSION,
        "outcome": "GO",
        "execution_context": "post_run_policy_simulation",
        "robot_runtime_transitions": False,
        "semantic_frame_source": "Gemini 2 fixed independent reference, not mounted on Go2",
        "go2_capture_receipts_role": "separate teleoperated context receipts, not the semantic frame source",
        "fixture_id": fixture.fixture_id,
        "fixture_sha256": fixture.fixture_sha256,
        "evidence_manifest_sha256": evidence_manifest.manifest_sha256,
        "policy_sequence": policy_sequence,
        "memory_state_sequence": memory_state_sequence,
        "retained_memory_state": retained_memory_state,
        "policy_action": fixture.policy_action,
        "reverify_status": "REQUESTED",
        "reverify_required": fixture.reverify_required,
        "motion_executed": fixture.motion_executed,
        "trace_summary_sha": summary_sha,
        "event_receipts": [event.sha256 for event in trace.events],
        "source_frame_receipts": [
            fixture.baseline.source_frame_sha256,
            fixture.conflict.source_frame_sha256,
        ],
        "observation_receipts": [
            fixture.baseline.observation_sha256,
            fixture.conflict.observation_sha256,
        ],
        "observed_result": {
            "change": fixture.reported_change,
            "reported_displacement_model_units": fixture.reported_displacement,
            "ambiguous": fixture.ambiguous,
            "confidence_semantics": MEMORY_CONFIDENCE_SEMANTICS,
            "memory_confidence_milli": {
                "pass_before": fixture.baseline.memory_confidence_milli,
                "pass_after": fixture.conflict.memory_confidence_milli,
            },
            "measurement_caveat": fixture.measurement_caveat,
        },
        "provenance_receipts": {
            "memory_events_sha256": fixture.provenance["memory_events_sha256"],
            "memory_snapshot_sha256": fixture.provenance["memory_snapshot_sha256"],
            "event_chain_head": fixture.provenance["event_chain_head"],
        },
        "pass_conditions": {
            "trace_hash_chain_verified": True,
            "policy_and_memory_sequences_verified": True,
            "ambiguous_change_remains_provisional": True,
            "hold_has_no_motor_authority": True,
            "raw_images_excluded": True,
        },
        "non_claims": [
            "post-run semantic fixture replay only",
            "no motor action or autonomous Go2 control",
            "no human-labeled ground truth",
            "no calibrated displacement or validated 3D grounding",
            "recorded internal trust labels are not independent accuracy verification",
            "policy phases are a post-run simulation, not robot-runtime transitions",
        ],
    }


def build_memory_replay_response(
    *,
    fixture: MemoryFixture,
    evidence_manifest: MemoryEvidenceManifest,
    trace: DecisionTrace,
) -> dict[str, Any]:
    """Build the exact fixed endpoint response checked by the ECS collector."""

    report = build_memory_replay_report(
        fixture=fixture,
        evidence_manifest=evidence_manifest,
        trace=trace,
    )
    return {
        "status": "ok",
        "schema_version": "qwenguard-memory-replay-response.v1",
        "source_mode": "fixture",
        "execution_context": "post_run_policy_simulation",
        "robot_runtime_transitions": False,
        "semantic_frame_source": report["semantic_frame_source"],
        "go2_capture_receipts_role": report["go2_capture_receipts_role"],
        "policy_sequence": report["policy_sequence"],
        "memory_state_sequence": report["memory_state_sequence"],
        "retained_memory_state": report["retained_memory_state"],
        "policy_action": report["policy_action"],
        "reverify_status": report["reverify_status"],
        "event_receipts": report["event_receipts"],
        "trace_summary_sha": report["trace_summary_sha"],
        "motion_executed": False,
        "fixture_sha256": fixture.fixture_sha256,
        "evidence_manifest_sha256": evidence_manifest.manifest_sha256,
        "trace": trace.to_dict(),
    }


def _observation_from_fixture_item(
    value: Any,
    *,
    expected_pass_id: str,
    coordinate_space: str,
    model: str,
) -> MemoryObservation:
    item = _require_dict(value, "observation")
    _require_exact_keys(item, {"pass_id", "frame", "detection"}, "observation")
    if item["pass_id"] != expected_pass_id:
        raise ValueError(f"expected pass_id {expected_pass_id}")
    frame = _require_dict(item["frame"], "frame")
    _require_exact_keys(frame, {"sha256", "width", "height"}, "frame")
    detection = _require_dict(item["detection"], "detection")
    _require_exact_keys(
        detection,
        {"object_id", "label", "bbox", "memory_confidence_milli"},
        "detection",
    )
    bbox_value = detection["bbox"]
    if not isinstance(bbox_value, list) or len(bbox_value) != 4:
        raise ValueError("detection bbox must contain four integers")
    reported_bbox = tuple(bbox_value)
    object_id = _require_nonempty_string(detection["object_id"], "object_id")
    memory_confidence_milli = _require_int(
        detection["memory_confidence_milli"],
        "memory_confidence_milli",
    )
    return MemoryObservation(
        observation_id=f"{expected_pass_id}:{object_id}",
        object_id=object_id,
        source_frame_sha256=_require_sha256(frame["sha256"], "frame.sha256"),
        observation_sha256=sha256_canonical(item),
        image_width=_require_positive_int(frame["width"], "frame.width"),
        image_height=_require_positive_int(frame["height"], "frame.height"),
        label=_require_nonempty_string(detection["label"], "detection.label"),
        reported_bbox=reported_bbox,  # type: ignore[arg-type]
        coordinate_space=coordinate_space,
        memory_confidence_milli=memory_confidence_milli,
        model=model,
    )


def _verify_trace_fixture_binding(*, trace: DecisionTrace, fixture: MemoryFixture) -> None:
    expected = (
        (trace.events[0], fixture.baseline),
        (trace.events[1], fixture.conflict),
    )
    for event, observation in expected:
        if event.command["memory_id"] != observation.object_id:
            raise ValueError("trace memory_id does not match the checked fixture")
        if event.command["source_frame_sha256"] != observation.source_frame_sha256:
            raise ValueError("trace frame receipt does not match the checked fixture")
        if event.command["observation_sha256"] != observation.observation_sha256:
            raise ValueError("trace observation receipt does not match the checked fixture")


def _reason_for_phase(policy_phase: str) -> str:
    return {
        "VERIFIED": "recorded baseline receipt initializes the reviewed belief",
        "PROVISIONAL": "ambiguous change remains provisional pending another observation",
        "HOLD": "local trust policy blocks action while the change is uncertain",
        "REVERIFY": "policy requests a new independent observation without granting motion",
    }[policy_phase]


def _validate_checked_observation(observation: MemoryObservation) -> None:
    if observation.object_id != MEMORY_TARGET_OBJECT_ID:
        raise ValueError("unexpected stable object_id")
    if observation.label != MEMORY_TARGET_LABEL:
        raise ValueError("unexpected memory target label")
    if observation.model != MEMORY_RECORDED_MODEL:
        raise ValueError("unexpected recorded model")
    pass_id = observation.observation_id.split(":", 1)[0]
    expected_confidence = MEMORY_RECORDED_CONFIDENCE_BY_PASS.get(pass_id)
    if observation.memory_confidence_milli != expected_confidence:
        raise ValueError("unexpected recorded Memory2 belief confidence")
    if (observation.image_width, observation.image_height) != MEMORY_RECORDED_IMAGE_SIZE:
        raise ValueError("unexpected recorded image size")


def _reject_private_text(serialized: str, *, label: str) -> None:
    if _SECRET_PATTERN.search(serialized):
        raise ValueError(f"{label} contains secret-like material")
    if any(marker in serialized for marker in ("/Users/", "/home/", "C:\\Users\\", "file://")):
        raise ValueError(f"{label} contains an absolute or host-specific path")


def _validate_capture_receipt(value: Any, *, name: str) -> dict[str, Any]:
    receipt = _require_dict(value, name)
    _require_exact_keys(
        receipt,
        {"raw_database_sha256", "replay_database_sha256", "highlight_database_sha256", "recorded_rows"},
        name,
    )
    result: dict[str, Any] = {}
    for field in ("raw_database_sha256", "replay_database_sha256", "highlight_database_sha256"):
        result[field] = _require_sha256(receipt[field], f"{name}.{field}")
    rows = _require_dict(receipt["recorded_rows"], f"{name}.recorded_rows")
    _require_exact_keys(rows, {"color_image", "lidar", "odom", "tf"}, f"{name}.recorded_rows")
    result["recorded_rows"] = {
        key: _require_positive_int(rows[key], f"{name}.recorded_rows.{key}")
        for key in ("color_image", "lidar", "odom", "tf")
    }
    return result


def _require_dict(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be an object")
    return value


def _require_exact_keys(value: dict[str, Any], expected: set[str], name: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{name} keys do not match the reviewed schema")


def _require_nonempty_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"{name} must be a non-empty string")
    if any(ord(char) < 32 for char in value):
        raise ValueError(f"{name} must not contain control characters")
    return value


def _require_string_list(value: Any, name: str) -> list[str]:
    if not isinstance(value, list):
        raise TypeError(f"{name} must be a list")
    return [_require_nonempty_string(item, f"{name}[{index}]") for index, item in enumerate(value)]


def _require_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    return value


def _require_positive_int(value: Any, name: str) -> int:
    parsed = _require_int(value, name)
    if parsed <= 0:
        raise ValueError(f"{name} must be positive")
    return parsed


def _require_nonnegative_int(value: Any, name: str) -> int:
    parsed = _require_int(value, name)
    if parsed < 0:
        raise ValueError(f"{name} must be non-negative")
    return parsed


def _require_sha256(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{name} must be a lowercase 64-character hex string")
    return value


def _validate_reported_bbox(value: tuple[int, int, int, int]) -> None:
    if not isinstance(value, tuple) or len(value) != 4:
        raise TypeError("reported_bbox must contain four integers")
    if any(isinstance(item, bool) or not isinstance(item, int) for item in value):
        raise TypeError("reported_bbox values must be integers")
    x1, y1, x2, y2 = value
    if min(value) < 0 or max(value) > 1000 or x1 >= x2 or y1 >= y2:
        raise ValueError("reported_bbox must stay within the recorded 0-1000 domain and have positive area")


def _reported_displacement(
    baseline_bbox: tuple[int, int, int, int],
    conflict_bbox: tuple[int, int, int, int],
) -> int:
    baseline_center = (
        (baseline_bbox[0] + baseline_bbox[2]) // 2,
        (baseline_bbox[1] + baseline_bbox[3]) // 2,
    )
    conflict_center = (
        (conflict_bbox[0] + conflict_bbox[2]) // 2,
        (conflict_bbox[1] + conflict_bbox[3]) // 2,
    )
    dx = conflict_center[0] - baseline_center[0]
    dy = conflict_center[1] - baseline_center[1]
    return isqrt(dx * dx + dy * dy)


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value
