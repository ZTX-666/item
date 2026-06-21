from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from chitung_center.config import settings


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AuditLogger:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or settings.chitung_audit_log
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event_type: str, payload: dict[str, Any]) -> str:
        audit_id = str(uuid.uuid4())
        event = {
            "audit_id": audit_id,
            "timestamp": utc_now_iso(),
            "event_type": event_type,
            "payload": payload,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        return audit_id


audit_logger = AuditLogger()
