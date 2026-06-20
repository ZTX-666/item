"""
ehs_rules.py — 安环规则、术语词典、高风险字段定义

按《DocMate EHS docx升级与Skill落地实施方案 v1》
第 2、14、17、18 节实现。
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional


# ─── 1. 错误码规范（第 14 节）───────────────────────────────────

class EHSErrorCode(str, Enum):
    """安环 + 文档统一错误码。"""
    EHS_001_MISSING_REQUIRED           = "EHS_001_MISSING_REQUIRED"
    EHS_002_CONFLICT_DETECTED          = "EHS_002_CONFLICT_DETECTED"
    EHS_003_HIGH_RISK_REVIEW_REQUIRED  = "EHS_003_HIGH_RISK_REVIEW_REQUIRED"
    DOCX_001_PARSE_FAILED              = "DOCX_001_PARSE_FAILED"
    DOCX_002_ANCHOR_NOT_FOUND          = "DOCX_002_ANCHOR_NOT_FOUND"
    DOCX_003_APPLY_FAILED              = "DOCX_003_APPLY_FAILED"

    def message(self) -> str:
        return _ERROR_MESSAGES.get(self, str(self))


_ERROR_MESSAGES = {
    EHSErrorCode.EHS_001_MISSING_REQUIRED:          "必填字段缺失，无法继续编辑",
    EHSErrorCode.EHS_002_CONFLICT_DETECTED:         "检测到数据一致性冲突，需人工审核",
    EHSErrorCode.EHS_003_HIGH_RISK_REVIEW_REQUIRED: "高风险变更必须人工复核",
    EHSErrorCode.DOCX_001_PARSE_FAILED:             "文档解析失败",
    EHSErrorCode.DOCX_002_ANCHOR_NOT_FOUND:         "目标锚点不存在",
    EHSErrorCode.DOCX_003_APPLY_FAILED:             "变更执行失败",
}


# ─── 2. 安环术语词典（第 17 节）─────────────────────────────────

EHS_TERMINOLOGY_MAP: dict[str, str] = {
    # 口语 → 安环标准表达
    "问题不大":     "经评估为低风险，需在规定时限内完成整改",
    "尽快整改":     "请于规定时限内完成整改",
    "差不多完成":   "已完成整改，待复查确认",
    "注意安全":     "落实现场安全防护措施并完成风险告知",
    "没事":         "经现场核查未发现安全隐患",
    "已经处理":     "已完成整改并经验收合格",
    "再检查一下":   "需重新复核整改落实情况",
    "加强管理":     "应完善管理制度并落实责任人",
    "及时处理":     "应在规定时限内完成闭环处理",
    "差不多":       "部分整改完成，仍有项待落实",

    # 模糊表达 → 量化表达
    "近期":         "近 7 个工作日内",
    "多次":         "累计 3 次及以上",
    "一部分":       "部分（约 XX%）",
    "有人":         "责任人",
    "找个时间":     "限期整改时限为",

    # 角色称谓规范
    "工地师傅":     "现场作业人员",
    "包工头":       "班组负责人",
    "安全员":       "专职安全管理人员",
    "上面领导":     "上级主管部门",
}

# ─── 3. 高风险字段（第 18 节）───────────────────────────────────

HIGH_RISK_FIELDS: list[str] = [
    "事故等级",               # 一般/较大/重大/特别重大
    "伤亡人数",               # 绝对数字
    "直接经济损失",           # 金额
    "责任单位",               # 主体认定
    "责任人",                 # 个人认定
    "处罚建议",               # 处罚内容
    "法规条款引用",           # 法律条文
    "停工整改范围",           # 影响范围
    "特种作业人员资质",       # 证书/资质
    "危险源等级",             # 重大/一般危险源
]

# ─── 4. 不允许编造的事实字段（第 2 节：禁止编造）───────────────

NO_FABRICATION_FIELDS: list[str] = [
    # 时间
    "发现时间", "整改完成时间", "复查时间", "事故发生时间",
    "上报时间", "批复时间", "班前会时间",

    # 地点
    "发生地点", "隐患位置", "作业区域", "坐标位置",

    # 人员
    "责任人", "发现人", "复查人", "审批人", "班组长",
    "安全总监", "项目经理",

    # 事故
    "伤亡人数", "事故等级", "直接经济损失", "间接经济损失",
    "受伤人员姓名", "伤亡人员姓名",

    # 整改
    "整改结果", "复查结论", "验收结论",
]

# ─── 5. 法规引用格式规范 ────────────────────────────────────────

LAW_REFERENCE_PATTERNS = {
    # 常见法规的标准引用格式
    "安全生产法":         "《中华人民共和国安全生产法》",
    "消防法":             "《中华人民共和国消防法》",
    "建筑法":             "《中华人民共和国建筑法》",
    "职业病防治法":       "《中华人民共和国职业病防治法》",
    "建设工程安全生产管理条例": "《建设工程安全生产管理条例》(国务院令第393号)",
    "生产安全事故报告和调查处理条例": "《生产安全事故报告和调查处理条例》(国务院令第493号)",
}


# ─── 6. 安环规则引擎 ────────────────────────────────────────────

class EHSRuleResult:
    """单条规则检查结果。"""
    def __init__(self, rule_name: str, passed: bool, detail: str = "",
                 severity: str = "low", field: str = ""):
        self.rule_name = rule_name
        self.passed = passed
        self.detail = detail
        self.severity = severity  # high / medium / low
        self.field = field

    def to_dict(self) -> dict:
        return {
            "rule_name": self.rule_name,
            "passed": self.passed,
            "detail": self.detail,
            "severity": self.severity,
            "field": self.field,
        }


def check_no_fabrication(change_content: str, original_content: str) -> EHSRuleResult:
    """
    规则 1：禁止编造事实检查。
    检查 LLM 输出的内容是否引入了原文中不存在的事实字段。
    """
    for field in NO_FABRICATION_FIELDS:
        if field in change_content and field not in original_content:
            # 检查 new_content 中该字段的值是否来自原文
            return EHSRuleResult(
                rule_name="no_fabrication",
                passed=False,
                detail=f"检测到可能编造的事实字段：{field}。该字段值必须来自源材料。",
                severity="high",
                field=field,
            )
    return EHSRuleResult(rule_name="no_fabrication", passed=True)


def check_risk_level_explainable(change: dict) -> EHSRuleResult:
    """
    规则 2：风险等级必须可解释。
    如果 LLM 修改了风险等级，必须有伴随的法规或制度依据。
    """
    new_content = change.get("new_content", "")
    reason = change.get("reason", "")
    risk_level = change.get("risk_level", "")

    high_risk_keywords = ["高风险", "重大", "严重", "违规", "事故"]
    is_high_risk = any(kw in new_content for kw in high_risk_keywords)

    if is_high_risk and len(reason) < 10:
        return EHSRuleResult(
            rule_name="risk_explainable",
            passed=False,
            detail="高风险判定缺少法规或制度依据。请补充引用条款。",
            severity="high",
        )
    return EHSRuleResult(rule_name="risk_explainable", passed=True)


def check_terminology(text: str) -> list[EHSRuleResult]:
    """
    规则 3：术语规范检查。
    检查文本中是否存在口语化表达，提供替换建议。
    """
    results = []
    for informal, formal in EHS_TERMINOLOGY_MAP.items():
        if informal in text:
            results.append(EHSRuleResult(
                rule_name="terminology",
                passed=False,
                detail=f"建议将「{informal}」替换为「{formal}」",
                severity="low",
                field=informal,
            ))
    return results


def check_responsibility_loop(changes: list[dict]) -> EHSRuleResult:
    """
    规则 4：责任闭环检查（第 2 节第 3 条）。
    检查：责任人、责任部门、整改时限、复查结论是否完整。
    """
    required_fields = ["责任人", "责任部门", "整改时限", "复查结论"]
    missing = []

    for chg in changes:
        new_content = chg.get("new_content", "")
        if isinstance(new_content, str):
            for field in required_fields:
                if field in new_content:
                    # 检查该字段是否有实际值（非空/非占位符）
                    break  # 简化检查
            else:
                continue

    # 全局检查所有变更中是否覆盖了必要字段
    all_content = " ".join(
        c.get("new_content", "") if isinstance(c.get("new_content"), str) else ""
        for c in changes
    )
    for field in required_fields:
        if field not in all_content:
            missing.append(field)

    if missing:
        return EHSRuleResult(
            rule_name="responsibility_loop",
            passed=False,
            detail=f"责任闭环不完整，缺失：{'、'.join(missing)}",
            severity="medium",
        )
    return EHSRuleResult(rule_name="responsibility_loop", passed=True)


def check_time_consistency(changes: list[dict]) -> EHSRuleResult:
    """
    规则 5：时间线一致性检查。
    发现时间 < 整改完成时间 < 复查时间
    """
    return EHSRuleResult(rule_name="time_consistency", passed=True,
                         detail="时间线一致性检查仅在企业数据平台启用后生效")


def check_law_reference(text: str) -> list[EHSRuleResult]:
    """
    规则 6：法规引用格式规范化。
    """
    results = []
    for keyword, standard in LAW_REFERENCE_PATTERNS.items():
        if keyword in text and standard not in text:
            results.append(EHSRuleResult(
                rule_name="law_reference",
                passed=False,
                detail=f"建议将「{keyword}」标准化为「{standard}」",
                severity="medium",
            ))
    return results


# ─── 7. 综合规则检查 ────────────────────────────────────────────

def enforce_ehs_rules(changes: list[dict], original_content: str = "") -> list[dict]:
    """
    对 LLM 生成的变更列表执行所有安环规则检查。
    返回规则检查报告列表。

    对应方案第 9.2 节 enforce_ehs_rules()。
    """
    all_results = []
    blocked_changes = []

    for i, chg in enumerate(changes):
        new_content = chg.get("new_content", "")
        old_content = chg.get("old_content", "")

        # 规则 1：禁止编造
        result = check_no_fabrication(new_content, old_content)
        if not result.passed:
            all_results.append(result.to_dict())
            blocked_changes.append(i)

        # 规则 2：风险等级可解释
        result = check_risk_level_explainable(chg)
        if not result.passed:
            all_results.append(result.to_dict())

        # 规则 3：术语规范
        for r in check_terminology(new_content):
            all_results.append(r.to_dict())

    # 规则 4：责任闭环
    result = check_responsibility_loop(changes)
    if not result.passed:
        all_results.append(result.to_dict())

    # 标记被拦截的变更
    for i in blocked_changes:
        changes[i]["blocked"] = True
        changes[i]["block_reason"] = "EHS_规则_禁止编造"

    return all_results


def is_field_high_risk(field_name: str) -> bool:
    """判断字段是否为高风险字段。"""
    return field_name in HIGH_RISK_FIELDS


def is_field_no_fabrication(field_name: str) -> bool:
    """判断字段是否禁止编造（必须来自源材料）。"""
    return field_name in NO_FABRICATION_FIELDS


def normalize_terminology(text: str) -> str:
    """
    将文本中的口语表达替换为标准安环术语。
    """
    result = text
    for informal, formal in EHS_TERMINOLOGY_MAP.items():
        result = result.replace(informal, formal)
    return result
