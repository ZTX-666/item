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
    "workflow_weather_query": WorkflowTemplate(
        workflow_name="workflow_weather_query",
        title="香港天气查询",
        description="只查询香港天文台天气和现场安全提示，不生成外部风险简报。",
        intent="weather_query",
        steps=[
            WorkflowStepTemplate("fetch_weather", "赤瞳守护者", "fetch_hko_weather"),
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
    "workflow_docmate_edit": WorkflowTemplate(
        workflow_name="workflow_docmate_edit",
        title="DocMate 文档编辑",
        description="DocMate 作为独立 AI 助手处理 DOCX 上传、LLM 修改方案、预览、提交和重试。",
        intent="docmate_edit",
        steps=[
            WorkflowStepTemplate("docmate_read", "DocMate", "docmate_read_docx"),
            WorkflowStepTemplate("docmate_generate", "DocMate", "docmate_generate_changeset"),
            WorkflowStepTemplate("docmate_preview", "DocMate", "docmate_preview_changeset"),
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
    "workflow_whatsapp_sql_query": WorkflowTemplate(
        workflow_name="workflow_whatsapp_sql_query",
        title="WhatsApp SQLite 查询",
        description="读取本地 wacli.db 表结构和只读 SELECT 查询结果。",
        intent="whatsapp_sql_query",
        steps=[
            WorkflowStepTemplate("whatsapp_sql_read", "赤瞳灵讯", "whatsapp_sql_query"),
        ],
    ),
    "workflow_whatsapp_wacli_ops": WorkflowTemplate(
        workflow_name="workflow_whatsapp_wacli_ops",
        title="WhatsApp wacli 运维",
        description="执行安全只读 wacli 命令，用于登录状态、搜索、聊天、群组和存储诊断。",
        intent="whatsapp_wacli_ops",
        steps=[
            WorkflowStepTemplate("whatsapp_wacli_readonly", "赤瞳灵讯", "whatsapp_command_run"),
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
    "workflow_web_search": WorkflowTemplate(
        workflow_name="workflow_web_search",
        title="网页搜索",
        description="实时搜索互联网获取最新安全资讯与参考信息。",
        intent="web_search",
        steps=[
            WorkflowStepTemplate("web_search", "桌面助手", "web_search"),
        ],
    ),
    "workflow_url_fetch": WorkflowTemplate(
        workflow_name="workflow_url_fetch",
        title="网页内容抓取",
        description="抓取公开 URL 并提取正文或链接列表。",
        intent="url_fetch",
        steps=[
            WorkflowStepTemplate("fetch_url", "桌面助手", "fetch_url_content"),
        ],
    ),
    "workflow_run_bash": WorkflowTemplate(
        workflow_name="workflow_run_bash",
        title="Bash 命令执行",
        description="在 workspace 沙箱中执行 Bash/Shell 命令。",
        intent="run_bash",
        steps=[
            WorkflowStepTemplate("run_bash", "桌面助手", "run_bash_command", requires_confirmation=True),
        ],
    ),
    "workflow_run_powershell": WorkflowTemplate(
        workflow_name="workflow_run_powershell",
        title="PowerShell 命令执行",
        description="在 Windows 沙箱中执行 PowerShell 命令。",
        intent="run_powershell",
        steps=[
            WorkflowStepTemplate("run_powershell", "桌面助手", "run_powershell_command", requires_confirmation=True),
        ],
    ),
    "workflow_file_inspect": WorkflowTemplate(
        workflow_name="workflow_file_inspect",
        title="本地文件读取",
        description="读取 workspace 内代码、PDF、DOCX、Jupyter 等文件。",
        intent="file_inspect",
        steps=[
            WorkflowStepTemplate("read_file", "桌面助手", "read_local_file"),
        ],
    ),
    "workflow_desktop_assistant": WorkflowTemplate(
        workflow_name="workflow_desktop_assistant",
        title="桌面助手",
        description="根据用户描述自动选择搜索、抓取、读文件或运行命令。",
        intent="desktop_assistant",
        steps=[
            WorkflowStepTemplate("desktop_route", "桌面助手", None),
        ],
    ),
    "workflow_daily_safety_briefing_auto": WorkflowTemplate(
        workflow_name="workflow_daily_safety_briefing_auto",
        title="每日安全简报自动化",
        description="定时抓取外部讯息、汇总现场风险、生成每日安全简报草稿，并进入发送确认。",
        intent="automation_daily_safety_briefing",
        steps=[
            WorkflowStepTemplate("fetch_external_info", "耀耀慧读", "fetch_hk_safety_updates"),
            WorkflowStepTemplate("draft_briefing", "闪闪助手", "draft_daily_risk_briefing", requires_confirmation=True),
            WorkflowStepTemplate("confirm_delivery", "赤瞳中台", None, requires_confirmation=True),
        ],
    ),
    "workflow_p1_external_info_alert": WorkflowTemplate(
        workflow_name="workflow_p1_external_info_alert",
        title="P1 外部讯息提醒",
        description="外部讯息监听命中 P0/P1 时，生成待确认事项，人工确认后再通知负责人。",
        intent="automation_p1_external_info_alert",
        steps=[
            WorkflowStepTemplate("monitor_external_info", "耀耀慧读", "external_info_monitor"),
            WorkflowStepTemplate("create_confirmation", "赤瞳中台", "create_pending_confirmation", requires_confirmation=True),
            WorkflowStepTemplate("send_alert", "赤瞳中台", "send_feishu_card", requires_confirmation=True),
        ],
    ),
    "workflow_visual_patrol_closed_loop": WorkflowTemplate(
        workflow_name="workflow_visual_patrol_closed_loop",
        title="视觉巡检闭环",
        description="摄像头检测风险后生成隐患草稿、整改通知、复查任务和闭环确认。",
        intent="automation_visual_patrol_closed_loop",
        steps=[
            WorkflowStepTemplate("capture_and_detect", "赤瞳守护者", "vlm_detect"),
            WorkflowStepTemplate("draft_case", "赤瞳守护者", "build_visual_patrol_draft", requires_confirmation=True),
            WorkflowStepTemplate("assign_rectification", "赤瞳中台", "generate_rectification_notice", requires_confirmation=True),
            WorkflowStepTemplate("review_close", "赤瞳中台", "close_case_with_review", requires_confirmation=True),
        ],
    ),
    "workflow_whatsapp_risk_ingestion": WorkflowTemplate(
        workflow_name="workflow_whatsapp_risk_ingestion",
        title="WhatsApp 风险消息入库",
        description="持续读取 WhatsApp 本地归档，识别安全风险消息并转成隐患线索或待确认事项。",
        intent="automation_whatsapp_risk_ingestion",
        steps=[
            WorkflowStepTemplate("read_whatsapp_archive", "赤瞳聆讯", "whatsapp_sql_query"),
            WorkflowStepTemplate("classify_risk_message", "闪闪助手", None),
            WorkflowStepTemplate("create_hazard_or_confirmation", "赤瞳中台", "create_pending_confirmation", requires_confirmation=True),
        ],
    ),
    "workflow_industry_lifting_incident_response": WorkflowTemplate(
        workflow_name="workflow_industry_lifting_incident_response",
        title="业界吊运事故主动响应",
        description="外部吊运风险确认后，自动提炼检测提示词、摄像头专项巡检、生成检测报告与警示图文，并通过 wacli WhatsApp 待确认发送。",
        intent="industry_lifting_incident_response",
        steps=[
            WorkflowStepTemplate("search_policy", "耀耀慧读", "search_policy_clauses"),
            WorkflowStepTemplate("refine_prompt", "赤瞳守护者", "refine_detection_prompt"),
            WorkflowStepTemplate("patrol_cameras", "赤瞳守护者", "workbench_video_detection"),
            WorkflowStepTemplate("create_case", "赤瞳中台", "create_safety_case"),
            WorkflowStepTemplate("generate_alert_bundle", "闪闪助手", "generate_safety_alert_bundle"),
            WorkflowStepTemplate("rectification_notice", "赤瞳中台", "generate_rectification_notice", requires_confirmation=True),
            WorkflowStepTemplate("notify_whatsapp", "赤瞳灵讯", "send_whatsapp_message", requires_confirmation=True),
        ],
    ),
    "workflow_lifting_safety_patrol": WorkflowTemplate(
        workflow_name="workflow_lifting_safety_patrol",
        title="吊运专项智能巡检",
        description="吊运计划、吊运事故新闻或人工发起时的专项视觉巡检与警示材料生成（与业界事故主动响应共用引擎）。",
        intent="lifting_safety_patrol",
        steps=[
            WorkflowStepTemplate("search_policy", "耀耀慧读", "search_policy_clauses"),
            WorkflowStepTemplate("patrol_cameras", "赤瞳守护者", "workbench_video_detection"),
            WorkflowStepTemplate("generate_alert_bundle", "闪闪助手", "generate_safety_alert_bundle"),
            WorkflowStepTemplate("notify_whatsapp", "赤瞳灵讯", "send_whatsapp_message", requires_confirmation=True),
        ],
    ),
}


INTENT_TO_WORKFLOW: dict[str, str] = {
    "hazard_intake": "workflow_hazard_intake",
    "weather_query": "workflow_weather_query",
    "weather_news_risk": "workflow_daily_risk_briefing",
    "document_form": "workflow_form_filling",
    "docmate_edit": "workflow_docmate_edit",
    "knowledge_query": "workflow_knowledge_query",
    "whatsapp_sql_query": "workflow_whatsapp_sql_query",
    "whatsapp_wacli_ops": "workflow_whatsapp_wacli_ops",
    "visual_detection": "workflow_visual_patrol",
    "web_search": "workflow_web_search",
    "url_fetch": "workflow_url_fetch",
    "run_bash": "workflow_run_bash",
    "run_powershell": "workflow_run_powershell",
    "file_inspect": "workflow_file_inspect",
    "desktop_assistant": "workflow_desktop_assistant",
    "industry_lifting_incident_response": "workflow_industry_lifting_incident_response",
    "lifting_safety_patrol": "workflow_lifting_safety_patrol",
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
