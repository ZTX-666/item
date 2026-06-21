from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


IntentName = Literal[
    "hazard_intake",
    "visual_detection",
    "document_form",
    "weather_news_risk",
    "knowledge_query",
    "general_chat",
]


class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1)
    channel: str = "local_web"
    user_id: str = "local_user"
    project_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class IntentResult(BaseModel):
    intent: IntentName
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    suggested_tools: list[str] = Field(default_factory=list)


class ActionCard(BaseModel):
    card_type: str
    title: str
    summary: str
    actions: list[dict[str, Any]] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)


class ChatMessageResponse(BaseModel):
    reply: str
    intent: IntentResult
    cards: list[ActionCard] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    audit_id: str


class CardActionRequest(BaseModel):
    action_id: str
    card_data: dict[str, Any] = Field(default_factory=dict)
    user_id: str = "local_user"
    channel: str = "local_web"


class HazardStatusUpdateRequest(BaseModel):
    status: str = "confirmed"
    notes: str | None = None


class DocumentRevisionRequest(BaseModel):
    title: str = "AI 文档改写预览"
    source: str = "chitung-center"
    instruction: str
    original_text: str
    revised_text: str | None = None


class SmartFormDraftRequest(BaseModel):
    query: str
    source_text: str
    template_id: str | None = None
    case_id: int | None = None
    known_fields: dict[str, Any] = Field(default_factory=dict)
    instruction: str = "生成安全表格草稿，并保留人工采纳确认。"


class SmartFormAcceptRequest(BaseModel):
    template_id: str
    fields: dict[str, Any] = Field(default_factory=dict)
    output_path: str | None = None
    case_id: int | None = None
    notes: str | None = None


class VisualPatrolDraftRequest(BaseModel):
    camera_url: str | None = None
    source: str | None = None
    area: str | None = None
    contractor: str | None = None
    count: int = 1
    conf: float | None = None


class VisualPatrolConfirmRequest(BaseModel):
    detections: dict[str, Any] | None = None
    vlm_result_path: str | None = None
    task_id: str | None = None
    image_path: str | None = None
    area: str | None = None
    contractor: str | None = None
    description: str | None = None


class CaseWorkflowRequest(BaseModel):
    case_id: int
    contractor: str | None = None
    due_date: str | None = None
    notes: str | None = None
    reviewer: str | None = None
    evidence_paths: list[str] = Field(default_factory=list)


class ReportGenerateRequest(BaseModel):
    report_type: Literal["community", "daily_safety", "rectification"] = "daily_safety"
    case_id: int | None = None
    title: str | None = None


class NotificationSendRequest(BaseModel):
    case_id: int
    text: str
    contractor: str | None = None
    channel: Literal["feishu", "whatsapp"] = "feishu"
    confirmed_by: str = "desktop_user"


class LlmSettingsRequest(BaseModel):
    base_url: str
    api_key: str
    model: str


class ConnectorSettingsRequest(BaseModel):
    whatsapp_archive_base_url: str = ""
    feishu_webhook_url: str = ""
    feishu_webhook_secret: str = ""
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_verification_token: str = ""
    feishu_encrypt_key: str = ""
    feishu_api_base_url: str = "https://open.feishu.cn"


class ProjectConfig(BaseModel):
    name: str = "赤瞳示范项目"
    default_area: str = "B2"
    location: str = "Hong Kong"


class CameraConfig(BaseModel):
    id: str
    name: str
    area: str
    rtmp_url: str | None = None
    enabled: bool = True


class ContractorConfig(BaseModel):
    id: str
    name: str
    contact: str | None = None
    channel: str | None = None
    default_due_days: int = 3


class AppConfigRequest(BaseModel):
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    cameras: list[CameraConfig] = Field(default_factory=list)
    contractors: list[ContractorConfig] = Field(default_factory=list)


class IntegrationStatus(BaseModel):
    name: str
    display_name: str
    enabled: bool
    category: str
    notes: str


class ToolCallPlan(BaseModel):
    tool_name: str
    payload: dict[str, Any] = Field(default_factory=dict)
    requires_confirmation: bool = False


PlanStatus = Literal[
    "DRAFT",
    "PLANNED",
    "PENDING_CONFIRMATION",
    "CONFIRMED",
    "EXECUTING",
    "SUCCEEDED",
    "FAILED",
]


RiskLevelName = Literal["low", "medium", "high", "critical"]


class HybridPlanRequest(BaseModel):
    session_id: str = Field(min_length=1)
    user_input: str = Field(min_length=1)
    prefer_codex: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class HybridActionView(BaseModel):
    action_id: str
    sequence_no: int
    tool_name: str
    payload: dict[str, Any] = Field(default_factory=dict)
    risk_level: RiskLevelName = "medium"
    requires_confirmation: bool = True
    status: str
    retry_count: int = 0
    max_retries: int = 2
    result: dict[str, Any] = Field(default_factory=dict)
    last_error: str | None = None


class HybridPlanView(BaseModel):
    plan_id: str
    session_id: str
    user_input: str
    workflow: str
    planner_mode: str
    status: PlanStatus
    fallback_used: bool = False
    fallback_reason: str | None = None
    selected_action_ids: list[str] = Field(default_factory=list)
    idempotency_key: str | None = None
    result: dict[str, Any] = Field(default_factory=dict)
    last_error: str | None = None
    created_at: str
    updated_at: str
    actions: list[HybridActionView] = Field(default_factory=list)


class HybridPlanResponse(BaseModel):
    ok: bool = True
    audit_id: str
    plan: HybridPlanView


class HybridConfirmRequest(BaseModel):
    session_id: str = Field(min_length=1)
    plan_id: str = Field(min_length=1)
    action_ids: list[str] = Field(default_factory=list)
    confirmed_by: str = "local_user"
    notes: str | None = None


class HybridExecuteRequest(BaseModel):
    session_id: str = Field(min_length=1)
    plan_id: str = Field(min_length=1)
    idempotency_key: str | None = None
    retry_failed_only: bool = True
    dry_run: bool = False


class HybridExecuteResponse(BaseModel):
    ok: bool
    audit_id: str
    idempotent_hit: bool = False
    plan: HybridPlanView
    action_results: list[dict[str, Any]] = Field(default_factory=list)


class AuditEventRequest(BaseModel):
    event_type: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    session_id: str | None = None
    plan_id: str | None = None
    action_id: str | None = None
    status: str | None = None


class AuditEventResponse(BaseModel):
    ok: bool = True
    audit_id: str
