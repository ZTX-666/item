from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from chitung_center import storage


DEFAULT_SETTINGS = {
    "enabled": True,
    "interval_minutes": 60,
    "sources": ["weather", "official", "media"],
    "keywords": ["施工安全", "天气预警", "工伤意外"],
    "area": "香港项目",
    "delivery_mode": "draft",
    "recipient": "",
    "alert_p0": True,
    "alert_p1": True,
    "lookback_hours": 24,
}


def _db_path() -> Path:
    value = os.getenv("SAFETY_DATABASE_PATH")
    if value:
        return Path(value)
    return storage.database_path()


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def ensure_schema() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS external_monitor_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                enabled INTEGER NOT NULL DEFAULT 1,
                interval_minutes INTEGER NOT NULL DEFAULT 60,
                sources_json TEXT NOT NULL DEFAULT '["weather","official","media"]',
                keywords_json TEXT NOT NULL DEFAULT '["施工安全","天气预警","工伤意外"]',
                area TEXT NOT NULL DEFAULT '香港项目',
                delivery_mode TEXT NOT NULL DEFAULT 'draft',
                recipient TEXT DEFAULT '',
                alert_p0 INTEGER NOT NULL DEFAULT 1,
                alert_p1 INTEGER NOT NULL DEFAULT 1,
                lookback_hours INTEGER NOT NULL DEFAULT 24,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS external_monitor_runs (
                run_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                duration_ms INTEGER DEFAULT 0,
                workflow_run_id TEXT,
                card_count INTEGER DEFAULT 0,
                new_raw_count INTEGER DEFAULT 0,
                new_event_count INTEGER DEFAULT 0,
                duplicate_count INTEGER DEFAULT 0,
                alert_count INTEGER DEFAULT 0,
                source_count INTEGER DEFAULT 0,
                error TEXT,
                summary_json TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS external_source_state (
                source_key TEXT PRIMARY KEY,
                source_name TEXT,
                source_type TEXT,
                last_seen_at TEXT,
                last_success_at TEXT,
                last_error_at TEXT,
                last_error TEXT,
                failure_count INTEGER DEFAULT 0,
                cooldown_until TEXT,
                etag TEXT,
                last_modified TEXT,
                last_status_code INTEGER,
                last_item_count INTEGER DEFAULT 0,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS external_raw_items (
                raw_id TEXT PRIMARY KEY,
                item_key TEXT UNIQUE NOT NULL,
                source_key TEXT NOT NULL,
                source_name TEXT,
                source_type TEXT,
                source_url TEXT,
                external_id TEXT,
                title TEXT NOT NULL,
                summary TEXT,
                content_text TEXT,
                published_at TEXT,
                normalized_title TEXT NOT NULL,
                normalized_title_hash TEXT NOT NULL,
                risk_level TEXT,
                priority TEXT,
                matched_keywords_json TEXT DEFAULT '[]',
                payload_json TEXT DEFAULT '{}',
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS external_events (
                event_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                normalized_title TEXT NOT NULL,
                event_hash TEXT UNIQUE NOT NULL,
                priority TEXT NOT NULL DEFAULT 'P2',
                risk_score INTEGER DEFAULT 0,
                relevance_score INTEGER DEFAULT 0,
                confidence REAL DEFAULT 0.0,
                source_count INTEGER DEFAULT 1,
                recommended_action TEXT,
                reason_codes_json TEXT DEFAULT '[]',
                requires_human_review INTEGER DEFAULT 0,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS external_event_sources (
                event_id TEXT NOT NULL,
                raw_id TEXT NOT NULL,
                source_key TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (event_id, raw_id)
            );

            CREATE INDEX IF NOT EXISTS idx_external_raw_source ON external_raw_items(source_key);
            CREATE INDEX IF NOT EXISTS idx_external_raw_seen ON external_raw_items(last_seen_at);
            CREATE INDEX IF NOT EXISTS idx_external_events_priority ON external_events(priority);
            CREATE INDEX IF NOT EXISTS idx_external_events_seen ON external_events(last_seen_at);
            """
        )
        _ensure_column(conn, "external_monitor_settings", "lookback_hours", "INTEGER NOT NULL DEFAULT 24")
        now = _now_iso()
        conn.execute(
            """
            INSERT OR IGNORE INTO external_monitor_settings
            (id, enabled, interval_minutes, sources_json, keywords_json, area, delivery_mode, recipient, alert_p0, alert_p1, lookback_hours, updated_at)
            VALUES (1, 1, 60, ?, ?, ?, 'draft', '', 1, 1, 24, ?)
            """,
            (
                json.dumps(DEFAULT_SETTINGS["sources"], ensure_ascii=False),
                json.dumps(DEFAULT_SETTINGS["keywords"], ensure_ascii=False),
                DEFAULT_SETTINGS["area"],
                now,
            ),
        )


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def get_settings() -> dict[str, Any]:
    ensure_schema()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM external_monitor_settings WHERE id = 1").fetchone()
    if not row:
        return DEFAULT_SETTINGS.copy()
    return {
        "enabled": bool(row["enabled"]),
        "interval_minutes": int(row["interval_minutes"] or 60),
        "sources": _json_loads(row["sources_json"], DEFAULT_SETTINGS["sources"]),
        "keywords": _json_loads(row["keywords_json"], DEFAULT_SETTINGS["keywords"]),
        "area": row["area"] or DEFAULT_SETTINGS["area"],
        "delivery_mode": row["delivery_mode"] or "draft",
        "recipient": row["recipient"] or "",
        "alert_p0": bool(row["alert_p0"]),
        "alert_p1": bool(row["alert_p1"]),
        "lookback_hours": int(row["lookback_hours"] or DEFAULT_SETTINGS["lookback_hours"]),
        "updated_at": row["updated_at"],
    }


def save_settings(settings: dict[str, Any]) -> dict[str, Any]:
    ensure_schema()
    current = get_settings()
    merged = {**current, **{key: value for key, value in settings.items() if value is not None}}
    merged["enabled"] = bool(merged.get("enabled", True))
    merged["interval_minutes"] = max(5, min(int(merged.get("interval_minutes") or 60), 24 * 60))
    merged["sources"] = _clean_list(merged.get("sources"), DEFAULT_SETTINGS["sources"])
    merged["keywords"] = _clean_list(merged.get("keywords"), DEFAULT_SETTINGS["keywords"])
    merged["area"] = str(merged.get("area") or DEFAULT_SETTINGS["area"]).strip() or DEFAULT_SETTINGS["area"]
    merged["delivery_mode"] = str(merged.get("delivery_mode") or "draft")
    merged["recipient"] = str(merged.get("recipient") or "")
    merged["alert_p0"] = bool(merged.get("alert_p0", True))
    merged["alert_p1"] = bool(merged.get("alert_p1", True))
    merged["lookback_hours"] = max(1, min(int(merged.get("lookback_hours") or 24), 24 * 30))
    now = _now_iso()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE external_monitor_settings SET
                enabled = ?, interval_minutes = ?, sources_json = ?, keywords_json = ?,
                area = ?, delivery_mode = ?, recipient = ?, alert_p0 = ?, alert_p1 = ?,
                lookback_hours = ?, updated_at = ?
            WHERE id = 1
            """,
            (
                int(merged["enabled"]),
                merged["interval_minutes"],
                json.dumps(merged["sources"], ensure_ascii=False),
                json.dumps(merged["keywords"], ensure_ascii=False),
                merged["area"],
                merged["delivery_mode"],
                merged["recipient"],
                int(merged["alert_p0"]),
                int(merged["alert_p1"]),
                merged["lookback_hours"],
                now,
            ),
        )
    return get_settings()


def create_run() -> dict[str, Any]:
    ensure_schema()
    now = _now_iso()
    run_id = f"monitor-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO external_monitor_runs (run_id, status, started_at, created_at, updated_at)
            VALUES (?, 'running', ?, ?, ?)
            """,
            (run_id, now, now, now),
        )
    return {"run_id": run_id, "status": "running", "started_at": now}


def finish_run(run_id: str, *, status: str, workflow_run_id: str | None = None, summary: dict[str, Any] | None = None, error: str | None = None) -> dict[str, Any]:
    ensure_schema()
    now = _now_iso()
    summary = summary or {}
    with _connect() as conn:
        row = conn.execute("SELECT started_at FROM external_monitor_runs WHERE run_id = ?", (run_id,)).fetchone()
        started_at = row["started_at"] if row else now
        duration_ms = max(0, int((datetime.fromisoformat(now) - datetime.fromisoformat(started_at)).total_seconds() * 1000))
        conn.execute(
            """
            UPDATE external_monitor_runs SET
                status = ?, finished_at = ?, duration_ms = ?, workflow_run_id = ?,
                card_count = ?, new_raw_count = ?, new_event_count = ?, duplicate_count = ?,
                alert_count = ?, source_count = ?, error = ?, summary_json = ?, updated_at = ?
            WHERE run_id = ?
            """,
            (
                status,
                now,
                duration_ms,
                workflow_run_id,
                int(summary.get("card_count", 0)),
                int(summary.get("new_raw_count", 0)),
                int(summary.get("new_event_count", 0)),
                int(summary.get("duplicate_count", 0)),
                int(summary.get("alert_count", 0)),
                int(summary.get("source_count", 0)),
                error,
                json.dumps(summary, ensure_ascii=False, default=str),
                now,
                run_id,
            ),
        )
    return get_run(run_id) or {"run_id": run_id, "status": status}


def get_run(run_id: str) -> dict[str, Any] | None:
    ensure_schema()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM external_monitor_runs WHERE run_id = ?", (run_id,)).fetchone()
    return _row_to_run(row) if row else None


def list_runs(limit: int = 20) -> dict[str, Any]:
    ensure_schema()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM external_monitor_runs ORDER BY datetime(started_at) DESC LIMIT ?",
            (max(1, min(limit, 200)),),
        ).fetchall()
    return {"ok": True, "items": [_row_to_run(row) for row in rows]}


def get_source_states() -> dict[str, Any]:
    ensure_schema()
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM external_source_state ORDER BY source_key").fetchall()
    return {"ok": True, "items": [_row_to_source(row) for row in rows]}


def get_last_success_run() -> dict[str, Any] | None:
    ensure_schema()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM external_monitor_runs WHERE status = 'success' ORDER BY datetime(started_at) DESC LIMIT 1"
        ).fetchone()
    return _row_to_run(row) if row else None


def get_last_run() -> dict[str, Any] | None:
    ensure_schema()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM external_monitor_runs ORDER BY datetime(started_at) DESC LIMIT 1").fetchone()
    return _row_to_run(row) if row else None


def ingest_workflow_result(run_id: str, result: dict[str, Any], lookback_hours: int | None = None) -> dict[str, Any]:
    ensure_schema()
    cards = _extract_cards(result)
    source_items = _extract_source_items(result)
    if not source_items:
        source_items = [_item_from_card(card) for card in cards]
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max(1, int(lookback_hours or 24)))
    source_items = [item for item in source_items if _is_in_lookback(item, cutoff)]

    new_raw = 0
    updated_raw = 0
    new_events = 0
    duplicate_events = 0
    new_event_ids: list[str] = []
    new_alert_cards: list[dict[str, Any]] = []
    now = _now_iso()

    with _connect() as conn:
        for item in source_items:
            normalized = _normalize_title(str(item.get("title") or "未命名讯息"))
            if not normalized:
                continue
            item_key = _item_key(item, normalized)
            raw_id = hashlib.sha1(item_key.encode("utf-8")).hexdigest()[:24]
            existing = conn.execute("SELECT raw_id FROM external_raw_items WHERE item_key = ?", (item_key,)).fetchone()
            payload = item.get("payload") if isinstance(item.get("payload"), dict) else item
            values = (
                raw_id,
                item_key,
                str(item.get("source") or item.get("source_key") or item.get("source_category") or "external"),
                str(item.get("source_name") or item.get("source") or "外部来源"),
                str(item.get("source_type") or item.get("source_category") or "external"),
                item.get("url") or item.get("source_url"),
                item.get("external_id"),
                str(item.get("title") or "未命名讯息"),
                item.get("short_summary") or item.get("summary"),
                item.get("content_text"),
                item.get("published_at") or item.get("event_date"),
                normalized,
                hashlib.sha1(normalized.encode("utf-8")).hexdigest(),
                item.get("risk_level"),
                item.get("priority") or _priority_for_level(str(item.get("risk_level") or "")),
                json.dumps(item.get("matched_keywords") or item.get("keywords") or [], ensure_ascii=False),
                json.dumps(payload, ensure_ascii=False, default=str),
                now,
                now,
                now,
                now,
            )
            conn.execute(
                """
                INSERT INTO external_raw_items (
                    raw_id, item_key, source_key, source_name, source_type, source_url, external_id,
                    title, summary, content_text, published_at, normalized_title, normalized_title_hash,
                    risk_level, priority, matched_keywords_json, payload_json, first_seen_at, last_seen_at,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(item_key) DO UPDATE SET
                    summary = excluded.summary,
                    content_text = excluded.content_text,
                    risk_level = excluded.risk_level,
                    priority = excluded.priority,
                    matched_keywords_json = excluded.matched_keywords_json,
                    payload_json = excluded.payload_json,
                    last_seen_at = excluded.last_seen_at,
                    updated_at = excluded.updated_at
                """,
                values,
            )
            if existing:
                updated_raw += 1
            else:
                new_raw += 1

            event = _event_from_item(item, normalized, now)
            event_row = conn.execute("SELECT event_id, source_count FROM external_events WHERE event_hash = ?", (event["event_hash"],)).fetchone()
            if event_row:
                event_id = event_row["event_id"]
                conn.execute(
                    """
                    UPDATE external_events SET
                        priority = ?, risk_score = MAX(risk_score, ?), relevance_score = MAX(relevance_score, ?),
                        confidence = MAX(confidence, ?), source_count = source_count + ?,
                        recommended_action = COALESCE(recommended_action, ?),
                        reason_codes_json = ?, last_seen_at = ?, updated_at = ?
                    WHERE event_id = ?
                    """,
                    (
                        event["priority"],
                        event["risk_score"],
                        event["relevance_score"],
                        event["confidence"],
                        0 if existing else 1,
                        event["recommended_action"],
                        json.dumps(event["reason_codes"], ensure_ascii=False),
                        now,
                        now,
                        event_id,
                    ),
                )
                duplicate_events += 1
            else:
                event_id = uuid.uuid4().hex[:16]
                conn.execute(
                    """
                    INSERT INTO external_events (
                        event_id, title, normalized_title, event_hash, priority, risk_score, relevance_score,
                        confidence, source_count, recommended_action, reason_codes_json, requires_human_review,
                        first_seen_at, last_seen_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        event["title"],
                        normalized,
                        event["event_hash"],
                        event["priority"],
                        event["risk_score"],
                        event["relevance_score"],
                        event["confidence"],
                        1,
                        event["recommended_action"],
                        json.dumps(event["reason_codes"], ensure_ascii=False),
                        int(event["requires_human_review"]),
                        now,
                        now,
                        now,
                        now,
                    ),
                )
                new_events += 1
                new_event_ids.append(event_id)
                new_card = _card_for_event_card(cards, item, event_id)
                if new_card:
                    new_alert_cards.append(new_card)

            conn.execute(
                """
                INSERT OR IGNORE INTO external_event_sources (event_id, raw_id, source_key, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (event_id, raw_id, str(item.get("source") or item.get("source_key") or item.get("source_category") or "external"), now),
            )

        _update_source_states(conn, source_items, result, now)

    return {
        "card_count": len(cards),
        "new_raw_count": new_raw,
        "updated_raw_count": updated_raw,
        "new_event_count": new_events,
        "duplicate_count": updated_raw + duplicate_events,
        "source_count": len({str(item.get("source") or item.get("source_key") or item.get("source_category") or "external") for item in source_items}),
        "cards": cards,
        "new_event_ids": new_event_ids,
        "new_alert_cards": new_alert_cards,
        "lookback_hours": max(1, int(lookback_hours or 24)),
    }


def list_events(limit: int = 50, lookback_hours: int | None = None) -> dict[str, Any]:
    ensure_schema()
    with _connect() as conn:
        if lookback_hours:
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=max(1, int(lookback_hours)))).isoformat()
            rows = conn.execute(
                """
                SELECT * FROM external_events
                WHERE datetime(last_seen_at) >= datetime(?)
                ORDER BY datetime(last_seen_at) DESC LIMIT ?
                """,
                (cutoff, max(1, min(limit, 200))),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM external_events ORDER BY datetime(last_seen_at) DESC LIMIT ?",
                (max(1, min(limit, 200)),),
            ).fetchall()
    return {"ok": True, "items": [_row_to_event(row) for row in rows]}


def next_run_at(settings: dict[str, Any] | None = None, last_run: dict[str, Any] | None = None) -> str | None:
    settings = settings or get_settings()
    if not settings.get("enabled", True):
        return None
    last_run = last_run or get_last_run()
    base = datetime.now(timezone.utc)
    if last_run and last_run.get("started_at"):
        try:
            base = datetime.fromisoformat(str(last_run["started_at"]))
        except ValueError:
            base = datetime.now(timezone.utc)
    return (base + timedelta(minutes=int(settings.get("interval_minutes") or 60))).isoformat()


def _update_source_states(conn: sqlite3.Connection, items: list[dict[str, Any]], result: dict[str, Any], now: str) -> None:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        key = str(item.get("source") or item.get("source_key") or item.get("source_category") or "external")
        grouped.setdefault(key, []).append(item)
    for key, source_items in grouped.items():
        sample = source_items[0]
        conn.execute(
            """
            INSERT INTO external_source_state (
                source_key, source_name, source_type, last_seen_at, last_success_at, failure_count,
                last_item_count, updated_at
            ) VALUES (?, ?, ?, ?, ?, 0, ?, ?)
            ON CONFLICT(source_key) DO UPDATE SET
                source_name = excluded.source_name,
                source_type = excluded.source_type,
                last_seen_at = excluded.last_seen_at,
                last_success_at = excluded.last_success_at,
                failure_count = 0,
                last_error = NULL,
                last_item_count = excluded.last_item_count,
                updated_at = excluded.updated_at
            """,
            (
                key,
                str(sample.get("source_name") or key),
                str(sample.get("source_type") or sample.get("source_category") or "external"),
                now,
                now,
                len(source_items),
                now,
            ),
        )
    for err in _extract_errors(result):
        key = err.split(":", 1)[0] if ":" in err else "unknown"
        conn.execute(
            """
            INSERT INTO external_source_state (source_key, source_name, source_type, last_error_at, last_error, failure_count, updated_at)
            VALUES (?, ?, 'external', ?, ?, 1, ?)
            ON CONFLICT(source_key) DO UPDATE SET
                last_error_at = excluded.last_error_at,
                last_error = excluded.last_error,
                failure_count = failure_count + 1,
                cooldown_until = CASE WHEN failure_count + 1 >= 3 THEN ? ELSE cooldown_until END,
                updated_at = excluded.updated_at
            """,
            (key, key, now, err[:500], now, (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()),
        )


def _extract_cards(result: dict[str, Any]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for tool_result in result.get("tool_results") or []:
        if isinstance(tool_result, dict) and isinstance(tool_result.get("cards"), list):
            cards.extend(card for card in tool_result["cards"] if isinstance(card, dict))
    return cards


def _extract_source_items(result: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for tool_result in result.get("tool_results") or []:
        if not isinstance(tool_result, dict):
            continue
        if tool_result.get("source") in {"hk_safety_updates", "hk_industrial_news"}:
            items.extend(item for item in tool_result.get("items") or [] if isinstance(item, dict))
        if tool_result.get("source") == "draft_daily_risk_briefing":
            items.extend(_item_from_card(card) for card in tool_result.get("cards") or [] if isinstance(card, dict))
    return items


def _extract_errors(result: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for tool_result in result.get("tool_results") or []:
        if isinstance(tool_result, dict):
            errors.extend(str(item) for item in tool_result.get("errors") or [])
            if tool_result.get("error"):
                errors.append(str(tool_result["error"]))
    return errors


def _item_from_card(card: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": card.get("source_category") or "external",
        "source_name": card.get("source_name") or "外部来源",
        "source_type": card.get("source_category") or "external",
        "title": card.get("title") or "未命名讯息",
        "url": card.get("source_url"),
        "short_summary": card.get("summary"),
        "matched_keywords": card.get("keywords") or [],
        "risk_level": card.get("risk_level"),
        "priority": card.get("priority"),
        "published_at": card.get("event_date"),
        "payload": card.get("payload") or card,
    }


def _event_from_item(item: dict[str, Any], normalized: str, now: str) -> dict[str, Any]:
    priority = str(item.get("priority") or _priority_for_level(str(item.get("risk_level") or "")))
    text = f"{item.get('title', '')} {item.get('short_summary', '')} {' '.join(item.get('matched_keywords') or item.get('keywords') or [])}"
    reason_codes: list[str] = []
    if str(item.get("source_type") or "").startswith("official") or str(item.get("source_category") or "") == "official":
        reason_codes.append("official_source")
    if any(token in text for token in ["死亡", "不治", "壓斃", "压毙", "墮下", "堕下", "吊運", "吊运", "密閉空間", "密闭空间"]):
        reason_codes.append("critical_safety_keyword")
    if any(token in text for token in ["暴雨", "酷熱", "酷热", "雷暴", "台风", "熱帶氣旋"]):
        reason_codes.append("weather_exposure")
    if priority == "P0":
        risk_score = 90
    elif priority == "P1":
        risk_score = 72
    else:
        risk_score = 45
    risk_score += min(len(reason_codes) * 5, 15)
    relevance_score = 55 + (10 if "official_source" in reason_codes else 0) + (10 if reason_codes else 0)
    return {
        "title": str(item.get("title") or "未命名讯息"),
        "event_hash": hashlib.sha1(normalized[:80].encode("utf-8")).hexdigest(),
        "priority": "P0" if risk_score >= 90 else ("P1" if risk_score >= 70 else "P2"),
        "risk_score": min(risk_score, 100),
        "relevance_score": min(relevance_score, 100),
        "confidence": 0.86 if reason_codes else 0.62,
        "reason_codes": reason_codes or ["keyword_match"],
        "recommended_action": _recommended_action(priority, text),
        "requires_human_review": priority in {"P0", "P1"} or "critical_safety_keyword" in reason_codes,
        "last_seen_at": now,
    }


def _recommended_action(priority: str, text: str) -> str:
    if "酷熱" in text or "酷热" in text:
        return "检查热压力安排、饮水休息点和户外高风险工序。"
    if "暴雨" in text or "雷暴" in text:
        return "检查排水、临电防水、斜坡基坑和高处作业安排。"
    if priority == "P0":
        return "立即通知安全负责人复核，并评估是否需要暂停相关高风险工序。"
    if priority == "P1":
        return "纳入今日巡检重点，并向相关分判商发出安全提示。"
    return "纳入每日简报，持续观察。"


def _priority_for_level(level: str) -> str:
    if level == "critical":
        return "P0"
    if level == "high":
        return "P1"
    return "P2"


def _item_key(item: dict[str, Any], normalized: str) -> str:
    source = str(item.get("source") or item.get("source_key") or item.get("source_category") or "")
    external_id = str(item.get("external_id") or "")
    url = str(item.get("url") or item.get("source_url") or "")
    basis = "|".join([source, external_id or url or normalized])
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()


def _normalize_title(value: str) -> str:
    text = re.sub(r"\s+", "", value.lower())
    text = re.sub(r"[^\w\u4e00-\u9fff]", "", text)
    return text[:160]


def _clean_list(value: Any, fallback: list[str]) -> list[str]:
    if not isinstance(value, list):
        return fallback.copy()
    cleaned = [str(item).strip() for item in value if str(item).strip()]
    return list(dict.fromkeys(cleaned)) or fallback.copy()


def _json_loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _row_to_run(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "run_id": row["run_id"],
        "status": row["status"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "duration_ms": row["duration_ms"],
        "workflow_run_id": row["workflow_run_id"],
        "card_count": row["card_count"],
        "new_raw_count": row["new_raw_count"],
        "new_event_count": row["new_event_count"],
        "duplicate_count": row["duplicate_count"],
        "alert_count": row["alert_count"],
        "source_count": row["source_count"],
        "error": row["error"],
        "summary": _json_loads(row["summary_json"], {}),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _row_to_source(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "source_key": row["source_key"],
        "source_name": row["source_name"],
        "source_type": row["source_type"],
        "last_seen_at": row["last_seen_at"],
        "last_success_at": row["last_success_at"],
        "last_error_at": row["last_error_at"],
        "last_error": row["last_error"],
        "failure_count": row["failure_count"],
        "cooldown_until": row["cooldown_until"],
        "etag": row["etag"],
        "last_modified": row["last_modified"],
        "last_status_code": row["last_status_code"],
        "last_item_count": row["last_item_count"],
        "updated_at": row["updated_at"],
    }


def _row_to_event(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "event_id": row["event_id"],
        "title": row["title"],
        "normalized_title": row["normalized_title"],
        "priority": row["priority"],
        "risk_score": row["risk_score"],
        "relevance_score": row["relevance_score"],
        "confidence": row["confidence"],
        "source_count": row["source_count"],
        "recommended_action": row["recommended_action"],
        "reason_codes": _json_loads(row["reason_codes_json"], []),
        "requires_human_review": bool(row["requires_human_review"]),
        "first_seen_at": row["first_seen_at"],
        "last_seen_at": row["last_seen_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _is_in_lookback(item: dict[str, Any], cutoff: datetime) -> bool:
    published = item.get("published_at") or item.get("event_date") or item.get("created_at")
    parsed = _parse_datetime(published)
    if parsed is None:
        return True
    return parsed >= cutoff


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _card_for_event_card(cards: list[dict[str, Any]], item: dict[str, Any], event_id: str) -> dict[str, Any] | None:
    target = _normalize_title(str(item.get("title") or ""))
    for card in cards:
        if _normalize_title(str(card.get("title") or "")) == target:
            return {**card, "event_id": event_id, "is_new_event": True}
    if item:
        return {
            "event_id": event_id,
            "is_new_event": True,
            "title": item.get("title") or "未命名讯息",
            "summary": item.get("summary") or item.get("short_summary"),
            "priority": item.get("priority") or _priority_for_level(str(item.get("risk_level") or "")),
            "recommended_action": item.get("recommended_action") or "请安全负责人复核该外部讯息。",
            "source_category": item.get("source_category") or item.get("source_type") or "external",
        }
    return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
