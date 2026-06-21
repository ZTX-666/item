from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable


StepHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class WorkflowStepTemplate:
    name: str
    agent_name: str
    tool_name: str | None = None
    requires_confirmation: bool = False


@dataclass(frozen=True)
class WorkflowTemplate:
    workflow_name: str
    title: str
    description: str
    intent: str
    steps: list[WorkflowStepTemplate] = field(default_factory=list)


WORKFLOW_TEMPLATES: dict[str, WorkflowTemplate] = {
    "workflow_hazard_intake": WorkflowTemplate(
        workflow_name="workflow_hazard_intake",
        title="隐患线索 intake",
        description="聊天消息归档为隐患线索，并生成整改/表格后续动作卡片。",
        intent="hazard_intake",
        steps=[
            WorkflowStepTemplate("ingest_chat_hazards", "赤瞳守护者", "ingest_chat_hazards"),
            WorkflowStepTemplate("suggest_followups", "赤瞳守护者", None),
        ],
    ),
    "workflow_daily_risk_briefing": WorkflowTemplate(
        workflow_name="workflow_daily_risk_briefing",
        title="每日外部风险简报",
        description="抓取天气与官方安全更新，持久化并生成简报草稿。",
        intent="weather_news_risk",
        steps=[
            WorkflowStepTemplate("fetch_weather", "赤瞳守护者", "fetch_hko_weather"),
            WorkflowStepTemplate("fetch_updates", "赤瞳守护者", "fetch_hk_safety_updates"),
            WorkflowStepTemplate("persist_risks", "赤瞳守护者", "persist_external_risk_items"),
            WorkflowStepTemplate("draft_briefing", "赤瞳守护者", "draft_daily_risk_briefing"),
        ],
    ),
    "workflow_form_filling": WorkflowTemplate(
        workflow_name="workflow_form_filling",
        title="智能表格填报",
        description="搜索制度表格模板，为后续预填和 DOCX 草稿做准备。",
        intent="document_form",
        steps=[
            WorkflowStepTemplate("search_templates", "闪闪文档", "search_form_templates"),
        ],
    ),
    "workflow_knowledge_query": WorkflowTemplate(
        workflow_name="workflow_knowledge_query",
        title="制度条款检索",
        description="在本地制度文件中检索相关条款。",
        intent="knowledge_query",
        steps=[
            WorkflowStepTemplate("search_policy", "耀耀慧读", "search_policy_clauses"),
        ],
    ),
    "workflow_visual_patrol": WorkflowTemplate(
        workflow_name="workflow_visual_patrol",
        title="视觉巡检",
        description="RTMP 截图与 VLM/YOLO 检测（需环境就绪）。",
        intent="visual_detection",
        steps=[
            WorkflowStepTemplate("patrol_draft", "赤瞳守护者", None),
        ],
    ),
}


INTENT_TO_WORKFLOW: dict[str, str] = {
    "hazard_intake": "workflow_hazard_intake",
    "weather_news_risk": "workflow_daily_risk_briefing",
    "document_form": "workflow_form_filling",
    "knowledge_query": "workflow_knowledge_query",
    "visual_detection": "workflow_visual_patrol",
}


def list_workflow_templates() -> list[dict[str, Any]]:
    return [
        {
            "workflow_name": item.workflow_name,
            "title": item.title,
            "description": item.description,
            "intent": item.intent,
            "step_count": len(item.steps),
        }
        for item in WORKFLOW_TEMPLATES.values()
    ]


def workflow_for_intent(intent: str) -> WorkflowTemplate | None:
    workflow_name = INTENT_TO_WORKFLOW.get(intent)
    if not workflow_name:
        return None
    return WORKFLOW_TEMPLATES.get(workflow_name)
