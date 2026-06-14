#!/usr/bin/env python3
"""Run the first Accountable Swarm GO gate."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from accountable_swarm.images import image_size
from accountable_swarm.qwen.bbox import parse_qwen_bbox_response
from accountable_swarm.qwen.client import DashScopeQwenClient, MissingAlibabaApiKey
from accountable_swarm.trace.models import PerceptionEvent, build_single_event_trace, verify_trace


FIXTURE_RESPONSE = '[{"bbox_2d":[250,250,750,750],"label":"marked hazard"}]'


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

    width, height = image_size(args.image)
    try:
        response_text = _get_response(args.mode, image_path=args.image, target=args.target, model=args.model)
    except MissingAlibabaApiKey as exc:
        print(str(exc), file=sys.stderr)
        return 3

    grounding = parse_qwen_bbox_response(response_text, image_width=width, image_height=height)
    perception = PerceptionEvent(
        event_id="perception-0000",
        source=f"image://{args.image.name}",
        image_width=width,
        image_height=height,
        label=grounding.label,
        bbox_2d_norm_1000=grounding.bbox_2d_norm_1000,
        bbox_2d_px=grounding.bbox_2d_px,
        model=args.model if args.mode == "dashscope" else "fixture-qwen3-vl-shape",
    )
    trace = build_single_event_trace(
        run_id="go-gate-0000",
        actor_id="physical-node-0",
        mode="cloud" if args.mode == "dashscope" else "fixture",
        perception=perception,
        intent="hold if marked hazard is visible",
        decision="VETO",
        reason="hazard label detected in keyframe",
        command={"type": "hold", "duration_ticks": 1},
    )
    verify_trace(trace)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(trace.to_canonical_json() + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    print(f"summary_sha {trace.summary_sha}")
    return 0


def _get_response(mode: str, *, image_path: Path, target: str, model: str) -> str:
    if mode == "fixture":
        return FIXTURE_RESPONSE
    return DashScopeQwenClient(model=model).detect_bbox(image_path=image_path, target=target)


if __name__ == "__main__":
    raise SystemExit(main())
