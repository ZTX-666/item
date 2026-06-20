from __future__ import annotations

from typing import Any

from chitung_center.app_config_service import get_default_camera, get_app_config
from chitung_center.audit import audit_logger
from chitung_center.models import VisualPatrolConfirmRequest, VisualPatrolDraftRequest
from chitung_center.toolbox_client import toolbox_client


async def build_visual_patrol_draft(request: VisualPatrolDraftRequest) -> dict[str, Any]:
    """Build a visual patrol draft using the serial YOLO→VLM pipeline.

    Pipeline steps:
    1. RTMP snapshot (reuse existing logic)
    2. YOLO dual-model detection (reuse run_vlm_detection_batch)
    3. If vlm_enabled and analysis_mode == "hybrid":
       a. Filter YOLO detections by conf >= yolo_conf_threshold
       b. Call toolbox /tools/secureeye_analyze_batch (crops → VLM)
       c. Call toolbox /tools/secureeye_merge_results (IoU merge)
       d. VLM failure → silent fallback to pure YOLO, audit event recorded
    4. Build candidates with source_mix / severity / description / detection_details
    """
    snapshot_result: dict[str, Any] | None = None
    source = request.source
    camera = _resolve_camera(request)
    camera_url = request.camera_url or (camera or {}).get("rtmp_url")
    area = request.area or (camera or {}).get("area")

    # ── Step 1: RTMP snapshot ──
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
            "analysis_mode": "yolo_only",
            "candidates": [],
        }

    # ── Step 2: YOLO detection ──
    vlm_result = await toolbox_client.call_tool(
        "run_vlm_detection_batch",
        {
            "source": source,
            "conf": request.conf,
            "worker_only": False,
            "machinery_only": False,
        },
    )
    audit_logger.write("visual_yolo_detect_done", {
        "task_id": vlm_result.get("task_id"),
        "source": source,
    })

    detections = _tool_data(vlm_result).get("detections", {})

    # ── Step 3: VLM enhancement (serial, after YOLO) ──
    merged_detections: list[dict[str, Any]] | None = None
    source_mix = "yolo"
    vlm_enhanced = False

    if request.vlm_enabled and request.analysis_mode == "hybrid":
        try:
            # 3a. Extract crops from YOLO results (filter by conf threshold)
            crops_by_image = _extract_crops_from_yolo(detections, request.yolo_conf_threshold)

            if crops_by_image:
                all_vlm_results: list[dict[str, Any]] = []
                for img_path, img_crops in crops_by_image.items():
                    batch_result = await toolbox_client.call_tool(
                        "secureeye_analyze_batch",
                        {
                            "image_path": img_path,
                            "crops": img_crops,
                            "context": area or "",
                        },
                    )
                    batch_data = _tool_data(batch_result)
                    all_vlm_results.extend(batch_data.get("results", []))

                audit_logger.write("visual_vlm_enhance_done", {
                    "crop_count": sum(len(c) for c in crops_by_image.values()),
                    "vlm_result_count": len(all_vlm_results),
                })

                # 3c. Merge YOLO + VLM results via IoU
                yolo_flat = _flatten_yolo_detections(detections)
                merge_result = await toolbox_client.call_tool(
                    "secureeye_merge_results",
                    {
                        "yolo_detections": yolo_flat,
                        "vlm_results": all_vlm_results,
                        "iou_threshold": 0.7,
                    },
                )
                merge_data = _tool_data(merge_result)
                merged_detections = merge_data.get("detections", [])

                audit_logger.write("visual_hybrid_merge_done", {
                    "merged_count": len(merged_detections),
                })

                vlm_enhanced = True
                source_mix = "hybrid"
        except Exception as exc:
            audit_logger.write("visual_hybrid_failed_fallback_yolo", {
                "error": str(exc),
            })
            # Silent fallback to pure YOLO
            merged_detections = None
            source_mix = "yolo"

    # ── Step 4: Build candidates ──
    candidates = _build_candidates(
        detections,
        request,
        vlm_result,
        area,
        merged_detections=merged_detections,
        source_mix=source_mix,
    )

    return {
        "ok": bool(vlm_result.get("ok")),
        "message": "Visual patrol draft generated. Confirm a candidate before creating a safety case.",
        "requires_confirmation": True,
        "snapshot": snapshot_result,
        "vlm": vlm_result,
        "source": source,
        "candidates": candidates,
        "analysis_mode": "hybrid" if vlm_enhanced else "yolo_only",
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
    """Confirm a visual patrol candidate and create a safety case."""
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


# ── Helper functions ────────────────────────────────────────────


def _resolve_camera(request: VisualPatrolDraftRequest) -> dict[str, Any] | None:
    if request.camera_id:
        config = get_app_config()
        for camera in config.get("cameras", []):
            if str(camera.get("id")) == request.camera_id:
                return camera
    if not request.camera_url and not request.area:
        return get_default_camera()
    return None


def _tool_data(result: dict[str, Any] | None) -> dict[str, Any]:
    """Extract the 'data' dict from a tool result, or return empty dict."""
    if not result:
        return {}
    data = result.get("data")
    return data if isinstance(data, dict) else {}


def _first_file_path(result: dict[str, Any] | None) -> str | None:
    """Return the first file path from a tool result's files list."""
    files = result.get("files", []) if result else []
    if isinstance(files, list):
        for file in files:
            if isinstance(file, dict) and file.get("path"):
                return str(file["path"])
    return None


def _extract_crops_from_yolo(
    detections: Any,
    conf_threshold: float,
) -> dict[str, list[dict[str, Any]]]:
    """Extract crop candidates from YOLO detection JSON, grouped by image path.

    Only detections with confidence >= conf_threshold are included.
    Returns a dict mapping image_path → list of crop dicts.
    """
    crops_by_image: dict[str, list[dict[str, Any]]] = {}

    if not isinstance(detections, dict):
        return crops_by_image

    images = detections.get("images", [])
    if not isinstance(images, list):
        return crops_by_image

    crop_idx = 0
    for image_entry in images:
        if not isinstance(image_entry, dict):
            continue

        img_path = image_entry.get("image", "")
        if not img_path:
            continue

        objects = image_entry.get("detections") or image_entry.get("objects") or []
        if not isinstance(objects, list):
            continue

        img_crops: list[dict[str, Any]] = []
        for det in objects:
            if not isinstance(det, dict):
                continue

            confidence = float(det.get("confidence", 0.0))
            if confidence < conf_threshold:
                continue

            bbox = det.get("bbox_xyxy") or det.get("bbox", [0, 0, 0, 0])
            label = det.get("class_name") or det.get("label", "unknown")

            crop_idx += 1
            img_crops.append({
                "id": f"c{crop_idx}",
                "bbox": [float(v) for v in bbox],
                "label": str(label),
                "confidence": confidence,
            })

        if img_crops:
            crops_by_image[img_path] = img_crops

    return crops_by_image


def _flatten_yolo_detections(detections: Any) -> list[dict[str, Any]]:
    """Flatten YOLO detection JSON into a list of unified detection dicts."""
    flattened: list[dict[str, Any]] = []

    if not isinstance(detections, dict):
        return flattened

    images = detections.get("images", [])
    if not isinstance(images, list):
        return flattened

    for image_entry in images:
        if not isinstance(image_entry, dict):
            continue

        objects = image_entry.get("detections") or image_entry.get("objects") or []
        if not isinstance(objects, list):
            continue

        for det in objects:
            if not isinstance(det, dict):
                continue

            bbox = det.get("bbox_xyxy") or det.get("bbox", [0, 0, 0, 0])
            label = det.get("class_name") or det.get("label", "unknown")
            confidence = float(det.get("confidence", 0.0))

            flattened.append({
                "bbox": [float(v) for v in bbox],
                "label": str(label),
                "confidence": confidence,
                "source": "yolo",
            })

    return flattened


def _build_candidates(
    detections: Any,
    request: VisualPatrolDraftRequest,
    vlm_result: dict[str, Any],
    area: str | None,
    merged_detections: list[dict[str, Any]] | None = None,
    source_mix: str = "yolo",
) -> list[dict[str, Any]]:
    """Build visual patrol candidates from detection results.

    If merged_detections is available (hybrid mode), build enhanced candidates
    with VLM description/severity/suggested_action and per-detection details.
    Otherwise, fall back to YOLO-only candidates.
    """
    task_id = vlm_result.get("task_id")

    # ── Enhanced path: merged YOLO+VLM detections ──
    if merged_detections is not None:
        return _build_candidates_from_merged(merged_detections, task_id, area, source_mix)

    # ── Fallback path: YOLO-only ──
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
                "task_id": task_id,
                "source_mix": source_mix,
                "severity": "low",
                "suggested_action": "建议人工抽查截图",
                "detection_details": [],
            }
        ]

    risk_level = "high" if _has_high_risk_label(labels) else "medium"
    severity = _severity_from_labels(labels)

    return [
        {
            "id": "visual-hazard-candidate",
            "title": "视觉巡检隐患候选",
            "risk_level": risk_level,
            "area": area or "未分区",
            "description": f"VLM 已处理 {image_count} 张图片，发现 {detection_count} 个目标：{', '.join(sorted(set(labels))[:8])}",
            "labels": sorted(set(labels)),
            "task_id": task_id,
            "source_mix": source_mix,
            "severity": severity,
            "suggested_action": "请安全主任复核图片识别结果",
            "detection_details": [],
        }
    ]


def _build_candidates_from_merged(
    merged_detections: list[dict[str, Any]],
    task_id: str | None,
    area: str | None,
    source_mix: str,
) -> list[dict[str, Any]]:
    """Build enhanced candidates from merged YOLO+VLM detection results."""
    if not merged_detections:
        return [
            {
                "id": "visual-review",
                "title": "视觉巡检完成，未发现明确目标",
                "risk_level": "low",
                "area": area or "未分区",
                "description": "YOLO+VLM 流水线未发现明确检测目标，建议人工抽查截图。",
                "labels": [],
                "task_id": task_id,
                "source_mix": source_mix,
                "severity": "low",
                "suggested_action": "建议人工抽查截图",
                "detection_details": [],
            }
        ]

    labels = sorted(set(d.get("label", "") for d in merged_detections if d.get("label")))
    severities = [d.get("severity", "low") for d in merged_detections]
    max_severity = _max_severity(severities)

    # Build per-detection details
    detection_details: list[dict[str, Any]] = []
    for det in merged_detections:
        detection_details.append({
            "bbox": det.get("bbox", [0, 0, 0, 0]),
            "label": det.get("label", "unknown"),
            "confidence": det.get("confidence", 0.0),
            "source": det.get("source", "yolo"),
            "description": det.get("description", ""),
            "severity": det.get("severity", "low"),
            "suggested_action": det.get("suggested_action", ""),
        })

    # Map severity to risk_level
    severity_to_risk = {
        "critical": "critical",
        "high": "high",
        "medium": "medium",
        "low": "low",
    }
    risk_level = severity_to_risk.get(max_severity, "medium")

    # Build description
    descriptions = [d.get("description", "") for d in merged_detections if d.get("description")]
    if descriptions:
        description = f"YOLO+VLM 串行检测完成，共 {len(merged_detections)} 个目标。主要风险: {'; '.join(descriptions[:3])}"
    else:
        description = f"YOLO+VLM 串行检测完成，共 {len(merged_detections)} 个目标：{', '.join(labels[:8])}"

    # Build suggested action
    actions = [d.get("suggested_action", "") for d in merged_detections if d.get("suggested_action")]
    suggested_action = actions[0] if actions else "请安全主任复核图片识别结果"

    return [
        {
            "id": "visual-hazard-candidate",
            "title": "视觉巡检隐患候选（YOLO+VLM 串行）",
            "risk_level": risk_level,
            "area": area or "未分区",
            "description": description,
            "labels": labels,
            "task_id": task_id,
            "source_mix": source_mix,
            "severity": max_severity,
            "suggested_action": suggested_action,
            "detection_details": detection_details,
        }
    ]


def _max_severity(severities: list[str]) -> str:
    """Return the highest severity from a list. Order: critical > high > medium > low."""
    order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    if not severities:
        return "low"
    return max(severities, key=lambda s: order.get(s.lower(), 0))


def _severity_from_labels(labels: list[str]) -> str:
    """Infer maximum severity from YOLO class labels."""
    text = " ".join(labels).lower()
    if any(t in text for t in ["no-hardhat", "no-mask", "no-safety", "no-helmet"]):
        return "high"
    if any(t in text for t in ["crane", "excavator", "bulldozer", "dump_truck"]):
        return "medium"
    return "low"


def _has_high_risk_label(labels: list[str]) -> bool:
    """Check if any label indicates a high-risk condition."""
    text = " ".join(labels).lower()
    return any(token in text for token in ["no-hardhat", "no helmet", "no-safety", "crane", "excavator"])


def _looks_like_image(path: str) -> bool:
    """Check if a path looks like an image file."""
    return path.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
