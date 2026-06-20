from __future__ import annotations

import json
import re
import shutil
import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from pydantic import BaseModel, Field

from ..config import settings
from ..models import ToolFile, ToolResult
from ..tasks import new_task_id, task_dir, write_json


class FormTemplateSearchRequest(BaseModel):
    query: str | None = None
    scene: str | None = None
    template_ids: list[str] = Field(default_factory=list)
    limit: int = Field(default=20, ge=1, le=100)


class FormTemplateDetailRequest(BaseModel):
    template_id: str
    include_cells: bool = True
    include_markdown: bool = False


class FormSuggestionRequest(BaseModel):
    scene: str | None = None
    risk_level: str | None = None
    case_id: int | None = None
    description: str | None = None
    limit: int = Field(default=10, ge=1, le=50)


class FormPrefillRequest(BaseModel):
    template_id: str
    source_text: str | None = None
    case_id: int | None = None
    known_fields: dict[str, Any] = Field(default_factory=dict)


class DocxGenerateFromTemplateRequest(BaseModel):
    template_id: str
    fields: dict[str, Any] = Field(default_factory=dict)
    output_path: str | None = None
    case_id: int | None = None
    record: bool = True


class FormRecordExportRequest(BaseModel):
    template_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    case_id: int | None = None
    output_path: str | None = None
    status: str = "draft"


SCENE_TEMPLATE_HINTS: dict[str, list[str]] = {
    "heat": ["酷熱", "热", "暑", "高温", "heat"],
    "lifting": ["吊", "起重", "天秤", "crane", "lifting"],
    "scaffold": ["棚架", "竹棚", "工作平台", "scaffold"],
    "edge": ["臨邊", "临边", "洞口", "高處", "高处", "墮", "坠"],
    "electrical": ["電", "电", "配電", "配电", "electric"],
    "fire": ["消防", "火", "危險品", "危险品", "hot work"],
    "confined": ["密閉", "密闭", "confined"],
    "incident": ["事故", "意外", "工傷", "工伤", "停工", "incident"],
}

TERM_VARIANTS: dict[str, list[str]] = {
    "吊运": ["吊運", "吊", "起重", "天秤"],
    "吊運": ["吊运", "吊", "起重", "天秤"],
    "临边": ["臨邊", "高處", "高处", "洞口"],
    "臨邊": ["临边", "高處", "高处", "洞口"],
    "高处": ["高處", "墮下", "堕下"],
    "高處": ["高处", "墮下", "堕下"],
    "酷热": ["酷熱", "暑熱", "热"],
    "酷熱": ["酷热", "暑熱", "熱"],
    "电": ["電", "配電"],
    "電": ["电", "配电"],
    "工伤": ["工傷", "意外", "事故"],
    "工傷": ["工伤", "意外", "事故"],
}


def search_form_templates(req: FormTemplateSearchRequest) -> ToolResult:
    index = _load_index()
    terms = _search_terms(req.query, req.scene, req.template_ids)
    matches = [_compact_template(item) for item in index if _matches_template(item, terms, req.template_ids)]
    return ToolResult(
        ok=True,
        tool="search_form_templates",
        summary=f"Matched {len(matches[: req.limit])} form templates.",
        data={"items": matches[: req.limit], "total_matches": len(matches), "terms": terms},
    )


def get_form_template_detail(req: FormTemplateDetailRequest) -> ToolResult:
    item = _find_template(req.template_id)
    detail = dict(item)
    if req.include_cells and item.get("json_path"):
        json_path = _resolve_template_path(item, "json_path")
        if json_path:
            detail["json_path"] = str(json_path)
            detail["table_json"] = _read_json(json_path)
    markdown_path = _resolve_template_path(item, "markdown_path")
    if req.include_markdown and markdown_path:
        detail["markdown_path"] = str(markdown_path)
        detail["markdown"] = markdown_path.read_text(encoding="utf-8", errors="ignore")
    return ToolResult(
        ok=True,
        tool="get_form_template_detail",
        summary=f"Loaded template {req.template_id}.",
        files=_template_files(item),
        data=detail,
    )


def suggest_forms_for_case(req: FormSuggestionRequest) -> ToolResult:
    text = " ".join(part for part in [req.scene, req.risk_level, req.description] if part)
    search = search_form_templates(
        FormTemplateSearchRequest(query=text or None, scene=req.scene, limit=req.limit)
    )
    return ToolResult(
        ok=True,
        tool="suggest_forms_for_case",
        summary=f"Suggested {len(search.data.get('items', []))} templates.",
        data={
            "case_id": req.case_id,
            "items": search.data.get("items", []),
            "basis": {"scene": req.scene, "risk_level": req.risk_level, "description": req.description},
        },
    )


def prefill_form_fields(req: FormPrefillRequest) -> ToolResult:
    detail = get_form_template_detail(FormTemplateDetailRequest(template_id=req.template_id, include_cells=True))
    table_json = detail.data.get("table_json") or {}
    labels = _extract_field_labels(table_json)
    fields = dict(req.known_fields)
    source_text = req.source_text or ""
    for label in labels:
        fields.setdefault(label, _guess_value_for_label(label, source_text))
    return ToolResult(
        ok=True,
        tool="prefill_form_fields",
        summary=f"Prepared {len(fields)} candidate fields for {req.template_id}.",
        data={
            "template_id": req.template_id,
            "case_id": req.case_id,
            "fields": fields,
            "needs_review": True,
        },
    )


def generate_docx_from_template(req: DocxGenerateFromTemplateRequest) -> ToolResult:
    item = _find_template(req.template_id)
    src = _resolve_template_path(item, "docx_path")
    task_id = new_task_id("form_docx")
    out_path = Path(req.output_path) if req.output_path else task_dir(task_id) / f"{req.template_id}_{_safe_name(item.get('title'))}.docx"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if src:
        shutil.copy2(src, out_path)
    else:
        _write_basic_docx(out_path, req.template_id, item, req.fields)
    payload_path = out_path.with_suffix(".payload.json")
    write_json(payload_path, {"template_id": req.template_id, "fields": req.fields, "case_id": req.case_id})

    record_id = None
    if req.record:
        record = export_form_record(
            FormRecordExportRequest(
                template_id=req.template_id,
                payload=req.fields,
                case_id=req.case_id,
                output_path=str(out_path),
                status="generated_template_copy",
            )
        )
        record_id = record.data.get("record_id")

    return ToolResult(
        ok=True,
        tool="generate_docx_from_template",
        summary="Generated a DOCX draft by copying the selected template. Field filling is reserved for the next pass.",
        task_id=task_id,
        files=[
            ToolFile(path=str(out_path), name=out_path.name, mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            ToolFile(path=str(payload_path), name=payload_path.name, mime_type="application/json"),
        ],
        data={"template_id": req.template_id, "output_path": str(out_path), "payload_path": str(payload_path), "record_id": record_id},
    )


def export_form_record(req: FormRecordExportRequest) -> ToolResult:
    _ensure_form_records_schema()
    now = _now()
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO form_records (case_id, template_id, status, output_path, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (req.case_id, req.template_id, req.status, req.output_path, json.dumps(req.payload, ensure_ascii=False, sort_keys=True), now),
        )
        record_id = int(cursor.lastrowid)
    return ToolResult(
        ok=True,
        tool="export_form_record",
        summary=f"Recorded form draft {record_id}.",
        data={"record_id": record_id, "template_id": req.template_id, "case_id": req.case_id, "output_path": req.output_path},
    )


def _load_index() -> list[dict[str, Any]]:
    path = settings.safety_policy_templates_dir / "table_index.json"
    if not path.exists():
        raise FileNotFoundError(f"Template index not found: {path}")
    return _read_json(path)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_template(template_id: str) -> dict[str, Any]:
    wanted = template_id.upper()
    for item in _load_index():
        if str(item.get("id", "")).upper() == wanted:
            return item
    raise ValueError(f"Unknown template_id: {template_id}")


def _compact_template(item: dict[str, Any]) -> dict[str, Any]:
    docx_path = _resolve_template_path(item, "docx_path")
    json_path = _resolve_template_path(item, "json_path")
    markdown_path = _resolve_template_path(item, "markdown_path")
    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "policy_context": item.get("policy_context"),
        "rows": item.get("rows"),
        "columns": item.get("columns"),
        "headers_guess": item.get("headers_guess", []),
        "docx_path": str(docx_path) if docx_path else item.get("docx_path"),
        "json_path": str(json_path) if json_path else item.get("json_path"),
        "markdown_path": str(markdown_path) if markdown_path else item.get("markdown_path"),
    }


def _search_terms(query: str | None, scene: str | None, template_ids: list[str]) -> list[str]:
    terms: list[str] = []
    if query:
        terms.extend(re.split(r"[\s,，/、]+", query))
    if scene:
        terms.append(scene)
        for key, hints in SCENE_TEMPLATE_HINTS.items():
            if scene.lower() == key or scene in hints:
                terms.extend(hints)
    terms.extend(template_ids)
    expanded: list[str] = []
    for term in terms:
        if not term:
            continue
        expanded.append(term)
        expanded.extend(TERM_VARIANTS.get(term, []))
    return list(dict.fromkeys(expanded))


def _matches_template(item: dict[str, Any], terms: list[str], template_ids: list[str]) -> bool:
    if template_ids and item.get("id") in {template_id.upper() for template_id in template_ids}:
        return True
    if not terms:
        return True
    haystack = json.dumps(
        {
            "id": item.get("id"),
            "title": item.get("title"),
            "policy_context": item.get("policy_context"),
            "nearby_paragraphs": item.get("nearby_paragraphs"),
            "headers_guess": item.get("headers_guess"),
        },
        ensure_ascii=False,
    ).lower()
    return any(term.lower() in haystack for term in terms)


def _extract_field_labels(table_json: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    for row in table_json.get("cells", []):
        for cell in row:
            text = str(cell).strip()
            if not text:
                continue
            if text.endswith(("：", ":")) or len(text) <= 12:
                labels.append(text.rstrip("：:"))
    seen: set[str] = set()
    unique = []
    for label in labels:
        if label not in seen:
            seen.add(label)
            unique.append(label)
    return unique[:80]


def _guess_value_for_label(label: str, source_text: str) -> str:
    if any(token in label for token in ["日期", "填表日期"]):
        return datetime.now().strftime("%Y-%m-%d")
    if any(token in label for token in ["地盤", "地盘", "工程"]):
        return _extract_after(source_text, ["地盤", "地盘", "工程"]) or ""
    if any(token in label for token in ["分判", "承建"]):
        return _extract_after(source_text, ["分判商", "承建商"]) or ""
    if any(token in label for token in ["位置", "地點", "地点", "區", "区"]):
        return _extract_after(source_text, ["位置", "地點", "地点", "區", "区"]) or ""
    return ""


def _extract_after(text: str, keys: list[str]) -> str | None:
    for key in keys:
        match = re.search(rf"{re.escape(key)}[：:\s]*(\S{{1,30}})", text)
        if match:
            return match.group(1)
    return None


def _template_files(item: dict[str, Any]) -> list[ToolFile]:
    files: list[ToolFile] = []
    for key, mime in [
        ("docx_path", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("json_path", "application/json"),
        ("markdown_path", "text/markdown"),
    ]:
        resolved = _resolve_template_path(item, key)
        path = str(resolved) if resolved else item.get(key)
        if path:
            files.append(ToolFile(path=path, name=Path(path).name, mime_type=mime))
    return files


def _resolve_template_path(item: dict[str, Any], key: str) -> Path | None:
    raw_path = item.get(key)
    if raw_path:
        path = Path(str(raw_path))
        if path.exists():
            return path

    template_id = str(item.get("id") or "").upper()
    subdirs = {
        "docx_path": "tables-docx",
        "json_path": "tables-json",
        "markdown_path": "tables-md",
    }
    suffixes = {
        "docx_path": ".docx",
        "json_path": ".json",
        "markdown_path": ".md",
    }
    subdir = subdirs.get(key)
    suffix = suffixes.get(key)
    if not template_id or not subdir or not suffix:
        return None

    base = settings.safety_policy_templates_dir / subdir
    if not base.exists():
        return None
    matches = sorted(base.glob(f"{template_id}_*{suffix}"))
    return matches[0] if matches else None


def _write_basic_docx(out_path: Path, template_id: str, item: dict[str, Any], fields: dict[str, Any]) -> None:
    title = f"{template_id} {item.get('title') or '安全表格草稿'}".strip()
    lines = [title, "此 DOCX 由赤瞳根据模板索引和预填字段生成，源模板文件缺失时使用基础版式。"]
    lines.extend(f"{key}: {value}" for key, value in fields.items())
    body = "".join(f"<w:p><w:r><w:t>{escape(str(line))}</w:t></w:r></w:p>" for line in lines)
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}<w:sectPr><w:pgSz w:w=\"11906\" w:h=\"16838\"/><w:pgMar w:top=\"1440\" w:right=\"1440\" w:bottom=\"1440\" w:left=\"1440\"/></w:sectPr></w:body>"
        "</w:document>"
    )
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            "</Relationships>",
        )
        archive.writestr("word/document.xml", document_xml)


def _ensure_form_records_schema() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS form_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER,
                template_id TEXT,
                status TEXT NOT NULL DEFAULT 'suggested',
                output_path TEXT,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_form_records_template ON form_records(template_id);
            CREATE INDEX IF NOT EXISTS idx_form_records_case ON form_records(case_id);
            """
        )


def _connect() -> sqlite3.Connection:
    path = settings.safety_database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_name(value: str | None) -> str:
    text = re.sub(r"[\\/:*?\"<>|]+", "_", value or "template")
    return text[:40] or "template"
