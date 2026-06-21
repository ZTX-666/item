from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from ..config import settings
from ..models import ToolFile, ToolResult
from ..runner import CommandError, run_command
from ..tasks import copy_input_file, new_task_id, record_task_event, task_dir


class VlmDetectRequest(BaseModel):
    source: str
    conf: float | None = Field(default=None, ge=0.0, le=1.0)
    device: str | None = None
    worker_only: bool = False
    machinery_only: bool = False
    save_img: bool = True
    export_json: bool = True
    timeout_seconds: int = Field(default=900, ge=30, le=7200)


def _json_summary(json_path: Path) -> tuple[str, dict]:
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    images = payload.get("images", [])
    image_count = len(images)
    detection_count = sum(int(item.get("detection_count", 0)) for item in images)
    summary = f"VLM 检测完成，共处理 {image_count} 张图片，发现 {detection_count} 个目标。"
    return summary, payload


def run_vlm_detect(req: VlmDetectRequest) -> ToolResult:
    task_id = new_task_id("vlm")
    base = task_dir(task_id)
    out_dir = base / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    source_path = Path(req.source)
    source_for_script = source_path
    if source_path.is_file():
        source_for_script = copy_input_file(source_path, task_id)

    command = [
        settings.vlm_python,
        str(settings.vlm_detection_dir / "detect.py"),
        "--source",
        str(source_for_script),
        "--out",
        str(out_dir),
    ]
    if req.save_img:
        command.append("--save-img")
    if req.export_json:
        command.append("--export-json")
    if req.conf is not None:
        command.extend(["--conf", str(req.conf)])
    if req.device:
        command.extend(["--device", req.device])
    if req.worker_only:
        command.append("--worker-only")
    if req.machinery_only:
        command.append("--machinery-only")

    record_task_event(task_id, {"tool": "vlm_detect", "status": "running", "source": str(source_path)})
    try:
        result = run_command(command, cwd=settings.vlm_detection_dir, timeout=req.timeout_seconds)
    except CommandError as exc:
        record_task_event(task_id, {"tool": "vlm_detect", "status": "failed", "stderr": exc.stderr})
        return ToolResult(
            ok=False,
            tool="vlm_detect",
            task_id=task_id,
            summary="VLM 检测失败。",
            logs=[exc.stdout, exc.stderr],
            error=str(exc),
        )

    files: list[ToolFile] = []
    for p in sorted((out_dir / "images").glob("*")):
        if p.is_file():
            files.append(ToolFile(path=str(p), name=p.name, kind="image"))

    json_payload: dict = {}
    json_files = sorted(out_dir.glob("detections_*.json"))
    if json_files:
        json_path = json_files[-1]
        files.append(ToolFile(path=str(json_path), name=json_path.name, kind="json", mime_type="application/json"))
        summary, json_payload = _json_summary(json_path)
    else:
        summary = "VLM 检测完成，但未生成 JSON 文件。"

    record_task_event(task_id, {"tool": "vlm_detect", "status": "done", "file_count": len(files)})
    return ToolResult(
        ok=True,
        tool="vlm_detect",
        task_id=task_id,
        summary=summary,
        files=files,
        data={
            "source": str(source_path),
            "output_dir": str(out_dir),
            "detections": json_payload,
        },
        logs=[result.stdout, result.stderr],
    )
