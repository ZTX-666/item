from __future__ import annotations

from types import SimpleNamespace

from agent_toolbox.models import ToolResult
from agent_toolbox.mcp_server import _call_tool
from agent_toolbox.registry import tool_specs
from agent_toolbox.tools.communications import WhatsAppGroupListRequest, list_whatsapp_groups
from agent_toolbox.tools import whatsapp as whatsapp_tools
from agent_toolbox.tools.whatsapp import (
    WhatsAppAuthStartRequest,
    WhatsAppAuthStopRequest,
    WhatsAppSearchRequest,
    WhatsAppSendTextRequest,
    WhatsAppWacliGroupsRequest,
    list_groups_wacli,
    search_messages,
    send_text_confirmed,
    stop_auth,
)


class _EmptyStream:
    def readline(self):
        return ""


class _FakeProcess:
    def __init__(self, running: bool = True, code: int = 0):
        self.running = running
        self.code = code
        self.stdout = _EmptyStream()
        self.stderr = _EmptyStream()
        self.terminated = False

    def poll(self):
        return None if self.running else self.code

    def terminate(self):
        self.terminated = True
        self.running = False

    def wait(self, timeout=None):
        self.running = False
        return self.code

    def kill(self):
        self.running = False


def test_list_groups_wacli_parses_wacli_json(monkeypatch):
    def fake_run_wacli(args, timeout=60):
        assert args == ["--read-only", "--json", "groups", "list", "--limit", "20"]
        return (
            True,
            0,
            '{"items":[{"id":"120363@g.us","name":"B2 安全群"}]}',
            "",
            ["wacli", *args],
        )

    monkeypatch.setattr("agent_toolbox.tools.whatsapp._run_wacli", fake_run_wacli)

    result = list_groups_wacli(WhatsAppWacliGroupsRequest(limit=20))

    assert result.ok is True
    assert result.data["items"] == [{"id": "120363@g.us", "name": "B2 安全群"}]
    assert result.data["command"] == ["wacli", "--read-only", "--json", "groups", "list", "--limit", "20"]


def test_list_groups_wacli_treats_null_data_as_unavailable(monkeypatch):
    def fake_run_wacli(args, timeout=60):
        return (
            True,
            0,
            '{"success":true,"data":null,"error":null}',
            "",
            ["wacli", *args],
        )

    monkeypatch.setattr("agent_toolbox.tools.whatsapp._run_wacli", fake_run_wacli)

    result = list_groups_wacli(WhatsAppWacliGroupsRequest(limit=20))

    assert result.ok is False
    assert result.error == "wacli_group_data_unavailable"
    assert result.data["items"] == []
    assert result.data["raw"] == '{"success":true,"data":null,"error":null}'


def test_search_messages_treats_null_wacli_messages_as_empty_results(monkeypatch):
    def fake_get(*args, **kwargs):
        raise whatsapp_tools.requests.RequestException("archive down")

    def fake_run_wacli(args, timeout=60):
        return (
            True,
            0,
            '{"success":true,"data":{"fts":true,"messages":null},"error":null}',
            "",
            ["wacli", *args],
        )

    monkeypatch.setattr(whatsapp_tools.requests, "get", fake_get)
    monkeypatch.setattr("agent_toolbox.tools.whatsapp._run_wacli", fake_run_wacli)

    result = search_messages(WhatsAppSearchRequest(q="整改", limit=5))

    assert result.ok is True
    assert result.summary == "WhatsApp wacli 本地搜索完成，找到 0 条消息。"
    assert result.data["rows"] == []
    assert result.data["query"] == "整改"


def test_send_text_confirmed_requires_confirmation_before_wacli(monkeypatch):
    calls: list[list[str]] = []

    def fake_run_wacli(args, timeout=60):
        calls.append(args)
        return True, 0, '{"message_id":"wamid-test"}', "", ["wacli", *args]

    monkeypatch.setattr("agent_toolbox.tools.whatsapp._run_wacli", fake_run_wacli)

    blocked = send_text_confirmed(
        WhatsAppSendTextRequest(chat="B2 安全群", text="请复核临边围护", confirmed=False)
    )
    assert blocked.ok is False
    assert calls == []

    sent = send_text_confirmed(
        WhatsAppSendTextRequest(
            chat="B2 安全群",
            text="请复核临边围护",
            confirmed=True,
            confirmed_by="safety_officer",
        )
    )

    assert sent.ok is True
    assert calls == [["send", "text", "--to", "B2 安全群", "--message", "请复核临边围护"]]
    assert sent.data["confirmed_by"] == "safety_officer"


def test_list_whatsapp_groups_prefers_wacli_over_placeholder(monkeypatch):
    monkeypatch.setattr(
        "agent_toolbox.tools.communications.list_groups_wacli",
        lambda request: ToolResult(
            ok=True,
            tool="whatsapp_groups_wacli",
            summary="real groups",
            data={"items": [{"id": "real-group", "name": "真实群组", "source": "wacli"}]},
        ),
    )

    result = list_whatsapp_groups(WhatsAppGroupListRequest())

    assert result.ok is True
    assert result.tool == "list_whatsapp_groups"
    assert result.data["items"][0]["id"] == "real-group"


def test_registry_and_mcp_expose_whatsapp_runtime_tools(monkeypatch):
    specs = {spec.name: spec for spec in tool_specs()}

    for name in [
        "whatsapp_auth_start",
        "whatsapp_auth_status",
        "whatsapp_groups_wacli",
        "whatsapp_groups_refresh",
        "whatsapp_send_text_confirmed",
        "whatsapp_sync_start",
        "whatsapp_sync_status",
        "whatsapp_sync_stop",
    ]:
        assert name in specs

    result = _call_tool(
        "whatsapp_send_text_confirmed",
        {"chat": "B2 安全群", "text": "dry run", "confirmed": True, "dry_run": True},
    )

    assert result["ok"] is True
    assert result["data"]["status"] == "dry_run"


def test_wacli_bin_uses_publish3_runtime_exe_on_windows(monkeypatch, tmp_path):
    exe = tmp_path / "publish3.0" / "runtime" / "bin" / "wacli.exe"
    exe.parent.mkdir(parents=True)
    exe.write_text("fake windows exe")
    fake_settings = SimpleNamespace(wacli_bin="wacli", root=tmp_path / "agent-toolbox")

    monkeypatch.setattr(whatsapp_tools, "settings", fake_settings)
    monkeypatch.setattr(whatsapp_tools.shutil, "which", lambda name: None)
    monkeypatch.setattr(whatsapp_tools, "_is_windows_platform", lambda: True)

    assert whatsapp_tools._wacli_bin() == str(exe)


def test_wacli_bin_uses_publish3_runtime_darwin_binary(monkeypatch, tmp_path):
    binary = tmp_path / "publish3.0" / "runtime" / "bin" / "wacli-darwin-arm64"
    binary.parent.mkdir(parents=True)
    binary.write_text("fake darwin binary")
    fake_settings = SimpleNamespace(wacli_bin="wacli", root=tmp_path / "agent-toolbox")

    monkeypatch.setattr(whatsapp_tools, "settings", fake_settings)
    monkeypatch.setattr(whatsapp_tools.shutil, "which", lambda name: None)
    monkeypatch.setattr(whatsapp_tools, "_is_windows_platform", lambda: False)
    monkeypatch.setattr(whatsapp_tools, "_platform_wacli_name", lambda: "wacli-darwin-arm64")

    assert whatsapp_tools._wacli_bin() == str(binary)


def test_auth_start_explains_packaged_windows_exe_on_non_windows(monkeypatch, tmp_path):
    exe = tmp_path / "publish3.0" / "runtime" / "bin" / "wacli.exe"
    exe.parent.mkdir(parents=True)
    exe.write_text("fake windows exe")
    fake_settings = SimpleNamespace(wacli_bin="wacli", root=tmp_path / "agent-toolbox")

    monkeypatch.setattr(whatsapp_tools, "settings", fake_settings)
    monkeypatch.setattr(whatsapp_tools.shutil, "which", lambda name: None)
    monkeypatch.setattr(whatsapp_tools, "_is_windows_platform", lambda: False)

    result = whatsapp_tools.start_auth(WhatsAppAuthStartRequest())

    assert result.ok is False
    assert result.error == "packaged_wacli_is_windows_only"
    assert "Windows" in result.summary
    assert result.data["detected_windows_wacli"] == str(exe)


def test_auth_start_switches_running_qr_flow_to_phone_pairing(monkeypatch, tmp_path):
    old_proc = _FakeProcess(running=True)
    new_proc = _FakeProcess(running=True)
    popen_calls: list[list[str]] = []
    fake_settings = SimpleNamespace(
        wacli_bin="wacli",
        wacli_workdir=tmp_path,
        wacli_store_dir=tmp_path,
    )

    def fake_popen(command, **kwargs):
        popen_calls.append(command)
        return new_proc

    monkeypatch.setattr(whatsapp_tools, "settings", fake_settings)
    monkeypatch.setattr(whatsapp_tools, "_auth_process", old_proc)
    monkeypatch.setattr(whatsapp_tools, "_auth_state", whatsapp_tools._auth_state | {"phone": "", "status": "waiting_scan"})
    monkeypatch.setattr(whatsapp_tools, "_wacli_bin", lambda: "/bin/wacli")
    monkeypatch.setattr(whatsapp_tools, "_is_wacli_authenticated", lambda: (False, "Not authenticated"))
    monkeypatch.setattr(whatsapp_tools.subprocess, "Popen", fake_popen)

    result = whatsapp_tools.start_auth(WhatsAppAuthStartRequest(mode="phone", phone="+85291234567"))

    assert old_proc.terminated is True
    assert result.ok is True
    assert result.data["phone"] == "+85291234567"
    assert popen_calls == [
        ["/bin/wacli", "--events", "auth", "--qr-format", "text", "--follow", "--phone", "+85291234567"]
    ]


def test_stop_auth_clears_transient_login_state(monkeypatch):
    old_proc = _FakeProcess(running=True)
    monkeypatch.setattr(whatsapp_tools, "_auth_process", old_proc)
    monkeypatch.setattr(
        whatsapp_tools,
        "_auth_state",
        whatsapp_tools._auth_state
        | {
            "phone": "+85291234567",
            "pairing_code": "ABCD-EFGH",
            "qr_payload": "qr-payload",
            "status": "waiting_phone_confirm",
        },
    )

    result = stop_auth(WhatsAppAuthStopRequest(reason="manual_stop"))

    assert result.ok is True
    assert result.data["status"] == "stopped"
    assert result.data["phone"] == ""
    assert result.data["pairing_code"] == ""
    assert result.data["qr_payload"] == ""


def test_qr_timeout_event_clears_stale_qr_payload(monkeypatch):
    monkeypatch.setattr(
        whatsapp_tools,
        "_auth_state",
        whatsapp_tools._auth_state
        | {
            "running": True,
            "status": "waiting_scan",
            "qr_payload": "stale-qr-payload",
            "pairing_code": "",
            "last_error": "",
        },
    )

    whatsapp_tools._extract_auth_signal(
        '{"event":"error","data":{"message":"QR code timed out; run `wacli auth` again to get a new code"}}'
    )

    assert whatsapp_tools._auth_state["running"] is False
    assert whatsapp_tools._auth_state["status"] == "qr_timed_out"
    assert whatsapp_tools._auth_state["qr_payload"] == ""
    assert "QR code timed out" in whatsapp_tools._auth_state["last_error"]
