from __future__ import annotations

from typing import Any

from chitung_center.audit import audit_logger
from chitung_center.intent_router import route_intent
from chitung_center.models import ActionCard, ChatMessageRequest, ChatMessageResponse
from chitung_center.toolbox_client import toolbox_client


class ChitungOrchestrator:
    async def handle_message(self, request: ChatMessageRequest) -> ChatMessageResponse:
        intent = route_intent(request.message)
        tool_results: list[dict[str, Any]] = []
        cards: list[ActionCard] = []

        if intent.intent == "hazard_intake":
            result = await self._try_ingest_chat_hazard(request)
            tool_results.append(result)
            cards.append(
                ActionCard(
                    card_type="hazard_review",
                    title="隐患线索已归档，等待确认",
                    summary="系统已把消息作为安全隐患线索处理，可继续生成整改通知或关联表格。",
                    actions=[
                        {"id": "draft_rectification_notice", "label": "生成整改通知草稿"},
                        {"id": "link_required_forms", "label": "推荐相关表格"},
                    ],
                    data={"source": "chat", "tool_result": result},
                )
            )
            reply = "我已按安全隐患线索处理，并生成了待确认卡片。"
        elif intent.intent == "weather_news_risk":
            weather_result = await self._try_call_tool("fetch_hko_weather", {"lang": "tc"})
            updates_result = await self._try_call_tool("fetch_hk_safety_updates", {"limit_per_source": 5})
            persist_result = await self._try_call_tool(
                "persist_external_risk_items",
                {"weather_result": weather_result, "safety_updates_result": updates_result, "source_batch": "daily_risk"},
            )
            briefing_result = await self._try_call_tool(
                "draft_daily_risk_briefing",
                {"weather_result": weather_result, "safety_updates_result": updates_result},
            )
            form_link_result = await self._try_call_tool(
                "link_external_risk_to_forms",
                {"weather_result": weather_result, "safety_updates_result": updates_result, "limit_per_risk": 5},
            )
            tool_results.extend([weather_result, updates_result, persist_result, briefing_result, form_link_result])
            cards.append(
                ActionCard(
                    card_type="external_risk_briefing",
                    title="晴晴外部风险监测",
                    summary="已抓取香港天文台天气、官方来源和白名单媒体的施工安全相关更新，并生成每日简报草稿。",
                    actions=[{"id": "generate_daily_briefing", "label": "生成每日风险简报"}],
                    data={
                        "reserved_module": "external_risk",
                        "weather": weather_result,
                        "updates": updates_result,
                        "persist": persist_result,
                        "briefing": briefing_result,
                        "form_links": form_link_result,
                    },
                )
            )
            reply = "我已进入“晴晴外部风险监测”，并生成了每日外部风险简报草稿。"
        elif intent.intent == "document_form":
            template_result = await self._try_call_tool(
                "search_form_templates",
                {"query": request.message, "limit": 10},
            )
            tool_results.append(template_result)
            cards.append(
                ActionCard(
                    card_type="document_form_reserved",
                    title="闪闪文档填表流程",
                    summary="已搜索制度表格模板，可继续进行字段预填和 DOCX 草稿生成。",
                    actions=[{"id": "search_form_templates", "label": "查找表格模板"}],
                    data={"reserved_module": "document_form", "templates": template_result},
                )
            )
            reply = "我已搜索相关表格模板，并返回填表流程卡片。"
        elif intent.intent == "knowledge_query":
            policy_result = await self._try_call_tool(
                "search_policy_clauses",
                {"query": request.message, "limit": 5},
            )
            tool_results.append(policy_result)
            cards.append(
                ActionCard(
                    card_type="policy_search",
                    title="制度条款检索",
                    summary="已在本地安全管理办法全文中检索相关条款。",
                    actions=[{"id": "summarize_policy_document", "label": "生成制度摘要"}],
                    data={"policy": policy_result},
                )
            )
            reply = "我已在本地制度文件中检索相关条款。"
        else:
            reply = "我已收到，会按赤瞳中台的意图路由继续判断下一步工具。"

        audit_id = audit_logger.write(
            "chat_message_handled",
            {
                "channel": request.channel,
                "user_id": request.user_id,
                "intent": intent.intent,
                "tool_count": len(tool_results),
            },
        )
        return ChatMessageResponse(
            reply=reply,
            intent=intent,
            cards=cards,
            tool_results=tool_results,
            audit_id=audit_id,
        )

    async def handle_card_action(self, action_id: str, card_data: dict[str, Any]) -> dict[str, Any]:
        audit_id = audit_logger.write(
            "card_action_requested",
            {"action_id": action_id, "card_data_keys": sorted(card_data.keys())},
        )
        return {
            "ok": True,
            "audit_id": audit_id,
            "message": "Action received. The concrete workflow will be wired to AgentToolbox tools.",
            "action_id": action_id,
        }

    async def _try_ingest_chat_hazard(self, request: ChatMessageRequest) -> dict[str, Any]:
        payload = {
            "messages": [
                {
                    "message_id": request.metadata.get("message_id"),
                    "chat_id": request.metadata.get("chat_id", request.channel),
                    "sender": request.user_id,
                    "text": request.message,
                    "timestamp": request.metadata.get("timestamp"),
                    "metadata": request.metadata,
                }
            ]
        }
        try:
            return await toolbox_client.call_tool("ingest_chat_hazards", payload)
        except Exception as exc:  # noqa: BLE001 - keep chat responsive if toolbox is offline.
            return {
                "ok": False,
                "error": str(exc),
                "fallback": "AgentToolbox is unavailable. The card was created locally.",
            }

    async def _try_call_tool(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return await toolbox_client.call_tool(tool_name, payload)
        except Exception as exc:  # noqa: BLE001 - keep chat responsive if toolbox/source is offline.
            return {
                "ok": False,
                "tool_name": tool_name,
                "error": str(exc),
                "fallback": "Tool call failed. The action card was still created locally.",
            }


orchestrator = ChitungOrchestrator()
