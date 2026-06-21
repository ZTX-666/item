from __future__ import annotations

from typing import Any

from chitung_center.confirmation_service import handle_card_action
from chitung_center.models import ChatMessageRequest
from chitung_center.orchestrator import orchestrator
from chitung_center.toolbox_client import toolbox_client


async def handle_feishu_event(payload: dict[str, Any]) -> dict[str, Any]:
    callback = await toolbox_client.call_tool("feishu_handle_event_callback", {"payload": payload})
    if not callback.get("ok"):
        return {"ok": False, "stage": "callback", "tool_result": callback}

    # Encrypted events are decrypted inside the toolbox; use the decrypted
    # payload (returned in callback.data.payload) for routing decisions.
    if isinstance(callback.get("data"), dict) and isinstance(callback["data"].get("payload"), dict):
        payload = callback["data"]["payload"]

    challenge = payload.get("challenge") or (
        callback.get("data", {}).get("challenge") if isinstance(callback.get("data"), dict) else None
    )
    if payload.get("type") == "url_verification" and challenge:
        return {
            "ok": True,
            "stage": "url_verification",
            "response": {"challenge": challenge},
            "tool_result": callback,
        }

    event_type = (
        payload.get("header", {}).get("event_type")
        or payload.get("event", {}).get("type")
        or payload.get("type")
        or ""
    )

    if "card.action" in str(event_type) or "card_action" in str(event_type):
        parsed = await toolbox_client.call_tool("feishu_parse_card_action", {"payload": payload})
        card_action = {}
        if isinstance(parsed.get("data"), dict):
            card_action = parsed["data"].get("card_action") or {}
        action_value = card_action.get("action_value") or {}
        action_id = (
            action_value.get("action_id")
            or card_action.get("action_id")
            or "approve_confirmation"
        )
        result = await handle_card_action(
            action_id=str(action_id),
            card_data={
                "confirmation_id": action_value.get("confirmation_id"),
                "receive_id": action_value.get("receive_id"),
                "briefing_text": action_value.get("briefing_text"),
                **action_value,
            },
            user_id=str(card_action.get("open_id") or "feishu_user"),
            channel="feishu",
        )
        return {"ok": True, "stage": "card_action", "parsed": parsed, "result": result, "tool_result": callback}

    route = await toolbox_client.call_tool("feishu_build_center_route_payload", {"payload": payload})
    center_payload = {}
    if isinstance(route.get("data"), dict):
        center_payload = route["data"].get("center_payload") or {}

    message_text = str(center_payload.get("message") or "").strip()
    if not message_text:
        return {
            "ok": True,
            "stage": "archived_only",
            "message": "Feishu event archived without routable text message.",
            "tool_result": callback,
            "route": route,
        }

    chat_request = ChatMessageRequest(
        message=message_text,
        channel="feishu",
        user_id=str(center_payload.get("user_id") or "feishu_user"),
        project_id=center_payload.get("project_id"),
        metadata=center_payload.get("metadata") or {},
    )
    chat_response = await orchestrator.handle_message(chat_request)
    chat_response_payload = chat_response.model_dump()
    reply_send: dict[str, Any] | None = None
    chat_id = center_payload.get("metadata", {}).get("chat_id") if isinstance(center_payload.get("metadata"), dict) else None
    reply_text = str(chat_response_payload.get("reply") or "").strip()
    if chat_id and reply_text:
        reply_send = await toolbox_client.call_tool(
            "feishu_send_text_message",
            {"receive_id": str(chat_id), "receive_id_type": "chat_id", "text": reply_text},
        )
    return {
        "ok": True,
        "stage": "chat_routed",
        "tool_result": callback,
        "route": route,
        "chat_response": chat_response_payload,
        "reply_send": reply_send,
    }
