from __future__ import annotations

from typing import Any

from chitung_center.audit import audit_logger
from chitung_center.docmate_service import generate_changeset, preview_changeset, read_docx
from chitung_center.intent_router import route_intent_with_llm
from chitung_center.models import ActionCard, ChatMessageRequest, ChatMessageResponse, IntentResult
from chitung_center.skill_service import enhance_with_skill
from chitung_center.workflow_engine import workflow_engine
from chitung_center.workflow_templates import WorkflowTemplate, workflow_for_intent


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

        if intent.intent == "docmate_edit":
            return await self._handle_docmate_edit(request, intent, template)

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

    async def _handle_docmate_edit(
        self,
        request: ChatMessageRequest,
        intent: IntentResult,
        template: WorkflowTemplate | None,
    ) -> ChatMessageResponse:
        params = _assistant_entry_params(request)
        file_path = str(params.get("file_path") or request.metadata.get("file_path") or "").strip()
        doc_id = str(params.get("doc_id") or request.metadata.get("doc_id") or "").strip()
        instruction = str(params.get("instruction") or request.metadata.get("instruction") or request.message).strip()
        context = params.get("context", request.metadata.get("context"))
        workflow_name = template.workflow_name if template else "workflow_docmate_edit"

        if not file_path and not doc_id:
            reply = "已进入 DocMate 文档编辑模式。请先上传 .docx 文件，随后我会生成可预览、可确认的修改方案。"
            audit_id = audit_logger.write(
                "chat_message_handled",
                {
                    "channel": request.channel,
                    "user_id": request.user_id,
                    "intent": intent.intent,
                    "tool_count": 0,
                    "workflow": True,
                    "workflow_name": workflow_name,
                },
            )
            return ChatMessageResponse(
                reply=reply,
                intent=intent,
                cards=[
                    ActionCard(
                        card_type="docmate_edit",
                        title="DocMate 文档编辑",
                        summary="上传 DOCX 后生成 changeset 预览；人工确认后再 commit。",
                        actions=[
                            {"id": "upload_docmate_file", "label": "上传 DOCX"},
                            {"id": "open_docmate_edit", "label": "打开 DocMate"},
                        ],
                        data={
                            "reserved_module": "docmate_edit",
                            "workflow_name": workflow_name,
                            "accepted_file_types": [".docx"],
                            "message": request.message,
                        },
                    )
                ],
                tool_results=[],
                audit_id=audit_id,
                applied_skill=_docmate_skill_payload(reply),
            )

        tool_results: list[dict[str, Any]] = []
        if file_path and not doc_id:
            read_result = await read_docx(file_path)
            tool_results.append({"tool": "docmate_read_docx", **read_result})
            doc_id = str(_nested(read_result, "data", "doc_id") or "")
            if not read_result.get("ok") or not doc_id:
                return _docmate_error_response(request, intent, workflow_name, tool_results, "DocMate 读取 DOCX 失败，请确认文件路径和格式。")

        gen_result = await generate_changeset(doc_id, instruction, context)
        tool_results.append({"tool": "docmate_generate_changeset", **gen_result})
        if not gen_result.get("ok"):
            return _docmate_error_response(
                request,
                intent,
                workflow_name,
                tool_results,
                str(gen_result.get("summary") or "DocMate 未能生成修改方案，请补充更具体的编辑指令。"),
            )

        changeset_id = str(_nested(gen_result, "data", "changeset_id") or "")
        preview_result = await preview_changeset(changeset_id)
        tool_results.append({"tool": "docmate_preview_changeset", **preview_result})
        preview_cards = _nested(preview_result, "data", "preview_cards") or _nested(gen_result, "data", "preview_cards") or []
        total_changes = len(preview_cards) if isinstance(preview_cards, list) else 0
        reply = f"DocMate 已生成 {total_changes} 项修改预览。请先核对 changeset，再选择要提交的变更。"
        audit_id = audit_logger.write(
            "workflow_completed",
            {
                "workflow_name": workflow_name,
                "intent": intent.intent,
                "tool_count": len(tool_results),
                "card_count": 1,
            },
        )
        return ChatMessageResponse(
            reply=reply,
            intent=intent,
            cards=[
                ActionCard(
                    card_type="docmate_changeset_preview",
                    title="DocMate 修改预览",
                    summary=reply,
                    actions=[
                        {"id": "commit_docmate_changeset", "label": "提交已选变更"},
                        {"id": "retry_docmate_changeset", "label": "重新生成"},
                    ],
                    data={
                        "reserved_module": "docmate_edit",
                        "workflow_name": workflow_name,
                        "doc_id": doc_id,
                        "changeset_id": changeset_id,
                        "preview_cards": preview_cards,
                        "generate_result": gen_result,
                    },
                )
            ],
            tool_results=tool_results,
            audit_id=audit_id,
            applied_skill=_docmate_skill_payload(reply),
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


def _assistant_entry_params(request: ChatMessageRequest) -> dict[str, Any]:
    params = request.metadata.get("assistant_entry_params")
    return params if isinstance(params, dict) else {}


def _docmate_error_response(
    request: ChatMessageRequest,
    intent: IntentResult,
    workflow_name: str,
    tool_results: list[dict[str, Any]],
    reply: str,
) -> ChatMessageResponse:
    audit_id = audit_logger.write(
        "workflow_completed",
        {
            "workflow_name": workflow_name,
            "intent": intent.intent,
            "tool_count": len(tool_results),
            "card_count": 1,
            "ok": False,
        },
    )
    return ChatMessageResponse(
        reply=reply,
        intent=intent,
        cards=[
            ActionCard(
                card_type="docmate_edit",
                title="DocMate 文档编辑",
                summary=reply,
                actions=[
                    {"id": "upload_docmate_file", "label": "重新上传"},
                    {"id": "retry_docmate_changeset", "label": "重试"},
                ],
                data={"reserved_module": "docmate_edit", "workflow_name": workflow_name, "message": request.message},
            )
        ],
        tool_results=tool_results,
        audit_id=audit_id,
        applied_skill=_docmate_skill_payload(reply),
    )


def _docmate_skill_payload(reply: str) -> dict[str, Any]:
    return {
        "skill": "docmate-edit",
        "reply": reply,
        "highlights": ["DOCX 上传", "changeset 预览", "人工确认后 commit", "失败可 retry"],
        "next_actions": ["上传 .docx 文件", "审阅修改预览", "提交已选变更"],
    }


def _nested(value: dict[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


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
