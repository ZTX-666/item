from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from pydantic import BaseModel, Field

from ..config import settings
from ..models import ToolFile, ToolResult
from ..tasks import new_task_id, record_task_event, task_dir, write_json


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _load_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def _hash_key(*parts: str | None) -> str:
    text = "|".join(_normalize_text(part).lower() for part in parts if part)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


def _db_path() -> Path:
    path = settings.safety_database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_safety_schema() -> Path:
    db_path = _db_path()
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS source_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT UNIQUE,
                chat TEXT,
                sender TEXT,
                sent_at TEXT,
                text TEXT,
                attachments_json TEXT NOT NULL DEFAULT '[]',
                raw_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS source_vlm_detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT,
                task_id TEXT,
                image_path TEXT,
                label TEXT,
                confidence REAL,
                bbox_json TEXT NOT NULL DEFAULT '{}',
                raw_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS source_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE,
                source_type TEXT,
                extracted_text TEXT,
                summary TEXT,
                classification_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ai_classifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL,
                source_id TEXT,
                is_safety_related INTEGER NOT NULL,
                scene TEXT,
                risk_level TEXT,
                category TEXT,
                confidence REAL,
                recommended_action TEXT,
                template_ids_json TEXT NOT NULL DEFAULT '[]',
                entities_json TEXT NOT NULL DEFAULT '{}',
                raw_text TEXT,
                raw_payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS safety_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_key TEXT UNIQUE NOT NULL,
                status TEXT NOT NULL DEFAULT 'candidate',
                source_type TEXT,
                source_id TEXT,
                scene TEXT,
                risk_level TEXT,
                area TEXT,
                contractor TEXT,
                description TEXT,
                recommended_action TEXT,
                template_ids_json TEXT NOT NULL DEFAULT '[]',
                classification_id INTEGER,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                evidence_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(classification_id) REFERENCES ai_classifications(id)
            );

            CREATE TABLE IF NOT EXISTS evidence_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER,
                source_type TEXT,
                source_id TEXT,
                path TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'file',
                created_at TEXT NOT NULL,
                FOREIGN KEY(case_id) REFERENCES safety_cases(id)
            );

            CREATE TABLE IF NOT EXISTS form_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER,
                template_id TEXT,
                status TEXT NOT NULL DEFAULT 'suggested',
                output_path TEXT,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY(case_id) REFERENCES safety_cases(id)
            );

            CREATE TABLE IF NOT EXISTS classification_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                classification_id INTEGER,
                case_id INTEGER,
                corrected_scene TEXT,
                corrected_risk_level TEXT,
                corrected_status TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(classification_id) REFERENCES ai_classifications(id),
                FOREIGN KEY(case_id) REFERENCES safety_cases(id)
            );

            CREATE INDEX IF NOT EXISTS idx_ai_classifications_source ON ai_classifications(source_type, source_id);
            CREATE INDEX IF NOT EXISTS idx_safety_cases_status ON safety_cases(status);
            CREATE INDEX IF NOT EXISTS idx_safety_cases_scene_area ON safety_cases(scene, area);
            CREATE INDEX IF NOT EXISTS idx_evidence_files_case ON evidence_files(case_id);
            """
        )
    return db_path


class SafetyDatabaseInitRequest(BaseModel):
    reset: bool = False


class AIArchiveClassifyRequest(BaseModel):
    source_type: str = Field(default="manual_input")
    source_id: str | None = None
    time: str | None = None
    area: str | None = None
    contractor: str | None = None
    description: str | None = None
    text: str | None = None
    evidence_files: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    persist: bool = True
    create_case: bool = True


class ChatHazardIngestRequest(BaseModel):
    messages: list[dict[str, Any]] = Field(default_factory=list)
    q: str | None = None
    chat: str | None = None
    limit: int = Field(default=50, ge=1, le=500)
    persist: bool = True


class VlmHazardIngestRequest(BaseModel):
    detections: dict[str, Any] | None = None
    vlm_result_path: str | None = None
    task_id: str | None = None
    image_path: str | None = None
    area: str | None = None
    contractor: str | None = None
    persist: bool = True


class HazardDedupeRequest(BaseModel):
    case_id: int | None = None
    status: str | None = None
    limit: int = Field(default=50, ge=1, le=500)


class SafetyActionConnectRequest(BaseModel):
    case_id: int | None = None
    status: str = "candidate"
    create_form_suggestions: bool = True
    limit: int = Field(default=20, ge=1, le=200)


class ClassificationFeedbackRequest(BaseModel):
    classification_id: int | None = None
    case_id: int | None = None
    corrected_scene: str | None = None
    corrected_risk_level: str | None = None
    corrected_status: str | None = None
    notes: str | None = None


SCENE_RULES: list[dict[str, Any]] = [
    {
        "category": "incident",
        "scene": "安全事件/近危事件",
        "risk_level": "high",
        "templates": ["T014", "T015", "T016", "T017", "T019"],
        "action": "draft_incident_or_stop_work_record",
        "keywords": ["工伤", "工傷", "意外", "事故", "近危", "受伤", "受傷", "停工"],
    },
    {
        "category": "edge_protection",
        "scene": "临边洞口防护隐患",
        "risk_level": "high",
        "templates": ["T006", "T015", "T118"],
        "action": "create_rectification_task",
        "keywords": ["临边", "臨邊", "洞口", "护栏", "護欄", "栏杆", "欄杆", "高处", "高處", "坠落", "墮", "被拆", "未盖", "未蓋"],
    },
    {
        "category": "lifting",
        "scene": "吊运/起重作业风险",
        "risk_level": "high",
        "templates": ["T037", "T043", "T048", "T050", "T057"],
        "action": "run_lifting_operation_checker",
        "keywords": ["吊运", "吊運", "吊机", "吊機", "起重", "天秤", "crane", "mobile_crane", "tower_crane"],
    },
    {
        "category": "electrical",
        "scene": "临时用电/配电箱隐患",
        "risk_level": "high",
        "templates": ["T073", "T074"],
        "action": "run_electrical_box_precheck",
        "keywords": ["配电", "配電", "电箱", "電箱", "漏电", "漏電", "接地", "电线", "電線"],
    },
    {
        "category": "ppe",
        "scene": "PPE 穿戴违规",
        "risk_level": "medium",
        "templates": ["T006", "T118", "T129"],
        "action": "create_ppe_rectification_record",
        "keywords": ["安全帽", "反光衣", "ppe", "NO-Hardhat", "NO-Safety Vest", "NO-Mask", "no helmet", "no vest"],
    },
    {
        "category": "fire_dangerous_goods",
        "scene": "消防/危险品/充电隐患",
        "risk_level": "medium",
        "templates": ["T062", "T063", "T065"],
        "action": "create_fire_or_dangerous_goods_check",
        "keywords": ["危险品", "危險品", "消防", "灭火", "滅火", "火警", "充电", "充電", "烟", "煙"],
    },
    {
        "category": "scaffold",
        "scene": "棚架/临时支架作业风险",
        "risk_level": "high",
        "templates": ["T097", "T099", "T101"],
        "action": "create_high_risk_work_check",
        "keywords": ["棚架", "支架", "红架", "紅架", "scaffold"],
    },
    {
        "category": "confined_space",
        "scene": "密闭空间作业风险",
        "risk_level": "high",
        "templates": ["T103", "T104", "T105", "T106", "T107"],
        "action": "create_confined_space_check",
        "keywords": ["密闭", "密閉", "有限空间", "有限空間", "氧气", "氧氣"],
    },
    {
        "category": "heat_stress",
        "scene": "热应激/工友健康风险",
        "risk_level": "high",
        "templates": ["T150", "T151", "T155", "T158", "T159"],
        "action": "run_heat_stress_health_check",
        "keywords": ["中暑", "暑热", "暑熱", "高温", "高溫", "不适", "不適", "头晕", "頭暈", "65岁", "65歲"],
    },
    {
        "category": "rectification",
        "scene": "一般隐患整改",
        "risk_level": "medium",
        "templates": ["T005", "T006", "T007"],
        "action": "create_rectification_task",
        "keywords": ["隐患", "隱患", "整改", "改善", "巡查", "检查", "檢查", "必须整改", "必須整改"],
    },
]


def _classify_text(text: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    metadata = metadata or {}
    haystack = f"{text}\n{_json(metadata)}"
    matches: list[dict[str, Any]] = []
    for rule in SCENE_RULES:
        score = 0
        matched_keywords = []
        for keyword in rule["keywords"]:
            if keyword.lower() in haystack.lower():
                score += 1
                matched_keywords.append(keyword)
        if score:
            matches.append({**rule, "score": score, "matched_keywords": matched_keywords})

    if not matches:
        return {
            "is_safety_related": False,
            "scene": "未识别为安全事项",
            "risk_level": "low",
            "category": "general",
            "confidence": 0.25,
            "recommended_action": "archive_only",
            "template_ids": [],
            "matched_keywords": [],
            "entities": _extract_entities(text, metadata),
        }

    best = sorted(matches, key=lambda item: (item["score"], item["risk_level"] == "high"), reverse=True)[0]
    confidence = min(0.95, 0.55 + best["score"] * 0.12)
    return {
        "is_safety_related": True,
        "scene": best["scene"],
        "risk_level": best["risk_level"],
        "category": best["category"],
        "confidence": confidence,
        "recommended_action": best["action"],
        "template_ids": best["templates"],
        "matched_keywords": best["matched_keywords"],
        "entities": _extract_entities(text, metadata),
    }


def _extract_entities(text: str, metadata: dict[str, Any]) -> dict[str, Any]:
    entities: dict[str, Any] = {}
    for key in ["area", "contractor", "sender", "chat", "image_path"]:
        if metadata.get(key):
            entities[key] = metadata[key]

    area_match = re.search(r"([A-Z]?\d+区|[A-Z]?\d+區|[A-Z]\d+|[一二三四五六七八九十\d]+号楼|[一二三四五六七八九十\d]+號樓)", text)
    if area_match and not entities.get("area"):
        entities["area"] = area_match.group(1)

    deadline_match = re.search(r"(今天|今日|明天|明日|本周|本週|下周|下週|\d{1,2}[/-]\d{1,2}|\d{4}[/-]\d{1,2}[/-]\d{1,2})", text)
    if deadline_match:
        entities["deadline"] = deadline_match.group(1)

    return entities


def _persist_classification(req: AIArchiveClassifyRequest, classification: dict[str, Any]) -> dict[str, Any]:
    ensure_safety_schema()
    text = _normalize_text(req.text or req.description)
    source_id = req.source_id or _hash_key(req.source_type, text, _json(req.raw_payload))
    created = _now()
    raw_payload = {**req.raw_payload, "metadata": req.metadata}

    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO ai_classifications (
                source_type, source_id, is_safety_related, scene, risk_level, category,
                confidence, recommended_action, template_ids_json, entities_json,
                raw_text, raw_payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                req.source_type,
                source_id,
                1 if classification["is_safety_related"] else 0,
                classification["scene"],
                classification["risk_level"],
                classification["category"],
                classification["confidence"],
                classification["recommended_action"],
                _json(classification["template_ids"]),
                _json(classification["entities"]),
                text,
                _json(raw_payload),
                created,
            ),
        )
        classification_id = int(cur.lastrowid)
        case_id = None

        if req.create_case and classification["is_safety_related"]:
            case_id = _upsert_case(conn, req, classification, source_id, classification_id)

        for path in req.evidence_files:
            if case_id:
                conn.execute(
                    """
                    INSERT INTO evidence_files (case_id, source_type, source_id, path, kind, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (case_id, req.source_type, source_id, path, _evidence_kind(path), created),
                )

    return {"classification_id": classification_id, "case_id": case_id, "source_id": source_id}


def _upsert_case(
    conn: sqlite3.Connection,
    req: AIArchiveClassifyRequest,
    classification: dict[str, Any],
    source_id: str,
    classification_id: int,
) -> int:
    text = _normalize_text(req.description or req.text)
    area = req.area or classification["entities"].get("area")
    contractor = req.contractor or classification["entities"].get("contractor")
    case_key = _hash_key(classification["category"], classification["scene"], area, contractor, text[:120])
    seen_at = req.time or _now()
    evidence = list(req.evidence_files)
    now = _now()

    row = conn.execute("SELECT id, evidence_json FROM safety_cases WHERE case_key = ?", (case_key,)).fetchone()
    if row:
        existing_evidence = json.loads(row["evidence_json"] or "[]")
        merged_evidence = sorted(set(existing_evidence + evidence))
        conn.execute(
            """
            UPDATE safety_cases
            SET last_seen_at = ?, updated_at = ?, evidence_json = ?, classification_id = ?
            WHERE id = ?
            """,
            (seen_at, now, _json(merged_evidence), classification_id, row["id"]),
        )
        return int(row["id"])

    cur = conn.execute(
        """
        INSERT INTO safety_cases (
            case_key, status, source_type, source_id, scene, risk_level, area,
            contractor, description, recommended_action, template_ids_json,
            classification_id, first_seen_at, last_seen_at, evidence_json,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            case_key,
            "candidate",
            req.source_type,
            source_id,
            classification["scene"],
            classification["risk_level"],
            area,
            contractor,
            text,
            classification["recommended_action"],
            _json(classification["template_ids"]),
            classification_id,
            seen_at,
            seen_at,
            _json(evidence),
            now,
            now,
        ),
    )
    return int(cur.lastrowid)


def _evidence_kind(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}:
        return "image"
    if suffix in {".mp4", ".mov", ".avi", ".mkv"}:
        return "video"
    if suffix in {".doc", ".docx", ".pdf", ".xls", ".xlsx"}:
        return "document"
    return "file"


def init_safety_database(req: SafetyDatabaseInitRequest) -> ToolResult:
    task_id = new_task_id("safety_db")
    record_task_event(task_id, {"tool": "init_safety_database", "status": "running"})
    try:
        if req.reset and _db_path().exists():
            _db_path().unlink()
        db_path = ensure_safety_schema()
    except Exception as exc:
        record_task_event(task_id, {"tool": "init_safety_database", "status": "failed", "error": str(exc)})
        return ToolResult(ok=False, tool="init_safety_database", task_id=task_id, summary="安全数据库初始化失败。", error=str(exc))

    record_task_event(task_id, {"tool": "init_safety_database", "status": "done", "db_path": str(db_path)})
    return ToolResult(
        ok=True,
        tool="init_safety_database",
        task_id=task_id,
        summary="安全数据库已初始化。",
        files=[ToolFile(path=str(db_path), name=db_path.name, kind="database", mime_type="application/x-sqlite3")],
        data={"db_path": str(db_path)},
    )


def ai_archive_classifier(req: AIArchiveClassifyRequest) -> ToolResult:
    task_id = new_task_id("ai_archive")
    text = _normalize_text(req.text or req.description or "")
    metadata = {**req.metadata, "area": req.area, "contractor": req.contractor}
    record_task_event(task_id, {"tool": "ai_archive_classifier", "status": "running", "source_type": req.source_type})

    classification = _classify_text(text, metadata)
    persistence: dict[str, Any] = {}
    if req.persist:
        persistence = _persist_classification(req, classification)

    payload = {"classification": classification, "persistence": persistence}
    out_path = task_dir(task_id) / "classification.json"
    write_json(out_path, payload)
    record_task_event(task_id, {"tool": "ai_archive_classifier", "status": "done", **persistence})

    summary = "识别为安全相关事项。" if classification["is_safety_related"] else "未识别为安全相关事项，仅归档分类。"
    return ToolResult(
        ok=True,
        tool="ai_archive_classifier",
        task_id=task_id,
        summary=f"{summary} 场景：{classification['scene']}，风险：{classification['risk_level']}。",
        files=[ToolFile(path=str(out_path), name=out_path.name, kind="json", mime_type="application/json")],
        data=payload,
    )


def ingest_chat_hazards(req: ChatHazardIngestRequest) -> ToolResult:
    task_id = new_task_id("chat_hazards")
    record_task_event(task_id, {"tool": "ingest_chat_hazards", "status": "running"})
    ensure_safety_schema()

    messages = list(req.messages)
    if not messages and req.q:
        params: dict[str, Any] = {"q": req.q, "limit": req.limit}
        if req.chat:
            params["chat"] = req.chat
        try:
            resp = requests.get(f"{settings.whatsapp_archive_base_url.rstrip('/')}/api/messages/search", params=params, timeout=20)
            resp.raise_for_status()
            payload = resp.json()
            messages = payload.get("rows", []) or payload.get("messages", [])
        except requests.RequestException as exc:
            record_task_event(task_id, {"tool": "ingest_chat_hazards", "status": "failed", "error": str(exc)})
            return ToolResult(ok=False, tool="ingest_chat_hazards", task_id=task_id, summary="聊天记录读取失败。", error=str(exc))

    results = []
    for message in messages:
        source_id = str(message.get("id") or message.get("message_id") or _hash_key(_json(message)))
        text = _normalize_text(str(message.get("text") or message.get("body") or message.get("content") or ""))
        attachments = message.get("attachments") or message.get("media") or []
        if isinstance(attachments, str):
            attachments = [attachments]
        with _connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO source_messages (
                    source_id, chat, sender, sent_at, text, attachments_json, raw_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    message.get("chat") or message.get("chat_name") or message.get("jid"),
                    message.get("sender") or message.get("from"),
                    message.get("time") or message.get("timestamp") or message.get("sent_at"),
                    text,
                    _json(attachments),
                    _json(message),
                    _now(),
                ),
            )
        classify_req = AIArchiveClassifyRequest(
            source_type="chat_message",
            source_id=source_id,
            time=message.get("time") or message.get("timestamp") or message.get("sent_at"),
            area=message.get("area"),
            contractor=message.get("contractor"),
            text=text,
            evidence_files=[str(item) for item in attachments],
            metadata={
                "chat": message.get("chat") or message.get("chat_name") or message.get("jid"),
                "sender": message.get("sender") or message.get("from"),
            },
            raw_payload=message,
            persist=req.persist,
        )
        classification = _classify_text(text, classify_req.metadata)
        persistence = _persist_classification(classify_req, classification) if req.persist else {}
        results.append({"source_id": source_id, "classification": classification, "persistence": persistence})

    out_path = task_dir(task_id) / "chat_hazards.json"
    write_json(out_path, {"messages": results})
    safety_count = sum(1 for item in results if item["classification"]["is_safety_related"])
    record_task_event(task_id, {"tool": "ingest_chat_hazards", "status": "done", "count": len(results), "safety_count": safety_count})
    return ToolResult(
        ok=True,
        tool="ingest_chat_hazards",
        task_id=task_id,
        summary=f"聊天记录归类完成，共处理 {len(results)} 条，识别安全相关 {safety_count} 条。",
        files=[ToolFile(path=str(out_path), name=out_path.name, kind="json", mime_type="application/json")],
        data={"results": results, "safety_count": safety_count},
    )


def _iter_vlm_images(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(payload.get("images"), list):
        return payload["images"]
    if isinstance(payload.get("detections"), dict) and isinstance(payload["detections"].get("images"), list):
        return payload["detections"]["images"]
    if isinstance(payload.get("data"), dict):
        return _iter_vlm_images(payload["data"])
    return [{"image": payload.get("image") or payload.get("source"), "detections": payload.get("detections", [])}]


def ingest_vlm_hazards(req: VlmHazardIngestRequest) -> ToolResult:
    task_id = new_task_id("vlm_hazards")
    record_task_event(task_id, {"tool": "ingest_vlm_hazards", "status": "running"})
    ensure_safety_schema()

    payload = req.detections or {}
    if req.vlm_result_path:
        payload = _load_json_file(Path(req.vlm_result_path))

    results = []
    for image in _iter_vlm_images(payload):
        image_path = str(req.image_path or image.get("image") or image.get("source") or "")
        detections = image.get("detections") or image.get("objects") or []
        labels = []
        evidence = [image_path] if image_path else []
        for idx, det in enumerate(detections):
            label = str(det.get("class_name") or det.get("label") or det.get("name") or det.get("class") or "")
            labels.append(label)
            source_id = str(det.get("id") or _hash_key(req.task_id, image_path, label, str(idx), _json(det)))
            with _connect() as conn:
                conn.execute(
                    """
                    INSERT INTO source_vlm_detections (
                        source_id, task_id, image_path, label, confidence, bbox_json, raw_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_id,
                        req.task_id,
                        image_path,
                        label,
                        det.get("confidence"),
                        _json(det.get("bbox") or det.get("xyxy") or det.get("box") or {}),
                        _json(det),
                        _now(),
                    ),
                )

        text = f"VLM Detection image={image_path} labels={' '.join(labels)}"
        classify_req = AIArchiveClassifyRequest(
            source_type="vlm_detection",
            source_id=str(image.get("source_id") or _hash_key(req.task_id, image_path, " ".join(labels))),
            area=req.area,
            contractor=req.contractor,
            text=text,
            evidence_files=evidence,
            metadata={"image_path": image_path, "labels": labels, "task_id": req.task_id},
            raw_payload=image,
            persist=req.persist,
        )
        classification = _classify_text(text, classify_req.metadata)
        # Machinery + person in the same frame is worth reviewing even if PPE keywords are absent.
        lower_labels = " ".join(labels).lower()
        if "person" in lower_labels and any(item in lower_labels for item in ["crane", "excavator", "dump_truck", "bulldozer", "loader"]):
            classification.update(
                {
                    "is_safety_related": True,
                    "scene": "人员与机械混行/接近机械",
                    "risk_level": "high",
                    "category": "plant_person_interface",
                    "recommended_action": "create_visual_hazard_review",
                    "template_ids": sorted(set(classification.get("template_ids", []) + ["T006", "T118"])),
                    "confidence": max(float(classification.get("confidence", 0.0)), 0.72),
                }
            )
        persistence = _persist_classification(classify_req, classification) if req.persist else {}
        results.append({"image_path": image_path, "labels": labels, "classification": classification, "persistence": persistence})

    out_path = task_dir(task_id) / "vlm_hazards.json"
    write_json(out_path, {"images": results})
    safety_count = sum(1 for item in results if item["classification"]["is_safety_related"])
    record_task_event(task_id, {"tool": "ingest_vlm_hazards", "status": "done", "count": len(results), "safety_count": safety_count})
    return ToolResult(
        ok=True,
        tool="ingest_vlm_hazards",
        task_id=task_id,
        summary=f"VLM 隐患归类完成，共处理 {len(results)} 张图片，识别安全相关 {safety_count} 条。",
        files=[ToolFile(path=str(out_path), name=out_path.name, kind="json", mime_type="application/json")],
        data={"results": results, "safety_count": safety_count},
    )


def dedupe_and_link_hazards(req: HazardDedupeRequest) -> ToolResult:
    task_id = new_task_id("hazard_dedupe")
    record_task_event(task_id, {"tool": "dedupe_and_link_hazards", "status": "running"})
    ensure_safety_schema()

    params: list[Any] = []
    query = "SELECT * FROM safety_cases WHERE 1=1"
    if req.case_id is not None:
        query += " AND id = ?"
        params.append(req.case_id)
    if req.status:
        query += " AND status = ?"
        params.append(req.status)
    query += " ORDER BY updated_at DESC LIMIT ?"
    params.append(req.limit)

    with _connect() as conn:
        rows = [dict(row) for row in conn.execute(query, params).fetchall()]
        groups: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            key = _hash_key(row.get("scene"), row.get("area"), row.get("contractor"))
            groups.setdefault(key, []).append(row)

        duplicate_groups = [items for items in groups.values() if len(items) > 1]
        for items in duplicate_groups:
            keeper = items[0]
            duplicate_ids = [item["id"] for item in items[1:]]
            evidence = []
            for item in items:
                evidence.extend(json.loads(item.get("evidence_json") or "[]"))
            conn.execute(
                "UPDATE safety_cases SET evidence_json = ?, updated_at = ? WHERE id = ?",
                (_json(sorted(set(evidence))), _now(), keeper["id"]),
            )
            for duplicate_id in duplicate_ids:
                conn.execute(
                    "UPDATE safety_cases SET status = ?, updated_at = ? WHERE id = ?",
                    (f"duplicate_of_{keeper['id']}", _now(), duplicate_id),
                )

    out_path = task_dir(task_id) / "dedupe_report.json"
    write_json(out_path, {"checked": rows, "duplicate_groups": duplicate_groups})
    record_task_event(task_id, {"tool": "dedupe_and_link_hazards", "status": "done", "duplicate_groups": len(duplicate_groups)})
    return ToolResult(
        ok=True,
        tool="dedupe_and_link_hazards",
        task_id=task_id,
        summary=f"隐患去重完成，发现 {len(duplicate_groups)} 组潜在重复记录。",
        files=[ToolFile(path=str(out_path), name=out_path.name, kind="json", mime_type="application/json")],
        data={"duplicate_groups": duplicate_groups},
    )


def connect_hazard_actions(req: SafetyActionConnectRequest) -> ToolResult:
    task_id = new_task_id("hazard_actions")
    record_task_event(task_id, {"tool": "connect_hazard_actions", "status": "running"})
    ensure_safety_schema()

    params: list[Any] = []
    query = "SELECT * FROM safety_cases WHERE 1=1"
    if req.case_id is not None:
        query += " AND id = ?"
        params.append(req.case_id)
    else:
        query += " AND status = ?"
        params.append(req.status)
    query += " ORDER BY updated_at DESC LIMIT ?"
    params.append(req.limit)

    actions = []
    with _connect() as conn:
        cases = [dict(row) for row in conn.execute(query, params).fetchall()]
        for case in cases:
            template_ids = json.loads(case.get("template_ids_json") or "[]")
            recommended = {
                "case_id": case["id"],
                "scene": case["scene"],
                "risk_level": case["risk_level"],
                "recommended_action": case["recommended_action"],
                "template_ids": template_ids,
                "next_steps": _next_steps(case, template_ids),
            }
            if req.create_form_suggestions:
                for template_id in template_ids:
                    conn.execute(
                        """
                        INSERT INTO form_records (case_id, template_id, status, payload_json, created_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (case["id"], template_id, "suggested", _json({"source": "connect_hazard_actions"}), _now()),
                    )
            actions.append(recommended)

    out_path = task_dir(task_id) / "hazard_actions.json"
    write_json(out_path, {"actions": actions})
    record_task_event(task_id, {"tool": "connect_hazard_actions", "status": "done", "count": len(actions)})
    return ToolResult(
        ok=True,
        tool="connect_hazard_actions",
        task_id=task_id,
        summary=f"已为 {len(actions)} 条隐患生成后续动作建议。",
        files=[ToolFile(path=str(out_path), name=out_path.name, kind="json", mime_type="application/json")],
        data={"actions": actions},
    )


def _next_steps(case: dict[str, Any], template_ids: list[str]) -> list[str]:
    steps = ["人工确认隐患是否成立，并补充分判商、责任人和整改期限。"]
    if case.get("risk_level") == "high":
        steps.append("高风险事项建议立即通知安全主任/地盘经理。")
    if template_ids:
        steps.append(f"建议预生成表格：{', '.join(template_ids)}。")
    action = case.get("recommended_action") or ""
    if "stop_work" in action:
        steps.append("停工整改命令只生成草稿，必须人工审批后发送。")
    if "lifting" in action:
        steps.append("核对吊运人员委任、设备证书、吊具检查和现场警戒。")
    if "electrical" in action:
        steps.append("核对配电箱入场资料、漏电保护、接地、标签和门锁。")
    return steps


def record_classification_feedback(req: ClassificationFeedbackRequest) -> ToolResult:
    task_id = new_task_id("hazard_feedback")
    record_task_event(task_id, {"tool": "record_classification_feedback", "status": "running"})
    ensure_safety_schema()

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO classification_feedback (
                classification_id, case_id, corrected_scene, corrected_risk_level,
                corrected_status, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                req.classification_id,
                req.case_id,
                req.corrected_scene,
                req.corrected_risk_level,
                req.corrected_status,
                req.notes,
                _now(),
            ),
        )
        if req.case_id and req.corrected_status:
            conn.execute("UPDATE safety_cases SET status = ?, updated_at = ? WHERE id = ?", (req.corrected_status, _now(), req.case_id))

    record_task_event(task_id, {"tool": "record_classification_feedback", "status": "done"})
    return ToolResult(
        ok=True,
        tool="record_classification_feedback",
        task_id=task_id,
        summary="人工确认/修正结果已记录。",
        data=req.model_dump(),
    )
