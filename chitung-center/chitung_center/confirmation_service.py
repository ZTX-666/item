from __future__ import annotations

from typing import Any

from chitung_center.audit import audit_logger
from chitung_center.settings_service import get_connector_settings_status
from chitung_center.toolbox_client import toolbox_client
from chitung_center import workflow_store


APPROVE_ACTIONS = {
    "approve",
    "confirm",
    "approve_confirmation",
    "confirm_send",
    "confirm_rectification",
    "confirm_daily_briefing",
}

REJECT_ACTIONS = {
    "reject",
    "dismiss",
    "ignore",
    "false_positive",
    "mark_false_positive",
}


async def list_pending_confirmations(
    *,
    status: str = "pending",
    action_type: str | None = None,
    source_channel: str | None = None,
    workflow_run_id: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    await workflow_store.ensure_schema()
    result = await toolbox_client.call_tool(
        "query_pending_confirmations",
        {
            "status": status,
            "action_type": action_type,
            "source_channel": source_channel,
            "workflow_run_id": workflow_run_id,
            "limit": limit,
        },
    )
    items = []
    if isinstance(result.get("data"), dict):
        items = result["data"].get("items", [])
    return {"ok": bool(result.get("ok")), "items": items, "tool_result": result}


async def create_pending_confirmation(
    *,
    action_type: str,
    title: str,
    summary: str = "",
    payload: dict[str, Any] | None = None,
    risk_level: str = "medium",
    source_channel: str = "local_web",
    source_user_id: str | None = None,
    workflow_run_id: str | None = None,
    workflow_step_id: str | None = None,
    idempotency_key: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    await workflow_store.ensure_schema()
    return await toolbox_client.call_tool(
        "create_pending_confirmation",
        {
            "action_type": action_type,
            "title": title,
            "summary": summary,
            "payload": payload or {},
            "risk_level": risk_level,
            "source_channel": source_channel,
            "source_user_id": source_user_id,
            "workflow_run_id": workflow_run_id,
            "workflow_step_id": workflow_step_id,
            "idempotency_key": idempotency_key,
            "metadata": metadata or {},
        },
    )


async def resolve_confirmation(
    *,
    confirmation_id: str,
    decision: str,
    decided_by: str = "local_user",
    notes: str | None = None,
    result_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    await workflow_store.ensure_schema()
    return await toolbox_client.call_tool(
        "resolve_pending_confirmation",
        {
            "confirmation_id": confirmation_id,
            "decision": decision,
            "decided_by": decided_by,
            "notes": notes,
            "result_payload": result_payload or {},
        },
    )


async def execute_approved_confirmation(confirmation: dict[str, Any], *, decided_by: str) -> dict[str, Any]:
    action_type = str(confirmation.get("action_type") or "")
    payload = confirmation.get("payload") or {}
    if not isinstance(payload, dict):
        payload = {}

    if action_type in {"send_feishu_message", "send_feishu_card"}:
        tool_result = await _execute_feishu_send(action_type, payload)
    elif action_type == "send_whatsapp_message":
        tool_result = await toolbox_client.call_tool(
            "whatsapp_send_text_confirmed",
            {
                "chat": payload.get("chat"),
                "text": payload.get("text") or payload.get("body") or "",
                "confirmed": True,
                "dry_run": bool(payload.get("dry_run", False)),
                "confirmed_by": decided_by,
            },
        )
    elif action_type == "generate_rectification_notice":
        tool_result = await toolbox_client.call_tool(
            "generate_rectification_notice",
            {"case_id": payload.get("case_id"), "language": payload.get("language", "zh-HK")},
        )
    elif action_type == "generate_warning_letter":
        tool_result = await toolbox_client.call_tool(
            "generate_warning_letter",
            {"case_id": payload.get("case_id"), "language": payload.get("language", "zh-HK")},
        )
    elif action_type == "close_safety_case":
        tool_result = await toolbox_client.call_tool(
            "close_case_with_review",
            {
                "case_id": payload.get("case_id"),
                "review_notes": payload.get("review_notes") or "Confirmed via Chitung Center.",
                "reviewer": decided_by,
                "evidence_paths": payload.get("evidence_paths") or [],
            },
        )
    elif action_type == "draft_group_message":
        tool_result = await toolbox_client.call_tool(
            "draft_group_message",
            {
                "recipients": payload.get("recipients") or [],
                "subject": payload.get("subject"),
                "body": payload.get("body") or payload.get("text") or "",
                "source_case_id": payload.get("source_case_id"),
                "channel": payload.get("channel", "feishu"),
            },
        )
    else:
        return {
            "ok": False,
            "message": f"No execution handler for action_type={action_type}",
            "action_type": action_type,
        }

    execution_ok = bool(tool_result.get("ok"))
    simulated = bool(tool_result.get("simulated"))
    decision = "mark_executed" if (execution_ok or simulated) else "mark_failed"
    await resolve_confirmation(
        confirmation_id=str(confirmation.get("confirmation_id")),
        decision=decision,
        decided_by=decided_by,
        notes="Simulated local delivery (Feishu not configured)." if simulated else "Auto execution after approval.",
        result_payload={"tool_result": tool_result, "simulated": simulated},
    )
    return {
        "ok": execution_ok,
        "message": (
            "Approved action archived locally; configure Feishu to send externally."
            if simulated
            else ("Approved action executed." if execution_ok else "Approved action execution failed.")
        ),
        "action_type": action_type,
        "tool_result": tool_result,
        "simulated": simulated,
    }


async def resolve_and_execute(
    *,
    confirmation_id: str,
    decision: str,
    decided_by: str = "local_user",
    notes: str | None = None,
) -> dict[str, Any]:
    normalized = str(decision).lower()
    if normalized == "approve":
        approved = await resolve_confirmation(
            confirmation_id=confirmation_id,
            decision="approve",
            decided_by=decided_by,
            notes=notes or "Approved from confirmations API.",
        )
        confirmation = _confirmation_from_tool(approved)
        if not confirmation:
            confirmation = {"confirmation_id": confirmation_id}
        execution = await execute_approved_confirmation(confirmation, decided_by=decided_by)
        return {
            "ok": bool(execution.get("ok")),
            "confirmation_id": confirmation_id,
            "approval": approved,
            "execution": execution,
        }

    rejected = await resolve_confirmation(
        confirmation_id=confirmation_id,
        decision="reject",
        decided_by=decided_by,
        notes=notes or "Rejected from confirmations API.",
    )
    return {"ok": True, "confirmation_id": confirmation_id, "rejection": rejected}


async def handle_card_action(
    *,
    action_id: str,
    card_data: dict[str, Any],
    user_id: str = "local_user",
    channel: str = "local_web",
) -> dict[str, Any]:
    await workflow_store.ensure_schema()
    audit_id = audit_logger.write(
        "card_action_requested",
        {"action_id": action_id, "channel": channel, "user_id": user_id, "card_data_keys": sorted(card_data.keys())},
    )

    nested_data = card_data.get("data") if isinstance(card_data.get("data"), dict) else {}
    confirmation_id = (
        card_data.get("confirmation_id")
        or card_data.get("pending_confirmation_id")
        or nested_data.get("confirmation_id")
        or nested_data.get("pending_confirmation_id")
    )
    if confirmation_id:
        normalized = str(action_id).lower()
        if normalized in APPROVE_ACTIONS:
            approved = await resolve_confirmation(
                confirmation_id=str(confirmation_id),
                decision="approve",
                decided_by=user_id,
                notes="Approved from action card.",
            )
            confirmation = {}
            if isinstance(approved.get("data"), dict):
                confirmation = approved["data"].get("confirmation") or {}
            execution = await execute_approved_confirmation(confirmation, decided_by=user_id)
            return {
                "ok": execution.get("ok", False),
                "audit_id": audit_id,
                "action_id": action_id,
                "confirmation_id": confirmation_id,
                "approval": approved,
                "execution": execution,
            }
        if normalized in REJECT_ACTIONS:
            rejected = await resolve_confirmation(
                confirmation_id=str(confirmation_id),
                decision="reject",
                decided_by=user_id,
                notes="Rejected from action card.",
            )
            return {"ok": True, "audit_id": audit_id, "action_id": action_id, "confirmation_id": confirmation_id, "rejection": rejected}

    if action_id == "draft_rectification_notice":
        case_id = card_data.get("case_id") or _nested_case_id(card_data)
        workflow_run_id = card_data.get("workflow_run_id")
        draft = await toolbox_client.call_tool("generate_rectification_notice", {"case_id": case_id})
        pending = await create_pending_confirmation(
            action_type="generate_rectification_notice",
            title="确认生成整改通知",
            summary="请确认整改通知草稿后才会进入外发流程。",
            payload={"case_id": case_id, "draft": draft},
            risk_level="high",
            source_channel=channel,
            source_user_id=user_id,
            workflow_run_id=str(workflow_run_id) if workflow_run_id else None,
        )
        confirmation = _confirmation_from_tool(pending)
        return {
            "ok": True,
            "audit_id": audit_id,
            "action_id": action_id,
            "message": "Rectification notice draft created and waiting for confirmation.",
            "draft": draft,
            "confirmation": confirmation,
            "navigate_to": "pending-confirmations",
        }

    if action_id == "generate_daily_briefing":
        workflow_run_id = card_data.get("workflow_run_id")
        briefing_text = (
            card_data.get("briefing_text")
            or _extract_nested_briefing(card_data.get("briefing"))
            or card_data.get("summary")
            or "每日风险简报草稿"
        )
        pending = await create_pending_confirmation(
            action_type="send_feishu_message",
            title="确认发送每日风险简报",
            summary="确认后才会发送到飞书群；未配置飞书凭证时将本地归档。",
            payload={
                "receive_id": card_data.get("receive_id"),
                "receive_id_type": card_data.get("receive_id_type", "chat_id"),
                "text": briefing_text,
            },
            risk_level="medium",
            source_channel=channel,
            source_user_id=user_id,
            workflow_run_id=str(workflow_run_id) if workflow_run_id else None,
        )
        return {
            "ok": True,
            "audit_id": audit_id,
            "action_id": action_id,
            "message": "Daily briefing send request queued for confirmation.",
            "confirmation": _confirmation_from_tool(pending),
            "navigate_to": "pending-confirmations",
        }

    if action_id == "open_visual_patrol":
        return {
            "ok": True,
            "audit_id": audit_id,
            "action_id": action_id,
            "message": "Open visual patrol page to run RTMP/VLM detection.",
            "navigate_to": "visual-patrol",
        }

    if action_id in {"open_shanshan_doc", "link_required_forms", "search_form_templates", "summarize_policy_document"}:
        navigate_to = "shanshan-doc" if action_id == "open_shanshan_doc" else "smart-form" if action_id in {"link_required_forms", "search_form_templates"} else None
        return {
            "ok": True,
            "audit_id": audit_id,
            "action_id": action_id,
            "message": "Navigation or lookup action acknowledged.",
            "navigate_to": navigate_to,
            "card_data": card_data,
        }

    return {
        "ok": True,
        "audit_id": audit_id,
        "action_id": action_id,
        "message": "Action received. No dedicated handler yet; stored in audit log only.",
        "card_data": card_data,
    }


def _confirmation_from_tool(tool_result: dict[str, Any]) -> dict[str, Any]:
    data = tool_result.get("data")
    if isinstance(data, dict):
        confirmation = data.get("confirmation")
        if isinstance(confirmation, dict):
            return confirmation
    return {}


def _nested_case_id(card_data: dict[str, Any]) -> int | None:
    tool_result = card_data.get("tool_result")
    if isinstance(tool_result, dict):
        data = tool_result.get("data")
        if isinstance(data, dict):
            case_id = data.get("case_id")
            if case_id is not None:
                return int(case_id)
    return None


def _extract_nested_briefing(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    data = value.get("data")
    if isinstance(data, dict):
        for key in ("briefing_text", "text", "summary"):
            text = data.get(key)
            if isinstance(text, str) and text.strip():
                return text.strip()
    return None


def _feishu_delivery_mode() -> str:
    connectors = get_connector_settings_status()
    feishu = connectors.get("feishu")
    if not isinstance(feishu, dict):
        return "none"
    if feishu.get("configured"):
        return "app"
    if feishu.get("webhook_configured"):
        return "webhook"
    return "none"


async def _execute_feishu_send(action_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    mode = _feishu_delivery_mode()
    text = str(payload.get("text") or payload.get("body") or "")

    if action_type == "send_feishu_card" and mode == "app":
        return await toolbox_client.call_tool(
            "feishu_send_interactive_card",
            {
                "receive_id": payload.get("receive_id"),
                "receive_id_type": payload.get("receive_id_type", "chat_id"),
                "card": payload.get("card") or {},
            },
        )

    if mode == "app":
        return await toolbox_client.call_tool(
            "feishu_send_text_message",
            {
                "receive_id": payload.get("receive_id"),
                "receive_id_type": payload.get("receive_id_type", "chat_id"),
                "text": text,
            },
        )

    if mode == "webhook":
        return await toolbox_client.call_tool("notify_feishu", {"text": text})

    draft = await toolbox_client.call_tool(
        "draft_group_message",
        {
            "recipients": [str(payload.get("receive_id") or "local-feishu-placeholder")],
            "subject": str(payload.get("title") or "待发送飞书消息"),
            "body": text,
            "channel": "feishu",
        },
    )
    archive = await toolbox_client.call_tool(
        "archive_sent_notification",
        {
            "channel": "feishu",
            "recipients": [str(payload.get("receive_id") or "unconfigured")],
            "text": text,
            "status": "simulated_local",
            "metadata": {"reason": "feishu_credentials_missing"},
        },
    )
    return {
        "ok": True,
        "simulated": True,
        "delivery_mode": "local_archive",
        "message": "Feishu credentials are not configured. Message drafted and archived locally.",
        "draft": draft,
        "archive": archive,
    }
