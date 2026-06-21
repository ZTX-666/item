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


def test_feishu_group_message_without_bot_mention_is_archived_only():
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
                        "message": "今天进度怎么样",
                        "channel": "feishu",
                        "user_id": "ou_demo",
                        "metadata": {"chat_id": "oc_group"},
                    }
                },
            }
        raise AssertionError(f"unexpected tool call: {tool_name}")

    payload = {
        "schema": "2.0",
        "header": {"event_type": "im.message.receive_v1"},
        "event": {
            "sender": {"sender_id": {"open_id": "ou_demo"}},
            "message": {
                "chat_id": "oc_group",
                "chat_type": "group",
                "content": "{\"text\":\"今天进度怎么样\"}",
                "mentions": [],
            },
        },
    }

    with (
        patch("chitung_center.feishu_adapter_service.toolbox_client.call_tool", new=AsyncMock(side_effect=fake_call_tool)),
        patch("chitung_center.feishu_adapter_service.orchestrator.handle_message", new=AsyncMock()) as handle_message,
    ):
        result = asyncio.run(handle_feishu_event(payload))

    assert result["stage"] == "ignored_group_message"
    handle_message.assert_not_awaited()
    assert not any(call[0] == "feishu_send_text_message" for call in calls)


def test_feishu_group_message_with_bot_mention_routes_and_removes_mention_text():
    calls: list[tuple[str, dict[str, object]]] = []
    routed_messages: list[str] = []

    async def fake_call_tool(tool_name: str, payload: dict[str, object]) -> dict[str, object]:
        calls.append((tool_name, payload))
        if tool_name == "feishu_handle_event_callback":
            return {"ok": True, "data": {"event_type": "im.message.receive_v1", "payload": payload["payload"]}}
        if tool_name == "feishu_build_center_route_payload":
            return {
                "ok": True,
                "data": {
                    "center_payload": {
                        "message": "@_user_1 你支持哪些功能",
                        "channel": "feishu",
                        "user_id": "ou_demo",
                        "metadata": {"chat_id": "oc_group"},
                    }
                },
            }
        if tool_name == "feishu_send_text_message":
            return {"ok": True, "summary": "sent"}
        raise AssertionError(f"unexpected tool call: {tool_name}")

    async def fake_handle_message(request):
        routed_messages.append(request.message)
        return SimpleNamespace(model_dump=lambda: {"reply": "我可以做隐患、CCTV 和报告。"})

    payload = {
        "schema": "2.0",
        "header": {"event_type": "im.message.receive_v1"},
        "event": {
            "sender": {"sender_id": {"open_id": "ou_demo"}},
            "message": {
                "chat_id": "oc_group",
                "chat_type": "group",
                "content": "{\"text\":\"@_user_1 你支持哪些功能\"}",
                "mentions": [
                    {
                        "key": "@_user_1",
                        "name": "赤瞳",
                        "mentioned_type": "app",
                        "id": {"open_id": "ou_bot"},
                    }
                ],
            },
        },
    }

    with (
        patch("chitung_center.feishu_adapter_service.toolbox_client.call_tool", new=AsyncMock(side_effect=fake_call_tool)),
        patch("chitung_center.feishu_adapter_service.orchestrator.handle_message", new=AsyncMock(side_effect=fake_handle_message)),
    ):
        result = asyncio.run(handle_feishu_event(payload))

    assert result["stage"] == "chat_routed"
    assert routed_messages == ["你支持哪些功能"]
    assert ("feishu_send_text_message", {"receive_id": "oc_group", "receive_id_type": "chat_id", "text": "我可以做隐患、CCTV 和报告。"}) in calls


def test_feishu_reply_sends_report_files_and_images_from_tool_results():
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
                        "message": "生成今日安全报告",
                        "channel": "feishu",
                        "user_id": "ou_demo",
                        "metadata": {"chat_id": "oc_demo"},
                    }
                },
            }
        if tool_name in {"feishu_send_text_message", "feishu_send_file_message", "feishu_send_image_message"}:
            return {"ok": True, "summary": f"{tool_name} sent"}
        raise AssertionError(f"unexpected tool call: {tool_name}")

    response_payload = {
        "reply": "报告已生成。",
        "tool_results": [
            {"tool": "generate_report", "output_path": "/tmp/daily-safety.docx"},
            {"tool": "visual_patrol", "files": [{"path": "/tmp/site-evidence.png"}]},
        ],
    }

    payload = {
        "schema": "2.0",
        "header": {"event_type": "im.message.receive_v1"},
        "event": {
            "sender": {"sender_id": {"open_id": "ou_demo"}},
            "message": {"chat_id": "oc_demo", "content": "{\"text\":\"生成今日安全报告\"}"},
        },
    }

    with (
        patch("chitung_center.feishu_adapter_service.toolbox_client.call_tool", new=AsyncMock(side_effect=fake_call_tool)),
        patch(
            "chitung_center.feishu_adapter_service.orchestrator.handle_message",
            new=AsyncMock(return_value=SimpleNamespace(model_dump=lambda: response_payload)),
        ),
    ):
        result = asyncio.run(handle_feishu_event(payload))

    assert result["stage"] == "chat_routed"
    assert ("feishu_send_file_message", {"receive_id": "oc_demo", "receive_id_type": "chat_id", "file_path": "/tmp/daily-safety.docx"}) in calls
    assert ("feishu_send_image_message", {"receive_id": "oc_demo", "receive_id_type": "chat_id", "image_path": "/tmp/site-evidence.png"}) in calls
    assert result["attachment_sends"] == [
        {"ok": True, "summary": "feishu_send_file_message sent"},
        {"ok": True, "summary": "feishu_send_image_message sent"},
    ]
