"""
ehs_skills/risk_gate_ehs.py — Skill-5 高风险审查闸门

按《DocMate EHS docx升级与Skill落地实施方案 v1》第 8.5 节实现。

触发高风险审查的字段：
1. 事故等级（一般/较大/重大/特别重大）
2. 责任认定
3. 法规条款引用
4. 处罚建议
5. 伤亡与损失数字
"""

from __future__ import annotations

from typing import Any, Optional

from ..ehs_rules import HIGH_RISK_FIELDS, NO_FABRICATION_FIELDS


# ─── 1. 高风险触发检测 ──────────────────────────────────────────

def _detect_high_risk_changes(changes: list[dict]) -> list[str]:
    """
    扫描变更列表，标记涉及高风险字段的变更 ID。
    """
    high_risk_change_ids = []

    for chg in changes:
        change_type = chg.get("change_type", "")
        new_content = chg.get("new_content", "")
        old_content = chg.get("old_content", "")
        target_field = chg.get("target", {}).get("field", "")

        # 检查是否涉及高风险字段
        is_high_risk = False
        reason = ""

        for field in HIGH_RISK_FIELDS:
            if field in str(new_content) or field in str(old_content) or field == target_field:
                is_high_risk = True
                reason = f"涉及高风险字段：{field}"
                break

        # 检查是否编造了事实字段
        if not is_high_risk:
            for field in NO_FABRICATION_FIELDS:
                if field in str(new_content) and field not in str(old_content):
                    is_high_risk = True
                    reason = f"涉及新增敏感字段：{field}（需核实来源）"
                    break

        if is_high_risk:
            chg_id = chg.get("change_id", "")
            if chg_id:
                high_risk_change_ids.append(chg_id)
                chg["risk_level"] = "high"
                chg["risk_override"] = True
                chg["risk_reason"] = reason

    return high_risk_change_ids


# ─── 2. 高风险闸门核心逻辑 ──────────────────────────────────────

def risk_gate_ehs(changes: list[dict]) -> dict:
    """
    高风险审查闸门。

    对应方案第 8.5 节。

    Args:
        changes: LLM 生成的变更列表

    Returns:
        {
            "ok": True,
            "allow_auto_apply": bool,
            "review_required_changes": ["chg_3", "chg_5"],
            "reason": "涉及事故等级与责任主体变更",
            "auto_apply_changes": ["chg_1", "chg_2"],
        }
    """
    high_risk_ids = _detect_high_risk_changes(changes)

    auto_apply = []
    review_required = []

    for chg in changes:
        chg_id = chg.get("change_id", "")
        if chg_id in high_risk_ids:
            review_required.append(chg_id)
        else:
            auto_apply.append(chg_id)

    if review_required:
        allow_auto = False
        reason = f"{len(review_required)} 条变更涉及高风险字段或敏感内容，需人工复核"
    else:
        allow_auto = True
        reason = "所有变更为低/中风险，可自动应用"

    return {
        "ok": True,
        "allow_auto_apply": allow_auto,
        "review_required_changes": review_required,
        "auto_apply_changes": auto_apply,
        "reason": reason,
        "high_risk_field_check": {
            "scanned_fields": HIGH_RISK_FIELDS[:10],
            "triggered_fields": _get_triggered_fields(changes),
        },
    }


def _get_triggered_fields(changes: list[dict]) -> list[str]:
    """返回此次变更涉及的具体高风险字段。"""
    triggered = set()
    for chg in changes:
        new_content = str(chg.get("new_content", ""))
        old_content = str(chg.get("old_content", ""))
        for field in HIGH_RISK_FIELDS + NO_FABRICATION_FIELDS:
            if field in new_content or field in old_content:
                triggered.add(field)
    return sorted(triggered)


# ─── 3. 高风险变更类型特别处理 ──────────────────────────────────

# 以下变更类型无论内容如何，都需要人工确认
ALWAYS_REVIEW_CHANGE_TYPES = {
    # 任何涉及责任主体变更的操作
    # 实际通过字段检查来触发
}


def should_force_review(change: dict) -> tuple[bool, str]:
    """
    判断单条变更是否必须人工审核。

    Returns:
        (force_review, reason)
    """
    change_type = change.get("change_type", "")
    new_content = str(change.get("new_content", ""))

    # 事故等级变更
    for level in ("特别重大", "重大", "较大"):
        if level in new_content:
            return True, f"涉及 {level} 事故等级"

    # 伤亡数字
    for keyword in ("伤亡", "死亡", "重伤", "轻伤"):
        if keyword in new_content:
            return True, f"涉及 {keyword} 信息"

    # 处罚建议
    for keyword in ("处罚", "罚款", "停产", "吊销"):
        if keyword in new_content:
            return True, f"涉及 {keyword}"

    # 法规条款
    for keyword in ("违反", "第X条", "依据"):
        if keyword in new_content:
            return True, "涉及法规条款引用"

    return False, ""
