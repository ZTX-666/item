from __future__ import annotations

from pathlib import Path
from typing import Any

from chitung_center.confirmation_service import handle_card_action
from chitung_center.config import settings
from chitung_center.models import ChatMessageRequest
from chitung_center.orchestrator import orchestrator
from chitung_center.toolbox_client import toolbox_client

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}


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
    if _is_message_event(str(event_type)) and _is_group_message(payload) and not _mentions_this_bot(payload):
        return {
            "ok": True,
            "stage": "ignored_group_message",
            "message": "Group message archived without bot mention.",
            "tool_result": callback,
        }

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

    message_text = _strip_bot_mentions(message_text, payload)
    if not message_text:
        return {
            "ok": True,
            "stage": "archived_only",
            "message": "Feishu event archived after removing bot mention with no remaining routable text.",
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
    attachment_sends = await _send_reply_attachments(str(chat_id), chat_response_payload) if chat_id else []
    return {
        "ok": True,
        "stage": "chat_routed",
        "tool_result": callback,
        "route": route,
        "chat_response": chat_response_payload,
        "reply_send": reply_send,
        "attachment_sends": attachment_sends,
    }


def _is_message_event(event_type: str) -> bool:
    return "im.message.receive" in event_type or event_type in {"message", "message_event"}


def _event(payload: dict[str, Any]) -> dict[str, Any]:
    event = payload.get("event") or payload.get("event_callback") or payload
    return event if isinstance(event, dict) else {}


def _message(payload: dict[str, Any]) -> dict[str, Any]:
    message = _event(payload).get("message") or {}
    return message if isinstance(message, dict) else {}


def _is_group_message(payload: dict[str, Any]) -> bool:
    chat_type = str(_message(payload).get("chat_type") or _event(payload).get("chat_type") or "").lower()
    return chat_type == "group"


def _mentions_this_bot(payload: dict[str, Any]) -> bool:
    return any(_is_this_bot_mention(item) for item in _message_mentions(payload))


def _strip_bot_mentions(text: str, payload: dict[str, Any]) -> str:
    cleaned = text
    for mention in _message_mentions(payload):
        if not _is_this_bot_mention(mention):
            continue
        key = str(mention.get("key") or "").strip()
        name = str(mention.get("name") or "").strip()
        for token in [key, f"@{name}" if name else "", name if cleaned.strip().startswith(name) else ""]:
            if token:
                cleaned = cleaned.replace(token, " ")
    return " ".join(cleaned.split()).strip()


def _message_mentions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    mentions = _message(payload).get("mentions") or _event(payload).get("mentions") or []
    if not isinstance(mentions, list):
        return []
    return [item for item in mentions if isinstance(item, dict)]


def _is_this_bot_mention(mention: dict[str, Any]) -> bool:
    configured_open_id = settings.feishu_bot_open_id.strip()
    if configured_open_id:
        mention_id = mention.get("id") if isinstance(mention.get("id"), dict) else {}
        mention_open_id = str(mention_id.get("open_id") or mention.get("open_id") or "").strip()
        if mention_open_id == configured_open_id:
            return True

    mention_name = str(mention.get("name") or "").strip()
    configured_names = [name.strip() for name in settings.feishu_bot_names.split(",") if name.strip()]
    if mention_name and mention_name in configured_names:
        return True

    mentioned_type = str(mention.get("mentioned_type") or "").lower()
    return not configured_names and mentioned_type in {"app", "bot"}


async def _send_reply_attachments(chat_id: str, chat_response_payload: dict[str, Any]) -> list[dict[str, Any]]:
    sends: list[dict[str, Any]] = []
    for path in _extract_attachment_paths(chat_response_payload):
        tool_name = "feishu_send_image_message" if _is_image_path(path) else "feishu_send_file_message"
        payload_key = "image_path" if tool_name == "feishu_send_image_message" else "file_path"
        sends.append(
            await toolbox_client.call_tool(
                tool_name,
                {"receive_id": chat_id, "receive_id_type": "chat_id", payload_key: path},
            )
        )
    return sends


def _extract_attachment_paths(chat_response_payload: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for key in ("output_path", "file_path", "image_path", "path"):
        _append_path(paths, chat_response_payload.get(key))
    for key in ("files", "images", "attachments", "tool_results"):
        _collect_paths(chat_response_payload.get(key), paths)
    return list(dict.fromkeys(paths))


def _collect_paths(value: Any, paths: list[str]) -> None:
    if isinstance(value, list):
        for item in value:
            _collect_paths(item, paths)
        return
    if not isinstance(value, dict):
        return
    for key in ("output_path", "file_path", "image_path", "path"):
        _append_path(paths, value.get(key))
    for key in ("files", "images", "attachments", "data"):
        _collect_paths(value.get(key), paths)


def _append_path(paths: list[str], value: Any) -> None:
    if isinstance(value, str) and value.strip():
        paths.append(value.strip())


def _is_image_path(path: str) -> bool:
    return Path(path).suffix.lower() in IMAGE_SUFFIXES
