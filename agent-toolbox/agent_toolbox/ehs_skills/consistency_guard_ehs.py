"""
ehs_skills/consistency_guard_ehs.py — Skill-4 一致性守护

按《DocMate EHS docx升级与Skill落地实施方案 v1》第 8.4 节实现。

检查范围：
1. 时间线一致性（发现 → 整改 → 复查）
2. 责任主体一致性（部门、人名、岗位）
3. 风险等级一致性（文本段落与表格字段）
4. 数值一致性（隐患数量、整改完成数）
5. 法规引用一致性（名称、条款格式）
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional


# ─── 1. 冲突类型枚举 ────────────────────────────────────────────

CONFLICT_TYPES = {
    "date_conflict":       "时间冲突",
    "responsibility_conflict": "责任主体冲突",
    "risk_level_conflict": "风险等级冲突",
    "numeric_conflict":    "数值冲突",
    "law_reference_conflict": "法规引用冲突",
}


# ─── 2. 时间线一致性检查 ────────────────────────────────────────

def _check_date_consistency(
    filled_fields: list[dict],
    changes: list[dict],
) -> list[dict]:
    """
    检查时间线：发现时间 < 整改完成时间 < 复查时间。
    """
    conflicts = []

    dates = {}
    for f in filled_fields:
        field = f.get("field", "")
        value = f.get("value", "")
        if "时间" in field or "日期" in field:
            try:
                parsed = _parse_date(value)
                if parsed:
                    dates[field] = parsed
            except Exception:
                pass

    # 简单校验
    if "发现时间" in dates and "整改完成时间" in dates:
        if dates["发现时间"] > dates["整改完成时间"]:
            conflicts.append({
                "type": "date_conflict",
                "location": "filled_fields",
                "detail": "发现时间晚于整改完成时间",
                "severity": "high",
                "suggestion": "请确认时间顺序：发现 → 整改 → 复查",
                "fields": ["发现时间", "整改完成时间"],
            })

    if "整改完成时间" in dates and "复查时间" in dates:
        if dates["整改完成时间"] > dates["复查时间"]:
            conflicts.append({
                "type": "date_conflict",
                "location": "filled_fields",
                "detail": "复查时间早于整改完成时间",
                "severity": "high",
                "suggestion": "请确认复查日期在整改完成之后",
                "fields": ["整改完成时间", "复查时间"],
            })

    return conflicts


def _parse_date(date_str: str) -> Optional[datetime]:
    """尝试解析多种日期格式。"""
    formats = [
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y.%m.%d",
        "%Y年%m月%d日",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


# ─── 3. 责任主体一致性 ──────────────────────────────────────────

def _check_responsibility_consistency(
    filled_fields: list[dict],
    all_changes_text: str,
) -> list[dict]:
    """
    检查责任主体在各处是否一致。
    """
    conflicts = []

    # 提取责任主体
    responsibility_fields = {}
    for f in filled_fields:
        field = f.get("field", "")
        if field in ("责任人", "责任部门", "发现人", "复查人", "审批人"):
            responsibility_fields[field] = f.get("value", "")

    # 检查同名责任人是否有不同的写法
    person_names = set()
    for field, value in responsibility_fields.items():
        if value and len(value) >= 2:
            # 简单去重
            cleaned = value.strip().replace(" ", "")
            if cleaned in person_names:
                conflicts.append({
                    "type": "responsibility_conflict",
                    "location": f"field:{field}",
                    "detail": f"责任主体「{value}」出现不一致的写法",
                    "severity": "medium",
                    "suggestion": f"请统一责任人/责任部门名称格式",
                    "fields": list(responsibility_fields.keys()),
                })
            person_names.add(cleaned)

    return conflicts


# ─── 4. 风险等级一致性 ──────────────────────────────────────────

def _check_risk_level_consistency(
    changes: list[dict],
) -> list[dict]:
    """
    检查文本段落中的风险等级与表格字段是否一致。
    """
    conflicts = []
    risk_levels_found = {}

    for chg in changes:
        new_content = chg.get("new_content", "")
        old_content = chg.get("old_content", "")

        for level in ("高风险", "中风险", "低风险", "重大风险"):
            if level in new_content:
                if level not in risk_levels_found:
                    risk_levels_found[level] = []
                risk_levels_found[level].append(chg.get("change_id", ""))

    # 如果有多个不同等级同时出现，检查是否冲突
    if len(risk_levels_found) > 1:
        # 不一定是冲突，但值得标记
        conflicts.append({
            "type": "risk_level_conflict",
            "location": "changes",
            "detail": f"文档中出现多个风险等级：{'、'.join(risk_levels_found.keys())}",
            "severity": "low",
            "suggestion": "请确认各处的风险等级是否基于同一评估标准",
            "levels": list(risk_levels_found.keys()),
        })

    return conflicts


# ─── 5. 数值一致性 ──────────────────────────────────────────────

def _check_numeric_consistency(
    changes: list[dict],
    filled_fields: list[dict],
) -> list[dict]:
    """
    检查数值字段是否一致（隐患数量 vs 整改完成数等）。
    """
    conflicts = []
    numeric_fields = {}

    for f in filled_fields:
        field = f.get("field", "")
        value = f.get("value", "")
        if field in ("隐患个数", "隐患数量", "整改完成数", "伤亡人数", "参训人数"):
            try:
                numeric_fields[field] = int(value)
            except (ValueError, TypeError):
                pass

    # 隐患数量 ≥ 整改完成数
    if "隐患数量" in numeric_fields and "整改完成数" in numeric_fields:
        if numeric_fields["整改完成数"] > numeric_fields["隐患数量"]:
            conflicts.append({
                "type": "numeric_conflict",
                "location": "filled_fields",
                "detail": "整改完成数大于隐患总数，逻辑异常",
                "severity": "high",
                "suggestion": "请确认两者数值是否正确",
                "fields": ["隐患数量", "整改完成数"],
            })

    return conflicts


# ─── 6. 法规引用一致性 ──────────────────────────────────────────

def _check_law_reference_consistency(
    all_changes_text: str,
) -> list[dict]:
    """检查法规引用格式是否一致。"""
    conflicts = []
    return conflicts  # 简化为由 ehs_rules.py 处理


# ─── 7. 主入口 ──────────────────────────────────────────────────

def consistency_guard_ehs(
    filled_fields: Optional[list[dict]] = None,
    changes: Optional[list[dict]] = None,
    all_changes_text: str = "",
) -> dict:
    """
    综合一致性检查。

    对应方案第 8.4 节。

    Returns:
        {
            "ok": True,
            "conflicts": [...],
            "conflict_count": N,
        }
    """
    filled_fields = filled_fields or []
    changes = changes or []

    all_conflicts = []
    all_conflicts.extend(_check_date_consistency(filled_fields, changes))
    all_conflicts.extend(_check_responsibility_consistency(filled_fields, all_changes_text))
    all_conflicts.extend(_check_risk_level_consistency(changes))
    all_conflicts.extend(_check_numeric_consistency(changes, filled_fields))
    all_conflicts.extend(_check_law_reference_consistency(all_changes_text))

    return {
        "ok": True,
        "conflicts": all_conflicts,
        "conflict_count": len(all_conflicts),
        "has_high_severity": any(c["severity"] == "high" for c in all_conflicts),
        "has_medium_severity": any(c["severity"] == "medium" for c in all_conflicts),
    }
