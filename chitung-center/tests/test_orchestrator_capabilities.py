from __future__ import annotations

import asyncio
import os
import sys
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "chitung-center"))

from chitung_center.models import ChatMessageRequest, IntentResult
from chitung_center.orchestrator import ChitungOrchestrator
from chitung_center.intent_router import route_intent, route_intent_with_llm
from chitung_center.workflow_engine import WorkflowEngine, _extract_briefing_text, _whatsapp_command_reply


def test_capability_question_returns_concrete_function_list():
    response = asyncio.run(ChitungOrchestrator().handle_message(ChatMessageRequest(message="你支持哪些功能 @赤瞳")))

    assert "我可以" in response.reply
    assert "CCTV" in response.reply
    assert "隐患" in response.reply
    assert "表格" in response.reply
    assert "天气" in response.reply


def test_identity_question_returns_assistant_identity_not_router_fallback():
    response = asyncio.run(ChitungOrchestrator().handle_message(ChatMessageRequest(message="你是谁")))

    assert "赤瞳 AI 助手" in response.reply
    assert "CCTV" in response.reply
    assert "意图路由" not in response.reply


def test_colloquial_capability_question_returns_function_list():
    response = asyncio.run(ChitungOrchestrator().handle_message(ChatMessageRequest(message="你能干啥")))

    assert "我可以" in response.reply
    assert "隐患" in response.reply
    assert "制度" in response.reply


def test_natural_external_attention_request_routes_to_weather_news_risk():
    intent = route_intent("今天外面有什么要留意的，帮我整理一版简报")

    assert intent.intent == "weather_news_risk"
    assert "fetch_hko_weather" in intent.suggested_tools


def test_plain_weather_question_routes_to_weather_query_not_daily_briefing():
    intent = route_intent("香港天气如何")

    assert intent.intent == "weather_query"
    assert intent.suggested_tools == ["fetch_hko_weather"]


def test_whatsapp_sql_question_routes_to_whatsapp_sql_skill():
    intent = route_intent("帮我看 WhatsApp 本地数据库有哪些表")

    assert intent.intent == "whatsapp_sql_query"
    assert "whatsapp_sql_tables" in intent.suggested_tools


def test_whatsapp_wacli_question_routes_to_whatsapp_wacli_skill():
    intent = route_intent("帮我用 wacli 查 WhatsApp 登录状态")

    assert intent.intent == "whatsapp_wacli_ops"
    assert "whatsapp_command_run" in intent.suggested_tools


def test_whatsapp_sql_chat_lists_tables_through_skill_workflow():
    with (
        patch(
            "chitung_center.workflow_engine.list_whatsapp_sql_tables",
            return_value={
                "ok": True,
                "summary": "已读取 2 个数据表。",
                "data": {"tables": ["messages", "chats"], "database_path": "/tmp/wacli.db"},
            },
        ),
        patch("chitung_center.workflow_engine._start_step", new=AsyncMock(return_value={"workflow_step_id": "step-wa-sql"})),
        patch("chitung_center.workflow_engine._finish_step", new=AsyncMock()),
        patch("chitung_center.orchestrator.enhance_with_skill", new=AsyncMock(return_value=None)),
        patch("chitung_center.workflow_engine.workflow_store.ensure_schema", new=AsyncMock(return_value={"ok": True})),
        patch(
            "chitung_center.workflow_engine.workflow_store.create_run",
            new=AsyncMock(return_value={"workflow_run": {"workflow_run_id": "run-wa-sql"}}),
        ),
        patch("chitung_center.workflow_engine.workflow_store.link_event", new=AsyncMock(return_value={"ok": True})),
    ):
        response = asyncio.run(
            ChitungOrchestrator().handle_message(ChatMessageRequest(message="帮我看 WhatsApp 本地数据库有哪些表"))
        )

    assert response.intent.intent == "whatsapp_sql_query"
    assert response.cards[0].card_type == "whatsapp_sql_query"
    assert "messages" in response.reply


def test_whatsapp_wacli_chat_runs_auth_status_through_skill_workflow():
    def fake_run_command(args_text: str, timeout_seconds: int = 60, read_only: bool = True):
        assert args_text == "auth status"
        assert read_only is True
        return {
            "ok": True,
            "summary": "wacli 命令执行完成。",
            "data": {"args": ["auth", "status"], "stdout": "Authenticated as 852@s.whatsapp.net", "stderr": ""},
        }

    with (
        patch("chitung_center.workflow_engine.run_whatsapp_command", side_effect=fake_run_command),
        patch("chitung_center.workflow_engine._start_step", new=AsyncMock(return_value={"workflow_step_id": "step-wa-cmd"})),
        patch("chitung_center.workflow_engine._finish_step", new=AsyncMock()),
        patch("chitung_center.orchestrator.enhance_with_skill", new=AsyncMock(return_value=None)),
        patch("chitung_center.workflow_engine.workflow_store.ensure_schema", new=AsyncMock(return_value={"ok": True})),
        patch(
            "chitung_center.workflow_engine.workflow_store.create_run",
            new=AsyncMock(return_value={"workflow_run": {"workflow_run_id": "run-wa-cmd"}}),
        ),
        patch("chitung_center.workflow_engine.workflow_store.link_event", new=AsyncMock(return_value={"ok": True})),
    ):
        response = asyncio.run(
            ChitungOrchestrator().handle_message(ChatMessageRequest(message="帮我看 WhatsApp 登录状态"))
        )

    assert response.intent.intent == "whatsapp_wacli_ops"
    assert response.cards[0].card_type == "whatsapp_wacli_command"
    assert "auth status" in response.reply


def test_whatsapp_wacli_skill_uses_llm_plan_with_full_command_catalog(monkeypatch):
    monkeypatch.setattr("chitung_center.workflow_engine.settings.llm_base_url", "https://open.bigmodel.cn/api/paas/v4/chat/completions")
    monkeypatch.setattr("chitung_center.workflow_engine.settings.llm_api_key", "glm-secret")
    monkeypatch.setattr("chitung_center.workflow_engine.settings.llm_model", "glm-5.1")

    async def fake_complete_json(system_prompt: str, user_text: str) -> dict[str, object]:
        assert "完整 wacli 命令目录" in system_prompt
        for command_group in ["auth", "accounts", "sync", "messages", "send", "media", "contacts", "chats", "groups", "channels", "history", "presence", "profile", "calls", "store", "doctor"]:
            assert command_group in system_prompt
        assert "任务：帮我看看有哪些群组" in user_text
        return {"action": "run", "args": "groups list", "reason": "用户要列出群组"}

    def fake_run_command(args_text: str, timeout_seconds: int = 60, read_only: bool = True):
        assert args_text == "groups list"
        assert read_only is True
        return {
            "ok": True,
            "summary": "wacli 命令执行完成。",
            "data": {"args": ["groups", "list"], "stdout": "[]", "stderr": ""},
        }

    request = ChatMessageRequest(
        message="执行 WhatsApp wacli 只读诊断\n任务：帮我看看有哪些群组",
        metadata={"assistant_entry_params": {"task": "帮我看看有哪些群组", "args": ""}},
    )
    with (
        patch("chitung_center.workflow_engine.llm_gateway.complete_json", new=AsyncMock(side_effect=fake_complete_json)),
        patch("chitung_center.workflow_engine.run_whatsapp_command", side_effect=fake_run_command),
        patch("chitung_center.workflow_engine._start_step", new=AsyncMock(return_value={"workflow_step_id": "step-wa-groups"})),
        patch("chitung_center.workflow_engine._finish_step", new=AsyncMock()),
        patch("chitung_center.orchestrator.enhance_with_skill", new=AsyncMock(return_value=None)),
        patch("chitung_center.workflow_engine.workflow_store.ensure_schema", new=AsyncMock(return_value={"ok": True})),
        patch(
            "chitung_center.workflow_engine.workflow_store.create_run",
            new=AsyncMock(return_value={"workflow_run": {"workflow_run_id": "run-wa-groups"}}),
        ),
        patch("chitung_center.workflow_engine.workflow_store.link_event", new=AsyncMock(return_value={"ok": True})),
    ):
        response = asyncio.run(ChitungOrchestrator().handle_message(request))

    assert response.intent.intent == "whatsapp_wacli_ops"
    assert "groups list" in response.reply


def test_whatsapp_wacli_skill_rejects_unsafe_llm_command(monkeypatch):
    monkeypatch.setattr("chitung_center.workflow_engine.settings.llm_base_url", "https://open.bigmodel.cn/api/paas/v4/chat/completions")
    monkeypatch.setattr("chitung_center.workflow_engine.settings.llm_api_key", "glm-secret")
    monkeypatch.setattr("chitung_center.workflow_engine.settings.llm_model", "glm-5.1")

    async def fake_complete_json(system_prompt: str, user_text: str) -> dict[str, object]:
        return {"action": "run", "args": "send text --to 123 --message hi", "reason": "用户想发送消息"}

    with (
        patch("chitung_center.workflow_engine.llm_gateway.complete_json", new=AsyncMock(side_effect=fake_complete_json)),
        patch("chitung_center.workflow_engine.run_whatsapp_command") as run_command,
        patch("chitung_center.workflow_engine._start_step", new=AsyncMock(return_value={"workflow_step_id": "step-wa-unsafe"})),
        patch("chitung_center.workflow_engine._finish_step", new=AsyncMock()),
        patch("chitung_center.orchestrator.enhance_with_skill", new=AsyncMock(return_value=None)),
        patch("chitung_center.workflow_engine.workflow_store.ensure_schema", new=AsyncMock(return_value={"ok": True})),
        patch(
            "chitung_center.workflow_engine.workflow_store.create_run",
            new=AsyncMock(return_value={"workflow_run": {"workflow_run_id": "run-wa-unsafe"}}),
        ),
        patch("chitung_center.workflow_engine.workflow_store.link_event", new=AsyncMock(return_value={"ok": True})),
    ):
        response = asyncio.run(
            ChitungOrchestrator().handle_message(ChatMessageRequest(message="帮我给 123 发 WhatsApp 消息 hi"))
        )

    run_command.assert_not_called()
    assert response.intent.intent == "whatsapp_wacli_ops"
    assert response.tool_results[0]["ok"] is False
    assert response.tool_results[0]["error"] == "unsafe_wacli_command"


def test_whatsapp_wacli_readonly_chat_name_is_resolved_to_jid(monkeypatch):
    monkeypatch.setattr("chitung_center.workflow_engine.settings.llm_base_url", "https://open.bigmodel.cn/api/paas/v4/chat/completions")
    monkeypatch.setattr("chitung_center.workflow_engine.settings.llm_api_key", "glm-secret")
    monkeypatch.setattr("chitung_center.workflow_engine.settings.llm_model", "glm-5.1")

    async def fake_complete_json(system_prompt: str, user_text: str) -> dict[str, object]:
        assert "群名" in system_prompt
        return {
            "action": "run",
            "args": "messages list --chat 信息测试群 --limit 10",
            "reason": "用户要查看群组最近消息",
        }

    def fake_sql_query(sql: str, limit: int = 100, db_path: str | None = None):
        if "LIKE" in sql:
            return {
                "ok": True,
                "summary": "查询完成，返回 1 行。",
                "data": {
                    "columns": ["name", "jid"],
                    "rows": [{"name": "安全信息测试群", "jid": "120363425802490084@g.us"}],
                },
            }
        return {"ok": True, "summary": "查询完成，返回 0 行。", "data": {"columns": ["name", "jid"], "rows": []}}

    def fake_run_command(args_text: str, timeout_seconds: int = 60, read_only: bool = True):
        assert args_text == "messages list --chat 120363425802490084@g.us --limit 10"
        assert read_only is True
        return {
            "ok": True,
                "summary": "wacli 命令执行完成。",
                "data": {
                    "args": ["messages", "list", "--chat", "120363425802490084@g.us", "--limit", "10"],
                    "stdout": (
                        "TIME                 CHAT     FROM  ID                                TEXT\n"
                        "2026-06-22 09:00:00  安全信息测试群  陈工    msg-1                             test message"
                    ),
                    "stderr": "",
                },
            }

    request = ChatMessageRequest(
        message="运行工作流：WhatsApp wacli 运维\n任务参数：看看信息测试群的最近消息",
        metadata={"assistant_entry_params": {"task": "看看信息测试群的最近消息", "args": ""}},
    )
    with (
        patch("chitung_center.workflow_engine.llm_gateway.complete_json", new=AsyncMock(side_effect=fake_complete_json)),
        patch("chitung_center.workflow_engine.run_whatsapp_sql_query", side_effect=fake_sql_query),
        patch("chitung_center.workflow_engine.run_whatsapp_command", side_effect=fake_run_command),
        patch("chitung_center.workflow_engine._start_step", new=AsyncMock(return_value={"workflow_step_id": "step-wa-name"})),
        patch("chitung_center.workflow_engine._finish_step", new=AsyncMock()),
        patch("chitung_center.orchestrator.enhance_with_skill", new=AsyncMock(return_value=None)),
        patch("chitung_center.workflow_engine.workflow_store.ensure_schema", new=AsyncMock(return_value={"ok": True})),
        patch(
            "chitung_center.workflow_engine.workflow_store.create_run",
            new=AsyncMock(return_value={"workflow_run": {"workflow_run_id": "run-wa-name"}}),
        ),
        patch("chitung_center.workflow_engine.workflow_store.link_event", new=AsyncMock(return_value={"ok": True})),
    ):
        response = asyncio.run(ChitungOrchestrator().handle_message(request))

    assert response.intent.intent == "whatsapp_wacli_ops"
    assert response.tool_results[0]["ok"] is True
    assert response.tool_results[0]["args_text"] == "messages list --chat 信息测试群 --limit 10"
    assert response.tool_results[0]["data"]["resolved_references"][0]["input"] == "信息测试群"
    assert response.tool_results[0]["data"]["resolved_references"][0]["name"] == "安全信息测试群"
    assert "安全信息测试群" in response.reply
    assert "test message" in response.reply
    assert "TIME" not in response.reply
    assert "120363425802490084@g.us" not in response.reply


def test_whatsapp_wacli_uses_readonly_fallback_when_llm_plan_fails(monkeypatch):
    monkeypatch.setattr("chitung_center.workflow_engine.settings.llm_base_url", "https://open.bigmodel.cn/api/paas/v4/chat/completions")
    monkeypatch.setattr("chitung_center.workflow_engine.settings.llm_api_key", "glm-secret")
    monkeypatch.setattr("chitung_center.workflow_engine.settings.llm_model", "glm-5.1")

    async def fake_complete_json(system_prompt: str, user_text: str) -> dict[str, object]:
        raise RuntimeError("empty model response")

    def fake_sql_query(sql: str, limit: int = 100, db_path: str | None = None):
        if "LIKE" in sql:
            return {
                "ok": True,
                "summary": "查询完成，返回 1 行。",
                "data": {
                    "columns": ["name", "jid"],
                    "rows": [{"name": "安全信息测试群", "jid": "120363425802490084@g.us"}],
                },
            }
        return {"ok": True, "summary": "查询完成，返回 0 行。", "data": {"columns": ["name", "jid"], "rows": []}}

    def fake_run_command(args_text: str, timeout_seconds: int = 60, read_only: bool = True):
        assert args_text == "messages list --chat 120363425802490084@g.us --limit 10"
        return {
            "ok": True,
            "summary": "wacli 命令执行完成。",
            "data": {"stdout": "2026-06-22 09:00:00  安全信息测试群  陈工    msg-1                             test message"},
        }

    request = ChatMessageRequest(
        message="运行工作流：WhatsApp wacli 运维\n任务参数：看看信息测试群的最近消息",
        metadata={"assistant_entry_params": {"task": "看看信息测试群的最近消息", "args": ""}},
    )
    with (
        patch("chitung_center.workflow_engine.llm_gateway.complete_json", new=AsyncMock(side_effect=fake_complete_json)),
        patch("chitung_center.workflow_engine.run_whatsapp_sql_query", side_effect=fake_sql_query),
        patch("chitung_center.workflow_engine.run_whatsapp_command", side_effect=fake_run_command),
        patch("chitung_center.workflow_engine._start_step", new=AsyncMock(return_value={"workflow_step_id": "step-wa-fallback"})),
        patch("chitung_center.workflow_engine._finish_step", new=AsyncMock()),
        patch("chitung_center.orchestrator.enhance_with_skill", new=AsyncMock(return_value=None)),
        patch("chitung_center.workflow_engine.workflow_store.ensure_schema", new=AsyncMock(return_value={"ok": True})),
        patch(
            "chitung_center.workflow_engine.workflow_store.create_run",
            new=AsyncMock(return_value={"workflow_run": {"workflow_run_id": "run-wa-fallback"}}),
        ),
        patch("chitung_center.workflow_engine.workflow_store.link_event", new=AsyncMock(return_value={"ok": True})),
    ):
        response = asyncio.run(ChitungOrchestrator().handle_message(request))

    assert response.tool_results[0]["ok"] is True
    assert response.tool_results[0]["plan"]["fallback"] == "readonly_rule_after_llm_failure"
    assert "test message" in response.reply


def test_whatsapp_wacli_send_request_creates_pending_confirmation(monkeypatch):
    monkeypatch.setattr("chitung_center.workflow_engine.settings.llm_base_url", "https://open.bigmodel.cn/api/paas/v4/chat/completions")
    monkeypatch.setattr("chitung_center.workflow_engine.settings.llm_api_key", "glm-secret")
    monkeypatch.setattr("chitung_center.workflow_engine.settings.llm_model", "glm-5.1")

    async def fake_complete_json(system_prompt: str, user_text: str) -> dict[str, object]:
        assert "confirm_required" in system_prompt
        return {
            "action": "confirm_required",
            "args": "send text --to '安全信息测试群' --message test1",
            "reason": "发送 WhatsApp 消息需要人工确认",
        }

    def fake_sql_query(sql: str, limit: int = 100, db_path: str | None = None):
        assert "FROM groups" in sql
        return {
            "ok": True,
            "summary": "查询完成，返回 1 行。",
            "data": {
                "columns": ["name", "jid"],
                "rows": [{"name": "安全信息测试群", "jid": "120363425802490084@g.us"}],
            },
        }

    async def fake_create_pending_confirmation(**kwargs):
        assert kwargs["action_type"] == "send_whatsapp_message"
        assert kwargs["risk_level"] == "high"
        assert kwargs["payload"] == {
            "chat": "120363425802490084@g.us",
            "chat_name": "安全信息测试群",
            "text": "test1",
            "dry_run": False,
            "args": ["send", "text", "--to", "安全信息测试群", "--message", "test1"],
        }
        return {
            "ok": True,
            "data": {
                "confirmation": {
                    "confirmation_id": "pcf-wa-send-1",
                    "action_type": "send_whatsapp_message",
                    "status": "pending",
                }
            },
        }

    request = ChatMessageRequest(
        message="运行工作流：WhatsApp wacli 运维\n任务参数：帮我去安全信息测试群发一条消息 内容是test1",
        metadata={"assistant_entry_params": {"task": "帮我去安全信息测试群发一条消息 内容是test1", "args": ""}},
    )
    with (
        patch("chitung_center.workflow_engine.llm_gateway.complete_json", new=AsyncMock(side_effect=fake_complete_json)),
        patch("chitung_center.workflow_engine.run_whatsapp_sql_query", side_effect=fake_sql_query),
        patch("chitung_center.workflow_engine.create_pending_confirmation", new=AsyncMock(side_effect=fake_create_pending_confirmation)),
        patch("chitung_center.workflow_engine.run_whatsapp_command") as run_command,
        patch("chitung_center.workflow_engine._start_step", new=AsyncMock(return_value={"workflow_step_id": "step-wa-send"})),
        patch("chitung_center.workflow_engine._finish_step", new=AsyncMock()),
        patch("chitung_center.orchestrator.enhance_with_skill", new=AsyncMock(return_value=None)),
        patch("chitung_center.workflow_engine.workflow_store.ensure_schema", new=AsyncMock(return_value={"ok": True})),
        patch(
            "chitung_center.workflow_engine.workflow_store.create_run",
            new=AsyncMock(return_value={"workflow_run": {"workflow_run_id": "run-wa-send"}}),
        ),
        patch("chitung_center.workflow_engine.workflow_store.link_event", new=AsyncMock(return_value={"ok": True})),
    ):
        response = asyncio.run(ChitungOrchestrator().handle_message(request))

    run_command.assert_not_called()
    assert response.intent.intent == "whatsapp_wacli_ops"
    assert "待确认" in response.reply
    assert response.tool_results[0]["tool"] == "whatsapp_send_confirmation"
    assert response.tool_results[0]["ok"] is True
    assert response.cards[0].card_type == "whatsapp_send_confirmation"
    assert response.cards[0].data["confirmation_id"] == "pcf-wa-send-1"
    assert response.cards[0].actions[0]["id"] == "confirm_send"


def test_whatsapp_send_confirmation_reply_is_not_overridden_by_skill(monkeypatch):
    async def fake_route(message: str):
        return IntentResult(
            intent="whatsapp_wacli_ops",
            confidence=0.92,
            reason="test",
            suggested_tools=["whatsapp_command_run"],
        )

    async def fake_run_for_intent(intent: str, request: ChatMessageRequest):
        return {
            "ok": True,
            "reply": "已创建 WhatsApp 消息待确认项：发送到 安全信息测试群，内容为「test1」。批准后才会发送。",
            "cards": [
                {
                    "card_type": "whatsapp_send_confirmation",
                    "title": "WhatsApp 消息待确认",
                    "summary": "已创建 WhatsApp 消息待确认项。",
                    "actions": [{"id": "confirm_send", "label": "批准并发送"}],
                    "data": {"confirmation_id": "pcf-wa-send-1"},
                }
            ],
            "tool_results": [{"tool": "whatsapp_send_confirmation", "ok": True}],
            "audit_id": "audit-wa-send",
        }

    monkeypatch.setattr("chitung_center.orchestrator.route_intent_with_llm", fake_route)
    monkeypatch.setattr("chitung_center.orchestrator.workflow_engine.run_for_intent", fake_run_for_intent)
    monkeypatch.setattr(
        "chitung_center.orchestrator.enhance_with_skill",
        AsyncMock(
            return_value={
                "skill": "whatsapp-wacli-ops",
                "reply": "当前 WhatsApp wacli 运维 Skill 仅支持只读诊断，无法执行发送。",
                "highlights": ["只读"],
            }
        ),
    )

    response = asyncio.run(
        ChitungOrchestrator().handle_message(
            ChatMessageRequest(message="帮我去安全信息测试群发一条消息 内容是test1")
        )
    )

    assert "已创建 WhatsApp 消息待确认项" in response.reply
    assert "无法执行发送" not in response.reply
    assert response.applied_skill["skill"] == "whatsapp-wacli-ops"


def test_whatsapp_wacli_groups_list_falls_back_to_local_sql_when_wacli_is_empty(monkeypatch):
    monkeypatch.setattr("chitung_center.workflow_engine.settings.llm_base_url", "https://open.bigmodel.cn/api/paas/v4/chat/completions")
    monkeypatch.setattr("chitung_center.workflow_engine.settings.llm_api_key", "glm-secret")
    monkeypatch.setattr("chitung_center.workflow_engine.settings.llm_model", "glm-5.1")

    async def fake_complete_json(system_prompt: str, user_text: str) -> dict[str, object]:
        return {"action": "run", "args": "groups list", "reason": "用户要查看群组"}

    def fake_run_command(args_text: str, timeout_seconds: int = 60, read_only: bool = True):
        return {
            "ok": True,
            "summary": "wacli 命令执行完成。",
            "data": {"args": ["groups", "list"], "stdout": '{"success":true,"data":null,"error":null}\n', "stderr": ""},
        }

    def fake_sql_query(sql: str, limit: int = 100, db_path: str | None = None):
        assert "FROM groups" in sql
        return {
            "ok": True,
            "summary": "查询完成，返回 2 行。",
            "data": {
                "columns": ["name", "jid", "updated_at"],
                "rows": [
                    {"name": "安全整改群", "jid": "111@g.us", "updated_at": 1},
                    {"name": "项目管理群", "jid": "222@g.us", "updated_at": 2},
                ],
            },
        }

    with (
        patch("chitung_center.workflow_engine.llm_gateway.complete_json", new=AsyncMock(side_effect=fake_complete_json)),
        patch("chitung_center.workflow_engine.run_whatsapp_command", side_effect=fake_run_command),
        patch("chitung_center.workflow_engine.run_whatsapp_sql_query", side_effect=fake_sql_query),
        patch("chitung_center.workflow_engine._start_step", new=AsyncMock(return_value={"workflow_step_id": "step-wa-group-fallback"})),
        patch("chitung_center.workflow_engine._finish_step", new=AsyncMock()),
        patch("chitung_center.orchestrator.enhance_with_skill", new=AsyncMock(return_value=None)),
        patch("chitung_center.workflow_engine.workflow_store.ensure_schema", new=AsyncMock(return_value={"ok": True})),
        patch(
            "chitung_center.workflow_engine.workflow_store.create_run",
            new=AsyncMock(return_value={"workflow_run": {"workflow_run_id": "run-wa-group-fallback"}}),
        ),
        patch("chitung_center.workflow_engine.workflow_store.link_event", new=AsyncMock(return_value={"ok": True})),
    ):
        response = asyncio.run(
            ChitungOrchestrator().handle_message(
                ChatMessageRequest(
                    message="执行 WhatsApp wacli 运维\n任务：帮我看看有哪些群组",
                    metadata={"assistant_entry_params": {"task": "帮我看看有哪些群组", "args": ""}},
                )
            )
        )

    assert "安全整改群" in response.reply
    assert response.tool_results[0]["data"]["fallback_source"] == "wacli.db.groups"
    assert response.tool_results[0]["data"]["fallback_rows"][0]["name"] == "安全整改群"


def test_whatsapp_wacli_groups_table_reply_shows_group_rows():
    reply = _whatsapp_command_reply(
        "groups list",
        {
            "ok": True,
            "summary": "wacli 命令执行完成。",
            "data": {
                "stdout": (
                    "NAME                     JID                      TYPE       PARENT                   CREATED\n"
                    "安全信息测试群                  120363425802490084@g.us  group      -                        2026-06-21\n"
                    "沙嶺 - 中港石屎群組              120363407338589346@g.us  group      -                        2026-06-15\n"
                )
            },
        },
    )

    assert "安全信息测试群" in reply
    assert "沙嶺 - 中港石屎群組" in reply
    assert "NAME JID TYPE" not in reply


def test_llm_router_uses_model_result_before_rule_fallback(monkeypatch):
    monkeypatch.setattr("chitung_center.intent_router.settings.llm_base_url", "https://open.bigmodel.cn/api/paas/v4/chat/completions")
    monkeypatch.setattr("chitung_center.intent_router.settings.llm_api_key", "glm-secret")
    monkeypatch.setattr("chitung_center.intent_router.settings.llm_model", "glm-5.1")

    async def fake_complete_json(system_prompt: str, user_text: str) -> dict[str, object]:
        assert "allowed_intents" in system_prompt
        assert user_text == "明天开工前要准备什么"
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"intent":"knowledge_query","confidence":0.82,'
                            '"reason":"用户在问开工前制度要求",'
                            '"suggested_tools":["search_policy_clauses"]}'
                        )
                    }
                }
            ]
        }

    with patch("chitung_center.intent_router.llm_gateway.complete_json", new=AsyncMock(side_effect=fake_complete_json)):
        intent = asyncio.run(route_intent_with_llm("明天开工前要准备什么"))

    assert intent.intent == "knowledge_query"
    assert intent.confidence == 0.82
    assert intent.suggested_tools == ["search_policy_clauses"]


def test_llm_router_falls_back_to_rules_on_invalid_model_json(monkeypatch):
    monkeypatch.setattr("chitung_center.intent_router.settings.llm_base_url", "https://open.bigmodel.cn/api/paas/v4/chat/completions")
    monkeypatch.setattr("chitung_center.intent_router.settings.llm_api_key", "glm-secret")
    monkeypatch.setattr("chitung_center.intent_router.settings.llm_model", "glm-5.1")

    with patch(
        "chitung_center.intent_router.llm_gateway.complete_json",
        new=AsyncMock(return_value={"choices": [{"message": {"content": "not json"}}]}),
    ):
        intent = asyncio.run(route_intent_with_llm("香港天气怎么样"))

    assert intent.intent == "weather_query"
    assert "plain weather" in intent.reason.lower()


def test_plain_weather_orchestrator_does_not_apply_daily_risk_skill():
    async def fake_safe_tool(tool_name: str, payload: dict[str, object]) -> dict[str, object]:
        assert tool_name == "fetch_hko_weather"
        return {
            "ok": True,
            "tool": tool_name,
            "summary": {
                "highest_risk_level": "low",
                "risk_basis": [],
                "special_tips": ["{'desc': '高温天气持续，请补充水分。', 'updateTime': '2026-06-21T16:20:00+08:00'}"],
            },
        }

    with (
        patch("chitung_center.workflow_engine._safe_tool", new=AsyncMock(side_effect=fake_safe_tool)),
        patch("chitung_center.workflow_engine._start_step", new=AsyncMock(return_value={"workflow_step_id": "step-1"})),
        patch("chitung_center.workflow_engine._finish_step", new=AsyncMock()),
        patch("chitung_center.workflow_engine.workflow_store.ensure_schema", new=AsyncMock(return_value={"ok": True})),
        patch(
            "chitung_center.workflow_engine.workflow_store.create_run",
            new=AsyncMock(return_value={"workflow_run": {"workflow_run_id": "run-weather"}}),
        ),
        patch("chitung_center.workflow_engine.workflow_store.link_event", new=AsyncMock(return_value={"ok": True})),
    ):
        response = asyncio.run(ChitungOrchestrator().handle_message(ChatMessageRequest(message="香港天气如何")))

    assert response.intent.intent == "weather_query"
    assert response.applied_skill is None
    assert "香港天气" in response.reply
    assert "高温天气持续" in response.reply
    assert "{'desc'" not in response.reply
    assert "。。" not in response.reply
    assert "外部风险" not in response.reply
    assert "简报" not in response.reply
    assert response.cards[0].card_type == "weather_query"


def test_plain_weather_question_gets_weather_answer_not_module_announcement():
    async def fake_safe_tool(tool_name: str, payload: dict[str, object]) -> dict[str, object]:
        if tool_name == "fetch_hko_weather":
            return {
                "ok": True,
                "tool": tool_name,
                "summary": {
                    "highest_risk_level": "medium",
                    "risk_basis": [{"warning_code": "WHOT", "risk_level": "medium"}],
                    "special_tips": ["局部地区有骤雨"],
                },
            }
        if tool_name == "fetch_hk_safety_updates":
            return {"ok": True, "tool": tool_name, "items": [], "summary": {"matched_item_count": 0}}
        if tool_name == "persist_external_risk_items":
            return {"ok": True, "tool": tool_name, "summary": {"item_count": 1}}
        if tool_name == "draft_daily_risk_briefing":
            return {"ok": True, "tool": tool_name, "items": [{"text": "# 今日外部风险简报"}], "summary": {"total_items": 1}}
        if tool_name == "link_external_risk_to_forms":
            raise AssertionError("external risk briefing must not call legacy form-linking")
        raise AssertionError(f"unexpected tool call: {tool_name}")

    with (
        patch("chitung_center.workflow_engine._safe_tool", new=AsyncMock(side_effect=fake_safe_tool)),
        patch("chitung_center.workflow_engine._start_step", new=AsyncMock(return_value={"workflow_step_id": "step-1"})),
        patch("chitung_center.workflow_engine._finish_step", new=AsyncMock()),
        patch(
            "chitung_center.workflow_engine.persist_external_briefing_report",
            return_value={"ok": True, "report_id": 1, "title": "天气简报", "created_at": "2026-06-21T12:00:00"},
        ),
    ):
        reply, tool_results, cards = asyncio.run(
            WorkflowEngine()._run_daily_risk_briefing(
                ChatMessageRequest(message="香港天气怎么样"),
                "run-1",
            )
        )

    assert "香港天气" in reply
    assert "WHOT" in reply
    assert "局部地区有骤雨" in reply
    assert "我已进入" not in reply
    assert "简报草稿" not in reply
    assert len(tool_results) == 4
    assert all(result.get("tool") != "link_external_risk_to_forms" for result in tool_results)
    assert cards[0].card_type == "external_risk_briefing"


def test_extract_briefing_text_reads_toolbox_items_text():
    briefing = {
        "ok": True,
        "tool": "draft_daily_risk_briefing",
        "items": [
            {
                "format": "markdown",
                "text": "# 晴晴外部风险简报\n\n- 重点关注吊运安全和酷热天气。",
            }
        ],
        "summary": {"total_items": 3},
    }

    assert _extract_briefing_text(briefing).startswith("# 晴晴外部风险简报")


def test_daily_risk_briefing_persists_report_id_on_card():
    async def fake_safe_tool(tool_name: str, payload: dict[str, object]) -> dict[str, object]:
        if tool_name == "fetch_hko_weather":
            return {"ok": True, "tool": tool_name, "summary": {"highest_risk_level": "low"}}
        if tool_name == "fetch_hk_safety_updates":
            return {"ok": True, "tool": tool_name, "items": [{"title": "劳工处安全提示", "url": "https://example.test/a"}]}
        if tool_name == "persist_external_risk_items":
            return {"ok": True, "tool": tool_name, "summary": {"item_count": 1}}
        if tool_name == "draft_daily_risk_briefing":
            return {
                "ok": True,
                "tool": tool_name,
                "items": [{"text": "# 今日外部风险简报\n- 关注吊运安全"}],
                "summary": {"total_items": 1},
            }
        raise AssertionError(f"unexpected tool call: {tool_name}")

    with (
        patch("chitung_center.workflow_engine._safe_tool", new=AsyncMock(side_effect=fake_safe_tool)),
        patch("chitung_center.workflow_engine._start_step", new=AsyncMock(return_value={"workflow_step_id": "step-1"})),
        patch("chitung_center.workflow_engine._finish_step", new=AsyncMock()),
        patch(
            "chitung_center.workflow_engine.persist_external_briefing_report",
            return_value={
                "ok": True,
                "report_id": 12,
                "title": "今日外部风险简报",
                "created_at": "2026-06-21T12:00:00",
            },
        ) as persist_report,
    ):
        _reply, _tool_results, cards = asyncio.run(
            WorkflowEngine()._run_daily_risk_briefing(
                ChatMessageRequest(message="生成今日外部风险简报"),
                "run-briefing",
            )
        )

    persist_report.assert_called_once()
    assert cards[0].data["briefing_report_id"] == 12


def test_visual_patrol_chat_runs_workbench_video_detection_without_image_source():
    async def fake_run_workbench_video_detection(request):
        assert request.detection_direction == "检查 B2 摄像头 PPE 和机械安全距离"
        assert request.camera_id == "cam-1"
        assert request.vlm_enabled is True
        return {
            "ok": True,
            "report_id": "video-chat-1",
            "summary": {
                "text": "已完成 1 路摄像头检测，发现 2 个目标。",
                "severity": "medium",
                "detection_count": 2,
                "suggested_action": "复核标注图。",
            },
            "snapshot_url": "/api/visual/patrol-files/patrol-1/snapshot.jpg",
            "annotated_url": "/api/visual/patrol-files/patrol-1/annotated.jpg",
            "storage": {
                "sqlite_path": "/tmp/video_detection_results.db",
                "sqlite_table": "workbench_video_detection_results",
                "sqlite_rows": 1,
            },
        }

    with (
        patch(
            "chitung_center.workflow_engine.run_workbench_video_detection",
            new=AsyncMock(side_effect=fake_run_workbench_video_detection),
        ),
        patch("chitung_center.workflow_engine._start_step", new=AsyncMock(return_value={"workflow_step_id": "step-video"})),
        patch("chitung_center.workflow_engine._finish_step", new=AsyncMock()),
        patch("chitung_center.workflow_engine.workflow_store.link_event", new=AsyncMock()),
    ):
        reply, tool_results, cards = asyncio.run(
            WorkflowEngine()._run_visual_patrol(
                ChatMessageRequest(
                    message="检查 B2 摄像头 PPE 和机械安全距离",
                    metadata={"camera_id": "cam-1"},
                ),
                "run-video",
            )
        )

    assert "已完成 1 路摄像头检测" in reply
    assert tool_results[0]["tool"] == "workbench_video_detection"
    assert tool_results[0]["report_id"] == "video-chat-1"
    assert cards[0].card_type == "video_detection_report"
    assert cards[0].data["report"]["annotated_url"].endswith("annotated.jpg")
