from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from chitung_center.audit import audit_logger
from chitung_center.chat_store import chat_store
from chitung_center.config import settings
from chitung_center.llm_gateway import llm_gateway

MEMORY_PATH = settings.chitung_data_dir / "long_term_memory.md"


def read_long_term_memory() -> dict[str, Any]:
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not MEMORY_PATH.exists():
        MEMORY_PATH.write_text(_initial_memory(), encoding="utf-8")
    content = MEMORY_PATH.read_text(encoding="utf-8", errors="ignore")
    return {
        "ok": True,
        "content": content,
        "path": str(MEMORY_PATH),
        "updated_at": datetime.fromtimestamp(MEMORY_PATH.stat().st_mtime, timezone.utc).isoformat(),
    }


def save_long_term_memory(content: str) -> dict[str, Any]:
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    text = content.strip()
    if not text.startswith("#"):
        text = "# 赤瞳长期记忆\n\n" + text
    MEMORY_PATH.write_text(text + "\n", encoding="utf-8")
    audit_id = audit_logger.write("long_term_memory_saved", {"chars": len(text), "path": str(MEMORY_PATH)})
    return {**read_long_term_memory(), "audit_id": audit_id}


def memory_context(max_chars: int = 2400) -> str:
    content = str(read_long_term_memory().get("content") or "")
    compact = _strip_noise(content)
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 20] + "\n...[已截断]"


async def summarize_today_into_memory(user_id: str = "local_user") -> dict[str, Any]:
    since = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    messages = chat_store.list_messages_since(since, limit=600)
    messages = [m for m in messages if str(m.get("content") or "").strip()]
    summary = await _summarize_messages(messages)
    existing = str(read_long_term_memory().get("content") or "")
    today = datetime.now().strftime("%Y-%m-%d")
    next_content = _merge_daily_summary(existing, today, summary)
    saved = save_long_term_memory(next_content)
    audit_id = audit_logger.write(
        "long_term_memory_summarized",
        {"user_id": user_id, "message_count": len(messages), "summary_chars": len(summary)},
    )
    return {
        "ok": True,
        "message": f"已总结今日 {len(messages)} 条对话，并写入长期记忆。",
        "summary": summary,
        "memory": saved,
        "audit_id": audit_id,
        "message_count": len(messages),
    }


async def _summarize_messages(messages: list[dict[str, Any]]) -> str:
    if not messages:
        return "- 今日暂无可总结的对话。"
    transcript = "\n".join(
        f"{m.get('created_at', '')} {m.get('role', '')}: {str(m.get('content') or '').strip()[:1200]}"
        for m in messages[-120:]
    )
    if settings.llm_configured:
        raw = await llm_gateway.complete_document_json(
            "你是赤瞳中台的长期记忆整理器。只返回 JSON object。",
            json.dumps(
                {
                    "task": "总结今日对话，提炼适合长期保留的事实、用户偏好、项目决策、待办和避免重复解释的上下文。",
                    "rules": [
                        "不要记录一次性的闲聊、临时日志和敏感密钥。",
                        "保留软件架构、模块命名、用户偏好、已完成/待验证功能。",
                        "输出 markdown bullets，必须精简。",
                    ],
                    "transcript": transcript,
                },
                ensure_ascii=False,
            ),
        )
        parsed = _extract_json(raw)
        summary = parsed.get("summary_markdown") or parsed.get("summary") or parsed.get("memory")
        if isinstance(summary, str) and summary.strip():
            return summary.strip()
    return _rule_based_summary(messages)


def _rule_based_summary(messages: list[dict[str, Any]]) -> str:
    user_messages = [str(m.get("content") or "").strip() for m in messages if m.get("role") == "user"]
    assistant_messages = [str(m.get("content") or "").strip() for m in messages if m.get("role") == "assistant"]
    latest_user = user_messages[-8:]
    latest_done = [m for m in assistant_messages if any(token in m for token in ["已完成", "完成", "通过", "修复", "新增"])][-8:]
    bullets = ["- 用户正在建设赤瞳安全生产 AI 操作系统，偏好中文界面、模块化板块、可视化操作和可手动校正。"]
    for text in latest_user:
        bullets.append(f"- 近期用户需求：{_shorten(text)}")
    for text in latest_done:
        bullets.append(f"- 近期实现/反馈：{_shorten(text)}")
    return "\n".join(dict.fromkeys(bullets))


def _merge_daily_summary(existing: str, date_text: str, summary: str) -> str:
    base = existing.strip() or _initial_memory().strip()
    section = f"## {date_text}\n\n{summary.strip()}\n"
    pattern = re.compile(rf"## {re.escape(date_text)}\n.*?(?=\n## \d{{4}}-\d{{2}}-\d{{2}}\n|\Z)", re.S)
    if pattern.search(base):
        return pattern.sub(section.strip(), base).strip()
    return f"{base}\n\n{section}".strip()


def _extract_json(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    if raw.get("available") is False:
        return {}
    if any(key in raw for key in ["summary", "summary_markdown", "memory"]):
        return raw
    choices = raw.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else {}
        content = message.get("content") if isinstance(message, dict) else ""
        if isinstance(content, str):
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return {"summary": content}
    return {}


def _strip_noise(content: str) -> str:
    lines = []
    for line in content.splitlines():
        if line.strip().startswith("<!--"):
            continue
        lines.append(line.rstrip())
    return "\n".join(lines).strip()


def _shorten(text: str, limit: int = 180) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    return compact if len(compact) <= limit else compact[: limit - 1] + "…"


def _initial_memory() -> str:
    return """# 赤瞳长期记忆

这份文档用于保存赤瞳中台与用户长期协作中值得保留的上下文。闪闪助手会定期参考这里的内容，但不会把它当作不可修改的事实；用户可在“长期记忆”页面手动编辑。

## 稳定偏好

- 默认使用中文沟通和中文界面文案。
- 功能应尽量可视化、可手动确认、可回溯，不要隐藏在后台。
- 重要动作优先做成中台页面、Skill 或执行中心任务，方便后续维护。
"""
