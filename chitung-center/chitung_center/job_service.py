from __future__ import annotations

import asyncio
import json
import traceback
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from chitung_center import storage


JobCallable = Callable[[str], Awaitable[dict[str, Any]]]


def ensure_schema() -> None:
    storage.ensure_schema()
    with storage.transaction() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS job_runs (
                job_id TEXT PRIMARY KEY,
                job_type TEXT NOT NULL,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                progress INTEGER NOT NULL DEFAULT 0,
                source_module TEXT,
                request_json TEXT DEFAULT '{}',
                result_json TEXT DEFAULT '{}',
                error TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS task_events (
                event_id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                message TEXT,
                progress INTEGER,
                payload_json TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY(job_id) REFERENCES job_runs(job_id)
            );

            CREATE INDEX IF NOT EXISTS idx_job_runs_status ON job_runs(status);
            CREATE INDEX IF NOT EXISTS idx_job_runs_created ON job_runs(created_at);
            CREATE INDEX IF NOT EXISTS idx_task_events_job ON task_events(job_id, created_at);
            """
        )


def create_job(
    *,
    job_type: str,
    title: str,
    source_module: str,
    request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ensure_schema()
    now = storage.now_iso()
    job_id = f"job_{uuid.uuid4().hex[:16]}"
    with storage.transaction() as conn:
        conn.execute(
            """
            INSERT INTO job_runs (
                job_id, job_type, title, status, progress, source_module, request_json,
                created_at, updated_at
            ) VALUES (?, ?, ?, 'queued', 0, ?, ?, ?, ?)
            """,
            (job_id, job_type, title, source_module, _json(request or {}), now, now),
        )
    add_event(job_id, "queued", "任务已进入后台队列", progress=0)
    return get_job(job_id) or {"job_id": job_id, "status": "queued"}


def start_background_job(
    *,
    job_type: str,
    title: str,
    source_module: str,
    request: dict[str, Any] | None,
    runner: JobCallable,
) -> dict[str, Any]:
    job = create_job(job_type=job_type, title=title, source_module=source_module, request=request)
    job_id = str(job["job_id"])
    asyncio.create_task(_run_job(job_id, runner), name=f"job:{job_type}:{job_id}")
    return job


async def _run_job(job_id: str, runner: JobCallable) -> None:
    mark_running(job_id)
    try:
        result = await runner(job_id)
        mark_finished(job_id, result=result)
    except Exception as exc:  # noqa: BLE001
        mark_failed(job_id, str(exc), traceback.format_exc())


def mark_running(job_id: str) -> None:
    now = storage.now_iso()
    with storage.transaction() as conn:
        conn.execute(
            "UPDATE job_runs SET status = 'running', progress = 5, started_at = ?, updated_at = ? WHERE job_id = ?",
            (now, now, job_id),
        )
    add_event(job_id, "started", "任务开始执行", progress=5)


def update_progress(job_id: str, progress: int, message: str, payload: dict[str, Any] | None = None) -> None:
    progress = max(0, min(int(progress), 99))
    now = storage.now_iso()
    with storage.transaction() as conn:
        conn.execute(
            "UPDATE job_runs SET progress = ?, updated_at = ? WHERE job_id = ?",
            (progress, now, job_id),
        )
    add_event(job_id, "progress", message, progress=progress, payload=payload or {})


def mark_finished(job_id: str, *, result: dict[str, Any]) -> None:
    now = storage.now_iso()
    with storage.transaction() as conn:
        conn.execute(
            """
            UPDATE job_runs SET status = 'success', progress = 100, result_json = ?,
                finished_at = ?, updated_at = ?
            WHERE job_id = ?
            """,
            (_json(result), now, now, job_id),
        )
    add_event(job_id, "finished", "任务执行完成", progress=100, payload=result)


def mark_failed(job_id: str, error: str, details: str | None = None) -> None:
    now = storage.now_iso()
    payload = {"traceback": details} if details else {}
    with storage.transaction() as conn:
        conn.execute(
            """
            UPDATE job_runs SET status = 'failed', error = ?, finished_at = ?, updated_at = ?
            WHERE job_id = ?
            """,
            (error, now, now, job_id),
        )
    add_event(job_id, "failed", error, payload=payload)


def add_event(
    job_id: str,
    event_type: str,
    message: str,
    *,
    progress: int | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    ensure_schema()
    with storage.transaction() as conn:
        conn.execute(
            """
            INSERT INTO task_events (event_id, job_id, event_type, message, progress, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"evt_{uuid.uuid4().hex[:16]}",
                job_id,
                event_type,
                message,
                progress,
                _json(payload or {}),
                storage.now_iso(),
            ),
        )


def get_job(job_id: str) -> dict[str, Any] | None:
    ensure_schema()
    with storage.connect() as conn:
        row = conn.execute("SELECT * FROM job_runs WHERE job_id = ?", (job_id,)).fetchone()
    return _row_to_job(row) if row else None


def list_jobs(
    status: str | None = None,
    limit: int = 50,
    source_module: str | None = None,
    job_type: str | None = None,
) -> dict[str, Any]:
    ensure_schema()
    limit = max(1, min(limit, 200))
    filters: list[str] = []
    params: list[Any] = []
    if status:
        filters.append("status = ?")
        params.append(status)
    if source_module:
        filters.append("source_module = ?")
        params.append(source_module)
    if job_type:
        filters.append("job_type = ?")
        params.append(job_type)
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    with storage.connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM job_runs {where} ORDER BY datetime(created_at) DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
    return {"ok": True, "items": [_row_to_job(row) for row in rows]}


def job_stats() -> dict[str, Any]:
    ensure_schema()
    with storage.connect() as conn:
        status_rows = conn.execute(
            "SELECT status, COUNT(*) AS count FROM job_runs GROUP BY status ORDER BY status"
        ).fetchall()
        module_rows = conn.execute(
            """
            SELECT COALESCE(source_module, 'unknown') AS source_module, COUNT(*) AS count
            FROM job_runs
            GROUP BY COALESCE(source_module, 'unknown')
            ORDER BY count DESC
            """
        ).fetchall()
        type_rows = conn.execute(
            """
            SELECT job_type, COUNT(*) AS count
            FROM job_runs
            GROUP BY job_type
            ORDER BY count DESC
            """
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) AS count FROM job_runs").fetchone()["count"]
    return {
        "ok": True,
        "total": int(total or 0),
        "by_status": {row["status"]: row["count"] for row in status_rows},
        "by_module": {row["source_module"]: row["count"] for row in module_rows},
        "by_type": {row["job_type"]: row["count"] for row in type_rows},
    }


def list_events(job_id: str, limit: int = 100) -> dict[str, Any]:
    ensure_schema()
    with storage.connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM task_events WHERE job_id = ?
            ORDER BY datetime(created_at) ASC LIMIT ?
            """,
            (job_id, max(1, min(limit, 500))),
        ).fetchall()
    return {"ok": True, "items": [_row_to_event(row) for row in rows]}


def _row_to_job(row: Any) -> dict[str, Any]:
    return {
        "job_id": row["job_id"],
        "job_type": row["job_type"],
        "title": row["title"],
        "status": row["status"],
        "progress": row["progress"],
        "source_module": row["source_module"],
        "request": _loads(row["request_json"], {}),
        "result": _loads(row["result_json"], {}),
        "error": row["error"],
        "created_at": row["created_at"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "updated_at": row["updated_at"],
    }


def _row_to_event(row: Any) -> dict[str, Any]:
    return {
        "event_id": row["event_id"],
        "job_id": row["job_id"],
        "event_type": row["event_type"],
        "message": row["message"],
        "progress": row["progress"],
        "payload": _loads(row["payload_json"], {}),
        "created_at": row["created_at"],
    }


def _json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback
