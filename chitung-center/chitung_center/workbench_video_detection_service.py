from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from chitung_center.app_config_service import get_app_config
from chitung_center.config import settings
from chitung_center.llm_gateway import llm_gateway
from chitung_center.models import WorkbenchVideoDetectionRequest
from chitung_center.rag_service import rag_service
from chitung_center.video_detection_store import (
    TABLE_NAME as VIDEO_DETECTION_TABLE_NAME,
    persist_video_detection_report,
)
from chitung_center.visual_patrol_batch_service import run_guardian_patrol


def _report_store_path() -> Path:
    return settings.chitung_data_dir / "video_detection_reports.json"


def _detection_store_path() -> Path:
    return _report_store_path().with_name("video_detection_results.db")


async def refine_detection_prompt(direction: str, cameras: list[dict[str, Any]] | dict[str, Any]) -> dict[str, Any]:
    camera_list = _normalize_camera_list(cameras)
    policy_context = await _search_policy_context(direction)
    fallback_prompt = _fallback_refined_prompt(direction, camera_list, policy_context)
    if not settings.llm_configured:
        return {
            "original_direction": direction,
            "refined_prompt": fallback_prompt,
            "policy_context": policy_context,
            "source": "fallback",
        }

    payload = {
        "detection_direction": direction,
        "cameras": [
            {
                "id": camera.get("id"),
                "name": camera.get("name"),
                "area": camera.get("area"),
            }
            for camera in camera_list
        ],
        "policy_context": policy_context,
    }
    try:
        result = await llm_gateway.complete_json(
            system_prompt=(
                "你是香港工地安全视觉巡检提示词工程师。"
                "请把用户的检测方向改写成给视觉大模型使用的中文检测提示词，"
                "需要覆盖用户选中的所有摄像头区域。"
                "若画面包含挖掘机、吊机、车辆等机械设备，必须要求判断人员与机械安全距离、"
                "机械作业半径、隔离围挡/警戒线是否充分，不要只做物体识别。"
                "只返回JSON，字段为 refined_prompt、focus_items、risk_keywords。"
            ),
            user_text=json.dumps(payload, ensure_ascii=False),
        )
        parsed = _extract_llm_json(result)
        refined_prompt = str(parsed.get("refined_prompt") or "").strip()
        if refined_prompt:
            return {
                "original_direction": direction,
                "refined_prompt": refined_prompt,
                "policy_context": policy_context,
                "focus_items": _string_list(parsed.get("focus_items")),
                "risk_keywords": _string_list(parsed.get("risk_keywords")),
                "source": "llm",
            }
    except Exception:
        pass

    return {
        "original_direction": direction,
        "refined_prompt": fallback_prompt,
        "policy_context": policy_context,
        "source": "fallback",
    }


async def preview_workbench_detection_prompt(request: WorkbenchVideoDetectionRequest) -> dict[str, Any]:
    cameras = _resolve_cameras(request.camera_ids, request.camera_id, detection_direction=request.detection_direction)
    if not cameras:
        return {"ok": False, "error": "No enabled camera was found.", "message": "未找到可用摄像头。"}

    prompt = await refine_detection_prompt(request.detection_direction, cameras)
    return {
        "ok": True,
        "detection_direction": request.detection_direction,
        "camera_ids": [str(camera.get("id")) for camera in cameras],
        "camera_names": [str(camera.get("name") or camera.get("id")) for camera in cameras],
        "refined_prompt": str(prompt.get("refined_prompt") or request.detection_direction),
        "prompt_source": prompt.get("source", "fallback"),
        "policy_context": prompt.get("policy_context", []),
        "focus_items": prompt.get("focus_items", []),
        "risk_keywords": prompt.get("risk_keywords", []),
    }


async def run_workbench_video_detection(request: WorkbenchVideoDetectionRequest) -> dict[str, Any]:
    cameras = _resolve_cameras(request.camera_ids, request.camera_id, detection_direction=request.detection_direction)
    if not cameras:
        return {"ok": False, "error": "No enabled camera was found.", "message": "未找到可用摄像头。"}

    user_prompt = (request.refined_prompt or "").strip()
    if user_prompt:
        prompt = {
            "original_direction": request.detection_direction,
            "refined_prompt": user_prompt,
            "policy_context": [],
            "source": "user",
        }
    else:
        prompt = await refine_detection_prompt(request.detection_direction, cameras)
    refined_prompt = str(prompt.get("refined_prompt") or request.detection_direction)

    camera_reports: list[dict[str, Any]] = []
    patrol_reports: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    camera_ids = [str(camera.get("id")) for camera in cameras if str(camera.get("id")).strip()]
    patrol_kwargs: dict[str, Any] = {
        "vlm_enabled": request.vlm_enabled,
        "inspection_prompt": refined_prompt,
    }
    if len(camera_ids) == 1:
        patrol_kwargs["camera_id"] = camera_ids[0]
    elif camera_ids:
        patrol_kwargs["camera_ids"] = camera_ids

    patrol_result = await run_guardian_patrol(**patrol_kwargs)
    if not patrol_result.get("ok"):
        message = str(patrol_result.get("error") or "视频检测失败。")
        return {
            "ok": False,
            "error": message,
            "message": message,
            "prompt": prompt,
            "camera_errors": [{"camera_id": "batch", "error": message}],
        }

    report = patrol_result.get("report") if isinstance(patrol_result.get("report"), dict) else {}
    if report:
        patrol_reports.append(report)

    for camera in cameras:
        camera_id = str(camera.get("id"))
        camera_result = _select_camera_result(report, camera_id)
        if not camera_result:
            errors.append({"camera_id": camera_id, "error": "巡检完成，但没有返回该摄像头结果。"})
            continue
        if camera_result.get("success") is False:
            errors.append(
                {
                    "camera_id": camera_id,
                    "error": str(camera_result.get("error") or "真实摄像头抽帧失败，未使用本地回退图"),
                }
            )
            continue
        camera_summary = _build_concise_summary(request.detection_direction, camera_result)
        camera_reports.append(
            {
                **camera_result,
                "user_question": request.detection_direction,
                "summary": camera_summary,
                "patrol_id": report.get("patrol_id"),
            }
        )

    if not camera_reports:
        message = errors[0]["error"] if errors else "视频检测失败。"
        return {
            "ok": False,
            "error": message,
            "message": message,
            "prompt": prompt,
            "camera_errors": errors,
        }

    summary = _build_aggregate_summary(request.detection_direction, camera_reports)
    primary_camera = camera_reports[0]
    report_id = f"video-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    record = {
        "report_id": report_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "user_question": request.detection_direction,
        "direction": request.detection_direction,
        "refined_prompt": refined_prompt,
        "prompt_source": prompt.get("source", "fallback"),
        "policy_context": prompt.get("policy_context", []),
        "camera_id": primary_camera.get("camera_id"),
        "camera_name": primary_camera.get("camera_name") or primary_camera.get("camera_id"),
        "camera_ids": [str(camera.get("id")) for camera in cameras],
        "camera_names": [str(camera.get("camera_name") or camera.get("camera_id")) for camera in camera_reports],
        "camera_count": len(camera_reports),
        "area": primary_camera.get("area"),
        "patrol_id": primary_camera.get("patrol_id"),
        "snapshot_url": primary_camera.get("snapshot_url"),
        "annotated_url": primary_camera.get("annotated_url"),
        "snapshot_path": primary_camera.get("snapshot_path"),
        "annotated_path": primary_camera.get("annotated_path"),
        "summary": summary,
        "detections": _flatten_detections(camera_reports),
        "cameras": camera_reports,
        "camera_errors": errors,
        "patrol_report": _merge_patrol_reports(patrol_reports, camera_reports, refined_prompt),
        "patrol_reports": patrol_reports,
    }
    _persist_detection_rows(record)
    _prepend_report(record)
    return {"ok": True, **record}


def list_video_detection_reports(limit: int = 20) -> dict[str, Any]:
    items = _read_reports()
    safe_limit = max(1, min(limit, 100))
    return {"ok": True, "items": items[:safe_limit]}


async def _search_policy_context(direction: str) -> list[str]:
    try:
        result = await rag_service.query(direction, top_k=3, collection="safety")
    except Exception:
        try:
            result = await rag_service.query(direction, top_k=3)
        except Exception:
            return []
    items = result.get("items") if isinstance(result, dict) else []
    if not isinstance(items, list):
        return []
    snippets: list[str] = []
    for item in items[:3]:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if text:
            snippets.append(text[:300])
    return snippets


def _fallback_refined_prompt(direction: str, cameras: list[dict[str, Any]], policy_context: list[str]) -> str:
    camera_list = _normalize_camera_list(cameras)
    areas = sorted({str(camera.get("area") or "现场") for camera in camera_list})
    area = "、".join(areas[:4]) if areas else "现场"
    context = "；".join(policy_context[:2])
    context_part = f"参考制度要点：{context}。" if context else ""
    return (
        f"请重点检查{area}等 {len(camera_list)} 路摄像头画面中是否存在“{direction}”相关风险。"
        f"{context_part}"
        "结合人员PPE合规、安全帽和反光衣、机械车辆、机械作业半径、人员与机械安全距离、"
        "隔离围挡/警戒线、临边/高处作业、通道占用和危险区域距离进行判断；"
        "如果发现人员靠近挖掘机、吊机、车辆或其他机械作业区，应作为需要人工复核的潜在风险输出；"
        "请输出风险描述、风险等级和可执行处置建议。"
    )


def _extract_llm_json(result: dict[str, Any]) -> dict[str, Any]:
    if "choices" not in result:
        return result
    choices = result.get("choices")
    if not isinstance(choices, list) or not choices:
        return {}
    message = choices[0].get("message") if isinstance(choices[0], dict) else {}
    content = message.get("content") if isinstance(message, dict) else ""
    if isinstance(content, dict):
        return content
    if not isinstance(content, str):
        return {}
    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _normalize_camera_list(cameras: list[dict[str, Any]] | dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(cameras, dict):
        return [cameras]
    return [camera for camera in cameras if isinstance(camera, dict)]


def _resolve_cameras(
    camera_ids: list[str] | None = None,
    legacy_camera_id: str | None = None,
    *,
    detection_direction: str | None = None,
) -> list[dict[str, Any]]:
    config = get_app_config()
    cameras = [cam for cam in config.get("cameras", []) if isinstance(cam, dict) and cam.get("enabled", True)]
    requested_ids = [str(item) for item in (camera_ids or []) if str(item).strip()]
    if not requested_ids and legacy_camera_id:
        requested_ids = [legacy_camera_id]
    if not requested_ids and detection_direction:
        requested_ids = _camera_ids_mentioned_in_text(detection_direction, cameras)
    if not requested_ids and detection_direction:
        scope = patrol_scope_from_message(detection_direction)
        if scope == "all_enabled":
            return cameras
        if scope == "default_single":
            return cameras[:1]
    if not requested_ids:
        # 视觉巡检技能默认：全部已启用摄像头（当前 11 路）
        return cameras

    seen: set[str] = set()
    selected: list[dict[str, Any]] = []
    by_id = {str(cam.get("id")): cam for cam in cameras}
    for camera_id in requested_ids:
        if camera_id in seen:
            continue
        camera = by_id.get(camera_id)
        if camera:
            selected.append(camera)
            seen.add(camera_id)
    return selected


def patrol_scope_from_message(message: str) -> str:
    """Classify patrol scope from natural language."""
    text = (message or "").strip()
    if not text:
        return "default_single"

    lowered = text.lower()
    if re.search(r"(?:11|十一|\d+)\s*[支路个]", text) and any(token in text for token in ("摄像头", "摄像", "监控", "cctv")):
        return "all_enabled"
    if any(
        marker in text
        for marker in (
            "全部摄像头",
            "所有摄像头",
            "各路摄像头",
            "全路摄像头",
            "逐个摄像头",
            "每一路",
            "全盘",
        )
    ):
        return "all_enabled"
    if "地盘" in text and any(token in text for token in ("摄像头", "监控", "cctv")):
        return "all_enabled"
    if "地盘" in text and any(token in text for token in ("检查", "巡检", "检测", "识别")):
        return "all_enabled"
    if any(token in text for token in ("吊运", "起吊", "吊车", "吊机")) and any(
        token in text for token in ("检测", "巡检", "检查", "识别", "地盘", "摄像头", "监控")
    ):
        return "all_enabled"
    if any(token in text for token in ("视觉巡检", "巡检", "检测", "识别")) and "摄像头" not in text:
        # 技能触发语（如「检查吊运安全」）未点名单路时，默认全盘
        return "all_enabled"
    if any(token in lowered for token in ("all cameras", "every camera")):
        return "all_enabled"
    return "default_single"


def _camera_ids_mentioned_in_text(message: str, cameras: list[dict[str, Any]]) -> list[str]:
    text = message or ""
    matched: list[str] = []
    for camera in cameras:
        camera_id = str(camera.get("id") or "")
        camera_name = str(camera.get("name") or "")
        if camera_name and camera_name in text:
            matched.append(camera_id)
        elif camera_id and camera_id in text:
            matched.append(camera_id)
    return list(dict.fromkeys(matched))


def _select_camera_result(report: dict[str, Any], camera_id: str) -> dict[str, Any] | None:
    cameras = report.get("cameras")
    if not isinstance(cameras, list):
        return None
    for cam in cameras:
        if isinstance(cam, dict) and str(cam.get("camera_id")) == camera_id:
            return cam
    first = cameras[0] if cameras else None
    return first if isinstance(first, dict) else None


def _build_concise_summary(direction: str, camera_result: dict[str, Any]) -> dict[str, Any]:
    detections = camera_result.get("detections") if isinstance(camera_result.get("detections"), list) else []
    severity = _max_severity([str(det.get("severity") or "low") for det in detections if isinstance(det, dict)])
    labels = sorted({str(det.get("label")) for det in detections if isinstance(det, dict) and det.get("label")})
    machinery_review_needed = _needs_machinery_exclusion_review(direction, labels)
    if machinery_review_needed:
        severity = _at_least_severity(severity, "medium")
    descriptions = [str(det.get("description")) for det in detections if isinstance(det, dict) and det.get("description")]
    actions = [str(det.get("suggested_action")) for det in detections if isinstance(det, dict) and det.get("suggested_action")]
    camera_name = str(camera_result.get("camera_name") or camera_result.get("camera_id") or "摄像头")
    detection_count = len(detections)
    if detection_count:
        text = f"{camera_name}围绕“{direction}”完成检测，发现 {detection_count} 个目标：{', '.join(labels[:5])}。"
    else:
        text = f"{camera_name}围绕“{direction}”完成检测，未发现明确目标。"
    if descriptions:
        text += f" 主要风险：{'；'.join(descriptions[:2])}"
    if actions:
        text += f" 建议：{actions[0]}"
    elif machinery_review_needed:
        text += " 需复核人员与机械作业区安全距离、隔离围挡和现场管控。"
    return {
        "title": f"{camera_name} 视频检测简报",
        "text": text,
        "severity": severity,
        "detection_count": detection_count,
        "labels": labels,
        "suggested_action": actions[0]
        if actions
        else (
            "请复核人员与机械作业区安全距离、隔离围挡和现场管控。"
            if machinery_review_needed
            else "请安全主任复核标注图。"
        ),
    }


def _build_aggregate_summary(direction: str, camera_reports: list[dict[str, Any]]) -> dict[str, Any]:
    detections = _flatten_detections(camera_reports)
    severity = _max_severity([str(det.get("severity") or "low") for det in detections if isinstance(det, dict)])
    labels = sorted({str(det.get("label")) for det in detections if isinstance(det, dict) and det.get("label")})
    machinery_review_needed = _needs_machinery_exclusion_review(direction, labels)
    if machinery_review_needed:
        severity = _at_least_severity(severity, "medium")
    high_risk_count = sum(
        1
        for det in detections
        if isinstance(det, dict) and str(det.get("severity") or "").lower() in {"high", "critical"}
    )
    camera_names = [str(camera.get("camera_name") or camera.get("camera_id")) for camera in camera_reports]
    camera_count = len(camera_reports)
    enabled_count = len(
        [cam for cam in get_app_config().get("cameras", []) if isinstance(cam, dict) and cam.get("enabled", True)]
    )
    total_cameras = enabled_count or camera_count
    detection_count = len(detections)
    scope_text = f"{camera_count}/{total_cameras}" if total_cameras > 1 else str(camera_count)
    if detection_count:
        if machinery_review_needed:
            text = f"已按“{direction}”完成 {scope_text} 路摄像头检测，共发现 {detection_count} 个需复核目标。"
        else:
            text = (
                f"已按“{direction}”完成 {scope_text} 路摄像头检测，"
                f"共发现 {detection_count} 个目标，{high_risk_count} 个高风险。"
            )
        if labels:
            text += f" 主要标签：{', '.join(labels[:6])}。"
        if machinery_review_needed:
            text += " 画面同时出现人员与机械设备，需复核人员与机械作业区安全距离、隔离围挡和现场管控。"
    else:
        text = f"已按“{direction}”完成 {scope_text} 路摄像头检测，未发现明确目标，当前画面中无明显异常或风险。"
    if total_cameras > camera_count:
        text += f" 另有 {total_cameras - camera_count} 路待补检。"
    suggested_action = (
        "请复核人员与机械作业区安全距离、隔离围挡和现场管控。"
        if machinery_review_needed
        else "请安全主任优先复核高风险标注图。"
    )
    return {
        "title": f"{camera_count} 路视频检测简报",
        "text": text,
        "severity": severity,
        "detection_count": detection_count,
        "labels": labels,
        "suggested_action": suggested_action,
        "camera_names": camera_names,
    }


def _needs_machinery_exclusion_review(direction: str, labels: list[str]) -> bool:
    direction_text = direction.lower()
    label_text = " ".join(labels)
    has_person = any(token in label_text for token in ["人员", "人", "worker", "person"])
    has_machinery = any(token in label_text for token in ["挖掘机", "机械", "吊机", "车辆", "excavator", "machinery"])
    cares_about_exclusion = any(token in direction_text for token in ["机械", "作业半径", "隔离", "靠近", "安全距离", "exclusion"])
    return has_person and has_machinery and cares_about_exclusion


def _at_least_severity(current: str, minimum: str) -> str:
    order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    current_key = (current or "low").lower()
    minimum_key = (minimum or "low").lower()
    return current_key if order.get(current_key, 0) >= order.get(minimum_key, 0) else minimum_key


def _flatten_detections(camera_reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    detections: list[dict[str, Any]] = []
    for camera in camera_reports:
        camera_detections = camera.get("detections")
        if not isinstance(camera_detections, list):
            continue
        for detection in camera_detections:
            if isinstance(detection, dict):
                detections.append(
                    {
                        **detection,
                        "camera_id": camera.get("camera_id"),
                        "camera_name": camera.get("camera_name"),
                    }
                )
    return detections


def _merge_patrol_reports(
    patrol_reports: list[dict[str, Any]], camera_reports: list[dict[str, Any]], inspection_prompt: str
) -> dict[str, Any]:
    first_report = patrol_reports[0] if patrol_reports else {}
    return {
        "patrol_id": first_report.get("patrol_id"),
        "timestamp": first_report.get("timestamp"),
        "camera_count": len(camera_reports),
        "success_count": len(camera_reports),
        "fail_count": 0,
        "total_detections": len(_flatten_detections(camera_reports)),
        "high_risk_count": sum(
            1
            for detection in _flatten_detections(camera_reports)
            if str(detection.get("severity") or "").lower() in {"high", "critical"}
        ),
        "vlm_enabled": first_report.get("vlm_enabled"),
        "inspection_prompt": inspection_prompt,
        "cameras": camera_reports,
    }


def _max_severity(severities: list[str]) -> str:
    order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    if not severities:
        return "low"
    return max((item.lower() for item in severities), key=lambda item: order.get(item, 0))


def _prepend_report(record: dict[str, Any]) -> None:
    items = [record, *_read_reports()]
    _write_reports(items[:100])


def _read_reports() -> list[dict[str, Any]]:
    path = _report_store_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []


def _write_reports(items: list[dict[str, Any]]) -> None:
    path = _report_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _persist_detection_rows(record: dict[str, Any]) -> None:
    db_path = _detection_store_path()
    try:
        storage = persist_video_detection_report(record, db_path)
        record["storage"] = {
            "sqlite_path": str(storage.get("db_path") or db_path),
            "sqlite_table": str(storage.get("table") or VIDEO_DETECTION_TABLE_NAME),
            "sqlite_rows": int(storage.get("rows") or 0),
        }
    except Exception as exc:  # noqa: BLE001
        record["storage_error"] = str(exc)
        record["storage"] = {
            "sqlite_path": str(db_path),
            "sqlite_table": VIDEO_DETECTION_TABLE_NAME,
            "sqlite_rows": 0,
        }
