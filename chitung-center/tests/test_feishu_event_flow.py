from __future__ import annotations

import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "chitung-center"))

from chitung_center.feishu_adapter_service import handle_feishu_event
from chitung_center.models import FeishuEventWebhookRequest


def test_feishu_webhook_request_accepts_raw_event_payload():
    raw_payload = {
        "schema": "2.0",
        "header": {"event_type": "im.message.receive_v1"},
        "event": {"message": {"chat_id": "oc_demo", "content": "{\"text\":\"ping\"}"}},
    }

    request = FeishuEventWebhookRequest.model_validate(raw_payload)

    assert request.payload == raw_payload


def test_feishu_text_event_sends_chat_reply_to_source_chat():
    calls: list[tuple[str, dict[str, object]]] = []

    async def fake_call_tool(tool_name: str, payload: dict[str, object]) -> dict[str, object]:
        calls.append((tool_name, payload))
        if tool_name == "feishu_handle_event_callback":
            return {"ok": True, "data": {"event_type": "im.message.receive_v1", "payload": payload["payload"]}}
        if tool_name == "feishu_build_center_route_payload":
            return {
                "ok": True,
                "data": {
                    "center_payload": {
                        "message": "项目状态",
                        "channel": "feishu",
                        "user_id": "ou_demo",
                        "metadata": {"chat_id": "oc_demo"},
                    }
                },
            }
        if tool_name == "feishu_send_text_message":
            return {"ok": True, "summary": "sent"}
        raise AssertionError(f"unexpected tool call: {tool_name}")

    payload = {
        "schema": "2.0",
        "header": {"event_type": "im.message.receive_v1"},
        "event": {
            "sender": {"sender_id": {"open_id": "ou_demo"}},
            "message": {"chat_id": "oc_demo", "content": "{\"text\":\"项目状态\"}"},
        },
    }

    with (
        patch("chitung_center.feishu_adapter_service.toolbox_client.call_tool", new=AsyncMock(side_effect=fake_call_tool)),
        patch(
            "chitung_center.feishu_adapter_service.orchestrator.handle_message",
            new=AsyncMock(return_value=SimpleNamespace(model_dump=lambda: {"reply": "已收到项目状态。"})),
        ),
    ):
        result = asyncio.run(handle_feishu_event(payload))

    assert result["stage"] == "chat_routed"
    assert ("feishu_send_text_message", {"receive_id": "oc_demo", "receive_id_type": "chat_id", "text": "已收到项目状态。"}) in calls
    assert result["reply_send"]["ok"] is True
