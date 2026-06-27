from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from chitung_center import storage
from chitung_center.config import settings
from chitung_center.job_service import start_background_job, update_progress
from chitung_center.models import ChatMessageRequest


LIFTING_PATROL_TASK_ID = "auto_lifting_safety_patrol_6h"
LIFTING_PATROL_PROMPT = (
    "检测地盘全部已启用 CCTV 是否存在不安全吊运行为："
    "起重机/吊机作业、吊索吊具与绑扎点、警戒区与隔离围挡、"
    "人员是否进入吊运荷载下方或回转半径、司索/信号员指挥、"
    "吊运与交叉作业冲突、PPE 合规、视线与天气是否适合吊运。"
)

DEFAULT_TASKS: list[dict[str, Any]] = [
    {
        "task_id": LIFTING_PATROL_TASK_ID,
        "name": "6小时吊运专项巡检（11路CCTV）",
        "template_id": "tpl_lifting_patrol",
        "workflow_name": "workflow_lifting_safety_patrol",
        "prompt": LIFTING_PATROL_PROMPT,
        "status": "ACTIVE",
        "schedule_type": "recurring",
        "interval_minutes": 360,
        "rrule": "RRULE:FREQ=HOURLY;INTERVAL=6",
        "config": {
            "auto_send_whatsapp": True,
            "whatsapp_to": settings.lifting_alert_whatsapp_to,
            "vlm_enabled": True,
        },
    }
]


def ensure_schema() -> None:
    storage.ensure_schema()
    with storage.transaction() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS automation_tasks (
                task_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                template_id TEXT,
                workflow_name TEXT,
                prompt TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                schedule_type TEXT NOT NULL DEFAULT 'recurring',
                interval_minutes INTEGER NOT NULL DEFAULT 360,
                rrule TEXT DEFAULT '',
                scheduled_at TEXT,
                config_json TEXT NOT NULL DEFAULT '{}',
                next_run_at TEXT,
                last_run_at TEXT,
                last_run_status TEXT,
                last_run_summary TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS automation_runs (
                run_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                triggered_by TEXT NOT NULL DEFAULT 'scheduler',
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                workflow_run_id TEXT,
                job_id TEXT,
                result_summary TEXT,
                error TEXT,
                result_json TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES automation_tasks(task_id)
            );

            CREATE INDEX IF NOT EXISTS idx_automation_tasks_status ON automation_tasks(status);
            CREATE INDEX IF NOT EXISTS idx_automation_runs_task ON automation_runs(task_id, started_at);
            """
        )
    _seed_default_tasks()


def _seed_default_tasks() -> None:
    now = storage.now_iso()
    with storage.transaction() as conn:
        for item in DEFAULT_TASKS:
            task_id = str(item["task_id"])
            exists = conn.execute("SELECT 1 FROM automation_tasks WHERE task_id = ?", (task_id,)).fetchone()
            if exists:
                continue
            config = item.get("config") if isinstance(item.get("config"), dict) else {}
            next_run = _estimate_next_run(int(item.get("interval_minutes") or 360))
            conn.execute(
                """
                INSERT INTO automation_tasks (
                    task_id, name, template_id, workflow_name, prompt, status, schedule_type,
                    interval_minutes, rrule, config_json, next_run_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    item["name"],
                    item.get("template_id"),
                    item.get("workflow_name"),
                    item.get("prompt") or "",
                    item.get("status") or "ACTIVE",
                    item.get("schedule_type") or "recurring",
                    int(item.get("interval_minutes") or 360),
                    str(item.get("rrule") or ""),
                    json.dumps(config, ensure_ascii=False),
                    next_run,
                    now,
                    now,
                ),
            )


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _parse_json(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def _row_to_task(row: Any) -> dict[str, Any]:
    return {
        "task_id": row["task_id"],
        "name": row["name"],
        "template_id": row["template_id"],
        "workflow_name": row["workflow_name"],
        "prompt": row["prompt"],
        "status": row["status"],
        "schedule_type": row["schedule_type"],
        "interval_minutes": row["interval_minutes"],
        "rrule": row["rrule"],
        "scheduled_at": row["scheduled_at"],
        "config": _parse_json(row["config_json"], {}),
        "next_run_at": row["next_run_at"],
        "last_run_at": row["last_run_at"],
        "last_run_status": row["last_run_status"],
        "last_run_summary": row["last_run_summary"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_tasks() -> list[dict[str, Any]]:
    ensure_schema()
    with storage.transaction() as conn:
        rows = conn.execute("SELECT * FROM automation_tasks ORDER BY created_at ASC").fetchall()
    return [_row_to_task(row) for row in rows]


def get_task(task_id: str) -> dict[str, Any] | None:
    ensure_schema()
    with storage.transaction() as conn:
        row = conn.execute("SELECT * FROM automation_tasks WHERE task_id = ?", (task_id,)).fetchone()
    return _row_to_task(row) if row else None


def save_task(payload: dict[str, Any]) -> dict[str, Any]:
    ensure_schema()
    task_id = str(payload.get("task_id") or payload.get("id") or f"auto_{uuid.uuid4().hex[:10]}")
    existing = get_task(task_id)
    now = storage.now_iso()
    config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    interval_minutes = max(5, int(payload.get("interval_minutes") or existing.get("interval_minutes") if existing else 360))
    status = str(payload.get("status") or (existing or {}).get("status") or "ACTIVE")
    next_run_at = payload.get("next_run_at")
    if next_run_at is None:
        if status == "ACTIVE":
            next_run_at = _estimate_next_run(interval_minutes)
        else:
            next_run_at = None
    with storage.transaction() as conn:
        conn.execute(
            """
            INSERT INTO automation_tasks (
                task_id, name, template_id, workflow_name, prompt, status, schedule_type,
                interval_minutes, rrule, scheduled_at, config_json, next_run_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET
                name = excluded.name,
                template_id = excluded.template_id,
                workflow_name = excluded.workflow_name,
                prompt = excluded.prompt,
                status = excluded.status,
                schedule_type = excluded.schedule_type,
                interval_minutes = excluded.interval_minutes,
                rrule = excluded.rrule,
                scheduled_at = excluded.scheduled_at,
                config_json = excluded.config_json,
                next_run_at = excluded.next_run_at,
                updated_at = excluded.updated_at
            """,
            (
                task_id,
                str(payload.get("name") or (existing or {}).get("name") or task_id),
                payload.get("template_id") or (existing or {}).get("template_id"),
                payload.get("workflow_name") or (existing or {}).get("workflow_name"),
                str(payload.get("prompt") or (existing or {}).get("prompt") or ""),
                status,
                str(payload.get("schedule_type") or (existing or {}).get("schedule_type") or "recurring"),
                interval_minutes,
                str(payload.get("rrule") or (existing or {}).get("rrule") or ""),
                payload.get("scheduled_at"),
                _json(config),
                next_run_at,
                (existing or {}).get("created_at") or now,
                now,
            ),
        )
    return get_task(task_id) or {"task_id": task_id}


def list_runs(*, task_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    ensure_schema()
    limit = max(1, min(limit, 200))
    query = "SELECT * FROM automation_runs"
    params: list[Any] = []
    if task_id:
        query += " WHERE task_id = ?"
        params.append(task_id)
    query += " ORDER BY started_at DESC LIMIT ?"
    params.append(limit)
    with storage.transaction() as conn:
        rows = conn.execute(query, params).fetchall()
    return [
        {
            "run_id": row["run_id"],
            "task_id": row["task_id"],
            "triggered_by": row["triggered_by"],
            "status": row["status"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "workflow_run_id": row["workflow_run_id"],
            "job_id": row["job_id"],
            "result_summary": row["result_summary"],
            "error": row["error"],
            "result": _parse_json(row["result_json"], {}),
        }
        for row in rows
    ]


def _estimate_next_run(interval_minutes: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=max(5, interval_minutes))).isoformat()


def _create_run(task_id: str, *, triggered_by: str) -> dict[str, Any]:
    now = storage.now_iso()
    run_id = f"autorun_{uuid.uuid4().hex[:12]}"
    with storage.transaction() as conn:
        conn.execute(
            """
            INSERT INTO automation_runs (
                run_id, task_id, triggered_by, status, started_at, created_at
            ) VALUES (?, ?, ?, 'running', ?, ?)
            """,
            (run_id, task_id, triggered_by, now, now),
        )
    return {"run_id": run_id, "task_id": task_id, "triggered_by": triggered_by, "status": "running", "started_at": now}


def _finish_run(
    run_id: str,
    *,
    status: str,
    summary: str,
    workflow_run_id: str = "",
    job_id: str = "",
    error: str | None = None,
    result: dict[str, Any] | None = None,
) -> None:
    now = storage.now_iso()
    with storage.transaction() as conn:
        conn.execute(
            """
            UPDATE automation_runs
            SET status = ?, finished_at = ?, workflow_run_id = ?, job_id = ?,
                result_summary = ?, error = ?, result_json = ?
            WHERE run_id = ?
            """,
            (status, now, workflow_run_id or None, job_id or None, summary, error, _json(result or {}), run_id),
        )


def _mark_task_run(task: dict[str, Any], *, status: str, summary: str) -> None:
    now = storage.now_iso()
    interval = int(task.get("interval_minutes") or 360)
    next_run = _estimate_next_run(interval) if task.get("status") == "ACTIVE" else None
    with storage.transaction() as conn:
        conn.execute(
            """
            UPDATE automation_tasks
            SET last_run_at = ?, last_run_status = ?, last_run_summary = ?,
                next_run_at = ?, updated_at = ?
            WHERE task_id = ?
            """,
            (now, status, summary, next_run, now, task["task_id"]),
        )


def _reserve_next_run(task: dict[str, Any]) -> None:
    """Push next_run_at forward as soon as a run starts — prevents 30s re-trigger pile-up."""
    now = storage.now_iso()
    interval = int(task.get("interval_minutes") or 360)
    next_run = _estimate_next_run(interval) if task.get("status") == "ACTIVE" else None
    with storage.transaction() as conn:
        conn.execute(
            """
            UPDATE automation_tasks
            SET last_run_at = ?, last_run_status = ?, next_run_at = ?, updated_at = ?
            WHERE task_id = ?
            """,
            (now, "running", next_run, now, task["task_id"]),
        )


def _task_has_active_job(task_id: str) -> bool:
    ensure_schema()
    with storage.connect() as conn:
        rows = conn.execute(
            """
            SELECT job_id FROM job_runs
            WHERE source_module = 'automation_scheduler'
              AND status IN ('queued', 'running')
            ORDER BY created_at DESC
            LIMIT 20
            """
        ).fetchall()
    for row in rows:
        job = get_job(str(row["job_id"]))
        if not job:
            continue
        req = job.get("request")
        if isinstance(req, dict) and str(req.get("task_id") or "") == task_id:
            return True
    return False


async def run_task(task_id: str, *, triggered_by: str = "manual") -> dict[str, Any]:
    task = get_task(task_id)
    if not task:
        return {"ok": False, "error": "task_not_found", "task_id": task_id}

    workflow_name = str(task.get("workflow_name") or "").strip()
    if not workflow_name:
        return {"ok": False, "error": "workflow_name_missing", "task_id": task_id}

    run = _create_run(task_id, triggered_by=triggered_by)
    config = task.get("config") if isinstance(task.get("config"), dict) else {}
    _reserve_next_run(task)

    async def runner(job_id: str) -> dict[str, Any]:
        from chitung_center.workflow_engine import workflow_engine

        update_progress(job_id, 10, f"启动工作流：{workflow_name}")
        request = ChatMessageRequest(
            message=str(task.get("prompt") or LIFTING_PATROL_PROMPT),
            channel="automation_scheduler",
            user_id=f"automation:{task_id}",
            metadata={
                "trigger": triggered_by,
                "automation_task_id": task_id,
                "automation_run_id": run["run_id"],
                "external_card": {
                    "title": str(task.get("name") or "定时吊运专项巡检"),
                    "summary": str(task.get("prompt") or LIFTING_PATROL_PROMPT),
                    "priority": "P1",
                    "recommended_action": "复核检测结果并通知前线",
                },
                "auto_send_whatsapp": bool(config.get("auto_send_whatsapp", True)),
                "whatsapp_to": str(config.get("whatsapp_to") or settings.lifting_alert_whatsapp_to),
                "vlm_enabled": bool(config.get("vlm_enabled", True)),
            },
        )
        update_progress(job_id, 25, "执行 11 路 CCTV 吊运专项检测…")
        result = await workflow_engine.run_template(workflow_name, request)
        summary = str(result.get("reply") or "自动化工作流执行完成。")
        status = "success" if result.get("ok") else "failed"
        _finish_run(
            run["run_id"],
            status=status,
            summary=summary,
            workflow_run_id=str(result.get("workflow_run_id") or ""),
            job_id=job_id,
            error=None if result.get("ok") else str(result.get("error") or summary),
            result=result if isinstance(result, dict) else {},
        )
        _mark_task_run(task, status=status, summary=summary)
        return {"ok": bool(result.get("ok")), "run_id": run["run_id"], "workflow_run_id": result.get("workflow_run_id"), "summary": summary, "result": result}

    job = start_background_job(
        job_type="automation_workflow",
        title=str(task.get("name") or task_id),
        source_module="automation_scheduler",
        request={"task_id": task_id, "workflow_name": workflow_name, "triggered_by": triggered_by, "run_id": run["run_id"]},
        runner=runner,
    )
    with storage.transaction() as conn:
        conn.execute(
            "UPDATE automation_runs SET job_id = ? WHERE run_id = ?",
            (str(job.get("job_id") or ""), run["run_id"]),
        )
    return {"ok": True, "task_id": task_id, "run_id": run["run_id"], "job_id": job.get("job_id"), "status": "running"}


class AutomationScheduler:
    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._running_task_id: str | None = None
        self._last_error: str | None = None

    def start(self) -> None:
        ensure_schema()
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop(), name="automation-scheduler")

    async def stop(self) -> None:
        if not self._task:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _loop(self) -> None:
        while True:
            try:
                await self._check_due_tasks()
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                self._last_error = str(exc)
                await asyncio.sleep(30)

    async def _check_due_tasks(self) -> None:
        if self._running_task_id:
            return
        now = datetime.now(timezone.utc)
        for task in list_tasks():
            task_id = str(task.get("task_id") or "")
            if task.get("status") != "ACTIVE" or task.get("schedule_type") != "recurring":
                continue
            if task_id and _task_has_active_job(task_id):
                continue
            next_run_at = task.get("next_run_at")
            if not next_run_at:
                continue
            try:
                due_at = datetime.fromisoformat(str(next_run_at))
            except (TypeError, ValueError):
                continue
            if due_at > now:
                continue
            self._running_task_id = str(task["task_id"])
            try:
                await run_task(str(task["task_id"]), triggered_by="scheduler")
            finally:
                self._running_task_id = None

    def status(self) -> dict[str, Any]:
        tasks = list_tasks()
        return {
            "ok": True,
            "scheduler_active": bool(self._task and not self._task.done()),
            "running_task_id": self._running_task_id,
            "task_count": len(tasks),
            "active_task_count": sum(1 for item in tasks if item.get("status") == "ACTIVE"),
            "last_error": self._last_error,
            "tasks": tasks,
        }


automation_scheduler = AutomationScheduler()
