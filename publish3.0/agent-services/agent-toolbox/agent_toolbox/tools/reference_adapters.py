from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from ..models import ToolResult


REFERENCE_ADAPTERS = [
    {
        "name": "mcp_construction_tool_map",
        "reference_project": "MCP-construction",
        "purpose": "Map construction-agent tool ideas to Chitung/AgentToolbox tools.",
        "status": "interface_ready",
    },
    {
        "name": "visual_safety_event_normalizer",
        "reference_project": "HazardLens / Construction-PPE-Detection / SafetyVision",
        "purpose": "Normalize PPE, restricted-zone, near-miss, and fall events into one safety-event shape.",
        "status": "interface_ready",
    },
    {
        "name": "hazard_zone_rule_engine",
        "reference_project": "Construction-Hazard-Detection",
        "purpose": "Evaluate restricted-area and person-equipment proximity rules.",
        "status": "rule_baseline_ready",
    },
    {
        "name": "visual_safety_pipeline_recommender",
        "reference_project": "HazardLens / Construction-PPE-Detection / SentinelVision",
        "purpose": "Recommend a future visual-safety implementation path by scenario.",
        "status": "interface_ready",
    },
    {
        "name": "safety_report_from_events",
        "reference_project": "SafetyVision",
        "purpose": "Draft a safety report from normalized visual and external risk events.",
        "status": "rule_baseline_ready",
    },
]

CONSTRUCTION_TOOL_MAP = {
    "rfi": ["draft_group_message", "export_form_record", "search_policy_clauses"],
    "daily_report": ["draft_daily_risk_briefing", "query_safety_cases", "query_external_risks"],
    "change_order": ["create_safety_case", "generate_warning_letter", "export_safety_data"],
    "safety_incident": ["create_safety_case", "add_case_evidence", "generate_rectification_notice"],
    "inspection": ["search_form_templates", "prefill_form_fields", "generate_docx_from_template"],
    "subcontractor": ["query_safety_cases", "get_dashboard_metrics"],
    "schedule_risk": ["fetch_hko_weather", "draft_daily_risk_briefing"],
}


class ReferenceAdapterListRequest(BaseModel):
    pass


class ConstructionToolMapRequest(BaseModel):
    workflow: str
    include_schema_hint: bool = True


class VisualSafetyEventNormalizeRequest(BaseModel):
    source_project: str = "generic"
    camera_id: str | None = None
    image_path: str | None = None
    timestamp: str | None = None
    detections: list[dict[str, Any]] = Field(default_factory=list)
    raw_event: dict[str, Any] = Field(default_factory=dict)


class HazardZoneRuleRequest(BaseModel):
    persons: list[dict[str, Any]] = Field(default_factory=list)
    equipment: list[dict[str, Any]] = Field(default_factory=list)
    restricted_zones: list[dict[str, Any]] = Field(default_factory=list)
    min_person_equipment_distance: float = 80.0
    coordinate_unit: str = "pixel"


class VisualPipelineRecommendRequest(BaseModel):
    scenario: Literal["ppe", "restricted_zone", "near_miss", "fall_detection", "multi_camera", "reporting"] = "ppe"
    deployment: Literal["local", "server", "edge_camera"] = "local"
    priority: Literal["fast_mvp", "low_false_alarm", "production"] = "fast_mvp"


class SafetyReportFromEventsRequest(BaseModel):
    events: list[dict[str, Any]] = Field(default_factory=list)
    project_name: str | None = None
    report_type: str = "visual_safety"
    include_recommendations: bool = True


def list_reference_adapters(req: ReferenceAdapterListRequest) -> ToolResult:
    del req
    return ToolResult(
        ok=True,
        tool="list_reference_adapters",
        summary=f"Returned {len(REFERENCE_ADAPTERS)} reference adapters.",
        data={"items": REFERENCE_ADAPTERS},
    )


def map_mcp_construction_tool(req: ConstructionToolMapRequest) -> ToolResult:
    workflow = req.workflow.lower().strip()
    tools = CONSTRUCTION_TOOL_MAP.get(workflow)
    if tools is None:
        tools = _guess_workflow_tools(workflow)
    schema_hint = {
        "workflow": workflow,
        "platform_tools": tools,
        "recommended_flow": " -> ".join(tools),
        "requires_human_confirmation": any(tool in tools for tool in ["draft_group_message", "generate_warning_letter", "generate_rectification_notice"]),
    }
    return ToolResult(
        ok=True,
        tool="map_mcp_construction_tool",
        summary=f"Mapped workflow {workflow} to {len(tools)} platform tools.",
        data=schema_hint if req.include_schema_hint else {"platform_tools": tools},
    )


def normalize_visual_safety_event(req: VisualSafetyEventNormalizeRequest) -> ToolResult:
    labels = [_label(det) for det in req.detections]
    violations = _visual_violations(labels, req.raw_event)
    risk_level = "high" if any(v["risk_level"] == "high" for v in violations) else "medium" if violations else "low"
    event = {
        "source_project": req.source_project,
        "camera_id": req.camera_id,
        "image_path": req.image_path,
        "timestamp": req.timestamp or _now(),
        "event_type": "visual_safety",
        "risk_level": risk_level,
        "violations": violations,
        "labels": labels,
        "raw_event": req.raw_event,
    }
    return ToolResult(
        ok=True,
        tool="normalize_visual_safety_event",
        summary=f"Normalized visual event with {len(violations)} violations.",
        data={"event": event, "case_candidate": _case_candidate_from_event(event)},
    )


def evaluate_hazard_zone_rules(req: HazardZoneRuleRequest) -> ToolResult:
    violations: list[dict[str, Any]] = []
    for person in req.persons:
        point = _center(person)
        for zone in req.restricted_zones:
            polygon = zone.get("polygon") or []
            if polygon and _point_in_polygon(point, polygon):
                violations.append(
                    {
                        "type": "restricted_zone_intrusion",
                        "risk_level": zone.get("risk_level", "high"),
                        "person_id": person.get("id"),
                        "zone_id": zone.get("id"),
                        "zone_name": zone.get("name"),
                    }
                )
        for machine in req.equipment:
            distance = _distance(point, _center(machine))
            if distance <= req.min_person_equipment_distance:
                violations.append(
                    {
                        "type": "person_equipment_near_miss",
                        "risk_level": "high",
                        "person_id": person.get("id"),
                        "equipment_id": machine.get("id"),
                        "distance": distance,
                        "unit": req.coordinate_unit,
                    }
                )
    return ToolResult(
        ok=True,
        tool="evaluate_hazard_zone_rules",
        summary=f"Evaluated hazard zones and found {len(violations)} violations.",
        data={"violations": violations, "requires_human_review": bool(violations)},
    )


def recommend_visual_safety_pipeline(req: VisualPipelineRecommendRequest) -> ToolResult:
    if req.scenario == "ppe":
        reference = "Construction-PPE-Detection"
        flow = ["YOLOv8 PPE detection", "tracking/cooldown", "violation log", "create_safety_case"]
    elif req.scenario in {"restricted_zone", "near_miss"}:
        reference = "Construction-Hazard-Detection + HazardLens"
        flow = ["camera calibration", "zone polygon config", "distance/rule engine", "visual event card"]
    elif req.scenario == "fall_detection":
        reference = "HazardLens / SentinelVision"
        flow = ["pose or aspect-ratio detection", "multi-frame confirmation", "human review", "incident draft"]
    elif req.scenario == "multi_camera":
        reference = "Construction-PPE-Detection"
        flow = ["camera registry", "RTMP/MJPEG/WebSocket", "batch detector workers", "dashboard"]
    else:
        reference = "SafetyVision"
        flow = ["normalized events", "policy/RAG lookup", "LLM report prompt", "human-confirmed report"]
    return ToolResult(
        ok=True,
        tool="recommend_visual_safety_pipeline",
        summary=f"Recommended {reference} style pipeline.",
        data={"scenario": req.scenario, "deployment": req.deployment, "priority": req.priority, "reference_project": reference, "flow": flow},
    )


def draft_safety_report_from_events(req: SafetyReportFromEventsRequest) -> ToolResult:
    title_project = f" - {req.project_name}" if req.project_name else ""
    lines = [
        f"# 安全事件报告草稿{title_project}",
        "",
        f"- 报告类型：{req.report_type}",
        f"- 生成时间：{_now()}",
        f"- 事件数量：{len(req.events)}",
        "",
        "## 事件摘要",
    ]
    if not req.events:
        lines.append("- 暂无事件。")
    for event in req.events[:20]:
        lines.append(
            f"- [{event.get('risk_level', 'medium')}] {event.get('event_type', 'visual_safety')} "
            f"{event.get('camera_id', '')} {event.get('image_path', '')}"
        )
    if req.include_recommendations:
        lines.extend(["", "## 建议动作"])
        lines.extend(f"- {action}" for action in _report_recommendations(req.events))
    return ToolResult(
        ok=True,
        tool="draft_safety_report_from_events",
        summary="Drafted safety report from normalized events.",
        data={"markdown": "\n".join(lines), "requires_human_confirmation": True},
    )


def _guess_workflow_tools(workflow: str) -> list[str]:
    if any(term in workflow for term in ["safety", "hazard", "incident"]):
        return CONSTRUCTION_TOOL_MAP["safety_incident"]
    if any(term in workflow for term in ["form", "inspection", "checklist"]):
        return CONSTRUCTION_TOOL_MAP["inspection"]
    if any(term in workflow for term in ["report", "daily"]):
        return CONSTRUCTION_TOOL_MAP["daily_report"]
    return ["search_policy_clauses", "draft_group_message"]


def _label(det: dict[str, Any]) -> str:
    return str(det.get("label") or det.get("class_name") or det.get("class") or det.get("name") or "").lower()


def _visual_violations(labels: list[str], raw_event: dict[str, Any]) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    text = " ".join(labels + [str(raw_event).lower()])
    if any(term in text for term in ["no-hardhat", "no_helmet", "no helmet", "missing helmet"]):
        violations.append({"type": "ppe_missing_helmet", "risk_level": "high"})
    if any(term in text for term in ["no-vest", "no_vest", "missing vest", "no reflective"]):
        violations.append({"type": "ppe_missing_reflective_vest", "risk_level": "medium"})
    if any(term in text for term in ["restricted", "intrusion", "danger zone"]):
        violations.append({"type": "restricted_zone_intrusion", "risk_level": "high"})
    if any(term in text for term in ["near_miss", "near-miss", "too close"]):
        violations.append({"type": "person_equipment_near_miss", "risk_level": "high"})
    if any(term in text for term in ["fall", "fallen", "跌倒", "墮下", "堕下"]):
        violations.append({"type": "fall_or_abnormal_posture", "risk_level": "high"})
    return violations


def _case_candidate_from_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "description": f"Visual safety event from {event.get('camera_id') or 'camera'}: {', '.join(v['type'] for v in event.get('violations', [])) or 'no violation'}",
        "scene": "视觉安全事件",
        "risk_level": event.get("risk_level", "medium"),
        "source_type": "visual_safety",
        "source_id": event.get("image_path") or event.get("camera_id"),
        "recommended_action": "请安全主任复核截图/视频片段，并决定是否创建整改任务。",
    }


def _center(item: dict[str, Any]) -> tuple[float, float]:
    if "center" in item:
        return float(item["center"][0]), float(item["center"][1])
    bbox = item.get("bbox") or [0, 0, 0, 0]
    x1, y1, x2, y2 = [float(value) for value in bbox[:4]]
    return (x1 + x2) / 2, (y1 + y2) / 2


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def _point_in_polygon(point: tuple[float, float], polygon: list[list[float]]) -> bool:
    x, y = point
    inside = False
    j = len(polygon) - 1
    for i, current in enumerate(polygon):
        xi, yi = current
        xj, yj = polygon[j]
        intersects = (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi
        if intersects:
            inside = not inside
        j = i
    return inside


def _report_recommendations(events: list[dict[str, Any]]) -> list[str]:
    text = str(events).lower()
    actions = []
    if "ppe_missing_helmet" in text:
        actions.append("加强安全帽佩戴巡查，并向相关分判商发出整改提醒。")
    if "restricted_zone_intrusion" in text:
        actions.append("复核危险区域围封、警示牌和摄像头区域配置。")
    if "near_miss" in text:
        actions.append("复查人机分流、机械倒车警示和吊运/机械作业禁区。")
    if "fall" in text or "墮下" in text or "堕下" in text:
        actions.append("重点检查临边、防坠落、工作平台和梯具管理。")
    return actions or ["保留事件记录，安排安全主任人工复核。"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
