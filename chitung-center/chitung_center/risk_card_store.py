"""Risk card persistence layer for the external risk monitoring module.

Stores structured risk cards generated from weather warnings, official
announcements, and media reports.  Shares the same SQLite database as
``external_briefing_store`` and ``external_risk``.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from chitung_center import storage


TABLE_NAME = "risk_cards"


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _db_path() -> Path:
    """Return the path to the shared safety platform database.

    Mirrors the logic in ``external_briefing_store.default_db_path`` so both
    modules always operate on the same file.
    """
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


def _ensure_schema() -> None:
    """Create the ``risk_cards`` table and indexes if they do not exist."""
    with _connect() as conn:
        conn.executescript(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id TEXT UNIQUE NOT NULL,
                report_id TEXT,
                source_category TEXT NOT NULL,
                source_name TEXT NOT NULL,
                source_url TEXT,
                title TEXT NOT NULL,
                summary TEXT,
                priority TEXT NOT NULL,
                risk_level TEXT,
                emoji_tag TEXT NOT NULL DEFAULT '\U0001F4F0',
                keywords_json TEXT DEFAULT '[]',
                location TEXT,
                event_date TEXT,
                recommended_action TEXT,
                is_confirmed INTEGER DEFAULT 1,
                payload_json TEXT DEFAULT '{{}}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_risk_cards_category
                ON {TABLE_NAME}(source_category);
            CREATE INDEX IF NOT EXISTS idx_risk_cards_priority
                ON {TABLE_NAME}(priority);
            CREATE INDEX IF NOT EXISTS idx_risk_cards_report
                ON {TABLE_NAME}(report_id);
            CREATE INDEX IF NOT EXISTS idx_risk_cards_created
                ON {TABLE_NAME}(created_at);
            """
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def persist_risk_cards(
    cards: list[dict[str, Any]],
    report_id: str | None = None,
) -> dict[str, Any]:
    """Batch-insert or update risk cards.

    Cards are de-duplicated on ``(source_category, title, source_url)``.
    When a match is found the existing row is updated; otherwise a new row
    is inserted.

    Returns ``{"persisted": N, "updated": N}``.
    """
    _ensure_schema()
    persisted = 0
    updated = 0
    now = _now_iso()

    with _connect() as conn:
        for card in cards:
            card_id = card.get("card_id") or uuid.uuid4().hex[:12]
            source_category = card.get("source_category", "media")
            source_name = card.get("source_name", "")
            source_url = card.get("source_url") or ""
            title = card.get("title", "")
            keywords = card.get("keywords", card.get("keywords_json", []))
            payload = card.get("payload", card.get("payload_json", {}))
            effective_report_id = report_id or card.get("report_id")

            existing = conn.execute(
                f"SELECT id FROM {TABLE_NAME} "
                "WHERE source_category = ? AND title = ? AND COALESCE(source_url, '') = ?",
                (source_category, title, source_url),
            ).fetchone()

            if existing:
                conn.execute(
                    f"""
                    UPDATE {TABLE_NAME} SET
                        card_id = ?,
                        report_id = ?,
                        source_name = ?,
                        summary = ?,
                        priority = ?,
                        risk_level = ?,
                        emoji_tag = ?,
                        keywords_json = ?,
                        location = ?,
                        event_date = ?,
                        recommended_action = ?,
                        is_confirmed = ?,
                        payload_json = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        card_id,
                        effective_report_id,
                        source_name,
                        card.get("summary"),
                        card.get("priority", "P2"),
                        card.get("risk_level"),
                        card.get("emoji_tag", "\U0001F4F0"),
                        json.dumps(keywords, ensure_ascii=False),
                        card.get("location"),
                        card.get("event_date"),
                        card.get("recommended_action"),
                        int(card.get("is_confirmed", 1)),
                        json.dumps(payload, ensure_ascii=False, default=str),
                        now,
                        existing["id"],
                    ),
                )
                updated += 1
            else:
                conn.execute(
                    f"""
                    INSERT INTO {TABLE_NAME} (
                        card_id, report_id, source_category, source_name, source_url,
                        title, summary, priority, risk_level, emoji_tag,
                        keywords_json, location, event_date, recommended_action,
                        is_confirmed, payload_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        card_id,
                        effective_report_id,
                        source_category,
                        source_name,
                        source_url or None,
                        title,
                        card.get("summary"),
                        card.get("priority", "P2"),
                        card.get("risk_level"),
                        card.get("emoji_tag", "\U0001F4F0"),
                        json.dumps(keywords, ensure_ascii=False),
                        card.get("location"),
                        card.get("event_date"),
                        card.get("recommended_action"),
                        int(card.get("is_confirmed", 1)),
                        json.dumps(payload, ensure_ascii=False, default=str),
                        now,
                        now,
                    ),
                )
                persisted += 1

    return {"persisted": persisted, "updated": updated}


def list_risk_cards(filters: dict[str, Any]) -> list[dict[str, Any]]:
    """Query risk cards with optional filtering.

    Supported filter keys: ``category``, ``priority``, ``date_from``,
    ``date_to``, ``keyword``, ``report_id``, ``limit`` (default 100).
    """
    _ensure_schema()

    conditions: list[str] = []
    params: list[Any] = []

    if filters.get("category"):
        conditions.append("source_category = ?")
        params.append(filters["category"])
    if filters.get("priority"):
        conditions.append("priority = ?")
        params.append(filters["priority"])
    if filters.get("date_from"):
        conditions.append("datetime(created_at) >= datetime(?)")
        params.append(filters["date_from"])
    if filters.get("date_to"):
        conditions.append("datetime(created_at) <= datetime(?)")
        params.append(filters["date_to"])
    if filters.get("keyword"):
        conditions.append("(title LIKE ? OR summary LIKE ? OR keywords_json LIKE ?)")
        kw = f"%{filters['keyword']}%"
        params.extend([kw, kw, kw])
    if filters.get("report_id"):
        conditions.append("report_id = ?")
        params.append(filters["report_id"])

    limit = min(max(int(filters.get("limit", 100)), 1), 500)
    where_clause = " AND ".join(conditions) if conditions else "1=1"

    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM {TABLE_NAME}
            WHERE {where_clause}
            ORDER BY datetime(created_at) DESC
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()

    return [_row_to_card(row) for row in rows]


def get_risk_card(card_id: str) -> dict[str, Any] | None:
    """Return a single risk card by ``card_id`` or ``None``."""
    _ensure_schema()
    with _connect() as conn:
        row = conn.execute(
            f"SELECT * FROM {TABLE_NAME} WHERE card_id = ?",
            (card_id,),
        ).fetchone()
    return _row_to_card(row) if row else None


def delete_risk_cards_by_report(report_id: str) -> int:
    """Delete all cards associated with a given ``report_id``."""
    _ensure_schema()
    with _connect() as conn:
        cursor = conn.execute(
            f"DELETE FROM {TABLE_NAME} WHERE report_id = ?",
            (report_id,),
        )
        return cursor.rowcount


def get_card_stats() -> dict[str, Any]:
    """Return aggregate statistics about stored risk cards."""
    _ensure_schema()
    with _connect() as conn:
        total_row = conn.execute(
            f"SELECT COUNT(*) AS count FROM {TABLE_NAME}"
        ).fetchone()
        total = total_row["count"] if total_row else 0

        priority_rows = conn.execute(
            f"SELECT priority, COUNT(*) AS count FROM {TABLE_NAME} GROUP BY priority"
        ).fetchall()
        priority_counts: dict[str, int] = {"P0": 0, "P1": 0, "P2": 0}
        for row in priority_rows:
            priority_counts[row["priority"]] = row["count"]

        category_rows = conn.execute(
            f"SELECT source_category, COUNT(*) AS count "
            f"FROM {TABLE_NAME} GROUP BY source_category"
        ).fetchall()
        category_counts: dict[str, int] = {"weather": 0, "official": 0, "media": 0}
        for row in category_rows:
            category_counts[row["source_category"]] = row["count"]

    return {
        "P0": priority_counts["P0"],
        "P1": priority_counts["P1"],
        "P2": priority_counts["P2"],
        "total": total,
        "by_category": category_counts,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _row_to_card(row: sqlite3.Row) -> dict[str, Any]:
    """Convert a ``sqlite3.Row`` into a plain dict for the API layer."""
    return {
        "card_id": row["card_id"],
        "report_id": row["report_id"],
        "source_category": row["source_category"],
        "source_name": row["source_name"],
        "source_url": row["source_url"],
        "title": row["title"],
        "summary": row["summary"],
        "priority": row["priority"],
        "risk_level": row["risk_level"],
        "emoji_tag": row["emoji_tag"],
        "keywords": _json_loads(row["keywords_json"], []),
        "location": row["location"],
        "event_date": row["event_date"],
        "recommended_action": row["recommended_action"],
        "is_confirmed": bool(row["is_confirmed"]),
        "payload": _json_loads(row["payload_json"], {}),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _json_loads(raw: str | None, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except Exception:  # noqa: BLE001
        return fallback


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
