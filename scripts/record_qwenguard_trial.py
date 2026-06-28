#!/usr/bin/env python3
"""Record one measured QwenGuard physical trial with a bound DecisionTrace."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
import sys
from typing import Any

from accountable_swarm.qwen.bbox import rescale_norm_1000_bbox
from accountable_swarm.qwenguard.evaluator import EvaluationResult
from accountable_swarm.qwenguard.outcome_gate import GateDecision, GATE_DECISIONS, RISK_LEVELS
from accountable_swarm.qwenguard.selector import RELATIONS, SelectorResult
from accountable_swarm.qwenguard.trial import (
    CLOUD_MODES,
    GATE_MODES,
    OUTCOMES,
    POLICIES,
    SELECTOR_MODES,
    TrialRecord,
    trial_csv_header,
)
from accountable_swarm.trace.models import (
    GENESIS_SHA,
    DecisionEvent,
    DecisionTrace,
    PerceptionEvent,
    canonical_json,
    verify_trace,
)


REPORT_SCHEMA_VERSION = "qwenguard-trial-record-report.v1"
ISSUE_URL = "https://github.com/omarespejel/accountable-swarm/issues/103"
UMBRELLA_ISSUE_URL = "https://github.com/omarespejel/accountable-swarm/issues/95"
DEFAULT_TRACE_DIR = Path("runs/physical/qwenguard_trials/traces")
DEFAULT_CSV_OUT = Path("runs/physical/qwenguard_trials/trial_results.csv")
DEFAULT_TASK = "pick the red cube left of the green cube and place it in the bin"
DEFAULT_TARGET_LABEL = "red cube left of green cube"
CONTROL_LABELS = {"AUTONOMOUS", "TELEOP", "SCRIPTED"}
ATTEMPTED_OUTCOMES = {"success", "wrong_object", "missed_grasp", "dropped_object", "not_in_bin"}
NO_MOTION_OUTCOMES = {"cloud_hold", "unsafe_hold", "uncertain"}
FAILURE_TYPE_BY_OUTCOME = {
    "success": "none",
    "wrong_object": "wrong_object",
    "missed_grasp": "missed_grasp",
    "dropped_object": "dropped_object",
    "not_in_bin": "not_in_bin",
    "unsafe_hold": "unsafe_scene",
    "cloud_hold": "cloud_unavailable",
    "uncertain": "uncertain_view",
}
EVALUATOR_OUTCOME_BY_TRIAL_OUTCOME = {
    "success": "success",
    "wrong_object": "failure",
    "missed_grasp": "failure",
    "dropped_object": "failure",
    "not_in_bin": "failure",
    "unsafe_hold": "failure",
    "cloud_hold": "uncertain",
    "uncertain": "uncertain",
}
SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"Authorization:[ \t]*Bearer[ \t]+(?!<redacted>)\S+", re.IGNORECASE),
    re.compile(r"ALIBABA_API_KEY[ \t]*=[ \t]*\S+", re.IGNORECASE),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"gh(?:p|o|u|s|r)_[A-Za-z0-9_]{12,}"),
    re.compile(r"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9._-]{20,}"),
)
RAW_FRAME_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"data:image/[A-Za-z0-9.+-]+;base64,", re.IGNORECASE),
    re.compile(r"base64,[A-Za-z0-9+/]{80,}={0,2}", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{160,}={0,2}(?![A-Za-z0-9+/])"),
)
TEXT_LIMITS = {
    "trial_id": 81,
    "task_instruction": 240,
    "object_layout_id": 120,
    "operator_label": 120,
    "qwen_eval_label": 120,
    "notes": 240,
    "target_mark_id": 32,
    "target_label": 120,
    "source_ref": 160,
    "selector_evidence": 512,
    "evaluator_evidence": 512,
    "trace_dir": 240,
    "csv_out": 240,
    "report_out": 240,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trial-id", required=True)
    parser.add_argument("--task-instruction", default=DEFAULT_TASK)
    parser.add_argument("--object-layout-id", default="qwenguard-cubes-layout-001")
    parser.add_argument("--selector-mode", choices=sorted(SELECTOR_MODES), default="qwen")
    parser.add_argument("--gate-mode", choices=sorted(GATE_MODES), default="on")
    parser.add_argument("--policy", choices=sorted(POLICIES), default="act")
    parser.add_argument("--cloud-mode", choices=sorted(CLOUD_MODES), default="online")
    parser.add_argument("--outcome", choices=sorted(OUTCOMES), required=True)
    parser.add_argument("--operator-label", default="")
    parser.add_argument("--qwen-eval-label", default="")
    parser.add_argument("--notes", default="")
    parser.add_argument("--control-label", choices=sorted(CONTROL_LABELS), default="TELEOP")
    parser.add_argument("--motion-executed", choices=("true", "false"), default="false")
    parser.add_argument("--gate-decision", choices=sorted(GATE_DECISIONS), default="ALLOW")
    parser.add_argument("--predicted-success-milli", type=int, default=800)
    parser.add_argument("--risk-level", choices=sorted(RISK_LEVELS), default="medium")
    parser.add_argument("--target-mark-id", default="A")
    parser.add_argument("--target-label", default=DEFAULT_TARGET_LABEL)
    parser.add_argument("--relation", choices=sorted(RELATIONS), default="left_of")
    parser.add_argument("--reference-mark-id", action="append", default=None)
    parser.add_argument("--selector-confidence-milli", type=int, default=900)
    parser.add_argument("--evaluator-confidence-milli", type=int, default=800)
    parser.add_argument("--selector-evidence", default="Qwen selected the marked relational cube target.")
    parser.add_argument("--evaluator-evidence", default="")
    parser.add_argument("--image-width", type=int, default=640)
    parser.add_argument("--image-height", type=int, default=480)
    parser.add_argument("--bbox-norm-1000", default="150,390,315,690")
    parser.add_argument("--source-ref", default="operator://qwenguard-physical-trial")
    parser.add_argument("--trace-dir", type=Path, default=DEFAULT_TRACE_DIR)
    parser.add_argument("--csv-out", type=Path, default=DEFAULT_CSV_OUT)
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    try:
        repo_root = _find_repo_root(Path.cwd())
        trace_dir = _repo_path(repo_root, args.trace_dir)
        csv_out = _repo_path(repo_root, args.csv_out)
        report_out = _repo_path(
            repo_root,
            args.report_out if args.report_out is not None else Path("runs/physical/qwenguard_trials/reports") / f"{args.trial_id}.json",
        )
        _validate_text_inputs(args)
        _validate_trial_semantics(args)
        reference_mark_ids = _normalize_reference_mark_ids(args.reference_mark_id, relation=args.relation)
        bbox = _parse_bbox(args.bbox_norm_1000)
        trace = build_trial_trace(
            trial_id=args.trial_id,
            task_instruction=args.task_instruction,
            source_ref=args.source_ref,
            image_width=args.image_width,
            image_height=args.image_height,
            bbox_norm_1000=bbox,
            target_mark_id=args.target_mark_id,
            target_label=args.target_label,
            relation=args.relation,
            reference_mark_ids=reference_mark_ids,
            selector_mode=args.selector_mode,
            selector_confidence_milli=args.selector_confidence_milli,
            selector_evidence=args.selector_evidence,
            gate_decision=args.gate_decision,
            predicted_success_milli=args.predicted_success_milli,
            risk_level=args.risk_level,
            gate_mode=args.gate_mode,
            policy=args.policy,
            cloud_mode=args.cloud_mode,
            control_label=args.control_label,
            motion_executed=args.motion_executed == "true",
            outcome=args.outcome,
            evaluator_confidence_milli=args.evaluator_confidence_milli,
            evaluator_evidence=args.evaluator_evidence or _default_evaluator_evidence(args.outcome),
        )
        summary_sha = verify_trace(trace)
        trial_record = TrialRecord(
            trial_id=args.trial_id,
            task_instruction=args.task_instruction,
            object_layout_id=args.object_layout_id,
            selector_mode=args.selector_mode,
            gate_mode=args.gate_mode,
            policy=args.policy,
            cloud_mode=args.cloud_mode,
            outcome=args.outcome,
            operator_label=args.operator_label or args.outcome,
            qwen_eval_label=args.qwen_eval_label or _qwen_eval_label(args.outcome),
            trace_summary_sha=summary_sha,
            notes=args.notes,
        )
        trace_path = trace_dir / f"{args.trial_id}.json"
    except ValueError as exc:
        print(f"qwenguard trial record failed: {exc}", file=sys.stderr)
        return 2

    report = _report(
        repo_root=repo_root,
        trace_path=trace_path,
        csv_out=csv_out,
        report_out=report_out,
        trial_record=trial_record,
        control_label=args.control_label,
        motion_executed=args.motion_executed == "true",
    )
    if _contains_secret_material(canonical_json(report)):
        print("qwenguard trial record failed: report would contain secret-like material", file=sys.stderr)
        return 2
    try:
        _write_outputs(
            repo_root=repo_root,
            trace=trace,
            trace_path=trace_path,
            csv_out=csv_out,
            report_out=report_out,
            report=report,
            trial_record=trial_record,
            overwrite=args.overwrite,
        )
    except ValueError as exc:
        print(f"qwenguard trial record failed: {exc}", file=sys.stderr)
        return 2

    print("outcome GO")
    print(f"trace_summary_sha {trial_record.trace_summary_sha}")
    print(f"trace {_display_path(repo_root, trace_path)}")
    print(f"csv {_display_path(repo_root, csv_out)}")
    print(f"report {_display_path(repo_root, report_out)}")
    return 0


def build_trial_trace(
    *,
    trial_id: str,
    task_instruction: str,
    source_ref: str,
    image_width: int,
    image_height: int,
    bbox_norm_1000: tuple[int, int, int, int],
    target_mark_id: str,
    target_label: str,
    relation: str,
    reference_mark_ids: tuple[str, ...],
    selector_mode: str,
    selector_confidence_milli: int,
    selector_evidence: str,
    gate_decision: str,
    predicted_success_milli: int,
    risk_level: str,
    gate_mode: str,
    policy: str,
    cloud_mode: str,
    control_label: str,
    motion_executed: bool,
    outcome: str,
    evaluator_confidence_milli: int,
    evaluator_evidence: str,
) -> DecisionTrace:
    selector = SelectorResult(
        target_mark_id=target_mark_id,
        target_label=target_label,
        bbox_2d_norm_1000=bbox_norm_1000,
        relation=relation,
        reference_mark_ids=reference_mark_ids,
        confidence_milli=selector_confidence_milli,
        evidence=selector_evidence,
    )
    gate = GateDecision(
        gate_decision=gate_decision,
        candidate_action="pick_place" if gate_decision in {"ALLOW", "RETRY"} else "hold",
        predicted_success_milli=predicted_success_milli,
        risk_level=risk_level,
        reasons=_gate_reasons(
            selector_mode=selector_mode,
            gate_mode=gate_mode,
            policy=policy,
            cloud_mode=cloud_mode,
            control_label=control_label,
            motion_executed=motion_executed,
        ),
    )
    evaluation = EvaluationResult(
        outcome=EVALUATOR_OUTCOME_BY_TRIAL_OUTCOME[outcome],
        failure_type=FAILURE_TYPE_BY_OUTCOME[outcome],
        confidence_milli=evaluator_confidence_milli,
        evidence=evaluator_evidence,
    )
    perception = PerceptionEvent(
        event_id=f"{trial_id}-perception",
        source=source_ref,
        image_width=image_width,
        image_height=image_height,
        label=target_label,
        bbox_2d_norm_1000=bbox_norm_1000,
        bbox_2d_px=rescale_norm_1000_bbox(bbox_norm_1000, image_width=image_width, image_height=image_height),
        model="qwen3-vl-flash" if selector_mode == "qwen" else f"{selector_mode}:operator-recorded",
        score_milli=selector_confidence_milli,
    )
    events: list[DecisionEvent] = []
    prev_sha = GENESIS_SHA
    select_event = DecisionEvent(
        tick=0,
        actor_id="edge-node-0",
        mode=_selector_event_mode(selector_mode=selector_mode, cloud_mode=cloud_mode),
        intent="select relational cube target from marked candidates",
        decision="SELECT" if cloud_mode == "online" else "HOLD",
        reason="operator-recorded selector result bound to trial trace",
        command=selector.to_command(),
        perception=perception,
        prev_sha=prev_sha,
    ).with_computed_sha()
    events.append(select_event)
    prev_sha = select_event.sha256

    gate_event = DecisionEvent(
        tick=1,
        actor_id="edge-node-0",
        mode="edge",
        intent="gate local pick-place action before motion authority",
        decision=gate.gate_decision,
        reason="operator-recorded local outcome gate decision",
        command=gate.to_command(),
        perception=perception,
        prev_sha=prev_sha,
    ).with_computed_sha()
    events.append(gate_event)
    prev_sha = gate_event.sha256

    action_decision = gate.gate_decision if gate.gate_decision in {"ALLOW", "RETRY"} else "HOLD"
    action_event = DecisionEvent(
        tick=2,
        actor_id="so101-act-policy",
        mode="edge" if action_decision in {"ALLOW", "RETRY"} else "degraded",
        intent="record physical action boundary and control label",
        decision=action_decision,
        reason="operator-attested physical action intent for measured trial",
        command={
            "type": "physical_action_intent",
            "requested_action": gate.candidate_action,
            "motion_executed": motion_executed,
            "control_label": control_label,
            "gate_decision": gate.gate_decision,
            "policy": policy,
            "operator_attested": True,
        },
        perception=perception,
        prev_sha=prev_sha,
    ).with_computed_sha()
    events.append(action_event)
    prev_sha = action_event.sha256

    eval_event = DecisionEvent(
        tick=3,
        actor_id="edge-node-0",
        mode="cloud" if cloud_mode == "online" else "degraded",
        intent="evaluate before-after physical outcome",
        decision="EVALUATE",
        reason="operator-recorded QwenGuard evaluator result",
        command=evaluation.to_command(),
        perception=perception,
        prev_sha=prev_sha,
    ).with_computed_sha()
    events.append(eval_event)

    return DecisionTrace(run_id=f"qwenguard-trial-{trial_id}", events=tuple(events)).with_computed_summary()


def _write_outputs(
    *,
    repo_root: Path,
    trace: DecisionTrace,
    trace_path: Path,
    csv_out: Path,
    report_out: Path,
    report: dict[str, Any],
    trial_record: TrialRecord,
    overwrite: bool,
) -> None:
    if len({trace_path.resolve(), csv_out.resolve(), report_out.resolve()}) != 3:
        raise ValueError("trace, CSV, and report outputs must be distinct paths")
    if trace_path.exists() and not overwrite:
        raise ValueError(f"trace already exists: {_display_path(repo_root, trace_path)}")
    if report_out.exists() and not overwrite:
        raise ValueError(f"report already exists: {_display_path(repo_root, report_out)}")
    trace_text = trace.to_canonical_json() + "\n"
    record_text = canonical_json(trial_record.to_dict())
    report_text = canonical_json(report) + "\n"
    csv_text = _updated_csv_text(csv_out=csv_out, trial_record=trial_record, overwrite=overwrite)
    joined = "\n".join(
        [
            trace_text,
            record_text,
            csv_text,
            report_text,
            _display_path(repo_root, trace_path),
            _display_path(repo_root, csv_out),
            _display_path(repo_root, report_out),
        ]
    )
    if _contains_secret_material(joined) or _contains_raw_frame_material(joined):
        raise ValueError("trial record would contain secret-like material")
    _atomic_write_texts(
        (
            (trace_path, trace_text),
            (csv_out, csv_text),
            (report_out, report_text),
        )
    )


def _updated_csv_text(*, csv_out: Path, trial_record: TrialRecord, overwrite: bool) -> str:
    header = trial_csv_header()
    rows = _updated_csv_rows(csv_out=csv_out, trial_record=trial_record, overwrite=overwrite)
    from io import StringIO

    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=header, extrasaction="raise")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def _updated_csv_rows(*, csv_out: Path, trial_record: TrialRecord, overwrite: bool) -> list[dict[str, str]]:
    header = trial_csv_header()
    rows: list[dict[str, str]] = []
    if csv_out.exists() and csv_out.stat().st_size > 0:
        with csv_out.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != header:
                raise ValueError("existing trial CSV header does not match TrialRecord schema")
            rows = [dict(row) for row in reader]
    duplicate_indexes = [index for index, row in enumerate(rows) if row.get("trial_id") == trial_record.trial_id]
    if duplicate_indexes and not overwrite:
        raise ValueError(f"trial_id already exists in CSV: {trial_record.trial_id}")
    new_row = {key: str(value) for key, value in trial_record.to_dict().items()}
    if duplicate_indexes:
        rows = [row for row in rows if row.get("trial_id") != trial_record.trial_id]
    rows.append(new_row)
    return rows


def _atomic_write_texts(paths_and_texts: tuple[tuple[Path, str], ...]) -> None:
    prepared: list[tuple[Path, Path]] = []
    try:
        for path, text in paths_and_texts:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = path.with_name(f".{path.name}.tmp")
            tmp_path.write_text(text, encoding="utf-8")
            prepared.append((tmp_path, path))
        for tmp_path, path in prepared:
            tmp_path.replace(path)
    except OSError:
        for tmp_path, _path in prepared:
            tmp_path.unlink(missing_ok=True)
        raise


def _report(
    *,
    repo_root: Path,
    trace_path: Path,
    csv_out: Path,
    report_out: Path,
    trial_record: TrialRecord,
    control_label: str,
    motion_executed: bool,
) -> dict[str, Any]:
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "outcome": "GO",
        "issue": ISSUE_URL,
        "umbrella_issue": UMBRELLA_ISSUE_URL,
        "trial_record": trial_record.to_dict(),
        "control_label": control_label,
        "motion_executed": motion_executed,
        "trace_path": _display_path(repo_root, trace_path),
        "csv_path": _display_path(repo_root, csv_out),
        "report_path": _display_path(repo_root, report_out),
        "trace_summary_sha": trial_record.trace_summary_sha,
        "pass_conditions": {
            "trace_json_prepared": True,
            "csv_row_prepared": True,
            "report_prepared": True,
            "trace_summary_bound_to_csv": True,
            "raw_float_free_trace": True,
            "secret_material_absent": True,
        },
        "non_claims": [
            "operator-recorded trial evidence, not automatic physical success proof",
            "not Qwen motor control",
            "not a safety, latency, or reliability claim",
            "not DimOS physical control",
        ],
    }


def _validate_text_inputs(args: argparse.Namespace) -> None:
    values = {
        "trial_id": args.trial_id,
        "task_instruction": args.task_instruction,
        "object_layout_id": args.object_layout_id,
        "operator_label": args.operator_label,
        "qwen_eval_label": args.qwen_eval_label,
        "notes": args.notes,
        "target_mark_id": args.target_mark_id,
        "target_label": args.target_label,
        "source_ref": args.source_ref,
        "selector_evidence": args.selector_evidence,
        "evaluator_evidence": args.evaluator_evidence,
        "trace_dir": str(args.trace_dir),
        "csv_out": str(args.csv_out),
        "report_out": str(args.report_out or ""),
    }
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,80}", args.trial_id):
        raise ValueError("trial_id must be ASCII and contain only letters, digits, dot, underscore, or dash")
    for name, value in values.items():
        limit = TEXT_LIMITS[name]
        if len(value) > limit:
            raise ValueError(f"{name} must be {limit} characters or fewer")
        if _has_control_chars(value):
            raise ValueError(f"{name} must not contain control characters")
        if _contains_secret_material(value):
            raise ValueError(f"{name} contains secret-like material")
        if _contains_raw_frame_material(value):
            raise ValueError(f"{name} contains raw-frame-like material")
    if args.image_width <= 0 or args.image_height <= 0:
        raise ValueError("image dimensions must be positive")
    _validate_milli("predicted_success_milli", args.predicted_success_milli)
    _validate_milli("selector_confidence_milli", args.selector_confidence_milli)
    _validate_milli("evaluator_confidence_milli", args.evaluator_confidence_milli)


def _validate_trial_semantics(args: argparse.Namespace) -> None:
    motion_executed = args.motion_executed == "true"
    if args.outcome == "cloud_hold":
        if args.cloud_mode != "degraded":
            raise ValueError("outcome=cloud_hold requires cloud_mode=degraded")
        if args.gate_decision != "HOLD":
            raise ValueError("outcome=cloud_hold requires gate_decision=HOLD")
        if motion_executed:
            raise ValueError("outcome=cloud_hold requires motion_executed=false")
        if args.predicted_success_milli != 0:
            raise ValueError("outcome=cloud_hold requires predicted_success_milli=0")
        if args.risk_level != "high":
            raise ValueError("outcome=cloud_hold requires risk_level=high")
    if args.gate_decision == "HOLD" and motion_executed:
        raise ValueError("gate_decision=HOLD requires motion_executed=false")
    if args.outcome == "success":
        if not motion_executed:
            raise ValueError("outcome=success requires motion_executed=true")
        if args.gate_decision not in {"ALLOW", "RETRY"}:
            raise ValueError("outcome=success requires gate_decision=ALLOW or RETRY")
    if args.outcome in ATTEMPTED_OUTCOMES - {"success"}:
        if not motion_executed:
            raise ValueError(f"outcome={args.outcome} requires motion_executed=true")
        if args.gate_decision not in {"ALLOW", "RETRY"}:
            raise ValueError(f"outcome={args.outcome} requires gate_decision=ALLOW or RETRY")
    if not motion_executed and args.outcome not in NO_MOTION_OUTCOMES:
        raise ValueError(f"outcome={args.outcome} requires motion_executed=true")
    if args.outcome == "unsafe_hold":
        if args.gate_decision != "HOLD":
            raise ValueError("outcome=unsafe_hold requires gate_decision=HOLD")
        if args.risk_level != "high":
            raise ValueError("outcome=unsafe_hold requires risk_level=high")


def _normalize_reference_mark_ids(raw_values: list[str] | None, *, relation: str) -> tuple[str, ...]:
    values = raw_values if raw_values is not None else ["B"]
    references: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = raw.strip()
        if not value:
            raise ValueError("reference_mark_id must be non-empty")
        if len(value) > 32:
            raise ValueError("reference_mark_id must be 32 characters or fewer")
        if not value.isascii():
            raise ValueError("reference_mark_id must be ASCII")
        if _has_control_chars(value) or _contains_secret_material(value) or _contains_raw_frame_material(value):
            raise ValueError("reference_mark_id is not safe to record")
        if value not in seen:
            references.append(value)
            seen.add(value)
    if relation == "between" and len(references) != 2:
        raise ValueError("relation between requires exactly two distinct reference marks")
    if relation in {"left_of", "right_of", "nearest_bin"} and not references:
        raise ValueError(f"relation {relation} requires at least one reference mark")
    return tuple(references)


def _parse_bbox(value: str) -> tuple[int, int, int, int]:
    parts = value.split(",")
    if len(parts) != 4:
        raise ValueError("bbox-norm-1000 must have four comma-separated integers")
    try:
        bbox = tuple(int(part.strip()) for part in parts)
    except ValueError as exc:
        raise ValueError("bbox-norm-1000 must have four comma-separated integers") from exc
    x1, y1, x2, y2 = bbox
    if min(bbox) < 0 or max(bbox) > 1000 or x1 >= x2 or y1 >= y2:
        raise ValueError("bbox-norm-1000 must be a positive-area bbox within 0-1000")
    return bbox  # type: ignore[return-value]


def _gate_reasons(
    *,
    selector_mode: str,
    gate_mode: str,
    policy: str,
    cloud_mode: str,
    control_label: str,
    motion_executed: bool,
) -> tuple[str, ...]:
    return (
        f"selector_mode:{selector_mode}",
        f"gate_mode:{gate_mode}",
        f"policy:{policy}",
        f"cloud_mode:{cloud_mode}",
        f"control_label:{control_label}",
        f"motion_executed:{str(motion_executed).lower()}",
        "operator_recorded_trial",
    )


def _selector_event_mode(*, selector_mode: str, cloud_mode: str) -> str:
    if cloud_mode == "degraded":
        return "degraded"
    if selector_mode == "qwen":
        return "cloud"
    if selector_mode == "fixture":
        return "fixture"
    return "edge"


def _default_evaluator_evidence(outcome: str) -> str:
    if outcome == "success":
        return "Operator/QwenGuard evaluator recorded the object in the bin."
    if outcome == "cloud_hold":
        return "Cloud evaluator unavailable; local system held or recorded uncertain outcome."
    return f"Operator/QwenGuard evaluator recorded physical outcome: {outcome}."


def _qwen_eval_label(outcome: str) -> str:
    if outcome == "success":
        return "success"
    if outcome == "uncertain":
        return "uncertain"
    if outcome == "cloud_hold":
        return "uncertain:cloud_unavailable"
    return f"failure:{outcome}"


def _validate_milli(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if value < 0 or value > 1000:
        raise ValueError(f"{name} must be within 0-1000")


def _find_repo_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "AGENTS.md").exists() and (candidate / "pyproject.toml").exists():
            return candidate
    raise ValueError("could not find repository root from current working directory")


def _repo_path(repo_root: Path, candidate: Path) -> Path:
    path = (repo_root / candidate).resolve()
    try:
        path.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ValueError("paths must stay inside the repository checkout") from exc
    return path


def _display_path(repo_root: Path, path: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def _contains_secret_material(text: str) -> bool:
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def _contains_raw_frame_material(text: str) -> bool:
    return any(pattern.search(text) for pattern in RAW_FRAME_PATTERNS)


def _has_control_chars(value: str) -> bool:
    return any(ord(char) < 32 for char in value)


if __name__ == "__main__":
    raise SystemExit(main())
