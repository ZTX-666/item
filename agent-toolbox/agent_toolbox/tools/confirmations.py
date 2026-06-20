from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from ..config import settings
from ..models import ToolResult, ToolSpec


ConfirmationStatus = Literal["pending", "approved", "rejected", "expired", "executed", "failed"]
Decision = Literal["approve", "reject", "expire", "mark_executed", "mark_failed"]
WorkflowStatus = Literal["planned", "running", "pending_confirmation", "succeeded", "failed", "cancelled"]
StepStatus = Literal["planned", "running", "pending_confirmation", "succeeded", "failed", "skipped"]


class WorkflowSchemaInitRequest(BaseModel):
    include_indexes: bool = True


class WorkflowRunCreateRequest(BaseModel):
    workflow_name: str = Field(min_length=1)
    title: str | None = None
    trigger_source: str = "manual"
    trigger_payload: dict[str, Any] = Field(default_factory=dict)
    channel: str = "local_web"
    user_id: str = "local_user"
    status: WorkflowStatus = "planned"
    idempotency_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowStepAppendRequest(BaseModel):
    workflow_run_id: str = Field(min_length=1)
    step_name: str = Field(min_length=1)
    agent_name: str | None = None
    tool_name: str | None = None
    sequence_no: int | None = None
    input_payload: dict[str, Any] = Field(default_factory=dict)
    output_payload: dict[str, Any] = Field(default_factory=dict)
    status: StepStatus = "planned"
    error: str | None = None


class WorkflowStepUpdateRequest(BaseModel):
    workflow_step_id: str = Field(min_length=1)
    status: StepStatus
    output_payload: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class PendingConfirmationCreateRequest(BaseModel):
    action_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    summary: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    risk_level: str = "medium"
    source_channel: str = "local_web"
    source_user_id: str | None = None
    source_chat_id: str | None = None
    source_message_id: str | None = None
    workflow_run_id: str | None = None
    workflow_step_id: str | None = None
    expires_at: str | None = None
    idempotency_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PendingConfirmationQueryRequest(BaseModel):
    status: ConfirmationStatus = "pending"
    action_type: str | None = None
    source_channel: str | None = None
    workflow_run_id: str | None = None
    limit: int = Field(default=50, ge=1, le=500)


class PendingConfirmationResolveRequest(BaseModel):
    confirmation_id: str = Field(min_length=1)
    decision: Decision
    decided_by: str = "local_user"
    notes: str | None = None
    result_payload: dict[str, Any] = Field(default_factory=dict)


class WorkflowArtifactRecordRequest(BaseModel):
    workflow_run_id: str | None = None
    workflow_step_id: str | None = None
    artifact_type: str = Field(min_length=1)
    title: str | None = None
    path: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class WorkflowEventLinkRequest(BaseModel):
    workflow_run_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


CONFIRMATION_TOOL_SPECS = [
    ToolSpec(
        name="init_workflow_confirmation_schema",
        description="Initialize workflow run, step, artifact, event link, and pending confirmation tables.",
        input_schema={"type": "object", "properties": {"include_indexes": {"type": "boolean", "default": True}}},
    ),
    ToolSpec(
        name="create_workflow_run",
        description="Create a local workflow run record for a fixed Chitung workflow.",
        input_schema={
            "type": "object",
            "properties": {
                "workflow_name": {"type": "string"},
                "title": {"type": "string"},
                "trigger_source": {"type": "string", "default": "manual"},
                "trigger_payload": {"type": "object"},
                "channel": {"type": "string", "default": "local_web"},
                "user_id": {"type": "string", "default": "local_user"},
                "status": {"type": "string", "default": "planned"},
                "idempotency_key": {"type": "string"},
                "metadata": {"type": "object"},
            },
            "required": ["workflow_name"],
        },
    ),
    ToolSpec(
        name="append_workflow_step",
        description="Append one auditable step to a workflow run.",
        input_schema={
            "type": "object",
            "properties": {
                "workflow_run_id": {"type": "string"},
                "step_name": {"type": "string"},
                "agent_name": {"type": "string"},
                "tool_name": {"type": "string"},
                "sequence_no": {"type": "integer"},
                "input_payload": {"type": "object"},
                "output_payload": {"type": "object"},
                "status": {"type": "string", "default": "planned"},
                "error": {"type": "string"},
            },
            "required": ["workflow_run_id", "step_name"],
        },
    ),
    ToolSpec(
        name="update_workflow_step",
        description="Update workflow step status, output payload, and error message.",
        input_schema={
            "type": "object",
            "properties": {
                "workflow_step_id": {"type": "string"},
                "status": {"type": "string"},
                "output_payload": {"type": "object"},
                "error": {"type": "string"},
            },
            "required": ["workflow_step_id", "status"],
        },
    ),
    ToolSpec(
        name="create_pending_confirmation",
        description="Create a human-in-the-loop confirmation item for external sends, case closure, reports, and status changes.",
        input_schema={
            "type": "object",
            "properties": {
                "action_type": {"type": "string"},
                "title": {"type": "string"},
                "summary": {"type": "string"},
                "payload": {"type": "object"},
                "risk_level": {"type": "string", "default": "medium"},
                "source_channel": {"type": "string", "default": "local_web"},
                "source_user_id": {"type": "string"},
                "source_chat_id": {"type": "string"},
                "source_message_id": {"type": "string"},
                "workflow_run_id": {"type": "string"},
                "workflow_step_id": {"type": "string"},
                "expires_at": {"type": "string"},
                "idempotency_key": {"type": "string"},
                "metadata": {"type": "object"},
            },
            "required": ["action_type", "title"],
        },
    ),
    ToolSpec(
        name="query_pending_confirmations",
        description="Query pending or resolved confirmation items.",
        input_schema={
            "type": "object",
            "properties": {
                "status": {"type": "string", "default": "pending"},
                "action_type": {"type": "string"},
                "source_channel": {"type": "string"},
                "workflow_run_id": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
        },
    ),
    ToolSpec(
        name="resolve_pending_confirmation",
        description="Approve, reject, expire, or mark a pending confirmation as executed/failed.",
        input_schema={
            "type": "object",
            "properties": {
                "confirmation_id": {"type": "string"},
                "decision": {"type": "string"},
                "decided_by": {"type": "string", "default": "local_user"},
                "notes": {"type": "string"},
                "result_payload": {"type": "object"},
            },
            "required": ["confirmation_id", "decision"],
        },
    ),
    ToolSpec(
        name="record_workflow_artifact",
        description="Record a report, form, notice draft, Feishu card, or other workflow artifact.",
        input_schema={
            "type": "object",
            "properties": {
                "workflow_run_id": {"type": "string"},
                "workflow_step_id": {"type": "string"},
                "artifact_type": {"type": "string"},
                "title": {"type": "string"},
                "path": {"type": "string"},
                "payload": {"type": "object"},
            },
            "required": ["artifact_type"],
        },
    ),
    ToolSpec(
        name="link_workflow_event",
        description="Link a workflow run to a source event such as Feishu message, external risk, safety case, or form record.",
        input_schema={
            "type": "object",
            "properties": {
                "workflow_run_id": {"type": "string"},
                "event_type": {"type": "string"},
                "source_type": {"type": "string"},
                "source_id": {"type": "string"},
                "payload": {"type": "object"},
            },
            "required": ["workflow_run_id", "event_type", "source_type", "source_id"],
        },
    ),
]


def init_workflow_confirmation_schema(req: WorkflowSchemaInitRequest) -> ToolResult:
    ensure_schema(req.include_indexes)
    return ToolResult(
        ok=True,
        tool="init_workflow_confirmation_schema",
        summary="Workflow and confirmation tables are ready.",
        data={"database_path": str(settings.safety_database_path)},
    )


def create_workflow_run(req: WorkflowRunCreateRequest) -> ToolResult:
    ensure_schema()
    workflow_run_id = _stable_or_random_id("wfr", req.idempotency_key)
    now = _now()
    with _connect() as conn:
        if req.idempotency_key:
            existing = conn.execute(
                "SELECT * FROM workflow_runs WHERE idempotency_key = ?",
                (req.idempotency_key,),
            ).fetchone()
            if existing:
                return ToolResult(
                    ok=True,
                    tool="create_workflow_run",
                    summary=f"Reused workflow run {existing['workflow_run_id']}.",
                    data={"workflow_run": _row_to_dict(existing), "idempotent_hit": True},
                )
        conn.execute(
            """
            INSERT INTO workflow_runs (
                workflow_run_id, workflow_name, title, trigger_source, trigger_payload_json,
                channel, user_id, status, idempotency_key, metadata_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                workflow_run_id,
                req.workflow_name,
                req.title,
                req.trigger_source,
                _json(req.trigger_payload),
                req.channel,
                req.user_id,
                req.status,
                req.idempotency_key,
                _json(req.metadata),
                now,
                now,
            ),
        )
        row = conn.execute("SELECT * FROM workflow_runs WHERE workflow_run_id = ?", (workflow_run_id,)).fetchone()
    return ToolResult(
        ok=True,
        tool="create_workflow_run",
        summary=f"Created workflow run {workflow_run_id}.",
        data={"workflow_run": _row_to_dict(row), "idempotent_hit": False},
    )


def append_workflow_step(req: WorkflowStepAppendRequest) -> ToolResult:
    ensure_schema()
    workflow_step_id = f"wfs_{uuid.uuid4().hex[:20]}"
    now = _now()
    with _connect() as conn:
        if req.sequence_no is None:
            row = conn.execute(
                "SELECT COALESCE(MAX(sequence_no), 0) + 1 AS next_no FROM workflow_steps WHERE workflow_run_id = ?",
                (req.workflow_run_id,),
            ).fetchone()
            sequence_no = int(row["next_no"])
        else:
            sequence_no = req.sequence_no
        conn.execute(
            """
            INSERT INTO workflow_steps (
                workflow_step_id, workflow_run_id, sequence_no, step_name, agent_name, tool_name,
                status, input_payload_json, output_payload_json, error, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                workflow_step_id,
                req.workflow_run_id,
                sequence_no,
                req.step_name,
                req.agent_name,
                req.tool_name,
                req.status,
                _json(req.input_payload),
                _json(req.output_payload),
                req.error,
                now,
                now,
            ),
        )
        row = conn.execute("SELECT * FROM workflow_steps WHERE workflow_step_id = ?", (workflow_step_id,)).fetchone()
    return ToolResult(ok=True, tool="append_workflow_step", summary=f"Created workflow step {workflow_step_id}.", data={"workflow_step": _row_to_dict(row)})


def update_workflow_step(req: WorkflowStepUpdateRequest) -> ToolResult:
    ensure_schema()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE workflow_steps
            SET status = ?, output_payload_json = ?, error = ?, updated_at = ?
            WHERE workflow_step_id = ?
            """,
            (req.status, _json(req.output_payload), req.error, _now(), req.workflow_step_id),
        )
        row = conn.execute("SELECT * FROM workflow_steps WHERE workflow_step_id = ?", (req.workflow_step_id,)).fetchone()
    if row is None:
        return ToolResult(ok=False, tool="update_workflow_step", summary="Workflow step not found.", error=f"Unknown workflow_step_id: {req.workflow_step_id}")
    return ToolResult(ok=True, tool="update_workflow_step", summary=f"Updated workflow step {req.workflow_step_id}.", data={"workflow_step": _row_to_dict(row)})


def create_pending_confirmation(req: PendingConfirmationCreateRequest) -> ToolResult:
    ensure_schema()
    confirmation_id = _stable_or_random_id("pcf", req.idempotency_key)
    now = _now()
    with _connect() as conn:
        if req.idempotency_key:
            existing = conn.execute(
                "SELECT * FROM pending_confirmations WHERE idempotency_key = ?",
                (req.idempotency_key,),
            ).fetchone()
            if existing:
                return ToolResult(
                    ok=True,
                    tool="create_pending_confirmation",
                    summary=f"Reused pending confirmation {existing['confirmation_id']}.",
                    data={"confirmation": _row_to_dict(existing), "idempotent_hit": True},
                )
        conn.execute(
            """
            INSERT INTO pending_confirmations (
                confirmation_id, action_type, title, summary, payload_json, risk_level, status,
                source_channel, source_user_id, source_chat_id, source_message_id,
                workflow_run_id, workflow_step_id, expires_at, idempotency_key, metadata_json,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                confirmation_id,
                req.action_type,
                req.title,
                req.summary,
                _json(req.payload),
                req.risk_level,
                req.source_channel,
                req.source_user_id,
                req.source_chat_id,
                req.source_message_id,
                req.workflow_run_id,
                req.workflow_step_id,
                req.expires_at,
                req.idempotency_key,
                _json(req.metadata),
                now,
                now,
            ),
        )
        if req.workflow_run_id:
            conn.execute("UPDATE workflow_runs SET status = 'pending_confirmation', updated_at = ? WHERE workflow_run_id = ?", (now, req.workflow_run_id))
        if req.workflow_step_id:
            conn.execute("UPDATE workflow_steps SET status = 'pending_confirmation', updated_at = ? WHERE workflow_step_id = ?", (now, req.workflow_step_id))
        row = conn.execute("SELECT * FROM pending_confirmations WHERE confirmation_id = ?", (confirmation_id,)).fetchone()
    return ToolResult(
        ok=True,
        tool="create_pending_confirmation",
        summary=f"Created pending confirmation {confirmation_id}.",
        data={"confirmation": _row_to_dict(row), "idempotent_hit": False},
    )


def query_pending_confirmations(req: PendingConfirmationQueryRequest) -> ToolResult:
    ensure_schema()
    clauses = ["status = ?"]
    params: list[Any] = [req.status]
    if req.action_type:
        clauses.append("action_type = ?")
        params.append(req.action_type)
    if req.source_channel:
        clauses.append("source_channel = ?")
        params.append(req.source_channel)
    if req.workflow_run_id:
        clauses.append("workflow_run_id = ?")
        params.append(req.workflow_run_id)
    params.append(req.limit)
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM pending_confirmations WHERE {' AND '.join(clauses)} ORDER BY created_at DESC LIMIT ?",
            params,
        ).fetchall()
    return ToolResult(
        ok=True,
        tool="query_pending_confirmations",
        summary=f"Returned {len(rows)} confirmations.",
        data={"items": [_row_to_dict(row) for row in rows], "limit": req.limit},
    )


def resolve_pending_confirmation(req: PendingConfirmationResolveRequest) -> ToolResult:
    ensure_schema()
    status_by_decision: dict[Decision, ConfirmationStatus] = {
        "approve": "approved",
        "reject": "rejected",
        "expire": "expired",
        "mark_executed": "executed",
        "mark_failed": "failed",
    }
    new_status = status_by_decision[req.decision]
    now = _now()
    with _connect() as conn:
        current = conn.execute("SELECT * FROM pending_confirmations WHERE confirmation_id = ?", (req.confirmation_id,)).fetchone()
        if current is None:
            return ToolResult(ok=False, tool="resolve_pending_confirmation", summary="Pending confirmation not found.", error=f"Unknown confirmation_id: {req.confirmation_id}")
        conn.execute(
            """
            UPDATE pending_confirmations
            SET status = ?, decided_by = ?, decided_at = ?, decision_notes = ?,
                result_payload_json = ?, updated_at = ?
            WHERE confirmation_id = ?
            """,
            (new_status, req.decided_by, now, req.notes, _json(req.result_payload), now, req.confirmation_id),
        )
        updated = conn.execute("SELECT * FROM pending_confirmations WHERE confirmation_id = ?", (req.confirmation_id,)).fetchone()
    return ToolResult(
        ok=True,
        tool="resolve_pending_confirmation",
        summary=f"Marked confirmation {req.confirmation_id} as {new_status}.",
        data={"confirmation": _row_to_dict(updated), "decision": req.decision},
    )


def record_workflow_artifact(req: WorkflowArtifactRecordRequest) -> ToolResult:
    ensure_schema()
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO workflow_artifacts (
                workflow_run_id, workflow_step_id, artifact_type, title, path, payload_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (req.workflow_run_id, req.workflow_step_id, req.artifact_type, req.title, req.path, _json(req.payload), _now()),
        )
    return ToolResult(ok=True, tool="record_workflow_artifact", summary=f"Recorded workflow artifact {cursor.lastrowid}.", data={"artifact_id": int(cursor.lastrowid)})


def link_workflow_event(req: WorkflowEventLinkRequest) -> ToolResult:
    ensure_schema()
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO workflow_event_links (
                workflow_run_id, event_type, source_type, source_id, payload_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (req.workflow_run_id, req.event_type, req.source_type, req.source_id, _json(req.payload), _now()),
        )
    return ToolResult(ok=True, tool="link_workflow_event", summary=f"Linked workflow event {cursor.lastrowid}.", data={"link_id": int(cursor.lastrowid)})


def ensure_schema(include_indexes: bool = True) -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS workflow_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_run_id TEXT UNIQUE NOT NULL,
                workflow_name TEXT NOT NULL,
                title TEXT,
                trigger_source TEXT,
                trigger_payload_json TEXT NOT NULL DEFAULT '{}',
                channel TEXT,
                user_id TEXT,
                status TEXT NOT NULL DEFAULT 'planned',
                idempotency_key TEXT UNIQUE,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS workflow_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_step_id TEXT UNIQUE NOT NULL,
                workflow_run_id TEXT NOT NULL,
                sequence_no INTEGER NOT NULL,
                step_name TEXT NOT NULL,
                agent_name TEXT,
                tool_name TEXT,
                status TEXT NOT NULL DEFAULT 'planned',
                input_payload_json TEXT NOT NULL DEFAULT '{}',
                output_payload_json TEXT NOT NULL DEFAULT '{}',
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(workflow_run_id) REFERENCES workflow_runs(workflow_run_id)
            );

            CREATE TABLE IF NOT EXISTS pending_confirmations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                confirmation_id TEXT UNIQUE NOT NULL,
                action_type TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT,
                payload_json TEXT NOT NULL DEFAULT '{}',
                risk_level TEXT NOT NULL DEFAULT 'medium',
                status TEXT NOT NULL DEFAULT 'pending',
                source_channel TEXT,
                source_user_id TEXT,
                source_chat_id TEXT,
                source_message_id TEXT,
                workflow_run_id TEXT,
                workflow_step_id TEXT,
                expires_at TEXT,
                idempotency_key TEXT UNIQUE,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                decided_by TEXT,
                decided_at TEXT,
                decision_notes TEXT,
                result_payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(workflow_run_id) REFERENCES workflow_runs(workflow_run_id),
                FOREIGN KEY(workflow_step_id) REFERENCES workflow_steps(workflow_step_id)
            );

            CREATE TABLE IF NOT EXISTS workflow_artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_run_id TEXT,
                workflow_step_id TEXT,
                artifact_type TEXT NOT NULL,
                title TEXT,
                path TEXT,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY(workflow_run_id) REFERENCES workflow_runs(workflow_run_id),
                FOREIGN KEY(workflow_step_id) REFERENCES workflow_steps(workflow_step_id)
            );

            CREATE TABLE IF NOT EXISTS workflow_event_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_run_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY(workflow_run_id) REFERENCES workflow_runs(workflow_run_id)
            );
            """
        )
        if include_indexes:
            conn.executescript(
                """
                CREATE INDEX IF NOT EXISTS idx_workflow_runs_status ON workflow_runs(status);
                CREATE INDEX IF NOT EXISTS idx_workflow_steps_run ON workflow_steps(workflow_run_id, sequence_no);
                CREATE INDEX IF NOT EXISTS idx_pending_confirmations_status ON pending_confirmations(status);
                CREATE INDEX IF NOT EXISTS idx_pending_confirmations_action ON pending_confirmations(action_type);
                CREATE INDEX IF NOT EXISTS idx_pending_confirmations_source ON pending_confirmations(source_channel, source_chat_id);
                CREATE INDEX IF NOT EXISTS idx_workflow_event_links_run ON workflow_event_links(workflow_run_id);
                """
            )


def _connect() -> sqlite3.Connection:
    path = settings.safety_database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        return {}
    data = dict(row)
    for key in list(data.keys()):
        if key.endswith("_json") and isinstance(data[key], str):
            try:
                data[key[:-5]] = json.loads(data[key])
            except json.JSONDecodeError:
                data[key[:-5]] = data[key]
    return data


def _stable_or_random_id(prefix: str, idempotency_key: str | None) -> str:
    if idempotency_key:
        return f"{prefix}_{uuid.uuid5(uuid.NAMESPACE_URL, idempotency_key).hex[:20]}"
    return f"{prefix}_{uuid.uuid4().hex[:20]}"
