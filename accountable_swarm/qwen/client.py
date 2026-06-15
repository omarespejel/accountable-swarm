"""Minimal DashScope OpenAI-compatible client for the GO gate."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib import request
from urllib.error import HTTPError, URLError

from accountable_swarm.images import image_data_url

DASHSCOPE_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"


class MissingAlibabaApiKey(RuntimeError):
    pass


class DashScopeResponseError(RuntimeError):
    pass


class DashScopeQwenClient:
    def __init__(self, *, model: str = "qwen3-vl-flash", api_key: str | None = None) -> None:
        self.model = model
        self.api_key = api_key or os.getenv("ALIBABA_API_KEY")
        if not self.api_key:
            raise MissingAlibabaApiKey(
                "ALIBABA_API_KEY is not set. Add it to the environment or run fixture mode."
            )

    def detect_bbox(self, *, image_path: Path, target: str) -> str:
        prompt = (
            f"Find the {target}. Return ONLY a JSON array with one object using this exact "
            "shape: [{\"bbox_2d\":[x1,y1,x2,y2],\"label\":\"label\"}]. "
            "Use Qwen3-VL normalized 0-1000 coordinates. Do not include prose."
        )
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_data_url(image_path)}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            "max_tokens": 256,
            "temperature": 0,
        }
        return _extract_text_content(self._post_chat_completion(payload))

    def chat_text(self, *, prompt: str, max_tokens: int = 16) -> str:
        if not prompt.strip():
            raise ValueError("prompt must be non-empty")
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }
        return _extract_text_content(self._post_chat_completion(payload))

    def _post_chat_completion(self, payload: dict[str, Any]) -> dict[str, Any]:
        req = request.Request(
            f"{DASHSCOPE_BASE_URL}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            raise DashScopeResponseError(f"DashScope HTTP error: {exc.code}") from exc
        except URLError as exc:
            raise DashScopeResponseError(f"DashScope connection error: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise DashScopeResponseError("DashScope returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise DashScopeResponseError("DashScope response must be a JSON object")
        return data


def _extract_text_content(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise DashScopeResponseError("DashScope response missing choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise DashScopeResponseError("DashScope choice has invalid shape")
    message = first.get("message")
    if not isinstance(message, dict):
        raise DashScopeResponseError("DashScope response missing message")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise DashScopeResponseError("DashScope response missing text content")
    return content
