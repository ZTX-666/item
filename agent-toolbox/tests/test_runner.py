from __future__ import annotations

import subprocess

from agent_toolbox.runner import run_command


def test_run_command_does_not_pass_windows_hide_on_non_windows(monkeypatch):
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured.update(kwargs)
        return subprocess.CompletedProcess(command, 0, "ok", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_command(["echo", "ok"])

    assert result.stdout == "ok"
    assert "windows_hide" not in captured
