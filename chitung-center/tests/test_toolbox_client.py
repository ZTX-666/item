from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "chitung-center"))

from chitung_center.toolbox_client import ToolboxClient


def test_toolbox_client_uses_configurable_timeout(monkeypatch):
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"ok": True}

    class FakeAsyncClient:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, json):
            captured["url"] = url
            captured["payload"] = json
            return FakeResponse()

    monkeypatch.setattr("chitung_center.toolbox_client.httpx.AsyncClient", FakeAsyncClient)

    result = asyncio.run(ToolboxClient("http://toolbox.local", timeout_seconds=123.0).call_tool("slow_tool", {"a": 1}))

    assert result == {"ok": True}
    assert captured["timeout"] == 123.0
    assert captured["url"] == "http://toolbox.local/tools/slow_tool"
