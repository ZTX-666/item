from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path
from typing import Any

from chitung_center import storage


def ensure_schema() -> None:
    storage.ensure_schema()
    with storage.transaction() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS assets (
                asset_id TEXT PRIMARY KEY,
                stored_path TEXT NOT NULL,
                original_name TEXT,
                mime_type TEXT,
                size_bytes INTEGER DEFAULT 0,
                source_module TEXT NOT NULL,
                source_id TEXT,
                checksum TEXT,
                created_at TEXT NOT NULL,
                metadata_json TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS documents (
                document_id TEXT PRIMARY KEY,
                asset_id TEXT,
                title TEXT NOT NULL,
                document_type TEXT,
                collection TEXT,
                source_module TEXT,
                created_at TEXT NOT NULL,
                metadata_json TEXT DEFAULT '{}',
                FOREIGN KEY(asset_id) REFERENCES assets(asset_id)
            );

            CREATE TABLE IF NOT EXISTS document_chunks (
                chunk_id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                collection TEXT,
                text TEXT NOT NULL,
                embedding_id TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(document_id) REFERENCES documents(document_id)
            );
            """
        )


def register_asset(
    *,
    stored_path: str | Path,
    source_module: str,
    original_name: str | None = None,
    source_id: str | None = None,
    mime_type: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ensure_schema()
    path = Path(stored_path)
    asset_id = f"asset_{uuid.uuid4().hex[:16]}"
    guessed_mime = mime_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    created_at = storage.now_iso()
    size = path.stat().st_size if path.exists() else 0
    with storage.transaction() as conn:
        conn.execute(
            """
            INSERT INTO assets (
                asset_id, stored_path, original_name, mime_type, size_bytes,
                source_module, source_id, created_at, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                asset_id,
                str(path),
                original_name or path.name,
                guessed_mime,
                size,
                source_module,
                source_id,
                created_at,
                storage_json(metadata or {}),
            ),
        )
    return get_asset(asset_id) or {"asset_id": asset_id, "stored_path": str(path)}


def register_document(
    *,
    title: str,
    source_module: str,
    asset_id: str | None = None,
    document_type: str | None = None,
    collection: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ensure_schema()
    document_id = f"doc_{uuid.uuid4().hex[:16]}"
    created_at = storage.now_iso()
    with storage.transaction() as conn:
        conn.execute(
            """
            INSERT INTO documents (
                document_id, asset_id, title, document_type, collection, source_module, created_at, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                asset_id,
                title,
                document_type,
                collection,
                source_module,
                created_at,
                storage_json(metadata or {}),
            ),
        )
    return {"document_id": document_id, "asset_id": asset_id, "title": title, "created_at": created_at}


def get_asset(asset_id: str) -> dict[str, Any] | None:
    ensure_schema()
    with storage.connect() as conn:
        row = conn.execute("SELECT * FROM assets WHERE asset_id = ?", (asset_id,)).fetchone()
    return _row_to_asset(row) if row else None


def list_assets(source_module: str | None = None, limit: int = 50) -> dict[str, Any]:
    ensure_schema()
    limit = max(1, min(limit, 200))
    with storage.connect() as conn:
        if source_module:
            rows = conn.execute(
                "SELECT * FROM assets WHERE source_module = ? ORDER BY datetime(created_at) DESC LIMIT ?",
                (source_module, limit),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM assets ORDER BY datetime(created_at) DESC LIMIT ?", (limit,)).fetchall()
    return {"ok": True, "items": [_row_to_asset(row) for row in rows]}


def _row_to_asset(row: Any) -> dict[str, Any]:
    return {
        "asset_id": row["asset_id"],
        "stored_path": row["stored_path"],
        "original_name": row["original_name"],
        "mime_type": row["mime_type"],
        "size_bytes": row["size_bytes"],
        "source_module": row["source_module"],
        "source_id": row["source_id"],
        "created_at": row["created_at"],
    }


def storage_json(value: dict[str, Any]) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, default=str)
