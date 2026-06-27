from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import threading
import time
from typing import Any

from pydantic import BaseModel, Field
import requests

from ..config import settings
from ..models import ToolResult
from ..tasks import new_task_id, record_task_event


class WhatsAppSearchRequest(BaseModel):
    q: str = Field(min_length=1)
    chat: str | None = None
    limit: int = Field(default=20, ge=1, le=200)


class WhatsAppDownloadMediaRequest(BaseModel):
    message_id: str = Field(min_length=10)
    dir: str | None = None


class WhatsAppWacliGroupsRequest(BaseModel):
    include_archived: bool = False
    limit: int = Field(default=50, ge=1, le=200)
    dry_run: bool = False


class WhatsAppGroupsRefreshRequest(BaseModel):
    dry_run: bool = False


class WhatsAppSendTextRequest(BaseModel):
    chat: str = Field(min_length=1, description="WhatsApp chat/group id or name")
    text: str = Field(min_length=1)
    confirmed: bool = False
    dry_run: bool = False
    confirmed_by: str | None = None


class WhatsAppSendFileRequest(BaseModel):
    chat: str = Field(min_length=1, description="WhatsApp recipient phone, JID, or chat name")
    file_path: str = Field(min_length=1)
    caption: str = ""
    confirmed: bool = False
    dry_run: bool = False
    confirmed_by: str | None = None


class WhatsAppAuthStartRequest(BaseModel):
    phone: str | None = Field(default=None, description="Hong Kong phone number, e.g. 91234567 or +85291234567")
    mode: str = Field(default="qr", description="qr or phone")
    timeout_seconds: int = Field(default=120, ge=30, le=600)


class WhatsAppAuthStatusRequest(BaseModel):
    include_logs: bool = True


class WhatsAppAuthStopRequest(BaseModel):
    reason: str = "manual_stop"


class WhatsAppAuthLogoutRequest(BaseModel):
    confirmed: bool = False
    reason: str = "manual_logout"


class WhatsAppSyncStartRequest(BaseModel):
    webhook_url: str = "http://127.0.0.1:8999/integrations/whatsapp/events"
    webhook_secret: str = ""
    download_media: bool = False
    refresh_groups: bool = True


class WhatsAppSyncStatusRequest(BaseModel):
    include_logs: bool = True


class WhatsAppSyncStopRequest(BaseModel):
    reason: str = "manual_stop"


_PAIR_RE = re.compile(r"^[A-Z0-9]{4}-[A-Z0-9]{4}$", re.IGNORECASE)
_auth_lock = threading.Lock()
_auth_process: subprocess.Popen[str] | None = None
_auth_state: dict[str, Any] = {
    "running": False,
    "status": "idle",
    "qr_payload": "",
    "pairing_code": "",
    "phone": "",
    "started_at": None,
    "updated_at": None,
    "logs": [],
    "last_error": "",
}
_sync_lock = threading.Lock()
_sync_process: subprocess.Popen[str] | None = None
_sync_state: dict[str, Any] = {
    "running": False,
    "status": "idle",
    "webhook_url": "",
    "started_at": None,
    "updated_at": None,
    "logs": [],
    "last_error": "",
    "messages_synced": 0,
}


def _base_url() -> str:
    return settings.whatsapp_archive_base_url.rstrip("/")


def _is_windows_platform() -> bool:
    return os.name == "nt"


def _platform_wacli_name() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "darwin":
        arch = "arm64" if machine in {"arm64", "aarch64"} else "amd64"
        return f"wacli-darwin-{arch}"
    if system == "linux":
        arch = "arm64" if machine in {"arm64", "aarch64"} else "amd64"
        return f"wacli-linux-{arch}"
    if _is_windows_platform():
        return "wacli.exe"
    return ""


def _packaged_wacli_candidates() -> list[Path]:
    root = Path(getattr(settings, "root", Path.cwd()))
    platform_name = _platform_wacli_name()
    candidates = [
        # Repo layout: item/agent-toolbox -> item/publish3.0/runtime/bin/wacli.exe
        root.parent / "publish3.0" / "runtime" / "bin" / "wacli.exe",
        # Publish layout: publish3.0/agent-services/agent-toolbox -> publish3.0/runtime/bin/wacli.exe
        root.parent.parent / "runtime" / "bin" / "wacli.exe",
    ]
    if platform_name:
        candidates = [
            root.parent / "publish3.0" / "runtime" / "bin" / platform_name,
            root.parent.parent / "runtime" / "bin" / platform_name,
            *candidates,
        ]
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def _detected_packaged_windows_wacli() -> Path | None:
    for candidate in _packaged_wacli_candidates():
        if candidate.exists():
            return candidate
    return None


def _wacli_bin() -> str | None:
    configured = settings.wacli_bin
    if os.path.isabs(configured) and os.path.exists(configured):
        if configured.lower().endswith(".exe") and not _is_windows_platform():
            return None
        return configured
    resolved = shutil.which(configured)
    if resolved:
        return resolved
    if configured == "wacli":
        for packaged in _packaged_wacli_candidates():
            if not packaged.exists():
                continue
            if packaged.suffix.lower() == ".exe" and not _is_windows_platform():
                continue
            return str(packaged)
    return None


def _wacli_unavailable_details(default_summary: str) -> tuple[str, str, dict[str, Any]]:
    data: dict[str, Any] = {"wacli_bin": settings.wacli_bin}
    packaged = _detected_packaged_windows_wacli()
    if packaged:
        data["detected_windows_wacli"] = str(packaged)
    if packaged and not _is_windows_platform():
        return (
            "检测到发布包里的 Windows wacli.exe，但当前系统不能运行 Windows 程序。请在 Windows 发布包环境运行，或配置 macOS 版 WACLI_BIN。",
            "packaged_wacli_is_windows_only",
            data,
        )
    return default_summary, f"wacli not found: {settings.wacli_bin}", data


def _run_wacli(args: list[str], timeout: int = 60) -> tuple[bool, int, str, str, list[str]]:
    binary = _wacli_bin()
    if not binary:
        _summary, error, _data = _wacli_unavailable_details("未找到 wacli。")
        return False, 127, "", error, [settings.wacli_bin, *args]
    settings.wacli_workdir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.setdefault("WACLI_STORE_DIR", str(settings.wacli_store_dir))
    process = subprocess.run(
        [binary, *args],
        cwd=str(settings.wacli_workdir),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    return process.returncode == 0, process.returncode, process.stdout, process.stderr, [binary, *args]


def _json_items(stdout: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("items", "rows", "chats", "groups", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _wacli_message_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    if isinstance(data, dict):
        messages = data.get("messages")
    else:
        messages = payload.get("messages")
    if not isinstance(messages, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in messages:
        if not isinstance(item, dict):
            continue
        text = item.get("Text") or item.get("DisplayText") or item.get("Snippet") or ""
        rows.append(
            {
                "message_id": item.get("MsgID"),
                "chat_id": item.get("ChatJID"),
                "chat_name": item.get("ChatName"),
                "sender_id": item.get("SenderJID"),
                "sender_name": item.get("SenderName"),
                "timestamp": item.get("Timestamp"),
                "text": text,
                "content": text,
                "media_type": item.get("MediaType"),
                "filename": item.get("Filename"),
                "local_path": item.get("LocalPath"),
                "source": "wacli",
                "raw": item,
            }
        )
    return rows


def _search_messages_wacli(req: WhatsAppSearchRequest, task_id: str) -> ToolResult:
    args = ["--read-only", "--json", "messages", "search", req.q, "--limit", str(req.limit)]
    if req.chat:
        args.extend(["--chat", req.chat])
    ok, code, stdout, stderr, command = _run_wacli(args, timeout=30)
    if not ok:
        return ToolResult(
            ok=False,
            tool="whatsapp_search",
            task_id=task_id,
            summary="WhatsApp wacli 本地搜索失败，请确认 wacli 已登录并完成同步。",
            error=stderr or stdout or f"exit_code={code}",
            data={"source": "wacli", "command": command, "exit_code": code},
        )
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return ToolResult(
            ok=False,
            tool="whatsapp_search",
            task_id=task_id,
            summary="WhatsApp wacli 搜索输出不是 JSON。",
            error=str(exc),
            data={"source": "wacli", "raw": stdout[:4000]},
        )
    rows = _wacli_message_rows(payload)
    return ToolResult(
        ok=True,
        tool="whatsapp_search",
        task_id=task_id,
        summary=f"WhatsApp wacli 本地搜索完成，找到 {len(rows)} 条消息。",
        data={"rows": rows, "query": req.q, "source": "wacli", "raw": payload},
    )


def _normalize_hk_phone(phone: str | None) -> str:
    if not phone:
        return ""
    digits = re.sub(r"\D+", "", phone)
    if digits.startswith("852"):
        digits = digits[3:]
    if len(digits) == 8:
        return f"+852{digits}"
    return phone if phone.startswith("+") else f"+{digits}"


def _set_auth_state(**values: Any) -> None:
    with _auth_lock:
        _auth_state.update(values)
        _auth_state["updated_at"] = time.time()


def _set_auth_error(message: str) -> None:
    status = "qr_timed_out" if "qr code timed out" in message.lower() else "failed"
    values: dict[str, Any] = {
        "running": False,
        "status": status,
        "last_error": message,
    }
    if status == "qr_timed_out" or "qr" in message.lower():
        values["qr_payload"] = ""
    _set_auth_state(**values)


def _append_auth_log(line: str) -> None:
    with _auth_lock:
        logs = list(_auth_state.get("logs") or [])
        logs.append(line)
        _auth_state["logs"] = logs[-200:]
        _auth_state["updated_at"] = time.time()


def _append_sync_log(line: str) -> None:
    with _sync_lock:
        logs = list(_sync_state.get("logs") or [])
        logs.append(line)
        _sync_state["logs"] = logs[-200:]
        _sync_state["updated_at"] = time.time()


def _snapshot_auth_state(include_logs: bool = True) -> dict[str, Any]:
    with _auth_lock:
        data = dict(_auth_state)
    if not include_logs:
        data.pop("logs", None)
    process = _auth_process
    data["process_running"] = bool(process and process.poll() is None)
    return data


def _snapshot_sync_state(include_logs: bool = True) -> dict[str, Any]:
    with _sync_lock:
        data = dict(_sync_state)
    if not include_logs:
        data.pop("logs", None)
    process = _sync_process
    data["process_running"] = bool(process and process.poll() is None)
    return data


def _is_wacli_authenticated() -> tuple[bool, str]:
    ok, _code, stdout, stderr, _command = _run_wacli(["auth", "status"], timeout=15)
    output = (stdout or stderr or "").strip()
    return ok and "authenticated as" in output.lower(), output


def _extract_sync_signal(line: str) -> None:
    text = line.strip()
    if not text:
        return
    if text.startswith("{"):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return
        event = str(payload.get("event") or payload.get("status") or "")
        if event:
            _set_sync_state(status=event)
        data = payload.get("data")
        if isinstance(data, dict):
            synced = data.get("messages_synced")
            if isinstance(synced, int):
                _set_sync_state(messages_synced=synced)
    elif "connected" in text.lower():
        _set_sync_state(status="connected")
    elif "disconnected" in text.lower():
        _set_sync_state(status="disconnected")


def _set_sync_state(**values: Any) -> None:
    with _sync_lock:
        _sync_state.update(values)
        _sync_state["updated_at"] = time.time()


def _extract_auth_signal(line: str) -> None:
    text = line.strip()
    if not text:
        return
    if text.startswith("2@"):
        _set_auth_state(qr_payload=text, status="waiting_scan")
        return
    if _PAIR_RE.match(text):
        _set_auth_state(pairing_code=text.upper(), status="waiting_phone_confirm")
        return
    if text.startswith("{"):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return
        status = payload.get("status") or payload.get("event")
        data = payload.get("data")
        if isinstance(status, str) and status.lower() == "error":
            message = ""
            if isinstance(data, dict):
                message = str(data.get("message") or data.get("error") or "")
            _set_auth_error(message or "wacli auth error")
            return
        for key in ("pairingCode", "pair_code", "code"):
            value = payload.get(key)
            if isinstance(value, str) and _PAIR_RE.match(value.strip()):
                _set_auth_state(pairing_code=value.strip().upper(), status="waiting_phone_confirm")
        qr = payload.get("qr")
        if isinstance(qr, str) and qr:
            _set_auth_state(qr_payload=qr, status="waiting_scan")
        if isinstance(data, dict):
            code = data.get("code")
            event = str(status or "")
            if isinstance(code, str) and code and ("qr" in event.lower() or code.startswith("https://wa.me/")):
                _set_auth_state(qr_payload=code, status="waiting_scan")
            if isinstance(code, str) and _PAIR_RE.match(code.strip()):
                _set_auth_state(pairing_code=code.strip().upper(), status="waiting_phone_confirm")
        if isinstance(status, str) and (
            "auth" in status.lower()
            or status.lower() in {"connected", "logged_in", "login_success", "history_sync"}
        ):
            _set_auth_state(status=status)
        return
    compact = re.sub(r"[^A-Z0-9]", "", text.upper())
    if len(compact) == 8:
        _set_auth_state(pairing_code=f"{compact[:4]}-{compact[4:]}", status="waiting_phone_confirm")
    if "authenticated" in text.lower() or "connected" in text.lower():
        _set_auth_state(status="authenticated", running=False)


def _read_auth_stream(proc: subprocess.Popen[str]) -> None:
    assert proc.stdout is not None
    assert proc.stderr is not None

    def pump(stream: Any) -> None:
        for line in iter(stream.readline, ""):
            _append_auth_log(line.rstrip("\n"))
            _extract_auth_signal(line)

    threads = [
        threading.Thread(target=pump, args=(proc.stdout,), daemon=True),
        threading.Thread(target=pump, args=(proc.stderr,), daemon=True),
    ]
    for thread in threads:
        thread.start()
    code = proc.wait()
    for thread in threads:
        thread.join(timeout=1)
    with _auth_lock:
        if _auth_process is proc:
            _auth_state["running"] = False
            status = str(_auth_state.get("status") or "")
            if status not in {"authenticated", "waiting_phone_confirm", "qr_timed_out"}:
                _auth_state["status"] = "ended" if code == 0 else "failed"
            if code != 0 and status != "waiting_phone_confirm":
                _auth_state["qr_payload"] = ""
            _auth_state["last_error"] = "" if code == 0 else (_auth_state.get("last_error") or f"wacli auth exited with code {code}")
            _auth_state["updated_at"] = time.time()


def _read_sync_stream(proc: subprocess.Popen[str]) -> None:
    assert proc.stdout is not None
    assert proc.stderr is not None

    def pump(stream: Any) -> None:
        for line in iter(stream.readline, ""):
            _append_sync_log(line.rstrip("\n"))
            _extract_sync_signal(line)

    threads = [
        threading.Thread(target=pump, args=(proc.stdout,), daemon=True),
        threading.Thread(target=pump, args=(proc.stderr,), daemon=True),
    ]
    for thread in threads:
        thread.start()
    code = proc.wait()
    for thread in threads:
        thread.join(timeout=1)
    with _sync_lock:
        if _sync_process is proc:
            _sync_state["running"] = False
            _sync_state["status"] = "ended" if code == 0 else "failed"
            _sync_state["last_error"] = "" if code == 0 else f"wacli sync exited with code {code}"
            _sync_state["updated_at"] = time.time()


def _terminate_auth_process(proc: subprocess.Popen[str] | None) -> None:
    if not proc or proc.poll() is not None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def start_auth(req: WhatsAppAuthStartRequest) -> ToolResult:
    global _auth_process

    task_id = new_task_id("wa_auth")
    phone = _normalize_hk_phone(req.phone)
    requested_phone = phone if req.mode == "phone" or phone else ""
    requested_mode = "phone" if requested_phone else "qr"
    running_proc: subprocess.Popen[str] | None = None
    should_restart = False
    with _auth_lock:
        if _auth_process and _auth_process.poll() is None:
            running_proc = _auth_process
            current_phone = str(_auth_state.get("phone") or "")
            current_mode = "phone" if current_phone else "qr"
            should_restart = current_mode != requested_mode or (requested_phone and current_phone != requested_phone)
    if running_proc and not should_restart:
        return ToolResult(
            ok=True,
            tool="whatsapp_auth_start",
            task_id=task_id,
            summary="WhatsApp 登录流程已在运行。",
            data=_snapshot_auth_state(),
        )
    if running_proc and should_restart:
        _terminate_auth_process(running_proc)
        with _auth_lock:
            if _auth_process is running_proc:
                _auth_process = None

    binary = _wacli_bin()
    if not binary:
        summary, error, data = _wacli_unavailable_details("未找到 wacli，无法启动 WhatsApp 登录。")
        return ToolResult(
            ok=False,
            tool="whatsapp_auth_start",
            task_id=task_id,
            summary=summary,
            error=error,
            data=data,
        )

    authenticated, auth_output = _is_wacli_authenticated()
    if authenticated:
        _set_auth_state(running=False, status="authenticated", last_error="", qr_payload="", pairing_code="")
        return ToolResult(
            ok=True,
            tool="whatsapp_auth_start",
            task_id=task_id,
            summary="WhatsApp 已登录，无需重新生成二维码。",
            data=_snapshot_auth_state() | {"auth_status": auth_output},
        )

    args = ["--events", "auth", "--qr-format", "text", "--follow"]
    if req.mode == "phone" or phone:
        if not phone:
            return ToolResult(ok=False, tool="whatsapp_auth_start", task_id=task_id, summary="手机号配对需要先输入电话号码。", error="phone_required")
        args.extend(["--phone", phone])

    settings.wacli_workdir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.setdefault("WACLI_STORE_DIR", str(settings.wacli_store_dir))
    proc = subprocess.Popen(
        [binary, *args],
        cwd=str(settings.wacli_workdir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    now = time.time()
    with _auth_lock:
        _auth_process = proc
        _auth_state.update(
            {
                "running": True,
                "status": "starting",
                "qr_payload": "",
                "pairing_code": "",
                "phone": phone,
                "started_at": now,
                "updated_at": now,
                "logs": [],
                "last_error": "",
                "command": [binary, *args],
            }
        )
    threading.Thread(target=_read_auth_stream, args=(proc,), daemon=True).start()
    return ToolResult(ok=True, tool="whatsapp_auth_start", task_id=task_id, summary="WhatsApp 登录流程已启动。", data=_snapshot_auth_state())


def auth_status(req: WhatsAppAuthStatusRequest) -> ToolResult:
    authenticated, auth_output = _is_wacli_authenticated()
    if authenticated:
        _set_auth_state(status="authenticated", last_error="", qr_payload="", pairing_code="")
        data = _snapshot_auth_state(req.include_logs)
        data["auth_status"] = auth_output
        return ToolResult(ok=True, tool="whatsapp_auth_status", summary="WhatsApp 已登录。", data=data)
    return ToolResult(ok=True, tool="whatsapp_auth_status", summary="WhatsApp 登录状态。", data=_snapshot_auth_state(req.include_logs))


def stop_auth(req: WhatsAppAuthStopRequest) -> ToolResult:
    global _auth_process
    with _auth_lock:
        proc = _auth_process
        _auth_process = None
    _terminate_auth_process(proc)
    _set_auth_state(
        running=False,
        status="stopped",
        qr_payload="",
        pairing_code="",
        phone="",
        last_error=req.reason,
    )
    return ToolResult(ok=True, tool="whatsapp_auth_stop", summary="WhatsApp 登录流程已停止。", data=_snapshot_auth_state())


def logout_auth(req: WhatsAppAuthLogoutRequest) -> ToolResult:
    if not req.confirmed:
        return ToolResult(
            ok=False,
            tool="whatsapp_auth_logout",
            summary="退出 WhatsApp 登录需要人工确认。",
            error="confirmed must be true",
            data={"requires_human_confirmation": True, "reason": req.reason},
        )
    stop_auth(WhatsAppAuthStopRequest(reason="logout_before_auth_logout"))
    ok, code, stdout, stderr, command = _run_wacli(["auth", "logout"], timeout=60)
    if not ok:
        return ToolResult(
            ok=False,
            tool="whatsapp_auth_logout",
            summary="WhatsApp 退出登录失败。",
            error=stderr or stdout or f"exit_code={code}",
            data={"command": command, "exit_code": code},
        )
    _set_auth_state(running=False, status="logged_out", qr_payload="", pairing_code="", phone="", last_error="")
    return ToolResult(ok=True, tool="whatsapp_auth_logout", summary="WhatsApp 已退出登录。", data=_snapshot_auth_state(False) | {"command": command, "stdout": stdout[:4000]})


def start_sync(req: WhatsAppSyncStartRequest) -> ToolResult:
    global _sync_process

    task_id = new_task_id("wa_sync")
    with _sync_lock:
        already_running = bool(_sync_process and _sync_process.poll() is None)
    if already_running:
        return ToolResult(ok=True, tool="whatsapp_sync_start", task_id=task_id, summary="WhatsApp Agent 监听已在运行。", data=_snapshot_sync_state())

    authenticated, auth_output = _is_wacli_authenticated()
    if not authenticated:
        return ToolResult(
            ok=False,
            tool="whatsapp_sync_start",
            task_id=task_id,
            summary="WhatsApp 尚未登录，无法启动 Agent 监听。",
            error=auth_output or "not_authenticated",
        )

    binary = _wacli_bin()
    if not binary:
        summary, error, data = _wacli_unavailable_details("未找到 wacli。")
        return ToolResult(ok=False, tool="whatsapp_sync_start", task_id=task_id, summary=summary, error=error, data=data)

    args = ["--events", "sync", "--follow", "--webhook", req.webhook_url, "--webhook-allow-private"]
    if req.webhook_secret:
        args.extend(["--webhook-secret", req.webhook_secret])
    if req.refresh_groups:
        args.append("--refresh-groups")
    if req.download_media:
        args.append("--download-media")

    settings.wacli_workdir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.setdefault("WACLI_STORE_DIR", str(settings.wacli_store_dir))
    proc = subprocess.Popen(
        [binary, *args],
        cwd=str(settings.wacli_workdir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    now = time.time()
    with _sync_lock:
        _sync_process = proc
        _sync_state.update(
            {
                "running": True,
                "status": "starting",
                "webhook_url": req.webhook_url,
                "started_at": now,
                "updated_at": now,
                "logs": [],
                "last_error": "",
                "messages_synced": 0,
                "command": [binary, *args],
            }
        )
    threading.Thread(target=_read_sync_stream, args=(proc,), daemon=True).start()
    return ToolResult(ok=True, tool="whatsapp_sync_start", task_id=task_id, summary="WhatsApp Agent 监听已启动。", data=_snapshot_sync_state())


def sync_status(req: WhatsAppSyncStatusRequest) -> ToolResult:
    return ToolResult(ok=True, tool="whatsapp_sync_status", summary="WhatsApp Agent 监听状态。", data=_snapshot_sync_state(req.include_logs))


def stop_sync(req: WhatsAppSyncStopRequest) -> ToolResult:
    global _sync_process
    with _sync_lock:
        proc = _sync_process
        _sync_process = None
    if proc and proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    _set_sync_state(running=False, status="stopped", last_error=req.reason)
    return ToolResult(ok=True, tool="whatsapp_sync_stop", summary="WhatsApp Agent 监听已停止。", data=_snapshot_sync_state())


def search_messages(req: WhatsAppSearchRequest) -> ToolResult:
    task_id = new_task_id("wa_search")
    params = {"q": req.q, "limit": req.limit}
    if req.chat:
        params["chat"] = req.chat

    record_task_event(task_id, {"tool": "whatsapp_search", "status": "running", "query": req.q})
    try:
        resp = requests.get(f"{_base_url()}/api/messages/search", params=params, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        fallback = _search_messages_wacli(req, task_id)
        if fallback.ok:
            record_task_event(task_id, {"tool": "whatsapp_search", "status": "done", "source": "wacli", "query": req.q})
            fallback.logs.append(f"archive_search_unavailable: {exc}")
            return fallback
        record_task_event(task_id, {"tool": "whatsapp_search", "status": "failed", "error": str(exc), "fallback_error": fallback.error})
        return ToolResult(
            ok=False,
            tool="whatsapp_search",
            task_id=task_id,
            summary="WhatsApp 搜索失败：归档 app-server 不可用，wacli 本地回退也失败。",
            error=f"archive: {exc}; wacli: {fallback.error}",
            data={"archive_error": str(exc), "wacli_error": fallback.error},
        )

    payload = resp.json()
    rows = payload.get("rows", [])
    record_task_event(task_id, {"tool": "whatsapp_search", "status": "done", "count": len(rows)})
    return ToolResult(
        ok=True,
        tool="whatsapp_search",
        task_id=task_id,
        summary=f"WhatsApp 搜索完成，找到 {len(rows)} 条消息。",
        data={"rows": rows, "query": req.q},
    )


def list_groups_wacli(req: WhatsAppWacliGroupsRequest) -> ToolResult:
    task_id = new_task_id("wa_groups")
    args = ["--read-only", "--json", "groups", "list", "--limit", str(req.limit)]
    if req.dry_run:
        return ToolResult(
            ok=True,
            tool="whatsapp_groups_wacli",
            task_id=task_id,
            summary="WhatsApp 群组列表 dry-run：未执行 wacli。",
            data={"command": [settings.wacli_bin, *args], "items": []},
        )
    ok, code, stdout, stderr, command = _run_wacli(args)
    if not ok:
        return ToolResult(
            ok=False,
            tool="whatsapp_groups_wacli",
            task_id=task_id,
            summary="wacli 群组列表失败，请确认赤瞳灵讯/wacli 已安装并登录。",
            error=stderr or stdout or f"exit_code={code}",
            data={"command": command, "exit_code": code},
        )
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict) and "data" in payload and payload.get("data") is None:
        return ToolResult(
            ok=False,
            tool="whatsapp_groups_wacli",
            task_id=task_id,
            summary="wacli 未返回群组数据，请先完成 WhatsApp 登录并启动同步/刷新群组。",
            error="wacli_group_data_unavailable",
            data={"items": [], "raw": stdout[:4000], "command": command, "exit_code": code},
        )
    items = _json_items(stdout)
    return ToolResult(
        ok=True,
        tool="whatsapp_groups_wacli",
        task_id=task_id,
        summary=f"wacli 群组列表完成，找到 {len(items)} 个群组。",
        data={"items": items, "raw": stdout[:4000], "command": command},
    )


def refresh_groups_wacli(req: WhatsAppGroupsRefreshRequest) -> ToolResult:
    task_id = new_task_id("wa_groups_refresh")
    args = ["groups", "refresh"]
    if req.dry_run:
        return ToolResult(ok=True, tool="whatsapp_groups_refresh", task_id=task_id, summary="WhatsApp 群组刷新 dry-run：未执行 wacli。", data={"command": [settings.wacli_bin, *args]})
    ok, code, stdout, stderr, command = _run_wacli(args, timeout=120)
    if not ok:
        return ToolResult(
            ok=False,
            tool="whatsapp_groups_refresh",
            task_id=task_id,
            summary="WhatsApp 群组刷新失败。",
            error=stderr or stdout or f"exit_code={code}",
            data={"command": command, "exit_code": code, "stdout": stdout[:4000], "stderr": stderr[:4000]},
        )
    groups = list_groups_wacli(WhatsAppWacliGroupsRequest(limit=200))
    return ToolResult(ok=True, tool="whatsapp_groups_refresh", task_id=task_id, summary="WhatsApp 群组已刷新。", data={"command": command, "stdout": stdout[:4000], "groups": groups.data.get("items", [])})


def send_text_confirmed(req: WhatsAppSendTextRequest) -> ToolResult:
    task_id = new_task_id("wa_send")
    args = ["send", "text", "--to", req.chat, "--message", req.text]
    draft = {
        "chat": req.chat,
        "text": req.text,
        "requires_human_confirmation": True,
        "confirmed": req.confirmed,
        "confirmed_by": req.confirmed_by,
        "command": [settings.wacli_bin, *args],
    }
    if not req.confirmed:
        return ToolResult(
            ok=False,
            tool="whatsapp_send_text_confirmed",
            task_id=task_id,
            summary="已生成 WhatsApp 发送草稿，需人工确认后才会发送。",
            error="confirmed must be true",
            data=draft,
        )
    if req.dry_run:
        return ToolResult(
            ok=True,
            tool="whatsapp_send_text_confirmed",
            task_id=task_id,
            summary="WhatsApp 发送 dry-run 成功：未实际发送。",
            data=draft | {"dry_run": True, "status": "dry_run"},
        )
    record_task_event(task_id, {"tool": "whatsapp_send_text_confirmed", "status": "running", "chat": req.chat})
    try:
        ok, code, stdout, stderr, command = _run_wacli(args, timeout=60)
    except subprocess.TimeoutExpired as exc:
        record_task_event(task_id, {"tool": "whatsapp_send_text_confirmed", "status": "failed", "error": "timeout"})
        return ToolResult(
            ok=False,
            tool="whatsapp_send_text_confirmed",
            task_id=task_id,
            summary="WhatsApp 发送超时。",
            error=str(exc),
            data=draft,
        )
    if not ok:
        record_task_event(task_id, {"tool": "whatsapp_send_text_confirmed", "status": "failed", "code": code})
        return ToolResult(
            ok=False,
            tool="whatsapp_send_text_confirmed",
            task_id=task_id,
            summary="WhatsApp 消息发送失败，请确认 wacli 已登录且 chat 参数正确。",
            error=stderr or stdout or f"exit_code={code}",
            data=draft | {"command": command, "exit_code": code, "stdout": stdout[:4000], "stderr": stderr[:4000]},
        )
    record_task_event(task_id, {"tool": "whatsapp_send_text_confirmed", "status": "done", "chat": req.chat})
    return ToolResult(
        ok=True,
        tool="whatsapp_send_text_confirmed",
        task_id=task_id,
        summary="WhatsApp 消息已发送。",
        data=draft | {"command": command, "status": "sent", "stdout": stdout[:4000], "stderr": stderr[:4000]},
    )


def send_file_confirmed(req: WhatsAppSendFileRequest) -> ToolResult:
    task_id = new_task_id("wa_send_file")
    file_path = Path(req.file_path).expanduser()
    if not file_path.exists() or not file_path.is_file():
        return ToolResult(
            ok=False,
            tool="whatsapp_send_file_confirmed",
            task_id=task_id,
            summary=f"WhatsApp 附件不存在：{file_path}",
            error="file_not_found",
            data={"file_path": str(file_path), "chat": req.chat},
        )
    args = ["send", "file", "--to", req.chat, "--file", str(file_path)]
    if req.caption.strip():
        args.extend(["--caption", req.caption.strip()])
    draft = {
        "chat": req.chat,
        "file_path": str(file_path),
        "caption": req.caption,
        "requires_human_confirmation": True,
        "confirmed": req.confirmed,
        "confirmed_by": req.confirmed_by,
        "command": [settings.wacli_bin, *args],
    }
    if not req.confirmed:
        return ToolResult(
            ok=False,
            tool="whatsapp_send_file_confirmed",
            task_id=task_id,
            summary="已生成 WhatsApp 文件发送草稿，需人工确认后才会发送。",
            error="confirmed must be true",
            data=draft,
        )
    if req.dry_run:
        return ToolResult(
            ok=True,
            tool="whatsapp_send_file_confirmed",
            task_id=task_id,
            summary="WhatsApp 文件发送 dry-run 成功：未实际发送。",
            data=draft | {"dry_run": True, "status": "dry_run"},
        )
    record_task_event(task_id, {"tool": "whatsapp_send_file_confirmed", "status": "running", "chat": req.chat})
    try:
        ok, code, stdout, stderr, command = _run_wacli(args, timeout=120)
    except subprocess.TimeoutExpired as exc:
        record_task_event(task_id, {"tool": "whatsapp_send_file_confirmed", "status": "failed", "error": "timeout"})
        return ToolResult(
            ok=False,
            tool="whatsapp_send_file_confirmed",
            task_id=task_id,
            summary="WhatsApp 文件发送超时。",
            error=str(exc),
            data=draft,
        )
    if not ok:
        record_task_event(task_id, {"tool": "whatsapp_send_file_confirmed", "status": "failed", "code": code})
        return ToolResult(
            ok=False,
            tool="whatsapp_send_file_confirmed",
            task_id=task_id,
            summary="WhatsApp 文件发送失败，请确认 wacli 已登录且收件人正确。",
            error=stderr or stdout or f"exit_code={code}",
            data=draft | {"command": command, "exit_code": code, "stdout": stdout[:4000], "stderr": stderr[:4000]},
        )
    record_task_event(task_id, {"tool": "whatsapp_send_file_confirmed", "status": "done", "chat": req.chat})
    return ToolResult(
        ok=True,
        tool="whatsapp_send_file_confirmed",
        task_id=task_id,
        summary="WhatsApp 文件已发送。",
        data=draft | {"command": command, "status": "sent", "stdout": stdout[:4000], "stderr": stderr[:4000]},
    )


def download_media(req: WhatsAppDownloadMediaRequest) -> ToolResult:
    task_id = new_task_id("wa_media")
    body: dict[str, str] = {"messageId": req.message_id}
    if req.dir:
        body["dir"] = req.dir

    record_task_event(task_id, {"tool": "whatsapp_download_media", "status": "running", "message_id": req.message_id})
    try:
        resp = requests.post(f"{_base_url()}/api/media/download", json=body, timeout=120)
        resp.raise_for_status()
    except requests.RequestException as exc:
        record_task_event(task_id, {"tool": "whatsapp_download_media", "status": "failed", "error": str(exc)})
        return ToolResult(
            ok=False,
            tool="whatsapp_download_media",
            task_id=task_id,
            summary="WhatsApp 附件下载失败，请确认 app-server 和 whatscli 可用。",
            error=str(exc),
        )

    payload = resp.json()
    record_task_event(task_id, {"tool": "whatsapp_download_media", "status": "done"})
    return ToolResult(
        ok=True,
        tool="whatsapp_download_media",
        task_id=task_id,
        summary="WhatsApp 附件下载请求已完成。",
        data=payload,
    )
