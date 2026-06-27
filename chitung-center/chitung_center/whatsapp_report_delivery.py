from __future__ import annotations

import shlex
import shutil
from pathlib import Path
from typing import Any

from chitung_center.config import settings
from chitung_center.toolbox_client import toolbox_client
from chitung_center.visual_patrol_batch_service import resolve_patrol_file


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def collect_patrol_evidence_images(patrol: dict[str, Any], *, max_images: int = 8) -> list[dict[str, str]]:
    cameras = patrol.get("cameras") if isinstance(patrol.get("cameras"), list) else []
    ranked: list[tuple[int, dict[str, str]]] = []
    for camera in cameras:
        if not isinstance(camera, dict):
            continue
        path = resolve_camera_image_path(camera)
        if path is None:
            continue
        detection_count = _camera_detection_count(camera)
        camera_name = str(camera.get("camera_name") or camera.get("camera_id") or "摄像头")
        ranked.append(
            (
                detection_count,
                {
                    "path": str(path),
                    "camera_id": str(camera.get("camera_id") or ""),
                    "camera_name": camera_name,
                    "caption": f"{camera_name} · 检测标注图"
                    + (f"（{detection_count} 个目标）" if detection_count else ""),
                    "detection_count": str(detection_count),
                },
            )
        )

    ranked.sort(key=lambda item: (-item[0], item[1]["camera_name"]))
    selected: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    for _, item in ranked:
        if item["path"] in seen_paths:
            continue
        seen_paths.add(item["path"])
        selected.append(item)
        if len(selected) >= max_images:
            break

    if selected:
        return selected

    fallback = _pick_any_patrol_image(patrol)
    if fallback:
        return [
            {
                "path": str(fallback),
                "camera_id": "",
                "camera_name": "巡检",
                "caption": "巡检标注图",
                "detection_count": "0",
            }
        ]
    return []


def persist_evidence_images(report_id: str, images: list[dict[str, str]]) -> list[dict[str, str]]:
    if not images:
        return []
    out_dir = settings.chitung_data_dir / "detection_reports" / report_id / "images"
    out_dir.mkdir(parents=True, exist_ok=True)
    persisted: list[dict[str, str]] = []
    for index, item in enumerate(images, start=1):
        src = Path(item["path"])
        if not src.exists() or src.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        camera_id = item.get("camera_id") or f"cam-{index}"
        dest = out_dir / f"{index:02d}_{camera_id}{src.suffix.lower()}"
        shutil.copy2(src, dest)
        persisted.append({**item, "path": str(dest), "persisted_path": str(dest)})
    return persisted


def resolve_camera_image_path(camera: dict[str, Any]) -> Path | None:
    patrol_id = str(camera.get("patrol_id") or "").strip()
    camera_id = str(camera.get("camera_id") or "").strip()
    if patrol_id and camera_id:
        for filename in (f"{camera_id}_annotated.jpg", f"{camera_id}_snapshot.jpg"):
            resolved = resolve_patrol_file(patrol_id, filename)
            if resolved and resolved.suffix.lower() in IMAGE_SUFFIXES:
                return resolved

    for key in ("annotated_path", "snapshot_path"):
        raw = str(camera.get(key) or "").strip()
        if not raw:
            continue
        path = Path(raw)
        if path.exists() and path.suffix.lower() in IMAGE_SUFFIXES:
            return path
    return None


def _pick_any_patrol_image(patrol: dict[str, Any]) -> Path | None:
    cameras = patrol.get("cameras") if isinstance(patrol.get("cameras"), list) else []
    for camera in cameras:
        if isinstance(camera, dict):
            path = resolve_camera_image_path(camera)
            if path:
                return path
    for key in ("annotated_path", "snapshot_path"):
        path = Path(str(patrol.get(key) or ""))
        if path.exists() and path.suffix.lower() in IMAGE_SUFFIXES:
            return path
    return None


def _camera_detection_count(camera: dict[str, Any]) -> int:
    detections = camera.get("detections")
    if isinstance(detections, list):
        return len(detections)
    summary = camera.get("summary")
    if isinstance(summary, dict):
        return int(summary.get("detection_count") or 0)
    return 0


async def send_whatsapp_text(*, chat: str, text: str, confirmed_by: str) -> dict[str, Any]:
    try:
        result = await toolbox_client.call_tool(
            "whatsapp_send_text_confirmed",
            {"chat": chat, "text": text, "confirmed": True, "confirmed_by": confirmed_by},
        )
        if result.get("ok"):
            return result
    except Exception as exc:  # noqa: BLE001
        fallback = _run_wacli_send_text(chat, text)
        fallback["toolbox_error"] = str(exc)
        return fallback

    fallback = _run_wacli_send_text(chat, text)
    fallback["toolbox_result"] = result
    return fallback if fallback.get("ok") else result


async def send_whatsapp_file(
    *,
    chat: str,
    file_path: str,
    caption: str = "",
    confirmed_by: str,
) -> dict[str, Any]:
    path = Path(file_path)
    if not path.exists() or path.suffix.lower() not in IMAGE_SUFFIXES:
        return {
            "ok": False,
            "tool": "whatsapp_send_file_confirmed",
            "summary": f"附件不存在或格式不支持：{file_path}",
            "error": "invalid_attachment",
        }
    try:
        result = await toolbox_client.call_tool(
            "whatsapp_send_file_confirmed",
            {
                "chat": chat,
                "file_path": str(path),
                "caption": caption,
                "confirmed": True,
                "confirmed_by": confirmed_by,
            },
        )
        if result.get("ok"):
            return result
    except Exception as exc:  # noqa: BLE001
        fallback = _run_wacli_send_file(chat, str(path), caption)
        fallback["toolbox_error"] = str(exc)
        return fallback

    fallback = _run_wacli_send_file(chat, str(path), caption)
    fallback["toolbox_result"] = result
    return fallback if fallback.get("ok") else result


async def deliver_whatsapp_detection_report(
    *,
    chat: str,
    text: str,
    attachments: list[dict[str, str]],
    confirmed_by: str,
) -> dict[str, Any]:
    text_result = await send_whatsapp_text(chat=chat, text=text, confirmed_by=confirmed_by)
    file_results: list[dict[str, Any]] = []
    for item in attachments:
        file_results.append(
            await send_whatsapp_file(
                chat=chat,
                file_path=item["path"],
                caption=str(item.get("caption") or "检测标注图"),
                confirmed_by=confirmed_by,
            )
        )
    files_ok = all(result.get("ok") for result in file_results) if file_results else True
    return {
        "ok": bool(text_result.get("ok")) and files_ok,
        "summary": (
            f"已发送文字报告及 {sum(1 for r in file_results if r.get('ok'))}/{len(file_results)} 张检测图。"
            if file_results
            else "已发送文字报告（无可用检测图）。"
        ),
        "text_result": text_result,
        "file_results": file_results,
        "attachment_count": len(file_results),
    }


def _run_wacli_send_text(chat: str, text: str) -> dict[str, Any]:
    from chitung_center.whatsapp_local_service import run_whatsapp_command

    args_text = shlex.join(["send", "text", "--to", chat, "--message", text])
    result = run_whatsapp_command(args_text, read_only=False, timeout_seconds=90)
    return {
        "ok": bool(result.get("ok")),
        "tool": "whatsapp_send_text_confirmed",
        "summary": result.get("summary") or "wacli 本地发送文字完成。",
        "data": result.get("data") or {},
        "delivery_mode": "local_wacli_fallback",
        "error": result.get("error"),
    }


def _run_wacli_send_file(chat: str, file_path: str, caption: str) -> dict[str, Any]:
    from chitung_center.whatsapp_local_service import run_whatsapp_command

    args = ["send", "file", "--to", chat, "--file", file_path]
    if caption.strip():
        args.extend(["--caption", caption.strip()])
    result = run_whatsapp_command(shlex.join(args), read_only=False, timeout_seconds=120)
    return {
        "ok": bool(result.get("ok")),
        "tool": "whatsapp_send_file_confirmed",
        "summary": result.get("summary") or "wacli 本地发送文件完成。",
        "data": result.get("data") or {},
        "delivery_mode": "local_wacli_fallback",
        "error": result.get("error"),
    }
