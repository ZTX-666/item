from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TABLE_NAME = "workbench_video_detection_results"
AUDIT_COLUMN_DEFINITIONS = {
    "user_question": "TEXT NOT NULL DEFAULT ''",
    "vlm_prompts_json": "TEXT NOT NULL DEFAULT '[]'",
    "vlm_raw_responses_json": "TEXT NOT NULL DEFAULT '[]'",
    "roi_images_json": "TEXT NOT NULL DEFAULT '[]'",
    "model_request_json": "TEXT NOT NULL DEFAULT '[]'",
    "model_response_json": "TEXT NOT NULL DEFAULT '[]'",
}


def default_video_detection_db_path(report_store_path: Path) -> Path:
    return report_store_path.with_name("video_detection_results.db")


def persist_video_detection_report(record: dict[str, Any], db_path: Path) -> dict[str, Any]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [_camera_row(record, camera) for camera in _camera_reports(record)]
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _ensure_schema(conn)
        if rows:
            _insert_rows(conn, rows)
        conn.commit()
    return {"db_path": str(db_path), "table": TABLE_NAME, "rows": len(rows)}


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            inserted_at TEXT NOT NULL,
            user_question TEXT NOT NULL DEFAULT '',
            direction TEXT NOT NULL,
            refined_prompt TEXT NOT NULL,
            prompt_source TEXT,
            policy_context_json TEXT NOT NULL,
            camera_id TEXT NOT NULL,
            camera_name TEXT,
            area TEXT,
            camera_count INTEGER NOT NULL DEFAULT 0,
            camera_ids_json TEXT NOT NULL,
            camera_names_json TEXT NOT NULL,
            patrol_id TEXT,
            success INTEGER NOT NULL DEFAULT 0,
            snapshot_path TEXT,
            snapshot_url TEXT,
            annotated_path TEXT,
            annotated_url TEXT,
            snapshot_source TEXT,
            fallback_used INTEGER NOT NULL DEFAULT 0,
            fallback_image TEXT,
            fallback_reason TEXT,
            source_mix TEXT,
            detection_count INTEGER NOT NULL DEFAULT 0,
            high_risk_count INTEGER NOT NULL DEFAULT 0,
            labels_json TEXT NOT NULL,
            detections_json TEXT NOT NULL,
            vlm_prompts_json TEXT NOT NULL DEFAULT '[]',
            vlm_raw_responses_json TEXT NOT NULL DEFAULT '[]',
            roi_images_json TEXT NOT NULL DEFAULT '[]',
            model_request_json TEXT NOT NULL DEFAULT '[]',
            model_response_json TEXT NOT NULL DEFAULT '[]',
            summary_title TEXT,
            summary_text TEXT,
            summary_severity TEXT,
            suggested_action TEXT,
            camera_summary_json TEXT NOT NULL,
            camera_report_json TEXT NOT NULL,
            patrol_report_json TEXT NOT NULL,
            patrol_reports_json TEXT NOT NULL,
            camera_errors_json TEXT NOT NULL,
            UNIQUE(report_id, camera_id)
        )
        """
    )
    _migrate_schema(conn)
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_report ON {TABLE_NAME}(report_id)")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_camera ON {TABLE_NAME}(camera_id)")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_created ON {TABLE_NAME}(created_at)")


def _migrate_schema(conn: sqlite3.Connection) -> None:
    existing = {str(row[1]) for row in conn.execute(f"PRAGMA table_info({TABLE_NAME})")}
    for column, definition in AUDIT_COLUMN_DEFINITIONS.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN {column} {definition}")


def _insert_rows(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    columns = list(rows[0].keys())
    placeholders = ", ".join("?" for _ in columns)
    updates = ", ".join(f"{column}=excluded.{column}" for column in columns if column not in {"report_id", "camera_id"})
    sql = (
        f"INSERT INTO {TABLE_NAME} ({', '.join(columns)}) VALUES ({placeholders}) "
        f"ON CONFLICT(report_id, camera_id) DO UPDATE SET {updates}"
    )
    conn.executemany(sql, [[row[column] for column in columns] for row in rows])


def _camera_reports(record: dict[str, Any]) -> list[dict[str, Any]]:
    cameras = record.get("cameras")
    return [camera for camera in cameras if isinstance(camera, dict)] if isinstance(cameras, list) else []


def _camera_row(record: dict[str, Any], camera: dict[str, Any]) -> dict[str, Any]:
    detections = [item for item in camera.get("detections", []) if isinstance(item, dict)]
    labels = _labels(camera, detections)
    summary = camera.get("summary") if isinstance(camera.get("summary"), dict) else {}
    camera_id = str(camera.get("camera_id") or "")
    return {
        "report_id": _text(record.get("report_id")),
        "created_at": _text(record.get("created_at")),
        "inserted_at": datetime.now(timezone.utc).isoformat(),
        "user_question": _text(record.get("user_question") or record.get("direction")),
        "direction": _text(record.get("direction")),
        "refined_prompt": _text(record.get("refined_prompt")),
        "prompt_source": _text(record.get("prompt_source")),
        "policy_context_json": _json(record.get("policy_context", [])),
        "camera_id": camera_id,
        "camera_name": _text(camera.get("camera_name") or camera.get("name") or camera_id),
        "area": _text(camera.get("area") or record.get("area")),
        "camera_count": int(record.get("camera_count") or len(_camera_reports(record))),
        "camera_ids_json": _json(record.get("camera_ids", [])),
        "camera_names_json": _json(record.get("camera_names", [])),
        "patrol_id": _text(camera.get("patrol_id") or record.get("patrol_id")),
        "success": 1 if camera.get("success", True) else 0,
        "snapshot_path": _text(camera.get("snapshot_path")),
        "snapshot_url": _text(camera.get("snapshot_url")),
        "annotated_path": _text(camera.get("annotated_path")),
        "annotated_url": _text(camera.get("annotated_url")),
        "snapshot_source": _text(camera.get("snapshot_source")),
        "fallback_used": 1 if camera.get("fallback_used") else 0,
        "fallback_image": _text(camera.get("fallback_image")),
        "fallback_reason": _text(camera.get("fallback_reason")),
        "source_mix": _text(camera.get("source_mix")),
        "detection_count": len(detections),
        "high_risk_count": _high_risk_count(detections),
        "labels_json": _json(labels),
        "detections_json": _json(detections),
        "vlm_prompts_json": _json(_vlm_prompts(camera, detections)),
        "vlm_raw_responses_json": _json(_vlm_raw_responses(camera, detections)),
        "roi_images_json": _json(_audit_records(camera, detections, "roi_images", "roi_image")),
        "model_request_json": _json(_audit_records(camera, detections, "model_requests", "model_request")),
        "model_response_json": _json(_audit_records(camera, detections, "model_responses", "model_response")),
        "summary_title": _text(summary.get("title")),
        "summary_text": _text(summary.get("text")),
        "summary_severity": _text(summary.get("severity")),
        "suggested_action": _text(summary.get("suggested_action")),
        "camera_summary_json": _json(summary),
        "camera_report_json": _json(camera),
        "patrol_report_json": _json(record.get("patrol_report", {})),
        "patrol_reports_json": _json(record.get("patrol_reports", [])),
        "camera_errors_json": _json(record.get("camera_errors", [])),
    }


def _vlm_prompts(camera: dict[str, Any], detections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    explicit = camera.get("vlm_prompts")
    if isinstance(explicit, list):
        return [item for item in explicit if isinstance(item, dict)]

    records: list[dict[str, Any]] = []
    for index, detection in enumerate(detections):
        audit = detection.get("vlm_audit") if isinstance(detection.get("vlm_audit"), dict) else {}
        if not audit:
            continue
        records.append(
            {
                "detection_index": index,
                "label": detection.get("label", ""),
                "bbox": detection.get("bbox", []),
                "prompt": audit.get("prompt", ""),
                "messages": audit.get("messages", []),
            }
        )
    return records


def _vlm_raw_responses(camera: dict[str, Any], detections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    explicit = camera.get("vlm_raw_responses")
    if isinstance(explicit, list):
        return [item for item in explicit if isinstance(item, dict)]

    records: list[dict[str, Any]] = []
    for index, detection in enumerate(detections):
        audit = detection.get("vlm_audit") if isinstance(detection.get("vlm_audit"), dict) else {}
        if not audit:
            continue
        records.append(
            {
                "detection_index": index,
                "label": detection.get("label", ""),
                "bbox": detection.get("bbox", []),
                "raw_response": audit.get("raw_response", ""),
            }
        )
    return records


def _audit_records(
    camera: dict[str, Any],
    detections: list[dict[str, Any]],
    camera_key: str,
    audit_key: str,
) -> list[dict[str, Any]]:
    explicit = camera.get(camera_key)
    if isinstance(explicit, list):
        return [item for item in explicit if isinstance(item, dict)]

    records: list[dict[str, Any]] = []
    for index, detection in enumerate(detections):
        audit = detection.get("vlm_audit") if isinstance(detection.get("vlm_audit"), dict) else {}
        if not audit or audit_key not in audit:
            continue
        records.append(
            {
                "detection_index": index,
                "label": detection.get("label", ""),
                "bbox": detection.get("bbox", []),
                audit_key: audit[audit_key],
            }
        )
    return records


def _labels(camera: dict[str, Any], detections: list[dict[str, Any]]) -> list[str]:
    summary = camera.get("summary") if isinstance(camera.get("summary"), dict) else {}
    summary_labels = summary.get("labels") if isinstance(summary.get("labels"), list) else []
    if summary_labels:
        return [str(label) for label in summary_labels if str(label).strip()]
    return sorted({str(item.get("label")) for item in detections if item.get("label")})


def _high_risk_count(detections: list[dict[str, Any]]) -> int:
    return sum(1 for item in detections if str(item.get("severity") or "").lower() in {"high", "critical"})


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
