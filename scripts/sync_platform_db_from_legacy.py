#!/usr/bin/env python3
"""Merge platform history from legacy repo path into the active workspace database."""

from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

DEFAULT_SOURCE = Path(r"E:\ChinaOverSea Final\chitung-center\data\chitung_platform.db")
DEFAULT_TARGET = Path(r"E:\ChinaOverSeaFinal\chitung-center\data\chitung_platform.db")

# Tables seeded for demo usage history + external risk cards.
SYNC_TABLES = [
    "risk_cards",
    "job_runs",
    "task_events",
    "external_events",
    "external_event_sources",
    "external_raw_items",
    "external_monitor_runs",
    "external_source_state",
    "external_risk_briefing_reports",
    "workflow_runs",
    "workflow_steps",
    "safety_cases",
    "pending_confirmations",
    "automation_tasks",
    "automation_runs",
    "platform_seed_runs",
]


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def table_columns(conn: sqlite3.Connection, name: str) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info({name})")]


def ensure_table_from_source(src: sqlite3.Connection, dst: sqlite3.Connection, name: str) -> None:
    if table_exists(dst, name):
        return
    ddl = src.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    if not ddl or not ddl[0]:
        return
    dst.executescript(ddl[0])


def merge_table(src: sqlite3.Connection, dst: sqlite3.Connection, name: str) -> tuple[int, int]:
    if not table_exists(src, name):
        return 0, 0
    ensure_table_from_source(src, dst, name)
    if not table_exists(dst, name):
        return 0, 0

    src_cols = table_columns(src, name)
    dst_cols = table_columns(dst, name)
    cols = [col for col in src_cols if col in dst_cols]
    if not cols:
        return 0, 0

    col_sql = ", ".join(cols)
    placeholders = ", ".join("?" for _ in cols)
    rows = src.execute(f"SELECT {col_sql} FROM {name}").fetchall()
    before = dst.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]

    dst.executemany(
        f"INSERT OR IGNORE INTO {name} ({col_sql}) VALUES ({placeholders})",
        rows,
    )
    after = dst.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
    return len(rows), after - before


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync legacy platform DB into active workspace.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--no-backup", action="store_true")
    args = parser.parse_args()

    if not args.source.exists():
        print(f"[FAIL] Source DB not found: {args.source}")
        return 1
    if not args.target.exists():
        print(f"[FAIL] Target DB not found: {args.target}")
        return 1

    if not args.no_backup:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = args.target.with_name(f"chitung_platform.db.bak-{stamp}")
        shutil.copy2(args.target, backup)
        print(f"[OK] Backup: {backup}")

    src = sqlite3.connect(args.source)
    dst = sqlite3.connect(args.target)
    try:
        print(f"Source: {args.source}")
        print(f"Target: {args.target}")
        print("-" * 60)
        total_inserted = 0
        for name in SYNC_TABLES:
            scanned, inserted = merge_table(src, dst, name)
            if scanned:
                count = dst.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
                print(f"{name:32} scanned={scanned:4} inserted={inserted:4} total={count}")
                total_inserted += inserted
        dst.commit()
        print("-" * 60)
        cards = dst.execute("SELECT COUNT(*) FROM risk_cards").fetchone()[0]
        jobs = dst.execute("SELECT COUNT(*) FROM job_runs").fetchone()[0]
        print(f"[DONE] inserted_rows={total_inserted} risk_cards={cards} job_runs={jobs}")
    finally:
        src.close()
        dst.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
