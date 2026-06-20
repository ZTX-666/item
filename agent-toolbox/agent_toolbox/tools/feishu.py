from __future__ import annotations

import base64
import hashlib
import hmac
import json
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field
import requests

from ..config import settings
from ..models import ToolResult
from ..tasks import new_task_id, record_task_event


class FeishuNotifyRequest(BaseModel):
    text: str = Field(min_length=1)


class FeishuTenantTokenRequest(BaseModel):
    force_refresh: bool = False


class FeishuSendMessageRequest(BaseModel):
    receive_id: str
    receive_id_type: str = "chat_id"
    text: str


class FeishuSendCardRequest(BaseModel):
    receive_id: str
    receive_id_type: str = "chat_id"
    card: dict[str, Any]


class FeishuSafetyCardRequest(BaseModel):
    receive_id: str | None = None
    receive_id_type: str = "chat_id"
    title: str
    summary: str
    risk_level: str = "medium"
    actions: list[dict[str, Any]] = Field(default_factory=list)
    source_case_id: int | None = None
    source_event_id: int | None = None
    send: bool = False


class FeishuEventCallbackRequest(BaseModel):
    payload: dict[str, Any]


class FeishuChatListRequest(BaseModel):
    page_size: int = Field(default=20, ge=1, le=100)
    page_token: str | None = None


class FeishuEventArchiveRequest(BaseModel):
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    status: str = "received"


class FeishuEventToPlatformEventRequest(BaseModel):
    event_payload: dict[str, Any]
    default_risk_level: str = "medium"


def _sign(secret: str, timestamp: str) -> str:
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def _decrypt_feishu_event(encrypt_key: str, encrypt_b64: str) -> dict[str, Any]:
    """Decrypt a Feishu event-subscription `encrypt` payload (AES-256-CBC).

    Feishu derives the AES key as SHA256(encrypt_key); the base64-decoded blob
    is `IV(16 bytes) || ciphertext`, PKCS7-padded. Returns the decoded JSON dict.
    """
    from Crypto.Cipher import AES

    key = hashlib.sha256(encrypt_key.encode("utf-8")).digest()
    blob = base64.b64decode(encrypt_b64)
    iv, ciphertext = blob[:16], blob[16:]
    decrypted = AES.new(key, AES.MODE_CBC, iv).decrypt(ciphertext)
    pad = decrypted[-1]
    if 1 <= pad <= 16:
        decrypted = decrypted[:-pad]
    return json.loads(decrypted.decode("utf-8"))


def notify_feishu(req: FeishuNotifyRequest) -> ToolResult:
    task_id = new_task_id("feishu")
    if not settings.feishu_webhook_url:
        return ToolResult(
            ok=False,
            tool="notify_feishu",
            task_id=task_id,
            summary="飞书 webhook 未配置。",
            error="Set FEISHU_WEBHOOK_URL in .env",
        )

    payload: dict[str, object] = {
        "msg_type": "text",
        "content": {"text": req.text},
    }
    if settings.feishu_webhook_secret:
        timestamp = str(int(time.time()))
        payload["timestamp"] = timestamp
        payload["sign"] = _sign(settings.feishu_webhook_secret, timestamp)

    record_task_event(task_id, {"tool": "notify_feishu", "status": "running"})
    try:
        resp = requests.post(settings.feishu_webhook_url, json=payload, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        record_task_event(task_id, {"tool": "notify_feishu", "status": "failed", "error": str(exc)})
        return ToolResult(
            ok=False,
            tool="notify_feishu",
            task_id=task_id,
            summary="飞书消息发送失败。",
            error=str(exc),
        )

    record_task_event(task_id, {"tool": "notify_feishu", "status": "done"})
    return ToolResult(
        ok=True,
        tool="notify_feishu",
        task_id=task_id,
        summary="飞书消息已发送。",
        data={"response": resp.text},
    )


def feishu_get_tenant_access_token(req: FeishuTenantTokenRequest) -> ToolResult:
    del req
    if not settings.feishu_app_id or not settings.feishu_app_secret:
        return ToolResult(
            ok=False,
            tool="feishu_get_tenant_access_token",
            summary="飞书 App 凭证未配置。",
            error="Set FEISHU_APP_ID and FEISHU_APP_SECRET in .env",
        )
    resp = requests.post(
        f"{settings.feishu_api_base_url.rstrip('/')}/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": settings.feishu_app_id, "app_secret": settings.feishu_app_secret},
        timeout=15,
    )
    try:
        data = resp.json()
    except ValueError:
        data = {"raw": resp.text}
    ok = resp.ok and data.get("code") in {0, None} and bool(data.get("tenant_access_token"))
    return ToolResult(
        ok=ok,
        tool="feishu_get_tenant_access_token",
        summary="获取飞书 tenant_access_token 成功。" if ok else "获取飞书 tenant_access_token 失败。",
        data={"expires": data.get("expire"), "token_preview": _mask(data.get("tenant_access_token")), "response": _without_secret(data)},
        error=None if ok else str(data),
    )


def feishu_send_text_message(req: FeishuSendMessageRequest) -> ToolResult:
    payload = {"receive_id": req.receive_id, "msg_type": "text", "content": json.dumps({"text": req.text}, ensure_ascii=False)}
    return _send_openapi_message("feishu_send_text_message", req.receive_id_type, payload)


def feishu_send_interactive_card(req: FeishuSendCardRequest) -> ToolResult:
    payload = {"receive_id": req.receive_id, "msg_type": "interactive", "content": json.dumps(req.card, ensure_ascii=False)}
    return _send_openapi_message("feishu_send_interactive_card", req.receive_id_type, payload)


def feishu_build_safety_review_card(req: FeishuSafetyCardRequest) -> ToolResult:
    card = _safety_card(req)
    if req.send:
        if not req.receive_id:
            return ToolResult(ok=False, tool="feishu_build_safety_review_card", summary="发送卡片需要 receive_id。", error="receive_id required when send=true")
        sent = feishu_send_interactive_card(FeishuSendCardRequest(receive_id=req.receive_id, receive_id_type=req.receive_id_type, card=card))
        sent.data["card"] = card
        return sent
    return ToolResult(ok=True, tool="feishu_build_safety_review_card", summary="已生成飞书安全审核卡片。", data={"card": card, "requires_send": True})


def feishu_handle_event_callback(req: FeishuEventCallbackRequest) -> ToolResult:
    payload = req.payload
    if "encrypt" in payload:
        if not settings.feishu_encrypt_key:
            return ToolResult(
                ok=False,
                tool="feishu_handle_event_callback",
                summary="收到加密飞书事件，但未配置 FEISHU_ENCRYPT_KEY。",
                error="Set FEISHU_ENCRYPT_KEY in .env to decrypt events.",
                data={"encrypted": True},
            )
        try:
            payload = _decrypt_feishu_event(settings.feishu_encrypt_key, payload["encrypt"])
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                ok=False,
                tool="feishu_handle_event_callback",
                summary="飞书加密事件解密失败，请检查 Encrypt Key 是否正确。",
                error=f"decrypt_failed: {exc}",
                data={"encrypted": True},
            )
    token = payload.get("token") or payload.get("header", {}).get("token")
    if settings.feishu_verification_token and token and token != settings.feishu_verification_token:
        return ToolResult(ok=False, tool="feishu_handle_event_callback", summary="飞书事件 token 校验失败。", error="invalid verification token")
    if payload.get("type") == "url_verification" and payload.get("challenge"):
        return ToolResult(ok=True, tool="feishu_handle_event_callback", summary="飞书 URL 验证 challenge。", data={"challenge": payload["challenge"], "response": {"challenge": payload["challenge"]}, "payload": payload})
    event_type = payload.get("header", {}).get("event_type") or payload.get("event", {}).get("type") or payload.get("type") or "unknown"
    archived = feishu_archive_event(FeishuEventArchiveRequest(event_type=event_type, payload=payload))
    return ToolResult(ok=True, tool="feishu_handle_event_callback", summary=f"已处理飞书事件 {event_type}。", data={"event_type": event_type, "archive": archived.data, "payload": payload})


def feishu_list_chats(req: FeishuChatListRequest) -> ToolResult:
    token = _tenant_token()
    if not token:
        return ToolResult(ok=False, tool="feishu_list_chats", summary="飞书 App 凭证未配置，无法列出群。", error="missing tenant_access_token")
    params: dict[str, Any] = {"page_size": req.page_size}
    if req.page_token:
        params["page_token"] = req.page_token
    resp = requests.get(
        f"{settings.feishu_api_base_url.rstrip('/')}/open-apis/im/v1/chats",
        headers=_auth_headers(token),
        params=params,
        timeout=15,
    )
    return _openapi_result("feishu_list_chats", resp)


def feishu_archive_event(req: FeishuEventArchiveRequest) -> ToolResult:
    _ensure_feishu_schema()
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO feishu_events (event_type, status, payload_json, created_at) VALUES (?, ?, ?, ?)",
            (req.event_type, req.status, json.dumps(req.payload, ensure_ascii=False, sort_keys=True), _now()),
        )
    return ToolResult(ok=True, tool="feishu_archive_event", summary=f"已归档飞书事件 {cursor.lastrowid}。", data={"event_id": int(cursor.lastrowid)})


def feishu_event_to_platform_event(req: FeishuEventToPlatformEventRequest) -> ToolResult:
    event = req.event_payload.get("event") or req.event_payload
    message = event.get("message") or {}
    content = message.get("content") or event.get("content") or ""
    try:
        content_obj = json.loads(content) if isinstance(content, str) else content
    except json.JSONDecodeError:
        content_obj = {"text": str(content)}
    text = content_obj.get("text") if isinstance(content_obj, dict) else str(content_obj)
    platform_event = {
        "event_type": "feishu_message",
        "source_type": "feishu",
        "source_id": message.get("message_id") or event.get("event_id"),
        "title": (text or "飞书消息")[:80],
        "summary": text,
        "risk_level": req.default_risk_level,
        "payload": req.event_payload,
    }
    return ToolResult(ok=True, tool="feishu_event_to_platform_event", summary="已转换为平台事件 payload。", data={"platform_event": platform_event})


def _send_openapi_message(tool: str, receive_id_type: str, payload: dict[str, Any]) -> ToolResult:
    token = _tenant_token()
    if not token:
        return ToolResult(ok=False, tool=tool, summary="飞书 App 凭证未配置，消息未发送。", error="missing tenant_access_token", data={"payload": payload})
    resp = requests.post(
        f"{settings.feishu_api_base_url.rstrip('/')}/open-apis/im/v1/messages",
        headers=_auth_headers(token),
        params={"receive_id_type": receive_id_type},
        json=payload,
        timeout=15,
    )
    result = _openapi_result(tool, resp)
    result.data["request_payload"] = payload
    return result


def _tenant_token() -> str | None:
    if not settings.feishu_app_id or not settings.feishu_app_secret:
        return None
    resp = requests.post(
        f"{settings.feishu_api_base_url.rstrip('/')}/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": settings.feishu_app_id, "app_secret": settings.feishu_app_secret},
        timeout=15,
    )
    try:
        data = resp.json()
    except ValueError:
        return None
    return data.get("tenant_access_token")


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}


def _openapi_result(tool: str, resp: requests.Response) -> ToolResult:
    try:
        data = resp.json()
    except ValueError:
        data = {"raw": resp.text}
    ok = resp.ok and data.get("code") in {0, None}
    return ToolResult(ok=ok, tool=tool, summary="飞书 OpenAPI 调用成功。" if ok else "飞书 OpenAPI 调用失败。", data={"status_code": resp.status_code, "response": data}, error=None if ok else str(data))


def _safety_card(req: FeishuSafetyCardRequest) -> dict[str, Any]:
    color = {"critical": "red", "high": "red", "medium": "orange", "low": "blue"}.get(req.risk_level, "orange")
    actions = req.actions or [
        {"action_id": "approve", "label": "确认处理", "type": "primary"},
        {"action_id": "reject", "label": "暂不处理", "type": "default"},
    ]
    return {
        "config": {"wide_screen_mode": True},
        "header": {"template": color, "title": {"tag": "plain_text", "content": req.title}},
        "elements": [
            {"tag": "markdown", "content": f"**风险等级：** {req.risk_level}\n\n{req.summary}"},
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": action.get("label", action.get("action_id", "操作"))},
                        "type": action.get("type", "default"),
                        "value": {
                            "action_id": action.get("action_id"),
                            "source_case_id": req.source_case_id,
                            "source_event_id": req.source_event_id,
                        },
                    }
                    for action in actions
                ],
            },
        ],
    }


def _ensure_feishu_schema() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS feishu_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT,
                status TEXT,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            """
        )


def _connect() -> sqlite3.Connection:
    path = settings.safety_database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _mask(value: str | None) -> str | None:
    if not value:
        return None
    return value[:6] + "***" + value[-4:]


def _without_secret(data: dict[str, Any]) -> dict[str, Any]:
    safe = dict(data)
    if "tenant_access_token" in safe:
        safe["tenant_access_token"] = _mask(safe["tenant_access_token"])
    return safe


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
