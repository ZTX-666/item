from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from ..config import settings
from ..models import ToolResult


class SafetyCaseCreateRequest(BaseModel):
    description: str
    scene: str | None = None
    risk_level: str = "medium"
    area: str | None = None
    contractor: str | None = None
    source_type: str = "manual"
    source_id: str | None = None
    recommended_action: str | None = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class SafetyCaseStatusRequest(BaseModel):
    case_id: int
    status: str
    notes: str | None = None


class SafetyCaseAssignRequest(BaseModel):
    case_id: int
    assignee: str | None = None
    contractor: str | None = None
    due_date: str | None = None
    priority: str | None = None


class CaseEvidenceRequest(BaseModel):
    case_id: int
    path: str
    kind: str = "file"
    source_type: str = "manual"
    source_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CaseDraftRequest(BaseModel):
    case_id: int
    language: str = "zh-HK"
    tone: str = "formal"


class CaseCloseReviewRequest(BaseModel):
    case_id: int
    review_notes: str
    reviewer: str | None = None
    evidence_paths: list[str] = Field(default_factory=list)


def create_safety_case(req: SafetyCaseCreateRequest) -> ToolResult:
    _ensure_case_schema()
    now = _now()
    key = _case_key(req)
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO safety_cases (
                case_key, status, source_type, source_id, scene, risk_level, area, contractor,
                description, recommended_action, template_ids_json, first_seen_at, last_seen_at,
                evidence_json, created_at, updated_at
            )
            VALUES (?, 'candidate', ?, ?, ?, ?, ?, ?, ?, ?, '[]', ?, ?, ?, ?, ?)
            ON CONFLICT(case_key) DO UPDATE SET
                last_seen_at = excluded.last_seen_at,
                updated_at = excluded.updated_at
            RETURNING id
            """,
            (
                key,
                req.source_type,
                req.source_id,
                req.scene,
                req.risk_level,
                req.area,
                req.contractor,
                req.description,
                req.recommended_action,
                now,
                now,
                json.dumps(req.evidence, ensure_ascii=False),
                now,
                now,
            ),
        )
        case_id = int(cursor.fetchone()[0])
    return ToolResult(ok=True, tool="create_safety_case", summary=f"Created or reused safety case {case_id}.", data={"case_id": case_id, "case_key": key})


def update_safety_case_status(req: SafetyCaseStatusRequest) -> ToolResult:
    _ensure_case_schema()
    with _connect() as conn:
        conn.execute(
            "UPDATE safety_cases SET status = ?, updated_at = ? WHERE id = ?",
            (req.status, _now(), req.case_id),
        )
        _insert_case_action(conn, req.case_id, "status_update", {"status": req.status, "notes": req.notes})
    return ToolResult(ok=True, tool="update_safety_case_status", summary=f"Updated case {req.case_id} to {req.status}.", data=req.model_dump())


def assign_safety_case(req: SafetyCaseAssignRequest) -> ToolResult:
    _ensure_case_schema()
    payload = req.model_dump()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE safety_cases
            SET contractor = COALESCE(?, contractor), updated_at = ?
            WHERE id = ?
            """,
            (req.contractor, _now(), req.case_id),
        )
        _insert_case_action(conn, req.case_id, "assignment", payload)
    return ToolResult(ok=True, tool="assign_safety_case", summary=f"Assigned case {req.case_id}.", data=payload)


def add_case_evidence(req: CaseEvidenceRequest) -> ToolResult:
    _ensure_case_schema()
    now = _now()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO evidence_files (case_id, source_type, source_id, path, kind, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (req.case_id, req.source_type, req.source_id, req.path, req.kind, now),
        )
        _insert_case_action(conn, req.case_id, "evidence_added", req.model_dump())
    return ToolResult(ok=True, tool="add_case_evidence", summary=f"Added evidence to case {req.case_id}.", data=req.model_dump())


def generate_rectification_notice(req: CaseDraftRequest) -> ToolResult:
    case = _get_case(req.case_id)
    text = _draft_notice(case, notice_type="rectification")
    return ToolResult(
        ok=True,
        tool="generate_rectification_notice",
        summary=f"Drafted rectification notice for case {req.case_id}.",
        data={"case_id": req.case_id, "draft_text": text, "requires_human_confirmation": True},
    )


def generate_warning_letter(req: CaseDraftRequest) -> ToolResult:
    case = _get_case(req.case_id)
    text = _draft_notice(case, notice_type="warning")
    return ToolResult(
        ok=True,
        tool="generate_warning_letter",
        summary=f"Drafted warning letter for case {req.case_id}.",
        data={"case_id": req.case_id, "draft_text": text, "requires_human_confirmation": True},
    )


def close_case_with_review(req: CaseCloseReviewRequest) -> ToolResult:
    _ensure_case_schema()
    with _connect() as conn:
        conn.execute("UPDATE safety_cases SET status = 'closed', updated_at = ? WHERE id = ?", (_now(), req.case_id))
        _insert_case_action(conn, req.case_id, "review_closed", req.model_dump())
    return ToolResult(ok=True, tool="close_case_with_review", summary=f"Closed case {req.case_id} after review.", data=req.model_dump())


def _ensure_case_schema() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS safety_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_key TEXT UNIQUE NOT NULL,
                status TEXT NOT NULL DEFAULT 'candidate',
                source_type TEXT,
                source_id TEXT,
                scene TEXT,
                risk_level TEXT,
                area TEXT,
                contractor TEXT,
                description TEXT,
                recommended_action TEXT,
                template_ids_json TEXT NOT NULL DEFAULT '[]',
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                evidence_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS evidence_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER,
                source_type TEXT,
                source_id TEXT,
                path TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'file',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS case_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_case_actions_case ON case_actions(case_id);
            """
        )


def _insert_case_action(conn: sqlite3.Connection, case_id: int, action_type: str, payload: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO case_actions (case_id, action_type, payload_json, created_at) VALUES (?, ?, ?, ?)",
        (case_id, action_type, json.dumps(payload, ensure_ascii=False, sort_keys=True), _now()),
    )


def _get_case(case_id: int) -> sqlite3.Row:
    _ensure_case_schema()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM safety_cases WHERE id = ?", (case_id,)).fetchone()
    if row is None:
        raise ValueError(f"Safety case not found: {case_id}")
    return row


def _draft_notice(case: sqlite3.Row, notice_type: str) -> str:
    heading = "整改通知草稿" if notice_type == "rectification" else "安全警告信草稿"
    action = case["recommended_action"] or "请立即安排整改，并提交整改前后照片及复查记录。"
    return "\n".join(
        [
            heading,
            "",
            f"事项：{case['description'] or '现场安全隐患'}",
            f"区域：{case['area'] or '待补充'}",
            f"分判商/责任单位：{case['contractor'] or '待补充'}",
            f"风险等级：{case['risk_level'] or 'medium'}",
            f"建议措施：{action}",
            "",
            "请责任单位收到后立即确认，并按安全主任要求完成整改及提交证明资料。",
        ]
    )


def _case_key(req: SafetyCaseCreateRequest) -> str:
    text = "|".join([req.source_type, req.source_id or "", req.scene or "", req.area or "", req.contractor or "", req.description])
    return hashlib.sha256(text.lower().encode("utf-8")).hexdigest()[:24]


def _connect() -> sqlite3.Connection:
    path = settings.safety_database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
