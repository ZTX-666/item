"""Skill-guided response enhancement.

Bridges the previously inert `SKILL.md` files into live behaviour: when a
workflow finishes, the matching skill document is injected into the LLM as the
governing operating rules, and GLM produces a skill-compliant reply that is
attached to the chat response. Falls back silently (returns ``None``) whenever
the LLM is not configured or anything goes wrong, so the deterministic workflow
output is never blocked.
"""

from __future__ import annotations

import json
from typing import Any

from chitung_center.audit import audit_logger
from chitung_center.config import settings
from chitung_center.llm_gateway import llm_gateway
from chitung_center.skills import skill_loader


_MAX_SKILL_CHARS = 6000
_MAX_RESULT_CHARS = 2500


def _extract_content(llm_result: dict[str, Any]) -> str | None:
    if not isinstance(llm_result, dict):
        return None
    if llm_result.get("available") is False:
        return None
    choices = llm_result.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    return content if isinstance(content, str) else None


def _summarize_run(workflow_run: dict[str, Any]) -> str:
    parts: list[str] = []
    base_reply = workflow_run.get("reply")
    if base_reply:
        parts.append(f"工作流回复：{base_reply}")
    cards = workflow_run.get("cards") or []
    for card in cards[:4]:
        if not isinstance(card, dict):
            continue
        title = card.get("title", "")
        summary = card.get("summary", "")
        parts.append(f"卡片：{title} — {summary}")
    blob = "\n".join(parts)
    return blob[:_MAX_RESULT_CHARS]


async def enhance_with_skill(
    intent: str,
    user_message: str,
    workflow_run: dict[str, Any],
) -> dict[str, Any] | None:
    """Return a skill-guided enhancement dict, or None if not applicable."""
    if not settings.llm_configured:
        return None

    skill = skill_loader.skill_for_intent(intent)
    if not skill:
        return None
    skill_text = skill_loader.read_skill(skill.name)
    if not skill_text:
        return None

    system_prompt = (
        "你是赤瞳安全智能平台的安全运营助理。下面是你本次必须严格遵循的 Skill 操作规范"
        "（SKILL.md），它定义了处理流程、工具序列、风险口径和确认要求。\n"
        "请依据该规范，对当前已经执行的工作流结果生成一段简洁、专业、可执行的中文回复，"
        "并给出要点和建议的下一步动作。不要编造规范之外的事实。\n"
        '只返回 JSON，格式：{"reply": "字符串", "highlights": ["要点"], '
        '"next_actions": ["建议动作"]}。\n\n'
        f"=== SKILL.md ({skill.name}) ===\n{skill_text[:_MAX_SKILL_CHARS]}"
    )
    user_text = (
        f"用户输入：{user_message}\n\n"
        f"当前工作流执行结果：\n{_summarize_run(workflow_run)}"
    )

    try:
        llm_result = await llm_gateway.complete_json(system_prompt, user_text)
    except Exception as exc:  # noqa: BLE001
        audit_logger.write("skill_enhance_failed", {"skill": skill.name, "error": str(exc)})
        return None

    content = _extract_content(llm_result)
    if not content:
        return None
    try:
        parsed = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        parsed = {"reply": content.strip()}

    reply = str(parsed.get("reply") or "").strip()
    if not reply:
        return None

    audit_logger.write(
        "skill_applied",
        {"skill": skill.name, "intent": intent, "model": settings.llm_model},
    )
    return {
        "skill": skill.name,
        "skill_path": skill.path,
        "reply": reply,
        "highlights": parsed.get("highlights") or [],
        "next_actions": parsed.get("next_actions") or [],
    }
