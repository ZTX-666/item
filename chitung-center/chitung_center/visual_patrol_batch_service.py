from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

from chitung_center.app_config_service import get_app_config
from chitung_center.audit import audit_logger
from chitung_center.config import ROOT, settings


SUITE_ROOT = ROOT.parent
SCRIPTS_DIR = SUITE_ROOT / "scripts"
DEFAULT_PATROL_OUTPUT = SUITE_ROOT / "patrol-output"


def _patrol_output_dir() -> Path:
    env_path = Path(os.environ.get("PATROL_OUTPUT_DIR", str(DEFAULT_PATROL_OUTPUT)))
    return env_path


def _vlm_base_from_chat_url(url: str) -> str:
    stripped = url.rstrip("/")
    if stripped.endswith("/chat/completions"):
        return stripped[: -len("/chat/completions")]
    return stripped


def _configure_nightly_vlm(nightly_patrol: Any) -> None:
    base_url = os.environ.get("SECUREEYE_BASE_URL") or _vlm_base_from_chat_url(settings.secureeye_base_url)
    api_key = os.environ.get("SECUREEYE_API_KEY") or settings.secureeye_api_key
    model = os.environ.get("SECUREEYE_MODEL") or settings.secureeye_model
    concurrency = int(os.environ.get("SECUREEYE_MAX_CONCURRENCY", str(settings.secureeye_max_concurrency)))
    max_targets = int(os.environ.get("SECUREEYE_MAX_TARGETS_PER_CAMERA", str(settings.secureeye_max_targets_per_camera)))
    timeout = int(os.environ.get("SECUREEYE_TIMEOUT_SECONDS", str(settings.secureeye_timeout_seconds)))

    if base_url:
        nightly_patrol.VLM_BASE_URL = base_url
    if api_key:
        nightly_patrol.VLM_API_KEY = api_key
    if model:
        nightly_patrol.VLM_MODEL = model
    nightly_patrol.VLM_MAX_CONCURRENCY = max(1, concurrency)
    nightly_patrol.VLM_MAX_TARGETS_PER_CAMERA = max(0, max_targets)
    nightly_patrol.VLM_TIMEOUT = max(1, timeout)


def _load_nightly_patrol():
    scripts_path = str(SCRIPTS_DIR)
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    import nightly_patrol  # type: ignore[import-untyped]

    nightly_patrol.OUTPUT_BASE = _patrol_output_dir()
    _configure_nightly_vlm(nightly_patrol)
    return nightly_patrol


def _csmart_cache_candidates() -> list[Path]:
    candidates: list[Path] = []
    env_path = os.environ.get("CCTV_CHANNEL_CACHE_FILE")
    if env_path:
        candidates.append(Path(env_path))
    candidates.append(SUITE_ROOT.parent / "csmart-channel-list-latest.json")
    candidates.append(SUITE_ROOT / "cctv-gateway" / "csmart-channel-list-latest.json")
    return candidates


def _load_csmart_channels() -> list[dict[str, Any]]:
    for path in _csmart_cache_candidates():
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        channels = payload.get("channels") if isinstance(payload, dict) else payload
        if isinstance(channels, list):
            return [item for item in channels if isinstance(item, dict)]
    return []


def _match_csmart_channel(camera: dict[str, Any], channels: list[dict[str, Any]]) -> dict[str, Any] | None:
    channel_id = str(camera.get("csmart_channel_id") or "")
    channel_number = camera.get("csmart_channel_number")
    camera_name = str(camera.get("name") or "")

    if channel_id:
        for channel in channels:
            if str(channel.get("id") or "") == channel_id:
                return channel
    if channel_number is not None:
        for channel in channels:
            if str(channel.get("number") or "") == str(channel_number):
                return channel
    if camera_name:
        for channel in channels:
            if str(channel.get("cameraName") or channel.get("name") or "") == camera_name:
                return channel
    return None


def _append_candidate(candidates: list[str], seen: set[str], value: Any) -> None:
    if not isinstance(value, str):
        return
    text = value.strip()
    if text and text not in seen:
        candidates.append(text)
        seen.add(text)


def _raw_snapshot_url_candidates(camera: dict[str, Any], channel: dict[str, Any]) -> list[str]:
    keys = ("screenshot", "snapshot", "captureUrl", "snapshot_url", "snapshotUrl", "screenshot_url")
    candidates: list[str] = []
    seen: set[str] = set()
    for source in (channel, camera):
        for key in keys:
            _append_candidate(candidates, seen, source.get(key))
    return candidates


def _gateway_snapshot_url(camera: dict[str, Any], channel: dict[str, Any]) -> str:
    base_url = os.environ.get("CCTV_GATEWAY_BASE_URL", "http://127.0.0.1:3457").strip().rstrip("/")
    if not base_url:
        return ""
    channel_number = channel.get("number") or camera.get("csmart_channel_number")
    if channel_number is None or str(channel_number).strip() == "":
        return ""
    return f"{base_url}/api/csmart/snapshot/{quote(str(channel_number), safe='')}"


def _snapshot_url_candidates(camera: dict[str, Any], channel: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()
    _append_candidate(candidates, seen, _gateway_snapshot_url(camera, channel))
    for url in _raw_snapshot_url_candidates(camera, channel):
        _append_candidate(candidates, seen, url)
    return candidates


def _sync_cameras(nightly_patrol: Any) -> list[dict[str, Any]]:
    config = get_app_config()
    csmart_channels = _load_csmart_channels()
    cameras: list[dict[str, Any]] = []
    for cam in config.get("cameras", []):
        if not cam.get("enabled", True):
            continue
        channel = _match_csmart_channel(cam, csmart_channels) or {}
        snapshot_candidates = _snapshot_url_candidates(cam, channel)
        remote_snapshot_candidates = _raw_snapshot_url_candidates(cam, channel)
        cameras.append(
            {
                "id": str(cam.get("id")),
                "name": str(cam.get("name") or cam.get("id")),
                "area": str(cam.get("area") or "施工区域"),
                "rtmp_url": str(channel.get("flv") or cam.get("rtmp_url") or ""),
                "snapshot_url": snapshot_candidates[0] if snapshot_candidates else "",
                "snapshot_remote_url": remote_snapshot_candidates[0] if remote_snapshot_candidates else "",
                "snapshot_url_candidates": snapshot_candidates,
            }
        )
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
    inspection_prompt: str | None = None,
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
        summary = await nightly.run_patrol(
            vlm_enabled=vlm_enabled,
            camera_filter=camera_id,
            inspection_prompt=inspection_prompt,
        )
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
