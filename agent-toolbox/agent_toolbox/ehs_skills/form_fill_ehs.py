"""
ehs_skills/form_fill_ehs.py — Skill-2 表单智能填充

按《DocMate EHS docx升级与Skill落地实施方案 v1》第 8.2 节实现。

目标：对安环模板进行字段级填充，输出「已填、缺失、需确认」三类结果。
"""

from __future__ import annotations

from typing import Any, Optional

# ─── 1. 安环表单 Schema 定义 ────────────────────────────────────

# 隐患整改通知单字段
HAZARD_RECTIFICATION_SCHEMA = {
    "form_type": "hazard_rectification",
    "required_fields": [
        "隐患编号", "发现时间", "发现人", "隐患描述",
        "隐患位置", "风险等级", "整改措施", "责任人",
        "责任部门", "整改时限", "复查结论", "复查人",
    ],
    "optional_fields": [
        "隐患照片", "整改前照片", "整改后照片",
        "整改费用", "关联事故编号", "备注",
    ],
    "field_types": {
        "发现时间": "datetime",
        "整改时限": "date",
        "风险等级": "enum:高|中|低",
    },
}

# 事故快报表字段
ACCIDENT_REPORT_SCHEMA = {
    "form_type": "accident_report",
    "required_fields": [
        "事故发生时间", "事故地点", "事故类型", "事故等级",
        "伤亡人数", "直接经济损失", "事故简述", "初步原因分析",
        "已采取措施", "报告人", "报告时间",
    ],
    "optional_fields": [
        "间接经济损失", "现场照片", "证人信息",
        "关联隐患编号", "处理进度",
    ],
    "field_types": {
        "事故等级": "enum:一般|较大|重大|特别重大",
        "伤亡人数": "integer",
        "直接经济损失": "decimal",
        "事故发生时间": "datetime",
        "报告时间": "datetime",
    },
}

# 巡检记录表字段
INSPECTION_RECORD_SCHEMA = {
    "form_type": "inspection_record",
    "required_fields": [
        "巡检日期", "巡检区域", "巡检人", "巡检内容",
        "发现问题", "处理措施", "复查人", "复查日期",
    ],
    "optional_fields": [
        "照片", "巡检时长", "天气情况", "备注",
    ],
}

# 培训记录表字段
TRAINING_RECORD_SCHEMA = {
    "form_type": "training_record",
    "required_fields": [
        "培训日期", "培训主题", "讲师", "参训人员",
        "参训人数", "培训内容", "考核结果",
    ],
    "optional_fields": [
        "培训时长", "培训照片", "签到表", "培训地点",
    ],
}

EHS_FORM_SCHEMAS = {
    "hazard_rectification": HAZARD_RECTIFICATION_SCHEMA,
    "accident_report": ACCIDENT_REPORT_SCHEMA,
    "inspection_record": INSPECTION_RECORD_SCHEMA,
    "training_record": TRAINING_RECORD_SCHEMA,
}


# ─── 2. 字段填充核心逻辑 ────────────────────────────────────────

def form_fill_ehs(
    form_type: str,
    source_material: str,
    constraints: Optional[dict] = None,
    existing_values: Optional[dict] = None,
) -> dict:
    """
    对安环模板进行字段级填充。

    对应方案第 8.2 节。

    Args:
        form_type: 表单类型（hazard_rectification / accident_report / ...）
        source_material: 源材料文本（巡检记录、事故描述等）
        constraints: 约束条件（如 no_fabrication=true）
        existing_values: 已有字段值（用于增量填充）

    Returns:
        {
            "filled_fields": [{"field": "...", "value": "...", "confidence": 0.95}],
            "missing_required": ["字段1", "字段2"],
            "needs_confirmation": ["字段3"],
        }
    """
    schema = EHS_FORM_SCHEMAS.get(form_type)
    if not schema:
        return {
            "ok": False,
            "error": f"Unknown form_type: {form_type}",
            "available_types": list(EHS_FORM_SCHEMAS.keys()),
        }

    no_fabrication = constraints.get("no_fabrication", True) if constraints else True
    existing = existing_values or {}

    filled_fields = []
    missing_required = []
    needs_confirmation = []

    # 处理必填字段
    for field in schema["required_fields"]:
        if field in existing and existing[field]:
            # 已有值，直接使用
            filled_fields.append({
                "field": field,
                "value": existing[field],
                "confidence": 1.0,
                "source": "existing",
            })
        else:
            # 从源材料中提取
            extracted = _extract_field_from_material(field, source_material, schema)

            if extracted["found"]:
                filled_fields.append({
                    "field": field,
                    "value": extracted["value"],
                    "confidence": extracted["confidence"],
                    "source": "extracted",
                })

                if extracted["confidence"] < 0.8:
                    needs_confirmation.append(field)
            else:
                missing_required.append(field)

    # 处理可选字段
    for field in schema.get("optional_fields", []):
        if field in existing and existing[field]:
            filled_fields.append({
                "field": field,
                "value": existing[field],
                "confidence": 1.0,
                "source": "existing",
            })
        else:
            extracted = _extract_field_from_material(field, source_material, schema)
            if extracted["found"] and extracted["confidence"] > 0.7:
                filled_fields.append({
                    "field": field,
                    "value": extracted["value"],
                    "confidence": extracted["confidence"],
                    "source": "extracted",
                })

    return {
        "ok": True,
        "form_type": form_type,
        "filled_fields": filled_fields,
        "missing_required": missing_required,
        "needs_confirmation": needs_confirmation,
        "fill_rate": _calculate_fill_rate(filled_fields, schema),
        "no_fabrication_mode": no_fabrication,
    }


# ─── 3. 字段提取辅助 ────────────────────────────────────────────

def _extract_field_from_material(
    field: str,
    material: str,
    schema: dict,
) -> dict:
    """
    从源材料中提取字段值。
    基于关键词匹配 + 规则。
    注：完整版应调用 LLM 进行精确提取。
    """
    # 关键词映射（中文字段名 → 文本中可能的表达方式）
    keyword_map = {
        "发现时间":   ["发现时间", "发现于", "检查时间", "巡检时间"],
        "事故等级":   ["事故等级", "级别", "等级"],
        "伤亡人数":   ["伤亡", "受伤", "死亡", "伤亡人数"],
        "直接经济损失": ["直接经济损失", "损失", "经济损失"],
        "整改措施":   ["整改措施", "措施", "处理方案"],
        "责任人":     ["责任人", "负责", "责任"],
        "隐患位置":   ["隐患位置", "位置", "地点", "区域"],
        "整改时限":   ["整改时限", "时限", "限期", "期限"],
        "复查结论":   ["复查结论", "复查", "验收结论", "验收"],
        "复查人":     ["复查人", "复查", "验收人"],
        "发现人":     ["发现人", "发现", "检查人"],
        "巡检人":     ["巡检人", "巡检", "检查人"],
        "复查日期":   ["复查日期", "复查时间", "验收日期"],
        "培训主题":   ["培训主题", "主题", "培训内容"],
        "参训人数":   ["参训人数", "人数", "参加人数"],
    }

    keywords = keyword_map.get(field, [field])
    found_value = ""
    confidence = 0.0

    # 简单关键词匹配
    for kw in keywords:
        if kw in material:
            # 粗略提取：取关键词后的 30 个字符
            idx = material.index(kw)
            extracted = material[idx:idx + 60].strip()
            # 尝试提取冒号后的值
            if "：" in extracted:
                found_value = extracted.split("：", 1)[1].split("。")[0].strip()[:40]
            elif ":" in extracted:
                found_value = extracted.split(":", 1)[1].split(".")[0].strip()[:40]
            else:
                found_value = extracted[len(kw):].split("。")[0].strip()[:40]
            confidence = 0.75
            break

    return {
        "found": bool(found_value),
        "value": found_value,
        "confidence": confidence,
    }


def _calculate_fill_rate(filled_fields: list, schema: dict) -> float:
    """计算填充率 = 已填必填 / 总必填。"""
    required_count = len(schema["required_fields"])
    if required_count == 0:
        return 1.0
    filled_required = sum(
        1 for f in filled_fields if f["field"] in schema["required_fields"]
    )
    return round(filled_required / required_count, 2)
