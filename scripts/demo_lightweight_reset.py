"""Pause auto schedulers, fail stuck jobs, free resources before demo."""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "chitung-center" / "data" / "chitung_platform.db"


def main() -> int:
    if not DB.exists():
        print(f"[skip] database not found: {DB}")
        return 0

    now = datetime.now(timezone.utc).isoformat()
    far = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(
            """
            UPDATE automation_tasks
            SET status = 'PAUSED', next_run_at = ?, last_run_status = 'paused_for_demo',
                updated_at = ?
            WHERE task_id = 'auto_lifting_safety_patrol_6h'
            """,
            (far, now),
        )
        failed = conn.execute(
            """
            UPDATE job_runs
            SET status = 'failed', error = 'paused_for_demo', finished_at = ?, updated_at = ?
            WHERE status IN ('queued', 'running')
              AND source_module = 'automation_scheduler'
            """,
            (now, now),
        ).rowcount
        stuck = conn.execute(
            """
            UPDATE job_runs
            SET status = 'failed', error = 'paused_for_demo', finished_at = ?, updated_at = ?
            WHERE status IN ('queued', 'running')
              AND source_module IN ('automation_scheduler', 'agent_orchestrator')
            """,
            (now, now),
        ).rowcount
        conn.execute(
            """
            UPDATE job_runs
            SET status = 'failed', error = 'paused_for_demo', finished_at = ?, updated_at = ?
            WHERE status = 'running' AND job_type IN ('visual_patrol', 'automation_workflow')
            """,
            (now, now),
        )
        try:
            conn.execute(
                """
                UPDATE external_monitor_settings
                SET enabled = 0, updated_at = ?
                WHERE id = 1
                """,
                (now,),
            )
        except sqlite3.OperationalError:
            pass
        conn.commit()
        print(f"[ok] automation patrol PAUSED until {far[:10]}")
        print(f"[ok] marked {stuck} stuck background jobs as failed")
        print("[ok] external monitor disabled for demo")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
