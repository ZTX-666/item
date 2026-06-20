from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from ..config import settings
from ..models import ToolResult


ROLE_PERMISSIONS = {
    "admin": ["*"],
    "safety_officer": ["read", "create_case", "update_case", "confirm_send", "close_case", "generate_document"],
    "supervisor": ["read", "update_case", "confirm_send"],
    "viewer": ["read"],
}


class ToolAuditRecordRequest(BaseModel):
    tool_name: str
    user_id: str | None = None
    channel: str | None = None
    input_summary: dict[str, Any] = Field(default_factory=dict)
    output_summary: dict[str, Any] = Field(default_factory=dict)
    status: str = "ok"


class LlmAuditRecordRequest(BaseModel):
    provider: str | None = None
    model: str | None = None
    user_id: str | None = None
    prompt_summary: dict[str, Any] = Field(default_factory=dict)
    response_summary: dict[str, Any] = Field(default_factory=dict)
    sanitized: bool = True
    status: str = "ok"


class AuditLogQueryRequest(BaseModel):
    event_type: str | None = None
    user_id: str | None = None
    limit: int = Field(default=100, ge=1, le=1000)


class UserRoleManageRequest(BaseModel):
    user_id: str
    role: str
    display_name: str | None = None


class ActionPermissionCheckRequest(BaseModel):
    user_id: str
    action: str
    default_role: str = "viewer"


def record_tool_audit(req: ToolAuditRecordRequest) -> ToolResult:
    audit_id = _insert_audit("tool", req.user_id, req.channel, req.model_dump())
    return ToolResult(ok=True, tool="record_tool_audit", summary=f"Recorded tool audit {audit_id}.", data={"audit_id": audit_id})


def record_llm_audit(req: LlmAuditRecordRequest) -> ToolResult:
    audit_id = _insert_audit("llm", req.user_id, None, req.model_dump())
    return ToolResult(ok=True, tool="record_llm_audit", summary=f"Recorded LLM audit {audit_id}.", data={"audit_id": audit_id})


def list_audit_logs(req: AuditLogQueryRequest) -> ToolResult:
    _ensure_audit_schema()
    where = []
    params: list[Any] = []
    if req.event_type:
        where.append("event_type = ?")
        params.append(req.event_type)
    if req.user_id:
        where.append("user_id = ?")
        params.append(req.user_id)
    where_sql = f" WHERE {' AND '.join(where)}" if where else ""
    with _connect() as conn:
        rows = conn.execute(f"SELECT * FROM audit_logs{where_sql} ORDER BY id DESC LIMIT ?", (*params, req.limit)).fetchall()
    return ToolResult(ok=True, tool="list_audit_logs", summary=f"Returned {len(rows)} audit logs.", data={"items": [_row(row) for row in rows]})


def manage_user_roles(req: UserRoleManageRequest) -> ToolResult:
    _ensure_audit_schema()
    if req.role not in ROLE_PERMISSIONS:
        raise ValueError(f"Unsupported role: {req.role}")
    now = _now()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO user_roles (user_id, role, display_name, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET role = excluded.role, display_name = excluded.display_name, updated_at = excluded.updated_at
            """,
            (req.user_id, req.role, req.display_name, now, now),
        )
    return ToolResult(ok=True, tool="manage_user_roles", summary=f"Set {req.user_id} role to {req.role}.", data=req.model_dump())


def check_action_permission(req: ActionPermissionCheckRequest) -> ToolResult:
    _ensure_audit_schema()
    with _connect() as conn:
        row = conn.execute("SELECT role FROM user_roles WHERE user_id = ?", (req.user_id,)).fetchone()
    role = row["role"] if row else req.default_role
    permissions = ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS["viewer"])
    allowed = "*" in permissions or req.action in permissions or (req.action.startswith("read") and "read" in permissions)
    return ToolResult(
        ok=True,
        tool="check_action_permission",
        summary="Permission checked.",
        data={"user_id": req.user_id, "role": role, "action": req.action, "allowed": allowed, "permissions": permissions},
    )


def _insert_audit(event_type: str, user_id: str | None, channel: str | None, payload: dict[str, Any]) -> int:
    _ensure_audit_schema()
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO audit_logs (event_type, user_id, channel, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (event_type, user_id, channel, json.dumps(payload, ensure_ascii=False, sort_keys=True), _now()),
        )
        return int(cursor.lastrowid)


def _ensure_audit_schema() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                user_id TEXT,
                channel TEXT,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS user_roles (
                user_id TEXT PRIMARY KEY,
                role TEXT NOT NULL,
                display_name TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_audit_logs_event_user ON audit_logs(event_type, user_id);
            """
        )


def _row(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def _connect() -> sqlite3.Connection:
    path = settings.safety_database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
