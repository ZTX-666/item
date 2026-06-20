from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from ..models import ToolResult, ToolSpec


class FeishuMessageParseRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


class FeishuCardActionParseRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


class FeishuPlatformMessageRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)
    default_user_id: str = "feishu_user"


class FeishuCenterRoutePayloadRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)
    default_user_id: str = "feishu_user"
    project_id: str | None = None


FEISHU_EVENT_TOOL_SPECS = [
    ToolSpec(
        name="feishu_parse_message_event",
        description="Parse a Feishu message callback into open_id, chat_id, message_id, text, attachments, and metadata.",
        input_schema={"type": "object", "properties": {"payload": {"type": "object"}}, "required": ["payload"]},
    ),
    ToolSpec(
        name="feishu_parse_card_action",
        description="Parse a Feishu interactive card action callback into operator, action_id, action_value, message_id, and card_id.",
        input_schema={"type": "object", "properties": {"payload": {"type": "object"}}, "required": ["payload"]},
    ),
    ToolSpec(
        name="feishu_event_to_platform_message",
        description="Convert a Feishu message event to the platform's channel/user/chat/message/attachments shape.",
        input_schema={
            "type": "object",
            "properties": {"payload": {"type": "object"}, "default_user_id": {"type": "string", "default": "feishu_user"}},
            "required": ["payload"],
        },
    ),
    ToolSpec(
        name="feishu_build_center_route_payload",
        description="Build a /api/chat/message-compatible payload from a Feishu message callback.",
        input_schema={
            "type": "object",
            "properties": {
                "payload": {"type": "object"},
                "default_user_id": {"type": "string", "default": "feishu_user"},
                "project_id": {"type": "string"},
            },
            "required": ["payload"],
        },
    ),
]


def feishu_parse_message_event(req: FeishuMessageParseRequest) -> ToolResult:
    event = _event(req.payload)
    sender = event.get("sender") or {}
    message = event.get("message") or {}
    chat_id = message.get("chat_id") or event.get("chat_id")
    message_id = message.get("message_id") or event.get("message_id")
    message_type = message.get("message_type") or event.get("message_type")
    content = _loads_maybe_json(message.get("content") or event.get("content"))
    text = _extract_text(content)
    attachments = _extract_attachments(message, content)
    parsed = {
        "event_id": _header(req.payload).get("event_id") or event.get("event_id"),
        "event_type": _header(req.payload).get("event_type") or event.get("type") or req.payload.get("type"),
        "tenant_key": _header(req.payload).get("tenant_key"),
        "schema": req.payload.get("schema"),
        "open_id": _first_non_empty(sender.get("sender_id", {}).get("open_id"), sender.get("open_id"), event.get("open_id")),
        "union_id": _first_non_empty(sender.get("sender_id", {}).get("union_id"), sender.get("union_id")),
        "user_id": _first_non_empty(sender.get("sender_id", {}).get("user_id"), sender.get("user_id")),
        "chat_id": chat_id,
        "chat_type": message.get("chat_type") or event.get("chat_type"),
        "message_id": message_id,
        "message_type": message_type,
        "text": text,
        "attachments": attachments,
        "raw_content": content,
        "raw_event": event,
    }
    return ToolResult(
        ok=True,
        tool="feishu_parse_message_event",
        summary="Parsed Feishu message event.",
        data={"message": parsed, "is_text_message": bool(text)},
    )


def feishu_parse_card_action(req: FeishuCardActionParseRequest) -> ToolResult:
    event = _event(req.payload)
    action = event.get("action") or req.payload.get("action") or {}
    operator = event.get("operator") or event.get("user") or req.payload.get("operator") or {}
    context = event.get("context") or {}
    action_value = action.get("value") or {}
    if isinstance(action_value, str):
        action_value = _loads_maybe_json(action_value)
    parsed = {
        "event_id": _header(req.payload).get("event_id") or event.get("event_id"),
        "event_type": _header(req.payload).get("event_type") or event.get("type") or req.payload.get("type"),
        "open_id": _first_non_empty(operator.get("open_id"), operator.get("operator_id", {}).get("open_id")),
        "union_id": _first_non_empty(operator.get("union_id"), operator.get("operator_id", {}).get("union_id")),
        "user_id": _first_non_empty(operator.get("user_id"), operator.get("operator_id", {}).get("user_id")),
        "action_id": _first_non_empty(action.get("tag"), action.get("name"), action_value.get("action_id"), action_value.get("id")),
        "action_value": action_value,
        "form_value": action.get("form_value") or {},
        "message_id": _first_non_empty(context.get("open_message_id"), event.get("open_message_id"), event.get("message_id")),
        "card_id": _first_non_empty(context.get("open_card_id"), event.get("open_card_id"), event.get("card_id")),
        "raw_event": event,
    }
    return ToolResult(
        ok=True,
        tool="feishu_parse_card_action",
        summary="Parsed Feishu card action event.",
        data={"card_action": parsed, "requires_action_lookup": not bool(parsed["action_value"])},
    )


def feishu_event_to_platform_message(req: FeishuPlatformMessageRequest) -> ToolResult:
    parsed_result = feishu_parse_message_event(FeishuMessageParseRequest(payload=req.payload))
    message = parsed_result.data["message"]
    user_id = message.get("open_id") or message.get("user_id") or req.default_user_id
    platform_message = {
        "channel": "feishu",
        "user_id": user_id,
        "chat_id": message.get("chat_id"),
        "message": message.get("text") or "",
        "attachments": message.get("attachments") or [],
        "metadata": {
            "message_id": message.get("message_id"),
            "event_id": message.get("event_id"),
            "event_type": message.get("event_type"),
            "tenant_key": message.get("tenant_key"),
            "message_type": message.get("message_type"),
            "raw": req.payload,
        },
    }
    return ToolResult(
        ok=True,
        tool="feishu_event_to_platform_message",
        summary="Converted Feishu event to platform message payload.",
        data={"platform_message": platform_message},
    )


def feishu_build_center_route_payload(req: FeishuCenterRoutePayloadRequest) -> ToolResult:
    converted = feishu_event_to_platform_message(
        FeishuPlatformMessageRequest(payload=req.payload, default_user_id=req.default_user_id)
    )
    platform_message = converted.data["platform_message"]
    center_payload = {
        "message": platform_message["message"],
        "channel": "feishu",
        "user_id": platform_message["user_id"],
        "project_id": req.project_id,
        "metadata": {
            "chat_id": platform_message.get("chat_id"),
            "attachments": platform_message.get("attachments") or [],
            **platform_message.get("metadata", {}),
        },
    }
    return ToolResult(
        ok=True,
        tool="feishu_build_center_route_payload",
        summary="Built /api/chat/message compatible payload from Feishu event.",
        data={"center_payload": center_payload, "platform_message": platform_message},
    )


def _header(payload: dict[str, Any]) -> dict[str, Any]:
    return payload.get("header") or {}


def _event(payload: dict[str, Any]) -> dict[str, Any]:
    return payload.get("event") or payload.get("event_callback") or payload


def _loads_maybe_json(value: Any) -> Any:
    if value is None:
        return {}
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {"text": value}


def _extract_text(content: Any) -> str:
    if isinstance(content, dict):
        if isinstance(content.get("text"), str):
            return content["text"].strip()
        if isinstance(content.get("content"), str):
            return content["content"].strip()
        if isinstance(content.get("title"), str):
            return content["title"].strip()
    if isinstance(content, list):
        pieces: list[str] = []
        for item in content:
            if isinstance(item, dict):
                pieces.append(_extract_text(item))
            elif isinstance(item, str):
                pieces.append(item)
        return " ".join(piece for piece in pieces if piece).strip()
    if isinstance(content, str):
        return content.strip()
    return ""


def _extract_attachments(message: dict[str, Any], content: Any) -> list[dict[str, Any]]:
    attachments: list[dict[str, Any]] = []
    for key in ("image_key", "file_key", "file_id", "media_id"):
        value = message.get(key)
        if value:
            attachments.append({"kind": key, "resource_id": value, "source": "message"})
    if isinstance(content, dict):
        for key in ("image_key", "file_key", "file_id", "media_id"):
            value = content.get(key)
            if value:
                attachments.append({"kind": key, "resource_id": value, "source": "content"})
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                attachments.extend(_extract_attachments({}, item))
    return attachments


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value:
            return value
    return None
