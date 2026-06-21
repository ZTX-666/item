from __future__ import annotations

import json
from typing import Any

from chitung_center.config import settings
from chitung_center.llm_gateway import llm_gateway
from chitung_center.models import IntentResult


RULES: list[tuple[str, list[str], list[str]]] = [
    ("hazard_intake", ["隐患", "整改", "事故", "工伤", "危险", "护栏", "吊运", "临边"], ["ingest_chat_hazards", "connect_hazard_actions"]),
    ("visual_detection", ["摄像头", "cctv", "rtmp", "vlm", "照片", "视频", "识别"], ["ingest_vlm_hazards"]),
    ("document_form", ["表格", "填表", "模板", "word", "docx", "闪闪文档", "报告", "检查表", "檢查表", "表单", "表單", "改文档", "替换", "潤色", "变更", "changeset", "docmate", "docx修改"], ["ai_archive_classifier"]),
    (
        "weather_news_risk",
        ["天气", "天文台", "暴雨", "酷热", "台风", "新闻", "舆情", "工伤意外", "外部风险", "外部", "外面", "预警", "简报"],
        ["fetch_hko_weather", "fetch_hk_safety_updates", "fetch_hk_industrial_news"],
    ),
    ("knowledge_query", ["制度", "规程", "办法", "要求", "安全管理"], ["search_policy_clauses"]),
]

INTENT_TOOL_DEFAULTS: dict[str, list[str]] = {name: tools for name, _keywords, tools in RULES} | {"general_chat": []}
ALLOWED_INTENTS = set(INTENT_TOOL_DEFAULTS)


def route_intent(message: str) -> IntentResult:
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


async def route_intent_with_llm(message: str) -> IntentResult:
    fallback = route_intent(message)
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
    schema = {
        "allowed_intents": sorted(ALLOWED_INTENTS),
        "intent_meanings": {
            "hazard_intake": "隐患、事故、整改、现场安全问题入库和闭环",
            "visual_detection": "摄像头、CCTV、图片、视频、视觉巡检、VLM/YOLO 识别",
            "document_form": "表格、报告、DOCX、模板、智能填表和文档处理",
            "weather_news_risk": "香港天气、外部风险、新闻舆情、监管安全更新、每日简报",
            "knowledge_query": "制度、规程、条款、管理要求、RAG 问答",
            "general_chat": "闲聊、无法归类、需要澄清的问题",
        },
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
