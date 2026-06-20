"""
ehs_skills/__init__.py — 安环 Skill 包入口

按《DocMate EHS docx升级与Skill落地实施方案 v1》第 8 节实现。
"""

from .clarify_intent_ehs import clarify_intent_ehs
from .form_fill_ehs import form_fill_ehs, EHS_FORM_SCHEMAS
from .style_guard_ehs import style_guard_ehs
from .consistency_guard_ehs import consistency_guard_ehs
from .risk_gate_ehs import risk_gate_ehs

__all__ = [
    "clarify_intent_ehs",
    "form_fill_ehs",
    "EHS_FORM_SCHEMAS",
    "style_guard_ehs",
    "consistency_guard_ehs",
    "risk_gate_ehs",
]

# Skill 注册表：供编排器调用
SKILL_REGISTRY = {
    "clarify_intent_ehs": clarify_intent_ehs,
    "form_fill_ehs": form_fill_ehs,
    "style_guard_ehs": style_guard_ehs,
    "consistency_guard_ehs": consistency_guard_ehs,
    "risk_gate_ehs": risk_gate_ehs,
}
