"""Promote the 202605+ safety compilation PDF to the builtin RAG document."""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from chitung_center.config import settings  # noqa: E402
from chitung_center.rag_service import (  # noqa: E402
    BUILTIN_SAFETY_COLLECTION,
    BUILTIN_SAFETY_DOC_ID,
    BUILTIN_SAFETY_FILE_NAME,
    RagService,
)

SOURCE_DOC_ID = "8f2cf044e0094bc185640061cf56a277"
OLD_BUILTIN_NAME = "内置安全管理规定"


def migrate() -> None:
    service = RagService()
    meta = service._read_meta()
    source = meta.get(SOURCE_DOC_ID)
    if not source:
        print(f"Source document not found in rag_meta.json: {SOURCE_DOC_ID}")
        sys.exit(1)

    collection = service._collection()
    source_rows = collection.get(where={"doc_id": SOURCE_DOC_ID}, include=["documents", "metadatas", "embeddings"])
    source_ids = source_rows.get("ids") or []
    if not source_ids:
        print(f"No Chroma chunks found for source doc: {SOURCE_DOC_ID}")
        sys.exit(1)

    documents = source_rows.get("documents") or []
    metadatas = source_rows.get("metadatas") or []
    embeddings = source_rows.get("embeddings")

    collection.delete(where={"doc_id": BUILTIN_SAFETY_DOC_ID})
    collection.delete(where={"doc_id": SOURCE_DOC_ID})

    new_ids: list[str] = []
    new_metadatas: list[dict] = []
    for metadata in metadatas:
        if not isinstance(metadata, dict):
            continue
        chunk_index = int(metadata.get("chunk_index") or 0)
        new_ids.append(f"{BUILTIN_SAFETY_DOC_ID}:{chunk_index}")
        new_metadatas.append(
            {
                "doc_id": BUILTIN_SAFETY_DOC_ID,
                "file_name": BUILTIN_SAFETY_FILE_NAME,
                "file_type": "builtin",
                "chunk_index": chunk_index,
                "collection": BUILTIN_SAFETY_COLLECTION,
            }
        )

    upsert_kwargs: dict = {
        "ids": new_ids,
        "documents": documents,
        "metadatas": new_metadatas,
    }
    if embeddings is not None:
        upsert_kwargs["embeddings"] = embeddings
    collection.upsert(**upsert_kwargs)

    source_path = Path(str(source.get("stored_path") or ""))
    target_path = settings.rag_upload_dir / f"{BUILTIN_SAFETY_DOC_ID}.pdf"
    if source_path.exists():
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if source_path.resolve() != target_path.resolve():
            shutil.copy2(source_path, target_path)
    elif not target_path.exists():
        print(f"Warning: source PDF missing at {source_path}")

    created_at = str(source.get("created_at") or datetime.now(timezone.utc).isoformat())
    meta.pop(SOURCE_DOC_ID, None)
    meta[BUILTIN_SAFETY_DOC_ID] = {
        "doc_id": BUILTIN_SAFETY_DOC_ID,
        "file_name": BUILTIN_SAFETY_FILE_NAME,
        "file_type": "builtin",
        "chunk_count": len(new_ids),
        "collection": BUILTIN_SAFETY_COLLECTION,
        "stored_path": str(target_path),
        "created_at": created_at,
    }
    service._write_meta(meta)

    print(f"Removed old builtin: {OLD_BUILTIN_NAME}")
    print(f"Promoted {SOURCE_DOC_ID} -> {BUILTIN_SAFETY_DOC_ID} ({len(new_ids)} chunks)")
    print(f"Stored PDF: {target_path}")


if __name__ == "__main__":
    migrate()
