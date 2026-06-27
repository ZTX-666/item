#!/usr/bin/env python3
"""Merge active workspace (with-space) into canonical no-space root E:\\ChinaOverSeaFinal."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

SOURCE = Path(r"E:\ChinaOverSea Final")
TARGET = Path(r"E:\ChinaOverSeaFinal")

EXCLUDE_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "__pycache__",
    "dist",
    "release",
    "patrol-output",
    "publish3.0",
    "publish80",
    "open-source-references",
    "external",
    "docmate-shanshan",
    "chitong-lingxun",
    "fixtures",
    "models",
    "frontend-ui-prototype",
    ".cursor",
    ".local-change-backups",
}

# Runtime data copied explicitly (not walked with source tree).
RUNTIME_COPY = [
    ("chitung-center/data/rag_chroma", True),
    ("chitung-center/data/rag_meta.json", False),
    ("chitung-center/data/rag_uploads", True),
    ("chitung-center/data/long_term_memory.md", False),
    ("chitung-center/data/video_detection_reports.json", False),
    ("chitung-center/data/audit.jsonl", False),
    ("agent-toolbox/workspace/safety_platform.db", False),
    ("agent-toolbox/workspace/wacli/wacli.db", False),
]

PATH_REWRITES = [
    (r"E:\\ChinaOverSeaFinal", r"E:\\ChinaOverSeaFinal"),
    (r"E:/ChinaOverSeaFinal", r"E:/ChinaOverSeaFinal"),
    (r"E:\\ChinaOverSeaFinal\\", r"E:\\ChinaOverSeaFinal\\"),
    (r"E:/ChinaOverSeaFinal/", r"E:/ChinaOverSeaFinal/"),
]


def should_skip(rel: Path) -> bool:
    parts = set(rel.parts)
    if parts & EXCLUDE_DIRS:
        return True
    if rel.suffix in {".pyc", ".db-wal", ".db-shm"}:
        return True
    if "data" in rel.parts and rel.name.startswith("chitung_platform.db.bak"):
        return True
    return False


def rewrite_paths_in_file(path: Path) -> None:
    if path.suffix.lower() not in {".env", ".bat", ".json", ".py", ".ts", ".vue", ".md", ".cjs", ".js", ".vbs"}:
        return
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return
    updated = text
    for old, new in PATH_REWRITES:
        updated = updated.replace(old, new)
    if updated != text:
        path.write_text(updated, encoding="utf-8")


def copy_tree(src_root: Path, dst_root: Path, *, dry_run: bool) -> tuple[int, int]:
    copied = skipped = 0
    for dirpath, dirnames, filenames in os.walk(src_root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for name in filenames:
            rel = Path(dirpath).joinpath(name).relative_to(src_root)
            if should_skip(rel):
                skipped += 1
                continue
            src = src_root / rel
            dst = dst_root / rel
            if dry_run:
                copied += 1
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(src, dst)
            except PermissionError as exc:
                skipped += 1
                print(f"LOCKED skip: {rel} ({exc})")
                continue
            rewrite_paths_in_file(dst)
            copied += 1
    return copied, skipped


def copy_runtime(src_root: Path, dst_root: Path, *, dry_run: bool) -> list[str]:
    notes: list[str] = []
    for rel, is_dir in RUNTIME_COPY:
        src = src_root / rel
        dst = dst_root / rel
        if not src.exists():
            notes.append(f"skip missing runtime: {rel}")
            continue
        if dry_run:
            notes.append(f"would copy runtime: {rel}")
            continue
        if dst.exists():
            backup = dst.with_name(dst.name + f".bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
            if is_dir and dst.is_dir():
                shutil.copytree(dst, backup, dirs_exist_ok=True)
            elif dst.is_file():
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dst, backup)
        if is_dir:
            if dst.exists():
                shutil.rmtree(dst, ignore_errors=True)
            try:
                shutil.copytree(src, dst, ignore=shutil.ignore_patterns("LOCK"))
            except PermissionError as exc:
                notes.append(f"locked runtime dir (partial): {rel} ({exc})")
                continue
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(src, dst)
            except PermissionError as exc:
                notes.append(f"locked runtime file: {rel} ({exc})")
                continue
        notes.append(f"copied runtime: {rel}")
    return notes


def merge_platform_db(src_db: Path, dst_db: Path, *, dry_run: bool) -> str:
    if not src_db.exists():
        return "source db missing"
    if dry_run:
        return f"would merge db {src_db.name} -> {dst_db.name}"
    dst_db.parent.mkdir(parents=True, exist_ok=True)
    if dst_db.exists() and dst_db.is_file():
        backup = dst_db.with_suffix(f".db.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
        shutil.copy2(dst_db, backup)
    try:
        shutil.copy2(src_db, dst_db)
    except PermissionError as exc:
        return f"platform db locked: {exc}"
    return f"platform db replaced from source ({src_db.stat().st_size} bytes)"


def write_canonical_marker(target: Path, *, dry_run: bool) -> None:
    marker = target / "WORKSPACE_ROOT.txt"
    text = (
        "Canonical Chitung workspace root (no spaces in path).\n"
        f"Unified at: {datetime.now().isoformat()}\n"
        "Start platform: scripts\\启动赤瞳平台.bat\n"
        "Preflight: scripts\\演示前检查.bat\n"
    )
    if dry_run:
        return
    marker.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Unify workspace to E:\\ChinaOverSeaFinal")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not SOURCE.exists():
        print(f"ERROR: source missing: {SOURCE}")
        return 1
    TARGET.mkdir(parents=True, exist_ok=True)

    print(f"Source: {SOURCE}")
    print(f"Target: {TARGET}")
    print(f"Dry run: {args.dry_run}")
    print()

    copied, skipped = copy_tree(SOURCE, TARGET, dry_run=args.dry_run)
    print(f"Tree copy: {copied} files, skipped {skipped}")

    for note in copy_runtime(SOURCE, TARGET, dry_run=args.dry_run):
        print(note)

    db_note = merge_platform_db(
        SOURCE / "chitung-center/data/chitung_platform.db",
        TARGET / "chitung-center/data/chitung_platform.db",
        dry_run=args.dry_run,
    )
    print(db_note)

    # Ensure demo preflight scripts exist in target (from source)
    for script in ("demo_preflight.py", "sync_platform_db_from_legacy.py", "unify_to_nospace.py", "演示前检查.bat", "停止赤瞳平台.bat"):
        src = SOURCE / "scripts" / script
        dst = TARGET / "scripts" / script
        if src.exists() and not args.dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            rewrite_paths_in_file(dst)

    # Best startup script: merge no-space restart logic with source extras
    startup_src = SOURCE / "scripts" / "启动赤瞳平台.bat"
    startup_dst = TARGET / "scripts" / "启动赤瞳平台.bat"
    if startup_src.exists() and not args.dry_run:
        text = startup_src.read_text(encoding="utf-8")
        # Adopt no-space restart/wait improvements
        text = text.replace(
            'echo [2/5] 启动 agent-toolbox (:8899)...',
            'echo [2/5] 重启 agent-toolbox (:8899)...',
        )
        text = re.sub(
            r'if errorlevel 1 \(\s*\r?\n\s*start "agent-toolbox".*?\r?\n\s*\)',
            'for /f "tokens=5" %%P in (\'netstat -ano ^| findstr ":8899" ^| findstr "LISTENING"\') do taskkill /F /PID %%P >nul 2>&1\r\n'
            'timeout /t 1 /nobreak >nul\r\n'
            'start "agent-toolbox" /MIN /D "%TOOLBOX%" cmd /c ".venv\\Scripts\\python.exe run_server.py"',
            text,
            count=1,
            flags=re.DOTALL,
        )
        startup_dst.write_text(text, encoding="utf-8")
        rewrite_paths_in_file(startup_dst)

    write_canonical_marker(TARGET, dry_run=args.dry_run)

    if not args.dry_run:
        # Rewrite env paths under target
        for env_path in [
            TARGET / "agent-toolbox/.env",
            TARGET / "chitung-center/.env",
            TARGET / "cctv-gateway/.env",
            TARGET / "chitung-frontend/.env",
        ]:
            if env_path.exists():
                rewrite_paths_in_file(env_path)

    print("\nDone. Use E:\\ChinaOverSeaFinal as the only workspace root.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
