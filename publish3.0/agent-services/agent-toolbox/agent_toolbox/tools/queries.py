from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from ..config import settings
from ..models import ToolFile, ToolResult
from ..tasks import new_task_id, task_dir, write_json


class SafetyCaseQueryRequest(BaseModel):
    status: str | None = None
    scene: str | None = None
    risk_level: str | None = None
    limit: int = Field(default=50, ge=1, le=500)


class ExternalRiskQueryRequest(BaseModel):
    source: str | None = None
    risk_level: str | None = None
    limit: int = Field(default=50, ge=1, le=500)


class FormRecordQueryRequest(BaseModel):
    template_id: str | None = None
    case_id: int | None = None
    limit: int = Field(default=50, ge=1, le=500)


class PendingActionQueryRequest(BaseModel):
    limit: int = Field(default=100, ge=1, le=500)


class DashboardMetricsRequest(BaseModel):
    include_samples: bool = True


class SafetyDataExportRequest(BaseModel):
    table: Literal["safety_cases", "external_risk_items", "form_records", "case_actions"] = "safety_cases"
    format: Literal["json", "csv"] = "json"
    limit: int = Field(default=500, ge=1, le=5000)


def query_safety_cases(req: SafetyCaseQueryRequest) -> ToolResult:
    rows = _select_rows(
        "safety_cases",
        filters={"status": req.status, "scene": req.scene, "risk_level": req.risk_level},
        order_by="updated_at DESC",
        limit=req.limit,
    )
    return ToolResult(ok=True, tool="query_safety_cases", summary=f"Returned {len(rows)} safety cases.", data={"items": rows})


def query_external_risks(req: ExternalRiskQueryRequest) -> ToolResult:
    rows = _select_rows(
        "external_risk_items",
        filters={"source": req.source, "risk_level": req.risk_level},
        order_by="last_seen_at DESC",
        limit=req.limit,
    )
    return ToolResult(ok=True, tool="query_external_risks", summary=f"Returned {len(rows)} external risks.", data={"items": rows})


def query_form_records(req: FormRecordQueryRequest) -> ToolResult:
    rows = _select_rows(
        "form_records",
        filters={"template_id": req.template_id, "case_id": req.case_id},
        order_by="created_at DESC",
        limit=req.limit,
    )
    return ToolResult(ok=True, tool="query_form_records", summary=f"Returned {len(rows)} form records.", data={"items": rows})


def query_pending_actions(req: PendingActionQueryRequest) -> ToolResult:
    statuses = ["candidate", "confirmed", "rectification_required", "in_progress", "pending_review"]
    if not _table_exists("safety_cases"):
        return ToolResult(ok=True, tool="query_pending_actions", summary="No safety_cases table found.", data={"items": []})
    placeholders = ",".join("?" for _ in statuses)
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM safety_cases WHERE status IN ({placeholders}) ORDER BY updated_at DESC LIMIT ?",
            (*statuses, req.limit),
        ).fetchall()
    return ToolResult(ok=True, tool="query_pending_actions", summary=f"Returned {len(rows)} pending actions.", data={"items": [_row(row) for row in rows]})


def get_dashboard_metrics(req: DashboardMetricsRequest) -> ToolResult:
    metrics = {
        "safety_cases_by_status": _count_group("safety_cases", "status"),
        "safety_cases_by_risk": _count_group("safety_cases", "risk_level"),
        "external_risks_by_risk": _count_group("external_risk_items", "risk_level"),
        "form_records_by_status": _count_group("form_records", "status"),
    }
    samples: dict[str, Any] = {}
    if req.include_samples:
        samples = {
            "recent_cases": query_safety_cases(SafetyCaseQueryRequest(limit=5)).data.get("items", []),
            "recent_external_risks": query_external_risks(ExternalRiskQueryRequest(limit=5)).data.get("items", []),
        }
    return ToolResult(ok=True, tool="get_dashboard_metrics", summary="Built dashboard metrics.", data={"metrics": metrics, "samples": samples})


def export_safety_data(req: SafetyDataExportRequest) -> ToolResult:
    rows = _select_rows(req.table, filters={}, order_by="id DESC", limit=req.limit)
    task_id = new_task_id("export")
    out_dir = task_dir(task_id)
    if req.format == "json":
        out_path = out_dir / f"{req.table}.json"
        write_json(out_path, rows)
        mime = "application/json"
    else:
        out_path = out_dir / f"{req.table}.csv"
        _write_csv(out_path, rows)
        mime = "text/csv"
    return ToolResult(
        ok=True,
        tool="export_safety_data",
        summary=f"Exported {len(rows)} rows from {req.table}.",
        task_id=task_id,
        files=[ToolFile(path=str(out_path), name=out_path.name, mime_type=mime)],
        data={"table": req.table, "format": req.format, "row_count": len(rows), "path": str(out_path)},
    )


def _select_rows(table: str, filters: dict[str, Any], order_by: str, limit: int) -> list[dict[str, Any]]:
    if not _table_exists(table):
        return []
    where = []
    params: list[Any] = []
    for key, value in filters.items():
        if value is None:
            continue
        where.append(f"{key} = ?")
        params.append(value)
    where_sql = f" WHERE {' AND '.join(where)}" if where else ""
    with _connect() as conn:
        rows = conn.execute(f"SELECT * FROM {table}{where_sql} ORDER BY {order_by} LIMIT ?", (*params, limit)).fetchall()
    return [_row(row) for row in rows]


def _count_group(table: str, column: str) -> dict[str, int]:
    if not _table_exists(table):
        return {}
    with _connect() as conn:
        rows = conn.execute(f"SELECT COALESCE({column}, 'unknown') AS key, COUNT(*) AS count FROM {table} GROUP BY {column}").fetchall()
    return {str(row["key"]): int(row["count"]) for row in rows}


def _table_exists(table: str) -> bool:
    with _connect() as conn:
        row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row is not None


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _row(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def _connect() -> sqlite3.Connection:
    path = settings.safety_database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn
