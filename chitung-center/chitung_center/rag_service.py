from __future__ import annotations

import json
import hashlib
import io
import math
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import UploadFile

from chitung_center.asset_service import register_asset, register_document
from chitung_center.config import settings
from chitung_center.llm_gateway import llm_gateway


SUPPORTED_SUFFIXES = {".pdf", ".docx", ".txt", ".md", ".markdown", ".html", ".htm"}
BUILTIN_SAFETY_COLLECTION = "safety"
BUILTIN_SAFETY_DOC_ID = "builtin-safety-management-rules"
BUILTIN_SAFETY_FILE_NAME = "《中建香港安全管理辦法彙編》(202605+版).pdf"


class RagServiceError(RuntimeError):
    """Clear user-facing RAG failure that should not crash FastAPI startup."""


class RagDependencyError(RagServiceError):
    pass


class RagService:
    collection_name = "chitung_rag"

    def __init__(self) -> None:
        self.chroma_dir = settings.rag_chroma_dir
        self.meta_path = settings.rag_meta_path
        self.upload_dir = settings.rag_upload_dir
        self.chroma_dir.mkdir(parents=True, exist_ok=True)
        self.meta_path.parent.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self._sentence_model: Any | None = None

    async def upload_document(self, upload: UploadFile, collection: str = "default") -> dict[str, Any]:
        filename = Path(upload.filename or "document").name
        suffix = Path(filename).suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            raise RagServiceError(f"Unsupported document type: {suffix or '(none)'}")

        doc_id = uuid.uuid4().hex
        target = self.upload_dir / f"{doc_id}{suffix}"
        content = await upload.read()
        if not content:
            raise RagServiceError("Uploaded file is empty.")
        target.write_bytes(content)

        text = self._load_text(target, filename)
        chunks = _filter_searchable_chunks(self._split_text(text))
        if not chunks:
            raise RagServiceError("No searchable text could be extracted from the document. The PDF text may be scanned or garbled.")

        chunk_ids = [f"{doc_id}:{idx}" for idx in range(len(chunks))]
        metadatas = [
            {
                "doc_id": doc_id,
                "file_name": filename,
                "file_type": suffix.lstrip("."),
                "chunk_index": idx,
                "collection": collection or "default",
            }
            for idx in range(len(chunks))
        ]
        embeddings = await self._embed_texts(chunks)
        collection_obj = self._collection()
        if embeddings is None:
            collection_obj.add(ids=chunk_ids, documents=chunks, metadatas=metadatas)
        else:
            collection_obj.add(ids=chunk_ids, documents=chunks, metadatas=metadatas, embeddings=embeddings)

        created_at = datetime.now(timezone.utc).isoformat()
        meta = self._read_meta()
        meta[doc_id] = {
            "doc_id": doc_id,
            "file_name": filename,
            "file_type": suffix.lstrip("."),
            "chunk_count": len(chunks),
            "collection": collection or "default",
            "stored_path": str(target),
            "created_at": created_at,
        }
        self._write_meta(meta)
        try:
            asset = register_asset(
                stored_path=target,
                source_module="rag",
                original_name=filename,
                source_id=doc_id,
                metadata={"collection": collection or "default", "chunk_count": len(chunks)},
            )
            register_document(
                title=filename,
                source_module="rag",
                asset_id=str(asset.get("asset_id") or ""),
                document_type=suffix.lstrip("."),
                collection=collection or "default",
                metadata={"doc_id": doc_id, "chunk_count": len(chunks)},
            )
        except Exception:
            pass
        return {
            "ok": True,
            "doc_id": doc_id,
            "chunk_count": len(chunks),
            "file_name": filename,
            "file_type": suffix.lstrip("."),
            "collection": collection or "default",
            "created_at": created_at,
        }

    def list_documents(self, collection: str | None = None) -> dict[str, Any]:
        if collection in (None, "", BUILTIN_SAFETY_COLLECTION):
            self.ensure_builtin_safety_knowledge()
        meta = self._read_meta()
        items = list(meta.values())
        if collection:
            items = [item for item in items if item.get("collection", "default") == collection]
        return {"ok": True, "items": sorted(items, key=lambda item: item.get("created_at", ""), reverse=True)}

    def delete_document(self, doc_id: str) -> dict[str, Any]:
        if doc_id.startswith("builtin-"):
            raise RagServiceError("Built-in knowledge documents cannot be deleted.")
        meta = self._read_meta()
        if doc_id not in meta:
            raise RagServiceError(f"Document not found: {doc_id}")
        self._collection().delete(where={"doc_id": doc_id})
        stored_path = meta[doc_id].get("stored_path")
        if stored_path:
            Path(str(stored_path)).unlink(missing_ok=True)
        removed = meta.pop(doc_id)
        self._write_meta(meta)
        return {"ok": True, "doc_id": doc_id, "removed_chunks": removed.get("chunk_count", 0)}

    async def query(self, query: str, top_k: int = 5, collection: str | None = None) -> dict[str, Any]:
        if collection in (None, "", BUILTIN_SAFETY_COLLECTION):
            self.ensure_builtin_safety_knowledge()
        where = {"collection": collection} if collection else None
        query_embeddings = await self._embed_texts([query])
        if query_embeddings is None:
            result = self._collection().query(query_texts=[query], n_results=top_k, where=where)
        else:
            result = self._collection().query(query_embeddings=query_embeddings, n_results=top_k, where=where)
        documents = result.get("documents", [[]])[0] if result.get("documents") else []
        metadatas = result.get("metadatas", [[]])[0] if result.get("metadatas") else []
        distances = result.get("distances", [[]])[0] if result.get("distances") else []
        matches = []
        for idx, text in enumerate(documents):
            metadata = metadatas[idx] if idx < len(metadatas) and isinstance(metadatas[idx], dict) else {}
            text_value = str(text or "")
            text_quality = _text_quality(text_value)
            matches.append(
                {
                    "text": text_value,
                    "display_text": _display_text(text_value, text_quality),
                    "text_quality": text_quality,
                    "source_file_name": metadata.get("file_name", ""),
                    "doc_id": metadata.get("doc_id", ""),
                    "chunk_index": metadata.get("chunk_index", 0),
                    "collection": metadata.get("collection", "default"),
                    "score": distances[idx] if idx < len(distances) else None,
                }
            )
        return {"ok": True, "query": query, "items": matches}

    async def answer_question(self, question: str, top_k: int = 5, collection: str | None = None) -> dict[str, Any]:
        search = await self.query(question, top_k=top_k, collection=collection)
        matches = [item for item in search.get("items", []) if isinstance(item, dict)]
        usable_matches = [item for item in matches if item.get("text_quality") != "garbled"]
        if not matches:
            return {
                "ok": True,
                "query": question,
                "answer": "知识库里没有检索到足够相关的内容。请先上传制度、规范或报告资料，或换一个更具体的问题。",
                "citations": [],
                "matches": [],
            }
        if not usable_matches:
            return {
                "ok": True,
                "query": question,
                "answer": "知识库检索到了相关片段，但这些片段的 PDF 文字解析质量较低，暂不能作为可靠回答依据。请重新上传可复制文本 PDF/Word，或先将 PDF 转成文本后再入库。",
                "citations": [],
                "matches": matches,
            }

        system_prompt = (
            "你是赤瞳安全智能平台的 RAG 问答助手。只根据给定知识库片段回答，"
            "不要编造未出现在片段中的制度条款。输出 JSON object，字段为 answer 和 citations。"
            "citations 是数组，每项包含 source_file_name 和 chunk_index。"
        )
        user_text = _build_answer_user_text(question, usable_matches)
        llm_error = ""
        try:
            raw = await llm_gateway.complete_json(system_prompt, user_text)
            parsed = _extract_json_object(raw)
            answer = str(parsed.get("answer") or "").strip()
            if answer:
                return {
                    "ok": True,
                    "query": question,
                    "answer": answer,
                    "citations": _normalize_citations(parsed.get("citations"), usable_matches),
                    "matches": matches,
                    "llm_raw": raw,
                }
        except Exception as exc:  # noqa: BLE001
            llm_error = str(exc)

        return {
            "ok": True,
            "query": question,
            "answer": _fallback_answer(usable_matches),
            "citations": _default_citations(usable_matches),
            "matches": matches,
            "llm_error": llm_error or "LLM did not return a usable answer.",
        }

    def stats(self, collection: str | None = None) -> dict[str, Any]:
        if collection in (None, "", BUILTIN_SAFETY_COLLECTION):
            self.ensure_builtin_safety_knowledge()
        meta = self._read_meta()
        items = list(meta.values())
        if collection:
            items = [item for item in items if item.get("collection", "default") == collection]
        chunk_count = sum(int(item.get("chunk_count", 0)) for item in items)
        try:
            if collection:
                result = self._collection().get(where={"collection": collection}, include=[])
                vector_count = len(result.get("ids", []))
            else:
                vector_count = self._collection().count()
        except Exception:
            vector_count = 0
        return {
            "ok": True,
            "document_count": len(items),
            "chunk_count": chunk_count,
            "vector_count": vector_count,
            "chroma_dir": str(self.chroma_dir),
        }

    def ensure_builtin_safety_knowledge(self) -> None:
        meta = self._read_meta()
        entry = meta.get(BUILTIN_SAFETY_DOC_ID)
        if isinstance(entry, dict) and entry.get("file_type") == "builtin":
            return
        if entry and str(entry.get("file_name") or "") == "内置安全管理规定":
            self._upgrade_legacy_builtin(meta, entry)
            return
        self._upgrade_legacy_uploaded_compilation(meta)

    def _upgrade_legacy_builtin(self, meta: dict[str, dict[str, Any]], entry: dict[str, Any]) -> None:
        source_id = self._find_uploaded_compilation_doc_id(meta)
        if not source_id:
            return
        self._promote_uploaded_compilation_to_builtin(meta, source_id, entry.get("created_at"))

    def _upgrade_legacy_uploaded_compilation(self, meta: dict[str, dict[str, Any]]) -> None:
        source_id = self._find_uploaded_compilation_doc_id(meta)
        if not source_id:
            return
        self._promote_uploaded_compilation_to_builtin(meta, source_id)

    def _find_uploaded_compilation_doc_id(self, meta: dict[str, dict[str, Any]]) -> str | None:
        for doc_id, item in meta.items():
            if doc_id.startswith("builtin-"):
                continue
            if not isinstance(item, dict):
                continue
            if str(item.get("file_name") or "") == BUILTIN_SAFETY_FILE_NAME:
                return doc_id
        return None

    def _promote_uploaded_compilation_to_builtin(
        self,
        meta: dict[str, dict[str, Any]],
        source_doc_id: str,
        created_at: str | None = None,
    ) -> None:
        source = meta.get(source_doc_id)
        if not isinstance(source, dict):
            return
        try:
            collection = self._collection()
            rows = collection.get(where={"doc_id": source_doc_id}, include=["documents", "metadatas", "embeddings"])
            source_ids = rows.get("ids") or []
            if not source_ids:
                return
            documents = rows.get("documents") or []
            metadatas = rows.get("metadatas") or []
            embeddings = rows.get("embeddings")
            collection.delete(where={"doc_id": BUILTIN_SAFETY_DOC_ID})
            collection.delete(where={"doc_id": source_doc_id})
            new_ids: list[str] = []
            new_metadatas: list[dict[str, Any]] = []
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
            upsert_kwargs: dict[str, Any] = {
                "ids": new_ids,
                "documents": documents,
                "metadatas": new_metadatas,
            }
            if embeddings is not None:
                upsert_kwargs["embeddings"] = embeddings
            collection.upsert(**upsert_kwargs)
        except Exception:
            return

        source_path = Path(str(source.get("stored_path") or ""))
        target_path = self.upload_dir / f"{BUILTIN_SAFETY_DOC_ID}.pdf"
        if source_path.exists() and source_path.resolve() != target_path.resolve():
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(source_path.read_bytes())

        meta.pop(source_doc_id, None)
        meta[BUILTIN_SAFETY_DOC_ID] = {
            "doc_id": BUILTIN_SAFETY_DOC_ID,
            "file_name": BUILTIN_SAFETY_FILE_NAME,
            "file_type": "builtin",
            "chunk_count": len(new_ids),
            "collection": BUILTIN_SAFETY_COLLECTION,
            "stored_path": str(target_path if target_path.exists() else source_path),
            "created_at": str(created_at or source.get("created_at") or datetime.now(timezone.utc).isoformat()),
        }
        self._write_meta(meta)

    def _collection(self) -> Any:
        try:
            import chromadb
            from chromadb.config import Settings
        except ImportError as exc:
            raise RagDependencyError("ChromaDB is not installed. Run pip install -r requirements.txt.") from exc
        client = chromadb.PersistentClient(path=str(self.chroma_dir), settings=Settings(anonymized_telemetry=False))
        return client.get_or_create_collection(self.collection_name)

    def _read_meta(self) -> dict[str, dict[str, Any]]:
        if not self.meta_path.exists():
            return {}
        data: Any = {}
        for attempt in range(3):
            try:
                data = json.loads(self.meta_path.read_text(encoding="utf-8"))
                break
            except json.JSONDecodeError:
                if attempt == 2:
                    return {}
                import time

                time.sleep(0.05)
            except OSError:
                return {}
        return data if isinstance(data, dict) else {}

    def _write_meta(self, meta: dict[str, dict[str, Any]]) -> None:
        self.meta_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.meta_path.with_name(f"{self.meta_path.name}.{uuid.uuid4().hex}.tmp")
        temp_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp_path, self.meta_path)

    def _load_text(self, path: Path, original_name: str) -> str:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return self._load_pdf(path)
        if suffix == ".docx":
            return self._load_docx(path)
        text = path.read_text(encoding="utf-8", errors="ignore")
        if suffix in {".html", ".htm"}:
            text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", text, flags=re.I | re.S)
            text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            raise RagServiceError(f"No text extracted from {original_name}.")
        return text

    def _load_pdf(self, path: Path) -> str:
        extracted_text = ""
        try:
            import fitz

            with fitz.open(str(path)) as doc:
                extracted_text = "\n".join(page.get_text("text") for page in doc)
            extracted_text = extracted_text.strip()
            if extracted_text and not _is_mojibake_text(extracted_text):
                return extracted_text
        except Exception:
            pass

        try:
            from langchain_community.document_loaders import PyPDFLoader

            docs = PyPDFLoader(str(path)).load()
            extracted_text = "\n".join(doc.page_content for doc in docs)
        except Exception:
            try:
                from pypdf import PdfReader
            except ImportError as exc:
                raise RagDependencyError("PDF parsing requires pypdf or langchain-community.") from exc
            reader = PdfReader(str(path))
            extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages)
        extracted_text = extracted_text.strip()
        if extracted_text and not _is_mojibake_text(extracted_text):
            return extracted_text

        ocr_text = self._load_pdf_with_ocr(path)
        if ocr_text:
            return ocr_text
        if extracted_text:
            raise RagServiceError(
                "PDF text extraction returned garbled text, and OCR did not return usable text. "
                "Please install rapidocr-onnxruntime or pytesseract with a Chinese OCR language pack, then retry."
            )
        raise RagServiceError(
            "No text extracted from PDF. The PDF appears to be scanned. "
            "Please install rapidocr-onnxruntime or pytesseract with a Chinese OCR language pack, then retry."
        )

    def _load_pdf_with_ocr(self, path: Path) -> str:
        try:
            import fitz
        except Exception:
            return ""

        page_texts: list[str] = []
        with fitz.open(str(path)) as doc:
            for page_index, page in enumerate(doc):
                image = _render_pdf_page(page)
                if image is None:
                    continue
                text = _ocr_image_text(image)
                text = re.sub(r"\s+", " ", text).strip()
                if text and not _is_mojibake_text(text):
                    page_texts.append(f"第 {page_index + 1} 页 OCR：{text}")
        return "\n".join(page_texts).strip()

    def _load_docx(self, path: Path) -> str:
        try:
            from langchain_community.document_loaders import Docx2txtLoader

            docs = Docx2txtLoader(str(path)).load()
            text = "\n".join(doc.page_content for doc in docs)
        except Exception:
            try:
                from docx import Document
            except ImportError as exc:
                raise RagDependencyError("DOCX parsing requires python-docx.") from exc
            doc = Document(str(path))
            text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
        text = text.strip()
        if not text:
            raise RagServiceError("No text extracted from DOCX.")
        return text

    def _split_text(self, text: str) -> list[str]:
        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter
        except ImportError:
            try:
                from langchain.text_splitter import RecursiveCharacterTextSplitter
            except ImportError:
                return _simple_split_text(text, chunk_size=500, overlap=50)
        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        return [chunk.strip() for chunk in splitter.split_text(text) if chunk.strip()]

    async def _embed_texts(self, texts: list[str]) -> list[list[float]] | None:
        last_error: Exception | None = None
        if settings.llm_configured:
            try:
                return await self._embed_with_llm_gateway(texts)
            except Exception as exc:
                last_error = exc
        try:
            return self._embed_with_sentence_transformers(texts)
        except Exception as exc:
            if last_error:
                print(f"RAG LLM embedding failed, falling back locally: {last_error}")
            print(f"RAG sentence-transformers unavailable, using local hash embeddings: {exc}")
            return _embed_with_local_hash(texts)

    async def _embed_with_llm_gateway(self, texts: list[str]) -> list[list[float]]:
        url = settings.llm_embedding_base_url or _default_embedding_url(settings.llm_base_url)
        model = settings.llm_embedding_model or settings.llm_model
        headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json={"model": model, "input": texts})
            response.raise_for_status()
            data = response.json()
        vectors = [item.get("embedding") for item in data.get("data", [])]
        if len(vectors) != len(texts) or not all(isinstance(item, list) for item in vectors):
            raise RagServiceError("Embedding endpoint returned an unexpected response shape.")
        return vectors

    def _embed_with_sentence_transformers(self, texts: list[str]) -> list[list[float]]:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RagDependencyError("sentence-transformers is not installed.") from exc
        if self._sentence_model is None:
            self._sentence_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        vectors = self._sentence_model.encode(texts, normalize_embeddings=True)
        return [vector.tolist() for vector in vectors]


def _default_embedding_url(base_url: str) -> str:
    stripped = base_url.rstrip("/")
    if stripped.endswith("/chat/completions"):
        return stripped[: -len("/chat/completions")] + "/embeddings"
    if stripped.endswith("/v1"):
        return stripped + "/embeddings"
    return stripped + "/embeddings"


def _render_pdf_page(page: Any) -> Any | None:
    try:
        import fitz
        from PIL import Image

        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        return Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    except Exception:
        return None


def _ocr_image_text(image: Any) -> str:
    text = _ocr_image_with_rapidocr(image)
    if text.strip():
        return text
    return _ocr_image_with_tesseract(image)


def _ocr_image_with_rapidocr(image: Any) -> str:
    try:
        import numpy as np
        from rapidocr_onnxruntime import RapidOCR
    except Exception:
        return ""
    try:
        engine = RapidOCR()
        result, _elapsed = engine(np.array(image))
    except Exception:
        return ""
    lines: list[str] = []
    for item in result or []:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            text = str(item[1] or "").strip()
            if text:
                lines.append(text)
    return "\n".join(lines)


def _ocr_image_with_tesseract(image: Any) -> str:
    try:
        import pytesseract
    except Exception:
        return ""
    languages = ("chi_sim+chi_tra+eng", "chi_sim+eng", "eng")
    for language in languages:
        try:
            text = pytesseract.image_to_string(image, lang=language)
        except Exception:
            continue
        if text.strip():
            return text
    return ""


def _simple_split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    chunks: list[str] = []
    start = 0
    step = max(1, chunk_size - overlap)
    while start < len(normalized):
        chunks.append(normalized[start : start + chunk_size])
        start += step
    return chunks


def _filter_searchable_chunks(chunks: list[str]) -> list[str]:
    return [chunk for chunk in chunks if chunk.strip() and not _is_mojibake_text(chunk)]


def _text_quality(text: str) -> str:
    return "garbled" if _is_mojibake_text(text) else "normal"


def _display_text(text: str, text_quality: str) -> str:
    if text_quality == "garbled":
        return (
            "该片段疑似 PDF 文字解析乱码，已隐藏原始乱码。"
            "建议重新上传可复制文本 PDF/Word，或重新入库后再检索。"
        )
    return _trim_leading_extraction_noise(text)


def _trim_leading_extraction_noise(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    cjk_match = re.search(r"[\u3400-\u9fff]{2,}", normalized)
    if not cjk_match:
        return normalized
    prefix = normalized[: cjk_match.start()]
    if len(prefix) < 20 or cjk_match.start() > 260:
        return normalized

    noise_chars = len(re.findall(r"[#{}\\\\/$€|^~*_@¿¡À-ÿ]", prefix))
    alnum_chars = len(re.findall(r"[A-Za-z0-9]", prefix))
    prefix_len = max(1, len(prefix))
    if noise_chars >= 6 and (noise_chars / prefix_len >= 0.16 or alnum_chars / prefix_len < 0.55):
        return normalized[cjk_match.start() :].strip()
    return normalized


def _is_mojibake_text(text: str) -> bool:
    normalized = re.sub(r"\s+", "", text)
    if len(normalized) < 40:
        return False
    cjk_count = len(re.findall(r"[\u3400-\u9fff]", normalized))
    suspicious_count = len(re.findall(r"[À-ÿÐÞðþ€æÆœŒƒ#¿¡¬¦±§¨´¸]", normalized))
    ascii_letters = len(re.findall(r"[A-Za-z]", normalized))
    punctuation_noise = len(re.findall(r"[#^_`|~\\\\/<>]", normalized))
    length = max(1, len(normalized))
    suspicious_ratio = suspicious_count / length
    noise_ratio = (suspicious_count + punctuation_noise) / length

    if cjk_count >= 8 and suspicious_ratio < 0.08:
        return False
    if suspicious_count >= 6 and suspicious_ratio >= 0.035:
        return True
    return cjk_count < 4 and ascii_letters >= 20 and suspicious_count >= 6 and noise_ratio >= 0.05


def _embed_with_local_hash(texts: list[str], dimensions: int = 384) -> list[list[float]]:
    vectors: list[list[float]] = []
    for text in texts:
        vector = [0.0] * dimensions
        normalized = re.sub(r"\s+", " ", text.lower()).strip()
        tokens = re.findall(r"[\w\u4e00-\u9fff]+", normalized)
        features = tokens or [normalized]
        for token in features:
            digest = hashlib.blake2b(token.encode("utf-8", errors="ignore"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "little") % dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        vectors.append([value / norm for value in vector])
    return vectors


def _build_answer_user_text(question: str, matches: list[dict[str, Any]]) -> str:
    parts = [f"用户问题：{question}", "知识库片段："]
    for idx, item in enumerate(matches, start=1):
        source = str(item.get("source_file_name") or "unknown")
        chunk_index = item.get("chunk_index", 0)
        text = str(item.get("text") or "").strip()
        parts.append(f"[{idx}] {source}#chunk-{chunk_index}\n{text}")
    parts.append("请给出中文回答，并列出引用的 source_file_name 和 chunk_index。")
    return "\n\n".join(parts)


def _extract_json_object(raw: dict[str, Any]) -> dict[str, Any]:
    if "answer" in raw:
        return raw
    choices = raw.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0] if isinstance(choices[0], dict) else {}
        message = first.get("message") if isinstance(first, dict) else {}
        content = message.get("content") if isinstance(message, dict) else ""
        if isinstance(content, str) and content.strip():
            return json.loads(content)
    return raw


def _normalize_citations(value: Any, matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue
            source = str(item.get("source_file_name") or item.get("source") or "").strip()
            if not source:
                continue
            citations.append(
                {
                    "source_file_name": source,
                    "chunk_index": int(item.get("chunk_index") or 0),
                }
            )
    return citations or _default_citations(matches)


def _default_citations(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    for item in matches[:5]:
        citations.append(
            {
                "source_file_name": str(item.get("source_file_name") or "未知来源"),
                "chunk_index": int(item.get("chunk_index") or 0),
            }
        )
    return citations


def _fallback_answer(matches: list[dict[str, Any]]) -> str:
    snippets = []
    for item in matches[:3]:
        source = str(item.get("source_file_name") or "未知来源")
        chunk_index = item.get("chunk_index", 0)
        text = re.sub(r"\s+", " ", str(item.get("text") or "")).strip()
        if text:
            snippets.append(f"- {source}#chunk-{chunk_index}: {text[:260]}")
    if not snippets:
        return "知识库里没有检索到足够相关的内容。"
    return "LLM 暂时不可用，先按知识库检索片段给出依据：\n" + "\n".join(snippets)


rag_service = RagService()
