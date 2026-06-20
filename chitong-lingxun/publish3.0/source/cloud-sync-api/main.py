"""
赤瞳灵讯 · 云端同步接收 API（部署在云服务器）

环境变量:
  SYNC_API_TOKEN     必填，与赤瞳 runtime/cloud-sync.json 中 SyncToken 一致
  MYSQL_HOST         默认 127.0.0.1
  MYSQL_PORT         默认 3306
  MYSQL_USER         默认 sync_writer
  MYSQL_PASSWORD
  MYSQL_DATABASE     默认 wacli_sync
  MEDIA_STORAGE_DIR  默认 ./media_storage

启动:
  pip install -r requirements.txt
  export SYNC_API_TOKEN=your-secret-token
  uvicorn main:app --host 0.0.0.0 --port 8090
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

import pymysql
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field

APP_TOKEN = os.environ.get("SYNC_API_TOKEN", "")
MEDIA_DIR = Path(os.environ.get("MEDIA_STORAGE_DIR", "media_storage"))
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Chitong Cloud Sync API", version="1.0.0")


def db_conn():
    return pymysql.connect(
        host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get("MYSQL_USER", "sync_writer"),
        password=os.environ.get("MYSQL_PASSWORD", ""),
        database=os.environ.get("MYSQL_DATABASE", "wacli_sync"),
        charset="utf8mb4",
        autocommit=True,
    )


def verify_token(authorization: str | None = Header(None), x_api_key: str | None = Header(None)):
    if not APP_TOKEN:
        raise HTTPException(500, "SYNC_API_TOKEN not configured on server")
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    elif x_api_key:
        token = x_api_key.strip()
    if token != APP_TOKEN:
        raise HTTPException(401, "Invalid token")


class MessageItem(BaseModel):
    msg_id: str
    chat_jid: str
    chat_name: str = ""
    sender_name: str = ""
    sender_jid: str = ""
    ts: int
    text: str = ""
    display_text: str = ""
    media_type: str = ""
    local_path: str = ""
    filename: str = ""
    revoked: int = 0
    deleted_for_me: int = 0


class MessagesPayload(BaseModel):
    owner_id: str
    tier: int = 0
    items: list[MessageItem] = Field(default_factory=list)


@app.get("/sync/v1/health")
def health():
    err: str | None = None
    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        db_ok = True
    except Exception as ex:
        db_ok = False
        err = str(ex)
    return {"ok": True, "service": "chitong-cloud-sync", "database": db_ok, "error": err}


@app.post("/sync/v1/messages")
def sync_messages(payload: MessagesPayload, _: None = Depends(verify_token)):
    if not payload.owner_id:
        raise HTTPException(400, "owner_id required")
    accepted = 0
    sql = """
        INSERT INTO sync_messages (
            owner_id, msg_id, chat_jid, chat_name, sender_name, sender_jid, ts,
            text, display_text, media_type, local_path, filename, revoked, deleted_for_me
        ) VALUES (
            %(owner_id)s, %(msg_id)s, %(chat_jid)s, %(chat_name)s, %(sender_name)s, %(sender_jid)s, %(ts)s,
            %(text)s, %(display_text)s, %(media_type)s, %(local_path)s, %(filename)s, %(revoked)s, %(deleted_for_me)s
        )
        ON DUPLICATE KEY UPDATE
            chat_name=VALUES(chat_name), sender_name=VALUES(sender_name), sender_jid=VALUES(sender_jid),
            ts=VALUES(ts), text=VALUES(text), display_text=VALUES(display_text),
            media_type=VALUES(media_type), local_path=VALUES(local_path), filename=VALUES(filename),
            revoked=VALUES(revoked), deleted_for_me=VALUES(deleted_for_me)
    """
    with db_conn() as conn:
        with conn.cursor() as cur:
            for it in payload.items:
                row = it.model_dump()
                row["owner_id"] = payload.owner_id
                cur.execute(sql, row)
                accepted += 1
    return {"ok": True, "accepted": accepted, "skipped": 0}


@app.post("/sync/v1/media")
async def sync_media(
    owner_id: str = Form(...),
    msg_id: str = Form(...),
    chat_jid: str = Form(""),
    kind: str = Form("full"),
    file: UploadFile = File(...),
    _: None = Depends(verify_token),
):
    if kind not in ("thumbnail", "full"):
        raise HTTPException(400, "kind must be thumbnail or full")
    ext = Path(file.filename or "bin").suffix or ".bin"
    object_key = f"{owner_id}/{kind}/{msg_id}{ext}"
    dest = MEDIA_DIR / object_key
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = await file.read()
    dest.write_bytes(data)
    mime = file.content_type or "application/octet-stream"
    sql = """
        INSERT INTO sync_media (owner_id, msg_id, chat_jid, kind, object_key, size_bytes, mime_type)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            object_key=VALUES(object_key), size_bytes=VALUES(size_bytes),
            mime_type=VALUES(mime_type), uploaded_at=CURRENT_TIMESTAMP
    """
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (owner_id, msg_id, chat_jid, kind, object_key, len(data), mime))
    return {"ok": True, "object_key": object_key, "size": len(data)}
