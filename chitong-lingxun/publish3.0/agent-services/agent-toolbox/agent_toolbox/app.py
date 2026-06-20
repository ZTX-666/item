from __future__ import annotations

from fastapi import FastAPI, Request
from pydantic import BaseModel, Field
from typing import Any

from .config import settings
from .models import HealthResult
from .registry import health_checks, tool_specs
from .mcp_server import _call_tool
from .tasks import ensure_workspace
from .tools.audit_permissions import (
    ActionPermissionCheckRequest,
    AuditLogQueryRequest,
    LlmAuditRecordRequest,
    ToolAuditRecordRequest,
    UserRoleManageRequest,
    check_action_permission,
    list_audit_logs,
    manage_user_roles,
    record_llm_audit,
    record_tool_audit,
)
from .tools.communications import (
    ChatGroupDailySummaryRequest,
    ConfirmedSendRequest,
    GroupMessageDraftRequest,
    NotificationArchiveRequest,
    RecentChatHazardRequest,
    WhatsAppGroupListRequest,
    archive_sent_notification,
    draft_group_message,
    extract_hazards_from_recent_chats,
    list_whatsapp_groups,
    send_group_message_with_confirm,
    summarize_chat_group_daily,
)
from .tools.documents_ocr import (
    CertificateExpiryCheckRequest,
    CertificateFieldExtractRequest,
    DocumentTypeClassifyRequest,
    OcrDocumentRequest,
    PolicyClauseSearchRequest,
    PolicyDocumentSummarizeRequest,
    TableExtractionRequest,
    check_certificate_expiry,
    classify_document_type,
    extract_certificate_fields,
    extract_tables_from_document,
    ocr_document_or_image,
    search_policy_clauses,
    summarize_policy_document,
)
from .tools.case_management import (
    CaseCloseReviewRequest,
    CaseDraftRequest,
    CaseEvidenceRequest,
    SafetyCaseAssignRequest,
    SafetyCaseCreateRequest,
    SafetyCaseStatusRequest,
    add_case_evidence,
    assign_safety_case,
    close_case_with_review,
    create_safety_case,
    generate_rectification_notice,
    generate_warning_letter,
    update_safety_case_status,
)
from .tools.external_risk import (
    DailyRiskBriefingRequest,
    ExternalRiskFetchRequest,
    ExternalRiskPersistRequest,
    ExternalRiskFormLinkRequest,
    ExternalRiskSummarizeRequest,
    HkoWeatherFetchRequest,
    draft_daily_risk_briefing,
    fetch_hk_industrial_news,
    fetch_hk_safety_updates,
    fetch_hko_weather,
    link_external_risk_to_forms,
    persist_external_risk_items,
    summarize_external_risks,
)
from .tools.feishu import (
    FeishuChatListRequest,
    FeishuEventArchiveRequest,
    FeishuEventCallbackRequest,
    FeishuEventToPlatformEventRequest,
    FeishuNotifyRequest,
    FeishuSafetyCardRequest,
    FeishuSendCardRequest,
    FeishuSendMessageRequest,
    FeishuTenantTokenRequest,
    feishu_archive_event,
    feishu_build_safety_review_card,
    feishu_event_to_platform_event,
    feishu_get_tenant_access_token,
    feishu_handle_event_callback,
    feishu_list_chats,
    feishu_send_interactive_card,
    feishu_send_text_message,
    notify_feishu,
)
from .tools.forms import (
    DocxGenerateFromTemplateRequest,
    FormPrefillRequest,
    FormRecordExportRequest,
    FormSuggestionRequest,
    FormTemplateDetailRequest,
    FormTemplateSearchRequest,
    export_form_record,
    generate_docx_from_template,
    get_form_template_detail,
    prefill_form_fields,
    search_form_templates,
    suggest_forms_for_case,
)
from .tools.docmate_docx import (
    ApplyChangesetRequest,
    GenerateChangesetRequest,
    PreviewChangesetRequest,
    ReadDocxRequest,
    tool_docmate_apply_changeset,
    tool_docmate_generate_changeset,
    tool_docmate_preview_changeset,
    tool_docmate_read_docx,
)
from .tools.future_operations import FUTURE_TOOL_MODELS, call_future_tool
from .tools.queries import (
    DashboardMetricsRequest,
    ExternalRiskQueryRequest,
    FormRecordQueryRequest,
    PendingActionQueryRequest,
    SafetyCaseQueryRequest,
    SafetyDataExportRequest,
    export_safety_data,
    get_dashboard_metrics,
    query_external_risks,
    query_form_records,
    query_pending_actions,
    query_safety_cases,
)
from .tools.reference_adapters import (
    ConstructionToolMapRequest,
    HazardZoneRuleRequest,
    ReferenceAdapterListRequest,
    SafetyReportFromEventsRequest,
    VisualPipelineRecommendRequest,
    VisualSafetyEventNormalizeRequest,
    draft_safety_report_from_events,
    evaluate_hazard_zone_rules,
    list_reference_adapters,
    map_mcp_construction_tool,
    normalize_visual_safety_event,
    recommend_visual_safety_pipeline,
)
from .tools.prompt_templates import (
    PromptTemplateListRequest,
    PromptTemplateRenderRequest,
    list_prompt_templates,
    render_prompt_template,
)
from .tools.report import GenerateReportRequest, generate_report
from .tools.rtmp import RtmpSnapshotRequest, run_rtmp_snapshot
from .tools.safety import (
    AIArchiveClassifyRequest,
    ChatHazardIngestRequest,
    ClassificationFeedbackRequest,
    HazardDedupeRequest,
    SafetyActionConnectRequest,
    SafetyDatabaseInitRequest,
    VlmHazardIngestRequest,
    ai_archive_classifier,
    connect_hazard_actions,
    dedupe_and_link_hazards,
    ingest_chat_hazards,
    ingest_vlm_hazards,
    init_safety_database,
    record_classification_feedback,
)
from .tools.vlm import VlmDetectRequest, run_vlm_detect
from .tools.vlm_workflows import (
    CameraPatrolScheduleRequest,
    CameraSnapshotRequest,
    VlmBatchRequest,
    VlmBeforeAfterCompareRequest,
    VlmCaseCreateRequest,
    VlmHazardClassifyRequest,
    capture_camera_snapshot,
    classify_vlm_hazard,
    compare_vlm_before_after,
    create_case_from_vlm,
    run_vlm_detection_batch,
    schedule_camera_patrol,
)
from .tools.whatsapp import (
    WhatsAppDownloadMediaRequest,
    WhatsAppSearchRequest,
    download_media,
    search_messages,
)


app = FastAPI(
    title="AgentToolbox",
    version="0.1.0",
    description="Expose local programs as HTTP tools for AI agents.",
)


class GenericToolCallRequest(BaseModel):
    name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


@app.on_event("startup")
def _startup() -> None:
    ensure_workspace()


@app.get("/health", response_model=HealthResult)
def health() -> HealthResult:
    checks = health_checks()
    return HealthResult(
        ok=all(bool(item.get("available")) for name, item in checks.items() if name != "feishu_notify"),
        workspace=str(settings.workspace),
        tools=checks,
    )


@app.get("/tools")
def list_tools() -> dict:
    return {"tools": [spec.model_dump() for spec in tool_specs()]}


@app.post("/integrations/feishu/events")
async def feishu_events_callback(request: Request):
    payload = await request.json()
    result = feishu_handle_event_callback(FeishuEventCallbackRequest(payload=payload))
    response = result.data.get("response")
    if response:
        return response
    return result.model_dump()


@app.post("/tools/call")
def call_tool(req: GenericToolCallRequest) -> dict[str, Any]:
    return _call_tool(req.name, req.arguments)


@app.post("/tools/future/{tool_name}")
def call_future_operation(tool_name: str, arguments: dict[str, Any] | None = None):
    if tool_name not in FUTURE_TOOL_MODELS:
        return {"ok": False, "tool": tool_name, "summary": "Unknown future operation tool.", "error": f"Unknown tool: {tool_name}"}
    return call_future_tool(tool_name, arguments or {})


@app.post("/tools/rtmp_snapshot")
def rtmp_snapshot(req: RtmpSnapshotRequest):
    return run_rtmp_snapshot(req)


@app.post("/tools/vlm_detect")
def vlm_detect(req: VlmDetectRequest):
    return run_vlm_detect(req)


@app.post("/tools/whatsapp_search")
def whatsapp_search(req: WhatsAppSearchRequest):
    return search_messages(req)


@app.post("/tools/whatsapp_download_media")
def whatsapp_download_media(req: WhatsAppDownloadMediaRequest):
    return download_media(req)


@app.post("/tools/generate_report")
def report(req: GenerateReportRequest):
    return generate_report(req)


@app.post("/tools/notify_feishu")
def feishu_notify(req: FeishuNotifyRequest):
    return notify_feishu(req)


@app.post("/tools/feishu_get_tenant_access_token")
def feishu_tenant_access_token(req: FeishuTenantTokenRequest):
    return feishu_get_tenant_access_token(req)


@app.post("/tools/feishu_send_text_message")
def feishu_text_message_send(req: FeishuSendMessageRequest):
    return feishu_send_text_message(req)


@app.post("/tools/feishu_send_interactive_card")
def feishu_interactive_card_send(req: FeishuSendCardRequest):
    return feishu_send_interactive_card(req)


@app.post("/tools/feishu_build_safety_review_card")
def feishu_safety_review_card_build(req: FeishuSafetyCardRequest):
    return feishu_build_safety_review_card(req)


@app.post("/tools/feishu_handle_event_callback")
def feishu_event_callback_handle(req: FeishuEventCallbackRequest):
    return feishu_handle_event_callback(req)


@app.post("/tools/feishu_list_chats")
def feishu_chats_list(req: FeishuChatListRequest):
    return feishu_list_chats(req)


@app.post("/tools/feishu_archive_event")
def feishu_event_archive(req: FeishuEventArchiveRequest):
    return feishu_archive_event(req)


@app.post("/tools/feishu_event_to_platform_event")
def feishu_to_platform_event(req: FeishuEventToPlatformEventRequest):
    return feishu_event_to_platform_event(req)


@app.post("/tools/fetch_hko_weather")
def hko_weather(req: HkoWeatherFetchRequest):
    return fetch_hko_weather(req)


@app.post("/tools/fetch_hk_safety_updates")
def hk_safety_updates(req: ExternalRiskFetchRequest):
    return fetch_hk_safety_updates(req)


@app.post("/tools/fetch_hk_industrial_news")
def hk_industrial_news(req: ExternalRiskFetchRequest):
    return fetch_hk_industrial_news(req)


@app.post("/tools/persist_external_risk_items")
def external_risk_persist(req: ExternalRiskPersistRequest):
    return persist_external_risk_items(req)


@app.post("/tools/summarize_external_risks")
def external_risk_summary(req: ExternalRiskSummarizeRequest):
    return summarize_external_risks(req)


@app.post("/tools/draft_daily_risk_briefing")
def daily_risk_briefing(req: DailyRiskBriefingRequest):
    return draft_daily_risk_briefing(req)


@app.post("/tools/link_external_risk_to_forms")
def external_risk_form_link(req: ExternalRiskFormLinkRequest):
    return link_external_risk_to_forms(req)


@app.post("/tools/search_form_templates")
def form_templates_search(req: FormTemplateSearchRequest):
    return search_form_templates(req)


@app.post("/tools/get_form_template_detail")
def form_template_detail(req: FormTemplateDetailRequest):
    return get_form_template_detail(req)


@app.post("/tools/suggest_forms_for_case")
def forms_for_case(req: FormSuggestionRequest):
    return suggest_forms_for_case(req)


@app.post("/tools/prefill_form_fields")
def form_fields_prefill(req: FormPrefillRequest):
    return prefill_form_fields(req)


@app.post("/tools/generate_docx_from_template")
def docx_from_template(req: DocxGenerateFromTemplateRequest):
    return generate_docx_from_template(req)


@app.post("/tools/export_form_record")
def form_record_export(req: FormRecordExportRequest):
    return export_form_record(req)


@app.post("/tools/create_safety_case")
def safety_case_create(req: SafetyCaseCreateRequest):
    return create_safety_case(req)


@app.post("/tools/update_safety_case_status")
def safety_case_status_update(req: SafetyCaseStatusRequest):
    return update_safety_case_status(req)


@app.post("/tools/assign_safety_case")
def safety_case_assign(req: SafetyCaseAssignRequest):
    return assign_safety_case(req)


@app.post("/tools/add_case_evidence")
def case_evidence_add(req: CaseEvidenceRequest):
    return add_case_evidence(req)


@app.post("/tools/generate_rectification_notice")
def rectification_notice_generate(req: CaseDraftRequest):
    return generate_rectification_notice(req)


@app.post("/tools/generate_warning_letter")
def warning_letter_generate(req: CaseDraftRequest):
    return generate_warning_letter(req)


@app.post("/tools/close_case_with_review")
def case_close_review(req: CaseCloseReviewRequest):
    return close_case_with_review(req)


@app.post("/tools/query_safety_cases")
def safety_cases_query(req: SafetyCaseQueryRequest):
    return query_safety_cases(req)


@app.post("/tools/query_external_risks")
def external_risks_query(req: ExternalRiskQueryRequest):
    return query_external_risks(req)


@app.post("/tools/query_form_records")
def form_records_query(req: FormRecordQueryRequest):
    return query_form_records(req)


@app.post("/tools/query_pending_actions")
def pending_actions_query(req: PendingActionQueryRequest):
    return query_pending_actions(req)


@app.post("/tools/get_dashboard_metrics")
def dashboard_metrics(req: DashboardMetricsRequest):
    return get_dashboard_metrics(req)


@app.post("/tools/export_safety_data")
def safety_data_export(req: SafetyDataExportRequest):
    return export_safety_data(req)


@app.post("/tools/list_whatsapp_groups")
def whatsapp_groups_list(req: WhatsAppGroupListRequest):
    return list_whatsapp_groups(req)


@app.post("/tools/draft_group_message")
def group_message_draft(req: GroupMessageDraftRequest):
    return draft_group_message(req)


@app.post("/tools/send_group_message_with_confirm")
def group_message_send_confirm(req: ConfirmedSendRequest):
    return send_group_message_with_confirm(req)


@app.post("/tools/archive_sent_notification")
def sent_notification_archive(req: NotificationArchiveRequest):
    return archive_sent_notification(req)


@app.post("/tools/extract_hazards_from_recent_chats")
def recent_chats_hazard_extract(req: RecentChatHazardRequest):
    return extract_hazards_from_recent_chats(req)


@app.post("/tools/summarize_chat_group_daily")
def chat_group_daily_summary(req: ChatGroupDailySummaryRequest):
    return summarize_chat_group_daily(req)


@app.post("/tools/capture_camera_snapshot")
def camera_snapshot_capture(req: CameraSnapshotRequest):
    return capture_camera_snapshot(req)


@app.post("/tools/run_vlm_detection_batch")
def vlm_detection_batch(req: VlmBatchRequest):
    return run_vlm_detection_batch(req)


@app.post("/tools/classify_vlm_hazard")
def vlm_hazard_classify(req: VlmHazardClassifyRequest):
    return classify_vlm_hazard(req)


@app.post("/tools/create_case_from_vlm")
def case_from_vlm_create(req: VlmCaseCreateRequest):
    return create_case_from_vlm(req)


@app.post("/tools/compare_vlm_before_after")
def vlm_before_after_compare(req: VlmBeforeAfterCompareRequest):
    return compare_vlm_before_after(req)


@app.post("/tools/schedule_camera_patrol")
def camera_patrol_schedule(req: CameraPatrolScheduleRequest):
    return schedule_camera_patrol(req)


@app.post("/tools/ocr_document_or_image")
def document_or_image_ocr(req: OcrDocumentRequest):
    return ocr_document_or_image(req)


@app.post("/tools/extract_tables_from_document")
def document_tables_extract(req: TableExtractionRequest):
    return extract_tables_from_document(req)


@app.post("/tools/classify_document_type")
def document_type_classify(req: DocumentTypeClassifyRequest):
    return classify_document_type(req)


@app.post("/tools/extract_certificate_fields")
def certificate_fields_extract(req: CertificateFieldExtractRequest):
    return extract_certificate_fields(req)


@app.post("/tools/check_certificate_expiry")
def certificate_expiry_check(req: CertificateExpiryCheckRequest):
    return check_certificate_expiry(req)


@app.post("/tools/summarize_policy_document")
def policy_document_summarize(req: PolicyDocumentSummarizeRequest):
    return summarize_policy_document(req)


@app.post("/tools/search_policy_clauses")
def policy_clauses_search(req: PolicyClauseSearchRequest):
    return search_policy_clauses(req)


@app.post("/tools/record_tool_audit")
def tool_audit_record(req: ToolAuditRecordRequest):
    return record_tool_audit(req)


@app.post("/tools/record_llm_audit")
def llm_audit_record(req: LlmAuditRecordRequest):
    return record_llm_audit(req)


@app.post("/tools/list_audit_logs")
def audit_logs_list(req: AuditLogQueryRequest):
    return list_audit_logs(req)


@app.post("/tools/manage_user_roles")
def user_roles_manage(req: UserRoleManageRequest):
    return manage_user_roles(req)


@app.post("/tools/check_action_permission")
def action_permission_check(req: ActionPermissionCheckRequest):
    return check_action_permission(req)


@app.post("/tools/list_prompt_templates")
def prompt_templates_list(req: PromptTemplateListRequest):
    return list_prompt_templates(req)


@app.post("/tools/render_prompt_template")
def prompt_template_render(req: PromptTemplateRenderRequest):
    return render_prompt_template(req)


@app.post("/tools/list_reference_adapters")
def reference_adapters_list(req: ReferenceAdapterListRequest):
    return list_reference_adapters(req)


@app.post("/tools/map_mcp_construction_tool")
def mcp_construction_tool_map(req: ConstructionToolMapRequest):
    return map_mcp_construction_tool(req)


@app.post("/tools/normalize_visual_safety_event")
def visual_safety_event_normalize(req: VisualSafetyEventNormalizeRequest):
    return normalize_visual_safety_event(req)


@app.post("/tools/evaluate_hazard_zone_rules")
def hazard_zone_rules_evaluate(req: HazardZoneRuleRequest):
    return evaluate_hazard_zone_rules(req)


@app.post("/tools/recommend_visual_safety_pipeline")
def visual_safety_pipeline_recommend(req: VisualPipelineRecommendRequest):
    return recommend_visual_safety_pipeline(req)


@app.post("/tools/draft_safety_report_from_events")
def safety_report_from_events_draft(req: SafetyReportFromEventsRequest):
    return draft_safety_report_from_events(req)


@app.post("/tools/init_safety_database")
def safety_database_init(req: SafetyDatabaseInitRequest):
    return init_safety_database(req)


@app.post("/tools/ai_archive_classifier")
def archive_classifier(req: AIArchiveClassifyRequest):
    return ai_archive_classifier(req)


@app.post("/tools/ingest_chat_hazards")
def chat_hazards(req: ChatHazardIngestRequest):
    return ingest_chat_hazards(req)


@app.post("/tools/ingest_vlm_hazards")
def vlm_hazards(req: VlmHazardIngestRequest):
    return ingest_vlm_hazards(req)


@app.post("/tools/dedupe_and_link_hazards")
def hazard_dedupe(req: HazardDedupeRequest):
    return dedupe_and_link_hazards(req)


@app.post("/tools/connect_hazard_actions")
def hazard_actions(req: SafetyActionConnectRequest):
    return connect_hazard_actions(req)


@app.post("/tools/record_classification_feedback")
def classification_feedback(req: ClassificationFeedbackRequest):
    return record_classification_feedback(req)


# ── DocMate .docx 工具端点 ────────────────────────────────────

@app.post("/tools/docmate_read_docx")
async def docmate_read_docx_endpoint(req: ReadDocxRequest):
    return await tool_docmate_read_docx(req)


@app.post("/tools/docmate_generate_changeset")
async def docmate_generate_changeset_endpoint(req: GenerateChangesetRequest):
    return await tool_docmate_generate_changeset(req)


@app.post("/tools/docmate_preview_changeset")
async def docmate_preview_changeset_endpoint(req: PreviewChangesetRequest):
    return await tool_docmate_preview_changeset(req)


@app.post("/tools/docmate_apply_changeset")
async def docmate_apply_changeset_endpoint(req: ApplyChangesetRequest):
    return await tool_docmate_apply_changeset(req)
