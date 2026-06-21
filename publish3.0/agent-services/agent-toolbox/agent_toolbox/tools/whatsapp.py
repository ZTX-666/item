from __future__ import annotations

from pydantic import BaseModel, Field
import requests

from ..config import settings
from ..models import ToolResult
from ..tasks import new_task_id, record_task_event


class WhatsAppSearchRequest(BaseModel):
    q: str = Field(min_length=1)
    chat: str | None = None
    limit: int = Field(default=20, ge=1, le=200)


class WhatsAppDownloadMediaRequest(BaseModel):
    message_id: str = Field(min_length=10)
    dir: str | None = None


def _base_url() -> str:
    return settings.whatsapp_archive_base_url.rstrip("/")


def search_messages(req: WhatsAppSearchRequest) -> ToolResult:
    task_id = new_task_id("wa_search")
    params = {"q": req.q, "limit": req.limit}
    if req.chat:
        params["chat"] = req.chat

    record_task_event(task_id, {"tool": "whatsapp_search", "status": "running", "query": req.q})
    try:
        resp = requests.get(f"{_base_url()}/api/messages/search", params=params, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        record_task_event(task_id, {"tool": "whatsapp_search", "status": "failed", "error": str(exc)})
        return ToolResult(
            ok=False,
            tool="whatsapp_search",
            task_id=task_id,
            summary="WhatsApp 归档搜索失败，请确认 app-server 已启动。",
            error=str(exc),
        )

    payload = resp.json()
    rows = payload.get("rows", [])
    record_task_event(task_id, {"tool": "whatsapp_search", "status": "done", "count": len(rows)})
    return ToolResult(
        ok=True,
        tool="whatsapp_search",
        task_id=task_id,
        summary=f"WhatsApp 搜索完成，找到 {len(rows)} 条消息。",
        data={"rows": rows, "query": req.q},
    )


def download_media(req: WhatsAppDownloadMediaRequest) -> ToolResult:
    task_id = new_task_id("wa_media")
    body: dict[str, str] = {"messageId": req.message_id}
    if req.dir:
        body["dir"] = req.dir

    record_task_event(task_id, {"tool": "whatsapp_download_media", "status": "running", "message_id": req.message_id})
    try:
        resp = requests.post(f"{_base_url()}/api/media/download", json=body, timeout=120)
        resp.raise_for_status()
    except requests.RequestException as exc:
        record_task_event(task_id, {"tool": "whatsapp_download_media", "status": "failed", "error": str(exc)})
        return ToolResult(
            ok=False,
            tool="whatsapp_download_media",
            task_id=task_id,
            summary="WhatsApp 附件下载失败，请确认 app-server 和 whatscli 可用。",
            error=str(exc),
        )

    payload = resp.json()
    record_task_event(task_id, {"tool": "whatsapp_download_media", "status": "done"})
    return ToolResult(
        ok=True,
        tool="whatsapp_download_media",
        task_id=task_id,
        summary="WhatsApp 附件下载请求已完成。",
        data=payload,
    )
