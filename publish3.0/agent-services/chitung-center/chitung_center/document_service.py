from __future__ import annotations

import json
from difflib import SequenceMatcher
from typing import Any

from chitung_center.llm_gateway import llm_gateway
from chitung_center.models import DocumentRevisionRequest


async def build_document_revision_preview(request: DocumentRevisionRequest) -> dict[str, Any]:
    original_lines = _lines(request.original_text)
    revised_text, llm_meta = await _resolve_revised_text(request)
    revised_lines = _lines(revised_text)

    diff_lines: list[dict[str, str]] = []
    additions = 0
    deletions = 0

    matcher = SequenceMatcher(a=original_lines, b=revised_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for line in original_lines[i1:i2]:
                diff_lines.append(_line("context", line))
        elif tag == "delete":
            for line in original_lines[i1:i2]:
                deletions += 1
                diff_lines.append(_line("removed", line))
        elif tag == "insert":
            for line in revised_lines[j1:j2]:
                additions += 1
                diff_lines.append(_line("added", line))
        elif tag == "replace":
            for line in original_lines[i1:i2]:
                deletions += 1
                diff_lines.append(_line("removed", line))
            for line in revised_lines[j1:j2]:
                additions += 1
                diff_lines.append(_line("added", line))

    return {
        "id": "doc-revision-preview",
        "title": request.title,
        "source": request.source,
        "instruction": request.instruction,
        "additions": additions,
        "deletions": deletions,
        "status": "draft",
        "llm": llm_meta,
        "lines": [
            {**line, "id": f"line-{index + 1}"}
            for index, line in enumerate(diff_lines)
        ],
    }


async def _resolve_revised_text(request: DocumentRevisionRequest) -> tuple[str, dict[str, Any]]:
    if request.revised_text is not None:
        return request.revised_text, {"used": False, "reason": "revised_text was provided by caller"}

    try:
        llm_result = await llm_gateway.complete_json(
            system_prompt=(
                "你是香港/内地工程安全文档助手。你只返回 JSON，不要返回 Markdown。"
                "目标是把现场口语化内容改写成正式、可审计、适合安全主任人工确认的文档文本。"
                "不得编造具体日期、人员姓名、公司名称或证据编号。"
                "JSON 格式必须为：{\"revised_text\":\"...\",\"reason\":\"...\"}。"
            ),
            user_text=json.dumps(
                {
                    "title": request.title,
                    "source": request.source,
                    "instruction": request.instruction,
                    "original_text": request.original_text,
                    "requirements": [
                        "保留事实，不要添加未提供的责任人或日期",
                        "语气正式，适合整改通知/表格草稿",
                        "明确整改、提交证明、人工复核",
                        "输出 revised_text 使用换行分段",
                    ],
                },
                ensure_ascii=False,
            ),
        )
        parsed = _extract_llm_json(llm_result)
        revised_text = str(parsed.get("revised_text") or "").strip()
        if revised_text:
            return revised_text, {
                "used": True,
                "available": True,
                "reason": parsed.get("reason") or "LLM generated revised_text",
            }
        return _draft_revised_text(request.original_text, request.instruction), {
            "used": False,
            "available": bool(llm_result.get("available", True)),
            "reason": "LLM response did not include revised_text; fallback draft was used",
        }
    except Exception as exc:  # noqa: BLE001 - document preview must remain available.
        return _draft_revised_text(request.original_text, request.instruction), {
            "used": False,
            "available": False,
            "reason": f"LLM revision failed; fallback draft was used: {exc}",
        }


def _extract_llm_json(raw: dict[str, Any]) -> dict[str, Any]:
    if raw.get("available") is False:
        return raw
    if "revised_text" in raw:
        return raw

    choices = raw.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, str) and content.strip():
            return json.loads(content)

    return raw


def _lines(text: str) -> list[str]:
    lines = [line.rstrip() for line in text.strip().splitlines()]
    return lines or [""]


def _line(line_type: str, text: str) -> dict[str, str]:
    return {"type": line_type, "text": text}


def _draft_revised_text(original_text: str, instruction: str) -> str:
    normalized = original_text.strip()
    if not normalized:
        normalized = "请在此处填写现场安全事项。"

    return "\n".join(
        [
            "关于现场安全隐患的整改通知",
            "经现场巡查发现，相关区域存在安全管理风险，请责任单位立即安排整改。",
            f"AI 改写要求：{instruction.strip()}",
            "整改完成后须提交整改前后照片、责任人确认记录及安全主任复核意见。",
            "本修改仅为 AI 草稿，须经人工采纳后方可写入正式文档。",
        ]
    )
