#!/usr/bin/env python3
"""Run the camera/static-frame Accountable Swarm GO gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess

from accountable_swarm.images import image_size
from accountable_swarm.qwen.bbox import parse_qwen_bbox_response
from accountable_swarm.qwen.client import DashScopeQwenClient, DashScopeResponseError, MissingAlibabaApiKey
from accountable_swarm.trace.models import (
    TRACE_SCHEMA_VERSION,
    PerceptionEvent,
    build_single_event_trace,
    canonical_json,
    trace_from_dict,
    verify_trace,
)


FIXTURE_RESPONSE = '[{"bbox_2d":[250,250,750,750],"label":"marked hazard"}]'
REPORT_SCHEMA_VERSION = "camera-go-gate-report.v1"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--image", type=Path)
    source.add_argument("--capture-webcam", type=Path, metavar="OUT_IMAGE")
    parser.add_argument("--trace-out", type=Path, required=True)
    parser.add_argument("--report-out", type=Path, required=True)
    parser.add_argument("--mode", choices=["fixture", "dashscope", "degraded"], default="fixture")
    parser.add_argument("--degraded-on-error", action="store_true")
    parser.add_argument("--target", default="marked hazard")
    parser.add_argument("--model", default="qwen3-vl-flash")
    args = parser.parse_args()

    try:
        image_path, source_kind = _resolve_frame_source(args.image, args.capture_webcam)
        trace, conditions, model_error = _build_trace(
            image_path=image_path,
            source_kind=source_kind,
            mode=args.mode,
            target=args.target,
            model=args.model,
        )
    except MissingAlibabaApiKey as exc:
        if not args.degraded_on_error:
            print(str(exc), file=sys.stderr)
            return 3
        trace, conditions, model_error = _build_degraded_trace(
            image_path=args.image or args.capture_webcam,
            source_kind="degraded",
            model=args.model,
            reason=str(exc),
        )
    except (DashScopeResponseError, OSError, RuntimeError, ValueError) as exc:
        if not args.degraded_on_error:
            print(f"camera-go-gate validation failed: {exc}", file=sys.stderr)
            return 4
        trace, conditions, model_error = _build_degraded_trace(
            image_path=args.image or args.capture_webcam,
            source_kind="degraded",
            model=args.model,
            reason=str(exc),
        )

    summary_sha = verify_trace(trace)
    args.trace_out.parent.mkdir(parents=True, exist_ok=True)
    args.trace_out.write_text(trace.to_canonical_json() + "\n", encoding="utf-8")

    loaded = trace_from_dict(json.loads(args.trace_out.read_text(encoding="utf-8")))
    replay_sha = verify_trace(loaded)
    conditions["trace_replay_deterministic"] = summary_sha == replay_sha
    conditions["frame_emits_decisiontrace_schema"] = loaded.schema_version == TRACE_SCHEMA_VERSION and len(loaded.events) == 1

    outcome = _outcome(args.mode, conditions)
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "outcome": outcome,
        "mode": args.mode,
        "model": args.model,
        "source_kind": trace.events[0].perception.source.split("://", 1)[0],
        "trace_summary_sha": summary_sha,
        "pass_conditions": conditions,
        "model_error": model_error,
        "non_claims": [
            "no physical motion",
            "no SO-101 connectivity",
            "no safety claim",
            "no latency or reliability claim",
            "no swarm behavior",
        ],
    }
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(canonical_json(report) + "\n", encoding="utf-8")

    print(f"outcome {outcome}")
    print(f"trace_summary_sha {summary_sha}")
    print(f"wrote {args.trace_out}")
    print(f"wrote {args.report_out}")
    return 0 if outcome in {"GO", "NARROW_CLAIM", "DEGRADED"} else 4


def _resolve_frame_source(image: Path | None, capture_webcam: Path | None) -> tuple[Path, str]:
    if image is not None:
        if not image.exists():
            raise ValueError(f"image does not exist: {image}")
        if not image.is_file():
            raise ValueError(f"image is not a file: {image}")
        return image, "static_image"
    assert capture_webcam is not None
    _capture_webcam(capture_webcam)
    return capture_webcam, "webcam_capture"


def _capture_webcam(output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    imagesnap = shutil.which("imagesnap")
    if imagesnap:
        result = subprocess.run([imagesnap, str(output)], text=True, capture_output=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(f"imagesnap failed: {result.stderr.strip() or result.stdout.strip()}")
        return
    try:
        import cv2  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        raise RuntimeError("webcam capture requires imagesnap or opencv-python") from exc
    camera = cv2.VideoCapture(0)
    try:
        ok, frame = camera.read()
        if not ok:
            raise RuntimeError("webcam capture failed")
        if not cv2.imwrite(str(output), frame):
            raise RuntimeError(f"failed to write webcam frame: {output}")
    finally:
        camera.release()


def _build_trace(
    *, image_path: Path, source_kind: str, mode: str, target: str, model: str
) -> tuple[object, dict[str, bool], str]:
    if mode == "degraded":
        return _build_degraded_trace(
            image_path=image_path,
            source_kind=source_kind,
            model=model,
            reason="degraded mode requested",
        )
    width, height = image_size(image_path)
    response_text = FIXTURE_RESPONSE if mode == "fixture" else DashScopeQwenClient(model=model).detect_bbox(
        image_path=image_path, target=target
    )
    grounding = parse_qwen_bbox_response(response_text, image_width=width, image_height=height)
    perception = PerceptionEvent(
        event_id="camera-perception-0000",
        source=f"{source_kind}://{image_path.name}",
        image_width=width,
        image_height=height,
        label=grounding.label,
        bbox_2d_norm_1000=grounding.bbox_2d_norm_1000,
        bbox_2d_px=grounding.bbox_2d_px,
        model=model if mode == "dashscope" else "fixture-qwen3-vl-shape",
    )
    trace = build_single_event_trace(
        run_id="camera-go-gate-0000",
        actor_id="edge-node-0",
        mode="cloud" if mode == "dashscope" else "fixture",
        perception=perception,
        intent="hold if marked hazard is visible",
        decision="VETO",
        reason="hazard label detected in keyframe",
        command={"type": "hold", "duration_ticks": 1},
    )
    conditions = {
        "model_responded": mode == "dashscope",
        "json_validated": True,
        "bbox_rescaled": _bbox_within_image(grounding.bbox_2d_px, width, height),
        "trace_replay_deterministic": False,
        "frame_emits_decisiontrace_schema": False,
    }
    return trace, conditions, ""


def _build_degraded_trace(
    *, image_path: Path | None, source_kind: str, model: str, reason: str
) -> tuple[object, dict[str, bool], str]:
    path = image_path or Path("unknown")
    width, height = image_size(path) if path.exists() and path.is_file() else (1, 1)
    perception = PerceptionEvent(
        event_id="camera-perception-0000",
        source=f"{source_kind}://{path.name}",
        image_width=width,
        image_height=height,
        label="degraded_no_model",
        bbox_2d_norm_1000=(0, 0, 1000, 1000),
        bbox_2d_px=(0, 0, width, height),
        model=f"{model}:unavailable",
    )
    trace = build_single_event_trace(
        run_id="camera-go-gate-0000",
        actor_id="edge-node-0",
        mode="degraded",
        perception=perception,
        intent="hold when cloud perception is unavailable",
        decision="HOLD",
        reason="cloud model unavailable; local safe fallback selected",
        command={"type": "hold", "duration_ticks": 1},
    )
    conditions = {
        "model_responded": False,
        "json_validated": False,
        "bbox_rescaled": True,
        "trace_replay_deterministic": False,
        "frame_emits_decisiontrace_schema": False,
    }
    return trace, conditions, reason


def _bbox_within_image(bbox: tuple[int, int, int, int], width: int, height: int) -> bool:
    x1, y1, x2, y2 = bbox
    return 0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height


def _outcome(mode: str, conditions: dict[str, bool]) -> str:
    if mode == "degraded":
        return "DEGRADED"
    if all(conditions.values()):
        return "GO"
    return "NARROW_CLAIM"


if __name__ == "__main__":
    raise SystemExit(main())
