from __future__ import annotations

from typing import Any

from chitung_center.audit import audit_logger
from chitung_center.intent_router import route_intent_with_llm
from chitung_center.models import ActionCard, ChatMessageRequest, ChatMessageResponse, IntentResult
from chitung_center.skill_service import enhance_with_skill
from chitung_center.workflow_engine import workflow_engine
from chitung_center.workflow_templates import workflow_for_intent


class ChitungOrchestrator:
    async def handle_message(self, request: ChatMessageRequest) -> ChatMessageResponse:
        if _is_identity_question(request.message) or _is_capability_question(request.message):
            audit_id = audit_logger.write(
                "chat_message_handled",
                {
                    "channel": request.channel,
                    "user_id": request.user_id,
                    "intent": "general_chat",
                    "tool_count": 0,
                    "workflow": False,
                    "handler": "identity_capability",
                },
            )
            return ChatMessageResponse(
                reply=_capability_reply(),
                intent=IntentResult(
                    intent="general_chat",
                    confidence=0.95,
                    reason="Matched identity/capability help question.",
                    suggested_tools=[],
                ),
                cards=[],
                tool_results=[],
                audit_id=audit_id,
            )

        intent = await route_intent_with_llm(request.message)
        template = workflow_for_intent(intent.intent)

        if template:
            run = await workflow_engine.run_for_intent(intent.intent, request)
            if run.get("ok"):
                cards = [ActionCard.model_validate(card) for card in (run.get("cards") or [])]
                reply = str(run.get("reply") or "")
                applied_skill = None
                try:
                    applied_skill = await enhance_with_skill(intent.intent, request.message, run)
                except Exception:  # noqa: BLE001 — skill layer must never block workflow output
                    applied_skill = None
                if applied_skill and applied_skill.get("reply") and not _should_preserve_workflow_reply(cards):
                    reply = applied_skill["reply"]
                return ChatMessageResponse(
                    reply=reply,
                    intent=intent,
                    cards=cards,
                    tool_results=run.get("tool_results") or [],
                    audit_id=str(run.get("audit_id") or ""),
                    applied_skill=applied_skill,
                )

        audit_id = audit_logger.write(
            "chat_message_handled",
            {
                "channel": request.channel,
                "user_id": request.user_id,
                "intent": intent.intent,
                "tool_count": 0,
                "workflow": False,
            },
        )
        if _is_capability_question(request.message):
            return ChatMessageResponse(
                reply=_capability_reply(),
                intent=intent,
                cards=[],
                tool_results=[],
                audit_id=audit_id,
            )
        return ChatMessageResponse(
            reply="我已收到，会按赤瞳中台的意图路由继续判断下一步工具。",
            intent=intent,
            cards=[],
            tool_results=[],
            audit_id=audit_id,
        )

    async def handle_card_action(
        self,
        action_id: str,
        card_data: dict[str, Any],
        *,
        user_id: str = "local_user",
        channel: str = "local_web",
    ) -> dict[str, Any]:
        from chitung_center.confirmation_service import handle_card_action as confirm_handle_card_action

        return await confirm_handle_card_action(
            action_id=action_id,
            card_data=card_data,
            user_id=user_id,
            channel=channel,
        )


orchestrator = ChitungOrchestrator()


def _is_capability_question(message: str) -> bool:
    lowered = message.lower()
    normalized = lowered.replace(" ", "")
    return any(
        keyword in normalized
        for keyword in [
            "你能干嘛",
            "你能干啥",
            "你能做什么",
            "你能帮啥",
            "你会什么",
            "能干点啥",
            "支持哪些功能",
            "支持什么功能",
            "有哪些功能",
            "功能列表",
            "help",
            "怎么用",
            "使用帮助",
            "菜单",
        ]
    )


def _should_preserve_workflow_reply(cards: list[ActionCard]) -> bool:
    return any(card.card_type in {"whatsapp_send_confirmation"} for card in cards)


def _is_identity_question(message: str) -> bool:
    normalized = message.lower().replace(" ", "")
    return any(
        keyword in normalized
        for keyword in [
            "你是谁",
            "你叫什么",
            "你是什么",
            "你是做什么的",
            "介绍一下自己",
            "自我介绍",
            "whoareyou",
            "whatcanyoudo",
        ]
    )


def _capability_reply() -> str:
    return (
        "我是赤瞳 AI 助手，定位是赤瞳安全智能平台的中台编排助手。我可以帮你做这些事：\n"
        "1. 隐患闭环：接收隐患描述，生成整改动作和确认卡片。\n"
        "2. CCTV/视觉巡检：打开监控巡检入口，辅助识别现场风险。\n"
        "3. 表格和文档：按模板起草检查表、整改通知和报告草稿。\n"
        "4. 天气和外部风险：拉取香港天气、新闻和工伤风险，生成每日简报。\n"
        "5. 安全制度问答：围绕项目安全制度、规程和管理要求做查询。\n"
        "6. WhatsApp 灵讯：查询本地 wacli.db，执行只读 wacli 诊断和消息检索。"
    )
