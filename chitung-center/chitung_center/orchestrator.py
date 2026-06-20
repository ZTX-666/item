from __future__ import annotations

from typing import Any

from chitung_center.audit import audit_logger
from chitung_center.intent_router import route_intent
from chitung_center.models import ActionCard, ChatMessageRequest, ChatMessageResponse
from chitung_center.skill_service import enhance_with_skill
from chitung_center.workflow_engine import workflow_engine
from chitung_center.workflow_templates import workflow_for_intent


class ChitungOrchestrator:
    async def handle_message(self, request: ChatMessageRequest) -> ChatMessageResponse:
        intent = route_intent(request.message)
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
                if applied_skill and applied_skill.get("reply"):
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
