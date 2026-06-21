from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "chitung-center"))

from lark_oapi.api.im.v1.model.p2_im_message_receive_v1 import P2ImMessageReceiveV1

from chitung_center.feishu_long_connection import (
    build_lark_event_dispatcher,
    sdk_event_to_payload,
    submit_feishu_payload,
)


def test_sdk_event_to_payload_preserves_message_fields():
    event = P2ImMessageReceiveV1(
        {
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "token": "verification-token",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou_demo"}},
                "message": {
                    "chat_id": "oc_demo",
                    "message_type": "text",
                    "content": "{\"text\":\"项目状态\"}",
                },
            },
        }
    )

    payload = sdk_event_to_payload(event)

    assert payload["schema"] == "2.0"
    assert payload["header"]["event_type"] == "im.message.receive_v1"
    assert payload["event"]["message"]["chat_id"] == "oc_demo"
    assert payload["event"]["sender"]["sender_id"]["open_id"] == "ou_demo"


def test_submit_feishu_payload_schedules_async_handler_on_running_loop():
    seen: list[dict[str, object]] = []

    async def scenario() -> None:
        done = asyncio.Event()

        async def fake_handler(payload: dict[str, object]) -> dict[str, object]:
            seen.append(payload)
            done.set()
            return {"ok": True}

        submit_feishu_payload({"hello": "feishu"}, handler=fake_handler)
        await asyncio.wait_for(done.wait(), timeout=1)

    asyncio.run(scenario())

    assert seen == [{"hello": "feishu"}]


def test_build_lark_event_dispatcher_registers_message_and_card_callbacks():
    async def fake_handler(payload: dict[str, object]) -> dict[str, object]:
        return {"ok": True, "payload": payload}

    dispatcher = build_lark_event_dispatcher(
        encrypt_key="",
        verification_token="verification-token",
        handler=fake_handler,
    )

    assert "p2.im.message.receive_v1" in dispatcher._processorMap
    assert "p2.card.action.trigger" in dispatcher._callback_processor_map
