from __future__ import annotations

import os
import platform
import shlex
import shutil
import sqlite3
import subprocess
import mimetypes
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
WRITE_KEYWORDS = {
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "create",
    "replace",
    "attach",
    "detach",
    "vacuum",
    "reindex",
    "pragma",
}


def whatsapp_runtime_status() -> dict[str, Any]:
    db_path = _resolve_db_path(None)
    wacli = _resolve_wacli_bin()
    return {
        "ok": True,
        "database_path": str(db_path) if db_path else "",
        "database_found": bool(db_path),
        "default_store_dir": str(_default_store_dir()),
        "wacli_bin": wacli.get("path") or os.getenv("WACLI_BIN", "wacli"),
        "wacli_available": bool(wacli.get("path")),
        "wacli_error": wacli.get("error") or "",
    }


def list_whatsapp_sql_tables(db_path: str | None = None) -> dict[str, Any]:
    resolved = _resolve_db_path(db_path)
    if not resolved:
        return {
            "ok": False,
            "summary": "未找到 WhatsApp SQLite 数据库。",
            "error": "database_not_found",
            "data": {"tables": [], "database_path": "", "default_store_dir": str(_default_store_dir())},
        }
    with _connect_readonly(resolved) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view') ORDER BY name"
        ).fetchall()
    return {
        "ok": True,
        "summary": f"已读取 {len(rows)} 个数据表。",
        "data": {"tables": [row["name"] for row in rows], "database_path": str(resolved)},
    }


def run_whatsapp_sql_query(
    sql: str,
    limit: int = 100,
    db_path: str | None = None,
    offset: int = 0,
) -> dict[str, Any]:
    resolved = _resolve_db_path(db_path)
    if not resolved:
        return {
            "ok": False,
            "summary": "未找到 WhatsApp SQLite 数据库。",
            "error": "database_not_found",
            "data": {
                "columns": [],
                "rows": [],
                "database_path": "",
                "default_store_dir": str(_default_store_dir()),
                "limit": limit,
                "offset": offset,
                "total": 0,
            },
        }
    safe_sql = _validate_select(sql)
    bounded_limit = max(1, min(int(limit or 100), 500))
    bounded_offset = max(0, int(offset or 0))
    count_sql = f"SELECT COUNT(*) AS total FROM ({safe_sql})"
    wrapped_sql = f"SELECT * FROM ({safe_sql}) LIMIT ? OFFSET ?"
    try:
        with _connect_readonly(resolved) as conn:
            total = int(conn.execute(count_sql).fetchone()["total"])
            cursor = conn.execute(wrapped_sql, (bounded_limit, bounded_offset))
            rows = cursor.fetchall()
            columns = [item[0] for item in cursor.description or []]
    except sqlite3.Error as exc:
        return {
            "ok": False,
            "summary": "SQLite 查询执行失败。",
            "error": str(exc),
            "data": {
                "columns": [],
                "rows": [],
                "database_path": str(resolved),
                "limit": bounded_limit,
                "offset": bounded_offset,
                "total": 0,
            },
        }
    return {
        "ok": True,
        "summary": f"查询完成，返回 {len(rows)} 行。",
        "data": {
            "columns": columns,
            "rows": [dict(row) for row in rows],
            "database_path": str(resolved),
            "limit": bounded_limit,
            "offset": bounded_offset,
            "total": total,
        },
    }


def resolve_whatsapp_media_file(msg_id: str) -> dict[str, Any]:
    resolved = _resolve_db_path(None)
    if not resolved:
        return {"ok": False, "error": "database_not_found"}
    cleaned = (msg_id or "").strip()
    if not cleaned:
        return {"ok": False, "error": "empty_msg_id"}

    with _connect_readonly(resolved) as conn:
        row = conn.execute(
            """
            SELECT local_path, mime_type, filename, media_type
            FROM messages
            WHERE msg_id = ?
            LIMIT 1
            """,
            (cleaned,),
        ).fetchone()
    if not row:
        return {"ok": False, "error": "message_not_found"}

    path_text = str(row["local_path"] or "").strip()
    if not path_text:
        return {"ok": False, "error": "media_not_downloaded"}
    path = Path(path_text).expanduser()
    if not path.exists() or not path.is_file():
        return {"ok": False, "error": "media_file_not_found", "path": str(path)}

    mime_type = str(row["mime_type"] or "").strip() or mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    filename = str(row["filename"] or "").strip() or path.name
    return {
        "ok": True,
        "path": str(path),
        "mime_type": mime_type,
        "filename": filename,
        "media_type": str(row["media_type"] or "").strip(),
    }


def run_whatsapp_command(args_text: str, timeout_seconds: int = 60, read_only: bool = True) -> dict[str, Any]:
    args = shlex.split(args_text.strip())
    if not args:
        return {"ok": False, "summary": "命令参数为空。", "error": "empty_args", "data": {"stdout": "", "stderr": ""}}
    if read_only and not _is_readonly_command(args):
        return {
            "ok": False,
            "summary": "命令工具当前只允许只读命令。",
            "error": "read_only_command_required",
            "data": {"args": args},
        }
    wacli = _resolve_wacli_bin()
    if not wacli.get("path"):
        return {
            "ok": False,
            "summary": "未找到可运行的 wacli。",
            "error": wacli.get("error") or "wacli_not_found",
            "data": {"args": args, "stdout": "", "stderr": "", **wacli},
        }
    workdir = _default_store_dir()
    workdir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.setdefault("WACLI_STORE_DIR", str(workdir))
    try:
        process = subprocess.run(
            [str(wacli["path"]), *args],
            cwd=str(workdir),
            env=env,
            capture_output=True,
            text=True,
            timeout=max(5, min(timeout_seconds, 120)),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {"ok": False, "summary": "wacli 命令执行超时。", "error": str(exc), "data": {"args": args}}
    return {
        "ok": process.returncode == 0,
        "summary": "wacli 命令执行完成。" if process.returncode == 0 else "wacli 命令执行失败。",
        "error": "" if process.returncode == 0 else (process.stderr or process.stdout or f"exit_code={process.returncode}"),
        "data": {
            "args": args,
            "command": [str(wacli["path"]), *args],
            "exit_code": process.returncode,
            "stdout": process.stdout[-12000:],
            "stderr": process.stderr[-12000:],
        },
    }


def _validate_select(sql: str) -> str:
    cleaned = sql.strip().rstrip(";").strip()
    if ";" in cleaned:
        raise ValueError("SQLite 查询只允许单条 SELECT，不允许多语句。")
    lowered = cleaned.lower()
    if not lowered.startswith("select"):
        raise ValueError("SQLite 查询只允许 SELECT。")
    tokens = set(lowered.replace("\n", " ").split())
    if tokens & WRITE_KEYWORDS:
        raise ValueError("SQLite 查询包含写入或结构变更关键字。")
    return cleaned


def _connect_readonly(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _resolve_db_path(value: str | None) -> Path | None:
    if value:
        path = Path(value).expanduser()
        if path.exists() and path.is_file():
            return path
    env_path = os.getenv("WACLI_DB_PATH")
    if env_path:
        path = Path(env_path).expanduser()
        if path.exists() and path.is_file():
            return path
    for root in _db_search_roots():
        if not root.exists():
            continue
        direct = root / "wacli.db"
        if direct.exists() and direct.is_file():
            return direct
        named = sorted(root.rglob("wacli.db"), key=lambda item: item.stat().st_mtime, reverse=True)
        for candidate in named:
            if candidate.is_file():
                return candidate
    for root in _db_search_roots():
        if not root.exists():
            continue
        candidates = sorted(root.rglob("*.db"), key=lambda item: item.stat().st_mtime, reverse=True)
        for candidate in candidates:
            if candidate.is_file() and candidate.name != "session.db" and _looks_like_wacli_db(candidate):
                return candidate
    return None


def _db_search_roots() -> list[Path]:
    roots = [
        Path(os.getenv("WACLI_STORE_DIR", "")).expanduser() if os.getenv("WACLI_STORE_DIR") else None,
        ROOT / "agent-toolbox" / "workspace" / "wacli",
        Path.home() / "ChitongLingxun",
    ]
    return [root for root in roots if root is not None]


def _default_store_dir() -> Path:
    return Path(os.getenv("WACLI_STORE_DIR") or (ROOT / "agent-toolbox" / "workspace" / "wacli")).expanduser()


def _platform_wacli_name() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "darwin":
        arch = "arm64" if machine in {"arm64", "aarch64"} else "amd64"
        return f"wacli-darwin-{arch}"
    if system == "linux":
        arch = "arm64" if machine in {"arm64", "aarch64"} else "amd64"
        return f"wacli-linux-{arch}"
    if os.name == "nt":
        return "wacli.exe"
    return ""


def _resolve_wacli_bin() -> dict[str, str]:
    configured = os.getenv("WACLI_BIN", "wacli")
    candidates: list[Path] = []
    if os.path.isabs(configured):
        candidates.append(Path(configured))
    resolved = shutil.which(configured)
    if resolved:
        candidates.append(Path(resolved))
    platform_name = _platform_wacli_name()
    if platform_name:
        candidates.append(ROOT / "publish3.0" / "runtime" / "bin" / platform_name)
    candidates.append(ROOT / "publish3.0" / "runtime" / "bin" / "wacli.exe")
    for candidate in candidates:
        if candidate.exists():
            if candidate.suffix.lower() == ".exe" and os.name != "nt":
                return {"path": "", "error": "packaged_wacli_is_windows_only", "detected_windows_wacli": str(candidate)}
            return {"path": str(candidate), "error": ""}
    return {"path": "", "error": f"wacli not found: {configured}"}


def _is_readonly_command(args: list[str]) -> bool:
    command_args = _without_wacli_global_options(args)
    command_text = " ".join(command_args).lower()
    if command_text.startswith("history fill"):
        return "--dry-run" in command_args
    if command_text.startswith("store cleanup"):
        return "--dry-run" in command_args and "--confirm" not in command_args
    if command_text.startswith(("chats cleanup", "groups prune")):
        return "--dry-run" in command_args and "--confirm" not in command_args
    allowed_prefixes = (
        "doctor",
        "version",
        "docs",
        "help",
        "auth status",
        "sync --help",
        "history coverage",
        "history fill --dry-run",
        "history backfill --help",
        "messages list",
        "messages search",
        "messages starred",
        "messages export --help",
        "messages show --help",
        "messages context --help",
        "chats list",
        "chats show",
        "groups list",
        "groups info",
        "channels list",
        "contacts search",
        "contacts show",
        "calls list",
        "polls list",
        "poll show",
        "profile picture-info",
        "profile get-about",
        "profile business",
        "store stats",
    )
    return command_text.startswith(allowed_prefixes)


def is_whatsapp_command_readonly(args: list[str]) -> bool:
    return _is_readonly_command(args)


def _without_wacli_global_options(args: list[str]) -> list[str]:
    flags = {"--read-only", "--json", "--full", "--events"}
    options_with_value = {"--store", "--account", "--lock-wait"}
    cleaned: list[str] = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg in flags:
            index += 1
            continue
        if any(arg.startswith(f"{option}=") for option in options_with_value):
            index += 1
            continue
        if arg in options_with_value:
            index += 2
            continue
        cleaned.append(arg)
        index += 1
    return cleaned


def _looks_like_wacli_db(path: Path) -> bool:
    try:
        with _connect_readonly(path) as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('messages', 'chats')"
            ).fetchall()
    except sqlite3.Error:
        return False
    names = {row["name"] for row in rows}
    return {"messages", "chats"}.issubset(names)
