import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from accountable_swarm.qwen.client import DashScopeQwenClient


class _FakeResponse:
    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps({"choices": [{"message": {"content": "[]"}}]}).encode("utf-8")


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
