"""Trace-only SO-101 camera probe surface.

This module intentionally does not move hardware. It only attempts to read one
camera frame through LeRobot's OpenCV camera adapter when the optional
dependencies are present.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import inspect
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SO101CameraSpec:
    """Minimal camera spec aligned with LeRobot/OpenCV capture."""

    camera_name: str
    index_or_path: str | int
    width: int = 640
    height: int = 480
    fps: int = 30
    rotation: int = 0


def parse_index_or_path(value: str) -> str | int:
    """Convert plain numeric camera identifiers to integers."""

    stripped = value.strip()
    if stripped.isdigit():
        return int(stripped)
    return stripped


def dependency_status() -> tuple[bool, str]:
    try:
        _load_camera_classes()
    except RuntimeError as exc:
        return False, str(exc)
    return True, "ok"


def capture_frame(spec: SO101CameraSpec, output_path: Path) -> dict[str, Any]:
    """Capture one frame through LeRobot's OpenCV camera path."""

    OpenCVCamera, OpenCVCameraConfig, cv2 = _load_camera_classes()
    config_kwargs = {
        "camera_index": spec.index_or_path,
        "camera_path": spec.index_or_path,
        "index_or_path": spec.index_or_path,
        "width": spec.width,
        "height": spec.height,
        "fps": spec.fps,
        "rotation": spec.rotation,
        "name": spec.camera_name,
    }
    config = _construct_config(OpenCVCameraConfig, config_kwargs)
    camera = OpenCVCamera(config)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        _call_if_present(camera, "connect")
        frame = _read_frame(camera)
        if not cv2.imwrite(str(output_path), frame):
            raise RuntimeError(f"failed to write SO-101 camera frame: {output_path}")
        height, width = frame.shape[:2]
    finally:
        _call_if_present(camera, "disconnect")
        _call_if_present(camera, "close")
    return {
        "camera_name": spec.camera_name,
        "index_or_path": spec.index_or_path,
        "width": width,
        "height": height,
        "output_path": output_path.name,
    }


def _load_camera_classes() -> tuple[type[Any], type[Any], Any]:
    failures: list[str] = []
    module_pairs = (
        ("lerobot.cameras.opencv.camera_opencv", "OpenCVCamera"),
        ("lerobot.cameras.opencv.configuration_opencv", "OpenCVCameraConfig"),
    )
    legacy_pairs = (
        ("lerobot.common.cameras.opencv.camera_opencv", "OpenCVCamera"),
        ("lerobot.common.cameras.opencv.configuration_opencv", "OpenCVCameraConfig"),
    )
    try:
        cv2 = importlib.import_module("cv2")
    except Exception as exc:  # pragma: no cover - exercised in controlled failure path
        failures.append(f"cv2 import failed: {exc}")
        cv2 = None

    resolved: dict[str, Any] = {}
    for module_name, attr in module_pairs:
        try:
            resolved[attr] = getattr(importlib.import_module(module_name), attr)
        except Exception as exc:
            failures.append(f"{module_name}.{attr}: {exc}")
    if "OpenCVCamera" not in resolved or "OpenCVCameraConfig" not in resolved:
        resolved = {}
        failures.append("falling back to legacy lerobot.common camera paths")
        for module_name, attr in legacy_pairs:
            try:
                resolved[attr] = getattr(importlib.import_module(module_name), attr)
            except Exception as exc:
                failures.append(f"{module_name}.{attr}: {exc}")

    if cv2 is None or "OpenCVCamera" not in resolved or "OpenCVCameraConfig" not in resolved:
        raise RuntimeError(
            "SO-101 camera probe requires optional lerobot + opencv dependencies. "
            "Install current LeRobot camera extras and ensure an OpenCV camera path is available. "
            + "; ".join(failures)
        )
    return resolved["OpenCVCamera"], resolved["OpenCVCameraConfig"], cv2


def _construct_config(config_class: type[Any], kwargs: dict[str, Any]) -> Any:
    signature = inspect.signature(config_class)
    accepted = {name for name in signature.parameters if name != "self"}
    filtered = {key: value for key, value in kwargs.items() if key in accepted}
    return config_class(**filtered)


def _call_if_present(instance: Any, method_name: str) -> None:
    method = getattr(instance, method_name, None)
    if callable(method):
        method()


def _read_frame(camera: Any) -> Any:
    if hasattr(camera, "async_read"):
        return camera.async_read()
    if hasattr(camera, "read"):
        result = camera.read()
        if isinstance(result, tuple) and len(result) == 2:
            ok, frame = result
            if not ok:
                raise RuntimeError("SO-101 camera read returned failure")
            return frame
        return result
    raise RuntimeError("SO-101 camera object does not expose read or async_read")
