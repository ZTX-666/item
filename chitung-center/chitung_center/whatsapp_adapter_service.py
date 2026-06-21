from __future__ import annotations

import json
import re
from typing import Any

import httpx

from chitung_center.audit import audit_logger
from chitung_center.llm_gateway import llm_gateway
from chitung_center.models import ChatMessageRequest
from chitung_center.orchestrator import orchestrator
from chitung_center.rag_service import RagDependencyError, RagServiceError, rag_service
from chitung_center.toolbox_client import toolbox_client


TRIGGER_PATTERNS = (
    r"@赤瞳",
    r"#赤瞳",
    r"/ai\b",
    r"问赤瞳",
    r"赤瞳[:：]",
)


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("String", "User", "Raw", "JID", "jid", "id"):
            nested = value.get(key)
            if isinstance(nested, str) and nested:
                return nested
    return str(value)


def _parse_wacli_message(payload: dict[str, Any]) -> dict[str, Any]:
    chat = payload.get("Chat") or payload.get("chat") or payload.get("ChatJID") or payload.get("chat_jid")
    text = payload.get("Text") or payload.get("text") or payload.get("DisplayText") or payload.get("display_text") or ""
    return {
        "chat_id": _as_text(chat),
        "message_id": _as_text(payload.get("ID") or payload.get("MsgID") or payload.get("message_id") or payload.get("id")),
        "sender_id": _as_text(payload.get("SenderJID") or payload.get("sender_jid") or payload.get("sender_id")),
        "sender_name": _as_text(payload.get("PushName") or payload.get("SenderName") or payload.get("sender_name")),
        "text": _as_text(text).strip(),
        "from_me": bool(payload.get("FromMe") or payload.get("from_me")),
        "raw": payload,
    }


def _strip_trigger(text: str) -> tuple[bool, str, str]:
    for pattern in TRIGGER_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            cleaned = (text[: match.start()] + text[match.end() :]).strip()
            cleaned = re.sub(r"^[,，:：\s]+", "", cleaned).strip()
            return True, cleaned or text.strip(), match.group(0)
    return False, text.strip(), ""


async def _safe_rag_query(query: str) -> dict[str, Any]:
    try:
        return await rag_service.query(query=query, top_k=5, collection=None)
    except (RagDependencyError, RagServiceError, Exception) as exc:  # noqa: BLE001
        return {"ok": False, "items": [], "error": str(exc)}


def _rag_context(rag: dict[str, Any]) -> str:
    items = rag.get("items") if isinstance(rag, dict) else []
    if not isinstance(items, list):
        return ""
    lines: list[str] = []
    for idx, item in enumerate(items[:5], start=1):
        if not isinstance(item, dict):
            continue
        source = item.get("source_file_name") or item.get("doc_id") or "knowledge"
        text = str(item.get("text") or "").strip()
        if text:
            lines.append(f"[{idx}] {source}: {text[:600]}")
    return "\n".join(lines)


async def _rag_assisted_reply(user_text: str, rag_context: str, fallback_reply: str) -> str | None:
    system_prompt = (
        "你是赤瞳安全智能平台的 WhatsApp 群机器人。"
        "请只根据用户问题、已有工作流结果和知识库片段生成简洁、可执行的中文回复。"
        "如果知识库片段为空或不足，请基于通用安全管理原则回答，并明确提示需要人工确认。"
        "只返回 JSON：{\"reply\":\"...\"}。"
    )
    payload = {
        "user_message": user_text,
        "workflow_reply": fallback_reply,
        "rag_context": rag_context,
    }
    try:
        result = await llm_gateway.complete_json(system_prompt, json.dumps(payload, ensure_ascii=False))
    except (httpx.HTTPError, Exception):  # noqa: BLE001
        return None
    choices = result.get("choices") if isinstance(result, dict) else None
    if not isinstance(choices, list) or not choices:
        return None
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        return None
    try:
        parsed = json.loads(content)
        reply = parsed.get("reply")
        return str(reply).strip() if reply else content.strip()
    except json.JSONDecodeError:
        return content.strip()


async def handle_whatsapp_event(payload: dict[str, Any]) -> dict[str, Any]:
    msg = _parse_wacli_message(payload)
    audit_logger.write("whatsapp_event_received", {"message_id": msg["message_id"], "chat_id": msg["chat_id"], "from_me": msg["from_me"]})

    if msg["from_me"]:
        return {"ok": True, "stage": "ignored_from_me", "message": msg}
    if not msg["text"]:
        return {"ok": True, "stage": "ignored_empty", "message": msg}

    triggered, clean_text, trigger = _strip_trigger(msg["text"])
    if not triggered:
        return {"ok": True, "stage": "archived_only", "message": msg, "auto_reply": False}

    rag = await _safe_rag_query(clean_text)
    rag_text = _rag_context(rag)
    chat_request = ChatMessageRequest(
        message=clean_text,
        channel="whatsapp",
        user_id=msg["sender_name"] or msg["sender_id"] or "whatsapp_user",
        metadata={
            "source": "whatsapp_webhook",
            "trigger": trigger,
            "chat_id": msg["chat_id"],
            "message_id": msg["message_id"],
            "sender_id": msg["sender_id"],
            "raw": payload,
            "rag": rag,
            "rag_context": rag_text,
        },
    )
    response = await orchestrator.handle_message(chat_request)
    reply = response.reply
    rag_reply = await _rag_assisted_reply(clean_text, rag_text, reply)
    if rag_reply:
        reply = rag_reply

    send_result = await toolbox_client.call_tool(
        "whatsapp_send_text_confirmed",
        {
            "chat": msg["chat_id"],
            "text": reply,
            "confirmed": True,
            "dry_run": bool(payload.get("dry_run") or payload.get("_dry_run")),
            "confirmed_by": "whatsapp_agent",
        },
    )
    audit_logger.write("whatsapp_agent_replied", {"message_id": msg["message_id"], "chat_id": msg["chat_id"], "send_ok": bool(send_result.get("ok"))})
    return {
        "ok": bool(send_result.get("ok")),
        "stage": "agent_replied",
        "message": msg,
        "clean_text": clean_text,
        "rag": rag,
        "chat_response": response.model_dump(),
        "reply": reply,
        "send_result": send_result,
    }
