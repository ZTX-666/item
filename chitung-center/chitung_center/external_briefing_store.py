from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from chitung_center.config import ROOT


TABLE_NAME = "external_risk_briefing_reports"


def default_db_path() -> Path:
    value = os.getenv("SAFETY_DATABASE_PATH")
    if value:
        return Path(value)
    return ROOT.parent / "agent-toolbox" / "workspace" / "safety_platform.db"


def persist_external_briefing_report(
    report: dict[str, Any],
    *,
    db_path: Path | None = None,
) -> dict[str, Any]:
    path = db_path or default_db_path()
    now = _now_iso()
    payload = _normalize_report(report)
    path.parent.mkdir(parents=True, exist_ok=True)

    with _connect(path) as conn:
        _ensure_schema(conn)
        cursor = conn.execute(
            f"""
            INSERT INTO {TABLE_NAME} (
                workflow_run_id,
                title,
                summary,
                briefing_text,
                report_images_json,
                report_links_json,
                tool_results_json,
                config_json,
                payload_json,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["workflow_run_id"],
                payload["title"],
                payload["summary"],
                payload["briefing_text"],
                _json(payload["report_images"]),
                _json(payload["report_links"]),
                _json(payload["tool_results"]),
                _json(payload["config"]),
                _json(payload["payload"]),
                now,
                now,
            ),
        )
        report_id = int(cursor.lastrowid)

    return {
        "ok": True,
        "report_id": report_id,
        "title": payload["title"],
        "created_at": now,
        "db_path": str(path),
        "table": TABLE_NAME,
    }


def list_external_briefing_reports(
    *,
    limit: int = 20,
    db_path: Path | None = None,
) -> dict[str, Any]:
    path = db_path or default_db_path()
    if not path.exists():
        return {"ok": True, "items": [], "db_path": str(path), "table": TABLE_NAME}

    with _connect(path) as conn:
        _ensure_schema(conn)
        rows = conn.execute(
            f"""
            SELECT *
            FROM {TABLE_NAME}
            ORDER BY datetime(created_at) DESC, report_id DESC
            LIMIT ?
            """,
            (max(1, min(limit, 100)),),
        ).fetchall()

    return {
        "ok": True,
        "items": [_row_to_report(row) for row in rows],
        "db_path": str(path),
        "table": TABLE_NAME,
    }


def get_external_briefing_report(report_id: int, *, db_path: Path | None = None) -> dict[str, Any] | None:
    path = db_path or default_db_path()
    if not path.exists():
        return None
    with _connect(path) as conn:
        _ensure_schema(conn)
        row = conn.execute(f"SELECT * FROM {TABLE_NAME} WHERE report_id = ?", (report_id,)).fetchone()
    return _row_to_report(row) if row else None


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_run_id TEXT,
            title TEXT NOT NULL,
            summary TEXT,
            briefing_text TEXT NOT NULL,
            report_images_json TEXT NOT NULL DEFAULT '[]',
            report_links_json TEXT NOT NULL DEFAULT '[]',
            tool_results_json TEXT NOT NULL DEFAULT '[]',
            config_json TEXT NOT NULL DEFAULT '{{}}',
            payload_json TEXT NOT NULL DEFAULT '{{}}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_external_briefing_reports_created
        ON {TABLE_NAME}(created_at);

        CREATE INDEX IF NOT EXISTS idx_external_briefing_reports_workflow
        ON {TABLE_NAME}(workflow_run_id);
        """
    )


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _normalize_report(report: dict[str, Any]) -> dict[str, Any]:
    title = str(report.get("title") or "今日外部风险简报").strip() or "今日外部风险简报"
    briefing_text = str(report.get("briefing_text") or report.get("text") or "").strip()
    if not briefing_text:
        briefing_text = "简报已生成，但没有返回正文。"
    return {
        "workflow_run_id": str(report.get("workflow_run_id") or "").strip(),
        "title": title,
        "summary": str(report.get("summary") or "").strip(),
        "briefing_text": briefing_text,
        "report_images": _list_of_dicts(report.get("report_images")),
        "report_links": _list_of_dicts(report.get("report_links")),
        "tool_results": _list_of_dicts(report.get("tool_results")),
        "config": report.get("config") if isinstance(report.get("config"), dict) else {},
        "payload": report,
    }


def _row_to_report(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "report_id": int(row["report_id"]),
        "workflow_run_id": row["workflow_run_id"] or "",
        "title": row["title"] or "今日外部风险简报",
        "summary": row["summary"] or "",
        "briefing_text": row["briefing_text"] or "",
        "report_images": _json_loads(row["report_images_json"], []),
        "report_links": _json_loads(row["report_links_json"], []),
        "tool_results": _json_loads(row["tool_results_json"], []),
        "config": _json_loads(row["config_json"], {}),
        "payload": _json_loads(row["payload_json"], {}),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _json_loads(raw: str, fallback: Any) -> Any:
    try:
        return json.loads(raw)
    except Exception:  # noqa: BLE001
        return fallback


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
