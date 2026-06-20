from __future__ import annotations

from typing import Any

from chitung_center.app_config_service import get_default_camera
from chitung_center.models import VisualPatrolConfirmRequest, VisualPatrolDraftRequest
from chitung_center.toolbox_client import toolbox_client


async def build_visual_patrol_draft(request: VisualPatrolDraftRequest) -> dict[str, Any]:
    snapshot_result: dict[str, Any] | None = None
    source = request.source
    camera = get_default_camera() if not request.camera_url and not request.area else None
    camera_url = request.camera_url or (camera or {}).get("rtmp_url")
    area = request.area or (camera or {}).get("area")

    if not source:
        snapshot_result = await toolbox_client.call_tool(
            "capture_camera_snapshot",
            {
                "url": camera_url,
                "count": request.count,
                "interval": 1,
                "prefix": f"patrol_{area or 'site'}",
            },
        )
        source = _first_file_path(snapshot_result) or _tool_data(snapshot_result).get("output_dir")

    if not source:
        return {
            "ok": False,
            "message": "No image source was available for VLM detection.",
            "requires_confirmation": True,
            "snapshot": snapshot_result,
        }

    vlm_result = await toolbox_client.call_tool(
        "run_vlm_detection_batch",
        {
            "source": source,
            "conf": request.conf,
            "worker_only": False,
            "machinery_only": False,
        },
    )
    detections = _tool_data(vlm_result).get("detections", {})
    candidates = _build_candidates(detections, request, vlm_result, area)

    return {
        "ok": bool(vlm_result.get("ok")),
        "message": "Visual patrol draft generated. Confirm a candidate before creating a safety case.",
        "requires_confirmation": True,
        "snapshot": snapshot_result,
        "vlm": vlm_result,
        "source": source,
        "candidates": candidates,
        "confirm_payload": {
            "detections": detections,
            "task_id": vlm_result.get("task_id"),
            "image_path": source if _looks_like_image(source) else None,
            "area": area,
            "contractor": request.contractor,
            "description": candidates[0]["description"] if candidates else "VLM visual safety hazard candidate",
        },
    }


async def confirm_visual_patrol_candidate(request: VisualPatrolConfirmRequest) -> dict[str, Any]:
    result = await toolbox_client.call_tool(
        "create_case_from_vlm",
        {
            "detections": request.detections,
            "vlm_result_path": request.vlm_result_path,
            "task_id": request.task_id,
            "image_path": request.image_path,
            "area": request.area,
            "contractor": request.contractor,
            "description": request.description,
        },
    )
    return {
        "ok": bool(result.get("ok")),
        "message": "Visual patrol candidate confirmed and converted to a safety case.",
        "tool_result": result,
    }


def _tool_data(result: dict[str, Any] | None) -> dict[str, Any]:
    if not result:
        return {}
    data = result.get("data")
    return data if isinstance(data, dict) else {}


def _first_file_path(result: dict[str, Any] | None) -> str | None:
    files = result.get("files", []) if result else []
    if isinstance(files, list):
        for file in files:
            if isinstance(file, dict) and file.get("path"):
                return str(file["path"])
    return None


def _build_candidates(
    detections: Any,
    request: VisualPatrolDraftRequest,
    vlm_result: dict[str, Any],
    area: str | None,
) -> list[dict[str, Any]]:
    labels: list[str] = []
    image_count = 0
    detection_count = 0

    if isinstance(detections, dict):
        images = detections.get("images", [])
        if isinstance(images, list):
            image_count = len(images)
            for image in images:
                if not isinstance(image, dict):
                    continue
                objects = image.get("detections") or image.get("objects") or []
                if isinstance(objects, list):
                    detection_count += len(objects)
                    for item in objects:
                        if isinstance(item, dict):
                            label = item.get("class_name") or item.get("label") or item.get("name") or item.get("class")
                            if label:
                                labels.append(str(label))

    if detection_count == 0:
        return [
            {
                "id": "visual-review",
                "title": "视觉巡检完成，未发现明确目标",
                "risk_level": "low",
                "area": area or "未分区",
                "description": "VLM 未返回明确检测目标，建议人工抽查截图。",
                "labels": [],
                "task_id": vlm_result.get("task_id"),
            }
        ]

    risk_level = "high" if _has_high_risk_label(labels) else "medium"
    return [
        {
            "id": "visual-hazard-candidate",
            "title": "视觉巡检隐患候选",
            "risk_level": risk_level,
            "area": area or "未分区",
            "description": f"VLM 已处理 {image_count} 张图片，发现 {detection_count} 个目标：{', '.join(sorted(set(labels))[:8])}",
            "labels": sorted(set(labels)),
            "task_id": vlm_result.get("task_id"),
        }
    ]


def _has_high_risk_label(labels: list[str]) -> bool:
    text = " ".join(labels).lower()
    return any(token in text for token in ["no-hardhat", "no helmet", "no-safety", "crane", "excavator"])


def _looks_like_image(path: str) -> bool:
    return path.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
