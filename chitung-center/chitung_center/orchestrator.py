from __future__ import annotations

from typing import Any

from chitung_center.audit import audit_logger
from chitung_center.docmate_service import generate_changeset, preview_changeset, read_docx
from chitung_center.external_monitor_skill_service import apply_external_monitor_skill
from chitung_center.intent_router import INTENT_TOOL_DEFAULTS, route_intent_with_llm
from chitung_center.job_service import create_job, mark_failed, mark_finished, mark_running, start_background_job, update_progress
from chitung_center.long_term_memory_service import summarize_today_into_memory
from chitung_center.models import ActionCard, ChatMessageRequest, ChatMessageResponse, IntentResult
from chitung_center.skill_service import enhance_with_skill
from chitung_center.skills import skill_loader
from chitung_center.coach_service import COACH_PROFILES, coach_by_skill_name, coach_profile_for_intent
from chitung_center.workflow_engine import workflow_engine
from chitung_center.workflow_templates import WorkflowTemplate, workflow_for_intent


class ChitungOrchestrator:
    async def handle_message(self, request: ChatMessageRequest) -> ChatMessageResponse:
        route = skill_loader.resolve_route(request.message, request.metadata)
        if route:
            skill_info = skill_loader.get_info(route.skill_name)
            if skill_info and not skill_info.enabled:
                return self._skill_disabled_response(request, skill_info)

            if route.intent == "long_term_memory":
                return await self._handle_long_term_memory_skill(request)

            if route.intent in {profile.intent for profile in COACH_PROFILES.values()}:
                return await self._handle_usage_coach_skill(request, route.intent)

            if route.intent == "external_info_monitor":
                return await self._handle_external_monitor_skill(request)

            intent = IntentResult(
                intent=route.intent,  # type: ignore[arg-type]
                confidence=route.confidence,
                reason=route.reason,
                suggested_tools=INTENT_TOOL_DEFAULTS.get(route.intent, []),
            )
        else:
            if _is_long_term_memory_skill_request(request.message):
                return await self._handle_long_term_memory_skill(request)

            coach_intent = _match_usage_coach_request(request.message)
            if coach_intent:
                return await self._handle_usage_coach_skill(request, coach_intent)

            if _is_external_monitor_skill_request(request.message):
                return await self._handle_external_monitor_skill(request)

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

        if template and intent.intent == "visual_detection":
            return await self._handle_visual_patrol_background(request, intent, template)

        if template:
            job = create_job(
                job_type="agent_workflow",
                title=f"Agent 执行：{template.title}",
                source_module="agent_orchestrator",
                request={"intent": intent.intent, "workflow_name": template.workflow_name, "message": request.message},
            )
            job_id = str(job["job_id"])
            mark_running(job_id)
            run = await workflow_engine.run_for_intent(intent.intent, request)
            if run.get("ok"):
                mark_finished(
                    job_id,
                    result={
                        "intent": intent.intent,
                        "workflow_name": template.workflow_name,
                        "tool_count": len(run.get("tool_results") or []),
                        "card_count": len(run.get("cards") or []),
                    },
                )
            else:
                mark_failed(job_id, str(run.get("error") or run.get("reply") or "Agent workflow failed."))
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
                    agent_trace=_build_agent_trace(intent.intent, run, applied_skill),
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
            agent_trace=[
                {"stage": "plan", "status": "done", "title": "意图识别", "detail": intent.reason},
                {"stage": "result", "status": "done", "title": "等待进一步指令", "detail": "未匹配到可直接执行的工作流。"},
            ],
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

    async def _handle_visual_patrol_background(
        self,
        request: ChatMessageRequest,
        intent: IntentResult,
        template: WorkflowTemplate,
    ) -> ChatMessageResponse:
        from chitung_center.app_config_service import get_app_config
        from chitung_center.workbench_video_detection_service import _resolve_cameras

        enabled_cameras = [
            cam for cam in get_app_config().get("cameras", []) if isinstance(cam, dict) and cam.get("enabled", True)
        ]
        selected = _resolve_cameras(detection_direction=request.message)
        camera_count = len(selected) or len(enabled_cameras)

        async def runner(job_id: str) -> dict[str, Any]:
            update_progress(job_id, 15, f"正在巡检 {camera_count} 路摄像头（抽帧 + YOLO + VLM）...")
            run = await workflow_engine.run_for_intent(intent.intent, request)
            update_progress(job_id, 95, "视觉巡检完成，正在整理报告")
            if not run.get("ok"):
                raise RuntimeError(str(run.get("error") or run.get("reply") or "visual_patrol_failed"))
            return run

        job = start_background_job(
            job_type="visual_patrol",
            title=f"视觉巡检：{request.message[:48]}",
            source_module="agent_orchestrator",
            request={
                "intent": intent.intent,
                "workflow_name": template.workflow_name,
                "message": request.message,
                "camera_count": camera_count,
            },
            runner=runner,
        )
        job_id = str(job["job_id"])
        audit_id = audit_logger.write(
            "visual_patrol_background_started",
            {"job_id": job_id, "camera_count": camera_count, "message": request.message[:120]},
        )
        reply = (
            f"已提交视觉巡检后台任务，将巡检 {camera_count} 路摄像头（抽帧 → YOLO → VLM）。"
            f"预计 2–5 分钟，任务号 {job_id}；完成后本对话会自动更新结果，也可在「执行中心」查看。"
        )
        return ChatMessageResponse(
            reply=reply,
            intent=intent,
            cards=[
                ActionCard(
                    card_type="visual_patrol_job",
                    title="视觉巡检进行中",
                    summary=reply,
                    actions=[{"id": "open_execution_center", "label": "打开执行中心"}],
                    data={"job_id": job_id, "camera_count": camera_count},
                )
            ],
            tool_results=[],
            audit_id=audit_id,
            agent_trace=[
                {"stage": "plan", "status": "done", "title": "意图识别", "detail": intent.reason},
                {"stage": "dispatch", "status": "done", "title": "后台任务已提交", "detail": job_id},
                {"stage": "execute", "status": "running", "title": "视觉巡检执行中", "detail": f"{camera_count} 路摄像头"},
            ],
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

    async def _handle_external_monitor_skill(self, request: ChatMessageRequest) -> ChatMessageResponse:
        result = await apply_external_monitor_skill(request.message)
        reply = str(result.get("summary") or "外部讯息监听设置已处理。")
        audit_id = audit_logger.write(
            "chat_message_handled",
            {
                "channel": request.channel,
                "user_id": request.user_id,
                "intent": "external_info_monitor",
                "tool_count": 1,
                "workflow": False,
                "handler": "external_info_monitor_skill",
            },
        )
        return ChatMessageResponse(
            reply=reply,
            intent=IntentResult(
                intent="external_info_monitor",
                confidence=0.98,
                reason="Matched external-info-monitor skill marker or monitor command.",
                suggested_tools=["external_info_monitor"],
            ),
            cards=[
                ActionCard(
                    card_type="external_info_monitor_skill",
                    title="外部讯息监听",
                    summary=reply,
                    actions=[{"id": "open_external_info_monitor", "label": "打开外部讯息"}],
                    data=result,
                )
            ],
            tool_results=[{"tool": "external_info_monitor_skill", **result}],
            audit_id=audit_id,
            applied_skill={
                "name": "external-info-monitor",
                "reply": reply,
                "result": result,
            },
            agent_trace=[
                {"stage": "plan", "status": "done", "title": "外部讯息监听 Skill", "detail": "解析关键词、来源、频率和立即监听意图。"},
                {"stage": "execute", "status": "done", "title": "保存/触发监听", "detail": reply},
                {"stage": "result", "status": "done", "title": "处理完成", "detail": str(result.get("job_id") or "设置已更新")},
            ],
        )

    async def _handle_long_term_memory_skill(self, request: ChatMessageRequest) -> ChatMessageResponse:
        result = await summarize_today_into_memory(user_id=request.user_id)
        reply = str(result.get("message") or "长期记忆已更新。")
        summary = str(result.get("summary") or "")
        audit_id = audit_logger.write(
            "chat_message_handled",
            {
                "channel": request.channel,
                "user_id": request.user_id,
                "intent": "long_term_memory",
                "handler": "long_term_memory_skill",
                "message_count": result.get("message_count"),
            },
        )
        return ChatMessageResponse(
            reply=f"{reply}\n\n本次压缩摘要：\n{summary}",
            intent=IntentResult(
                intent="long_term_memory",
                confidence=0.96,
                reason="Matched long-term memory skill trigger.",
                suggested_tools=["long_term_memory_summarize_today"],
            ),
            cards=[
                ActionCard(
                    card_type="long_term_memory",
                    title="长期记忆已更新",
                    summary=reply,
                    actions=[{"id": "open_long_term_memory", "label": "查看长期记忆"}],
                    data={
                        "reserved_module": "long_term_memory",
                        "summary": summary,
                        "memory_path": (result.get("memory") or {}).get("path") if isinstance(result.get("memory"), dict) else "",
                    },
                )
            ],
            tool_results=[{"tool": "long_term_memory_summarize_today", **result}],
            audit_id=audit_id,
            applied_skill={
                "name": "long-term-memory",
                "display_name": "长期记忆",
                "summary": reply,
            },
            agent_trace=[
                {"stage": "plan", "status": "done", "title": "读取今日对话", "detail": "从本地聊天记录筛选今日消息。"},
                {"stage": "execute", "status": "done", "title": "压缩长期记忆", "detail": "总结为 Markdown 片段并写入统一记忆文档。"},
                {"stage": "result", "status": "done", "title": "记忆更新完成", "detail": summary[:180]},
            ],
        )


    async def _handle_usage_coach_skill(self, request: ChatMessageRequest, intent: str) -> ChatMessageResponse:
        profile = coach_profile_for_intent(intent)
        if not profile:
            raise ValueError(f"unknown usage coach intent: {intent}")
        result = await coach_by_skill_name(
            profile.skill_name,
            user_message=request.message,
            session_id=request.session_id,
            user_id=request.user_id,
        )
        reply = str(result.get("reply") or "我可以继续帮你梳理步骤。")
        actions = [{"id": action_id, "label": label} for action_id, label in profile.open_actions]
        audit_id = audit_logger.write(
            "chat_message_handled",
            {
                "channel": request.channel,
                "user_id": request.user_id,
                "intent": profile.intent,
                "tool_count": 0,
                "workflow": False,
                "handler": "usage_coach",
                "coach_skill": profile.skill_name,
                "mode": result.get("mode"),
            },
        )
        return ChatMessageResponse(
            reply=reply,
            intent=IntentResult(
                intent=profile.intent,  # type: ignore[arg-type]
                confidence=0.97,
                reason=f"Matched {profile.display_name}.",
                suggested_tools=[],
            ),
            cards=[
                ActionCard(
                    card_type="usage_coach",
                    title=profile.display_name,
                    summary="纯对话指导，结合本地使用记录个性化建议。",
                    actions=actions,
                    data={
                        "reserved_module": profile.domain,
                        "coach_skill": profile.skill_name,
                        "mode": result.get("mode"),
                        "usage_summary": (result.get("usage") or {}).get("totals", {}),
                        "follow_up_questions": result.get("follow_up_questions") or [],
                    },
                )
            ],
            tool_results=[],
            audit_id=audit_id,
            applied_skill={
                "name": profile.skill_name,
                "display_name": profile.display_name,
                "reply": reply,
                "mode": result.get("mode"),
            },
            agent_trace=[
                {"stage": "plan", "status": "done", "title": "读取本地使用快照", "detail": profile.domain},
                {"stage": "coach", "status": "done", "title": "生成指导回复", "detail": str(result.get("mode") or "llm_coach")},
                {"stage": "result", "status": "done", "title": "等待用户追问", "detail": "不执行工具、不生成 Skill 文件"},
            ],
        )


    def _skill_disabled_response(self, request: ChatMessageRequest, skill_info) -> ChatMessageResponse:
        label = skill_info.display_name or skill_info.name
        audit_id = audit_logger.write(
            "chat_message_handled",
            {
                "channel": request.channel,
                "user_id": request.user_id,
                "intent": "general_chat",
                "handler": "skill_disabled",
                "skill": skill_info.name,
            },
        )
        return ChatMessageResponse(
            reply=f"技能「{label}」当前已停用。请在中台 Skill 页面重新启用，或换一种说法继续。",
            intent=IntentResult(
                intent="general_chat",
                confidence=0.9,
                reason=f"Skill disabled: {skill_info.name}",
                suggested_tools=[],
            ),
            cards=[],
            tool_results=[],
            audit_id=audit_id,
        )


orchestrator = ChitungOrchestrator()


def _build_agent_trace(intent: str, workflow_run: dict[str, Any], applied_skill: dict[str, Any] | None) -> list[dict[str, Any]]:
    trace: list[dict[str, Any]] = [
        {
            "stage": "plan",
            "status": "done",
            "title": "意图识别与工作流选择",
            "detail": f"intent={intent}, workflow={workflow_run.get('workflow_name') or workflow_run.get('workflow_run_id') or 'matched'}",
        }
    ]
    for item in workflow_run.get("tool_results") or []:
        if not isinstance(item, dict):
            continue
        tool = str(item.get("tool") or item.get("source") or "tool")
        ok = item.get("ok", True) is not False
        trace.append(
            {
                "stage": "execute",
                "status": "done" if ok else "error",
                "title": f"调用工具：{tool}",
                "detail": str(item.get("summary") or item.get("error") or "工具已返回结果。"),
            }
        )
    cards = workflow_run.get("cards") or []
    if cards:
        trace.append(
            {
                "stage": "result",
                "status": "done",
                "title": "生成结果卡片",
                "detail": f"共 {len(cards)} 张卡片，需要人工确认的动作会进入确认中心。",
            }
        )
    if applied_skill:
        trace.append(
            {
                "stage": "skill",
                "status": "done",
                "title": f"应用 Skill：{applied_skill.get('skill') or applied_skill.get('name')}",
                "detail": str(applied_skill.get("reply") or "Skill 已参与生成回复。"),
            }
        )
    return trace


def _is_external_monitor_skill_request(message: str) -> bool:
    normalized = message.replace(" ", "").lower()
    return (
        "external-info-monitor" in normalized
        or "外部讯息监听" in normalized
        or "外部信息监听" in normalized
        or ("使用技能" in normalized and ("外部讯息" in normalized or "外部信息" in normalized))
        or ("监听" in normalized and ("外部讯息" in normalized or "外部信息" in normalized))
    )


def _is_long_term_memory_skill_request(message: str) -> bool:
    normalized = message.replace(" ", "").lower()
    return (
        "long-term-memory" in normalized
        or "longtermmemory" in normalized
        or "长期记忆" in normalized
        or "長期記憶" in normalized
        or "长期记忆技能" in normalized
        or "记住今天" in normalized
        or "記住今天" in normalized
        or "总结今日对话" in normalized
        or "總結今日對話" in normalized
    )


def _match_usage_coach_request(message: str) -> str | None:
    normalized = message.replace(" ", "").lower()
    if "skill使用教练" in normalized or "skill教练" in normalized or ("使用技能" in normalized and "教练" in normalized and "skill" in normalized):
        return "skill_usage_coach"
    if "自动化使用教练" in normalized or "自动化教练" in normalized or ("自动化" in normalized and "教练" in normalized):
        return "automation_usage_coach"
    if (
        "工作流使用教练" in normalized
        or "工作流教练" in normalized
        or "编排教练" in normalized
        or "workflowcoach" in normalized
        or ("工作流" in normalized and "教练" in normalized)
        or "教我编排" in normalized
    ):
        return "workflow_usage_coach"
    return None


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
        "我是赤瞳 AI 助手，定位是赤瞳中台的编排助手。你可以直接用自然语言说出需求，我会按 Skill 意图路由到对应能力：\n"
        "1. 隐患闭环：登记隐患、整改跟进和确认卡片。\n"
        "2. CCTV/视觉巡检：摄像头、图片、视频风险识别。\n"
        "3. 表格和文档：模板填表、DocMate 文档润色与修改预览。\n"
        "4. 天气和外部风险：天气查询、新闻舆情和每日简报。\n"
        "5. 制度问答：安全制度、规程和管理要求检索。\n"
        "6. WhatsApp 灵讯：本地数据库查询与 wacli 只读诊断。\n"
        "7. 外部讯息监听：配置关键词并立即监听。\n"
        "8. 长期记忆：总结今日对话写入共享记忆文档。\n"
        "也可以在聊天框点 🔨 技能，或说「使用技能：xxx」明确指定。"
    )
