from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ..config import settings
from ..models import ToolResult


class OcrDocumentRequest(BaseModel):
    path: str
    engine: str = "reserved"


class TableExtractionRequest(BaseModel):
    path: str
    engine: str = "reserved"


class DocumentTypeClassifyRequest(BaseModel):
    text: str | None = None
    path: str | None = None


class CertificateFieldExtractRequest(BaseModel):
    text: str | None = None
    path: str | None = None


class CertificateExpiryCheckRequest(BaseModel):
    certificates: list[dict[str, Any]] = Field(default_factory=list)
    warning_days: int = 30


class PolicyDocumentSummarizeRequest(BaseModel):
    query: str | None = None
    max_chars: int = 2000


class PolicyClauseSearchRequest(BaseModel):
    query: str
    limit: int = Field(default=10, ge=1, le=50)
    context_chars: int = Field(default=120, ge=40, le=1000)


def ocr_document_or_image(req: OcrDocumentRequest) -> ToolResult:
    """OCR a document or image file using the Yaoyao OCR engine."""
    path = Path(req.path)
    if not path.exists():
        return ToolResult(
            ok=True,
            tool="ocr_document_or_image",
            summary=f"File not found: {req.path}",
            data={"path": req.path, "exists": False, "engine": req.engine, "text": ""},
        )

    try:
        from .yaoyao_ocr_engine import get_engine

        engine = get_engine()
        text = engine.recognize_file(str(path), fast_mode=True)
        return ToolResult(
            ok=True,
            tool="ocr_document_or_image",
            summary=f"OCR completed: {len(text)} chars extracted.",
            data={"path": req.path, "exists": True, "engine": "rapidocr", "text": text},
        )
    except Exception as exc:
        return ToolResult(
            ok=False,
            tool="ocr_document_or_image",
            summary=f"OCR failed: {exc}",
            data={"path": req.path, "exists": True, "engine": "rapidocr", "text": ""},
            error=str(exc),
        )


def extract_tables_from_document(req: TableExtractionRequest) -> ToolResult:
    """Extract structured content from a document using Yaoyao OCR + PDF render."""
    path = Path(req.path)
    if not path.exists():
        return ToolResult(
            ok=True,
            tool="extract_tables_from_document",
            summary=f"File not found: {req.path}",
            data={"path": req.path, "exists": False, "engine": req.engine, "tables": []},
        )

    try:
        from .yaoyao_structured_input import get_workflow_service

        workflow = get_workflow_service()
        result = workflow.structured_extract(path, regions=None, max_pages=5)

        tables = []
        for page in result.pages:
            row = {"page": page.page_number}
            row.update(page.values)
            tables.append(row)

        return ToolResult(
            ok=True,
            tool="extract_tables_from_document",
            summary=f"Extracted {len(tables)} pages, {len(result.field_candidates)} fields.",
            data={
                "path": req.path,
                "exists": True,
                "engine": "rapidocr",
                "tables": tables,
                "page_count": result.page_count,
                "elapsed_seconds": result.elapsed_seconds,
            },
        )
    except Exception as exc:
        return ToolResult(
            ok=False,
            tool="extract_tables_from_document",
            summary=f"Table extraction failed: {exc}",
            data={"path": req.path, "exists": True, "engine": "rapidocr", "tables": []},
            error=str(exc),
        )


def classify_document_type(req: DocumentTypeClassifyRequest) -> ToolResult:
    text = _input_text(req.text, req.path)
    doc_type = "unknown"
    if any(term in text for term in ["證書", "证书", "certificate", "有效期", "expiry"]):
        doc_type = "certificate"
    elif any(term in text for term in ["檢查表", "检查表", "巡查", "checklist"]):
        doc_type = "inspection_form"
    elif any(term in text for term in ["整改", "警告信", "通知"]):
        doc_type = "notice_or_letter"
    elif any(term in text for term in ["安全管理", "制度", "辦法", "办法"]):
        doc_type = "policy"
    return ToolResult(ok=True, tool="classify_document_type", summary=f"Classified document as {doc_type}.", data={"document_type": doc_type})


def extract_certificate_fields(req: CertificateFieldExtractRequest) -> ToolResult:
    text = _input_text(req.text, req.path)
    dates = _extract_dates(text)
    fields = {
        "certificate_no": _match_first(text, [r"(?:證書|证书|certificate)\s*(?:編號|编号|no\.?)[:：\s]*([A-Za-z0-9\-/]+)"]),
        "holder": _match_first(text, [r"(?:持有人|姓名|holder|name)[:：\s]*([^\n\r]{2,40})"]),
        "issue_date": dates[0] if dates else None,
        "expiry_date": dates[-1] if dates else None,
        "dates": dates,
    }
    return ToolResult(ok=True, tool="extract_certificate_fields", summary="Extracted candidate certificate fields.", data={"fields": fields, "needs_review": True})


def check_certificate_expiry(req: CertificateExpiryCheckRequest) -> ToolResult:
    today = date.today()
    items = []
    for cert in req.certificates:
        expiry = cert.get("expiry_date")
        status = "unknown"
        days_remaining = None
        if expiry:
            try:
                expiry_date = datetime.fromisoformat(str(expiry)).date()
                days_remaining = (expiry_date - today).days
                status = "expired" if days_remaining < 0 else "warning" if days_remaining <= req.warning_days else "valid"
            except ValueError:
                status = "invalid_date"
        items.append({**cert, "status": status, "days_remaining": days_remaining})
    return ToolResult(ok=True, tool="check_certificate_expiry", summary=f"Checked {len(items)} certificates.", data={"items": items})


def summarize_policy_document(req: PolicyDocumentSummarizeRequest) -> ToolResult:
    text = _policy_text()
    if req.query:
        snippets = _search_snippets(text, req.query, limit=5, context_chars=200)
        source = "\n\n".join(item["snippet"] for item in snippets)
    else:
        source = text[: req.max_chars]
    summary = source[: req.max_chars]
    return ToolResult(ok=True, tool="summarize_policy_document", summary="Prepared policy summary source text.", data={"summary": summary, "query": req.query})


def search_policy_clauses(req: PolicyClauseSearchRequest) -> ToolResult:
    text = _policy_text()
    snippets = _search_snippets(text, req.query, req.limit, req.context_chars)
    return ToolResult(ok=True, tool="search_policy_clauses", summary=f"Found {len(snippets)} policy snippets.", data={"items": snippets})


def _input_text(text: str | None, path: str | None) -> str:
    if text:
        return text
    if path and Path(path).exists() and Path(path).suffix.lower() in {".txt", ".md", ".json"}:
        return Path(path).read_text(encoding="utf-8", errors="ignore")
    return ""


def _policy_text() -> str:
    path = settings.safety_policy_templates_dir / "text" / "full_text.txt"
    if not path.exists():
        raise FileNotFoundError(f"Policy full text not found: {path}")
    return path.read_text(encoding="utf-8", errors="ignore")


def _search_snippets(text: str, query: str, limit: int, context_chars: int) -> list[dict[str, Any]]:
    terms = [term for term in re.split(r"[\s,，/、]+", query) if term]
    items = []
    lowered = text.lower()
    for term in terms:
        start = 0
        while len(items) < limit:
            idx = lowered.find(term.lower(), start)
            if idx < 0:
                break
            left = max(0, idx - context_chars)
            right = min(len(text), idx + len(term) + context_chars)
            items.append({"term": term, "offset": idx, "snippet": text[left:right]})
            start = idx + len(term)
    return items


def _extract_dates(text: str) -> list[str]:
    dates: list[str] = []
    for match in re.finditer(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})", text):
        year, month, day = match.groups()
        dates.append(f"{int(year):04d}-{int(month):02d}-{int(day):02d}")
    return dates


def _match_first(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return match.group(1).strip()
    return None
