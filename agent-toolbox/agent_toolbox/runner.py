from __future__ import annotations

import os
import subprocess
from pathlib import Path


class CommandError(RuntimeError):
    def __init__(self, command: list[str], returncode: int, stdout: str, stderr: str):
        self.command = command
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(f"Command failed with exit code {returncode}: {' '.join(command)}")


def run_command(command: list[str], cwd: Path | None = None, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    kwargs: dict[str, object] = {
        "cwd": str(cwd) if cwd else None,
        "capture_output": True,
        "text": True,
        "timeout": timeout,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    result = subprocess.run(command, **kwargs)
    if result.returncode != 0:
        raise CommandError(command, result.returncode, result.stdout, result.stderr)
    return result
