from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from chitung_center.app_config_service import get_app_config
from chitung_center.audit import audit_logger
from chitung_center.config import ROOT


SUITE_ROOT = ROOT.parent
SCRIPTS_DIR = SUITE_ROOT / "scripts"
DEFAULT_PATROL_OUTPUT = SUITE_ROOT / "patrol-output"


def _patrol_output_dir() -> Path:
    env_path = Path(__import__("os").environ.get("PATROL_OUTPUT_DIR", str(DEFAULT_PATROL_OUTPUT)))
    return env_path


def _load_nightly_patrol():
    scripts_path = str(SCRIPTS_DIR)
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    import nightly_patrol  # type: ignore[import-untyped]

    nightly_patrol.OUTPUT_BASE = _patrol_output_dir()
    return nightly_patrol


def _sync_cameras(nightly_patrol: Any) -> list[dict[str, str]]:
    config = get_app_config()
    cameras = [
        {
            "id": str(cam.get("id")),
            "name": str(cam.get("name") or cam.get("id")),
            "area": str(cam.get("area") or "施工区域"),
            "rtmp_url": str(cam.get("rtmp_url") or ""),
        }
        for cam in config.get("cameras", [])
        if cam.get("enabled", True)
    ]
    if cameras:
        nightly_patrol.CAMERAS = cameras
    return cameras


def _asset_url(patrol_id: str, filename: str) -> str:
    return f"/api/visual/patrol-files/{patrol_id}/{filename}"


def _rewrite_paths(summary: dict[str, Any]) -> dict[str, Any]:
    patrol_id = str(summary.get("patrol_id") or "")
    output_dir = _patrol_output_dir() / patrol_id
    cameras = summary.get("cameras")
    if not isinstance(cameras, list):
        return summary

    for cam in cameras:
        if not isinstance(cam, dict):
            continue
        for key in ("snapshot_path", "annotated_path"):
            raw = cam.get(key)
            if isinstance(raw, str) and raw:
                filename = Path(raw).name
                cam[f"{key.replace('_path', '')}_url"] = _asset_url(patrol_id, filename)
                cam[key] = str(output_dir / filename) if (output_dir / filename).exists() else raw
    summary["output_dir"] = str(output_dir)
    return summary


async def run_guardian_patrol(
    *,
    camera_id: str | None = None,
    vlm_enabled: bool = True,
) -> dict[str, Any]:
    nightly = _load_nightly_patrol()
    cameras = _sync_cameras(nightly)
    if not cameras:
        return {"ok": False, "error": "No enabled cameras in app config."}

    audit_id = audit_logger.write(
        "visual_guardian_patrol_started",
        {"camera_id": camera_id, "vlm_enabled": vlm_enabled, "camera_count": len(cameras)},
    )

    try:
        summary = await nightly.run_patrol(vlm_enabled=vlm_enabled, camera_filter=camera_id)
    except Exception as exc:  # noqa: BLE001
        audit_logger.write("visual_guardian_patrol_failed", {"error": str(exc), "audit_id": audit_id})
        return {"ok": False, "error": str(exc), "audit_id": audit_id}

    if summary.get("error"):
        return {"ok": False, "error": summary["error"], "audit_id": audit_id}

    summary = _rewrite_paths(summary)
    audit_logger.write(
        "visual_guardian_patrol_completed",
        {
            "audit_id": audit_id,
            "patrol_id": summary.get("patrol_id"),
            "success_count": summary.get("success_count"),
            "total_detections": summary.get("total_detections"),
        },
    )
    return {"ok": True, "audit_id": audit_id, "report": summary}


def list_patrol_runs(*, limit: int = 20) -> dict[str, Any]:
    output_dir = _patrol_output_dir()
    if not output_dir.exists():
        return {"ok": True, "items": []}

    items: list[dict[str, Any]] = []
    for child in sorted(output_dir.iterdir(), reverse=True):
        if not child.is_dir():
            continue
        report_path = child / "patrol_report.json"
        if report_path.exists():
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            items.append(
                {
                    "patrol_id": report.get("patrol_id", child.name),
                    "timestamp": report.get("timestamp"),
                    "camera_count": report.get("camera_count", 0),
                    "success_count": report.get("success_count", 0),
                    "total_detections": report.get("total_detections", 0),
                    "high_risk_count": report.get("high_risk_count", 0),
                    "hybrid_cameras": report.get("hybrid_cameras", 0),
                    "vlm_enabled": report.get("vlm_enabled", True),
                }
            )
        else:
            items.append({"patrol_id": child.name, "timestamp": None, "camera_count": 0, "success_count": 0})
        if len(items) >= limit:
            break
    return {"ok": True, "items": items}


def get_patrol_run(patrol_id: str) -> dict[str, Any]:
    report_path = _patrol_output_dir() / patrol_id / "patrol_report.json"
    if not report_path.exists():
        return {"ok": False, "error": f"Patrol run not found: {patrol_id}"}
    report = json.loads(report_path.read_text(encoding="utf-8"))
    return {"ok": True, "report": _rewrite_paths(report)}


def resolve_patrol_file(patrol_id: str, filename: str) -> Path | None:
    if ".." in filename or "/" in filename or "\\" in filename:
        return None
    file_path = (_patrol_output_dir() / patrol_id / filename).resolve()
    base = _patrol_output_dir().resolve()
    if not str(file_path).startswith(str(base)):
        return None
    if not file_path.exists() or not file_path.is_file():
        return None
    return file_path


def camera_result_to_draft(cam: dict[str, Any], patrol_id: str) -> dict[str, Any]:
    detections = cam.get("detections") or []
    labels = sorted({str(d.get("label")) for d in detections if isinstance(d, dict) and d.get("label")})
    severities = [str(d.get("severity") or "low") for d in detections if isinstance(d, dict)]
    max_severity = _max_severity(severities)
    risk_map = {"critical": "critical", "high": "high", "medium": "medium", "low": "low"}
    descriptions = [str(d.get("description")) for d in detections if isinstance(d, dict) and d.get("description")]

    detection_details = []
    for det in detections:
        if not isinstance(det, dict):
            continue
        detection_details.append(
            {
                "bbox": det.get("bbox", []),
                "label": det.get("label", "unknown"),
                "confidence": float(det.get("confidence", 0.0)),
                "source": det.get("source", "yolo"),
                "description": det.get("description", ""),
                "severity": det.get("severity", "low"),
                "suggested_action": det.get("suggested_action", ""),
            }
        )

    actions = [str(d.get("suggested_action")) for d in detections if isinstance(d, dict) and d.get("suggested_action")]
    snapshot_url = cam.get("snapshot_url") or _asset_url(patrol_id, f"{cam.get('camera_id')}_snapshot.jpg")
    annotated_url = cam.get("annotated_url") or _asset_url(patrol_id, f"{cam.get('camera_id')}_annotated.jpg")

    return {
        "ok": bool(cam.get("success")),
        "message": "赤瞳守护者巡检完成，请确认候选后入库。" if cam.get("success") else str(cam.get("error") or "巡检失败"),
        "requires_confirmation": True,
        "patrol_id": patrol_id,
        "camera_id": cam.get("camera_id"),
        "camera_name": cam.get("camera_name"),
        "source": cam.get("snapshot_path"),
        "snapshot_url": snapshot_url,
        "annotated_url": annotated_url,
        "analysis_mode": "hybrid" if cam.get("source_mix") == "hybrid" else "yolo_only",
        "candidates": [
            {
                "id": f"visual-{cam.get('camera_id')}",
                "title": f"{cam.get('camera_name')} 巡检候选",
                "risk_level": risk_map.get(max_severity, "medium"),
                "area": cam.get("area") or "未分区",
                "description": (
                    "; ".join(descriptions[:3])
                    if descriptions
                    else f"检测到 {len(detections)} 个目标：{', '.join(labels[:8])}"
                ),
                "labels": labels,
                "source_mix": cam.get("source_mix", "yolo"),
                "severity": max_severity,
                "suggested_action": actions[0] if actions else "请安全主任复核巡检结果",
                "detection_details": detection_details,
            }
        ],
        "confirm_payload": {
            "image_path": cam.get("snapshot_path"),
            "annotated_path": cam.get("annotated_path"),
            "area": cam.get("area"),
            "description": descriptions[0] if descriptions else f"{cam.get('camera_name')} 视觉巡检候选",
            "detections": {"items": detections, "camera_id": cam.get("camera_id"), "patrol_id": patrol_id},
        },
    }


def _max_severity(severities: list[str]) -> str:
    order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    if not severities:
        return "low"
    return max(severities, key=lambda item: order.get(item.lower(), 0))
