from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ..models import ToolResult
from .case_management import SafetyCaseCreateRequest, create_safety_case
from .rtmp import RtmpSnapshotRequest, run_rtmp_snapshot
from .safety import VlmHazardIngestRequest, ingest_vlm_hazards
from .vlm import VlmDetectRequest, run_vlm_detect


class CameraSnapshotRequest(BaseModel):
    url: str | None = None
    count: int = 1
    interval: float = 5
    prefix: str = "camera_snapshot"


class VlmBatchRequest(BaseModel):
    source: str
    conf: float | None = None
    device: str | None = None
    worker_only: bool = False
    machinery_only: bool = False


class VlmHazardClassifyRequest(BaseModel):
    detections: dict[str, Any] | None = None
    vlm_result_path: str | None = None
    task_id: str | None = None
    image_path: str | None = None
    area: str | None = None
    contractor: str | None = None


class VlmCaseCreateRequest(VlmHazardClassifyRequest):
    description: str | None = None


class VlmBeforeAfterCompareRequest(BaseModel):
    before_image: str
    after_image: str
    notes: str | None = None


class CameraPatrolScheduleRequest(BaseModel):
    name: str
    camera_urls: list[str] = Field(default_factory=list)
    cron: str = "0 8 * * *"
    enabled: bool = False


def capture_camera_snapshot(req: CameraSnapshotRequest) -> ToolResult:
    return run_rtmp_snapshot(RtmpSnapshotRequest(url=req.url, count=req.count, interval=req.interval, prefix=req.prefix))


def run_vlm_detection_batch(req: VlmBatchRequest) -> ToolResult:
    return run_vlm_detect(
        VlmDetectRequest(
            source=req.source,
            conf=req.conf,
            device=req.device,
            worker_only=req.worker_only,
            machinery_only=req.machinery_only,
        )
    )


def classify_vlm_hazard(req: VlmHazardClassifyRequest) -> ToolResult:
    return ingest_vlm_hazards(
        VlmHazardIngestRequest(
            detections=req.detections,
            vlm_result_path=req.vlm_result_path,
            task_id=req.task_id,
            image_path=req.image_path,
            area=req.area,
            contractor=req.contractor,
            persist=True,
        )
    )


def create_case_from_vlm(req: VlmCaseCreateRequest) -> ToolResult:
    classified = classify_vlm_hazard(req)
    description = req.description or classified.summary or "VLM visual safety hazard candidate"
    case = create_safety_case(
        SafetyCaseCreateRequest(
            description=description,
            scene="VLM视觉隐患",
            risk_level="medium",
            area=req.area,
            contractor=req.contractor,
            source_type="vlm",
            source_id=req.task_id or req.image_path or req.vlm_result_path,
            recommended_action="请安全主任复核图片识别结果，并决定是否发出整改通知。",
        )
    )
    return ToolResult(
        ok=True,
        tool="create_case_from_vlm",
        summary="Created a safety case from VLM classification.",
        data={"classification": classified.model_dump(), "case": case.model_dump()},
    )


def compare_vlm_before_after(req: VlmBeforeAfterCompareRequest) -> ToolResult:
    before_exists = Path(req.before_image).exists()
    after_exists = Path(req.after_image).exists()
    return ToolResult(
        ok=True,
        tool="compare_vlm_before_after",
        summary="Placeholder visual comparison. Real image diff/VLM comparison will be wired later.",
        data={"before_exists": before_exists, "after_exists": after_exists, "notes": req.notes, "requires_human_review": True},
    )


def schedule_camera_patrol(req: CameraPatrolScheduleRequest) -> ToolResult:
    return ToolResult(
        ok=True,
        tool="schedule_camera_patrol",
        summary="Camera patrol schedule placeholder created. Real scheduler will be wired later.",
        data=req.model_dump(),
    )
