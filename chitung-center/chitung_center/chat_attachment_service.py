from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import quote

from chitung_center.config import ROOT, settings

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}
DOC_SUFFIXES = {".pdf", ".docx", ".xlsx", ".xls", ".csv", ".md", ".txt", ".json", ".zip", ".doc", ".pptx"}


def allowed_roots() -> list[Path]:
    roots = [
        settings.chitung_data_dir.resolve(),
        ROOT.resolve(),
        (ROOT.parent / "agent-toolbox").resolve(),
    ]
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root)
        if key in seen:
            continue
        seen.add(key)
        unique.append(root)
    return unique


def resolve_chat_attachment_path(raw_path: str) -> Path | None:
    cleaned = str(raw_path or "").strip()
    if not cleaned or cleaned.startswith(("http://", "https://", "data:", "/api/")):
        return None
    path = Path(cleaned).expanduser()
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    else:
        path = path.resolve()
    if not path.exists() or not path.is_file():
        return None
    for root in allowed_roots():
        try:
            path.relative_to(root)
            return path
        except ValueError:
            continue
    return None


def chat_attachment_api_url(path: str) -> str:
    return f"/api/chat/attachment?path={quote(path, safe='')}"


def attachment_meta(path: Path) -> dict[str, Any]:
    mime, _ = mimetypes.guess_type(str(path))
    stat = path.stat()
    suffix = path.suffix.lower()
    return {
        "file_name": path.name,
        "mime": mime or "application/octet-stream",
        "size": stat.st_size,
        "is_image": suffix in IMAGE_SUFFIXES or str(mime or "").startswith("image/"),
    }


def normalize_asset_ref(raw: str | None) -> str:
    cleaned = str(raw or "").strip()
    if not cleaned:
        return ""
    if cleaned.startswith(("http://", "https://", "data:")):
        return cleaned
    if cleaned.startswith("/api/"):
        return cleaned
    resolved = resolve_chat_attachment_path(cleaned)
    if resolved:
        suffix = resolved.suffix.lower()
        if suffix in IMAGE_SUFFIXES:
            return f"/api/yaoyao/preview-file?path={quote(cleaned)}"
        return chat_attachment_api_url(cleaned)
    if Path(cleaned).suffix.lower() in IMAGE_SUFFIXES:
        return f"/api/yaoyao/preview-file?path={quote(cleaned)}"
    return chat_attachment_api_url(cleaned)
