"""
docx_diff.py — 变更预览卡片生成

按《DocMate EHS docx升级与Skill落地实施方案 v1》第 6.3 节 + 第 10 节实现。
"""

from __future__ import annotations

from typing import Optional

from .docx_model import (
    ChangeType,
    RiskLevel,
    ChangeStatus,
    DocumentChange,
    ChangeSet,
    PreviewCard,
)


# ─── 1. 变更类型 → 中文标题映射 ─────────────────────────────────

_CHANGE_TYPE_TITLES = {
    ChangeType.TEXT_REPLACE:      "段落文字替换",
    ChangeType.TEXT_INSERT:       "插入新段落",
    ChangeType.TEXT_DELETE:       "删除段落",
    ChangeType.TABLE_CELL_UPDATE: "表格单元格修改",
    ChangeType.TABLE_INSERT:      "插入新表格",
    ChangeType.IMAGE_INSERT:      "插入图片",
    ChangeType.IMAGE_REPLACE:     "替换图片",
}

_RISK_LABELS = {
    RiskLevel.HIGH:   "⚠ 高风险",
    RiskLevel.MEDIUM: "● 中风险",
    RiskLevel.LOW:    "○ 低风险",
}


# ─── 2. 生成预览卡片 ────────────────────────────────────────────

def generate_preview_cards(changeset: ChangeSet) -> list[PreviewCard]:
    """
    对 ChangeSet 中的每条变更生成预览卡片。
    对应方案第 6.3 节 Response。
    """
    cards = []
    for chg in changeset.changes:
        card = _build_card(chg)
        cards.append(card)
    return cards


def _build_card(chg: DocumentChange) -> PreviewCard:
    """为单条变更构建预览卡片。"""
    title = _CHANGE_TYPE_TITLES.get(chg.change_type, str(chg.change_type.value))

    # 定位信息
    location = _build_location(chg)

    # old/new
    old_content = chg.old_content or "(空)"
    new_content = _format_new_content(chg)

    return PreviewCard(
        change_id=chg.change_id,
        title=title,
        old_content=str(old_content)[:500],
        new_content=str(new_content)[:500],
        risk_level=chg.risk_level.value,
        location=location,
        reason=chg.reason or "",
    )


def _build_location(chg: DocumentChange) -> str:
    """构建人类可读的定位信息。"""
    parts = []
    ct = chg.change_type

    if chg.target.paragraph_id:
        match = __import__("re").match(r"P(\d+)#", chg.target.paragraph_id)
        if match:
            parts.append(f"第{match.group(1)}段")

    if chg.target.table_id:
        match = __import__("re").match(r"T(\d+)#", chg.target.table_id)
        if match:
            parts.append(f"第{match.group(1)}个表格")

    if chg.target.cell:
        r = chg.target.cell.get("row", "?")
        c = chg.target.cell.get("col", "?")
        parts.append(f"第{r}行第{c}列")

    if ct == ChangeType.TEXT_INSERT:
        parts.append("之后插入")
    elif ct == ChangeType.IMAGE_INSERT:
        parts.append("之后插入图片")

    return " · ".join(parts) if parts else "全文"


def _format_new_content(chg: DocumentChange) -> str:
    """格式化 new_content 用于预览。"""
    if chg.change_type == ChangeType.IMAGE_INSERT:
        img_path = chg.image_path or chg.new_content
        return f"[图片] {img_path}"
    if chg.change_type == ChangeType.TABLE_INSERT:
        rows = chg.table_rows
        cols = chg.table_cols
        return f"[表格 {rows}行 × {cols}列]"
    return chg.new_content or "(空)"


# ─── 3. 批量操作建议 ────────────────────────────────────────────

def get_batch_suggestions(changeset: ChangeSet) -> dict:
    """
    生成批量操作建议（对应方案第 10 节）。
    """
    high_risk_ids = []
    medium_risk_ids = []
    low_risk_ids = []

    for chg in changeset.changes:
        if chg.status != ChangeStatus.PENDING:
            continue
        if chg.risk_level == RiskLevel.HIGH:
            high_risk_ids.append(chg.change_id)
        elif chg.risk_level == RiskLevel.MEDIUM:
            medium_risk_ids.append(chg.change_id)
        else:
            low_risk_ids.append(chg.change_id)

    return {
        "accept_all_except_high": {
            "label": "全部接受（高风险除外）",
            "change_ids": medium_risk_ids + low_risk_ids,
            "count": len(medium_risk_ids) + len(low_risk_ids),
        },
        "reject_all": {
            "label": "全部拒绝",
            "change_ids": [],
            "action": "reject_all",
        },
        "accept_low_only": {
            "label": "仅接受低风险",
            "change_ids": low_risk_ids,
            "count": len(low_risk_ids),
        },
        "high_risk_review": {
            "label": "高风险需人工复核",
            "change_ids": high_risk_ids,
            "count": len(high_risk_ids),
            "force_review": True,
        },
    }


# ─── 4. 变更摘要 ────────────────────────────────────────────────

def generate_changeset_summary(changeset: ChangeSet) -> dict:
    """
    生成 ChangeSet 的可读摘要。
    """
    cards = generate_preview_cards(changeset)
    suggestions = get_batch_suggestions(changeset)

    return {
        "changeset_id": changeset.changeset_id,
        "doc_id": changeset.doc_id,
        "created_at": changeset.created_at,
        "summary": changeset.summary.to_dict(),
        "preview_cards": [c.to_dict() for c in cards],
        "batch_suggestions": suggestions,
    }
