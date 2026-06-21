from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field

from ..config import settings
from ..models import ToolResult, ToolSpec
from ..tasks import new_task_id, task_dir, write_json


class ScheduledJobCreateRequest(BaseModel):
    name: str
    job_type: str
    cron: str = "0 8 * * *"
    payload: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class ScheduledJobQueryRequest(BaseModel):
    enabled: bool | None = None
    job_type: str | None = None
    limit: int = Field(default=100, ge=1, le=500)


class ScheduledJobRunRequest(BaseModel):
    job_id: int
    triggered_by: str = "manual"


class ScheduledJobPauseRequest(BaseModel):
    job_id: int
    paused: bool = True


class JobRunRecordRequest(BaseModel):
    job_id: int | None = None
    job_name: str | None = None
    status: str = "ok"
    result: dict[str, Any] = Field(default_factory=dict)


class PlatformEventCreateRequest(BaseModel):
    event_type: str
    source_type: str
    source_id: str | None = None
    title: str
    summary: str | None = None
    risk_level: str = "medium"
    payload: dict[str, Any] = Field(default_factory=dict)


class PlatformEventQueryRequest(BaseModel):
    event_type: str | None = None
    source_type: str | None = None
    reviewed: bool | None = None
    limit: int = Field(default=100, ge=1, le=500)


class EventCaseLinkRequest(BaseModel):
    event_id: int
    case_id: int
    relation: str = "evidence"


class EventReviewedRequest(BaseModel):
    event_id: int
    reviewed: bool = True
    reviewer: str | None = None
    notes: str | None = None


class EventDedupeRequest(BaseModel):
    event_type: str | None = None
    limit: int = Field(default=200, ge=1, le=1000)


class ReviewTaskCreateRequest(BaseModel):
    title: str
    task_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    priority: str = "medium"
    assigned_to: str | None = None


class ReviewTaskQueryRequest(BaseModel):
    status: str | None = None
    assigned_to: str | None = None
    limit: int = Field(default=100, ge=1, le=500)


class ReviewTaskDecisionRequest(BaseModel):
    task_id: int
    reviewer: str | None = None
    notes: str | None = None


class ReviewToActionRequest(BaseModel):
    task_id: int
    action_type: str
    action_payload: dict[str, Any] = Field(default_factory=dict)


class ProjectProfileRequest(BaseModel):
    project_id: str = "default"
    name: str
    location: str | None = None
    contract_no: str | None = None
    client: str | None = None
    main_contractor: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectAreaRequest(BaseModel):
    area_id: str
    name: str
    project_id: str = "default"
    parent_area_id: str | None = None
    responsible_person: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContractorRequest(BaseModel):
    contractor_id: str
    name: str
    trade: str | None = None
    contact: str | None = None
    phone: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PersonnelRequest(BaseModel):
    person_id: str
    name: str
    role: str
    contractor_id: str | None = None
    phone: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectContextQueryRequest(BaseModel):
    project_id: str = "default"
    include_contractors: bool = True
    include_personnel: bool = True
    include_areas: bool = True


class EquipmentRecordRequest(BaseModel):
    equipment_id: str
    name: str
    equipment_type: str
    contractor_id: str | None = None
    area_id: str | None = None
    status: str = "active"
    metadata: dict[str, Any] = Field(default_factory=dict)


class CertificateRecordRequest(BaseModel):
    certificate_id: str
    certificate_type: str
    holder_id: str | None = None
    holder_name: str | None = None
    issue_date: str | None = None
    expiry_date: str | None = None
    file_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExpiringCertificateQueryRequest(BaseModel):
    within_days: int = Field(default=30, ge=0, le=3650)
    limit: int = Field(default=100, ge=1, le=500)


class CertificateEquipmentLinkRequest(BaseModel):
    certificate_id: str
    equipment_id: str


class CertificateExpiryNoticeRequest(BaseModel):
    certificate_id: str
    audience: str = "site_safety_team"


class ContractorScoreRequest(BaseModel):
    contractor_id: str
    period: str | None = None


class ContractorScorecardQueryRequest(BaseModel):
    contractor_id: str | None = None
    limit: int = Field(default=50, ge=1, le=500)


class ContractorScoreEventRequest(BaseModel):
    contractor_id: str
    points: int
    reason: str
    event_type: str = "penalty"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContractorReviewDraftRequest(BaseModel):
    contractor_id: str
    month: str | None = None


class MediaEvidenceRequest(BaseModel):
    path: str
    source_type: str = "manual"
    source_id: str | None = None
    case_id: int | None = None
    event_id: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MediaThumbnailRequest(BaseModel):
    media_id: int | None = None
    path: str | None = None


class MediaMetadataRequest(BaseModel):
    path: str


class MediaCaseLinkRequest(BaseModel):
    media_id: int
    case_id: int


class EvidenceBundleRequest(BaseModel):
    case_id: int


class ReportDraftRequest(BaseModel):
    project_id: str = "default"
    period: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class IncidentReportDraftRequest(BaseModel):
    case_id: int | None = None
    event_id: int | None = None
    description: str | None = None


class ReportPackageExportRequest(BaseModel):
    report_id: int | None = None
    case_id: int | None = None


class RfiDraftRequest(BaseModel):
    subject: str
    question: str
    project_id: str = "default"
    case_id: int | None = None
    priority: str = "normal"


class RfiQueryRequest(BaseModel):
    status: str | None = None
    project_id: str | None = None
    limit: int = Field(default=50, ge=1, le=500)


class SiteMemoDraftRequest(BaseModel):
    subject: str
    body: str
    project_id: str = "default"
    case_id: int | None = None


class SubmittalReviewDraftRequest(BaseModel):
    submittal_name: str
    review_notes: str
    project_id: str = "default"
    status: str = "draft"


class RfiCaseLinkRequest(BaseModel):
    rfi_id: int
    case_id: int


class LlmPayloadRiskRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)
    text: str | None = None


class LlmSanitizePayloadRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)
    text: str | None = None


class LlmJsonValidateRequest(BaseModel):
    text: str
    required_keys: list[str] = Field(default_factory=list)


class LlmRepairPromptRequest(BaseModel):
    bad_output: str
    error: str | None = None
    expected_schema: dict[str, Any] = Field(default_factory=dict)


class PromptVersionRecordRequest(BaseModel):
    name: str
    version: str
    content: str
    notes: str | None = None


def create_scheduled_job(req: ScheduledJobCreateRequest) -> ToolResult:
    _ensure_future_schema()
    now = _now()
    with _connect() as conn:
        cursor = conn.execute(
            """INSERT INTO scheduled_jobs (name, job_type, cron, payload_json, enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (req.name, req.job_type, req.cron, _json(req.payload), int(req.enabled), now, now),
        )
        job_id = int(cursor.lastrowid)
    return _ok("create_scheduled_job", f"Created scheduled job {job_id}.", {"job_id": job_id, **req.model_dump()})


def list_scheduled_jobs(req: ScheduledJobQueryRequest) -> ToolResult:
    rows = _select("scheduled_jobs", {"enabled": None if req.enabled is None else int(req.enabled), "job_type": req.job_type}, "id DESC", req.limit)
    return _ok("list_scheduled_jobs", f"Returned {len(rows)} scheduled jobs.", {"items": rows})


def run_scheduled_job_now(req: ScheduledJobRunRequest) -> ToolResult:
    record = record_job_run(JobRunRecordRequest(job_id=req.job_id, status="triggered", result={"triggered_by": req.triggered_by}))
    return _ok("run_scheduled_job_now", "Recorded manual scheduled job trigger.", record.data)


def pause_scheduled_job(req: ScheduledJobPauseRequest) -> ToolResult:
    _ensure_future_schema()
    with _connect() as conn:
        conn.execute("UPDATE scheduled_jobs SET enabled = ?, updated_at = ? WHERE id = ?", (0 if req.paused else 1, _now(), req.job_id))
    return _ok("pause_scheduled_job", f"Updated scheduled job {req.job_id}.", req.model_dump())


def record_job_run(req: JobRunRecordRequest) -> ToolResult:
    _ensure_future_schema()
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO job_runs (job_id, job_name, status, result_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (req.job_id, req.job_name, req.status, _json(req.result), _now()),
        )
    return _ok("record_job_run", "Recorded job run.", {"run_id": int(cursor.lastrowid)})


def create_platform_event(req: PlatformEventCreateRequest) -> ToolResult:
    _ensure_future_schema()
    key = _hash(req.event_type, req.source_type, req.source_id, req.title)
    now = _now()
    with _connect() as conn:
        cursor = conn.execute(
            """INSERT INTO platform_events (event_key, event_type, source_type, source_id, title, summary, risk_level, payload_json, reviewed, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            ON CONFLICT(event_key) DO UPDATE SET updated_at = excluded.updated_at
            RETURNING id""",
            (key, req.event_type, req.source_type, req.source_id, req.title, req.summary, req.risk_level, _json(req.payload), now, now),
        )
        event_id = int(cursor.fetchone()[0])
    return _ok("create_platform_event", f"Created or reused platform event {event_id}.", {"event_id": event_id, "event_key": key})


def query_platform_events(req: PlatformEventQueryRequest) -> ToolResult:
    rows = _select("platform_events", {"event_type": req.event_type, "source_type": req.source_type, "reviewed": None if req.reviewed is None else int(req.reviewed)}, "updated_at DESC", req.limit)
    return _ok("query_platform_events", f"Returned {len(rows)} platform events.", {"items": rows})


def link_event_to_case(req: EventCaseLinkRequest) -> ToolResult:
    _ensure_future_schema()
    with _connect() as conn:
        conn.execute("INSERT INTO event_case_links (event_id, case_id, relation, created_at) VALUES (?, ?, ?, ?)", (req.event_id, req.case_id, req.relation, _now()))
    return _ok("link_event_to_case", "Linked event to case.", req.model_dump())


def mark_event_reviewed(req: EventReviewedRequest) -> ToolResult:
    _ensure_future_schema()
    with _connect() as conn:
        conn.execute("UPDATE platform_events SET reviewed = ?, updated_at = ? WHERE id = ?", (int(req.reviewed), _now(), req.event_id))
        conn.execute("INSERT INTO review_audit (target_type, target_id, reviewer, decision, notes, created_at) VALUES ('event', ?, ?, ?, ?, ?)", (req.event_id, req.reviewer, "reviewed" if req.reviewed else "unreviewed", req.notes, _now()))
    return _ok("mark_event_reviewed", "Updated event review status.", req.model_dump())


def dedupe_platform_events(req: EventDedupeRequest) -> ToolResult:
    rows = _select("platform_events", {"event_type": req.event_type}, "updated_at DESC", req.limit)
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(_hash(row.get("event_type"), row.get("title"), row.get("source_type")), []).append(row)
    duplicates = [group for group in groups.values() if len(group) > 1]
    return _ok("dedupe_platform_events", f"Found {len(duplicates)} duplicate groups.", {"groups": duplicates})


def create_review_task(req: ReviewTaskCreateRequest) -> ToolResult:
    _ensure_future_schema()
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO review_tasks (title, task_type, payload_json, priority, assigned_to, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)",
            (req.title, req.task_type, _json(req.payload), req.priority, req.assigned_to, _now(), _now()),
        )
    return _ok("create_review_task", "Created review task.", {"task_id": int(cursor.lastrowid)})


def query_review_tasks(req: ReviewTaskQueryRequest) -> ToolResult:
    rows = _select("review_tasks", {"status": req.status, "assigned_to": req.assigned_to}, "updated_at DESC", req.limit)
    return _ok("query_review_tasks", f"Returned {len(rows)} review tasks.", {"items": rows})


def approve_review_task(req: ReviewTaskDecisionRequest) -> ToolResult:
    return _review_decision("approve_review_task", req, "approved")


def reject_review_task(req: ReviewTaskDecisionRequest) -> ToolResult:
    return _review_decision("reject_review_task", req, "rejected")


def convert_review_to_action(req: ReviewToActionRequest) -> ToolResult:
    _ensure_future_schema()
    with _connect() as conn:
        conn.execute("UPDATE review_tasks SET status = 'converted', updated_at = ? WHERE id = ?", (_now(), req.task_id))
        conn.execute("INSERT INTO review_actions (task_id, action_type, action_payload_json, created_at) VALUES (?, ?, ?, ?)", (req.task_id, req.action_type, _json(req.action_payload), _now()))
    return _ok("convert_review_to_action", "Converted review task to action.", req.model_dump())


def upsert_project_profile(req: ProjectProfileRequest) -> ToolResult:
    _ensure_future_schema()
    _upsert("project_profiles", "project_id", req.project_id, req.model_dump())
    return _ok("upsert_project_profile", "Upserted project profile.", req.model_dump())


def upsert_project_area(req: ProjectAreaRequest) -> ToolResult:
    _ensure_future_schema()
    _upsert("project_areas", "area_id", req.area_id, req.model_dump())
    return _ok("upsert_project_area", "Upserted project area.", req.model_dump())


def upsert_contractor(req: ContractorRequest) -> ToolResult:
    _ensure_future_schema()
    _upsert("contractors", "contractor_id", req.contractor_id, req.model_dump())
    return _ok("upsert_contractor", "Upserted contractor.", req.model_dump())


def upsert_personnel(req: PersonnelRequest) -> ToolResult:
    _ensure_future_schema()
    _upsert("personnel", "person_id", req.person_id, req.model_dump())
    return _ok("upsert_personnel", "Upserted personnel.", req.model_dump())


def query_project_context(req: ProjectContextQueryRequest) -> ToolResult:
    data: dict[str, Any] = {"project": _one("project_profiles", "project_id", req.project_id)}
    if req.include_areas:
        data["areas"] = _select("project_areas", {"project_id": req.project_id}, "area_id ASC", 500)
    if req.include_contractors:
        data["contractors"] = _select("contractors", {}, "contractor_id ASC", 500)
    if req.include_personnel:
        data["personnel"] = _select("personnel", {}, "person_id ASC", 500)
    return _ok("query_project_context", "Returned project context.", data)


def upsert_equipment_record(req: EquipmentRecordRequest) -> ToolResult:
    _ensure_future_schema()
    _upsert("equipment_records", "equipment_id", req.equipment_id, req.model_dump())
    return _ok("upsert_equipment_record", "Upserted equipment record.", req.model_dump())


def upsert_certificate_record(req: CertificateRecordRequest) -> ToolResult:
    _ensure_future_schema()
    _upsert("certificate_records", "certificate_id", req.certificate_id, req.model_dump())
    return _ok("upsert_certificate_record", "Upserted certificate record.", req.model_dump())


def query_expiring_certificates(req: ExpiringCertificateQueryRequest) -> ToolResult:
    _ensure_future_schema()
    today = date.today()
    rows = _select("certificate_records", {}, "expiry_date ASC", req.limit)
    items = []
    for row in rows:
        expiry = _parse_date(row.get("expiry_date"))
        if expiry is None:
            continue
        days = (expiry - today).days
        if days <= req.within_days:
            items.append({**row, "days_remaining": days, "status": "expired" if days < 0 else "warning"})
    return _ok("query_expiring_certificates", f"Returned {len(items)} expiring certificates.", {"items": items})


def link_certificate_to_equipment(req: CertificateEquipmentLinkRequest) -> ToolResult:
    _ensure_future_schema()
    with _connect() as conn:
        conn.execute("INSERT OR REPLACE INTO equipment_certificate_links (equipment_id, certificate_id, created_at) VALUES (?, ?, ?)", (req.equipment_id, req.certificate_id, _now()))
    return _ok("link_certificate_to_equipment", "Linked certificate to equipment.", req.model_dump())


def generate_certificate_expiry_notice(req: CertificateExpiryNoticeRequest) -> ToolResult:
    cert = _one("certificate_records", "certificate_id", req.certificate_id) or {}
    text = f"证书到期提醒：{cert.get('certificate_type', req.certificate_id)} 将于 {cert.get('expiry_date', '待补充')} 到期，请安排复核或续期。"
    return _ok("generate_certificate_expiry_notice", "Generated certificate expiry notice draft.", {"text": text, "audience": req.audience, "requires_human_confirmation": True})


def calculate_contractor_safety_score(req: ContractorScoreRequest) -> ToolResult:
    _ensure_future_schema()
    events = _select("contractor_score_events", {"contractor_id": req.contractor_id}, "created_at DESC", 1000)
    score = max(0, min(100, 100 + sum(int(event.get("points") or 0) for event in events)))
    now = _now()
    with _connect() as conn:
        conn.execute("INSERT OR REPLACE INTO contractor_scorecards (contractor_id, score, period, payload_json, updated_at) VALUES (?, ?, ?, ?, ?)", (req.contractor_id, score, req.period, _json({"events": events[:50]}), now))
    return _ok("calculate_contractor_safety_score", "Calculated contractor safety score.", {"contractor_id": req.contractor_id, "score": score, "event_count": len(events)})


def query_contractor_scorecard(req: ContractorScorecardQueryRequest) -> ToolResult:
    rows = _select("contractor_scorecards", {"contractor_id": req.contractor_id}, "updated_at DESC", req.limit)
    return _ok("query_contractor_scorecard", f"Returned {len(rows)} contractor scorecards.", {"items": rows})


def record_contractor_penalty(req: ContractorScoreEventRequest) -> ToolResult:
    req.event_type = "penalty"
    if req.points > 0:
        req.points = -req.points
    return _record_contractor_score_event("record_contractor_penalty", req)


def record_contractor_praise(req: ContractorScoreEventRequest) -> ToolResult:
    req.event_type = "praise"
    if req.points < 0:
        req.points = -req.points
    return _record_contractor_score_event("record_contractor_praise", req)


def draft_contractor_monthly_review(req: ContractorReviewDraftRequest) -> ToolResult:
    score = calculate_contractor_safety_score(ContractorScoreRequest(contractor_id=req.contractor_id, period=req.month)).data
    text = f"分判商月度安全评价草稿：{req.contractor_id} 本期安全评分 {score.get('score')}。请结合隐患复发率、整改速度和现场表现进行人工确认。"
    return _ok("draft_contractor_monthly_review", "Drafted contractor monthly review.", {"text": text, "score": score})


def register_media_evidence(req: MediaEvidenceRequest) -> ToolResult:
    _ensure_future_schema()
    path = Path(req.path)
    payload = {**req.model_dump(), "exists": path.exists(), "suffix": path.suffix, "size_bytes": path.stat().st_size if path.exists() else None}
    with _connect() as conn:
        cursor = conn.execute("INSERT INTO media_evidence (path, source_type, source_id, case_id, event_id, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (req.path, req.source_type, req.source_id, req.case_id, req.event_id, _json(payload), _now()))
    return _ok("register_media_evidence", "Registered media evidence.", {"media_id": int(cursor.lastrowid), **payload})


def generate_evidence_thumbnail(req: MediaThumbnailRequest) -> ToolResult:
    return _ok("generate_evidence_thumbnail", "Thumbnail generation placeholder.", {"media_id": req.media_id, "path": req.path, "thumbnail_path": None})


def extract_media_metadata(req: MediaMetadataRequest) -> ToolResult:
    path = Path(req.path)
    data = {"path": req.path, "exists": path.exists(), "suffix": path.suffix, "size_bytes": path.stat().st_size if path.exists() else None}
    return _ok("extract_media_metadata", "Extracted basic media metadata.", data)


def link_media_to_case(req: MediaCaseLinkRequest) -> ToolResult:
    _ensure_future_schema()
    with _connect() as conn:
        conn.execute("UPDATE media_evidence SET case_id = ? WHERE id = ?", (req.case_id, req.media_id))
    return _ok("link_media_to_case", "Linked media to case.", req.model_dump())


def create_evidence_bundle(req: EvidenceBundleRequest) -> ToolResult:
    rows = _select("media_evidence", {"case_id": req.case_id}, "created_at DESC", 500)
    task_id = new_task_id("evidence_bundle")
    out = task_dir(task_id) / f"case_{req.case_id}_evidence_bundle.json"
    write_json(out, rows)
    return _ok("create_evidence_bundle", f"Created evidence bundle with {len(rows)} items.", {"task_id": task_id, "path": str(out), "items": rows})


def draft_daily_safety_report(req: ReportDraftRequest) -> ToolResult:
    return _draft_report("draft_daily_safety_report", "每日安全日报", req)


def draft_weekly_safety_report(req: ReportDraftRequest) -> ToolResult:
    return _draft_report("draft_weekly_safety_report", "每周安全周报", req)


def draft_monthly_safety_report(req: ReportDraftRequest) -> ToolResult:
    return _draft_report("draft_monthly_safety_report", "月度安全报告", req)


def draft_incident_report(req: IncidentReportDraftRequest) -> ToolResult:
    text = f"事故/近危事件报告草稿\n\n事项：{req.description or '待补充'}\n关联案例：{req.case_id or '无'}\n关联事件：{req.event_id or '无'}\n\n请安全主任补充时间、地点、人员、原因分析和整改措施。"
    return _record_report("draft_incident_report", "incident", text, req.model_dump())


def export_report_package(req: ReportPackageExportRequest) -> ToolResult:
    task_id = new_task_id("report_package")
    out = task_dir(task_id) / "report_package_manifest.json"
    write_json(out, req.model_dump())
    return _ok("export_report_package", "Created report package manifest.", {"task_id": task_id, "path": str(out)})


def draft_rfi(req: RfiDraftRequest) -> ToolResult:
    _ensure_future_schema()
    with _connect() as conn:
        cursor = conn.execute("INSERT INTO rfi_records (project_id, subject, question, status, priority, case_id, created_at, updated_at) VALUES (?, ?, ?, 'draft', ?, ?, ?, ?)", (req.project_id, req.subject, req.question, req.priority, req.case_id, _now(), _now()))
    return _ok("draft_rfi", "Drafted RFI.", {"rfi_id": int(cursor.lastrowid), **req.model_dump()})


def query_rfi_records(req: RfiQueryRequest) -> ToolResult:
    rows = _select("rfi_records", {"status": req.status, "project_id": req.project_id}, "updated_at DESC", req.limit)
    return _ok("query_rfi_records", f"Returned {len(rows)} RFIs.", {"items": rows})


def draft_site_memo(req: SiteMemoDraftRequest) -> ToolResult:
    text = f"Site Memo 草稿\n\n主题：{req.subject}\n项目：{req.project_id}\n关联案例：{req.case_id or '无'}\n\n{req.body}"
    return _record_report("draft_site_memo", "site_memo", text, req.model_dump())


def draft_submittal_review(req: SubmittalReviewDraftRequest) -> ToolResult:
    text = f"提交文件审查意见草稿\n\n文件：{req.submittal_name}\n状态：{req.status}\n\n审查意见：{req.review_notes}"
    return _record_report("draft_submittal_review", "submittal_review", text, req.model_dump())


def link_rfi_to_case(req: RfiCaseLinkRequest) -> ToolResult:
    _ensure_future_schema()
    with _connect() as conn:
        conn.execute("UPDATE rfi_records SET case_id = ?, updated_at = ? WHERE id = ?", (req.case_id, _now(), req.rfi_id))
    return _ok("link_rfi_to_case", "Linked RFI to case.", req.model_dump())


def estimate_llm_payload_risk(req: LlmPayloadRiskRequest) -> ToolResult:
    text = req.text or _json(req.payload)
    findings = _sensitive_findings(text)
    level = "high" if any(item["type"] in {"hkid", "phone", "email"} for item in findings) else "medium" if findings else "low"
    return _ok("estimate_llm_payload_risk", "Estimated LLM payload risk.", {"risk_level": level, "findings": findings, "chars": len(text)})


def sanitize_llm_payload(req: LlmSanitizePayloadRequest) -> ToolResult:
    text = req.text if req.text is not None else _json(req.payload)
    sanitized = _sanitize(text)
    return _ok("sanitize_llm_payload", "Sanitized payload for LLM.", {"text": sanitized, "changed": sanitized != text})


def validate_llm_json_output(req: LlmJsonValidateRequest) -> ToolResult:
    try:
        data = json.loads(req.text)
        missing = [key for key in req.required_keys if key not in data]
        return _ok("validate_llm_json_output", "Validated JSON output.", {"valid": not missing, "missing_keys": missing, "data": data})
    except json.JSONDecodeError as exc:
        return ToolResult(ok=False, tool="validate_llm_json_output", summary="Invalid JSON output.", error=str(exc), data={"valid": False})


def retry_llm_with_repair_prompt(req: LlmRepairPromptRequest) -> ToolResult:
    prompt = "请修复以下模型输出，使其成为严格 JSON。不要添加 Markdown。\n\n"
    if req.expected_schema:
        prompt += f"期望 schema:\n{_json(req.expected_schema)}\n\n"
    if req.error:
        prompt += f"错误信息：{req.error}\n\n"
    prompt += f"原始输出：\n{req.bad_output}"
    return _ok("retry_llm_with_repair_prompt", "Prepared repair prompt.", {"prompt": prompt})


def record_prompt_version(req: PromptVersionRecordRequest) -> ToolResult:
    _ensure_future_schema()
    checksum = _hash(req.name, req.version, req.content)
    with _connect() as conn:
        conn.execute("INSERT OR REPLACE INTO prompt_versions (name, version, content, checksum, notes, created_at) VALUES (?, ?, ?, ?, ?, ?)", (req.name, req.version, req.content, checksum, req.notes, _now()))
    return _ok("record_prompt_version", "Recorded prompt version.", {"name": req.name, "version": req.version, "checksum": checksum})


def _review_decision(tool: str, req: ReviewTaskDecisionRequest, status: str) -> ToolResult:
    _ensure_future_schema()
    with _connect() as conn:
        conn.execute("UPDATE review_tasks SET status = ?, updated_at = ? WHERE id = ?", (status, _now(), req.task_id))
        conn.execute("INSERT INTO review_audit (target_type, target_id, reviewer, decision, notes, created_at) VALUES ('review_task', ?, ?, ?, ?, ?)", (req.task_id, req.reviewer, status, req.notes, _now()))
    return _ok(tool, f"Review task {status}.", req.model_dump())


def _record_contractor_score_event(tool: str, req: ContractorScoreEventRequest) -> ToolResult:
    _ensure_future_schema()
    with _connect() as conn:
        cursor = conn.execute("INSERT INTO contractor_score_events (contractor_id, points, reason, event_type, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?)", (req.contractor_id, req.points, req.reason, req.event_type, _json(req.metadata), _now()))
    return _ok(tool, "Recorded contractor score event.", {"event_id": int(cursor.lastrowid), **req.model_dump()})


def _draft_report(tool: str, title: str, req: ReportDraftRequest) -> ToolResult:
    text = f"{title}草稿\n\n项目：{req.project_id}\n周期：{req.period or '待补充'}\n\n请结合隐患、外部风险、表格记录和巡查情况完善。"
    return _record_report(tool, title, text, req.model_dump())


def _record_report(tool: str, report_type: str, text: str, payload: dict[str, Any]) -> ToolResult:
    _ensure_future_schema()
    with _connect() as conn:
        cursor = conn.execute("INSERT INTO report_records (report_type, text, payload_json, created_at) VALUES (?, ?, ?, ?)", (report_type, text, _json(payload), _now()))
    return _ok(tool, "Drafted report.", {"report_id": int(cursor.lastrowid), "text": text, "requires_human_confirmation": True})


def _ensure_future_schema() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS scheduled_jobs (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, job_type TEXT, cron TEXT, payload_json TEXT NOT NULL DEFAULT '{}', enabled INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS job_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER, job_name TEXT, status TEXT, result_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS platform_events (id INTEGER PRIMARY KEY AUTOINCREMENT, event_key TEXT UNIQUE, event_type TEXT, source_type TEXT, source_id TEXT, title TEXT, summary TEXT, risk_level TEXT, payload_json TEXT NOT NULL DEFAULT '{}', reviewed INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS event_case_links (id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER, case_id INTEGER, relation TEXT, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS review_tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, task_type TEXT, payload_json TEXT NOT NULL DEFAULT '{}', priority TEXT, assigned_to TEXT, status TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS review_actions (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER, action_type TEXT, action_payload_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS review_audit (id INTEGER PRIMARY KEY AUTOINCREMENT, target_type TEXT, target_id INTEGER, reviewer TEXT, decision TEXT, notes TEXT, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS project_profiles (project_id TEXT PRIMARY KEY, payload_json TEXT NOT NULL DEFAULT '{}', updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS project_areas (area_id TEXT PRIMARY KEY, project_id TEXT, payload_json TEXT NOT NULL DEFAULT '{}', updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS contractors (contractor_id TEXT PRIMARY KEY, payload_json TEXT NOT NULL DEFAULT '{}', updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS personnel (person_id TEXT PRIMARY KEY, payload_json TEXT NOT NULL DEFAULT '{}', updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS equipment_records (equipment_id TEXT PRIMARY KEY, payload_json TEXT NOT NULL DEFAULT '{}', updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS certificate_records (certificate_id TEXT PRIMARY KEY, certificate_type TEXT, expiry_date TEXT, payload_json TEXT NOT NULL DEFAULT '{}', updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS equipment_certificate_links (equipment_id TEXT, certificate_id TEXT, created_at TEXT NOT NULL, PRIMARY KEY(equipment_id, certificate_id));
            CREATE TABLE IF NOT EXISTS contractor_score_events (id INTEGER PRIMARY KEY AUTOINCREMENT, contractor_id TEXT, points INTEGER, reason TEXT, event_type TEXT, metadata_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS contractor_scorecards (contractor_id TEXT PRIMARY KEY, score INTEGER, period TEXT, payload_json TEXT NOT NULL DEFAULT '{}', updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS media_evidence (id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT, source_type TEXT, source_id TEXT, case_id INTEGER, event_id INTEGER, metadata_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS report_records (id INTEGER PRIMARY KEY AUTOINCREMENT, report_type TEXT, text TEXT, payload_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS rfi_records (id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT, subject TEXT, question TEXT, status TEXT, priority TEXT, case_id INTEGER, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS prompt_versions (name TEXT, version TEXT, content TEXT, checksum TEXT, notes TEXT, created_at TEXT NOT NULL, PRIMARY KEY(name, version));
            """
        )


def _upsert(table: str, key_col: str, key: str, payload: dict[str, Any]) -> None:
    now = _now()
    extra_cols = ""
    extra_vals: list[Any] = []
    if table == "certificate_records":
        extra_cols = ", certificate_type, expiry_date"
        extra_vals = [payload.get("certificate_type"), payload.get("expiry_date")]
    elif table == "project_areas":
        extra_cols = ", project_id"
        extra_vals = [payload.get("project_id")]
    with _connect() as conn:
        conn.execute(
            f"INSERT OR REPLACE INTO {table} ({key_col}{extra_cols}, payload_json, updated_at) VALUES (?{', ?' * len(extra_vals)}, ?, ?)",
            (key, *extra_vals, _json(payload), now),
        )


def _select(table: str, filters: dict[str, Any], order_by: str, limit: int) -> list[dict[str, Any]]:
    _ensure_future_schema()
    where = []
    params = []
    for key, value in filters.items():
        if value is None:
            continue
        where.append(f"{key} = ?")
        params.append(value)
    where_sql = f" WHERE {' AND '.join(where)}" if where else ""
    with _connect() as conn:
        rows = conn.execute(f"SELECT * FROM {table}{where_sql} ORDER BY {order_by} LIMIT ?", (*params, limit)).fetchall()
    return [_row(row) for row in rows]


def _one(table: str, key_col: str, key: str) -> dict[str, Any] | None:
    _ensure_future_schema()
    with _connect() as conn:
        row = conn.execute(f"SELECT * FROM {table} WHERE {key_col} = ?", (key,)).fetchone()
    return _row(row) if row else None


def _row(row: sqlite3.Row) -> dict[str, Any]:
    data = {key: row[key] for key in row.keys()}
    if "payload_json" in data:
        try:
            data["payload"] = json.loads(data["payload_json"] or "{}")
        except json.JSONDecodeError:
            data["payload"] = {}
    return data


def _sensitive_findings(text: str) -> list[dict[str, Any]]:
    checks = {
        "email": r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+",
        "phone": r"(?<!\d)(?:\+?852[-\s]?)?\d{4}[-\s]?\d{4}(?!\d)",
        "hkid": r"\b[A-Z]{1,2}\d{6}\([0-9A]\)\b",
    }
    findings = []
    for kind, pattern in checks.items():
        matches = re.findall(pattern, text, flags=re.I)
        if matches:
            findings.append({"type": kind, "count": len(matches)})
    return findings


def _sanitize(text: str) -> str:
    text = re.sub(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", "[EMAIL]", text)
    text = re.sub(r"(?<!\d)(?:\+?852[-\s]?)?\d{4}[-\s]?\d{4}(?!\d)", "[PHONE]", text)
    text = re.sub(r"\b[A-Z]{1,2}\d{6}\([0-9A]\)\b", "[HKID]", text, flags=re.I)
    return text


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _connect() -> sqlite3.Connection:
    path = settings.safety_database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _ok(tool: str, summary: str, data: dict[str, Any]) -> ToolResult:
    return ToolResult(ok=True, tool=tool, summary=summary, data=data)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _hash(*parts: Any) -> str:
    return hashlib.sha256("|".join(str(part or "") for part in parts).lower().encode("utf-8")).hexdigest()[:24]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


ToolHandler = Callable[[BaseModel], ToolResult]


FUTURE_TOOL_MODELS: dict[str, type[BaseModel]] = {
    "create_scheduled_job": ScheduledJobCreateRequest,
    "list_scheduled_jobs": ScheduledJobQueryRequest,
    "run_scheduled_job_now": ScheduledJobRunRequest,
    "pause_scheduled_job": ScheduledJobPauseRequest,
    "record_job_run": JobRunRecordRequest,
    "create_platform_event": PlatformEventCreateRequest,
    "query_platform_events": PlatformEventQueryRequest,
    "link_event_to_case": EventCaseLinkRequest,
    "mark_event_reviewed": EventReviewedRequest,
    "dedupe_platform_events": EventDedupeRequest,
    "create_review_task": ReviewTaskCreateRequest,
    "query_review_tasks": ReviewTaskQueryRequest,
    "approve_review_task": ReviewTaskDecisionRequest,
    "reject_review_task": ReviewTaskDecisionRequest,
    "convert_review_to_action": ReviewToActionRequest,
    "upsert_project_profile": ProjectProfileRequest,
    "upsert_project_area": ProjectAreaRequest,
    "upsert_contractor": ContractorRequest,
    "upsert_personnel": PersonnelRequest,
    "query_project_context": ProjectContextQueryRequest,
    "upsert_equipment_record": EquipmentRecordRequest,
    "upsert_certificate_record": CertificateRecordRequest,
    "query_expiring_certificates": ExpiringCertificateQueryRequest,
    "link_certificate_to_equipment": CertificateEquipmentLinkRequest,
    "generate_certificate_expiry_notice": CertificateExpiryNoticeRequest,
    "calculate_contractor_safety_score": ContractorScoreRequest,
    "query_contractor_scorecard": ContractorScorecardQueryRequest,
    "record_contractor_penalty": ContractorScoreEventRequest,
    "record_contractor_praise": ContractorScoreEventRequest,
    "draft_contractor_monthly_review": ContractorReviewDraftRequest,
    "register_media_evidence": MediaEvidenceRequest,
    "generate_evidence_thumbnail": MediaThumbnailRequest,
    "extract_media_metadata": MediaMetadataRequest,
    "link_media_to_case": MediaCaseLinkRequest,
    "create_evidence_bundle": EvidenceBundleRequest,
    "draft_daily_safety_report": ReportDraftRequest,
    "draft_weekly_safety_report": ReportDraftRequest,
    "draft_monthly_safety_report": ReportDraftRequest,
    "draft_incident_report": IncidentReportDraftRequest,
    "export_report_package": ReportPackageExportRequest,
    "draft_rfi": RfiDraftRequest,
    "query_rfi_records": RfiQueryRequest,
    "draft_site_memo": SiteMemoDraftRequest,
    "draft_submittal_review": SubmittalReviewDraftRequest,
    "link_rfi_to_case": RfiCaseLinkRequest,
    "estimate_llm_payload_risk": LlmPayloadRiskRequest,
    "sanitize_llm_payload": LlmSanitizePayloadRequest,
    "validate_llm_json_output": LlmJsonValidateRequest,
    "retry_llm_with_repair_prompt": LlmRepairPromptRequest,
    "record_prompt_version": PromptVersionRecordRequest,
}


FUTURE_TOOL_HANDLERS: dict[str, Callable[[Any], ToolResult]] = {
    name: globals()[name] for name in FUTURE_TOOL_MODELS
}


def call_future_tool(name: str, arguments: dict[str, Any]) -> ToolResult:
    model = FUTURE_TOOL_MODELS[name]
    return FUTURE_TOOL_HANDLERS[name](model(**arguments))


def future_tool_specs() -> list[ToolSpec]:
    return [
        ToolSpec(name=name, description=f"Future reserved backend tool: {name}.", input_schema=model.model_json_schema())
        for name, model in FUTURE_TOOL_MODELS.items()
    ]
