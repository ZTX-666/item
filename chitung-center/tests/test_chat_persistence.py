from __future__ import annotations

import asyncio
import os
import sqlite3
import sys
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "chitung-center"))


def test_chat_store_persists_session_and_messages(tmp_path):
    from chitung_center.chat_store import ChatStore

    store = ChatStore(tmp_path / "chat.db")
    session = store.ensure_session(
        session_id=None,
        channel="local_chat",
        user_id="chen",
        metadata={"route": "/yaoyao/feed", "module": "feed"},
        title_source="生成今日舆情简报",
    )

    store.append_message(session["session_id"], role="user", content="生成今日舆情简报")
    store.append_message(
        session["session_id"],
        role="assistant",
        content="已生成外部风险简报。",
        intent={"intent": "weather_news_risk"},
        tool_results=[{"tool": "draft_daily_risk_briefing", "ok": True}],
        cards=[{"card_type": "external_risk_briefing", "title": "简报"}],
        audit_id="audit-1",
    )

    history = store.get_history(session["session_id"])

    assert history["session"]["title"] == "生成今日舆情简报"
    assert history["session"]["route"] == "/yaoyao/feed"
    assert history["session"]["module"] == "feed"
    assert [item["role"] for item in history["messages"]] == ["user", "assistant"]
    assert history["messages"][1]["intent"]["intent"] == "weather_news_risk"
    assert history["messages"][1]["tool_results"][0]["tool"] == "draft_daily_risk_briefing"

    with sqlite3.connect(tmp_path / "chat.db") as conn:
        count = conn.execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0]

    assert count == 2


def test_chat_api_stores_user_and_assistant_messages(monkeypatch, tmp_path):
    from chitung_center.app import app
    from chitung_center.chat_store import ChatStore
    from chitung_center.models import ActionCard, ChatMessageResponse, IntentResult

    test_store = ChatStore(tmp_path / "chat.db")
    monkeypatch.setattr("chitung_center.app.chat_store", test_store)

    async def fake_handle_message(request):
        assert request.metadata["route"] == "/lingxun/whatsapp"
        return ChatMessageResponse(
            reply="已生成今日外部风险舆情简报。",
            intent=IntentResult(
                intent="weather_news_risk",
                confidence=0.91,
                reason="test",
                suggested_tools=["fetch_hko_weather", "fetch_hk_safety_updates"],
            ),
            cards=[
                ActionCard(
                    card_type="external_risk_briefing",
                    title="外部风险简报",
                    summary="今日关注吊运安全。",
                )
            ],
            tool_results=[{"tool": "draft_daily_risk_briefing", "ok": True}],
            applied_skill={"skill": "daily-risk-briefing", "highlights": ["外部风险"]},
            audit_id="audit-1",
        )

    monkeypatch.setattr("chitung_center.app.orchestrator.handle_message", fake_handle_message)

    client = TestClient(app)
    response = client.post(
        "/api/chat/message",
        json={
            "channel": "local_chat",
            "user_id": "chen",
            "message": "生成今日舆情简报",
            "metadata": {"route": "/lingxun/whatsapp", "module": "whatsapp"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"]

    history = client.get(f"/api/chat/history?session_id={payload['session_id']}").json()

    assert history["session"]["session_id"] == payload["session_id"]
    assert [item["role"] for item in history["messages"]] == ["user", "assistant"]
    assert history["messages"][0]["content"] == "生成今日舆情简报"
    assert history["messages"][1]["intent"]["intent"] == "weather_news_risk"
    assert history["messages"][1]["cards"][0]["card_type"] == "external_risk_briefing"
    assert history["messages"][1]["metadata"]["applied_skill"]["skill"] == "daily-risk-briefing"


def test_chat_api_returns_skill_and_workflow_metadata(monkeypatch, tmp_path):
    from chitung_center.app import app
    from chitung_center.chat_store import ChatStore
    from chitung_center.models import ActionCard, ChatMessageResponse, IntentResult

    test_store = ChatStore(tmp_path / "chat.db")
    monkeypatch.setattr("chitung_center.app.chat_store", test_store)

    async def fake_handle_message(request):
        return ChatMessageResponse(
            reply="已生成视觉巡检报告。",
            intent=IntentResult(
                intent="visual_detection",
                confidence=0.88,
                reason="test",
                suggested_tools=["workbench_video_detection"],
            ),
            cards=[
                ActionCard(
                    card_type="video_detection_report",
                    title="视频巡检结果",
                    summary="发现 1 项 PPE 风险。",
                    data={"workflow_run_id": "workflow-visual-1"},
                )
            ],
            tool_results=[{"tool": "workbench_video_detection", "ok": True}],
            audit_id="audit-visual-1",
            applied_skill={
                "skill": "visual-patrol",
                "reply": "按视觉巡检 skill 输出。",
                "highlights": ["PPE 风险"],
                "next_actions": ["人工复核"],
            },
        )

    monkeypatch.setattr("chitung_center.app.orchestrator.handle_message", fake_handle_message)

    client = TestClient(app)
    response = client.post(
        "/api/chat/message",
        json={"channel": "local_chat", "user_id": "chen", "message": "检查摄像头 PPE 风险"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_name"] == "workflow_visual_patrol"
    assert payload["workflow_run_id"] == "workflow-visual-1"
    assert payload["skill"]["name"] == "visual-patrol"
    assert payload["applied_skill"]["skill"] == "visual-patrol"

    history = client.get(f"/api/chat/history?session_id={payload['session_id']}").json()

    assistant = history["messages"][1]
    assert assistant["workflow_run_id"] == "workflow-visual-1"
    assert assistant["metadata"]["workflow_name"] == "workflow_visual_patrol"
    assert assistant["metadata"]["skill"]["name"] == "visual-patrol"
    assert assistant["metadata"]["applied_skill"]["skill"] == "visual-patrol"


def test_each_supported_chat_intent_has_one_workflow_and_skill():
    from chitung_center.intent_router import INTENT_TOOL_DEFAULTS
    from chitung_center.skills import skill_loader
    from chitung_center.workflow_templates import workflow_for_intent

    supported_intents = [
        "hazard_intake",
        "visual_detection",
        "document_form",
        "knowledge_query",
        "weather_news_risk",
    ]

    for intent_name in supported_intents:
        workflow = workflow_for_intent(intent_name)
        skill = skill_loader.skill_for_intent(intent_name)

        assert workflow is not None, intent_name
        assert workflow.intent == intent_name
        assert skill is not None, intent_name
        assert skill.enabled is True
        assert INTENT_TOOL_DEFAULTS[intent_name]


def test_router_treats_public_opinion_as_external_risk():
    from chitung_center.intent_router import route_intent
    from chitung_center.skills import skill_loader

    intent = route_intent("帮我生成今天香港工地安全舆情简报")

    assert intent.intent == "weather_news_risk"
    assert "fetch_hk_industrial_news" in intent.suggested_tools
    assert skill_loader.skill_for_intent("weather_news_risk").name == "daily-risk-briefing"


def test_chatbox_intents_have_one_skill_each():
    from chitung_center.skills import skill_loader

    expected = {
        "hazard_intake": "hazard-intake",
        "visual_detection": "visual-patrol",
        "document_form": "shanshan-doc",
        "weather_news_risk": "daily-risk-briefing",
        "knowledge_query": "knowledge-query",
    }

    for intent, skill_name in expected.items():
        skill = skill_loader.skill_for_intent(intent)
        assert skill is not None, intent
        assert skill.name == skill_name
