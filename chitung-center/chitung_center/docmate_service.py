"""DocMate service layer — thin wrappers around AgentToolbox docmate tools."""

from __future__ import annotations

from chitung_center.toolbox_client import toolbox_client


async def read_docx(file_path: str) -> dict:
    """Step 1: Parse a .docx file into structured paragraphs/tables/images."""
    return await toolbox_client.call_tool("docmate_read_docx", {"file_path": file_path})


async def generate_changeset(doc_id: str, instruction: str, context: str | None = None) -> dict:
    """Step 2: Generate a changeset from a natural-language instruction."""
    payload: dict = {"doc_id": doc_id, "instruction": instruction}
    if context:
        payload["context"] = context
    return await toolbox_client.call_tool("docmate_generate_changeset", payload)


async def preview_changeset(changeset_id: str) -> dict:
    """Step 3: Preview the changeset as change cards."""
    return await toolbox_client.call_tool("docmate_preview_changeset", {"changeset_id": changeset_id})


async def apply_changeset(changeset_id: str, accepted_change_ids: list[str], save_as: str | None = None) -> dict:
    """Step 4: Apply accepted changes and write the output .docx."""
    payload: dict = {"changeset_id": changeset_id, "accepted_change_ids": accepted_change_ids}
    if save_as:
        payload["save_as"] = save_as
    return await toolbox_client.call_tool("docmate_apply_changeset", payload)


async def pipeline_edit(file_path: str, instruction: str, save_as: str | None = None, context: str | None = None) -> dict:
    """Full pipeline: read → generate → apply in one call."""
    # Step 1: Read
    read_result = await read_docx(file_path)
    if not read_result.get("ok"):
        return {"ok": False, "error": "read_docx failed", "detail": read_result}

    doc_id = read_result["data"]["doc_id"]

    # Step 2: Generate
    gen_result = await generate_changeset(doc_id, instruction, context)
    if not gen_result.get("ok"):
        return {"ok": False, "error": "generate_changeset failed", "detail": gen_result}

    changeset_id = gen_result["data"]["changeset_id"]
    accepted = [c["change_id"] for c in gen_result["data"]["changes"]]

    # Step 3: Apply
    apply_result = await apply_changeset(changeset_id, accepted, save_as)
    if not apply_result.get("ok"):
        return {"ok": False, "error": "apply_changeset failed", "detail": apply_result}

    return {
        "ok": True,
        "steps": {"read": read_result, "generate": gen_result, "apply": apply_result},
        "output_path": apply_result["data"].get("output_path"),
        "backup_path": apply_result["data"].get("backup_path"),
    }
