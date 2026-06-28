from __future__ import annotations

import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from accountable_swarm.qwen.client import DashScopeQwenClient, DashScopeResponseError


class _FakeResponse:
    def __init__(self, payload: object | None = None, raw: bytes | None = None) -> None:
        self.payload = payload if payload is not None else {"choices": [{"message": {"content": "[]"}}]}
        self.raw = raw

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def read(self) -> bytes:
        if self.raw is not None:
            return self.raw
        return json.dumps(self.payload).encode("utf-8")


class DashScopeQwenClientTests(TestCase):
    def test_detect_bbox_pins_temperature_zero(self) -> None:
        captured: dict[str, object] = {}

        def fake_urlopen(req: object, timeout: int) -> _FakeResponse:
            captured["timeout"] = timeout
            captured["payload"] = json.loads(req.data.decode("utf-8"))  # type: ignore[attr-defined]
            return _FakeResponse()

        with patch(
            "accountable_swarm.qwen.client.image_data_url",
            return_value="data:image/png;base64,AA==",
        ), patch("accountable_swarm.qwen.client.request.urlopen", side_effect=fake_urlopen):
            DashScopeQwenClient(model="fake-qwen", api_key="test-key").detect_bbox(
                image_path=Path("fixture.png"),
                target="marked hazard",
            )

        self.assertEqual(captured["timeout"], 60)
        payload = captured["payload"]
        self.assertIsInstance(payload, dict)
        self.assertEqual(payload["model"], "fake-qwen")
        self.assertEqual(payload["temperature"], 0)

    def test_chat_json_object_uses_dashscope_json_mode(self) -> None:
        captured: dict[str, object] = {}

        def fake_urlopen(req: object, timeout: int) -> _FakeResponse:
            captured["timeout"] = timeout
            captured["payload"] = json.loads(req.data.decode("utf-8"))  # type: ignore[attr-defined]
            return _FakeResponse()

        with patch("accountable_swarm.qwen.client.request.urlopen", side_effect=fake_urlopen):
            DashScopeQwenClient(model="fake-qwen", api_key="test-key").chat_json_object(
                prompt="Return a json object.",
            )

        self.assertEqual(captured["timeout"], 60)
        payload = captured["payload"]
        self.assertIsInstance(payload, dict)
        self.assertEqual(payload["model"], "fake-qwen")
        self.assertEqual(payload["temperature"], 0)
        self.assertEqual(payload["enable_thinking"], False)
        self.assertEqual(payload["response_format"], {"type": "json_object"})

    def test_chat_json_object_requires_json_word(self) -> None:
        with self.assertRaisesRegex(ValueError, "must mention json"):
            DashScopeQwenClient(model="fake-qwen", api_key="test-key").chat_json_object(
                prompt="Return an object.",
            )

    def test_chat_json_object_rejects_blank_prompt(self) -> None:
        with self.assertRaisesRegex(ValueError, "prompt must be non-empty"):
            DashScopeQwenClient(model="fake-qwen", api_key="test-key").chat_json_object(prompt="   ")

    def test_chat_json_object_rejects_invalid_max_tokens(self) -> None:
        client = DashScopeQwenClient(model="fake-qwen", api_key="test-key")

        for max_tokens in (0, -1, True):
            with self.subTest(max_tokens=max_tokens):
                with self.assertRaisesRegex(ValueError, "max_tokens"):
                    client.chat_json_object(
                        prompt="Return a json object.",
                        max_tokens=max_tokens,  # type: ignore[arg-type]
                    )

    def test_chat_json_object_rejects_empty_dashscope_content(self) -> None:
        response = _FakeResponse(payload={"choices": [{"message": {"content": "   "}}]})

        with patch("accountable_swarm.qwen.client.request.urlopen", return_value=response):
            with self.assertRaisesRegex(DashScopeResponseError, "missing text content"):
                DashScopeQwenClient(model="fake-qwen", api_key="test-key").chat_json_object(
                    prompt="Return a json object.",
                )

    def test_chat_json_object_rejects_malformed_dashscope_json(self) -> None:
        response = _FakeResponse(raw=b"{")

        with patch("accountable_swarm.qwen.client.request.urlopen", return_value=response):
            with self.assertRaisesRegex(DashScopeResponseError, "invalid JSON"):
                DashScopeQwenClient(model="fake-qwen", api_key="test-key").chat_json_object(
                    prompt="Return a json object.",
                )
