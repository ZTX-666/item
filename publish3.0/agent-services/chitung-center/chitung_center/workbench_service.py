from __future__ import annotations

from typing import Any

from chitung_center.config import settings
from chitung_center.toolbox_client import toolbox_client


async def build_workbench_summary() -> dict[str, Any]:
    toolbox_health = await toolbox_client.health()
    toolbox_ready = _required_toolbox_ready(toolbox_health)
    metrics_result = await _call_tool("get_dashboard_metrics", {"include_samples": True})
    cases_result = await _call_tool("query_pending_actions", {"limit": 6})

    metrics_data = _tool_data(metrics_result)
    cases = _items(cases_result)
    sample_cases = _items(metrics_data.get("samples", {}).get("recent_cases", {}))
    if not cases:
        cases = sample_cases

    return {
        "status": {
            "center_ok": True,
            "toolbox_ok": toolbox_ready,
            "toolbox_base_url": settings.agent_toolbox_base_url,
            "llm_configured": settings.llm_configured,
        },
        "metrics": _build_metrics(metrics_data.get("metrics", {}), cases),
        "hazards": [_hazard_from_case(row) for row in cases[:5]],
        "activities": _build_activities(cases, metrics_data),
        "workflow_steps": [
            {"id": "intent", "label": "识别意图", "status": "done"},
            {"id": "tool", "label": "调用工具", "status": "pending" if toolbox_ready else "active"},
            {"id": "confirm", "label": "等待确认", "status": "pending"},
        ],
    }


async def update_hazard_status(case_id: int, status: str, notes: str | None = None) -> dict[str, Any]:
    result = await toolbox_client.call_tool(
        "update_safety_case_status",
        {"case_id": case_id, "status": status, "notes": notes},
    )
    return {
        "ok": bool(result.get("ok")),
        "case_id": case_id,
        "status": status,
        "tool_result": result,
    }


async def _call_tool(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return await toolbox_client.call_tool(tool_name, payload)
    except Exception as exc:  # noqa: BLE001 - desktop summary should stay available offline.
        return {"ok": False, "tool": tool_name, "data": {}, "error": str(exc)}


def _tool_data(result: dict[str, Any]) -> dict[str, Any]:
    data = result.get("data")
    return data if isinstance(data, dict) else {}


def _required_toolbox_ready(toolbox_health: dict[str, Any]) -> bool:
    checks = toolbox_health.get("tools")
    if not isinstance(checks, dict):
        return False
    required = [
        "rtmp_snapshot",
        "vlm_detect",
        "generate_report",
        "safety_policy_templates",
        "safety_platform_database",
    ]
    return all(bool(checks.get(name, {}).get("available")) for name in required)


def _items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        raw_items = value.get("items", [])
    else:
        raw_items = value
    return [item for item in raw_items if isinstance(item, dict)] if isinstance(raw_items, list) else []


def _build_metrics(metrics: dict[str, Any], cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_status = _dict(metrics.get("safety_cases_by_status"))
    by_risk = _dict(metrics.get("safety_cases_by_risk"))
    form_status = _dict(metrics.get("form_records_by_status"))
    external_risk = _dict(metrics.get("external_risks_by_risk"))

    open_count = sum(count for status, count in by_status.items() if status not in {"closed", "resolved", "done"})
    high_count = by_risk.get("high", 0) + by_risk.get("critical", 0)
    pending_count = len(cases) if cases else open_count

    return [
        {"id": "open", "label": "未闭环隐患", "value": open_count, "tone": "red", "helper": f"{pending_count} 条待处理"},
        {"id": "high", "label": "高风险隐患", "value": high_count, "tone": "orange", "helper": "优先人工确认"},
        {"id": "forms", "label": "表格记录", "value": sum(form_status.values()), "tone": "blue", "helper": "来自本地台账"},
        {"id": "external", "label": "外部风险", "value": sum(external_risk.values()), "tone": "orange", "helper": "天气/新闻/监管"},
        {"id": "llm", "label": "大模型网关", "value": "已配置" if settings.llm_configured else "未配置", "tone": "green" if settings.llm_configured else "gray", "helper": "统一走中台"},
    ]


def _build_activities(cases: list[dict[str, Any]], metrics_data: dict[str, Any]) -> list[dict[str, Any]]:
    activities = []
    for row in cases[:4]:
        case_id = str(row.get("case_id") or row.get("id") or "CASE")
        title = str(row.get("title") or row.get("summary") or row.get("description") or "待处理安全事项")
        activities.append(
            {
                "id": f"case-{case_id}",
                "time": _short_time(row.get("updated_at") or row.get("created_at")),
                "title": title,
                "description": f"{_risk_text(row.get('risk_level'))} · {row.get('status') or '待确认'}",
                "actionLabel": "查看详情",
            }
        )

    recent_risks = _items(metrics_data.get("samples", {}).get("recent_external_risks", {}))
    for row in recent_risks[:2]:
        risk_id = str(row.get("id") or row.get("source") or "risk")
        activities.append(
            {
                "id": f"risk-{risk_id}",
                "time": _short_time(row.get("last_seen_at") or row.get("created_at")),
                "title": str(row.get("title") or "外部风险更新"),
                "description": str(row.get("source") or row.get("summary") or "已进入风险监测"),
                "actionLabel": "生成简报",
            }
        )

    if activities:
        return activities

    return [
        {
            "id": "empty",
            "time": "--:--",
            "title": "工作台已就绪",
            "description": "启动 AgentToolbox 后会显示真实隐患、表格和外部风险动态。",
        }
    ]


def _hazard_from_case(row: dict[str, Any]) -> dict[str, Any]:
    case_id = str(row.get("case_id") or row.get("id") or "CASE")
    return {
        "id": case_id,
        "title": str(row.get("title") or row.get("summary") or row.get("description") or "未命名隐患"),
        "area": str(row.get("area") or row.get("scene") or row.get("location") or "未分区"),
        "riskLevel": _risk_level(row.get("risk_level")),
        "status": str(row.get("status") or "待确认"),
        "dueText": str(row.get("due_at") or row.get("deadline") or "待排期"),
    }


def _dict(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, int] = {}
    for key, raw_count in value.items():
        try:
            result[str(key)] = int(raw_count)
        except (TypeError, ValueError):
            result[str(key)] = 0
    return result


def _risk_level(value: Any) -> str:
    normalized = str(value or "").lower()
    if normalized in {"low", "medium", "high", "critical"}:
        return normalized
    return "medium"


def _risk_text(value: Any) -> str:
    return {
        "low": "低风险",
        "medium": "中风险",
        "high": "高风险",
        "critical": "重大风险",
    }.get(_risk_level(value), "中风险")


def _short_time(value: Any) -> str:
    text = str(value or "")
    if "T" in text:
        text = text.split("T", 1)[1]
    if " " in text:
        text = text.rsplit(" ", 1)[-1]
    return text[:5] if len(text) >= 5 else "--:--"
