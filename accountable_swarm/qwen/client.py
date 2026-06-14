"""Minimal DashScope OpenAI-compatible client for the GO gate."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib import request

from accountable_swarm.images import image_data_url

DASHSCOPE_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"


class MissingAlibabaApiKey(RuntimeError):
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
        }
        req = request.Request(
            f"{DASHSCOPE_BASE_URL}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=60) as resp:
            data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
        return str(data["choices"][0]["message"]["content"])
