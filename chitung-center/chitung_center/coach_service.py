from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from chitung_center.audit import audit_logger
from chitung_center.chat_store import chat_store
from chitung_center.config import settings
from chitung_center.coach_usage_service import build_usage_snapshot
from chitung_center.llm_gateway import llm_gateway
from chitung_center.skills import skill_loader

_MAX_SKILL_CHARS = 9000
_MAX_HISTORY = 10
_MAX_REPLY_CHARS = 6000


@dataclass(frozen=True)
class CoachProfile:
    skill_name: str
    intent: str
    display_name: str
    domain: str
    role_title: str
    default_follow_ups: tuple[str, ...]
    open_actions: tuple[tuple[str, str], ...]


COACH_PROFILES: dict[str, CoachProfile] = {
    "skill-usage-coach": CoachProfile(
        skill_name="skill-usage-coach",
        intent="skill_usage_coach",
        display_name="Skill 使用教练",
        domain="skill",
        role_title="Skill 使用教练",
        default_follow_ups=(
            "你想先了解「怎么触发 Skill」还是「怎么在 Skill 页管理」？",
            "你目前最常用的是制度问答、外部讯息还是文档编辑？",
        ),
        open_actions=(
            ("open_skills", "打开 Skill 管理"),
            ("open_assistant", "打开 AI 助手"),
        ),
    ),
    "workflow-usage-coach": CoachProfile(
        skill_name="workflow-usage-coach",
        intent="workflow_usage_coach",
        display_name="工作流使用教练",
        domain="workflow",
        role_title="工作流使用教练",
        default_follow_ups=(
            "你要做「一次性 Chat 触发」还是「多步闭环」？",
            "最终产出需要经过待确认页面吗？",
        ),
        open_actions=(
            ("open_execution_center", "打开执行中心"),
            ("open_confirmations", "打开待确认"),
        ),
    ),
    "automation-usage-coach": CoachProfile(
        skill_name="automation-usage-coach",
        intent="automation_usage_coach",
        display_name="自动化使用教练",
        domain="automation",
        role_title="自动化使用教练",
        default_follow_ups=(
            "你希望「每天定时跑」还是「有事件才跑」？",
            "自动化结果要自动发送，还是只生成草稿？",
        ),
        open_actions=(
            ("open_automation", "打开自动化"),
            ("open_execution_center", "打开执行中心"),
        ),
    ),
}


async def coach_by_skill_name(
    skill_name: str,
    *,
    user_message: str,
    session_id: str | None = None,
    user_id: str = "local_user",
) -> dict[str, Any]:
    profile = COACH_PROFILES.get(skill_name)
    if not profile:
        raise ValueError(f"unknown coach skill: {skill_name}")
    usage = build_usage_snapshot(profile.domain)
    skill_text = _load_skill_bundle(profile.skill_name)
    history = _recent_coach_history(session_id, profile)

    if not settings.llm_configured:
        return {
            "ok": True,
            "reply": _fallback_reply(profile, user_message, usage),
            "mode": "rule_fallback",
            "follow_up_questions": list(profile.default_follow_ups),
            "usage": usage,
        }

    system_prompt = _build_system_prompt(profile, skill_text, usage)
    messages = _build_messages(history, user_message)
    try:
        llm_result = await llm_gateway.complete_chat(system_prompt, messages, max_tokens=4096)
        reply = _extract_reply(llm_result).strip()
        if not reply:
            raise ValueError("empty coach reply")
        reply = reply[:_MAX_REPLY_CHARS]
    except Exception as exc:  # noqa: BLE001
        audit_logger.write("usage_coach_failed", {"skill": skill_name, "error": str(exc)})
        return {
            "ok": True,
            "reply": _fallback_reply(profile, user_message, usage),
            "mode": "rule_fallback",
            "follow_up_questions": list(profile.default_follow_ups),
            "usage": usage,
            "llm_error": str(exc),
        }

    audit_logger.write(
        "usage_coach_replied",
        {"skill": skill_name, "user_id": user_id, "session_id": session_id or "", "chars": len(reply)},
    )
    return {
        "ok": True,
        "reply": reply,
        "mode": "llm_coach",
        "follow_up_questions": _extract_follow_ups(reply) or list(profile.default_follow_ups),
        "usage": usage,
    }


def coach_profile_for_intent(intent: str) -> CoachProfile | None:
    for profile in COACH_PROFILES.values():
        if profile.intent == intent:
            return profile
    return None


def _load_skill_bundle(skill_name: str) -> str:
    parts: list[str] = []
    base = settings.chitung_skills_dir / skill_name
    for filename in ("SKILL.md", "reference.md"):
        path = base / filename
        if path.exists():
            parts.append(f"=== {filename} ===\n{path.read_text(encoding='utf-8', errors='ignore')}")
    if not parts:
        loaded = skill_loader.read_skill(skill_name)
        if loaded:
            parts.append(loaded)
    return "\n\n".join(parts)[:_MAX_SKILL_CHARS]


def _build_system_prompt(profile: CoachProfile, skill_text: str, usage: dict[str, Any]) -> str:
    usage_json = json.dumps(usage, ensure_ascii=False, indent=2)
    return (
        f"你是赤瞳安全智能平台的「{profile.role_title}」。你必须严格遵循下面的 Skill 规范。\n"
        "你只能输出给用户看的中文 Markdown 对话内容。\n"
        "绝对不要生成 SKILL.md、代码、JSON 配置，不要假装执行了工作流、自动化或工具。\n"
        "必须结合「本地使用情况快照」给出个性化建议：优先推荐已用过/已启用的项，对从未运行的项说明如何低风险试跑。\n"
        "对初学者要耐心、分步、可落地；每轮回复控制篇幅，并留 1–2 个引导性问题。\n\n"
        f"{skill_text}\n\n"
        "=== 本地使用情况快照（实时，仅供你分析，不要原样整段贴给用户） ===\n"
        f"{usage_json}\n"
    )


def _build_messages(history: list[dict[str, str]], user_message: str) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for item in history:
        role = item.get("role")
        content = str(item.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message.strip()})
    return messages


def _recent_coach_history(session_id: str | None, profile: CoachProfile) -> list[dict[str, str]]:
    coach_skill_names = set(COACH_PROFILES.keys())
    coach_intents = {item.intent for item in COACH_PROFILES.values()}
    if not session_id:
        return []
    payload = chat_store.get_history(session_id, limit=_MAX_HISTORY)
    rows = payload.get("messages") if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        return []
    history: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        intent = row.get("intent") if isinstance(row.get("intent"), dict) else {}
        intent_name = str(intent.get("intent") or "")
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        applied = metadata.get("applied_skill") if isinstance(metadata.get("applied_skill"), dict) else {}
        applied_name = str(applied.get("name") or "")
        is_coach = intent_name in coach_intents or applied_name in coach_skill_names
        if is_coach and intent_name and intent_name != profile.intent:
            continue
        role = str(row.get("role") or "")
        content = str(row.get("content") or "").strip()
        if not content:
            continue
        history.append({"role": role, "content": content})
    return history[-_MAX_HISTORY:]


def _extract_reply(llm_result: dict[str, Any]) -> str:
    if llm_result.get("available") is False:
        return ""
    choices = llm_result.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else {}
        content = message.get("content") if isinstance(message, dict) else ""
        return content if isinstance(content, str) else ""
    return ""


def _extract_follow_ups(reply: str) -> list[str]:
    lines = [line.strip(" -•\t") for line in reply.splitlines()]
    questions = [line for line in lines if line.endswith("？") or line.endswith("?")]
    return questions[-2:]


def _fallback_reply(profile: CoachProfile, user_message: str, usage: dict[str, Any]) -> str:
    lines = [
        f"## {profile.display_name}（离线简版）",
        "",
        "当前 LLM 未配置。我会结合本地记录给你可执行的入门指引：",
        "",
        "### 本地使用概况",
    ]
    lines.extend(_usage_summary_lines(profile.domain, usage))
    lines.extend(
        [
            "",
            "### 三步开始",
            "1. 运行 `scripts\\演示前检查.bat`",
            "2. 打开对应页面按步骤操作",
            "3. 到执行中心查看是否 success",
            "",
            "### 提醒",
            "- 本教练只对话指导，不生成 Skill 文件、不直接执行流程",
            "- 配置 LLM 后可获得更详细的个性化教练",
            "",
            _domain_quick_tip(profile.domain, user_message),
        ]
    )
    return "\n".join(lines)


def _usage_summary_lines(domain: str, usage: dict[str, Any]) -> list[str]:
    totals = usage.get("totals") if isinstance(usage.get("totals"), dict) else {}
    if domain == "skill":
        lines = [f"- 已安装 Skill：**{totals.get('skill_count', 0)}** 个（启用 {totals.get('enabled_skill_count', 0)}）"]
        most_used = usage.get("most_used_skills") if isinstance(usage.get("most_used_skills"), list) else []
        if most_used:
            lines.append("- 最近有运行记录的 Skill：")
            for row in most_used[:4]:
                if isinstance(row, dict):
                    lines.append(f"  - {row.get('display_name')}（{row.get('run_count')} 次）")
        never = usage.get("never_run_skills") if isinstance(usage.get("never_run_skills"), list) else []
        if never:
            lines.append(f"- 尚未看到运行记录：{', '.join(str(x) for x in never[:5])}")
        return lines
    if domain == "workflow":
        return [
            f"- 工作流模板：**{totals.get('workflow_template_count', 0)}** 个",
            f"- Chat/Agent 工作流 job：**{totals.get('agent_workflow_jobs', 0)}** 次（成功 {totals.get('success_jobs', 0)} / 失败 {totals.get('failed_jobs', 0)}）",
            *_top_workflow_lines(usage.get("by_workflow")),
        ]
    return [
        f"- 自动化类模板：**{totals.get('automation_template_count', 0)}** 个",
        f"- 后端自动化相关 job：**{totals.get('backend_automation_jobs', 0)}** 次",
        "- Automation 页任务在浏览器 localStorage，请打开 `#/center/automation` 查看",
        *_top_workflow_lines(usage.get("by_workflow")),
    ]


def _top_workflow_lines(value: Any) -> list[str]:
    if not isinstance(value, dict) or not value:
        return ["- 暂无可统计的运行记录，建议先在 Chat 手动触发一次"]
    top = list(value.items())[:4]
    return ["- 运行较多的流程："] + [f"  - `{name}`：{count} 次" for name, count in top]


def _domain_quick_tip(domain: str, user_message: str) -> str:
    lowered = user_message.lower()
    if domain == "skill":
        return "试试：`🔨 使用技能：制度知识问答`，再到 `#/center/skills` 查看启用状态。"
    if domain == "workflow":
        if any(token in lowered for token in ["视觉", "巡检"]):
            return "建议：先用 `#/guardian/patrol` 跑通，再到 `#/center/execution` 看 job。"
        return "建议：在 Chat 触发一次，例如「生成今日外部风险简报」。"
    return "建议：打开 `#/center/automation` 选模板 → 保存 → 先手动运行一次再开定时。"
