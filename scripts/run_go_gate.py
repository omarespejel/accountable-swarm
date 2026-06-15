#!/usr/bin/env python3
"""Run the first Accountable Swarm GO gate."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from accountable_swarm.images import image_size
from accountable_swarm.qwen.bbox import QwenGrounding, parse_qwen_bbox_optional_response
from accountable_swarm.qwen.client import DashScopeQwenClient, DashScopeResponseError, MissingAlibabaApiKey
from accountable_swarm.trace.models import PerceptionEvent, build_single_event_trace, verify_trace


FIXTURE_RESPONSE = '[{"bbox_2d":[250,250,750,750],"label":"marked hazard"}]'
CLEAR_FIXTURE_RESPONSE = "[]"
MAX_DASHSCOPE_PARSE_ATTEMPTS = 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--mode", choices=["fixture", "dashscope"], default="fixture")
    parser.add_argument("--target", default="marked hazard")
    parser.add_argument("--model", default="qwen3-vl-flash")
    args = parser.parse_args()

    if not args.image.exists():
        print(f"image does not exist: {args.image}", file=sys.stderr)
        return 2
    if not args.image.is_file():
        print(f"image is not a file: {args.image}", file=sys.stderr)
        return 2

    try:
        width, height = image_size(args.image)
        grounding = _get_grounding(
            args.mode,
            image_path=args.image,
            target=args.target,
            model=args.model,
            image_width=width,
            image_height=height,
        )
    except MissingAlibabaApiKey as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except (DashScopeResponseError, OSError, ValueError) as exc:
        print(f"go-gate input/API validation failed: {exc}", file=sys.stderr)
        return 4
    perception = _perception_from_grounding(
        grounding,
        image_name=args.image.name,
        image_width=width,
        image_height=height,
        model=args.model if args.mode == "dashscope" else "fixture-qwen3-vl-shape",
    )
    decision, reason, command = _decision_from_grounding(grounding)
    trace = build_single_event_trace(
        run_id="go-gate-0000",
        actor_id="physical-node-0",
        mode="cloud" if args.mode == "dashscope" else "fixture",
        perception=perception,
        intent="hold if marked hazard is visible",
        decision=decision,
        reason=reason,
        command=command,
    )
    verify_trace(trace)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(trace.to_canonical_json() + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    print(f"decision {decision}")
    print(f"summary_sha {trace.summary_sha}")
    return 0


def _perception_from_grounding(
    grounding: QwenGrounding | None,
    *,
    image_name: str,
    image_width: int,
    image_height: int,
    model: str,
) -> PerceptionEvent:
    if grounding is None:
        return PerceptionEvent(
            event_id="perception-0000",
            source=f"image://{image_name}",
            image_width=image_width,
            image_height=image_height,
            label="clear frame",
            bbox_2d_norm_1000=(0, 0, 1000, 1000),
            bbox_2d_px=(0, 0, image_width, image_height),
            model=model,
        )
    return PerceptionEvent(
        event_id="perception-0000",
        source=f"image://{image_name}",
        image_width=image_width,
        image_height=image_height,
        label=grounding.label,
        bbox_2d_norm_1000=grounding.bbox_2d_norm_1000,
        bbox_2d_px=grounding.bbox_2d_px,
        model=model,
    )


def _decision_from_grounding(grounding: QwenGrounding | None) -> tuple[str, str, dict[str, object]]:
    if grounding is None:
        return (
            "MOVE",
            "target label not detected in keyframe",
            {"type": "move", "dx_milli": 0, "dy_milli": 0, "duration_ticks": 1},
        )
    return (
        "VETO",
        "target label detected in keyframe",
        {"type": "hold", "duration_ticks": 1},
    )


def _get_grounding(
    mode: str,
    *,
    image_path: Path,
    target: str,
    model: str,
    image_width: int,
    image_height: int,
) -> QwenGrounding | None:
    if mode == "fixture":
        response_text = CLEAR_FIXTURE_RESPONSE if "clear" in image_path.stem else FIXTURE_RESPONSE
        return _parse_optional_grounding(response_text, image_width=image_width, image_height=image_height)

    client = DashScopeQwenClient(model=model)
    last_error: ValueError | None = None
    for _attempt in range(MAX_DASHSCOPE_PARSE_ATTEMPTS):
        response_text = client.detect_bbox(image_path=image_path, target=target)
        try:
            return _parse_optional_grounding(response_text, image_width=image_width, image_height=image_height)
        except ValueError as exc:
            last_error = exc
    raise ValueError(f"Qwen bbox response stayed invalid after retry: {last_error}")


def _parse_optional_grounding(
    response_text: str, *, image_width: int, image_height: int
) -> QwenGrounding | None:
    return parse_qwen_bbox_optional_response(response_text, image_width=image_width, image_height=image_height)


if __name__ == "__main__":
    raise SystemExit(main())
