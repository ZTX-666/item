from __future__ import annotations

from typing import Any

from chitung_center.audit import audit_logger
from chitung_center.external_briefing_store import persist_external_briefing_report
from chitung_center.models import ActionCard, ChatMessageRequest, VisualPatrolDraftRequest, WorkbenchVideoDetectionRequest
from chitung_center.rag_service import rag_service
from chitung_center.toolbox_client import toolbox_client
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
        elif workflow_name == "workflow_daily_risk_briefing":
            reply, tool_results, cards = await self._run_daily_risk_briefing(request, workflow_run_id)
        elif workflow_name == "workflow_form_filling":
            reply, tool_results, cards = await self._run_form_filling(request, workflow_run_id)
        elif workflow_name == "workflow_knowledge_query":
            reply, tool_results, cards = await self._run_knowledge_query(request, workflow_run_id)
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

    async def _run_daily_risk_briefing(
        self,
        request: ChatMessageRequest,
        workflow_run_id: str,
    ) -> tuple[str, list[dict[str, Any]], list[ActionCard]]:
        results: list[dict[str, Any]] = []
        weather_step = await _start_step(workflow_run_id, "fetch_weather", "赤瞳守护者", "fetch_hko_weather")
        weather = await _safe_tool("fetch_hko_weather", {"lang": "tc"})
        await _finish_step(weather_step, weather)
        results.append(weather)

        updates_step = await _start_step(workflow_run_id, "fetch_updates", "赤瞳守护者", "fetch_hk_safety_updates")
        updates = await _safe_tool("fetch_hk_safety_updates", {"limit_per_source": 5})
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
            {"weather_result": weather, "safety_updates_result": updates},
        )
        await _finish_step(briefing_step, briefing)
        results.append(briefing)

        briefing_text = _extract_briefing_text(briefing)
        report_images = _extract_report_images(weather, updates, briefing)
        report_links = _extract_report_links(updates)
        briefing_report = persist_external_briefing_report(
            {
                "title": "今日外部风险简报",
                "summary": "已生成今日外部风险图文简报草稿。",
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
                title="晴晴外部风险监测",
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
        return "已生成今日外部风险图文简报草稿，包含香港天气、官方安全更新和建议动作。", results, cards

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
    special_tips = [
        str(item)
        for item in (summary.get("special_tips") if isinstance(summary.get("special_tips"), list) else [])
        if str(item).strip()
    ]

    parts = [f"香港天气已查询，当前外部风险等级是 {highest}。"]
    if warning_codes:
        parts.append(f"天文台警告/提示代码：{', '.join(warning_codes[:4])}。")
    if special_tips:
        parts.append(f"特别天气提示：{'；'.join(special_tips[:3])}。")
    if highest in {"medium", "high", "critical"}:
        parts.append("现场建议同步检查室外高处作业、临时用电、排水和防暑防风安排。")
    return "".join(parts)
