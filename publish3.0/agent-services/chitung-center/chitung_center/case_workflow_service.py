from __future__ import annotations

from typing import Any

from chitung_center.models import CaseWorkflowRequest, NotificationSendRequest
from chitung_center.toolbox_client import toolbox_client


async def draft_rectification_notice(request: CaseWorkflowRequest) -> dict[str, Any]:
    notice = await toolbox_client.call_tool(
        "generate_rectification_notice",
        {"case_id": request.case_id, "language": "zh-HK", "tone": "formal"},
    )
    status = await toolbox_client.call_tool(
        "update_safety_case_status",
        {
            "case_id": request.case_id,
            "status": "rectification_notice_drafted",
            "notes": request.notes or "Rectification notice drafted; waiting for human send confirmation.",
        },
    )
    return {
        "ok": bool(notice.get("ok")),
        "message": "Rectification notice drafted. It must be sent by a human-confirmed channel.",
        "notice": _tool_data(notice),
        "tool_results": [notice, status],
    }


async def confirm_contractor_assignment(request: CaseWorkflowRequest) -> dict[str, Any]:
    assignment = await toolbox_client.call_tool(
        "assign_safety_case",
        {
            "case_id": request.case_id,
            "contractor": request.contractor,
            "due_date": request.due_date,
            "priority": "high",
        },
    )
    status = await toolbox_client.call_tool(
        "update_safety_case_status",
        {
            "case_id": request.case_id,
            "status": "contractor_confirmed",
            "notes": request.notes or "Contractor assignment confirmed by human operator.",
        },
    )
    return {
        "ok": bool(assignment.get("ok")),
        "message": "Contractor confirmation recorded.",
        "assignment": _tool_data(assignment),
        "tool_results": [assignment, status],
    }


async def close_case_after_review(request: CaseWorkflowRequest) -> dict[str, Any]:
    close_result = await toolbox_client.call_tool(
        "close_case_with_review",
        {
            "case_id": request.case_id,
            "review_notes": request.notes or "Reviewed and closed from Chitung desktop workbench.",
            "reviewer": request.reviewer,
            "evidence_paths": request.evidence_paths,
        },
    )
    return {
        "ok": bool(close_result.get("ok")),
        "message": "Case closed after review.",
        "review": _tool_data(close_result),
        "tool_result": close_result,
    }


async def send_rectification_notification(request: NotificationSendRequest) -> dict[str, Any]:
    if request.channel == "feishu":
        send_result = await toolbox_client.call_tool("notify_feishu", {"text": request.text})
        status_value = "notification_sent_feishu" if send_result.get("ok") else "notification_send_failed"
        status_notes = send_result.get("summary") or send_result.get("error") or "Feishu send attempted."
        status = await toolbox_client.call_tool(
            "update_safety_case_status",
            {"case_id": request.case_id, "status": status_value, "notes": status_notes},
        )
        return {
            "ok": bool(send_result.get("ok")),
            "message": status_notes,
            "channel": request.channel,
            "send_result": send_result,
            "tool_results": [send_result, status],
        }

    draft = await toolbox_client.call_tool(
        "draft_group_message",
        {
            "recipients": [request.contractor or "default_contractor"],
            "subject": f"整改通知 #{request.case_id}",
            "body": request.text,
            "source_case_id": request.case_id,
            "channel": "whatsapp",
        },
    )
    draft_id = _tool_data(draft).get("draft_id")
    confirm = await toolbox_client.call_tool(
        "send_group_message_with_confirm",
        {"draft_id": draft_id, "confirmed": True, "confirmed_by": request.confirmed_by},
    ) if draft_id else {"ok": False, "summary": "WhatsApp draft was not created.", "error": "missing draft_id"}
    status = await toolbox_client.call_tool(
        "update_safety_case_status",
        {
            "case_id": request.case_id,
            "status": "notification_confirmed_pending_sender" if confirm.get("ok") else "notification_send_failed",
            "notes": confirm.get("summary") or confirm.get("error") or "WhatsApp notification confirmed.",
        },
    )
    return {
        "ok": bool(confirm.get("ok")),
        "message": confirm.get("summary") or "WhatsApp notification confirmed.",
        "channel": request.channel,
        "send_result": confirm,
        "tool_results": [draft, confirm, status],
    }


def _tool_data(result: dict[str, Any]) -> dict[str, Any]:
    data = result.get("data")
    return data if isinstance(data, dict) else {}
