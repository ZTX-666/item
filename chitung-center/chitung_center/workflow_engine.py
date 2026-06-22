from __future__ import annotations

import ast
import json
import re
import shlex
from typing import Any

from chitung_center.audit import audit_logger
from chitung_center.confirmation_service import create_pending_confirmation
from chitung_center.config import settings
from chitung_center.external_briefing_store import persist_external_briefing_report
from chitung_center.llm_gateway import llm_gateway
from chitung_center.models import ActionCard, ChatMessageRequest, VisualPatrolDraftRequest, WorkbenchVideoDetectionRequest
from chitung_center.rag_service import rag_service
from chitung_center.toolbox_client import toolbox_client
from chitung_center.whatsapp_local_service import (
    is_whatsapp_command_readonly,
    list_whatsapp_sql_tables,
    run_whatsapp_command,
    run_whatsapp_sql_query,
)
from chitung_center import workflow_store
from chitung_center.visual_patrol_service import build_visual_patrol_draft
from chitung_center.workbench_video_detection_service import run_workbench_video_detection
from chitung_center.workflow_templates import (
    WORKFLOW_TEMPLATES,
    WorkflowTemplate,
    list_workflow_templates,
    workflow_for_intent,
)


class WorkflowEngine:
    async def list_templates(self) -> list[dict[str, Any]]:
        return list_workflow_templates()

    async def get_run(self, workflow_run_id: str) -> dict[str, Any]:
        await workflow_store.ensure_schema()
        # Reuse query via pending confirmations / artifacts is thin; return run metadata from create payload for now.
        return {
            "ok": True,
            "workflow_run_id": workflow_run_id,
            "message": "Workflow run lookup is backed by toolbox workflow tables.",
        }

    async def run_for_intent(self, intent: str, request: ChatMessageRequest) -> dict[str, Any]:
        template = workflow_for_intent(intent)
        if not template:
            return {"ok": False, "error": f"No workflow template for intent={intent}"}
        return await self.run_template(template.workflow_name, request)

    async def run_template(self, workflow_name: str, request: ChatMessageRequest) -> dict[str, Any]:
        template = WORKFLOW_TEMPLATES.get(workflow_name)
        if not template:
            return {"ok": False, "error": f"Unknown workflow: {workflow_name}"}

        await workflow_store.ensure_schema()
        run_result = await workflow_store.create_run(
            workflow_name=workflow_name,
            title=template.title,
            trigger_source="chat_message",
            trigger_payload={"message": request.message, "channel": request.channel},
            channel=request.channel,
            user_id=request.user_id,
            status="running",
            metadata={"intent": template.intent},
        )
        workflow_run_id = _nested(run_result, "workflow_run", "workflow_run_id")
        tool_results: list[dict[str, Any]] = []
        cards: list[ActionCard] = []
        reply = ""

        if workflow_name == "workflow_hazard_intake":
            reply, tool_results, cards = await self._run_hazard_intake(request, workflow_run_id)
        elif workflow_name == "workflow_weather_query":
            reply, tool_results, cards = await self._run_weather_query(request, workflow_run_id)
        elif workflow_name == "workflow_daily_risk_briefing":
            reply, tool_results, cards = await self._run_daily_risk_briefing(request, workflow_run_id)
        elif workflow_name == "workflow_form_filling":
            reply, tool_results, cards = await self._run_form_filling(request, workflow_run_id)
        elif workflow_name == "workflow_knowledge_query":
            reply, tool_results, cards = await self._run_knowledge_query(request, workflow_run_id)
        elif workflow_name == "workflow_whatsapp_sql_query":
            reply, tool_results, cards = await self._run_whatsapp_sql_query(request, workflow_run_id)
        elif workflow_name == "workflow_whatsapp_wacli_ops":
            reply, tool_results, cards = await self._run_whatsapp_wacli_ops(request, workflow_run_id)
        elif workflow_name == "workflow_visual_patrol":
            reply, tool_results, cards = await self._run_visual_patrol(request, workflow_run_id)
        else:
            reply = f"Workflow {workflow_name} is registered but not implemented."

        await workflow_store.link_event(
            workflow_run_id=workflow_run_id,
            event_type="workflow_completed",
            source_type="workflow",
            source_id=workflow_name,
            payload={"tool_count": len(tool_results)},
        )
        audit_id = audit_logger.write(
            "workflow_completed",
            {
                "workflow_name": workflow_name,
                "workflow_run_id": workflow_run_id,
                "intent": template.intent,
                "tool_count": len(tool_results),
                "card_count": len(cards),
            },
        )
        return {
            "ok": True,
            "workflow_name": workflow_name,
            "workflow_run_id": workflow_run_id,
            "reply": reply,
            "cards": [card.model_dump() for card in cards],
            "tool_results": tool_results,
            "audit_id": audit_id,
        }

    async def _run_hazard_intake(
        self,
        request: ChatMessageRequest,
        workflow_run_id: str,
    ) -> tuple[str, list[dict[str, Any]], list[ActionCard]]:
        step = await _start_step(workflow_run_id, "ingest_chat_hazards", "赤瞳守护者", "ingest_chat_hazards")
        payload = {
            "messages": [
                {
                    "message_id": request.metadata.get("message_id"),
                    "chat_id": request.metadata.get("chat_id", request.channel),
                    "sender": request.user_id,
                    "text": request.message,
                    "timestamp": request.metadata.get("timestamp"),
                    "metadata": {**request.metadata, "workflow_run_id": workflow_run_id},
                }
            ]
        }
        result = await _safe_tool("ingest_chat_hazards", payload)
        await _finish_step(step, result)
        await workflow_store.link_event(
            workflow_run_id=workflow_run_id,
            event_type="hazard_ingested",
            source_type="chat",
            source_id=request.channel,
            payload={"ok": result.get("ok")},
        )
        cards = [
            ActionCard(
                card_type="hazard_review",
                title="隐患线索已归档，等待确认",
                summary="系统已把消息作为安全隐患线索处理，可继续生成整改通知或关联表格。",
                actions=[
                    {"id": "draft_rectification_notice", "label": "生成整改通知草稿"},
                    {"id": "link_required_forms", "label": "推荐相关表格"},
                ],
                data={"source": "chat", "tool_result": result, "workflow_run_id": workflow_run_id},
            )
        ]
        return "我已按安全隐患线索处理，并生成了待确认卡片。", [result], cards

    async def _run_weather_query(
        self,
        request: ChatMessageRequest,
        workflow_run_id: str,
    ) -> tuple[str, list[dict[str, Any]], list[ActionCard]]:
        step = await _start_step(workflow_run_id, "fetch_weather", "赤瞳守护者", "fetch_hko_weather")
        weather = await _safe_tool("fetch_hko_weather", {"lang": "tc"})
        await _finish_step(step, weather)
        reply = _plain_weather_reply(weather)
        cards = [
            ActionCard(
                card_type="weather_query",
                title="香港天气",
                summary=reply,
                actions=[],
                data={
                    "reserved_module": "weather",
                    "workflow_run_id": workflow_run_id,
                    "weather": weather,
                },
            )
        ]
        return reply, [weather], cards

    async def _run_daily_risk_briefing(
        self,
        request: ChatMessageRequest,
        workflow_run_id: str,
    ) -> tuple[str, list[dict[str, Any]], list[ActionCard]]:
        results: list[dict[str, Any]] = []
        sources = request.metadata.get("sources")
        keywords = request.metadata.get("keywords")
        area = str(request.metadata.get("area") or "")
        lookback_hours = max(1, int(request.metadata.get("lookback_hours") or 24))
        source_ids = _source_ids_for_external_monitor(sources)
        update_payload: dict[str, Any] = {"limit_per_source": 5, "lookback_hours": lookback_hours}
        if source_ids:
            update_payload["sources"] = source_ids
        if isinstance(keywords, list) and keywords:
            update_payload["keywords"] = [str(item) for item in keywords if str(item).strip()]
        weather_step = await _start_step(workflow_run_id, "fetch_weather", "赤瞳守护者", "fetch_hko_weather")
        weather = await _safe_tool("fetch_hko_weather", {"lang": "tc"})
        await _finish_step(weather_step, weather)
        results.append(weather)

        updates_step = await _start_step(workflow_run_id, "fetch_updates", "赤瞳守护者", "fetch_hk_safety_updates")
        updates = await _safe_tool("fetch_hk_safety_updates", update_payload)
        await _finish_step(updates_step, updates)
        results.append(updates)

        persist_step = await _start_step(workflow_run_id, "persist_risks", "赤瞳守护者", "persist_external_risk_items")
        persist = await _safe_tool(
            "persist_external_risk_items",
            {"weather_result": weather, "safety_updates_result": updates, "source_batch": "daily_risk"},
        )
        await _finish_step(persist_step, persist)
        results.append(persist)

        briefing_step = await _start_step(workflow_run_id, "draft_briefing", "赤瞳守护者", "draft_daily_risk_briefing")
        briefing = await _safe_tool(
            "draft_daily_risk_briefing",
            {"weather_result": weather, "safety_updates_result": updates, "project_name": area},
        )
        await _finish_step(briefing_step, briefing)
        results.append(briefing)

        briefing_text = _extract_briefing_text(briefing)
        report_images = _extract_report_images(weather, updates, briefing)
        report_links = _extract_report_links(updates)
        briefing_report = persist_external_briefing_report(
            {
                "title": f"最近 {lookback_hours} 小时外部讯息简报",
                "summary": f"已生成最近 {lookback_hours} 小时外部讯息图文简报草稿。",
                "briefing_text": briefing_text,
                "workflow_run_id": workflow_run_id,
                "report_images": report_images,
                "report_links": report_links,
                "tool_results": results,
                "config": {
                    "message": request.message,
                    "channel": request.channel,
                    **request.metadata,
                },
            }
        )
        cards = [
            ActionCard(
                card_type="external_risk_briefing",
                title="外部讯息监测",
                summary="已抓取香港天文台天气、官方来源和白名单媒体的施工安全相关更新，并生成图文简报草稿。",
                actions=[{"id": "generate_daily_briefing", "label": "提交发送确认"}],
                data={
                    "reserved_module": "external_risk",
                    "workflow_run_id": workflow_run_id,
                    "weather": weather,
                    "updates": updates,
                    "persist": persist,
                    "briefing": briefing,
                    "briefing_text": briefing_text,
                    "report_images": report_images,
                    "report_links": report_links,
                    "briefing_report_id": briefing_report.get("report_id"),
                    "briefing_report": briefing_report,
                },
            )
        ]
        if _is_plain_weather_question(request.message):
            return _weather_reply(weather), results, cards
        return "已生成今日外部讯息图文简报草稿，包含香港天气、官方安全更新和建议动作。", results, cards

    async def _run_form_filling(
        self,
        request: ChatMessageRequest,
        workflow_run_id: str,
    ) -> tuple[str, list[dict[str, Any]], list[ActionCard]]:
        docmate_keywords = ["改文档", "替换", "润色", "变更", "docx修改", "changeset", "闪闪文档"]
        if any(kw in request.message for kw in docmate_keywords):
            cards = [
                ActionCard(
                    card_type="docmate_edit",
                    title="闪闪文档编辑模式",
                    summary="已识别文档编辑意图，可前往「闪闪文档」页面进行 .docx 文件的读取、修改和预览。",
                    actions=[{"id": "open_shanshan_doc", "label": "打开闪闪文档编辑器"}],
                    data={"reserved_module": "shanshan_doc", "message": request.message, "workflow_run_id": workflow_run_id},
                )
            ]
            return "我已识别为文档编辑任务，建议使用闪闪文档编辑器进行 .docx 的结构化修改。", [], cards

        step = await _start_step(workflow_run_id, "search_templates", "闪闪文档", "search_form_templates")
        template_result = await _safe_tool("search_form_templates", {"query": request.message, "limit": 10})
        await _finish_step(step, template_result)
        cards = [
            ActionCard(
                card_type="document_form_reserved",
                title="闪闪文档填表流程",
                summary="已搜索制度表格模板，可继续进行字段预填和 DOCX 草稿生成。",
                actions=[{"id": "search_form_templates", "label": "查找表格模板"}],
                data={"reserved_module": "document_form", "templates": template_result, "workflow_run_id": workflow_run_id},
            )
        ]
        return "我已搜索相关表格模板，并返回填表流程卡片。", [template_result], cards

    async def _run_knowledge_query(
        self,
        request: ChatMessageRequest,
        workflow_run_id: str,
    ) -> tuple[str, list[dict[str, Any]], list[ActionCard]]:
        step = await _start_step(workflow_run_id, "rag_ask", "耀耀慧读", "rag_ask")
        try:
            answer = await rag_service.answer_question(request.message, top_k=5)
        except Exception as exc:  # noqa: BLE001
            answer = {"ok": False, "tool": "rag_ask", "error": str(exc)}
        await _finish_step(step, answer)
        if answer.get("ok") is not False and str(answer.get("answer") or "").strip():
            result = {"tool": "rag_ask", **answer}
            cards = [
                ActionCard(
                    card_type="rag_answer",
                    title="知识库回答",
                    summary=str(answer.get("answer") or ""),
                    actions=[{"id": "open_yaoyao_rag", "label": "打开知识库"}],
                    data={
                        "workflow_run_id": workflow_run_id,
                        "answer": answer.get("answer"),
                        "citations": answer.get("citations") or [],
                        "matches": answer.get("matches") or [],
                    },
                )
            ]
            return str(answer.get("answer") or ""), [result], cards

        fallback_step = await _start_step(workflow_run_id, "search_policy", "耀耀慧读", "search_policy_clauses")
        policy_result = await _safe_tool("search_policy_clauses", {"query": request.message, "limit": 5})
        await _finish_step(fallback_step, policy_result)
        cards = [
            ActionCard(
                card_type="policy_search",
                title="制度条款检索",
                summary="已在本地安全管理办法全文中检索相关条款。",
                actions=[{"id": "summarize_policy_document", "label": "生成制度摘要"}],
                data={"policy": policy_result, "workflow_run_id": workflow_run_id},
            )
        ]
        return "我已在本地制度文件中检索相关条款。", [policy_result], cards

    async def _run_whatsapp_sql_query(
        self,
        request: ChatMessageRequest,
        workflow_run_id: str,
    ) -> tuple[str, list[dict[str, Any]], list[ActionCard]]:
        plan = _whatsapp_sql_plan(request)
        step = await _start_step(workflow_run_id, "whatsapp_sql_read", "赤瞳灵讯", plan["tool"])
        if plan["kind"] == "tables":
            raw_result = list_whatsapp_sql_tables()
        else:
            raw_result = run_whatsapp_sql_query(str(plan["sql"]), int(plan["limit"]))
        result = {"tool": plan["tool"], "plan": plan, **raw_result}
        await _finish_step(step, result)
        reply = _whatsapp_sql_reply(plan, raw_result)
        cards = [
            ActionCard(
                card_type="whatsapp_sql_query",
                title="WhatsApp SQLite 查询",
                summary=reply,
                actions=[{"id": "open_whatsapp_ops", "label": "打开 WhatsApp 控制台"}],
                data={"workflow_run_id": workflow_run_id, "plan": plan, "result": raw_result},
            )
        ]
        return reply, [result], cards

    async def _run_whatsapp_wacli_ops(
        self,
        request: ChatMessageRequest,
        workflow_run_id: str,
    ) -> tuple[str, list[dict[str, Any]], list[ActionCard]]:
        plan = await _whatsapp_wacli_plan(request)
        args_text = str(plan.get("args") or "").strip()
        step = await _start_step(workflow_run_id, "whatsapp_wacli_readonly", "赤瞳灵讯", "whatsapp_command_run")
        if plan.get("action") == "confirm_required" and args_text:
            raw_result = await _create_whatsapp_send_confirmation(request, workflow_run_id, step, args_text, plan)
        elif plan.get("action") != "run" or not args_text:
            raw_result = {
                "ok": False,
                "summary": str(plan.get("reason") or "模型未给出可执行的只读 wacli 命令。"),
                "error": str(plan.get("error") or "llm_wacli_plan_not_runnable"),
                "data": {"plan": plan},
            }
        else:
            try:
                parsed_args = shlex.split(args_text)
            except ValueError as exc:
                parsed_args = []
                raw_result = {
                    "ok": False,
                    "summary": "模型返回的 wacli 命令参数无法解析。",
                    "error": str(exc),
                    "data": {"plan": plan, "args_text": args_text},
                }
            else:
                if not is_whatsapp_command_readonly(parsed_args):
                    raw_result = {
                        "ok": False,
                        "summary": "模型选择了非只读或高风险 wacli 命令，已拦截。",
                        "error": "unsafe_wacli_command",
                        "data": {"plan": plan, "args": parsed_args},
                    }
                else:
                    prepared = _prepare_wacli_readonly_args(args_text)
                    if not prepared.get("ok", True):
                        raw_result = {
                            "ok": False,
                            "summary": str(prepared.get("summary") or "wacli 命令参数解析失败。"),
                            "error": str(prepared.get("error") or "wacli_args_prepare_failed"),
                            "data": {"plan": plan, "args": parsed_args, "resolution": prepared},
                        }
                    else:
                        run_args_text = str(prepared.get("args_text") or args_text)
                        raw_result = run_whatsapp_command(run_args_text, read_only=True)
                        raw_result = _attach_wacli_arg_resolution(raw_result, args_text, prepared)
                        raw_result = _augment_wacli_result_with_local_fallback(run_args_text, raw_result)
        result = {"tool": "whatsapp_command_run", "args_text": args_text, "plan": plan, **raw_result}
        await _finish_step(step, result)
        if raw_result.get("tool") == "whatsapp_send_confirmation":
            reply = str(raw_result.get("summary") or "WhatsApp 消息发送已进入待确认流程。")
            confirmation = _nested(raw_result, "confirmation") or {}
            cards = [
                ActionCard(
                    card_type="whatsapp_send_confirmation",
                    title="WhatsApp 消息待确认",
                    summary=reply,
                    actions=[
                        {"id": "confirm_send", "label": "批准并发送"},
                        {"id": "reject", "label": "拒绝"},
                    ],
                    data={
                        "workflow_run_id": workflow_run_id,
                        "confirmation_id": confirmation.get("confirmation_id"),
                        "pending_confirmation_id": confirmation.get("confirmation_id"),
                        "result": raw_result,
                    },
                )
            ]
        else:
            reply = _whatsapp_command_reply(args_text, raw_result)
            cards = [
                ActionCard(
                    card_type="whatsapp_wacli_command",
                    title="WhatsApp wacli 只读命令",
                    summary=reply,
                    actions=[{"id": "open_whatsapp_ops", "label": "打开 WhatsApp 控制台"}],
                    data={"workflow_run_id": workflow_run_id, "args_text": args_text, "result": raw_result},
                )
            ]
        return reply, [result], cards

    async def _run_visual_patrol(
        self,
        request: ChatMessageRequest,
        workflow_run_id: str,
    ) -> tuple[str, list[dict[str, Any]], list[ActionCard]]:
        source = request.metadata.get("source") or request.metadata.get("image_path")
        if source:
            draft = await build_visual_patrol_draft(
                VisualPatrolDraftRequest(
                    source=str(source),
                    area=request.metadata.get("area"),
                    contractor=request.metadata.get("contractor"),
                    conf=request.metadata.get("conf"),
                    analysis_mode=request.metadata.get("analysis_mode", "hybrid"),
                    vlm_enabled=bool(request.metadata.get("vlm_enabled", True)),
                    yolo_conf_threshold=float(request.metadata.get("yolo_conf_threshold", 0.45)),
                )
            )
            await workflow_store.link_event(
                workflow_run_id=workflow_run_id,
                event_type="visual_patrol_draft_created",
                source_type="image",
                source_id=str(source),
                payload={"ok": draft.get("ok"), "candidate_count": len(draft.get("candidates") or [])},
            )
            cards = [
                ActionCard(
                    card_type="visual_patrol",
                    title="视觉巡检候选",
                    summary=str(draft.get("message") or "已生成视觉巡检候选，等待人工确认。"),
                    actions=[{"id": "confirm_visual_candidate", "label": "确认入库"}],
                    data={"workflow_run_id": workflow_run_id, "draft": draft},
                )
            ]
            return "已基于本地图片生成视觉巡检候选，请人工确认后入库。", [draft], cards

        step = await _start_step(workflow_run_id, "workbench_video_detection", "赤瞳守护者", "workbench_video_detection")
        camera_ids = request.metadata.get("camera_ids")
        if not isinstance(camera_ids, list):
            camera_ids = []
        detection = await run_workbench_video_detection(
            WorkbenchVideoDetectionRequest(
                detection_direction=request.message,
                camera_id=str(request.metadata.get("camera_id") or "") or None,
                camera_ids=[str(item) for item in camera_ids if str(item).strip()],
                refined_prompt=str(request.metadata.get("refined_prompt") or "") or None,
                vlm_enabled=bool(request.metadata.get("vlm_enabled", True)),
            )
        )
        await _finish_step(step, detection)
        tool_result = {"tool": "workbench_video_detection", **detection}
        summary = detection.get("summary") if isinstance(detection.get("summary"), dict) else {}
        summary_text = str(summary.get("text") or detection.get("message") or detection.get("error") or "")
        cards = [
            ActionCard(
                card_type="video_detection_report",
                title="视频巡检结果",
                summary=summary_text or "视频巡检已执行。",
                actions=[{"id": "open_hazard_ledger", "label": "查看证据"}],
                data={"workflow_run_id": workflow_run_id, "report": detection},
            )
        ]
        if detection.get("ok") is False:
            return summary_text or "视频巡检执行失败。", [tool_result], cards
        return summary_text or "视频巡检已完成，结果已写入本地 SQLite。", [tool_result], cards


workflow_engine = WorkflowEngine()


def _source_ids_for_external_monitor(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    group_map = {
        "weather": [],
        "official": [
            "gov_press_rss",
            "labour_department",
            "housing_authority",
            "development_bureau",
            "buildings_department",
            "oshc",
            "cic",
        ],
        "media": [
            "hk01",
            "sing_tao",
            "ming_pao",
            "oriental_daily",
            "hkcd",
            "rthk",
            "am730",
            "bastille_post",
            "dotdot_news",
            "wenweipo",
        ],
    }
    selected: list[str] = []
    for item in value:
        key = str(item)
        selected.extend(group_map.get(key, [key]))
    return list(dict.fromkeys(selected))


async def _safe_tool(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return await toolbox_client.call_tool(tool_name, payload)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "tool_name": tool_name, "error": str(exc)}


async def _start_step(
    workflow_run_id: str,
    step_name: str,
    agent_name: str,
    tool_name: str | None,
) -> dict[str, Any]:
    result = await workflow_store.append_step(
        workflow_run_id=workflow_run_id,
        step_name=step_name,
        agent_name=agent_name,
        tool_name=tool_name,
        status="running",
    )
    step_id = _nested(result, "workflow_step", "workflow_step_id")
    return {"workflow_step_id": step_id or "", "tool_result": result}


async def _finish_step(step: dict[str, Any], output: dict[str, Any]) -> None:
    step_id = step.get("workflow_step_id")
    if not step_id:
        return
    await workflow_store.update_step(
        workflow_step_id=str(step_id),
        status="succeeded" if output.get("ok", True) else "failed",
        output_payload=output,
        error=str(output.get("error")) if not output.get("ok", True) else None,
    )


def _whatsapp_sql_plan(request: ChatMessageRequest) -> dict[str, Any]:
    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    params = metadata.get("assistant_entry_params") if isinstance(metadata.get("assistant_entry_params"), dict) else {}
    message = _assistant_task_text(request)
    limit = _bounded_int(metadata.get("limit") or params.get("limit"), default=20, minimum=1, maximum=100)
    explicit_sql = str(metadata.get("sql") or params.get("sql") or "").strip()
    extracted_sql = explicit_sql or _extract_select_sql(message)
    if extracted_sql:
        return {"kind": "query", "tool": "whatsapp_sql_query", "sql": extracted_sql, "limit": limit}

    normalized = message.lower()
    if any(token in normalized for token in ["有哪些表", "表名", "表列表", "tables", "schema"]):
        return {"kind": "tables", "tool": "whatsapp_sql_tables", "limit": limit}
    if any(token in normalized for token in ["聊天", "chat"]):
        return {
            "kind": "query",
            "tool": "whatsapp_sql_query",
            "sql": "SELECT jid, kind, name, unread_count, last_message_ts FROM chats ORDER BY last_message_ts DESC",
            "limit": limit,
        }
    if any(token in normalized for token in ["联系人", "contact"]):
        return {
            "kind": "query",
            "tool": "whatsapp_sql_query",
            "sql": "SELECT jid, phone, push_name, full_name, business_name, updated_at FROM contacts ORDER BY updated_at DESC",
            "limit": limit,
        }
    if any(token in normalized for token in ["群组", "群", "group"]):
        return {
            "kind": "query",
            "tool": "whatsapp_sql_query",
            "sql": "SELECT jid, name, owner_jid, updated_at FROM groups ORDER BY updated_at DESC",
            "limit": limit,
        }
    if any(token in normalized for token in ["通话", "call"]):
        return {
            "kind": "query",
            "tool": "whatsapp_sql_query",
            "sql": "SELECT chat_name, sender_name, event_type, direction, media, outcome, ts FROM call_events ORDER BY ts DESC",
            "limit": limit,
        }
    if any(token in normalized for token in ["状态", "status"]):
        return {
            "kind": "query",
            "tool": "whatsapp_sql_query",
            "sql": "SELECT sender_name, text, media_type, media_caption, ts FROM status_messages ORDER BY ts DESC",
            "limit": limit,
        }
    return {
        "kind": "query",
        "tool": "whatsapp_sql_query",
        "sql": "SELECT chat_name, sender_name, text, media_type, filename, ts FROM messages ORDER BY ts DESC",
        "limit": limit,
    }


def _extract_select_sql(message: str) -> str:
    lowered = message.lower()
    index = lowered.find("select")
    if index < 0:
        return ""
    sql = message[index:].strip().strip("`").strip()
    for marker in ["\n\n", "；", "。"]:
        if marker in sql:
            sql = sql.split(marker, 1)[0]
    return sql.rstrip(";").strip()


def _whatsapp_sql_reply(plan: dict[str, Any], result: dict[str, Any]) -> str:
    if not result.get("ok", True):
        return f"WhatsApp SQLite 查询失败：{result.get('error') or result.get('summary') or '未知错误'}。"
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    if plan.get("kind") == "tables":
        tables = data.get("tables") if isinstance(data.get("tables"), list) else []
        preview = "、".join(str(item) for item in tables[:12])
        suffix = "等" if len(tables) > 12 else ""
        return f"WhatsApp 本地库表名读取完成，共 {len(tables)} 个表：{preview}{suffix}。"
    rows = data.get("rows") if isinstance(data.get("rows"), list) else []
    columns = data.get("columns") if isinstance(data.get("columns"), list) else []
    preview_cols = "、".join(str(item) for item in columns[:6])
    return f"WhatsApp SQLite 只读查询完成，返回 {len(rows)} 行。字段：{preview_cols}。"


def _prepare_wacli_readonly_args(args_text: str) -> dict[str, Any]:
    try:
        args = shlex.split(args_text)
    except ValueError as exc:
        return {"ok": False, "summary": "模型返回的 wacli 命令参数无法解析。", "error": str(exc)}

    resolved_references: list[dict[str, str]] = []
    index = 0
    while index < len(args) - 1:
        option = args[index]
        if option not in {"--chat", "--jid", "--to"}:
            index += 1
            continue
        value = args[index + 1]
        if not _should_resolve_whatsapp_chat_value(value):
            index += 2
            continue
        chat = _resolve_whatsapp_send_chat(value)
        if not chat.get("ok"):
            return {
                "ok": False,
                "summary": str(chat.get("summary") or f"未能解析 WhatsApp 聊天对象「{value}」。"),
                "error": str(chat.get("error") or "whatsapp_chat_not_found"),
                "data": {"option": option, "input": value, "resolution": chat},
            }
        jid = str(chat.get("jid") or "")
        if not jid:
            return {
                "ok": False,
                "summary": f"未能为「{value}」找到可执行的 WhatsApp JID。",
                "error": "whatsapp_jid_not_found",
                "data": {"option": option, "input": value, "resolution": chat},
            }
        args[index + 1] = jid
        resolved_references.append(
            {
                "option": option,
                "input": value,
                "name": str(chat.get("name") or value),
                "jid": jid,
                "source": str(chat.get("source") or ""),
            }
        )
        index += 2
    return {
        "ok": True,
        "args": args,
        "args_text": shlex.join(args),
        "resolved_references": resolved_references,
    }


def _should_resolve_whatsapp_chat_value(value: str) -> bool:
    cleaned = value.strip()
    if not cleaned or "@" in cleaned:
        return False
    if re.fullmatch(r"\+?[\d\s().-]+", cleaned):
        return False
    return True


def _attach_wacli_arg_resolution(result: dict[str, Any], original_args_text: str, prepared: dict[str, Any]) -> dict[str, Any]:
    references = prepared.get("resolved_references")
    if not isinstance(references, list) or not references:
        return result
    data = dict(result.get("data") if isinstance(result.get("data"), dict) else {})
    data.update(
        {
            "original_args_text": original_args_text,
            "executed_args_text": prepared.get("args_text") or original_args_text,
            "resolved_references": references,
        }
    )
    return {**result, "data": data}


async def _create_whatsapp_send_confirmation(
    request: ChatMessageRequest,
    workflow_run_id: str,
    step: dict[str, Any],
    args_text: str,
    plan: dict[str, Any],
) -> dict[str, Any]:
    try:
        args = shlex.split(args_text)
    except ValueError as exc:
        return {
            "ok": False,
            "tool": "whatsapp_send_confirmation",
            "summary": "模型返回的 WhatsApp 发送命令参数无法解析。",
            "error": str(exc),
            "data": {"plan": plan, "args_text": args_text},
        }
    parsed = _parse_wacli_send_text(args)
    if not parsed:
        return {
            "ok": False,
            "tool": "whatsapp_send_confirmation",
            "summary": "当前仅支持将 WhatsApp 文本发送请求转入人工确认。",
            "error": "unsupported_confirmation_command",
            "data": {"plan": plan, "args": args},
        }
    chat = _resolve_whatsapp_send_chat(parsed["to"])
    if not chat.get("ok"):
        return {
            "ok": False,
            "tool": "whatsapp_send_confirmation",
            "summary": str(chat.get("summary") or "未能解析 WhatsApp 收件对象。"),
            "error": str(chat.get("error") or "whatsapp_recipient_not_found"),
            "data": {"plan": plan, "args": args, "recipient": parsed["to"], "resolution": chat},
        }

    payload = {
        "chat": str(chat["jid"]),
        "chat_name": str(chat.get("name") or parsed["to"]),
        "text": parsed["message"],
        "dry_run": bool(request.metadata.get("dry_run", False)),
        "args": args,
    }
    pending = await create_pending_confirmation(
        action_type="send_whatsapp_message",
        title=f"确认发送 WhatsApp 消息到 {payload['chat_name']}",
        summary=f"消息内容：{payload['text']}",
        payload=payload,
        risk_level="high",
        source_channel=request.channel,
        source_user_id=request.user_id,
        workflow_run_id=workflow_run_id,
        workflow_step_id=str(step.get("workflow_step_id") or "") or None,
        metadata={"plan": plan, "args_text": args_text},
    )
    confirmation = _nested(pending, "confirmation") or {}
    if not pending.get("ok") or not confirmation:
        return {
            "ok": False,
            "tool": "whatsapp_send_confirmation",
            "summary": "WhatsApp 发送确认项创建失败。",
            "error": str(pending.get("error") or pending.get("summary") or "confirmation_create_failed"),
            "data": {"plan": plan, "args": args, "pending": pending},
        }
    return {
        "ok": True,
        "tool": "whatsapp_send_confirmation",
        "summary": f"已创建 WhatsApp 消息待确认项：发送到 {payload['chat_name']}，内容为「{payload['text']}」。批准后才会发送。",
        "data": {"plan": plan, "args": args, "payload": payload, "confirmation": confirmation},
    }


def _parse_wacli_send_text(args: list[str]) -> dict[str, str] | None:
    if len(args) < 2 or args[0] != "send" or args[1] != "text":
        return None
    values: dict[str, str] = {}
    index = 2
    while index < len(args):
        arg = args[index]
        if arg in {"--to", "--message"} and index + 1 < len(args):
            values[arg[2:]] = args[index + 1]
            index += 2
            continue
        index += 1
    recipient = values.get("to", "").strip()
    message = values.get("message", "").strip()
    if not recipient or not message:
        return None
    return {"to": recipient, "message": message}


def _resolve_whatsapp_send_chat(recipient: str) -> dict[str, Any]:
    cleaned = recipient.strip()
    if not cleaned:
        return {"ok": False, "summary": "WhatsApp 收件对象为空。", "error": "empty_recipient"}
    if "@" in cleaned:
        return {"ok": True, "name": cleaned, "jid": cleaned, "source": "direct_jid"}

    exact = _find_whatsapp_chat_by_name(cleaned, exact=True)
    if exact:
        return {"ok": True, **exact}
    fuzzy_rows = _find_whatsapp_chats_by_name(cleaned, exact=False)
    if len(fuzzy_rows) == 1:
        return {"ok": True, **fuzzy_rows[0]}
    if len(fuzzy_rows) > 1:
        names = "、".join(str(row.get("name") or row.get("jid")) for row in fuzzy_rows[:5])
        return {
            "ok": False,
            "summary": f"找到多个 WhatsApp 收件对象：{names}。请补充更精确的群名。",
            "error": "ambiguous_recipient",
            "data": {"matches": fuzzy_rows},
        }
    return {
        "ok": False,
        "summary": f"未在本地 WhatsApp 群组/聊天列表中找到「{cleaned}」。请先同步群组或使用 JID。",
        "error": "recipient_not_found",
    }


def _find_whatsapp_chat_by_name(name: str, *, exact: bool) -> dict[str, Any] | None:
    if exact:
        group_rows = _query_whatsapp_chat_table("groups", name, exact=True)
        if group_rows:
            return group_rows[0]
        chat_rows = _query_whatsapp_chat_table("chats", name, exact=True)
        return chat_rows[0] if chat_rows else None
    rows = _find_whatsapp_chats_by_name(name, exact=exact)
    return rows[0] if rows else None


def _find_whatsapp_chats_by_name(name: str, *, exact: bool) -> list[dict[str, Any]]:
    return _dedupe_whatsapp_chat_rows([
        *_query_whatsapp_chat_table("groups", name, exact=exact),
        *_query_whatsapp_chat_table("chats", name, exact=exact),
    ])


def _dedupe_whatsapp_chat_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        jid = str(row.get("jid") or "")
        key = jid or str(row.get("name") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _query_whatsapp_chat_table(table: str, name: str, *, exact: bool) -> list[dict[str, Any]]:
    condition = f"name = {_sql_literal(name)}" if exact else f"name LIKE {_sql_literal('%' + name + '%')}"
    if table == "groups":
        sql = f"SELECT name, jid, 'groups' AS source FROM groups WHERE {condition} ORDER BY updated_at DESC"
    else:
        sql = f"SELECT name, jid, 'chats' AS source FROM chats WHERE {condition} ORDER BY last_message_ts DESC"
    rows: list[dict[str, Any]] = []
    result = run_whatsapp_sql_query(sql, 10)
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    for row in data.get("rows") if isinstance(data.get("rows"), list) else []:
        if isinstance(row, dict) and row.get("jid"):
            rows.append(row)
    return rows


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


WACLI_COMMAND_CATALOG = """
完整 wacli 命令目录

全局选项：
- --store DIR
- --account NAME
- --json
- --full
- --read-only / WACLI_READONLY=1
- --lock-wait DURATION
- --events

认证 auth：
- auth
- auth --qr-format text
- auth --phone PHONE
- auth --follow
- auth --download-media
- auth --webhook URL
- auth status
- auth logout

多账号 accounts：
- accounts list
- accounts add NAME
- accounts add NAME --no-auth
- accounts use NAME
- accounts show NAME
- accounts remove NAME

同步 sync：
- sync --once
- sync --follow
- sync --follow --idle-exit DURATION
- sync --follow --download-media
- sync --once --refresh-contacts --refresh-groups --refresh-channels
- sync --follow --max-messages N --max-db-size SIZE
- sync --follow --webhook URL
- sync --help

消息 messages：
- messages list --chat JID --limit N --after DATE --before DATE
- messages list --chat JID --from-me
- messages list --chat JID --from-them
- messages search QUERY --limit N
- messages search QUERY --chat JID --has-media --type TYPE
- messages starred --chat JID --limit N
- messages export --chat JID --output PATH --after DATE --before DATE
- messages show --chat JID --id MSG_ID
- messages context --chat JID --id MSG_ID --before N --after N
- messages edit --chat JID --id MSG_ID --message TEXT
- messages delete --chat JID --id MSG_ID --for-me --delete-media
- messages revoke --chat JID --id MSG_ID
- messages forward --chat JID --id MSG_ID --to RECIPIENT

发送 send / poll：
- send text --to RECIPIENT --message TEXT --mention USER --no-preview --ephemeral --reply-to MSG_ID
- send file --to RECIPIENT --file PATH --caption TEXT --filename NAME --mime TYPE --reply-to MSG_ID
- send sticker --to RECIPIENT --file PATH --reply-to MSG_ID
- send voice --to RECIPIENT --file PATH --mime TYPE --reply-to MSG_ID
- send poll --to RECIPIENT --question TEXT --option TEXT --multi N
- send status --message TEXT
- send status --file PATH --message TEXT --mime TYPE
- send react --to JID --id MSG_ID --reaction EMOJI
- poll vote --to RECIPIENT --id MSG_ID --option TEXT
- poll show --to RECIPIENT --id MSG_ID
- polls list --chat RECIPIENT --limit N
- send select --to RECIPIENT --id MSG_ID --label TEXT

媒体 media：
- media download --chat JID --id MSG_ID --output PATH

联系人 contacts：
- contacts search QUERY --limit N
- contacts show --jid JID
- contacts refresh
- contacts import-system --dry-run --clear
- contacts alias set --jid JID --alias NAME
- contacts alias rm --jid JID
- contacts tags add --jid JID --tag TAG
- contacts tags rm --jid JID --tag TAG

聊天 chats：
- chats list --query TEXT --limit N --archived --no-archived --pinned --no-pinned --muted --no-muted --unread --no-unread
- chats show --jid JID
- chats archive --chat CHAT
- chats unarchive --chat CHAT
- chats pin --chat CHAT
- chats unpin --chat CHAT
- chats mute --chat CHAT --duration DURATION
- chats unmute --chat CHAT
- chats mark-read --chat CHAT
- chats mark-unread --chat CHAT
- chats cleanup --days N --dry-run --confirm

群组 groups：
- groups list --query TEXT --limit N
- groups refresh
- groups info --jid GROUP_JID
- groups create --name NAME --user PHONE
- groups rename --jid GROUP_JID --name NAME
- groups topic --jid GROUP_JID --text TEXT
- groups description --jid GROUP_JID --text TEXT
- groups announce-only --jid GROUP_JID --on/--off
- groups locked --jid GROUP_JID --on/--off
- groups leave --jid GROUP_JID
- groups participants add --jid GROUP_JID --user PHONE
- groups participants remove --jid GROUP_JID --user PHONE
- groups participants promote --jid GROUP_JID --user PHONE
- groups participants demote --jid GROUP_JID --user PHONE
- groups requests list --jid GROUP_JID
- groups requests approve --jid GROUP_JID --user PHONE
- groups requests reject --jid GROUP_JID --user PHONE
- groups invite link get --jid GROUP_JID
- groups invite link revoke --jid GROUP_JID
- groups join --code INVITE_CODE
- groups prune --days N --dry-run --confirm

频道 channels：
- channels list
- channels info --jid CHANNEL_JID
- channels join --invite LINK_OR_CODE
- channels leave --jid CHANNEL_JID

历史 history：
- history coverage --query TEXT --kind KIND --include-blocked --only-actionable --limit N
- history fill --dry-run --kind KIND --limit N
- history backfill --chat JID --count N --requests N --wait DURATION

状态 presence：
- presence typing --to PHONE_OR_JID --media audio
- presence paused --to PHONE_OR_JID

个人资料 profile：
- profile set-picture IMAGE
- profile remove-picture
- profile set-about TEXT
- profile set-name NAME
- profile picture-info --jid JID_OR_PHONE --preview --existing-id ID
- profile get-about --jid JID_OR_PHONE
- profile business --jid JID_OR_PHONE

通话 calls：
- calls list --chat JID --asc --limit N --after DATE --before DATE

本地存储 store：
- store stats
- store cleanup --days N --dry-run --confirm

诊断和工具：
- doctor
- doctor --connect
- doctor --json
- docs
- version
- completion SHELL
- help COMMAND

只读 Skill 允许直接执行：doctor、version、docs、help、auth status、sync --help、messages list/search/starred/show/context/help、chats list/show、groups list/info、channels list、contacts search/show、history coverage、history fill --dry-run、store stats、store cleanup --dry-run、calls list、polls list、poll show、profile picture-info/get-about/business。
发送文本消息的特殊规则：如果用户明确要求发 WhatsApp 文本消息，输出 action=confirm_required 和 send text --to ... --message ...；系统只创建待确认项，批准前不发送。
只读 Skill 必须拒绝：auth logout、accounts add/use/remove、sync --follow/--once、messages edit/delete/revoke/forward/export、media download、contacts refresh/import/alias/tags 写操作、chats archive/pin/mute/mark-read/cleanup --confirm、groups create/rename/topic/description/participants/requests approve/reject/invite revoke/join/leave/prune --confirm、channels join/leave、presence、profile set/remove，以及非文本外发。
""".strip()


async def _whatsapp_wacli_plan(request: ChatMessageRequest) -> dict[str, Any]:
    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    params = metadata.get("assistant_entry_params") if isinstance(metadata.get("assistant_entry_params"), dict) else {}
    explicit_args = str(metadata.get("args") or params.get("args") or "").strip()
    if explicit_args:
        return {"action": "run", "args": explicit_args, "reason": "用户显式提供 wacli 参数。"}

    if not settings.llm_configured:
        return {
            "action": "refuse",
            "args": "",
            "reason": "WhatsApp wacli Skill 需要调用大模型理解用户意图，但当前 LLM 未配置。",
            "error": "llm_not_configured",
        }

    user_text = (
        f"用户原始输入：{request.message.strip()}\n"
        f"任务：{_assistant_task_text(request)}\n"
        f"上下文 metadata：{json.dumps(metadata, ensure_ascii=False, default=str)[:2000]}"
    )
    system_prompt = (
        "你是 WhatsApp wacli 命令规划器。你必须先理解用户自然语言意图，再从下面的完整命令目录里选择最合适的 wacli 命令。\n"
        "当前运行环境默认只读：允许直接执行的只能是只读命令。\n"
        "用户可以用中文群名、联系人名或聊天名提问；不要要求用户先查询 JID。需要 --chat/--jid/--to 时，可以直接填用户给出的名称，后端会解析为 JID。\n"
        "如果用户明确要求发送 WhatsApp 文本消息，请输出 confirm_required，并给出 send text 命令；系统会创建人工确认项，批准前不会发送。\n"
        "除发送文本消息外，如果用户要写入、编辑、删除、退出登录、修改群组或下载文件，请输出 refuse。\n"
        "不要因为模板里出现“诊断/只读/wacli”就选择 doctor；必须以“任务”字段里的真实用户需求为准。\n"
        '只返回 JSON object，格式：{"action":"run|confirm_required|refuse|needs_clarification","args":"不含 wacli 前缀的参数字符串","reason":"中文原因"}。\n'
        f"\n{WACLI_COMMAND_CATALOG}"
    )
    try:
        raw = await llm_gateway.complete_json(system_prompt, user_text)
        plan = _extract_wacli_llm_plan(raw)
    except Exception as exc:  # noqa: BLE001
        fallback = _fallback_whatsapp_wacli_plan(request, str(exc))
        if fallback:
            return fallback
        return {"action": "refuse", "args": "", "reason": f"模型规划 wacli 命令失败：{exc}", "error": "llm_plan_failed"}
    action = str(plan.get("action") or "").strip()
    args = str(plan.get("args") or "").strip()
    reason = str(plan.get("reason") or "模型完成 wacli 命令规划。").strip()
    if action not in {"run", "confirm_required", "refuse", "needs_clarification"}:
        return {"action": "refuse", "args": "", "reason": "模型返回了无法识别的 action。", "error": "invalid_llm_action", "raw": plan}
    return {"action": action, "args": args, "reason": reason, "raw": plan}


def _fallback_whatsapp_wacli_plan(request: ChatMessageRequest, error: str) -> dict[str, Any] | None:
    task = _assistant_task_text(request)
    normalized = task.lower()
    if any(token in task for token in ["发消息", "发送", "删除", "撤回", "编辑", "修改", "退出登录"]):
        return None
    if "send" in normalized or "delete" in normalized or "logout" in normalized:
        return None
    if any(token in task for token in ["登录状态", "认证状态"]) or "auth status" in normalized:
        return {
            "action": "run",
            "args": "auth status",
            "reason": f"LLM 规划失败后使用只读登录状态降级：{error}",
            "fallback": "readonly_rule_after_llm_failure",
        }
    if any(token in task for token in ["群组列表", "有哪些群", "有哪些群组"]):
        return {
            "action": "run",
            "args": "groups list",
            "reason": f"LLM 规划失败后使用只读群组列表降级：{error}",
            "fallback": "readonly_rule_after_llm_failure",
        }
    if any(token in task for token in ["最近消息", "最新消息", "聊天记录"]):
        chat_name = _extract_chat_name_for_recent_messages(task)
        if chat_name:
            return {
                "action": "run",
                "args": f"messages list --chat {_shell_quote(chat_name)} --limit 10",
                "reason": f"LLM 规划失败后使用只读最近消息降级：{error}",
                "fallback": "readonly_rule_after_llm_failure",
            }
    return None


def _extract_chat_name_for_recent_messages(message: str) -> str:
    quoted = _first_quoted(message)
    if quoted:
        return quoted
    patterns = [
        r"(?:帮我|请)?(?:看看|看下|查看|查询|查)?(?P<name>.+?)(?:的)?(?:最近|最新|近期)(?:的)?(?:消息|聊天记录)",
        r"(?:帮我|请)?(?:看看|看下|查看|查询|查)?(?P<name>.+?)(?:的)?(?:消息|聊天记录)",
    ]
    for pattern in patterns:
        match = re.search(pattern, message)
        if not match:
            continue
        name = match.group("name").strip(" ，,。:：")
        name = re.sub(r"^(一下|下|看一下|看看)", "", name).strip(" ，,。:：")
        if name:
            return name
    return _extract_query_term(message)


def _extract_wacli_llm_plan(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("model did not return a JSON object")
    if raw.get("available") is False:
        raise ValueError(str(raw.get("reason") or "LLM is not available"))
    if "action" in raw:
        return raw
    choices = raw.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else {}
        content = message.get("content") if isinstance(message, dict) else ""
        if isinstance(content, str) and content.strip():
            return json.loads(content)
    raise ValueError("model did not return a wacli command plan")


def _assistant_task_text(request: ChatMessageRequest) -> str:
    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    params = metadata.get("assistant_entry_params") if isinstance(metadata.get("assistant_entry_params"), dict) else {}
    for key in ("task", "question", "query", "message"):
        value = params.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return request.message.strip()


def _extract_query_term(message: str) -> str:
    stripped = message.strip()
    quoted = _first_quoted(stripped)
    if quoted:
        return quoted
    cleanup_tokens = [
        "帮我",
        "看看",
        "看下",
        "看一下",
        "有哪些",
        "哪些",
        "所有",
        "全部",
        "请",
        "用",
        "通过",
        "whatsapp",
        "WhatsApp",
        "wacli",
        "查询",
        "搜索",
        "搜",
        "查",
        "一下",
        "消息",
        "聊天",
        "群组",
        "联系人",
        "数据库",
        "本地库",
        "登录状态",
        "认证状态",
    ]
    value = stripped
    for token in cleanup_tokens:
        value = value.replace(token, " ")
    parts = [part.strip(" ，,。:：") for part in value.split() if part.strip(" ，,。:：")]
    return parts[-1] if parts else ""


def _first_quoted(message: str) -> str:
    for left, right in [("“", "”"), ("\"", "\""), ("'", "'"), ("「", "」")]:
        start = message.find(left)
        if start < 0:
            continue
        end = message.find(right, start + 1)
        if end > start:
            return message[start + 1 : end].strip()
    return ""


def _shell_quote(value: str) -> str:
    if not value:
        return ""
    if all(ch.isalnum() or ch in "@._-/" for ch in value):
        return value
    escaped = value.replace("'", "'\"'\"'")
    return f"'{escaped}'"


def _whatsapp_command_reply(args_text: str, result: dict[str, Any]) -> str:
    if not result.get("ok", True):
        return f"wacli {args_text} 执行失败：{result.get('error') or result.get('summary') or '未知错误'}。"
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    fallback_rows = data.get("fallback_rows") if isinstance(data.get("fallback_rows"), list) else []
    if fallback_rows:
        names = [
            str(row.get("name") or row.get("chat_name") or row.get("jid") or "").strip()
            for row in fallback_rows
            if isinstance(row, dict)
        ]
        preview = "、".join([name for name in names if name][:8])
        suffix = "等" if len(fallback_rows) > 8 else ""
        return (
            f"已执行 wacli {args_text}，但 wacli 未返回明细；"
            f"已从本地 wacli.db 读取 {len(fallback_rows)} 条记录：{preview}{suffix}。"
        )
    stdout = str(data.get("stdout") or "").strip()
    resolved_reply = _wacli_resolved_reference_reply(args_text, data, stdout)
    if resolved_reply:
        return resolved_reply
    table_reply = _wacli_table_reply(args_text, stdout)
    if table_reply:
        return table_reply
    first_line = stdout.splitlines()[0] if stdout else str(result.get("summary") or "命令执行完成")
    return f"已执行 wacli {args_text}。{first_line[:180]}"


def _wacli_resolved_reference_reply(args_text: str, data: dict[str, Any], stdout: str) -> str:
    references = data.get("resolved_references") if isinstance(data.get("resolved_references"), list) else []
    if not references:
        return ""
    labels = []
    for item in references:
        if not isinstance(item, dict):
            continue
        input_name = str(item.get("input") or "").strip()
        resolved_name = str(item.get("name") or "").strip()
        if input_name and resolved_name and input_name != resolved_name:
            labels.append(f"「{input_name}」→「{resolved_name}」")
        elif resolved_name:
            labels.append(f"「{resolved_name}」")
    if not labels:
        return ""
    first_line = _first_informative_wacli_line(stdout)
    suffix = f"。{first_line[:160]}" if first_line else "。"
    return f"已自动识别聊天对象{'、'.join(labels)}，并执行 wacli {args_text}{suffix}"


def _first_informative_wacli_line(stdout: str) -> str:
    for line in stdout.splitlines() if stdout else []:
        stripped = line.strip()
        if not stripped or _looks_like_wacli_table_header(stripped):
            continue
        return stripped
    return ""


def _looks_like_wacli_table_header(line: str) -> bool:
    normalized = " ".join(line.split()).upper()
    known_headers = [
        "TIME CHAT FROM ID TEXT",
        "DATE CHAT SENDER CONTENT",
        "NAME JID TYPE PARENT CREATED",
    ]
    return any(header in normalized for header in known_headers)


def _wacli_table_reply(args_text: str, stdout: str) -> str:
    if not stdout:
        return ""
    lines = [line.rstrip() for line in stdout.splitlines() if line.strip()]
    if len(lines) < 2:
        return ""
    header = lines[0]
    rows = lines[1:]
    if _is_wacli_groups_list(args_text) and "JID" in header:
        names: list[str] = []
        for row in rows:
            match = re.match(r"^(?P<name>.+?)\s+(?P<jid>\S+@\S+)\s+", row)
            if match:
                names.append(match.group("name").strip())
        names = [name for name in names if name]
        if names:
            preview = "、".join(names[:8])
            suffix = "等" if len(names) > 8 else ""
            return f"已执行 wacli {args_text}，获取到 {len(names)} 个群组：{preview}{suffix}。"
    if "  " not in header:
        return ""
    first_cells = []
    for row in rows:
        cells = re.split(r"\s{2,}", row.strip())
        if cells and cells[0]:
            first_cells.append(cells[0])
    if not first_cells:
        return ""
    preview = "、".join(first_cells[:8])
    suffix = "等" if len(first_cells) > 8 else ""
    return f"已执行 wacli {args_text}，返回 {len(first_cells)} 行：{preview}{suffix}。"


def _augment_wacli_result_with_local_fallback(args_text: str, result: dict[str, Any]) -> dict[str, Any]:
    if not result.get("ok", True):
        return result
    if not _is_wacli_groups_list(args_text) or not _wacli_result_is_empty(result):
        return result
    fallback = run_whatsapp_sql_query(
        "SELECT name, jid, owner_jid, updated_at FROM groups ORDER BY updated_at DESC",
        50,
    )
    data = fallback.get("data") if isinstance(fallback.get("data"), dict) else {}
    rows = data.get("rows") if isinstance(data.get("rows"), list) else []
    if not fallback.get("ok") or not rows:
        return result
    merged_data = dict(result.get("data") if isinstance(result.get("data"), dict) else {})
    merged_data.update(
        {
            "fallback_source": "wacli.db.groups",
            "fallback_reason": "wacli groups list returned no local group rows",
            "fallback_columns": data.get("columns") or [],
            "fallback_rows": rows,
        }
    )
    return {
        **result,
        "summary": f"wacli groups list 未返回群组，已回退本地 wacli.db，找到 {len(rows)} 个群组。",
        "data": merged_data,
    }


def _is_wacli_groups_list(args_text: str) -> bool:
    try:
        args = shlex.split(args_text)
    except ValueError:
        return False
    command_args: list[str] = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg in {"--read-only", "--json", "--full", "--events"}:
            index += 1
            continue
        if arg in {"--store", "--account", "--lock-wait"}:
            index += 2
            continue
        if any(arg.startswith(f"{option}=") for option in ["--store", "--account", "--lock-wait"]):
            index += 1
            continue
        command_args.append(arg)
        index += 1
    return len(command_args) >= 2 and command_args[0] == "groups" and command_args[1] == "list"


def _wacli_result_is_empty(result: dict[str, Any]) -> bool:
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    stdout = str(data.get("stdout") or "").strip()
    if not stdout:
        return True
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError:
        lines = [line.strip() for line in stdout.splitlines() if line.strip()]
        return len(lines) <= 1 and bool(lines and "JID" in lines[0])
    payload = parsed.get("data") if isinstance(parsed, dict) else None
    if payload is None:
        return True
    if isinstance(payload, list) and not payload:
        return True
    return False


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(number, maximum))


def _nested(result: dict[str, Any], *keys: str) -> Any:
    current: Any = result.get("data", result)
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _extract_briefing_text(briefing_result: dict[str, Any]) -> str:
    data = briefing_result.get("data")
    if isinstance(data, dict):
        for key in ("briefing_text", "text", "summary", "draft_text"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        draft = data.get("briefing") or data.get("draft")
        if isinstance(draft, dict):
            for key in ("text", "summary", "body"):
                value = draft.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    for item in briefing_result.get("items") or []:
        if not isinstance(item, dict):
            continue
        for key in ("briefing_text", "text", "summary", "draft_text"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    summary = briefing_result.get("summary")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    return "每日风险简报草稿（请在中台生成完整文本后发送）"


def _extract_report_images(*results: dict[str, Any]) -> list[dict[str, str]]:
    images: list[dict[str, str]] = []
    for result in results:
        for key in ("report_images", "images"):
            value = result.get(key)
            if isinstance(value, list):
                for item in value:
                    if not isinstance(item, dict):
                        continue
                    url = str(item.get("url") or item.get("image_url") or item.get("path") or "").strip()
                    if not url:
                        continue
                    images.append(
                        {
                            "title": str(item.get("title") or item.get("source") or "简报配图"),
                            "url": url,
                            "caption": str(item.get("caption") or item.get("title") or ""),
                        }
                    )
        for item in result.get("items") or []:
            if not isinstance(item, dict):
                continue
            url = str(item.get("image_url") or item.get("thumbnail_url") or item.get("chart_url") or "").strip()
            if url:
                images.append(
                    {
                        "title": str(item.get("title") or "简报配图"),
                        "url": url,
                        "caption": str(item.get("caption") or item.get("source_name") or ""),
                    }
                )
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for image in images:
        if image["url"] in seen:
            continue
        seen.add(image["url"])
        unique.append(image)
    return unique[:6]


def _extract_report_links(result: dict[str, Any]) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    for item in result.get("items") or []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        title = str(item.get("title") or "外部更新").strip()
        if not url and not title:
            continue
        links.append(
            {
                "title": title or "外部更新",
                "source": str(item.get("source_name") or item.get("source") or "外部来源"),
                "url": url,
            }
        )
    return links[:12]


def _is_plain_weather_question(message: str) -> bool:
    normalized = message.lower().replace(" ", "")
    if not any(token in normalized for token in ["天气", "天文台", "weather"]):
        return False
    return not any(token in normalized for token in ["简报", "舆情", "新闻", "风险", "监管", "工伤", "报告", "生成"])


def _weather_reply(weather: dict[str, Any]) -> str:
    if not weather.get("ok", True):
        error = weather.get("error") or "; ".join(str(item) for item in weather.get("errors", []) if item)
        return f"香港天气我查了一下，但天文台数据暂时拉取失败：{error or '未知错误'}。"

    summary = weather.get("summary") if isinstance(weather.get("summary"), dict) else {}
    highest = str(summary.get("highest_risk_level") or "low")
    risk_basis = summary.get("risk_basis") if isinstance(summary.get("risk_basis"), list) else []
    warning_codes = [
        str(item.get("warning_code"))
        for item in risk_basis
        if isinstance(item, dict) and item.get("warning_code")
    ]
    special_tips = _weather_special_tips(summary)

    parts = [f"香港天气已查询，当前外部风险等级是 {highest}。"]
    if warning_codes:
        parts.append(f"天文台警告/提示代码：{', '.join(warning_codes[:4])}。")
    if special_tips:
        parts.append(_weather_tips_sentence(special_tips[:3]))
    if highest in {"medium", "high", "critical"}:
        parts.append("现场建议同步检查室外高处作业、临时用电、排水和防暑防风安排。")
    return "".join(parts)


def _plain_weather_reply(weather: dict[str, Any]) -> str:
    if not weather.get("ok", True):
        error = weather.get("error") or "; ".join(str(item) for item in weather.get("errors", []) if item)
        return f"香港天气我查了一下，但天文台数据暂时拉取失败：{error or '未知错误'}。"

    summary = weather.get("summary") if isinstance(weather.get("summary"), dict) else {}
    warning_codes = _weather_warning_codes(summary)
    special_tips = _weather_special_tips(summary)

    parts = ["香港天气已查询。"]
    if warning_codes:
        parts.append(f"天文台警告/提示代码：{', '.join(warning_codes[:4])}。")
    if special_tips:
        parts.append(_weather_tips_sentence(special_tips[:3]))
    if not warning_codes and not special_tips:
        parts.append("当前未识别到特别天气提示。")
    return "".join(parts)


def _weather_warning_codes(summary: dict[str, Any]) -> list[str]:
    active_codes = summary.get("active_warning_codes")
    if isinstance(active_codes, list):
        codes = [str(code) for code in active_codes if str(code).strip()]
        if codes:
            return codes

    risk_basis = summary.get("risk_basis") if isinstance(summary.get("risk_basis"), list) else []
    return [
        str(item.get("warning_code"))
        for item in risk_basis
        if isinstance(item, dict) and item.get("warning_code")
    ]


def _weather_special_tips(summary: dict[str, Any]) -> list[str]:
    raw_tips = summary.get("special_tips") if isinstance(summary.get("special_tips"), list) else []
    tips: list[str] = []
    for item in raw_tips:
        text = _weather_tip_text(item)
        if text:
            tips.append(text)
    return tips


def _weather_tips_sentence(tips: list[str]) -> str:
    cleaned = [tip.strip().rstrip("。.!！?？；;") for tip in tips if tip.strip()]
    if not cleaned:
        return ""
    return f"特别天气提示：{'；'.join(cleaned)}。"


def _weather_tip_text(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("desc") or item.get("text") or item.get("message") or "").strip()

    text = str(item).strip()
    if text.startswith("{") and text.endswith("}"):
        try:
            parsed = ast.literal_eval(text)
        except (SyntaxError, ValueError):
            return text
        if isinstance(parsed, dict):
            return _weather_tip_text(parsed)
    return text
