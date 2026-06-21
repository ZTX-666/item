from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import settings


def new_task_id(prefix: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{prefix}_{stamp}_{uuid.uuid4().hex[:8]}"


def ensure_workspace() -> Path:
    settings.workspace.mkdir(parents=True, exist_ok=True)
    (settings.workspace / "tasks").mkdir(parents=True, exist_ok=True)
    return settings.workspace


def task_dir(task_id: str) -> Path:
    ensure_workspace()
    path = settings.workspace / "tasks" / task_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def record_task_event(task_id: str, event: dict[str, Any]) -> None:
    path = task_dir(task_id) / "events.jsonl"
    event = {
        "time": datetime.now(timezone.utc).isoformat(),
        **event,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def copy_input_file(src: Path, task_id: str) -> Path:
    import shutil

    if not src.is_file():
        raise FileNotFoundError(f"Input file does not exist: {src}")
    dest = task_dir(task_id) / "input" / src.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest
