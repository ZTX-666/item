from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from ..config import settings
from ..models import ToolResult, ToolSpec


class WorkflowRunRequest(BaseModel):
    project_id: str = "default"
    requested_by: str = "safety_officer"
    source: str = "local_chatbox"
    trigger_payload: dict[str, Any] = Field(default_factory=dict)
    require_confirmation: bool = True
    dry_run: bool = False
    notes: str | None = None


class SupplementalToolRequest(BaseModel):
    project_id: str = "default"
    requested_by: str = "safety_officer"
    payload: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None
    dry_run: bool = True


class WorkflowCatalogRequest(BaseModel):
    category: str | None = None
    include_steps: bool = False


class WorkflowTemplateDetailRequest(BaseModel):
    workflow_name: str


class WorkflowActionConfirmRequest(BaseModel):
    workflow_run_id: int
    confirmation_key: str
    confirmed: bool
    confirmed_by: str = "safety_officer"
    notes: str | None = None


WORKFLOW_DEFINITIONS: dict[str, dict[str, Any]] = {
    "workflow_human_hazard_escalation": {
        "title": "人主动发起：疑似隐患取证与整改通知",
        "category": "human_initiated",
        "priority": "P0",
        "trigger": "安全主任发现分判商疑似不安全行为但证据不足。",
        "outputs": ["视觉证据", "制度条款依据", "整改通知或警告信草稿", "群组通知草稿", "闭环记录"],
        "confirmations": ["send_rectification_notice", "send_whatsapp_or_feishu_message", "close_case"],
        "steps": [
            {"agent": "center", "action": "创建工作流和候选隐患", "tool": "create_safety_case"},
            {"agent": "guardian", "action": "按区域调取摄像头截图并运行 VLM", "tool": "capture_camera_snapshot"},
            {"agent": "guardian", "action": "把 VLM 输出转成隐患候选", "tool": "ingest_vlm_hazards"},
            {"agent": "knowledge", "action": "检索公司制度和香港安全要求", "tool": "search_policy_clauses"},
            {"agent": "document", "action": "生成整改通知或警告信草稿", "tool": "generate_rectification_notice"},
            {"agent": "communication", "action": "生成待确认群组消息", "tool": "draft_group_message", "requires_confirmation": True},
            {"agent": "center", "action": "归档证据、消息和操作日志", "tool": "record_tool_audit"},
        ],
    },
    "workflow_external_risk_to_site_action": {
        "title": "系统主动预警：行业事故触发专项巡检",
        "category": "system_initiated",
        "priority": "P0",
        "trigger": "外部新闻、政府公告或行业事故命中地盘高风险关键词。",
        "outputs": ["行业事故风险摘要", "专项巡检任务", "VLM 检查提示词", "早会 Brief", "分判商通知"],
        "confirmations": ["send_special_briefing", "create_site_action"],
        "steps": [
            {"agent": "communication", "action": "抓取香港工伤及施工安全新闻", "tool": "fetch_hk_industrial_news"},
            {"agent": "knowledge", "action": "提炼风险点和制度依据", "tool": "summarize_external_risks"},
            {"agent": "center", "action": "把行业风险转为地盘事件", "tool": "create_platform_event"},
            {"agent": "guardian", "action": "生成专项检测提示词", "tool": "risk_to_detection_prompt"},
            {"agent": "guardian", "action": "安排摄像头专项巡检", "tool": "schedule_camera_patrol"},
            {"agent": "document", "action": "生成安全分析和早会 Brief", "tool": "toolbox_talk_generator"},
            {"agent": "communication", "action": "发送前生成确认卡", "tool": "feishu_build_safety_review_card", "requires_confirmation": True},
        ],
    },
    "workflow_daily_start_risk_briefing": {
        "title": "每日开工风险简报",
        "category": "daily_operation",
        "priority": "P0",
        "trigger": "每日开工前定时，或安全主任手动请求。",
        "outputs": ["天气风险", "外部风险摘要", "未关闭隐患", "今日检查重点", "早会稿"],
        "confirmations": ["send_daily_briefing"],
        "steps": [
            {"agent": "communication", "action": "抓取香港天文台预警", "tool": "fetch_hko_weather"},
            {"agent": "communication", "action": "抓取政府和媒体施工安全动态", "tool": "fetch_hk_safety_updates"},
            {"agent": "center", "action": "查询未关闭和逾期事项", "tool": "query_pending_actions"},
            {"agent": "document", "action": "生成每日风险简报", "tool": "draft_daily_risk_briefing"},
            {"agent": "communication", "action": "生成群组通知草稿", "tool": "draft_group_message", "requires_confirmation": True},
        ],
    },
    "workflow_daily_inspection_safety_diary": {
        "title": "每日巡查与安全日记",
        "category": "daily_operation",
        "priority": "P0",
        "trigger": "巡查输入、照片上传、摄像头巡检或群消息异常。",
        "outputs": ["每日巡查记录", "安全日记", "隐患清单", "整改建议"],
        "confirmations": ["escalate_serious_hazard", "send_notice"],
        "steps": [
            {"agent": "communication", "action": "抽取群组隐患线索", "tool": "ingest_chat_hazards"},
            {"agent": "guardian", "action": "运行视觉巡查", "tool": "run_vlm_detection_batch"},
            {"agent": "center", "action": "去重并关联隐患", "tool": "dedupe_and_link_hazards"},
            {"agent": "document", "action": "生成安全日记草稿", "tool": "safety_diary_drafter"},
            {"agent": "center", "action": "生成后续行动建议", "tool": "connect_hazard_actions"},
        ],
    },
    "workflow_safety_plan_monthly_self_check": {
        "title": "安全施工计划与每月自检报告",
        "category": "planning_reporting",
        "priority": "P1",
        "trigger": "每月、每三个月或新阶段施工前。",
        "outputs": ["安全施工计划", "每月自检报告", "高危工序时间表", "关注事项"],
        "confirmations": ["export_form_or_report"],
        "steps": [
            {"agent": "knowledge", "action": "检索安全施工计划模板", "tool": "search_form_templates"},
            {"agent": "center", "action": "汇总本期隐患和整改", "tool": "query_safety_cases"},
            {"agent": "document", "action": "预填制度表格字段", "tool": "prefill_form_fields"},
            {"agent": "document", "action": "生成 DOCX 草稿", "tool": "generate_docx_from_template", "requires_confirmation": True},
        ],
    },
    "workflow_digital_ptw_check": {
        "title": "数字化工作许可证 PTW 检查",
        "category": "high_risk_operation",
        "priority": "P1",
        "trigger": "高危作业计划、PTW 上传、许可证到期或现场巡查发现。",
        "outputs": ["PTW 缺口清单", "作业准入建议", "暂停/整改建议", "许可证台账更新"],
        "confirmations": ["suspend_work", "notify_contractor"],
        "steps": [
            {"agent": "knowledge", "action": "读取许可证和证书字段", "tool": "extract_certificate_fields"},
            {"agent": "knowledge", "action": "检查证书和许可证有效期", "tool": "check_certificate_expiry"},
            {"agent": "knowledge", "action": "执行 PTW 准入规则", "tool": "permit_to_work_checker"},
            {"agent": "center", "action": "更新 PTW 看板状态", "tool": "ptw_status_dashboard"},
            {"agent": "communication", "action": "生成缺失资料通知", "tool": "draft_group_message", "requires_confirmation": True},
        ],
    },
    "workflow_lifting_safety_patrol": {
        "title": "吊运专项智能巡检",
        "category": "high_risk_operation",
        "priority": "P0",
        "trigger": "吊运计划、吊运事故新闻、摄像头识别吊机或人工发起。",
        "outputs": ["吊运风险卡", "吊运检查表", "VLM 证据图", "整改通知"],
        "confirmations": ["pause_lifting_operation", "send_lifting_notice"],
        "steps": [
            {"agent": "knowledge", "action": "生成吊运专项提示词包", "tool": "lifting_detection_prompt_pack"},
            {"agent": "guardian", "action": "识别吊机、人员和警戒区", "tool": "evaluate_hazard_zone_rules"},
            {"agent": "knowledge", "action": "检索吊运制度和表格", "tool": "search_policy_clauses"},
            {"agent": "document", "action": "生成吊运 Brief 和整改通知", "tool": "generate_rectification_notice"},
            {"agent": "communication", "action": "发出专项提醒草稿", "tool": "draft_group_message", "requires_confirmation": True},
        ],
    },
    "workflow_scaffold_edge_work_at_height": {
        "title": "棚架、临边洞口和高处作业专项",
        "category": "high_risk_operation",
        "priority": "P1",
        "trigger": "棚架搭拆、高处作业计划、视觉异常或照片上传。",
        "outputs": ["棚架/高处检查清单", "视觉证据", "整改通知", "停工建议"],
        "confirmations": ["issue_stop_work_order", "send_notice"],
        "steps": [
            {"agent": "guardian", "action": "检测临边洞口和高处防护缺失", "tool": "edge_opening_detector_adapter"},
            {"agent": "knowledge", "action": "执行棚架检查规则", "tool": "scaffold_checklist_workflow"},
            {"agent": "center", "action": "创建或更新隐患案例", "tool": "create_case_from_vlm"},
            {"agent": "document", "action": "生成整改通知", "tool": "generate_rectification_notice", "requires_confirmation": True},
        ],
    },
    "workflow_mobile_plant_people_separation": {
        "title": "流动机械与人机分隔",
        "category": "high_risk_operation",
        "priority": "P1",
        "trigger": "机械进场、摄像头识别人机接近或外部机械事故预警。",
        "outputs": ["near-miss 线索", "隔离不足证据", "整改任务", "分判商扣分建议"],
        "confirmations": ["escalate_repeated_near_miss"],
        "steps": [
            {"agent": "guardian", "action": "判断人员和机械距离", "tool": "plant_person_distance_rule"},
            {"agent": "guardian", "action": "归一化视觉安全事件", "tool": "normalize_visual_safety_event"},
            {"agent": "center", "action": "创建隐患并记录分判商事件", "tool": "record_contractor_penalty"},
            {"agent": "communication", "action": "通知现场隔离整改", "tool": "draft_group_message", "requires_confirmation": True},
        ],
    },
    "workflow_confined_hot_electrical_work": {
        "title": "密闭空间、热工序和带电工程检查",
        "category": "high_risk_operation",
        "priority": "P1",
        "trigger": "密闭空间、热工序、带电工程 PTW 或作业前检查。",
        "outputs": ["作业准入清单", "许可证缺失提醒", "培训/监护要求", "整改通知"],
        "confirmations": ["permit_or_suspend_work"],
        "steps": [
            {"agent": "knowledge", "action": "执行密闭空间 PTW 检查", "tool": "confined_space_ptw_workflow"},
            {"agent": "knowledge", "action": "执行热工序 PTW 检查", "tool": "hot_work_ptw_workflow"},
            {"agent": "knowledge", "action": "执行带电工程 PTW 检查", "tool": "electrical_work_ptw_workflow"},
            {"agent": "document", "action": "生成作业检查表", "tool": "prefill_form_fields"},
            {"agent": "communication", "action": "发送缺口提醒", "tool": "draft_group_message", "requires_confirmation": True},
        ],
    },
    "workflow_certificate_equipment_qualification": {
        "title": "证书、设备和人员资格到期管理",
        "category": "asset_control",
        "priority": "P0",
        "trigger": "证书导入、设备进场、每日到期扫描。",
        "outputs": ["到期清单", "禁用提醒", "补交资料通知", "设备证书台账"],
        "confirmations": ["send_expiry_notice", "mark_equipment_inactive"],
        "steps": [
            {"agent": "knowledge", "action": "提取证书字段", "tool": "extract_certificate_fields"},
            {"agent": "center", "action": "写入证书台账", "tool": "upsert_certificate_record"},
            {"agent": "center", "action": "查询即将到期证书", "tool": "query_expiring_certificates"},
            {"agent": "document", "action": "生成证书到期通知", "tool": "generate_certificate_expiry_notice"},
            {"agent": "communication", "action": "发送催办草稿", "tool": "draft_group_message", "requires_confirmation": True},
        ],
    },
    "workflow_rectification_feedback_recheck": {
        "title": "整改反馈读取与视觉复查闭环",
        "category": "closure",
        "priority": "P0",
        "trigger": "分判商在 WhatsApp/飞书提交整改照片或说明。",
        "outputs": ["整改反馈摘要", "复查判断", "补交要求", "关闭建议"],
        "confirmations": ["close_case"],
        "steps": [
            {"agent": "communication", "action": "读取整改群组回复和附件", "tool": "read_rectification_replies"},
            {"agent": "center", "action": "登记整改证据", "tool": "add_case_evidence"},
            {"agent": "guardian", "action": "对比整改前后照片", "tool": "compare_vlm_before_after"},
            {"agent": "document", "action": "生成复查记录", "tool": "export_form_record"},
            {"agent": "center", "action": "关闭隐患或要求补交", "tool": "close_case_with_review", "requires_confirmation": True},
        ],
    },
    "workflow_incident_near_miss_investigation": {
        "title": "事故、工伤和近危事件调查",
        "category": "incident",
        "priority": "P1",
        "trigger": "工伤、近危、严重隐患或群组/媒体事件线索。",
        "outputs": ["事件时间线", "证据包", "原因分析", "整改措施", "调查报告"],
        "confirmations": ["submit_incident_report"],
        "steps": [
            {"agent": "center", "action": "创建平台事件", "tool": "create_platform_event"},
            {"agent": "communication", "action": "归档相关聊天和反馈", "tool": "extract_hazards_from_recent_chats"},
            {"agent": "center", "action": "生成事件时间线", "tool": "incident_timeline_builder"},
            {"agent": "center", "action": "打包证据", "tool": "create_evidence_bundle"},
            {"agent": "document", "action": "生成事故调查报告", "tool": "draft_incident_report", "requires_confirmation": True},
        ],
    },
    "workflow_stop_work_and_resume_review": {
        "title": "停工整改与复工复查",
        "category": "incident",
        "priority": "P1",
        "trigger": "严重不安全情况、重复违规、重大事件或近危事件。",
        "outputs": ["停工令草稿", "整改要求", "复查记录", "复工通知"],
        "confirmations": ["issue_stop_work_order", "approve_resume_work"],
        "steps": [
            {"agent": "knowledge", "action": "检索停工整改制度", "tool": "search_policy_clauses"},
            {"agent": "document", "action": "生成停工令草稿", "tool": "stop_work_order_generator", "requires_confirmation": True},
            {"agent": "communication", "action": "抄送分判商和地盘领导", "tool": "draft_group_message", "requires_confirmation": True},
            {"agent": "guardian", "action": "复工前现场复查", "tool": "run_vlm_detection_batch"},
            {"agent": "document", "action": "生成复工复查意见", "tool": "resume_work_review_workflow", "requires_confirmation": True},
        ],
    },
    "workflow_contractor_scoring_rewards_penalties": {
        "title": "分判商评分与奖惩管理",
        "category": "contractor_management",
        "priority": "P1",
        "trigger": "隐患关闭、重复违规、处罚、表扬或月度统计。",
        "outputs": ["分判商评分", "扣分原因", "奖惩草稿", "月度表现报告"],
        "confirmations": ["issue_penalty_or_reward"],
        "steps": [
            {"agent": "center", "action": "汇总分判商隐患和处罚事件", "tool": "query_safety_cases"},
            {"agent": "center", "action": "计算安全评分", "tool": "calculate_contractor_safety_score"},
            {"agent": "document", "action": "生成月度评分报告", "tool": "monthly_contractor_score_workflow"},
            {"agent": "communication", "action": "通知分判商和管理层", "tool": "draft_group_message", "requires_confirmation": True},
        ],
    },
    "workflow_training_toolbox_talk": {
        "title": "安全培训、早会和工具箱讲座",
        "category": "training",
        "priority": "P2",
        "trigger": "新工人入场、高危工序、事故教训、天气风险或专项检查。",
        "outputs": ["早会稿", "工具箱讲座", "培训海报文案", "培训记录"],
        "confirmations": ["send_training_material"],
        "steps": [
            {"agent": "knowledge", "action": "提炼制度和事故教训", "tool": "search_policy_clauses"},
            {"agent": "document", "action": "生成工具箱讲座和海报文案", "tool": "toolbox_talk_generator"},
            {"agent": "center", "action": "登记培训记录", "tool": "training_record_workflow"},
            {"agent": "communication", "action": "发送培训材料", "tool": "draft_group_message", "requires_confirmation": True},
        ],
    },
    "workflow_weather_emergency_response": {
        "title": "防风、防暑和恶劣天气应急",
        "category": "emergency",
        "priority": "P0",
        "trigger": "酷热、雷暴、暴雨、台风、山泥倾泻等天气预警。",
        "outputs": ["天气风险等级", "防风/防暑检查表", "停工/复工建议", "群组通知"],
        "confirmations": ["send_weather_action", "suspend_or_resume_work"],
        "steps": [
            {"agent": "communication", "action": "抓取香港天文台天气", "tool": "fetch_hko_weather"},
            {"agent": "knowledge", "action": "关联制度和表格", "tool": "link_external_risk_to_forms"},
            {"agent": "document", "action": "生成天气应急清单", "tool": "weather_emergency_workflow"},
            {"agent": "communication", "action": "发送天气和检查提醒", "tool": "draft_group_message", "requires_confirmation": True},
        ],
    },
    "workflow_environmental_permit_pollution_control": {
        "title": "环保牌照、噪音、废物和污染风险",
        "category": "environment",
        "priority": "P2",
        "trigger": "新开地盘、限制时间施工、环保资料到期、投诉或异常。",
        "outputs": ["环保许可清单", "环境巡查报告", "缺失提醒", "整改建议"],
        "confirmations": ["send_environment_notice", "export_environment_report"],
        "steps": [
            {"agent": "knowledge", "action": "登记环保牌照和许可要求", "tool": "environment_permit_register"},
            {"agent": "knowledge", "action": "检索环保制度条款", "tool": "search_policy_clauses"},
            {"agent": "document", "action": "生成环境巡查报告", "tool": "environment_inspection_report"},
            {"agent": "communication", "action": "通知责任人补交或整改", "tool": "draft_group_message", "requires_confirmation": True},
        ],
    },
    "workflow_policy_qa_form_filling": {
        "title": "制度问答与表格智能填报",
        "category": "document_form",
        "priority": "P0",
        "trigger": "安全主任询问制度、找表格或要求填表。",
        "outputs": ["制度答案", "条款引用", "表格推荐", "DOCX 草稿"],
        "confirmations": ["export_form"],
        "steps": [
            {"agent": "knowledge", "action": "检索制度条款", "tool": "search_policy_clauses"},
            {"agent": "document", "action": "搜索表格模板", "tool": "search_form_templates"},
            {"agent": "document", "action": "预填表格字段", "tool": "prefill_form_fields"},
            {"agent": "document", "action": "生成 DOCX 文件", "tool": "generate_docx_from_template", "requires_confirmation": True},
        ],
    },
    "workflow_weekly_monthly_dashboard_report": {
        "title": "周报、月报和管理看板",
        "category": "planning_reporting",
        "priority": "P1",
        "trigger": "每周/月定时，或管理层要求。",
        "outputs": ["安全周报/月报", "看板指标", "趋势分析", "下期关注事项"],
        "confirmations": ["send_management_report"],
        "steps": [
            {"agent": "center", "action": "查询看板指标", "tool": "get_dashboard_metrics"},
            {"agent": "center", "action": "查询外部风险和表格记录", "tool": "query_external_risks"},
            {"agent": "document", "action": "生成周报/月报", "tool": "draft_monthly_safety_report"},
            {"agent": "communication", "action": "发送报告草稿", "tool": "draft_group_message", "requires_confirmation": True},
        ],
    },
    "workflow_regulator_client_inspection_response": {
        "title": "劳工处、房屋署、业主或顾问检查应对",
        "category": "external_response",
        "priority": "P2",
        "trigger": "政府/业主信件、检查记录、顾问意见、RFI 或 Site Memo。",
        "outputs": ["回应草稿", "整改证据包", "后续跟进任务", "对外资料包"],
        "confirmations": ["send_external_response"],
        "steps": [
            {"agent": "knowledge", "action": "OCR 和分类来函", "tool": "classify_document_type"},
            {"agent": "center", "action": "查询相关案件和证据", "tool": "query_safety_cases"},
            {"agent": "document", "action": "生成监管/顾问回复草稿", "tool": "regulator_letter_response_workflow"},
            {"agent": "document", "action": "生成 RFI 或 Site Memo", "tool": "draft_site_memo", "requires_confirmation": True},
        ],
    },
    "workflow_safety_audit_hearing_package": {
        "title": "安全审计、复核和内部聆讯准备",
        "category": "audit_review",
        "priority": "P2",
        "trigger": "季度指标超标、重大事件、公司抽查、审计或内部聆讯。",
        "outputs": ["审计资料包", "聆讯材料", "趋势分析", "整改追踪表"],
        "confirmations": ["export_audit_package"],
        "steps": [
            {"agent": "center", "action": "创建审核任务", "tool": "create_review_task"},
            {"agent": "center", "action": "汇总整改和事故趋势", "tool": "get_dashboard_metrics"},
            {"agent": "document", "action": "生成审计资料包", "tool": "audit_package_generator"},
            {"agent": "communication", "action": "催收缺失材料", "tool": "draft_group_message", "requires_confirmation": True},
        ],
    },
    "workflow_chat_archive_hazard_mining": {
        "title": "聊天记录自动归档与隐患挖掘",
        "category": "data_intake",
        "priority": "P0",
        "trigger": "定时同步 WhatsApp/飞书消息或手动搜索。",
        "outputs": ["隐患候选", "附件证据", "消息摘要", "待确认案件"],
        "confirmations": ["promote_candidate_to_case"],
        "steps": [
            {"agent": "communication", "action": "解析飞书消息事件", "tool": "feishu_parse_message_event"},
            {"agent": "communication", "action": "搜索 WhatsApp 消息", "tool": "whatsapp_search"},
            {"agent": "center", "action": "抽取聊天隐患", "tool": "ingest_chat_hazards"},
            {"agent": "center", "action": "去重并关联证据", "tool": "dedupe_and_link_hazards"},
            {"agent": "center", "action": "人工确认分类反馈", "tool": "record_classification_feedback", "requires_confirmation": True},
        ],
    },
    "workflow_data_export_handover_knowledge": {
        "title": "数据导出、交接和知识沉淀",
        "category": "data_asset",
        "priority": "P2",
        "trigger": "项目阶段转换、人员交接、审计、管理复盘。",
        "outputs": ["数据导出包", "报告包", "证据包", "经验教训摘要"],
        "confirmations": ["export_sensitive_data"],
        "steps": [
            {"agent": "center", "action": "导出安全数据", "tool": "export_safety_data"},
            {"agent": "document", "action": "导出报告包", "tool": "export_report_package"},
            {"agent": "center", "action": "脱敏导出内容", "tool": "sanitize_llm_payload"},
            {"agent": "knowledge", "action": "沉淀经验知识摘要", "tool": "summarize_policy_document", "requires_confirmation": True},
        ],
    },
}


SUPPLEMENTAL_TOOL_DEFINITIONS: dict[str, dict[str, Any]] = {
    "risk_to_detection_prompt": {"agent": "guardian", "purpose": "把外部风险或制度风险转成 VLM/摄像头巡检提示词。"},
    "safety_diary_drafter": {"agent": "document", "purpose": "根据每日隐患、巡查和整改生成安全日记草稿。"},
    "permit_to_work_checker": {"agent": "knowledge", "purpose": "检查高危作业 PTW、证书、人员和作业条件是否齐备。"},
    "ptw_status_dashboard": {"agent": "center", "purpose": "维护工作许可证申请、批准、过期和暂停状态看板。"},
    "lifting_detection_prompt_pack": {"agent": "guardian", "purpose": "生成吊运专项视觉检测规则、关注对象和风险描述。"},
    "edge_opening_detector_adapter": {"agent": "guardian", "purpose": "识别临边、洞口、高处作业和防护缺失的视觉事件。"},
    "scaffold_checklist_workflow": {"agent": "knowledge", "purpose": "按棚架/工作平台制度生成检查清单和缺口。"},
    "plant_person_distance_rule": {"agent": "guardian", "purpose": "根据视觉检测判断流动机械与人员距离或隔离风险。"},
    "confined_space_ptw_workflow": {"agent": "knowledge", "purpose": "检查密闭空间 PTW、气体检测、通风、监护和救援要求。"},
    "hot_work_ptw_workflow": {"agent": "knowledge", "purpose": "检查热工序许可证、防火隔离、灭火器和火种监察要求。"},
    "electrical_work_ptw_workflow": {"agent": "knowledge", "purpose": "检查带电工程、临电、隔离上锁和合资格人员要求。"},
    "read_rectification_replies": {"agent": "communication", "purpose": "读取分判商整改回复、图片和附件并关联案件。"},
    "incident_timeline_builder": {"agent": "center", "purpose": "把聊天、照片、报告和操作日志整理成事故时间线。"},
    "stop_work_order_generator": {"agent": "document", "purpose": "生成局部/全面停工整改命令草稿。"},
    "resume_work_review_workflow": {"agent": "document", "purpose": "生成复工复查意见和复工通知草稿。"},
    "monthly_contractor_score_workflow": {"agent": "document", "purpose": "生成分判商月度安全评分报告和奖惩建议。"},
    "toolbox_talk_generator": {"agent": "document", "purpose": "生成早会、工具箱讲座、Brief 和海报文案。"},
    "training_record_workflow": {"agent": "center", "purpose": "登记培训主题、参与人、材料和签到记录。"},
    "weather_emergency_workflow": {"agent": "document", "purpose": "根据天气预警生成防暑、防风、暴雨和复工检查清单。"},
    "environment_permit_register": {"agent": "knowledge", "purpose": "登记环保牌照、噪音、废物、污水和限制时间施工许可。"},
    "environment_inspection_report": {"agent": "document", "purpose": "生成环境巡查报告、污染风险和整改建议。"},
    "regulator_letter_response_workflow": {"agent": "document", "purpose": "生成劳工处、业主、顾问或监管信件回复草稿。"},
    "audit_package_generator": {"agent": "document", "purpose": "生成安全审计、季度监控、内部聆讯资料包。"},
    "feishu_parse_message_event": {"agent": "communication", "purpose": "解析飞书消息事件、附件、发送人和群组上下文。"},
}


def list_workflow_templates(req: WorkflowCatalogRequest) -> ToolResult:
    workflows = []
    for name, definition in WORKFLOW_DEFINITIONS.items():
        if req.category and definition["category"] != req.category:
            continue
        item = {
            "name": name,
            "title": definition["title"],
            "category": definition["category"],
            "priority": definition["priority"],
            "trigger": definition["trigger"],
            "outputs": definition["outputs"],
            "confirmations": definition["confirmations"],
        }
        if req.include_steps:
            item["steps"] = definition["steps"]
        workflows.append(item)
    return _ok("list_workflow_templates", "Listed Chitung workflow templates.", {"workflows": workflows, "count": len(workflows)})


def get_workflow_template(req: WorkflowTemplateDetailRequest) -> ToolResult:
    definition = WORKFLOW_DEFINITIONS.get(req.workflow_name)
    if not definition:
        return ToolResult(ok=False, tool="get_workflow_template", summary="Unknown workflow template.", error=f"Unknown workflow: {req.workflow_name}")
    return _ok("get_workflow_template", "Loaded Chitung workflow template.", {"name": req.workflow_name, "definition": definition})


def confirm_workflow_action(req: WorkflowActionConfirmRequest) -> ToolResult:
    _ensure_schema()
    now = _now()
    with _connect() as conn:
        cursor = conn.execute(
            """
            UPDATE pending_confirmations
            SET status = ?, confirmed_by = ?, confirmed_at = ?, notes = ?
            WHERE workflow_run_id = ? AND confirmation_key = ?
            """,
            ("confirmed" if req.confirmed else "rejected", req.confirmed_by, now, req.notes, req.workflow_run_id, req.confirmation_key),
        )
        if cursor.rowcount == 0:
            return ToolResult(
                ok=False,
                tool="confirm_workflow_action",
                summary="No matching pending confirmation.",
                error=f"workflow_run_id={req.workflow_run_id}, confirmation_key={req.confirmation_key}",
            )
        conn.execute(
            "UPDATE workflow_runs SET updated_at = ? WHERE id = ?",
            (now, req.workflow_run_id),
        )
    return _ok(
        "confirm_workflow_action",
        "Updated workflow confirmation.",
        {"workflow_run_id": req.workflow_run_id, "confirmation_key": req.confirmation_key, "confirmed": req.confirmed},
    )


def run_workflow_tool(name: str, req: WorkflowRunRequest) -> ToolResult:
    definition = WORKFLOW_DEFINITIONS[name]
    _ensure_schema()
    now = _now()
    plan = _build_plan(name, definition, req)
    status = "planned" if req.dry_run else "ready_for_execution"
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO workflow_runs
            (workflow_name, title, category, priority, project_id, status, source, requested_by, trigger_payload_json, plan_json, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                definition["title"],
                definition["category"],
                definition["priority"],
                req.project_id,
                status,
                req.source,
                req.requested_by,
                _json(req.trigger_payload),
                _json(plan),
                req.notes,
                now,
                now,
            ),
        )
        workflow_run_id = int(cursor.lastrowid)
        for index, step in enumerate(definition["steps"], start=1):
            conn.execute(
                """
                INSERT INTO workflow_steps
                (workflow_run_id, step_index, agent, action, tool_name, status, requires_confirmation, payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    workflow_run_id,
                    index,
                    step["agent"],
                    step["action"],
                    step["tool"],
                    "pending",
                    1 if step.get("requires_confirmation") else 0,
                    _json({"trigger_payload": req.trigger_payload, "definition_step": step}),
                    now,
                    now,
                ),
            )
        confirmations = definition.get("confirmations", []) if req.require_confirmation else []
        for confirmation_key in confirmations:
            conn.execute(
                """
                INSERT INTO pending_confirmations
                (workflow_run_id, confirmation_key, action_type, status, payload_json, requested_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    workflow_run_id,
                    confirmation_key,
                    confirmation_key,
                    "pending",
                    _json({"workflow_name": name, "trigger_payload": req.trigger_payload}),
                    req.requested_by,
                    now,
                ),
            )
    data = {
        "workflow_run_id": workflow_run_id,
        "workflow_name": name,
        "status": status,
        "plan": plan,
        "pending_confirmations": confirmations,
    }
    return _ok(name, f"Created workflow run for {definition['title']}.", data)


def run_supplemental_tool(name: str, req: SupplementalToolRequest) -> ToolResult:
    definition = SUPPLEMENTAL_TOOL_DEFINITIONS[name]
    _ensure_schema()
    now = _now()
    output = {
        "tool_name": name,
        "agent": definition["agent"],
        "purpose": definition["purpose"],
        "project_id": req.project_id,
        "requested_by": req.requested_by,
        "payload": req.payload,
        "implementation_status": "reserved_api",
        "next_development_note": "Replace this placeholder with the real engine while preserving the input/output contract.",
    }
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO workflow_artifacts
            (workflow_run_id, artifact_type, name, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (None, "supplemental_tool_result", name, _json(output), now),
        )
    return _ok(name, f"Reserved supplemental workflow tool: {name}.", output)


def call_workflow_tool(name: str, arguments: dict[str, Any]) -> ToolResult:
    if name == "list_workflow_templates":
        return list_workflow_templates(WorkflowCatalogRequest(**arguments))
    if name == "get_workflow_template":
        return get_workflow_template(WorkflowTemplateDetailRequest(**arguments))
    if name == "confirm_workflow_action":
        return confirm_workflow_action(WorkflowActionConfirmRequest(**arguments))
    if name in WORKFLOW_DEFINITIONS:
        return run_workflow_tool(name, WorkflowRunRequest(**arguments))
    if name in SUPPLEMENTAL_TOOL_DEFINITIONS:
        return run_supplemental_tool(name, SupplementalToolRequest(**arguments))
    return ToolResult(ok=False, tool=name, summary="Unknown workflow tool.", error=f"Unknown workflow tool: {name}")


def workflow_tool_specs() -> list[ToolSpec]:
    specs = [
        ToolSpec(
            name="list_workflow_templates",
            description="List the reserved Chitung 24 workflow templates.",
            input_schema=WorkflowCatalogRequest.model_json_schema(),
        ),
        ToolSpec(
            name="get_workflow_template",
            description="Get one Chitung workflow template definition with steps, confirmations, and outputs.",
            input_schema=WorkflowTemplateDetailRequest.model_json_schema(),
        ),
        ToolSpec(
            name="confirm_workflow_action",
            description="Confirm or reject a pending workflow action such as sending a notice or closing a case.",
            input_schema=WorkflowActionConfirmRequest.model_json_schema(),
        ),
    ]
    for name, definition in WORKFLOW_DEFINITIONS.items():
        specs.append(
            ToolSpec(
                name=name,
                description=f"Chitung workflow template: {definition['title']}.",
                input_schema=WorkflowRunRequest.model_json_schema(),
            )
        )
    for name, definition in SUPPLEMENTAL_TOOL_DEFINITIONS.items():
        specs.append(
            ToolSpec(
                name=name,
                description=f"Supplemental reserved workflow tool for {definition['agent']}: {definition['purpose']}",
                input_schema=SupplementalToolRequest.model_json_schema(),
            )
        )
    return specs


WORKFLOW_TOOL_MODELS: dict[str, type[BaseModel]] = {
    "list_workflow_templates": WorkflowCatalogRequest,
    "get_workflow_template": WorkflowTemplateDetailRequest,
    "confirm_workflow_action": WorkflowActionConfirmRequest,
    **{name: WorkflowRunRequest for name in WORKFLOW_DEFINITIONS},
    **{name: SupplementalToolRequest for name in SUPPLEMENTAL_TOOL_DEFINITIONS},
}


def _build_plan(name: str, definition: dict[str, Any], req: WorkflowRunRequest) -> dict[str, Any]:
    tools = [step["tool"] for step in definition["steps"]]
    supplemental = [tool for tool in tools if tool in SUPPLEMENTAL_TOOL_DEFINITIONS]
    return {
        "workflow_name": name,
        "title": definition["title"],
        "category": definition["category"],
        "priority": definition["priority"],
        "trigger": definition["trigger"],
        "trigger_payload": req.trigger_payload,
        "agents": sorted({step["agent"] for step in definition["steps"]}),
        "steps": definition["steps"],
        "outputs": definition["outputs"],
        "confirmations": definition["confirmations"] if req.require_confirmation else [],
        "required_tools": tools,
        "supplemental_reserved_tools": supplemental,
        "execution_policy": {
            "dry_run": req.dry_run,
            "human_confirmation_required": req.require_confirmation,
            "no_external_send_without_confirmation": True,
            "local_audit_required": True,
        },
    }


def _ensure_schema() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS workflow_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_name TEXT NOT NULL,
                title TEXT NOT NULL,
                category TEXT,
                priority TEXT,
                project_id TEXT,
                status TEXT,
                source TEXT,
                requested_by TEXT,
                trigger_payload_json TEXT NOT NULL DEFAULT '{}',
                plan_json TEXT NOT NULL DEFAULT '{}',
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS workflow_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_run_id INTEGER NOT NULL,
                step_index INTEGER NOT NULL,
                agent TEXT,
                action TEXT,
                tool_name TEXT,
                status TEXT,
                requires_confirmation INTEGER NOT NULL DEFAULT 0,
                payload_json TEXT NOT NULL DEFAULT '{}',
                result_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS pending_confirmations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_run_id INTEGER NOT NULL,
                confirmation_key TEXT NOT NULL,
                action_type TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                payload_json TEXT NOT NULL DEFAULT '{}',
                requested_by TEXT,
                confirmed_by TEXT,
                confirmed_at TEXT,
                notes TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS agent_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_run_id INTEGER,
                from_agent TEXT,
                to_agent TEXT,
                message_type TEXT,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS workflow_artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_run_id INTEGER,
                artifact_type TEXT,
                name TEXT,
                file_path TEXT,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS workflow_event_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_run_id INTEGER NOT NULL,
                event_type TEXT,
                event_id TEXT,
                relation TEXT,
                created_at TEXT NOT NULL
            );
            """
        )


def _connect() -> sqlite3.Connection:
    settings.safety_database_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(settings.safety_database_path)


def _ok(tool: str, summary: str, data: dict[str, Any]) -> ToolResult:
    return ToolResult(ok=True, tool=tool, summary=summary, data=data)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
