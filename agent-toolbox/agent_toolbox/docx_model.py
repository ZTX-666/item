"""
docx_model.py — 文档结构模型 + ChangeSet 数据结构 + Schema 校验

按《DocMate EHS docx升级与Skill落地实施方案 v1》第 5 节契约实现。
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

# ─── 1. 变更类型枚举 ────────────────────────────────────────────

class ChangeType(str, Enum):
    TEXT_REPLACE      = "text_replace"
    TEXT_INSERT       = "text_insert"
    TEXT_DELETE       = "text_delete"
    TABLE_CELL_UPDATE = "table_cell_update"
    TABLE_INSERT      = "table_insert"
    IMAGE_INSERT      = "image_insert"
    IMAGE_REPLACE     = "image_replace"


class ChangeStatus(str, Enum):
    PENDING   = "pending"
    ACCEPTED  = "accepted"
    REJECTED  = "rejected"
    REVERTED  = "reverted"


class RiskLevel(str, Enum):
    HIGH   = "high"
    MEDIUM = "medium"
    LOW    = "low"


class ActionType(str, Enum):
    GENERATE_CHANGES = "generate_changes"
    CLARIFY          = "clarify"


# ─── 2. Run 模型（段落内文字片段）────────────────────────────────

@dataclass
class RunModel:
    """段落内的一个文字片段（run），携带格式信息。"""
    run_id: str
    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    font_name: str = ""
    font_size: int = 12
    color: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ─── 3. 段落模型 ────────────────────────────────────────────────

@dataclass
class ParagraphModel:
    """一个段落的锚点模型。paragraph_id 为 hash 锚点（如 P12#a13f）。"""
    paragraph_id: str
    index: int          # 1‑based 段落序号
    text: str
    style: str = "Normal"
    runs: list[RunModel] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["runs"] = [r.to_dict() for r in self.runs]
        return d


# ─── 4. 表格单元格模型 ──────────────────────────────────────────

@dataclass
class TableCellModel:
    row: int
    col: int
    text: str
    bold: bool = False
    alignment: str = "left"

    def to_dict(self) -> dict:
        return asdict(self)


# ─── 5. 表格模型 ────────────────────────────────────────────────

@dataclass
class TableModel:
    table_id: str       # e.g. "T2"
    index: int          # 1‑based 表格序号
    rows: int
    cols: int
    cells: list[TableCellModel] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["cells"] = [c.to_dict() for c in self.cells]
        return d


# ─── 6. 图片模型 ────────────────────────────────────────────────

@dataclass
class ImageModel:
    image_id: str               # e.g. "IMG3"
    index: int                  # 1‑based 图片序号
    anchor_paragraph_id: str    # 锚定段落 ID
    name: str                   # 文件名
    width_px: int = 640
    height_px: int = 360
    image_path: str = ""        # 本地文件路径

    def to_dict(self) -> dict:
        return asdict(self)


# ─── 7. 文档结构模型（顶层）─────────────────────────────────────

@dataclass
class DocumentStructure:
    """
    对应方案第 5.1 节 JSON。
    """
    doc_id: str
    source_path: str
    paragraphs: list[ParagraphModel] = field(default_factory=list)
    tables: list[TableModel] = field(default_factory=list)
    images: list[ImageModel] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "source_path": self.source_path,
            "paragraphs": [p.to_dict() for p in self.paragraphs],
            "tables": [t.to_dict() for t in self.tables],
            "images": [i.to_dict() for i in self.images],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def find_paragraph(self, paragraph_id: str) -> Optional[ParagraphModel]:
        for p in self.paragraphs:
            if p.paragraph_id == paragraph_id:
                return p
        return None

    def find_table(self, table_id: str) -> Optional[TableModel]:
        for t in self.tables:
            if t.table_id == table_id:
                return t
        return None

    def get_context_for_llm(self, instruction: str, max_paragraphs: int = 20) -> dict:
        """提取与指令相关的上下文，发送给 LLM（减少 token 消耗）。"""
        # 简单实现：返回前 max_paragraphs 个段落 + 所有表格列表
        relevant_paragraphs = self.paragraphs[:max_paragraphs]
        return {
            "doc_id": self.doc_id,
            "paragraphs": [p.to_dict() for p in relevant_paragraphs],
            "table_count": len(self.tables),
            "tables_summary": [
                {"table_id": t.table_id, "rows": t.rows, "cols": t.cols}
                for t in self.tables
            ],
            "image_count": len(self.images),
            "total_paragraphs": len(self.paragraphs),
        }


# ─── 8. 变更命令模型（单条变更）──────────────────────────────────

@dataclass
class ChangeTarget:
    """变更定位目标"""
    paragraph_id: Optional[str] = None
    table_id: Optional[str] = None
    cell: Optional[dict] = None       # {"row": 1, "col": 2}
    anchor: Optional[str] = None      # image_insert 时的锚点段落 ID

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class DocumentChange:
    """
    对应方案第 5.2 节 JSON。
    """
    change_id: str
    change_type: ChangeType
    target: ChangeTarget
    old_content: str = ""
    new_content: str = ""
    reason: str = ""
    risk_level: RiskLevel = RiskLevel.LOW
    confidence: float = 0.0
    status: ChangeStatus = ChangeStatus.PENDING

    # 表格专用字段
    table_rows: int = 0
    table_cols: int = 0
    table_data: Optional[list[list[str]]] = None

    # 图片专用字段
    image_path: str = ""
    image_width_px: int = 640

    def to_dict(self) -> dict:
        d = {
            "change_id": self.change_id,
            "change_type": self.change_type.value,
            "target": self.target.to_dict(),
            "old_content": self.old_content,
            "new_content": self.new_content,
            "reason": self.reason,
            "risk_level": self.risk_level.value,
            "confidence": self.confidence,
            "status": self.status.value,
        }
        # 表格专用
        if self.change_type in (ChangeType.TABLE_INSERT,):
            d["table_rows"] = self.table_rows
            d["table_cols"] = self.table_cols
            if self.table_data:
                d["table_data"] = self.table_data
        # 图片专用
        if self.change_type in (ChangeType.IMAGE_INSERT, ChangeType.IMAGE_REPLACE):
            d["image_path"] = self.image_path
            d["image_width_px"] = self.image_width_px
        return d


# ─── 9. ChangeSet 模型（多条变更聚合）───────────────────────────

@dataclass
class ChangeSetSummary:
    total: int = 0
    high_risk: int = 0
    medium_risk: int = 0
    low_risk: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ChangeSet:
    """
    对应方案第 5.3 节 JSON。
    """
    changeset_id: str
    doc_id: str
    source_path: str = ""
    created_at: str = ""
    changes: list[DocumentChange] = field(default_factory=list)
    summary: ChangeSetSummary = field(default_factory=ChangeSetSummary)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def add_change(self, change: DocumentChange):
        self.changes.append(change)
        self._recalc_summary()

    def _recalc_summary(self):
        high = 0; med = 0; low = 0
        for c in self.changes:
            if c.risk_level == RiskLevel.HIGH: high += 1
            elif c.risk_level == RiskLevel.MEDIUM: med += 1
            else: low += 1
        self.summary = ChangeSetSummary(
            total=len(self.changes),
            high_risk=high,
            medium_risk=med,
            low_risk=low,
        )

    def get_pending_changes(self) -> list[DocumentChange]:
        return [c for c in self.changes if c.status == ChangeStatus.PENDING]

    def get_accepted_changes(self) -> list[DocumentChange]:
        return [c for c in self.changes if c.status == ChangeStatus.ACCEPTED]

    def to_dict(self) -> dict:
        return {
            "changeset_id": self.changeset_id,
            "doc_id": self.doc_id,
            "source_path": self.source_path,
            "created_at": self.created_at,
            "changes": [c.to_dict() for c in self.changes],
            "summary": self.summary.to_dict(),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# ─── 10. 预览卡片模型 ──────────────────────────────────────────

@dataclass
class PreviewCard:
    """对应方案第 6.3 节的预览卡片。"""
    change_id: str
    title: str
    old_content: str
    new_content: str
    risk_level: str
    location: str = ""
    reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ─── 11. 工具辅助函数 ──────────────────────────────────────────

def make_hash_id(prefix: str, index: int, text: str) -> str:
    """生成段落/表格的唯一 hash 锚点。例如 'P12#a13f'"""
    short_hash = hashlib.md5(text.encode()).hexdigest()[:4]
    return f"{prefix}{index}#{short_hash}"


def generate_change_id() -> str:
    """生成变更 ID：chg_uuid8"""
    return f"chg_{uuid.uuid4().hex[:8]}"


def generate_changeset_id() -> str:
    """生成 ChangeSet ID：cs_YYYYMMDD_uuid6"""
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"cs_{date_str}_{uuid.uuid4().hex[:6]}"


# ─── 12. Schema 校验（对应方案第 7.2 节）────────────────────────

LLM_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["action"],
    "properties": {
        "action": {
            "type": "string",
            "enum": ["generate_changes", "clarify"],
        },
        "clarify_questions": {
            "type": "array",
            "items": {"type": "string"},
        },
        "changes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "change_type", "target", "old_content",
                    "new_content", "reason", "risk_level"
                ],
                "properties": {
                    "change_type": {
                        "type": "string",
                        "enum": [
                            "text_replace", "text_insert", "text_delete",
                            "table_cell_update", "table_insert",
                            "image_insert", "image_replace",
                        ],
                    },
                    "target": {
                        "type": "object",
                        "properties": {
                            "paragraph_id": {"type": "string"},
                            "table_id": {"type": "string"},
                            "cell": {
                                "type": "object",
                                "properties": {
                                    "row": {"type": "integer"},
                                    "col": {"type": "integer"},
                                },
                            },
                            "anchor": {"type": "string"},
                        },
                    },
                    "old_content": {"type": "string"},
                    "new_content": {
                        "oneOf": [
                            {"type": "string"},
                            {
                                "type": "object",
                                "properties": {
                                    "image_path": {"type": "string"},
                                    "image_keyword": {"type": "string"},
                                    "width_px": {"type": "integer"},
                                },
                            },
                        ],
                    },
                    "reason": {"type": "string"},
                    "risk_level": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                    },
                },
            },
        },
    },
}

VALID_CHANGE_TYPES = frozenset([
    "text_replace", "text_insert", "text_delete",
    "table_cell_update", "table_insert",
    "image_insert", "image_replace",
])


def validate_llm_response(data: dict) -> tuple[bool, str]:
    """
    校验 LLM 返回的 JSON 是否符合契约。
    返回 (valid, error_message)
    """
    if not isinstance(data, dict):
        return False, "Response must be a JSON object"
    if "action" not in data:
        return False, "Missing required field 'action'"

    action = data.get("action")
    if action not in ("generate_changes", "clarify"):
        return False, f"Invalid action: {action}"

    if action == "clarify":
        questions = data.get("clarify_questions", [])
        if not isinstance(questions, list):
            return False, "clarify_questions must be an array"
        return True, ""

    if action == "generate_changes":
        changes = data.get("changes", [])
        if not isinstance(changes, list):
            return False, "changes must be an array"

        for i, chg in enumerate(changes):
            if not isinstance(chg, dict):
                return False, f"changes[{i}] must be an object"

            # 检查必填字段
            required_fields = [
                "change_type", "target", "old_content",
                "new_content", "reason", "risk_level",
            ]
            for field in required_fields:
                if field not in chg:
                    return False, f"changes[{i}] missing required field '{field}'"

            # 校验 change_type
            if chg["change_type"] not in VALID_CHANGE_TYPES:
                return False, f"changes[{i}] invalid change_type: {chg['change_type']}"

            # 校验 risk_level
            if chg["risk_level"] not in ("high", "medium", "low"):
                return False, f"changes[{i}] invalid risk_level: {chg['risk_level']}"

        return True, ""


def validate_create(validator_func):
    """装饰器：对 LLM 响应执行验证后进行后续处理。"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            if isinstance(result, dict):
                valid, error = validator_func(result)
                if not valid:
                    return {"ok": False, "error": f"Schema validation failed: {error}"}
            return {"ok": True, "data": result}
        return wrapper
    return decorator
