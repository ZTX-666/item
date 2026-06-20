from __future__ import annotations

from chitung_center.models import IntentResult


RULES: list[tuple[str, list[str], list[str]]] = [
    ("hazard_intake", ["隐患", "整改", "事故", "工伤", "危险", "护栏", "吊运", "临边"], ["ingest_chat_hazards", "connect_hazard_actions"]),
    ("visual_detection", ["摄像头", "cctv", "rtmp", "vlm", "照片", "视频", "识别"], ["ingest_vlm_hazards"]),
    ("document_form", ["表格", "填表", "模板", "word", "docx", "闪闪文档", "报告", "检查表", "檢查表", "表单", "表單", "改文档", "替换", "潤色", "变更", "changeset", "docmate", "docx修改"], ["ai_archive_classifier"]),
    (
        "weather_news_risk",
        ["天气", "天文台", "暴雨", "酷热", "台风", "新闻", "舆情", "工伤意外"],
        ["fetch_hko_weather", "fetch_hk_safety_updates", "fetch_hk_industrial_news"],
    ),
    ("knowledge_query", ["制度", "规程", "办法", "要求", "安全管理"], ["ai_archive_classifier"]),
]


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
