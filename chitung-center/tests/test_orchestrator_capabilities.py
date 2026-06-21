from __future__ import annotations

import asyncio
import os
import sys
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "chitung-center"))

from chitung_center.models import ChatMessageRequest
from chitung_center.orchestrator import ChitungOrchestrator
from chitung_center.intent_router import route_intent, route_intent_with_llm
from chitung_center.workflow_engine import WorkflowEngine, _extract_briefing_text


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

    assert intent.intent == "weather_news_risk"
    assert "LLM routing failed" in intent.reason


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
