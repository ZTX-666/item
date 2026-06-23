from __future__ import annotations

import importlib.util
import shutil
import sqlite3
from pathlib import Path
from typing import Any

from chitung_center import storage
from chitung_center.asset_service import list_assets
from chitung_center.config import ROOT, settings
from chitung_center.external_monitor_scheduler import external_monitor_scheduler
from chitung_center.job_service import list_jobs
from chitung_center.rag_service import rag_service
from chitung_center.toolbox_client import toolbox_client


async def build_system_diagnostics() -> dict[str, Any]:
    toolbox = await toolbox_client.health()
    db = _database_check()
    jobs = list_jobs(limit=10)
    assets = list_assets(limit=10)
    return {
        "ok": bool(toolbox.get("ok")) and db["ok"],
        "center": {
            "ok": True,
            "data_dir": str(settings.chitung_data_dir),
            "database": db,
        },
        "agent_toolbox": toolbox,
        "external_monitor": external_monitor_scheduler.status(),
        "jobs": {
            "ok": True,
            "recent_count": len(jobs.get("items", [])),
            "recent": jobs.get("items", []),
        },
        "assets": {
            "ok": True,
            "recent_count": len(assets.get("items", [])),
            "recent": assets.get("items", []),
        },
        "rag": {
            "ok": True,
            "chroma_dir": str(rag_service.chroma_dir),
            "meta_path": str(rag_service.meta_path),
            "upload_dir": str(rag_service.upload_dir),
            "document_count": len(rag_service.list_documents().get("items", [])),
        },
        "dependencies": {
            "ocr": {
                "rapidocr": importlib.util.find_spec("rapidocr_onnxruntime") is not None,
                "pytesseract": importlib.util.find_spec("pytesseract") is not None,
            },
            "vision": {
                "cv2": importlib.util.find_spec("cv2") is not None,
                "ultralytics": importlib.util.find_spec("ultralytics") is not None,
            },
            "commands": {
                        "wacli": _wacli_check(),
                "node": bool(shutil.which("node")),
                "python": bool(shutil.which("python")),
            },
        },
    }


def _database_check() -> dict[str, Any]:
    path = storage.database_path()
    try:
        storage.ensure_schema()
        with storage.connect() as conn:
            journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
            tables = [
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                ).fetchall()
            ]
        return {
            "ok": True,
            "path": str(path),
            "exists": path.exists(),
            "journal_mode": journal_mode,
            "foreign_keys": bool(foreign_keys),
            "tables": tables,
        }
    except sqlite3.Error as exc:
        return {"ok": False, "path": str(path), "error": str(exc)}


def _wacli_check() -> dict[str, Any]:
    path_value = shutil.which("wacli") or shutil.which("wacli.exe")
    candidates = [
        ROOT.parent / "publish3.0" / "runtime" / "bin" / "wacli.exe",
        ROOT.parent / "agent-toolbox" / "workspace" / "wacli" / "wacli.exe",
        ROOT.parent.parent / "publish3.0" / "runtime" / "bin" / "wacli.exe",
    ]
    existing = [str(path) for path in candidates if path.exists()]
    return {
        "available": bool(path_value or existing),
        "path": path_value,
        "packaged_candidates": existing,
    }
