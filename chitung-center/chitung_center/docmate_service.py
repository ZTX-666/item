"""DocMate service layer — thin wrappers around AgentToolbox docmate tools.

`generate_changeset` is LLM-first: when the unified Chitung Center LLM gateway
is configured, it asks the model for structured edits and registers them as a
real changeset; otherwise it falls back to the toolbox pattern matcher. Either
way the changeset is stored in the toolbox so preview/apply stay identical.
"""

from __future__ import annotations

import json
import re
from typing import Any

from chitung_center.config import settings
from chitung_center.llm_gateway import llm_gateway
from chitung_center.toolbox_client import toolbox_client


_EDIT_SYSTEM_PROMPT = (
    "你是专业公文与文档改稿助手。用户会给出一份按段落编号的文档和一条自然语言修改指令。"
    "请只输出 JSON 对象，格式为 {\"edits\": [{\"type\": \"replace|delete|append\", "
    "\"target\": \"...\", \"replacement\": \"...\"}]}。规则："
    "1) replace 表示把 target 替换为 replacement；delete 表示删除 target；append 表示在文末新增 replacement。"
    "2) target 必须是文档中【逐字复制】的真实片段（含标点），不要改写、不要加引号，否则无法定位。"
    "3) 只针对指令要求的改动产出 edits，保持最小必要修改。"
    "4) 若指令无法在文档中落地，返回 {\"edits\": []}。只输出 JSON，不要解释。"
)


_RETRY_SYSTEM_PROMPT = (
    "你是专业公文与文档改稿助手。用户对下列若干处修改不满意，请针对【每一处】给出"
    "不同的替代改写方案，保持修改意图一致但表达不同。只输出 JSON 对象，格式为 "
    "{\"edits\": [{\"type\": \"replace|delete|append\", \"target\": \"...\", \"replacement\": \"...\"}]}。"
    "规则：1) target 必须是文档中【逐字复制】的真实片段（含标点），不要改写、不要加引号；"
    "2) 只针对需要重做的条目产出 edits，数量尽量与待重做条目一致；"
    "3) 若无法给出替代方案，返回 {\"edits\": []}。只输出 JSON，不要解释。"
)


async def read_docx(file_path: str) -> dict:
    """Step 1: Parse a .docx file into structured paragraphs/tables/images."""
    return await toolbox_client.call_tool("docmate_read_docx", {"file_path": file_path})


def _extract_edits(llm_response: Any) -> list[dict[str, Any]]:
    """Extract a list of edit dicts from a raw LLM JSON response."""
    if not isinstance(llm_response, dict):
        return []
    if llm_response.get("available") is False:
        return []

    content: str | None = None
    choices = llm_response.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(message, dict):
            content = message.get("content")
    if content is None and "edits" in llm_response:
        # Some gateways may return the parsed object directly.
        edits = llm_response.get("edits")
        return [e for e in edits if isinstance(e, dict)] if isinstance(edits, list) else []
    if not content:
        return []

    text = content.strip()
    # Strip ```json fences if present.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return []
        try:
            data = json.loads(match.group(0))
        except (TypeError, ValueError):
            return []

    edits = data.get("edits") if isinstance(data, dict) else None
    if not isinstance(edits, list):
        edits = data.get("changes") if isinstance(data, dict) else None
    if not isinstance(edits, list):
        return []
    return [e for e in edits if isinstance(e, dict)]


async def _llm_generate_changeset(doc_id: str, instruction: str) -> dict | None:
    """Try LLM-backed generation through the unified gateway. Returns None on failure."""
    doc = await toolbox_client.call_tool("docmate_get_document", {"doc_id": doc_id})
    if not doc.get("ok"):
        return None
    paragraphs = doc.get("data", {}).get("paragraphs", [])
    if not paragraphs:
        return None

    doc_text = "\n".join(f'[{p.get("index")}] {p.get("text", "")}' for p in paragraphs)
    user_text = f"文档内容（按段落编号）：\n{doc_text}\n\n修改指令：{instruction}"

    llm_response = await llm_gateway.complete_document_json(_EDIT_SYSTEM_PROMPT, user_text)
    edits = _extract_edits(llm_response)
    if not edits:
        return None

    registered = await toolbox_client.call_tool(
        "docmate_register_changeset",
        {"doc_id": doc_id, "instruction": instruction, "changes": edits},
    )
    if registered.get("ok") and registered.get("data", {}).get("preview_cards"):
        return registered
    return None


async def generate_changeset(doc_id: str, instruction: str, context: str | None = None) -> dict:
    """Step 2: Generate a changeset from a natural-language instruction.

    LLM-first (unified gateway), with graceful fallback to the toolbox pattern
    matcher when the LLM is unconfigured, errors, or yields no usable edits.
    """
    if settings.llm_configured:
        try:
            llm_result = await _llm_generate_changeset(doc_id, instruction)
            if llm_result:
                return llm_result
        except Exception:  # noqa: BLE001 — never let LLM failure block editing; fall back.
            pass

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


async def retry_edits(doc_id: str, instruction: str, items: list[dict]) -> dict:
    """Regenerate ALTERNATIVE edits for the specific items the user selected.

    Sends the document, the original instruction, and the specific edits to
    reconsider to the unified LLM gateway, then registers the alternatives as a
    fresh changeset. Only the selected diffs are replaced by the caller.
    """
    if not settings.llm_configured:
        return {"ok": False, "error": "未配置大模型，无法重试。", "available": False}
    doc = await toolbox_client.call_tool("docmate_get_document", {"doc_id": doc_id})
    if not doc.get("ok"):
        return {"ok": False, "error": "文档不存在或已过期。"}
    paragraphs = doc.get("data", {}).get("paragraphs", [])
    if not paragraphs:
        return {"ok": False, "error": "文档为空。"}

    doc_text = "\n".join(f'[{p.get("index")}] {p.get("text", "")}' for p in paragraphs)
    redo_lines = "\n".join(
        f'- {it.get("type", "replace")}: target="{it.get("target", "")}" replacement="{it.get("replacement", "")}"'
        for it in items
    )
    user_text = (
        f"文档内容（按段落编号）：\n{doc_text}\n\n"
        f"原始修改指令：{instruction}\n\n"
        f"需要重做的修改（请逐条给出不同的替代方案）：\n{redo_lines}"
    )
    llm_response = await llm_gateway.complete_document_json(_RETRY_SYSTEM_PROMPT, user_text)
    edits = _extract_edits(llm_response)
    if not edits:
        return {"ok": False, "error": "未能生成替代方案，请稍后再试。"}
    return await toolbox_client.call_tool(
        "docmate_register_changeset",
        {"doc_id": doc_id, "instruction": instruction, "changes": edits},
    )


async def commit_edits(doc_id: str, edits: list[dict], save_as: str | None = None) -> dict:
    """Commit a batch of accepted explicit edits to the document in one pass.

    Registers the accumulated edits as a changeset, then applies all of them.
    Used by the work-list flow where the user accepts/rejects diffs and only the
    final accepted set is written once at the end (then offered for download).
    """
    if not edits:
        return {"ok": False, "error": "没有可写入的修改。"}
    registered = await toolbox_client.call_tool(
        "docmate_register_changeset",
        {"doc_id": doc_id, "instruction": "合并采纳的修改", "changes": edits},
    )
    if not registered.get("ok"):
        return registered
    changeset_id = registered["data"]["changeset_id"]
    change_ids = [c["change_id"] for c in registered["data"]["changes"]]
    payload: dict = {"changeset_id": changeset_id, "accepted_change_ids": change_ids}
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
