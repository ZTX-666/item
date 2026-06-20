from __future__ import annotations

from typing import Any

from chitung_center.document_service import build_document_revision_preview
from chitung_center.models import DocumentRevisionRequest, SmartFormAcceptRequest, SmartFormDraftRequest
from chitung_center.toolbox_client import toolbox_client


async def build_smart_form_draft(request: SmartFormDraftRequest) -> dict[str, Any]:
    templates_result = await toolbox_client.call_tool(
        "search_form_templates",
        {
            "query": request.query,
            "template_ids": [request.template_id] if request.template_id else [],
            "limit": 5,
        },
    )
    templates = _items(templates_result)
    if not templates:
        return {
            "ok": False,
            "message": "No matching form templates were found.",
            "templates": [],
            "requires_acceptance": True,
        }

    selected = _select_template(templates, request.template_id)
    template_id = str(selected.get("id"))

    prefill_result = await toolbox_client.call_tool(
        "prefill_form_fields",
        {
            "template_id": template_id,
            "source_text": request.source_text,
            "case_id": request.case_id,
            "known_fields": request.known_fields,
        },
    )
    fields = _tool_data(prefill_result).get("fields", {})
    if not isinstance(fields, dict):
        fields = {}

    docx_result = await toolbox_client.call_tool(
        "generate_docx_from_template",
        {
            "template_id": template_id,
            "fields": fields,
            "case_id": request.case_id,
            "record": False,
        },
    )

    revision_preview = await build_document_revision_preview(
        DocumentRevisionRequest(
            title=f"{template_id} {selected.get('title') or '安全表格草稿'}",
            source="smart-form-draft",
            instruction=request.instruction,
            original_text=request.source_text,
            revised_text=_fields_to_review_text(template_id, selected, fields),
        )
    )

    return {
        "ok": True,
        "message": "Smart form draft generated. It must be accepted before writing a form record.",
        "requires_acceptance": True,
        "templates": templates,
        "selected_template": selected,
        "prefill": {
            "fields": fields,
            "tool_result": prefill_result,
        },
        "docx_draft": {
            "output_path": _tool_data(docx_result).get("output_path"),
            "payload_path": _tool_data(docx_result).get("payload_path"),
            "files": docx_result.get("files", []),
            "tool_result": docx_result,
        },
        "revision_preview": revision_preview,
        "accept_payload": {
            "template_id": template_id,
            "fields": fields,
            "output_path": _tool_data(docx_result).get("output_path"),
            "case_id": request.case_id,
        },
    }


async def accept_smart_form_draft(request: SmartFormAcceptRequest) -> dict[str, Any]:
    result = await toolbox_client.call_tool(
        "export_form_record",
        {
            "template_id": request.template_id,
            "payload": {
                **request.fields,
                "_acceptance_notes": request.notes or "Accepted from Chitung desktop workbench.",
            },
            "case_id": request.case_id,
            "output_path": request.output_path,
            "status": "accepted",
        },
    )
    return {
        "ok": bool(result.get("ok")),
        "message": "Smart form draft accepted and written to form_records.",
        "record": _tool_data(result),
        "tool_result": result,
    }


def _items(result: dict[str, Any]) -> list[dict[str, Any]]:
    raw_items = _tool_data(result).get("items", [])
    return [item for item in raw_items if isinstance(item, dict)] if isinstance(raw_items, list) else []


def _tool_data(result: dict[str, Any]) -> dict[str, Any]:
    data = result.get("data")
    return data if isinstance(data, dict) else {}


def _select_template(templates: list[dict[str, Any]], template_id: str | None) -> dict[str, Any]:
    if template_id:
        wanted = template_id.upper()
        for template in templates:
            if str(template.get("id", "")).upper() == wanted:
                return template
    return templates[0]


def _fields_to_review_text(template_id: str, template: dict[str, Any], fields: dict[str, Any]) -> str:
    lines = [
        f"模板：{template_id} {template.get('title') or ''}".strip(),
        "以下字段由 AI/规则预填，需人工采纳后写入：",
    ]
    for key, value in list(fields.items())[:20]:
        lines.append(f"{key}：{value}")
    if len(fields) > 20:
        lines.append(f"另有 {len(fields) - 20} 个字段待审核。")
    return "\n".join(lines)
