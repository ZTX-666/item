"""
ehs_skills/clarify_intent_ehs.py — Skill-1 意图澄清

按《DocMate EHS docx升级与Skill落地实施方案 v1》第 8.1 节实现。

触发条件：
- 指令含"改一下""规范点""优化一下"但无明确对象/范围。
"""

from __future__ import annotations

from typing import Any, Optional

# ─── 触发检测 ───────────────────────────────────────────────────

_AMBIGUOUS_KEYWORDS = [
    "改一下", "规范点", "优化一下", "调整一下",
    "弄好看点", "专业点", "改改", "完善一下",
    "看着办", "随便改",
]

_SPECIFIC_KEYWORDS = [
    "改为", "改成", "替换", "删除", "添加", "插入", "追加",
    "修改为", "更新为", "变更为", "修正为",
    "第",  # 含"第X段/第X行"等定位
    "巡检人员", "日期", "编号", "区域",  # 具体字段名
]


def is_ambiguous(instruction: str) -> bool:
    """检测指令是否模糊。
    
    模糊：含"改一下""优化一下"等笼统词，且不含具体定位词（"改为""第X段"）。
    具体：含"改为""改成""替换"等精确操作词 → 不模糊。
    """
    has_ambiguous = any(kw in instruction for kw in _AMBIGUOUS_KEYWORDS)
    has_specific = any(kw in instruction for kw in _SPECIFIC_KEYWORDS)
    
    # 如果既有模糊词又有具体词 → 以具体为准
    if has_specific:
        return False
    return has_ambiguous


# ─── 意图澄清核心逻辑 ──────────────────────────────────────────

def clarify_intent_ehs(
    instruction: str,
    doc_outline: Optional[list[str]] = None,
    selected_text: Optional[str] = None,
    form_type: str = "",
) -> dict:
    """
    对模糊指令生成最小追问列表。

    对应方案第 8.1 节。

    Args:
        instruction: 用户原始指令
        doc_outline: 文档大纲（段落/标题列表）
        selected_text: 用户选中的文本
        form_type: 表单类型

    Returns:
        {"action": "clarify", "questions": [...]}
    """ 
    # 指令不够模糊 → 直接放行，不追问
    if not is_ambiguous(instruction):
        return {"action": "direct", "reason": "instruction_is_specific"}
    
    questions = []

    # Q1: 修改范围
    if not selected_text:
        doc_hint = ""
        if doc_outline:
            headings = [h for h in doc_outline if h.startswith("#")]
            if headings:
                doc_hint = f"（文档包含：{', '.join(headings[:5])}）"
        questions.append(f"请确认修改范围：全文、某段还是某个表格？{doc_hint}")
    else:
        questions.append("请确认：仅修改选中的文字，还是整段？")

    # Q2: 保留约束
    questions.append("是否保留原风险等级与责任主体不变？")

    # Q3: 目标文档类型
    if not form_type:
        options = "整改通知 / 事故通报 / 巡检记录 / 培训记录 / 台账"
        questions.append(f"目标文档类型是？({options})")

    # Q4: 改写方向（如果有"优化"类关键词）
    if any(kw in instruction for kw in ["优化", "规范", "专业", "完善"]):
        questions.append("希望往哪个方向优化？（更正式/更简洁/补充细节/调整结构/统一格式）")

    return {
        "action": "clarify",
        "questions": questions,
        "original_instruction": instruction,
    }


# ─── 兜底：生成精细化追问 ──────────────────────────────────────

def generate_detailed_clarify(
    instruction: str,
    doc_structure: Optional[dict] = None,
) -> dict:
    """
    完整版：根据文档结构生成更精细的追问。
    供编排器在 LLM 判断需要澄清时调用。
    """
    result = clarify_intent_ehs(instruction)

    if doc_structure:
        para_count = len(doc_structure.get("paragraphs", []))
        table_count = len(doc_structure.get("tables", []))
        img_count = len(doc_structure.get("images", []))

        context_hint = f"文档共 {para_count} 段、{table_count} 个表格、{img_count} 张图片。"
        result["questions"].insert(0, context_hint)

        # 补充定位问题
        if table_count > 0:
            result["questions"].append(
                f"是否涉及表格修改？（文档含 {table_count} 个表格）"
            )

    return result
