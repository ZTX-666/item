"""Yaoyao Structured Input Service — orchestrates OCR structured extraction
through the toolbox layer, with audit logging and human confirmation.

Sits between chitung-center API routes and agent-toolbox tool endpoints.
"""

from __future__ import annotations

from typing import Any

from chitung_center.audit import audit_logger
from chitung_center.models import (
    YaoyaoConfirmRequest,
    YaoyaoStructuredDraftRequest,
    YaoyaoTemplateLoadRequest,
    YaoyaoTemplateSaveRequest,
)
from chitung_center.toolbox_client import toolbox_client


async def build_yaoyao_structured_draft(
    request: YaoyaoStructuredDraftRequest,
) -> dict[str, Any]:
    """Call toolbox to perform structured OCR extraction.

    Returns a draft with field candidates and a confirm_payload
    that must be accepted by a human before writing to the database.
    """
    audit_logger.write("yaoyao_draft_requested", {
        "file_path": request.file_path,
        "template_id": request.template_id,
        "case_id": request.case_id,
        "region_count": len(request.regions),
    })

    # Convert Pydantic regions to plain dicts for the toolbox call.
    regions_payload = [
        r.model_dump() if hasattr(r, "model_dump") else dict(r)
        for r in request.regions
    ]

    result = await toolbox_client.call_tool(
        "yaoyao_structured_extract",
        {
            "file_path": request.file_path,
            "regions": regions_payload,
            "page_index": request.page_index,
            "template_id": request.template_id,
            "case_id": request.case_id,
            "render_width": request.render_width,
            "render_height": request.render_height,
        },
        context={"source": "yaoyao_structured_service"},
    )

    ok = bool(result.get("ok"))
    if not ok:
        error = result.get("error", "Unknown toolbox error.")
        audit_logger.write("yaoyao_draft_failed", {
            "file_path": request.file_path,
            "error": error,
        })
        return {
            "ok": False,
            "message": f"Structured extraction failed: {error}",
            "requires_acceptance": False,
        }

    # Extract field candidates from toolbox result.
    raw_candidates = result.get("field_candidates", [])
    field_candidates = [
        {
            "field_name": fc.get("field_name", ""),
            "value": fc.get("value", ""),
            "confidence": fc.get("confidence", 0.0),
            "source_region": fc.get("source_region", ""),
            "page_number": fc.get("page_number", 1),
        }
        for fc in raw_candidates
        if isinstance(fc, dict)
    ]

    draft_id = result.get("draft_id", "")
    confirm_payload = result.get("confirm_payload", {})
    # Ensure the confirm payload has all needed fields.
    confirm_payload.update({
        "draft_id": draft_id,
        "template_id": request.template_id,
        "case_id": request.case_id,
    })

    audit_logger.write("yaoyao_draft_ready", {
        "draft_id": draft_id,
        "field_count": len(field_candidates),
        "page_count": result.get("page_count", 0),
    })

    return {
        "ok": True,
        "message": "Structured extraction draft ready. Fields must be confirmed before writing.",
        "draft_id": draft_id,
        "preview_image_path": result.get("preview_image_path"),
        "pages": result.get("pages", []),
        "field_candidates": field_candidates,
        "page_count": result.get("page_count", 0),
        "elapsed_seconds": result.get("elapsed_seconds", 0),
        "requires_acceptance": True,
        "confirm_payload": confirm_payload,
    }


async def confirm_yaoyao_structured_draft(
    request: YaoyaoConfirmRequest,
) -> dict[str, Any]:
    """Confirm a structured extraction draft and write to form_records.

    All field values have been human-reviewed before this call.
    Writes via toolbox export_form_record and logs audit.
    """
    audit_logger.write("yaoyao_confirm_requested", {
        "draft_id": request.draft_id,
        "template_id": request.template_id,
        "case_id": request.case_id,
        "field_count": len(request.fields),
    })

    # Write confirmed fields to form_records via toolbox.
    template_id = request.template_id or "yaoyao_structured"
    result = await toolbox_client.call_tool(
        "export_form_record",
        {
            "template_id": template_id,
            "payload": {
                **request.fields,
                "_acceptance_notes": request.notes or "Accepted from Yaoyao structured input.",
                "_draft_id": request.draft_id,
                "_source": "yaoyao_structured_input",
            },
            "case_id": request.case_id,
            "output_path": None,
            "status": "accepted",
        },
        context={"source": "yaoyao_structured_service", "draft_id": request.draft_id},
    )

    ok = bool(result.get("ok"))
    audit_id = audit_logger.write("yaoyao_confirmed", {
        "draft_id": request.draft_id,
        "template_id": template_id,
        "case_id": request.case_id,
        "ok": ok,
        "field_count": len(request.fields),
    })

    if not ok:
        return {
            "ok": False,
            "message": "Failed to write confirmed fields to form_records.",
            "audit_id": audit_id,
        }

    # Extract record info from toolbox result.
    data = result.get("data", {}) if isinstance(result.get("data"), dict) else {}
    record_id = data.get("id") or data.get("record_id", "")
    output_path = data.get("output_path", "")

    return {
        "ok": True,
        "message": "Structured input confirmed and written to form_records.",
        "record_id": record_id,
        "output_path": output_path,
        "audit_id": audit_id,
    }


async def save_yaoyao_template(
    request: YaoyaoTemplateSaveRequest,
) -> dict[str, Any]:
    """Save an OCR recognition template via toolbox."""
    audit_logger.write("yaoyao_template_save", {
        "template_id": request.template_id,
        "name": request.name,
        "region_count": len(request.regions),
    })

    regions_payload = [
        r.model_dump() if hasattr(r, "model_dump") else dict(r)
        for r in request.regions
    ]

    result = await toolbox_client.call_tool(
        "yaoyao_save_template",
        {
            "regions": regions_payload,
            "rows": request.rows,
            "name": request.name,
            "template_id": request.template_id,
        },
    )
    return result


async def list_yaoyao_templates() -> dict[str, Any]:
    """List saved OCR templates via toolbox."""
    return await toolbox_client.call_tool("yaoyao_list_templates", {})


async def load_yaoyao_template(
    template_id: str,
) -> dict[str, Any]:
    """Load an OCR recognition template via toolbox."""
    result = await toolbox_client.call_tool(
        "yaoyao_load_template",
        {"template_id": template_id},
    )
    return result
