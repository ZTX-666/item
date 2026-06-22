from __future__ import annotations

import os
import sqlite3

import pytest

from chitung_center.whatsapp_local_service import (
    list_whatsapp_sql_tables,
    run_whatsapp_command,
    run_whatsapp_sql_query,
)
from chitung_center import whatsapp_local_service


def test_whatsapp_sql_tables_and_select_are_read_only(tmp_path):
    db_path = tmp_path / "wacli.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, text TEXT)")
        conn.execute("INSERT INTO messages (text) VALUES ('hello')")

    tables = list_whatsapp_sql_tables(str(db_path))
    result = run_whatsapp_sql_query("SELECT id, text FROM messages", 10, str(db_path))

    assert tables["ok"] is True
    assert "messages" in tables["data"]["tables"]
    assert result["ok"] is True
    assert result["data"]["columns"] == ["id", "text"]
    assert result["data"]["rows"][0]["text"] == "hello"

    with pytest.raises(ValueError):
        run_whatsapp_sql_query("DELETE FROM messages", 10, str(db_path))


def test_whatsapp_sql_auto_resolution_prefers_wacli_db_over_newer_session_db(monkeypatch, tmp_path):
    store_dir = tmp_path / "agent-toolbox" / "workspace" / "wacli"
    store_dir.mkdir(parents=True)
    wacli_db = store_dir / "wacli.db"
    session_db = store_dir / "session.db"

    with sqlite3.connect(wacli_db) as conn:
        conn.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, text TEXT)")
    with sqlite3.connect(session_db) as conn:
        conn.execute("CREATE TABLE identities (id INTEGER PRIMARY KEY, jid TEXT)")

    os.utime(wacli_db, (100, 100))
    os.utime(session_db, (200, 200))
    monkeypatch.setattr(whatsapp_local_service, "ROOT", tmp_path)
    monkeypatch.delenv("WACLI_DB_PATH", raising=False)
    monkeypatch.delenv("WACLI_STORE_DIR", raising=False)

    result = list_whatsapp_sql_tables()

    assert result["ok"] is True
    assert result["data"]["database_path"] == str(wacli_db)
    assert result["data"]["tables"] == ["messages"]


def test_whatsapp_command_rejects_write_command_in_readonly_mode():
    result = run_whatsapp_command("send text --to group --message hi", read_only=True)

    assert result["ok"] is False
    assert result["error"] == "read_only_command_required"


def test_whatsapp_command_rejects_write_command_even_with_readonly_global_flag():
    result = run_whatsapp_command("--read-only auth logout", read_only=True)

    assert result["ok"] is False
    assert result["error"] == "read_only_command_required"


@pytest.mark.parametrize(
    "args_text",
    [
        "store stats",
        "store cleanup --days 365 --dry-run",
        "calls list --limit 20",
        "channels list",
        "polls list --chat 123@g.us --limit 20",
        "groups info --jid 123@g.us",
        "chats show --jid 852@s.whatsapp.net",
    ],
)
def test_whatsapp_command_allows_more_safe_readonly_commands(monkeypatch, args_text):
    calls: list[list[str]] = []

    class FakeProcess:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return FakeProcess()

    monkeypatch.setattr(whatsapp_local_service, "_resolve_wacli_bin", lambda: {"path": "/bin/wacli", "error": ""})
    monkeypatch.setattr(whatsapp_local_service.subprocess, "run", fake_run)

    result = run_whatsapp_command(args_text, read_only=True)

    assert result["ok"] is True
    assert calls


def test_runtime_status_detects_publish3_darwin_wacli(monkeypatch, tmp_path):
    binary = tmp_path / "publish3.0" / "runtime" / "bin" / "wacli-darwin-arm64"
    binary.parent.mkdir(parents=True)
    binary.write_text("fake darwin binary")

    monkeypatch.setattr(whatsapp_local_service, "ROOT", tmp_path)
    monkeypatch.setattr(whatsapp_local_service, "_platform_wacli_name", lambda: "wacli-darwin-arm64")
    monkeypatch.setattr(whatsapp_local_service.shutil, "which", lambda name: None)
    monkeypatch.delenv("WACLI_BIN", raising=False)
    monkeypatch.delenv("WACLI_STORE_DIR", raising=False)

    result = whatsapp_local_service.whatsapp_runtime_status()

    assert result["wacli_available"] is True
    assert result["wacli_bin"] == str(binary)
