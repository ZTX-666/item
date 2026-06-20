from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from chitung_center.app_config_service import get_app_config, save_app_config
from chitung_center.case_workflow_service import (
    close_case_after_review,
    confirm_contractor_assignment,
    draft_rectification_notice,
    send_rectification_notification,
)
from chitung_center.config import settings
from chitung_center.document_service import build_document_revision_preview
from chitung_center.integrations import list_integrations
from chitung_center.hybrid_orchestration import hybrid_orchestration_service
from chitung_center.models import (
    AuditEventRequest,
    AppConfigRequest,
    CardActionRequest,
    CaseWorkflowRequest,
    ChatMessageRequest,
    ConnectorSettingsRequest,
    DocumentRevisionRequest,
    HazardStatusUpdateRequest,
    HybridConfirmRequest,
    HybridExecuteRequest,
    HybridPlanRequest,
    LlmSettingsRequest,
    NotificationSendRequest,
    ReportGenerateRequest,
    SmartFormAcceptRequest,
    SmartFormDraftRequest,
    WhatsAppGroupsApiRequest,
    WhatsAppSearchApiRequest,
    VisualPatrolConfirmRequest,
    VisualPatrolDraftRequest,
)
from chitung_center.orchestrator import orchestrator
from chitung_center.runtime_service import build_runtime_status
from chitung_center.report_service import generate_report_file
from chitung_center.settings_service import (
    get_connector_settings_status,
    get_llm_settings_status,
    save_connector_settings,
    save_llm_settings,
    test_llm_connection,
)
from chitung_center.skills import skill_loader
from chitung_center.smart_form_service import accept_smart_form_draft, build_smart_form_draft
from chitung_center.toolbox_client import toolbox_client
from chitung_center.visual_patrol_service import build_visual_patrol_draft, confirm_visual_patrol_candidate
from chitung_center.workbench_service import build_workbench_summary, update_hazard_status


app = FastAPI(
    title="Chitung Center",
    description="Lightweight agent base for the Chitong Safety Platform.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, object]:
    toolbox = await toolbox_client.health()
    return {
        "ok": True,
        "service": "chitung-center",
        "llm_configured": settings.llm_configured,
        "agent_toolbox": toolbox,
    }


@app.get("/api/integrations")
async def integrations() -> dict[str, object]:
    return {"items": [item.model_dump() for item in list_integrations()]}


@app.get("/api/skills")
async def skills() -> dict[str, object]:
    return {"items": [skill.__dict__ for skill in skill_loader.list_skills()]}


@app.get("/api/workbench/summary")
async def workbench_summary() -> dict[str, object]:
    return await build_workbench_summary()


@app.get("/api/runtime/status")
async def runtime_status() -> dict[str, object]:
    return await build_runtime_status()


@app.get("/api/config/app")
async def app_config_get() -> dict[str, object]:
    return get_app_config()


@app.post("/api/config/app")
async def app_config_save(request: AppConfigRequest) -> dict[str, object]:
    return save_app_config(request)


@app.get("/api/settings/llm")
async def llm_settings_status() -> dict[str, object]:
    return get_llm_settings_status()


@app.post("/api/settings/llm")
async def llm_settings_save(request: LlmSettingsRequest) -> dict[str, object]:
    return save_llm_settings(request)


@app.post("/api/settings/llm/test")
async def llm_settings_test() -> dict[str, object]:
    return await test_llm_connection()


@app.get("/api/settings/connectors")
async def connector_settings_status() -> dict[str, object]:
    return get_connector_settings_status()


@app.post("/api/settings/connectors")
async def connector_settings_save(request: ConnectorSettingsRequest) -> dict[str, object]:
    return save_connector_settings(request)


@app.post("/api/hazards/{case_id}/status")
async def hazard_status(case_id: int, request: HazardStatusUpdateRequest) -> dict[str, object]:
    return await update_hazard_status(case_id, request.status, request.notes)


@app.get("/api/hazards")
async def hazard_list(status: str | None = None, limit: int = 50) -> dict[str, object]:
    result = await toolbox_client.call_tool(
        "query_safety_cases",
        {"status": status, "limit": max(1, min(limit, 200))},
    )
    return {
        "ok": bool(result.get("ok")),
        "items": result.get("data", {}).get("items", []) if isinstance(result.get("data"), dict) else [],
        "tool_result": result,
    }


@app.post("/api/documents/revision-preview")
async def document_revision_preview(request: DocumentRevisionRequest) -> dict[str, object]:
    return await build_document_revision_preview(request)


@app.post("/api/forms/smart-draft")
async def smart_form_draft(request: SmartFormDraftRequest) -> dict[str, object]:
    return await build_smart_form_draft(request)


@app.get("/api/forms/templates")
async def form_templates(query: str | None = None, limit: int = 20) -> dict[str, object]:
    result = await toolbox_client.call_tool(
        "search_form_templates",
        {"query": query, "limit": max(1, min(limit, 100))},
    )
    return {
        "ok": bool(result.get("ok")),
        "items": result.get("data", {}).get("items", []) if isinstance(result.get("data"), dict) else [],
        "tool_result": result,
    }


@app.post("/api/forms/accept-draft")
async def smart_form_accept(request: SmartFormAcceptRequest) -> dict[str, object]:
    return await accept_smart_form_draft(request)


@app.post("/api/visual/patrol-draft")
async def visual_patrol_draft(request: VisualPatrolDraftRequest) -> dict[str, object]:
    return await build_visual_patrol_draft(request)


@app.post("/api/visual/confirm-candidate")
async def visual_patrol_confirm(request: VisualPatrolConfirmRequest) -> dict[str, object]:
    return await confirm_visual_patrol_candidate(request)


@app.post("/api/cases/rectification-notice")
async def case_rectification_notice(request: CaseWorkflowRequest) -> dict[str, object]:
    return await draft_rectification_notice(request)


@app.post("/api/cases/contractor-confirm")
async def case_contractor_confirm(request: CaseWorkflowRequest) -> dict[str, object]:
    return await confirm_contractor_assignment(request)


@app.post("/api/cases/close-review")
async def case_close_review(request: CaseWorkflowRequest) -> dict[str, object]:
    return await close_case_after_review(request)


@app.post("/api/cases/send-notification")
async def case_send_notification(request: NotificationSendRequest) -> dict[str, object]:
    return await send_rectification_notification(request)


@app.post("/api/reports/generate")
async def report_generate(request: ReportGenerateRequest) -> dict[str, object]:
    return await generate_report_file(request)


@app.post("/api/chat/message")
async def chat_message(request: ChatMessageRequest) -> dict[str, object]:
    response = await orchestrator.handle_message(request)
    return response.model_dump()


@app.post("/api/chat/card-action")
async def card_action(request: CardActionRequest) -> dict[str, object]:
    return await orchestrator.handle_card_action(request.action_id, request.card_data)


@app.post("/plan")
async def hybrid_plan(request: HybridPlanRequest) -> dict[str, object]:
    return await hybrid_orchestration_service.plan(
        session_id=request.session_id,
        user_input=request.user_input,
        prefer_codex=request.prefer_codex,
        metadata=request.metadata,
    )


@app.post("/confirm")
async def hybrid_confirm(request: HybridConfirmRequest) -> dict[str, object]:
    try:
        return hybrid_orchestration_service.confirm(
            session_id=request.session_id,
            plan_id=request.plan_id,
            action_ids=request.action_ids,
            confirmed_by=request.confirmed_by,
            notes=request.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/execute")
async def hybrid_execute(request: HybridExecuteRequest) -> dict[str, object]:
    try:
        return await hybrid_orchestration_service.execute(
            session_id=request.session_id,
            plan_id=request.plan_id,
            idempotency_key=request.idempotency_key,
            retry_failed_only=request.retry_failed_only,
            dry_run=request.dry_run,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/audit/event")
async def hybrid_audit_event(request: AuditEventRequest) -> dict[str, object]:
    return hybrid_orchestration_service.audit_event(
        event_type=request.event_type,
        payload=request.payload,
        session_id=request.session_id,
        plan_id=request.plan_id,
        action_id=request.action_id,
        status=request.status,
    )


@app.get("/plan/{plan_id}")
async def hybrid_get_plan(plan_id: str) -> dict[str, object]:
    try:
        return {"ok": True, "plan": hybrid_orchestration_service.get_plan(plan_id)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/whatsapp/search")
async def whatsapp_search_api(request: WhatsAppSearchApiRequest) -> dict[str, object]:
    result = await toolbox_client.call_tool(
        "whatsapp_search",
        {"q": request.q, "chat": request.chat, "limit": request.limit},
    )
    return result if isinstance(result, dict) else {"ok": False, "error": "unexpected_result"}


@app.post("/api/whatsapp/groups")
async def whatsapp_groups_api(request: WhatsAppGroupsApiRequest) -> dict[str, object]:
    result = await toolbox_client.call_tool(
        "list_whatsapp_groups",
        {"include_archived": request.include_archived},
    )
    return result if isinstance(result, dict) else {"ok": False, "error": "unexpected_result"}
