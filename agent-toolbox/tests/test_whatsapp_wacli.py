from __future__ import annotations

from agent_toolbox.models import ToolResult
from agent_toolbox.mcp_server import _call_tool
from agent_toolbox.registry import tool_specs
from agent_toolbox.tools.communications import WhatsAppGroupListRequest, list_whatsapp_groups
from agent_toolbox.tools.whatsapp import (
    WhatsAppSendTextRequest,
    WhatsAppWacliGroupsRequest,
    list_groups_wacli,
    send_text_confirmed,
)


def test_list_groups_wacli_parses_wacli_json(monkeypatch):
    def fake_run_wacli(args, timeout=60):
        assert args == ["--read-only", "--json", "groups", "list", "--limit", "20"]
        return (
            True,
            0,
            '{"items":[{"id":"120363@g.us","name":"B2 安全群"}]}',
            "",
            ["wacli", *args],
        )

    monkeypatch.setattr("agent_toolbox.tools.whatsapp._run_wacli", fake_run_wacli)

    result = list_groups_wacli(WhatsAppWacliGroupsRequest(limit=20))

    assert result.ok is True
    assert result.data["items"] == [{"id": "120363@g.us", "name": "B2 安全群"}]
    assert result.data["command"] == ["wacli", "--read-only", "--json", "groups", "list", "--limit", "20"]


def test_send_text_confirmed_requires_confirmation_before_wacli(monkeypatch):
    calls: list[list[str]] = []

    def fake_run_wacli(args, timeout=60):
        calls.append(args)
        return True, 0, '{"message_id":"wamid-test"}', "", ["wacli", *args]

    monkeypatch.setattr("agent_toolbox.tools.whatsapp._run_wacli", fake_run_wacli)

    blocked = send_text_confirmed(
        WhatsAppSendTextRequest(chat="B2 安全群", text="请复核临边围护", confirmed=False)
    )
    assert blocked.ok is False
    assert calls == []

    sent = send_text_confirmed(
        WhatsAppSendTextRequest(
            chat="B2 安全群",
            text="请复核临边围护",
            confirmed=True,
            confirmed_by="safety_officer",
        )
    )

    assert sent.ok is True
    assert calls == [["send", "text", "--to", "B2 安全群", "--message", "请复核临边围护"]]
    assert sent.data["confirmed_by"] == "safety_officer"


def test_list_whatsapp_groups_prefers_wacli_over_placeholder(monkeypatch):
    monkeypatch.setattr(
        "agent_toolbox.tools.communications.list_groups_wacli",
        lambda request: ToolResult(
            ok=True,
            tool="whatsapp_groups_wacli",
            summary="real groups",
            data={"items": [{"id": "real-group", "name": "真实群组", "source": "wacli"}]},
        ),
    )

    result = list_whatsapp_groups(WhatsAppGroupListRequest())

    assert result.ok is True
    assert result.tool == "list_whatsapp_groups"
    assert result.data["items"][0]["id"] == "real-group"


def test_registry_and_mcp_expose_whatsapp_runtime_tools(monkeypatch):
    specs = {spec.name: spec for spec in tool_specs()}

    for name in [
        "whatsapp_auth_start",
        "whatsapp_auth_status",
        "whatsapp_groups_wacli",
        "whatsapp_groups_refresh",
        "whatsapp_send_text_confirmed",
        "whatsapp_sync_start",
        "whatsapp_sync_status",
        "whatsapp_sync_stop",
    ]:
        assert name in specs

    result = _call_tool(
        "whatsapp_send_text_confirmed",
        {"chat": "B2 安全群", "text": "dry run", "confirmed": True, "dry_run": True},
    )

    assert result["ok"] is True
    assert result["data"]["status"] == "dry_run"
