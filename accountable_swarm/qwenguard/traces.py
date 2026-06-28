"""DecisionTrace helpers for QwenGuard fixture and hardware-adjacent gates."""

from __future__ import annotations

from accountable_swarm.qwen.bbox import rescale_norm_1000_bbox
from accountable_swarm.qwenguard.evaluator import EvaluationResult
from accountable_swarm.qwenguard.outcome_gate import GateDecision
from accountable_swarm.qwenguard.selector import SelectorResult
from accountable_swarm.trace.models import (
    GENESIS_SHA,
    DecisionEvent,
    DecisionTrace,
    PerceptionEvent,
)


def build_qwenguard_trace(
    *,
    run_id: str,
    source: str,
    image_width: int,
    image_height: int,
    model: str,
    selector: SelectorResult | None,
    gate: GateDecision,
    evaluation: EvaluationResult,
    mode: str,
) -> DecisionTrace:
    """Build a multi-stage QwenGuard trace."""

    perception = _perception_from_selector_or_frame(
        selector=selector,
        source=source,
        image_width=image_width,
        image_height=image_height,
        model=model,
    )
    events: list[DecisionEvent] = []
    prev_sha = GENESIS_SHA
    if selector is not None:
        select_event = DecisionEvent(
            tick=0,
            actor_id="edge-node-0",
            mode=mode,
            intent="select relational cube target from marked candidates",
            decision="SELECT",
            reason="validated marked target selected",
            command=selector.to_command(),
            perception=perception,
            prev_sha=prev_sha,
        ).with_computed_sha()
        events.append(select_event)
        prev_sha = select_event.sha256
    else:
        select_event = DecisionEvent(
            tick=0,
            actor_id="edge-node-0",
            mode="degraded",
            intent="select relational cube target from marked candidates",
            decision="HOLD",
            reason="selector unavailable; local safe fallback selected",
            command={"type": "qwenguard_select_target", "status": "unavailable"},
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
        reason="deterministic local outcome gate evaluated candidate action",
        command=gate.to_command(),
        perception=perception,
        prev_sha=prev_sha,
    ).with_computed_sha()
    events.append(gate_event)
    prev_sha = gate_event.sha256

    action_decision = gate.gate_decision if gate.gate_decision in {"ALLOW", "RETRY"} else "HOLD"
    action_mode = "edge" if action_decision in {"ALLOW", "RETRY"} else "degraded"
    action_event = DecisionEvent(
        tick=2,
        actor_id="so101-act-policy",
        mode=action_mode,
        intent="apply local policy only when gate allows",
        decision=action_decision,
        reason="no-motion health check records intent without moving hardware",
        command={
            "type": "physical_action_intent",
            "requested_action": gate.candidate_action,
            "motion_executed": False,
            "gate_decision": gate.gate_decision,
        },
        perception=perception,
        prev_sha=prev_sha,
    ).with_computed_sha()
    events.append(action_event)
    prev_sha = action_event.sha256

    eval_event = DecisionEvent(
        tick=3,
        actor_id="edge-node-0",
        mode=mode if mode != "degraded" else "degraded",
        intent="evaluate before-after outcome without granting motor authority",
        decision="EVALUATE",
        reason="validated evaluator output recorded",
        command=evaluation.to_command(),
        perception=perception,
        prev_sha=prev_sha,
    ).with_computed_sha()
    events.append(eval_event)

    return DecisionTrace(run_id=run_id, events=tuple(events)).with_computed_summary()


def _perception_from_selector_or_frame(
    *,
    selector: SelectorResult | None,
    source: str,
    image_width: int,
    image_height: int,
    model: str,
) -> PerceptionEvent:
    if selector is None:
        return PerceptionEvent(
            event_id="qwenguard-perception-0000",
            source=source,
            image_width=image_width,
            image_height=image_height,
            label="degraded_no_target",
            bbox_2d_norm_1000=(0, 0, 1000, 1000),
            bbox_2d_px=(0, 0, image_width, image_height),
            model=f"{model}:unavailable",
            score_milli=0,
        )
    return PerceptionEvent(
        event_id="qwenguard-perception-0000",
        source=source,
        image_width=image_width,
        image_height=image_height,
        label=selector.target_label,
        bbox_2d_norm_1000=selector.bbox_2d_norm_1000,
        bbox_2d_px=rescale_norm_1000_bbox(
            selector.bbox_2d_norm_1000,
            image_width=image_width,
            image_height=image_height,
        ),
        model=model,
        score_milli=selector.confidence_milli,
    )
