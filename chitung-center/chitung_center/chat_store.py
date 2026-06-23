from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from chitung_center.config import settings


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False)


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


class ChatStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or (settings.chitung_data_dir / "chitung_center.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    session_id TEXT PRIMARY KEY,
                    title TEXT,
                    channel TEXT,
                    user_id TEXT,
                    route TEXT,
                    module TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    message_count INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS chat_messages (
                    message_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    status TEXT,
                    intent_json TEXT NOT NULL DEFAULT '{}',
                    tool_results_json TEXT NOT NULL DEFAULT '[]',
                    cards_json TEXT NOT NULL DEFAULT '[]',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    audit_id TEXT,
                    workflow_run_id TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES chat_sessions(session_id)
                );

                CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated
                    ON chat_sessions(updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created
                    ON chat_messages(session_id, created_at);
                """
            )

    def ensure_session(
        self,
        *,
        session_id: str | None,
        channel: str,
        user_id: str,
        metadata: dict[str, Any] | None = None,
        title_source: str = "",
    ) -> dict[str, Any]:
        self.ensure_schema()
        metadata = metadata or {}
        route = str(metadata.get("route") or "")
        module = str(metadata.get("module") or "")
        now = _now()
        with self._connect() as conn:
            if session_id:
                row = conn.execute(
                    "SELECT * FROM chat_sessions WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
                if row:
                    conn.execute(
                        """
                        UPDATE chat_sessions
                        SET channel = ?, user_id = ?, route = COALESCE(NULLIF(?, ''), route),
                            module = COALESCE(NULLIF(?, ''), module),
                            metadata_json = ?, updated_at = ?
                        WHERE session_id = ?
                        """,
                        (channel, user_id, route, module, _json(metadata), now, session_id),
                    )
                    return self._session_row_to_dict(row)

            new_id = session_id or f"chat_{uuid.uuid4().hex}"
            title = _title_from_message(title_source)
            conn.execute(
                """
                INSERT INTO chat_sessions
                (session_id, title, channel, user_id, route, module, metadata_json, created_at, updated_at, message_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (new_id, title, channel, user_id, route, module, _json(metadata), now, now),
            )
        return self.get_session(new_id)

    def get_session(self, session_id: str) -> dict[str, Any]:
        self.ensure_schema()
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM chat_sessions WHERE session_id = ?", (session_id,)).fetchone()
        if not row:
            raise KeyError(session_id)
        return self._session_row_to_dict(row)

    def append_message(
        self,
        session_id: str,
        *,
        role: str,
        content: str,
        status: str | None = None,
        intent: dict[str, Any] | None = None,
        tool_results: list[dict[str, Any]] | None = None,
        cards: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
        audit_id: str | None = None,
        workflow_run_id: str | None = None,
    ) -> dict[str, Any]:
        self.ensure_schema()
        message_id = f"msg_{uuid.uuid4().hex}"
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO chat_messages
                (message_id, session_id, role, content, status, intent_json, tool_results_json,
                 cards_json, metadata_json, audit_id, workflow_run_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    session_id,
                    role,
                    content,
                    status,
                    _json(intent or {}),
                    _json(tool_results or []),
                    _json(cards or []),
                    _json(metadata or {}),
                    audit_id,
                    workflow_run_id,
                    now,
                ),
            )
            conn.execute(
                """
                UPDATE chat_sessions
                SET message_count = message_count + 1, updated_at = ?
                WHERE session_id = ?
                """,
                (now, session_id),
            )
        return self._message_dict(
            {
                "message_id": message_id,
                "session_id": session_id,
                "role": role,
                "content": content,
                "status": status,
                "intent_json": _json(intent or {}),
                "tool_results_json": _json(tool_results or []),
                "cards_json": _json(cards or []),
                "metadata_json": _json(metadata or {}),
                "audit_id": audit_id,
                "workflow_run_id": workflow_run_id,
                "created_at": now,
            }
        )

    def get_history(self, session_id: str | None = None, *, limit: int = 100) -> dict[str, Any]:
        self.ensure_schema()
        with self._connect() as conn:
            if not session_id:
                row = conn.execute("SELECT * FROM chat_sessions ORDER BY updated_at DESC LIMIT 1").fetchone()
                if not row:
                    return {"session": None, "messages": []}
                session_id = str(row["session_id"])
                session = self._session_row_to_dict(row)
            else:
                row = conn.execute("SELECT * FROM chat_sessions WHERE session_id = ?", (session_id,)).fetchone()
                if not row:
                    return {"session": None, "messages": []}
                session = self._session_row_to_dict(row)

            rows = conn.execute(
                """
                SELECT * FROM chat_messages
                WHERE session_id = ?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (session_id, max(1, min(limit, 500))),
            ).fetchall()
        return {"session": session, "messages": [self._message_row_to_dict(row) for row in rows]}

    def list_sessions(self, *, limit: int = 20) -> dict[str, Any]:
        self.ensure_schema()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM chat_sessions ORDER BY updated_at DESC LIMIT ?",
                (max(1, min(limit, 100)),),
            ).fetchall()
        return {"items": [self._session_row_to_dict(row) for row in rows]}

    def list_messages_since(self, since_iso: str, *, limit: int = 500) -> list[dict[str, Any]]:
        self.ensure_schema()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM chat_messages
                WHERE created_at >= ?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (since_iso, max(1, min(limit, 2000))),
            ).fetchall()
        return [self._message_row_to_dict(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _session_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "session_id": row["session_id"],
            "title": row["title"],
            "channel": row["channel"],
            "user_id": row["user_id"],
            "route": row["route"],
            "module": row["module"],
            "metadata": _json_loads(row["metadata_json"], {}),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "message_count": row["message_count"],
        }

    @staticmethod
    def _message_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        return ChatStore._message_dict(dict(row))

    @staticmethod
    def _message_dict(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "message_id": row["message_id"],
            "session_id": row["session_id"],
            "role": row["role"],
            "content": row["content"],
            "status": row.get("status"),
            "intent": _json_loads(row.get("intent_json"), {}),
            "tool_results": _json_loads(row.get("tool_results_json"), []),
            "cards": _json_loads(row.get("cards_json"), []),
            "metadata": _json_loads(row.get("metadata_json"), {}),
            "audit_id": row.get("audit_id"),
            "workflow_run_id": row.get("workflow_run_id"),
            "created_at": row["created_at"],
        }


def _title_from_message(message: str) -> str:
    cleaned = " ".join(message.strip().split())
    if not cleaned:
        return "新对话"
    return cleaned[:40]


chat_store = ChatStore()
