from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from chitung_center.app import app
from chitung_center.whatsapp_adapter_service import handle_whatsapp_event


def test_whatsapp_event_uses_rag_orchestrator_and_confirmed_send(monkeypatch):
    async def fake_query(**kwargs):
        assert kwargs["query"] == "临边围护要求是什么？"
        return {
            "ok": True,
            "items": [
                {
                    "source_file_name": "安全制度.pdf",
                    "text": "临边作业应设置连续、稳固的防护栏杆。",
                }
            ],
        }

    async def fake_complete_json(system_prompt, payload):
        assert "WhatsApp 群机器人" in system_prompt
        assert "临边围护要求是什么" in payload
        return {"choices": [{"message": {"content": '{"reply":"临边应设置连续稳固防护栏杆，并安排现场复核。"}'}}]}

    async def fake_handle_message(request):
        assert request.channel == "whatsapp"
        assert request.message == "临边围护要求是什么？"
        assert request.metadata["chat_id"] == "120363@g.us"
        return SimpleNamespace(reply="工作流默认回复", model_dump=lambda: {"reply": "工作流默认回复"})

    sent: dict = {}

    async def fake_call_tool(tool_name, arguments):
        sent["tool_name"] = tool_name
        sent["arguments"] = arguments
        return {"ok": True, "summary": "sent"}

    monkeypatch.setattr("chitung_center.whatsapp_adapter_service.rag_service.query", fake_query)
    monkeypatch.setattr("chitung_center.whatsapp_adapter_service.llm_gateway.complete_json", fake_complete_json)
    monkeypatch.setattr(
        "chitung_center.whatsapp_adapter_service.orchestrator.handle_message",
        AsyncMock(side_effect=fake_handle_message),
    )
    monkeypatch.setattr("chitung_center.whatsapp_adapter_service.toolbox_client.call_tool", fake_call_tool)

    result = asyncio.run(
        handle_whatsapp_event(
            {
                "Chat": {"JID": "120363@g.us"},
                "MsgID": "wamid-1",
                "SenderName": "陈工",
                "Text": "@赤瞳 临边围护要求是什么？",
                "dry_run": True,
            }
        )
    )

    assert result["ok"] is True
    assert result["stage"] == "agent_replied"
    assert result["clean_text"] == "临边围护要求是什么？"
    assert sent["tool_name"] == "whatsapp_send_text_confirmed"
    assert sent["arguments"] == {
        "chat": "120363@g.us",
        "text": "临边应设置连续稳固防护栏杆，并安排现场复核。",
        "confirmed": True,
        "dry_run": True,
        "confirmed_by": "whatsapp_agent",
    }


def test_whatsapp_event_ignores_untriggered_messages(monkeypatch):
    call_tool = AsyncMock()
    monkeypatch.setattr("chitung_center.whatsapp_adapter_service.toolbox_client.call_tool", call_tool)

    result = asyncio.run(handle_whatsapp_event({"ChatJID": "120363@g.us", "Text": "普通聊天消息"}))

    assert result["ok"] is True
    assert result["stage"] == "archived_only"
    assert result["auto_reply"] is False
    call_tool.assert_not_awaited()


def test_whatsapp_send_api_routes_to_confirmed_tool(monkeypatch):
    async def fake_call_tool(tool_name, arguments):
        return {"ok": True, "tool": tool_name, "data": arguments}

    monkeypatch.setattr("chitung_center.app.toolbox_client.call_tool", fake_call_tool)

    client = TestClient(app)
    response = client.post(
        "/api/whatsapp/send",
        json={
            "chat": "B2 安全群",
            "text": "请复核临边围护",
            "confirmed": True,
            "dry_run": True,
            "confirmed_by": "desktop_user",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["tool"] == "whatsapp_send_text_confirmed"
    assert payload["data"] == {
        "chat": "B2 安全群",
        "text": "请复核临边围护",
        "confirmed": True,
        "dry_run": True,
        "confirmed_by": "desktop_user",
    }
