"""Yaoyao Template Store — save/load OCR recognition templates as JSON.

Python rewrite of PaddlePdfOcrApp/Services/TemplatePersistenceService.cs.
Templates contain region definitions + previously recognized result rows.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import settings


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TemplateStore:
    """Persist and load OCR recognition templates.

    Equivalent to PaddlePdfOcrApp.Services.TemplatePersistenceService.
    Templates are stored as JSON files in the yaoyao work directory.
    """

    def __init__(self, work_dir: Path | None = None) -> None:
        self._work_dir = work_dir or settings.yaoyao_work_dir
        self._templates_dir = self._work_dir / "templates"
        self._templates_dir.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        regions: list[dict[str, Any]],
        rows: list[dict[str, Any]] | None = None,
        name: str | None = None,
        template_id: str | None = None,
    ) -> dict[str, Any]:
        """Save a template and return its metadata.

        *regions*: list of {name, x, y, width, height, angle}.
        *rows*: list of {page, values: {field_name: value}}.
        """
        if not template_id:
            template_id = f"tpl_{uuid.uuid4().hex[:12]}"

        template = {
            "id": template_id,
            "name": name or f"Template {template_id[-6:]}",
            "created_at": _utc_now_iso(),
            "regions": [
                {
                    "name": r.get("name", ""),
                    "x": float(r.get("x", 0)),
                    "y": float(r.get("y", 0)),
                    "width": float(r.get("width", 0)),
                    "height": float(r.get("height", 0)),
                    "angle": float(r.get("angle", 0)),
                }
                for r in regions
            ],
            "rows": rows or [],
        }

        file_path = self._templates_dir / f"{template_id}.json"
        file_path.write_text(
            json.dumps(template, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return {
            "ok": True,
            "template_id": template_id,
            "name": template["name"],
            "path": str(file_path),
            "region_count": len(template["regions"]),
            "row_count": len(template["rows"]),
        }

    def load(self, template_id: str) -> dict[str, Any]:
        """Load a template by ID."""
        file_path = self._templates_dir / f"{template_id}.json"
        if not file_path.exists():
            raise FileNotFoundError(f"Template not found: {template_id}")

        template = json.loads(file_path.read_text(encoding="utf-8"))
        return template

    def list_templates(self) -> list[dict[str, Any]]:
        """List all saved templates (metadata only)."""
        templates: list[dict[str, Any]] = []
        for fp in sorted(self._templates_dir.glob("*.json")):
            try:
                tpl = json.loads(fp.read_text(encoding="utf-8"))
                templates.append({
                    "id": tpl.get("id", fp.stem),
                    "name": tpl.get("name", fp.stem),
                    "created_at": tpl.get("created_at", ""),
                    "region_count": len(tpl.get("regions", [])),
                    "row_count": len(tpl.get("rows", [])),
                })
            except Exception:
                continue
        return templates

    def delete(self, template_id: str) -> bool:
        """Delete a template by ID.  Returns True if deleted."""
        file_path = self._templates_dir / f"{template_id}.json"
        if file_path.exists():
            file_path.unlink()
            return True
        return False


# ── module-level singleton ──────────────────────────────────────

_template_store: TemplateStore | None = None


def get_template_store() -> TemplateStore:
    global _template_store
    if _template_store is None:
        _template_store = TemplateStore()
    return _template_store
