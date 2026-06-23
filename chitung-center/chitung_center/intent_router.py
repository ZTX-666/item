from __future__ import annotations

import json
from typing import Any

from chitung_center.config import settings
from chitung_center.llm_gateway import llm_gateway
from chitung_center.models import IntentResult
from chitung_center.skills import skill_loader


RULES: list[tuple[str, list[str], list[str]]] = [
    (
        "whatsapp_sql_query",
        ["whatsapp", "wa", "wacli.db", "sqlite", "sql", "数据库", "本地库", "数据表", "表名"],
        ["whatsapp_sql_tables", "whatsapp_sql_query"],
    ),
    (
        "whatsapp_wacli_ops",
        ["whatsapp", "wa", "wacli", "登录状态", "认证状态", "消息搜索", "搜消息", "发", "发消息", "发送", "回复", "转发", "删除", "退出登录", "send", "聊天列表", "群组", "联系人", "星标", "通话", "存储统计"],
        ["whatsapp_command_run"],
    ),
    (
        "docmate_edit",
        ["docmate", "闪闪文档", "docx", "word", "改文档", "修改文档", "改报告", "润色", "潤色", "替换", "变更", "changeset", "docx修改", "修改预览"],
        ["docmate_read_docx", "docmate_generate_changeset", "docmate_preview_changeset"],
    ),
    ("hazard_intake", ["隐患", "整改", "事故", "工伤", "危险", "护栏", "吊运", "临边"], ["ingest_chat_hazards", "connect_hazard_actions"]),
    ("visual_detection", ["摄像头", "cctv", "rtmp", "vlm", "照片", "视频", "识别"], ["ingest_vlm_hazards"]),
    ("document_form", ["表格", "填表", "模板", "报告", "检查表", "檢查表", "表单", "表單"], ["search_form_templates"]),
    ("weather_query", ["天气", "天文台", "weather"], ["fetch_hko_weather"]),
    (
        "weather_news_risk",
        ["天气", "天文台", "暴雨", "酷热", "台风", "新闻", "舆情", "工伤意外", "外部风险", "外部", "外面", "预警", "简报"],
        ["fetch_hko_weather", "fetch_hk_safety_updates", "fetch_hk_industrial_news"],
    ),
    ("knowledge_query", ["制度", "规程", "办法", "要求", "安全管理"], ["search_policy_clauses"]),
    ("external_info_monitor", ["外部讯息", "外部信息", "外部讯息监听", "外部信息监听", "监听外部"], ["external_info_monitor"]),
    ("long_term_memory", ["长期记忆", "長期記憶", "记住今天", "总结今日对话", "總結今日對話"], ["long_term_memory_summarize_today"]),
]

INTENT_TOOL_DEFAULTS: dict[str, list[str]] = {name: tools for name, _keywords, tools in RULES} | {"general_chat": []}
ALLOWED_INTENTS = set(INTENT_TOOL_DEFAULTS)


def route_intent(message: str) -> IntentResult:
    if _is_plain_weather_question(message):
        return IntentResult(
            intent="weather_query",
            confidence=0.78,
            reason="Plain weather query matched weather terms without briefing or risk intent.",
            suggested_tools=INTENT_TOOL_DEFAULTS["weather_query"],
        )

    lowered = message.lower()
    best_name = "general_chat"
    best_hits: list[str] = []
    best_tools: list[str] = []

    for name, keywords, tools in RULES:
        hits = [keyword for keyword in keywords if keyword.lower() in lowered]
        form_requested = any(term in lowered for term in ["表格", "填表", "模板", "检查表", "檢查表", "表单", "表單"])
        if len(hits) > len(best_hits) or (len(hits) == len(best_hits) and name == "document_form" and form_requested):
            best_name = name
            best_hits = hits
            best_tools = tools

    if not best_hits:
        skill_route = skill_loader.resolve_route(message)
        if skill_route and skill_route.intent in ALLOWED_INTENTS:
            return IntentResult(
                intent=skill_route.intent,  # type: ignore[arg-type]
                confidence=skill_route.confidence,
                reason=skill_route.reason,
                suggested_tools=INTENT_TOOL_DEFAULTS.get(skill_route.intent, []),
            )
        return IntentResult(
            intent="general_chat",
            confidence=0.35,
            reason="No strong rule matched.",
            suggested_tools=[],
        )

    confidence = min(0.9, 0.45 + 0.12 * len(best_hits))
    return IntentResult(
        intent=best_name,  # type: ignore[arg-type]
        confidence=confidence,
        reason=f"Matched keywords: {', '.join(best_hits)}",
        suggested_tools=best_tools,
    )


async def route_intent_with_llm(message: str, *, hint_intent: str | None = None) -> IntentResult:
    if hint_intent and hint_intent in ALLOWED_INTENTS:
        return IntentResult(
            intent=hint_intent,  # type: ignore[arg-type]
            confidence=0.93,
            reason=f"Skill 路由指定 intent：{hint_intent}",
            suggested_tools=INTENT_TOOL_DEFAULTS.get(hint_intent, []),
        )

    fallback = route_intent(message)
    if fallback.intent == "weather_query":
        return fallback
    if not settings.llm_configured:
        return fallback

    try:
        raw = await llm_gateway.complete_json(_router_system_prompt(), message)
        parsed = _extract_llm_json(raw)
        intent_name = str(parsed.get("intent") or "").strip()
        if intent_name not in ALLOWED_INTENTS:
            raise ValueError(f"unsupported intent: {intent_name}")
        confidence = float(parsed.get("confidence", fallback.confidence))
        suggested_tools = _validated_tools(intent_name, parsed.get("suggested_tools"))
        reason = str(parsed.get("reason") or "LLM intent routing.")
        return IntentResult(
            intent=intent_name,  # type: ignore[arg-type]
            confidence=max(0.0, min(confidence, 0.95)),
            reason=reason,
            suggested_tools=suggested_tools,
        )
    except Exception as exc:  # noqa: BLE001
        return IntentResult(
            intent=fallback.intent,
            confidence=fallback.confidence,
            reason=f"{fallback.reason} LLM routing failed: {exc}",
            suggested_tools=fallback.suggested_tools,
        )


def _router_system_prompt() -> str:
    catalog = skill_loader.routing_catalog_for_llm(enabled_only=True)
    schema = {
        "allowed_intents": sorted(ALLOWED_INTENTS),
        "intent_meanings": {
            "hazard_intake": "隐患、事故、整改、现场安全问题入库和闭环",
            "visual_detection": "摄像头、CCTV、图片、视频、视觉巡检、VLM/YOLO 识别",
            "document_form": "表格、报告、模板、智能填表和文档处理",
            "weather_query": "只查询香港当前天气或天文台提示，不生成外部风险简报",
            "weather_news_risk": "外部风险、新闻舆情、监管安全更新、天气风险汇总和每日简报",
            "knowledge_query": "制度、规程、条款、管理要求、RAG 问答",
            "docmate_edit": "DocMate/闪闪文档作为 AI 助手处理 DOCX 上传、修改方案、预览、提交和重试",
            "whatsapp_sql_query": "WhatsApp 本地 SQLite/wacli.db 数据库、表名和只读 SQL 查询",
            "whatsapp_wacli_ops": "WhatsApp wacli 只读命令、登录状态、消息搜索、聊天/群组/联系人诊断",
            "external_info_monitor": "外部讯息监听：关键词、来源、频率、立即监听",
            "long_term_memory": "总结今日对话并写入长期记忆 Markdown",
            "general_chat": "闲聊、无法归类、需要澄清的问题",
        },
        "skill_catalog": catalog,
        "routing_rules": [
            "优先根据用户自然语言选择最匹配的 intent。",
            "若用户明确提到某个 Skill 名称、display_name 或 example_prompts 的场景，优先选对应 intent。",
            "只问当前天气时不要选 weather_news_risk。",
            "DocMate/docx 文档润色选 docmate_edit；表格模板填表选 document_form。",
        ],
        "output_schema": {
            "intent": "one allowed intent",
            "confidence": "0 to 1",
            "reason": "short Chinese reason",
            "suggested_tools": "array of known tool names",
        },
    }
    return (
        "你是赤瞳中台的意图路由器。只返回 JSON object，不要 Markdown。"
        "你只能选择 allowed_intents 里的 intent；工具只能从候选工作流工具中选择。"
        "skill_catalog 列出了每个内置 Skill 的描述、触发词和示例说法，请结合它们理解自然语言。"
        f"\n{json.dumps(schema, ensure_ascii=False)}"
    )


def _extract_llm_json(raw: dict[str, Any]) -> dict[str, Any]:
    if "intent" in raw:
        return raw
    choices = raw.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else {}
        content = message.get("content") if isinstance(message, dict) else ""
        if isinstance(content, str):
            return json.loads(content)
    raise ValueError("model did not return routable JSON")


def _validated_tools(intent_name: str, value: Any) -> list[str]:
    defaults = INTENT_TOOL_DEFAULTS.get(intent_name, [])
    if not isinstance(value, list):
        return defaults
    allowed = set(defaults)
    return [str(item) for item in value if str(item) in allowed] or defaults


def _is_plain_weather_question(message: str) -> bool:
    normalized = message.lower().replace(" ", "")
    if not any(token in normalized for token in ["天气", "天文台", "weather"]):
        return False
    return not any(token in normalized for token in ["简报", "舆情", "新闻", "风险", "监管", "工伤", "报告", "生成", "预警", "外部", "外面"])
