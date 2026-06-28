#!/usr/bin/env python3
"""Run the QwenGuard selector/gate/evaluator spine without moving hardware."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from accountable_swarm.images import image_size
from accountable_swarm.physical.contract import PhysicalNodeSafety
from accountable_swarm.qwenguard.evaluator import degraded_evaluation, parse_evaluator_response
from accountable_swarm.qwenguard.outcome_gate import OutcomeGateInput, evaluate_outcome_gate
from accountable_swarm.qwenguard.selector import fixture_cube_candidates, parse_selector_response
from accountable_swarm.qwenguard.traces import build_qwenguard_trace
from accountable_swarm.trace.models import TRACE_SCHEMA_VERSION, canonical_json, trace_from_dict, verify_trace

REPORT_SCHEMA_VERSION = "qwenguard-no-motion-health-check-report.v1"

FIXTURE_SELECTOR_RESPONSE = json.dumps(
    {
        "target_mark_id": "A",
        "target_label": "red cube left of green cube",
        "relation": "left_of",
        "reference_mark_ids": ["B"],
        "confidence_milli": 910,
        "evidence": "Mark A is the red cube to the left of the green cube marked B.",
    },
    sort_keys=True,
)

FIXTURE_EVALUATOR_RESPONSES = {
    "success": json.dumps(
        {
            "outcome": "success",
            "failure_type": "none",
            "confidence_milli": 860,
            "evidence": "Fixture before/after pair shows the target cube in the bin.",
        },
        sort_keys=True,
    ),
    "failure": json.dumps(
        {
            "outcome": "failure",
            "failure_type": "not_in_bin",
            "confidence_milli": 820,
            "evidence": "Fixture before/after pair does not show the target cube in the bin.",
        },
        sort_keys=True,
    ),
    "uncertain": json.dumps(
        {
            "outcome": "uncertain",
            "failure_type": "uncertain_view",
            "confidence_milli": 500,
            "evidence": "Fixture no-motion health check did not execute a physical action.",
        },
        sort_keys=True,
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, default=Path("fixtures/hazard_marker.ppm"))
    parser.add_argument("--trace-out", type=Path, required=True)
    parser.add_argument("--report-out", type=Path, required=True)
    parser.add_argument("--mode", choices=["fixture", "degraded"], default="fixture")
    parser.add_argument("--instruction", default="pick the red cube left of the green cube")
    parser.add_argument("--model", default="fixture-qwen3-vl-shape")
    parser.add_argument("--policy-available", action="store_true")
    parser.add_argument("--simulate-safe-motion-authority", action="store_true")
    parser.add_argument("--fixture-outcome", choices=sorted(FIXTURE_EVALUATOR_RESPONSES), default="uncertain")
    args = parser.parse_args()

    try:
        trace, report = _run(args)
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        print(f"qwenguard health check failed: {exc}", file=sys.stderr)
        return 4

    args.trace_out.parent.mkdir(parents=True, exist_ok=True)
    args.trace_out.write_text(trace.to_canonical_json() + "\n", encoding="utf-8")
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(canonical_json(report) + "\n", encoding="utf-8")

    print(f"outcome {report['outcome']}")
    print(f"trace_summary_sha {report['trace_summary_sha']}")
    print(f"gate_decision {report['gate']['gate_decision']}")
    print(f"wrote {args.trace_out}")
    print(f"wrote {args.report_out}")
    return 0 if report["outcome"] in {"GO", "DEGRADED"} else 4


def _run(args: argparse.Namespace) -> tuple[object, dict[str, object]]:
    if not args.image.exists():
        raise ValueError(f"image does not exist: {args.image}")
    width, height = image_size(args.image)
    candidates = fixture_cube_candidates()
    selector = None
    if args.mode == "fixture":
        selector = parse_selector_response(FIXTURE_SELECTOR_RESPONSE, candidates=candidates)
        evaluation = parse_evaluator_response(FIXTURE_EVALUATOR_RESPONSES[args.fixture_outcome])
    else:
        evaluation = degraded_evaluation("degraded mode requested")

    safety = _safety(args.simulate_safe_motion_authority)
    gate = evaluate_outcome_gate(
        OutcomeGateInput(
            selector=selector,
            safety=safety,
            policy_available=args.policy_available,
            cloud_available=args.mode != "degraded",
            workspace_ok=True,
        )
    )
    trace = build_qwenguard_trace(
        run_id="qwenguard-no-motion-0000",
        source=f"image://{args.image.name}",
        image_width=width,
        image_height=height,
        model=args.model,
        selector=selector,
        gate=gate,
        evaluation=evaluation,
        mode="fixture" if args.mode == "fixture" else "degraded",
    )
    summary_sha = verify_trace(trace)
    loaded = trace_from_dict(trace.to_dict())
    replay_sha = verify_trace(loaded)
    motion_executed_values = [
        event.command.get("motion_executed")
        for event in loaded.events
        if event.command.get("type") == "physical_action_intent"
    ]
    no_motion_executed = bool(motion_executed_values) and all(value is False for value in motion_executed_values)
    pass_conditions = {
        "selector_validated": selector is not None or args.mode == "degraded",
        "gate_evaluated": gate.gate_decision in {"ALLOW", "HOLD", "RETRY"},
        "gate_allows_action": args.mode != "fixture" or gate.gate_decision == "ALLOW",
        "evaluator_validated": True,
        "trace_replay_deterministic": summary_sha == replay_sha,
        "frame_emits_decisiontrace_schema": loaded.schema_version == TRACE_SCHEMA_VERSION and len(loaded.events) == 4,
        "no_motion_executed": no_motion_executed,
        "degraded_holds": args.mode != "degraded" or gate.gate_decision == "HOLD",
    }
    outcome = "DEGRADED" if args.mode == "degraded" else "GO"
    if not all(pass_conditions.values()):
        outcome = "NARROW_CLAIM"
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "outcome": outcome,
        "instruction": args.instruction,
        "mode": args.mode,
        "model": args.model,
        "trace_summary_sha": summary_sha,
        "selector": selector.to_command() if selector is not None else {"status": "unavailable"},
        "gate": gate.to_dict(),
        "evaluation": evaluation.to_command(),
        "pass_conditions": pass_conditions,
        "non_claims": [
            "no physical motion",
            "no SO-101 connectivity proof",
            "no ACT policy success",
            "no safety claim",
            "no latency or reliability claim",
            "no DimOS runtime execution",
            "no Alibaba ECS deployment proof",
        ],
    }
    return trace, report


def _safety(simulate_safe_motion_authority: bool) -> PhysicalNodeSafety:
    if not simulate_safe_motion_authority:
        return PhysicalNodeSafety()
    return PhysicalNodeSafety(
        low_speed_mode=True,
        workspace_bounds_enabled=True,
        operator_armed=True,
        motion_enabled=True,
        emergency_stop_available=True,
        autonomous_setup_motion_allowed=False,
    )


if __name__ == "__main__":
    raise SystemExit(main())
