from __future__ import annotations

import asyncio
import base64
import io
import json
import re
from typing import Any

import httpx
from PIL import Image
from pydantic import BaseModel, Field

from ..config import settings
from ..models import ToolResult
from ..tasks import new_task_id, record_task_event


# ── Request models ──────────────────────────────────────────────


class SecureEyeCropAnalyzeRequest(BaseModel):
    image_path: str
    bbox: list[float]  # [x1, y1, x2, y2]
    label: str
    confidence: float
    padding_ratio: float = 0.15
    context: str = ""


class SecureEyeBatchAnalyzeRequest(BaseModel):
    image_path: str
    crops: list[dict] = Field(default_factory=list)
    max_concurrency: int | None = None
    context: str = ""


class SecureEyeMergeRequest(BaseModel):
    yolo_detections: list[dict] = Field(default_factory=list)
    vlm_results: list[dict] = Field(default_factory=list)
    iou_threshold: float = 0.7


# ── ROI crop ────────────────────────────────────────────────────


def crop_roi(
    image_path: str,
    bbox: list[float],
    padding_ratio: float = 0.15,
    target_size: int = 640,
) -> str:
    """Crop the ROI region from the source image per *bbox* [x1,y1,x2,y2],
    expand by *padding_ratio* on all sides (clamped to image bounds),
    resize to *target_size* × *target_size*, and return a base64-encoded JPEG string.
    """
    img = Image.open(image_path).convert("RGB")
    img_w, img_h = img.size

    x1, y1, x2, y2 = bbox
    w = x2 - x1
    h = y2 - y1

    pad_w = w * padding_ratio
    pad_h = h * padding_ratio

    crop_x1 = max(0, int(x1 - pad_w))
    crop_y1 = max(0, int(y1 - pad_h))
    crop_x2 = min(img_w, int(x2 + pad_w))
    crop_y2 = min(img_h, int(y2 + pad_h))

    cropped = img.crop((crop_x1, crop_y1, crop_x2, crop_y2))
    cropped = cropped.resize((target_size, target_size), Image.LANCZOS)

    buf = io.BytesIO()
    cropped.save(buf, format="JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode("ascii")


# ── IoU ─────────────────────────────────────────────────────────


def _compute_iou(box_a: list[float], box_b: list[float]) -> float:
    """Compute Intersection over Union of two boxes in [x1, y1, x2, y2] format."""
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter_area

    if union <= 0:
        return 0.0
    return inter_area / union


# ── VLM API call ────────────────────────────────────────────────


def _build_vlm_prompt(label: str, context: str = "") -> str:
    ctx_part = f"区域信息：{context}。" if context else ""
    return (
        f"图中显示的是工地现场，检测类别为{label}。{ctx_part}"
        "请判断该区域的安全风险等级(low/medium/high/critical)和建议处置措施。"
        "请用JSON格式返回: {\"description\": \"...\", \"severity\": \"...\", \"suggested_action\": \"...\"}"
    )


def _parse_vlm_json(raw_text: str) -> dict[str, Any]:
    """Best-effort extraction of a JSON object from the LLM response text."""
    # Try direct parse first
    try:
        return json.loads(raw_text)
    except (json.JSONDecodeError, TypeError):
        pass

    # Try to find a JSON block in the text
    match = re.search(r"\{[^{}]*\}", raw_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Fallback: return a minimal default
    return {
        "description": raw_text.strip()[:200] if raw_text else "VLM analysis unavailable",
        "severity": "medium",
        "suggested_action": "请人工复核",
    }


async def _call_vlm_api(base64_image: str, prompt: str) -> dict[str, Any]:
    """Call the VLM chat-completions API and return parsed JSON."""
    url = f"{settings.secureeye_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.secureeye_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.secureeye_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                    },
                ],
            }
        ],
    }

    async with httpx.AsyncClient(timeout=settings.secureeye_timeout_seconds) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        result = response.json()

    content = ""
    choices = result.get("choices", [])
    if choices and isinstance(choices, list):
        message = choices[0].get("message", {})
        content = message.get("content", "")

    parsed = _parse_vlm_json(content)
    # Ensure required keys exist
    parsed.setdefault("description", "VLM analysis completed")
    parsed.setdefault("severity", "medium")
    parsed.setdefault("suggested_action", "请人工复核")
    parsed["source"] = "vlm"
    return parsed


# ── Single-crop analysis ────────────────────────────────────────


async def analyze_crop(req: SecureEyeCropAnalyzeRequest) -> ToolResult:
    """Crop the ROI for a single detection, call VLM, and return the enriched result."""
    task_id = new_task_id("secureeye_crop")

    try:
        b64_img = crop_roi(req.image_path, req.bbox, req.padding_ratio)
    except Exception as exc:
        record_task_event(task_id, {"tool": "secureeye_analyze_crop", "status": "crop_failed", "error": str(exc)})
        return ToolResult(
            ok=False,
            tool="secureeye_analyze_crop",
            task_id=task_id,
            summary=f"ROI crop failed: {exc}",
            error=str(exc),
        )

    prompt = _build_vlm_prompt(req.label, req.context)
    record_task_event(task_id, {"tool": "secureeye_analyze_crop", "status": "vlm_calling", "label": req.label})

    try:
        vlm_result = await _call_vlm_api(b64_img, prompt)
    except Exception as exc:
        record_task_event(task_id, {"tool": "secureeye_analyze_crop", "status": "vlm_failed", "error": str(exc)})
        # Fallback: return a YOLO-only result
        fallback = {
            "bbox": req.bbox,
            "label": req.label,
            "confidence": req.confidence,
            "source": "yolo",
            "description": f"YOLO检测到{req.label}，VLM分析不可用",
            "severity": "medium",
            "suggested_action": "请人工复核",
        }
        return ToolResult(
            ok=True,
            tool="secureeye_analyze_crop",
            task_id=task_id,
            summary=f"VLM unavailable, returned YOLO fallback for {req.label}.",
            data=fallback,
            logs=[f"VLM error: {exc}"],
        )

    merged = {
        "bbox": req.bbox,
        "label": req.label,
        "confidence": req.confidence,
        "source": "vlm",
        "description": vlm_result.get("description", ""),
        "severity": vlm_result.get("severity", "medium"),
        "suggested_action": vlm_result.get("suggested_action", ""),
    }
    record_task_event(task_id, {"tool": "secureeye_analyze_crop", "status": "done", "label": req.label})

    return ToolResult(
        ok=True,
        tool="secureeye_analyze_crop",
        task_id=task_id,
        summary=f"VLM analysis completed for {req.label}.",
        data=merged,
    )


# ── Batch analysis ──────────────────────────────────────────────


async def analyze_batch(req: SecureEyeBatchAnalyzeRequest) -> ToolResult:
    """Concurrently analyze multiple crops with a semaphore for concurrency control."""
    task_id = new_task_id("secureeye_batch")

    if not req.crops:
        return ToolResult(
            ok=True,
            tool="secureeye_analyze_batch",
            task_id=task_id,
            summary="No crops to analyze.",
            data={"results": [], "count": 0},
        )

    max_conc = req.max_concurrency or settings.secureeye_max_concurrency
    semaphore = asyncio.Semaphore(max_conc)
    record_task_event(task_id, {"tool": "secureeye_analyze_batch", "status": "running", "crop_count": len(req.crops)})

    async def _analyze_one(crop: dict, index: int) -> dict:
        crop_req = SecureEyeCropAnalyzeRequest(
            image_path=req.image_path,
            bbox=crop.get("bbox", [0, 0, 0, 0]),
            label=crop.get("label", "unknown"),
            confidence=float(crop.get("confidence", 0.0)),
            padding_ratio=float(crop.get("padding_ratio", 0.15)),
            context=req.context,
        )
        async with semaphore:
            result = await analyze_crop(crop_req)

        data = result.data if result.ok else {
            "bbox": crop.get("bbox", [0, 0, 0, 0]),
            "label": crop.get("label", "unknown"),
            "confidence": float(crop.get("confidence", 0.0)),
            "source": "yolo",
            "description": f"VLM analysis failed for {crop.get('label', 'unknown')}",
            "severity": "medium",
            "suggested_action": "请人工复核",
        }
        data["crop_id"] = crop.get("id", f"c{index}")
        return data

    results = await asyncio.gather(*[_analyze_one(c, i) for i, c in enumerate(req.crops)])

    record_task_event(task_id, {"tool": "secureeye_analyze_batch", "status": "done", "result_count": len(results)})

    return ToolResult(
        ok=True,
        tool="secureeye_analyze_batch",
        task_id=task_id,
        summary=f"Batch VLM analysis completed for {len(results)} crops.",
        data={"results": results, "count": len(results)},
    )


# ── Merge YOLO + VLM results ────────────────────────────────────


def merge_results(req: SecureEyeMergeRequest) -> ToolResult:
    """Merge YOLO detections with VLM-enriched results using IoU matching.

    Rules:
    - IoU > threshold → same target; VLM's description/severity/suggested_action overrides YOLO → source="hybrid"
    - YOLO conf >= 0.85 with no VLM match → keep YOLO original → source="yolo"
    - Remaining YOLO detections with no VLM match → source="yolo"
    - VLM results with no YOLO match → source="vlm"
    """
    task_id = new_task_id("secureeye_merge")

    yolo_dets = req.yolo_detections
    vlm_dets = req.vlm_results
    threshold = req.iou_threshold

    merged: list[dict[str, Any]] = []
    matched_vlm_indices: set[int] = set()

    for yolo_det in yolo_dets:
        yolo_bbox = yolo_det.get("bbox") or yolo_det.get("bbox_xyxy") or [0, 0, 0, 0]
        yolo_label = yolo_det.get("label") or yolo_det.get("class_name") or "unknown"
        yolo_conf = float(yolo_det.get("confidence", 0.0))

        best_iou = 0.0
        best_vlm_idx = -1
        for vi, vlm_det in enumerate(vlm_dets):
            if vi in matched_vlm_indices:
                continue
            vlm_bbox = vlm_det.get("bbox", [0, 0, 0, 0])
            iou = _compute_iou(yolo_bbox, vlm_bbox)
            if iou > best_iou:
                best_iou = iou
                best_vlm_idx = vi

        if best_vlm_idx >= 0 and best_iou > threshold:
            vlm_det = vlm_dets[best_vlm_idx]
            matched_vlm_indices.add(best_vlm_idx)
            merged.append({
                "bbox": yolo_bbox,
                "label": yolo_label,
                "confidence": yolo_conf,
                "source": "hybrid",
                "description": vlm_det.get("description", ""),
                "severity": vlm_det.get("severity", "medium"),
                "suggested_action": vlm_det.get("suggested_action", ""),
            })
        else:
            # No VLM match — keep YOLO original
            merged.append({
                "bbox": yolo_bbox,
                "label": yolo_label,
                "confidence": yolo_conf,
                "source": "yolo",
                "description": yolo_det.get("description", f"YOLO检测到{yolo_label}"),
                "severity": yolo_det.get("severity", "medium"),
                "suggested_action": yolo_det.get("suggested_action", "请人工复核"),
            })

    # Add unmatched VLM results
    for vi, vlm_det in enumerate(vlm_dets):
        if vi not in matched_vlm_indices:
            merged.append({
                "bbox": vlm_det.get("bbox", [0, 0, 0, 0]),
                "label": vlm_det.get("label", "unknown"),
                "confidence": float(vlm_det.get("confidence", 0.0)),
                "source": "vlm",
                "description": vlm_det.get("description", ""),
                "severity": vlm_det.get("severity", "medium"),
                "suggested_action": vlm_det.get("suggested_action", ""),
            })

    record_task_event(task_id, {
        "tool": "secureeye_merge_results",
        "status": "done",
        "yolo_count": len(yolo_dets),
        "vlm_count": len(vlm_dets),
        "merged_count": len(merged),
    })

    return ToolResult(
        ok=True,
        tool="secureeye_merge_results",
        task_id=task_id,
        summary=f"Merged {len(yolo_dets)} YOLO + {len(vlm_dets)} VLM → {len(merged)} detections.",
        data={"detections": merged, "count": len(merged)},
    )
