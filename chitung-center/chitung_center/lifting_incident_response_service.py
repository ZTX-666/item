from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from chitung_center.app_config_service import get_app_config
from chitung_center.config import settings
from chitung_center.confirmation_service import create_pending_confirmation
from chitung_center.llm_gateway import llm_gateway
from chitung_center.models import ActionCard, ChatMessageRequest, WorkbenchVideoDetectionRequest
from chitung_center.rag_service import rag_service
from chitung_center.toolbox_client import toolbox_client
from chitung_center.whatsapp_report_delivery import collect_patrol_evidence_images, persist_evidence_images
from chitung_center.workbench_video_detection_service import run_workbench_video_detection
from chitung_center import workflow_store


LIFTING_KEYWORDS = (
    "吊运",
    "起吊",
    "吊车",
    "吊机",
    "crane",
    "lifting",
    "load",
    "吊索",
    "吊具",
    "塔吊",
)

POSTER_ASSET = Path(__file__).resolve().parent / "assets" / "lifting_safety_alert_poster.svg"
DEFAULT_DETECTION_DIRECTION = (
    "吊运专项安全：检查吊机作业区、警戒区设置、人员与吊运半径距离、司索指挥、绑扎点与吊具状态"
)


def is_lifting_related_text(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in text or keyword in lowered for keyword in LIFTING_KEYWORDS)


def is_lifting_related_card(card: dict[str, Any] | None) -> bool:
    if not isinstance(card, dict):
        return False
    parts = [
        str(card.get("title") or ""),
        str(card.get("summary") or ""),
        str(card.get("recommended_action") or ""),
        str(card.get("category") or ""),
        " ".join(str(item) for item in (card.get("keywords") or [])),
        " ".join(str(item) for item in (card.get("reason_codes") or [])),
    ]
    return is_lifting_related_text(" ".join(parts))


def bundled_poster_path() -> Path:
    return POSTER_ASSET


def bundled_poster_api_url() -> str:
    return "/api/assets/lifting-safety-alert-poster"


async def handle_external_info_alert_approval(confirmation: dict[str, Any], *, decided_by: str) -> dict[str, Any]:
    payload = confirmation.get("payload") if isinstance(confirmation.get("payload"), dict) else {}
    card = payload.get("card") if isinstance(payload.get("card"), dict) else {}
    if is_lifting_related_card(card):
        from chitung_center.workflow_engine import workflow_engine

        result = await workflow_engine.run_template(
            "workflow_industry_lifting_incident_response",
            ChatMessageRequest(
                message=f"业界吊运风险主动响应：{card.get('title') or '外部讯息'}",
                channel=str(confirmation.get("source_channel") or "external_monitor"),
                user_id=decided_by,
                metadata={
                    "external_card": card,
                    "trigger": "external_info_alert_approved",
                    "parent_workflow_run_id": payload.get("workflow_run_id"),
                    "priority": card.get("priority"),
                },
            ),
        )
        return {
            "ok": bool(result.get("ok")),
            "message": str(result.get("reply") or "吊运专项响应工作流已执行。"),
            "action_type": "external_info_alert",
            "workflow_result": result,
        }

    text = _format_generic_external_alert(card, payload)
    from chitung_center.confirmation_service import _execute_feishu_send

    send_result = await _execute_feishu_send(
        "send_feishu_message",
        {
            "title": str(card.get("title") or "外部安全讯息提醒"),
            "text": text,
            "receive_id": payload.get("receive_id"),
            "receive_id_type": payload.get("receive_id_type", "chat_id"),
        },
    )
    return {
        "ok": bool(send_result.get("ok")),
        "message": str(send_result.get("message") or send_result.get("summary") or "外部讯息提醒已处理。"),
        "action_type": "external_info_alert",
        "tool_result": send_result,
    }


async def run_lifting_incident_response(
    request: ChatMessageRequest,
    workflow_run_id: str,
) -> tuple[str, list[dict[str, Any]], list[ActionCard]]:
    tool_results: list[dict[str, Any]] = []
    external_card = request.metadata.get("external_card") if isinstance(request.metadata.get("external_card"), dict) else {}
    card_title = str(external_card.get("title") or request.message or "业界吊运事故警示")
    card_summary = str(external_card.get("summary") or external_card.get("recommended_action") or "")

    policy_step = await _start_step(workflow_run_id, "search_policy", "耀耀慧读", "search_policy_clauses")
    policy_context = await _fetch_policy_context(card_title, card_summary)
    await _finish_step(policy_step, {"ok": True, "policy_context": policy_context})
    tool_results.append({"tool": "search_policy_clauses", "ok": True, "data": {"snippets": policy_context}})

    detection_direction = _build_detection_direction(external_card, request.message)
    prompt_step = await _start_step(workflow_run_id, "refine_prompt", "赤瞳守护者", "refine_detection_prompt")
    camera_ids = _resolve_camera_ids(request.metadata)
    patrol = await run_workbench_video_detection(
        WorkbenchVideoDetectionRequest(
            detection_direction=detection_direction,
            camera_ids=camera_ids,
            vlm_enabled=bool(request.metadata.get("vlm_enabled", True)),
        )
    )
    await _finish_step(prompt_step, patrol)
    tool_results.append({"tool": "workbench_video_detection", **patrol})

    case_result: dict[str, Any] | None = None
    case_id: int | None = None
    if patrol.get("ok"):
        case_result = await _maybe_create_case_from_patrol(patrol, external_card, detection_direction)
    if not case_result and external_card:
        case_result = await _create_case_from_external_card(external_card, detection_direction, patrol)
    if case_result:
        tool_results.append(case_result)
        case_id = _extract_case_id(case_result)

    notice_result: dict[str, Any] | None = None
    if case_id:
        notice_step = await _start_step(workflow_run_id, "rectification_notice", "赤瞳中台", "generate_rectification_notice")
        notice_result = await toolbox_client.call_tool(
            "generate_rectification_notice",
            {"case_id": case_id, "language": "zh-HK", "tone": "formal"},
        )
        await _finish_step(notice_step, notice_result)
        tool_results.append(notice_result)

    alert_bundle = await generate_safety_alert_bundle(
        external_card=external_card,
        patrol_result=patrol if patrol.get("ok") else {},
        policy_context=policy_context,
        case_id=case_id,
        workflow_run_id=workflow_run_id,
    )
    tool_results.append({"tool": "generate_safety_alert_bundle", "ok": True, "data": alert_bundle})

    notification_text = _compose_notification_text(alert_bundle, patrol, case_id)
    detection_report = compose_patrol_detection_report(
        external_card=external_card,
        patrol=patrol,
        alert_bundle=alert_bundle,
        case_id=case_id,
        workflow_run_id=workflow_run_id,
    )
    tool_results.append({"tool": "compose_patrol_detection_report", "ok": True, "data": detection_report})

    whatsapp_to = normalize_whatsapp_phone(
        str(request.metadata.get("whatsapp_to") or settings.lifting_alert_whatsapp_to)
    )
    attachment_paths = detection_report.get("attachment_paths") if isinstance(detection_report.get("attachment_paths"), list) else []
    image_count = len(attachment_paths)
    auto_send_whatsapp = bool(request.metadata.get("auto_send_whatsapp"))
    if auto_send_whatsapp:
        from chitung_center.whatsapp_report_delivery import deliver_whatsapp_detection_report

        delivery = await deliver_whatsapp_detection_report(
            chat=whatsapp_to,
            text=str(detection_report.get("whatsapp_text") or notification_text),
            attachments=attachment_paths,
            confirmed_by=f"automation:{request.metadata.get('automation_task_id') or request.user_id}",
        )
        tool_results.append({"tool": "deliver_whatsapp_detection_report", **delivery})
        whatsapp_note = (
            f"检测报告与 {sum(1 for item in (delivery.get('file_results') or []) if item.get('ok'))}/{image_count} 张标注图已通过 WhatsApp 自动发送至 {whatsapp_to}。"
            if delivery.get("ok")
            else f"WhatsApp 自动发送部分失败：{delivery.get('summary') or '请人工补发'}"
        )
    else:
        pending = await create_pending_confirmation(
            action_type="send_whatsapp_message",
            title=f"确认发送吊运检测报告至 WhatsApp：{whatsapp_to}",
            summary=(
                f"确认后通过 wacli 发送检测报告至 {whatsapp_to}。"
                + (f" 含 {image_count} 张检测标注图。" if image_count else " 仅文本报告（无可用标注图）。")
            ),
            payload={
                "chat": whatsapp_to,
                "text": detection_report.get("whatsapp_text") or notification_text,
                "file_path": attachment_paths[0]["path"] if attachment_paths else None,
                "file_paths": attachment_paths,
                "file_caption": str(detection_report.get("attachment_caption") or alert_bundle.get("alert_title") or "吊运专项巡检标注图"),
                "report_id": detection_report.get("report_id"),
                "report_markdown_path": detection_report.get("markdown_path"),
                "images_dir": detection_report.get("images_dir"),
                "poster_path": alert_bundle.get("poster_path"),
                "case_id": case_id,
                "workflow_run_id": workflow_run_id,
                "channel": "whatsapp",
            },
            risk_level="high",
            source_channel=request.channel,
            source_user_id=request.user_id,
            workflow_run_id=workflow_run_id,
            idempotency_key=f"lifting-alert-whatsapp:{workflow_run_id}",
            metadata={"scenario": "industry_lifting_incident_response", "priority": external_card.get("priority")},
        )
        tool_results.append(pending)
        whatsapp_note = f"检测报告已生成，WhatsApp 发送至 {whatsapp_to} 已进入待确认。"

    patrol_summary = ""
    summary = patrol.get("summary") if isinstance(patrol.get("summary"), dict) else {}
    if summary.get("text"):
        patrol_summary = str(summary.get("text"))

    reply_parts = [
        f"已完成业界吊运风险主动响应（工作流 {workflow_run_id}）。",
        f"外部讯息：{card_title}",
    ]
    if patrol.get("ok"):
        reply_parts.append(patrol_summary or "摄像头吊运专项巡检已完成。")
    else:
        reply_parts.append(str(patrol.get("message") or patrol.get("error") or "摄像头巡检未完全成功，请人工补检。"))
    if case_id:
        reply_parts.append(f"已创建/关联隐患案例 #{case_id}，整改通知草稿已生成。")
    reply_parts.append(whatsapp_note)
    reply = " ".join(part for part in reply_parts if part)

    cards = [
        ActionCard(
            card_type="lifting_incident_response",
            title=alert_bundle.get("alert_title") or "吊运专项主动响应",
            summary=alert_bundle.get("alert_body") or reply,
            actions=[
                {"id": "approve_confirmation", "label": "前往待确认发送 WhatsApp"},
                {"id": "open_hazard_ledger", "label": "查看隐患台账"},
            ],
            data={
                "workflow_run_id": workflow_run_id,
                "external_card": external_card,
                "patrol": patrol,
                "alert_bundle": alert_bundle,
                "detection_report": detection_report,
                "whatsapp_to": whatsapp_to,
                "case_id": case_id,
                "rectification_notice": notice_result,
                "pending_confirmation": _confirmation_from_tool(pending),
                "rich_blocks": _build_alert_rich_blocks(alert_bundle, patrol, detection_report.get("markdown_text") or notification_text),
            },
        )
    ]
    await workflow_store.link_event(
        workflow_run_id=workflow_run_id,
        event_type="lifting_incident_response_completed",
        source_type="external_card",
        source_id=str(external_card.get("card_id") or card_title),
        payload={"case_id": case_id, "patrol_ok": patrol.get("ok"), "alert_bundle_path": alert_bundle.get("bundle_path")},
    )
    return reply, tool_results, cards


async def generate_safety_alert_bundle(
    *,
    external_card: dict[str, Any],
    patrol_result: dict[str, Any],
    policy_context: list[str],
    case_id: int | None,
    workflow_run_id: str,
) -> dict[str, Any]:
    generated = await _generate_alert_text_llm(external_card, patrol_result, policy_context, case_id)
    bundle_dir = settings.chitung_data_dir / "lifting_alerts"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    bundle_path = bundle_dir / f"lifting_alert_{workflow_run_id}_{stamp}.json"
    poster_path = str(bundled_poster_path())
    bundle = {
        "alert_title": generated.get("alert_title"),
        "alert_body": generated.get("alert_body"),
        "operator_reminders": generated.get("operator_reminders") or [],
        "immediate_actions": generated.get("immediate_actions") or [],
        "source": generated.get("source", "fallback"),
        "external_card": external_card,
        "case_id": case_id,
        "patrol_report_id": patrol_result.get("report_id"),
        "poster_path": poster_path,
        "poster_api_url": bundled_poster_api_url(),
        "workflow_run_id": workflow_run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    bundle_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    bundle["bundle_path"] = str(bundle_path)
    return bundle


async def _generate_alert_text_llm(
    external_card: dict[str, Any],
    patrol_result: dict[str, Any],
    policy_context: list[str],
    case_id: int | None,
) -> dict[str, Any]:
    fallback = _fallback_alert_text(external_card, patrol_result, case_id)
    if not settings.llm_configured:
        return {**fallback, "source": "fallback"}

    patrol_summary = patrol_result.get("summary") if isinstance(patrol_result.get("summary"), dict) else {}
    payload = {
        "external_title": external_card.get("title"),
        "external_summary": external_card.get("summary") or external_card.get("recommended_action"),
        "priority": external_card.get("priority"),
        "patrol_summary": patrol_summary.get("text"),
        "patrol_severity": patrol_summary.get("severity"),
        "policy_context": policy_context[:3],
        "case_id": case_id,
    }
    try:
        result = await llm_gateway.complete_json(
            system_prompt=(
                "你是香港工地安全主任。根据业界吊运事故外部讯息和现场摄像头巡检结果，"
                "生成面向机手、司索和前线管理人员的警示文案。"
                "只返回 JSON，字段：alert_title（≤30字）、alert_body（150-280字，含事故教训与现场要求）、"
                "operator_reminders（3-5条短句）、immediate_actions（2-4条可执行动作）。"
                "语气正式、紧迫，避免空话。"
            ),
            user_text=json.dumps(payload, ensure_ascii=False),
        )
        parsed = _extract_llm_json(result)
        alert_title = str(parsed.get("alert_title") or "").strip()
        alert_body = str(parsed.get("alert_body") or "").strip()
        if alert_title and alert_body:
            return {
                "alert_title": alert_title,
                "alert_body": alert_body,
                "operator_reminders": _string_list(parsed.get("operator_reminders")),
                "immediate_actions": _string_list(parsed.get("immediate_actions")),
                "source": "llm",
            }
    except Exception:
        pass
    return {**fallback, "source": "fallback"}


def _fallback_alert_text(
    external_card: dict[str, Any],
    patrol_result: dict[str, Any],
    case_id: int | None,
) -> dict[str, Any]:
    title = str(external_card.get("title") or "业界吊运事故警示")
    patrol_summary = patrol_result.get("summary") if isinstance(patrol_result.get("summary"), dict) else {}
    patrol_text = str(patrol_summary.get("text") or "请立即对吊运区域开展专项自查。")
    body = (
        f"【外部讯息】{title}。"
        f"请各分判商及前线管理人员立即组织吊运专项自查：确认吊具绑扎、警戒区隔离、"
        f"人员与吊运半径距离、司索指挥及恶劣天气停工条件。"
        f"【现场巡检】{patrol_text}"
    )
    if case_id:
        body += f" 系统已登记隐患案例 #{case_id}，请按整改通知要求反馈。"
    return {
        "alert_title": "吊运安全专项警示",
        "alert_body": body,
        "operator_reminders": [
            "吊运前必须确认吊具、绑扎点及荷载",
            "警戒区内禁止无关人员停留",
            "发现异常立即停工并上报",
        ],
        "immediate_actions": [
            "30 分钟内完成吊运区域自查并拍照留档",
            "24 小时内提交整改说明",
        ],
    }


def normalize_whatsapp_phone(phone: str) -> str:
    cleaned = phone.strip()
    if not cleaned:
        return settings.lifting_alert_whatsapp_to
    digits = re.sub(r"\D+", "", cleaned)
    if digits.startswith("852") and len(digits) >= 11:
        return f"+{digits}"
    if len(digits) == 8:
        return f"+852{digits}"
    return cleaned if cleaned.startswith("+") else f"+{digits}"


def compose_patrol_detection_report(
    *,
    external_card: dict[str, Any],
    patrol: dict[str, Any],
    alert_bundle: dict[str, Any],
    case_id: int | None,
    workflow_run_id: str,
) -> dict[str, Any]:
    report_id = str(patrol.get("report_id") or f"lift-{workflow_run_id}")
    summary = patrol.get("summary") if isinstance(patrol.get("summary"), dict) else {}
    markdown_lines = [
        f"# 吊运专项视觉检测报告",
        "",
        f"- 报告编号：`{report_id}`",
        f"- 工作流：`{workflow_run_id}`",
        f"- 生成时间：{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "## 外部讯息触发",
        f"- 标题：{external_card.get('title') or '（无）'}",
        f"- 优先级：{external_card.get('priority') or 'P1'}",
        f"- 摘要：{external_card.get('summary') or external_card.get('recommended_action') or '（无）'}",
        "",
        "## 检测提示词",
        f"- 原始方向：{patrol.get('direction') or patrol.get('user_question') or DEFAULT_DETECTION_DIRECTION}",
        f"- 润色提示词：{patrol.get('refined_prompt') or '（未生成）'}",
        "",
        "## 巡检摘要",
        str(summary.get("text") or patrol.get("message") or "（无摘要）"),
        "",
        "## 摄像头结果",
    ]
    cameras = patrol.get("cameras") if isinstance(patrol.get("cameras"), list) else []
    if cameras:
        for camera in cameras:
            if not isinstance(camera, dict):
                continue
            camera_summary = camera.get("summary")
            camera_text = camera_summary.get("text") if isinstance(camera_summary, dict) else str(camera_summary or "")
            markdown_lines.append(
                f"- {camera.get('camera_name') or camera.get('camera_id')}: {camera_text or '已完成检测'}"
            )
    else:
        markdown_lines.append("- （无摄像头结果）")

    markdown_lines.extend(
        [
            "",
            "## 安全警示",
            str(alert_bundle.get("alert_title") or "吊运安全专项警示"),
            "",
            str(alert_bundle.get("alert_body") or ""),
            "",
        ]
    )
    if case_id:
        markdown_lines.extend([f"## 隐患案例", f"- 案例编号：#{case_id}", ""])

    raw_images = collect_patrol_evidence_images(patrol)
    attachment_paths = persist_evidence_images(report_id, raw_images)
    if attachment_paths:
        markdown_lines.extend(["", "## 附件", f"- 共 {len(attachment_paths)} 张检测标注图（已持久化至 `{report_id}/images/`）"])

    markdown_text = "\n".join(markdown_lines).strip()
    patrol_with_meta = {**patrol, "attachment_count": len(attachment_paths)}
    whatsapp_text = _compose_whatsapp_report_text(
        report_id=report_id,
        external_card=external_card,
        patrol=patrol_with_meta,
        alert_bundle=alert_bundle,
        case_id=case_id,
        summary=summary,
    )

    report_dir = settings.chitung_data_dir / "detection_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = report_dir / f"{report_id}.md"
    markdown_path.write_text(markdown_text, encoding="utf-8")

    attachment_path = attachment_paths[0]["path"] if attachment_paths else ""
    return {
        "report_id": report_id,
        "markdown_path": str(markdown_path),
        "markdown_text": markdown_text,
        "whatsapp_text": whatsapp_text,
        "attachment_path": attachment_path,
        "attachment_paths": attachment_paths,
        "attachment_count": len(attachment_paths),
        "attachment_caption": f"吊运专项巡检标注图 · {report_id}",
        "images_dir": str((settings.chitung_data_dir / "detection_reports" / report_id / "images")),
        "json_store": str(settings.chitung_data_dir / "video_detection_reports.json"),
        "sqlite_store": str(settings.chitung_data_dir / "video_detection_results.db"),
    }


def _compose_whatsapp_report_text(
    *,
    report_id: str,
    external_card: dict[str, Any],
    patrol: dict[str, Any],
    alert_bundle: dict[str, Any],
    case_id: int | None,
    summary: dict[str, Any],
) -> str:
    lines = [
        "【赤瞳 · 吊运专项检测报告】",
        f"报告编号：{report_id}",
        "",
        f"外部讯息：{external_card.get('title') or '业界吊运风险'}",
        f"优先级：{external_card.get('priority') or 'P1'}",
        "",
        "—— 巡检摘要 ——",
        str(summary.get("text") or patrol.get("message") or "已完成专项巡检。"),
        "",
        "—— 安全警示 ——",
        str(alert_bundle.get("alert_title") or "吊运安全专项警示"),
        str(alert_bundle.get("alert_body") or ""),
    ]
    reminders = alert_bundle.get("operator_reminders") or []
    if reminders:
        lines.extend(["", "机手/司索提醒："])
        lines.extend(f"• {item}" for item in reminders[:5])
    if case_id:
        lines.extend(["", f"隐患案例：#{case_id}"])
    image_count = int(patrol.get("attachment_count") or 0)
    if image_count:
        lines.extend(["", f"（随文附 {image_count} 张摄像头检测标注图）"])
    else:
        lines.extend(["", "（本次未采集到可发送的标注图，仅文字报告）"])
    text = "\n".join(lines).strip()
    return text[:3900] + ("…" if len(text) > 3900 else "")


def _pick_patrol_attachment(patrol: dict[str, Any]) -> str:
    for key in ("annotated_path", "snapshot_path"):
        path = patrol.get(key)
        if path and Path(str(path)).exists():
            return str(path)
    cameras = patrol.get("cameras") if isinstance(patrol.get("cameras"), list) else []
    for camera in cameras:
        if not isinstance(camera, dict):
            continue
        for key in ("annotated_path", "snapshot_path"):
            path = camera.get(key)
            if path and Path(str(path)).exists():
                return str(path)
    poster = bundled_poster_path()
    return str(poster) if poster.exists() else ""


def _compose_notification_text(alert_bundle: dict[str, Any], patrol: dict[str, Any], case_id: int | None) -> str:
    lines = [
        str(alert_bundle.get("alert_title") or "吊运安全专项警示"),
        "",
        str(alert_bundle.get("alert_body") or ""),
        "",
        "【机手/司索提醒】",
    ]
    for item in alert_bundle.get("operator_reminders") or []:
        lines.append(f"• {item}")
    lines.append("")
    lines.append("【立即行动】")
    for item in alert_bundle.get("immediate_actions") or []:
        lines.append(f"• {item}")
    summary = patrol.get("summary") if isinstance(patrol.get("summary"), dict) else {}
    if summary.get("text"):
        lines.extend(["", "【摄像头巡检摘要】", str(summary.get("text"))])
    if case_id:
        lines.extend(["", f"【隐患案例】#{case_id} 已登记，请按整改通知执行。"])
    lines.extend(["", "（随文附内置吊运安全警示图，确认后通过飞书发送；WhatsApp 外发需另行操作。）"])
    return "\n".join(lines)


def _build_alert_rich_blocks(alert_bundle: dict[str, Any], patrol: dict[str, Any], notification_text: str) -> list[dict[str, Any]]:
    from chitung_center.rich_content import build_video_detection_rich_blocks

    blocks: list[dict[str, Any]] = [
        {"kind": "markdown", "title": "警示正文", "text": notification_text},
        {
            "kind": "image",
            "title": "吊运安全警示图",
            "url": str(alert_bundle.get("poster_api_url") or bundled_poster_api_url()),
            "caption": "内置警示海报（随通知一并发送）",
        },
    ]
    blocks.extend(build_video_detection_rich_blocks(patrol))
    return blocks


async def _fetch_policy_context(title: str, summary: str) -> list[str]:
    query = f"吊运 安全 警戒区 绑扎 {title} {summary}".strip()
    try:
        result = await rag_service.query(query, top_k=3, collection="safety")
    except Exception:
        try:
            result = await rag_service.query(query, top_k=3)
        except Exception:
            return []
    items = result.get("items") if isinstance(result, dict) else []
    snippets: list[str] = []
    for item in items[:3]:
        if isinstance(item, dict):
            text = str(item.get("text") or "").strip()
            if text:
                snippets.append(text[:320])
    return snippets


def _build_detection_direction(external_card: dict[str, Any], message: str) -> str:
    title = str(external_card.get("title") or "")
    summary = str(external_card.get("summary") or external_card.get("recommended_action") or "")
    if title or summary:
        return f"{DEFAULT_DETECTION_DIRECTION}。关联外部讯息：{title}。{summary}".strip()
    if message.strip():
        return f"{DEFAULT_DETECTION_DIRECTION}。{message.strip()}"
    return DEFAULT_DETECTION_DIRECTION


def _resolve_camera_ids(metadata: dict[str, Any]) -> list[str]:
    raw = metadata.get("camera_ids")
    if isinstance(raw, list) and raw:
        return [str(item) for item in raw if str(item).strip()]
    config = get_app_config()
    cameras = config.get("cameras") if isinstance(config.get("cameras"), list) else []
    selected: list[str] = []
    for camera in cameras:
        if not isinstance(camera, dict) or not camera.get("enabled", True):
            continue
        area = str(camera.get("area") or "")
        name = str(camera.get("name") or "")
        if any(token in area + name for token in ("施工", "吊", "crane", "lifting")):
            selected.append(str(camera.get("id")))
    if selected:
        return selected
    return [str(camera.get("id")) for camera in cameras if isinstance(camera, dict) and camera.get("enabled", True)]


async def _create_case_from_external_card(
    external_card: dict[str, Any],
    detection_direction: str,
    patrol: dict[str, Any],
) -> dict[str, Any] | None:
    if not is_lifting_related_card(external_card):
        return None
    priority = str(external_card.get("priority") or "P1")
    if priority not in {"P0", "P1"}:
        return None
    patrol_summary = patrol.get("summary") if isinstance(patrol.get("summary"), dict) else {}
    description = (
        f"业界吊运风险主动响应：{external_card.get('title') or detection_direction}。"
        f" {external_card.get('summary') or external_card.get('recommended_action') or ''}"
        f" 现场巡检：{patrol_summary.get('text') or '已完成专项巡检。'}"
    ).strip()
    return await toolbox_client.call_tool(
        "create_safety_case",
        {
            "description": description[:500],
            "scene": "业界吊运风险预警",
            "risk_level": "high" if priority == "P0" else "medium",
            "area": "施工区域",
            "source_type": "external_lifting_alert",
            "source_id": str(external_card.get("card_id") or external_card.get("title") or ""),
            "recommended_action": "请组织吊运专项自查并在24小时内反馈整改说明。",
        },
    )


async def _maybe_create_case_from_patrol(
    patrol: dict[str, Any],
    external_card: dict[str, Any],
    detection_direction: str,
) -> dict[str, Any] | None:
    summary = patrol.get("summary") if isinstance(patrol.get("summary"), dict) else {}
    severity = str(summary.get("severity") or "low").lower()
    detection_count = int(summary.get("detection_count") or 0)
    if detection_count <= 0 and severity in {"low", "info", "none", ""}:
        return None
    if severity not in {"medium", "high", "critical"} and detection_count <= 0:
        return None

    description = (
        f"吊运专项巡检：{external_card.get('title') or detection_direction}。"
        f" {summary.get('text') or ''}"
    ).strip()
    area = str(patrol.get("area") or "")
    evidence_paths = []
    for key in ("annotated_path", "snapshot_path"):
        path = patrol.get(key)
        if path:
            evidence_paths.append(str(path))
    for camera in patrol.get("cameras") if isinstance(patrol.get("cameras"), list) else []:
        if not isinstance(camera, dict):
            continue
        for key in ("annotated_path", "snapshot_path"):
            path = camera.get(key)
            if path:
                evidence_paths.append(str(path))

    case = await toolbox_client.call_tool(
        "create_safety_case",
        {
            "description": description[:500],
            "scene": "吊运专项巡检",
            "risk_level": "high" if severity in {"high", "critical"} else "medium",
            "area": area or "施工区域",
            "source_type": "lifting_incident_response",
            "source_id": str(patrol.get("report_id") or patrol.get("patrol_id") or ""),
            "recommended_action": str(summary.get("suggested_action") or "请安全主任复核吊运区域并发出整改要求。"),
        },
    )
    case_id = _extract_case_id(case)
    if case_id and evidence_paths:
        for path in list(dict.fromkeys(evidence_paths))[:3]:
            await toolbox_client.call_tool(
                "add_case_evidence",
                {"case_id": case_id, "evidence_type": "image", "path": path, "notes": "吊运专项巡检证据"},
            )
    return case


def _extract_case_id(tool_result: dict[str, Any] | None) -> int | None:
    if not isinstance(tool_result, dict):
        return None
    data = tool_result.get("data")
    if isinstance(data, dict):
        case_id = data.get("case_id")
        if case_id is not None:
            return int(case_id)
        nested = data.get("case")
        if isinstance(nested, dict) and nested.get("case_id") is not None:
            return int(nested["case_id"])
    return None


def _format_generic_external_alert(card: dict[str, Any], payload: dict[str, Any]) -> str:
    lines = [
        f"【{card.get('priority') or 'P1'} 外部安全讯息】",
        str(card.get("title") or "未命名讯息"),
        "",
        str(card.get("summary") or card.get("recommended_action") or "请安全负责人复核。"),
    ]
    url = card.get("url") or card.get("source_url")
    if url:
        lines.extend(["", f"链接：{url}"])
    if payload.get("recommended_action"):
        lines.extend(["", f"建议动作：{payload.get('recommended_action')}"])
    return "\n".join(lines)


def _confirmation_from_tool(tool_result: dict[str, Any]) -> dict[str, Any]:
    data = tool_result.get("data")
    if isinstance(data, dict):
        confirmation = data.get("confirmation")
        if isinstance(confirmation, dict):
            return confirmation
    return {}


async def _start_step(workflow_run_id: str, step_name: str, agent_name: str, tool_name: str | None) -> dict[str, Any]:
    result = await workflow_store.append_step(
        workflow_run_id=workflow_run_id,
        step_name=step_name,
        agent_name=agent_name,
        tool_name=tool_name,
        status="running",
    )
    step_id = None
    if isinstance(result.get("workflow_step"), dict):
        step_id = result["workflow_step"].get("workflow_step_id")
    return {"workflow_step_id": step_id or "", "tool_result": result}


async def _finish_step(step: dict[str, Any], result: dict[str, Any]) -> None:
    step_id = step.get("workflow_step_id")
    if not step_id:
        return
    await workflow_store.update_step(
        workflow_step_id=str(step_id),
        status="succeeded" if result.get("ok", True) else "failed",
        output_payload=result,
        error=str(result.get("error")) if not result.get("ok", True) else None,
    )


def _extract_llm_json(result: dict[str, Any]) -> dict[str, Any]:
    if "choices" not in result:
        return result if isinstance(result, dict) else {}
    choices = result.get("choices")
    if not isinstance(choices, list) or not choices:
        return {}
    message = choices[0].get("message") if isinstance(choices[0], dict) else {}
    content = message.get("content") if isinstance(message, dict) else ""
    if isinstance(content, dict):
        return content
    if not isinstance(content, str):
        return {}
    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}
    return {}


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []
