"""
ehs_skills/style_guard_ehs.py — Skill-3 风格规范守护

按《DocMate EHS docx升级与Skill落地实施方案 v1》第 8.3 节实现。

目标：将口语化、模糊表达规范为安环公文表达。
"""

from __future__ import annotations

from typing import Any


# ─── 1. 风格转换规则 ────────────────────────────────────────────

# 模糊表达 → 精确表达
STYLE_RULES = [
    # 时间模糊 → 精确
    ("尽快",     "于规定时限内"),
    ("马上",     "立即"),
    ("过几天",   "于 3 个工作日内"),
    ("最近",     "近 7 个工作日内"),

    # 程度模糊 → 量化
    ("好几次",   "累计 3 次及以上"),
    ("不少",     "多处（≥3 处）"),
    ("一些",     "若干（≥2 项）"),
    ("差不多",   "基本"),
    ("大部分",   "80% 以上"),

    # 人员模糊 → 角色
    ("施工队",   "施工作业班组"),
    ("监理",     "监理单位"),
    ("甲方",     "建设单位"),
    ("领导",     "上级主管部门负责人"),

    # 动作模糊 → 标准动作
    ("确认一下", "核实确认"),
    ("检查一下", "现场检查"),
    ("通知一下", "书面通知"),
    ("说一声",   "口头告知"),
    ("看一下",   "现场查看"),
    ("处理掉",   "完成整改"),

    # 结论模糊 → 标准结论
    ("应该没问题", "经初步判断合格"),
    ("不太对",     "不符合规范要求"),
    ("还行",       "基本满足要求"),
    ("挺严重",     "情节严重"),
    ("没什么大事", "经评估为一般隐患"),
]


# ─── 2. 风格守护核心逻辑 ──────────────────────────────────────

def style_guard_ehs(text: str) -> dict:
    """
    检测并建议替换文本中的口语化表达。

    对应方案第 8.3 节。

    Args:
        text: 待检查的文本（可以是整段、整句）

    Returns:
        {
            "ok": True,
            "suggestions": [
                {"original": "尽快", "replacement": "于规定时限内", "position": 15}
            ],
            "normalized_text": "替换后的文本"
        }
    """
    suggestions = []
    normalized = text

    for informal, formal in STYLE_RULES:
        if informal in normalized:
            pos = normalized.index(informal)
            suggestions.append({
                "original": informal,
                "replacement": formal,
                "position": pos,
                "rule": "terminology_normalization",
            })
            normalized = normalized.replace(informal, formal)

    return {
        "ok": True,
        "original_text": text,
        "normalized_text": normalized,
        "suggestions": suggestions,
        "change_count": len(suggestions),
    }


# ─── 3. 批量检查 ────────────────────────────────────────────────

def style_guard_batch(paragraphs: list[str]) -> dict:
    """
    批量检查多个段落。

    Returns:
        {
            "ok": True,
            "results": [{paragraph_index, suggestions, normalized_text}, ...],
            "total_suggestions": N,
        }
    """
    results = []
    total = 0

    for i, text in enumerate(paragraphs):
        r = style_guard_ehs(text)
        r["paragraph_index"] = i
        results.append(r)
        total += r["change_count"]

    return {
        "ok": True,
        "results": results,
        "total_suggestions": total,
    }


# ─── 4. 安环公文风格标准 ────────────────────────────────────────

EHS_STYLE_STANDARDS = {
    "tone": "正式、客观、准确",
    "person": "第三人称（避免'我''我们'）",
    "tense": "完成时（已完成整改）/ 将来时（限期整改）",
    "structure": "发现 → 判断 → 处理 → 复查 → 闭环",
    "format": {
        "日期": "YYYY-MM-DD HH:MM",
        "金额": "X万元 / X元",
        "百分比": "X%",
        "编号": "公司统一编号规则",
    },
}


def get_style_guide() -> dict:
    """返回安环公文风格指引。"""
    return EHS_STYLE_STANDARDS
