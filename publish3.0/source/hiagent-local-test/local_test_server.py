"""
赤瞳灵讯 · HiAgent 本地连通性测试服务

用途：在本机起一个简单 HTTP API，验证 HiAgent（或 curl）能否访问并拿到数据。

启动：
  cd hiagent-local-test
  pip install -r requirements.txt
  python local_test_server.py

本机自测：
  http://127.0.0.1:8787/health
  http://127.0.0.1:8787/api/ping
  http://127.0.0.1:8787/api/messages/search?q=test&limit=5

云端 HiAgent 访问本机需内网穿透，例如：
  cloudflared tunnel --url http://127.0.0.1:8787
  或 ngrok http 8787
然后把公网 HTTPS 地址配到 HiAgent 的 OpenAPI / HTTP 工具里。
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

HOST = os.environ.get("HIAGENT_TEST_HOST", "0.0.0.0")
PORT = int(os.environ.get("HIAGENT_TEST_PORT", "8787"))
API_KEY = os.environ.get("HIAGENT_TEST_API_KEY", "")  # 空=不校验；设置后请求头 X-Api-Key 需一致

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
UPLOAD_LOG = LOG_DIR / "uploads.jsonl"
ACCESS_LOG = LOG_DIR / "access.jsonl"

app = FastAPI(
    title="ChitongLingxun Local Test API",
    description="本地连通性测试 · 非生产 MCP 服务",
    version="0.1.0",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _check_api_key(x_api_key: str | None) -> None:
    if API_KEY and (not x_api_key or x_api_key != API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing X-Api-Key")


def _find_wacli_db() -> Path | None:
    env = os.environ.get("WACLI_DB_PATH")
    if env:
        p = Path(env)
        if p.is_file():
            return p

    here = Path(__file__).resolve().parent
    candidates = [
        here.parent / "publish11" / "runtime" / "data" / "wacli.db",
        here.parent / "publish10" / "runtime" / "data" / "wacli.db",
        here.parent.parent / "source" / "publish11" / "runtime" / "data" / "wacli.db",
        Path.home() / ".wacli" / "wacli.db",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def _query_messages(db: Path, q: str, limit: int) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 50))
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        sql = """
            SELECT
                m.msg_id,
                m.chat_jid,
                COALESCE(m.chat_name, '') AS chat_name,
                COALESCE(m.sender_name, '') AS sender_name,
                datetime(m.ts, 'unixepoch', 'localtime') AS message_time,
                COALESCE(NULLIF(TRIM(m.display_text), ''), NULLIF(TRIM(m.text), ''), '') AS text,
                COALESCE(m.media_type, '') AS media_type
            FROM messages m
            WHERE m.revoked = 0 AND m.deleted_for_me = 0
        """
        params: list[Any] = []
        if q.strip():
            sql += """
              AND (
                    COALESCE(m.text, '') LIKE ?
                 OR COALESCE(m.display_text, '') LIKE ?
                 OR COALESCE(m.sender_name, '') LIKE ?
                 OR COALESCE(m.chat_name, '') LIKE ?
              )
            """
            like = f"%{q.strip()}%"
            params.extend([like, like, like, like])
        sql += " ORDER BY m.ts DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.middleware("http")
async def log_access(request: Request, call_next):
    response = await call_next(request)
    _append_jsonl(
        ACCESS_LOG,
        {
            "time": _now_iso(),
            "method": request.method,
            "path": str(request.url.path),
            "query": str(request.url.query),
            "client": request.client.host if request.client else None,
            "status": response.status_code,
        },
    )
    return response


@app.get("/health")
def health():
    db = _find_wacli_db()
    return {
        "ok": True,
        "time": _now_iso(),
        "service": "chitong-local-test",
        "wacli_db": str(db) if db else None,
        "wacli_db_exists": db is not None,
        "api_key_required": bool(API_KEY),
    }


@app.get("/api/ping")
def ping(x_api_key: str | None = Header(default=None, alias="X-Api-Key")):
    _check_api_key(x_api_key)
    return {
        "message": "hello from local ChitongLingxun test server",
        "time": _now_iso(),
        "python": sys.version.split()[0],
    }


@app.get("/api/db/status")
def db_status(x_api_key: str | None = Header(default=None, alias="X-Api-Key")):
    _check_api_key(x_api_key)
    db = _find_wacli_db()
    if not db:
        return {
            "found": False,
            "hint": "先在本机完成登录/sync，或设置环境变量 WACLI_DB_PATH 指向 wacli.db",
        }
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        msg_count = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE revoked = 0 AND deleted_for_me = 0"
        ).fetchone()[0]
        chat_count = conn.execute("SELECT COUNT(*) FROM chats").fetchone()[0]
    finally:
        conn.close()
    return {
        "found": True,
        "path": str(db),
        "messages": msg_count,
        "chats": chat_count,
    }


@app.get("/api/messages/search")
def search_messages(
    q: str = Query(default="", description="关键词，留空则返回最近消息"),
    limit: int = Query(default=10, ge=1, le=50),
    x_api_key: str | None = Header(default=None, alias="X-Api-Key"),
):
    _check_api_key(x_api_key)
    db = _find_wacli_db()
    if not db:
        raise HTTPException(
            status_code=404,
            detail="未找到 wacli.db。请先运行赤瞳灵讯并完成 sync，或设置 WACLI_DB_PATH",
        )
    try:
        rows = _query_messages(db, q, limit)
    except sqlite3.Error as ex:
        raise HTTPException(status_code=500, detail=f"SQLite 查询失败: {ex}") from ex
    return {
        "query": q,
        "limit": limit,
        "count": len(rows),
        "db": str(db),
        "items": rows,
    }


class UploadPayload(BaseModel):
    source: str = Field(default="hiagent-test", description="调用方标识")
    query: str = Field(default="")
    items: list[dict[str, Any]] = Field(default_factory=list)
    note: str = Field(default="")


@app.post("/api/upload")
def upload_results(
    body: UploadPayload,
    x_api_key: str | None = Header(default=None, alias="X-Api-Key"),
):
    """模拟「检索结果上传」：写入 logs/uploads.jsonl，便于确认 HiAgent 是否 POST 成功。"""
    _check_api_key(x_api_key)
    record = {
        "time": _now_iso(),
        "source": body.source,
        "query": body.query,
        "item_count": len(body.items),
        "note": body.note,
        "items_preview": body.items[:3],
    }
    _append_jsonl(UPLOAD_LOG, record)
    return {
        "ok": True,
        "received": len(body.items),
        "log_file": str(UPLOAD_LOG),
        "task_id": f"local-test-{int(datetime.now().timestamp())}",
    }


@app.get("/")
def root():
    return JSONResponse(
        {
            "docs": "/docs",
            "health": "/health",
            "ping": "/api/ping",
            "search": "/api/messages/search?q=hello&limit=5",
            "upload": "POST /api/upload",
        }
    )


if __name__ == "__main__":
    import uvicorn

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    db = _find_wacli_db()
    print("=" * 60)
    print("ChitongLingxun Local Test API")
    print(f"  Listen: http://{HOST}:{PORT}")
    print(f"  Docs:   http://127.0.0.1:{PORT}/docs")
    print(f"  Health: http://127.0.0.1:{PORT}/health")
    print(f"  Auth:   {'X-Api-Key required' if API_KEY else 'disabled (set HIAGENT_TEST_API_KEY to enable)'}")
    print(f"  wacli.db: {db or '(not found)'}")
    print("=" * 60)
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
