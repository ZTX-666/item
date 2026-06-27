#!/usr/bin/env python3
"""Check and repair Chitung SQLite databases."""
from __future__ import annotations

import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DBS = [
    ROOT / "chitung-center" / "data" / "chitung_platform.db",
    ROOT / "agent-toolbox" / "workspace" / "safety_platform.db",
]
LEGACY = Path(r"E:\ChinaOverSea Final")
LEGACY_DBS = [
    LEGACY / "chitung-center" / "data" / "chitung_platform.db",
    LEGACY / "agent-toolbox" / "workspace" / "safety_platform.db",
]


def integrity(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing"
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        result = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        conn.close()
        return result.lower() == "ok", result
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def counts(path: Path) -> dict[str, int]:
    out: dict[str, int] = {}
    if not path.exists():
        return out
    conn = sqlite3.connect(path)
    try:
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        ]
        for table in tables:
            try:
                out[table] = int(conn.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0])
            except sqlite3.DatabaseError:
                out[table] = -1
    finally:
        conn.close()
    return out


def repair(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing"
    backup = path.with_suffix(path.suffix + f".bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(path, backup)
    recovered = path.with_suffix(path.suffix + ".recovered")
    if recovered.exists():
        recovered.unlink()
    src = sqlite3.connect(path)
    try:
        dst = sqlite3.connect(recovered)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    ok, msg = integrity(recovered)
    if not ok:
        return False, f"recovered still bad: {msg}"
    path.replace(path.with_suffix(path.suffix + ".corrupt"))
    recovered.replace(path)
    return True, f"repaired from backup dump; backup={backup.name}"


def pick_best_legacy(target: Path) -> Path | None:
    name = target.name
    candidates = [p for p in LEGACY_DBS if p.name == name and p.exists()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_size)


def restore_wacli_db() -> tuple[bool, str]:
    wacli_dir = ROOT / "agent-toolbox" / "workspace" / "wacli"
    db = wacli_dir / "wacli.db"
    if not db.exists():
        return False, "wacli.db missing"
    ok, msg = integrity(db)
    if ok:
        return True, "wacli.db already ok"
    candidates = sorted(
        [p for p in wacli_dir.glob("wacli.db.bak-*") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    legacy_dir = ROOT / "agent-toolbox" / "workspace"
    candidates.extend(
        sorted(legacy_dir.glob("wacli.bak-*/wacli.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    )
    for candidate in candidates:
        ok2, msg2 = integrity(candidate)
        if not ok2:
            continue
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        if db.exists():
            shutil.copy2(db, db.with_suffix(db.suffix + f".corrupt-{stamp}"))
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(db) + suffix)
            if sidecar.exists():
                sidecar.unlink()
        shutil.copy2(candidate, db)
        return True, f"restored wacli from {candidate.name}"
    ok3, msg3 = repair(db)
    return ok3, msg3


def restore_from_legacy(target: Path) -> tuple[bool, str]:
    legacy = pick_best_legacy(target)
    if not legacy:
        return False, "no legacy copy"
    ok, msg = integrity(legacy)
    if not ok:
        return False, f"legacy corrupt: {msg}"
    backup = target.with_suffix(target.suffix + f".pre-restore-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    if target.exists():
        shutil.copy2(target, backup)
    shutil.copy2(legacy, target)
    return True, f"restored from {legacy} (backup {backup.name})"


def main() -> int:
    failed = 0
    for db in DBS:
        print(f"\n=== {db} ===")
        if not db.exists():
            print("missing; trying legacy restore")
            ok, msg = restore_from_legacy(db)
            print(("OK" if ok else "FAIL"), msg)
            failed += 0 if ok else 1
            continue
        ok, msg = integrity(db)
        print("integrity:", "OK" if ok else "BAD", msg)
        c = counts(db)
        interesting = {
            k: v
            for k, v in c.items()
            if any(x in k for x in ("confirmation", "safety", "job", "automation", "external", "case"))
        }
        if interesting:
            print("counts:", interesting)
        if ok:
            continue
        print("attempt repair...")
        ok2, msg2 = repair(db)
        print(("OK" if ok2 else "FAIL"), msg2)
        if ok2:
            continue
        print("attempt legacy restore...")
        ok3, msg3 = restore_from_legacy(db)
        print(("OK" if ok3 else "FAIL"), msg3)
        if not ok3:
            failed += 1
    w_ok, w_msg = restore_wacli_db()
    print(f"\n=== wacli.db ===")
    print("OK" if w_ok else "FAIL", w_msg)
    if not w_ok:
        failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
