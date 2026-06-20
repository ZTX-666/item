"""
tools/docmate_docx.py — DocMate .docx 工具入口（FastAPI ToolSpec）

按《DocMate EHS docx升级与Skill落地实施方案 v1》第 6 节 API 契约实现。

4 个端点：
1. docmate_read_docx          — 解析 .docx 获取结构化索引
2. docmate_generate_changeset — LLM 生成变更命令
3. docmate_preview_changeset  — 预览变更卡片
4. docmate_apply_changeset    — 应用变更到 .docx
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from ..models import ToolSpec
from ..docx_parser import parse_docx
from ..docx_executor import apply_changeset, create_backup, revert_changeset
from ..docx_diff import generate_preview_cards, get_batch_suggestions, generate_changeset_summary
from ..docx_model import (
    DocumentChange,
    ChangeTarget,
    ChangeSet,
    ChangeSetSummary,
    ChangeType,
    ChangeStatus,
    RiskLevel,
    generate_change_id,
    generate_changeset_id,
    validate_llm_response,
)
from ..ehs_rules import enforce_ehs_rules
from ..ehs_skills import (
    clarify_intent_ehs,
    form_fill_ehs,
    style_guard_ehs,
    consistency_guard_ehs,
    risk_gate_ehs,
    SKILL_REGISTRY,
)

logger = logging.getLogger(__name__)

# ─── 1. 请求模型 ────────────────────────────────────────────────

class ReadDocxRequest(BaseModel):
    file_path: str = Field(..., description=".docx 文件路径")


class GenerateChangesetRequest(BaseModel):
    doc_id: str = Field(..., description="文档 ID（来自 docmate_read_docx）")
    instruction: str = Field(..., description="用户自然语言编辑指令")
    context: Optional[dict] = Field(default=None, description="额外上下文（selected_text, form_type 等）")


class PreviewChangesetRequest(BaseModel):
    changeset_id: str = Field(..., description="ChangeSet ID")


class ApplyChangesetRequest(BaseModel):
    changeset_id: str = Field(..., description="ChangeSet ID")
    accepted_change_ids: list[str] = Field(default_factory=list, description="接受的变更 ID 列表")
    save_as: str = Field(..., description="输出文件路径")


# ─── 2. 全局状态（临时存储，生产环境应替换为数据库）─────────────

# doc_id → DocumentStructure
_doc_store: dict[str, Any] = {}

# doc_id → source_path
_doc_paths: dict[str, str] = {}

# changeset_id → ChangeSet
_changeset_store: dict[str, ChangeSet] = {}


# ─── 3. 工具端点实现 ────────────────────────────────────────────

async def tool_docmate_read_docx(request: ReadDocxRequest) -> dict:
    """
    端点 1: docmate_read_docx

    解析 .docx 文件，返回结构化文档模型。
    对应方案第 6.1 节。
    """
    file_path = request.file_path
    path = Path(file_path)

    if not path.exists():
        return {
            "ok": False,
            "error": f"File not found: {file_path}",
            "error_code": "DOCX_001_PARSE_FAILED",
        }

    if path.suffix.lower() not in (".docx",):
        return {
            "ok": False,
            "error": f"Unsupported file type: {path.suffix}. Only .docx is supported.",
            "error_code": "DOCX_001_PARSE_FAILED",
        }

    try:
        structure = parse_docx(str(path))
    except Exception as e:
        logger.exception("Failed to parse docx")
        return {
            "ok": False,
            "error": f"Parse failed: {e}",
            "error_code": "DOCX_001_PARSE_FAILED",
        }

    _doc_store[structure.doc_id] = structure
    _doc_paths[structure.doc_id] = str(path)

    return {
        "ok": True,
        "data": {
            "doc_id": structure.doc_id,
            "source_path": str(path),
            "structure": structure.to_dict(),
            "stats": {
                "paragraph_count": len(structure.paragraphs),
                "table_count": len(structure.tables),
                "image_count": len(structure.images),
            },
        },
    }


async def tool_docmate_generate_changeset(request: GenerateChangesetRequest) -> dict:
    """
    端点 2: docmate_generate_changeset

    根据用户指令生成 ChangeSet。
    对应方案第 6.2 节。

    流程：
    1. Skill Pipeline（澄清 → 表单填充 → 风格规范 → 一致性 → 风险闸门）
    2. LLM 生成变更命令
    3. ChangeSet 入库
    """
    # 获取文档结构
    structure = _doc_store.get(request.doc_id)
    if not structure:
        return {
            "ok": False,
            "error": f"Document not found: {request.doc_id}. Call docmate_read_docx first.",
            "error_code": "DOCX_001_PARSE_FAILED",
        }

    instruction = request.instruction
    context = request.context or {}

    # ── Step 1: Skill Pipeline ─────────────────────────────────

    # Skill 1: 意图澄清
    clarify_result = clarify_intent_ehs(
        instruction=instruction,
        doc_outline=[p.text[:60] for p in structure.paragraphs if p.style == "Heading1"],
        selected_text=context.get("selected_text"),
        form_type=context.get("form_type", ""),
    )
    if clarify_result.get("action") == "clarify":
        return {
            "ok": True,
            "data": {
                "action": "clarify",
                "questions": clarify_result["questions"],
            },
        }

    # Skill 2: 表单填充（如果指定了 form_type）
    form_type = context.get("form_type", "")
    form_fill_result = None
    skills_output = {}
    if form_type:
        form_fill_result = form_fill_ehs(
            form_type=form_type,
            source_material=await _build_source_material(structure),
            constraints={"no_fabrication": True},
        )
        skills_output["form_fill"] = form_fill_result

    # Skill 3: 风格规范
    relevant_text = _build_context_for_llm(structure, instruction)
    style_result = style_guard_ehs(relevant_text)
    skills_output["style_guard"] = style_result

    # ── Step 2: LLM 生成变更命令 ───────────────────────────────
    # 此处在实际部署时会调用 LLM API
    # 现在用本地规则生成 mock 结构以供测试

    changes = await _call_llm_for_changes(
        structure=structure,
        instruction=instruction,
        context=context,
        skills_output=skills_output,
    )

    # 如果 LLM 需要澄清
    if isinstance(changes, dict) and changes.get("action") == "clarify":
        return {
            "ok": True,
            "data": changes,
        }

    # Skill 4: 一致性检查
    consistency_result = consistency_guard_ehs(
        filled_fields=form_fill_result.get("filled_fields", []) if form_fill_result else [],
        changes=[c.to_dict() if hasattr(c, "to_dict") else c for c in changes]
    )
    skills_output["consistency_guard"] = consistency_result

    # Skill 5: 风险闸门
    risk_result = risk_gate_ehs(
        [c.to_dict() if hasattr(c, "to_dict") else c for c in changes]
    )
    skills_output["risk_gate"] = risk_result

    # ── Step 3: EHS 规则执行 ───────────────────────────────────
    changes_dicts = [c.to_dict() if hasattr(c, "to_dict") else c for c in changes]
    rule_results = enforce_ehs_rules(changes_dicts)

    # ── Step 4: 构建 ChangeSet ─────────────────────────────────
    changeset = ChangeSet(
        changeset_id=generate_changeset_id(),
        doc_id=request.doc_id,
        source_path=_doc_paths.get(request.doc_id, ""),
    )

    for i, chg in enumerate(changes):
        if isinstance(chg, DocumentChange):
            changeset.add_change(chg)
        else:
            changeset.add_change(DocumentChange(
                change_id=generate_change_id(),
                change_type=ChangeType(chg.get("change_type", "text_replace")),
                target=ChangeTarget(**chg.get("target", {})),
                old_content=chg.get("old_content", ""),
                new_content=chg.get("new_content", ""),
                reason=chg.get("reason", ""),
                risk_level=RiskLevel(chg.get("risk_level", "low")),
                confidence=chg.get("confidence", 0.0),
                image_path=chg.get("image_path", ""),
                table_rows=chg.get("table_rows", 0),
                table_cols=chg.get("table_cols", 0),
                table_data=chg.get("table_data"),
            ))

    _changeset_store[changeset.changeset_id] = changeset

    # 生成预览
    preview = generate_changeset_summary(changeset)

    return {
        "ok": True,
        "data": {
            "changeset_id": changeset.changeset_id,
            "changes": [c.to_dict() for c in changeset.changes],
            "summary": changeset.summary.to_dict(),
            "preview_cards": preview["preview_cards"],
            "batch_suggestions": preview["batch_suggestions"],
            "skills_output": skills_output,
            "ehs_rules": rule_results,
            "risk_gate": risk_result,
        },
    }


async def tool_docmate_preview_changeset(request: PreviewChangesetRequest) -> dict:
    """
    端点 3: docmate_preview_changeset

    预览 ChangeSet 的所有变更卡片。
    对应方案第 6.3 节。
    """
    changeset = _changeset_store.get(request.changeset_id)
    if not changeset:
        return {
            "ok": False,
            "error": f"ChangeSet not found: {request.changeset_id}",
            "error_code": "DOCX_002_ANCHOR_NOT_FOUND",
        }

    preview = generate_changeset_summary(changeset)

    return {
        "ok": True,
        "data": {
            "changeset_id": changeset.changeset_id,
            "preview_cards": preview["preview_cards"],
            "batch_suggestions": preview["batch_suggestions"],
            "summary": changeset.summary.to_dict(),
        },
    }


async def tool_docmate_apply_changeset(request: ApplyChangesetRequest) -> dict:
    """
    端点 4: docmate_apply_changeset

    接受/拒绝变更并应用到 .docx 文件。
    对应方案第 6.4 节。
    """
    changeset = _changeset_store.get(request.changeset_id)
    if not changeset:
        return {
            "ok": False,
            "error": f"ChangeSet not found: {request.changeset_id}",
            "error_code": "DOCX_002_ANCHOR_NOT_FOUND",
        }

    # 标记接受/拒绝
    accepted_ids = set(request.accepted_change_ids)
    for chg in changeset.changes:
        if chg.status == ChangeStatus.PENDING:
            if chg.change_id in accepted_ids:
                chg.status = ChangeStatus.ACCEPTED
            else:
                chg.status = ChangeStatus.REJECTED

    # 创建备份
    source_path = _doc_paths.get(changeset.doc_id, changeset.source_path)
    backup_path = create_backup(source_path)

    # 执行变更
    result = apply_changeset(
        changeset=changeset,
        output_path=request.save_as,
    )

    return {
        "ok": result["ok"],
        "data": {
            "output_path": request.save_as,
            "applied": result.get("data", {}).get("applied", 0),
            "rejected": result.get("data", {}).get("rejected", 0),
            "errors": result.get("data", {}).get("errors", []),
            "backup_path": backup_path,
        },
    }


# ─── 4. LLM 调用接口（占位）─────────────────────────────────────

async def _call_llm_for_changes(
    structure: Any,
    instruction: str,
    context: dict,
    skills_output: dict,
) -> list:
    """
    调用 LLM 生成变更命令。

    实际部署时替换为 OpenAI/Claude API 调用。
    现在返回基于规则的简单变更列表用于测试。
    """
    # 构建 System Prompt（方案第 7.1 节）
    system_prompt = _build_system_prompt()

    # 构建 User Prompt（含结构化上下文）
    user_prompt = _build_user_prompt(structure, instruction, context, skills_output)

    logger.info(f"[LLM] System: {system_prompt[:100]}...")
    logger.info(f"[LLM] User: {user_prompt[:200]}...")

    # === TODO: 替换为真实 LLM 调用 ===
    # response = await openai.ChatCompletion.create(
    #     model="gpt-4o",
    #     messages=[
    #         {"role": "system", "content": system_prompt},
    #         {"role": "user", "content": user_prompt},
    #     ],
    #     response_format={"type": "json_object"},
    # )
    # result = json.loads(response.choices[0].message.content)

    # 临时：返回基于规则的 mock 变更
    return _mock_changes_from_instruction(structure, instruction)


def _mock_changes_from_instruction(structure: Any, instruction: str) -> list:
    """
    Mock 变更生成器（用于本地测试，无需 LLM API）。
    生产环境需替换为真实 LLM 调用。
    """
    changes = []

    # 简单的关键词匹配 → 生成对应的变更
    if "风险等级" in instruction:
        for keyword in ("高风险", "中风险", "低风险"):
            if keyword in instruction:
                # 找到第一个包含"风险"的段落
                for p in structure.paragraphs:
                    if "风险" in p.text:
                        old_level = "中风险" if "中风险" in p.text else (
                            "高风险" if "高风险" in p.text else "低风险"
                        )
                        changes.append(DocumentChange(
                            change_id=generate_change_id(),
                            change_type=ChangeType.TEXT_REPLACE,
                            target=ChangeTarget(paragraph_id=p.paragraph_id),
                            old_content=f"风险等级：{old_level}" if old_level in p.text else p.text[:30],
                            new_content=f"风险等级：{keyword}",
                            reason="用户指令：调整风险等级",
                            risk_level=RiskLevel.HIGH if keyword == "高风险" else RiskLevel.MEDIUM,
                            confidence=0.9,
                        ))
                        return changes

    if "整改时限" in instruction or "限期" in instruction:
        import re
        days = re.search(r"(\d+)\s*天", instruction)
        if days:
            days_val = days.group(1)
            for p in structure.paragraphs:
                if "整改时限" in p.text or "限期" in p.text:
                    changes.append(DocumentChange(
                        change_id=generate_change_id(),
                        change_type=ChangeType.TEXT_REPLACE,
                        target=ChangeTarget(paragraph_id=p.paragraph_id),
                        old_content=p.text[:50],
                        new_content=p.text.replace(
                            "整改时限", f"整改时限：{days_val}天"
                        ) if "整改时限" in p.text else p.text,
                        reason=f"用户指令：整改时限改为 {days_val} 天",
                        risk_level=RiskLevel.LOW,
                        confidence=0.95,
                    ))
                    return changes

    if "加一张" in instruction or "插入图片" in instruction or "加图片" in instruction:
        import re
        img_keyword = "图片"
        img_match = re.search(r"加一张[「「](.+?)[」」]", instruction)
        if img_match:
            img_keyword = img_match.group(1)

        for p in structure.paragraphs:
            if len(p.text) > 20:
                changes.append(DocumentChange(
                    change_id=generate_change_id(),
                    change_type=ChangeType.IMAGE_INSERT,
                    target=ChangeTarget(anchor=p.paragraph_id),
                    old_content="",
                    new_content=f"[图片] {img_keyword}",
                    reason=f"用户指令：插入图片「{img_keyword}」",
                    risk_level=RiskLevel.LOW,
                    confidence=0.8,
                    image_path="",  # 由本地图片索引填充
                ))
                return changes

    if "表格" in instruction or "加表" in instruction:
        for p in structure.paragraphs:
            if "整改" in p.text or "检查" in p.text:
                changes.append(DocumentChange(
                    change_id=generate_change_id(),
                    change_type=ChangeType.TABLE_INSERT,
                    target=ChangeTarget(paragraph_id=p.paragraph_id),
                    old_content="",
                    new_content="[表格 3行×3列]",
                    reason="用户指令：插入表格",
                    risk_level=RiskLevel.LOW,
                    confidence=0.8,
                    table_rows=3,
                    table_cols=3,
                    table_data=[["项次", "内容", "状态"], ["1", "待填", ""], ["2", "待填", ""]],
                ))
                return changes

    # 兜底：返回澄清请求
    return {"action": "clarify", "clarify_questions": [
        "未能在文档中找到与指令匹配的内容。请确认修改目标段落或提供更具体的指引。"
    ]}


# ─── 5. Prompt 构建 ─────────────────────────────────────────────

def _build_system_prompt() -> str:
    """构建 System Prompt（方案第 7.1 节）。"""
    return """你是安环(EHS)文稿编辑助手。你只能根据用户输入事实进行改写、结构化补全和合规检查。
禁止编造事故事实、责任主体、时间地点、损失数据。
你必须输出严格 JSON，不得输出解释性文本。
每条变更必须包含：change_type、target、old_content、new_content、reason、risk_level。
当关键信息不足时，输出 action=clarify，并给出最小追问列表。"""


def _build_user_prompt(
    structure: Any,
    instruction: str,
    context: dict,
    skills_output: dict,
) -> str:
    """构建 User Prompt（含结构化文档上下文 + 技能输出）。"""
    # 获取相关上下文
    doc_context = structure.get_context_for_llm(instruction, max_paragraphs=15)

    # 构建 prompt
    parts = []

    parts.append("=== 文档结构 ===")
    parts.append(json.dumps(doc_context, ensure_ascii=False, indent=2))

    parts.append("\n=== 用户指令 ===")
    parts.append(instruction)

    if context.get("selected_text"):
        parts.append(f"\n=== 用户选中文本 ===")
        parts.append(context["selected_text"])

    if context.get("form_type"):
        parts.append(f"\n=== 表单类型 ===")
        parts.append(context["form_type"])

    if skills_output:
        parts.append(f"\n=== 技能预检结果 ===")
        parts.append(json.dumps({
            k: v for k, v in skills_output.items()
            if isinstance(v, dict) and not isinstance(v.get("normalized_text"), str)
        }, ensure_ascii=False, indent=2))

    return "\n".join(parts)


async def _build_source_material(structure: Any) -> str:
    """从文档结构中提取源材料文本。"""
    texts = []
    for p in structure.paragraphs[:30]:
        if p.text:
            texts.append(p.text)
    return "\n".join(texts)


def _build_context_for_llm(structure: Any, instruction: str) -> str:
    """提取与指令相关的关联文本。"""
    texts = []
    keywords = instruction.replace("，", " ").replace("、", " ").split()
    for p in structure.paragraphs:
        if any(kw in p.text for kw in keywords if len(kw) >= 2):
            texts.append(p.text)
    if not texts:
        texts = [p.text for p in structure.paragraphs[:5] if p.text]
    return "\n".join(texts[:10])


# ─── 6. ToolSpec 注册 ──────────────────────────────────────────

DOCMATE_READ_DOCX_SPEC = ToolSpec(
    name="docmate_read_docx",
    description="解析 .docx 文件，返回结构化文档索引（段落/表格/图片），用于后续编辑操作。",
    input_schema={
        "type": "object",
        "required": ["file_path"],
        "properties": {
            "file_path": {
                "type": "string",
                "description": ".docx 文件的绝对路径",
            },
        },
    },
)

DOCMATE_GENERATE_CHANGESET_SPEC = ToolSpec(
    name="docmate_generate_changeset",
    description="根据自然语言指令生成 .docx 文档的结构化变更集（ChangeSet）。支持文字替换、表格操作、图片插入。",
    input_schema={
        "type": "object",
        "required": ["doc_id", "instruction"],
        "properties": {
            "doc_id": {
                "type": "string",
                "description": "文档 ID（来自 docmate_read_docx 返回值）",
            },
            "instruction": {
                "type": "string",
                "description": "用户的自然语言编辑指令",
            },
            "context": {
                "type": "object",
                "description": "额外上下文（selected_text, form_type 等）",
                "properties": {
                    "selected_text": {"type": "string"},
                    "form_type": {"type": "string"},
                },
            },
        },
    },
)

DOCMATE_PREVIEW_CHANGESET_SPEC = ToolSpec(
    name="docmate_preview_changeset",
    description="预览变更集的每一条变更卡片，展示 old/new 对比和风险级别。",
    input_schema={
        "type": "object",
        "required": ["changeset_id"],
        "properties": {
            "changeset_id": {
                "type": "string",
                "description": "ChangeSet ID",
            },
        },
    },
)

DOCMATE_APPLY_CHANGESET_SPEC = ToolSpec(
    name="docmate_apply_changeset",
    description="将已确认的变更应用到 .docx 文件并保存。自动创建备份。",
    input_schema={
        "type": "object",
        "required": ["changeset_id", "accepted_change_ids", "save_as"],
        "properties": {
            "changeset_id": {
                "type": "string",
                "description": "ChangeSet ID",
            },
            "accepted_change_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "用户接受的变更 ID 列表",
            },
            "save_as": {
                "type": "string",
                "description": "输出 .docx 文件路径",
            },
        },
    },
)

DOCMATE_TOOL_ROUTES = {
    "docmate_read_docx":           ("/tools/docmate_read_docx",           tool_docmate_read_docx),
    "docmate_generate_changeset":  ("/tools/docmate_generate_changeset",  tool_docmate_generate_changeset),
    "docmate_preview_changeset":   ("/tools/docmate_preview_changeset",   tool_docmate_preview_changeset),
    "docmate_apply_changeset":     ("/tools/docmate_apply_changeset",     tool_docmate_apply_changeset),
}

ALL_DOCMATE_SPECS = [
    DOCMATE_READ_DOCX_SPEC,
    DOCMATE_GENERATE_CHANGESET_SPEC,
    DOCMATE_PREVIEW_CHANGESET_SPEC,
    DOCMATE_APPLY_CHANGESET_SPEC,
]
